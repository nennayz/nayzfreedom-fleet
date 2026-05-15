# NayzFreedom Command Router Design

**Purpose:** Define how Dashboard, Telegram, and future Discord commands should control the pipeline through one shared command layer instead of each interface building its own behavior.

---

## 1. Problem

The system can already start pipeline runs from:

- terminal
- dashboard
- Telegram bot

Future interfaces may include:

- Discord
- Nami commands
- scheduled automations

If every interface constructs subprocess commands directly, behavior will drift and become difficult to secure.

---

## 2. Recommended Architecture

```text
Dashboard UI
Telegram Bot
Discord Bot
Scheduler
    ↓
Command Router
    ↓
Mission Service
    ↓
Pipeline Runner
```

---

## 3. Command Router Responsibilities

The router should standardize:

- project validation
- content type validation
- dry-run behavior
- unattended behavior
- command source tracking
- lock / concurrency rules
- user-facing status messages

It should not contain UI-specific code.

---

## 4. Initial Command Interface

Suggested first functions:

```python
create_content_mission(
    project: str,
    brief: str,
    content_type: str,
    dry_run: bool,
    unattended: bool,
    source: str,
) -> MissionLaunchResult
```

```python
get_mission_status(job_id: str) -> MissionStatus
```

```python
list_recent_missions(limit: int = 10) -> list[MissionSummary]
```

---

## 5. Interface Mapping

## Dashboard

- form submits to FastAPI
- FastAPI calls command router
- command router launches mission

## Telegram

- `/new_mission`
- `/status`
- `/cancel`
- `/approve`
- eventually Nami daily brief

## Discord

Future channel model:

```text
#captains-deck
#the-aurora
#the-freedom
#the-lyra
#mission-logs
#approvals
```

Discord should come after Telegram unless a team/community workflow becomes urgent.

---

## 6. Telegram First Recommendation

Telegram is the best next command surface because it is:

- private
- mobile-native
- already partly implemented
- good for checkpoint approval
- good for Captain-level quick actions

Recommended commands:

```text
/start_mission
/status
/recent
/approve
/cancel
/today
```

---

## 7. Safety Rules

1. Only authorized chat IDs can issue commands
2. Live runs must be explicit
3. Dry run should be default for new command surfaces
4. Long-running commands must return immediate acknowledgement
5. Mission locks should prevent accidental overlapping runs
6. Every command should record its source

---

## 8. Future Nami Integration

Nami should eventually sit above the command router:

```text
Captain request
    ↓
Nami interprets and clarifies
    ↓
Command Router executes approved command
```

Nami should suggest actions, but high-impact live actions should still require explicit Captain confirmation.

