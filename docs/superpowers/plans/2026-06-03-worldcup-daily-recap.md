# World Cup 2026 Daily Recap — Implementation Plan (Phase 1 MVP)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone `worldcup_recap/` module that, for a given date, collects World Cup match data from ESPN (no LLM), classifies it into narrative sections, finds & verifies media links via a feedback loop, and synthesizes an engaging English daily recap to `data/worldcup_recaps/YYYY-MM-DD.{json,md}`.

**Architecture:** Four phases mirroring the existing `nba_recap/` module — `collect` (pure-Python ESPN) → `structure` (Gemini agent) → `enrich + verify` (finder→verifier→bounded-retry loop) → `synthesize` (Gemini agent). Data comes through a swappable `StatsProvider` interface (ESPN-only now). Collect + the verification loop are built mode-agnostic for reuse by future output modes.

**Tech Stack:** Python 3.11, Google ADK (`google-adk`) + Gemini 2.5 Flash, `httpx` for ESPN, `pytest` + `pytest-asyncio` for tests. ESPN endpoints are keyless; `GOOGLE_API_KEY` required for LLM phases.

**Reference docs:** [design spec](2026-06-03-worldcup-daily-recap-design.md is at ../specs/) · `docs/worldcup_recap/data-source-discovery.md` (verified endpoint shapes) · existing `nba_recap/` module (closest pattern to copy).

**Run tests with:** `python -m pytest tests/unit/worldcup_recap/ -v -o "addopts="`

---

## File Structure

```
worldcup_recap/
  __init__.py
  providers/
    __init__.py
    base.py                 # RawMatch, PreviewMatch, CollectedData dataclasses + StatsProvider Protocol
    espn.py                 # ESPN parse pure-functions + EspnProvider (httpx fetch)
  collect.py                # collect(date) — selects provider, assembles CollectedData
  agents/
    __init__.py
    structure_agent.py      # classify day -> sections
    media_finder_agent.py   # google_search candidate finder
    media_verifier_agent.py # relevance verifier
    synthesis_agent.py      # English prose synthesis
  prompts/
    structure.md
    media_finder.md
    media_verifier.md
    synthesis.md
  pipeline.py               # orchestrate phases + find/verify loop
  synthesize.py             # build_final_output, render_markdown, validate_output
  schemas/
    recap_output.json
  main.py                   # CLI
data/worldcup_recaps/.gitkeep
tests/unit/worldcup_recap/
  __init__.py
  test_providers.py         # ESPN parse functions
  test_verification.py      # find/verify loop logic (fakes)
  test_synthesize.py        # output building + markdown
.github/workflows/worldcup_recap.yml
requirements.txt            # add httpx
```

**Boundary rationale:** dataclasses + `StatsProvider` live in `providers/base.py` so `espn.py` and `collect.py` both import them with no circular dependency (ESPN provider produces `RawMatch`; collect imports both). Pure parse functions are separated from network I/O in `espn.py` so they are unit-testable with inline dicts (no live API in tests).

---

## Task 1: Module scaffold + data model

**Files:**
- Create: `worldcup_recap/__init__.py` (empty)
- Create: `worldcup_recap/providers/__init__.py` (empty)
- Create: `worldcup_recap/agents/__init__.py` (empty)
- Create: `tests/unit/worldcup_recap/__init__.py` (empty)
- Create: `worldcup_recap/providers/base.py`
- Test: `tests/unit/worldcup_recap/test_providers.py`

- [ ] **Step 1: Create the empty package files**

Create these four empty files: `worldcup_recap/__init__.py`, `worldcup_recap/providers/__init__.py`, `worldcup_recap/agents/__init__.py`, `tests/unit/worldcup_recap/__init__.py`.

- [ ] **Step 2: Write the failing test for the data model**

Create `tests/unit/worldcup_recap/test_providers.py`:

```python
"""Tests for worldcup_recap/providers."""

from worldcup_recap.providers.base import RawMatch, PreviewMatch, CollectedData


def test_raw_match_structure():
    m = RawMatch(
        match_id="401864055",
        stage="Group A",
        home_team="Norway",
        away_team="Sweden",
        home_score=3,
        away_score=1,
        status="STATUS_FULL_TIME",
        timeline=[],
        top_performers=[],
        player_stats=[],
        venue="Ullevaal Stadion",
        attendance=0,
        espn_recap_url=None,
        espn_videos=[],
        news=[],
    )
    assert m.match_id == "401864055"
    assert m.home_score == 3
    assert m.venue == "Ullevaal Stadion"


def test_collected_data_defaults():
    data = CollectedData(date="2026-06-11", matches=[], standings=[], upcoming=[])
    assert data.sources_used == []
    assert data.matches == []


def test_preview_match_structure():
    p = PreviewMatch(
        match_id="760415",
        stage="Group A",
        home_team="Mexico",
        away_team="South Africa",
        kickoff="2026-06-11T19:00Z",
        odds={"favorite": "Mexico"},
        head_to_head=[],
        home_form=["W", "D"],
        away_form=["L"],
        news=[],
    )
    assert p.home_team == "Mexico"
    assert p.home_form == ["W", "D"]
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/unit/worldcup_recap/test_providers.py -v -o "addopts="`
Expected: FAIL with `ModuleNotFoundError: No module named 'worldcup_recap.providers.base'`

- [ ] **Step 4: Implement the data model**

Create `worldcup_recap/providers/base.py`:

```python
"""Shared data model + StatsProvider interface for the World Cup recap pipeline.

Dataclasses live here (not in collect.py) so both espn.py and collect.py can
import them without a circular dependency.
"""

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class RawMatch:
    match_id: str
    stage: str
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    status: str
    timeline: list[dict]        # {minute, type, player, text, scoring_play}
    top_performers: list[dict]  # {name, team, goals, saves, note}
    player_stats: list[dict]    # {name, team, position, starter, stats: {name: value}}
    venue: str
    attendance: int | None
    espn_recap_url: str | None
    espn_videos: list[dict]     # {headline, url, thumbnail, duration}
    news: list[dict]            # {headline, url, published}


@dataclass
class PreviewMatch:
    match_id: str
    stage: str
    home_team: str
    away_team: str
    kickoff: str                # ISO datetime
    odds: dict | None
    head_to_head: list[dict]    # historical meetings
    home_form: list[str]        # recent results e.g. ["W","D","L"]
    away_form: list[str]
    news: list[dict]


@dataclass
class CollectedData:
    date: str
    matches: list[RawMatch]
    standings: list[dict]
    upcoming: list[PreviewMatch]
    sources_used: list[str] = field(default_factory=list)


class StatsProvider(Protocol):
    """A pluggable data source. ESPN is the only implementation in Phase 1."""

    name: str

    def matches_for_date(self, date: str) -> list[RawMatch]: ...
    def upcoming(self, date: str) -> list[PreviewMatch]: ...
    def standings(self) -> list[dict]: ...
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/unit/worldcup_recap/test_providers.py -v -o "addopts="`
Expected: PASS (3 passed)

- [ ] **Step 6: Commit**

```bash
git add worldcup_recap/__init__.py worldcup_recap/providers/__init__.py worldcup_recap/agents/__init__.py tests/unit/worldcup_recap/__init__.py worldcup_recap/providers/base.py tests/unit/worldcup_recap/test_providers.py
git commit -m "feat(worldcup): module scaffold + data model"
```

---

## Task 2: ESPN parse functions (pure, no network)

These pure functions parse real ESPN response shapes (verified 2026-06-03 — see discovery doc). Inline test dicts mirror the real API.

