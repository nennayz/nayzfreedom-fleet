# Slay Hack Agency — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the complete Phase 1 pipeline — CLI, all 8 agents (Robin + 7 specialists), 4 human-in-the-loop checkpoints, job persistence, and dry-run mode — runnable end-to-end with `python main.py --project slay_hack --brief "..." --dry-run`.

**Architecture:** Robin (claude-opus-4-7 with tool use) orchestrates 7 agents by calling them as Claude tools. Each agent receives a `ContentJob` Pydantic model, updates it, and persists state to `output/<page_name>/<job_id>/job.json` after every step. Four `request_checkpoint` tool calls pause the loop and read user input from stdin.

**Tech Stack:** Python 3.11+, `anthropic` SDK (tool use + prompt caching), `pydantic` v2, `pyyaml`, `python-dotenv`, `requests` (Brave Search), `pytest`, `pytest-mock`, `ruff`, `mypy`

---

## File Map

**Create (new files):**
```
requirements.txt
.env.example
.gitignore
config.py
models/__init__.py
models/content_job.py
agents/__init__.py
agents/base_agent.py
agents/mia.py
agents/zoe.py
agents/bella.py
agents/lila.py
agents/nora.py
agents/roxy.py
agents/emma.py
tools/__init__.py
tools/agent_tools.py
checkpoint.py
orchestrator.py
main.py
projects/slay_hack/pm_profile.yaml
projects/slay_hack/brand.yaml
tests/__init__.py
tests/test_models.py
tests/test_config.py
tests/test_checkpoint.py
tests/test_mia.py
tests/test_zoe.py
tests/test_bella.py
tests/test_lila.py
tests/test_nora.py
tests/test_roxy.py
tests/test_emma.py
tests/test_orchestrator.py
```

---

## Task 1: Project Scaffold

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `.gitignore`

- [ ] **Step 1: Create `requirements.txt`**

```
anthropic>=0.40.0
openai>=1.0.0
pydantic>=2.0.0
python-dotenv>=1.0.0
pyyaml>=6.0
requests>=2.31.0
pytest>=8.0.0
pytest-mock>=3.12.0
ruff>=0.5.0
mypy>=1.10.0
types-requests>=2.31.0
types-pyyaml>=6.0
```

- [ ] **Step 2: Create `.env.example`**

```
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
BRAVE_SEARCH_API_KEY=
GOOGLE_CLOUD_PROJECT=
GOOGLE_APPLICATION_CREDENTIALS=
META_ACCESS_TOKEN=
TIKTOK_ACCESS_TOKEN=
YOUTUBE_API_KEY=
```

- [ ] **Step 3: Create `.gitignore`**

```
.env
.venv/
__pycache__/
*.pyc
output/
.mypy_cache/
.ruff_cache/
.superpowers/
```

- [ ] **Step 4: Install dependencies and verify**

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -c "import anthropic, pydantic, yaml; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git init
git add requirements.txt .env.example .gitignore
git commit -m "chore: project scaffold"
```

---

## Task 2: Data Models

**Files:**
- Create: `models/__init__.py`
- Create: `models/content_job.py`
- Create: `tests/__init__.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write the failing test**

`tests/test_models.py`:
```python
from models.content_job import (
    ContentJob, PMProfile, BrandProfile, VisualIdentity,
    Idea, Script, QAResult, GrowthStrategy, CheckpointDecision,
    PostPerformance, JobStatus
)

def make_brand():
    return BrandProfile(
        mission="Test mission",
        visual=VisualIdentity(colors=["#FFF"], style="minimalist"),
        platforms=["instagram"],
        tone="casual",
        target_audience="Gen Z women USA",
        script_style="lowercase slang",
        nora_max_retries=2,
    )

def make_pm():
    return PMProfile(page_name="Test Page", persona="You are a test PM.", brand=make_brand())

def test_content_job_defaults():
    job = ContentJob(project="test", pm=make_pm(), brief="test brief", platforms=["instagram"])
    assert job.status == JobStatus.PENDING
    assert job.stage == "init"
    assert job.dry_run is False
    assert job.nora_retry_count == 0
    assert job.checkpoint_log == []
    assert job.performance == []

def test_content_job_id_is_timestamp_format():
    job = ContentJob(project="test", pm=make_pm(), brief="b", platforms=["instagram"])
    assert len(job.id) == 15  # YYYYMMDD_HHMMSS

def test_idea_model():
    idea = Idea(number=1, title="Test Idea", hook="Test hook", angle="Tutorial")
    assert idea.number == 1

def test_qa_result_defaults():
    qa = QAResult(passed=True)
    assert qa.send_back_to is None
    assert qa.script_feedback is None
```

- [ ] **Step 2: Run test — verify it fails**

```bash
pytest tests/test_models.py -v
```

Expected: `ModuleNotFoundError: No module named 'models'`

- [ ] **Step 3: Create `models/__init__.py`** (empty file)

- [ ] **Step 4: Create `models/content_job.py`**

```python
from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"


class VisualIdentity(BaseModel):
    colors: list[str]
    style: str


class BrandProfile(BaseModel):
    mission: str
    visual: VisualIdentity
    platforms: list[str]
    tone: str
    target_audience: str
    script_style: str
    nora_max_retries: int = 2


class PMProfile(BaseModel):
    page_name: str
    persona: str
    brand: BrandProfile


class Idea(BaseModel):
    number: int
    title: str
    hook: str
    angle: str


class Script(BaseModel):
    hook: str
    body: str
    cta: str
    duration_seconds: int


class QAResult(BaseModel):
    passed: bool
    script_feedback: Optional[str] = None
    visual_feedback: Optional[str] = None
    send_back_to: Optional[str] = None  # "bella" | "lila" | None


class GrowthStrategy(BaseModel):
    hashtags: list[str]
    caption: str
    best_post_time_utc: str
    best_post_time_thai: str


class CheckpointDecision(BaseModel):
    stage: str
    decision: str
    timestamp: datetime = Field(default_factory=datetime.now)


class PostPerformance(BaseModel):
    platform: str
    likes: Optional[int] = None
    reach: Optional[int] = None
    saves: Optional[int] = None
    shares: Optional[int] = None
    recorded_at: Optional[datetime] = None


class ContentJob(BaseModel):
    id: str = Field(default_factory=lambda: datetime.now().strftime("%Y%m%d_%H%M%S"))
    project: str
    pm: PMProfile
    brief: str
    platforms: list[str]
    stage: str = "init"
    status: JobStatus = JobStatus.PENDING
    dry_run: bool = False
    trend_data: Optional[dict] = None
    ideas: Optional[list[Idea]] = None
    selected_idea: Optional[Idea] = None
    script: Optional[Script] = None
    visual_prompt: Optional[str] = None
    image_path: Optional[str] = None
    video_path: Optional[str] = None
    qa_result: Optional[QAResult] = None
    nora_retry_count: int = 0
    growth_strategy: Optional[GrowthStrategy] = None
    community_faq_path: Optional[str] = None
    publish_result: Optional[dict] = None
    checkpoint_log: list[CheckpointDecision] = Field(default_factory=list)
    performance: list[PostPerformance] = Field(default_factory=list)
```

