# NayzFreedom Logging and Memory Strategy

**Status:** Working strategy  
**Date:** 2026-05-15  
**Purpose:** Define where operational logs, job artifacts, product decisions, design docs, and long-term knowledge should live as NayzFreedom grows into a fleet operating system.

---

## 1. Why this matters

NayzFreedom is becoming more than a content pipeline. It now includes:

- `The Aurora` — work, brands, content missions
- `The Freedom` — personal life and the Freedom Five
- `The Lyra` — music, songs, releases, and soul expression
- `The Horizon Atlas` — travel memories and expedition planning

As the system grows, it needs memory at multiple levels:

- machine-readable logs
- mission artifacts
- design documentation
- decision history
- human-readable knowledge and reflection

These should not all live in the same place.

---

## 2. Memory layers

## Layer 1 — Operational logs

**Purpose:** Debugging and runtime history.

Current location:

```text
logs/activity-YYYY-MM-DD.log
```

Current logger:

```text
activity_logger.py
```

Current events include:

- `main_invocation`
- `start_job`
- `orchestrator_start`
- `run_agent`
- `request_checkpoint`
- `orchestrator_complete`
- scheduler start/complete events

These logs are for systems and debugging, not long-term storytelling.

### Retention recommendation

- keep recent logs locally
- back up before VPS migration if operational history matters
- do not commit logs to git

---

## Layer 2 — Mission state and artifacts

**Purpose:** Source of truth for content missions.

Current location:

```text
output/<page_name>/<job_id>/
```

Current files can include:

- `job.json`
- `ideas.md`
- `script.md`
- `visual_prompt.txt`
- `growth.md`
- `faq.md`
- image/video outputs when available

`job.json` is the mission state record. It stores:

- job id
- project
- brief
- status
- stage
- dry-run flag
- selected idea
- agent outputs
- checkpoint log
- publish result
- performance records

### Retention recommendation

- keep `output/` out of git
- back it up separately
- eventually add export-to-vault summaries for important completed missions

---

## Layer 3 — Project documentation

**Purpose:** Durable design, architecture, and implementation knowledge.

Current location:

```text
docs/
```

Use docs for:

- architecture plans
- design systems
- implementation plans
- product blueprints
- deployment plans
- command architecture

Docs are shareable project knowledge and should not contain secrets.

---

## Layer 4 — Decision records

**Purpose:** Preserve why important decisions were made.

Location:

```text
docs/decisions/
```

Use decision records for choices such as:

- ship naming
- architecture boundaries
- security decisions
- integration strategy
- product scope decisions

### Decision record template

```markdown
# YYYY-MM-DD — Decision title

**Status:** Accepted / Proposed / Superseded

## Context

What situation created the decision?

## Decision

What did we choose?

## Consequences

What becomes easier, harder, or deferred?

## Follow-ups

What should be revisited later?
```

---

## Layer 5 — Personal knowledge vault

**Purpose:** Long-term human knowledge, reflection, goals, ideas, lyrics, travel memories, and personal operating system notes.

Recommended tool:

```text
Obsidian
```

Recommended actual private vault location:

```text
~/Documents/NayzFreedom Vault/
```

or any private synced location the Captain trusts.

The repo contains only:

```text
vault-template/
```

This is a safe starter structure. The real private `vault/` is ignored by git.

---

## 3. What belongs where

| Information | Best home |
|---|---|
| API keys | `.env`, never docs or vault template |
| runtime actions | `logs/` |
| mission state | `output/.../job.json` |
| generated scripts/ideas | `output/.../` |
| dashboard architecture | `docs/` |
| accepted product decisions | `docs/decisions/` |
| personal goals | private Obsidian vault |
| investment notes | private Obsidian vault |
| health/love/soul notes | private Obsidian vault |
| song lyrics | private Obsidian vault or dedicated Lyra storage later |
| travel memories | private Obsidian vault / Horizon Atlas |

---

## 4. Current state inventory

As of 2026-05-15:

- operational logging exists through `activity_logger.py`
- daily log files are written under `logs/`
- mission state is written under `output/`
- dashboard and fleet design docs exist under `docs/`
- decision records are now introduced under `docs/decisions/`
- Obsidian-style structure is introduced under `vault-template/`

---

## 5. Recommended evolution

## Phase 1 — Now

- keep logs and output as they are
- begin writing decision records
- use `vault-template/` to create a private vault outside the repo
- do not automate private personal data yet

## Phase 2 — After The Freedom starts

- define what Nami can read
- define what Nami must never send to external AI without confirmation
- create private note categories for Freedom Five

## Phase 3 — After VPS deployment

- ensure backups for `output/`, `logs/`, and private vault if applicable
- add production log rotation
- consider SQLite for mission metadata

## Phase 4 — Cross-system memory

- export completed mission summaries to vault
- export weekly reports to vault
- link songs/trips/campaigns across ships
- keep source-of-truth records separate from narrative notes

---

## 6. Privacy rules

1. Never commit `.env`.
2. Never commit the real private vault.
3. Do not place financial, health, relationship, or private journal details in public docs.
4. Use `docs/` for shareable system knowledge only.
5. Use the private vault for personal knowledge.
6. If Nami later reads vault notes, require explicit boundaries and confirmation.

---

## 7. Immediate practice

When a major choice happens:

1. write a decision record in `docs/decisions/`
2. if it affects personal life, optionally mirror a more reflective note in the private vault
3. keep implementation details in `docs/`
4. let logs stay machine-oriented

