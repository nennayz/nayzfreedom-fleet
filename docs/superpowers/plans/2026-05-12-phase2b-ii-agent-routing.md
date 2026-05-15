# Phase 2B-ii: Agent Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire content-type routing through the full pipeline — Bella branches by type, Lila skips articles, Nora builds dynamic QA prompts, Roxy loads editorial guidance, Robin routes correctly at idea selection.

**Architecture:** All Phase 2B-i models are live. This plan migrates agents from `job.script` → `job.bella_output`, adds content-type branching, removes the deprecated `script` field from `ContentJob`, and updates all test fixtures. The orchestrator is updated to set `job.content_type` at the idea_selection checkpoint.

**Tech Stack:** Python 3.9+, Pydantic v2, Anthropic SDK, pytest, pytest-mock

---

## File Map

| File | Change |
|---|---|
| `orchestrator.py` | Update `_dispatch` to set `job.content_type` at idea_selection; update Robin system prompt for content_type routing |
| `agents/bella.py` | Branch on `content_type`; write to `job.bella_output`; update `_write_bella_output_file` |
| `models/content_job.py` | Remove `script: Optional[Script]` field |
| `agents/lila.py` | Skip for articles; differentiate prompt by content_type; read `bella_output` |
| `agents/nora.py` | Build QA prompt dynamically by content_type; skip visual QA for articles; read `bella_output` |
| `agents/roxy.py` | Load `platform_specs.yaml` in live path; populate `editorial_guidance`; update `_write_growth_file` |
| `tests/test_bella.py` | 4 content-type variants; assert `bella_output` not `script` |
| `tests/test_lila.py` | Update fixture to use `bella_output`; add article-skip test |
| `tests/test_nora.py` | Update fixture to use `bella_output`; add content-type QA prompt tests |
| `tests/test_roxy.py` | Assert `editorial_guidance` populated in live test |
| `tests/test_orchestrator.py` | Assert `bella_output` not `script`; assert `content_type` set post-checkpoint |

---

## Task 1: Orchestrator — idea_selection dispatch + Robin system prompt

**Files:**
- Modify: `orchestrator.py`
- Test: `tests/test_orchestrator.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_orchestrator.py`:

```python
from models.content_job import ContentType, Idea

def test_orchestrator_sets_content_type_at_idea_selection(mocker, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "output").mkdir()

    # Pre-populate ideas so the dispatcher can resolve the selection
    from tests.test_mia import make_config, make_job
    from models.content_job import ContentType, Idea

    orch = Orchestrator(make_config())
    job = make_job(dry_run=True)
    job.ideas = [
        Idea(number=1, title="Lip Hack", hook="h", angle="Tutorial", content_type=ContentType.VIDEO),
        Idea(number=2, title="Morning Routine", hook="h2", angle="Lifestyle", content_type=ContentType.ARTICLE),
    ]

    # Simulate idea_selection checkpoint returning "2"
    mock_checkpoint = MagicMock()
    mock_checkpoint.decision = "2"
    mocker.patch("orchestrator.pause", return_value=mock_checkpoint)

    orch._dispatch(
        "request_checkpoint",
        {"stage": "idea_selection", "summary": "pick one", "options": ["1", "2"]},
        job,
    )

    assert job.content_type == ContentType.ARTICLE
    assert job.selected_idea.number == 2
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/nennayz/Documents/NayzFreedom/code/slayhack && \
  .venv/bin/pytest tests/test_orchestrator.py::test_orchestrator_sets_content_type_at_idea_selection -v
```

Expected: FAIL — `_dispatch` does not set `content_type` yet.

- [ ] **Step 3: Update `_dispatch` in orchestrator.py**

Replace the `request_checkpoint` branch in `_dispatch`:

```python
    def _dispatch(self, tool_name: str, tool_input: dict, job: ContentJob) -> dict:
        if tool_name == "request_checkpoint":
            result = pause(
                stage=tool_input["stage"],
                summary=tool_input["summary"],
                options=tool_input.get("options", []),
                job=job,
            )
            if tool_input["stage"] == "idea_selection" and job.ideas:
                decision_num = int(result.decision)
                job.selected_idea = next(
                    i for i in job.ideas if i.number == decision_num
                )
                job.content_type = job.selected_idea.content_type
            return {"decision": result.decision}
```

- [ ] **Step 4: Update Robin system prompt**

Replace `_ROBIN_SYSTEM` in `orchestrator.py` with this updated version that adds content_type routing after step 4:

```python
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

Never skip a checkpoint. After final_approval, declare the job complete.
"""
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd /Users/nennayz/Documents/NayzFreedom/code/slayhack && \
  .venv/bin/pytest tests/test_orchestrator.py -v
```