- [ ] **Step 5: Run test — verify it passes**

```bash
pytest tests/test_models.py -v
```

Expected: 4 tests PASSED

- [ ] **Step 6: Commit**

```bash
git add models/ tests/__init__.py tests/test_models.py
git commit -m "feat: ContentJob data models"
```

---

## Task 3: Config Loader

**Files:**
- Create: `config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

`tests/test_config.py`:
```python
import os
import pytest
from config import Config, MissingAPIKeyError


def test_config_loads_from_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-123")
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "brave-key")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    cfg = Config.from_env()
    assert cfg.anthropic_api_key == "test-key-123"
    assert cfg.brave_search_api_key == "brave-key"
    assert cfg.openai_api_key == "openai-key"


def test_config_raises_on_missing_anthropic_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(MissingAPIKeyError, match="ANTHROPIC_API_KEY"):
        Config.from_env()
```

- [ ] **Step 2: Run test — verify it fails**

```bash
pytest tests/test_config.py -v
```

Expected: `ModuleNotFoundError: No module named 'config'`

- [ ] **Step 3: Create `config.py`**

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
            tiktok_access_token=os.getenv("TIKTOK_ACCESS_TOKEN", ""),
            youtube_api_key=os.getenv("YOUTUBE_API_KEY", ""),
        )
```

- [ ] **Step 4: Run test — verify it passes**

```bash
pytest tests/test_config.py -v
```

Expected: 2 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add config.py tests/test_config.py
git commit -m "feat: config loader with env validation"
```

---

## Task 4: Project Loader + Job Persistence

**Files:**
- Create: `project_loader.py`
- Create: `job_store.py`
- Create: `tests/test_project_loader.py`

- [ ] **Step 1: Create `projects/slay_hack/pm_profile.yaml`**

```bash
mkdir -p projects/slay_hack
```

`projects/slay_hack/pm_profile.yaml`:
```yaml
page_name: "Slay Hack Agency"
persona: |
  You are the PM for Slay Hack Agency. You speak with confident, trendy energy.
  You push the team toward bold, viral-first ideas aimed at Gen Z & Millennial
  women in the USA. You never approve anything that feels safe or corporate.
  Your aesthetic is Quiet Luxury — minimalist, high-end, aspirational.
```

`projects/slay_hack/brand.yaml`:
```yaml
mission: "Quiet Luxury content for Gen Z & Millennial women in USA"
visual:
  colors: ["#FFFFFF", "#F5F0E8", "#D4AF37", "#1A3A5C"]
  style: "minimalist high-end, soft studio lighting"
platforms:
  - instagram
  - facebook
tone: "sassy, confident"
target_audience: "Gen Z & Millennial women, USA"
script_style: "lowercase Gen Z slang"
nora_max_retries: 2
```

- [ ] **Step 2: Write the failing test**

`tests/test_project_loader.py`:
```python
import pytest
from project_loader import load_project, ProjectNotFoundError
from models.content_job import PMProfile


def test_load_slay_hack():
    pm = load_project("slay_hack")
    assert isinstance(pm, PMProfile)
    assert pm.page_name == "Slay Hack Agency"
    assert pm.brand.nora_max_retries == 2
    assert "#D4AF37" in pm.brand.visual.colors


def test_load_missing_project_raises():
    with pytest.raises(ProjectNotFoundError, match="nonexistent"):
        load_project("nonexistent")
```

- [ ] **Step 3: Run test — verify it fails**

```bash
pytest tests/test_project_loader.py -v
```

Expected: `ModuleNotFoundError: No module named 'project_loader'`

- [ ] **Step 4: Create `project_loader.py`**

```python
from __future__ import annotations
from pathlib import Path
import yaml
from models.content_job import PMProfile, BrandProfile, VisualIdentity


class ProjectNotFoundError(Exception):
    pass


def load_project(project_slug: str) -> PMProfile:
    base = Path("projects") / project_slug
    if not base.exists():
        raise ProjectNotFoundError(f"Project '{project_slug}' not found in projects/")

    pm_data = yaml.safe_load((base / "pm_profile.yaml").read_text())
    brand_data = yaml.safe_load((base / "brand.yaml").read_text())

    brand = BrandProfile(
        mission=brand_data["mission"],
        visual=VisualIdentity(**brand_data["visual"]),
        platforms=brand_data["platforms"],
        tone=brand_data["tone"],
        target_audience=brand_data["target_audience"],
        script_style=brand_data["script_style"],
        nora_max_retries=brand_data.get("nora_max_retries", 2),
    )
    return PMProfile(
        page_name=pm_data["page_name"],
        persona=pm_data["persona"].strip(),
        brand=brand,
    )
```

- [ ] **Step 5: Create `job_store.py`**

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
```

- [ ] **Step 6: Run tests — verify they pass**

```bash
pytest tests/test_project_loader.py -v
```

Expected: 2 tests PASSED

- [ ] **Step 7: Commit**

```bash
git add projects/ project_loader.py job_store.py tests/test_project_loader.py
git commit -m "feat: project loader and job persistence"
```

---

## Task 5: Checkpoint Manager

**Files:**
- Create: `checkpoint.py`
- Create: `tests/test_checkpoint.py`

- [ ] **Step 1: Write the failing test**

`tests/test_checkpoint.py`:
```python
from unittest.mock import patch
from checkpoint import pause, CheckpointResult
from models.content_job import ContentJob, PMProfile, BrandProfile, VisualIdentity, CheckpointDecision


def make_job():
    brand = BrandProfile(
        mission="m", visual=VisualIdentity(colors=[], style=""), platforms=[],
        tone="", target_audience="", script_style="", nora_max_retries=2,
    )
    pm = PMProfile(page_name="Test Page", persona="", brand=brand)
    return ContentJob(project="test", pm=pm, brief="b", platforms=[])


def test_pause_approve(capsys):
    with patch("builtins.input", return_value="y"):
        result = pause("qa_review", "Script looks good.", [], make_job())
    assert result.decision == "y"
    assert result.stage == "qa_review"


def test_pause_records_to_checkpoint_log():
    job = make_job()
    with patch("builtins.input", return_value="skip"):
        result = pause("ideation", "Pick an idea.", ["1", "2", "3"], job)
    assert len(job.checkpoint_log) == 1
    assert job.checkpoint_log[0].stage == "ideation"
    assert job.checkpoint_log[0].decision == "skip"
```

