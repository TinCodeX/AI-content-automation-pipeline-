"""Prompt engineering templates and builders for multi-channel content generation.

Defines specialized platform guidelines for Blogs, Twitter/X threads, and
LinkedIn posts, supporting selective channel filtering and audience tuning.
"""

from __future__ import annotations

import json
from typing import List

SYSTEM_PROMPT = """You are a Principal Technical Writer and Developer Advocate.
Your goal is to transform core engineering concepts into high-impact, authentic,
and platform-optimized content assets.

Core Tenets:
1. Depth & Substance: Avoid superficial buzzwords or generic filler.
   Provide concrete technical substance, patterns, and trade-offs.
2. Platform Fidelity: Respect the native voice and layout patterns of each channel.
3. Strict Character Constraints: Twitter/X tweets MUST never exceed 280 characters.
4. Clean Formatting: Format code snippets, markdown headers, and whitespace thoughtfully.
"""

BLOG_GUIDELINES = """### 1. Long-form Technical Blog Post
- Title: Engaging, clear, and optimized for developers and engineering leaders.
- Slug: Clean kebab-case string (e.g. 'designing-autonomous-micro-agents-python').
- Meta Description: 120-160 characters summarizing the core thesis and practical takeaway.
- Table of Contents: 4 to 6 logical section headers.
- Markdown Content:
  * Comprehensive article formatted in markdown.
  * Use # for title, ## and ### for sections.
  * Include code blocks (Python/Bash) where relevant, architecture diagrams, or callouts.
  * Address real-world challenges, trade-offs, and best practices.
- Estimated Read Time: Integer minutes calculated at ~200 words per minute.
"""

TWITTER_GUIDELINES = """### 2. Twitter / X Thread
- Hook Tweet: Scroll-stopping opener highlighting a counter-intuitive insight or problem.
  Must be <= 280 characters.
- Body Tweets: 4 to 6 sequential tweets.
  * Each tweet must stand on its own while advancing the narrative.
  * STRICT CONSTRAINT: Every single tweet body must be <= 280 characters.
  * Include 1-2 relevant hashtags per tweet where fitting.
- Call to Action (CTA) Tweet: Closing tweet encouraging retweets, bookmarks, and replies.
  Must be <= 280 characters.
- Total Tweets: Total number of tweets in the thread (Hook + Body + CTA).
"""

LINKEDIN_GUIDELINES = """### 3. LinkedIn Thought Leadership Post
- Headline: Bold, single-line headline summarizing the topic.
- Hook: First 2-3 lines before the 'see more' fold that generate immediate curiosity.
- Body:
  * Generous visual whitespace with 1-2 sentence paragraphs for mobile readability.
  * Narrative exploring the industry context, personal or engineering insight, and solution.
- Key Takeaways: 3 to 5 scannable bullet points highlighting actionable learnings.
- Call to Action: Engaging, open-ended question prompting peer comments and discussion.
- Hashtags: 3 to 5 curated industry hashtags (e.g. #SoftwareEngineering, #Python, #AI).
"""


def build_generation_prompt(
    topic: str,
    target_audience: str,
    tone: str,
    channels: List[str],
) -> tuple[str, str]:
    """Construct system and user prompts filtered by requested distribution channels.

    Returns:
        tuple[str, str]: (system_prompt, user_prompt)
    """
    selected_channels = [c.lower().strip() for c in channels]

    channel_sections = []
    output_schema_hints = {}

    if "blog" in selected_channels:
        channel_sections.append(BLOG_GUIDELINES)
        output_schema_hints["blog"] = {
            "title": "string",
            "slug": "string",
            "meta_description": "string (120-160 chars)",
            "table_of_contents": ["section1", "section2"],
            "markdown_content": "# Title\\n\\n## Section...",
            "estimated_read_time_minutes": 5,
        }

    if "twitter" in selected_channels:
        channel_sections.append(TWITTER_GUIDELINES)
        output_schema_hints["twitter"] = {
            "hook_tweet": "string (<= 280 chars)",
            "body_tweets": [
                {"index": 1, "content": "string (<= 280 chars)", "hashtags": ["#Tag"]}
            ],
            "call_to_action_tweet": "string (<= 280 chars)",
            "total_tweets": 6,
        }

    if "linkedin" in selected_channels:
        channel_sections.append(LINKEDIN_GUIDELINES)
        output_schema_hints["linkedin"] = {
            "headline": "string",
            "hook": "string (2-3 lines)",
            "body": "string with whitespace breaks",
            "key_takeaways": ["takeaway 1", "takeaway 2"],
            "call_to_action": "string question",
            "hashtags": ["#AI", "#Engineering"],
        }

    assembled_guidelines = "\n".join(channel_sections)
    schema_blueprint = json.dumps(output_schema_hints, indent=2)

    user_prompt = f"""Content Generation Request:
- Topic / Angle: "{topic}"
- Target Audience: {target_audience}
- Voice & Tone: {tone}
- Requested Channels: {', '.join(selected_channels)}

Platform Execution Guidelines:
{assembled_guidelines}

CRITICAL OUTPUT REQUIREMENTS:
1. Output valid, parseable JSON conforming strictly to the requested schema.
2. For Twitter, verify that NO tweet exceeds 280 characters.
3. Populate only the keys for the requested channels: {list(output_schema_hints.keys())}.
4. Do not include markdown code block markers (like ```json) unless necessary. Return pure JSON.

JSON Blueprint Structure:
{schema_blueprint}
"""

    return SYSTEM_PROMPT, user_prompt
