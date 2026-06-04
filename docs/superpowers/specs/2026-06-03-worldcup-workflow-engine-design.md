# World Cup AI Workflow Engine — Design

**Date:** 2026-06-03
**Status:** Approved design direction; decomposed into sequenced sub-plans below
**Related:** [agentic-system-overview](../../worldcup_recap/agentic-system-overview.md) ·
[roadmap](../../worldcup_recap/roadmap.md) ·
[daily-recap design](2026-06-03-worldcup-daily-recap-design.md) ·
[daily-recap plan](../plans/2026-06-03-worldcup-daily-recap.md)

## Goal

Design a configurable **AI workflow engine** for World Cup content that can:

- **analyze past and future games** (review reports + previews/insights),
- **gather data for different use cases** from pluggable sources,
- **focus on different areas** — games / players / news / cup — as *lenses* over one
  shared data model,
- **generate outputs in multiple formats** — structured JSON, free text, and a
  beat-by-beat **video scenario** — via pluggable renderers,
- all wrapped in a **verification & feedback loop**.

A workflow is a **declarative YAML file** that composes **registered steps**. New
capabilities are new steps + new YAML, not engine rewrites. The Phase 1 daily recap
([its plan](../plans/2026-06-03-worldcup-daily-recap.md)) is the first concrete
workflow and is built first; the engine is then *extracted* from it.

## Design decisions (from brainstorming)

| Decision | Choice |
|----------|--------|
| Workflow composition | **Declarative YAML** pipelines of pluggable steps |
| Focus areas | **Lenses over one shared collection** (focus is a parameter) |
| Output formats | **JSON + free text + video scenario** (pluggable renderers) |
| Video scenario shape | **Beat-by-beat shot list** (narration + on-screen text + verified clip/image + duration per beat) |
| Analysis depth | **LLM insights from gathered data** (form, H2H, matchups, stakes); no predictive modeling |
| Temporal scope | **Past** (review) and **future** (preview); live is out of scope |
| Build order | **Daily-recap MVP first**, then extract the engine |

## Core concepts

```
   workflow.yaml ──▶ Runner ──▶ ordered / parallel Steps over a PipelineContext
        │                              │
   focus + inputs + steps      Step registry (dotted names):
                                 collect.*  analyze.*  enrich.*  render.*  deliver.*
                                       │
                          PipelineContext (shared model + telemetry)  +  Run store
```

### Step

The atomic unit. One tiny contract so a step can be a Python function, an **ADK
agent** (`AgentStep`), or an **external script** (`ScriptStep`):

```python
class Step(Protocol):
    name: str                 # dotted, e.g. "collect.espn_fixtures"
    requires: list[str]       # context keys it reads
    provides: list[str]       # context keys it writes
    async def run(self, ctx: PipelineContext, params: dict) -> PipelineContext: ...
```

Step categories (the registry namespaces):

- **`collect.*`** — pure data gathering, no LLM (e.g. `collect.espn_fixtures`,
  `collect.espn_match_detail`, `collect.espn_news`). Future: `collect.apifootball_stats`.
- **`analyze.*`** — LLM-reasoned insight & structuring over collected facts
  (`analyze.structure_sections`, `analyze.form_and_h2h`, `analyze.player_spotlight`,
  `analyze.stakes`).
- **`enrich.*`** — media discovery + the verify/feedback loop
  (`enrich.find_verify_media`), plus deterministic link attach.
- **`render.*`** — output formats (`render.json`, `render.text`,
  `render.video_scenario`).
- **`deliver.*`** — sinks (`deliver.file`, `deliver.email`, `deliver.slack`).

### PipelineContext (shared blackboard)

Carries everything between steps; this is what makes "collect once, lens later"
work:

```python
@dataclass
class PipelineContext:
    inputs: dict                 # date, team?, focus, mode, format(s)
    data: WorldCupData | None    # the shared domain model (collected facts)
    analysis: dict               # insights + structured sections from analyze.*
    media: dict                  # verified links keyed by need
    outputs: dict                # rendered artifacts keyed by format
    telemetry: dict              # per-step timings, verification stats
```

### Workflow (YAML)

```yaml
# workflows/match_preview.yaml
name: match_preview
focus: games                    # lens: games | players | news | cup
mode: future                    # past | future
inputs: { date: 2026-06-20, team: Brazil }
steps:
  - collect.espn_fixtures
  - collect.espn_news
  - analyze.form_and_h2h
  - analyze.stakes
  - group:                      # parallel block
      - enrich.find_verify_media
    parallel: true
  - render.json
  - render.video_scenario
  - deliver.email: { to: me@example.com }
```

### Runner

Loads YAML → resolves step graph from the registry → validates `requires`/`provides`
wiring → executes sequential steps and parallel groups → applies per-step
retry/timeout → records a run (inputs, step results, telemetry, artifacts) to a run
store → returns outputs. Graceful degradation: a non-fatal step failure is logged
and the pipeline continues where downstream steps allow.

## Shared domain model (collect once)

`collect.*` steps populate one model; lenses and renderers read from it:

```
WorldCupData:
  date / window
  matches: [ Match ]        # past (results, timeline, stats) AND future (fixtures)
  teams:   [ Team ]
  players: [ Player ]       # aggregated per day/tournament
  news:    [ NewsItem ]
  standings / groups / bracket
  sources_used: [str]
```