Expected: all orchestrator tests pass including the new one.

- [ ] **Step 6: Run full test suite**

```bash
cd /Users/nennayz/Documents/NayzFreedom/code/slayhack && .venv/bin/pytest -v
```

Expected: 59 passed.

- [ ] **Step 7: Commit**

```bash
git add orchestrator.py tests/test_orchestrator.py
git commit -m "feat(orchestrator): set job.content_type at idea_selection; update Robin routing prompt"
```

---

## Task 2: Bella — content_type branching + script field removal

**Files:**
- Modify: `agents/bella.py`
- Modify: `models/content_job.py` (remove `script` field)
- Modify: `tests/test_bella.py`
- Modify: `tests/test_lila.py` (fixture cascade)
- Modify: `tests/test_nora.py` (fixture cascade)
- Modify: `tests/test_orchestrator.py` (assert cascade)

- [ ] **Step 1: Write the failing tests**

Replace `tests/test_bella.py` entirely:

```python
import pytest
from agents.bella import BellaAgent
from agents.base_agent import TEAM_IDENTITY
from tests.test_mia import make_config, make_job
from models.content_job import (
    Idea, Script, Article, ImageCaption, InfographicContent,
    ContentType, BellaOutput,
)


def make_job_with_idea(dry_run=True, content_type=ContentType.VIDEO):
    job = make_job(dry_run=dry_run)
    job.content_type = content_type
    job.selected_idea = Idea(
        number=1, title="Lip Hack", hook="pov your lips last all day",
        angle="Tutorial", content_type=content_type,
    )
    return job


def test_bella_dry_run_video_returns_script():
    agent = BellaAgent(make_config())
    job = agent.run(make_job_with_idea(dry_run=True, content_type=ContentType.VIDEO))
    assert isinstance(job.bella_output, Script)
    assert job.bella_output.hook != ""
    assert job.bella_output.cta != ""
    assert job.stage == "bella_done"


def test_bella_dry_run_article_returns_article():
    agent = BellaAgent(make_config())
    job = agent.run(make_job_with_idea(dry_run=True, content_type=ContentType.ARTICLE))
    assert isinstance(job.bella_output, Article)
    assert job.bella_output.heading != ""
    assert job.bella_output.cta != ""
    assert job.stage == "bella_done"


def test_bella_dry_run_image_returns_caption():
    agent = BellaAgent(make_config())
    job = agent.run(make_job_with_idea(dry_run=True, content_type=ContentType.IMAGE))
    assert isinstance(job.bella_output, ImageCaption)
    assert job.bella_output.caption != ""
    assert job.bella_output.alt_text != ""
    assert job.stage == "bella_done"


def test_bella_dry_run_infographic_returns_infographic():
    agent = BellaAgent(make_config())
    job = agent.run(make_job_with_idea(dry_run=True, content_type=ContentType.INFOGRAPHIC))
    assert isinstance(job.bella_output, InfographicContent)
    assert job.bella_output.title != ""
    assert len(job.bella_output.points) > 0
    assert job.stage == "bella_done"


def test_bella_live_video_calls_claude(mocker):
    script_json = '{"type":"script","hook":"wait—","body":"step 1","cta":"save this","duration_seconds":30}'
    mocker.patch.object(BellaAgent, "_call_claude", return_value=script_json)
    agent = BellaAgent(make_config())
    job = agent.run(make_job_with_idea(dry_run=False, content_type=ContentType.VIDEO))
    assert isinstance(job.bella_output, Script)
    assert job.bella_output.hook == "wait—"
    assert job.bella_output.duration_seconds == 30


def test_bella_live_article_calls_claude(mocker):
    article_json = '{"type":"article","heading":"The Look","body":"Step 1...","cta":"Shop now"}'
    mocker.patch.object(BellaAgent, "_call_claude", return_value=article_json)
    agent = BellaAgent(make_config())
    job = agent.run(make_job_with_idea(dry_run=False, content_type=ContentType.ARTICLE))
    assert isinstance(job.bella_output, Article)
    assert job.bella_output.heading == "The Look"


def test_bella_system_prompt_includes_team_identity(mocker):
    captured = {}
    def fake_call(system, user, **kwargs):
        captured["system"] = system
        return '{"type":"script","hook":"h","body":"b","cta":"c","duration_seconds":30}'
    agent = BellaAgent(make_config())
    mocker.patch.object(agent, "_call_claude", side_effect=fake_call)
    job = make_job_with_idea(dry_run=False, content_type=ContentType.VIDEO)
    agent.run(job)
    assert captured["system"].startswith(TEAM_IDENTITY)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/nennayz/Documents/NayzFreedom/code/slayhack && .venv/bin/pytest tests/test_bella.py -v
```

