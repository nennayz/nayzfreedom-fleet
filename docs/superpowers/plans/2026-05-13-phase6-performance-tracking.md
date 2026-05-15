# Phase 6: Performance Tracking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `--track <JOB_ID>` CLI flag that polls Meta Graph API and TikTok for post metrics, stores results in `job.performance`, and feeds them into Robin's strategy via the existing `load_recent_performance` mechanism.

**Architecture:** New `tracker.py` at project root with `track_job(job, config) -> ContentJob`. Per-platform fetch functions call Meta Graph API (GET) and TikTok (POST /video/list/ or /video/query/). `main.py` gets `--track <JOB_ID>` in the mutually exclusive group. No changes to orchestrator, job_store, or models — `PostPerformance` and `job.performance` already exist.

**Tech Stack:** Python 3.9, `requests`, Meta Graph API v19.0, TikTok Content Posting API v2, pytest, pytest-mock.

---

## File Map

| File | Change |
|---|---|
| `tracker.py` | Create — `track_job`, `_fetch_platform_metrics`, `_fetch_facebook`, `_fetch_instagram`, `_fetch_tiktok` (placeholder Task 1, real Task 2), `_auth_headers`, `_job_publish_time` |
| `tests/test_tracker.py` | Create — 8 tests across 3 tasks |
| `main.py` | Modify — add `from tracker import track_job`, `--track` flag, handler block |

---

## Task 1: `tracker.py` — core + Facebook + Instagram + error handling

**Files:**
- Create: `tracker.py`
- Create: `tests/test_tracker.py`

- [ ] **Step 1: Create `tests/test_tracker.py` with 5 failing tests**

```python
from __future__ import annotations
from datetime import datetime, timezone
from tracker import track_job
from config import Config


def _make_config():
    return Config(
        anthropic_api_key="test",
        brave_search_api_key="brave",
        openai_api_key="oai",
        meta_access_token="meta-token",
        meta_page_id="page-123",
        meta_ig_user_id="ig-456",
        tiktok_access_token="tiktok-token",
    )


def _make_published_job(publish_result: dict):
    from tests.test_publish import make_image_job
    job = make_image_job(dry_run=False)
    job.stage = "publish_done"
    job.publish_result = publish_result
    return job


def test_track_fb_fetches_metrics(mocker):
    mock_get = mocker.patch("tracker.requests.get")
    mock_get.return_value.raise_for_status = mocker.MagicMock()
    mock_get.return_value.json.return_value = {
        "likes": {"summary": {"total_count": 142}},
        "shares": {"count": 18},
        "insights": {"data": [{"values": [{"value": 3200}]}]},
    }
    job = _make_published_job({"facebook": {"status": "published", "id": "post-1"}})
    result = track_job(job, _make_config())
    assert len(result.performance) == 1
    p = result.performance[0]
    assert p.platform == "facebook"
    assert p.likes == 142
    assert p.reach == 3200
    assert p.shares == 18
    assert p.recorded_at is not None


def test_track_ig_fetches_metrics(mocker):
    mock_get = mocker.patch("tracker.requests.get")
    mock_get.return_value.raise_for_status = mocker.MagicMock()
    mock_get.return_value.json.return_value = {
        "like_count": 89,
        "reach": 1100,
        "saved": 34,
    }
    job = _make_published_job({"instagram": {"status": "published", "id": "media-1"}})
    result = track_job(job, _make_config())
    assert len(result.performance) == 1
    p = result.performance[0]
    assert p.platform == "instagram"
    assert p.likes == 89
    assert p.reach == 1100
    assert p.saves == 34


def test_track_skips_non_published(mocker):
    mock_get = mocker.patch("tracker.requests.get")
    job = _make_published_job({
        "facebook": {"status": "failed", "error": "quota"},
        "instagram": {"status": "skipped", "reason": "no hosting"},
    })
    result = track_job(job, _make_config())
    assert result.performance == []
    assert not mock_get.called


def test_track_partial_failure_continues(mocker):
    mock_get = mocker.patch("tracker.requests.get")
    fb_resp = mocker.MagicMock()
    fb_resp.raise_for_status = mocker.MagicMock()
    fb_resp.json.return_value = {
        "likes": {"summary": {"total_count": 50}},
        "shares": {"count": 5},
        "insights": {},
    }
    ig_resp = mocker.MagicMock()
    ig_resp.raise_for_status.side_effect = Exception("IG quota exceeded")
    mock_get.side_effect = [fb_resp, ig_resp]
    job = _make_published_job({
        "facebook": {"status": "published", "id": "post-2"},
        "instagram": {"status": "published", "id": "media-2"},
    })
    result = track_job(job, _make_config())
    assert len(result.performance) == 1
    assert result.performance[0].platform == "facebook"


def test_track_accumulates_snapshots(mocker):
    mock_get = mocker.patch("tracker.requests.get")
    mock_get.return_value.raise_for_status = mocker.MagicMock()
    mock_get.return_value.json.return_value = {
        "likes": {"summary": {"total_count": 10}},
        "shares": {},
        "insights": {},
    }
    job = _make_published_job({"facebook": {"status": "published", "id": "post-3"}})
    config = _make_config()
    track_job(job, config)
    track_job(job, config)
    assert len(job.performance) == 2
```

