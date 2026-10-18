"""Application Configuration Module.

Strongly-typed settings backed by pydantic-settings with environment variable
loading, security masking, and rich terminal diagnostics.
"""

import sys
from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

# Resolve project base directory to locate .env reliably
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"


class Settings(BaseSettings):
    """Central application settings validated against environment variables."""

    # Webhook server configuration
    WEBHOOK_HOST: str = Field(
        default="127.0.0.1",
        description="Host interface the webhook server binds to.",
    )
    WEBHOOK_PORT: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="Port for the webhook server.",
    )
    WEBHOOK_SECRET: str = Field(
        default="super-secret-webhook-key-change-in-production",
        min_length=8,
        description="Shared secret key expected in the X-Webhook-Secret header.",
    )

    # LLM configuration
    LLM_PROVIDER: Literal["gemini", "openai"] = Field(
        default="gemini",
        description="Primary LLM provider to power pipeline generation ('gemini' or 'openai').",
    )
    LLM_MODEL: str = Field(
        default="gemini-2.5-flash",
        description="Model identifier to use with the selected provider.",
    )
    GEMINI_API_KEY: Optional[str] = Field(
        default=None,
        description="Google Gemini API Key.",
    )
    OPENAI_API_KEY: Optional[str] = Field(
        default=None,
        description="OpenAI API Key.",
    )

    # Environment & Diagnostics
    ENV: Literal["development", "staging", "production", "testing"] = Field(
        default="development",
        description="Application runtime environment.",
    )
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Logging verbosity level.",
    )

    model_config = SettingsConfigDict(
        env_file=(str(ENV_PATH), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    @field_validator("LLM_MODEL", mode="before")
    @classmethod
    def set_default_model(cls, value: Optional[str], info) -> str:
        """Provide sensible defaults if model string is blank or unspecified."""
        if value and value.strip():
            return value.strip()
        provider = info.data.get("LLM_PROVIDER", "gemini")
        return "gemini-2.5-flash" if provider == "gemini" else "gpt-4o-mini"

    @property
    def active_api_key(self) -> Optional[str]:
        """Return the API key associated with the active LLM provider."""
        if self.LLM_PROVIDER == "gemini":
            return self.GEMINI_API_KEY
        return self.OPENAI_API_KEY

    @property
    def webhook_url(self) -> str:
        """Construct base webhook endpoint URL."""
        return f"http://{self.WEBHOOK_HOST}:{self.WEBHOOK_PORT}/webhook/content-trigger"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Retrieve cached application settings instance."""
    return Settings()


def mask_secret(secret: Optional[str], visible_chars: int = 4) -> str:
    """Mask sensitive keys for safe console output."""
    if not secret:
        return "[dim red]<Not Configured>[/dim red]"
    if len(secret) <= visible_chars * 2:
        return "[yellow]*** (configured)[/yellow]"
    return f"[green]{secret[:visible_chars]}...{secret[-visible_chars:]}[/green]"


def print_settings_diagnostics(settings: Optional[Settings] = None) -> None:
    """Display a rich, formatted diagnostics panel of current active configuration."""
    cfg = settings or get_settings()

    table = Table(title="Content Pipeline Configuration Diagnostics", show_lines=True)
    table.add_column("Configuration Key", style="cyan bold", width=25)
    table.add_column("Value / Status", style="white", width=45)
    table.add_column("Description", style="dim", width=35)

    table.add_row(
        "Environment (ENV)",
        f"[bold magenta]{cfg.ENV}[/bold magenta]",
        "Active execution environment",
    )
    table.add_row(
        "Webhook Server",
        f"[bold green]{cfg.WEBHOOK_HOST}:{cfg.WEBHOOK_PORT}[/bold green]",
        "Bind address for incoming triggers",
    )
    table.add_row(
        "Webhook Endpoint",
        f"[cyan]{cfg.webhook_url}[/cyan]",
        "Target POST endpoint for triggers",
    )
    table.add_row(
        "Webhook Secret Auth",
        mask_secret(cfg.WEBHOOK_SECRET, 4),
        "Protected via X-Webhook-Secret header",
    )
    table.add_row(
        "LLM Provider",
        f"[bold yellow]{cfg.LLM_PROVIDER.upper()}[/bold yellow]",
        "Active generative provider",
    )
    table.add_row(
        "LLM Model",
        f"[bold blue]{cfg.LLM_MODEL}[/bold blue]",
        "Target model architecture",
    )

    # API key diagnostic status
    provider_key_status = (
        "[green]Active & Set[/green]"
        if cfg.active_api_key and not cfg.active_api_key.startswith("your_")
        else "[yellow]Placeholder or Unset[/yellow]"
    )
    table.add_row(
        f"{cfg.LLM_PROVIDER.upper()} Key Status",
        f"{provider_key_status} ({mask_secret(cfg.active_api_key, 3)})",
        "API credential for active provider",
    )

    panel = Panel(
        table,
        title="[bold green]AI Content Pipeline - Config Diagnostics[/bold green]",
        border_style="bright_blue",
        expand=False,
    )
    console.print(panel)


if __name__ == "__main__":
    print_settings_diagnostics()
