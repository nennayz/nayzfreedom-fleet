# Phase 2A: Agent Restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename Robin to Chief of Staff, add `name` field to PMProfile for short PM names, add Freedom Architects identity to all agents, and inject past performance data into Robin's context.

**Architecture:** Four independent changes applied in sequence: (1) data model update so `PMProfile` carries a short `name`; (2) YAML + loader update so `slay_hack` loads as `name="Slay"`, `page_name="Slay Hack"`; (3) module-level `TEAM_IDENTITY` constant in `base_agent.py` prepended to every agent's system prompt; (4) `load_recent_performance` helper in `job_store.py` and Robin's updated system prompt in `orchestrator.py`.

**Tech Stack:** Python 3.9+, Pydantic v2, PyYAML, pytest

---

## File Structure

| File | Change |
|---|---|
| `models/content_job.py` | Add `name: str` to `PMProfile` |
| `project_loader.py` | Pass `name` when constructing `PMProfile` |
| `projects/slay_hack/pm_profile.yaml` | Add `name: "Slay"`, set `page_name: "Slay Hack"` |
| `agents/base_agent.py` | Add `TEAM_IDENTITY` module-level constant |
| `agents/mia.py` | Prepend `TEAM_IDENTITY` to system prompt |
| `agents/zoe.py` | Prepend `TEAM_IDENTITY` to system prompt |
| `agents/bella.py` | Prepend `TEAM_IDENTITY` to system prompt |
| `agents/lila.py` | Prepend `TEAM_IDENTITY` to system prompt |
| `agents/nora.py` | Prepend `TEAM_IDENTITY` to system prompt |
| `agents/roxy.py` | Prepend `TEAM_IDENTITY` to system prompt |
| `agents/emma.py` | Prepend `TEAM_IDENTITY` to system prompt |
| `job_store.py` | Add `load_recent_performance(page_name, limit) -> str` |
| `orchestrator.py` | Chief of Staff system prompt + inject performance into first message |
| `tests/test_models.py` | Add `name` to `make_pm()` fixture |
| `tests/test_checkpoint.py` | Add `name` to `PMProfile` fixture |
| `tests/test_mia.py` | Add `name` to `PMProfile` fixture |
| `tests/test_project_loader.py` | Update assertions for new `name` + `page_name` |
| `tests/test_job_store.py` | New file — tests for `load_recent_performance` |

---

### Task 1: PMProfile `name` field + update all test fixtures

**Files:**
- Modify: `models/content_job.py:31-34`
- Modify: `tests/test_models.py`
- Modify: `tests/test_checkpoint.py`
- Modify: `tests/test_mia.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_models.py` after `test_qa_result_defaults`:

```python
def test_pm_profile_has_name():
    pm = PMProfile(name="Slay", page_name="Slay Hack", persona="test", brand=make_brand())
    assert pm.name == "Slay"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
source .venv/bin/activate && pytest tests/test_models.py::test_pm_profile_has_name -v
```

Expected: FAIL — `PMProfile() got an unexpected keyword argument 'name'`

- [ ] **Step 3: Add `name` field to `PMProfile`**

In `models/content_job.py`, change lines 31–34 from:

```python
class PMProfile(BaseModel):
    page_name: str
    persona: str
    brand: BrandProfile
```

to:

```python
class PMProfile(BaseModel):
    name: str
    page_name: str
    persona: str
    brand: BrandProfile
```

- [ ] **Step 4: Update `make_pm()` in `tests/test_models.py`**

Change line 19 from:

```python
    return PMProfile(page_name="Test Page", persona="You are a test PM.", brand=make_brand())
```

to:

```python
    return PMProfile(name="Test", page_name="Test Page", persona="You are a test PM.", brand=make_brand())
```

- [ ] **Step 5: Update `PMProfile` fixture in `tests/test_checkpoint.py`**

Change line 11 from:

```python
    pm = PMProfile(page_name="Test Page", persona="", brand=brand)
```

to:

```python
    pm = PMProfile(name="Test", page_name="Test Page", persona="", brand=brand)
```

- [ ] **Step 6: Update `PMProfile` fixture in `tests/test_mia.py`**

Change line 17 from:

```python
    pm = PMProfile(page_name="Slay Hack Agency", persona="test pm", brand=brand)
```

to:

```python
    pm = PMProfile(name="Slay", page_name="Slay Hack Agency", persona="test pm", brand=brand)
```

- [ ] **Step 7: Run all tests to verify fixtures pass**

```bash
pytest tests/test_models.py tests/test_checkpoint.py tests/test_mia.py -v
```

Expected: all tests PASS

- [ ] **Step 8: Commit**

```bash
git add models/content_job.py tests/test_models.py tests/test_checkpoint.py tests/test_mia.py
git commit -m "feat: add name field to PMProfile"
```

