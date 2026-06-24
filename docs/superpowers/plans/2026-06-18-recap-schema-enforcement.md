# Recap JSON Schema Enforcement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the World Cup daily-recap JSON an always-valid, inclusive contract by routing the final output through Pydantic v2 models that coerce/repair to a complete, predictable shape, with an auto-generated schema and a drift-guard test.

**Architecture:** A new `worldcup_recap/models.py` holds Pydantic v2 models that are the single source of truth for the recap shape. `build_final_output` keeps building plain dicts, then runs them through `RecapOutput.model_validate(...)` as a final gate (defaults fill gaps, extras are kept, types coerce). LLM-generated sections are validated individually via a `coerce_sections` helper so a malformed section is dropped (not fatal). `scripts/gen_schema.py` writes the JSON Schema from the models and a unit test fails if the committed schema drifts.

**Tech Stack:** Python 3, Pydantic v2 (already installed via google-adk — no new dependency), pytest, `uv` for running.

## Global Constraints

- **No new dependencies.** Pydantic v2 is already available via the `uv` environment (`uv run python -c "import pydantic; print(pydantic.VERSION)"` → 2.12.x). Do not add `jsonschema` or anything else.
- **Every model** sets `model_config = ConfigDict(extra="allow")` and gives **every field an empty/`None` default** (`""`, `None`, `0`, `Field(default_factory=...)`). The dumped shape must always be complete.
- **Never lose the recap.** Coerce/repair to always-valid; drop only individual unrepairable sections (logged), never fail the whole document.
- **`{date}.source.json` is out of scope.** Do not change `build_source_data`, the collection dataclasses (`RawMatch`, `PreviewMatch`), or the source-file shape.
- **Run tests with:** `uv run python -m pytest tests/unit/worldcup_recap/ -v -o "addopts="` (the `-o "addopts="` overrides `pytest.ini`'s `-v` default cleanly; keep it for parity with the spec).
- **`main.py` and `render_markdown` stay behavior-unchanged** — they still receive/emit a plain `dict`.

---

### Task 1: Deterministic core models (`models.py`)

Create the contract models for everything code-built and deterministic: verification telemetry, metadata, games, content, and the top-level `RecapOutput`. Sections are added in Task 2.

**Files:**
- Create: `worldcup_recap/models.py`
- Test: `tests/unit/worldcup_recap/test_models.py`

**Interfaces:**
- Consumes: nothing (new module).
- Produces (used by later tasks): `RecapOutput`, `Metadata`, `Verification`, `VerificationDetail`, `VerificationNeed`, `VerificationAttempt`, `Content`, `Game`, `TeamSide`, `GameMedia`, `Scorer`, `Performer`, `TimelineEvent`, `NewsItem`. All are Pydantic v2 `BaseModel`s with `extra="allow"` and full defaults. `RecapOutput.model_validate(dict) -> RecapOutput`; `RecapOutput.model_dump(mode="json") -> dict`.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/worldcup_recap/test_models.py`:

```python
"""Tests for worldcup_recap/models.py — the recap JSON contract."""

from worldcup_recap.models import Game, RecapOutput


def test_recap_output_fills_defaults_for_missing_fields():
    """A nearly-empty input still dumps a complete, predictable shape."""
    out = RecapOutput.model_validate({"recap_id": "worldcup-daily-2026-06-11"}).model_dump(mode="json")
    assert out["recap_id"] == "worldcup-daily-2026-06-11"
    assert out["date"] == ""
    assert out["generated_at"] == ""
    assert out["source_data_file"] == ""
    # nested defaults present
    assert out["metadata"]["matches_count"] == 0
    assert out["metadata"]["sources_used"] == []
    assert out["metadata"]["verification"] == {
        "searched": 0, "accepted": 0, "rejected": 0, "dropped": 0, "details": [],
    }
    assert out["content"]["headline"] == ""
    assert out["content"]["games"] == []
    assert out["content"]["sections"] == []


def test_recap_output_preserves_unknown_fields():
    """extra='allow' keeps anything useful instead of silently dropping it."""
    out = RecapOutput.model_validate(
        {"recap_id": "x", "future_field": "keep me",
         "content": {"headline": "h", "experimental": [1, 2]}}
    ).model_dump(mode="json")
    assert out["future_field"] == "keep me"
    assert out["content"]["experimental"] == [1, 2]


def test_game_coerces_string_score_to_int():
    """A stringy score like '3' is coerced to the int 3."""
    g = Game.model_validate({"match_id": "1", "home": {"team": "A", "score": "3"},
                             "away": {"team": "B", "score": 1}})
    assert g.home.score == 3
    assert g.away.score == 1


def test_verification_round_trips_real_shape():
    """The verification dict the pipeline emits round-trips into the model and back."""
    v = {
        "searched": 1, "accepted": 1, "rejected": 0, "dropped": 0,
        "details": [{
            "owner": "match_of_day",
            "need": {"kind": "highlights", "subject": "Germany vs Curaçao", "context": ""},
            "status": "accepted", "accepted_url": "https://x/v",
            "attempts": [{"attempt": 1, "raw_url": "https://x/raw", "resolved_url": "https://x/v",
                          "outcome": "accepted", "reason": "ok"}],
        }],
    }
    out = RecapOutput.model_validate({"metadata": {"verification": v}}).model_dump(mode="json")
    assert out["metadata"]["verification"]["details"][0]["need"]["kind"] == "highlights"
    assert out["metadata"]["verification"]["details"][0]["attempts"][0]["outcome"] == "accepted"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run python -m pytest tests/unit/worldcup_recap/test_models.py -o "addopts="`
Expected: FAIL with `ModuleNotFoundError: No module named 'worldcup_recap.models'`

- [ ] **Step 3: Create `worldcup_recap/models.py` with the deterministic core**

```python
"""Pydantic v2 contract models for the World Cup daily recap JSON.

Single source of truth for `schemas/recap_output.json`. Every model allows
extra fields (so nothing useful is silently dropped) and gives every field an
empty/`None` default (so a dumped recap always has the complete, predictable
shape downstream HTML/video renderers rely on).

Sections (the polymorphic, LLM-generated parts) live below the deterministic
core and are added/validated via `coerce_sections`.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)

_CONFIG = ConfigDict(extra="allow")


# ---------------------------------------------------------------------------
# Verification telemetry (built deterministically by the pipeline)
# ---------------------------------------------------------------------------

class VerificationAttempt(BaseModel):
    model_config = _CONFIG
    attempt: int = 0
    raw_url: str | None = None
    resolved_url: str | None = None
    outcome: str = ""
    reason: str = ""


class VerificationNeed(BaseModel):
    model_config = _CONFIG
    kind: str = ""
    subject: str = ""
    context: str = ""


class VerificationDetail(BaseModel):
    model_config = _CONFIG
    owner: str = ""
    need: VerificationNeed = Field(default_factory=VerificationNeed)
    status: str = ""
    accepted_url: str | None = None
    attempts: list[VerificationAttempt] = Field(default_factory=list)


class Verification(BaseModel):
    model_config = _CONFIG
    searched: int = 0
    accepted: int = 0
    rejected: int = 0
    dropped: int = 0
    details: list[VerificationDetail] = Field(default_factory=list)


class Metadata(BaseModel):
    model_config = _CONFIG
    matches_count: int = 0
    sources_used: list[str] = Field(default_factory=list)
    timezone: str = ""
    verification: Verification = Field(default_factory=Verification)
    generation_time_seconds: float = 0.0


# ---------------------------------------------------------------------------
# Games (deterministic + inclusive: timeline, top performers, attendance)
# ---------------------------------------------------------------------------

class TeamSide(BaseModel):
    model_config = _CONFIG
    team: str = ""
    score: int = 0
    logo_url: str | None = None
    team_url: str | None = None


class GameMedia(BaseModel):
    model_config = _CONFIG
    recap_url: str | None = None
    highlight_url: str | None = None


class Scorer(BaseModel):
    model_config = _CONFIG
    player: str = ""
    minute: str = ""
    profile_url: str | None = None


class Performer(BaseModel):
    model_config = _CONFIG
    name: str = ""
    team: str = ""
    goals: int = 0
    saves: int = 0
    note: str = ""
    profile_url: str | None = None
    headshot_url: str | None = None


class TimelineEvent(BaseModel):
    model_config = _CONFIG
    minute: str = ""
    type: str = ""
    player: str = ""
    text: str = ""
    scoring_play: bool = False


class NewsItem(BaseModel):
    model_config = _CONFIG
    headline: str = ""
    url: str | None = None
    published: str = ""


class Game(BaseModel):
    model_config = _CONFIG
    match_id: str = ""
    stage: str = ""
    status: str = ""
    home: TeamSide = Field(default_factory=TeamSide)
    away: TeamSide = Field(default_factory=TeamSide)
    venue: str = ""
    attendance: int | None = None
    media: GameMedia = Field(default_factory=GameMedia)
    scorers: list[Scorer] = Field(default_factory=list)
    top_performers: list[Performer] = Field(default_factory=list)
    timeline: list[TimelineEvent] = Field(default_factory=list)
    news: list[NewsItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Content + top-level document
# Sections (content.sections) are appended in Task 2.
# ---------------------------------------------------------------------------

class Content(BaseModel):
    model_config = _CONFIG
    headline: str = ""
    summary: str = ""
    games: list[Game] = Field(default_factory=list)
    sections: list = Field(default_factory=list)  # replaced with list[Section] in Task 2


class RecapOutput(BaseModel):
    model_config = _CONFIG
    recap_id: str = ""
    date: str = ""
    generated_at: str = ""
    metadata: Metadata = Field(default_factory=Metadata)
    content: Content = Field(default_factory=Content)
    source_data_file: str = ""
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run python -m pytest tests/unit/worldcup_recap/test_models.py -o "addopts="`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add worldcup_recap/models.py tests/unit/worldcup_recap/test_models.py
git commit -m "feat(worldcup): pydantic contract models for recap core (Metadata, Game, RecapOutput)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Section models, discriminated union, and `coerce_sections`

Add the six polymorphic LLM section types as a discriminated union on `type`, wire `Content.sections` to it, and add the `coerce_sections` helper that validates each section individually and drops (with a log) any that cannot be repaired.

**Files:**
- Modify: `worldcup_recap/models.py` (append section models; change `Content.sections` type; add `coerce_sections`)
- Test: `tests/unit/worldcup_recap/test_models.py` (add section tests)

**Interfaces:**
- Consumes: `_CONFIG`, `logger`, `Content`, `NewsItem` from Task 1.
- Produces (used by Task 4): `Section` (an `Annotated[Union[...6...], Field(discriminator="type")]`); `coerce_sections(raw_sections: list[dict]) -> list[Section]` — validates each section on its own, dropping+logging any invalid/unknown-`type` section. Section types: `MatchOfDaySection`, `ResultsRoundupSection`, `PlayerSpotlightSection`, `GroupWatchSection`, `StorylinesSection`, `LookingAheadSection`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/worldcup_recap/test_models.py`:

```python
from worldcup_recap.models import coerce_sections


def test_coerce_sections_validates_all_known_types():
    """One of each section type validates and keeps its `type` discriminator."""
    raw = [
        {"type": "match_of_day", "title": "MOTD", "home_team": "Germany",
         "away_team": "Curaçao", "score": "7-1", "facts": "f", "match_id": "1"},
        {"type": "results_roundup", "title": "R",
         "games": [{"matchup": "A 1-0 B", "note": "n", "match_id": "2"}]},
        {"type": "player_spotlight", "title": "P",
         "players": [{"name": "X", "team": "T", "line": "1 goal", "context": "c",
                      "media": {"profile_url": "https://p"}}]},
        {"type": "group_watch", "title": "G", "notes": "some notes"},
        {"type": "storylines", "title": "S",
         "stories": [{"headline": "h", "summary": "s"}]},
        {"type": "looking_ahead", "title": "L",
         "upcoming": [{"home": "France", "away": "Peru", "kickoff": "t",
                       "storyline": "opener",
                       "odds": {"favorite": "France", "line": "FRA -1", "over_under": 2.5},
                       "news": [{"headline": "preview", "url": "u"}]}]},
    ]
    out = coerce_sections(raw)
    assert [s.type for s in out] == [
        "match_of_day", "results_roundup", "player_spotlight",
        "group_watch", "storylines", "looking_ahead",
    ]


def test_coerce_sections_drops_unknown_type():
    """A section with an unrecognised `type` is dropped, not fatal."""
    out = coerce_sections([
        {"type": "match_of_day", "title": "keep"},
        {"type": "mystery_meat", "title": "drop me"},
    ])
    assert len(out) == 1
    assert out[0].type == "match_of_day"


def test_coerce_sections_drops_malformed_but_keeps_siblings():
    """A malformed section (wrong shape) is dropped while valid siblings survive."""
    out = coerce_sections([
        {"type": "results_roundup", "title": "ok", "games": [{"matchup": "A 1-0 B"}]},
        {"type": "results_roundup", "title": "bad", "games": "not-a-list"},
        {"type": "storylines", "title": "also ok", "stories": []},
    ])
    titles = [s.title for s in out]
    assert titles == ["ok", "also ok"]


def test_coerce_sections_drops_section_without_type():
    """A section missing the `type` discriminator is dropped."""
    out = coerce_sections([{"title": "no type here"}])
    assert out == []


def test_section_preserves_unknown_fields():
    """extra='allow' keeps per-section extras (e.g. a section-level narrative variant)."""
    out = coerce_sections([
        {"type": "group_watch", "title": "G", "notes": "n", "future_field": "keep"},
    ])
    assert out[0].model_dump(mode="json")["future_field"] == "keep"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run python -m pytest tests/unit/worldcup_recap/test_models.py -o "addopts="`
Expected: FAIL with `ImportError: cannot import name 'coerce_sections'`

- [ ] **Step 3: Append the section models, union, and helper to `worldcup_recap/models.py`**

First add these imports to the existing import block at the top of the file (replace the current `from typing` line — there is none yet — and the pydantic import line):

```python
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError
```

Then append at the end of the file:

```python
# ---------------------------------------------------------------------------
# Sections (polymorphic, discriminated union on `type`)
# ---------------------------------------------------------------------------

class _SectionBase(BaseModel):
    model_config = _CONFIG
    title: str = ""
    narrative: str = ""


class MatchOfDaySection(_SectionBase):
    type: Literal["match_of_day"] = "match_of_day"
    home_team: str = ""
    away_team: str = ""
    score: str = ""
    facts: str = ""
    match_id: str | None = None


class ResultGame(BaseModel):
    model_config = _CONFIG
    matchup: str = ""
    note: str = ""
    match_id: str | None = None


class ResultsRoundupSection(_SectionBase):
    type: Literal["results_roundup"] = "results_roundup"
    games: list[ResultGame] = Field(default_factory=list)


class PlayerMedia(BaseModel):
    model_config = _CONFIG
    profile_url: str | None = None
    headshot_url: str | None = None
    interview_url: str | None = None


class SpotlightPlayer(BaseModel):
    model_config = _CONFIG
    name: str = ""
    team: str = ""
    line: str = ""
    context: str = ""
    media: PlayerMedia = Field(default_factory=PlayerMedia)


class PlayerSpotlightSection(_SectionBase):
    type: Literal["player_spotlight"] = "player_spotlight"
    players: list[SpotlightPlayer] = Field(default_factory=list)


class GroupWatchSection(_SectionBase):
    type: Literal["group_watch"] = "group_watch"
    notes: str = ""


class Story(BaseModel):
    model_config = _CONFIG
    headline: str = ""
    summary: str = ""


class StorylinesSection(_SectionBase):
    type: Literal["storylines"] = "storylines"
    stories: list[Story] = Field(default_factory=list)


class OddsSummary(BaseModel):
    model_config = _CONFIG
    favorite: str | None = None
    line: str | None = None
    over_under: float | None = None


class UpcomingFixture(BaseModel):
    model_config = _CONFIG
    home: str = ""
    away: str = ""
    kickoff: str = ""
    storyline: str = ""
    odds: OddsSummary | None = None
    news: list[NewsItem] = Field(default_factory=list)


class LookingAheadSection(_SectionBase):
    type: Literal["looking_ahead"] = "looking_ahead"
    upcoming: list[UpcomingFixture] = Field(default_factory=list)


Section = Annotated[
    Union[
        MatchOfDaySection,
        ResultsRoundupSection,
        PlayerSpotlightSection,
        GroupWatchSection,
        StorylinesSection,
        LookingAheadSection,
    ],
    Field(discriminator="type"),
]

_SECTION_ADAPTER = TypeAdapter(Section)


def coerce_sections(raw_sections: list[dict]) -> list[Section]:
    """Validate each section on its own; drop (and log) any that can't be repaired.

    An unknown `type`, a missing `type`, or an otherwise-invalid section is
    dropped so a single malformed LLM section never fails the whole document.
    """
    coerced: list[Section] = []
    for raw in raw_sections or []:
        try:
            coerced.append(_SECTION_ADAPTER.validate_python(raw))
        except ValidationError as exc:
            logger.warning(
                "Dropping invalid recap section (type=%r): %s",
                (raw or {}).get("type"), exc,
            )
    return coerced
```

Finally, update `Content.sections` to use the union. Change the line in the `Content` model from:

```python
    sections: list = Field(default_factory=list)  # replaced with list[Section] in Task 2
```

to:

```python
    sections: list[Section] = Field(default_factory=list)
```

(`Section` is defined later in the module; because `from __future__ import annotations` is in effect, the forward reference resolves at validation time. Pydantic v2 resolves it via the module namespace — no manual `model_rebuild()` is needed since both live in the same module.)

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run python -m pytest tests/unit/worldcup_recap/test_models.py -o "addopts="`
Expected: PASS (all model tests, including the new section tests)

If you hit a `PydanticUndefinedAnnotation`/forward-ref error on import, add `RecapOutput.model_rebuild()` and `Content.model_rebuild()` at the very end of the module and re-run.

- [ ] **Step 5: Commit**

```bash
git add worldcup_recap/models.py tests/unit/worldcup_recap/test_models.py
git commit -m "feat(worldcup): section models + discriminated union + coerce_sections drop-invalid helper

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Inclusive `build_games` (timeline, top_performers, attendance)

Extend `build_games` so each game object carries the rendering-useful inclusive fields: the event `timeline`, `top_performers`, and `attendance`. Bulk raw per-player stats stay in `{date}.source.json` (unchanged).

**Files:**
- Modify: `worldcup_recap/synthesize.py` (add `_top_performers_for`; extend the `build_games` dict)
- Test: `tests/unit/worldcup_recap/test_synthesize.py` (add inclusive-shape test)

**Interfaces:**
- Consumes: `RawMatch.timeline`, `RawMatch.top_performers`, `RawMatch.attendance`, `RawMatch.player_stats` (from `providers/base.py`).
- Produces: `build_games(data)` entries now additionally contain `attendance`, `top_performers` (list of dicts with `profile_url` enriched from `player_stats` when available), and `timeline` (the raw event dicts). Consumed by Task 4's model gate.

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/worldcup_recap/test_synthesize.py`:

```python
def test_build_games_includes_inclusive_fields():
    """build_games now carries timeline, top_performers, and attendance."""
    from worldcup_recap.synthesize import build_games
    m = _match(
        attendance=74000,
        top_performers=[{"name": "Havertz", "team": "Germany", "goals": 2,
                         "saves": 0, "note": "brace"}],
    )
    data = CollectedData(date="2026-06-14", matches=[m], standings=[], upcoming=[],
                         sources_used=["espn"])
    g = build_games(data)[0]
    assert g["attendance"] == 74000
    assert g["timeline"][0]["player"] == "Havertz"
    assert g["timeline"][0]["type"] == "Goal"
    assert g["top_performers"][0]["name"] == "Havertz"
    assert g["top_performers"][0]["goals"] == 2
    # profile_url enriched from player_stats (Havertz has a profile in _match defaults)
    assert g["top_performers"][0]["profile_url"] == "https://espn/h"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run python -m pytest tests/unit/worldcup_recap/test_synthesize.py::test_build_games_includes_inclusive_fields -o "addopts="`
Expected: FAIL with `KeyError: 'attendance'`

- [ ] **Step 3: Add `_top_performers_for` and extend `build_games`**

In `worldcup_recap/synthesize.py`, add this helper directly below the existing `_scorers_for` function (after line ~62):

```python
def _top_performers_for(match) -> list[dict]:
    """Top performers with the player's profile link enriched from player_stats."""
    profile = {p.get("name"): p.get("profile_url") for p in match.player_stats}
    out = []
    for p in match.top_performers or []:
        tp = dict(p)
        if not tp.get("profile_url") and profile.get(p.get("name")):
            tp["profile_url"] = profile[p["name"]]
        out.append(tp)
    return out
```

Then, in `build_games`, replace the appended dict's tail. Change:

```python
            "venue": m.venue,
            "media": {"recap_url": m.espn_recap_url, "highlight_url": highlight},
            "scorers": _scorers_for(m),
            "news": (m.news or [])[:3],
        })