- [ ] **Step 2: Run to verify all 5 fail**

```bash
cd /Users/nennayz/Documents/NayzFreedom/code/nayzfreedom-fleet && .venv/bin/python -m pytest tests/test_tracker.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'tracker'`

- [ ] **Step 3: Create `tracker.py`**

```python
from __future__ import annotations
import logging
from datetime import datetime, timezone
import requests
from config import Config
from models.content_job import ContentJob, PostPerformance

_META_GRAPH_BASE = "https://graph.facebook.com/v19.0"
_TIKTOK_BASE = "https://open.tiktokapis.com/v2"
_TIKTOK_MATCH_WINDOW = 3600

logger = logging.getLogger(__name__)


def track_job(job: ContentJob, config: Config) -> ContentJob:
    if not job.publish_result:
        return job
    for platform, result in job.publish_result.items():
        if result.get("status") != "published":
            continue
        try:
            perf = _fetch_platform_metrics(platform, result, job, config)
            if perf:
                job.performance.append(perf)
        except Exception as e:
            logger.warning("Could not fetch metrics for %s: %s", platform, e)
    return job


def _fetch_platform_metrics(
    platform: str, result: dict, job: ContentJob, config: Config
) -> PostPerformance | None:
    if platform == "facebook":
        return _fetch_facebook(result["id"], config)
    if platform == "instagram":
        return _fetch_instagram(result["id"], config)
    if platform == "tiktok":
        return _fetch_tiktok(result, job, config)
    return None


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _fetch_facebook(post_id: str, config: Config) -> PostPerformance:
    resp = requests.get(
        f"{_META_GRAPH_BASE}/{post_id}",
        params={"fields": "likes.summary(true),shares,insights.metric(post_impressions_unique)"},
        headers=_auth_headers(config.meta_access_token),
    )
    resp.raise_for_status()
    data = resp.json()
    likes = data.get("likes", {}).get("summary", {}).get("total_count")
    shares = data.get("shares", {}).get("count")
    reach = None
    insights = data.get("insights", {}).get("data", [])
    if insights:
        values = insights[0].get("values", [])
        if values:
            reach = values[0].get("value")
    return PostPerformance(
        platform="facebook",
        likes=likes,
        reach=reach,
        shares=shares,
        recorded_at=datetime.now(timezone.utc),
    )


def _fetch_instagram(media_id: str, config: Config) -> PostPerformance:
    resp = requests.get(
        f"{_META_GRAPH_BASE}/{media_id}",
        params={"fields": "like_count,reach,saved"},
        headers=_auth_headers(config.meta_access_token),
    )
    resp.raise_for_status()
    data = resp.json()
    return PostPerformance(
        platform="instagram",
        likes=data.get("like_count"),
        reach=data.get("reach"),
        saves=data.get("saved"),
        recorded_at=datetime.now(timezone.utc),
    )


def _fetch_tiktok(result: dict, job: ContentJob, config: Config) -> PostPerformance | None:
    raise NotImplementedError("_fetch_tiktok not yet implemented")


def _job_publish_time(job: ContentJob) -> int:
    try:
        dt = datetime.strptime(job.id, "%Y%m%d_%H%M%S").replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    except (ValueError, AttributeError):
        return int(datetime.now(timezone.utc).timestamp())
```

- [ ] **Step 4: Run the 5 tests**

```bash
.venv/bin/python -m pytest tests/test_tracker.py::test_track_fb_fetches_metrics tests/test_tracker.py::test_track_ig_fetches_metrics tests/test_tracker.py::test_track_skips_non_published tests/test_tracker.py::test_track_partial_failure_continues tests/test_tracker.py::test_track_accumulates_snapshots -v
```