- [ ] **Step 2: Run test — verify it fails**

```bash
pytest tests/test_checkpoint.py -v
```

Expected: `ModuleNotFoundError: No module named 'checkpoint'`

- [ ] **Step 3: Create `checkpoint.py`**

```python
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from models.content_job import ContentJob, CheckpointDecision


@dataclass
class CheckpointResult:
    stage: str
    decision: str


def pause(stage: str, summary: str, options: list[str], job: ContentJob) -> CheckpointResult:
    print(f"\n{'='*60}")
    print(f"  CHECKPOINT: {stage.upper().replace('_', ' ')}")
    print(f"{'='*60}")
    print(f"\n{summary}\n")
    if options:
        for i, opt in enumerate(options, 1):
            print(f"  [{i}] {opt}")
    print()
    decision = input("Your choice (or type freely): ").strip()

    job.checkpoint_log.append(
        CheckpointDecision(stage=stage, decision=decision, timestamp=datetime.now())
    )
    return CheckpointResult(stage=stage, decision=decision)
```

- [ ] **Step 4: Run test — verify it passes**

```bash
pytest tests/test_checkpoint.py -v
```

Expected: 2 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add checkpoint.py tests/test_checkpoint.py
git commit -m "feat: checkpoint manager with stdin pause"
```

---

## Task 6: Base Agent

**Files:**
- Create: `agents/__init__.py`
- Create: `agents/base_agent.py`

- [ ] **Step 1: Create `agents/__init__.py`** (empty)

- [ ] **Step 2: Create `agents/base_agent.py`**

```python
from __future__ import annotations
from abc import ABC, abstractmethod
from anthropic import Anthropic
from config import Config
from models.content_job import ContentJob


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
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}],
        )
        return response.content[0].text
```

- [ ] **Step 3: Commit**

```bash
git add agents/
git commit -m "feat: base agent with dry-run dispatch"
```

---

## Task 7: Mia — Trend Research Agent

**Files:**
- Create: `agents/mia.py`
- Create: `tests/test_mia.py`

- [ ] **Step 1: Write the failing test**

`tests/test_mia.py`:
```python
import pytest
from unittest.mock import patch, MagicMock
from agents.mia import MiaAgent
from config import Config
from models.content_job import ContentJob, PMProfile, BrandProfile, VisualIdentity


def make_config():
    return Config(anthropic_api_key="test", brave_search_api_key="brave", openai_api_key="oai")


def make_job(dry_run=True):
    brand = BrandProfile(
        mission="m", visual=VisualIdentity(colors=[], style=""), platforms=["instagram"],
        tone="sassy", target_audience="Gen Z USA", script_style="lowercase", nora_max_retries=2,
    )
    pm = PMProfile(page_name="Slay Hack Agency", persona="test pm", brand=brand)
    return ContentJob(project="slay_hack", pm=pm, brief="lipstick that lasts", platforms=["instagram"], dry_run=dry_run)


def test_mia_dry_run_populates_trend_data():
    agent = MiaAgent(make_config())
    job = agent.run(make_job(dry_run=True))
    assert job.trend_data is not None
    assert "trends" in job.trend_data
    assert job.stage == "mia_done"


def test_mia_live_calls_brave_search(mocker):
    mock_get = mocker.patch("agents.mia.requests.get")
    mock_get.return_value.json.return_value = {
        "web": {"results": [{"title": "Glossy lips trend", "description": "trending now"}]}
    }
    mock_get.return_value.raise_for_status = MagicMock()
    mocker.patch.object(MiaAgent, "_call_claude", return_value='{"trends": ["Glossy lips"], "trending_sounds": ["Espresso"]}')

    agent = MiaAgent(make_config())
    job = agent.run(make_job(dry_run=False))
    assert job.trend_data is not None
    assert job.stage == "mia_done"
    mock_get.assert_called_once()
```

- [ ] **Step 2: Run test — verify it fails**

```bash
pytest tests/test_mia.py -v
```

Expected: `ModuleNotFoundError: No module named 'agents.mia'`

- [ ] **Step 3: Create `agents/mia.py`**

```python
from __future__ import annotations
import json
import requests
from agents.base_agent import BaseAgent
from config import Config
from models.content_job import ContentJob

_DRY_RUN_DATA = {
    "trends": ["Glossy lips that don't budge", "Quiet luxury skincare", "5-minute GRWM"],
    "trending_sounds": ["Espresso - Sabrina Carpenter", "Apple - Charli xcx"],
    "formats": ["POV", "Get ready with me", "Before & after"],
    "source": "dry-run mock",
}

_BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"


class MiaAgent(BaseAgent):
    def run_dry(self, job: ContentJob, **kwargs) -> ContentJob:
        job.trend_data = _DRY_RUN_DATA
        job.stage = "mia_done"
        return job

    def run_live(self, job: ContentJob, **kwargs) -> ContentJob:
        query = f"{job.brief} trend {' '.join(job.platforms)} 2025"
        resp = requests.get(
            _BRAVE_SEARCH_URL,
            headers={"Accept": "application/json", "X-Subscription-Token": self.config.brave_search_api_key},
            params={"q": query, "count": 10},
        )
        resp.raise_for_status()
        search_results = resp.json()

        snippets = "\n".join(
            f"- {r['title']}: {r.get('description', '')}"
            for r in search_results.get("web", {}).get("results", [])[:5]
        )
        system = (
            f"You are Mia, a trend researcher for {job.pm.page_name}. "
            f"Target audience: {job.pm.brand.target_audience}. "
            f"Platforms: {', '.join(job.platforms)}."
        )
        user = (
            f"Brief: {job.brief}\n\nSearch results:\n{snippets}\n\n"
            "Return a JSON object with keys: trends (list of str), "
            "trending_sounds (list of str), formats (list of str). JSON only."
        )
        raw = self._call_claude(system, user)
        job.trend_data = json.loads(raw)
        job.stage = "mia_done"
        return job
```

- [ ] **Step 4: Run test — verify it passes**

```bash
pytest tests/test_mia.py -v
```

Expected: 2 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add agents/mia.py tests/test_mia.py
git commit -m "feat: Mia trend research agent (Brave Search)"
```

---

## Task 8: Zoe — Idea Generator

**Files:**
- Create: `agents/zoe.py`
- Create: `tests/test_zoe.py`

- [ ] **Step 1: Write the failing test**

