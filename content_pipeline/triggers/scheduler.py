"""Cron and Interval-based Scheduler for Content Automation Pipeline.

Dispatches scheduled and recurring content generation jobs either directly
to the FastAPI webhook endpoint via authenticated HTTP requests or through
custom pipeline handlers. Uses APScheduler for robust cron-style scheduling.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# Ensure parent directory is in sys.path for direct script execution
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
import requests
from rich.console import Console
from rich.table import Table

try:
    from config import Settings, get_settings
except ImportError:  # pragma: no cover
    from ..config import Settings, get_settings  # type: ignore

console = Console()


class PipelineScheduler:
    """Manages scheduled content generation triggers."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        blocking: bool = True,
    ):
        self.settings = settings or get_settings()
        self.blocking = blocking
        self.scheduler = (
            BlockingScheduler() if blocking else BackgroundScheduler()
        )

    def dispatch_webhook(
        self,
        topic: str,
        target_audience: Optional[str] = "Tech professionals & software developers",
        tone: Optional[str] = "insightful & authoritative",
        channels: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Dispatch a content trigger to the configured webhook endpoint via HTTP POST."""
        url = self.settings.webhook_url
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Secret": self.settings.WEBHOOK_SECRET,
        }
        payload = {
            "topic": topic,
            "target_audience": target_audience,
            "tone": tone,
            "channels": channels or ["blog", "twitter", "linkedin"],
            "metadata": {
                "source": "apscheduler_cron",
                "dispatched_at": datetime.now(timezone.utc).isoformat(),
                **(metadata or {}),
            },
        }

        try:
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=10,
            )
            if response.status_code == 202:
                data = response.json()
                console.print(
                    f"[bold green][OK] Scheduler Dispatched Successfully[/bold green] "
                    f"Job ID: [cyan]{data.get('job_id')}[/cyan] | Topic: '{topic}'"
                )
                return data
            else:
                console.print(
                    f"[bold red][ERR] Webhook dispatch failed[/bold red] "
                    f"Status: {response.status_code} Detail: {response.text}"
                )
                return None
        except requests.exceptions.RequestException as exc:
            console.print(
                f"[bold red][ERR] Connection error during dispatch to {url}:[/bold red] {exc}"
            )
            return None

    def add_cron_job(
        self,
        job_id: str,
        topic: str,
        cron_expr: str = "0 9 * * 1",  # Every Monday at 09:00 AM UTC
        target_audience: Optional[str] = None,
        tone: Optional[str] = None,
        channels: Optional[List[str]] = None,
    ) -> None:
        """Add a recurring content creation job using a standard 5-part cron expression.

        Format: minute hour day month day_of_week
        """
        parts = cron_expr.split()
        if len(parts) != 5:
            raise ValueError(f"Expected standard 5-field cron expression, got: '{cron_expr}'")

        trigger = CronTrigger.from_crontab(cron_expr, timezone="UTC")
        self.scheduler.add_job(
            func=self.dispatch_webhook,
            trigger=trigger,
            id=job_id,
            name=f"Cron: {topic}",
            replace_existing=True,
            kwargs={
                "topic": topic,
                "target_audience": target_audience,
                "tone": tone,
                "channels": channels,
                "metadata": {"job_id": job_id, "cron": cron_expr},
            },
        )
        console.print(
            f"[green]Registered Cron Job:[/green] [cyan]{job_id}[/cyan] -> "
            f"Cron: '{cron_expr}' | Topic: '{topic}'"
        )

    def add_interval_job(
        self,
        job_id: str,
        topic: str,
        seconds: Optional[int] = None,
        minutes: Optional[int] = None,
        hours: Optional[int] = None,
        days: Optional[int] = None,
        target_audience: Optional[str] = None,
        tone: Optional[str] = None,
        channels: Optional[List[str]] = None,
    ) -> None:
        """Add an interval-based trigger for testing or frequent recurring workflows."""
        trigger = IntervalTrigger(
            seconds=seconds or 0,
            minutes=minutes or 0,
            hours=hours or 0,
            days=days or 0,
            timezone="UTC",
        )
        self.scheduler.add_job(
            func=self.dispatch_webhook,
            trigger=trigger,
            id=job_id,
            name=f"Interval: {topic}",
            replace_existing=True,
            kwargs={
                "topic": topic,
                "target_audience": target_audience,
                "tone": tone,
                "channels": channels,
                "metadata": {"job_id": job_id, "interval_sec": seconds},
            },
        )
        console.print(
            f"[green]Registered Interval Job:[/green] [cyan]{job_id}[/cyan] -> "
            f"Every {seconds or 0}s/{minutes or 0}m/{hours or 0}h | Topic: '{topic}'"
        )

    def register_default_content_schedules(self) -> None:
        """Register default weekly editorial calendar jobs."""
        # 1. Monday Deep Dive
        self.add_cron_job(
            job_id="monday_deep_dive",
            topic="Practical LLM Agents in Production: Patterns & Anti-patterns",
            cron_expr="0 9 * * 1",  # Mondays at 09:00 UTC
            target_audience="Junior to mid-level backend developers",
            tone="insightful & authoritative",
            channels=["blog", "linkedin"],
        )

        # 2. Wednesday Hands-on Engineering Tutorial
        self.add_cron_job(
            job_id="wednesday_tutorial",
            topic="Building Autonomous Workflows with FastAPI and AI Microservices",
            cron_expr="0 14 * * 3",  # Wednesdays at 14:00 UTC
            target_audience="Full-stack engineers & AI practitioners",
            tone="step-by-step & educational",
            channels=["blog", "twitter"],
        )

        # 3. Friday Industry Round-up
        self.add_cron_job(
            job_id="friday_roundup",
            topic="AI Engineering Weekly Recap: Open Models, Benchmarks & Tooling",
            cron_expr="0 16 * * 5",  # Fridays at 16:00 UTC
            target_audience="Tech leaders, founders & engineers",
            tone="conversational & crisp",
            channels=["twitter", "linkedin"],
        )

    def print_jobs_table(self) -> None:
        """Display an overview of all registered scheduler jobs."""
        jobs = self.scheduler.get_jobs()
        table = Table(title="Pipeline Scheduler: Active Jobs", show_lines=True)
        table.add_column("Job ID", style="cyan bold")
        table.add_column("Job Name", style="white")
        table.add_column("Trigger Spec", style="yellow")
        table.add_column("Next Execution (UTC)", style="green")

        for job in jobs:
            table.add_row(
                job.id,
                job.name,
                str(job.trigger),
                str(job.next_run_time) if job.next_run_time else "Paused",
            )
        console.print(table)

    def start(self) -> None:
        """Start the scheduler loop."""
        self.print_jobs_table()
        console.print("[bold blue]Scheduler started. Press Ctrl+C to stop.[/bold blue]")
        try:
            self.scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            console.print("[yellow]Scheduler shutting down gracefully.[/yellow]")

    def stop(self) -> None:
        """Shutdown the scheduler if running."""
        if self.scheduler.running:
            self.scheduler.shutdown()


def main() -> None:
    """CLI entry point for running the scheduler or sending test dispatches."""
    parser = argparse.ArgumentParser(description="AI Content Pipeline Scheduler Runner")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Dispatch a single test trigger immediately without starting scheduler loop",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=None,
        help="Run recurring test dispatches every N seconds",
    )
    parser.add_argument(
        "--topic",
        type=str,
        default="Practical LLM Agents in Production",
        help="Topic for one-off or test dispatch",
    )
    args = parser.parse_args()

    scheduler = PipelineScheduler(blocking=True)

    if args.once:
        console.print(f"[cyan]Dispatching one-time content trigger for: '{args.topic}'...[/cyan]")
        scheduler.dispatch_webhook(
            topic=args.topic,
            target_audience="Software Engineers & AI Architects",
            tone="insightful & authoritative",
            channels=["blog", "twitter", "linkedin"],
        )
        return

    if args.interval:
        console.print(f"[cyan]Setting up recurring test interval of {args.interval}s...[/cyan]")
        scheduler.add_interval_job(
            job_id="interval_test_job",
            topic=args.topic,
            seconds=args.interval,
        )
    else:
        scheduler.register_default_content_schedules()

    scheduler.start()


if __name__ == "__main__":
    main()
