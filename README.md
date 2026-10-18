# 🚀 Multi-Channel AI Content Automation Pipeline

> An event-driven, production-grade content engine that automatically transforms raw topics into publish-ready blog articles, Twitter/X threads, and LinkedIn posts using Python, FastAPI, ChromaDB, and structured LLM generation.

![Python](https://img.shields.io/badge/Python-3.11+-3776AB.svg?style=flat&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?style=flat&logo=fastapi&logoColor=white)
![ChromaDB](https://img.shields.io/badge/ChromaDB-0.5.0+-orange.svg?style=flat)
![Google Gemini](https://img.shields.io/badge/Google%20GenAI-Gemini%202.0%20Flash-4285F4.svg?style=flat&logo=google)
![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o--mini-412991.svg?style=flat&logo=openai)
![Pydantic](https://img.shields.io/badge/Pydantic-v2-E92063.svg?style=flat)
![APScheduler](https://img.shields.io/badge/APScheduler-Cron%20Engine-blue.svg?style=flat)
![License](https://img.shields.io/badge/License-MIT-green.svg)

---

## 📌 Overview

The **Multi-Channel AI Content Automation Pipeline** eliminates the manual toil of content drafting and multi-platform repurposing. It connects event-driven triggers (FastAPI webhooks and cron schedules) to a multi-stage LLM transformation engine backed by persistent vector memory. 

Before invoking any LLM, the pipeline checks a local **ChromaDB** vector store using cosine similarity ($\ge 82\%$). If a topic is redundant or too close to recent publications, the system rejects it early to save API costs and prevent audience fatigue.

---

## 🏗️ Architecture
content_pipeline/
├── .env / .env.example       # Validated environment configuration
├── config.py                 # Strongly-typed settings with masked diagnostics
├── requirements.txt          # Modern pinned dependencies
├── triggers/
│   ├── webhook_server.py     # FastAPI webhook receiver (X-Webhook-Secret auth)
│   └── scheduler.py          # APScheduler cron & interval recurring dispatcher
├── generator/
│   ├── schema.py             # Pydantic data models (TweetItem, TwitterThread, LinkedInPost, BlogPost, ContentBundle)
│   ├── prompts.py            # Platform-tailored prompt templates & channel filtering
│   └── engine.py             # Multi-channel orchestrator (Gemini, OpenAI & deterministic Mock)
├── memory/
│   └── vector_store.py       # ChromaDB vector store for cosine similarity topic deduplication
├── deliverables/             # Serialized artifact directories (YYYYMMDD_HHMMSS_/)
├── integrations/
│   ├── n8n_workflow.json     # Importable production n8n workflow definition
│   └── make_spec.md          # Step-by-step webhook integration blueprint for Make.com
├── exporters.py              # Multi-channel deliverable file serializer (.json, .md)
├── pipeline.py               # Core orchestrator: Deduplication -> Generation -> Vector Ingestion -> Export
├── main.py                   # Production CLI runner, interactive wizard & webhook simulator
├── verify_triggers.py        # Task 1 diagnostic suite (8/8 passed)
├── verify_generator.py       # Task 2 diagnostic suite (5/5 passed)
├── verify_memory.py          # Task 3 diagnostic suite (4/4 passed)
└── verify_pipeline.py        # Task 4 end-to-end smoke test (5/5 passed)


---

## ✨ Key Features

- **Dual-Trigger Architecture:** 
  - **FastAPI Webhooks:** Authenticated via `X-Webhook-Secret` or Bearer token, returning immediate `202 Accepted` job receipts.
  - **Cron / Recurring Scheduler:** APScheduler support for standard 5-part cron syntax (`0 9 * * 1`) and recurring intervals.
- **Semantic Vector Deduplication (ChromaDB):**
  - Evaluates proposed topics using local embeddings and cosine distance.
  - Rejects near-duplicates and semantic collisions before spending LLM tokens.
- **Platform-Native Content Synthesis:**
  - **Technical Blog:** Structured Markdown with YAML frontmatter, slug, reading time estimate, and table of contents.
  - **Twitter/X Thread:** Strict $\le 280$-character boundary validation per tweet, numbered hooks, and closing CTAs.
  - **LinkedIn Post:** Whitespace-optimized copy with key takeaway bullets, engagement questions, and relevant tags.
- **Deterministic Offline Testing:** Includes a `--mock` flag across all modules for full pipeline execution without burning API credits.
- **No-Code Automation Integration:** Includes an import-ready **n8n workflow JSON** and a **Make.com integration spec**.

---

## 🚀 Quickstart

### 1. Setup Virtual Environment

```bash
# Clone the repository and enter directory
cd content_pipeline

# Create and activate virtual environment
python -m venv .venv

# On Linux/macOS:
source .venv/bin/activate
# On Windows (PowerShell):
.\.venv\Scripts\Activate.ps1

# Install pinned dependencies
pip install -r requirements.txt