`tests/test_zoe.py`:
```python
from agents.zoe import ZoeAgent
from tests.test_mia import make_config, make_job
from models.content_job import Idea


def test_zoe_dry_run_returns_ideas():
    job = make_job(dry_run=True)
    job.trend_data = {"trends": ["Glossy lips"], "trending_sounds": ["Espresso"], "formats": ["POV"]}
    agent = ZoeAgent(make_config())
    job = agent.run(job)
    assert job.ideas is not None
    assert len(job.ideas) >= 3
    assert all(isinstance(i, Idea) for i in job.ideas)
    assert job.stage == "zoe_done"


def test_zoe_live_calls_claude(mocker):
    ideas_json = '[{"number":1,"title":"Lip Hack","hook":"pov your lips last","angle":"Tutorial"}]'
    mocker.patch.object(ZoeAgent, "_call_claude", return_value=ideas_json)
    job = make_job(dry_run=False)
    job.trend_data = {"trends": ["Glossy lips"], "trending_sounds": [], "formats": []}
    agent = ZoeAgent(make_config())
    job = agent.run(job)
    assert len(job.ideas) == 1
    assert job.ideas[0].title == "Lip Hack"
```

- [ ] **Step 2: Run test — verify it fails**

```bash
pytest tests/test_zoe.py -v
```

Expected: `ModuleNotFoundError: No module named 'agents.zoe'`

- [ ] **Step 3: Create `agents/zoe.py`**

```python
from __future__ import annotations
import json
from agents.base_agent import BaseAgent
from models.content_job import ContentJob, Idea

_DRY_RUN_IDEAS = [
    Idea(number=1, title="The Invisible Lip Liner Hack", hook="POV: your lips last all day", angle="Tutorial"),
    Idea(number=2, title="Quiet Luxury Morning Routine", hook="This is how rich girls start their day", angle="Lifestyle"),
    Idea(number=3, title="5 Dupes That Beat the Original", hook="Stop wasting money on expensive formulas", angle="Review"),
    Idea(number=4, title="The 3-Step Kiss-Proof Secret", hook="omg why did nobody tell me this earlier", angle="Tutorial"),
    Idea(number=5, title="Get Ready With Me: Date Night Edition", hook="come get ready with me for a night out", angle="GRWM"),
]


def _write_ideas_file(job: ContentJob) -> None:
    from pathlib import Path
    out_dir = Path("output") / job.pm.page_name / job.id
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = [f"{i.number}. **{i.title}**\n   Hook: {i.hook}\n   Angle: {i.angle}" for i in job.ideas]
    (out_dir / "ideas.md").write_text("# Ideas\n\n" + "\n\n".join(lines))


class ZoeAgent(BaseAgent):
    def run_dry(self, job: ContentJob, **kwargs) -> ContentJob:
        job.ideas = _DRY_RUN_IDEAS
        job.stage = "zoe_done"
        _write_ideas_file(job)
        return job

    def run_live(self, job: ContentJob, **kwargs) -> ContentJob:
        trends_str = json.dumps(job.trend_data, ensure_ascii=False)
        system = (
            f"You are Zoe, a content ideation specialist for {job.pm.page_name}. "
            f"Brand tone: {job.pm.brand.tone}. "
            f"Target audience: {job.pm.brand.target_audience}."
        )
        user = (
            f"Brief: {job.brief}\nPlatforms: {', '.join(job.platforms)}\n"
            f"Trends: {trends_str}\n\n"
            "Generate 5-7 content ideas. Return a JSON array of objects with keys: "
            "number (int), title (str), hook (str, max 10 words), angle (str). JSON only."
        )
        raw = self._call_claude(system, user, max_tokens=1024)
        job.ideas = [Idea(**i) for i in json.loads(raw)]
        job.stage = "zoe_done"
        _write_ideas_file(job)
        return job
```

- [ ] **Step 4: Run test — verify it passes**

```bash
pytest tests/test_zoe.py -v
```

Expected: 2 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add agents/zoe.py tests/test_zoe.py
git commit -m "feat: Zoe idea generator agent"
```

---

## Task 9: Bella — Script Writer

**Files:**
- Create: `agents/bella.py`
- Create: `tests/test_bella.py`

- [ ] **Step 1: Write the failing test**

`tests/test_bella.py`:
```python
from agents.bella import BellaAgent
from tests.test_mia import make_config, make_job
from models.content_job import Idea, Script


def make_job_with_idea(dry_run=True):
    job = make_job(dry_run=dry_run)
    job.selected_idea = Idea(number=1, title="Lip Hack", hook="pov your lips last all day", angle="Tutorial")
    return job


def test_bella_dry_run_returns_script():
    agent = BellaAgent(make_config())
    job = agent.run(make_job_with_idea(dry_run=True))
    assert isinstance(job.script, Script)
    assert job.script.hook != ""
    assert job.script.cta != ""
    assert job.stage == "bella_done"


def test_bella_live_calls_claude(mocker):
    script_json = '{"hook":"wait—","body":"step 1: do this","cta":"save this","duration_seconds":30}'
    mocker.patch.object(BellaAgent, "_call_claude", return_value=script_json)
    agent = BellaAgent(make_config())
    job = agent.run(make_job_with_idea(dry_run=False))
    assert job.script.hook == "wait—"
    assert job.script.duration_seconds == 30
```

- [ ] **Step 2: Run test — verify it fails**

```bash
pytest tests/test_bella.py -v
```

- [ ] **Step 3: Create `agents/bella.py`**

```python
from __future__ import annotations
import json
from agents.base_agent import BaseAgent
from models.content_job import ContentJob, Script

_DRY_RUN_SCRIPT = Script(
    hook="wait— you've been doing your lips WRONG this whole time",
    body="step 1: exfoliate. step 2: liner ALL the way around. "
         "step 3: the trick nobody tells you— blot with tissue, dust translucent powder, reapply. "
         "your lips will literally last 8 hours.",
    cta="save this for your next glam sesh bestie",
    duration_seconds=30,
)


def _write_script_file(job: ContentJob) -> None:
    from pathlib import Path
    out_dir = Path("output") / job.pm.page_name / job.id
    out_dir.mkdir(parents=True, exist_ok=True)
    s = job.script
    (out_dir / "script.md").write_text(
        f"# Script\n\n**Hook:** {s.hook}\n\n**Body:** {s.body}\n\n**CTA:** {s.cta}\n\n_Duration: {s.duration_seconds}s_"
    )