Expected: failures — Bella still writes `job.script` and `bella_output` is never set.

- [ ] **Step 3: Rewrite agents/bella.py**

```python
from __future__ import annotations
import json
from pathlib import Path
from agents.base_agent import BaseAgent, TEAM_IDENTITY
from models.content_job import (
    ContentJob, ContentType,
    Script, Article, ImageCaption, InfographicContent, BellaOutput,
)

_DRY_RUN_OUTPUTS: dict[ContentType, BellaOutput] = {
    ContentType.VIDEO: Script(
        hook="wait— you've been doing your lips WRONG this whole time",
        body="step 1: exfoliate. step 2: liner ALL the way around. "
             "step 3: the trick nobody tells you— blot with tissue, dust translucent powder, reapply. "
             "your lips will literally last 8 hours.",
        cta="save this for your next glam sesh bestie",
        duration_seconds=30,
    ),
    ContentType.ARTICLE: Article(
        heading="The Quiet Luxury Lip Trick Nobody's Talking About",
        body="You've been applying lip liner wrong. Here's the three-step method that makes your lips last all day without touch-ups.",
        cta="Bookmark this for your next glam session.",
    ),
    ContentType.IMAGE: ImageCaption(
        caption="the lip hack you didn't know you needed 💋",
        alt_text="Close-up of gold-cased lipstick on ivory marble, soft morning light",
    ),
    ContentType.INFOGRAPHIC: InfographicContent(
        title="3-Step Kiss-Proof Lips",
        points=[
            "Step 1: Exfoliate — use a damp cloth or sugar scrub",
            "Step 2: Line all the way around, slightly outside your natural lip line",
            "Step 3: Blot → translucent powder → reapply. Done.",
        ],
        cta="Save this for your next glam sesh",
    ),
}

_PROMPTS = {
    ContentType.VIDEO: (
        "Write a 15-60 second Reels script. Return JSON with keys: "
        "type (must be \"script\"), hook (str), body (str), cta (str), duration_seconds (int). JSON only."
    ),
    ContentType.ARTICLE: (
        "Write a short article with a compelling heading, body paragraphs, and a CTA. "
        "Return JSON with keys: type (must be \"article\"), heading (str), body (str), cta (str). JSON only."
    ),
    ContentType.IMAGE: (
        "Write a social media image caption and alt text. "
        "Return JSON with keys: type (must be \"image\"), caption (str, max 150 chars), alt_text (str). JSON only."
    ),
    ContentType.INFOGRAPHIC: (
        "Write infographic content: a title, a list of data points or tips, and a CTA. "
        "Return JSON with keys: type (must be \"infographic\"), title (str), points (list of str), cta (str). JSON only."
    ),
}


def _write_bella_output_file(job: ContentJob) -> None:
    out_dir = Path("output") / job.pm.page_name / job.id
    out_dir.mkdir(parents=True, exist_ok=True)
    b = job.bella_output
    if isinstance(b, Script):
        content = f"# Script\n\n**Hook:** {b.hook}\n\n**Body:** {b.body}\n\n**CTA:** {b.cta}\n\n_Duration: {b.duration_seconds}s_"
    elif isinstance(b, Article):
        content = f"# Article\n\n## {b.heading}\n\n{b.body}\n\n**CTA:** {b.cta}"
    elif isinstance(b, ImageCaption):
        content = f"# Image Caption\n\n**Caption:** {b.caption}\n\n**Alt text:** {b.alt_text}"
    elif isinstance(b, InfographicContent):
        points = "\n".join(f"- {p}" for p in b.points)
        content = f"# Infographic\n\n## {b.title}\n\n{points}\n\n**CTA:** {b.cta}"
    else:
        content = str(b)
    (out_dir / "bella_output.md").write_text(content)


class BellaAgent(BaseAgent):
    def run_dry(self, job: ContentJob, **kwargs) -> ContentJob:
        job.bella_output = _DRY_RUN_OUTPUTS[job.content_type]
        job.stage = "bella_done"
        _write_bella_output_file(job)
        return job

    def run_live(self, job: ContentJob, **kwargs) -> ContentJob:
        from pydantic import TypeAdapter
        from models.content_job import BellaOutput as _BellaOutput
        idea = job.selected_idea
        system = (
            TEAM_IDENTITY +
            f"You are Bella, a content writer for {job.pm.page_name}. "
            f"Writing style: {job.pm.brand.script_style}. "
            f"Tone: {job.pm.brand.tone}. "
            f"Audience: {job.pm.brand.target_audience}."
        )
        user = (
            f"Brief: {job.brief}\nIdea: {idea.title}\nHook line: {idea.hook}\nAngle: {idea.angle}\n"
            f"Content type: {job.content_type.value}\nPlatforms: {', '.join(job.platforms)}\n\n"
            + _PROMPTS[job.content_type]
        )
        raw = self._call_claude(system, user, max_tokens=1024)
        ta = TypeAdapter(_BellaOutput)
        job.bella_output = ta.validate_python(self._parse_json(raw))
        job.stage = "bella_done"
        _write_bella_output_file(job)
        return job
```