Expected: all 5 PASS.

- [ ] **Step 5: Run full test suite**

```bash
.venv/bin/python -m pytest --tb=short -q
```

Expected: 106 passed (101 existing + 5 new).

- [ ] **Step 6: Commit**

```bash
git add tracker.py tests/test_tracker.py
git commit -m "feat(tracker): add track_job with Facebook and Instagram metrics"
```

---

## Task 2: TikTok metrics

**Files:**
- Modify: `tracker.py` (replace `_fetch_tiktok` placeholder)
- Modify: `tests/test_tracker.py` (add 2 tests)

- [ ] **Step 1: Add 2 failing tests at the bottom of `tests/test_tracker.py`**

```python
def test_track_tiktok_resolves_video_id_and_fetches_metrics(mocker):
    mock_post = mocker.patch("tracker.requests.post")
    mock_post.return_value.raise_for_status = mocker.MagicMock()
    job = _make_published_job({"tiktok": {"status": "published", "publish_id": "pub-1"}})
    job.id = "20260513_120000"
    job_ts = int(
        datetime.strptime("20260513_120000", "%Y%m%d_%H%M%S")
        .replace(tzinfo=timezone.utc)
        .timestamp()
    )
    mock_post.return_value.json.return_value = {
        "data": {
            "videos": [
                {
                    "id": "vid-1",
                    "create_time": job_ts + 30,
                    "like_count": 211,
                    "view_count": 8400,
                    "share_count": 47,
                }
            ]
        }
    }
    result = track_job(job, _make_config())
    assert len(result.performance) == 1
    p = result.performance[0]
    assert p.platform == "tiktok"
    assert p.likes == 211
    assert p.reach == 8400
    assert p.shares == 47
    assert result.publish_result["tiktok"]["video_id"] == "vid-1"
    call_url = mock_post.call_args[0][0]
    assert "video/list" in call_url


def test_track_tiktok_uses_cached_video_id(mocker):
    mock_post = mocker.patch("tracker.requests.post")
    mock_post.return_value.raise_for_status = mocker.MagicMock()
    mock_post.return_value.json.return_value = {
        "data": {
            "videos": [
                {"id": "vid-2", "like_count": 300, "view_count": 9000, "share_count": 60}
            ]
        }
    }
    job = _make_published_job({
        "tiktok": {"status": "published", "publish_id": "pub-2", "video_id": "vid-2"}
    })
    result = track_job(job, _make_config())
    assert len(result.performance) == 1
    assert result.performance[0].likes == 300
    call_url = mock_post.call_args[0][0]
    assert "video/query" in call_url
```

- [ ] **Step 2: Run to verify they fail**

```bash
.venv/bin/python -m pytest tests/test_tracker.py::test_track_tiktok_resolves_video_id_and_fetches_metrics tests/test_tracker.py::test_track_tiktok_uses_cached_video_id -v
```

Expected: FAIL — `NotImplementedError` (caught as warning, performance stays empty → assertion fails)

- [ ] **Step 3: Replace `_fetch_tiktok` in `tracker.py`**

Replace the placeholder `_fetch_tiktok` method body:

```python
def _fetch_tiktok(result: dict, job: ContentJob, config: Config) -> PostPerformance | None:
    token = config.tiktok_access_token
    headers = _auth_headers(token)
    video_id = result.get("video_id")
    if not video_id:
        list_resp = requests.post(
            f"{_TIKTOK_BASE}/video/list/",
            params={"fields": "id,create_time,like_count,view_count,share_count"},
            headers={**headers, "Content-Type": "application/json; charset=UTF-8"},
            json={"max_count": 10},
        )
        list_resp.raise_for_status()
        videos = list_resp.json().get("data", {}).get("videos", [])
        job_ts = _job_publish_time(job)
        matched = next(
            (v for v in videos if abs(v.get("create_time", 0) - job_ts) <= _TIKTOK_MATCH_WINDOW),
            None,
        )
        if not matched:
            logger.warning(
                "TikTok: could not match video for job %s within ±%ds window",
                job.id,
                _TIKTOK_MATCH_WINDOW,
            )
            return None
        video_id = matched["id"]
        result["video_id"] = video_id
    else:
        query_resp = requests.post(
            f"{_TIKTOK_BASE}/video/query/",
            params={"fields": "id,like_count,view_count,share_count"},
            headers={**headers, "Content-Type": "application/json; charset=UTF-8"},
            json={"filters": {"video_ids": [video_id]}},
        )
        query_resp.raise_for_status()
        videos = query_resp.json().get("data", {}).get("videos", [])
        matched = videos[0] if videos else None
        if not matched:
            return None
    return PostPerformance(
        platform="tiktok",
        likes=matched.get("like_count"),
        reach=matched.get("view_count"),
        shares=matched.get("share_count"),
        recorded_at=datetime.now(timezone.utc),
    )
```

