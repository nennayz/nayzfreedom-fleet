# Slay Hack Agency — System Design Spec
_Date: 2026-05-12 | Phase 1: Foundation + Orchestrator_

---

## 1. Overview

**NayzFreedom / Slay Hack Agency** is a Python-based multi-agent AI pipeline that automates social media content production — from trend research through scripting, visual creation, QA, and publishing. The system supports multiple brand pages, each managed by a dedicated Project Manager (PM) agent with a unique persona.

**Primary platforms:** Facebook, Instagram (Reels focus)
**Secondary:** TikTok, YouTube (later phases)
**Target audience:** Gen Z & Millennial women in USA
**Initial brand:** Slay Hack — Quiet Luxury, minimalist high-end aesthetic

---

## 2. Agent Roster

| Agent | File | Role |
|---|---|---|
| **Robin** | `orchestrator.py` | Creative Director. Claude tool-use loop. Receives brief, routes to PM, coordinates team. |
| **PM (per page)** | `projects/<name>/pm_profile.yaml` | Project Manager per brand. Unique persona. Injects brand context into every agent call. |
| **Mia Trend** | `agents/mia.py` | Research. Queries Brave Search API for current trends, sounds, and formats. |
| **Zoe Spark** | `agents/zoe.py` | Ideation. Generates 5–10 content ideas from Mia's research. |
| **Bella Quill** | `agents/bella.py` | Script writer. 15–60s Reels scripts structured as Hook → Body → CTA. Tone, language style, and audience register are defined entirely by the PM's brand profile — Bella has no hardcoded style. |
| **Lila Lens** | `agents/lila.py` | Visual Director. Generates image/video prompts and calls: **GPT Image 2** (OpenAI) for static images, **Google Veo3** (Vertex AI) for video, and **Nano Banana** as an alternative image generation option. |
| **Nora Sharp** | `agents/nora.py` | QA Editor. Reviews script and visuals. Sends back for revision if below bar. Max 2 retries per job. |
| **Roxy Rise** | `agents/roxy.py` | Growth Strategist. Outputs hashtags (5–10), caption, and optimal posting time for USA audience. |
| **Emma Heart** | `agents/emma.py` | Community Manager. Produces FAQ markdown file with pre-written responses for expected comments. |

---

## 3. The Slay Chain (Pipeline + Checkpoints)

```
python main.py --project slay_hack --brief "วิธีใช้ลิปสติกให้ทนทั้งวัน"

Robin reads projects/slay_hack/ → loads PM "Alex" + brand context
  └→ Mia:  Brave Search trends
  └→ Zoe:  5–10 content ideas

⏸ CHECKPOINT 1 — User picks idea (type 1–10 in terminal)

  └→ Bella: write script
  └→ Lila:  generate visual prompt

⏸ CHECKPOINT 2 — User reviews script + visual prompt (approve / request changes)

  └→ Lila calls DALL-E (image) / Veo3 (video)
  └→ Nora: QA review
      └→ fail → send back to Bella or Lila (max 2 retries)
      └→ still fail after 2 → Robin escalates to user

⏸ CHECKPOINT 3 — User sees QA report (proceed / rework / override)

  └→ Roxy: hashtags + caption + posting time
  └→ Emma: FAQ markdown

⏸ CHECKPOINT 4 — Final approval before publish

  └→ Publish → Meta Graph API (FB + IG)
```

---

## 4. Multi-Page PM Architecture

Each brand page lives in its own project folder. Adding a new page = create a new folder with 2 YAML files. No code changes required.

```
projects/
├── slay_hack/
│   ├── pm_profile.yaml     ← PM persona (unique per page)
│   └── brand.yaml          ← visual ID, audience, platforms
├── client_wellness/
│   ├── pm_profile.yaml
│   └── brand.yaml
└── client_fashion/
    ├── pm_profile.yaml
    └── brand.yaml
```

**pm_profile.yaml (Slay Hack example):**
```yaml
page_name: "Slay Hack Agency"
persona: |
  You are the PM for Slay Hack Agency. You speak with confident,
  trendy energy. You push the team toward bold, viral-first ideas.
  You never approve anything that feels "safe" or "corporate".
```

**brand.yaml (Slay Hack example):**
```yaml
mission: "Quiet Luxury content for Gen Z & Millennial women in USA"
visual:
  colors: ["#FFFFFF", "#F5F0E8", "#D4AF37", "#1A3A5C"]
  style: "minimalist high-end, soft studio lighting"
platforms: [instagram, facebook]
tone: "sassy, confident"
target_audience: "Gen Z & Millennial women, USA"
script_style: "lowercase Gen Z slang"   # ← defined per page, not hardcoded in Bella
nora_max_retries: 2
```

The `script_style` and `target_audience` fields in `brand.yaml` fully control how Bella writes — swapping these values changes the output without touching any code. Robin loads the correct project folder based on `--project` flag (or page name). The PM's `page_name` appears in all job output paths and logs so it's always clear which page a job belongs to.

---

## 5. Data Models

