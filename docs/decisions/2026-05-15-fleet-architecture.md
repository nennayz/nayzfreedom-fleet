# 2026-05-15 — Adopt NayzFreedom Fleet Architecture

**Status:** Accepted

## Context

The project began as a Python multi-agent content pipeline for SlayHack. During dashboard design, the product direction expanded into a broader operating system for Captain Nayz, covering work, personal freedom, music, and travel.

The system needed a structure that could grow without mixing content operations, personal life systems, and artistic work into one flat project list.

## Decision

Adopt **NayzFreedom Fleet** as the top-level architecture.

Canonical structure:

```text
NayzFreedom Fleet
├── The Aurora
├── The Freedom
└── The Lyra
```

- `The Aurora` handles work, brands, content, and external impact.
- `The Freedom` handles personal life and the Freedom Five.
- `The Lyra` handles music, songs, and releases.

## Consequences

- Dashboard navigation should become ship-based.
- Existing SlayHack content work belongs under `The Aurora`.
- Personal systems should not be forced into the content pipeline.
- Music deserves a separate ship because it has its own creative workflow.

## Follow-ups

- Build The Freedom only after privacy and memory boundaries are clear.
- Build The Lyra after the basic Fleet shell is stable.