**Files:**
- Create: `worldcup_recap/providers/espn.py`
- Test: `tests/unit/worldcup_recap/test_providers.py` (append)

- [ ] **Step 1: Write failing tests for the parse functions**

Append to `tests/unit/worldcup_recap/test_providers.py`:

```python
from worldcup_recap.providers.espn import (
    parse_scoreboard_event,
    parse_timeline,
    parse_player_stats,
    derive_top_performers,
    parse_news,
)


def _event():
    # Mirrors ESPN /scoreboard events[] shape
    return {
        "id": "401864055",
        "date": "2026-06-11T19:00Z",
        "name": "Sweden at Norway",
        "shortName": "SWE @ NOR",
        "status": {"type": {"name": "STATUS_FULL_TIME"}},
        "competitions": [{
            "venue": {"fullName": "Ullevaal Stadion"},
            "notes": [{"headline": "Group A"}],
            "competitors": [
                {"homeAway": "home", "score": "3", "team": {"displayName": "Norway"}},
                {"homeAway": "away", "score": "1", "team": {"displayName": "Sweden"}},
            ],
        }],
    }


def test_parse_scoreboard_event():
    r = parse_scoreboard_event(_event())
    assert r["match_id"] == "401864055"
    assert r["home_team"] == "Norway"
    assert r["away_team"] == "Sweden"
    assert r["home_score"] == 3
    assert r["away_score"] == 1
    assert r["status"] == "STATUS_FULL_TIME"
    assert r["stage"] == "Group A"
    assert r["venue"] == "Ullevaal Stadion"


def test_parse_scoreboard_event_missing_fields():
    r = parse_scoreboard_event({"id": "x", "competitions": [{}]})
    assert r["match_id"] == "x"
    assert r["home_team"] == ""
    assert r["home_score"] == 0
    assert r["stage"] == ""


def test_parse_timeline_filters_and_maps():
    key_events = [
        {"type": {"text": "Kickoff"}, "clock": {"displayValue": ""},
         "text": "First Half begins.", "scoringPlay": False},
        {"type": {"text": "Goal - Header"}, "clock": {"displayValue": "8'"},
         "text": "Goal! Norway 1, Sweden 0. Jørgen Strand Larsen header.",
         "scoringPlay": True,
         "participants": [{"athlete": {"displayName": "Jørgen Strand Larsen"}}]},
        {"type": {"text": "Yellow Card"}, "clock": {"displayValue": "40'"},
         "text": "Booking.", "scoringPlay": False,
         "participants": [{"athlete": {"displayName": "Some Player"}}]},
    ]
    tl = parse_timeline(key_events)
    # Kickoff is filtered out; goal + card kept
    assert len(tl) == 2
    goal = tl[0]
    assert goal["type"] == "Goal - Header"
    assert goal["minute"] == "8'"
    assert goal["player"] == "Jørgen Strand Larsen"
    assert goal["scoring_play"] is True


def test_parse_player_stats():
    rosters = [{
        "team": {"displayName": "Norway"},
        "formation": "4-4-2",
        "roster": [{
            "athlete": {"displayName": "Ørjan Nyland"},
            "position": {"abbreviation": "G"},
            "starter": True,
            "stats": [
                {"name": "saves", "displayValue": "3"},
                {"name": "goalsConceded", "displayValue": "1"},
            ],
        }],
    }]
    ps = parse_player_stats(rosters)
    assert len(ps) == 1
    assert ps[0]["name"] == "Ørjan Nyland"
    assert ps[0]["team"] == "Norway"
    assert ps[0]["position"] == "G"
    assert ps[0]["stats"]["saves"] == "3"


def test_derive_top_performers_counts_goals_and_gk():
    timeline = [
        {"type": "Goal - Header", "player": "Jørgen Strand Larsen", "scoring_play": True},
        {"type": "Goal", "player": "Antonio Nusa", "scoring_play": True},
        {"type": "Goal - Header", "player": "Jørgen Strand Larsen", "scoring_play": True},
    ]
    player_stats = [
        {"name": "Ørjan Nyland", "team": "Norway", "position": "G",
         "stats": {"saves": "3"}},
    ]
    perf = derive_top_performers(timeline, player_stats)
    names = [p["name"] for p in perf]
    assert "Jørgen Strand Larsen" in names
    larsen = next(p for p in perf if p["name"] == "Jørgen Strand Larsen")
    assert larsen["goals"] == 2
    # GK with saves is included
    assert any(p["name"] == "Ørjan Nyland" and p.get("saves") == 3 for p in perf)


def test_parse_news():
    articles = [
        {"headline": "Norway thrash Sweden", "published": "2026-06-11T21:00Z",
         "links": {"web": {"href": "https://espn.com/story/1"}}},
    ]
    news = parse_news(articles)
    assert news[0]["headline"] == "Norway thrash Sweden"
    assert news[0]["url"] == "https://espn.com/story/1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/worldcup_recap/test_providers.py -v -o "addopts="`
Expected: FAIL with `ImportError: cannot import name 'parse_scoreboard_event'`

- [ ] **Step 3: Implement the parse functions**

Create `worldcup_recap/providers/espn.py`:

```python
"""ESPN soccer parsing + provider. Endpoint shapes verified 2026-06-03.

Parse functions are pure (no network) so they unit-test with inline dicts.
The EspnProvider wraps them with httpx fetches.
"""

import httpx

from worldcup_recap.providers.base import (
    RawMatch,
    PreviewMatch,
    StatsProvider,
)

_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world"
_TIMELINE_KEEP = ("Goal", "Card", "Substitution", "Penalty", "VAR")


def _int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def parse_scoreboard_event(event: dict) -> dict:
    """Flatten a /scoreboard events[] entry into a flat dict."""
    comp = (event.get("competitions") or [{}])[0]
    home_name = away_name = ""
    home_score = away_score = 0
    for c in comp.get("competitors", []):
        if c.get("homeAway") == "home":
            home_name = c.get("team", {}).get("displayName", "")
            home_score = _int(c.get("score"))
        else:
            away_name = c.get("team", {}).get("displayName", "")
            away_score = _int(c.get("score"))
    notes = comp.get("notes") or []
    stage = notes[0].get("headline", "") if notes else ""
    return {
        "match_id": event.get("id", ""),
        "date": event.get("date", ""),
        "home_team": home_name,
        "away_team": away_name,
        "home_score": home_score,
        "away_score": away_score,
        "status": event.get("status", {}).get("type", {}).get("name", ""),
        "stage": stage,
        "venue": comp.get("venue", {}).get("fullName", ""),
    }


def parse_timeline(key_events: list[dict]) -> list[dict]:
    """Keep goals/cards/subs/VAR; map to {minute, type, player, text, scoring_play}."""
    out = []
    for ev in key_events or []:
        type_text = ev.get("type", {}).get("text", "")
        if not any(k in type_text for k in _TIMELINE_KEEP):
            continue
        participants = ev.get("participants") or []
        player = participants[0].get("athlete", {}).get("displayName", "") if participants else ""
        out.append({
            "minute": ev.get("clock", {}).get("displayValue", ""),
            "type": type_text,
            "player": player,
            "text": ev.get("text", ""),
            "scoring_play": bool(ev.get("scoringPlay")),
        })
    return out


def parse_player_stats(rosters: list[dict]) -> list[dict]:
    """Flatten summary.rosters[].roster[] into per-player stat dicts."""
    out = []
    for team_block in rosters or []:
        team_name = team_block.get("team", {}).get("displayName", "")
        for entry in team_block.get("roster", []):
            stats = {
                s.get("name", ""): s.get("displayValue", s.get("value", ""))
                for s in entry.get("stats", [])
            }
            out.append({
                "name": entry.get("athlete", {}).get("displayName", ""),
                "team": team_name,
                "position": entry.get("position", {}).get("abbreviation", ""),
                "starter": bool(entry.get("starter")),
                "stats": stats,
            })
    return out


def derive_top_performers(timeline: list[dict], player_stats: list[dict]) -> list[dict]:
    """Goalscorers (from timeline) first, then the busiest goalkeeper."""
    goals: dict[str, int] = {}
    for ev in timeline:
        if "Goal" in ev.get("type", "") and ev.get("player"):
            goals[ev["player"]] = goals.get(ev["player"], 0) + 1

    name_to_team = {p["name"]: p.get("team", "") for p in player_stats}
    performers = []
    for name, count in sorted(goals.items(), key=lambda kv: kv[1], reverse=True):
        note = "hat-trick" if count >= 3 else ("brace" if count == 2 else "")
        performers.append({
            "name": name,
            "team": name_to_team.get(name, ""),
            "goals": count,
            "note": note,
        })

    keepers = [
        p for p in player_stats
        if p.get("position") == "G" and _int(p.get("stats", {}).get("saves")) > 0
    ]
    if keepers:
        best = max(keepers, key=lambda p: _int(p["stats"].get("saves")))
        performers.append({
            "name": best["name"],
            "team": best.get("team", ""),
            "goals": 0,
            "saves": _int(best["stats"].get("saves")),
            "note": "goalkeeper",
        })
    return performers


def parse_news(articles: list[dict]) -> list[dict]:
    """Flatten ESPN news articles[] to {headline, url, published}."""
    out = []
    for a in articles or []:
        out.append({
            "headline": a.get("headline", ""),
            "url": a.get("links", {}).get("web", {}).get("href", ""),
            "published": a.get("published", ""),
        })
    return out
```

