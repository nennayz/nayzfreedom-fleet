# Phase 4 — Meta Publishing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `PublishAgent` that posts completed content jobs to Facebook and Instagram via Meta Graph API, with immediate or scheduled publish, partial-success per platform, and a `--publish-only` retry flag.

**Architecture:** `PublishAgent(BaseAgent)` in `agents/publish.py` iterates over `job.platforms`, uploads media directly to Meta (multipart for FB, resumable upload for IG Reels, source upload for IG images), creates post/container objects with optional scheduling, and stores per-platform results in `job.publish_result`. Config gains `meta_page_id` and `meta_ig_user_id`. Robin's orchestrator gains `run_publish` as a step-12 tool. `main.py` gains `--publish-only <job_id>` and `--schedule` flags.

**Tech Stack:** Python 3.9, `requests` (already in requirements.txt), Meta Graph API v19.0, Meta Resumable Upload API

---

## Files

| File | Change |
|---|---|
| `config.py` | Add `meta_page_id: str = ""`, `meta_ig_user_id: str = ""` |
| `.env.example` | Add `META_PAGE_ID=`, `META_IG_USER_ID=` |
| `agents/publish.py` | Create `PublishAgent` — all Meta publish logic |
| `tests/test_publish.py` | Create — all `PublishAgent` tests |
| `tools/agent_tools.py` | Add `run_publish` tool definition |
| `orchestrator.py` | Import + register `PublishAgent`; update Robin system prompt |
| `main.py` | Add `--publish-only <job_id>` and `--schedule` flags |
| `tests/test_config.py` | Add tests for two new Config fields |

---

### Task 1: Add `meta_page_id` and `meta_ig_user_id` to Config

**Files:**
- Modify: `config.py`
- Modify: `.env.example`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_config.py`:

```python
def test_config_loads_meta_page_id(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "key")
    monkeypatch.setenv("META_PAGE_ID", "123456789")
    monkeypatch.setenv("META_IG_USER_ID", "987654321")
    cfg = Config.from_env()
    assert cfg.meta_page_id == "123456789"
    assert cfg.meta_ig_user_id == "987654321"


def test_config_meta_fields_default_empty(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "key")
    monkeypatch.delenv("META_PAGE_ID", raising=False)
    monkeypatch.delenv("META_IG_USER_ID", raising=False)
    cfg = Config.from_env()
    assert cfg.meta_page_id == ""
    assert cfg.meta_ig_user_id == ""
```

- [ ] **Step 2: Run tests — confirm they FAIL**

```bash
.venv/bin/python -m pytest tests/test_config.py::test_config_loads_meta_page_id tests/test_config.py::test_config_meta_fields_default_empty -v
```

Expected: FAIL with `AttributeError: 'Config' object has no attribute 'meta_page_id'`

- [ ] **Step 3: Update `config.py`**

Replace the `Config` dataclass and `from_env` method:

```python
from __future__ import annotations
import os
from dataclasses import dataclass
from dotenv import load_dotenv


class MissingAPIKeyError(Exception):
    pass


@dataclass
class Config:
    anthropic_api_key: str
    brave_search_api_key: str
    openai_api_key: str
    google_cloud_project: str = ""
    google_application_credentials: str = ""
    meta_access_token: str = ""
    meta_page_id: str = ""
    meta_ig_user_id: str = ""
    tiktok_access_token: str = ""
    youtube_api_key: str = ""

    @classmethod
    def from_env(cls) -> Config:
        load_dotenv()
        anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not anthropic_key:
            raise MissingAPIKeyError("ANTHROPIC_API_KEY is required")
        return cls(
            anthropic_api_key=anthropic_key,
            brave_search_api_key=os.getenv("BRAVE_SEARCH_API_KEY", ""),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            google_cloud_project=os.getenv("GOOGLE_CLOUD_PROJECT", ""),
            google_application_credentials=os.getenv("GOOGLE_APPLICATION_CREDENTIALS", ""),
            meta_access_token=os.getenv("META_ACCESS_TOKEN", ""),
            meta_page_id=os.getenv("META_PAGE_ID", ""),
            meta_ig_user_id=os.getenv("META_IG_USER_ID", ""),
            tiktok_access_token=os.getenv("TIKTOK_ACCESS_TOKEN", ""),
            youtube_api_key=os.getenv("YOUTUBE_API_KEY", ""),
        )
```

- [ ] **Step 4: Update `.env.example`**

Replace entire file:

```
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
BRAVE_SEARCH_API_KEY=
GOOGLE_CLOUD_PROJECT=
GOOGLE_APPLICATION_CREDENTIALS=
META_ACCESS_TOKEN=
META_PAGE_ID=
META_IG_USER_ID=
TIKTOK_ACCESS_TOKEN=
YOUTUBE_API_KEY=
```

- [ ] **Step 5: Run tests — confirm PASS**

```bash
.venv/bin/python -m pytest tests/test_config.py -v
```

Expected: all PASS

- [ ] **Step 6: Run full suite — no regressions**

```bash
.venv/bin/python -m pytest --tb=short -q
```

Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add config.py .env.example tests/test_config.py
git commit -m "feat(config): add meta_page_id and meta_ig_user_id fields"
```

