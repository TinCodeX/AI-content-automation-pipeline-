"""FastAPI Webhook Receiver Endpoint.

Listens for inbound content generation trigger events, enforces header-based
security authentication, validates request payloads, and returns 202 Accepted.
"""

from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional
import uuid

# Ensure parent directory is in sys.path when executed directly or as module
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from rich.console import Console
import uvicorn

try:
    from config import Settings, get_settings
except ImportError:  # pragma: no cover
    from ..config import Settings, get_settings  # type: ignore

console = Console()


# ---------------------------------------------------------------------------
# Request and Response Schemas
# ---------------------------------------------------------------------------

class ContentTriggerPayload(BaseModel):
    """Payload schema for requesting automated content generation."""

    topic: str = Field(
        ...,
        min_length=3,
        max_length=300,
        description="The primary topic, subject, or angle for content creation.",
        examples=["Practical LLM Agents in Production"],
    )
    target_audience: Optional[str] = Field(
        default="Tech professionals & software developers",
        max_length=200,
        description="Audience demographic, background, and familiarity level.",
        examples=["Junior to mid-level backend developers"],
    )
    tone: Optional[str] = Field(
        default="insightful & authoritative",
        max_length=100,
        description="Desired voice, tone, and pacing of generated assets.",
        examples=["insightful & authoritative"],
    )
    channels: Optional[List[str]] = Field(
        default_factory=lambda: ["blog", "twitter", "linkedin"],
        description="Target distribution channels for the generated content.",
        examples=[["blog", "twitter", "linkedin"]],
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Optional execution context, schedule tags, or caller metadata.",
    )


class ContentTriggerResponse(BaseModel):
    """Response returned upon successfully accepting a content trigger."""

    status: str = Field(default="queued")
    message: str = Field(default="Content generation job accepted and queued.")
    job_id: str = Field(description="Unique UUID tracking ID for the job.")
    timestamp: str = Field(description="ISO 8601 UTC timestamp of receipt.")
    topic: str
    target_audience: Optional[str]
    tone: Optional[str]
    channels: List[str]


# ---------------------------------------------------------------------------
# Security Authentication Dependency
# ---------------------------------------------------------------------------

def verify_webhook_secret(
    x_webhook_secret: Optional[str] = Header(None, alias="X-Webhook-Secret"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
    settings: Settings = Depends(get_settings),
) -> str:
    """Validate webhook secret against X-Webhook-Secret header or Bearer token."""
    expected_secret = settings.WEBHOOK_SECRET

    token_to_check = x_webhook_secret
    if not token_to_check and authorization and authorization.startswith("Bearer "):
        token_to_check = authorization.split("Bearer ", 1)[1].strip()

    if not token_to_check:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing webhook authentication. Provide 'X-Webhook-Secret' header.",
        )

    if token_to_check != expected_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook secret token provided.",
        )

    return token_to_check


# ---------------------------------------------------------------------------
# Application Factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    """Build and configure the FastAPI webhook receiver application."""
    settings = get_settings()

    fastapi_app = FastAPI(
        title="AI Content Automation Pipeline - Webhook Trigger Server",
        description=(
            "Dual-trigger ingestion layer for scheduled and event-driven content generation."
        ),
        version="1.0.0",
    )

    @fastapi_app.get("/", tags=["Diagnostic"])
    def root() -> Dict[str, Any]:
        """Root endpoint presenting service metadata."""
        return {
            "service": "AI Content Automation Pipeline - Webhook Trigger",
            "version": "1.0.0",
            "status": "healthy",
            "endpoints": {
                "health": "/health",
                "content_trigger": "/webhook/content-trigger",
            },
        }

    @fastapi_app.get("/health", tags=["Diagnostic"])
    def health_check() -> Dict[str, Any]:
        """Health check endpoint for container probes and monitoring."""
        return {
            "status": "ok",
            "environment": settings.ENV,
            "provider": settings.LLM_PROVIDER,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @fastapi_app.post(
        "/webhook/content-trigger",
        status_code=status.HTTP_202_ACCEPTED,
        response_model=ContentTriggerResponse,
        summary="Receive and queue content creation job",
        tags=["Triggers"],
    )
    async def trigger_content_generation(
        payload: ContentTriggerPayload,
        _: str = Depends(verify_webhook_secret),
    ) -> ContentTriggerResponse:
        """Endpoint to receive content generation triggers.

        Enforces secret token verification, creates a traceable job ID,
        and accepts the job for asynchronous downstream pipeline processing.
        """
        job_id = str(uuid.uuid4())
        now_utc = datetime.now(timezone.utc).isoformat()

        console.log(
            f"[bold green]Received Webhook Trigger:[/bold green] JobID=[cyan]{job_id}[/cyan] "
            f"Topic='[magenta]{payload.topic}[/magenta]' Channels={payload.channels}"
        )

        return ContentTriggerResponse(
            status="queued",
            message="Content generation job accepted and queued.",
            job_id=job_id,
            timestamp=now_utc,
            topic=payload.topic,
            target_audience=payload.target_audience,
            tone=payload.tone,
            channels=payload.channels or ["blog", "twitter", "linkedin"],
        )

    return fastapi_app


app = create_app()


def start_server() -> None:
    """Launch the webhook server via Uvicorn with application settings."""
    settings = get_settings()
    console.print(
        f"[bold blue]Starting Webhook Server on "
        f"http://{settings.WEBHOOK_HOST}:{settings.WEBHOOK_PORT}...[/bold blue]"
    )
    uvicorn.run(
        "triggers.webhook_server:app",
        host=settings.WEBHOOK_HOST,
        port=settings.WEBHOOK_PORT,
        reload=False,
        log_level=settings.LOG_LEVEL.lower(),
    )


if __name__ == "__main__":
    start_server()