---

### Task 2: Update pm_profile.yaml + project_loader

**Files:**
- Modify: `projects/slay_hack/pm_profile.yaml`
- Modify: `project_loader.py:33-37`
- Modify: `tests/test_project_loader.py`

- [ ] **Step 1: Write the failing test**

In `tests/test_project_loader.py`, update `test_load_slay_hack` to:

```python
def test_load_slay_hack():
    pm = load_project("slay_hack")
    assert isinstance(pm, PMProfile)
    assert pm.name == "Slay"
    assert pm.page_name == "Slay Hack"
    assert pm.brand.nora_max_retries == 2
    assert "#D4AF37" in pm.brand.visual.colors
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_project_loader.py::test_load_slay_hack -v
```

Expected: FAIL — `PMProfile() missing required field 'name'` (or similar Pydantic validation error)

- [ ] **Step 3: Update `projects/slay_hack/pm_profile.yaml`**

Replace the entire file with:

```yaml
name: "Slay"
page_name: "Slay Hack"
persona: |
  You are Slay, the Project Manager for Slay Hack.
  You speak with confident, trendy energy. You push the
  Freedom Architects team toward bold, viral-first ideas
  aimed at Gen Z & Millennial women in the USA.
  You never approve anything that feels safe or corporate.
  Your aesthetic is Quiet Luxury — minimalist, high-end, aspirational.
```

- [ ] **Step 4: Update `project_loader.py` to pass `name`**

Change lines 33–37 from:

```python
    return PMProfile(
        page_name=pm_data["page_name"],
        persona=pm_data["persona"].strip(),
        brand=brand,
    )
```

to:

```python
    return PMProfile(
        name=pm_data["name"],
        page_name=pm_data["page_name"],
        persona=pm_data["persona"].strip(),
        brand=brand,
    )
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_project_loader.py -v
```

Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add projects/slay_hack/pm_profile.yaml project_loader.py tests/test_project_loader.py
git commit -m "feat: add PM short name to pm_profile.yaml and project_loader"
```

---

### Task 3: Freedom Architects identity in all 7 agents

**Files:**
- Modify: `agents/base_agent.py`
- Modify: `agents/mia.py`, `agents/zoe.py`, `agents/bella.py`, `agents/lila.py`, `agents/nora.py`, `agents/roxy.py`, `agents/emma.py`
- Test: `tests/test_zoe.py`

- [ ] **Step 1: Write the failing test**

Open `tests/test_zoe.py` and add after the existing imports:

```python
def test_zoe_system_prompt_includes_team_identity(mocker):
    from agents.zoe import ZoeAgent
    from tests.test_mia import make_config, make_job
    captured = {}
    def fake_call(system, user, **kwargs):
        captured["system"] = system
        return '[{"number":1,"title":"T","hook":"h","angle":"a"}]'
    agent = ZoeAgent(make_config())
    mocker.patch.object(agent, "_call_claude", side_effect=fake_call)
    job = make_job(dry_run=False)
    job.trend_data = {"trends": [], "trending_sounds": [], "formats": []}
    agent.run(job)
    assert "Freedom Architects" in captured["system"]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_zoe.py::test_zoe_system_prompt_includes_team_identity -v
```

Expected: FAIL — `AssertionError: assert 'Freedom Architects' in ...`

- [ ] **Step 3: Add `TEAM_IDENTITY` to `agents/base_agent.py`**

Add after the imports (after line 5, before `class BaseAgent`):

```python
TEAM_IDENTITY = "You are part of Freedom Architects, the content team at NayzFreedom.\n\n"
```

Full file after change:

```python
from __future__ import annotations
from abc import ABC, abstractmethod
from anthropic import Anthropic
from config import Config
from models.content_job import ContentJob

TEAM_IDENTITY = "You are part of Freedom Architects, the content team at NayzFreedom.\n\n"


class BaseAgent(ABC):
    def __init__(self, config: Config):
        self.config = config
        self.client = Anthropic(api_key=config.anthropic_api_key)
        self.model = "claude-sonnet-4-6"

    def run(self, job: ContentJob, **kwargs) -> ContentJob:
        if job.dry_run:
            return self.run_dry(job, **kwargs)
        return self.run_live(job, **kwargs)

    @abstractmethod
    def run_live(self, job: ContentJob, **kwargs) -> ContentJob:
        pass

    @abstractmethod
    def run_dry(self, job: ContentJob, **kwargs) -> ContentJob:
        pass

    def _call_claude(self, system: str, user: str, max_tokens: int = 2048) -> str:
        from anthropic.types import TextBlock
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}],
        )
        for block in response.content:
            if isinstance(block, TextBlock):
                return block.text
        raise ValueError("No text block in Claude response")

    def _parse_json(self, raw: str) -> dict | list:
        import json
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(f"Agent received invalid JSON from Claude: {e}\nRaw: {raw[:200]}")
```

- [ ] **Step 4: Update all 7 agent `run_live` system prompts**

In each file, add `from agents.base_agent import BaseAgent, TEAM_IDENTITY` to the import and prepend `TEAM_IDENTITY` to the `system` string in `run_live`.

**`agents/mia.py`** — change import line 5 and system prompt in `run_live` (lines 39–43):

```python
from agents.base_agent import BaseAgent, TEAM_IDENTITY
```

```python
        system = (
            TEAM_IDENTITY +
            f"You are Mia, a trend researcher for {job.pm.page_name}. "
            f"Target audience: {job.pm.brand.target_audience}. "
            f"Platforms: {', '.join(job.platforms)}."
        )
