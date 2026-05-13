# Phase 2B: Content Type Routing Design Spec
_Date: 2026-05-12_

---

## 1. Overview

Phase 2B extends the pipeline to support four content types: **video**, **article**, **image**, and **infographic**. Each type changes what Bella writes, whether Lila runs, how Nora QAs, and what Roxy outputs as editorial guidance.

Key changes:
- `ContentType` enum added to `ContentJob` and `Idea` — Zoe recommends a type per idea, user confirms at Checkpoint 1
- `brand.yaml` defines `allowed_content_types` per page — Zoe only generates ideas within these types
- `bella_output` (Union type) replaces the `script` field on `ContentJob`
- Robin skips Lila for articles; Nora skips visual QA for articles
- Roxy reads `platform_specs.yaml` per project and outputs `editorial_guidance` per platform
- `GrowthStrategy` gains `editorial_guidance: dict[str, str]`

No publishing logic changes. No new agents.

---

## 2. Data Model Changes

### `ContentType` enum

```python
class ContentType(str, Enum):
    VIDEO = "video"
    ARTICLE = "article"
    IMAGE = "image"
    INFOGRAPHIC = "infographic"
```

### `Idea` — add `content_type`

```python
class Idea(BaseModel):
    number: int
    title: str
    hook: str
    angle: str
    content_type: ContentType   # Zoe recommends per idea
```

### Existing `Script` model — add discriminator

```python
class Script(BaseModel):
    type: Literal["script"] = "script"
    hook: str
    body: str
    cta: str
    duration_seconds: int
```

### New Bella output models

```python
class Article(BaseModel):
    type: Literal["article"] = "article"
    heading: str
    body: str
    cta: str

class ImageCaption(BaseModel):
    type: Literal["image"] = "image"
    caption: str
    alt_text: str

class InfographicContent(BaseModel):
    type: Literal["infographic"] = "infographic"
    title: str
    points: list[str]
    cta: str

BellaOutput = Annotated[
    Script | Article | ImageCaption | InfographicContent,
    Field(discriminator="type")
]
```

The `type` field on each model allows Pydantic v2 to correctly deserialize `bella_output` from `job.json` when resuming a job. Without a discriminator, Pydantic cannot determine which model to validate against.

### `GrowthStrategy` — add `editorial_guidance`

```python
class GrowthStrategy(BaseModel):
    hashtags: list[str]
    caption: str
    best_post_time_utc: str
    best_post_time_thai: str
    editorial_guidance: dict[str, str]   # platform → guidance text
```

### `ContentJob` — two changes

```python
class ContentJob(BaseModel):
    ...
    content_type: Optional[ContentType] = None          # set when user picks idea at CP1
    bella_output: Optional[BellaOutput] = None          # replaces script field
    # script field is REMOVED
```

`script` is removed entirely. All references to `job.script` in agents and tests must migrate to `job.bella_output`. Agents that previously read `job.script.hook` (Roxy, Nora, Emma) must use type-aware access via `job.bella_output`.

### `BrandProfile` — add `allowed_content_types`

```python
class BrandProfile(BaseModel):
    mission: str
    visual: VisualIdentity
    platforms: list[str]
    tone: str
    target_audience: str
    script_style: str
    nora_max_retries: int = 2
    allowed_content_types: list[ContentType] = ["video", "image", "infographic", "article"]
```

---

## 3. Config Changes

### `projects/slay_hack/brand.yaml`

Add `allowed_content_types` and expand platforms to include YouTube:

```yaml
mission: "Quiet Luxury content for Gen Z & Millennial women in USA"
visual:
  colors: ["#FFFFFF", "#F5F0E8", "#D4AF37", "#1A3A5C"]
  style: "minimalist high-end, soft studio lighting"
platforms:
  - instagram
  - facebook
  - tiktok
  - youtube
tone: "sassy, confident"
target_audience: "Gen Z & Millennial women, USA"
script_style: "lowercase Gen Z slang"
nora_max_retries: 2
allowed_content_types:
  - video
  - image
  - infographic
  - article
```

### `projects/slay_hack/platform_specs.yaml` (new file)

