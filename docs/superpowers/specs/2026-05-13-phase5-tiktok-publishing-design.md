# Phase 5: TikTok Publishing Design

## Goal

Extend `PublishAgent` to publish VIDEO and IMAGE content to TikTok via the TikTok Content Posting API v2, consistent with the partial-success per-platform pattern established in Phase 4.

## Scope

- Extend `agents/publish.py` only — no changes to `orchestrator.py`, `agent_tools.py`, `main.py`, or `config.py`
- `config.py` already has `tiktok_access_token`
- No new CLI flags, no new tool definitions, no new agent classes

## Content Type Handling

| Content Type | TikTok behaviour |
|---|---|
| VIDEO | Upload via FILE_UPLOAD chunked flow, poll until PUBLISH_COMPLETE |
| IMAGE | Skip with `{"status": "skipped", "reason": "image carousel requires public URL hosting"}` |
| ARTICLE | Excluded from `effective_platforms` (same as Instagram) |
| INFOGRAPHIC | Skip with same reason as IMAGE |

## Architecture

`PublishAgent.run_live` gains one new branch in the platform loop:

```python
elif platform == "tiktok":
    post_result = self._post_tiktok(job, caption)
```

`effective_platforms` filter is updated to exclude TikTok for ARTICLE jobs:

```python
effective_platforms = [
    p for p in job.platforms
    if not (job.content_type == ContentType.ARTICLE and p in ("instagram", "tiktok"))
]
```

Two new private methods:

- `_post_tiktok(job, caption)` — dispatches to `_post_tiktok_video` or returns the image-skip dict
- `_post_tiktok_video(job, caption, token)` — full 3-step upload flow

## TikTok Content Posting API v2

Base URL: `https://open.tiktokapis.com/v2`

All requests use `Authorization: Bearer <tiktok_access_token>` header.

### Step 1 — Init upload session

```
POST /post/publish/video/init/
Content-Type: application/json; charset=UTF-8

{
  "post_info": {
    "title": "<caption>",
    "privacy_level": "PUBLIC_TO_EVERYONE",
    "disable_duet": false,
    "disable_comment": false,
    "disable_stitch": false
  },
  "source_info": {
    "source": "FILE_UPLOAD",
    "video_size": <bytes>,
    "chunk_size": <chunk_bytes>,
    "total_chunk_count": <n>
  }
}
```

Response: `{ "data": { "publish_id": "...", "upload_url": "..." } }`

Chunk size: 10 MB (10 * 1024 * 1024 bytes). Final chunk may be smaller.

### Step 2 — Upload chunks

```
PUT <upload_url>
Authorization: Bearer <token>
Content-Range: bytes <start>-<end>/<total>
Content-Type: video/mp4

<chunk bytes>
```

Repeat for each chunk sequentially.

### Step 3 — Poll publish status

```
POST /post/publish/status/fetch/
Content-Type: application/json; charset=UTF-8

{ "publish_id": "<publish_id>" }
```

Poll every 5 seconds, up to 300 seconds total.

Terminal statuses: `PUBLISH_COMPLETE`, `FAILED`.

On `PUBLISH_COMPLETE`: return `{"publish_id": publish_id, "status_code": "PUBLISH_COMPLETE"}`.

On `FAILED`: raise `RuntimeError("TikTok publish failed: <error_code>")`.

On timeout: raise `TimeoutError("timed out waiting for TikTok processing after 300s")`.

Both exceptions are caught by the existing per-platform `try/except` in `run_live`.

## Data Flow

```
run_live(job, schedule=...)
  │
  ├── effective_platforms excludes tiktok when content_type == ARTICLE
  │
  └── for platform in effective_platforms:
        elif platform == "tiktok":
              _post_tiktok(job, caption)
                │
                ├── VIDEO → _post_tiktok_video(job, caption, token)
                │             init → chunk upload → poll
                │             → {"status": "published", "publish_id": ...}
                │             → timeout/fail → exception → {"status": "failed", "error": ...}
                │
                └── IMAGE/INFOGRAPHIC
                      → {"status": "skipped", "reason": "image carousel requires public URL hosting"}
```

`schedule` kwarg is accepted but ignored for TikTok — TikTok Content Posting API v2 does not support scheduled publishing.

## Error Handling

All exceptions from `_post_tiktok_video` propagate up to the existing `try/except` block in `run_live` and are recorded as `{"status": "failed", "error": str(e)}`. TikTok failure does not affect Meta results in the same job.

## Testing

All tests in `tests/test_publish.py`.

| Test | What it verifies |
|---|---|
| `test_publish_tiktok_video_init_upload_publish` | Full 3-step flow: init → chunk upload → poll → `{"status": "published"}` |
| `test_publish_tiktok_video_poll_timeout` | Poll exceeds 300s → `{"status": "failed", "error": "timed out..."}` |
| `test_publish_tiktok_image_skips_with_reason` | IMAGE job → `{"status": "skipped", "reason": "..."}` |
| `test_publish_tiktok_article_excluded_from_platforms` | ARTICLE job with `tiktok` in platforms → `tiktok` absent from `publish_result` |
| `test_publish_tiktok_failure_does_not_affect_meta` | TikTok raises → `facebook` still `published` in same job |

## Config

`config.tiktok_access_token` — already present, read from `TIKTOK_ACCESS_TOKEN` env var.

No new config fields required.
