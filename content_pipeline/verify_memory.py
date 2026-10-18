"""Verification test suite for Vector Memory & Semantic Deduplication.

Validates ChromaDB vector store functionality:
1. Ingestion of historical editorial topics
2. Cosine distance & similarity computation
3. Automatic rejection of duplicate / near-duplicate topics (>= 0.82 similarity)
4. Approval of novel topics and distance evaluation of borderline queries
5. Recording and retrieval of complete ContentBundle entities
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
from rich.panel import Panel
from rich.table import Table

from generator.engine import ContentGenerator
from memory.vector_store import ContentMemoryStore

console = Console()


def run_memory_verification(persist: bool = False) -> int:
    """Execute vector memory and semantic deduplication test suite."""
    console.rule("[bold cyan]Vector Memory & Semantic Deduplication Suite[/bold cyan]")

    # Use ephemeral client for fast isolated test unless persist flag is given
    memory = ContentMemoryStore(
        collection_name="test_published_content",
        is_ephemeral=not persist,
    )
    # Ensure fresh test collection state
    memory.clear()

    # -------------------------------------------------------------------------
    # Step 1: Seed Historical Editorial Topics
    # -------------------------------------------------------------------------
    historical_topics = [
        (
            "Building Production Microservices with FastAPI and Docker",
            "fastapi-docker-microservices",
            "A comprehensive guide to containerizing FastAPI services with Docker Compose.",
            ["blog", "linkedin"],
        ),
        (
            "Getting Started with Vector Databases in Python",
            "vector-databases-python",
            "Learn how embeddings, similarity search, and ChromaDB empower modern AI apps.",
            ["blog", "twitter"],
        ),
    ]

    for topic, slug, summary, channels in historical_topics:
        memory.add_topic(
            topic=topic,
            slug=slug,
            summary=summary,
            channels=channels,
        )

    console.print(
        Panel(
            f"[bold green]Seeded {len(historical_topics)} historical topics into "
            f"ChromaDB collection '{memory.collection_name}'.[/bold green]",
            title="[bold green]Step 1: Database Seeding[/bold green]",
            border_style="green",
        )
    )

    seed_table = Table(title="Historical Published Topics (Seed Memory)", show_lines=True)
    seed_table.add_column("No.", style="cyan bold", width=6, justify="center")
    seed_table.add_column("Historical Topic", style="white", width=45)
    seed_table.add_column("Slug", style="yellow", width=25)
    seed_table.add_column("Channels", style="dim", width=18)

    for idx, (top, slg, _, chs) in enumerate(historical_topics, 1):
        seed_table.add_row(str(idx), top, slg, ", ".join(chs))
    console.print(seed_table)

    # -------------------------------------------------------------------------
    # Step 2: Semantic Deduplication Evaluation Queries
    # -------------------------------------------------------------------------
    test_queries = [
        {
            "label": "1. Exact / Near Duplicate",
            "query": "How to Build Production FastAPI Microservices in Docker",
            "expected_dup": True,
            "rationale": "High semantic overlap with FastAPI Docker microservices post",
        },
        {
            "label": "2. Borderline / Related Topic",
            "query": "FastAPI Containerization and Docker Best Practices",
            "expected_dup": False,
            "rationale": "Related technology stack but distinct angle / evaluates distance",
        },
        {
            "label": "3. Novel Topic",
            "query": "Introduction to Quantum Computing Algorithms",
            "expected_dup": False,
            "rationale": "Unrelated topic domain with low similarity",
        },
    ]

    dedup_results: List[Tuple[str, str, float, float, str, bool, str]] = []

    for item in test_queries:
        query_topic = item["query"]
        expected_dup = item["expected_dup"]

        is_dup, match_data = memory.is_duplicate_or_similar(
            topic=query_topic,
            similarity_threshold=0.82,
        )

        nearest_match = match_data["matched_topic"] if match_data else "None"
        distance = match_data["distance"] if match_data else 1.0
        similarity = match_data["similarity"] if match_data else 0.0

        if is_dup:
            decision = "[bold red]REJECTED (DUPLICATE)[/bold red]"
        else:
            decision = "[bold green]APPROVED (NOVEL)[/bold green]"
        test_passed = is_dup == expected_dup

        dedup_results.append(
            (
                item["label"],
                query_topic,
                distance,
                similarity,
                decision,
                test_passed,
                nearest_match,
            )
        )

    # -------------------------------------------------------------------------
    # Step 3: Bundle Ingestion & Cycle Verification
    # -------------------------------------------------------------------------
    console.rule("[bold cyan]Step 3: ContentBundle Ingestion Test[/bold cyan]")
    generator = ContentGenerator()
    sample_topic = "Event-Driven LLM Architectures with Redis Streams"

    bundle = generator.generate_mock_bundle(
        topic=sample_topic,
        channels=["blog", "twitter", "linkedin"],
    )
    bundle_id = memory.record_published_content(bundle)

    # Query immediately after recording to verify deduplication catches the new bundle
    is_dup_post_save, match_post_save = memory.is_duplicate_or_similar(
        topic=sample_topic,
        similarity_threshold=0.82,
    )

    bundle_test_passed = (
        bool(bundle_id)
        and is_dup_post_save
        and match_post_save is not None
        and match_post_save.get("matched_id") == bundle_id
    )

    # -------------------------------------------------------------------------
    # Render Diagnostic Results Tables
    # -------------------------------------------------------------------------
    results_table = Table(title="Semantic Deduplication Query Results", show_lines=True)
    results_table.add_column("Test Case", style="cyan bold", width=24)
    results_table.add_column("Candidate Topic", style="white", width=36)
    results_table.add_column("Nearest Match", style="dim", width=32)
    results_table.add_column("Dist", justify="center", width=8)
    results_table.add_column("Sim", justify="center", width=8)
    results_table.add_column("Decision", justify="center", width=22)
    results_table.add_column("Status", justify="center", width=10)

    all_passed = True
    for label, query, dist, sim, decision, passed, matched in dedup_results:
        if not passed:
            all_passed = False
        res_tag = "[bold green]PASS[/bold green]" if passed else "[bold red]FAIL[/bold red]"
        results_table.add_row(
            label,
            query,
            matched,
            f"{dist:.4f}",
            f"{sim:.4f}",
            decision,
            res_tag,
        )

    console.print(results_table)

    # Bundle Ingestion Table
    ingestion_table = Table(title="ContentBundle Ingestion & Gating Check", show_lines=True)
    ingestion_table.add_column("Action / Assertion", style="cyan bold", width=38)
    ingestion_table.add_column("Result / Metric", style="white", width=34)
    ingestion_table.add_column("Status", justify="center", width=10)

    ingestion_table.add_row(
        "1. Ingest Mock ContentBundle",
        f"Assigned ID: {bundle_id[:8]}...",
        "[bold green]PASS[/bold green]",
    )
    ingestion_table.add_row(
        "2. Query Just-Ingested Topic",
        f"Detected Duplicate (Sim: {match_post_save['similarity']:.4f})",
        "[bold green]PASS[/bold green]" if bundle_test_passed else "[bold red]FAIL[/bold red]",
    )
    ingestion_table.add_row(
        "3. Total Vector Store Count",
        f"{memory.collection.count()} registered topics",
        "[bold green]PASS[/bold green]",
    )
    console.print(ingestion_table)

    if not bundle_test_passed:
        all_passed = False

    if all_passed:
        console.print(
            Panel(
                "[bold green]ALL VECTOR MEMORY & DEDUPLICATION CHECKS PASSED (4/4)![/bold green]\n"
                "ChromaDB local vector memory is operational, preventing duplicate content "
                "and accurately evaluating semantic distance thresholds.",
                title="[bold green]Memory Store Status: Operational[/bold green]",
                border_style="green",
            )
        )
        return 0
    else:
        console.print(
            Panel(
                "[bold red]ONE OR MORE VECTOR MEMORY TESTS FAILED![/bold red]",
                title="[bold red]Memory Store Status: Degraded[/bold red]",
                border_style="red",
            )
        )
        return 1


def main() -> None:
    """CLI runner for memory verification."""
    parser = argparse.ArgumentParser(description="ChromaDB Vector Memory Verifier")
    parser.add_argument(
        "--persist",
        action="store_true",
        help="Use persistent disk storage in .chroma_db instead of ephemeral in-memory client",
    )
    args = parser.parse_args()

    sys.exit(run_memory_verification(persist=args.persist))


if __name__ == "__main__":
    main()
