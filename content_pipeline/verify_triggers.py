"""Verification and Diagnostic Test Suite for Dual-Trigger System.

Tests the FastAPI Webhook Receiver and APScheduler Dispatcher:
1. Header security verification (401 on missing or invalid secrets)
2. Validated payload receipt and 202 Accepted response with UUID job_id
3. Schema constraint validation (422 on invalid topics)
4. Health endpoint check (200 OK)
5. Scheduler dispatch integration test
6. Rich visual summary table and diagnostics report
"""

from __future__ import annotations

from pathlib import Path
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

# Ensure parent directory is in sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import requests
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
import uvicorn

from config import Settings, get_settings, print_settings_diagnostics
from triggers.scheduler import PipelineScheduler
from triggers.webhook_server import app

console = Console()


class LiveServerManager:
    """Helper to ensure a live HTTP server is running during test execution."""

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"
        self.server: Optional[uvicorn.Server] = None
        self.thread: Optional[threading.Thread] = None

    def is_server_online(self) -> bool:
        """Check if server responds on the configured port."""
        try:
            r = requests.get(f"{self.base_url}/health", timeout=1.5)
            return r.status_code == 200
        except requests.exceptions.RequestException:
            return False

    def start_background(self) -> bool:
        """Start an in-process Uvicorn server in a daemon thread if not already running."""
        if self.is_server_online():
            console.print(
                f"[cyan]Detected existing webhook server running at {self.base_url}.[/cyan]"
            )
            return False

        console.print(
            f"[yellow]No active server detected. "
            f"Spawning background test server on {self.base_url}...[/yellow]"
        )
        config = uvicorn.Config(
            app=app,
            host=self.host,
            port=self.port,
            log_level="error",
            loop="asyncio",
        )
        self.server = uvicorn.Server(config)
        self.thread = threading.Thread(target=self.server.run, daemon=True)
        self.thread.start()

        # Wait for server to come online
        for _ in range(30):
            time.sleep(0.2)
            if self.is_server_online():
                console.print(
                    f"[bold green][OK] Background test server is online at "
                    f"{self.base_url}.[/bold green]"
                )
                return True

        raise RuntimeError(f"Server failed to start within timeout at {self.base_url}")

    def stop(self) -> None:
        """Stop background server if one was started."""
        if self.server:
            self.server.should_exit = True
            if self.thread and self.thread.is_alive():
                self.thread.join(timeout=3)
            console.print("[dim]Background test server stopped.[/dim]")