- [ ] **Step 4: Remove `script` field from models/content_job.py**

In `models/content_job.py`, remove this line from `ContentJob`:

```python
    script: Optional[Script] = None   # kept for 2B-i, removed in 2B-ii
```

- [ ] **Step 5: Update fixture cascade in test_lila.py**

`make_job_with_script` in `test_lila.py` currently sets `job.script`. Replace with `bella_output`:

```python
from agents.lila import LilaAgent
from tests.test_bella import make_job_with_idea
from tests.test_mia import make_config
from models.content_job import Script, ContentType

def make_job_with_bella_output(dry_run=True):
    job = make_job_with_idea(dry_run=dry_run, content_type=ContentType.VIDEO)
    job.bella_output = Script(hook="h", body="b", cta="c", duration_seconds=30)
    return job

def test_lila_dry_run_sets_visual_prompt_and_image():
    agent = LilaAgent(make_config())
    job = agent.run(make_job_with_bella_output(dry_run=True))
    assert job.visual_prompt is not None
    assert job.image_path is not None
    assert job.stage == "lila_done"

def test_lila_live_calls_claude_for_prompt(mocker):
    prompt = "Cinematic shot of gold lipstick, ivory background, soft morning light"
    mocker.patch.object(LilaAgent, "_call_claude", return_value=prompt)
    mocker.patch.object(LilaAgent, "_generate_image", return_value="output/test/image.png")
    agent = LilaAgent(make_config())
    job = agent.run(make_job_with_bella_output(dry_run=False))
    assert job.visual_prompt == prompt
    assert job.image_path == "output/test/image.png"
```

- [ ] **Step 6: Update fixture cascade in test_nora.py**

`make_job_for_nora` uses `make_job_with_script`. Replace with the new fixture:

```python
from agents.nora import NoraAgent
from tests.test_lila import make_job_with_bella_output
from tests.test_mia import make_config
from models.content_job import QAResult

def make_job_for_nora(dry_run=True):
    job = make_job_with_bella_output(dry_run=dry_run)
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

- [ ] **Step 7: Update test_orchestrator.py assertion**

In `test_orchestrator_dry_run_completes`, change:

```python
    assert result.script is not None
```

to:

```python
    assert result.bella_output is not None
```

- [ ] **Step 8: Run tests to verify they pass**

```bash
cd /Users/nennayz/Documents/NayzFreedom/code/slayhack && .venv/bin/pytest tests/test_bella.py tests/test_lila.py tests/test_nora.py tests/test_orchestrator.py -v
```

Expected: all pass.

- [ ] **Step 9: Run full test suite**

```bash
cd /Users/nennayz/Documents/NayzFreedom/code/slayhack && .venv/bin/pytest -v
```

Expected: all tests pass (net +5 new Bella tests).

- [ ] **Step 10: Commit**

```bash
git add agents/bella.py models/content_job.py \
        tests/test_bella.py tests/test_lila.py \
        tests/test_nora.py tests/test_orchestrator.py
git commit -m "feat(bella): branch on content_type, write to bella_output; remove script field"
```

---

## Task 3: Lila — skip articles, differentiate prompt by content_type

**Files:**
- Modify: `agents/lila.py`
- Modify: `tests/test_lila.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_lila.py`:

```python
from models.content_job import ContentType, Article, ImageCaption, InfographicContent

def make_article_job(dry_run=True):
    from tests.test_bella import make_job_with_idea
    job = make_job_with_idea(dry_run=dry_run, content_type=ContentType.ARTICLE)
    job.bella_output = Article(heading="The Look", body="Step 1...", cta="Shop now")
    return job

def make_image_job(dry_run=True):
    from tests.test_bella import make_job_with_idea
    job = make_job_with_idea(dry_run=dry_run, content_type=ContentType.IMAGE)
    job.bella_output = ImageCaption(caption="Soft glam", alt_text="Woman in gold tones")
    return job

def test_lila_skips_for_article():
    agent = LilaAgent(make_config())
    job = agent.run(make_article_job(dry_run=True))
    assert job.visual_prompt is None
    assert job.image_path is None
    assert job.stage == "lila_done"

