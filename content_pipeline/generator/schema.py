"""Pydantic data schemas for multi-channel content generation contracts.

Defines structured models for Long-form Blog posts, Twitter/X threads,
LinkedIn posts, and the aggregated multi-channel ContentBundle.
"""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class TweetItem(BaseModel):
    """Single numbered tweet in a Twitter/X thread body."""

    index: int = Field(ge=1, description="Sequential position in thread body.")
    content: str = Field(
        max_length=280,
        description="Tweet text content (strictly <= 280 characters).",
    )
    hashtags: List[str] = Field(
        default_factory=list,
        description="Relevant topic tags (e.g. ['#AI', '#Python']).",
    )

    @field_validator("content")
    @classmethod
    def validate_content_length(cls, val: str) -> str:
        """Enforce strict Twitter 280-character boundary."""
        trimmed = val.strip()
        if len(trimmed) > 280:
            raise ValueError(
                f"Tweet content exceeds 280-char limit ({len(trimmed)} chars): '{trimmed[:40]}...'"
            )
        return trimmed


class TwitterThread(BaseModel):
    """Complete structured Twitter/X thread model."""

    hook_tweet: str = Field(
        max_length=280,
        description="High-engagement opener to capture scrolling attention.",
    )
    body_tweets: List[TweetItem] = Field(
        default_factory=list,
        description="Core insights broken down into bite-sized, sequential tweets.",
    )
    call_to_action_tweet: str = Field(
        max_length=280,
        description="Closing tweet prompting retweets, bookmarks, or replies.",
    )
    total_tweets: int = Field(
        ge=2,
        description="Total tweet count including hook, body, and CTA.",
    )

    @field_validator("hook_tweet", "call_to_action_tweet")
    @classmethod
    def validate_tweet_length(cls, val: str) -> str:
        """Ensure boundary constraints on hook and CTA tweets."""
        trimmed = val.strip()
        if len(trimmed) > 280:
            raise ValueError(f"Tweet exceeds 280 chars ({len(trimmed)} chars): '{trimmed[:40]}...'")
        return trimmed

    @field_validator("total_tweets", mode="before")
    @classmethod
    def compute_total_tweets(cls, val: Optional[int], info) -> int:
        """Compute or reconcile total tweets count."""
        body = info.data.get("body_tweets", [])
        expected = len(body) + 2
        return val if (val and val >= expected) else expected


class LinkedInPost(BaseModel):
    """Professional LinkedIn post optimized for feed engagement."""

    headline: str = Field(
        description="Bold top headline / hook statement.",
    )
    hook: str = Field(
        description="Initial 2-3 lines before the 'see more' fold.",
    )
    body: str = Field(
        description="Main body text with generous paragraph breaks for readability.",
    )
    key_takeaways: List[str] = Field(
        default_factory=list,
        description="3 to 5 scannable bullet points highlighting key insights.",
    )
    call_to_action: str = Field(
        description="Closing conversational prompt encouraging comments.",
    )
    hashtags: List[str] = Field(
        default_factory=list,
        description="3-5 professional hashtags (e.g. ['#SoftwareArchitecture']).",
    )


class BlogPost(BaseModel):
    """Long-form technical or thought-leadership blog post."""

    title: str = Field(
        min_length=5,
        max_length=150,
        description="Compelling SEO & human-optimized title.",
    )
    slug: str = Field(
        description="URL-friendly kebab-case slug identifier.",
    )
    meta_description: str = Field(
        description="SEO meta summary targeting 120-160 characters.",
    )
    table_of_contents: List[str] = Field(
        default_factory=list,
        description="List of section headings covered in the article.",
    )
    markdown_content: str = Field(
        description="Complete article markdown with H2/H3 headers, code blocks & callouts.",
    )
    estimated_read_time_minutes: int = Field(
        ge=1,
        description="Calculated reading duration in minutes based on ~200 WPM.",
    )

    @field_validator("slug", mode="before")
    @classmethod
    def sanitize_slug(cls, val: Optional[str], info) -> str:
        """Normalize or generate kebab-case slug from title."""
        raw = val or info.data.get("title", "post")
        slug = re.sub(r"[^a-zA-Z0-9\s-]", "", raw).strip().lower()
        return re.sub(r"[\s_-]+", "-", slug)

    @field_validator("meta_description")
    @classmethod
    def normalize_meta_description(cls, val: str) -> str:
        """Normalize meta description length toward 120-160 characters."""
        trimmed = val.strip()
        if len(trimmed) > 165:
            return trimmed[:157] + "..."
        return trimmed


class ContentBundle(BaseModel):
    """Aggregate multi-channel content payload containing all generated drafts."""

    job_id: str = Field(
        description="Unique UUID identifying the generation request.",
    )
    topic: str = Field(
        description="Core subject or seed angle requested.",
    )
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC generation timestamp.",
    )
    blog: Optional[BlogPost] = Field(
        default=None,
        description="Long-form blog draft if requested.",
    )
    twitter: Optional[TwitterThread] = Field(
        default=None,
        description="Twitter/X thread draft if requested.",
    )
    linkedin: Optional[LinkedInPost] = Field(
        default=None,
        description="LinkedIn feed draft if requested.",
    )
    raw_word_count: int = Field(
        default=0,
        description="Aggregate word count across all generated platforms.",
    )

    def calculate_word_count(self) -> int:
        """Calculate total word count across all active content channels."""
        total = 0
        if self.blog:
            total += len(self.blog.markdown_content.split())
        if self.twitter:
            total += len(self.twitter.hook_tweet.split())
            for t in self.twitter.body_tweets:
                total += len(t.content.split())
            total += len(self.twitter.call_to_action_tweet.split())
        if self.linkedin:
            total += len(self.linkedin.body.split())
            total += len(" ".join(self.linkedin.key_takeaways).split())
            total += len(self.linkedin.call_to_action.split())
        self.raw_word_count = total
        return total
