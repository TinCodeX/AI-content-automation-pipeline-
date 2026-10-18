"""Main pipeline orchestrator for Multi-Channel Content Automation.

Coordinates:
1. Semantic deduplication check via ChromaDB
2. Generative synthesis across target platform schemas (Gemini/OpenAI or Mock)
3. Vector registration of published artifacts
4. Multi-channel file export (.json, .md)
5. Webhook event notification
"""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any, Dict, List, Optional
import uuid

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
from rich.panel import Panel

from config import get_settings, Settings
from exporters import export_bundle
from generator.engine import ContentGenerator
from generator.schema import ContentBundle
from memory.vector_store import ContentMemoryStore

console = Console()


def run_content_pipeline(
    topic: str,
    target_audience: str = "Junior to mid-level backend developers",
    tone: str = "insightful & authoritative",
    channels: Optional[List[str]] = None,
    force: bool = False,
    mock: bool = False,
    job_id: Optional[str] = None,
    memory_store: Optional[ContentMemoryStore] = None,
    output_dir: Optional[Path | str] = None,
    settings: Optional[Settings] = None,
) -> Dict[str, Any]:
    """Execute the full end-to-end multi-channel content generation workflow.

    Workflow:
      1. Vector memory deduplication gate (threshold >= 0.82)
      2. Multi-channel content generation
      3. Vector memory registration
      4. File exports to deliverables/

    Returns:
        Dict[str, Any]: Execution status, job ID, and deliverables map.
    """
    cfg = settings or get_settings()
    active_job_id = job_id or str(uuid.uuid4())
    active_channels = channels or ["blog", "twitter", "linkedin"]
    memory = memory_store or ContentMemoryStore()

    console.rule("[bold cyan]Executing Content Automation Pipeline[/bold cyan]")
    console.print(
        f"[cyan]Job ID:[/cyan] [bold]{active_job_id}[/bold] | "
        f"[cyan]Topic:[/cyan] '[bold magenta]{topic}[/bold magenta]'"
    )

    # -------------------------------------------------------------------------
    # Step 1: Semantic Deduplication Check
    # -------------------------------------------------------------------------
    console.print("[dim]Step 1: Checking vector memory for semantic topic duplication...[/dim]")
    is_duplicate, match_data = memory.is_duplicate_or_similar(
        topic=topic,
        similarity_threshold=0.82,
    )

    if is_duplicate and not force:
        matched_title = match_data.get("matched_topic", "Unknown") if match_data else "Unknown"
        sim_score = match_data.get("similarity", 0.0) if match_data else 0.0
        dist_score = match_data.get("distance", 1.0) if match_data else 1.0

        warning_text = (
            f"[bold red]Topic Duplicate Detected![/bold red]\n"
            f"Candidate Topic: '[magenta]{topic}[/magenta]'\n"
            f"Nearest Existing: '[yellow]{matched_title}[/yellow]'\n"
            f"Cosine Distance: [cyan]{dist_score:.4f}[/cyan] | "
            f"Similarity: [bold red]{sim_score:.2%}[/bold red] (Threshold: 82%)\n\n"
            f"[dim]Use --force to override deduplication gating.[/dim]"
        )
        console.print(
            Panel(
                warning_text,
                title="[bold red]Pipeline Gated: Topic Rejected[/bold red]",
                border_style="red",
            )
        )
        return {
            "status": "duplicate_rejected",
            "job_id": active_job_id,
            "topic": topic,
            "message": (
                f"Rejected: Semantically similar to '{matched_title}' "
                f"(Similarity: {sim_score:.2%})"
            ),
            "match_data": match_data,
            "bundle": None,
            "exported_files": {},
            "word_count": 0,
            "channels": active_channels,
        }

    if is_duplicate and force:
        console.print(
            "[yellow]Notice: Candidate topic is duplicate but --force override was supplied. "
            "Proceeding with generation.[/yellow]"
        )

    # -------------------------------------------------------------------------
    # Step 2: Content Generation
    # -------------------------------------------------------------------------
    console.print(
        f"[dim]Step 2: Synthesizing content across channels {active_channels} "
        f"({'MOCK' if mock else cfg.LLM_PROVIDER.upper()})...[/dim]"
    )
    generator = ContentGenerator(settings=cfg)

    effective_mock = mock
    if not effective_mock:
        key = cfg.active_api_key
        if not key or key.startswith("your_"):
            console.print(
                "[yellow]No live API key found in configuration. "
                "Defaulting to mock generation.[/yellow]"
            )
            effective_mock = True

    if effective_mock:
        bundle: ContentBundle = generator.generate_mock_bundle(
            job_id=active_job_id,
            topic=topic,
            target_audience=target_audience,
            tone=tone,
            channels=active_channels,
        )
    else:
        bundle: ContentBundle = generator.generate_bundle(
            job_id=active_job_id,
            topic=topic,
            target_audience=target_audience,
            tone=tone,
            channels=active_channels,
        )

    # -------------------------------------------------------------------------
    # Step 3: Vector Memory Registration
    # -------------------------------------------------------------------------
    console.print("[dim]Step 3: Registering generated asset bundle in vector memory...[/dim]")
    memory.record_published_content(bundle)

    # -------------------------------------------------------------------------
    # Step 4: Export Deliverables
    # -------------------------------------------------------------------------
    console.print("[dim]Step 4: Serializing deliverables to filesystem...[/dim]")
    exported_map = export_bundle(
        bundle=bundle,
        output_dir=output_dir or (BASE_DIR / "deliverables"),
    )

    console.print(
        Panel(
            f"[bold green]Pipeline Execution Completed Successfully![/bold green]\n"
            f"Topic: [bold magenta]{bundle.topic}[/bold magenta]\n"
            f"Job ID: [cyan]{bundle.job_id}[/cyan]\n"
            f"Word Count: [bold yellow]{bundle.raw_word_count}[/bold yellow] words\n"
            f"Deliverables: [cyan]{len(exported_map)} files exported[/cyan]",
            title="[bold green]Pipeline Status: Completed[/bold green]",
            border_style="green",
        )
    )

    return {
        "status": "completed",
        "job_id": bundle.job_id,
        "topic": bundle.topic,
        "message": "Content successfully generated, vectorized, and exported.",
        "bundle": bundle,
        "exported_files": {k: str(v) for k, v in exported_map.items()},
        "word_count": bundle.raw_word_count,
        "channels": active_channels,
    }