```

to:

```python
            "venue": m.venue,
            "attendance": m.attendance,
            "media": {"recap_url": m.espn_recap_url, "highlight_url": highlight},
            "scorers": _scorers_for(m),
            "top_performers": _top_performers_for(m),
            "timeline": m.timeline,
            "news": (m.news or [])[:3],
        })
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run python -m pytest tests/unit/worldcup_recap/test_synthesize.py::test_build_games_includes_inclusive_fields -o "addopts="`
Expected: PASS

- [ ] **Step 5: Run the full synthesize suite to confirm no regressions**

Run: `uv run python -m pytest tests/unit/worldcup_recap/test_synthesize.py -o "addopts="`
Expected: PASS (existing `test_build_games_full_shape` still passes; new field test passes)

- [ ] **Step 6: Commit**

```bash
git add worldcup_recap/synthesize.py tests/unit/worldcup_recap/test_synthesize.py
git commit -m "feat(worldcup): make build_games inclusive (timeline, top_performers, attendance)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Route `build_final_output` through the model gate

Replace the shallow 5-key `validate_output` check with full model validation. `build_final_output` keeps building dicts, coerces sections via `coerce_sections`, validates the whole document via `RecapOutput.model_validate`, and returns `model_dump(mode="json")` — an always-valid, complete dict. Update `test_synthesize.py` for the new behavior.

