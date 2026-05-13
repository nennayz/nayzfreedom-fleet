# Phase 7: YouTube Publishing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `PublishAgent` to upload VIDEO content to YouTube via the Data API v3 OAuth 2.0 resumable upload flow, and skip IMAGE/INFOGRAPHIC with a descriptive reason.

**Architecture:** Add `_youtube_access_token`, `_post_youtube`, `_post_youtube_video`, and `_youtube_scheduled_iso` to `agents/publish.py`. Update `config.py` to replace `youtube_api_key` with three OAuth 2.0 fields. No changes to orchestrator, CLI, or job_store.

**Tech Stack:** Python 3.9, `requests`, YouTube Data API v3 (`https://www.googleapis.com/upload/youtube/v3`), Google OAuth 2.0 token endpoint, pytest, pytest-mock.

---

## File Map

| File | Change |
|---|---|
| `config.py` | Replace `youtube_api_key` with `youtube_client_id`, `youtube_client_secret`, `youtube_refresh_token` |
| `.env.example` | Replace `YOUTUBE_API_KEY` with three new vars |
| `agents/publish.py` | Add 2 constants; update `effective_platforms`; add `elif youtube` branch; add 4 new methods |
| `tests/test_publish.py` | Add YouTube credentials to `make_publish_config()`; add 5 new tests |

---

## Task 1: Config update + YouTube skip + article exclusion

**Files:**
- Modify: `config.py`
- Modify: `.env.example`
- Modify: `agents/publish.py:9-13` (constants), `agents/publish.py:25-28` (effective_platforms), `agents/publish.py:43-56` (platform loop)
- Modify: `tests/test_publish.py`

- [ ] **Step 1: Add two failing tests at the bottom of `tests/test_publish.py`**

```python
def test_publish_youtube_image_skips_with_reason(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    img_file = tmp_path / "image.png"
    img_file.write_bytes(b"PNG")
    agent = PublishAgent(make_publish_config())
    job = make_image_job(dry_run=False)
    job.image_path = str(img_file)
    job.platforms = ["youtube"]
    job = agent.run(job)
    assert job.publish_result["youtube"]["status"] == "skipped"
    assert "YouTube only supports video uploads" in job.publish_result["youtube"]["reason"]


def test_publish_youtube_article_excluded_from_platforms(mocker):
    mock_post = mocker.patch("agents.publish.requests.post")
    mock_post.return_value.raise_for_status = mocker.MagicMock()
    mock_post.return_value.json.return_value = {"id": "fb-1"}
    agent = PublishAgent(make_publish_config())
    job = make_article_job(dry_run=False)
    job.platforms = ["facebook", "youtube"]
    job = agent.run(job)
    assert "youtube" not in job.publish_result
    assert job.publish_result["facebook"]["status"] == "published"
    assert mock_post.call_count == 1
    assert "page-123/feed" in mock_post.call_args_list[0][0][0]
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd /Users/nennayz/Desktop/NayzFreedom && .venv/bin/python -m pytest tests/test_publish.py::test_publish_youtube_image_skips_with_reason tests/test_publish.py::test_publish_youtube_article_excluded_from_platforms -v
```

Expected: FAIL — `test_publish_youtube_image_skips_with_reason` gets `{"status": "skipped", "error": "unsupported platform: youtube"}` (wrong key), `test_publish_youtube_article_excluded_from_platforms` has `youtube` in `publish_result`.

- [ ] **Step 3: Update `config.py` — replace `youtube_api_key` with three OAuth fields**

Replace in `config.py`:

```python
    tiktok_access_token: str = ""
    youtube_api_key: str = ""
```

With:

```python
    tiktok_access_token: str = ""
    youtube_client_id: str = ""
    youtube_client_secret: str = ""
    youtube_refresh_token: str = ""
```

Replace in `from_env`:

```python
            tiktok_access_token=os.getenv("TIKTOK_ACCESS_TOKEN", ""),
            youtube_api_key=os.getenv("YOUTUBE_API_KEY", ""),
```

With:

```python
            tiktok_access_token=os.getenv("TIKTOK_ACCESS_TOKEN", ""),
            youtube_client_id=os.getenv("YOUTUBE_CLIENT_ID", ""),
            youtube_client_secret=os.getenv("YOUTUBE_CLIENT_SECRET", ""),
            youtube_refresh_token=os.getenv("YOUTUBE_REFRESH_TOKEN", ""),
```