```yaml
instagram:
  editorial: "Hook within 3 seconds. Caption under 150 chars. Hashtags in first comment."
facebook:
  editorial: "Conversational tone. 1-3 sentences. Hashtags optional, inline."
tiktok:
  editorial: "Text overlay on video. CTA in last 3 seconds. Sound-on assumed. Trending audio boosts reach."
youtube:
  editorial: "Thumbnail-first mindset. Title under 60 chars. Description with timestamps. First 30 seconds must hook."
```

---

## 4. Pipeline Routing

### Zoe

Zoe receives `job.pm.brand.allowed_content_types` in its prompt and assigns a `content_type` to each idea. Ideas must only use types in the allowed list.

### Checkpoint 1 (idea_selection)

After `request_checkpoint(stage: "idea_selection")` returns the user's decision (e.g., `"3"`), the orchestrator's `_dispatch` method automatically sets `job.selected_idea` and `job.content_type` from the matching idea in `job.ideas`. This happens in the orchestrator, not in Robin's AI reasoning — it is not a tool call Robin needs to make explicitly.

```python
# In Orchestrator._dispatch, for stage == "idea_selection":
decision_num = int(result.decision)
job.selected_idea = next(i for i in job.ideas if i.number == decision_num)
job.content_type = job.selected_idea.content_type
```

Robin sees `job.content_type` populated when it continues after the checkpoint.

### Bella

Bella receives `job.content_type` and produces the corresponding output type:

| `content_type` | Bella writes | Output model |
|---|---|---|
| `video` | Hook → Body → CTA script | `Script` |
| `article` | Heading + body paragraphs + CTA | `Article` |
| `image` | Caption + alt text | `ImageCaption` |
| `infographic` | Title + data points list + CTA | `InfographicContent` |

Result stored in `job.bella_output`.

### Lila

| `content_type` | Lila action |
|---|---|
| `video` | Generate video prompt (stub in Phase 2B, wired in Phase 3) |
| `article` | **Skip** — Lila is not called |
| `image` | Generate image prompt + call `_generate_image()` |
| `infographic` | Generate infographic prompt + call `_generate_image()` |

Robin's system prompt includes:
```
After Bella completes, check job.content_type:
- video, image, infographic → run_lila
- article → skip run_lila, proceed directly to run_nora
```

### Nora

| `content_type` | Nora QAs |
|---|---|
| `video` | `bella_output` (script) + `visual_prompt` |
| `article` | `bella_output` (article) only — no visual QA |
| `image` | `bella_output` (caption) + `visual_prompt` |
| `infographic` | `bella_output` (content structure) + `visual_prompt` |

Nora's prompt is built dynamically based on `job.content_type`.

### Roxy

Roxy reads `projects/<project>/platform_specs.yaml` and populates `editorial_guidance` keyed by each platform in `job.platforms`. Only platforms present in the YAML are included; missing platforms are silently skipped.

```python
editorial_guidance = {
    "instagram": "Hook within 3 seconds...",
    "facebook": "Conversational tone...",
}
```

---

## 5. Files Changed

| File | Change |
|---|---|
| `models/content_job.py` | Add `ContentType`, `Article`, `ImageCaption`, `InfographicContent`, `BellaOutput`; update `Idea`, `GrowthStrategy`, `ContentJob` (add `content_type`, `bella_output`; remove `script`); update `BrandProfile` |
| `project_loader.py` | Load `allowed_content_types` from `brand.yaml` |
| `projects/slay_hack/brand.yaml` | Add `allowed_content_types`, add `youtube` to platforms |
| `projects/slay_hack/platform_specs.yaml` | New file — editorial guidance per platform |
| `agents/zoe.py` | Include `allowed_content_types` in prompt; return ideas with `content_type` |
| `agents/bella.py` | Branch on `content_type`; write corresponding output model to `job.bella_output` |
| `agents/lila.py` | Accept any `bella_output` type; differentiate prompt by type |
| `agents/nora.py` | Build QA prompt dynamically based on `content_type`; skip visual QA for articles |
| `agents/roxy.py` | Load `platform_specs.yaml`; add `editorial_guidance` to `GrowthStrategy` |
| `orchestrator.py` | Update Robin system prompt for content_type routing; set `job.content_type` at idea selection |
| `tests/` | Update all fixtures using `Script`/`job.script` to `bella_output`; add tests for each content type path |

---

## 6. Out of Scope

- Google Drive / NotebookLM integration (Phase 2C)
- Real video generation (Phase 3)
- Publishing agents (Phase 4)
- TikTok platform (not added to slay_hack in this phase)
