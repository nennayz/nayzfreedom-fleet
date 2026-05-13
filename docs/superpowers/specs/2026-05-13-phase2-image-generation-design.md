# Phase 2 — Real Image Generation Design

_Date: 2026-05-13_

## Goal

Wire `LilaAgent._generate_image()` to call the OpenAI `gpt-image-1` API for IMAGE and INFOGRAPHIC content types, replacing the `NotImplementedError` stub from Phase 1.

## Scope

Two files change:

- `agents/lila.py` — implement `_generate_image(job)`
- `tests/test_lila.py` — replace two `NotImplementedError` tests with real behaviour tests

No new files, no model changes, no config changes. `openai_api_key` is already in `config.py` and `openai>=1.0.0` is already in `requirements.txt`.

## Architecture

`_generate_image` is implemented directly on `LilaAgent`. Lila is the only agent that generates images; there is no reason to push this onto `BaseAgent` or extract a separate service.

## Data Flow

```
run_live(job)  [content_type == IMAGE or INFOGRAPHIC]
  _call_claude(system, user, max_tokens=256)
      → job.visual_prompt (str)
  _generate_image(job)
      → openai.OpenAI(api_key=self.config.openai_api_key)
      → client.images.generate(
            model="gpt-image-1",
            prompt=job.visual_prompt,
            n=1,
            size="1024x1024",
            response_format="b64_json",
        )
      → base64.b64decode(response.data[0].b64_json)
      → write bytes to output/<page_name>/<job_id>/image.png
      → return path str
  job.image_path = path
  job.stage = "lila_done"
```

VIDEO content type: `_generate_image` is not called. `job.image_path` remains `None` (video generation is Phase 3).

ARTICLE content type: Lila returns early before any API calls.

## Error Handling

OpenAI errors are wrapped for clarity:

```python
except openai.OpenAIError as e:
    raise RuntimeError(
        f"Image generation failed for job {job.id} "
        f"({job.content_type}): {e}"
    ) from e
```

Job fails immediately. No retry, no fallback. User resumes from the last checkpoint via `python main.py --resume <job_id>`.

## Testing

Replace the two existing `NotImplementedError` tests with:

| Test | What it verifies |
|---|---|
| `test_lila_live_image_calls_openai` | `images.generate` called with correct model and prompt; `job.image_path` points to written file |
| `test_lila_live_infographic_calls_openai` | Same as above for INFOGRAPHIC content type |
| `test_lila_live_image_openai_error_raises_runtime` | `openai.OpenAIError` from API → `RuntimeError` raised with job ID in message |

All existing tests continue to pass unchanged.