`Match` holds both **past** detail (score, timeline, player_stats, top_performers,
ESPN media/news) and **future** preview data (kickoff, odds, head_to_head, form) —
the same structure already specced for Phase 1's `RawMatch` + `PreviewMatch`.

## Focus lenses

Focus is a **parameter**, not a separate pipeline. Each `analyze.*` step and each
renderer consults `ctx.inputs.focus` to decide emphasis:

| Focus | Emphasis |
|-------|----------|
| `games` | match results/previews, timelines, drama, tactics |
| `players` | standout performers, ratings, player storylines |
| `news` | curated, verified news digest around teams/players |
| `cup` | standings, groups, bracket, qualification scenarios |

The shared collection means switching focus never re-collects data.

## Analysis layer (insights, not predictions)

`analyze.*` steps turn facts into reasoning, LLM-driven:

- `analyze.structure_sections` — classify a day into narrative sections (Phase 1's
  structure agent, generalized).
- `analyze.form_and_h2h` — recent form + head-to-head read for future matches.
- `analyze.stakes` — qualification/bracket implications.
- `analyze.player_spotlight` — who mattered and why.

No quantitative forecasting (xG models, simulated win probabilities) — explicitly
out of scope.

## Verification & feedback loop (reusable)

`enrich.find_verify_media` is the generalized Phase 1 loop:

```
need ─▶ FINDER (google_search + YouTube) ─▶ candidate
              ◀── refine with reason ──┐         │
                                       ▼         ▼
                              VERIFIER: relevant to THIS subject/match/day?
                          accepted ─▶ attach   |   rejected ─▶ retry (≤3) then drop
```

It is source-agnostic and reused by every workflow. Telemetry (searched / accepted /
rejected / dropped) is recorded in `ctx.telemetry`. An **optional** `analyze.critic`
step can gate output quality (request a re-render) — designed as a seam, built only
if needed.

## Renderers (output formats)

Each renderer reads `ctx.analysis` + `ctx.media` and writes `ctx.outputs[format]`:

- **`render.json`** — schema-validated structured artifact.
- **`render.text`** — free-text / Markdown prose (the engaging recap).
- **`render.video_scenario`** — a **beat-by-beat shot list** for a video:

```json
{
  "title": "...", "estimated_duration_s": 90,
  "beats": [
    { "n": 1, "narration": "...", "on_screen_text": "...",
      "suggested_media": { "url": "<verified clip/image>", "type": "clip|image", "source": "..." },
      "duration_s": 8 }
  ]
}
```

The video scenario reuses **verified** media from `enrich.find_verify_media`, so no
unverified clip ever lands in a beat.

## How Phase 1 maps onto the engine

The daily recap built in [the Phase 1 plan](../plans/2026-06-03-worldcup-daily-recap.md)
is exactly this workflow once the engine exists:

```yaml
# workflows/daily_recap.yaml  (post-extraction)
name: daily_recap
focus: cup
mode: past
inputs: { date: 2026-06-11 }
steps:
  - collect.espn_fixtures
  - collect.espn_match_detail
  - collect.espn_news
  - analyze.structure_sections
  - enrich.find_verify_media
  - render.json
  - render.text
  - deliver.file
```

Phase 1's `collect`, structure/synthesis agents, and the `find_and_verify` loop are
written as standalone functions now and **wrapped as registered steps** during
engine extraction — minimal rework, because Phase 1's boundaries already match the
step categories.

## Decomposition into sub-plans (sequenced)

Each sub-plan is independently shippable and testable.

| Plan | Scope | Depends on | Roadmap phase |
|------|-------|------------|---------------|
| **A — Daily Recap MVP** *(plan written)* | Vertical slice: hardcoded daily recap, JSON+MD, CI | — | 1 |
| **B — Workflow engine core** | `Step`/`PipelineContext`/`Registry`/`Runner` + YAML loader + `ScriptStep`/`AgentStep`; re-express daily_recap as YAML by wrapping Plan A pieces as steps | A | 2 |
| **C — Shared model + lenses + analysis** | `WorldCupData` model; expand `collect.*`; focus lenses; `analyze.form_and_h2h` / `stakes` / `player_spotlight`; future-game preview mode | B | 5 (data/intel) |
| **D — Renderers** | `render.json` / `render.text` / `render.video_scenario` as steps | B (C for richer input) | 5 (outputs) |
| **E — Delivery + scheduling** | `deliver.*` sinks (email/slack/web), run store, backfill, scheduling tier | B | 3 + 4 |

**Critical path to the full vision:** A → B → (C, D in parallel) → E. B is the
keystone — it turns everything else into pluggable steps.

## Non-goals (this design)

- No predictive/quantitative modeling.
- No live in-match processing.
- No visual workflow builder UI (YAML only; UI is a later roadmap item).
- No multi-sport generalization yet (World Cup domain model first).

## Open items to resolve in sub-plan B

- Run-store backend (start: JSON files under `data/runs/`; later: Postgres from the
  planned backend).
- Parallel-group + conditional syntax details in the YAML schema.
- Whether `deliver.*` runs inside the Runner or as a separate post-step (lean: inside,
  as ordinary steps).
