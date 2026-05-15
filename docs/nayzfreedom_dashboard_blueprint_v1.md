# NayzFreedom Dashboard Blueprint v1

**Status:** Implementation planning draft  
**Purpose:** Translate the Fleet Bible into an information architecture and staged product plan for evolving the current SlayHack dashboard into the NayzFreedom Fleet command center.

---

## 1. Product Goal

Evolve the current dashboard from a narrow job viewer into a fleet-aware operating system that lets Captain Nayz:

- understand the state of every ship quickly
- inspect work in progress
- review agents and workflows
- make the next important decision without hunting through pages
- grow into personal and music operations later without redesigning from scratch

---

## 2. Current State

The existing dashboard currently provides:

- jobs list
- job detail
- metrics
- trigger form

It is useful operationally, but structurally it is still a single-ship dashboard for the current content pipeline.

---

## 3. Target Information Architecture

```text
Captain's Deck
├── Fleet Overview
├── Ships
│   ├── The Aurora
│   │   ├── Overview
│   │   ├── Islands / Projects
│   │   ├── Missions
│   │   ├── Crew
│   │   └── Metrics
│   ├── The Freedom
│   │   ├── Overview
│   │   ├── Freedom Five
│   │   └── Horizon Atlas
│   └── The Lyra
│       ├── Overview
│       ├── Songs
│       └── Releases
├── Crew Registry
└── Captain's Briefs
```

---

## 4. Navigation Model

## Global navigation

Recommended primary nav:

1. **Captain's Deck**
2. **The Aurora**
3. **The Freedom**
4. **The Lyra**
5. **Crew**

Recommended utility nav:

- Briefs
- Search
- Settings

## Why this navigation works

- it mirrors the fleet hierarchy
- it creates room for future ships
- it avoids burying the current dashboard inside generic labels
- it keeps the Captain-oriented experience central

---

## 5. Page Blueprints

## 5.1 Captain's Deck

### Primary question

**What needs the Captain's attention now?**

### Sections

1. **Captain Brief**
   - top priorities
   - urgent decisions
   - blockers
   - upcoming milestones

2. **Fleet Status**
   - one card per ship
   - health
   - active missions
   - pending decisions

3. **Current Voyages**
   - active work across ships
   - grouped by importance, not by recency alone

4. **Distress Signals**
   - overdue items
   - failed missions
   - approvals waiting

5. **Horizons**
   - strategic goals
   - progress against quarter / year

### MVP treatment

In the first release:

- `The Aurora` card is live
- `The Freedom` and `The Lyra` cards may be elegant placeholders
- Captain Brief can be composed from Aurora data first

---

## 5.2 The Aurora Overview

### Primary question

**How is the work ship performing?**

### Sections

1. Aurora hero panel
2. island cards (`SlayHack`, future projects)
3. active mission board
4. crew activity
5. recent outputs
6. growth metrics
7. quick action to start a new mission

### First implementation mapping

- existing jobs list becomes **missions**
- existing metrics page becomes **treasure report / performance**
- existing trigger page becomes **new mission**

---

## 5.3 Island Detail

### Primary question

**What is happening inside this specific project?**

### Sections

- island identity / page persona
- brand mission
- target audience
- recent missions
- content calendar
- performance snapshot
- active crew assignments

### First live island

- SlayHack

---

## 5.4 Mission Detail / Voyage Log

### Primary question

**Where is this mission in its route, and what has happened so far?**

### Replace the current flat detail page with:

1. mission header
2. stage timeline
3. assigned crew path
4. outputs grouped by agent
5. approvals / checkpoint log
6. publish result
7. performance after release

### Current pipeline mapping

| Current stage | Voyage label | Agent |
|---|---|---|
| Mia | Scout the Horizon | Mia |
| Zoe | Chart the Route | Zoe |
| Bella | Write the Tale | Bella |
| Lila | Shape the Vision | Lila |
| Nora | Inspect the Cargo | Nora |
| Roxy | Set the Trade Winds | Roxy |
| Emma | Prepare the Port Talk | Emma |
| Publish | Raise the Flag | Publish |

---

## 5.5 Crew Registry

### Primary question

**Who are the crew members, and what does each one do?**

### Sections

- filter by ship
- character cards
- role summary
- current assignments
- strengths / outputs

### Crew card fields

- portrait
- name
- ship
- role title
- one-line function
- current status
- signature color

---

## 5.6 Character Sheet

### Primary question

**What makes this crew member distinct?**

### Sections