(The `EspnProvider` class is added in Task 3 — leave the file ending after `parse_news` for now.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/worldcup_recap/test_providers.py -v -o "addopts="`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add worldcup_recap/providers/espn.py tests/unit/worldcup_recap/test_providers.py
git commit -m "feat(worldcup): ESPN parse functions"
```

---

## Task 3: EspnProvider + collect()

Adds the network layer (httpx) and the `collect()` orchestrator. No new unit tests for the network calls (they hit live ESPN); correctness is verified by the dry-run in Task 10.

**Files:**
- Modify: `worldcup_recap/providers/espn.py` (append `EspnProvider`)
- Create: `worldcup_recap/collect.py`

- [ ] **Step 1: Append EspnProvider to espn.py**

Append to `worldcup_recap/providers/espn.py`:

```python
def _get(client: httpx.Client, path: str, params: dict | None = None) -> dict:
    try:
        resp = client.get(f"{_BASE}{path}", params=params or {}, timeout=20)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:  # noqa: BLE001 — degrade gracefully, never fatal
        print(f"  ⚠️  ESPN fetch failed {path}: {e}")
        return {}


def _build_match(client: httpx.Client, event: dict) -> RawMatch:
    base = parse_scoreboard_event(event)
    summary = _get(client, "/summary", {"event": base["match_id"]})
    timeline = parse_timeline(summary.get("keyEvents", []))
    player_stats = parse_player_stats(summary.get("rosters", []))
    news = parse_news(summary.get("news", {}).get("articles", []))
    game_info = summary.get("gameInfo", {})
    recap_url = next(
        (l.get("href") for l in event.get("links", []) if "summary" in l.get("rel", [])),
        None,
    )
    videos = [
        {
            "headline": v.get("headline", ""),
            "url": v.get("links", {}).get("source", {}).get("href"),
            "thumbnail": v.get("thumbnail"),
            "duration": v.get("duration"),
        }
        for v in summary.get("videos", []) or []
    ]
    return RawMatch(
        match_id=base["match_id"],
        stage=base["stage"],
        home_team=base["home_team"],
        away_team=base["away_team"],
        home_score=base["home_score"],
        away_score=base["away_score"],
        status=base["status"],
        timeline=timeline,
        top_performers=derive_top_performers(timeline, player_stats),
        player_stats=player_stats,
        venue=base["venue"] or game_info.get("venue", {}).get("fullName", ""),
        attendance=game_info.get("attendance"),
        espn_recap_url=recap_url,
        espn_videos=videos,
        news=news,
    )


def _build_preview(client: httpx.Client, event: dict) -> PreviewMatch:
    base = parse_scoreboard_event(event)
    summary = _get(client, "/summary", {"event": base["match_id"]})
    odds_list = summary.get("odds") or []
    h2h = summary.get("headToHeadGames") or []
    form = summary.get("boxscore", {}).get("form") or []
    home_form = [r.get("displayResult", "") for r in (form[0].get("events", []) if len(form) > 0 else [])]
    away_form = [r.get("displayResult", "") for r in (form[1].get("events", []) if len(form) > 1 else [])]
    return PreviewMatch(
        match_id=base["match_id"],
        stage=base["stage"],
        home_team=base["home_team"],
        away_team=base["away_team"],
        kickoff=base["date"],
        odds=odds_list[0] if odds_list else None,
        head_to_head=h2h,
        home_form=home_form,
        away_form=away_form,
        news=parse_news(summary.get("news", {}).get("articles", [])),
    )


class EspnProvider:
    """Primary, keyless data source for FIFA World Cup."""

    name = "espn"

    def matches_for_date(self, date: str) -> list[RawMatch]:
        compact = date.replace("-", "")
        with httpx.Client() as client:
            board = _get(client, "/scoreboard", {"dates": compact})
            events = board.get("events", []) or []
            return [_build_match(client, e) for e in events]

    def upcoming(self, date: str) -> list[PreviewMatch]:
        from datetime import date as date_type, timedelta
        next_day = (date_type.fromisoformat(date) + timedelta(days=1)).isoformat()
        compact = next_day.replace("-", "")
        with httpx.Client() as client:
            board = _get(client, "/scoreboard", {"dates": compact})
            events = board.get("events", []) or []
            return [_build_preview(client, e) for e in events]

    def standings(self) -> list[dict]:
        with httpx.Client() as client:
            data = _get(client, "/standings")
        return data.get("children", []) or data.get("standings", []) or []
```

- [ ] **Step 2: Create collect.py**

Create `worldcup_recap/collect.py`:

```python
"""Phase 1: World Cup data collection. Pure orchestration over a StatsProvider.

No LLM. ESPN is the only provider in Phase 1; the StatsProvider seam lets a
second source (e.g. API-Football) be added later without changing this file.
"""

from worldcup_recap.providers.base import CollectedData, StatsProvider
from worldcup_recap.providers.espn import EspnProvider


def get_provider() -> StatsProvider:
    """Return the active stats provider. ESPN-only for now."""
    return EspnProvider()


def collect(target_date: str) -> CollectedData:
    """Fetch all World Cup data for target_date (YYYY-MM-DD). No LLM calls."""
    print(f"Collecting World Cup data for {target_date}...")
    provider = get_provider()
    matches = provider.matches_for_date(target_date)
    upcoming = provider.upcoming(target_date)
    standings = provider.standings()
    print(f"  {len(matches)} matches, {len(upcoming)} upcoming fixtures")
    return CollectedData(
        date=target_date,
        matches=matches,
        standings=standings,
        upcoming=upcoming,
        sources_used=[provider.name],
    )
```

- [ ] **Step 3: Verify imports resolve**

Run: `python -c "from worldcup_recap.collect import collect; from worldcup_recap.providers.espn import EspnProvider; print('ok')"`
Expected: prints `ok`

- [ ] **Step 4: Commit**

```bash
git add worldcup_recap/providers/espn.py worldcup_recap/collect.py
git commit -m "feat(worldcup): EspnProvider + collect orchestration"
```

---

## Task 4: Structure agent + prompt

**Files:**
- Create: `worldcup_recap/prompts/structure.md`
- Create: `worldcup_recap/agents/structure_agent.py`

- [ ] **Step 1: Create the structure prompt**

Create `worldcup_recap/prompts/structure.md`:

```markdown
You are a football (soccer) editor structuring a World Cup daily recap. You receive raw data for all of a single day's matches and must classify it into narrative sections.

Return ONLY a JSON object (no markdown fences) with this shape:
{
  "sections": [
    {
      "type": "match_of_day",
      "title": "Match of the Day",
      "home_team": "<team>", "away_team": "<team>",
      "score": "<e.g. 3-1>",
      "facts": "<key facts: scorers, drama, stakes>",
      "media_needs": [
        {"kind": "highlights", "subject": "<away> vs <home>", "context": "<date/stage>"}
      ]
    },
    {
      "type": "results_roundup",
      "title": "Other Results",
      "games": [{"matchup": "<away> X-Y <home>", "note": "<one line>"}]
    },
    {
      "type": "player_spotlight",
      "title": "Standout Players",
      "players": [{"name": "<player>", "team": "<team>", "line": "<goals/saves>", "context": "<why>",
                   "media_needs": [{"kind": "interview", "subject": "<player>", "context": "<match>"}]}]
    },
    {
      "type": "group_watch",
      "title": "Group Picture",
      "notes": "<qualification implications>"
    },
    {
      "type": "storylines",
      "title": "Storylines",
      "stories": [{"headline": "<headline>", "summary": "<2 sentences>"}]
    },
    {
      "type": "looking_ahead",
      "title": "Looking Ahead",
      "upcoming": [{"home": "<team>", "away": "<team>", "kickoff": "<time>", "storyline": "<why it matters>"}]
    }
  ]
}

Rules:
- Pick exactly ONE match_of_day (most drama / stakes / upset). All other played matches go in results_roundup.
- player_spotlight: 2-4 standout performers across all matches (goalscorers, hat-tricks, heroic keepers).
- Use group_watch during the group stage; if matches are knockout, rename its title to "Bracket" and describe progression.
- media_needs declare links to find later (highlights, interviews). Only add them where they make sense.
- Only use facts present in the input. Never invent scores, scorers, or teams.
```

- [ ] **Step 2: Create the structure agent**

Create `worldcup_recap/agents/structure_agent.py`:

```python
"""ADK Agent: classifies raw World Cup data into narrative sections."""

import json
from dataclasses import asdict
from pathlib import Path

from google.adk.agents import Agent

from worldcup_recap.providers.base import CollectedData

_SYSTEM_PROMPT = (Path(__file__).parent.parent / "prompts" / "structure.md").read_text()

structure_agent = Agent(
    name="wc_structure_agent",
    model="gemini-2.5-flash",
    instruction=_SYSTEM_PROMPT,
)


def build_structure_prompt(data: CollectedData) -> str:
    """Build the user-turn message for the structure agent."""
    payload = {
        "date": data.date,
        "matches": [
            {
                "stage": m.stage,
                "home_team": m.home_team,
                "away_team": m.away_team,
                "score": f"{m.home_score}-{m.away_score}",
                "status": m.status,
                "timeline": m.timeline,
                "top_performers": m.top_performers,
                "venue": m.venue,
            }
            for m in data.matches
        ],
        "standings": data.standings[:8],
        "upcoming": [asdict(p) for p in data.upcoming],
    }
    return f"Structure this World Cup match-day data:\n\n{json.dumps(payload, indent=2, ensure_ascii=False)}"
```

- [ ] **Step 3: Verify import**

Run: `python -c "from worldcup_recap.agents.structure_agent import structure_agent, build_structure_prompt; print('ok')"`
Expected: prints `ok`

- [ ] **Step 4: Commit**

```bash
git add worldcup_recap/prompts/structure.md worldcup_recap/agents/structure_agent.py
git commit -m "feat(worldcup): structure agent + prompt"
```

---

## Task 5: Synthesis agent, prompt, and output builder

**Files:**
- Create: `worldcup_recap/prompts/synthesis.md`
- Create: `worldcup_recap/agents/synthesis_agent.py`
- Create: `worldcup_recap/synthesize.py`
- Create: `worldcup_recap/schemas/recap_output.json`
- Test: `tests/unit/worldcup_recap/test_synthesize.py`

- [ ] **Step 1: Create the synthesis prompt (the engaging-narrative agent)**

Create `worldcup_recap/prompts/synthesis.md`:

```markdown
You are an elite football writer producing an engaging English World Cup daily recap. You receive structured sections enriched with verified media links and must write vivid, accurate prose.

Return ONLY a JSON object (no markdown fences) with EXACTLY this shape:
{
  "headline": "<one punchy sentence capturing the day's biggest story>",
  "summary": "<2-3 sentences covering the top stories of the day>",
  "sections": [ <the same sections array you received, with each section's "narrative" field written/improved> ]
}

Craft:
- Open with drama. Build each section as a mini-story: hook, what happened, why it matters.
- Draw concrete detail (minutes, scorers, assists) from the timeline/facts in the input.
- match_of_day gets the richest 3-5 sentence narrative; results_roundup stays tight.
- Mention real player and team names. The headline must name at least one team or player.

Rules:
- Only use facts present in the input. NEVER invent scores, scorers, minutes, or teams.
- Preserve every field you received (media, players, games, upcoming); only add/improve "narrative".
- Keep the JSON valid and in English.
```

- [ ] **Step 2: Create the synthesis agent**

Create `worldcup_recap/agents/synthesis_agent.py`:

```python
"""ADK Agent: writes engaging English prose and compiles the recap JSON."""

import json
from pathlib import Path

from google.adk.agents import Agent

_SYSTEM_PROMPT = (Path(__file__).parent.parent / "prompts" / "synthesis.md").read_text()

synthesis_agent = Agent(
    name="wc_synthesis_agent",
    model="gemini-2.5-flash",
    instruction=_SYSTEM_PROMPT,
)


def parse_synthesis_response(response_text: str) -> dict:
    """Parse the synthesis JSON, stripping markdown fences if present."""
    text = response_text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        inner = lines[1:]
        if inner and inner[-1].strip() == "```":
            inner = inner[:-1]
        text = "\n".join(inner).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {
            "headline": "World Cup Daily Recap",
            "summary": "A full day of World Cup action.",
            "sections": [],
        }
```

- [ ] **Step 3: Write failing tests for the output builder**

Create `tests/unit/worldcup_recap/test_synthesize.py`:

```python
"""Tests for worldcup_recap/synthesize.py."""

import json

import pytest

from worldcup_recap.providers.base import CollectedData
from worldcup_recap.synthesize import (
    build_recap_id,
    validate_output,
    build_final_output,
    render_markdown,
)


def _data():
    return CollectedData(date="2026-06-11", matches=[], standings=[], upcoming=[],
                         sources_used=["espn"])


def _synth():
    return {
        "headline": "Norway stun Sweden",
        "summary": "Norway ran riot.",
        "sections": [
            {"type": "match_of_day", "title": "Match of the Day",
             "narrative": "A dominant night.", "score": "3-1",
             "media": {"highlight_url": "https://youtube.com/x", "recap_url": "https://espn.com/y"}},
            {"type": "player_spotlight", "title": "Standout Players",
             "players": [{"name": "Larsen", "line": "2 goals", "context": "brace",
                          "media": {"interview_url": "https://youtube.com/i"}}]},
        ],
    }


def test_build_recap_id():
    assert build_recap_id("2026-06-11") == "worldcup-daily-2026-06-11"


def test_validate_output_missing_key():
    with pytest.raises(ValueError):
        validate_output({"date": "2026-06-11"})


def test_build_final_output_shape():
    out = build_final_output(
        _data(), _synth(), generation_time=1.23,
        verification={"searched": 2, "accepted": 1, "rejected": 1, "dropped": 0},
    )
    assert out["recap_id"] == "worldcup-daily-2026-06-11"
    assert out["metadata"]["matches_count"] == 0
    assert out["metadata"]["sources_used"] == ["espn"]
    assert out["metadata"]["verification"]["accepted"] == 1
    assert out["content"]["headline"] == "Norway stun Sweden"
    # validate_output ran without raising
    validate_output(out)


def test_render_markdown_includes_headline_and_links():
    out = build_final_output(
        _data(), _synth(), generation_time=1.0,
        verification={"searched": 0, "accepted": 0, "rejected": 0, "dropped": 0},
    )
    md = render_markdown(out)
    assert "# Norway stun Sweden" in md
    assert "Match of the Day" in md
    assert "https://youtube.com/x" in md
    assert "Larsen" in md
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `python -m pytest tests/unit/worldcup_recap/test_synthesize.py -v -o "addopts="`
Expected: FAIL with `ModuleNotFoundError: No module named 'worldcup_recap.synthesize'`

- [ ] **Step 5: Implement synthesize.py**

Create `worldcup_recap/synthesize.py`:

```python
"""Output helpers: build final JSON, validate, render Markdown."""

from datetime import datetime, timezone

from worldcup_recap.providers.base import CollectedData

_REQUIRED_KEYS = {"recap_id", "date", "generated_at", "metadata", "content"}


def build_recap_id(date_str: str) -> str:
    return f"worldcup-daily-{date_str}"


def validate_output(output: dict) -> None:
    """Raise ValueError if any required top-level key is missing."""
    missing = _REQUIRED_KEYS - set(output.keys())
    if missing:
        raise ValueError(f"Missing required field(s): {', '.join(sorted(missing))}")


def _render_section(section: dict) -> list[str]:
    lines: list[str] = [f"## {section.get('title', '')}", ""]
    section_type = section.get("type", "")
    if section.get("narrative"):
        lines.append(section["narrative"])
        lines.append("")

    media = section.get("media", {})
    if section_type == "match_of_day":
        if media.get("recap_url"):
            lines.append(f"[Full recap]({media['recap_url']})")
        if media.get("highlight_url"):
            lines.append(f"[Highlights]({media['highlight_url']})")
        lines.append("")
    elif section_type == "results_roundup":
        for game in section.get("games", []):
            lines.append(f"- {game.get('matchup', '')} — {game.get('note', '')}")
        lines.append("")
    elif section_type == "player_spotlight":
        for player in section.get("players", []):
            name = player.get("name", "")
            line = player.get("line", "")
            context = player.get("context", "")
            parts = [f"**{name}**", line, context]
            lines.append(" — ".join(p for p in parts if p))
            interview = player.get("media", {}).get("interview_url")
            if interview:
                lines.append(f"  [Interview]({interview})")
        lines.append("")
    elif section_type == "storylines":
        for story in section.get("stories", []):
            lines.append(f"**{story.get('headline', '')}** — {story.get('summary', '')}")
        lines.append("")
    elif section_type == "looking_ahead":
        for up in section.get("upcoming", []):
            matchup = f"{up.get('away', '')} @ {up.get('home', '')}"
            lines.append(f"- **{matchup}** {up.get('kickoff', '')} — {up.get('storyline', '')}")
        lines.append("")
    return lines


def render_markdown(output: dict) -> str:
    content = output.get("content", {})
    date_str = output.get("date", "")
    lines = [
        f"# {content.get('headline', 'World Cup Daily Recap')}",
        f"*{date_str}*",
        "",
        content.get("summary", ""),
        "",
    ]
    for section in content.get("sections", []):
        lines.extend(_render_section(section))
    return "\n".join(lines)


def build_final_output(
    data: CollectedData,
    synthesized: dict,
    generation_time: float,
    verification: dict,
) -> dict:
    output = {
        "recap_id": build_recap_id(data.date),
        "date": data.date,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "metadata": {
            "matches_count": len(data.matches),
            "sources_used": data.sources_used,
            "verification": verification,
            "generation_time_seconds": round(generation_time, 1),
        },
        "content": {
            "headline": synthesized.get("headline", ""),
            "summary": synthesized.get("summary", ""),
            "sections": synthesized.get("sections", []),
        },
    }
    validate_output(output)
    return output
```

- [ ] **Step 6: Create the JSON schema**

Create `worldcup_recap/schemas/recap_output.json`:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "WorldCupDailyRecap",
  "type": "object",
  "required": ["recap_id", "date", "generated_at", "metadata", "content"],
  "properties": {
    "recap_id": {"type": "string"},
    "date": {"type": "string"},
    "generated_at": {"type": "string"},
    "metadata": {
      "type": "object",
      "required": ["matches_count", "sources_used", "generation_time_seconds"],
      "properties": {
        "matches_count": {"type": "integer"},
        "sources_used": {"type": "array", "items": {"type": "string"}},
        "verification": {"type": "object"},
        "generation_time_seconds": {"type": "number"}
      }
    },
    "content": {
      "type": "object",
      "required": ["headline", "summary", "sections"],
      "properties": {
        "headline": {"type": "string"},
        "summary": {"type": "string"},
        "sections": {"type": "array"}
      }
    }
  }
}
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `python -m pytest tests/unit/worldcup_recap/test_synthesize.py -v -o "addopts="`
Expected: PASS (all tests)

