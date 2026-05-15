# NayzFreedom Production / VPS Readiness Plan

**Purpose:** Prepare the current local dashboard and pipeline for safe online access through a VPS without prematurely overbuilding the system.

---

## 1. Target Production Shape

```text
Browser / Mobile
    ↓ HTTPS
Domain + reverse proxy
    ↓
FastAPI Dashboard
    ↓
Mission command layer
    ↓
Pipeline runner / workers
    ↓
Projects, output, logs, assets
```

---

## 2. Recommended VPS Stack

## Minimum viable production stack

- Ubuntu VPS
- Python virtual environment
- `systemd` services
- Caddy or Nginx reverse proxy
- HTTPS certificate
- firewall allowing only SSH + HTTPS
- regular backup of `projects/`, `output/`, `.env`, and `logs/`

The repo already contains early `deploy/*.service` files, so deployment should build from that direction rather than inventing a new process manager.

---

## 3. Security Requirements Before Public Access

The dashboard currently uses HTTP Basic Auth. This is acceptable for local/small private use, but before putting it on the public internet:

1. Use HTTPS only
2. Use a strong password
3. Keep `.env` outside public paths
4. Run the app as a dedicated non-root user
5. Disable debug behavior
6. Add rate limiting at the reverse proxy
7. Add backups
8. Log failed auth attempts if practical

## Special warning for `The Freedom`

Do not put sensitive personal finance, health, love, or private journal data online until the privacy model is stronger.

Future `The Freedom` features may require:

- stronger authentication
- separate permissions
- encrypted storage
- explicit AI-sharing boundaries
- local-only or private-network-only modes

---

## 4. Process Layout

Recommended services:

```text
nayzfreedom-dashboard.service
nayzfreedom-telegram-bot.service
nayzfreedom-scheduler.timer
nayzfreedom-reporter.timer
```

Future services:

```text
nayzfreedom-worker.service
nayzfreedom-discord-bot.service
```

Avoid running long jobs directly inside web request handlers. The current dashboard starts subprocesses, which is acceptable for this phase, but a worker queue should eventually replace direct spawning.

---

## 5. Storage Plan

## Current

- `projects/`
- `output/`
- `logs/`
- `static/`
- `.env`

This remains acceptable while the system is single-user and file-based.

## Future

Move gradually toward:

- SQLite for metadata
- filesystem or object storage for large assets
- backups for every stateful directory
- migration scripts before introducing multiple users

---

## 6. Mobile / Remote Use Design Notes

If the dashboard is accessed from a phone:

- core pages must be responsive
- actions must be thumb-friendly
- mission status must not depend on wide tables
- launch forms must be easy to use on mobile
- destructive actions must require confirmation

The current mobile pass supports the first remote-use version, but before production launch it should be checked on actual devices.

---

## 7. Recommended Production Milestones

## Milestone 1 — Private VPS

- deploy dashboard behind HTTPS
- strong Basic Auth
- run services via systemd
- backups configured

## Milestone 2 — Command Layer

- dashboard and bots call the same command functions
- no duplicate subprocess command construction across interfaces

## Milestone 3 — Worker Mode

- queue missions
- track background jobs
- prevent overlapping unsafe runs

## Milestone 4 — Strong Privacy

- required before serious `The Freedom` data goes online