---

### Task 2: PublishAgent skeleton + `run_dry`

**Files:**
- Create: `agents/publish.py`
- Create: `tests/test_publish.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_publish.py`:

```python
from agents.publish import PublishAgent
from config import Config
from tests.test_lila import make_job_with_bella_output
from models.content_job import ContentType, ImageCaption, Article


def make_publish_config():
    return Config(
        anthropic_api_key="test",
        brave_search_api_key="brave",
        openai_api_key="oai",
        meta_access_token="meta-token",
        meta_page_id="page-123",
        meta_ig_user_id="ig-456",
    )


def make_image_job(dry_run=True):
    from tests.test_bella import make_job_with_idea
    job = make_job_with_idea(dry_run=dry_run, content_type=ContentType.IMAGE)
    job.bella_output = ImageCaption(caption="Soft glam look", alt_text="Woman in gold")
    job.visual_prompt = "Gold lipstick on marble"
    job.image_path = "assets/placeholder.png"
    job.growth_strategy = _make_growth_strategy()
    return job


def make_video_job(dry_run=True, video_path=None):
    from tests.test_bella import make_job_with_idea
    from models.content_job import Script
    job = make_job_with_idea(dry_run=dry_run, content_type=ContentType.VIDEO)
    job.bella_output = Script(hook="h", body="b", cta="c", duration_seconds=30)
    job.visual_prompt = "Cinematic gold close-up"
    job.video_path = video_path
    job.growth_strategy = _make_growth_strategy()
    return job


def make_article_job(dry_run=True):
    from tests.test_bella import make_job_with_idea
    job = make_job_with_idea(dry_run=dry_run, content_type=ContentType.ARTICLE)
    job.bella_output = Article(heading="The Look", body="Step 1...", cta="Shop now")
    job.growth_strategy = _make_growth_strategy()
    return job


def _make_growth_strategy():
    from models.content_job import GrowthStrategy
    return GrowthStrategy(
        hashtags=["#glam"],
        caption="look of the day",
        best_post_time_utc="13:00",
        best_post_time_thai="20:00",
    )


def test_publish_dry_run_sets_result():
    agent = PublishAgent(make_publish_config())
    job = make_image_job(dry_run=True)
    job = agent.run(job)
    assert job.publish_result == {"dry_run": True, "platforms": job.platforms}
    assert job.stage == "publish_done"
```

- [ ] **Step 2: Run test — confirm FAIL**

```bash
.venv/bin/python -m pytest tests/test_publish.py::test_publish_dry_run_sets_result -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'agents.publish'`

- [ ] **Step 3: Create `agents/publish.py` with skeleton + `run_dry`**

```python
from __future__ import annotations
import requests
from pathlib import Path
from agents.base_agent import BaseAgent
from models.content_job import ContentJob, ContentType

_META_GRAPH_BASE = "https://graph.facebook.com/v19.0"
_META_RUPLOAD_BASE = "https://rupload.facebook.com/video-upload/v19.0"


class PublishAgent(BaseAgent):
    def run_dry(self, job: ContentJob, **kwargs) -> ContentJob:
        job.publish_result = {"dry_run": True, "platforms": job.platforms}
        job.stage = "publish_done"
        return job

    def run_live(self, job: ContentJob, **kwargs) -> ContentJob:
        schedule: bool = kwargs.get("schedule", False)
        effective_platforms = [
            p for p in job.platforms
            if not (job.content_type == ContentType.ARTICLE and p == "instagram")
        ]
        result: dict = {}
        media_path = job.video_path if job.content_type == ContentType.VIDEO else job.image_path
        if not media_path:
            raise ValueError(
                f"PublishAgent: no media file on job {job.id} "
                f"(content_type={job.content_type})"
            )
        if not Path(media_path).exists():
            raise ValueError(
                f"PublishAgent: media file not found: {media_path} (job {job.id})"
            )
        scheduled_time = self._scheduled_unix_ts(job) if schedule else None
        caption = self._build_caption(job)
        for platform in effective_platforms:
            try:
                if platform == "facebook":
                    post_result = self._post_facebook(job, caption, scheduled_time)
                elif platform == "instagram":
                    post_result = self._post_instagram(job, caption, scheduled_time)
                else:
                    result[platform] = {"status": "skipped", "error": f"unsupported platform: {platform}"}
                    continue
                status = "scheduled" if scheduled_time else "published"
                result[platform] = {"status": status, **post_result}
            except Exception as e:
                result[platform] = {"status": "failed", "error": str(e)}
        job.publish_result = result
        job.stage = "publish_done"
        return job

    def _build_caption(self, job: ContentJob) -> str:
        if job.growth_strategy is None:
            return ""
        tags = " ".join(job.growth_strategy.hashtags)
        return f"{job.growth_strategy.caption}\n\n{tags}"

    def _scheduled_unix_ts(self, job: ContentJob) -> int | None:
        if job.growth_strategy is None:
            return None
        from datetime import datetime, timezone
        try:
            hh, mm = job.growth_strategy.best_post_time_utc.split(":")
            now = datetime.now(timezone.utc)
            scheduled = now.replace(hour=int(hh), minute=int(mm), second=0, microsecond=0)
            if scheduled <= now:
                from datetime import timedelta
                scheduled += timedelta(days=1)
            return int(scheduled.timestamp())
        except Exception:
            return None

    def _post_facebook(self, job: ContentJob, caption: str, scheduled_time: int | None) -> dict:
        raise NotImplementedError

    def _post_instagram(self, job: ContentJob, caption: str, scheduled_time: int | None) -> dict:
        raise NotImplementedError
```