def test_lila_dry_run_image_generates_prompt():
    agent = LilaAgent(make_config())
    job = agent.run(make_image_job(dry_run=True))
    assert job.visual_prompt is not None
    assert job.image_path is not None
    assert job.stage == "lila_done"

def test_lila_live_article_skips_claude(mocker):
    mock_call = mocker.patch.object(LilaAgent, "_call_claude")
    agent = LilaAgent(make_config())
    agent.run(make_article_job(dry_run=False))
    mock_call.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/nennayz/Documents/NayzFreedom/code/slayhack && \
  .venv/bin/pytest tests/test_lila.py::test_lila_skips_for_article \
                   tests/test_lila.py::test_lila_dry_run_image_generates_prompt \
                   tests/test_lila.py::test_lila_live_article_skips_claude -v
```

Expected: failures — Lila doesn't check `content_type` yet.

- [ ] **Step 3: Rewrite agents/lila.py**

```python
from __future__ import annotations
from pathlib import Path
from agents.base_agent import BaseAgent, TEAM_IDENTITY
from models.content_job import ContentJob, ContentType, Script, ImageCaption, InfographicContent

_DRY_RUN_PROMPTS = {
    ContentType.VIDEO: (
        "Cinematic close-up of a gold-cased lipstick on ivory marble surface, "
        "soft natural morning light, minimalist Quiet Luxury aesthetic, "
        "white and cream tones, high-end editorial style"
    ),
    ContentType.IMAGE: (
        "Flat-lay of luxury beauty essentials on cream linen, gold accents, "
        "soft diffused light, editorial minimalist style"
    ),
    ContentType.INFOGRAPHIC: (
        "Clean white infographic layout with gold typography, step-by-step icons, "
        "minimalist beauty aesthetic, sans-serif font"
    ),
}
_DRY_RUN_IMAGE = "assets/placeholder.png"


class LilaAgent(BaseAgent):
    def run_dry(self, job: ContentJob, **kwargs) -> ContentJob:
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

    def run_live(self, job: ContentJob, **kwargs) -> ContentJob:
        if job.content_type == ContentType.ARTICLE:
            job.stage = "lila_done"
            return job

        system = (
            TEAM_IDENTITY +
            f"You are Lila, visual director for {job.pm.page_name}. "
            f"Visual style: {job.pm.brand.visual.style}. "
            f"Color palette: {', '.join(job.pm.brand.visual.colors)}."
        )

        bella = job.bella_output
        if job.content_type == ContentType.VIDEO:
            hook_text = bella.hook if isinstance(bella, Script) else str(bella)
            user = (
                f"Script hook: {hook_text}\nBrief: {job.brief}\n"
                "Write a single cinematic image generation prompt for this Reel's key visual. "
                "Be specific about lighting, composition, and mood. Plain text only."
            )
            job.visual_prompt = self._call_claude(system, user, max_tokens=256)
            # Video generation wired in Phase 3 — stub
            job.image_path = None
        elif job.content_type == ContentType.IMAGE:
            caption_text = bella.caption if isinstance(bella, ImageCaption) else str(bella)
            user = (
                f"Caption: {caption_text}\nBrief: {job.brief}\n"
                "Write a single cinematic image generation prompt for this social media image. "
                "Be specific about lighting, composition, and mood. Plain text only."
            )
            job.visual_prompt = self._call_claude(system, user, max_tokens=256)
            job.image_path = self._generate_image(job)
        elif job.content_type == ContentType.INFOGRAPHIC:
            points_text = "; ".join(bella.points) if isinstance(bella, InfographicContent) else str(bella)
            user = (
                f"Infographic points: {points_text}\nBrief: {job.brief}\n"
                "Write a single image generation prompt for this infographic's visual layout. "
                "Describe the layout, typography style, and color palette. Plain text only."
            )
            job.visual_prompt = self._call_claude(system, user, max_tokens=256)
            job.image_path = self._generate_image(job)

        job.stage = "lila_done"
        self._write_prompt_file(job)
        return job

    def _write_prompt_file(self, job: ContentJob) -> None:
        if job.visual_prompt is None:
            return
        out_dir = Path("output") / job.pm.page_name / job.id
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "visual_prompt.txt").write_text(job.visual_prompt)

    def _generate_image(self, job: ContentJob) -> str:
        # Phase 2: wire GPT Image 2 here
        raise NotImplementedError("Image generation wired in Phase 2")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/nennayz/Documents/NayzFreedom/code/slayhack && .venv/bin/pytest tests/test_lila.py -v