def run_tests() -> int:
    """Execute end-to-end trigger verification tests and report results."""
    console.rule("[bold cyan]Dual-Trigger System Diagnostic Suite[/bold cyan]")

    settings = get_settings()
    print_settings_diagnostics(settings)

    server_manager = LiveServerManager(host=settings.WEBHOOK_HOST, port=settings.WEBHOOK_PORT)
    started_bg = server_manager.start_background()

    test_results: List[Tuple[str, str, int, int, bool, str]] = []

    def record(
        name: str,
        endpoint: str,
        expected_status: int,
        actual_status: int,
        passed: bool,
        notes: str,
    ) -> None:
        test_results.append((name, endpoint, expected_status, actual_status, passed, notes))

    base_url = server_manager.base_url
    trigger_url = f"{base_url}/webhook/content-trigger"

    try:
        # Test 1: Health Check Endpoint
        try:
            r = requests.get(f"{base_url}/health", timeout=5)
            passed = r.status_code == 200 and r.json().get("status") == "ok"
            record(
                "1. Health Probe Check",
                "/health",
                200,
                r.status_code,
                passed,
                "Status is healthy",
            )
        except Exception as e:
            record("1. Health Probe Check", "/health", 200, 0, False, str(e))

        # Test 2: Missing Webhook Secret Header
        try:
            payload = {"topic": "Security Testing Without Auth"}
            r = requests.post(trigger_url, json=payload, timeout=5)
            passed = r.status_code == 401
            record(
                "2. Auth - Missing Secret Header",
                "/webhook/content-trigger",
                401,
                r.status_code,
                passed,
                "Rejected missing header",
            )
        except Exception as e:
            record(
                "2. Auth - Missing Secret Header",
                "/webhook/content-trigger",
                401,
                0,
                False,
                str(e),
            )

        # Test 3: Invalid Webhook Secret Header
        try:
            payload = {"topic": "Security Testing With Invalid Key"}
            headers = {"X-Webhook-Secret": "definitely-invalid-key-999"}
            r = requests.post(trigger_url, json=payload, headers=headers, timeout=5)
            passed = r.status_code == 401
            record(
                "3. Auth - Invalid Secret Header",
                "/webhook/content-trigger",
                401,
                r.status_code,
                passed,
                "Rejected forged token",
            )
        except Exception as e:
            record(
                "3. Auth - Invalid Secret Header",
                "/webhook/content-trigger",
                401,
                0,
                False,
                str(e),
            )

        # Test 4: Valid Webhook Secret with Full Payload
        sample_job_id = None
        try:
            payload = {
                "topic": "Practical LLM Agents in Production: Patterns & Anti-patterns",
                "target_audience": "Junior to mid-level backend developers",
                "tone": "insightful & authoritative",
                "channels": ["blog", "twitter", "linkedin"],
                "metadata": {"test_run": True, "priority": "high"},
            }
            headers = {"X-Webhook-Secret": settings.WEBHOOK_SECRET}
            r = requests.post(trigger_url, json=payload, headers=headers, timeout=5)
            data = r.json() if r.status_code == 202 else {}
            sample_job_id = data.get("job_id")
            passed = (
                r.status_code == 202
                and data.get("status") == "queued"
                and bool(sample_job_id)
                and "timestamp" in data
                and data.get("topic") == payload["topic"]
            )
            record(
                "4. Webhook Ingestion - Full Payload",
                "/webhook/content-trigger",
                202,
                r.status_code,
                passed,
                f"Queued JobID: {sample_job_id[:8]}..." if sample_job_id else "No JobID",
            )
        except Exception as e:
            record(
                "4. Webhook Ingestion - Full Payload",
                "/webhook/content-trigger",
                202,
                0,
                False,
                str(e),
            )

        # Test 5: Authorization Bearer Token Fallback
        try:
            payload = {
                "topic": "Bearer Token Header Interoperability Test",
                "channels": ["linkedin"],
            }
            headers = {"Authorization": f"Bearer {settings.WEBHOOK_SECRET}"}
            r = requests.post(trigger_url, json=payload, headers=headers, timeout=5)
            data = r.json() if r.status_code == 202 else {}
            passed = r.status_code == 202 and data.get("status") == "queued"
            record(
                "5. Auth - Bearer Token Fallback",
                "/webhook/content-trigger",
                202,
                r.status_code,
                passed,
                "Accepted via Bearer header",
            )
        except Exception as e:
            record(
                "5. Auth - Bearer Token Fallback",
                "/webhook/content-trigger",
                202,
                0,
                False,
                str(e),
            )

        # Test 6: Default Values & Minimal Payload
        try:
            payload = {"topic": "Autonomous Agents Architecture"}
            headers = {"X-Webhook-Secret": settings.WEBHOOK_SECRET}
            r = requests.post(trigger_url, json=payload, headers=headers, timeout=5)
            data = r.json() if r.status_code == 202 else {}
            passed = (
                r.status_code == 202
                and data.get("channels") == ["blog", "twitter", "linkedin"]
                and data.get("tone") == "insightful & authoritative"
            )
            record(
                "6. Schema - Default Fields Applied",
                "/webhook/content-trigger",
                202,
                r.status_code,
                passed,
                "Default channels and tone set",
            )
        except Exception as e:
            record(
                "6. Schema - Default Fields Applied",
                "/webhook/content-trigger",
                202,
                0,
                False,
                str(e),
            )

        # Test 7: Schema Validation Error (Empty / Short Topic)
        try:
            payload = {"topic": "x"}  # Less than min_length=3
            headers = {"X-Webhook-Secret": settings.WEBHOOK_SECRET}
            r = requests.post(trigger_url, json=payload, headers=headers, timeout=5)
            passed = r.status_code == 422
            record(
                "7. Schema - Min Length Validation",
                "/webhook/content-trigger",
                422,
                r.status_code,
                passed,
                "Rejected topic < 3 chars",
            )
        except Exception as e:
            record(
                "7. Schema - Min Length Validation",
                "/webhook/content-trigger",
                422,
                0,
                False,
                str(e),
            )

        # Test 8: Scheduler Dispatcher Simulation
        try:
            scheduler = PipelineScheduler(settings=settings, blocking=False)
            dispatch_resp = scheduler.dispatch_webhook(
                topic="Automated Weekly Editorial Dispatch",
                target_audience="Engineering Leaders",
                tone="strategic & forward-looking",
                channels=["blog", "linkedin"],
            )
            passed = dispatch_resp is not None and dispatch_resp.get("status") == "queued"
            actual_code = 202 if passed else 500
            note = (
                f"Scheduler dispatched job {dispatch_resp.get('job_id', '')[:8]}..."
                if passed
                else "Dispatch failed"
            )
            record(
                "8. Scheduler Webhook Dispatch",
                "/webhook/content-trigger",
                202,
                actual_code,
                passed,
                note,
            )
        except Exception as e:
            record(
                "8. Scheduler Webhook Dispatch",
                "/webhook/content-trigger",
                202,
                0,
                False,
                str(e),
            )

    finally:
        if started_bg:
            server_manager.stop()

    # -------------------------------------------------------------------------
    # Render Diagnostic Table
    # -------------------------------------------------------------------------
    table = Table(title="Trigger Layer Verification Suite Results", show_lines=True)
    table.add_column("Test Case", style="cyan bold", width=34)
    table.add_column("Endpoint", style="dim", width=26)
    table.add_column("Expected", justify="center", width=10)
    table.add_column("Actual", justify="center", width=10)
    table.add_column("Result", justify="center", width=12)
    table.add_column("Notes", style="white", width=32)

    all_passed = True
    for name, endpoint, expected, actual, passed, notes in test_results:
        if not passed:
            all_passed = False
        res_str = "[bold green]PASS[/bold green]" if passed else "[bold red]FAIL[/bold red]"
        table.add_row(name, endpoint, str(expected), str(actual), res_str, notes)

    console.print(table)

    if all_passed:
        console.print(
            Panel(
                "[bold green]ALL DIAGNOSTIC TESTS PASSED SUCCESSFULLY (8/8)![/bold green]\n"
                "Dual-trigger system (FastAPI Webhook Server + APScheduler Dispatcher) "
                "is validated and production-ready.",
                title="[bold green]System Status: Operational[/bold green]",
                border_style="green",
            )
        )
        return 0
    else:
        console.print(
            Panel(
                "[bold red]ONE OR MORE DIAGNOSTIC TESTS FAILED![/bold red]\n"
                "Inspect the results table above to troubleshoot authentication, routing, "
                "or schema issues.",
                title="[bold red]System Status: Degraded[/bold red]",
                border_style="red",
            )
        )
        return 1


if __name__ == "__main__":
    sys.exit(run_tests())
