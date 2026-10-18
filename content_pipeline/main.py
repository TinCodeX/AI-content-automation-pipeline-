"""Production CLI runner and webhook simulator for Content Automation Pipeline.

Provides interactive wizard, CLI flag dispatch, semantic deduplication,
multi-channel file export, and n8n/Make webhook simulation.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import List

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
from rich.prompt import Confirm, Prompt
from rich.table import Table

from config import get_settings, print_settings_diagnostics
from pipeline import run_content_pipeline

console = Console()


def simulate_webhook_dispatch(
    topic: str,
    target_audience: str,
    tone: str,
    channels: List[str],
) -> bool:
    """Simulate an incoming n8n or Make trigger against the webhook server."""
    settings = get_settings()
    url = settings.webhook_url
    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Secret": settings.WEBHOOK_SECRET,
    }
    payload = {
        "topic": topic,
        "target_audience": target_audience,
        "tone": tone,
        "channels": channels,
        "metadata": {"caller": "main_cli_simulator", "env": settings.ENV},
    }

    console.print(
        f"[cyan]Dispatching simulated webhook payload to [bold]{url}[/bold]...[/cyan]"
    )

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=5)
        if resp.status_code == 202:
            data = resp.json()
            console.print(
                Panel(
                    f"[bold green]✔ Webhook Accepted (Status 202)![/bold green]\n"
                    f"Job ID: [cyan]{data.get('job_id')}[/cyan]\n"
                    f"Timestamp: [dim]{data.get('timestamp')}[/dim]\n"
                    f"Message: {data.get('message')}",
                    title="[bold green]Webhook Receiver Response[/bold green]",
                    border_style="green",
                )
            )
            return True
        else:
            console.print(
                f"[bold red]✘ Webhook rejected request (Status {resp.status_code}): "
                f"{resp.text}[/bold red]"
            )
            return False
    except requests.exceptions.RequestException as exc:
        console.print(
            f"[yellow]Notice: Could not connect to webhook server at {url}: {exc}\n"
            "Ensure server is running: uvicorn triggers.webhook_server:app --reload[/yellow]"
        )
        return False


def run_interactive_wizard() -> None:
    """Prompt the user interactively when no CLI arguments are supplied."""
    console.rule("[bold cyan]AI Content Automation Pipeline - Interactive Wizard[/bold cyan]")
    settings = get_settings()
    print_settings_diagnostics(settings)

    topic = Prompt.ask(
        "[bold cyan]Enter content topic or seed angle[/bold cyan]",
        default="Architecting Event-Driven LLM Workflows with Python",
    )

    audience = Prompt.ask(
        "[bold cyan]Target audience[/bold cyan]",
        default="Senior software engineers and AI platform architects",
    )

    tone = Prompt.ask(
        "[bold cyan]Tone and voice[/bold cyan]",
        default="insightful, pragmatic & authoritative",
    )

    channels_input = Prompt.ask(
        "[bold cyan]Channels to generate (comma-separated)[/bold cyan]",
        default="blog,twitter,linkedin",
    )
    channels = [c.strip().lower() for c in channels_input.split(",") if c.strip()]

    force = Confirm.ask(
        "[bold cyan]Force generation even if topic is semantically duplicate?[/bold cyan]",
        default=False,
    )

    mock = Confirm.ask(
        "[bold cyan]Run in offline mock mode (no API tokens consumed)?[/bold cyan]",
        default=(not settings.active_api_key or settings.active_api_key.startswith("your_")),
    )

    sim_webhook = Confirm.ask(
        "[bold cyan]Simulate incoming webhook dispatch before pipeline run?[/bold cyan]",
        default=False,
    )

    if sim_webhook:
        simulate_webhook_dispatch(topic, audience, tone, channels)

    result = run_content_pipeline(
        topic=topic,
        target_audience=audience,
        tone=tone,
        channels=channels,
        force=force,
        mock=mock,
    )

    render_pipeline_result(result)


def render_pipeline_result(result: dict) -> None:
    """Format and display pipeline outcome in a clean Rich summary table."""
    status = result.get("status", "unknown")
    table = Table(title="Pipeline Execution Summary", show_lines=True)
    table.add_column("Property", style="cyan bold", width=20)
    table.add_column("Value", style="white", width=60)

    status_str = (
        f"[bold green]{status.upper()}[/bold green]"
        if status == "completed"
        else f"[bold red]{status.upper()}[/bold red]"
    )
    table.add_row("Status", status_str)
    table.add_row("Job ID", str(result.get("job_id")))
    table.add_row("Topic", str(result.get("topic")))
    table.add_row("Word Count", f"{result.get('word_count', 0)} words")

    files = result.get("exported_files", {})
    if files:
        file_lines = "\n".join(f"• [cyan]{k}[/cyan]: {v}" for k, v in files.items())
        table.add_row("Exported Files", file_lines)
    else:
        table.add_row("Exported Files", "[dim]None (Execution aborted or duplicate)[/dim]")

    if result.get("match_data"):
        m = result["match_data"]
        match_info = (
            f"Existing: '{m.get('matched_topic')}' | "
            f"Similarity: {m.get('similarity', 0.0):.2%} | "
            f"Distance: {m.get('distance', 1.0):.4f}"
        )
        table.add_row("Deduplication Match", match_info)

    console.print(table)


def main() -> None:
    """Entry point for the Content Pipeline runner CLI."""
    parser = argparse.ArgumentParser(
        description="Multi-Channel AI Content Automation Pipeline Runner"
    )
    parser.add_argument(
        "-t", "--topic",
        type=str,
        default=None,
        help="Seed topic or headline to generate content for",
    )
    parser.add_argument(
        "-c", "--channels",
        type=str,
        default="blog,twitter,linkedin",
        help="Comma-separated target channels (default: blog,twitter,linkedin)",
    )
    parser.add_argument(
        "-a", "--audience",
        type=str,
        default="Junior to mid-level backend developers",
        help="Target audience demographic",
    )
    parser.add_argument(
        "--tone",
        type=str,
        default="insightful & authoritative",
        help="Voice and tone guidelines",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Bypass vector memory semantic deduplication check",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Generate realistic deterministic drafts without calling live LLMs",
    )
    parser.add_argument(
        "--simulate-webhook",
        action="store_true",
        help="Dispatch payload to live FastAPI webhook endpoint prior to generation",
    )

    args = parser.parse_args()

    # If no topic specified, launch interactive wizard
    if args.topic is None:
        run_interactive_wizard()
        return

    channels = [c.strip().lower() for c in args.channels.split(",") if c.strip()]

    if args.simulate_webhook:
        simulate_webhook_dispatch(args.topic, args.audience, args.tone, channels)

    result = run_content_pipeline(
        topic=args.topic,
        target_audience=args.audience,
        tone=args.tone,
        channels=channels,
        force=args.force,
        mock=args.mock,
    )

    render_pipeline_result(result)


if __name__ == "__main__":
    main()