- [ ] **Step 4: Update `.env.example`**

Replace:
```
YOUTUBE_API_KEY=
```

With:
```
# YouTube (OAuth 2.0 refresh token flow)
YOUTUBE_CLIENT_ID=
YOUTUBE_CLIENT_SECRET=
YOUTUBE_REFRESH_TOKEN=
```

- [ ] **Step 5: Add YouTube credentials to `make_publish_config()` in `tests/test_publish.py`**

Replace:

```python
def make_publish_config():
    return Config(
        anthropic_api_key="test",
        brave_search_api_key="brave",
        openai_api_key="oai",
        meta_access_token="meta-token",
        meta_page_id="page-123",
        meta_ig_user_id="ig-456",
        tiktok_access_token="tiktok-token",
    )
```

With:

```python
def make_publish_config():
    return Config(
        anthropic_api_key="test",
        brave_search_api_key="brave",
        openai_api_key="oai",
        meta_access_token="meta-token",
        meta_page_id="page-123",
        meta_ig_user_id="ig-456",
        tiktok_access_token="tiktok-token",
        youtube_client_id="yt-client-id",
        youtube_client_secret="yt-client-secret",
        youtube_refresh_token="yt-refresh-token",
    )
```

- [ ] **Step 6: Add two module-level constants to `agents/publish.py`**

Add after `_TIKTOK_POLL_TIMEOUT = 300`:

```python
_YOUTUBE_UPLOAD_BASE = "https://www.googleapis.com/upload/youtube/v3"
_YOUTUBE_TOKEN_URL = "https://oauth2.googleapis.com/token"
```

- [ ] **Step 7: Update `effective_platforms` filter in `run_live`**

Replace:

```python
        effective_platforms = [
            p for p in job.platforms
            if not (job.content_type == ContentType.ARTICLE and p in ("instagram", "tiktok"))
        ]
```

With:

```python
        effective_platforms = [
            p for p in job.platforms
            if not (job.content_type == ContentType.ARTICLE and p in ("instagram", "tiktok", "youtube"))
        ]
```

- [ ] **Step 8: Add the `elif platform == "youtube"` branch and placeholder methods**

In `run_live`, replace the existing `else` branch:

```python
                elif platform == "tiktok":
                    post_result = self._post_tiktok(job, caption)
                    if post_result.get("status") == "skipped":
                        result[platform] = post_result
                        continue
                else:
                    result[platform] = {"status": "skipped", "error": f"unsupported platform: {platform}"}
                    continue
```

With:

```python
                elif platform == "tiktok":
                    post_result = self._post_tiktok(job, caption)
                    if post_result.get("status") == "skipped":
                        result[platform] = post_result
                        continue
                elif platform == "youtube":
                    post_result = self._post_youtube(job, caption, scheduled_time)
                    if post_result.get("status") == "skipped":
                        result[platform] = post_result
                        continue
                else:
                    result[platform] = {"status": "skipped", "error": f"unsupported platform: {platform}"}
                    continue
```

Add `_post_youtube` as a new method after `_post_tiktok`:

```python
    def _post_youtube(self, job: ContentJob, caption: str, scheduled_time: int | None) -> dict:
        if job.content_type != ContentType.VIDEO:
            return {"status": "skipped", "reason": "YouTube only supports video uploads"}
        token = self._youtube_access_token(self.config)
        return self._post_youtube_video(job, caption, scheduled_time, token)
```

Add `_youtube_access_token` after `_post_youtube`:

```python
    def _youtube_access_token(self, config) -> str:
        resp = requests.post(
            _YOUTUBE_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "client_id": config.youtube_client_id,
                "client_secret": config.youtube_client_secret,
                "refresh_token": config.youtube_refresh_token,
            },
        )
        resp.raise_for_status()
        return resp.json()["access_token"]
```

Add `_post_youtube_video` placeholder after `_youtube_access_token`:

```python
    def _post_youtube_video(
        self, job: ContentJob, caption: str, scheduled_time: int | None, token: str
    ) -> dict:
        raise NotImplementedError("_post_youtube_video not yet implemented")
```

