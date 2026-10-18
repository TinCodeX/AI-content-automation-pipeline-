"""Deliverables exporter for Multi-Channel Content Automation Pipeline.

Serializes ContentBundle objects into structured files and formatted markdown
documents organized by timestamp and slug within the deliverables directory.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re
import sys
from typing import Dict, Union

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

from generator.schema import ContentBundle

console = Console()

DEFAULT_DELIVERABLES_DIR = BASE_DIR / "deliverables"


def sanitize_slug(text: str) -> str:
    """Produce clean kebab-case string suitable for filesystem folder naming."""
    clean = re.sub(r"[^a-zA-Z0-9\s-]", "", text).strip().lower()
    return re.sub(r"[\s_-]+", "-", clean)[:50]


def export_bundle(
    bundle: ContentBundle,
    output_dir: Union[Path, str] = DEFAULT_DELIVERABLES_DIR,
) -> Dict[str, Path]:
    """Serialize ContentBundle into organized deliverables directory.

    Folder layout: deliverables/YYYYMMDD_HHMMSS_<slug>/
      ├── full_bundle.json
      ├── blog_post.md        (if blog channel active)
      ├── twitter_thread.md   (if twitter channel active)
      └── linkedin_post.md    (if linkedin channel active)

    Returns:
        Dict[str, Path]: Map of channel keys to generated file paths.
    """
    base_out = Path(output_dir)
    timestamp_str = bundle.generated_at.strftime("%Y%m%d_%H%M%S")

    slug = ""
    if bundle.blog and bundle.blog.slug:
        slug = bundle.blog.slug
    else:
        slug = sanitize_slug(bundle.topic)

    folder_name = f"{timestamp_str}_{slug}"
    target_dir = base_out / folder_name
    target_dir.mkdir(parents=True, exist_ok=True)

    exported_paths: Dict[str, Path] = {}

    # 1. Full Bundle JSON Dump
    bundle_json_path = target_dir / "full_bundle.json"
    with open(bundle_json_path, "w", encoding="utf-8") as f:
        f.write(bundle.model_dump_json(indent=2))
    exported_paths["bundle_json"] = bundle_json_path

    # 2. Blog Post Markdown with YAML Frontmatter
    if bundle.blog:
        blog = bundle.blog
        toc_yaml = "\n".join(f"  - \"{item}\"" for item in blog.table_of_contents)
        blog_frontmatter = (
            "---\n"
            f"title: \"{blog.title}\"\n"
            f"slug: \"{blog.slug}\"\n"
            f"meta_description: \"{blog.meta_description}\"\n"
            f"estimated_read_time_minutes: {blog.estimated_read_time_minutes}\n"
            f"job_id: \"{bundle.job_id}\"\n"
            f"generated_at: \"{bundle.generated_at.isoformat()}\"\n"
            "table_of_contents:\n"
            f"{toc_yaml}\n"
            "---\n\n"
        )
        blog_file_content = f"{blog_frontmatter}{blog.markdown_content}\n"
        blog_path = target_dir / "blog_post.md"
        with open(blog_path, "w", encoding="utf-8") as f:
            f.write(blog_file_content)
        exported_paths["blog"] = blog_path

    # 3. Twitter / X Thread Markdown
    if bundle.twitter:
        tw = bundle.twitter
        twitter_lines = [
            f"# Twitter / X Thread: {bundle.topic}",
            f"> Job ID: `{bundle.job_id}` | Generated: {bundle.generated_at.isoformat()} | "
            f"Total Tweets: {tw.total_tweets}\n",
            "---",
            f"\n### 🧵 Tweet 1/Hook ({len(tw.hook_tweet)}/280 chars)",
            f"{tw.hook_tweet}\n",
            "---",
        ]
        for t in tw.body_tweets:
            tweet_num = t.index + 1
            tags = " ".join(t.hashtags) if t.hashtags else ""
            twitter_lines.extend(
                [
                    f"\n### 🧵 Tweet {tweet_num}/{tw.total_tweets} ({len(t.content)}/280 chars)",
                    f"{t.content}",
                ]
            )
            if tags and tags not in t.content:
                twitter_lines.append(f"\n*{tags}*")
            twitter_lines.append("\n---")

        twitter_lines.extend(
            [
                f"\n### 🧵 Tweet {tw.total_tweets}/CTA ({len(tw.call_to_action_tweet)}/280 chars)",
                f"{tw.call_to_action_tweet}\n",
                "---",
            ]
        )
        twitter_path = target_dir / "twitter_thread.md"
        with open(twitter_path, "w", encoding="utf-8") as f:
            f.write("\n".join(twitter_lines))
        exported_paths["twitter"] = twitter_path

    # 4. LinkedIn Post Markdown
    if bundle.linkedin:
        li = bundle.linkedin
        takeaways_text = "\n".join(f"• {item}" for item in li.key_takeaways)
        tags_text = " ".join(li.hashtags)

        linkedin_content = (
            f"# LinkedIn Post: {bundle.topic}\n"
            f"> Job ID: `{bundle.job_id}` | Generated: {bundle.generated_at.isoformat()}\n\n"
            "---\n\n"
            f"## Headline\n{li.headline}\n\n"
            f"## Hook\n{li.hook}\n\n"
            f"## Body\n{li.body}\n\n"
            f"## Key Takeaways\n{takeaways_text}\n\n"
            f"## Call to Action\n{li.call_to_action}\n\n"
            f"## Hashtags\n{tags_text}\n"
        )
        linkedin_path = target_dir / "linkedin_post.md"
        with open(linkedin_path, "w", encoding="utf-8") as f:
            f.write(linkedin_content)
        exported_paths["linkedin"] = linkedin_path

    console.log(
        f"[green]Deliverables exported to:[/green] [cyan]{target_dir.relative_to(BASE_DIR)}[/cyan] "
        f"({len(exported_paths)} files)"
    )
    return exported_paths