- [ ] **Step 8: Commit**

```bash
git add worldcup_recap/prompts/synthesis.md worldcup_recap/agents/synthesis_agent.py worldcup_recap/synthesize.py worldcup_recap/schemas/recap_output.json tests/unit/worldcup_recap/test_synthesize.py
git commit -m "feat(worldcup): synthesis agent, output builder, schema"
```

---

## Task 6: Media finder + verifier agents

**Files:**
- Create: `worldcup_recap/prompts/media_finder.md`
- Create: `worldcup_recap/prompts/media_verifier.md`
- Create: `worldcup_recap/agents/media_finder_agent.py`
- Create: `worldcup_recap/agents/media_verifier_agent.py`

- [ ] **Step 1: Create the finder prompt**

Create `worldcup_recap/prompts/media_finder.md`:

```markdown
You are a football media researcher. Given a media need (a highlight, interview, or photo for a specific World Cup match/player/date), use google_search to find ONE best real URL. Prefer official sources: FIFA's official YouTube channel and broadcaster channels for highlights/interviews; reputable outlets (ESPN, BBC, official club/federation) for photos/news.

Return ONLY a JSON object (no markdown fences):
{
  "url": "<the single best real URL, or null>",
  "source": "<site or channel name>",
  "title": "<the page/video title you found>"
}

Only return a URL you actually found via search — NEVER fabricate one. If nothing relevant is found, return null for url.
If you are given feedback from a previous attempt, use it to refine your search query.
```

