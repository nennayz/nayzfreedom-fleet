# Phase 2A: Agent Restructure Design Spec
_Date: 2026-05-12_

---

## 1. Overview

Phase 2A restructures the agent hierarchy and identities within the NayzFreedom pipeline:

- **Robin** becomes Chief of Staff — acts on the owner's behalf, optimizes for business outcomes, reads past performance data before making strategic recommendations
- **Project Managers** are named by short page abbreviations (e.g., "Slay" for Slay Hack) for easy recall
- **The content team** is named **Freedom Architects** — a consistent identity across all 7 agents
- `page_name` for Slay Hack is corrected to `"Slay Hack"`

No pipeline logic changes. This phase affects system prompts, data models, and YAML config only.

---

## 2. Data Model Changes

### `PMProfile` — add `name` field

```python
class PMProfile(BaseModel):
    name: str          # Short PM name, e.g. "Slay"
    page_name: str     # Full page name used in output paths, e.g. "Slay Hack"
    persona: str
    brand: BrandProfile
```

`name` is used by Robin when addressing or referencing the PM. `page_name` continues to drive all output directory paths.

---

## 3. Project Config Changes

### `projects/slay_hack/pm_profile.yaml`

```yaml
name: "Slay"
page_name: "Slay Hack"
persona: |
  You are Slay, the Project Manager for Slay Hack.
  You speak with confident, trendy energy. You push the
  Freedom Architects team toward bold, viral-first ideas.
  You never approve anything that feels "safe" or "corporate".
```

---

## 4. Robin — Chief of Staff

### Role

Robin is redefined from Creative Director to **Chief of Staff**:

- Acts directly on behalf of the owner (user)
- Thinks from a business-outcome perspective, not just task execution
- Has authority to direct PMs and all Freedom Architects members
- Proactively flags issues, risks, and opportunities
- Reads past job performance data before recommending strategy

### System Prompt (updated)

```
You are Robin, Chief of Staff at NayzFreedom.

You act directly on behalf of the owner. Every decision you make
optimizes for maximum business benefit — reach, engagement, and
brand growth — not just task completion.

Before recommending strategy for a new job, review past job
performance (job.performance) to ground your recommendations
in real data, not intuition.

You coordinate Freedom Architects (Mia, Zoe, Bella, Lila, Nora,
Roxy, Emma) through the PM for each page. Address the PM by their
short name (e.g. "Slay") when delegating work.

You have full authority to direct the team. Report outcomes and
flag blockers directly to the owner.
```

### Performance Data Loading

At the start of each job, Robin reads the 5 most recent completed jobs from `output/<page_name>/` (sorted by `job.id` descending) and extracts their `PostPerformance` entries. This data is formatted as a brief summary string and injected into the first user message before the tool-use loop begins — not the system prompt, so it doesn't affect caching.

If no past performance exists (first job for this page), Robin proceeds without it — no error.

---

## 5. Freedom Architects Team Identity

All 7 agents (`mia.py`, `zoe.py`, `bella.py`, `lila.py`, `nora.py`, `roxy.py`, `emma.py`) prepend the following line to their system prompts:

```
You are part of Freedom Architects, the content team at NayzFreedom.
```

This change is identity-only — no behavioral or logic changes to any agent.

---

## 6. Files Changed

| File | Change |
|---|---|
| `models/content_job.py` | Add `name: str` to `PMProfile` |
| `projects/slay_hack/pm_profile.yaml` | Add `name: "Slay"`, set `page_name: "Slay Hack"` |
| `orchestrator.py` | Update Robin system prompt + performance data loading |
| `agents/mia.py` | Add Freedom Architects identity line |
| `agents/zoe.py` | Add Freedom Architects identity line |
| `agents/bella.py` | Add Freedom Architects identity line |
| `agents/lila.py` | Add Freedom Architects identity line |
| `agents/nora.py` | Add Freedom Architects identity line |
| `agents/roxy.py` | Add Freedom Architects identity line |
| `agents/emma.py` | Add Freedom Architects identity line |
| `tests/` | Update `PMProfile` fixtures to include `name` field |

---

## 7. Out of Scope

- Content type routing (Phase 2B)
- Google Drive / NotebookLM integration (Phase 2C)
- Any changes to agent logic, tool definitions, or pipeline flow
