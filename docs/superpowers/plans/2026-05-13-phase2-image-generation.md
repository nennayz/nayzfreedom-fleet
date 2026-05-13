# Phase 2 — Real Image Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `LilaAgent._generate_image()` stub with a real OpenAI `gpt-image-1` API call that saves the generated image to disk and returns its path.

**Architecture:** Implement `_generate_image` directly on `LilaAgent` — it instantiates an `openai.OpenAI` client from `self.config.openai_api_key`, calls `images.generate` with `response_format="b64_json"`, decodes the result, and writes a PNG to `output/<page_name>/<job_id>/image.png`. OpenAI errors are caught and re-raised as `RuntimeError` with the job ID for debuggability.

**Tech Stack:** Python 3.9, `openai>=1.0.0` (already in requirements.txt), `base64` (stdlib), `pathlib` (stdlib)

---

## Files

| File | Change |
|---|---|
| `agents/lila.py` | Implement `_generate_image`; add `import base64` and `import openai` |
| `tests/test_lila.py` | Replace 2 `NotImplementedError` tests with 3 new tests |

---

### Task 1: Implement `_generate_image` in `lila.py`

**Files:**
- Modify: `agents/lila.py:1-4` (imports)
- Modify: `agents/lila.py:94-96` (`_generate_image` method body)

- [ ] **Step 1: Write the three failing tests**

Open `tests/test_lila.py`. Replace the two existing `NotImplementedError` tests (lines 68–84) with these three tests:

```python
def test_lila_live_image_calls_openai(mocker, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fake_b64 = base64.b64encode(b"PNG_BYTES").decode()
    mock_response = mocker.MagicMock()
    mock_response.data = [mocker.MagicMock(b64_json=fake_b64)]
    mock_client = mocker.MagicMock()
    mock_client.images.generate.return_value = mock_response
    mocker.patch("agents.lila.openai.OpenAI", return_value=mock_client)
    mocker.patch.object(LilaAgent, "_call_claude", return_value="gold lipstick on marble")
    agent = LilaAgent(make_config())
    job = make_image_job(dry_run=False)
    job = agent.run(job)
    mock_client.images.generate.assert_called_once_with(
        model="gpt-image-1",
        prompt="gold lipstick on marble",
        n=1,
        size="1024x1024",
        response_format="b64_json",
    )
    assert job.image_path is not None
    assert job.image_path.endswith("image.png")
    assert Path(job.image_path).read_bytes() == b"PNG_BYTES"
    assert job.stage == "lila_done"


def test_lila_live_infographic_calls_openai(mocker, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fake_b64 = base64.b64encode(b"PNG_BYTES").decode()
    mock_response = mocker.MagicMock()
    mock_response.data = [mocker.MagicMock(b64_json=fake_b64)]
    mock_client = mocker.MagicMock()
    mock_client.images.generate.return_value = mock_response
    mocker.patch("agents.lila.openai.OpenAI", return_value=mock_client)
    mocker.patch.object(LilaAgent, "_call_claude", return_value="clean white infographic layout")
    agent = LilaAgent(make_config())
    job = make_job_with_idea(dry_run=False, content_type=ContentType.INFOGRAPHIC)
    job.bella_output = InfographicContent(title="T", points=["p1"], cta="c")
    job = agent.run(job)
    mock_client.images.generate.assert_called_once_with(
        model="gpt-image-1",
        prompt="clean white infographic layout",
        n=1,
        size="1024x1024",
        response_format="b64_json",
    )
    assert job.image_path is not None
    assert job.image_path.endswith("image.png")
    assert job.stage == "lila_done"


def test_lila_live_image_openai_error_raises_runtime(mocker, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mock_client = mocker.MagicMock()
    mock_client.images.generate.side_effect = openai.OpenAIError("quota exceeded")
    mocker.patch("agents.lila.openai.OpenAI", return_value=mock_client)
    mocker.patch.object(LilaAgent, "_call_claude", return_value="some prompt")
    agent = LilaAgent(make_config())
    job = make_image_job(dry_run=False)
    with pytest.raises(RuntimeError, match=job.id):
        agent.run(job)
```

Add these imports at the top of `tests/test_lila.py` (after existing imports):

```python
import base64
import openai
from pathlib import Path
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
/Users/nennayz/Desktop/NayzFreedom/.venv/bin/python3 -m pytest tests/test_lila.py::test_lila_live_image_calls_openai tests/test_lila.py::test_lila_live_infographic_calls_openai tests/test_lila.py::test_lila_live_image_openai_error_raises_runtime -v
```

Expected: 3 FAILED — `test_lila_live_image_calls_openai` and `test_lila_live_infographic_calls_openai` fail because `_generate_image` raises `NotImplementedError`; `test_lila_live_image_openai_error_raises_runtime` fails because `NotImplementedError` is raised instead of `RuntimeError`.

- [ ] **Step 3: Add imports to `lila.py`**

In `agents/lila.py`, change the imports block from:

```python
from __future__ import annotations
from pathlib import Path
from agents.base_agent import BaseAgent, TEAM_IDENTITY
from models.content_job import ContentJob, ContentType, Script, ImageCaption, InfographicContent
```

to:

```python
from __future__ import annotations
import base64
from pathlib import Path
import openai
from agents.base_agent import BaseAgent, TEAM_IDENTITY
from models.content_job import ContentJob, ContentType, Script, ImageCaption, InfographicContent
```

- [ ] **Step 4: Implement `_generate_image` in `lila.py`**

Replace the existing `_generate_image` stub (lines ~94–96):

```python
    def _generate_image(self, job: ContentJob) -> str:
        # Phase 2: wire GPT Image 2 here
        raise NotImplementedError("Image generation wired in Phase 2")
```

with:

```python
    def _generate_image(self, job: ContentJob) -> str:
        client = openai.OpenAI(api_key=self.config.openai_api_key)
        try:
            response = client.images.generate(
                model="gpt-image-1",
                prompt=job.visual_prompt,
                n=1,
                size="1024x1024",
                response_format="b64_json",
            )
        except openai.OpenAIError as e:
            raise RuntimeError(
                f"Image generation failed for job {job.id} "
                f"({job.content_type}): {e}"
            ) from e
        image_bytes = base64.b64decode(response.data[0].b64_json)
        out_dir = Path("output") / job.pm.page_name / job.id
        out_dir.mkdir(parents=True, exist_ok=True)
        image_path = out_dir / "image.png"
        image_path.write_bytes(image_bytes)
        return str(image_path)
```

- [ ] **Step 5: Run the three new tests to verify they pass**

```bash
/Users/nennayz/Desktop/NayzFreedom/.venv/bin/python3 -m pytest tests/test_lila.py::test_lila_live_image_calls_openai tests/test_lila.py::test_lila_live_infographic_calls_openai tests/test_lila.py::test_lila_live_image_openai_error_raises_runtime -v
```

Expected: 3 PASSED

- [ ] **Step 6: Run the full test suite to verify no regressions**

```bash
/Users/nennayz/Desktop/NayzFreedom/.venv/bin/python3 -m pytest -v
```

Expected: all tests pass (was 72 before this task; will be 73 after adding one net new test)

- [ ] **Step 7: Commit**

```bash
git add agents/lila.py tests/test_lila.py
git commit -m "feat(lila): implement _generate_image via OpenAI gpt-image-1"
```
