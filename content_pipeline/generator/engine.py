"""Multi-channel content generation engine with LLM integration.

Orchestrates generation of structured content across Blogs, Twitter/X threads,
and LinkedIn feeds using Google Gemini or OpenAI with resilient JSON parsing.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional
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

from rich.console import Console

try:
    from config import Settings, get_settings
except ImportError:  # pragma: no cover
    from ..config import Settings, get_settings  # type: ignore

from .prompts import build_generation_prompt
from .schema import BlogPost, ContentBundle, LinkedInPost, TweetItem, TwitterThread

console = Console()


def clean_llm_json(raw_text: str) -> str:
    """Extract and sanitize JSON from markdown-wrapped LLM output."""
    trimmed = raw_text.strip()

    # Pattern 1: Strip ```json ... ``` or ``` ... ```
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", trimmed, re.IGNORECASE)
    if match:
        trimmed = match.group(1).strip()

    # Pattern 2: Extract from first '{' to last '}'
    first_brace = trimmed.find("{")
    last_brace = trimmed.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        trimmed = trimmed[first_brace : last_brace + 1]

    return trimmed


class ContentGenerator:
    """Orchestrator for multi-platform content generation via Gemini or OpenAI."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()

    def _call_gemini(self, system_prompt: str, user_prompt: str) -> str:
        """Execute structured generation using Google GenAI SDK."""
        api_key = self.settings.GEMINI_API_KEY
        if not api_key or api_key.startswith("your_"):
            raise ValueError(
                "GEMINI_API_KEY is not configured. Set it in .env or run with --mock."
            )

        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=self.settings.LLM_MODEL,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                temperature=0.7,
            ),
        )
        if not response.text:
            raise RuntimeError("Gemini returned an empty response.")
        return response.text

    def _call_openai(self, system_prompt: str, user_prompt: str) -> str:
        """Execute structured generation using OpenAI SDK."""
        api_key = self.settings.OPENAI_API_KEY
        if not api_key or api_key.startswith("your_"):
            raise ValueError(
                "OPENAI_API_KEY is not configured. Set it in .env or run with --mock."
            )

        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=self.settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.7,
        )
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("OpenAI returned an empty completion content.")
        return content

    def _invoke_llm(self, system_prompt: str, user_prompt: str) -> str:
        """Route to configured provider."""
        provider = self.settings.LLM_PROVIDER.lower()
        if provider == "gemini":
            return self._call_gemini(system_prompt, user_prompt)
        elif provider == "openai":
            return self._call_openai(system_prompt, user_prompt)
        else:
            raise ValueError(f"Unsupported LLM provider: '{provider}'")

    def generate_bundle(
        self,
        job_id: Optional[str] = None,
        topic: str = "Practical LLM Agents in Production",
        target_audience: str = "Junior to mid-level backend developers",
        tone: str = "insightful & authoritative",
        channels: Optional[List[str]] = None,
    ) -> ContentBundle:
        """Generate structured multi-channel content bundle via configured LLM."""
        active_job_id = job_id or str(uuid.uuid4())
        active_channels = channels or ["blog", "twitter", "linkedin"]

        system_prompt, user_prompt = build_generation_prompt(
            topic=topic,
            target_audience=target_audience,
            tone=tone,
            channels=active_channels,
        )

        console.print(
            f"[cyan]Calling {self.settings.LLM_PROVIDER.upper()} "
            f"({self.settings.LLM_MODEL}) for topic: '{topic}'...[/cyan]"
        )

        raw_output = self._invoke_llm(system_prompt, user_prompt)
        cleaned_json = clean_llm_json(raw_output)

        try:
            parsed_data = json.loads(cleaned_json)
        except json.JSONDecodeError as err:
            raise RuntimeError(
                f"Failed to parse LLM output as JSON: {err}\nOutput: {raw_output[:300]}"
            )

        return self._assemble_bundle(active_job_id, topic, parsed_data, active_channels)

    def generate_mock_bundle(
        self,
        job_id: Optional[str] = None,
        topic: str = "Designing Autonomous Micro-Agents with Python",
        target_audience: str = "Junior to mid-level backend developers",
        tone: str = "insightful & authoritative",
        channels: Optional[List[str]] = None,
    ) -> ContentBundle:
        """Construct realistic, validated mock bundle for offline testing."""
        active_job_id = job_id or str(uuid.uuid4())
        active_channels = [c.lower() for c in (channels or ["blog", "twitter", "linkedin"])]

        mock_data: Dict[str, Any] = {}

        if "blog" in active_channels:
            mock_data["blog"] = {
                "title": f"Architecting {topic}: Patterns & Production Realities",
                "slug": "designing-autonomous-micro-agents-python",
                "meta_description": (
                    "Master modern patterns for autonomous Python micro-agents: state management, "
                    "reliable tools, and resilient event-driven execution."
                ),
                "table_of_contents": [
                    "The Paradigm Shift to Micro-Agents",
                    "Core Architecture: The ReAct Loop",
                    "State & Memory Isolation",
                    "Production Observability & Guardrails",
                    "Conclusion & Implementation Blueprint",
                ],
                "markdown_content": (
                    f"# Architecting {topic}\n\n"
                    "Autonomous agents often fail not because models lack reasoning, "
                    "but because architectural boundaries around them are leaky.\n\n"
                    "## 1. The Paradigm Shift to Micro-Agents\n\n"
                    "Instead of a monolithic prompt executing arbitrary tasks, micro-agents "
                    "scope responsibilities to discrete operational surfaces.\n\n"
                    "```python\n"
                    "class MicroAgent:\n"
                    "    def __init__(self, name: str, tools: list):\n"
                    "        self.name = name\n"
                    "        self.tools = {t.name: t for t in tools}\n\n"
                    "    async def run_step(self, context: dict) -> dict:\n"
                    "        # Isolated agent execution loop\n"
                    "        return {'status': 'completed'}\n"
                    "```\n\n"
                    "## 2. Production Guardrails\n\n"
                    "> [!IMPORTANT]\n"
                    "> Always enforce deterministic timeouts and strict schema validation "
                    "on all agent-dispatched actions.\n\n"
                    "## 3. Summary\n\n"
                    "By adopting single-responsibility micro-agents, engineering teams "
                    "drastically cut token latency and eliminate runaway hallucination loops."
                ),
                "estimated_read_time_minutes": 6,
            }

        if "twitter" in active_channels:
            mock_data["twitter"] = {
                "hook_tweet": (
                    "Most autonomous AI agents crash in production. Why?\n\n"
                    "Because devs build monolithic agents instead of focused micro-agents.\n\n"
                    "Here is the blueprint for resilient, modular Python agents 🧵👇"
                ),
                "body_tweets": [
                    {
                        "index": 1,
                        "content": (
                            "1/ Monolithic agents try to do everything: research, write, "
                            "and deploy. When one step fails, the entire context breaks. "
                            "#Python #AIEngineering"
                        ),
                        "hashtags": ["#Python", "#AIEngineering"],
                    },
                    {
                        "index": 2,
                        "content": (
                            "2/ Solution: The Micro-Agent Pattern.\n\n"
                            "Give each agent ONE tool, ONE schema contract, and ONE clear "
                            "completion condition. Treat them like Unix processes."
                        ),
                        "hashtags": ["#Architecture"],
                    },
                    {
                        "index": 3,
                        "content": (
                            "3/ State Isolation.\n\n"
                            "Never pass 50k tokens of raw chat history between agents. "
                            "Pass typed Pydantic artifacts with minimal required context."
                        ),
                        "hashtags": ["#SoftwareDevelopment"],
                    },
                    {
                        "index": 4,
                        "content": (
                            "4/ Deterministic Fallbacks.\n\n"
                            "When an agent tool call errors, don't let the LLM guess. "
                            "Enforce retry quotas and circuit breakers before human-in-the-loop."
                        ),
                        "hashtags": ["#DevOps"],
                    },
                ],
                "call_to_action_tweet": (
                    "Liked this breakdown? 🔁 Retweet to share with fellow engineers and "
                    "drop your favorite agent framework in the replies! #AI #Python"
                ),
                "total_tweets": 6,
            }

        if "linkedin" in active_channels:
            mock_data["linkedin"] = {
                "headline": f"Why Monolithic AI Agents Fail (And How Micro-Agents Fix Them)",
                "hook": (
                    "We spent months debugging agent loops that hallucinated in production.\n\n"
                    "The fix was surprisingly simple: Treat AI agents like microservices."
                ),
                "body": (
                    "In early prototypes, it's tempting to build a 'Super-Agent' that does "
                    "research, synthesis, schema validation, and database updates all in one.\n\n"
                    "In practice, this creates context pollution, high latency, and unpredictable "
                    "token spend.\n\n"
                    "By decomposing the pipeline into micro-agents with strict Pydantic inputs "
                    "and outputs, we achieved 99.4% task completion reliability."
                ),
                "key_takeaways": [
                    "Single Responsibility: One toolset and one goal per agent instance.",
                    "Typed Contracts: Pydantic schemas eliminate ambiguous unstructured outputs.",
                    "Isolated Context: Pass minimal state artifacts instead of raw chat logs.",
                    "Circuit Breakers: Hard cutoffs on recursive reasoning steps.",
                ],
                "call_to_action": (
                    "Are you running autonomous agents in production today, or still testing "
                    "in staging? Let's discuss your architectural bottlenecks in the comments."
                ),
                "hashtags": ["#AIEngineering", "#Python", "#SoftwareArchitecture", "#LLMOps"],
            }

        return self._assemble_bundle(active_job_id, topic, mock_data, active_channels)

    def _assemble_bundle(
        self,
        job_id: str,
        topic: str,
        data: Dict[str, Any],
        channels: List[str],
    ) -> ContentBundle:
        """Validate and assemble platform payloads into a ContentBundle."""
        active_channels = [c.lower() for c in channels]

        blog_obj = None
        if "blog" in active_channels and "blog" in data and data["blog"]:
            blog_obj = BlogPost.model_validate(data["blog"])

        twitter_obj = None
        if "twitter" in active_channels and "twitter" in data and data["twitter"]:
            twitter_obj = TwitterThread.model_validate(data["twitter"])

        linkedin_obj = None
        if "linkedin" in active_channels and "linkedin" in data and data["linkedin"]:
            linkedin_obj = LinkedInPost.model_validate(data["linkedin"])

        bundle = ContentBundle(
            job_id=job_id,
            topic=topic,
            generated_at=datetime.now(timezone.utc),
            blog=blog_obj,
            twitter=twitter_obj,
            linkedin=linkedin_obj,
        )
        bundle.calculate_word_count()
        return bundle