- [ ] **Step 4: Run test — confirm PASS**

```bash
.venv/bin/python -m pytest tests/test_publish.py::test_publish_dry_run_sets_result -v
```

Expected: PASS

- [ ] **Step 5: Run full suite — no regressions**

```bash
.venv/bin/python -m pytest --tb=short -q
```

Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add agents/publish.py tests/test_publish.py
git commit -m "feat(publish): add PublishAgent skeleton with run_dry"
```

---

### Task 3: `_post_facebook` — image, video, article

**Files:**
- Modify: `agents/publish.py`
- Modify: `tests/test_publish.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_publish.py`:

```python
def test_publish_live_fb_image_calls_photos_endpoint(mocker, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    img_file = tmp_path / "image.png"
    img_file.write_bytes(b"PNG")
    mock_post = mocker.patch("agents.publish.requests.post")
    mock_post.return_value.raise_for_status = mocker.MagicMock()
    mock_post.return_value.json.return_value = {"id": "post-1"}
    agent = PublishAgent(make_publish_config())
    job = make_image_job(dry_run=False)
    job.image_path = str(img_file)
    job.platforms = ["facebook"]
    job = agent.run(job)
    assert mock_post.called
    call_url = mock_post.call_args[0][0]
    assert "page-123/photos" in call_url
    assert job.publish_result["facebook"]["status"] == "published"


def test_publish_live_fb_video_calls_videos_endpoint(mocker, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    vid_file = tmp_path / "video.mp4"
    vid_file.write_bytes(b"MP4")
    mock_post = mocker.patch("agents.publish.requests.post")
    mock_post.return_value.raise_for_status = mocker.MagicMock()
    mock_post.return_value.json.return_value = {"id": "vid-1"}
    agent = PublishAgent(make_publish_config())
    job = make_video_job(dry_run=False, video_path=str(vid_file))
    job.platforms = ["facebook"]
    job = agent.run(job)
    call_url = mock_post.call_args[0][0]
    assert "page-123/videos" in call_url
    assert job.publish_result["facebook"]["status"] == "published"


def test_publish_live_fb_article_calls_feed_endpoint(mocker):
    mock_post = mocker.patch("agents.publish.requests.post")
    mock_post.return_value.raise_for_status = mocker.MagicMock()
    mock_post.return_value.json.return_value = {"id": "feed-1"}
    agent = PublishAgent(make_publish_config())
    job = make_article_job(dry_run=False)
    job.platforms = ["facebook"]
    job = agent.run(job)
    call_url = mock_post.call_args[0][0]
    assert "page-123/feed" in call_url
    assert job.publish_result["facebook"]["status"] == "published"


def test_publish_live_fb_schedule_flag_sends_scheduled_time(mocker, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    img_file = tmp_path / "image.png"
    img_file.write_bytes(b"PNG")
    mock_post = mocker.patch("agents.publish.requests.post")
    mock_post.return_value.raise_for_status = mocker.MagicMock()
    mock_post.return_value.json.return_value = {"id": "post-sched"}
    agent = PublishAgent(make_publish_config())
    job = make_image_job(dry_run=False)
    job.image_path = str(img_file)
    job.platforms = ["facebook"]
    job = agent.run(job, schedule=True)
    call_data = mock_post.call_args[1].get("data", mock_post.call_args[0][1] if len(mock_post.call_args[0]) > 1 else {})
    assert "scheduled_publish_time" in str(mock_post.call_args)
    assert job.publish_result["facebook"]["status"] == "scheduled"
```

- [ ] **Step 2: Run tests — confirm FAIL**

```bash
.venv/bin/python -m pytest tests/test_publish.py::test_publish_live_fb_image_calls_photos_endpoint tests/test_publish.py::test_publish_live_fb_video_calls_videos_endpoint tests/test_publish.py::test_publish_live_fb_article_calls_feed_endpoint tests/test_publish.py::test_publish_live_fb_schedule_flag_sends_scheduled_time -v
```

Expected: FAIL with `NotImplementedError`

- [ ] **Step 3: Implement `_post_facebook` in `agents/publish.py`**

Replace the `_post_facebook` stub:

```python
    def _post_facebook(self, job: ContentJob, caption: str, scheduled_time: int | None) -> dict:
        token = self.config.meta_access_token
        page_id = self.config.meta_page_id
        if job.content_type == ContentType.ARTICLE:
            url = f"{_META_GRAPH_BASE}/{page_id}/feed"
            data: dict = {"message": caption, "access_token": token}
            if scheduled_time:
                data["scheduled_publish_time"] = str(scheduled_time)
                data["published"] = "false"
            resp = requests.post(url, data=data)
            resp.raise_for_status()
            return resp.json()
        media_path = job.image_path if job.content_type != ContentType.VIDEO else job.video_path
        assert media_path is not None
        if job.content_type == ContentType.VIDEO:
            url = f"{_META_GRAPH_BASE}/{page_id}/videos"
            field = "description"
        else:
            url = f"{_META_GRAPH_BASE}/{page_id}/photos"
            field = "caption"
        data = {field: caption, "access_token": token}
        if scheduled_time:
            data["scheduled_publish_time"] = str(scheduled_time)
            data["published"] = "false"
        with open(media_path, "rb") as f:
            resp = requests.post(url, data=data, files={"source": f})
        resp.raise_for_status()
        return resp.json()
```

- [ ] **Step 4: Run tests — confirm PASS**

```bash
.venv/bin/python -m pytest tests/test_publish.py::test_publish_live_fb_image_calls_photos_endpoint tests/test_publish.py::test_publish_live_fb_video_calls_videos_endpoint tests/test_publish.py::test_publish_live_fb_article_calls_feed_endpoint tests/test_publish.py::test_publish_live_fb_schedule_flag_sends_scheduled_time -v
```

Expected: 4 PASSED

- [ ] **Step 5: Run full suite — no regressions**

```bash
.venv/bin/python -m pytest --tb=short -q
```

Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add agents/publish.py tests/test_publish.py
git commit -m "feat(publish): implement _post_facebook for image, video, article"
```

---

### Task 4: `_post_instagram` — image feed + Reels

**Files:**
- Modify: `agents/publish.py`
- Modify: `tests/test_publish.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_publish.py`:

```python
def test_publish_live_ig_image_creates_container_then_publishes(mocker, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    img_file = tmp_path / "image.png"
    img_file.write_bytes(b"PNG")
    mock_post = mocker.patch("agents.publish.requests.post")
    container_resp = mocker.MagicMock()
    container_resp.raise_for_status = mocker.MagicMock()
    container_resp.json.return_value = {"id": "container-1"}
    publish_resp = mocker.MagicMock()
    publish_resp.raise_for_status = mocker.MagicMock()
    publish_resp.json.return_value = {"id": "ig-post-1"}
    mock_post.side_effect = [container_resp, publish_resp]
    agent = PublishAgent(make_publish_config())
    job = make_image_job(dry_run=False)
    job.image_path = str(img_file)
    job.platforms = ["instagram"]
    job = agent.run(job)
    assert mock_post.call_count == 2
    container_url = mock_post.call_args_list[0][0][0]
    publish_url = mock_post.call_args_list[1][0][0]
    assert "ig-456/media" in container_url
    assert "ig-456/media_publish" in publish_url
    assert job.publish_result["instagram"]["status"] == "published"


def test_publish_live_ig_reels_uses_resumable_upload(mocker, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    vid_file = tmp_path / "video.mp4"
    vid_file.write_bytes(b"MP4")
    mock_post = mocker.patch("agents.publish.requests.post")
    init_resp = mocker.MagicMock()
    init_resp.raise_for_status = mocker.MagicMock()
    init_resp.json.return_value = {"id": "container-2", "uri": "https://rupload.facebook.com/upload-123"}
    upload_resp = mocker.MagicMock()
    upload_resp.raise_for_status = mocker.MagicMock()
    upload_resp.json.return_value = {"success": True}
    publish_resp = mocker.MagicMock()
    publish_resp.raise_for_status = mocker.MagicMock()
    publish_resp.json.return_value = {"id": "reel-1"}
    mock_post.side_effect = [init_resp, upload_resp, publish_resp]
    agent = PublishAgent(make_publish_config())
    job = make_video_job(dry_run=False, video_path=str(vid_file))
    job.platforms = ["instagram"]
    job = agent.run(job)
    assert mock_post.call_count == 3
    init_url = mock_post.call_args_list[0][0][0]
    upload_url = mock_post.call_args_list[1][0][0]
    publish_url = mock_post.call_args_list[2][0][0]
    assert "ig-456/media" in init_url
    assert "rupload.facebook.com" in upload_url
    assert "ig-456/media_publish" in publish_url
    assert job.publish_result["instagram"]["status"] == "published"
```

- [ ] **Step 2: Run tests — confirm FAIL**

```bash
.venv/bin/python -m pytest tests/test_publish.py::test_publish_live_ig_image_creates_container_then_publishes tests/test_publish.py::test_publish_live_ig_reels_uses_resumable_upload -v
```

Expected: FAIL with `NotImplementedError`

- [ ] **Step 3: Implement `_post_instagram` in `agents/publish.py`**

Replace the `_post_instagram` stub:

```python
    def _post_instagram(self, job: ContentJob, caption: str, scheduled_time: int | None) -> dict:
        token = self.config.meta_access_token
        ig_user_id = self.config.meta_ig_user_id
        base = _META_GRAPH_BASE
        if job.content_type == ContentType.VIDEO:
            return self._post_ig_reel(job, caption, scheduled_time, token, ig_user_id, base)
        return self._post_ig_image(job, caption, scheduled_time, token, ig_user_id, base)

    def _post_ig_image(
        self,
        job: ContentJob,
        caption: str,
        scheduled_time: int | None,
        token: str,
        ig_user_id: str,
        base: str,
    ) -> dict:
        assert job.image_path is not None
        url = f"{base}/{ig_user_id}/media"
        data: dict = {"caption": caption, "access_token": token}
        if scheduled_time:
            data["scheduled_publish_time"] = str(scheduled_time)
        with open(job.image_path, "rb") as f:
            resp = requests.post(url, data=data, files={"source": f})
        resp.raise_for_status()
        container_id = resp.json()["id"]
        pub_url = f"{base}/{ig_user_id}/media_publish"
        pub_resp = requests.post(pub_url, data={"creation_id": container_id, "access_token": token})
        pub_resp.raise_for_status()
        return pub_resp.json()

    def _post_ig_reel(
        self,
        job: ContentJob,
        caption: str,
        scheduled_time: int | None,
        token: str,
        ig_user_id: str,
        base: str,
    ) -> dict:
        assert job.video_path is not None
        file_size = Path(job.video_path).stat().st_size
        url = f"{base}/{ig_user_id}/media"
        init_data: dict = {
            "media_type": "REELS",
            "upload_type": "resumable",
            "caption": caption,
            "access_token": token,
        }
        if scheduled_time:
            init_data["scheduled_publish_time"] = str(scheduled_time)
        init_resp = requests.post(
            url,
            data=init_data,
            headers={"file_size": str(file_size), "file_type": "video/mp4"},
        )
        init_resp.raise_for_status()
        init_json = init_resp.json()
        container_id = init_json["id"]
        upload_uri = init_json.get(
            "uri", f"https://rupload.facebook.com/video-upload/v19.0/{container_id}"
        )
        with open(job.video_path, "rb") as f:
            upload_resp = requests.post(
                upload_uri,
                headers={
                    "Authorization": f"OAuth {token}",
                    "offset": "0",
                    "file_size": str(file_size),
                },
                data=f,
            )
        upload_resp.raise_for_status()
        pub_url = f"{base}/{ig_user_id}/media_publish"
        pub_resp = requests.post(pub_url, data={"creation_id": container_id, "access_token": token})
        pub_resp.raise_for_status()
        return pub_resp.json()
```

- [ ] **Step 4: Run tests — confirm PASS**

```bash
.venv/bin/python -m pytest tests/test_publish.py::test_publish_live_ig_image_creates_container_then_publishes tests/test_publish.py::test_publish_live_ig_reels_uses_resumable_upload -v
```

Expected: 2 PASSED

- [ ] **Step 5: Run full suite — no regressions**

```bash
.venv/bin/python -m pytest --tb=short -q
```

Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add agents/publish.py tests/test_publish.py
git commit -m "feat(publish): implement _post_instagram for image feed and Reels"
```

---

### Task 5: `run_live` — multi-platform, ARTICLE skip, partial success, missing media guard

**Files:**
- Modify: `tests/test_publish.py` (new tests only)

Note: `run_live` skeleton was written in Task 2. These tests exercise the complete behaviour.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_publish.py`:

```python
def test_publish_article_skips_instagram(mocker):
    mock_post = mocker.patch("agents.publish.requests.post")
    mock_post.return_value.raise_for_status = mocker.MagicMock()
    mock_post.return_value.json.return_value = {"id": "fb-1"}
    agent = PublishAgent(make_publish_config())
    job = make_article_job(dry_run=False)
    job.platforms = ["instagram", "facebook"]
    job = agent.run(job)
    assert "instagram" not in job.publish_result
    assert job.publish_result["facebook"]["status"] == "published"
    call_url = mock_post.call_args[0][0]
    assert "ig-456" not in call_url


def test_publish_partial_failure_records_per_platform(mocker, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    img_file = tmp_path / "image.png"
    img_file.write_bytes(b"PNG")
    mock_post = mocker.patch("agents.publish.requests.post")
    fb_resp = mocker.MagicMock()
    fb_resp.raise_for_status = mocker.MagicMock()
    fb_resp.json.return_value = {"id": "fb-ok"}
    mock_post.side_effect = [fb_resp, Exception("IG quota exceeded")]
    agent = PublishAgent(make_publish_config())
    job = make_image_job(dry_run=False)
    job.image_path = str(img_file)
    job.platforms = ["facebook", "instagram"]
    job = agent.run(job)
    assert job.publish_result["facebook"]["status"] == "published"
    assert job.publish_result["instagram"]["status"] == "failed"
    assert "IG quota exceeded" in job.publish_result["instagram"]["error"]
    assert job.stage == "publish_done"


def test_publish_missing_image_path_raises_value_error():
    agent = PublishAgent(make_publish_config())
    job = make_image_job(dry_run=False)
    job.image_path = None
    import pytest
    with pytest.raises(ValueError, match=job.id):
        agent.run(job)


def test_publish_missing_media_file_raises_value_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import pytest
    agent = PublishAgent(make_publish_config())
    job = make_image_job(dry_run=False)
    job.image_path = str(tmp_path / "nonexistent.png")
    with pytest.raises(ValueError, match=job.id):
        agent.run(job)
```

- [ ] **Step 2: Run tests — confirm FAIL**

```bash
.venv/bin/python -m pytest tests/test_publish.py::test_publish_article_skips_instagram tests/test_publish.py::test_publish_partial_failure_records_per_platform tests/test_publish.py::test_publish_missing_image_path_raises_value_error tests/test_publish.py::test_publish_missing_media_file_raises_value_error -v
```

Expected: FAIL — partial failure test fails because current `run_live` lets the exception propagate; missing media tests fail because `run_live` is not yet wired.

Wait — `run_live` skeleton is already written in Task 2 with the missing-media guard and partial-success try/except. These tests should PASS after Task 2 IF `_post_facebook` and `_post_instagram` are implemented. The partial failure test needs IG to fail — `mock_post.side_effect = [fb_resp, Exception(...)]`. FB calls `_post_facebook` (1 call), IG calls `_post_ig_image` (tries 1st `requests.post` → raises Exception) → caught and recorded.

Run them now:

```bash
.venv/bin/python -m pytest tests/test_publish.py::test_publish_article_skips_instagram tests/test_publish.py::test_publish_partial_failure_records_per_platform tests/test_publish.py::test_publish_missing_image_path_raises_value_error tests/test_publish.py::test_publish_missing_media_file_raises_value_error -v
```

Expected: 4 PASSED (behaviour is already implemented in `run_live` skeleton from Task 2). If any fail, check the error and fix.

- [ ] **Step 3: Run full suite — no regressions**

```bash
.venv/bin/python -m pytest --tb=short -q
```

Expected: all PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_publish.py
git commit -m "test(publish): add multi-platform, partial-failure, and missing-media tests"
```

---

### Task 6: Orchestrator wiring — `run_publish` tool + Robin step 12

**Files:**
- Modify: `tools/agent_tools.py`
- Modify: `orchestrator.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_publish.py`:

```python
def test_publish_tool_registered_in_agent_tools():
    from tools.agent_tools import get_tool_definitions
    names = [t["name"] for t in get_tool_definitions()]
    assert "run_publish" in names


def test_publish_agent_registered_in_orchestrator():
    from orchestrator import Orchestrator
    from config import Config
    cfg = Config(anthropic_api_key="k", brave_search_api_key="b", openai_api_key="o")
    orch = Orchestrator(cfg)
    assert "publish" in orch.agents
```

- [ ] **Step 2: Run tests — confirm FAIL**

```bash
.venv/bin/python -m pytest tests/test_publish.py::test_publish_tool_registered_in_agent_tools tests/test_publish.py::test_publish_agent_registered_in_orchestrator -v
```

Expected: FAIL — `run_publish` not in tool definitions, `publish` not in `orch.agents`

- [ ] **Step 3: Add `run_publish` to `tools/agent_tools.py`**

Add to the list returned by `get_tool_definitions()`, after `run_emma`:

```python
        {
            "name": "run_publish",
            "description": (
                "Publish the approved content to Facebook and Instagram via Meta Graph API. "
                "Call this as the final step after final_approval checkpoint. "
                "Pass schedule=true to post at Roxy's recommended time instead of immediately."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "schedule": {
                        "type": "boolean",
                        "description": "If true, schedule post at best_post_time_utc. Default false.",
                    }
                },
                "required": [],
            },
        },
```

- [ ] **Step 4: Update `orchestrator.py` — import, register, update system prompt, pass kwarg**

Replace the entire file:

```python
from __future__ import annotations
import json
import anthropic
from agents.mia import MiaAgent
from agents.zoe import ZoeAgent
from agents.bella import BellaAgent
from agents.lila import LilaAgent
from agents.nora import NoraAgent
from agents.roxy import RoxyAgent
from agents.emma import EmmaAgent
from agents.publish import PublishAgent
from checkpoint import pause
from config import Config
from job_store import save_job, load_recent_performance
from models.content_job import ContentJob, JobStatus
from tools.agent_tools import get_tool_definitions

_ROBIN_SYSTEM = """You are Robin, Chief of Staff at NayzFreedom.

You act directly on behalf of the owner. Every decision you make optimizes for maximum business benefit — reach, engagement, and brand growth — not just task completion.

Before recommending strategy, review past job performance data provided in context. If no performance data exists, proceed without it.

You coordinate Freedom Architects (Mia, Zoe, Bella, Lila, Nora, Roxy, Emma) through {pm_name}, the PM for {page_name}.

## Team workflow (follow this order):
1. run_mia — research trends
2. run_zoe — generate ideas (each idea has a content_type)
3. request_checkpoint (stage: "idea_selection") — show ideas, wait for user to pick one
4. run_bella — write content for the selected idea based on its content_type
5. After Bella completes, check job.content_type:
   - video, image, or infographic → run_lila (visual direction)
   - article → skip run_lila entirely, go directly to step 6
6. request_checkpoint (stage: "content_review") — show content and visual (if applicable) for approval
7. run_nora — QA review. If QA fails and retry count < max_retries, re-run the relevant agent.
8. request_checkpoint (stage: "qa_review") — show QA result
9. run_roxy — hashtags + caption + timing + editorial guidance
10. run_emma — community FAQ
11. request_checkpoint (stage: "final_approval") — final sign-off before publishing
12. run_publish — publish to Meta (Facebook + Instagram). Pass schedule=true to post at Roxy's recommended time.

Never skip a checkpoint. After run_publish completes, declare the job complete.
"""


class Orchestrator:
    def __init__(self, config: Config):
        self.config = config
        self.client = anthropic.Anthropic(api_key=config.anthropic_api_key)
        self.agents = {
            "mia": MiaAgent(config),
            "zoe": ZoeAgent(config),
            "bella": BellaAgent(config),
            "lila": LilaAgent(config),
            "nora": NoraAgent(config),
            "roxy": RoxyAgent(config),
            "emma": EmmaAgent(config),
            "publish": PublishAgent(config),
        }

    def run(self, job: ContentJob) -> ContentJob:
        job.status = JobStatus.RUNNING
        system_prompt = _ROBIN_SYSTEM.format(
            pm_name=job.pm.name,
            page_name=job.pm.page_name,
        )
        perf_summary = load_recent_performance(job.pm.page_name)
        first_message = f"Brief: {job.brief}\nPlatforms: {', '.join(job.platforms)}"
        if perf_summary:
            first_message = f"{perf_summary}\n\n{first_message}"
        messages: list[dict] = [{"role": "user", "content": first_message}]

        while True:
            response = self.client.messages.create(
                model="claude-opus-4-7",
                max_tokens=4096,
                system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
                tools=get_tool_definitions(),
                messages=messages,
            )

            if response.stop_reason == "end_turn":
                job.status = JobStatus.COMPLETED
                save_job(job)
                return job

            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                result = self._dispatch(block.name, block.input, job)
                save_job(job)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result),
                })

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

    def _dispatch(self, tool_name: str, tool_input: dict, job: ContentJob) -> dict:
        if tool_name == "request_checkpoint":
            result = pause(
                stage=tool_input.get("stage"),
                summary=tool_input.get("summary"),
                options=tool_input.get("options", []),
                job=job,
            )
            if tool_input.get("stage") == "idea_selection" and job.ideas is not None:
                try:
                    decision_num = int(result.decision)
                    matched = next(
                        (i for i in job.ideas if i.number == decision_num), None
                    )
                    if matched is not None:
                        job.selected_idea = matched
                        job.content_type = matched.content_type
                except ValueError:
                    pass
            return {"decision": result.decision}

        agent_name = tool_name.replace("run_", "")
        if agent_name not in self.agents:
            return {"error": f"Unknown tool: {tool_name}"}

        kwargs = {}
        if agent_name == "publish" and "schedule" in tool_input:
            kwargs["schedule"] = bool(tool_input["schedule"])

        self.agents[agent_name].run(job, **kwargs)
        return {"status": "ok", "stage": job.stage}