```

**`agents/zoe.py`** — change import line 4 and system prompt in `run_live` (lines 32–36):

```python
from agents.base_agent import BaseAgent, TEAM_IDENTITY
```

```python
        system = (
            TEAM_IDENTITY +
            f"You are Zoe, a content ideation specialist for {job.pm.page_name}. "
            f"Brand tone: {job.pm.brand.tone}. "
            f"Target audience: {job.pm.brand.target_audience}."
        )
```

**`agents/bella.py`** — change import line 4 and system prompt in `run_live` (lines 36–42):

```python
from agents.base_agent import BaseAgent, TEAM_IDENTITY
```

```python
        system = (
            TEAM_IDENTITY +
            f"You are Bella, a script writer for {job.pm.page_name}. "
            f"Script style: {job.pm.brand.script_style}. "
            f"Tone: {job.pm.brand.tone}. "
            f"Audience: {job.pm.brand.target_audience}. "
            "Write Reels scripts with Hook → Body → CTA structure."
        )
```

**`agents/lila.py`** — change import line 4 and system prompt in `run_live` (lines 23–27):

```python
from agents.base_agent import BaseAgent, TEAM_IDENTITY
```

```python
        system = (
            TEAM_IDENTITY +
            f"You are Lila, visual director for {job.pm.page_name}. "
            f"Visual style: {job.pm.brand.visual.style}. "
            f"Color palette: {', '.join(job.pm.brand.visual.colors)}."
        )
```

**`agents/nora.py`** — change import line 3 and system prompt in `run_live` (lines 14–19):

```python
from agents.base_agent import BaseAgent, TEAM_IDENTITY
```

```python
        system = (
            TEAM_IDENTITY +
            f"You are Nora, QA editor for {job.pm.page_name}. "
            f"Brand tone: {job.pm.brand.tone}. "
            f"Audience: {job.pm.brand.target_audience}. "
            "Be strict. Reject weak hooks, off-brand visuals, and anything that feels generic."
        )
```

**`agents/roxy.py`** — change import line 4 and system prompt in `run_live` (lines 34–38):

```python
from agents.base_agent import BaseAgent, TEAM_IDENTITY
```

```python
        system = (
            TEAM_IDENTITY +
            f"You are Roxy, growth strategist for {job.pm.page_name}. "
            f"Target audience: {job.pm.brand.target_audience}. "
            f"Platforms: {', '.join(job.platforms)}."
        )
```

**`agents/emma.py`** — change import line 4 and system prompt in `run_live` (lines 27–31):

```python
from agents.base_agent import BaseAgent, TEAM_IDENTITY
```

```python
        system = (
            TEAM_IDENTITY +
            f"You are Emma, community manager for {job.pm.page_name}. "
            "Write warm, friendly, conversational responses. "
            f"Tone: {job.pm.brand.tone}."
        )
```

- [ ] **Step 5: Run all tests**

```bash
pytest -v
```

Expected: all 28 tests PASS (27 existing + 1 new)

- [ ] **Step 6: Commit**

```bash
git add agents/base_agent.py agents/mia.py agents/zoe.py agents/bella.py agents/lila.py agents/nora.py agents/roxy.py agents/emma.py tests/test_zoe.py
git commit -m "feat: add Freedom Architects team identity to all agents"
```

---

### Task 4: Robin Chief of Staff + performance loader

**Files:**
- Modify: `job_store.py`
- Modify: `orchestrator.py:17-37`
- Create: `tests/test_job_store.py`

- [ ] **Step 1: Write failing tests for `load_recent_performance`**

Create `tests/test_job_store.py`:

```python
from __future__ import annotations
from job_store import save_job, load_recent_performance
from models.content_job import (
    ContentJob, PMProfile, BrandProfile, VisualIdentity, PostPerformance
)


def make_pm():
    brand = BrandProfile(
        mission="m", visual=VisualIdentity(colors=[], style=""), platforms=[],
        tone="", target_audience="", script_style="", nora_max_retries=2,
    )
    return PMProfile(name="Test", page_name="Test", persona="", brand=brand)


