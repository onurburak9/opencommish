# World Cup 2026 — Agentic Content System (Main Objective)

**Date:** 2026-06-03
**Status:** Vision / north-star — frames the concrete specs below
**Related:**
- Design (first deliverable): [`docs/superpowers/specs/2026-06-03-worldcup-daily-recap-design.md`](../superpowers/specs/2026-06-03-worldcup-daily-recap-design.md)
- Data research: [`data-source-discovery.md`](./data-source-discovery.md)

## The objective

Build an **agentic system** that turns raw World Cup 2026 happenings into
publish-ready content. It runs in three stages:

```
        ┌──────────────┐      ┌────────────────────┐      ┌──────────────────┐
        │  1. FIND      │ ───▶ │ 2. VERIFY & ENRICH │ ───▶ │ 3. CREATE OUTPUTS │
        │  data         │      │  links / media     │      │  recaps, previews │
        └──────────────┘      └────────────────────┘      └──────────────────┘
        deterministic          agentic + feedback loop      LLM narrative
        (no LLM)               (find → verify → retry)       (mode-specific)
```

The **daily end-of-day recap** is the first concrete output. The same engine is
designed to later produce match previews, single-match reports, and news digests —
because stages 1 and 2 are mode-agnostic and reusable.

## Stage 1 — FIND (deterministic data gathering)

Pull the verifiable facts first, with **no LLM in the loop**, so the narrative is
always grounded in real data:

- **Fixtures & results** — schedule, scores, status (ESPN `scoreboard`).
- **Match detail** — goal/card/sub timeline with assists, per-player stats,
  formations, venue, attendance, officials (ESPN `summary`).
- **Standings / groups / bracket** — qualification picture.
- **Preview & historical data** — odds, win probabilities, head-to-head history,
  recent form for upcoming fixtures.
- **Native media & news** — ESPN highlight videos, news articles.

Source strategy: **ESPN** (keyless) is the primary provider today, behind a
swappable `StatsProvider` interface. **API-Football** (paid) is a documented future
provider for advanced stats (player ratings, possession, xG). See the discovery
doc for the full endpoint analysis.

## Stage 2 — VERIFY & ENRICH (the agentic core)

Raw data is enriched with media links — and **every searched link is verified
before it is trusted**. This is where the feedback loop lives:

```
        media need ─▶ FINDER (google_search + YouTube) ─▶ candidate link
                                                              │
                                  ◀── refine query with reason┤
                                                              ▼
                                              VERIFIER: relevant to THIS
                                              match / player / day?
                                          ┌──────────┴───────────┐
                                       relevant               not relevant
                                          │                  (≤3 retries,
                                          ▼                   then drop)
                                    attach to output
```

- **Deterministic links** from ESPN (recap URL, native highlight videos, news
  hrefs, headshots) are trusted directly.
- **Searched links** — YouTube highlights/interviews and Google-searched
  photos/news — fill the gaps ESPN can't, and run the **finder → verifier →
  bounded-retry** loop. Nothing searched is published unverified.
- Verification telemetry (searched / accepted / rejected / dropped) is recorded for
  every run.

This stage is **output-agnostic**: it verifies and enriches facts regardless of
which content type consumes them.

## Stage 3 — CREATE OUTPUTS (mode-specific narrative)

An LLM synthesis layer turns verified, enriched facts into engaging content. This
is the **only mode-specific stage**:

| Output | Status | Reuses stages 1+2 |
|--------|--------|-------------------|
| **Daily recap** (end-of-day) | **Building now** | ✅ |
| Match preview (pre-game odds/form/H2H) | Future | ✅ |
| Single-match report | Future | ✅ |
| News digest | Future | ✅ |

Each output is a structured **JSON + Markdown** artifact under
`data/worldcup_recaps/`, schema-validated, with verified media attached.

## Why this shape

- **Grounded:** deterministic FIND stage means the LLM never invents scores,
  scorers, or timelines.
- **Trustworthy media:** the VERIFY loop prevents broken/irrelevant/unofficial
  links from reaching readers.
- **Cheap to extend:** new content types are new prompts in stage 3 — the costly
  data + verification machinery is built once and reused.
- **Cost-aware:** ESPN keyless + Gemini Flash means the daily recap runs for free;
  paid sources are optional, pluggable upgrades.

## First milestone

Ship the **daily recap** for the opening match (2026-06-11), per the design spec.
Everything in stages 1 and 2 built for it is the foundation the later output modes
stand on.
