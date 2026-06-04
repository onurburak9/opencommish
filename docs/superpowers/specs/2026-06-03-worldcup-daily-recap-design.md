# World Cup 2026 — Daily Recap Agentic Pipeline (Design)

**Date:** 2026-06-03
**Status:** Approved design, ready for implementation planning
**Companion research:** [`docs/worldcup_recap/data-source-discovery.md`](../../worldcup_recap/data-source-discovery.md)

## Goal

Build an agentic pipeline that, given a date during the FIFA World Cup 2026
(2026-06-11 → 2026-07-19), produces a comprehensive **daily recap source** — a
structured JSON + Markdown artifact covering that day's matches, results, standout
players, storylines, group/bracket implications, and **verified** media links
(highlight videos, photos, news), with an engaging English narrative.

This mirrors the existing `nba_recap/` module (Google ADK + Gemini 2.5 Flash) and
lives as a new standalone sibling module `worldcup_recap/`. The downstream use of
the generated output is out of scope; this project builds the recap-source
generator only.

## Non-Goals

- No web/frontend, no database, no API endpoint. File output only.
- No live in-match updates; the pipeline runs once per day for a completed day.
- No API-Football integration code in this iteration (see "Future seams").
- No narrative critic/rewrite loop — synthesis is single-pass.

## Decisions (from brainstorming)

| Decision | Choice |
|----------|--------|
| Primary data source | **ESPN** public soccer API (keyless), slug `fifa.world` |
| Advanced-stats source | API-Football v3 — **deferred**; documented seam only |
| Recap language | **English** |
| Media handling | Find links, then **verify relevance** before inclusion |
| Verification on reject | **Bounded retry (≤3)** with refined query, then drop |
| Loop scope | **Media links only** (synthesis is single-pass) |
| Module placement | New `worldcup_recap/` module, mirrors `nba_recap/` |
| Provider strategy | ESPN-only now, behind a swappable `StatsProvider` interface |
| Recap modes | **Daily end-of-day recap only** now; preview/match modes deferred |
| Reusable core | Collect + verification built **mode-agnostic** so future modes reuse them |
| Look-ahead | **Rich preview block** — gather odds, H2H/historical, form, news for next-day fixtures |

## Architecture

Four phases, mirroring `nba_recap/`:

```
collect (pure Python)  →  structure (LLM)  →  enrich + verify (LLM loop)  →  synthesize (LLM)
```

### Mode-agnostic, reusable core

Although this iteration ships only the **daily end-of-day recap**, the phases are
split so the expensive, reusable machinery is **mode-agnostic**:

- **`collect` (data gathering)** and **`enrich + verify` (media discovery +
  verification loop)** know nothing about recap mode. They produce/validate raw
  facts and verified links for *any* consumer (daily review, future preview, future
  single-match report, news digest).
- Only **`structure`** (which sections, what to emphasize) and **`synthesis`**
  (the prose) are recap-mode-specific. Adding a `preview` or `match` mode later
  means new prompts + section types, **not** new collection or verification code.

This is why collect also gathers preview/historical fields now (see Phase 1): the
data is mode-agnostic and feeds both today's `looking_ahead` block and tomorrow's
preview mode.

### Module layout

```
worldcup_recap/
  __init__.py
  collect.py                  # Phase 1: ESPN collection (no LLM)
  providers/
    __init__.py
    base.py                   # StatsProvider protocol/ABC
    espn.py                   # EspnProvider (only impl now)
  agents/
    __init__.py
    structure_agent.py        # classify day → narrative sections
    media_finder_agent.py     # google_search for gap media
    media_verifier_agent.py   # judge link relevance (drives loop)
    synthesis_agent.py        # engaging English prose
  prompts/
    structure.md
    media_finder.md
    media_verifier.md
    synthesis.md
  pipeline.py                 # orchestrates phases + verification loop
  synthesize.py               # build_final_output + render_markdown
  schemas/
    recap_output.json
  main.py                     # CLI
data/worldcup_recaps/         # output dir (+ .gitkeep)
tests/unit/worldcup_recap/    # unit tests + saved ESPN JSON fixtures
.github/workflows/worldcup_recap.yml
```

