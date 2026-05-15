# Decision Records

This folder stores durable decisions for NayzFreedom.

Use a decision record when a choice changes product direction, architecture, privacy boundaries, workflow, naming, security, or long-term operating principles.

## Filename convention

```text
YYYY-MM-DD-short-decision-title.md
```

Examples:

```text
2026-05-15-fleet-architecture.md
2026-05-15-memory-logging-strategy.md
```

## Template

```markdown
# YYYY-MM-DD — Decision title

**Status:** Proposed / Accepted / Superseded

## Context

What situation created the decision?

## Decision

What did we choose?

## Consequences

What becomes easier, harder, or deferred?

## Follow-ups

What should be revisited later?
```

## Rules

- Preserve the reason, not only the result.
- Do not store API keys, passwords, private financial data, health records, or sensitive relationship notes here.
- If the decision depends on private personal context, summarize only the non-sensitive principle and keep private detail in the private vault.
- If a decision changes later, create a new decision record and mark the old one as superseded instead of deleting history.