**Files:**
- Modify: `worldcup_recap/synthesize.py` (imports; rewrite `validate_output`; remove `_REQUIRED_KEYS`; rewrite the tail of `build_final_output`)
- Modify: `tests/unit/worldcup_recap/test_synthesize.py` (drop the stale missing-key test; add coercion/shape assertions)

**Interfaces:**
- Consumes: `RecapOutput`, `coerce_sections` from `worldcup_recap.models` (Tasks 1–2); `build_games` (Task 3), `_clean_sections`, `_match_id_for` (existing).
- Produces: `build_final_output(...) -> dict` that is always schema-valid with a complete shape; `validate_output(output: dict) -> None` is now a thin alias that runs `RecapOutput.model_validate(output)` (raises on irreparable types — `pydantic.ValidationError` is a subclass of `ValueError`).

- [ ] **Step 1: Write/adjust the failing tests**

In `tests/unit/worldcup_recap/test_synthesize.py`:

(a) **Remove** the now-invalid test (missing keys no longer raise — the model fills defaults):

```python
def test_validate_output_missing_key():
    with pytest.raises(ValueError):
        validate_output({"date": "2026-06-11"})
```

(b) **Append** these tests:

```python
def test_build_final_output_is_model_valid_and_complete():
    """The returned dict is a complete RecapOutput shape (defaults filled, games inclusive)."""
    data = CollectedData(date="2026-06-14", matches=[_match()], standings=[], upcoming=[],
                         sources_used=["espn"])
    out = build_final_output(data, _synth(), generation_time=1.0,
                             verification={"searched": 0, "accepted": 0, "rejected": 0, "dropped": 0})
    # deterministic core + inclusive game fields present
    assert "timeline" in out["content"]["games"][0]
    assert "top_performers" in out["content"]["games"][0]
    assert "attendance" in out["content"]["games"][0]
    # verification dumped with full shape (details list present)
    assert out["metadata"]["verification"]["details"] == []
    # no legacy embedded source_data
    assert "source_data" not in out
    # re-validating the dump does not raise
    validate_output(out)


def test_build_final_output_drops_unknown_section_type():
    """An LLM section with an unknown type is dropped; valid siblings survive."""
    data = CollectedData(date="2026-06-14", matches=[], standings=[], upcoming=[],
                         sources_used=["espn"])
    synth = {"headline": "h", "summary": "s", "sections": [
        {"type": "storylines", "title": "Keep", "stories": [{"headline": "x", "summary": "y"}]},
        {"type": "totally_unknown", "title": "Drop"},
    ]}
    out = build_final_output(data, synth, 1.0,
                             {"searched": 0, "accepted": 0, "rejected": 0, "dropped": 0})
    titles = [s["title"] for s in out["content"]["sections"]]
    assert titles == ["Keep"]


def test_build_final_output_coerces_string_score():
    """A stringy game score is coerced to int through the model gate."""
    data = CollectedData(date="2026-06-14", matches=[_match(home_score="5")], standings=[],
                         upcoming=[], sources_used=["espn"])
    out = build_final_output(data, _synth(), 1.0,
                             {"searched": 0, "accepted": 0, "rejected": 0, "dropped": 0})
    assert out["content"]["games"][0]["home"]["score"] == 5
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run python -m pytest tests/unit/worldcup_recap/test_synthesize.py -o "addopts="`
Expected: FAIL — `test_build_final_output_is_model_valid_and_complete` fails on `out["metadata"]["verification"]["details"]` (old code passes the raw dict through unchanged, no `details` key) and the unknown-section test fails (old code keeps all sections).

