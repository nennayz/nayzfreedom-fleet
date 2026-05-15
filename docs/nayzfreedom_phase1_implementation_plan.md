# NayzFreedom Phase 1 Implementation Plan

**Phase:** Fleet Foundation  
**Goal:** Transform the current single-purpose dashboard shell into the first usable version of the NayzFreedom Fleet command center without rewriting the content pipeline.

---

## 1. Product Outcome

After Phase 1, Captain Nayz should be able to open the dashboard and immediately see:

- the new NayzFreedom Fleet identity
- a `Captain's Deck` landing page
- one live ship card for `The Aurora`
- elegant placeholder cards for `The Freedom` and `The Lyra`
- the existing Aurora operations still available: missions, metrics, and new mission launch

This phase should make the new world real while preserving all current functionality.

---

## 2. Scope

## In scope

- fleet-aware navigation
- new landing page at `/`
- rename current jobs view conceptually into Aurora missions
- ship overview page for `The Aurora`
- placeholder overview pages for `The Freedom` and `The Lyra`
- visual refresh of the shared shell
- reuse of existing job data and performance data

## Out of scope

- full crew registry
- character sheets
- workflow timeline redesign
- island detail pages
- personal finance data
- song catalog data
- cross-ship automation
- authentication changes

---

## 3. Existing Code to Reuse

| Existing asset | Reuse plan |
|---|---|
| `dashboard.py` | keep FastAPI app and auth; add fleet routes |
| `dashboard_store.py` | reuse job/performance readers; add lightweight summary helpers only if needed |
| `templates/base.html` | upgrade into fleet shell |
| `templates/jobs.html` | evolve into Aurora missions page |
| `templates/metrics.html` | keep as Aurora performance page |
| `templates/trigger.html` | keep as Aurora new mission form |
| `static/style.css` | expand into the new design system foundation |

---

## 4. Proposed Routes

| Method | Path | Page |
|---|---|---|
| `GET` | `/` | Captain's Deck |
| `GET` | `/aurora` | The Aurora overview |
| `GET` | `/aurora/missions` | Aurora missions list |
| `GET` | `/aurora/metrics` | Aurora metrics |
| `GET` | `/aurora/new-mission` | New mission form |
| `GET` | `/freedom` | The Freedom placeholder overview |
| `GET` | `/lyra` | The Lyra placeholder overview |

## Compatibility choice

To avoid breaking the current dashboard immediately:

- `/jobs` can redirect to `/aurora/missions`
- `/metrics` can redirect to `/aurora/metrics`
- `/trigger` can redirect to `/aurora/new-mission`

Existing deep job URLs such as `/jobs/{job_id}` may remain unchanged in Phase 1 and be visually reframed later.

---

## 5. Page-by-Page Build Plan

## 5.1 `Captain's Deck`

### Data needed now

- total Aurora missions
- completed missions
- running missions
- failed missions
- most recent missions
- last-7-days performance summary if available

### Sections

1. hero greeting
2. fleet cards for all three ships
3. Aurora quick stats
4. recent voyages
5. Captain brief / next attention panel

### Notes

- `The Aurora` card is live
- `The Freedom` and `The Lyra` cards should be visually complete but clearly marked as `coming next`

---

## 5.2 `The Aurora` Overview

### Data needed now

- current project count
- current projects
- mission counts by status
- recent missions
- latest metrics summary

### Sections

1. Aurora identity header
2. mission status cards
3. island/project cards
4. recent missions
5. quick actions

---

## 5.3 Aurora Missions

### Reuse

- current jobs list
- current HTMX polling fragment

### Changes

- rename page title and labels from generic jobs language to mission language
- keep same table structure in Phase 1
- preserve functionality exactly

---

## 5.4 Aurora Metrics

### Reuse

- current metrics page and data source

### Changes

- relocate under Aurora navigation
- update title and visual treatment

---

## 5.5 Aurora New Mission

### Reuse

- current trigger form and POST behavior

### Changes

- update copy from “New Run” to “New Mission”
- keep dry-run checked by default
- keep unattended trigger behavior

---

## 5.6 Freedom Placeholder

### Purpose

Create a beautiful, intentional empty state rather than leaving the ship invisible.

### Content

- ship meaning
- Freedom Five summary
- note that this ship will later hold personal life systems
- Nami as steward

---

## 5.7 Lyra Placeholder

### Purpose

Reserve the music ship in the product architecture from day one.

### Content

- ship meaning
- Genie summary
- Song Voyage preview
- note that song catalog and release planning are planned next

---

## 6. File-Level Changes

## Modify

| File | Planned changes |
|---|---|
| `dashboard.py` | add fleet routes, Aurora routes, redirects, page context helpers |
| `dashboard_store.py` | optionally add mission summary helper(s) |
| `templates/base.html` | replace current minimal nav with fleet shell |
| `templates/jobs.html` | retitle as Aurora missions |
| `templates/metrics.html` | retitle / restyle as Aurora metrics |
| `templates/trigger.html` | retitle / restyle as new mission |
| `static/style.css` | add fleet palette, layout system, cards, ship accents |

## Add

| File | Purpose |
|---|---|
| `templates/captains_deck.html` | fleet home |
| `templates/aurora.html` | Aurora overview |
| `templates/freedom.html` | Freedom placeholder |
| `templates/lyra.html` | Lyra placeholder |

---

## 7. Suggested Helpers

If the route code begins to feel repetitive, add simple non-domain-heavy helpers such as:

- `summarize_jobs(jobs)`
- `list_projects(root)`

Avoid premature generalized abstractions such as a full `Ship` model in this phase.

---

## 8. Visual System Foundation

## Shared palette

- navy base
- ivory surface
- antique gold accent
- aurora gradient accent
- indigo accent for Lyra

## Components to introduce now

- hero panel
- metric cards
- ship cards
- section headers
- empty-state cards
- pill badges
- responsive grid layout

## Design principle

Phase 1 should look substantially better than the current dashboard, but not yet require custom illustration assets to be finished.

---

## 9. Acceptance Criteria

Phase 1 is complete when:

1. `/` shows a Captain's Deck page, not the old jobs table
2. navigation includes `Captain's Deck`, `The Aurora`, `The Freedom`, and `The Lyra`
3. `The Aurora` overview is populated from real existing job data
4. `The Freedom` and `The Lyra` have polished placeholder pages
5. existing mission list, metrics, and new mission flow still work
6. existing dashboard tests are updated or extended and pass
7. no changes are required to the content pipeline runtime itself

---

## 10. Recommended Build Order

1. Add route skeletons and template files
2. Upgrade `base.html` navigation shell
3. Implement `Captain's Deck`
4. Implement `The Aurora` overview
5. Move / reframe current operations under Aurora
6. Add placeholder pages for `The Freedom` and `The Lyra`
7. Expand CSS
8. Update tests
9. Browser-check the dashboard visually

---

## 11. Deliberate Deferrals

Do **not** build these in Phase 1:

- illustrated crew portraits
- custom SVG ship diagrams
- character sheets
- ship-specific databases
- personal or music workflows
- generalized mission engine

These are valuable, but deferring them keeps Phase 1 fast, visible, and reversible.

---

## 12. Next Phase After This

Once Fleet Foundation is live, Phase 2 should focus on **The Aurora Upgrade**:

- crew registry
- character sheets
- mission workflow timeline
- island/project detail
- stronger mission storytelling

