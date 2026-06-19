# Recap JSON Schema Enforcement — Design

**Date:** 2026-06-18
**Status:** Approved design; ready for implementation plan
**Module:** `worldcup_recap/`

## Problem

The daily-recap JSON has **no enforced schema**:
- `worldcup_recap/schemas/recap_output.json` is **orphaned** — not referenced in code, and `jsonschema` isn't a dependency.
- The only runtime check, `validate_output()`, asserts **5 top-level keys exist** — nothing structural.
- The schema is **stale**: it lists `source_data`/`sections` but omits everything added since (`content.games`, `metadata.timezone`, `metadata.verification`, `source_data_file`).

Consequence: the deterministic parts (`content.games[]`, `metadata`) are code-built and fairly consistent, but the **LLM-generated `content.sections[]` are polymorphic and drift** (fields omitted/renamed/added run-to-run). Any consumer that renders the JSON to HTML/video could break or render blanks.

## Goal

Guarantee the recap JSON is a **consistent, always-valid, inclusive contract** that downstream renderers (HTML, video scenarios) can rely on without defensive guards.

## Decisions (from brainstorming)

| Decision | Choice |
|----------|--------|
| Mechanism | **Pydantic v2 models as the single source of truth** (already installed via google-adk; no new dep) |
| On violation | **Coerce / repair to always-valid** — never lose the whole recap |
| Contract scope | **Whole document**, with **hardened sections** (predictable shape per type) |
| Unknown/extra fields | **`extra="allow"`** — preserve anything useful, never silently drop |
| Inclusiveness | **Inclusive but lean** — recap carries all rendering-useful fields (with empty defaults); heavy raw per-player stats stay in `{date}.source.json` |
| Schema artifact | **Auto-generated** from the models (`model_json_schema()`); a test fails on drift |
| Out of scope | `{date}.source.json` (reference data); the internal collection dataclasses (`RawMatch`, etc.) |

## Architecture

### 1. `worldcup_recap/models.py` — the contract (new)

Pydantic v2 models; every model sets `model_config = ConfigDict(extra="allow")` (preserve extras) and gives every field an empty/`None` default so the dumped shape is always complete.

**Deterministic core:**
```
RecapOutput        recap_id, date, generated_at, metadata, content, source_data_file
Metadata           matches_count, sources_used[], timezone, verification, generation_time_seconds
Verification       searched, accepted, rejected, dropped, details[VerificationDetail]
VerificationDetail owner, need{kind,subject,context}, status, accepted_url, attempts[VerificationAttempt]
VerificationAttempt attempt, raw_url, resolved_url, outcome, reason
Content            headline, summary, games[Game], sections[Section]
Game               match_id, stage, status, home[TeamSide], away[TeamSide], venue,
                   attendance, media[GameMedia], scorers[Scorer], top_performers[Performer],
                   timeline[TimelineEvent], news[NewsItem]
TeamSide           team, score, logo_url, team_url
GameMedia          recap_url, highlight_url
Scorer             player, minute, profile_url
Performer          name, team, goals, saves, note, profile_url, headshot_url
TimelineEvent      minute, type, player, text, scoring_play
NewsItem           headline, url, published
```

`Game` is **inclusive** (timeline of key events, top_performers, attendance) so renderers have what they need; the bulk raw `player_stats` (52× per match) remains in `{date}.source.json`, joinable via `match_id`.

**Sections (polymorphic, discriminated union on `type`):** shared base gives `title`, `narrative`.
```
MatchOfDaySection    type, title, narrative, home_team, away_team, score, facts, match_id
ResultsRoundupSection type, title, narrative, games[ResultGame(matchup, note, match_id)]
PlayerSpotlightSection type, title, narrative, players[SpotlightPlayer(name,team,line,context,media[PlayerMedia])]
GroupWatchSection    type, title, narrative, notes
StorylinesSection    type, title, narrative, stories[Story(headline, summary)]
LookingAheadSection  type, title, narrative, upcoming[UpcomingFixture(home,away,kickoff,storyline,odds[OddsSummary],news[NewsItem])]
PlayerMedia          profile_url, headshot_url, interview_url
OddsSummary          favorite, line, over_under
Section = Annotated[Union[...6 types...], Field(discriminator="type")]
```

### 2. Coercion → always-valid

`build_final_output` keeps building plain dicts (existing `build_games`, `_clean_sections`, `_enrich_upcoming` — `build_games` extended to include `timeline`/`top_performers`/`attendance`), then runs them through the models as a **final gate**:

- **Sections coerced individually** via `TypeAdapter(Section)`: each section validated on its own; an unknown `type` or otherwise unrepairable section is **dropped and logged**, never failing the whole document.
- The full doc is then built as `RecapOutput.model_validate({...})`:
  - missing fields → **defaults** (empty string / `None` / `[]`);
  - unknown fields → **kept** (`extra="allow"`);
  - coercible types (e.g. score `"3"`→`3`) → coerced.
- Return `recap.model_dump(mode="json")` (a dict, so `main.py`/`json.dumps` are unchanged). The result is **always schema-valid with a complete, predictable shape**.

`validate_output()`'s 5-key check is replaced by model validation. A `coerce_sections(list) -> list[Section]` helper isolates the drop-invalid logic.

### 3. Schema auto-generation + drift guard

- `scripts/gen_schema.py` writes `RecapOutput.model_json_schema()` (indented JSON) to `worldcup_recap/schemas/recap_output.json`.
- A unit test asserts the **committed schema equals the freshly generated one** — any model change not regenerated fails the suite. The schema becomes a live, always-accurate contract for HTML/video consumers (and can be published).

### 4. Integration

- `worldcup_recap/synthesize.py`: `build_final_output` constructs/dumps via `RecapOutput`; `build_games` adds `timeline`/`top_performers`/`attendance`; remove the old `_REQUIRED_KEYS`/`validate_output` shallow check (or keep a thin alias that calls model validation).
- `main.py`: unchanged (still receives a dict, dumps JSON, writes `.source.json` + `.md`).
- `render_markdown`: unchanged in behavior; it reads the same (now-guaranteed) fields.

## Error handling

- A malformed LLM section never breaks the run — it's dropped; siblings and the deterministic core survive.
- A completely empty/invalid synthesis still yields a valid `RecapOutput` (defaults + empty lists).
- Network/collection failures are upstream and already degrade gracefully; the model gate is the last line ensuring the written file is always valid.

## Testing

`tests/unit/worldcup_recap/test_models.py`:
- **Round-trip:** build a representative dict → `RecapOutput.model_validate` → `model_dump` has the complete shape.
- **Coercion:** missing field → default present; unknown field → preserved (`extra="allow"`); section with unknown `type` → dropped; malformed section → dropped while valid siblings remain; `score:"3"` → `3`.
- **Inclusive games:** `build_games` output includes `timeline`, `top_performers`, `attendance`.
- **Schema drift test:** `model_json_schema()` == committed `recap_output.json`.
- Update `test_synthesize.py` for the new `build_final_output` return shape (e.g. `content.games[].timeline` present; no `source_data` key).

Run: `uv run python -m pytest tests/unit/worldcup_recap/ -v -o "addopts="`.

## Non-goals

- No change to the collection layer (`RawMatch`/`PreviewMatch` dataclasses) or `{date}.source.json` shape.
- No constraining of the Gemini call itself (structured-output) — coercion handles drift; that's a possible future optimization.
- No HTML renderer in this work — this only guarantees the contract it would consume.