Add `_youtube_scheduled_iso` after `_post_youtube_video`:

```python
    def _youtube_scheduled_iso(self, scheduled_time: int) -> str:
        from datetime import datetime, timezone
        return datetime.fromtimestamp(scheduled_time, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
```

- [ ] **Step 9: Run the two new tests**

```bash
.venv/bin/python -m pytest tests/test_publish.py::test_publish_youtube_image_skips_with_reason tests/test_publish.py::test_publish_youtube_article_excluded_from_platforms -v
```

Expected: both PASS.

- [ ] **Step 10: Run full test suite**

```bash
.venv/bin/python -m pytest --tb=short -q
```

Expected: 113 passed (111 existing + 2 new).

- [ ] **Step 11: Commit**

```bash
git add config.py .env.example agents/publish.py tests/test_publish.py
git commit -m "feat(publish): add YouTube platform branch — image skip and article exclusion"
```

---

## Task 2: YouTube video upload (auth + init + PUT)

**Files:**
- Modify: `agents/publish.py` (replace `_post_youtube_video` placeholder)
- Modify: `tests/test_publish.py` (add 3 tests)

- [ ] **Step 1: Add three failing tests at the bottom of `tests/test_publish.py`**

```python
def test_publish_youtube_video_upload(mocker, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    vid_file = tmp_path / "video.mp4"
    vid_file.write_bytes(b"MP4DATA")
    mock_post = mocker.patch("agents.publish.requests.post")
    mock_put = mocker.patch("agents.publish.requests.put")
    auth_resp = mocker.MagicMock()
    auth_resp.raise_for_status = mocker.MagicMock()
    auth_resp.json.return_value = {"access_token": "yt-token"}
    init_resp = mocker.MagicMock()
    init_resp.raise_for_status = mocker.MagicMock()
    init_resp.headers = {"Location": "https://upload.googleapis.com/v1/upload"}
    mock_post.side_effect = [auth_resp, init_resp]
    mock_put.return_value.raise_for_status = mocker.MagicMock()
    mock_put.return_value.json.return_value = {"id": "yt-1", "status": {"uploadStatus": "uploaded"}}
    agent = PublishAgent(make_publish_config())
    job = make_video_job(dry_run=False, video_path=str(vid_file))
    job.platforms = ["youtube"]
    job = agent.run(job)
    assert mock_post.call_count == 2
    auth_url = mock_post.call_args_list[0][0][0]
    assert "oauth2.googleapis.com/token" in auth_url
    init_url = mock_post.call_args_list[1][0][0]
    assert "youtube/v3/videos" in init_url
    assert mock_put.called
    assert job.publish_result["youtube"]["status"] == "published"
    assert job.publish_result["youtube"]["id"] == "yt-1"


def test_publish_youtube_scheduled(mocker, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    vid_file = tmp_path / "video.mp4"
    vid_file.write_bytes(b"MP4DATA")
    mock_post = mocker.patch("agents.publish.requests.post")
    mock_put = mocker.patch("agents.publish.requests.put")
    auth_resp = mocker.MagicMock()
    auth_resp.raise_for_status = mocker.MagicMock()
    auth_resp.json.return_value = {"access_token": "yt-token"}
    init_resp = mocker.MagicMock()
    init_resp.raise_for_status = mocker.MagicMock()
    init_resp.headers = {"Location": "https://upload.googleapis.com/v1/upload"}
    mock_post.side_effect = [auth_resp, init_resp]
    mock_put.return_value.raise_for_status = mocker.MagicMock()
    mock_put.return_value.json.return_value = {"id": "yt-2", "status": {"uploadStatus": "uploaded"}}
    agent = PublishAgent(make_publish_config())
    job = make_video_job(dry_run=False, video_path=str(vid_file))
    job.platforms = ["youtube"]
    job = agent.run(job, schedule=True)
    init_body = mock_post.call_args_list[1][1]["json"]
    assert init_body["status"]["privacyStatus"] == "private"
    assert "publishAt" in init_body["status"]
    assert job.publish_result["youtube"]["status"] == "scheduled"


def test_publish_youtube_failure_does_not_affect_meta(mocker, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    vid_file = tmp_path / "video.mp4"
    vid_file.write_bytes(b"MP4DATA")
    mock_post = mocker.patch("agents.publish.requests.post")
    mock_put = mocker.patch("agents.publish.requests.put")
    fb_resp = mocker.MagicMock()
    fb_resp.raise_for_status = mocker.MagicMock()
    fb_resp.json.return_value = {"id": "fb-vid-1"}
    auth_resp = mocker.MagicMock()
    auth_resp.raise_for_status = mocker.MagicMock()
    auth_resp.json.return_value = {"access_token": "yt-token"}
    init_resp = mocker.MagicMock()
    init_resp.raise_for_status.side_effect = Exception("QUOTA_EXCEEDED")
    mock_post.side_effect = [fb_resp, auth_resp, init_resp]
    mock_put.return_value.raise_for_status = mocker.MagicMock()
    agent = PublishAgent(make_publish_config())
    job = make_video_job(dry_run=False, video_path=str(vid_file))
    job.platforms = ["facebook", "youtube"]
    job = agent.run(job)
    assert job.publish_result["facebook"]["status"] == "published"
    assert job.publish_result["youtube"]["status"] == "failed"
    assert "QUOTA_EXCEEDED" in job.publish_result["youtube"]["error"]
```