def make_job():
    return ContentJob(project="test", pm=make_pm(), brief="b", platforms=["instagram"])


def test_load_recent_performance_no_output_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert load_recent_performance("Test") == ""


def test_load_recent_performance_no_performance_data(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    job = make_job()
    save_job(job)
    assert load_recent_performance("Test") == ""


def test_load_recent_performance_with_data(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    job = make_job()
    job.performance = [PostPerformance(platform="instagram", likes=100, reach=5000, saves=20)]
    save_job(job)
    result = load_recent_performance("Test")
    assert "likes=100" in result
    assert "reach=5000" in result
    assert "instagram" in result


def test_load_recent_performance_respects_limit(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # Create 7 job.json files with distinct IDs manually (ContentJob ID is second-granularity)
    for i in range(7):
        job = make_job()
        job.id = f"2026050{i}_120000"
        job.performance = [PostPerformance(platform="instagram", likes=i)]
        out_dir = tmp_path / "output" / "Test" / job.id
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "job.json").write_text(job.model_dump_json())
    result = load_recent_performance("Test", limit=3)
    # Should contain at most 3 jobs worth of data
    assert result.count("instagram") <= 3
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_job_store.py -v
```

Expected: FAIL — `ImportError: cannot import name 'load_recent_performance' from 'job_store'`

- [ ] **Step 3: Add `load_recent_performance` to `job_store.py`**

Full `job_store.py` after change:

```python
from __future__ import annotations
import json
from pathlib import Path
from models.content_job import ContentJob


def save_job(job: ContentJob) -> Path:
    out_dir = Path("output") / job.pm.page_name / job.id
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "job.json"
    path.write_text(job.model_dump_json(indent=2))
    return path


def load_job(job_id: str, page_name: str) -> ContentJob:
    path = Path("output") / page_name / job_id / "job.json"
    if not path.exists():
        raise FileNotFoundError(f"Job not found: {path}")
    return ContentJob.model_validate_json(path.read_text())


def find_job(job_id: str) -> ContentJob:
    for path in Path("output").rglob(f"{job_id}/job.json"):
        return ContentJob.model_validate_json(path.read_text())
    raise FileNotFoundError(f"Job ID '{job_id}' not found in output/")


def load_recent_performance(page_name: str, limit: int = 5) -> str:
    page_dir = Path("output") / page_name
    if not page_dir.exists():
        return ""
    job_files = sorted(page_dir.rglob("job.json"), reverse=True)[:limit]
    lines = []
    for path in job_files:
        try:
            job = ContentJob.model_validate_json(path.read_text())
            for p in job.performance:
                lines.append(
                    f"Job {job.id} ({p.platform}): "
                    f"likes={p.likes}, reach={p.reach}, saves={p.saves}, shares={p.shares}"
                )
        except Exception:
            continue
    if not lines:
        return ""
    return "Past performance data:\n" + "\n".join(lines)
```

- [ ] **Step 4: Run job_store tests**

```bash
pytest tests/test_job_store.py -v
```

Expected: all 4 tests PASS

- [ ] **Step 5: Update Robin's system prompt and first message in `orchestrator.py`**

Full `orchestrator.py` after change:

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
2. run_zoe — generate ideas
3. request_checkpoint (stage: "idea_selection") — show ideas, wait for user to pick one
4. run_bella — write script for the selected idea
5. run_lila — create visual prompt and key image
6. request_checkpoint (stage: "content_review") — show script and visual for approval
7. run_nora — QA review. If QA fails and retry count < max_retries, re-run the relevant agent.
8. request_checkpoint (stage: "qa_review") — show QA result
9. run_roxy — hashtags + caption + timing
10. run_emma — community FAQ
11. request_checkpoint (stage: "final_approval") — final sign-off before publishing

Never skip a checkpoint. After final_approval, declare the job complete.
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
                stage=tool_input["stage"],
                summary=tool_input["summary"],
                options=tool_input.get("options", []),
                job=job,
            )
            return {"decision": result.decision}

        agent_name = tool_name.replace("run_", "")
        if agent_name not in self.agents:
            return {"error": f"Unknown tool: {tool_name}"}

        self.agents[agent_name].run(job)
        return {"status": "ok", "stage": job.stage}
```

- [ ] **Step 6: Run the full test suite**

```bash
pytest -v
```

Expected: all tests PASS (minimum 31: 27 original + 1 team identity + 4 job store — exact count depends on `test_zoe.py` existing tests)

- [ ] **Step 7: Commit**

```bash
git add job_store.py orchestrator.py tests/test_job_store.py
git commit -m "feat: Robin Chief of Staff persona + load_recent_performance"
```
