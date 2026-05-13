# Phase 5: TikTok Publishing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `PublishAgent` to post VIDEO content to TikTok via the Content Posting API v2 (FILE_UPLOAD chunked flow), and skip IMAGE/INFOGRAPHIC with a descriptive reason.

**Architecture:** Add a `_post_tiktok` dispatcher and `_post_tiktok_video` method to `agents/publish.py`. Update the `effective_platforms` filter to exclude TikTok for ARTICLE jobs. No changes to orchestrator, CLI, or config — `tiktok_access_token` is already in `Config`.

**Tech Stack:** Python 3.9, `requests`, TikTok Content Posting API v2 (`https://open.tiktokapis.com/v2`), pytest, pytest-mock.

---

## File Map

| File | Change |
|---|---|
| `agents/publish.py` | Add `import time`; add 4 module-level constants; update `effective_platforms` filter; add `elif platform == "tiktok"` branch; add `_post_tiktok` and `_post_tiktok_video` methods |
| `tests/test_publish.py` | Add `tiktok_access_token` to `make_publish_config()`; add 5 new tests |

---

## Task 1: TikTok image skip + article exclusion

**Files:**
- Modify: `agents/publish.py:1-10` (imports + constants), `agents/publish.py:18-53` (run_live)
- Test: `tests/test_publish.py`

- [ ] **Step 1: Add two failing tests**

Add at the bottom of `tests/test_publish.py`:

```python
def test_publish_tiktok_image_skips_with_reason(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    img_file = tmp_path / "image.png"
    img_file.write_bytes(b"PNG")
    agent = PublishAgent(make_publish_config())
    job = make_image_job(dry_run=False)
    job.image_path = str(img_file)
    job.platforms = ["tiktok"]
    job = agent.run(job)
    assert job.publish_result["tiktok"]["status"] == "skipped"
    assert "public URL" in job.publish_result["tiktok"]["reason"]


def test_publish_tiktok_article_excluded_from_platforms(mocker):
    mock_post = mocker.patch("agents.publish.requests.post")
    mock_post.return_value.raise_for_status = mocker.MagicMock()
    mock_post.return_value.json.return_value = {"id": "fb-1"}
    agent = PublishAgent(make_publish_config())
    job = make_article_job(dry_run=False)
    job.platforms = ["facebook", "tiktok"]
    job = agent.run(job)
    assert "tiktok" not in job.publish_result
    assert job.publish_result["facebook"]["status"] == "published"
```

- [ ] **Step 2: Run to verify they fail**

```bash
.venv/bin/python -m pytest tests/test_publish.py::test_publish_tiktok_image_skips_with_reason tests/test_publish.py::test_publish_tiktok_article_excluded_from_platforms -v
```

Expected: FAIL — `test_publish_tiktok_image_skips_with_reason` will get `{"status": "skipped", "error": "unsupported platform: tiktok"}` (wrong key), and `test_publish_tiktok_article_excluded_from_platforms` will have `tiktok` in `publish_result` with `{"status": "skipped", "error": "unsupported platform: tiktok"}`.

- [ ] **Step 3: Add `tiktok_access_token` to `make_publish_config` and add module-level constants**

Update `make_publish_config` in `tests/test_publish.py`:

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

Add four module-level constants to `agents/publish.py` after the existing `_META_GRAPH_BASE` line:

```python
_META_GRAPH_BASE = "https://graph.facebook.com/v19.0"
_TIKTOK_BASE = "https://open.tiktokapis.com/v2"
_TIKTOK_CHUNK_SIZE = 10 * 1024 * 1024  # 10 MB
_TIKTOK_POLL_INTERVAL = 5
_TIKTOK_POLL_TIMEOUT = 300
```

- [ ] **Step 4: Add `import time` to `agents/publish.py`**

Replace the imports block at the top of `agents/publish.py`:

```python
from __future__ import annotations
import logging
import time
import requests
from pathlib import Path
from agents.base_agent import BaseAgent
from models.content_job import ContentJob, ContentType
```

- [ ] **Step 5: Update `effective_platforms` filter in `run_live`**

Replace the existing filter (line 20-23 in `agents/publish.py`):

```python
        effective_platforms = [
            p for p in job.platforms
            if not (job.content_type == ContentType.ARTICLE and p in ("instagram", "tiktok"))
        ]
```

- [ ] **Step 6: Add the `elif platform == "tiktok"` branch and `_post_tiktok` method**

In `run_live`, replace the existing `else` branch (lines 44-46):

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

Add `_post_tiktok` as a new method after `_auth_headers`:

```python
    def _post_tiktok(self, job: ContentJob, caption: str) -> dict:
        if job.content_type != ContentType.VIDEO:
            return {"status": "skipped", "reason": "image carousel requires public URL hosting"}
        token = self.config.tiktok_access_token
        return self._post_tiktok_video(job, caption, token)
```

