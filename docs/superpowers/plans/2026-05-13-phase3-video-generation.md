# Phase 3 — Video Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire Lila to generate videos via Google Veo3 (Vertex AI) for VIDEO jobs, fix a dry-run bug where `image_path` was incorrectly set for VIDEO, and update Nora to verify the video artifact before calling Claude and prevent expensive re-generation loops.

**Architecture:** `LilaAgent._generate_video()` is added alongside `_generate_image()` — it inits Vertex AI, submits a generation request, polls every 15s (max 600s), downloads the result, and writes `video.mp4`. Nora's VIDEO path adds a pre-Claude file check and silently overrides `send_back_to="lila"` to `None`. Two tasks: Lila first (self-contained), then Nora (depends on `job.video_path` being set by Lila).

**Tech Stack:** Python 3.9, `google-cloud-aiplatform` (new), `vertexai.preview.vision_models.VideoGenerationModel`, `time` (stdlib), `pathlib` (stdlib)

---

## Files

| File | Change |
|---|---|
| `requirements.txt` | Add `google-cloud-aiplatform>=1.60.0` |
| `agents/lila.py` | Add `_generate_video`; update `run_live` VIDEO branch; fix `run_dry` VIDEO bug |
| `agents/nora.py` | Add `from pathlib import Path`; VIDEO pre-check in `run_live`; `send_back_to` override; update `_build_qa_user_prompt` VIDEO branch |
| `tests/test_lila.py` | Replace `test_lila_dry_run_sets_visual_prompt_and_image` + `test_lila_live_calls_claude_for_prompt`; add 4 new video tests |
| `tests/test_nora.py` | Update 3 existing VIDEO tests to write temp file; add 3 new video artifact tests |

---

### Task 1: Lila — `_generate_video`, VIDEO `run_live`, dry-run fix

**Files:**
- Modify: `requirements.txt`
- Modify: `agents/lila.py`
- Modify: `tests/test_lila.py`

- [ ] **Step 1: Update `tests/test_lila.py` — replace 2 outdated tests, add 4 new failing tests**

Replace `test_lila_dry_run_sets_visual_prompt_and_image` (currently asserts `image_path is not None` for VIDEO, which will be wrong after Phase 3):

```python
def test_lila_dry_run_video_sets_video_path():
    agent = LilaAgent(make_config())
    job = agent.run(make_job_with_bella_output(dry_run=True))
    assert job.visual_prompt is not None
    assert job.video_path is not None
    assert job.image_path is None
    assert job.stage == "lila_done"
```

Replace `test_lila_live_calls_claude_for_prompt` (was checking `image_path is None` for VIDEO, now video must be generated):

```python
def test_lila_live_video_calls_claude_and_generate_video(mocker, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    prompt = "Cinematic shot of gold lipstick, ivory background, soft morning light"
    mocker.patch.object(LilaAgent, "_call_claude", return_value=prompt)
    mocker.patch.object(LilaAgent, "_generate_video", return_value=str(tmp_path / "video.mp4"))
    agent = LilaAgent(make_config())
    job = agent.run(make_job_with_bella_output(dry_run=False))
    assert job.visual_prompt == prompt
    assert job.video_path == str(tmp_path / "video.mp4")
    assert job.image_path is None
    assert job.stage == "lila_done"
```

Add these 4 new tests at the end of the file:

```python
def test_lila_live_video_calls_veo3(mocker, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mock_operation = mocker.MagicMock()
    mock_operation.done.return_value = True
    mock_operation.result.return_value.videos = [mocker.MagicMock(video_bytes=b"VIDEO_BYTES")]
    mock_model = mocker.MagicMock()
    mock_model.generate_video.return_value = mock_operation
    mock_model_class = mocker.patch("agents.lila.VideoGenerationModel")
    mock_model_class.from_pretrained.return_value = mock_model
    mocker.patch("agents.lila.vertexai.init")
    mocker.patch.object(LilaAgent, "_call_claude", return_value="cinematic video prompt")
    agent = LilaAgent(make_config())
    job = agent.run(make_job_with_bella_output(dry_run=False))
    mock_model_class.from_pretrained.assert_called_once_with("veo-003")
    mock_model.generate_video.assert_called_once_with(prompt="cinematic video prompt")
    assert job.video_path is not None
    assert job.video_path.endswith("video.mp4")
    assert Path(job.video_path).read_bytes() == b"VIDEO_BYTES"
    assert job.image_path is None
    assert job.stage == "lila_done"


def test_lila_live_video_timeout_raises_runtime(mocker, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mock_operation = mocker.MagicMock()
    mock_operation.done.return_value = False
    mock_model = mocker.MagicMock()
    mock_model.generate_video.return_value = mock_operation
    mock_model_class = mocker.patch("agents.lila.VideoGenerationModel")
    mock_model_class.from_pretrained.return_value = mock_model
    mocker.patch("agents.lila.vertexai.init")
    mocker.patch("agents.lila.time.sleep")
    mocker.patch("agents.lila.time.time", side_effect=[0, 601])
    mocker.patch.object(LilaAgent, "_call_claude", return_value="some prompt")
    agent = LilaAgent(make_config())
    job = make_job_with_bella_output(dry_run=False)
    with pytest.raises(RuntimeError, match=job.id):
        agent.run(job)


def test_lila_live_video_google_error_raises_runtime(mocker, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mock_model = mocker.MagicMock()
    mock_model.generate_video.side_effect = Exception("API quota exceeded")
    mock_model_class = mocker.patch("agents.lila.VideoGenerationModel")
    mock_model_class.from_pretrained.return_value = mock_model
    mocker.patch("agents.lila.vertexai.init")
    mocker.patch.object(LilaAgent, "_call_claude", return_value="some prompt")
    agent = LilaAgent(make_config())
    job = make_job_with_bella_output(dry_run=False)
    with pytest.raises(RuntimeError, match=job.id):
        agent.run(job)


def test_lila_live_video_generate_video_prompt_guard(mocker, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mocker.patch("agents.lila.vertexai.init")
    mocker.patch("agents.lila.VideoGenerationModel")
    agent = LilaAgent(make_config())
    job = make_job_with_bella_output(dry_run=False)
    job.visual_prompt = None
    with pytest.raises(ValueError, match=job.id):
        agent._generate_video(job)
```

- [ ] **Step 2: Run new/updated tests — confirm they FAIL**

```bash
/Users/nennayz/Documents/NayzFreedom/code/slayhack/.venv/bin/python3 -m pytest \
  tests/test_lila.py::test_lila_dry_run_video_sets_video_path \
  tests/test_lila.py::test_lila_live_video_calls_claude_and_generate_video \
  tests/test_lila.py::test_lila_live_video_calls_veo3 \
  tests/test_lila.py::test_lila_live_video_timeout_raises_runtime \
  tests/test_lila.py::test_lila_live_video_google_error_raises_runtime \
  tests/test_lila.py::test_lila_live_video_generate_video_prompt_guard \
  -v 2>&1 | tail -15
```

Expected: all 6 FAIL (old tests removed, new ones reference missing `_generate_video`, `vertexai`, `VideoGenerationModel`).

- [ ] **Step 3: Add `google-cloud-aiplatform` to `requirements.txt`**

Append to `/Users/nennayz/Documents/NayzFreedom/code/slayhack/requirements.txt`:

```
google-cloud-aiplatform>=1.60.0
```

Install it:

```bash
/Users/nennayz/Documents/NayzFreedom/code/slayhack/.venv/bin/python3 -m pip install google-cloud-aiplatform>=1.60.0 2>&1 | tail -3
```

- [ ] **Step 4: Update `agents/lila.py` imports**

Replace the existing import block:

```python
from __future__ import annotations
import base64
from pathlib import Path
import openai
from agents.base_agent import BaseAgent, TEAM_IDENTITY
from models.content_job import ContentJob, ContentType, Script, ImageCaption, InfographicContent
```

With:

```python
from __future__ import annotations
import base64
import time
from pathlib import Path
import openai
import vertexai
from vertexai.preview.vision_models import VideoGenerationModel
from agents.base_agent import BaseAgent, TEAM_IDENTITY
from models.content_job import ContentJob, ContentType, Script, ImageCaption, InfographicContent
```