```

- [ ] **Step 5: Run tests — confirm PASS**

```bash
.venv/bin/python -m pytest tests/test_publish.py::test_publish_tool_registered_in_agent_tools tests/test_publish.py::test_publish_agent_registered_in_orchestrator -v
```

Expected: 2 PASSED

- [ ] **Step 6: Run full suite — no regressions**

```bash
.venv/bin/python -m pytest --tb=short -q
```

Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add tools/agent_tools.py orchestrator.py tests/test_publish.py
git commit -m "feat(orchestrator): wire PublishAgent as run_publish tool, add to Robin step 12"
```

---

### Task 7: `--publish-only` and `--schedule` CLI flags

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_publish.py`:

```python
def test_main_publish_only_flag_dispatches_publish_agent(mocker, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from tests.test_bella import make_job_with_idea
    from models.content_job import ContentType, ImageCaption, GrowthStrategy
    from job_store import save_job

    job = make_job_with_idea(dry_run=False, content_type=ContentType.IMAGE)
    job.bella_output = ImageCaption(caption="test", alt_text="test")
    job.image_path = str(tmp_path / "image.png")
    (tmp_path / "image.png").write_bytes(b"PNG")
    job.growth_strategy = GrowthStrategy(
        hashtags=["#test"], caption="test", best_post_time_utc="13:00", best_post_time_thai="20:00"
    )
    job.stage = "emma_done"
    save_job(job)

    mock_run = mocker.patch.object(PublishAgent, "run_live", return_value=job)
    mocker.patch("main.Config.from_env", return_value=make_publish_config())

    import sys
    sys.argv = ["main.py", "--publish-only", job.id]
    from main import main
    main()

    mock_run.assert_called_once()
```

- [ ] **Step 2: Run test — confirm FAIL**

```bash
.venv/bin/python -m pytest tests/test_publish.py::test_main_publish_only_flag_dispatches_publish_agent -v
```

Expected: FAIL with `SystemExit` or argument parsing error — `--publish-only` not yet defined

- [ ] **Step 3: Update `main.py`**

Replace entire file:

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


def main() -> None:
    parser = argparse.ArgumentParser(description="Slay Hack Agency — AI Content Pipeline")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--project", help="Project slug (folder name under projects/)")
    group.add_argument("--resume", metavar="JOB_ID", help="Resume an interrupted job by ID")
    group.add_argument("--publish-only", metavar="JOB_ID", help="Publish a completed job by ID (skips content generation)")
    parser.add_argument("--brief", help="Content brief (required with --project)")
    parser.add_argument("--platforms", default="instagram,facebook",
                        help="Comma-separated platforms (default: instagram,facebook)")
    parser.add_argument("--dry-run", action="store_true", help="Run with mock data, no API calls")
    parser.add_argument("--schedule", action="store_true",
                        help="Schedule post at Roxy's recommended time instead of publishing immediately")
    args = parser.parse_args()

    try:
        config = Config.from_env()
    except MissingAPIKeyError as e:
        print(f"Error: {e}\nCopy .env.example to .env and fill in your API keys.")
        sys.exit(1)

    if args.publish_only:
        try:
            job = find_job(args.publish_only)
        except FileNotFoundError as e:
            print(f"Error: {e}")
            sys.exit(1)
        print(f"Publishing job {job.id} for {job.pm.page_name} (schedule={args.schedule})")
        agent = PublishAgent(config)
        result = agent.run(job, schedule=args.schedule)
        save_job(result)
        print(f"Publish complete: {result.publish_result}")
        return

    if args.resume:
        try:
            job = find_job(args.resume)
            print(f"Resuming job {job.id} for {job.pm.page_name} (stage: {job.stage})")
        except FileNotFoundError as e:
            print(f"Error: {e}")
            sys.exit(1)
    else:
        if not args.brief:
            print("Error: --brief is required when using --project")
            sys.exit(1)
        try:
            pm = load_project(args.project)
        except ProjectNotFoundError as e:
            print(f"Error: {e}")
            sys.exit(1)
        platforms = [p.strip() for p in args.platforms.split(",")]
        job = ContentJob(
            project=args.project,
            pm=pm,
            brief=args.brief,
            platforms=platforms,
            dry_run=args.dry_run,
        )
        save_job(job)
        print(f"Starting job {job.id} for {pm.page_name}")
        if args.dry_run:
            print("[DRY-RUN MODE] No real API calls will be made.\n")

    orchestrator = Orchestrator(config)
    result = orchestrator.run(job)

    if result.status == JobStatus.COMPLETED:
        out_dir = f"output/{result.pm.page_name}/{result.id}"
        print(f"\nJob complete! Output saved to: {out_dir}")
    else:
        print(f"\nJob ended with status: {result.status}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test — confirm PASS**

```bash
.venv/bin/python -m pytest tests/test_publish.py::test_main_publish_only_flag_dispatches_publish_agent -v
```

Expected: PASS

- [ ] **Step 5: Run full suite — no regressions**

```bash
.venv/bin/python -m pytest --tb=short -q
```

Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_publish.py
git commit -m "feat(main): add --publish-only and --schedule CLI flags"
```