class BellaAgent(BaseAgent):
    def run_dry(self, job: ContentJob, **kwargs) -> ContentJob:
        job.script = _DRY_RUN_SCRIPT
        job.stage = "bella_done"
        _write_script_file(job)
        return job

    def run_live(self, job: ContentJob, **kwargs) -> ContentJob:
        idea = job.selected_idea
        system = (
            f"You are Bella, a script writer for {job.pm.page_name}. "
            f"Script style: {job.pm.brand.script_style}. "
            f"Tone: {job.pm.brand.tone}. "
            f"Audience: {job.pm.brand.target_audience}. "
            "Write Reels scripts with Hook → Body → CTA structure."
        )
        user = (
            f"Brief: {job.brief}\nIdea: {idea.title}\nHook line: {idea.hook}\nAngle: {idea.angle}\n"
            f"Platforms: {', '.join(job.platforms)}\n\n"
            "Write a 15-60 second Reels script. Return JSON with keys: "
            "hook (str), body (str), cta (str), duration_seconds (int). JSON only."
        )
        raw = self._call_claude(system, user, max_tokens=1024)
        job.script = Script(**json.loads(raw))
        job.stage = "bella_done"
        _write_script_file(job)
        return job
```

- [ ] **Step 4: Run test — verify it passes**

```bash
pytest tests/test_bella.py -v
```

Expected: 2 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add agents/bella.py tests/test_bella.py
git commit -m "feat: Bella script writer agent"
```

---

## Task 10: Lila — Visual Director (Stub)

**Files:**
- Create: `agents/lila.py`
- Create: `tests/test_lila.py`

- [ ] **Step 1: Write the failing test**

`tests/test_lila.py`:
```python
from agents.lila import LilaAgent
from tests.test_bella import make_job_with_idea
from models.content_job import Script

def make_job_with_script(dry_run=True):
    job = make_job_with_idea(dry_run=dry_run)
    job.script = Script(hook="h", body="b", cta="c", duration_seconds=30)
    return job

def test_lila_dry_run_sets_visual_prompt_and_image():
    from tests.test_mia import make_config
    agent = LilaAgent(make_config())
    job = agent.run(make_job_with_script(dry_run=True))
    assert job.visual_prompt is not None
    assert job.image_path is not None
    assert job.stage == "lila_done"

def test_lila_live_calls_claude_for_prompt(mocker):
    from tests.test_mia import make_config
    prompt = "Cinematic shot of gold lipstick, ivory background, soft morning light"
    mocker.patch.object(LilaAgent, "_call_claude", return_value=prompt)
    mocker.patch.object(LilaAgent, "_generate_image", return_value="output/test/image.png")
    agent = LilaAgent(make_config())
    job = agent.run(make_job_with_script(dry_run=False))
    assert job.visual_prompt == prompt
    assert job.image_path == "output/test/image.png"
```

- [ ] **Step 2: Run test — verify it fails**

```bash
pytest tests/test_lila.py -v
```

- [ ] **Step 3: Create `agents/lila.py`**

```python
from __future__ import annotations
from pathlib import Path
from agents.base_agent import BaseAgent
from config import Config
from models.content_job import ContentJob

_DRY_RUN_PROMPT = (
    "Cinematic close-up of a gold-cased lipstick on ivory marble surface, "
    "soft natural morning light, minimalist Quiet Luxury aesthetic, "
    "white and cream tones, high-end editorial style"
)
_DRY_RUN_IMAGE = "assets/placeholder.png"


class LilaAgent(BaseAgent):
    def run_dry(self, job: ContentJob, **kwargs) -> ContentJob:
        job.visual_prompt = _DRY_RUN_PROMPT
        job.image_path = _DRY_RUN_IMAGE
        job.stage = "lila_done"
        self._write_prompt_file(job)
        return job

    def run_live(self, job: ContentJob, **kwargs) -> ContentJob:
        system = (
            f"You are Lila, visual director for {job.pm.page_name}. "
            f"Visual style: {job.pm.brand.visual.style}. "
            f"Color palette: {', '.join(job.pm.brand.visual.colors)}."
        )
        user = (
            f"Script hook: {job.script.hook}\nBrief: {job.brief}\n"
            "Write a single cinematic image generation prompt for this Reel's key visual. "
            "Be specific about lighting, composition, and mood. Plain text only."
        )
        job.visual_prompt = self._call_claude(system, user, max_tokens=256)
        job.image_path = self._generate_image(job)
        job.stage = "lila_done"
        self._write_prompt_file(job)
        return job

    def _write_prompt_file(self, job: ContentJob) -> None:
        from pathlib import Path
        out_dir = Path("output") / job.pm.page_name / job.id
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "visual_prompt.txt").write_text(job.visual_prompt or "")

    def _generate_image(self, job: ContentJob) -> str:
        # Phase 2: wire GPT Image 2 here
        # from openai import OpenAI
        # client = OpenAI(api_key=self.config.openai_api_key)
        # response = client.images.generate(model="gpt-image-1", prompt=job.visual_prompt, size="1024x1792")
        raise NotImplementedError("Image generation wired in Phase 2")
```

- [ ] **Step 4: Run test — verify it passes**

```bash
pytest tests/test_lila.py -v
```

Expected: 2 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add agents/lila.py tests/test_lila.py
git commit -m "feat: Lila visual director (stub, Phase 2 wires image gen)"
```

---

## Task 11: Nora — QA Editor

**Files:**
- Create: `agents/nora.py`
- Create: `tests/test_nora.py`

- [ ] **Step 1: Write the failing test**

`tests/test_nora.py`:
```python
from agents.nora import NoraAgent
from tests.test_lila import make_job_with_script
from tests.test_mia import make_config
from models.content_job import Script

def make_job_for_nora(dry_run=True):
    job = make_job_with_script(dry_run=dry_run)
    job.visual_prompt = "Gold lipstick, ivory background"
    job.image_path = "assets/placeholder.png"
    return job

def test_nora_dry_run_passes():
    agent = NoraAgent(make_config())
    job = agent.run(make_job_for_nora(dry_run=True))
    assert job.qa_result is not None
    assert job.qa_result.passed is True
    assert job.stage == "nora_done"

def test_nora_live_fail_increments_retry(mocker):
    qa_json = '{"passed":false,"script_feedback":"Hook too weak","visual_feedback":null,"send_back_to":"bella"}'
    mocker.patch.object(NoraAgent, "_call_claude", return_value=qa_json)
    agent = NoraAgent(make_config())
    job = make_job_for_nora(dry_run=False)
    job = agent.run(job)
    assert job.qa_result.passed is False
    assert job.qa_result.send_back_to == "bella"
    assert job.nora_retry_count == 1

def test_nora_live_pass(mocker):
    qa_json = '{"passed":true,"script_feedback":null,"visual_feedback":null,"send_back_to":null}'
    mocker.patch.object(NoraAgent, "_call_claude", return_value=qa_json)
    agent = NoraAgent(make_config())
    job = agent.run(make_job_for_nora(dry_run=False))
    assert job.qa_result.passed is True
    assert job.nora_retry_count == 0
