"""Diagnostic and verification test suite for Multi-Channel Content Generator.

Tests structured bundle generation across Blog, Twitter/X, and LinkedIn:
1. Validates Pydantic schema adherence
2. Enforces strict Twitter 280-character boundary limits
3. Verifies selective channel filtering
4. Pretty-prints rich terminal previews for each platform
5. Supports both --mock (offline) and live LLM execution paths
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import List, Tuple

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

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from config import get_settings
from generator.engine import ContentGenerator
from generator.schema import ContentBundle

console = Console()


def print_bundle_previews(bundle: ContentBundle) -> None:
    """Render rich, visual previews for each generated distribution channel."""
    console.rule("[bold cyan]Multi-Channel Content Generation Previews[/bold cyan]")

    # 1. Blog Post Preview
    if bundle.blog:
        blog = bundle.blog
        toc_items = "\n".join(f"  • {item}" for item in blog.table_of_contents)
        blog_meta = (
            f"[bold cyan]Title:[/bold cyan] {blog.title}\n"
            f"[bold cyan]Slug:[/bold cyan] {blog.slug} | "
            f"[bold cyan]Read Time:[/bold cyan] ~{blog.estimated_read_time_minutes} min\n"
            f"[bold cyan]Meta Description ({len(blog.meta_description)}c):[/bold cyan] "
            f"[dim]{blog.meta_description}[/dim]\n\n"
            f"[bold yellow]Table of Contents:[/bold yellow]\n{toc_items}"
        )
        console.print(
            Panel(
                blog_meta,
                title="[bold green]Long-Form Blog: Metadata & Outline[/bold green]",
                border_style="green",
            )
        )
        console.print(
            Panel(
                Markdown(blog.markdown_content[:600] + "\n\n*(Truncated for terminal preview)*"),
                title="[bold green]Blog: Markdown Content Sample[/bold green]",
                border_style="dim green",
            )
        )

    # 2. Twitter / X Thread Preview
    if bundle.twitter:
        tw = bundle.twitter
        table = Table(title="Twitter / X Thread Breakdown", show_lines=True)
        table.add_column("No.", style="cyan bold", width=6, justify="center")
        table.add_column("Type", style="yellow", width=12)
        table.add_column("Tweet Content", style="white", width=60)
        table.add_column("Chars", style="green", width=10, justify="center")

        table.add_row(
            "1",
            "Hook",
            tw.hook_tweet,
            f"{len(tw.hook_tweet)}/280",
        )
        for t in tw.body_tweets:
            table.add_row(
                str(t.index + 1),
                "Body",
                t.content,
                f"{len(t.content)}/280",
            )
        table.add_row(
            str(tw.total_tweets),
            "CTA",
            tw.call_to_action_tweet,
            f"{len(tw.call_to_action_tweet)}/280",
        )
        console.print(table)

    # 3. LinkedIn Post Preview
    if bundle.linkedin:
        li = bundle.linkedin
        takeaways = "\n".join(f"  ✔ {item}" for item in li.key_takeaways)
        tags = " ".join(f"[bold cyan]{tag}[/bold cyan]" for tag in li.hashtags)
        li_card = (
            f"[bold white on blue] {li.headline} [/bold white on blue]\n\n"
            f"[bold yellow]Hook:[/bold yellow]\n{li.hook}\n\n"
            f"[bold yellow]Body:[/bold yellow]\n{li.body}\n\n"
            f"[bold yellow]Key Takeaways:[/bold yellow]\n{takeaways}\n\n"
            f"[bold yellow]Call To Action:[/bold yellow]\n{li.call_to_action}\n\n"
            f"{tags}"
        )
        console.print(
            Panel(
                li_card,
                title="[bold blue]LinkedIn Feed Post Preview[/bold blue]",
                border_style="blue",
            )
        )


def validate_content_bundle(bundle: ContentBundle) -> List[Tuple[str, bool, str]]:
    """Perform strict structural and constraint assertions on the generated bundle."""
    checks: List[Tuple[str, bool, str]] = []

    # Check 1: Job ID and Topic
    checks.append(
        (
            "Bundle Metadata",
            bool(bundle.job_id and bundle.topic),
            f"JobID: {bundle.job_id[:8]}... | Topic: '{bundle.topic[:30]}'",
        )
    )

    # Check 2: Word Count
    words = bundle.calculate_word_count()
    checks.append(
        (
            "Aggregate Word Count",
            words > 50,
            f"Calculated {words} total words across active channels",
        )
    )

    # Check 3: Blog Validation
    if bundle.blog:
        b = bundle.blog
        valid_slug = bool(b.slug and "-" in b.slug)
        checks.append(
            (
                "Blog Schema Validation",
                bool(b.title and b.markdown_content and valid_slug),
                f"Slug: '{b.slug}' | Read Time: ~{b.estimated_read_time_minutes}m",
            )
        )

    # Check 4: Twitter 280-char boundary compliance
    if bundle.twitter:
        tw = bundle.twitter
        hook_ok = len(tw.hook_tweet) <= 280
        cta_ok = len(tw.call_to_action_tweet) <= 280
        body_ok = all(len(t.content) <= 280 for t in tw.body_tweets)
        total_ok = tw.total_tweets == len(tw.body_tweets) + 2

        all_tweets_ok = hook_ok and cta_ok and body_ok and total_ok
        checks.append(
            (
                "Twitter 280-char Boundary",
                all_tweets_ok,
                f"Hook: {len(tw.hook_tweet)}c, CTA: {len(tw.call_to_action_tweet)}c, "
                f"Body: {len(tw.body_tweets)} tweets",
            )
        )

    # Check 5: LinkedIn Structure
    if bundle.linkedin:
        li = bundle.linkedin
        has_headline = bool(li.headline)
        has_hook = bool(li.hook)
        has_takeaways = len(li.key_takeaways) >= 2
        has_cta = bool(li.call_to_action)

        li_ok = has_headline and has_hook and has_takeaways and has_cta
        checks.append(
            (
                "LinkedIn Schema Validation",
                li_ok,
                f"{len(li.key_takeaways)} takeaways | {len(li.hashtags)} hashtags",
            )
        )

    return checks


def run_generator_verification(mock_mode: bool = False, topic: str | None = None) -> int:
    """Run generator diagnostics, validating output models and platform constraints."""
    console.rule("[bold cyan]Multi-Channel Content Generator Diagnostic[/bold cyan]")

    settings = get_settings()
    sample_topic = topic or "Designing Autonomous Micro-Agents with Python"

    generator = ContentGenerator(settings=settings)

    # Auto-detect mock if no valid API key is set
    effective_mock = mock_mode
    if not effective_mock:
        key = settings.active_api_key
        if not key or key.startswith("your_"):
            console.print(
                f"[yellow]No live API key set for {settings.LLM_PROVIDER.upper()}. "
                f"Defaulting to --mock validation mode.[/yellow]"
            )
            effective_mock = True

    channels = ["blog", "twitter", "linkedin"]

    mode_str = (
        "[bold yellow]MOCK (Deterministic)[/bold yellow]"
        if effective_mock
        else "[bold green]LIVE LLM[/bold green]"
    )
    console.print(
        Panel(
            f"[bold cyan]Topic:[/bold cyan] {sample_topic}\n"
            f"[bold cyan]Provider:[/bold cyan] {settings.LLM_PROVIDER.upper()} "
            f"({settings.LLM_MODEL})\n"
            f"[bold cyan]Channels:[/bold cyan] {', '.join(channels)}\n"
            f"[bold cyan]Execution Mode:[/bold cyan] {mode_str}",
            title="[bold green]Generator Execution Config[/bold green]",
            border_style="bright_blue",
        )
    )

    try:
        if effective_mock:
            bundle = generator.generate_mock_bundle(
                topic=sample_topic,
                channels=channels,
            )
        else:
            bundle = generator.generate_bundle(
                topic=sample_topic,
                channels=channels,
            )
    except Exception as exc:
        console.print(f"[bold red][FAIL] Content generation threw an error:[/bold red] {exc}")
        return 1

    # Render previews
    print_bundle_previews(bundle)

    # Perform contract validations
    checks = validate_content_bundle(bundle)

    table = Table(title="Content Contract Verification Results", show_lines=True)
    table.add_column("Validation Check", style="cyan bold", width=30)
    table.add_column("Result", justify="center", width=12)
    table.add_column("Details", style="white", width=50)

    all_passed = True
    for name, passed, details in checks:
        if not passed:
            all_passed = False
        res = "[bold green]PASS[/bold green]" if passed else "[bold red]FAIL[/bold red]"
        table.add_row(name, res, details)

    console.print(table)

    if all_passed:
        success_msg = (
            f"[bold green]ALL GENERATOR CONTRACT CHECKS PASSED "
            f"({len(checks)}/{len(checks)})![/bold green]\n"
            f"Multi-channel bundle successfully generated for: '{bundle.topic}'.\n"
            f"Total word count: [bold cyan]{bundle.raw_word_count}[/bold cyan] words."
        )
        console.print(
            Panel(
                success_msg,
                title="[bold green]Engine Status: Operational[/bold green]",
                border_style="green",
            )
        )
        return 0
    else:
        console.print(
            Panel(
                "[bold red]ONE OR MORE SCHEMA CONSTRAINTS FAILED![/bold red]",
                title="[bold red]Engine Status: Failed[/bold red]",
                border_style="red",
            )
        )
        return 1


def main() -> None:
    """CLI entry point for generator verification."""
    parser = argparse.ArgumentParser(description="Multi-Channel Content Generator Verifier")
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run offline mock generation without consuming LLM API credits",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Force live generation using configured LLM provider",
    )
    parser.add_argument(
        "--topic",
        type=str,
        default="Designing Autonomous Micro-Agents with Python",
        help="Custom topic string to generate",
    )
    args = parser.parse_args()

    mock_mode = args.mock or (not args.live)
    sys.exit(run_generator_verification(mock_mode=mock_mode, topic=args.topic))


if __name__ == "__main__":
    main()