- [ ] **Step 4: Run the 2 new tests**

```bash
.venv/bin/python -m pytest tests/test_tracker.py::test_track_tiktok_resolves_video_id_and_fetches_metrics tests/test_tracker.py::test_track_tiktok_uses_cached_video_id -v
```

Expected: both PASS.

- [ ] **Step 5: Run full test suite**

```bash
.venv/bin/python -m pytest --tb=short -q
```

Expected: 108 passed (106 + 2).

- [ ] **Step 6: Commit**

```bash
git add tracker.py tests/test_tracker.py
git commit -m "feat(tracker): add TikTok metrics via video list resolution and query"
```

---

## Task 3: `--track` CLI flag in `main.py`

**Files:**
- Modify: `main.py`
- Modify: `tests/test_tracker.py` (add 1 test)

- [ ] **Step 1: Add 1 failing test at the bottom of `tests/test_tracker.py`**

```python
def test_main_track_flag_dispatches_tracker(mocker, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from tests.test_publish import make_image_job, make_publish_config
    from job_store import save_job

    job = make_image_job(dry_run=False)
    job.stage = "publish_done"
    job.publish_result = {"facebook": {"status": "published", "id": "post-1"}}
    save_job(job)

    mock_track = mocker.patch("main.track_job", return_value=job)
    mocker.patch("main.Config.from_env", return_value=make_publish_config())

    import sys
    sys.argv = ["main.py", "--track", job.id]
    from main import main
    main()

    mock_track.assert_called_once()
```

- [ ] **Step 2: Run to verify it fails**

```bash
.venv/bin/python -m pytest tests/test_tracker.py::test_main_track_flag_dispatches_tracker -v
```

Expected: FAIL — `error: one of the arguments --project/--resume/--publish-only is required`

- [ ] **Step 3: Update `main.py`**

Replace the import block at the top of `main.py`:

```python
from __future__ import annotations
import argparse
import sys
from agents.publish import PublishAgent
from config import Config, MissingAPIKeyError
from job_store import find_job, save_job
from models.content_job import ContentJob, JobStatus
from orchestrator import Orchestrator
from project_loader import load_project, ProjectNotFoundError
from tracker import track_job
```

Add `--track` to the mutually exclusive group (after `--publish-only`):

```python
    group.add_argument("--track", metavar="JOB_ID",
                       help="Fetch and record post metrics for a published job")
```

Add the `--track` handler block after the `--publish-only` block (line 49, before `if args.resume:`):

```python
    if args.track:
        try:
            job = find_job(args.track)
        except FileNotFoundError as e:
            print(f"Error: {e}")
            sys.exit(1)
        if job.stage != "publish_done":
            print(f"Error: job {job.id} is at stage '{job.stage}', expected 'publish_done'.")
            sys.exit(1)
        print(f"Tracking job {job.id} for {job.pm.page_name}")
        job = track_job(job, config)
        save_job(job)
        if not job.performance:
            print("No metrics available.")
        else:
            latest: dict = {}
            for p in job.performance:
                latest[p.platform] = p
            for platform, p in latest.items():
                print(
                    f"{platform}: likes={p.likes}, reach={p.reach}, "
                    f"shares={p.shares}, saves={p.saves}"
                )
        return
```

- [ ] **Step 4: Run the new test**

```bash
.venv/bin/python -m pytest tests/test_tracker.py::test_main_track_flag_dispatches_tracker -v
```

Expected: PASS.

- [ ] **Step 5: Run full test suite**

```bash
.venv/bin/python -m pytest --tb=short -q
```

Expected: 109 passed (108 + 1).

- [ ] **Step 6: Verify ruff**

```bash
.venv/bin/python -m ruff check tracker.py main.py
```

Expected: no output.

- [ ] **Step 7: Commit**

```bash
git add main.py tests/test_tracker.py
git commit -m "feat(main): add --track CLI flag for performance tracking"
```