- hero portrait
- ship role
- operational role
- personality
- strengths
- watch-outs
- inputs
- outputs
- linked missions
- signature quote

### MVP

Ship only the Aurora crew sheets first:

- Robin
- Mia
- Zoe
- Bella
- Lila
- Nora
- Roxy
- Emma

Nami and Genie can appear as coming soon or concept-level entries until their underlying ships are implemented.

---

## 5.7 The Freedom Overview

### Primary question

**Is the Captain's life aligned with the Freedom Five?**

### Future sections

- Freedom Five wheel
- Nami brief
- wealth summary
- health snapshot
- relationship / love intentions
- soul practices
- Horizon Atlas
- open loops

### MVP

- teaser page only
- define visual language and content model
- avoid implementing sensitive personal data before privacy architecture is planned

---

## 5.8 The Lyra Overview

### Primary question

**What songs are alive right now, and what is ready to move forward?**

### Future sections

- song pipeline
- latest sparks
- active demos
- release calendar
- current artistic era
- Genie notes

### MVP

- teaser page only
- establish visual language and future entity structure

---

## 6. Core Data Model

The current codebase only has content jobs. The future system should progressively move toward these concepts:

```text
Fleet
Ship
Agent
Project / Island
Domain
Mission
MissionStage
Goal / Horizon
Song
Expedition
Brief
Alert
```

## Suggested relationships

```text
Fleet 1---* Ship
Ship 1---* Agent
Ship 1---* Project/Domain
Project/Domain 1---* Mission
Mission 1---* MissionStage
Mission *---* Agent
Ship 1---* Goal
The Lyra 1---* Song
The Freedom 1---* Expedition
```

## Migration principle

Do not rewrite the whole backend at once.  
Wrap the current content-job model inside the new conceptual layer first.

Example:

- `ContentJob` remains the live runtime model
- the UI presents it as an Aurora mission
- later, a generalized `Mission` model can emerge if multiple ships need a shared workflow abstraction

---

## 7. MVP Scope

## Build now

1. Fleet-aware visual shell
2. Captain's Deck home
3. Aurora overview
4. mission-oriented redesign of existing jobs
5. crew registry
6. character sheets for Aurora crew
7. elegant placeholder pages for The Freedom and The Lyra

## Explicitly defer

- personal finance features
- investment calculations
- personal journaling
- travel itinerary system
- song production management
- release distribution
- authentication redesign
- cross-ship automations

---

## 8. Recommended Delivery Phases

## Phase 1 — Fleet Foundation

- new naming system
- global nav
- updated visual language
- Captain's Deck
- placeholders for all three ships

## Phase 2 — Aurora Upgrade

- transform existing dashboard pages into mission-oriented pages
- add island detail
- add workflow timeline
- add crew registry
- add character sheets

## Phase 3 — Freedom Design

- privacy architecture
- Freedom Five model
- Horizon Atlas model
- Nami workflows

## Phase 4 — Lyra Design

- song model
- song voyage workflow
- Genie workflows
- release calendar

## Phase 5 — Cross-Ship Intelligence

- linked missions
- captain brief generation
- cross-ship alerts
- dependencies and tradeoffs

---

## 9. Design System Recommendations

## Shared palette

- navy
- ivory
- cream
- antique gold
- deep indigo

## Ship accent colors

| Ship | Accent direction |
|---|---|
| The Aurora | aurora green / violet gradients |
| The Freedom | compass gold / sea blue |
| The Lyra | starlight silver / midnight indigo |

## Component language

- large hero cards
- illustrated crew cards
- route timelines
- status pills
- parchment / map motifs used sparingly
- premium spacing, never cluttered

---

## 10. Implementation Concerns

1. **Privacy**
   - `The Freedom` will contain the most sensitive data
   - do not implement it deeply before defining storage, access, and AI boundaries

2. **Theme overreach**
   - thematic labels must not obscure ordinary actions

3. **Data duplication**
   - songs, trips, and campaigns should link across ships rather than be copied

4. **Future extensibility**
   - current dashboard should evolve without breaking the content pipeline

5. **Character/IP originality**
   - keep all art and naming original to NayzFreedom

---

## 11. Immediate Next Build Recommendation

The next code change should be **Phase 1 — Fleet Foundation**, not a full rewrite.

### First concrete milestone

Create a new dashboard shell with:

- branded fleet header
- Captain's Deck home
- nav entries for the three ships
- Aurora status card populated from current job data
- placeholder cards for The Freedom and The Lyra

This gives the new world a real home while keeping implementation risk low.

