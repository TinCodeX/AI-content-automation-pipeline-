"""Vector memory store and semantic deduplication powered by ChromaDB.

Tracks editorial publication history in a persistent local vector collection,
detecting duplicate and semantically adjacent topics before content generation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple
import uuid

# Ensure parent directory is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import chromadb
from chromadb.api.models.Collection import Collection
from rich.console import Console

try:
    from generator.schema import ContentBundle
except ImportError:  # pragma: no cover
    from ..generator.schema import ContentBundle  # type: ignore

console = Console()

DEFAULT_CHROMA_PATH = BASE_DIR / ".chroma_db"
DEFAULT_COLLECTION_NAME = "published_content"


class ContentMemoryStore:
    """Manages persistent vector memory for published content assets."""

    def __init__(
        self,
        persist_directory: Optional[Path | str] = None,
        collection_name: str = DEFAULT_COLLECTION_NAME,
        is_ephemeral: bool = False,
    ):
        self.collection_name = collection_name
        self.is_ephemeral = is_ephemeral

        if is_ephemeral:
            self.client = chromadb.EphemeralClient()
            self.persist_path = None
        else:
            path = Path(persist_directory) if persist_directory else DEFAULT_CHROMA_PATH
            path.mkdir(parents=True, exist_ok=True)
            self.persist_path = path
            self.client = chromadb.PersistentClient(path=str(path))

        # Initialize collection using cosine similarity metric
        self.collection: Collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def is_duplicate_or_similar(
        self,
        topic: str,
        similarity_threshold: float = 0.82,
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Check if a candidate topic is duplicate or semantically close to past publications.

        ChromaDB cosine distance D ranges from 0.0 (identical) to 2.0 (opposite).
        Cosine similarity is calculated as: 1.0 - distance.

        Returns:
            Tuple[bool, Optional[Dict[str, Any]]]:
                (True, match_info) if similarity >= threshold (Duplicate detected)
                (False, match_info) if topic is sufficiently novel
        """
        count = self.collection.count()
        if count == 0:
            return False, None

        results = self.collection.query(
            query_texts=[topic],
            n_results=1,
            include=["documents", "metadatas", "distances"],
        )

        distances = results.get("distances", [[]])
        metadatas = results.get("metadatas", [[]])
        documents = results.get("documents", [[]])
        ids = results.get("ids", [[]])

        if not distances or not distances[0]:
            return False, None

        distance = float(distances[0][0])
        # Calculate normalized cosine similarity [0.0, 1.0]
        similarity = max(0.0, min(1.0, 1.0 - distance))

        meta = metadatas[0][0] if (metadatas and metadatas[0]) else {}
        matched_doc = documents[0][0] if (documents and documents[0]) else ""
        doc_id = ids[0][0] if (ids and ids[0]) else ""

        match_info = {
            "matched_id": doc_id,
            "matched_topic": meta.get("topic", matched_doc.split("\n")[0]),
            "distance": round(distance, 4),
            "similarity": round(similarity, 4),
            "threshold": similarity_threshold,
            "job_id": meta.get("job_id", ""),
            "slug": meta.get("slug", ""),
            "channels": meta.get("channels", ""),
            "published_at": meta.get("generated_at", ""),
        }

        is_dup = similarity >= similarity_threshold
        return is_dup, match_info

    def record_published_content(self, bundle: ContentBundle) -> str:
        """Embed and register a newly generated ContentBundle into vector memory."""
        # Synthesize document content incorporating topic + hook / meta summary
        summary = ""
        slug = ""
        if bundle.blog:
            summary = bundle.blog.meta_description
            slug = bundle.blog.slug
        elif bundle.twitter:
            summary = bundle.twitter.hook_tweet
        elif bundle.linkedin:
            summary = bundle.linkedin.hook

        document_content = f"{bundle.topic}\n\n{summary}".strip()

        active_channels = []
        for channel_name in ["blog", "twitter", "linkedin"]:
            if getattr(bundle, channel_name, None) is not None:
                active_channels.append(channel_name)

        doc_id = bundle.job_id or str(uuid.uuid4())
        metadata: Dict[str, Any] = {
            "job_id": doc_id,
            "topic": bundle.topic,
            "generated_at": bundle.generated_at.isoformat(),
            "slug": slug,
            "channels": ",".join(active_channels),
            "word_count": bundle.raw_word_count,
        }

        self.collection.upsert(
            ids=[doc_id],
            documents=[document_content],
            metadatas=[metadata],
        )

        console.log(
            f"[green]Recorded in Vector Memory:[/green] ID=[cyan]{doc_id}[/cyan] "
            f"Topic='[magenta]{bundle.topic}[/magenta]'"
        )
        return doc_id

    def add_topic(
        self,
        topic: str,
        job_id: Optional[str] = None,
        summary: Optional[str] = None,
        slug: Optional[str] = None,
        channels: Optional[List[str]] = None,
    ) -> str:
        """Helper to register a historical or seed topic directly."""
        doc_id = job_id or str(uuid.uuid4())
        doc_text = f"{topic}\n\n{summary or ''}".strip()
        metadata: Dict[str, Any] = {
            "job_id": doc_id,
            "topic": topic,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "slug": slug or "",
            "channels": ",".join(channels or ["blog", "twitter", "linkedin"]),
            "word_count": len(doc_text.split()),
        }

        self.collection.upsert(
            ids=[doc_id],
            documents=[doc_text],
            metadatas=[metadata],
        )
        return doc_id

    def list_recent_topics(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Fetch recent topic records stored in the vector database."""
        count = self.collection.count()
        if count == 0:
            return []

        results = self.collection.get(
            limit=limit,
            include=["metadatas", "documents"],
        )

        entries = []
        ids = results.get("ids", [])
        metadatas = results.get("metadatas", [])
        documents = results.get("documents", [])

        for i, entry_id in enumerate(ids):
            meta = metadatas[i] if i < len(metadatas) else {}
            doc = documents[i] if i < len(documents) else ""
            entries.append(
                {
                    "id": entry_id,
                    "topic": meta.get("topic", doc.split("\n")[0]),
                    "generated_at": meta.get("generated_at", ""),
                    "slug": meta.get("slug", ""),
                    "channels": meta.get("channels", ""),
                }
            )
        return entries

    def clear(self) -> None:
        """Clear all records from the collection (useful for testing)."""
        self.client.delete_collection(name=self.collection_name)
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )


def check_and_register_topic(
    topic: str,
    threshold: float = 0.82,
    store: Optional[ContentMemoryStore] = None,
    auto_register: bool = False,
    job_id: Optional[str] = None,
) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """Integration hook to gate topic creation before triggering LLM generation.

    Returns:
        Tuple[bool, Optional[Dict[str, Any]]]:
            (is_duplicate, match_info)
    """
    memory = store or ContentMemoryStore()
    is_duplicate, match_info = memory.is_duplicate_or_similar(
        topic=topic,
        similarity_threshold=threshold,
    )

    if not is_duplicate and auto_register:
        memory.add_topic(topic=topic, job_id=job_id)

    return is_duplicate, match_info