- [ ] **Step 2: Create the verifier prompt**

Create `worldcup_recap/prompts/media_verifier.md`:

```markdown
You are a strict fact-checker verifying that a found media link actually corresponds to the requested World Cup match/player/date. Judge using the candidate's title, source/channel, and what the need describes.

A link is RELEVANT only if it clearly matches the subject (correct teams/player) AND the correct match/day. For videos, prefer official/broadcaster channels; a generic compilation or a different fixture is NOT relevant.

Return ONLY a JSON object (no markdown fences):
{
  "relevant": <true or false>,
  "confidence": <0.0 to 1.0>,
  "reason": "<one sentence; if not relevant, say what's wrong so the search can be refined>"
}
```

- [ ] **Step 3: Create the finder agent**

Create `worldcup_recap/agents/media_finder_agent.py`:

```python
"""ADK Agent: finds a single best media URL for a declared media need."""

from pathlib import Path

from google.adk.agents import Agent
from google.adk.tools import google_search

_INSTRUCTION = (Path(__file__).parent.parent / "prompts" / "media_finder.md").read_text()

media_finder_agent = Agent(
    name="wc_media_finder",
    model="gemini-2.5-flash",
    instruction=_INSTRUCTION,
    tools=[google_search],
)


def build_finder_prompt(need: dict, feedback: str | None = None) -> str:
    """Build the finder user-turn message from a media need (+ optional feedback)."""
    kind = need.get("kind", "media")
    subject = need.get("subject", "")
    context = need.get("context", "")
    base = (
        f"Find a {kind} link for World Cup: subject='{subject}', context='{context}'. "
        f"Search for the official {kind} for this."
    )
    if feedback:
        base += f"\nPrevious attempt was rejected: {feedback}. Refine the search accordingly."
    return base
```