- [ ] **Step 7: Add a placeholder `_post_tiktok_video` (raises NotImplementedError) so the file parses**

```python
    def _post_tiktok_video(self, job: ContentJob, caption: str, token: str) -> dict:
        raise NotImplementedError("_post_tiktok_video not yet implemented")
```

- [ ] **Step 8: Run the two new tests**

```bash
.venv/bin/python -m pytest tests/test_publish.py::test_publish_tiktok_image_skips_with_reason tests/test_publish.py::test_publish_tiktok_article_excluded_from_platforms -v
```

Expected: both PASS.

- [ ] **Step 9: Run full test suite to confirm no regressions**

```bash
.venv/bin/python -m pytest --tb=short -q
```

Expected: all existing tests + 2 new = 98 passed.

- [ ] **Step 10: Commit**

```bash
git add agents/publish.py tests/test_publish.py
git commit -m "feat(publish): add TikTok platform branch — image skip and article exclusion"
```

---

## Task 2: TikTok video upload (init → chunk upload → poll)

**Files:**
- Modify: `agents/publish.py` (replace `_post_tiktok_video` placeholder)
- Test: `tests/test_publish.py`

- [ ] **Step 1: Add three failing tests**

Add at the bottom of `tests/test_publish.py`:

```python
def test_publish_tiktok_video_init_upload_publish(mocker, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    vid_file = tmp_path / "video.mp4"
    vid_file.write_bytes(b"MP4DATA")
    mock_post = mocker.patch("agents.publish.requests.post")
    mock_put = mocker.patch("agents.publish.requests.put")
    init_resp = mocker.MagicMock()
    init_resp.raise_for_status = mocker.MagicMock()
    init_resp.json.return_value = {
        "data": {"publish_id": "pub-1", "upload_url": "https://upload.tiktok.com/v1/upload"}
    }
    status_resp = mocker.MagicMock()
    status_resp.raise_for_status = mocker.MagicMock()
    status_resp.json.return_value = {"data": {"status": "PUBLISH_COMPLETE"}}
    mock_post.side_effect = [init_resp, status_resp]
    mock_put.return_value.raise_for_status = mocker.MagicMock()
    agent = PublishAgent(make_publish_config())
    job = make_video_job(dry_run=False, video_path=str(vid_file))
    job.platforms = ["tiktok"]
    job = agent.run(job)
    assert mock_post.call_count == 2
    init_url = mock_post.call_args_list[0][0][0]
    assert "video/init" in init_url
    assert mock_put.called
    assert job.publish_result["tiktok"]["status"] == "published"
    assert job.publish_result["tiktok"]["publish_id"] == "pub-1"


def test_publish_tiktok_video_poll_timeout(mocker, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    vid_file = tmp_path / "video.mp4"
    vid_file.write_bytes(b"MP4DATA")
    mock_post = mocker.patch("agents.publish.requests.post")
    mock_put = mocker.patch("agents.publish.requests.put")
    mocker.patch("agents.publish.time.sleep")
    init_resp = mocker.MagicMock()
    init_resp.raise_for_status = mocker.MagicMock()
    init_resp.json.return_value = {
        "data": {"publish_id": "pub-2", "upload_url": "https://upload.tiktok.com/v1/upload"}
    }
    status_resp = mocker.MagicMock()
    status_resp.raise_for_status = mocker.MagicMock()
    status_resp.json.return_value = {"data": {"status": "PROCESSING"}}
    mock_post.side_effect = [init_resp] + [status_resp] * 60
    mock_put.return_value.raise_for_status = mocker.MagicMock()
    agent = PublishAgent(make_publish_config())
    job = make_video_job(dry_run=False, video_path=str(vid_file))
    job.platforms = ["tiktok"]
    job = agent.run(job)
    assert job.publish_result["tiktok"]["status"] == "failed"
    assert "timed out" in job.publish_result["tiktok"]["error"]


def test_publish_tiktok_failure_does_not_affect_meta(mocker, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    vid_file = tmp_path / "video.mp4"
    vid_file.write_bytes(b"MP4DATA")
    mock_post = mocker.patch("agents.publish.requests.post")
    mock_put = mocker.patch("agents.publish.requests.put")
    fb_resp = mocker.MagicMock()
    fb_resp.raise_for_status = mocker.MagicMock()
    fb_resp.json.return_value = {"id": "fb-vid-1"}
    init_resp = mocker.MagicMock()
    init_resp.raise_for_status = mocker.MagicMock()
    init_resp.json.return_value = {
        "data": {"publish_id": "pub-3", "upload_url": "https://upload.tiktok.com/v1/upload"}
    }
    status_resp = mocker.MagicMock()
    status_resp.raise_for_status = mocker.MagicMock()
    status_resp.json.return_value = {"data": {"status": "FAILED", "fail_reason": "QUOTA_EXCEEDED"}}
    mock_post.side_effect = [fb_resp, init_resp, status_resp]
    mock_put.return_value.raise_for_status = mocker.MagicMock()
    agent = PublishAgent(make_publish_config())
    job = make_video_job(dry_run=False, video_path=str(vid_file))
    job.platforms = ["facebook", "tiktok"]
    job = agent.run(job)
    assert job.publish_result["facebook"]["status"] == "published"
    assert job.publish_result["tiktok"]["status"] == "failed"
    assert "QUOTA_EXCEEDED" in job.publish_result["tiktok"]["error"]
```