- [ ] **Step 3: Update imports and remove the shallow check in `synthesize.py`**

At the top of `worldcup_recap/synthesize.py`, add after the existing imports:

```python
from worldcup_recap.models import RecapOutput, coerce_sections
```

Remove the `_REQUIRED_KEYS` constant (line ~9):

```python
_REQUIRED_KEYS = {"recap_id", "date", "generated_at", "metadata", "content"}
```

Replace the old `validate_output` function:

```python
def validate_output(output: dict) -> None:
    """Raise ValueError if any required top-level key is missing."""
    missing = _REQUIRED_KEYS - set(output.keys())
    if missing:
        raise ValueError(f"Missing required field(s): {', '.join(sorted(missing))}")
```

with the thin model-backed alias:

```python
def validate_output(output: dict) -> None:
    """Validate a recap dict against the RecapOutput contract (raises on irreparable input)."""
    RecapOutput.model_validate(output)
```

- [ ] **Step 4: Rewrite the tail of `build_final_output` to use the model gate**

In `build_final_output`, replace the `output = {...}` assembly plus `validate_output(output); return output` (everything from `output = {` through `return output`) with:

```python
    output = {
        "recap_id": build_recap_id(data.date),
        "date": data.date,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "metadata": {
            "matches_count": len(data.matches),
            "sources_used": data.sources_used,
            "timezone": data.timezone,
            "verification": verification,
            "generation_time_seconds": round(generation_time, 1),
        },
        "content": {
            "headline": synthesized.get("headline", ""),
            "summary": synthesized.get("summary", ""),
            "games": games,
            "sections": coerce_sections(_clean_sections(raw_sections, data)),
        },
        "source_data_file": f"{data.date}.source.json",
    }
    return RecapOutput.model_validate(output).model_dump(mode="json")
```

