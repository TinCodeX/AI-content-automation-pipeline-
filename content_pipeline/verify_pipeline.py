"""End-to-End Smoke and Verification Test Suite for Production Pipeline.

Validates the complete content automation flow:
1. Novel topic execution, vector embedding, and multi-channel file export
2. Verification of generated deliverables on disk (.json, .md)
3. Immediate duplicate rejection on re-running identical topic
4. Force override verification (--force)
5. Webhook receiver simulation check
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import threading
import time
from typing import Any, Dict, List, Tuple

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

from config import get_settings
from memory.vector_store import ContentMemoryStore
from pipeline import run_content_pipeline
from triggers.webhook_server import app

console = Console()


def ensure_live_server(host: str, port: int) -> Tuple[bool, Optional[uvicorn.Server]]:
    """Ensure a live FastAPI server is running for webhook simulation."""
    url = f"http://{host}:{port}/health"
    try:
        r = requests.get(url, timeout=1.5)
        if r.status_code == 200:
            return False, None
    except requests.exceptions.RequestException:
        pass

    config = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        log_level="error",
        loop="asyncio",
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    for _ in range(30):
        time.sleep(0.2)
        try:
            r = requests.get(url, timeout=1.0)
            if r.status_code == 200:
                return True, server
        except requests.exceptions.RequestException:
            pass

    return False, server


def run_pipeline_verification() -> int:
    """Execute end-to-end integration and smoke test suite."""
    console.rule("[bold cyan]End-to-End Pipeline Verification Suite[/bold cyan]")
    settings = get_settings()

    # Use isolated test collection
    test_memory = ContentMemoryStore(
        collection_name="test_pipeline_e2e_collection",
        is_ephemeral=True,
    )
    test_memory.clear()

    deliverables_test_dir = BASE_DIR / "deliverables" / "_test_run"
    topic = "Real-time Telemetry with eBPF and Python"

    verification_checks: List[Tuple[str, str, bool, str]] = []

    # -------------------------------------------------------------------------
    # Test 1: Novel Topic Execution & Deliverables Export
    # -------------------------------------------------------------------------
    console.print("\n[bold cyan]Phase 1: Novel Topic Generation & Export[/bold cyan]")
    res_novel = run_content_pipeline(
        topic=topic,
        channels=["blog", "twitter", "linkedin"],
        force=False,
        mock=True,
        memory_store=test_memory,
        output_dir=deliverables_test_dir,
    )

    novel_passed = (
        res_novel.get("status") == "completed"
        and bool(res_novel.get("job_id"))
        and res_novel.get("word_count", 0) > 100
        and len(res_novel.get("exported_files", {})) >= 3
    )
    verification_checks.append(
        (
            "1. Novel Topic Pipeline",
            res_novel.get("status", ""),
            novel_passed,
            f"Generated {res_novel.get('word_count')} words across 3 channels",
        )
    )

    # Verify physical file existence on disk
    files_dict = res_novel.get("exported_files", {})
    all_files_exist = True
    for key, fpath in files_dict.items():
        p = Path(fpath)
        if not p.exists() or p.stat().st_size == 0:
            all_files_exist = False

    verification_checks.append(
        (
            "2. Artifact Files on Disk",
            "Files Verified" if all_files_exist else "Missing Files",
            all_files_exist,
            f"Verified {len(files_dict)} files (.json, .md) with non-zero bytes",
        )
    )

    # -------------------------------------------------------------------------
    # Test 2: Duplicate Rejection
    # -------------------------------------------------------------------------
    console.print("\n[bold cyan]Phase 2: Semantic Deduplication Gating[/bold cyan]")
    res_dup = run_content_pipeline(
        topic=topic,
        channels=["blog", "twitter", "linkedin"],
        force=False,
        mock=True,
        memory_store=test_memory,
        output_dir=deliverables_test_dir,
    )

    dup_passed = (
        res_dup.get("status") == "duplicate_rejected"
        and res_dup.get("match_data", {}).get("similarity", 0.0) >= 0.82
    )
    sim = res_dup.get("match_data", {}).get("similarity", 0.0)
    verification_checks.append(
        (
            "3. Duplicate Rejection Gate",
            res_dup.get("status", ""),
            dup_passed,
            f"Rejected duplicate: similarity {sim:.2%} >= 82% threshold",
        )
    )

    # -------------------------------------------------------------------------
    # Test 3: Force Override
    # -------------------------------------------------------------------------
    console.print("\n[bold cyan]Phase 3: Force Override Execution[/bold cyan]")
    res_force = run_content_pipeline(
        topic=topic,
        channels=["blog", "twitter", "linkedin"],
        force=True,
        mock=True,
        memory_store=test_memory,
        output_dir=deliverables_test_dir,
    )

    force_passed = res_force.get("status") == "completed"
    verification_checks.append(
        (
            "4. Force Override Execution",
            res_force.get("status", ""),
            force_passed,
            "--force successfully bypassed deduplication block",
        )
    )

    # -------------------------------------------------------------------------
    # Test 4: Webhook Ingestion Integration
    # -------------------------------------------------------------------------
    console.print("\n[bold cyan]Phase 4: Webhook Simulation Test[/bold cyan]")
    started_bg, server = ensure_live_server(settings.WEBHOOK_HOST, settings.WEBHOOK_PORT)
    webhook_passed = False
    try:
        url = settings.webhook_url
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Secret": settings.WEBHOOK_SECRET,
        }
        payload = {
            "topic": topic,
            "target_audience": "DevOps Engineers",
            "tone": "concise & practical",
            "channels": ["blog", "linkedin"],
        }
        r = requests.post(url, json=payload, headers=headers, timeout=5)
        webhook_passed = r.status_code == 202 and r.json().get("status") == "queued"
    except Exception as e:
        console.print(f"[yellow]Webhook request failed: {e}[/yellow]")
    finally:
        if started_bg and server:
            server.should_exit = True

    verification_checks.append(
        (
            "5. Webhook Ingestion API",
            "Status 202" if webhook_passed else "Failed",
            webhook_passed,
            "Accepted incoming trigger payload with 202 Queued response",
        )
    )

    # -------------------------------------------------------------------------
    # Render Diagnostic Results Table
    # -------------------------------------------------------------------------
    table = Table(title="End-to-End Pipeline Smoke Test Results", show_lines=True)
    table.add_column("Test Case", style="cyan bold", width=30)
    table.add_column("Outcome", justify="center", width=18)
    table.add_column("Result", justify="center", width=10)
    table.add_column("Details", style="white", width=46)

    all_passed = True
    for name, outcome, passed, details in verification_checks:
        if not passed:
            all_passed = False
        res_str = "[bold green]PASS[/bold green]" if passed else "[bold red]FAIL[/bold red]"
        table.add_row(name, outcome, res_str, details)

    console.print("\n")
    console.print(table)

    if all_passed:
        console.print(
            Panel(
                f"[bold green]ALL END-TO-END PIPELINE CHECKS PASSED "
                f"({len(verification_checks)}/{len(verification_checks)})![/bold green]\n"
                "The unified pipeline is production-ready across Ingestion, Deduplication, "
                "Generation, Serialization, and Webhook dispatch.",
                title="[bold green]Production Status: Ready[/bold green]",
                border_style="green",
            )
        )
        return 0
    else:
        console.print(
            Panel(
                "[bold red]ONE OR MORE END-TO-END PIPELINE CHECKS FAILED![/bold red]",
                title="[bold red]Production Status: Degraded[/bold red]",
                border_style="red",
            )
        )
        return 1


if __name__ == "__main__":
    sys.exit(run_pipeline_verification())