```

- [ ] **Step 2: Run test — verify it fails**

```bash
pytest tests/test_nora.py -v
```

- [ ] **Step 3: Create `agents/nora.py`**

```python
from __future__ import annotations
import json
from agents.base_agent import BaseAgent
from models.content_job import ContentJob, QAResult


class NoraAgent(BaseAgent):
    def run_dry(self, job: ContentJob, **kwargs) -> ContentJob:
        job.qa_result = QAResult(passed=True)
        job.stage = "nora_done"
        return job

    def run_live(self, job: ContentJob, **kwargs) -> ContentJob:
        system = (
            f"You are Nora, QA editor for {job.pm.page_name}. "
            f"Brand tone: {job.pm.brand.tone}. "
            f"Audience: {job.pm.brand.target_audience}. "
            "Be strict. Reject weak hooks, off-brand visuals, and anything that feels generic."
        )
        user = (
            f"Script hook: {job.script.hook}\n"
            f"Script body: {job.script.body}\n"
            f"CTA: {job.script.cta}\n"
            f"Visual prompt: {job.visual_prompt}\n\n"
            "Review this content. Return JSON with keys: passed (bool), "
            "script_feedback (str or null), visual_feedback (str or null), "
            "send_back_to ('bella' | 'lila' | null). JSON only."
        )
        raw = self._call_claude(system, user, max_tokens=512)
        result = QAResult(**json.loads(raw))
        if not result.passed:
            job.nora_retry_count += 1
        job.qa_result = result
        job.stage = "nora_done"
        return job
```

- [ ] **Step 4: Run test — verify it passes**

```bash
pytest tests/test_nora.py -v
```

Expected: 3 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add agents/nora.py tests/test_nora.py
git commit -m "feat: Nora QA editor agent with retry tracking"
```

---

## Task 12: Roxy — Growth Strategist

**Files:**
- Create: `agents/roxy.py`
- Create: `tests/test_roxy.py`

- [ ] **Step 1: Write the failing test**

`tests/test_roxy.py`:
```python
from agents.roxy import RoxyAgent
from tests.test_nora import make_job_for_nora
from tests.test_mia import make_config
from models.content_job import GrowthStrategy, QAResult

def make_job_post_qa(dry_run=True):
    job = make_job_for_nora(dry_run=dry_run)
    job.qa_result = QAResult(passed=True)
    return job

def test_roxy_dry_run_returns_strategy():
    agent = RoxyAgent(make_config())
    job = agent.run(make_job_post_qa(dry_run=True))
    assert isinstance(job.growth_strategy, GrowthStrategy)
    assert len(job.growth_strategy.hashtags) >= 5
    assert job.growth_strategy.caption != ""
    assert job.stage == "roxy_done"

def test_roxy_live_calls_claude(mocker):
    strategy_json = ('{"hashtags":["#LipHack","#GlossyLips"],'
                     '"caption":"your new fave hack","best_post_time_utc":"13:00","best_post_time_thai":"20:00"}')
    mocker.patch.object(RoxyAgent, "_call_claude", return_value=strategy_json)
    agent = RoxyAgent(make_config())
    job = agent.run(make_job_post_qa(dry_run=False))
    assert job.growth_strategy.hashtags == ["#LipHack", "#GlossyLips"]
```

- [ ] **Step 2: Run test — verify it fails**

```bash
pytest tests/test_roxy.py -v
```

- [ ] **Step 3: Create `agents/roxy.py`**

```python
from __future__ import annotations
import json
from agents.base_agent import BaseAgent
from models.content_job import ContentJob, GrowthStrategy

_DRY_RUN_STRATEGY = GrowthStrategy(
    hashtags=["#LongLastingLips","#GlossyLips","#LipHack","#QuietLuxury","#BeautyHacks","#GlowUp"],
    caption="the lip hack you didn't know you needed 💋 save this before your next glam sesh",
    best_post_time_utc="13:00",
    best_post_time_thai="20:00",
)


def _write_growth_file(job: ContentJob) -> None:
    from pathlib import Path
    g = job.growth_strategy
    out_dir = Path("output") / job.pm.page_name / job.id
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "growth.md").write_text(
        f"# Growth Strategy\n\n**Caption:** {g.caption}\n\n"
        f"**Hashtags:** {' '.join(g.hashtags)}\n\n"
        f"**Best post time:** {g.best_post_time_utc} UTC / {g.best_post_time_thai} Thai"
    )


class RoxyAgent(BaseAgent):
    def run_dry(self, job: ContentJob, **kwargs) -> ContentJob:
        job.growth_strategy = _DRY_RUN_STRATEGY
        job.stage = "roxy_done"
        _write_growth_file(job)
        return job

    def run_live(self, job: ContentJob, **kwargs) -> ContentJob:
        system = (
            f"You are Roxy, growth strategist for {job.pm.page_name}. "
            f"Target audience: {job.pm.brand.target_audience}. "
            f"Platforms: {', '.join(job.platforms)}."
        )
        user = (
            f"Brief: {job.brief}\nScript hook: {job.script.hook}\n"
            "Provide 5-10 hashtags, a short caption, and optimal post times for USA audience. "
            "Return JSON with keys: hashtags (list of str), caption (str), "
            "best_post_time_utc (str HH:MM), best_post_time_thai (str HH:MM). JSON only."
        )
        raw = self._call_claude(system, user, max_tokens=512)
        job.growth_strategy = GrowthStrategy(**json.loads(raw))
        job.stage = "roxy_done"
        _write_growth_file(job)
        return job
```

- [ ] **Step 4: Run test — verify it passes**

```bash
pytest tests/test_roxy.py -v
```

Expected: 2 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add agents/roxy.py tests/test_roxy.py
git commit -m "feat: Roxy growth strategist agent"
```

---

## Task 13: Emma — Community Manager

**Files:**
- Create: `agents/emma.py`
- Create: `tests/test_emma.py`

- [ ] **Step 1: Write the failing test**

`tests/test_emma.py`:
```python
from pathlib import Path
from agents.emma import EmmaAgent
from tests.test_roxy import make_job_post_qa
from tests.test_mia import make_config
from models.content_job import GrowthStrategy

def make_job_for_emma(dry_run=True, tmp_path=None):
    job = make_job_post_qa(dry_run=dry_run)
    job.growth_strategy = GrowthStrategy(
        hashtags=["#LipHack"], caption="test", best_post_time_utc="13:00", best_post_time_thai="20:00"
    )
    return job

def test_emma_dry_run_writes_faq_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "output" / "Slay Hack Agency").mkdir(parents=True)
    job = make_job_for_emma(dry_run=True)
    agent = EmmaAgent(make_config())
    job = agent.run(job)
    assert job.community_faq_path is not None
    assert Path(job.community_faq_path).exists()
    assert job.stage == "emma_done"
