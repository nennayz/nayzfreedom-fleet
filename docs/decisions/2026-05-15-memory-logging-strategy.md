# 2026-05-15 — Separate Logs, Docs, Decisions, and Vault

**Status:** Accepted

## Context

The project already had operational logs and mission output artifacts, but long-term memory was not clearly separated. Captain Nayz wants the system to learn and grow over time while preserving decisions and knowledge.

## Decision

Adopt a layered memory strategy:

1. `logs/` — machine-oriented activity logs
2. `output/` — mission state and generated artifacts
3. `docs/` — shareable project documentation
4. `docs/decisions/` — durable decision records
5. private Obsidian vault — personal knowledge, reflection, goals, songs, and travel memories

Use `vault-template/` as a safe starter structure, while ignoring real private vaults in git.

## Consequences

- Logs remain operational and are not treated as human knowledge.
- Decisions become durable and reviewable.
- Personal information gets a safer place outside committed project docs.
- Nami can later be designed around explicit memory boundaries.

## Follow-ups

- Create export workflows later for mission summaries and weekly reports.
- Define Nami's access boundaries before integrating private notes.

