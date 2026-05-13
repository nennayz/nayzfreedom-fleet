# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**NayzFreedom / Slay Hack Agency** is a Python-based multi-agent AI pipeline that automates social media content production — from trend research through scripting, visual creation, QA, and publishing. The system supports multiple brand pages, each managed by a dedicated Project Manager with a unique persona.

Primary platforms: Facebook, Instagram (Reels). Secondary: TikTok, YouTube (later phases).

Full design spec: [`docs/superpowers/specs/2026-05-12-slay-hack-agency-design.md`](docs/superpowers/specs/2026-05-12-slay-hack-agency-design.md)

---

## Agent Roster (The Slay Chain)

| Agent | File | Role |
|---|---|---|
| **Robin** | `orchestrator.py` | Claude tool-use orchestrator. Receives brief, loads PM, coordinates team. |
| **Mia Trend** | `agents/mia.py` | Trend research via Brave Search API |
| **Zoe Spark** | `agents/zoe.py` | Generates 5–10 content ideas from Mia's research |
| **Bella Quill** | `agents/bella.py` | Script writer (Hook → Body → CTA). Style defined by PM brand profile, not hardcoded. |
| **Lila Lens** | `agents/lila.py` | Visual Director. Calls GPT Image 2, Google Veo3, or Nano Banana. |
| **Nora Sharp** | `agents/nora.py` | QA Editor. Max 2 retries per job (configurable in `brand.yaml`). |
| **Roxy Rise** | `agents/roxy.py` | Hashtags, caption, optimal posting time |
| **Emma Heart** | `agents/emma.py` | FAQ markdown for community management |

---

## Multi-Page Architecture

Each brand page is a folder under `projects/`. Adding a new page requires only 2 YAML files — no code changes.

```
projects/
└── slay_hack/
    ├── pm_profile.yaml   ← page_name + PM persona
    └── brand.yaml        ← visual ID, tone, target_audience, script_style, platforms
```

`page_name` from `pm_profile.yaml` is used in all output paths and logs.

---

## Pipeline Flow

```
python main.py --project slay_hack --brief "..."

Robin → Mia → Zoe → [CHECKPOINT 1: pick idea]
  → Bella → Lila → [CHECKPOINT 2: review script + visual]
  → image/video generation → Nora QA → [CHECKPOINT 3: QA report]
  → Roxy → Emma → [CHECKPOINT 4: final approval]
  → Publish
```

Jobs are resumable: `python main.py --resume <job_id>`

---

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in API keys
```

Required env vars:
```
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
BRAVE_SEARCH_API_KEY=
GOOGLE_CLOUD_PROJECT=
GOOGLE_APPLICATION_CREDENTIALS=
META_ACCESS_TOKEN=
TIKTOK_ACCESS_TOKEN=
YOUTUBE_API_KEY=
```

---

## Common Commands

```bash
# Run pipeline
python main.py --project slay_hack --brief "your brief here"

# Resume interrupted job
python main.py --resume 20260512_143022

# Dry-run (no API calls, mock data throughout)
python main.py --project slay_hack --brief "..." --dry-run

# Run scheduler manually (dry-run — no API calls)
python scheduler.py --dry-run

# Cron entry for VPS (6 AM daily, logs to /var/log/nayzfreedom.log)
# 0 6 * * * /path/to/.venv/bin/python /path/to/scheduler.py >> /var/log/nayzfreedom.log 2>&1

# Run weekly performance reporter (generates markdown + sends Slack digest)
python reporter.py

# Weekly reporter dry-run (prints Slack message to stdout, no POST)
python reporter.py --dry-run

# Cron entry for VPS (8 AM every Monday)
# 0 8 * * 1 /path/to/.venv/bin/python /path/to/reporter.py >> /var/log/nayzfreedom.log 2>&1

# Run tests
pytest

# Single test file
pytest tests/test_orchestrator.py -v

# Type check
mypy .

# Lint
ruff check .
ruff format .
```

---

## Key Architecture Notes

- **Robin uses `claude-opus-4-7`** with tool use. Each agent tool call = dispatching to one of the 7 agents.
- **All agents use `claude-sonnet-4-6`** for writing/analysis tasks.
- **System prompts are cached** (`cache_control: {"type": "ephemeral"}`) on Robin and PM persona to reduce latency across multi-step pipeline runs.
- **`ContentJob`** (Pydantic model in `models/content_job.py`) is the single contract passed between all agents. Never pass raw dicts.
- **Jobs persist to `output/<page_name>/<job_id>/job.json`** after every agent completes. Resume reads this file and skips completed stages.
- **`job.dry_run: bool`** controls whether agents call real APIs or return mock data. Use `--dry-run` during development.
- **Bella has no hardcoded style** — `script_style` and `target_audience` in `brand.yaml` fully control her output.
- **Nora can send work back** to Bella or Lila. `nora_max_retries` in `brand.yaml` controls the limit (default: 2).

---

## Output Structure

```
output/
└── Slay Hack Agency/
    └── 20260512_143022/
        ├── job.json          ← full ContentJob state (resume point)
        ├── ideas.md          ← Zoe's ideas
        ├── script.md         ← Bella's final script
        ├── visual_prompt.txt ← Lila's prompt
        ├── image.png         ← GPT Image 2 output
        ├── video.mp4         ← Veo3 output (Phase 3+)
        ├── growth.md         ← Roxy's hashtags + caption + timing
        └── faq.md            ← Emma's pre-written responses
```