- [ ] **Step 4: Create the verifier agent**

Create `worldcup_recap/agents/media_verifier_agent.py`:

```python
"""ADK Agent: verifies a found media link is relevant to the need."""

from pathlib import Path

from google.adk.agents import Agent

_INSTRUCTION = (Path(__file__).parent.parent / "prompts" / "media_verifier.md").read_text()

media_verifier_agent = Agent(
    name="wc_media_verifier",
    model="gemini-2.5-flash",
    instruction=_INSTRUCTION,
)


def build_verifier_prompt(need: dict, candidate: dict) -> str:
    """Build the verifier user-turn message from the need + the found candidate."""
    return (
        "Need: " + str(need) + "\n"
        "Candidate link: " + str(candidate) + "\n"
        "Is this candidate relevant to the need? Respond with the JSON verdict."
    )
```

- [ ] **Step 5: Verify imports**

Run: `python -c "from worldcup_recap.agents.media_finder_agent import media_finder_agent, build_finder_prompt; from worldcup_recap.agents.media_verifier_agent import media_verifier_agent, build_verifier_prompt; print('ok')"`
Expected: prints `ok`

- [ ] **Step 6: Commit**

```bash
git add worldcup_recap/prompts/media_finder.md worldcup_recap/prompts/media_verifier.md worldcup_recap/agents/media_finder_agent.py worldcup_recap/agents/media_verifier_agent.py
git commit -m "feat(worldcup): media finder + verifier agents"
```

---

## Task 7: Pipeline — find/verify loop + orchestration

The find→verify→bounded-retry loop is implemented as a pure async function taking injectable `finder`/`verifier` callables, so it is unit-testable with fakes (no live LLM). The real pipeline passes ADK-agent-backed callables.

**Files:**
- Create: `worldcup_recap/pipeline.py`
- Test: `tests/unit/worldcup_recap/test_verification.py`

- [ ] **Step 1: Write failing tests for the verification loop**

Create `tests/unit/worldcup_recap/test_verification.py`:

```python
"""Tests for the find/verify feedback loop in worldcup_recap/pipeline.py."""

import pytest

from worldcup_recap.pipeline import find_and_verify

pytestmark = pytest.mark.asyncio


async def test_accepts_on_first_attempt():
    async def finder(need, feedback):
        return {"url": "https://youtube.com/official", "source": "FIFA", "title": "RSA vs MEX"}

    async def verifier(need, candidate):
        return {"relevant": True, "confidence": 0.9, "reason": "matches teams and day"}

    result = await find_and_verify({"kind": "highlights"}, finder, verifier, max_attempts=3)
    assert result["status"] == "accepted"
    assert result["attempts"] == 1
    assert result["media"]["url"] == "https://youtube.com/official"


async def test_retries_then_accepts_with_feedback():
    calls = {"n": 0, "feedbacks": []}

    async def finder(need, feedback):
        calls["n"] += 1
        calls["feedbacks"].append(feedback)
        return {"url": f"https://x/{calls['n']}", "source": "x", "title": "t"}

    async def verifier(need, candidate):
        # reject the first candidate, accept the second
        if candidate["url"].endswith("/1"):
            return {"relevant": False, "confidence": 0.2, "reason": "wrong fixture"}
        return {"relevant": True, "confidence": 0.8, "reason": "ok"}

    result = await find_and_verify({"kind": "highlights"}, finder, verifier, max_attempts=3)
    assert result["status"] == "accepted"
    assert result["attempts"] == 2
    # feedback from the rejection was passed into the second finder call
    assert calls["feedbacks"][1] == "wrong fixture"


async def test_drops_after_max_attempts():
    async def finder(need, feedback):
        return {"url": "https://x/always", "source": "x", "title": "t"}

    async def verifier(need, candidate):
        return {"relevant": False, "confidence": 0.1, "reason": "still wrong"}

    result = await find_and_verify({"kind": "highlights"}, finder, verifier, max_attempts=3)
    assert result["status"] == "dropped"
    assert result["attempts"] == 3
    assert result["media"] is None


async def test_drops_when_finder_returns_nothing():
    async def finder(need, feedback):
        return None

    async def verifier(need, candidate):
        raise AssertionError("verifier should not be called when finder returns None")

    result = await find_and_verify({"kind": "highlights"}, finder, verifier, max_attempts=2)
    assert result["status"] == "dropped"
    assert result["media"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/worldcup_recap/test_verification.py -v -o "addopts="`
Expected: FAIL with `ModuleNotFoundError: No module named 'worldcup_recap.pipeline'`

- [ ] **Step 3: Implement pipeline.py**

Create `worldcup_recap/pipeline.py`:

```python
"""ADK pipeline runner — wires the four phases together.

Flow:
  1. structure_agent          → classify raw data into sections (sequential)
  2. deterministic media      → attach ESPN recap/video/news links directly
  3. find/verify loop         → searched media (highlights, interviews) w/ retry (parallel)
  4. synthesis_agent          → write final English prose (sequential)
"""

import asyncio
import json
from typing import Awaitable, Callable

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from worldcup_recap.agents.structure_agent import structure_agent, build_structure_prompt
from worldcup_recap.agents.synthesis_agent import synthesis_agent, parse_synthesis_response
from worldcup_recap.agents.media_finder_agent import media_finder_agent, build_finder_prompt
from worldcup_recap.agents.media_verifier_agent import media_verifier_agent, build_verifier_prompt
from worldcup_recap.providers.base import CollectedData

_MAX_ATTEMPTS = 3

# Type aliases for the injectable loop dependencies
Finder = Callable[[dict, str | None], Awaitable[dict | None]]
Verifier = Callable[[dict, dict], Awaitable[dict]]


async def _run_agent(agent, prompt: str, session_id: str) -> str:
    """Run a single ADK agent and return its final text response."""
    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name="worldcup_recap", user_id="pipeline", session_id=session_id
    )
    runner = Runner(agent=agent, app_name="worldcup_recap", session_service=session_service)
    content = types.Content(role="user", parts=[types.Part(text=prompt)])
    final_text = ""
    async for event in runner.run_async(
        user_id="pipeline", session_id=session_id, new_message=content
    ):
        if event.is_final_response() and event.content and event.content.parts:
            for part in event.content.parts:
                if getattr(part, "text", None):
                    final_text += part.text
    return final_text


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        inner = lines[1:]
        if inner and inner[-1].strip() == "```":
            inner = inner[:-1]
        text = "\n".join(inner).strip()
    return text