- [ ] **Step 5: Add constants after `_DRY_RUN_IMAGE` in `agents/lila.py`**

Replace:

```python
_DRY_RUN_IMAGE = "assets/placeholder.png"
```

With:

```python
_DRY_RUN_IMAGE = "assets/placeholder.png"
_DRY_RUN_VIDEO = "assets/placeholder.mp4"
_VIDEO_GENERATION_TIMEOUT = 600
_VIDEO_POLL_INTERVAL = 15
```

- [ ] **Step 6: Fix `run_dry` VIDEO branch in `agents/lila.py`**

Replace:

```python
    def run_dry(self, job: ContentJob, **kwargs) -> ContentJob:
        if job.content_type is None:
            raise ValueError(f"LilaAgent requires content_type to be set on job {job.id}")
        if job.content_type == ContentType.ARTICLE:
            job.stage = "lila_done"
            return job
        job.visual_prompt = _DRY_RUN_PROMPTS.get(
            job.content_type,
            _DRY_RUN_PROMPTS[ContentType.VIDEO],
        )
        job.image_path = _DRY_RUN_IMAGE
        job.stage = "lila_done"
        self._write_prompt_file(job)
        return job
```

With:

```python
    def run_dry(self, job: ContentJob, **kwargs) -> ContentJob:
        if job.content_type is None:
            raise ValueError(f"LilaAgent requires content_type to be set on job {job.id}")
        if job.content_type == ContentType.ARTICLE:
            job.stage = "lila_done"
            return job
        job.visual_prompt = _DRY_RUN_PROMPTS.get(
            job.content_type,
            _DRY_RUN_PROMPTS[ContentType.VIDEO],
        )
        if job.content_type == ContentType.VIDEO:
            job.video_path = _DRY_RUN_VIDEO
            job.image_path = None
        else:
            job.image_path = _DRY_RUN_IMAGE
        job.stage = "lila_done"
        self._write_prompt_file(job)
        return job
```

- [ ] **Step 7: Update `run_live` VIDEO branch in `agents/lila.py`**

Replace:

```python
        if job.content_type == ContentType.VIDEO:
            hook_text = bella.hook if isinstance(bella, Script) else str(bella)
            user = (
                f"Script hook: {hook_text}\nBrief: {job.brief}\n"
                "Write a single cinematic image generation prompt for this Reel's key visual. "
                "Be specific about lighting, composition, and mood. Plain text only."
            )
            job.visual_prompt = self._call_claude(system, user, max_tokens=256)
            job.image_path = None
```

With:

```python
        if job.content_type == ContentType.VIDEO:
            hook_text = bella.hook if isinstance(bella, Script) else str(bella)
            user = (
                f"Script hook: {hook_text}\nBrief: {job.brief}\n"
                "Write a single cinematic video generation prompt for this Reel. "
                "Be specific about lighting, composition, and mood. Plain text only."
            )
            job.visual_prompt = self._call_claude(system, user, max_tokens=256)
            job.video_path = self._generate_video(job)
            job.image_path = None
```

- [ ] **Step 8: Add `_generate_video` method to `agents/lila.py`**

Add after `_generate_image` (before end of class):

```python
    def _generate_video(self, job: ContentJob) -> str:
        if not job.visual_prompt:
            raise ValueError(f"visual_prompt must be set before video generation for job {job.id}")
        vertexai.init(project=self.config.google_cloud_project, location="us-central1")
        model = VideoGenerationModel.from_pretrained("veo-003")
        try:
            operation = model.generate_video(prompt=job.visual_prompt)
        except Exception as e:
            raise RuntimeError(
                f"Video generation failed for job {job.id}: {e}"
            ) from e
        start = time.time()
        while not operation.done():
            if time.time() - start > _VIDEO_GENERATION_TIMEOUT:
                raise RuntimeError(
                    f"Video generation timed out after {_VIDEO_GENERATION_TIMEOUT}s "
                    f"for job {job.id}"
                )
            time.sleep(_VIDEO_POLL_INTERVAL)
        try:
            video_bytes = operation.result().videos[0].video_bytes
        except Exception as e:
            raise RuntimeError(
                f"Video generation failed for job {job.id}: {e}"
            ) from e
        out_dir = Path("output") / job.pm.page_name / job.id
        out_dir.mkdir(parents=True, exist_ok=True)
        video_path = out_dir / "video.mp4"
        video_path.write_bytes(video_bytes)
        return str(video_path)
```