(The earlier part of `build_final_output` — building `games`, `games_by_id`, and merging the searched MOTD highlight — is unchanged. Note `sections` is now `coerce_sections(...)`, replacing the old direct `_clean_sections(raw_sections, data)` call.)

- [ ] **Step 5: Run the synthesize suite to verify it passes**

Run: `uv run python -m pytest tests/unit/worldcup_recap/test_synthesize.py -o "addopts="`
Expected: PASS

Note: `test_build_final_output_shape` still calls `validate_output(out)` — this now runs model validation against the dumped dict, which passes. If any pre-existing assertion fails because the dumped shape added default keys (e.g. a strict equality on a section dict), relax that assertion to check the specific fields it cares about rather than full-dict equality. Do **not** remove fields from the model to satisfy a stale assertion.

- [ ] **Step 6: Commit**

```bash
git add worldcup_recap/synthesize.py tests/unit/worldcup_recap/test_synthesize.py
git commit -m "feat(worldcup): gate build_final_output through RecapOutput model (coerce to always-valid)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Schema auto-generation + drift guard

Add `scripts/gen_schema.py` that writes `RecapOutput.model_json_schema()` to `worldcup_recap/schemas/recap_output.json`, regenerate the (currently stale) committed schema, and add a unit test that fails if the committed file ever drifts from the models.

**Files:**
- Create: `scripts/gen_schema.py`
- Modify (regenerate): `worldcup_recap/schemas/recap_output.json`
- Test: `tests/unit/worldcup_recap/test_models.py` (add drift test)

**Interfaces:**
- Consumes: `RecapOutput` (Tasks 1–2).
- Produces: `scripts.gen_schema.generate_schema() -> str` (the canonical indented JSON + trailing newline); `scripts.gen_schema._SCHEMA_PATH` (the committed-file path). The drift test imports both so the test and the generator never disagree on formatting.

- [ ] **Step 1: Create `scripts/gen_schema.py`**

```python
#!/usr/bin/env python3
"""Generate worldcup_recap/schemas/recap_output.json from the Pydantic models.

The committed schema is the published contract for downstream HTML/video
renderers. Run this whenever the models change:

    uv run python scripts/gen_schema.py

A unit test (test_models.py) fails if the committed file drifts from the models.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from worldcup_recap.models import RecapOutput

_SCHEMA_PATH = (
    Path(__file__).parent.parent / "worldcup_recap" / "schemas" / "recap_output.json"
)


def generate_schema() -> str:
    """Return the indented JSON Schema string for RecapOutput (with trailing newline)."""
    return json.dumps(RecapOutput.model_json_schema(), indent=2, ensure_ascii=False) + "\n"


def main() -> None:
    _SCHEMA_PATH.write_text(generate_schema())
    print(f"✅ wrote {_SCHEMA_PATH}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Regenerate the committed schema**

Run: `uv run python scripts/gen_schema.py`
Expected: `✅ wrote .../worldcup_recap/schemas/recap_output.json`

Confirm it changed from the stale draft-07 hand-written file to the generated one:

Run: `head -5 worldcup_recap/schemas/recap_output.json`
Expected: a `"$defs"`-style Pydantic JSON Schema (contains `"$defs"`, `"properties"`, `"title": "RecapOutput"`), **not** the old `"$schema": "http://json-schema.org/draft-07/schema#"` hand-written version.

- [ ] **Step 3: Write the failing drift test**

Append to `tests/unit/worldcup_recap/test_models.py`:

```python
def test_committed_schema_matches_models():
    """The committed recap_output.json must equal the freshly generated schema."""
    import sys
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(repo_root))
    from scripts.gen_schema import generate_schema, _SCHEMA_PATH

    committed = _SCHEMA_PATH.read_text()
    assert committed == generate_schema(), (
        "recap_output.json is stale — regenerate with: uv run python scripts/gen_schema.py"
    )
```

- [ ] **Step 4: Run the drift test to verify it passes (schema was just regenerated)**

Run: `uv run python -m pytest tests/unit/worldcup_recap/test_models.py::test_committed_schema_matches_models -o "addopts="`
Expected: PASS

- [ ] **Step 5: Sanity-check the guard actually catches drift**

Temporarily append a throwaway field to a model and confirm the test fails, then revert:

Run: `uv run python -c "
from worldcup_recap.models import RecapOutput
import json, pathlib
p = pathlib.Path('worldcup_recap/schemas/recap_output.json')
p.write_text(p.read_text() + ' ')  # introduce drift (trailing space)
"`
Then: `uv run python -m pytest tests/unit/worldcup_recap/test_models.py::test_committed_schema_matches_models -o "addopts="`
Expected: FAIL ("recap_output.json is stale")
Then restore: `uv run python scripts/gen_schema.py`
Then re-run the test → Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add scripts/gen_schema.py worldcup_recap/schemas/recap_output.json tests/unit/worldcup_recap/test_models.py
git commit -m "feat(worldcup): auto-generate recap schema from models + drift-guard test

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Full-suite verification

Confirm the entire unit suite is green and the CLI still runs end-to-end before considering the work done.

**Files:** none (verification only).

- [ ] **Step 1: Run the full worldcup unit suite**

Run: `uv run python -m pytest tests/unit/worldcup_recap/ -v -o "addopts="`
Expected: PASS (all tests across `test_models.py`, `test_synthesize.py`, `test_providers.py`, `test_schedule.py`, `test_verification.py`)

- [ ] **Step 2: Run the whole project unit suite (per CLAUDE.md global rule)**

Run: `uv run python -m pytest tests/unit/ -v -o "addopts="`
Expected: PASS (no regressions in nba_recap or other suites)

- [ ] **Step 3: Smoke-test the CLI end-to-end (dry run avoids needing an API key)**

Run: `uv run python worldcup_recap/main.py 2026-06-16 --dry-run`
Expected: prints the day's matches and upcoming-fixture count without error (exercises `collect` + imports; confirms `synthesize.py` imports `worldcup_recap.models` cleanly).

- [ ] **Step 4: Regenerate one real recap JSON and validate it against the new contract**

This proves a real, full output passes the gate. Requires `GOOGLE_API_KEY` in `.env`; if unavailable, validate an existing committed recap instead:

Run: `uv run python -c "
import json
from worldcup_recap.synthesize import validate_output
out = json.load(open('data/worldcup_recaps/2026-06-16.json'))
validate_output(out)
print('✅ existing recap validates against the new contract')
"`
Expected: `✅ existing recap validates against the new contract` (extras like section-level `narrative` per player are preserved by `extra=\"allow\"`, so a real prior output is accepted).

---

## Self-Review

**Spec coverage:**
- Pydantic v2 models as source of truth → Tasks 1–2 (`models.py`). ✅
- Coerce/repair to always-valid; never lose recap → Task 4 (`model_validate` + `model_dump`). ✅
- Whole-document contract with hardened sections → Tasks 1–2 (discriminated union). ✅
- `extra="allow"` preserves unknowns → every model in Tasks 1–2; tested. ✅
- Inclusive-but-lean games (timeline/top_performers/attendance); raw stats stay in source.json → Task 3; source.json untouched (Global Constraints). ✅
- Sections coerced individually, unknown/malformed dropped + logged → Task 2 `coerce_sections`; tested in Tasks 2 & 4. ✅
- `coerce_sections(list) -> list[Section]` helper → Task 2. ✅
- Replace shallow `validate_output`/`_REQUIRED_KEYS` → Task 4. ✅
- Schema auto-generated via `model_json_schema()` + drift test → Task 5. ✅
- `main.py` / `render_markdown` unchanged → confirmed (no edits to either; Task 6 smoke test). ✅
- Tests enumerated in spec's Testing section → covered across Tasks 1–5 (round-trip, coercion, extras, unknown/malformed drop, inclusive games, schema drift, updated synthesize). ✅
- Non-goals (no collection-layer change, no Gemini structured-output, no HTML renderer) → respected. ✅

**Placeholder scan:** No TBD/"handle edge cases"/"similar to Task N"/"write tests for the above" — every code and test step contains the literal content. ✅

**Type consistency:** `coerce_sections` returns `list[Section]`; `Content.sections: list[Section]`; `build_final_output` passes `coerce_sections(...)` into `content.sections` then `RecapOutput.model_validate(...).model_dump(mode="json")`. `validate_output` consistently means model validation in Tasks 4–6. `generate_schema`/`_SCHEMA_PATH` names match between Task 5 script and the drift test. Game field names (`timeline`, `top_performers`, `attendance`) match between Task 3 producer and Task 4 assertions. ✅

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-06-18-recap-schema-enforcement.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**
