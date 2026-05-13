# Phase 7: YouTube Publishing Design

## Goal

Extend `PublishAgent` to publish VIDEO content to YouTube via the YouTube Data API v3 resumable upload flow, consistent with the per-platform pattern established in Phases 4 and 5.

## Scope

- Extend `agents/publish.py` only — no changes to `orchestrator.py`, `main.py`, `job_store.py`, or any agent
- Update `config.py`: replace `youtube_api_key` with `youtube_client_id`, `youtube_client_secret`, `youtube_refresh_token`
- Update `.env.example` to reflect new config fields
- No new CLI flags, no new agent classes

## Content Type Handling

| Content Type | YouTube behaviour |
|---|---|
| VIDEO | Resumable upload, public or scheduled-private |
| IMAGE | Skip with `{"status": "skipped", "reason": "YouTube only supports video uploads"}` |
| INFOGRAPHIC | Skip with same reason as IMAGE |
| ARTICLE | Excluded from `effective_platforms` (same as Instagram and TikTok) |

## Architecture

`effective_platforms` filter updated to exclude YouTube for ARTICLE jobs:

```python
effective_platforms = [
    p for p in job.platforms
    if not (job.content_type == ContentType.ARTICLE and p in ("instagram", "tiktok", "youtube"))
]
```

Four new private methods added to `PublishAgent`:

- `_youtube_access_token(config)` — exchanges refresh_token for a short-lived access_token
- `_post_youtube(job, caption, scheduled_time)` — dispatches to `_post_youtube_video` or returns skip dict
- `_post_youtube_video(job, caption, scheduled_time, token)` — full 2-step resumable upload flow
- `_youtube_scheduled_iso(scheduled_time)` — converts unix timestamp to ISO 8601 string required by YouTube

One new module-level constant:

```python
_YOUTUBE_UPLOAD_BASE = "https://www.googleapis.com/upload/youtube/v3"
_YOUTUBE_TOKEN_URL = "https://oauth2.googleapis.com/token"
```

## Config Changes

Replace `youtube_api_key: str = ""` in `config.py` with:

```python
youtube_client_id: str = ""
youtube_client_secret: str = ""
youtube_refresh_token: str = ""
```

Update `from_env` to read:
```python
youtube_client_id=os.getenv("YOUTUBE_CLIENT_ID", ""),
youtube_client_secret=os.getenv("YOUTUBE_CLIENT_SECRET", ""),
youtube_refresh_token=os.getenv("YOUTUBE_REFRESH_TOKEN", ""),
```

Update `.env.example`:
```
# YouTube (OAuth 2.0 refresh token flow)
YOUTUBE_CLIENT_ID=
YOUTUBE_CLIENT_SECRET=
YOUTUBE_REFRESH_TOKEN=
```

## YouTube Data API v3 Flow

### Step 0 — Auth refresh

```
POST https://oauth2.googleapis.com/token
Content-Type: application/x-www-form-urlencoded

grant_type=refresh_token
&client_id=<client_id>
&client_secret=<client_secret>
&refresh_token=<refresh_token>

→ { "access_token": "...", "expires_in": 3600 }
```

Called once per `_post_youtube_video` invocation. The access token is not cached between jobs.

### Step 1 — Initiate resumable upload session

```
POST https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable
Authorization: Bearer <access_token>
Content-Type: application/json
X-Upload-Content-Type: video/*
X-Upload-Content-Length: <file_size>

{
  "snippet": {
    "title": "<caption>",
    "description": "<caption>",
    "tags": ["<hashtag1>", "<hashtag2>"],
    "categoryId": "22"
  },
  "status": {
    "privacyStatus": "private",   ← "private" when scheduling, "public" otherwise
    "publishAt": "<ISO8601>"      ← omitted entirely when not scheduling
  }
}

→ Response header: Location: <upload_uri>
```

`privacyStatus` is always `"private"` when `publishAt` is set. When not scheduling, `privacyStatus` is `"public"` and `publishAt` is omitted entirely.

Tags come from `job.growth_strategy.hashtags` (Roxy's output). If `growth_strategy` is None, tags is `[]`.

`categoryId: "22"` = People & Blogs. Configurable per brand in a future phase.

### Step 2 — Upload video bytes

```
PUT <upload_uri>
Content-Type: video/*
Content-Length: <file_size>

<video bytes streamed from job.video_path>

→ { "id": "<video_id>", "status": { "uploadStatus": "uploaded" } }
```

Single PUT (no chunking required — YouTube handles resumable internally). Returns immediately after bytes are received; YouTube processes async.

Return value: `{"id": video_id, "status_code": "uploaded"}` — caller wraps as `{"status": "published", "id": video_id}`.

## Data Flow

```
run_live(job, schedule=...)
  │
  ├── effective_platforms excludes youtube when content_type == ARTICLE
  │
  └── for platform in effective_platforms:
        elif platform == "youtube":
              _post_youtube(job, caption, scheduled_time)
                │
                ├── VIDEO → _post_youtube_video(job, caption, scheduled_time, token)
                │             _youtube_access_token → access_token
                │             init upload session → upload_uri
                │             PUT video bytes → video_id
                │             → {"status": "published", "id": video_id}
                │             → exception → {"status": "failed", "error": ...}
                │
                └── IMAGE/INFOGRAPHIC
                      → {"status": "skipped", "reason": "YouTube only supports video uploads"}
```

`scheduled_time` is a unix int from `_scheduled_unix_ts`. `_youtube_scheduled_iso` converts it to RFC 3339 format required by YouTube (`2026-05-13T14:00:00Z`).

## Error Handling

All exceptions from `_post_youtube_video` propagate to the existing `try/except` block in `run_live` and are recorded as `{"status": "failed", "error": str(e)}`. YouTube failure does not affect Meta or TikTok results in the same job.

If `publish_result` for YouTube contains no `"id"`, the Phase 6 tracker already handles this gracefully (skips metrics with a warning).

## Testing

All tests in `tests/test_publish.py`.

| Test | What it verifies |
|---|---|
| `test_publish_youtube_video_upload` | Auth refresh → init upload → PUT video → `{"status": "published", "id": "yt-1"}` |
| `test_publish_youtube_scheduled` | `publishAt` set in init body, `privacyStatus: "private"` when `schedule=True` |
| `test_publish_youtube_image_skips` | IMAGE job → `{"status": "skipped", "reason": "YouTube only supports video uploads"}` |
| `test_publish_youtube_article_excluded` | ARTICLE job with `youtube` in platforms → `youtube` absent from `publish_result` |
| `test_publish_youtube_failure_does_not_affect_meta` | YouTube raises → Facebook still `published` in same job |

`make_publish_config()` in `tests/test_publish.py` updated to include `youtube_client_id`, `youtube_client_secret`, `youtube_refresh_token`.

## Config

Three new fields in `Config`, all read from environment:
- `youtube_client_id` — OAuth 2.0 client ID
- `youtube_client_secret` — OAuth 2.0 client secret
- `youtube_refresh_token` — long-lived refresh token obtained via one-time OAuth consent flow