```

Expected: all pass.

- [ ] **Step 5: Run full test suite**

```bash
cd /Users/nennayz/Documents/NayzFreedom/code/slayhack && .venv/bin/pytest -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add agents/lila.py tests/test_lila.py
git commit -m "feat(lila): skip articles; differentiate visual prompt by content_type"
```

---

## Task 4: Nora — dynamic QA prompt by content_type

**Files:**
- Modify: `agents/nora.py`
- Modify: `tests/test_nora.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_nora.py`:

```python
from models.content_job import ContentType, Article

def make_article_job_for_nora(dry_run=True):
    from tests.test_bella import make_job_with_idea
    job = make_job_with_idea(dry_run=dry_run, content_type=ContentType.ARTICLE)
    job.bella_output = Article(heading="The Look", body="Step 1...", cta="Shop now")
    return job

def test_nora_live_article_skips_visual_qa(mocker):
    captured = {}
    def fake_call(system, user, **kwargs):
        captured["user"] = user
        return '{"passed":true,"script_feedback":null,"visual_feedback":null,"send_back_to":null}'
    agent = NoraAgent(make_config())
    mocker.patch.object(agent, "_call_claude", side_effect=fake_call)
    job = make_article_job_for_nora(dry_run=False)
    agent.run(job)
    assert "visual" not in captured["user"].lower()
    assert "The Look" in captured["user"]

def test_nora_live_video_includes_visual_in_prompt(mocker):
    captured = {}
    def fake_call(system, user, **kwargs):
        captured["user"] = user
        return '{"passed":true,"script_feedback":null,"visual_feedback":null,"send_back_to":null}'
    agent = NoraAgent(make_config())
    mocker.patch.object(agent, "_call_claude", side_effect=fake_call)
    job = make_job_for_nora(dry_run=False)
    agent.run(job)
    assert "visual" in captured["user"].lower() or "visual_prompt" in captured["user"].lower()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/nennayz/Documents/NayzFreedom/code/slayhack && \
  .venv/bin/pytest tests/test_nora.py::test_nora_live_article_skips_visual_qa \
                   tests/test_nora.py::test_nora_live_video_includes_visual_in_prompt -v
```

Expected: failures — Nora always includes visual QA and reads from the old `job.script`.

- [ ] **Step 3: Rewrite agents/nora.py**

```python
from __future__ import annotations
from agents.base_agent import BaseAgent, TEAM_IDENTITY
from models.content_job import (
    ContentJob, ContentType, QAResult,
    Script, Article, ImageCaption, InfographicContent,
)


def _build_qa_user_prompt(job: ContentJob) -> str:
    bella = job.bella_output

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
    elif job.content_type == ContentType.ARTICLE and isinstance(bella, Article):
        return (
            f"Article heading: {bella.heading}\n"
            f"Article body: {bella.body}\n"
            f"CTA: {bella.cta}\n\n"
            "Review this article content only (no visual). Return JSON with keys: passed (bool), "
            "script_feedback (str or null), visual_feedback (must be null for articles), "
            "send_back_to ('bella' | null). JSON only."
        )
    elif job.content_type == ContentType.IMAGE and isinstance(bella, ImageCaption):
        return (
            f"Image caption: {bella.caption}\n"
            f"Alt text: {bella.alt_text}\n"
            f"Visual prompt: {job.visual_prompt}\n\n"
            "Review this image content. Return JSON with keys: passed (bool), "
            "script_feedback (str or null), visual_feedback (str or null), "
            "send_back_to ('bella' | 'lila' | null). JSON only."
        )
    elif job.content_type == ContentType.INFOGRAPHIC and isinstance(bella, InfographicContent):
        points_str = "\n".join(f"- {p}" for p in bella.points)
        return (
            f"Infographic title: {bella.title}\n"
            f"Points:\n{points_str}\n"
            f"CTA: {bella.cta}\n"
            f"Visual prompt: {job.visual_prompt}\n\n"
            "Review this infographic content. Return JSON with keys: passed (bool), "
            "script_feedback (str or null), visual_feedback (str or null), "
            "send_back_to ('bella' | 'lila' | null). JSON only."
        )
    else:
        raise ValueError(f"Unexpected content_type / bella_output combination: {job.content_type}")