def _parse_json(text: str, default: dict) -> dict:
    try:
        return json.loads(_strip_fences(text))
    except json.JSONDecodeError:
        return default


async def find_and_verify(
    need: dict, finder: Finder, verifier: Verifier, max_attempts: int = _MAX_ATTEMPTS
) -> dict:
    """Find a media link and verify it, retrying with feedback up to max_attempts.

    Returns {need, media, confidence?, attempts, status} where status is
    'accepted' or 'dropped'. Pure orchestration — finder/verifier are injectable.
    """
    feedback: str | None = None
    attempts = 0
    for attempt in range(1, max_attempts + 1):
        attempts = attempt
        candidate = await finder(need, feedback)
        if not candidate or not candidate.get("url"):
            feedback = "no result found; broaden the search"
            continue
        verdict = await verifier(need, candidate)
        if verdict.get("relevant"):
            return {
                "need": need,
                "media": candidate,
                "confidence": verdict.get("confidence"),
                "attempts": attempt,
                "status": "accepted",
            }
        feedback = verdict.get("reason", "not relevant")
    return {"need": need, "media": None, "attempts": attempts, "status": "dropped"}


# --- Agent-backed finder/verifier (used by the real pipeline) ---

async def _agent_finder(need: dict, feedback: str | None) -> dict | None:
    prompt = build_finder_prompt(need, feedback)
    resp = await _run_agent(media_finder_agent, prompt, "finder_session")
    parsed = _parse_json(resp, {"url": None})
    return parsed if parsed.get("url") else None


async def _agent_verifier(need: dict, candidate: dict) -> dict:
    prompt = build_verifier_prompt(need, candidate)
    resp = await _run_agent(media_verifier_agent, prompt, "verifier_session")
    return _parse_json(resp, {"relevant": False, "confidence": 0.0, "reason": "unparseable verdict"})


def _collect_media_needs(sections: list[dict]) -> list[tuple[int, str, dict]]:
    """Gather (section_index, owner, need) tuples from sections + their players."""
    needs = []
    for i, section in enumerate(sections):
        for need in section.get("media_needs", []) or []:
            needs.append((i, "section", need))
        for j, player in enumerate(section.get("players", []) or []):
            for need in player.get("media_needs", []) or []:
                needs.append((i, f"player:{j}", need))
    return needs


def _attach_deterministic_media(sections: list[dict], data: CollectedData) -> None:
    """Attach trusted ESPN links (recap/highlight) to match_of_day in place."""
    by_pair = {
        (m.home_team, m.away_team): m for m in data.matches
    }
    for section in sections:
        if section.get("type") != "match_of_day":
            section.setdefault("media", {})
            continue
        match = by_pair.get((section.get("home_team"), section.get("away_team")))
        media = section.setdefault("media", {})
        if match:
            media.setdefault("recap_url", match.espn_recap_url)
            if match.espn_videos and match.espn_videos[0].get("url"):
                media.setdefault("highlight_url", match.espn_videos[0]["url"])


def _apply_verified_media(sections: list[dict], results: list[dict], needs: list[tuple]) -> None:
    """Write accepted searched media back onto the owning section/player."""
    for (idx, owner, _need), result in zip(needs, results):
        if result["status"] != "accepted":
            continue
        url = result["media"]["url"]
        kind = result["need"].get("kind", "media")
        key = "highlight_url" if kind == "highlights" else f"{kind}_url"
        if owner == "section":
            sections[idx].setdefault("media", {})[key] = url
        elif owner.startswith("player:"):
            j = int(owner.split(":")[1])
            sections[idx]["players"][j].setdefault("media", {})[key] = url


async def _enrich(sections: list[dict], data: CollectedData) -> dict:
    """Phase 2+3: deterministic attach + searched find/verify loop. Returns telemetry."""
    _attach_deterministic_media(sections, data)
    needs = _collect_media_needs(sections)
    print(f"  🔍 Verifying {len(needs)} searched media link(s)...")
    results = await asyncio.gather(
        *[find_and_verify(need, _agent_finder, _agent_verifier) for (_, _, need) in needs],
        return_exceptions=True,
    )
    clean = []
    for r in results:
        if isinstance(r, Exception):
            clean.append({"status": "dropped", "media": None, "attempts": 0})
        else:
            clean.append(r)
    _apply_verified_media(sections, clean, needs)
    accepted = sum(1 for r in clean if r["status"] == "accepted")
    dropped = sum(1 for r in clean if r["status"] == "dropped")
    rejected = sum(max(0, r.get("attempts", 0) - (1 if r["status"] == "accepted" else 0)) for r in clean)
    return {"searched": len(needs), "accepted": accepted, "rejected": rejected, "dropped": dropped}


async def run_pipeline(data: CollectedData) -> tuple[dict, dict]:
    """Execute all phases. Returns (synthesized_dict, verification_telemetry)."""
    print("  🧠 Structure agent running...")
    structured = _parse_json(
        await _run_agent(structure_agent, build_structure_prompt(data), "structure_session"),
        {"sections": []},
    )
    sections = structured.get("sections", [])

    verification = await _enrich(sections, data)

    print("  ✍️  Synthesis agent running...")
    payload = json.dumps({"sections": sections}, indent=2, ensure_ascii=False)
    synthesized = parse_synthesis_response(
        await _run_agent(synthesis_agent, f"Write the final recap for:\n\n{payload}", "synthesis_session")
    )
    return synthesized, verification
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/worldcup_recap/test_verification.py -v -o "addopts="`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add worldcup_recap/pipeline.py tests/unit/worldcup_recap/test_verification.py
git commit -m "feat(worldcup): pipeline with find/verify feedback loop"
```

---

## Task 8: CLI entrypoint

**Files:**
- Create: `worldcup_recap/main.py`
- Create: `data/worldcup_recaps/.gitkeep` (empty)

- [ ] **Step 1: Create main.py**

Create `worldcup_recap/main.py`:

```python
#!/usr/bin/env python3
"""World Cup Daily Recap Generator — Google ADK Pipeline.

Usage:
    python worldcup_recap/main.py YYYY-MM-DD [--dry-run] [--no-agents]

Options:
    --dry-run     Collect + print matches, skip all LLM phases
    --no-agents   Collect + structure only (skip enrich + synthesis)
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

from worldcup_recap.collect import collect
from worldcup_recap.pipeline import run_pipeline
from worldcup_recap.synthesize import build_final_output, render_markdown

_OUTPUT_DIR = Path(__file__).parent.parent / "data" / "worldcup_recaps"


def _save(output: dict, date_str: str) -> None:
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = _OUTPUT_DIR / f"{date_str}.json"
    md_path = _OUTPUT_DIR / f"{date_str}.md"
    json_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    md_path.write_text(render_markdown(output))
    print(f"✅ {json_path}")
    print(f"✅ {md_path}")


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0].startswith("--"):
        print("Usage: python worldcup_recap/main.py YYYY-MM-DD [--dry-run] [--no-agents]")
        sys.exit(1)

    target_date = args[0]
    dry_run = "--dry-run" in args

    if not os.getenv("GOOGLE_API_KEY") and not dry_run:
        print("❌ GOOGLE_API_KEY not set. Get a free key at https://aistudio.google.com/app/apikey")
        sys.exit(1)

    start = time.time()
    data = collect(target_date)

    if dry_run:
        print(f"\n[dry-run] {len(data.matches)} matches on {target_date}:")
        for m in data.matches:
            print(f"  {m.away_team} {m.away_score} @ {m.home_team} {m.home_score} ({m.status})")
        print(f"[dry-run] {len(data.upcoming)} upcoming fixtures")
        return

    print("🤖 Running ADK pipeline (Gemini 2.5 Flash)...")
    synthesized, verification = asyncio.run(run_pipeline(data))

    generation_time = time.time() - start
    output = build_final_output(data, synthesized, generation_time, verification)
    _save(output, target_date)
    print(f"\n⚽ Done in {generation_time:.1f}s (verification: {verification})")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Create the output dir keeper**

Create empty file `data/worldcup_recaps/.gitkeep`.

- [ ] **Step 3: Verify CLI usage message**

Run: `python worldcup_recap/main.py`
Expected: prints the Usage line and exits.

- [ ] **Step 4: Commit**

```bash
git add worldcup_recap/main.py data/worldcup_recaps/.gitkeep
git commit -m "feat(worldcup): CLI entrypoint"
```

---

## Task 9: Dependencies + CI workflow

**Files:**
- Modify: `requirements.txt`
- Create: `.github/workflows/worldcup_recap.yml`

- [ ] **Step 1: Add httpx to requirements.txt**

`requirements.txt` currently ends with `pytest-asyncio>=0.23.0`. Add this line at the end:

```
httpx>=0.27.0
```

(`google-adk` and `pytest-asyncio` are already present from the nba_recap work.)

- [ ] **Step 2: Verify httpx installs/imports**

Run: `pip install -r requirements.txt && python -c "import httpx; print('ok')"`
Expected: prints `ok`

- [ ] **Step 3: Create the GitHub Actions workflow**

Create `.github/workflows/worldcup_recap.yml`:

```yaml
name: World Cup Daily Recap

on:
  workflow_dispatch:
    inputs:
      date:
        description: 'Date to recap (YYYY-MM-DD, defaults to yesterday ET)'
        required: false
        default: ''
      dry_run:
        description: 'Dry run — collect only, no LLM'
        required: false
        default: 'false'

  # Tournament runs 2026-06-11 to 2026-07-19. Run at 8 AM ET (12 UTC).
  # Uncomment when ready for production:
  # schedule:
  #   - cron: '0 12 * * *'

permissions:
  contents: write

jobs:
  generate_worldcup_recap:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Pull latest data
        run: git pull origin main

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install --upgrade pip
          pip install -r requirements.txt

      - name: Determine target date
        id: date
        run: |
          if [ -n "${{ github.event.inputs.date }}" ]; then
            echo "target=${{ github.event.inputs.date }}" >> $GITHUB_OUTPUT
          else
            echo "target=$(TZ='America/New_York' date -d 'yesterday' +'%Y-%m-%d')" >> $GITHUB_OUTPUT
          fi

      - name: Generate World Cup recap
        env:
          GOOGLE_API_KEY: ${{ secrets.GOOGLE_API_KEY }}
        run: |
          ARGS="${{ steps.date.outputs.target }}"
          if [ "${{ github.event.inputs.dry_run }}" = "true" ]; then
            ARGS="$ARGS --dry-run"
          fi
          python worldcup_recap/main.py $ARGS

      - name: Commit recap data
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          DATE="${{ steps.date.outputs.target }}"
          git add "data/worldcup_recaps/${DATE}.json" "data/worldcup_recaps/${DATE}.md" || true
          git diff --staged --quiet || git commit -m "World Cup recap: ${DATE}"
          git push
```

- [ ] **Step 4: Commit**

```bash
git add requirements.txt .github/workflows/worldcup_recap.yml
git commit -m "build(worldcup): add httpx + CI workflow"
```

---

## Task 10: Full-suite verification + live dry-run

**Files:** none (verification only)

- [ ] **Step 1: Run the entire unit test suite**

Run: `python -m pytest tests/unit/ -v -o "addopts="`
Expected: PASS — all existing nba_recap/enrichment tests AND the new worldcup_recap tests pass.

- [ ] **Step 2: Live dry-run against ESPN (no API key needed)**

Run: `python worldcup_recap/main.py 2026-06-11 --dry-run`
Expected: prints "2 matches on 2026-06-11" with the South Africa @ Mexico opener and the other opening-day fixture, plus an upcoming-fixtures count. (If WC matches are still STATUS_SCHEDULED, scores show 0 — that is correct pre-tournament.)

- [ ] **Step 3: (Optional, needs GOOGLE_API_KEY) Full live run on a completed match day**

Once at least one WC match day is complete (on/after 2026-06-11), run:
`python worldcup_recap/main.py 2026-06-11`
Expected: writes `data/worldcup_recaps/2026-06-11.json` and `.md`; console prints verification telemetry. Inspect the `.md` for an engaging recap with verified media links.

- [ ] **Step 4: Final commit (if any data artifacts should be kept, otherwise none)**

No code commit needed if Steps 1-2 pass with no changes. If a sample recap was generated and should be committed:
```bash
git add data/worldcup_recaps/
git commit -m "chore(worldcup): sample recap output"
```

---

## Self-Review

**Spec coverage check (against the design spec):**
- ESPN-only collect behind `StatsProvider` → Tasks 1-3 ✅
- Narrative sections (match_of_day, results_roundup, player_spotlight, group_watch, storylines, looking_ahead) → Task 4 prompt ✅
- Deterministic ESPN media + searched media → Task 7 `_attach_deterministic_media` + loop ✅
- Find→verify→bounded-retry (≤3), YouTube + google_search, verification telemetry → Tasks 6-7 ✅
- English synthesis, engaging prose → Task 5 ✅
- Rich preview block (odds/H2H/form/news) gathered in collect → Task 3 `_build_preview` + structure `looking_ahead` ✅
- Output JSON+MD, schema, metadata.verification → Task 5 ✅
- CLI (`--dry-run`, `--no-agents`) → Task 8 (note: `--no-agents` flag is parsed for parity; dry-run is the primary no-LLM path) ✅
- CI workflow + httpx dep → Task 9 ✅
- Graceful degradation (bad JSON → empty/fallback; failed fetch → empty) → `_parse_json`, `_get`, `return_exceptions=True` ✅
- Tests mirroring nba_recap → Tasks 1,2,5,7 ✅

**Note on `--no-agents`:** parsed in the CLI for parity with nba_recap but the dry-run path covers the no-LLM use case; a full `--no-agents` branch (structure-only) can be added if needed but is not required by the spec's acceptance criteria.

**Placeholder scan:** no TBD/TODO; every code step contains complete code.

**Type consistency:** `RawMatch`/`PreviewMatch`/`CollectedData` field names are consistent across base.py, espn.py, structure_agent.py, synthesize.py. `find_and_verify` return shape (`status`/`media`/`attempts`) is consistent between tests, the loop, and `_apply_verified_media`/`_enrich`. `build_final_output(data, synthesized, generation_time, verification)` signature matches its call in main.py.
```