- [ ] **Step 9: Run the 6 new/updated Lila tests — confirm they PASS**

```bash
/Users/nennayz/Documents/NayzFreedom/code/slayhack/.venv/bin/python3 -m pytest \
  tests/test_lila.py::test_lila_dry_run_video_sets_video_path \
  tests/test_lila.py::test_lila_live_video_calls_claude_and_generate_video \
  tests/test_lila.py::test_lila_live_video_calls_veo3 \
  tests/test_lila.py::test_lila_live_video_timeout_raises_runtime \
  tests/test_lila.py::test_lila_live_video_google_error_raises_runtime \
  tests/test_lila.py::test_lila_live_video_generate_video_prompt_guard \
  -v 2>&1 | tail -15
```

Expected: 6 PASSED.

- [ ] **Step 10: Run the full test suite — confirm no regressions**

```bash
/Users/nennayz/Documents/NayzFreedom/code/slayhack/.venv/bin/python3 -m pytest -v 2>&1 | tail -10
```

Expected: all tests pass.

- [ ] **Step 11: Commit**

```bash
git add requirements.txt agents/lila.py tests/test_lila.py
git commit -m "feat(lila): implement _generate_video via Veo3; fix VIDEO dry-run bug"
```

---

### Task 2: Nora — VIDEO artifact check + `send_back_to` constraint

**Files:**
- Modify: `agents/nora.py`
- Modify: `tests/test_nora.py`

- [ ] **Step 1: Update `tests/test_nora.py` — update 3 existing VIDEO tests + add 3 new failing tests**

Update `make_job_for_nora` to accept an optional `video_path`:

```python
def make_job_for_nora(dry_run=True, video_path=None):
    job = make_job_with_bella_output(dry_run=dry_run)
    job.visual_prompt = "Gold lipstick, ivory background"
    job.image_path = "assets/placeholder.png"
    if video_path is not None:
        job.video_path = video_path
    return job
```

Update `test_nora_live_fail_increments_retry` to provide a real video file:

```python
def test_nora_live_fail_increments_retry(mocker, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    video_file = tmp_path / "video.mp4"
    video_file.write_bytes(b"FAKE")
    qa_json = '{"passed":false,"script_feedback":"Hook too weak","visual_feedback":null,"send_back_to":"bella"}'
    mocker.patch.object(NoraAgent, "_call_claude", return_value=qa_json)
    agent = NoraAgent(make_config())
    job = make_job_for_nora(dry_run=False, video_path=str(video_file))
    job = agent.run(job)
    assert job.qa_result.passed is False
    assert job.qa_result.send_back_to == "bella"
    assert job.nora_retry_count == 1
```

Update `test_nora_live_pass` to provide a real video file:

```python
def test_nora_live_pass(mocker, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    video_file = tmp_path / "video.mp4"
    video_file.write_bytes(b"FAKE")
    qa_json = '{"passed":true,"script_feedback":null,"visual_feedback":null,"send_back_to":null}'
    mocker.patch.object(NoraAgent, "_call_claude", return_value=qa_json)
    agent = NoraAgent(make_config())
    job = make_job_for_nora(dry_run=False, video_path=str(video_file))
    job = agent.run(job)
    assert job.qa_result.passed is True
    assert job.nora_retry_count == 0
```

Update `test_nora_live_video_includes_visual_in_prompt` to provide a real video file:

```python
def test_nora_live_video_includes_visual_in_prompt(mocker, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    video_file = tmp_path / "video.mp4"
    video_file.write_bytes(b"FAKE")
    captured = {}
    def fake_call(system, user, **kwargs):
        captured["user"] = user
        return '{"passed":true,"script_feedback":null,"visual_feedback":null,"send_back_to":null}'
    agent = NoraAgent(make_config())
    mocker.patch.object(agent, "_call_claude", side_effect=fake_call)
    job = make_job_for_nora(dry_run=False, video_path=str(video_file))
    agent.run(job)
    assert "Script hook:" in captured["user"]
    assert "Gold lipstick, ivory background" in captured["user"]
```

Add 3 new tests at the end of `tests/test_nora.py`:

```python
def test_nora_video_qa_fails_if_no_video_path(mocker):
    mock_call = mocker.patch.object(NoraAgent, "_call_claude")
    agent = NoraAgent(make_config())
    job = make_job_for_nora(dry_run=False)  # video_path=None
    job = agent.run(job)
    mock_call.assert_not_called()
    assert job.qa_result.passed is False
    assert job.qa_result.script_feedback == "Video not generated"
    assert job.nora_retry_count == 1


def test_nora_video_qa_fails_if_video_file_missing(mocker, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mock_call = mocker.patch.object(NoraAgent, "_call_claude")
    agent = NoraAgent(make_config())
    job = make_job_for_nora(dry_run=False, video_path=str(tmp_path / "nonexistent.mp4"))
    job = agent.run(job)
    mock_call.assert_not_called()
    assert job.qa_result.passed is False
    assert job.qa_result.script_feedback == "Video file missing or empty"
    assert job.nora_retry_count == 1


def test_nora_video_qa_send_back_to_never_lila(mocker, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    video_file = tmp_path / "video.mp4"
    video_file.write_bytes(b"FAKE")
    qa_json = '{"passed":false,"script_feedback":"Off-brand","visual_feedback":null,"send_back_to":"lila"}'
    mocker.patch.object(NoraAgent, "_call_claude", return_value=qa_json)
    agent = NoraAgent(make_config())
    job = make_job_for_nora(dry_run=False, video_path=str(video_file))
    job = agent.run(job)
    assert job.qa_result.send_back_to is None
```

- [ ] **Step 2: Run the 6 affected Nora tests — confirm failures**

```bash
/Users/nennayz/Documents/NayzFreedom/code/slayhack/.venv/bin/python3 -m pytest \
  tests/test_nora.py::test_nora_live_fail_increments_retry \
  tests/test_nora.py::test_nora_live_pass \
  tests/test_nora.py::test_nora_live_video_includes_visual_in_prompt \
  tests/test_nora.py::test_nora_video_qa_fails_if_no_video_path \
  tests/test_nora.py::test_nora_video_qa_fails_if_video_file_missing \
  tests/test_nora.py::test_nora_video_qa_send_back_to_never_lila \
  -v 2>&1 | tail -15
```

Expected: all 6 FAIL (updated tests fail due to no video path; new tests fail because artifact check not implemented).

- [ ] **Step 3: Add `from pathlib import Path` import to `agents/nora.py`**

Replace:

```python
from __future__ import annotations
from agents.base_agent import BaseAgent, TEAM_IDENTITY
from models.content_job import (
    ContentJob, ContentType, QAResult,
    Script, Article, ImageCaption, InfographicContent,
)
```

With:

```python
from __future__ import annotations
from pathlib import Path
from agents.base_agent import BaseAgent, TEAM_IDENTITY
from models.content_job import (
    ContentJob, ContentType, QAResult,
    Script, Article, ImageCaption, InfographicContent,
)
```

- [ ] **Step 4: Update `_build_qa_user_prompt` VIDEO branch in `agents/nora.py`**

Replace:

```python
    if job.content_type == ContentType.VIDEO and isinstance(bella, Script):
        return (
            f"Script hook: {bella.hook}\n"
            f"Script body: {bella.body}\n"
            f"CTA: {bella.cta}\n"
            f"Visual prompt: {job.visual_prompt}\n\n"
            "Review this video content. Return JSON with keys: passed (bool), "
            "script_feedback (str or null), visual_feedback (str or null), "
            "send_back_to ('bella' | 'lila' | null). JSON only."
        )
```

With:

```python
    if job.content_type == ContentType.VIDEO and isinstance(bella, Script):
        return (
            f"Script hook: {bella.hook}\n"
            f"Script body: {bella.body}\n"
            f"CTA: {bella.cta}\n"
            f"Visual prompt: {job.visual_prompt}\n"
            f"Video generated: {'Yes' if job.video_path else 'No'}\n\n"
            "Review this video content. Return JSON with keys: passed (bool), "
            "script_feedback (str or null), visual_feedback (str or null), "
            "send_back_to ('bella' | null). JSON only."
        )
```

- [ ] **Step 5: Update `run_live` in `agents/nora.py`**

Replace:

```python
    def run_live(self, job: ContentJob, **kwargs) -> ContentJob:
        system = (
            TEAM_IDENTITY +
            f"You are Nora, QA editor for {job.pm.page_name}. "
            f"Brand tone: {job.pm.brand.tone}. "
            f"Audience: {job.pm.brand.target_audience}. "
            "Be strict. Reject weak hooks, off-brand visuals, and anything that feels generic."
        )
        user = _build_qa_user_prompt(job)
        try:
            raw = self._call_claude(system, user, max_tokens=512)
            result = QAResult(**self._parse_json(raw))
        except Exception:
            result = QAResult(
                passed=False,
                script_feedback="Nora failed to parse Claude response.",
            )
        if not result.passed:
            job.nora_retry_count += 1
        job.qa_result = result
        job.stage = "nora_done"
        return job
```

With:

```python
    def run_live(self, job: ContentJob, **kwargs) -> ContentJob:
        if job.content_type == ContentType.VIDEO:
            if not job.video_path:
                job.qa_result = QAResult(passed=False, script_feedback="Video not generated")
                job.nora_retry_count += 1
                job.stage = "nora_done"
                return job
            video_file = Path(job.video_path)
            if not video_file.exists() or video_file.stat().st_size == 0:
                job.qa_result = QAResult(passed=False, script_feedback="Video file missing or empty")
                job.nora_retry_count += 1
                job.stage = "nora_done"
                return job

        system = (
            TEAM_IDENTITY +
            f"You are Nora, QA editor for {job.pm.page_name}. "
            f"Brand tone: {job.pm.brand.tone}. "
            f"Audience: {job.pm.brand.target_audience}. "
            "Be strict. Reject weak hooks, off-brand visuals, and anything that feels generic."
        )
        user = _build_qa_user_prompt(job)
        try:
            raw = self._call_claude(system, user, max_tokens=512)
            result = QAResult(**self._parse_json(raw))
        except Exception:
            result = QAResult(
                passed=False,
                script_feedback="Nora failed to parse Claude response.",
            )
        if job.content_type == ContentType.VIDEO and result.send_back_to == "lila":
            result = result.model_copy(update={"send_back_to": None})
        if not result.passed:
            job.nora_retry_count += 1
        job.qa_result = result
        job.stage = "nora_done"
        return job
```

- [ ] **Step 6: Run the 6 Nora tests — confirm they PASS**

```bash
/Users/nennayz/Documents/NayzFreedom/code/slayhack/.venv/bin/python3 -m pytest \
  tests/test_nora.py::test_nora_live_fail_increments_retry \
  tests/test_nora.py::test_nora_live_pass \
  tests/test_nora.py::test_nora_live_video_includes_visual_in_prompt \
  tests/test_nora.py::test_nora_video_qa_fails_if_no_video_path \
  tests/test_nora.py::test_nora_video_qa_fails_if_video_file_missing \
  tests/test_nora.py::test_nora_video_qa_send_back_to_never_lila \
  -v 2>&1 | tail -15
```

Expected: 6 PASSED.

- [ ] **Step 7: Run the full test suite — confirm no regressions**

```bash
/Users/nennayz/Documents/NayzFreedom/code/slayhack/.venv/bin/python3 -m pytest -v 2>&1 | tail -10
```

Expected: all tests pass.

- [ ] **Step 8: Commit**

```bash
git add agents/nora.py tests/test_nora.py
git commit -m "feat(nora): add VIDEO artifact check and constrain send_back_to for VIDEO jobs"
```
