# Phase 3 — Video Generation Design

_Date: 2026-05-13_

## Goal

Wire `LilaAgent` to generate real videos via Google Veo3 (Vertex AI) for VIDEO content type, fix a dry-run bug where `image_path` was incorrectly set for VIDEO jobs, and update Nora's QA to verify the video artifact exists and prevent expensive re-generation loops.

## Scope

Four files change:

| File | Change |
|---|---|
| `agents/lila.py` | Add `_generate_video(job)`; VIDEO `run_live` calls it and sets `job.video_path`; dry_run VIDEO fix: set `video_path`, clear `image_path` |
| `agents/nora.py` | VIDEO QA: check `video_path` artifact before calling Claude; constrain `send_back_to` to `"bella"` or `null` (never `"lila"`) |
| `requirements.txt` | Add `google-cloud-aiplatform` |
| `tests/test_lila.py` + `tests/test_nora.py` | 7 new tests |

No model changes. `google_cloud_project` and `google_application_credentials` are already in `config.py`.

## Architecture

`_generate_video` is implemented directly on `LilaAgent`, parallel to `_generate_image`. It is the only method that touches Vertex AI — no changes to `BaseAgent`.

Nora's VIDEO QA adds a pre-Claude artifact check. If the video file is absent or empty, QA fails immediately without an LLM call. `send_back_to = "lila"` is silently overridden to `None` for VIDEO jobs to prevent costly re-generation loops.

## Data Flow

### Lila — `run_live` VIDEO

```
_call_claude(system, user, max_tokens=256)
    → job.visual_prompt

_generate_video(job)
    → vertexai.init(project=config.google_cloud_project, location="us-central1")
    → model = VideoGenerationModel.from_pretrained("veo-003")
    → operation = model.generate_video(prompt=job.visual_prompt)
    → poll every 15s, max 600s
        timeout → RuntimeError("Video generation timed out after 600s for job {job.id}")
        API error → RuntimeError("Video generation failed for job {job.id}: {e}")
    → download video bytes
    → write → output/<page_name>/<job_id>/video.mp4
    → return str(path)

job.video_path = path
job.image_path = None
job.stage = "lila_done"
```

### Lila — `run_dry` VIDEO (bug fix)

Before: `image_path = "assets/placeholder.png"`, `video_path` unset.
After:
```
job.visual_prompt = _DRY_RUN_PROMPTS[ContentType.VIDEO]
job.video_path = "assets/placeholder.mp4"
job.image_path = None
job.stage = "lila_done"
```

### Nora — `run_live` VIDEO

```
if job.video_path is None:
    → QAResult(passed=False, script_feedback="Video not generated")
    → job.stage = "nora_done"; return

if not Path(job.video_path).exists() or Path(job.video_path).stat().st_size == 0:
    → QAResult(passed=False, script_feedback="Video file missing or empty")
    → job.stage = "nora_done"; return

# Build QA prompt (existing script + visual_prompt content, plus "Video generated: ✓")
raw = _call_claude(system, user)
result = QAResult(**_parse_json(raw))

# Override: VIDEO never sends back to Lila
if result.send_back_to == "lila":
    result = result.model_copy(update={"send_back_to": None})

job.qa_result = result
job.stage = "nora_done"
```

## Error Handling

| Scenario | Behaviour |
|---|---|
| Vertex AI / network error | Caught as `Exception`, re-raised as `RuntimeError` with job ID |
| Poll timeout (>600s) | `RuntimeError("Video generation timed out after 600s for job {job.id}")` |
| `video_path` not set at QA time | Immediate `QAResult(passed=False)`, no LLM call |
| Video file missing or empty at QA time | Immediate `QAResult(passed=False)`, no LLM call |
| Nora returns `send_back_to="lila"` for VIDEO | Silently overridden to `None` |

## Testing

| Test | File |
|---|---|
| `test_lila_dry_run_video_sets_video_path` — VIDEO dry_run sets `video_path`, `image_path` is `None` | `test_lila.py` |
| `test_lila_live_video_calls_veo3` — mock Vertex AI; verify `generate_video` called with `visual_prompt`; `job.video_path` ends with `video.mp4`; file written | `test_lila.py` |
| `test_lila_live_video_timeout_raises_runtime` — poll exceeds 600s → `RuntimeError` with job ID | `test_lila.py` |
| `test_lila_live_video_google_error_raises_runtime` — API exception → `RuntimeError` with job ID | `test_lila.py` |
| `test_nora_video_qa_fails_if_no_video_path` — `video_path = None` → `passed=False`, no Claude call | `test_nora.py` |
| `test_nora_video_qa_fails_if_video_file_missing` — `video_path` set but file absent → `passed=False`, no Claude call | `test_nora.py` |
| `test_nora_video_qa_send_back_to_never_lila` — Claude returns `send_back_to="lila"` → overridden to `None` | `test_nora.py` |
