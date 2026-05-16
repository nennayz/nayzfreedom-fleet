# Aurora Operating Workflow v2

**Status:** Draft for implementation
**Date:** 2026-05-16
**Scope:** NayzFreedom Fleet, The Aurora dashboard, page/project PMs, central crew specialists

## Purpose

Aurora v1 behaves mostly like a single content pipeline:

```text
Robin -> Mia -> Zoe -> Bella -> Lila -> Nora -> Roxy -> Emma -> Publish
```

Aurora v2 should behave like a content operating system. It must support:

1. Discovering and validating new pages/projects.
2. Operating existing pages with a dedicated PM.
3. Planning daily content calendars with fixed minimum output requirements.
4. Producing articles, infographics, short videos, and long videos in parallel.
5. Running QA before publishing.
6. Reading engagement after publishing and turning results into scale, repair, or lesson-learned loops.
7. Allowing PMs and specialists to ask for clarification or route work sideways, not only forward.

The PM owns the page. The central Aurora crew provides specialist help.

## Operating Model

Aurora has two layers:

| Layer | Responsibility | Examples |
|---|---|---|
| Central Aurora Team | Shared specialists used by every project | Robin, Mia, Zoe, Nora, Roxy, Emma, Market & Monetization Analyst, Video Producer, Archivist, Growth Analyst |
| Page PM Squad | Dedicated owner and production context for one page | Slay for Slay Hack, future PMs for future pages |

The central team should not replace the PM. The PM decides what the page should do. The central team supplies research, production, QA, distribution, and learning support.

## Mission Types

Aurora v2 should introduce four mission types.

### 1. `new_project_discovery`

Used when the team is exploring a new page or project.

Goal: find page concepts with real audience, viral, and monetization potential.

Inputs:

- Captain brief or open research theme.
- Candidate niche or platform signal.
- Existing trend or creator/page example.
- Optional constraints: platform, language, monetization type, visual style.

Core flow:

```text
Robin frames the discovery mission
Mia scans trends and platform signals
Market & Monetization Analyst studies audience, competitors, and revenue paths
Zoe develops page concepts and initial content angles
Archivist checks memory, Drive, Notion, and prior project history
Nora reviews feasibility and risk
Robin packages the proposal for Captain review
```

Outputs:

- Page concept.
- Target audience.
- Platform focus.
- Content pillars.
- Monetization paths.
- Viral thesis.
- 7-day validation plan.
- Asset needs.
- Risks and open questions.
- Recommendation: build, test, watch, or reject.

Acceptance criteria:

- The concept has a clear audience and repeatable content engine.
- There is at least one plausible monetization path.
- There are at least 20 initial content ideas.
- There is a practical 7-day test plan.
- Duplicates or conflicts with existing Fleet projects are checked.

### 2. `content_calendar_plan`

Used when an existing page PM plans a day or week of content.

Goal: produce a structured content slate that satisfies daily minimums and fits the page strategy.

Default daily minimum:

```yaml
articles: 2
infographics: 2
videos:
  short_video:
    count: 1
    duration: "15-40 seconds"
  long_video:
    count: 1
    duration: "60-180 seconds"
    requires_storyboard: true
```

Core flow:

```text
PM reviews performance, calendar, and goals
Mia brings current signals
Archivist checks Drive and Notion for prior topics and duplicates
Zoe proposes angles and hooks
PM selects the daily slate
Robin turns the slate into production tickets
Nora checks coverage and risk before production begins
```

Outputs:

- Daily or weekly calendar.
- Per-item brief.
- Content type.
- Target platform.
- Hero character or asset need.
- Owner/specialist assignment.
- Deadline and publish window.
- QA expectations.

Acceptance criteria:

- The daily minimum is satisfied or explicitly waived by the Captain.
- Each item has a clear objective: reach, save, share, revenue, community, or learning.
- Existing content history is checked to reduce duplication.
- Video work includes format and storyboard requirements before production.

### 3. `production_batch`

Used when a PM-approved slate is turned into production work.

Goal: produce the assets needed for the daily content slate.

Core flow:

```text
PM dispatches tickets
Article Writer/Bella writes article copy
Lila builds infographic direction
Video Producer builds scene plans, script handoff, prompts, tools, and asset lists
Nora QA checks each item
Roxy packages captions, hashtags, timing, and CTAs
Emma prepares community responses and FAQ
PM approves or sends back
Publish runs after approval
```

Production ticket types:

| Ticket type | Owner | Required output |
|---|---|---|
| `article` | Bella or Article Writer | Headline, body, CTA, platform adaptation |
| `infographic` | Lila | 4:5 or platform-specific visual brief, copy blocks, visual prompt |
| `short_video` | Video Producer, Bella, Lila | 15-40 sec script, scene plan, visual prompts, CTA |
| `long_video` | Video Producer, Bella, Lila | 60-180 sec storyboard, scene timing, script, prompts, asset checklist |
| `community_post` | Emma | Group/Messenger prompt, moderation guide |
| `distribution_pack` | Roxy | Captions, hashtags, post timing, platform CTAs |

### 4. `performance_review`

Used after content is published.

Goal: convert engagement into the next creative decision.

Core flow:

```text
Growth Analyst pulls platform metrics
Archivist links metrics to the original content ticket and assets
Roxy interprets platform packaging performance
Zoe proposes follow-up creative routes
PM decides scale, repair, or lesson-learned
Robin records the loop in the mission history
```

Metrics to track:

- Views.
- Watch time and retention.
- Shares.
- Saves.
- Comments.
- Likes.
- Follower/subscriber conversion.
- Clicks, if available.
- Revenue signal, if available.
- Qualitative comments and questions.

Decision buckets:

| Bucket | Meaning | Next action |
|---|---|---|
| Scale | Strong content with repeatable signal | Make sequel, remix, series, cross-platform version |
| Repair | Mixed result with clear fix | Change hook, thumbnail, caption, timing, length, or angle |
| Lesson learned | Weak result or wrong direction | Store as avoid/rethink note and do not repeat unchanged |

## Roles

### Existing Aurora Crew

| Role | v2 responsibility |
|---|---|
| Robin | Mission orchestrator, route owner, escalation point |
| Mia | Trend, platform, and signal scout |
| Zoe | Idea generator, hook and angle builder |
| Bella | Article, script, and copy writer |
| Lila | Visual director, prompt direction, visual package owner |
| Nora | QA gate, revision routing, quality risk owner |
| Roxy | Distribution, captions, hashtags, timing, platform packaging |
| Emma | Community, FAQ, comments, group/Messenger support |

### New Central Specialists

| Role | Responsibility |
|---|---|
| Market & Monetization Analyst | Audience, competitor, niche, viral thesis, and revenue path analysis for new project discovery |
| Video Producer | Storyboard-first video planning, scene timing, tool-aware prompt packages, and video asset requirements |
| Archivist | Drive/Notion/history lookup, duplicate prevention, asset provenance, and durable lesson records |
| Growth Analyst | Engagement analysis and scale/repair/lesson decision support |

### Role Modes, Not Separate People

These responsibilities should stay as modes under existing roles until the dashboard shows a real bottleneck:

| Mode | Lives under | Reason |
|---|---|---|
| Calendar planning | PM and Robin | PM chooses priorities; Robin turns the slate into tickets |
| Infographic production | Lila | It is part of visual direction, not a separate routing lane |
| Lesson library | Archivist | Lesson records and duplicate prevention use the same memory system |
| Monetization strategy | Market & Monetization Analyst | Audience validation and revenue path should be decided together |

## Interactive Routing

Aurora v2 must allow sideways and backward movement.

Examples:

- Nora sends a video back to Video Producer if the scene flow is unclear.
- Lila asks Bella for tighter visual language if a script is too abstract.
- Roxy asks PM to choose the primary platform if captions conflict.
- Archivist blocks an idea if Notion/Drive shows it was already produced.
- Growth Analyst sends a winner back to Zoe for sequels.
- PM asks Market & Monetization Analyst for extra research before approving a new page.

## Anti-Duplication Rules

- Mia owns live signals; Market & Monetization Analyst owns business viability.
- Zoe proposes routes; the PM selects priorities and final slate.
- Bella owns words; Video Producer owns scene timing, video structure, and generation package.
- Lila owns visual language; Video Producer requests visual assets instead of replacing Lila.
- Nora checks quality and risk; the PM makes page-level business decisions.
- Growth Analyst diagnoses performance; Roxy turns that diagnosis into distribution changes.
- Archivist owns duplicate checks before production and lesson links after performance review.

Every production ticket should carry:

- `decision_owner` for final approval.
- `priority` so not every item competes equally.
- `platform_primary` when multiple platforms are listed.
- `acceptance_criteria` before production begins.
- `evidence_links` or source signals for research traceability.
- `asset_requirements` and `asset_sources` for Drive/Veo3/reference control.
- `linked_lessons` so prior learning affects new work.

The dashboard should eventually show these as "requests" or "blocks", not as failures.

## Slay Hack Page Operation

Slay Hack is the first concrete Page Operation target for v2.

Canonical project slug:

```text
slay_hack