```

- [ ] **Step 2: Run test — verify it fails**

```bash
pytest tests/test_emma.py -v
```

- [ ] **Step 3: Create `agents/emma.py`**

```python
from __future__ import annotations
from pathlib import Path
from agents.base_agent import BaseAgent
from models.content_job import ContentJob

_DRY_RUN_FAQ = """# FAQ — Community Responses

**Q: What product are you using?**
A: it's actually a technique, not just a product! the tissue blot + powder method works with literally any lipstick ✨

**Q: Does this work with glossy formulas?**
A: yes bestie! the key is the powder step — it sets the gloss so it won't budge

**Q: How long does it actually last?**
A: tested it for 8 hours straight — eating, drinking, everything. it held 💋
"""


class EmmaAgent(BaseAgent):
    def run_dry(self, job: ContentJob, **kwargs) -> ContentJob:
        faq_path = self._write_faq(job, _DRY_RUN_FAQ)
        job.community_faq_path = str(faq_path)
        job.stage = "emma_done"
        return job

    def run_live(self, job: ContentJob, **kwargs) -> ContentJob:
        system = (
            f"You are Emma, community manager for {job.pm.page_name}. "
            "Write warm, friendly, conversational responses. "
            f"Tone: {job.pm.brand.tone}."
        )
        user = (
            f"Brief: {job.brief}\nScript: {job.script.hook} — {job.script.body}\n\n"
            "Write a FAQ markdown with 3-5 likely comments and ideal responses. "
            "Use the brand's tone. Markdown only."
        )
        faq_content = self._call_claude(system, user, max_tokens=1024)
        faq_path = self._write_faq(job, faq_content)
        job.community_faq_path = str(faq_path)
        job.stage = "emma_done"
        return job

    def _write_faq(self, job: ContentJob, content: str) -> Path:
        out_dir = Path("output") / job.pm.page_name / job.id
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / "faq.md"
        path.write_text(content)
        return path
```

- [ ] **Step 4: Run test — verify it passes**

```bash
pytest tests/test_emma.py -v
```

Expected: 1 test PASSED

- [ ] **Step 5: Commit**

```bash
git add agents/emma.py tests/test_emma.py
git commit -m "feat: Emma community manager agent"
```

---

## Task 14: Agent Tool Definitions

**Files:**
- Create: `tools/__init__.py`
- Create: `tools/agent_tools.py`

- [ ] **Step 1: Create `tools/__init__.py`** (empty)

- [ ] **Step 2: Create `tools/agent_tools.py`**

```python
from __future__ import annotations


def get_tool_definitions() -> list[dict]:
    return [
        {
            "name": "run_mia",
            "description": "Research current trends relevant to the brief using Brave Search. Call this first.",
            "input_schema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "name": "run_zoe",
            "description": "Generate 5-7 content ideas based on Mia's trend research.",
            "input_schema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "name": "run_bella",
            "description": "Write the Reels script for the selected idea.",
            "input_schema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "name": "run_lila",
            "description": "Generate the visual prompt and create the key image for the Reel.",
            "input_schema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "name": "run_nora",
            "description": "QA review the script and visual. Returns pass/fail with optional feedback.",
            "input_schema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "name": "run_roxy",
            "description": "Generate hashtags, caption, and optimal posting time.",
            "input_schema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "name": "run_emma",
            "description": "Prepare FAQ markdown with pre-written community responses.",
            "input_schema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "name": "request_checkpoint",
            "description": (
                "Pause pipeline and ask the user for input or approval. "
                "Use at: (1) after Zoe to pick idea, (2) after Bella+Lila to review content, "
                "(3) after Nora QA, (4) before publishing."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "stage": {"type": "string", "description": "Checkpoint name, e.g. 'idea_selection'"},
                    "summary": {"type": "string", "description": "What to show the user"},
                    "options": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Numbered options to present (optional)",
                    },
                },
                "required": ["stage", "summary"],
            },
        },
    ]
```

- [ ] **Step 3: Commit**

```bash
git add tools/ 
git commit -m "feat: Claude tool definitions for Robin orchestrator"
```

---

## Task 15: Robin — Orchestrator

**Files:**
- Create: `orchestrator.py`
- Create: `tests/test_orchestrator.py`

- [ ] **Step 1: Write the failing test**

`tests/test_orchestrator.py`:
```python
import json
from unittest.mock import MagicMock, patch
from orchestrator import Orchestrator
from tests.test_mia import make_config, make_job
from models.content_job import JobStatus


def _make_tool_use_block(name, tool_id="t1", input_data=None):
    block = MagicMock()
    block.type = "tool_use"
    block.name = name
    block.id = tool_id
    block.input = input_data or {}
    return block


def _make_end_turn_response():
    resp = MagicMock()
    resp.stop_reason = "end_turn"
    resp.content = [MagicMock(type="text", text="All done!")]
    return resp


def test_orchestrator_dry_run_completes(mocker, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "output").mkdir()

    # Robin calls agents in sequence then end_turn
    tool_sequence = [
        [_make_tool_use_block("run_mia", "t1")],
        [_make_tool_use_block("run_zoe", "t2")],
        [_make_tool_use_block("request_checkpoint", "t3",
            {"stage": "idea_selection", "summary": "Pick an idea", "options": ["1. Lip Hack"]})],
        [_make_tool_use_block("run_bella", "t4")],
        [_make_tool_use_block("run_lila", "t5")],
        [_make_tool_use_block("request_checkpoint", "t6",
            {"stage": "content_review", "summary": "Review script"})],
        [_make_tool_use_block("run_nora", "t7")],
        [_make_tool_use_block("request_checkpoint", "t8",
            {"stage": "qa_review", "summary": "QA passed"})],
        [_make_tool_use_block("run_roxy", "t9")],
        [_make_tool_use_block("run_emma", "t10")],
        [_make_tool_use_block("request_checkpoint", "t11",
            {"stage": "final_approval", "summary": "Ready to publish?"})],
    ]

    call_count = [0]
    def mock_create(**kwargs):
        i = call_count[0]
        call_count[0] += 1
        if i < len(tool_sequence):
            resp = MagicMock()
            resp.stop_reason = "tool_use"
            resp.content = tool_sequence[i]
            return resp
        return _make_end_turn_response()

    mocker.patch("orchestrator.anthropic.Anthropic").return_value.messages.create.side_effect = mock_create
    mocker.patch("builtins.input", return_value="1")

    orch = Orchestrator(make_config())
    job = make_job(dry_run=True)
    result = orch.run(job)

    assert result.status == JobStatus.COMPLETED
    assert result.trend_data is not None
    assert result.ideas is not None
    assert result.script is not None
    assert len(result.checkpoint_log) == 4