- [ ] **Step 2: Run to verify they fail**

```bash
.venv/bin/python -m pytest tests/test_publish.py::test_publish_youtube_video_upload tests/test_publish.py::test_publish_youtube_scheduled tests/test_publish.py::test_publish_youtube_failure_does_not_affect_meta -v
```

Expected: all three FAIL with `NotImplementedError`.

- [ ] **Step 3: Replace `_post_youtube_video` placeholder in `agents/publish.py`**

Replace the `_post_youtube_video` method body:

```python
    def _post_youtube_video(
        self, job: ContentJob, caption: str, scheduled_time: int | None, token: str
    ) -> dict:
        if not job.video_path:
            raise ValueError(f"PublishAgent: video_path is None for job {job.id}")
        file_size = Path(job.video_path).stat().st_size
        if file_size == 0:
            raise ValueError(f"PublishAgent: video file is empty: {job.video_path}")
        tags = job.growth_strategy.hashtags if job.growth_strategy else []
        status_body: dict = {"privacyStatus": "private" if scheduled_time else "public"}
        if scheduled_time:
            status_body["publishAt"] = self._youtube_scheduled_iso(scheduled_time)
        init_resp = requests.post(
            f"{_YOUTUBE_UPLOAD_BASE}/videos?uploadType=resumable",
            headers={
                **self._auth_headers(token),
                "Content-Type": "application/json",
                "X-Upload-Content-Type": "video/*",
                "X-Upload-Content-Length": str(file_size),
            },
            json={
                "snippet": {
                    "title": caption,
                    "description": caption,
                    "tags": tags,
                    "categoryId": "22",
                },
                "status": status_body,
            },
        )
        init_resp.raise_for_status()
        upload_uri = init_resp.headers["Location"]
        with open(job.video_path, "rb") as f:
            upload_resp = requests.put(
                upload_uri,
                headers={
                    "Content-Type": "video/*",
                    "Content-Length": str(file_size),
                },
                data=f,
            )
        upload_resp.raise_for_status()
        video_id = upload_resp.json()["id"]
        return {"id": video_id, "status_code": "uploaded"}
```

- [ ] **Step 4: Run the three new tests**

```bash
.venv/bin/python -m pytest tests/test_publish.py::test_publish_youtube_video_upload tests/test_publish.py::test_publish_youtube_scheduled tests/test_publish.py::test_publish_youtube_failure_does_not_affect_meta -v
```

Expected: all three PASS.

- [ ] **Step 5: Run full test suite**

```bash
.venv/bin/python -m pytest --tb=short -q
```

Expected: 116 passed (113 + 3).

- [ ] **Step 6: Run ruff**

```bash
.venv/bin/python -m ruff check agents/publish.py config.py tests/test_publish.py
```

Expected: no output.

- [ ] **Step 7: Commit**

```bash
git add agents/publish.py tests/test_publish.py
git commit -m "feat(publish): add YouTube video upload via OAuth 2.0 resumable flow"
```
