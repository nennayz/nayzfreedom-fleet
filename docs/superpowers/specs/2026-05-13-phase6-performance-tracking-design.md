# Phase 6: Performance Tracking Design

## Goal

Add a `--track <JOB_ID>` CLI flag that polls Meta Graph API and TikTok for post metrics, stores results in `job.performance`, and feeds them into Robin's strategy via the existing `load_recent_performance` mechanism.

## Scope

- New `tracker.py` module at project root
- `main.py`: add `--track <JOB_ID>` to the mutually exclusive CLI group
- No changes to `orchestrator.py`, `job_store.py`, `models/content_job.py`, or any agent

## Architecture

`tracker.py` exposes one public function:

```python
def track_job(job: ContentJob, config: Config) -> ContentJob
```

It iterates over `job.publish_result`, skips entries where `status != "published"`, fetches metrics from each platform's API, and appends `PostPerformance` entries to `job.performance`. Multiple calls accumulate as a history (24h snapshot, 7d snapshot, etc.) — `recorded_at` timestamps distinguish them.

`main.py` handler: `find_job(job_id)` → stage guard (`publish_done`) → `track_job(job, config)` → `save_job(job)` → print clean per-platform summary.

`load_recent_performance` in `job_store.py` already reads `job.performance` — it works automatically once entries are populated.

## Platform API Details

### Facebook

```
GET https://graph.facebook.com/v19.0/{post_id}
    ?fields=likes.summary(true),shares,insights.metric(post_impressions_unique)
    Authorization: Bearer <meta_access_token>
```

Post ID comes from `job.publish_result["facebook"]["id"]`.

Fields mapped to `PostPerformance`:
- `likes.summary.total_count` → `likes`
- `shares.count` → `shares`
- `insights.data[0].values[0].value` (post_impressions_unique) → `reach`
- `saves` → `None` (not available via Graph API for pages)

### Instagram

```
GET https://graph.facebook.com/v19.0/{media_id}
    ?fields=like_count,reach,saved
    Authorization: Bearer <meta_access_token>
```

Media ID comes from `job.publish_result["instagram"]["id"]`.

Fields mapped to `PostPerformance`:
- `like_count` → `likes`
- `reach` → `reach`
- `saved` → `saves`
- `shares` → `None` (not available via Instagram Basic Display)

### TikTok

TikTok's publish flow returns a `publish_id` (operation ID), not a video ID. Metrics require a video ID.

**Resolution step:**

```
POST https://open.tiktokapis.com/v2/video/list/
     ?fields=id,create_time,like_count,view_count,share_count,comment_count
     Authorization: Bearer <tiktok_access_token>

body: {"max_count": 10}
```

Match the video whose `create_time` is closest to the job's publish time and within ±3600 seconds. If no match is found, log a warning and skip TikTok metrics.

**Store resolved video ID** back onto the job to avoid re-resolution on subsequent snapshots:
```python
job.publish_result["tiktok"]["video_id"] = resolved_video_id
```

Fields mapped to `PostPerformance`:
- `like_count` → `likes`
- `view_count` → `reach`
- `share_count` → `shares`
- `comment_count` → `None` (not in PostPerformance model)

## Data Flow

```
python main.py --track <JOB_ID>
  │
  ├── find_job(job_id) → ContentJob
  ├── guard: job.stage must be "publish_done"
  │
  └── track_job(job, config)
        │
        └── for platform, result in job.publish_result.items():
              if result["status"] != "published": skip
              │
              ├── "facebook"  → _fetch_facebook(post_id, config)
              ├── "instagram" → _fetch_instagram(media_id, config)
              └── "tiktok"    → _fetch_tiktok(job, config)
                                  use video_id if stored, else resolve via /video/list/
              │
              append PostPerformance(..., recorded_at=datetime.now(utc)) to job.performance
        │
        return job (caller calls save_job)

  ├── save_job(job)
  └── print per-platform summary:
        facebook:  likes=142, reach=3200, shares=18
        instagram: likes=89,  reach=1100, saves=34
        tiktok:    likes=211, reach=8400, shares=47
```

## Error Handling

Each platform fetch is wrapped in try/except. A failed fetch for one platform does not block others.

```python
for platform, result in job.publish_result.items():
    try:
        perf = _fetch_platform_metrics(platform, result, job, config)
        if perf:
            job.performance.append(perf)
    except Exception as e:
        logger.warning("Could not fetch metrics for %s: %s", platform, e)
```

Missing API fields (e.g. reach not available on personal accounts) remain `None` in `PostPerformance`. If `publish_result` has no `"published"` entries, `track_job` returns the job unchanged.

`--track` prints `No metrics available` if nothing was collected.

## CLI Output

```
Tracking job <job_id> for <page_name>
facebook:  likes=142, reach=3200, shares=18, saves=None
instagram: likes=89,  reach=1100, shares=None, saves=34
tiktok:    likes=211, reach=8400, shares=47, saves=None
```

If a platform failed: `tiktok: failed to fetch (quota exceeded)`

## Testing

All tests in `tests/test_tracker.py`.

| Test | What it verifies |
|---|---|
| `test_track_fb_fetches_metrics` | Mocked GET → `PostPerformance` fields populated, appended to `job.performance` |
| `test_track_ig_fetches_metrics` | Mocked GET → Instagram fields mapped correctly |
| `test_track_tiktok_resolves_video_id_and_fetches_metrics` | Mocked `/video/list/` → matched by timestamp → metrics populated, `video_id` stored in `publish_result` |
| `test_track_tiktok_uses_cached_video_id` | `video_id` already in `publish_result` → `/video/list/` not called |
| `test_track_skips_non_published` | `status == "skipped"` / `"failed"` entries ignored |
| `test_track_partial_failure_continues` | One platform raises → other platforms still tracked |
| `test_track_accumulates_snapshots` | Calling twice → two `PostPerformance` entries appended, both with `recorded_at` set |
| `test_main_track_flag_dispatches_tracker` | `--track <JOB_ID>` in `main.py` calls `track_job` |

## Config

All required fields already present in `Config`:
- `meta_access_token` — used for both Facebook and Instagram
- `tiktok_access_token` — used for TikTok video list + metrics