```

- [ ] **Step 2: Run test — verify it fails**

```bash
pytest tests/test_orchestrator.py -v
```

- [ ] **Step 3: Create `orchestrator.py`**

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
from job_store import save_job
from models.content_job import ContentJob, JobStatus
from tools.agent_tools import get_tool_definitions

_ROBIN_SYSTEM = """You are Robin, Creative Director and team coordinator for {page_name}.

{pm_persona}

Your job: receive a content brief and coordinate the team to produce a complete, publish-ready Reel.

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
            page_name=job.pm.page_name,
            pm_persona=job.pm.persona,
        )
        messages: list[dict] = [
            {"role": "user", "content": f"Brief: {job.brief}\nPlatforms: {', '.join(job.platforms)}"}
        ]

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

- [ ] **Step 4: Run test — verify it passes**

```bash
pytest tests/test_orchestrator.py -v
```

Expected: 1 test PASSED

- [ ] **Step 5: Commit**

```bash
git add orchestrator.py tests/test_orchestrator.py
git commit -m "feat: Robin orchestrator with Claude tool-use loop"
```

---

## Task 16: CLI Entry Point

**Files:**
- Create: `main.py`

- [ ] **Step 1: Create `main.py`**

```python
from __future__ import annotations
import argparse
import sys
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
    parser.add_argument("--brief", help="Content brief (required with --project)")
    parser.add_argument("--platforms", default="instagram,facebook",
                        help="Comma-separated platforms (default: instagram,facebook)")
    parser.add_argument("--dry-run", action="store_true", help="Run with mock data, no API calls")
    args = parser.parse_args()

    try:
        config = Config.from_env()
    except MissingAPIKeyError as e:
        print(f"Error: {e}\nCopy .env.example to .env and fill in your API keys.")
        sys.exit(1)

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

- [ ] **Step 2: Smoke test the CLI help**

```bash
python main.py --help
```

Expected: prints usage with `--project`, `--resume`, `--brief`, `--dry-run` flags

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "feat: CLI entry point with --project, --resume, --dry-run"
```

---

## Task 17: End-to-End Dry-Run Integration Test

**Files:**
- Create: `tests/test_integration.py`

- [ ] **Step 1: Write the integration test**

`tests/test_integration.py`:
```python
from unittest.mock import MagicMock, patch
from pathlib import Path
from orchestrator import Orchestrator
from project_loader import load_project
from models.content_job import ContentJob, JobStatus
from config import Config
import os


def _tool_block(name, tool_id, input_data=None):
    b = MagicMock()
    b.type = "tool_use"
    b.name = name
    b.id = tool_id
    b.input = input_data or {}
    return b


def test_full_dry_run_pipeline(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "output").mkdir()

    # Copy projects/ into tmp_path so project_loader can find it
    import shutil
    shutil.copytree(Path(__file__).parent.parent / "projects", tmp_path / "projects")

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "brave")
    monkeypatch.setenv("OPENAI_API_KEY", "oai")

    sequence = [
        [_tool_block("run_mia", "t1")],
        [_tool_block("run_zoe", "t2")],
        [_tool_block("request_checkpoint", "t3", {"stage": "idea_selection",
            "summary": "Ideas:\n1. Lip Hack\n2. Morning Routine", "options": ["1", "2", "3", "4", "5"]})],
        [_tool_block("run_bella", "t4")],
        [_tool_block("run_lila", "t5")],
        [_tool_block("request_checkpoint", "t6", {"stage": "content_review",
            "summary": "Script and visual ready for review."})],
        [_tool_block("run_nora", "t7")],
        [_tool_block("request_checkpoint", "t8", {"stage": "qa_review",
            "summary": "Nora says: PASSED ✓"})],
        [_tool_block("run_roxy", "t9")],
        [_tool_block("run_emma", "t10")],
        [_tool_block("request_checkpoint", "t11", {"stage": "final_approval",
            "summary": "Everything ready. Post to Instagram + Facebook?"})],
    ]

    call_count = [0]
    def mock_create(**kwargs):
        i = call_count[0]
        call_count[0] += 1
        if i < len(sequence):
            resp = MagicMock()
            resp.stop_reason = "tool_use"
            resp.content = sequence[i]
            return resp
        resp = MagicMock()
        resp.stop_reason = "end_turn"
        resp.content = [MagicMock(type="text", text="Job complete!")]
        return resp

    with patch("orchestrator.anthropic.Anthropic") as mock_anthropic, \
         patch("builtins.input", return_value="1"):
        mock_anthropic.return_value.messages.create.side_effect = mock_create

        config = Config(anthropic_api_key="test", brave_search_api_key="brave", openai_api_key="oai")
        pm = load_project("slay_hack")
        job = ContentJob(
            project="slay_hack", pm=pm,
            brief="lipstick that lasts all day",
            platforms=["instagram", "facebook"],
            dry_run=True,
        )
        orch = Orchestrator(config)
        result = orch.run(job)

    assert result.status == JobStatus.COMPLETED
    assert result.trend_data is not None
    assert result.ideas is not None and len(result.ideas) >= 3
    assert result.script is not None
    assert result.qa_result is not None and result.qa_result.passed
    assert result.growth_strategy is not None
    assert result.community_faq_path is not None
    assert len(result.checkpoint_log) == 4

    job_file = tmp_path / "output" / "Slay Hack Agency" / result.id / "job.json"
    assert job_file.exists()

    faq_file = Path(result.community_faq_path)
    assert faq_file.exists()
```

- [ ] **Step 2: Run test — verify it passes**

```bash
pytest tests/test_integration.py -v
```

Expected: 1 test PASSED

- [ ] **Step 3: Run full test suite**

```bash
pytest -v
```

Expected: all tests PASSED, 0 failures

- [ ] **Step 4: Type check**

```bash
mypy . --ignore-missing-imports
```

Expected: no errors

- [ ] **Step 5: Lint**

```bash
ruff check .
```

Expected: no issues

- [ ] **Step 6: Final commit**

```bash
git add tests/test_integration.py
git commit -m "test: end-to-end dry-run integration test"
```

---

## Phase 1 Complete ✓

At this point:
- `python main.py --project slay_hack --brief "your brief" --dry-run` runs the full 8-agent pipeline end-to-end
- All 4 checkpoints pause and accept user input
- Job state persists to `output/Slay Hack Agency/<job_id>/job.json` after every step
- `python main.py --resume <job_id>` picks up where it left off
- All agents tested with mocks; full dry-run integration test passes

**Phase 2 next steps** (separate plan):
- Wire GPT Image 2 in `agents/lila.py` `_generate_image()`
- Wire Brave Search live search in `agents/mia.py` `run_live()`
- Add publish agent for Meta Graph API