## Phase 1 — Collect (pure Python, no LLM)

`collect(target_date)` returns a `CollectedData` dataclass. All data comes through
the `StatsProvider` interface; the only implementation is `EspnProvider`.

### `StatsProvider` interface (`providers/base.py`)

A minimal protocol so a second source can be added later without touching
`collect.py` / `pipeline.py`:

```python
class StatsProvider(Protocol):
    name: str
    def matches_for_date(self, date: str) -> list[RawMatch]: ...
    def upcoming(self, date: str) -> list[dict]: ...
    def standings(self) -> list[dict]: ...
```

`collect()` selects the provider (ESPN) and assembles `CollectedData`.

### ESPN endpoints used (verified 2026-06-03)

- `GET /soccer/fifa.world/scoreboard?dates=YYYYMMDD` → day's events (id, teams,
  score, status, venue).
- `GET /soccer/fifa.world/summary?event={id}` → per match: `header` (final score,
  winner), `keyEvents` (goal/card/sub timeline with assist text), `rosters`
  (per-player stats + formation), `gameInfo` (venue/attendance/officials),
  `videos` (ESPN highlight clips), `news`.
- `GET /soccer/fifa.world/standings` → group tables.
- next-day `scoreboard` → `upcoming`, then `summary?event={id}` per upcoming match
  for the **rich preview block**: `odds` + `pickcenter` (betting/win
  probabilities), `headToHeadGames` (historical meetings), `boxscore.form` (recent
  results per team), plus `news` for those fixtures.

### Data model

```
CollectedData:
  date: str
  matches: list[RawMatch]
  standings: list[dict]          # group tables
  upcoming: list[PreviewMatch]   # next-day fixtures w/ rich preview data
  sources_used: list[str]

PreviewMatch:
  match_id: str
  stage: str
  home_team / away_team: str
  kickoff: str                   # ISO datetime
  odds: dict | None              # from summary.odds / pickcenter
  win_probabilities: dict | None
  head_to_head: list[dict]       # historical meetings (summary.headToHeadGames)
  home_form / away_form: list[str]  # recent results (boxscore.form)
  news: list[dict]               # {headline, url, published}

RawMatch:
  match_id: str                  # ESPN event id
  stage: str                     # "Group A", "Round of 32", ...
  home_team / away_team: str
  home_score / away_score: int
  status: str
  timeline: list[dict]           # {minute, type, player, assist, text, scoring_play}
  top_performers: list[dict]     # derived: scorers, assisters, GK saves, ratings(None now)
  player_stats: list[dict]       # from rosters
  venue: str
  attendance: int | None
  espn_recap_url / espn_videos: media from summary
  news: list[dict]               # {headline, url, published}
```

Derivation rules (pure functions, unit-tested):
- `top_performers`: players with goals/assists first, then by minutes/role; GK with
  most saves included. Hat-tricks flagged.
- `timeline`: filtered to Goal / Card / Substitution / VAR events.

## Phase 2 — Structure agent (Gemini)

Input: serialized `CollectedData`. Output: JSON `{ "sections": [...] }`. Section
types:

- `match_of_day` — the headline match (drama, stakes, margin, upset).
- `results_roundup` — all other results as quick hits.
- `player_spotlight` — standout performers (scorers, multi-goal, GK heroics).
- `group_watch` (group stage) / `bracket` (knockout) — standings/qualification
  implications.
- `storylines` — narrative threads (upsets, records, debuts, controversies).
- `looking_ahead` — tomorrow's fixtures as a **rich preview block**: per headline
  fixture, odds/win-probabilities, head-to-head history, recent form, and a couple
  of verified preview news/media links (reuses the Phase 3 loop).

Each section carries the structured facts synthesis needs **plus declared
`media_needs`** (e.g. `{kind: "interview", subject: "player name", context: "..."}`)
that drive Phase 3 searched-media discovery.

## Phase 3 — Enrich + verification feedback loop

Media falls into two buckets:

**Deterministic** (from ESPN `summary`/`news`) — included directly, no search:
match recap URL, ESPN highlight `videos`, news article hrefs, player headshots.
High trust, same model as `nba_recap`.