- [ ] **Step 2: Run to verify they fail**

```bash
.venv/bin/python -m pytest tests/test_publish.py::test_publish_tiktok_video_init_upload_publish tests/test_publish.py::test_publish_tiktok_video_poll_timeout tests/test_publish.py::test_publish_tiktok_failure_does_not_affect_meta -v
```

Expected: all three FAIL with `NotImplementedError`.

- [ ] **Step 3: Replace the `_post_tiktok_video` placeholder with the real implementation**

Replace the `_post_tiktok_video` method body in `agents/publish.py`:

```python
    def _post_tiktok_video(self, job: ContentJob, caption: str, token: str) -> dict:
        if not job.video_path:
            raise ValueError(f"PublishAgent: video_path is None for job {job.id}")
        headers = self._auth_headers(token)
        file_size = Path(job.video_path).stat().st_size
        total_chunk_count = (file_size + _TIKTOK_CHUNK_SIZE - 1) // _TIKTOK_CHUNK_SIZE
        init_resp = requests.post(
            f"{_TIKTOK_BASE}/post/publish/video/init/",
            headers={**headers, "Content-Type": "application/json; charset=UTF-8"},
            json={
                "post_info": {
                    "title": caption,
                    "privacy_level": "PUBLIC_TO_EVERYONE",
                    "disable_duet": False,
                    "disable_comment": False,
                    "disable_stitch": False,
                },
                "source_info": {
                    "source": "FILE_UPLOAD",
                    "video_size": file_size,
                    "chunk_size": _TIKTOK_CHUNK_SIZE,
                    "total_chunk_count": total_chunk_count,
                },
            },
        )
        init_resp.raise_for_status()
        init_data = init_resp.json()["data"]
        publish_id = init_data["publish_id"]
        upload_url = init_data["upload_url"]
        with open(job.video_path, "rb") as f:
            for chunk_index in range(total_chunk_count):
                chunk = f.read(_TIKTOK_CHUNK_SIZE)
                start = chunk_index * _TIKTOK_CHUNK_SIZE
                end = start + len(chunk) - 1
                requests.put(
                    upload_url,
                    headers={
                        **headers,
                        "Content-Range": f"bytes {start}-{end}/{file_size}",
                        "Content-Type": "video/mp4",
                    },
                    data=chunk,
                ).raise_for_status()
        elapsed = 0
        while elapsed < _TIKTOK_POLL_TIMEOUT:
            status_resp = requests.post(
                f"{_TIKTOK_BASE}/post/publish/status/fetch/",
                headers={**headers, "Content-Type": "application/json; charset=UTF-8"},
                json={"publish_id": publish_id},
            )
            status_resp.raise_for_status()
            status_data = status_resp.json().get("data", {})
            status = status_data.get("status")
            if status == "PUBLISH_COMPLETE":
                return {"publish_id": publish_id, "status_code": "PUBLISH_COMPLETE"}
            if status == "FAILED":
                fail_reason = status_data.get("fail_reason", "unknown")
                raise RuntimeError(f"TikTok publish failed: {fail_reason}")
            time.sleep(_TIKTOK_POLL_INTERVAL)
            elapsed += _TIKTOK_POLL_INTERVAL
        raise TimeoutError(
            f"timed out waiting for TikTok processing after {_TIKTOK_POLL_TIMEOUT}s"
        )
```

- [ ] **Step 4: Run the three new tests**

```bash
.venv/bin/python -m pytest tests/test_publish.py::test_publish_tiktok_video_init_upload_publish tests/test_publish.py::test_publish_tiktok_video_poll_timeout tests/test_publish.py::test_publish_tiktok_failure_does_not_affect_meta -v
```

Expected: all three PASS.

- [ ] **Step 5: Run full test suite**

```bash
.venv/bin/python -m pytest --tb=short -q
```

Expected: 101 passed (96 existing + 5 new).

- [ ] **Step 6: Commit**

```bash
git add agents/publish.py tests/test_publish.py
git commit -m "feat(publish): add TikTok video upload via FILE_UPLOAD chunked flow with poll"
```