```python
class VisualIdentity(BaseModel):
    colors: List[str]
    style: str

class BrandProfile(BaseModel):
    mission: str
    visual: VisualIdentity
    platforms: List[str]
    tone: str
    nora_max_retries: int = 2

class PMProfile(BaseModel):
    page_name: str              # e.g. "Slay Hack Agency" — used in all logs and output paths
    persona: str
    brand: BrandProfile

class Idea(BaseModel):
    number: int
    title: str
    hook: str
    angle: str

class Script(BaseModel):
    hook: str
    body: str
    cta: str
    duration_seconds: int

class QAResult(BaseModel):
    passed: bool
    script_feedback: Optional[str]
    visual_feedback: Optional[str]
    send_back_to: Optional[str]     # "bella" | "lila" | None

class GrowthStrategy(BaseModel):
    hashtags: List[str]
    caption: str
    best_post_time_utc: str
    best_post_time_thai: str

class CheckpointDecision(BaseModel):
    stage: str
    decision: str
    timestamp: datetime

class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"

class ContentJob(BaseModel):
    id: str                          # e.g. "20260512_143022"
    project: str                     # e.g. "slay_hack"
    pm: PMProfile
    brief: str
    platforms: List[str]
    stage: str
    status: JobStatus
    trend_data:       Optional[dict]
    ideas:            Optional[List[Idea]]
    selected_idea:    Optional[Idea]
    script:           Optional[Script]
    visual_prompt:    Optional[str]
    image_path:       Optional[str]
    video_path:       Optional[str]
    qa_result:        Optional[QAResult]
    nora_retry_count: int = 0
    growth_strategy:  Optional[GrowthStrategy]
    community_faq_path: Optional[str]
    publish_result:   Optional[dict]
    checkpoint_log:   List[CheckpointDecision] = []
```

---

## 6. Job Persistence & Resume

Every time an agent completes, `ContentJob` is serialized to:
```
output/<project>/<job_id>/job.json
```

If the pipeline is interrupted, resume with:
```bash
python main.py --resume 20260512_143022
```

Robin reads `job.json`, checks `stage` and `status`, and continues from the last completed checkpoint. No work is repeated.

---

## 7. Output File Structure

```
output/
└── Slay Hack Agency/
    └── 20260512_143022/
        ├── job.json            ← full ContentJob state
        ├── ideas.md            ← Zoe's 5–10 ideas
        ├── script.md           ← Bella's final script
        ├── visual_prompt.txt   ← Lila's image/video prompt
        ├── image.png           ← DALL-E output
        ├── video.mp4           ← Veo3 output (Phase 3+)
        ├── growth.md           ← Roxy's hashtags + caption + timing
        └── faq.md              ← Emma's pre-written responses
```

---

## 8. Claude API Usage

- **Robin (orchestrator):** `claude-opus-4-7` with tool use
- **PM + all agents:** `claude-sonnet-4-6` for writing tasks
- System prompts use `cache_control: {"type": "ephemeral"}` to cache Robin's + PM's system prompts across the pipeline run, reducing latency and cost on repeated calls

---

## 9. External APIs

| Service | Used by | Purpose |
|---|---|---|
| Anthropic Claude | Robin, all agents | Orchestration + content generation |
| Brave Search | Mia | Live trend research |
| OpenAI GPT Image 2 | Lila | Primary image generation |
| Nano Banana | Lila | Alternative image generation |
| Google Veo3 (Vertex AI) | Lila | Video generation (Phase 3) |
| Meta Graph API | Publish agent | Post to Facebook + Instagram |
| TikTok Content Posting API | Publish agent | Post to TikTok (Phase 4) |

---

## 10. Dry-Run Mode

All agents support a `--dry-run` flag that returns mock data instead of calling external APIs. This allows testing the full pipeline flow — checkpoints, job persistence, file output — without incurring API costs.

```bash
python main.py --project slay_hack --brief "..." --dry-run
```

In dry-run mode:
- Mia returns a static trends dict
- Zoe returns 3 hardcoded ideas
- Bella returns a placeholder script
- Lila skips image/video generation, copies a placeholder asset
- Nora always returns `passed: true`
- Roxy returns static hashtags and caption
- Publish step is skipped entirely

Each agent checks `job.dry_run: bool` at runtime to decide which path to take.

---

## 11. Performance Feedback Loop

`ContentJob` includes a `performance` field reserved for post-publish engagement data. Mia reads past job performance before researching new trends, allowing the system to learn what content works over time.

```python
class PostPerformance(BaseModel):
    platform: str
    likes: Optional[int]
    reach: Optional[int]
    saves: Optional[int]
    shares: Optional[int]
    recorded_at: Optional[datetime]

class ContentJob(BaseModel):
    ...
    performance: List[PostPerformance] = []   # populated after publish
```

Populating `performance` is a manual or webhook-driven step (Phase 4+). The field is included in the model from Phase 1 so no migration is needed later.

---

## 13. Error Handling

- **API timeout / rate limit:** Retry up to 3 times with exponential backoff before marking job `FAILED` and reporting to user
- **Nora QA fail:** Send back to relevant agent, max `nora_max_retries` (default 2). After limit, Robin presents issue to user at CLI
- **Publish fail:** Log error to `job.json`, user can re-run `--publish-only <job_id>` to retry without regenerating content

---

## 14. Phase Breakdown

| Phase | Scope |
|---|---|
| **Phase 1** | Foundation: CLI, config, ContentJob model, Robin orchestrator, Mia (Brave Search) + Zoe + Bella + Lila (stubs for image/video), Nora, Roxy, Emma, job persistence |
| **Phase 2** | Real image generation (DALL-E) |
| **Phase 3** | Video generation (Veo3), full QA on video output |
| **Phase 4** | Publishing (Meta Graph API, TikTok), auto-scheduling via Roxy |
