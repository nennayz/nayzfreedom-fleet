# Phase 4 — Meta Publishing Design

_Date: 2026-05-13 | Phase 4: Facebook + Instagram publishing via Meta Graph API_

## Goal

Add a `PublishAgent` that posts completed content jobs to Facebook and Instagram using the Meta Graph API. Supports immediate publish and scheduled publish (using Roxy's `best_post_time_utc`). TikTok is deferred to Phase 5.

---

## Scope

- **In scope:** Facebook Page posts, Instagram Feed posts (IMAGE/INFOGRAPHIC), Instagram Reels (VIDEO), scheduled publishing, `--publish-only <job_id>` retry, partial success per platform
- **Out of scope:** TikTok (Phase 5), YouTube (Phase 5+), Stories, Carousels, performance tracking (PostPerformance population)

---

## Architecture

Single `PublishAgent(BaseAgent)` in `agents/publish.py`. Runs after Emma as the final pipeline step. Follows the existing `run_dry` / `run_live` pattern.

`run_live` iterates over `job.platforms`, uploads media to Meta via Resumable Upload API, creates a container/post object, then publishes or schedules. Results are stored per-platform in `job.publish_result`. A failure on one platform does not abort others.

`run_dry` sets `job.publish_result = {"dry_run": True, "platforms": job.platforms}` without making any API calls.

---

## Content Type → Platform Mapping

| content_type  | Facebook             | Instagram              |
|---------------|----------------------|------------------------|
| VIDEO         | Page video post      | Reels                  |
| IMAGE         | Page photo post      | Feed post (image)      |
| INFOGRAPHIC   | Page photo post      | Feed post (image)      |
| ARTICLE       | Page feed post (text/link) | **skipped** — IG does not support article posts |

ARTICLE jobs publish to Facebook only, even if `job.platforms` includes `instagram`.

---

## Data Flow

```
PublishAgent.run_live(job, schedule=False/True)
  │
  ├─ ARTICLE? → platforms = ["facebook"] only
  │
  ├─ For each platform in effective_platforms:
  │   ├─ Verify media file exists (raise ValueError if missing)
  │   │
  │   ├─ Upload media → Meta Resumable Upload API
  │   │   ├─ IMAGE/INFOGRAPHIC → upload image file → image_handle
  │   │   └─ VIDEO            → upload video file → video_id
  │   │
  │   ├─ Build post object
  │   │   ├─ instagram + IMAGE/INFOGRAPHIC → POST /{ig-user-id}/media
  │   │   │     image_url, caption, hashtags
  │   │   ├─ instagram + VIDEO → POST /{ig-user-id}/media
  │   │   │     media_type=REELS, video_id, caption, hashtags
  │   │   └─ facebook → POST /{page-id}/photos | /videos | /feed
  │   │
  │   ├─ schedule=True  → add scheduled_publish_time (Unix ts), published=false
  │   │                    then POST /{ig-user-id}/media_publish or equivalent
  │   └─ schedule=False → publish immediately
  │
  ├─ job.publish_result = {
  │     "facebook":  {"status": "published"|"scheduled"|"failed", "post_id": "...", "error": null},
  │     "instagram": {"status": "published"|"scheduled"|"failed", "post_id": "...", "error": null}
  │   }
  └─ job.stage = "publish_done"
```

---

## Scheduling

When `schedule=True`, `PublishAgent` reads `job.growth_strategy.best_post_time_utc` (HH:MM format), combines with today's date in UTC, converts to a Unix timestamp, and passes it as `scheduled_publish_time` with `published=false` in the Meta API call.

If `best_post_time_utc` is missing or unparseable, fall back to immediate publish and log a warning in `publish_result`.

---

## Error Handling

| Scenario | Behaviour |
|---|---|
| Media file missing (`image_path`/`video_path` is None or file absent) | Raise `ValueError` with job ID before any upload |
| Upload fails (network, quota, token) | Wrap as `RuntimeError`, record `{"status": "failed", "error": "..."}` for that platform, continue to next platform |
| Publish/container creation fails | Same as upload fail — partial success, continue |
| `schedule=True` but `best_post_time_utc` missing | Fall back to immediate publish, record warning |
| `--publish-only` retry | Robin loads `job.json`, checks `publish_result` for `"failed"` platforms, dispatches `PublishAgent` targeting only those platforms |

---

## `--publish-only` Flag

`main.py` gains a `--publish-only <job_id>` flag. Robin:
1. Loads `output/<page_name>/<job_id>/job.json`
2. Identifies platforms where `publish_result[platform]["status"] == "failed"` (or all platforms if `publish_result` is None)
3. Dispatches `PublishAgent` with `platforms` overridden to only the failed ones
4. Re-saves `job.json` with updated `publish_result`

---

## Environment Variables

Add to `.env.example`:

```
META_PAGE_ID=          # Facebook Page ID
META_IG_USER_ID=       # Instagram Business Account ID linked to the Page
```

`META_ACCESS_TOKEN` is already present. Requires a **Page Access Token** with permissions: `pages_manage_posts`, `instagram_basic`, `instagram_content_publish`.

---

## New Files

| File | Purpose |
|---|---|
| `agents/publish.py` | `PublishAgent` — Meta Graph API publish logic |
| `tests/test_publish.py` | Unit tests for `PublishAgent` |

## Modified Files

| File | Change |
|---|---|
| `orchestrator.py` | Add `PublishAgent` dispatch after Emma; wire `--publish-only` |
| `main.py` | Add `--publish-only <job_id>` and `--schedule` CLI flags |
| `agents/base_agent.py` | Add `META_PAGE_ID`, `META_IG_USER_ID` to `AgentConfig` |
| `.env.example` | Add `META_PAGE_ID`, `META_IG_USER_ID` |

---

## Tests

| Test | What it verifies |
|---|---|
| `test_publish_dry_run_sets_result` | dry run sets `publish_result`, no API calls |
| `test_publish_live_image_calls_meta_upload_and_post` | IMAGE → upload + IG feed post + FB photo post |
| `test_publish_live_video_reel_calls_meta_upload_and_post` | VIDEO → upload + IG Reels + FB video post |
| `test_publish_article_skips_instagram` | ARTICLE → FB only, IG endpoint not called |
| `test_publish_partial_failure_records_per_platform` | FB succeeds, IG fails → both recorded in `publish_result` |
| `test_publish_schedule_flag_adds_timestamp` | `schedule=True` → `scheduled_publish_time` in API call |
| `test_publish_missing_media_raises_value_error` | missing `image_path`/`video_path` → `ValueError` before upload |

---

## Phase Breakdown

| Phase | Scope |
|---|---|
| Phase 4 (this) | Meta Graph API: Facebook + Instagram |
| Phase 5 | TikTok Content Posting API |