**Searched** (gaps ESPN can't fill — declared `media_needs`) — handled by the loop.
Backends: `google_search` (news, photos) **and YouTube** (official FIFA highlight
channel, player/manager post-match interviews, condensed-match clips). Every
searched link — YouTube included — passes through verification; nothing searched is
trusted blindly.

1. `media_finder_agent` (`google_search` + YouTube search) proposes a candidate URL
   given match/player/date context. YouTube results are preferred for
   highlight/interview `media_needs`.
2. `media_verifier_agent` judges relevance → `{relevant: bool, confidence: float,
   reason: str}`. Relevance = "does this link actually correspond to *this*
   match/player/day?" For YouTube it checks title/channel/description (official
   source preferred) against the match teams + date.
3. **Bounded retry:** if not relevant, the verifier's `reason` is fed back into the
   finder for a refined query. Max **3 attempts**; if still no match, the field is
   left `null`.

Searched-media needs are processed in parallel across sections via
`asyncio.gather`, matching `nba_recap`'s enrichment style. Verification telemetry
(attempts, accepts, rejects, drops) is recorded in output `metadata.verification`.

## Phase 4 — Synthesis agent (Gemini, English)

Single-pass. This is the agent that gets the most prompt-engineering investment —
the explicit goal of writing the day's "scenario" in an engaging way. The prompt
encodes: voice/tone, a dramatic arc (hook → match of the day → standout players →
storylines → looking ahead), and instructs the model to draw narrative detail from
the `keyEvents` timeline text. Output: `{ headline, summary, sections[] }` with the
verified media attached per section.

## Output

`data/worldcup_recaps/YYYY-MM-DD.{json,md}`, validated against
`schemas/recap_output.json`:

```
recap_id, date, generated_at,
metadata: { matches_count, sources_used, subagents_spawned,
            verification: { searched, accepted, rejected, dropped },
            generation_time_seconds },
content:  { headline, summary, sections[] }
```

Markdown rendered from the same structure for human reading.

## Error handling

Graceful degradation per phase (mirrors `nba_recap`):
- Collect: a failed `summary` fetch yields a minimal match record; pipeline
  continues. API errors logged, not fatal.
- Structure: invalid JSON → empty `sections`.
- Enrich: exhausted retries → `null` media; verifier/finder exception → drop that
  need, keep section.
- Synthesis: invalid JSON → fallback headline/summary with structured sections.

## Testing

Unit tests in `tests/unit/worldcup_recap/`, mirroring `tests/unit/nba_recap/`:
- **collect/providers**: parse saved ESPN JSON fixtures (captured 2026-06-03 from a
  real completed friendly + WC fixtures) into `RawMatch`; assert timeline,
  top_performers derivation, score parsing, graceful handling of missing fields.
- **verification loop**: mock finder/verifier; assert retry-then-drop after 3
  attempts, accept on first success, feedback-reason passed to finder.
- **synthesize**: `build_final_output` shape, schema validity, markdown rendering.

Run: `python -m pytest tests/unit/ -v -o "addopts="` (all existing + new pass).

## CLI & CI

```
python worldcup_recap/main.py YYYY-MM-DD [--dry-run] [--no-agents]
  --dry-run     collect only, print matches, skip LLM
  --no-agents   collect + structure only, skip enrich + synthesis
```

GitHub Actions `worldcup_recap.yml`: daily cron during the tournament (commented
until a live run is verified), `workflow_dispatch` enabled. Secret:
`GOOGLE_API_KEY`. Commits output to `data/worldcup_recaps/`.

## Future seams (documented, not built now)

- **API-Football provider** (`providers/apifootball.py`): adds player ratings,
  possession, pass %, shot maps, xG. Endpoints documented in the discovery doc.
  Activates behind a paid `APIFOOTBALL_KEY` + an `--advanced` flag, matched to ESPN
  matches by team-name + date. The `StatsProvider` interface and the optional
  `top_performers.rating`/advanced fields exist precisely to accept this later
  without reworking collect.
- **News breadth**: GNews / NewsAPI / YouTube Data API as additional searched-media
  backends behind the same finder→verifier loop.
- **Narrative critic loop**: optional Phase 4b critic agent if synthesis quality
  needs gating.