class NoraAgent(BaseAgent):
    def run_dry(self, job: ContentJob, **kwargs) -> ContentJob:
        job.qa_result = QAResult(passed=True)
        job.stage = "nora_done"
        return job

    def run_live(self, job: ContentJob, **kwargs) -> ContentJob:
        system = (
            TEAM_IDENTITY +
            f"You are Nora, QA editor for {job.pm.page_name}. "
            f"Brand tone: {job.pm.brand.tone}. "
            f"Audience: {job.pm.brand.target_audience}. "
            "Be strict. Reject weak hooks, off-brand visuals, and anything that feels generic."
        )
        user = _build_qa_user_prompt(job)
        raw = self._call_claude(system, user, max_tokens=512)
        result = QAResult(**self._parse_json(raw))
        if not result.passed:
            job.nora_retry_count += 1
        job.qa_result = result
        job.stage = "nora_done"
        return job
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/nennayz/Documents/NayzFreedom/code/slayhack && .venv/bin/pytest tests/test_nora.py -v
```

Expected: all pass.

- [ ] **Step 5: Run full test suite**

```bash
cd /Users/nennayz/Documents/NayzFreedom/code/slayhack && .venv/bin/pytest -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add agents/nora.py tests/test_nora.py
git commit -m "feat(nora): dynamic QA prompt by content_type; skip visual QA for articles"
```

---

## Task 5: Roxy — load platform_specs in live path + update growth file

**Files:**
- Modify: `agents/roxy.py`
- Modify: `tests/test_roxy.py`

- [ ] **Step 1: Write the failing tests**

Update `test_roxy_live_calls_claude` in `tests/test_roxy.py` to assert `editorial_guidance` is populated, and add a new test for the platform_specs integration:

```python
def test_roxy_live_calls_claude(mocker, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # Create a minimal platform_specs.yaml so load_platform_specs works
    import yaml
    (tmp_path / "projects").mkdir()
    (tmp_path / "projects" / "slay_hack").mkdir()
    (tmp_path / "projects" / "slay_hack" / "platform_specs.yaml").write_text(
        "instagram:\n  editorial: Hook within 3 seconds.\nfacebook:\n  editorial: Conversational tone.\n"
    )
    strategy_json = ('{"hashtags":["#LipHack","#GlossyLips"],'
                     '"caption":"your new fave hack","best_post_time_utc":"13:00","best_post_time_thai":"20:00"}')
    mocker.patch.object(RoxyAgent, "_call_claude", return_value=strategy_json)
    agent = RoxyAgent(make_config())
    job = make_job_post_qa(dry_run=False)
    job.pm.brand.platforms[:]  # ensure platforms is populated from fixture
    job = agent.run(job)
    assert job.growth_strategy.hashtags == ["#LipHack", "#GlossyLips"]
    assert job.growth_strategy.editorial_guidance == {}  # fixture job has no platforms in specs dir
    assert job.stage == "roxy_done"

def test_roxy_live_populates_editorial_guidance(mocker, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "projects").mkdir()
    (tmp_path / "projects" / "slay_hack").mkdir()
    (tmp_path / "projects" / "slay_hack" / "platform_specs.yaml").write_text(
        "instagram:\n  editorial: Hook within 3 seconds.\n"
        "facebook:\n  editorial: Conversational tone.\n"
    )
    strategy_json = ('{"hashtags":["#LipHack"],'
                     '"caption":"cap","best_post_time_utc":"13:00","best_post_time_thai":"20:00"}')
    mocker.patch.object(RoxyAgent, "_call_claude", return_value=strategy_json)
    agent = RoxyAgent(make_config())
    job = make_job_post_qa(dry_run=False)
    # make_job uses platforms=["instagram"] — should pick up the instagram editorial
    job = agent.run(job)
    assert "instagram" in job.growth_strategy.editorial_guidance
    assert job.growth_strategy.editorial_guidance["instagram"] == "Hook within 3 seconds."
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/nennayz/Documents/NayzFreedom/code/slayhack && \
  .venv/bin/pytest tests/test_roxy.py::test_roxy_live_populates_editorial_guidance -v
```

Expected: FAIL — Roxy's live path doesn't call `load_platform_specs` yet.

- [ ] **Step 3: Rewrite agents/roxy.py**

```python
from __future__ import annotations
import json
from pathlib import Path
from agents.base_agent import BaseAgent, TEAM_IDENTITY
from models.content_job import ContentJob, GrowthStrategy
from project_loader import load_platform_specs

_DRY_RUN_STRATEGY = GrowthStrategy(
    hashtags=["#LongLastingLips","#GlossyLips","#LipHack","#QuietLuxury","#BeautyHacks","#GlowUp"],
    caption="the lip hack you didn't know you needed 💋 save this before your next glam sesh",
    best_post_time_utc="13:00",
    best_post_time_thai="20:00",
    editorial_guidance={
        "instagram": "Hook within 3 seconds. Caption under 150 chars. Hashtags in first comment.",
        "facebook": "Conversational tone. 1-3 sentences. Hashtags optional, inline.",
        "tiktok": "Text overlay on video. CTA in last 3 seconds. Sound-on assumed. Trending audio boosts reach.",
        "youtube": "Thumbnail-first mindset. Title under 60 chars. Description with timestamps. First 30 seconds must hook.",
    },
)


def _write_growth_file(job: ContentJob) -> None:
    g = job.growth_strategy
    out_dir = Path("output") / job.pm.page_name / job.id
    out_dir.mkdir(parents=True, exist_ok=True)
    guidance_lines = ""
    if g.editorial_guidance:
        items = "\n".join(f"  - **{p}:** {text}" for p, text in g.editorial_guidance.items())
        guidance_lines = f"\n\n## Editorial Guidance\n\n{items}"
    (out_dir / "growth.md").write_text(
        f"# Growth Strategy\n\n**Caption:** {g.caption}\n\n"
        f"**Hashtags:** {' '.join(g.hashtags)}\n\n"
        f"**Best post time:** {g.best_post_time_utc} UTC / {g.best_post_time_thai} Thai"
        + guidance_lines
    )


class RoxyAgent(BaseAgent):
    def run_dry(self, job: ContentJob, **kwargs) -> ContentJob:
        job.growth_strategy = _DRY_RUN_STRATEGY
        job.stage = "roxy_done"
        _write_growth_file(job)
        return job

    def run_live(self, job: ContentJob, **kwargs) -> ContentJob:
        bella = job.bella_output
        # Extract a hook-like line from any content type for the prompt
        if hasattr(bella, "hook"):
            content_ref = f"Script hook: {bella.hook}"
        elif hasattr(bella, "heading"):
            content_ref = f"Article heading: {bella.heading}"
        elif hasattr(bella, "caption"):
            content_ref = f"Image caption: {bella.caption}"
        elif hasattr(bella, "title"):
            content_ref = f"Infographic title: {bella.title}"
        else:
            content_ref = f"Content: {str(bella)}"

        system = (
            TEAM_IDENTITY +
            f"You are Roxy, growth strategist for {job.pm.page_name}. "
            f"Target audience: {job.pm.brand.target_audience}. "
            f"Platforms: {', '.join(job.platforms)}."
        )
        user = (
            f"Brief: {job.brief}\n{content_ref}\n"
            "Provide 5-10 hashtags, a short caption, and optimal post times for USA audience. "
            "Return JSON with keys: hashtags (list of str), caption (str), "
            "best_post_time_utc (str HH:MM), best_post_time_thai (str HH:MM). JSON only."
        )
        raw = self._call_claude(system, user, max_tokens=512)
        parsed = self._parse_json(raw)

        # Load editorial guidance for each platform in this job
        all_specs = load_platform_specs(job.project)
        editorial_guidance = {p: all_specs[p] for p in job.platforms if p in all_specs}
        parsed["editorial_guidance"] = editorial_guidance

        job.growth_strategy = GrowthStrategy(**parsed)
        job.stage = "roxy_done"
        _write_growth_file(job)
        return job
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/nennayz/Documents/NayzFreedom/code/slayhack && .venv/bin/pytest tests/test_roxy.py -v
```

Expected: all pass.

- [ ] **Step 5: Run full test suite**

```bash
cd /Users/nennayz/Documents/NayzFreedom/code/slayhack && .venv/bin/pytest -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add agents/roxy.py tests/test_roxy.py
git commit -m "feat(roxy): load platform_specs in live path; render editorial_guidance in growth file"
```

---

## Self-Review

### Spec coverage

| Spec requirement | Covered in |
|---|---|
| Zoe prompt includes allowed_content_types (done in 2B-i) | ✅ complete |
| Orchestrator sets job.content_type at idea_selection | Task 1 |
| Robin system prompt includes content_type routing | Task 1 |
| Bella branches on content_type → correct BellaOutput | Task 2 |
| script field removed from ContentJob | Task 2 |
| Lila skips for articles | Task 3 |
| Lila differentiates prompt by type (video stub, image, infographic) | Task 3 |
| Nora builds QA prompt dynamically by content_type | Task 4 |
| Nora skips visual QA for articles | Task 4 |
| Roxy loads platform_specs.yaml in live path | Task 5 |
| Roxy populates editorial_guidance keyed by platform | Task 5 |
| _write_growth_file renders editorial_guidance | Task 5 |
| All tests migrated from job.script to job.bella_output | Task 2 |

### No placeholders found.

### Type consistency

- `_DRY_RUN_OUTPUTS` in bella.py is typed `dict[ContentType, BellaOutput]` — all 4 entries are valid union members.
- `_build_qa_user_prompt` in nora.py uses `isinstance` guards before accessing type-specific fields — safe.
- `load_platform_specs` returns `dict[str, str]` — Roxy's dict comprehension produces the same type as `GrowthStrategy.editorial_guidance`.
- `job.content_type` is `Optional[ContentType]` — all agents that branch on it are called after Task 1 sets it at idea_selection.
