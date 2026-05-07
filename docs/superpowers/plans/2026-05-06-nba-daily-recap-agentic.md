# NBA Daily Recap Agentic Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone Python pipeline (`nba_recap/`) that collects NBA game data daily, classifies it into narrative sections, dispatches Google ADK subagents with real web search for media/article enrichment, and outputs a structured JSON + Markdown recap — all using Gemini 2.0 Flash (free tier via Google AI Studio).

**Architecture:** Phase 1 collects raw NBA data via `nba_api` (pure Python, no LLM). Phases 2–4 use Google ADK agents powered by Gemini 2.0 Flash: a structure agent classifies games into sections, parallel subagents (`GameDetailFetcher`, `PlayerMediaFinder`) use ADK's built-in `google_search` tool to find real article/media links, and a synthesis agent writes final prose. The root orchestrator coordinates all four phases. CLI entry point: `python nba_recap/main.py YYYY-MM-DD`.

**Tech Stack:** Python 3.11, `google-adk>=0.4.0`, `nba_api>=1.4.0`, `pytest`, `pytest-asyncio`, GitHub Actions, `GOOGLE_API_KEY` from [Google AI Studio](https://aistudio.google.com/app/apikey) (free)

---

## File Map

| File | Responsibility |
|------|---------------|
| `nba_recap/__init__.py` | Package marker |
| `nba_recap/collect.py` | Phase 1: fetch scoreboard + box scores from `nba_api` (no LLM) |
| `nba_recap/agents/__init__.py` | Package marker |
| `nba_recap/agents/structure_agent.py` | ADK Agent: classifies raw data into narrative sections |
| `nba_recap/agents/game_detail_agent.py` | ADK Agent: searches web for game recap articles + highlight links |
| `nba_recap/agents/player_media_agent.py` | ADK Agent: searches web for player headshots + interview clips |
| `nba_recap/agents/synthesis_agent.py` | ADK Agent: writes final narrative prose + compiles JSON output |
| `nba_recap/pipeline.py` | Runs all ADK agents in sequence/parallel; bridges collect → agents |
| `nba_recap/synthesize.py` | Output helpers: `build_final_output`, `render_markdown`, `validate_output` |
| `nba_recap/main.py` | CLI entry point |
| `nba_recap/prompts/structure.md` | System prompt for structure agent |
| `nba_recap/prompts/synthesis.md` | System prompt for synthesis agent |
| `nba_recap/schemas/recap_output.json` | JSON schema for output validation |
| `tests/unit/nba_recap/__init__.py` | Package marker |
| `tests/unit/nba_recap/test_collect.py` | Unit tests for data collection |
| `tests/unit/nba_recap/test_agents.py` | Unit tests for ADK agent helpers |
| `tests/unit/nba_recap/test_synthesize.py` | Unit tests for output compilation |
| `data/nba_recaps/.gitkeep` | Ensure output directory is tracked |
| `.github/workflows/nba_recap.yml` | GitHub Actions cron at 8 AM ET |

---

## Task 1: Project Scaffold & Dependencies

**Files:**
- Create: `nba_recap/__init__.py`, `nba_recap/agents/__init__.py`
- Create: `nba_recap/prompts/structure.md`, `nba_recap/prompts/synthesis.md`
- Create: `nba_recap/schemas/recap_output.json`
- Create: `data/nba_recaps/.gitkeep`
- Create: `tests/unit/nba_recap/__init__.py`
- Modify: `requirements.txt`

- [ ] **Step 1: Add dependencies to requirements.txt**

  Open `requirements.txt` and append:

  ```
  google-adk>=0.4.0
  nba_api>=1.4.0
  pytest-asyncio>=0.23.0
  ```

  Final file:
  ```
  yfpy>=17.0.0
  beautifulsoup4>=4.12.0
  requests>=2.31.0
  anthropic>=0.40.0
  google-adk>=0.4.0
  nba_api>=1.4.0
  pytest-asyncio>=0.23.0
  ```

- [ ] **Step 2: Create directory structure**

  ```bash
  mkdir -p nba_recap/agents nba_recap/prompts nba_recap/schemas
  mkdir -p tests/unit/nba_recap
  mkdir -p data/nba_recaps
  touch nba_recap/__init__.py
  touch nba_recap/agents/__init__.py
  touch tests/unit/nba_recap/__init__.py
  touch data/nba_recaps/.gitkeep
  ```

- [ ] **Step 3: Create structure prompt**

  Write `nba_recap/prompts/structure.md`:

  ```markdown
  You are an NBA content editor. Given raw NBA game data for a single day as JSON, classify it into narrative sections.

  Return a JSON object with EXACTLY this shape (no markdown fences, no explanation):
  {
    "sections": [
      {
        "order": 1,
        "type": "game_of_night",
        "title": "Game of the Night",
        "game_id": "<game_id from input>",
        "home_team": "<abbr>",
        "away_team": "<abbr>",
        "home_score": 0,
        "away_score": 0,
        "narrative": "<2-3 sentence story arc>",
        "key_players": ["<name1>", "<name2>"]
      },
      {
        "order": 2,
        "type": "player_spotlight",
        "title": "Top Performers",
        "players": [
          {
            "name": "<full name>",
            "team": "<abbr>",
            "line": "<PTS/REB/AST>",
            "context": "<why this is notable>"
          }
        ]
      },
      {
        "order": 3,
        "type": "storylines",
        "title": "Key Storylines",
        "stories": [
          {"headline": "<text>", "summary": "<1 sentence>"}
        ]
      },
      {
        "order": 4,
        "type": "quick_hits",
        "title": "Around the League",
        "games": [
          {"matchup": "<AWAY SCORE @ HOME SCORE>", "note": "<1 notable thing>"}
        ]
      },
      {
        "order": 5,
        "type": "looking_ahead",
        "title": "Tonight's Matchups",
        "upcoming": [
          {"home": "<abbr>", "away": "<abbr>", "time_et": "TBD", "storyline": "<text>"}
        ]
      }
    ]
  }

  Selection rules:
  - game_of_night: overtime first; otherwise closest margin; pick 1 game
  - player_spotlight: top 3 by pts; triple-doubles always included regardless of pts
  - storylines: injuries, playoff implications, records, milestones (2-3 items)
  - quick_hits: all remaining games not featured in game_of_night (one line each)
  - looking_ahead: the upcoming_games list from input data
  ```

- [ ] **Step 4: Create synthesis prompt**

  Write `nba_recap/prompts/synthesis.md`:

  ```markdown
  You are an NBA journalist writing a daily recap. You receive structured section data enriched with media links.

  Return a JSON object with EXACTLY this shape (no markdown fences):
  {
    "headline": "<one punchy sentence summarizing the biggest story of the night>",
    "summary": "<2-3 sentences covering the top 2 stories>",
    "sections": [ <same sections array you received, with narrative fields improved> ]
  }

  Rules:
  - Improve each section's "narrative" field with 2-4 sentences of clean, engaging prose
  - Only use stats from the input data — never hallucinate numbers
  - headline must mention at least one player name or team name
  - If a section has a recap_url in its media, reference that it is available but do not embed it in prose
  ```

- [ ] **Step 5: Create JSON output schema**

  Write `nba_recap/schemas/recap_output.json`:

  ```json
  {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "NBADailyRecap",
    "type": "object",
    "required": ["recap_id", "date", "generated_at", "metadata", "content"],
    "properties": {
      "recap_id": {"type": "string"},
      "date": {"type": "string"},
      "generated_at": {"type": "string"},
      "metadata": {
        "type": "object",
        "required": ["games_count", "sources_used", "generation_time_seconds"],
        "properties": {
          "games_count": {"type": "integer"},
          "sources_used": {"type": "array", "items": {"type": "string"}},
          "subagents_spawned": {"type": "integer"},
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

- [ ] **Step 6: Add asyncio_mode to pytest.ini**

  Open `pytest.ini` and add the asyncio_mode line under `[pytest]`:

  ```ini
  [pytest]
  testpaths = tests
  python_files = test_*.py
  python_classes = Test*
  python_functions = test_*
  addopts = -v
  asyncio_mode = auto
  ```

- [ ] **Step 7: Install dependencies**

  ```bash
  uv pip install google-adk nba_api pytest-asyncio
  ```

  Or: `pip install google-adk nba_api pytest-asyncio`

- [ ] **Step 8: Verify ADK import**

  ```bash
  python -c "from google.adk.agents import Agent; from google.adk.runners import Runner; print('ADK OK')"
  python -c "from nba_api.stats.endpoints import ScoreboardV2; print('nba_api OK')"
  ```

  Expected:
  ```
  ADK OK
  nba_api OK
  ```

- [ ] **Step 9: Set up GOOGLE_API_KEY**

  Get a free API key from https://aistudio.google.com/app/apikey and add to `.env`:

  ```bash
  echo "GOOGLE_API_KEY=your_key_here" >> .env
  ```

  The key enables both Gemini model calls and search grounding in ADK agents.

- [ ] **Step 10: Commit scaffold**

  ```bash
  git add nba_recap/ tests/unit/nba_recap/ data/nba_recaps/.gitkeep requirements.txt pytest.ini
  git commit -m "feat: scaffold nba-daily-recap module with ADK dependencies"
  ```

---

## Task 2: Data Collector

**Files:**
- Create: `nba_recap/collect.py`
- Create: `tests/unit/nba_recap/test_collect.py`

Pure Python — no LLM. Fetches from `nba_api` (free, no auth required).

- [ ] **Step 1: Write failing tests**

  Create `tests/unit/nba_recap/test_collect.py`:

  ```python
  """Tests for nba_recap/collect.py."""

  import pytest
  from nba_recap.collect import (
      build_game_record,
      select_top_performers,
      parse_standings_entry,
      RawGameData,
  )


  def test_build_game_record_basic():
      raw = {
          "GAME_ID": "0022600001",
          "HOME_TEAM_ABBREVIATION": "LAL",
          "VISITOR_TEAM_ABBREVIATION": "GSW",
          "PTS_HOME": 128,
          "PTS_AWAY": 112,
          "GAME_STATUS_TEXT": "Final",
      }
      result = build_game_record(raw)
      assert result["game_id"] == "0022600001"
      assert result["home_team"] == "LAL"
      assert result["away_team"] == "GSW"
      assert result["home_score"] == 128
      assert result["away_score"] == 112
      assert result["margin"] == 16
      assert result["overtime"] is False


  def test_build_game_record_overtime():
      raw = {
          "GAME_ID": "0022600002",
          "HOME_TEAM_ABBREVIATION": "BOS",
          "VISITOR_TEAM_ABBREVIATION": "MIL",
          "PTS_HOME": 115,
          "PTS_AWAY": 113,
          "GAME_STATUS_TEXT": "Final/OT",
      }
      result = build_game_record(raw)
      assert result["overtime"] is True
      assert result["margin"] == 2


  def test_select_top_performers_sorted_by_pts():
      performers = [
          {"name": "A", "pts": 20, "reb": 5, "ast": 3},
          {"name": "B", "pts": 40, "reb": 8, "ast": 6},
          {"name": "C", "pts": 30, "reb": 4, "ast": 2},
      ]
      result = select_top_performers(performers, n=2)
      assert len(result) == 2
      assert result[0]["name"] == "B"


  def test_select_top_performers_triple_double_elevated():
      performers = [
          {"name": "Star", "pts": 40, "reb": 5, "ast": 3},
          {"name": "Triple", "pts": 18, "reb": 11, "ast": 10},
      ]
      result = select_top_performers(performers, n=2)
      names = [p["name"] for p in result]
      assert "Triple" in names


  def test_select_top_performers_empty():
      assert select_top_performers([], n=5) == []


  def test_parse_standings_entry():
      raw = {
          "TeamAbbreviation": "LAL",
          "TeamID": 1610612747,
          "WINS": 45,
          "LOSSES": 37,
          "Conference": "West",
      }
      result = parse_standings_entry(raw)
      assert result["team"] == "LAL"
      assert result["wins"] == 45
      assert result["conference"] == "West"


  def test_raw_game_data_structure():
      game = RawGameData(
          game_id="0022600001",
          home_team="LAL",
          away_team="GSW",
          home_score=128,
          away_score=112,
          status="Final",
          margin=16,
          overtime=False,
          top_performers=[],
          injuries=[],
      )
      assert game.game_id == "0022600001"
      assert game.overtime is False
  ```

- [ ] **Step 2: Run tests to verify they fail**

  ```bash
  python -m pytest tests/unit/nba_recap/test_collect.py -v -o "addopts="
  ```

  Expected: `ImportError: cannot import name 'build_game_record' from 'nba_recap.collect'`

- [ ] **Step 3: Implement collect.py**

  Create `nba_recap/collect.py`:

  ```python
  """Phase 1: NBA data collection — fetches scoreboard, box scores, standings via nba_api.

  No LLM involved. nba_api uses public stats.nba.com endpoints — no API key required.
  """

  import time
  from dataclasses import dataclass, field
  from datetime import date, timedelta


  @dataclass
  class RawGameData:
      game_id: str
      home_team: str
      away_team: str
      home_score: int
      away_score: int
      status: str
      margin: int
      overtime: bool
      top_performers: list[dict]
      injuries: list[dict]


  @dataclass
  class CollectedData:
      date: str
      games: list[RawGameData]
      standings_east: list[dict]
      standings_west: list[dict]
      upcoming_games: list[dict]
      sources_used: list[str] = field(default_factory=list)


  def build_game_record(raw: dict) -> dict:
      """Normalize a raw NBA API scoreboard row into a game dict."""
      home_score = raw.get("PTS_HOME") or 0
      away_score = raw.get("PTS_AWAY") or 0
      status = raw.get("GAME_STATUS_TEXT", "")
      return {
          "game_id": raw["GAME_ID"],
          "home_team": raw["HOME_TEAM_ABBREVIATION"],
          "away_team": raw["VISITOR_TEAM_ABBREVIATION"],
          "home_score": home_score,
          "away_score": away_score,
          "status": status,
          "margin": abs(home_score - away_score),
          "overtime": "OT" in status.upper(),
      }


  def select_top_performers(performers: list[dict], n: int = 5) -> list[dict]:
      """Return top n performers; triple-doubles are always included first."""
      if not performers:
          return []
      triple_doubles = [p for p in performers if _is_triple_double(p)]
      rest = sorted(
          [p for p in performers if not _is_triple_double(p)],
          key=lambda p: p.get("pts", 0),
          reverse=True,
      )
      return (triple_doubles + rest)[:n]


  def _is_triple_double(p: dict) -> bool:
      return sum(1 for c in [p.get("pts", 0), p.get("reb", 0), p.get("ast", 0)] if c >= 10) >= 3


  def parse_standings_entry(raw: dict) -> dict:
      return {
          "team": raw.get("TeamAbbreviation", ""),
          "team_id": raw.get("TeamID"),
          "wins": raw.get("WINS", 0),
          "losses": raw.get("LOSSES", 0),
          "conference": raw.get("Conference", ""),
      }


  def _nba_rows(endpoint_result, attribute: str) -> list[dict]:
      data = endpoint_result.get_dict()
      headers = data["resultSets"][0]["headers"] if "resultSets" in data else data[attribute]["headers"]
      rows = data["resultSets"][0]["rowSet"] if "resultSets" in data else data[attribute]["data"]
      return [dict(zip(headers, row)) for row in rows]


  def _fetch_scoreboard(game_date: str) -> list[dict]:
      from nba_api.stats.endpoints import ScoreboardV2
      time.sleep(0.6)
      board = ScoreboardV2(game_date=game_date, timeout=30)
      d = board.game_header.get_dict()
      return [dict(zip(d["headers"], row)) for row in d["data"]]


  def _fetch_box_score_performers(game_id: str) -> list[dict]:
      from nba_api.stats.endpoints import BoxScoreTraditionalV2
      time.sleep(0.6)
      try:
          box = BoxScoreTraditionalV2(game_id=game_id, timeout=30)
          d = box.player_stats.get_dict()
          players = [dict(zip(d["headers"], row)) for row in d["data"]]
          result = []
          for p in players:
              if p.get("MIN") is None:
                  continue
              result.append({
                  "name": p.get("PLAYER_NAME", ""),
                  "team": p.get("TEAM_ABBREVIATION", ""),
                  "pts": p.get("PTS") or 0,
                  "reb": p.get("REB") or 0,
                  "ast": p.get("AST") or 0,
                  "stl": p.get("STL") or 0,
                  "blk": p.get("BLK") or 0,
              })
          return result
      except Exception as e:
          print(f"  ⚠️  Box score failed for {game_id}: {e}")
          return []


  def _fetch_standings() -> tuple[list[dict], list[dict]]:
      from nba_api.stats.endpoints import LeagueStandingsV3
      time.sleep(0.6)
      try:
          s = LeagueStandingsV3(timeout=30)
          d = s.standings.get_dict()
          all_teams = [dict(zip(d["headers"], row)) for row in d["data"]]
          east = [parse_standings_entry(t) for t in all_teams if t.get("Conference") == "East"]
          west = [parse_standings_entry(t) for t in all_teams if t.get("Conference") == "West"]
          return east, west
      except Exception as e:
          print(f"  ⚠️  Standings failed: {e}")
          return [], []


  def _fetch_upcoming(target_date: str) -> list[dict]:
      from nba_api.stats.endpoints import ScoreboardV2
      next_day = (date.fromisoformat(target_date) + timedelta(days=1)).isoformat()
      time.sleep(0.6)
      try:
          board = ScoreboardV2(game_date=next_day, timeout=30)
          d = board.game_header.get_dict()
          rows = [dict(zip(d["headers"], row)) for row in d["data"]]
          return [
              {
                  "home": r.get("HOME_TEAM_ABBREVIATION", ""),
                  "away": r.get("VISITOR_TEAM_ABBREVIATION", ""),
                  "game_id": r.get("GAME_ID", ""),
              }
              for r in rows
          ]
      except Exception as e:
          print(f"  ⚠️  Upcoming games failed: {e}")
          return []


  def collect(target_date: str) -> CollectedData:
      """Fetch all NBA data for target_date (YYYY-MM-DD). No LLM calls."""
      print(f"📊 Collecting NBA data for {target_date}...")
      scoreboard_rows = _fetch_scoreboard(target_date)
      games: list[RawGameData] = []
      for row in scoreboard_rows:
          base = build_game_record(row)
          performers = _fetch_box_score_performers(base["game_id"])
          games.append(RawGameData(
              game_id=base["game_id"],
              home_team=base["home_team"],
              away_team=base["away_team"],
              home_score=base["home_score"],
              away_score=base["away_score"],
              status=base["status"],
              margin=base["margin"],
              overtime=base["overtime"],
              top_performers=performers,
              injuries=[],
          ))
      east, west = _fetch_standings()
      upcoming = _fetch_upcoming(target_date)
      print(f"  ✅ {len(games)} games, {len(east)+len(west)} standings entries")
      return CollectedData(
          date=target_date,
          games=games,
          standings_east=east,
          standings_west=west,
          upcoming_games=upcoming,
          sources_used=["nba_api"],
      )
  ```

- [ ] **Step 4: Run tests to verify they pass**

  ```bash
  python -m pytest tests/unit/nba_recap/test_collect.py -v -o "addopts="
  ```

  Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

  ```bash
  git add nba_recap/collect.py tests/unit/nba_recap/test_collect.py
  git commit -m "feat: implement NBA data collector (Phase 1)"
  ```

---

## Task 3: ADK Agent Definitions

**Files:**
- Create: `nba_recap/agents/structure_agent.py`
- Create: `nba_recap/agents/game_detail_agent.py`
- Create: `nba_recap/agents/player_media_agent.py`
- Create: `nba_recap/agents/synthesis_agent.py`
- Create: `tests/unit/nba_recap/test_agents.py`

Each agent is defined as a module-level constant so it can be imported and reused without re-instantiation.

> **Note on `google_search` tool:** ADK's built-in `google_search` uses Gemini's search grounding feature — it is included in the free tier of Google AI Studio with rate limits. It lets the model search the web and cite sources, which is exactly what `GameDetailFetcher` and `PlayerMediaFinder` need.

- [ ] **Step 1: Write failing tests**

  Create `tests/unit/nba_recap/test_agents.py`:

  ```python
  """Tests for nba_recap/agents/ — ADK agent definitions and helpers."""

  import pytest
  from unittest.mock import AsyncMock, MagicMock, patch

  from nba_recap.agents.structure_agent import build_structure_prompt
  from nba_recap.agents.game_detail_agent import build_game_search_prompt
  from nba_recap.agents.player_media_agent import build_player_search_prompt
  from nba_recap.agents.synthesis_agent import parse_synthesis_response
  from nba_recap.collect import CollectedData, RawGameData


  # --- build_structure_prompt ---

  def _make_collected_data():
      game = RawGameData(
          game_id="0022600001",
          home_team="LAL", away_team="GSW",
          home_score=128, away_score=112,
          status="Final", margin=16, overtime=False,
          top_performers=[
              {"name": "LeBron James", "team": "LAL", "pts": 38, "reb": 8, "ast": 6},
          ],
          injuries=[],
      )
      return CollectedData(
          date="2026-05-05",
          games=[game],
          standings_east=[{"team": "BOS", "wins": 58, "losses": 24, "conference": "East"}],
          standings_west=[{"team": "OKC", "wins": 62, "losses": 20, "conference": "West"}],
          upcoming_games=[{"home": "DEN", "away": "OKC", "game_id": "0022600010"}],
          sources_used=["nba_api"],
      )


  def test_build_structure_prompt_contains_date():
      data = _make_collected_data()
      prompt = build_structure_prompt(data)
      assert "2026-05-05" in prompt


  def test_build_structure_prompt_contains_game_ids():
      data = _make_collected_data()
      prompt = build_structure_prompt(data)
      assert "0022600001" in prompt


  def test_build_structure_prompt_contains_teams():
      data = _make_collected_data()
      prompt = build_structure_prompt(data)
      assert "LAL" in prompt
      assert "GSW" in prompt


  # --- build_game_search_prompt ---

  def test_build_game_search_prompt_contains_teams():
      prompt = build_game_search_prompt("LAL", "GSW", "2026-05-05")
      assert "Lakers" in prompt or "LAL" in prompt
      assert "Warriors" in prompt or "GSW" in prompt
      assert "2026-05-05" in prompt or "May" in prompt


  def test_build_game_search_prompt_asks_for_recap():
      prompt = build_game_search_prompt("BOS", "MIL", "2026-05-05")
      assert any(word in prompt.lower() for word in ["recap", "highlight", "article"])


  # --- build_player_search_prompt ---

  def test_build_player_search_prompt_contains_name():
      prompt = build_player_search_prompt("LeBron James", "LAL", "38/8/6")
      assert "LeBron James" in prompt


  def test_build_player_search_prompt_asks_for_image():
      prompt = build_player_search_prompt("Victor Wembanyama", "SAS", "35/15/5")
      assert any(word in prompt.lower() for word in ["image", "photo", "headshot"])


  # --- parse_synthesis_response ---

  def test_parse_synthesis_response_valid_json():
      response = '{"headline": "Big night", "summary": "Good games.", "sections": []}'
      result = parse_synthesis_response(response)
      assert result["headline"] == "Big night"
      assert result["sections"] == []


  def test_parse_synthesis_response_strips_markdown_fences():
      response = '```json\n{"headline": "Test", "summary": "s", "sections": []}\n```'
      result = parse_synthesis_response(response)
      assert result["headline"] == "Test"


  def test_parse_synthesis_response_invalid_returns_fallback():
      result = parse_synthesis_response("not json at all")
      assert "headline" in result
      assert "sections" in result
  ```

- [ ] **Step 2: Run tests to verify they fail**

  ```bash
  python -m pytest tests/unit/nba_recap/test_agents.py -v -o "addopts="
  ```

  Expected: `ImportError`

- [ ] **Step 3: Implement structure_agent.py**

  Create `nba_recap/agents/structure_agent.py`:

  ```python
  """ADK Agent: classifies raw NBA data into narrative sections."""

  import json
  import os
  from pathlib import Path

  from google.adk.agents import Agent

  from nba_recap.collect import CollectedData


  _SYSTEM_PROMPT = (Path(__file__).parent.parent / "prompts" / "structure.md").read_text()


  structure_agent = Agent(
      name="nba_structure_agent",
      model="gemini-2.0-flash",
      instruction=_SYSTEM_PROMPT,
  )


  def build_structure_prompt(data: CollectedData) -> str:
      """Build the user-turn message for the structure agent."""
      games_list = []
      for g in data.games:
          games_list.append({
              "game_id": g.game_id,
              "home_team": g.home_team,
              "away_team": g.away_team,
              "home_score": g.home_score,
              "away_score": g.away_score,
              "status": g.status,
              "margin": g.margin,
              "overtime": g.overtime,
              "top_performers": g.top_performers[:5],
          })
      payload = {
          "date": data.date,
          "games": games_list,
          "standings_east": data.standings_east[:5],
          "standings_west": data.standings_west[:5],
          "upcoming_games": data.upcoming_games,
      }
      return f"Structure this NBA data:\n\n{json.dumps(payload, indent=2)}"
  ```

- [ ] **Step 4: Implement game_detail_agent.py**

  Create `nba_recap/agents/game_detail_agent.py`:

  ```python
  """ADK Agent: searches the web for game recap articles and highlight links."""

  from google.adk.agents import Agent
  from google.adk.tools import google_search


  _INSTRUCTION = """
  You are a sports researcher. Given an NBA game matchup and date, use google_search to find:
  1. An official game recap article URL (ESPN, NBA.com, or The Athletic)
  2. A YouTube highlight video URL for the game

  Return a JSON object with exactly these keys:
  {
    "recap_url": "<url or null>",
    "highlight_url": "<url or null>",
    "source": "<site name>"
  }

  Search for the specific game. Only return real URLs you found — never fabricate them.
  If you cannot find a URL, use null.
  Return ONLY the JSON object, no explanation, no markdown fences.
  """


  game_detail_agent = Agent(
      name="nba_game_detail_fetcher",
      model="gemini-2.0-flash",
      instruction=_INSTRUCTION,
      tools=[google_search],
  )


  def build_game_search_prompt(home_team: str, away_team: str, date: str) -> str:
      """Build the user-turn message for the game detail agent."""
      return (
          f"Find recap article and highlight video for the NBA game: "
          f"{away_team} @ {home_team} on {date}. "
          f"Search for '{away_team} vs {home_team} {date} NBA recap highlights'."
      )
  ```

- [ ] **Step 5: Implement player_media_agent.py**

  Create `nba_recap/agents/player_media_agent.py`:

  ```python
  """ADK Agent: searches the web for player headshots and post-game interviews."""

  from google.adk.agents import Agent
  from google.adk.tools import google_search


  _INSTRUCTION = """
  You are a sports media researcher. Given an NBA player's name, team, and stat line, use google_search to find:
  1. An official player headshot or action photo URL (prefer cdn.nba.com or espn.com)
  2. A post-game interview or highlight clip URL (prefer YouTube or ESPN)

  Return a JSON object with exactly these keys:
  {
    "headshot_url": "<url or null>",
    "interview_url": "<url or null>"
  }

  Only return real URLs you found via search — never fabricate them.
  If you cannot find a URL, use null.
  Return ONLY the JSON object, no explanation, no markdown fences.
  """


  player_media_agent = Agent(
      name="nba_player_media_finder",
      model="gemini-2.0-flash",
      instruction=_INSTRUCTION,
      tools=[google_search],
  )


  def build_player_search_prompt(player_name: str, team: str, stat_line: str) -> str:
      """Build the user-turn message for the player media agent."""
      return (
          f"Find headshot image and post-game interview for NBA player: "
          f"{player_name} ({team}), who had {stat_line} tonight. "
          f"Search for '{player_name} NBA headshot photo' and '{player_name} post-game interview 2026'."
      )
  ```

- [ ] **Step 6: Implement synthesis_agent.py**

  Create `nba_recap/agents/synthesis_agent.py`:

  ```python
  """ADK Agent: writes final narrative prose and compiles the JSON output."""

  import json
  from pathlib import Path

  from google.adk.agents import Agent


  _SYSTEM_PROMPT = (Path(__file__).parent.parent / "prompts" / "synthesis.md").read_text()


  synthesis_agent = Agent(
      name="nba_synthesis_agent",
      model="gemini-2.0-flash",
      instruction=_SYSTEM_PROMPT,
  )


  def parse_synthesis_response(response_text: str) -> dict:
      """Parse the synthesis agent's JSON response, stripping markdown fences if present."""
      text = response_text.strip()
      if text.startswith("```"):
          lines = text.split("\n")
          text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
          text = text.strip()
      try:
          return json.loads(text)
      except json.JSONDecodeError:
          return {
              "headline": "NBA Daily Recap",
              "summary": "A full night of NBA action.",
              "sections": [],
          }
  ```

- [ ] **Step 7: Run tests to verify they pass**

  ```bash
  python -m pytest tests/unit/nba_recap/test_agents.py -v -o "addopts="
  ```

  Expected: All 10 tests PASS

- [ ] **Step 8: Commit**

  ```bash
  git add nba_recap/agents/ tests/unit/nba_recap/test_agents.py
  git commit -m "feat: implement ADK agent definitions (Phases 2-4)"
  ```

---

## Task 4: Synthesis Helpers & Output

**Files:**
- Create: `nba_recap/synthesize.py`
- Create: `tests/unit/nba_recap/test_synthesize.py`

These are pure functions — no LLM, no ADK. They assemble and validate the final output dict.

- [ ] **Step 1: Write failing tests**

  Create `tests/unit/nba_recap/test_synthesize.py`:

  ```python
  """Tests for nba_recap/synthesize.py — output compilation helpers."""

  import pytest
  from nba_recap.synthesize import (
      build_recap_id,
      render_markdown,
      validate_output,
      build_final_output,
  )
  from nba_recap.collect import CollectedData


  def test_build_recap_id():
      assert build_recap_id("2026-05-05") == "nba-daily-2026-05-05"


  def test_render_markdown_headline():
      output = {
          "content": {"headline": "Celtics Win", "summary": "Boston wins.", "sections": []},
          "date": "2026-05-05",
      }
      md = render_markdown(output)
      assert "Celtics Win" in md
      assert "2026-05-05" in md


  def test_render_markdown_section_narrative():
      output = {
          "content": {
              "headline": "Test",
              "summary": "Summary.",
              "sections": [
                  {
                      "order": 1,
                      "type": "game_of_night",
                      "title": "Game of the Night",
                      "narrative": "Epic game.",
                      "media": {"recap_url": "https://espn.com/test"},
                  }
              ],
          },
          "date": "2026-05-05",
      }
      md = render_markdown(output)
      assert "Game of the Night" in md
      assert "Epic game." in md
      assert "https://espn.com/test" in md


  def test_validate_output_valid():
      output = {
          "recap_id": "nba-daily-2026-05-05",
          "date": "2026-05-05",
          "generated_at": "2026-05-05T08:00:00Z",
          "metadata": {"games_count": 5, "sources_used": ["nba_api"], "generation_time_seconds": 45.0},
          "content": {"headline": "Test", "summary": "Summary.", "sections": []},
      }
      validate_output(output)  # should not raise


  def test_validate_output_missing_key_raises():
      with pytest.raises(ValueError, match="Missing required field"):
          validate_output({"recap_id": "x", "date": "2026-05-05"})


  def test_build_final_output_structure():
      data = CollectedData(
          date="2026-05-05",
          games=[],
          standings_east=[],
          standings_west=[],
          upcoming_games=[],
          sources_used=["nba_api"],
      )
      synthesized = {"headline": "Big Night", "summary": "Good games.", "sections": []}
      result = build_final_output(data=data, synthesized=synthesized, generation_time=30.5, subagents_spawned=4)
      assert result["recap_id"] == "nba-daily-2026-05-05"
      assert result["metadata"]["subagents_spawned"] == 4
      assert result["content"]["headline"] == "Big Night"
  ```

- [ ] **Step 2: Run tests to verify they fail**

  ```bash
  python -m pytest tests/unit/nba_recap/test_synthesize.py -v -o "addopts="
  ```

  Expected: `ImportError`

- [ ] **Step 3: Implement synthesize.py**

  Create `nba_recap/synthesize.py`:

  ```python
  """Output helpers: build final JSON, render Markdown, validate schema."""

  from datetime import datetime, timezone

  from nba_recap.collect import CollectedData


  _REQUIRED_KEYS = {"recap_id", "date", "generated_at", "metadata", "content"}


  def build_recap_id(date_str: str) -> str:
      return f"nba-daily-{date_str}"


  def validate_output(output: dict) -> None:
      """Raise ValueError if any required top-level key is missing."""
      missing = _REQUIRED_KEYS - set(output.keys())
      if missing:
          raise ValueError(f"Missing required field(s): {', '.join(sorted(missing))}")


  def render_markdown(output: dict) -> str:
      """Render the final output dict as a Markdown string."""
      content = output.get("content", {})
      date_str = output.get("date", "")
      lines = [
          f"# {content.get('headline', 'NBA Daily Recap')}",
          f"*{date_str}*",
          "",
          content.get("summary", ""),
          "",
      ]
      for section in content.get("sections", []):
          lines.append(f"## {section.get('title', '')}")
          lines.append("")
          if section.get("narrative"):
              lines.append(section["narrative"])
              lines.append("")
          media = section.get("media", {})
          if media.get("recap_url"):
              lines.append(f"[Full recap]({media['recap_url']})")
              lines.append("")
      return "\n".join(lines)


  def build_final_output(
      data: CollectedData,
      synthesized: dict,
      generation_time: float,
      subagents_spawned: int,
  ) -> dict:
      output = {
          "recap_id": build_recap_id(data.date),
          "date": data.date,
          "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
          "metadata": {
              "games_count": len(data.games),
              "sources_used": data.sources_used,
              "subagents_spawned": subagents_spawned,
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

- [ ] **Step 4: Run tests to verify they pass**

  ```bash
  python -m pytest tests/unit/nba_recap/test_synthesize.py -v -o "addopts="
  ```

  Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

  ```bash
  git add nba_recap/synthesize.py tests/unit/nba_recap/test_synthesize.py
  git commit -m "feat: implement output helpers (render_markdown, validate_output)"
  ```

---

## Task 5: ADK Pipeline Runner

**Files:**
- Create: `nba_recap/pipeline.py`

This module wires all four ADK agents together. It runs the structure agent first, then dispatches game detail and player media agents in parallel, then runs the synthesis agent.

- [ ] **Step 1: Implement pipeline.py**

  Create `nba_recap/pipeline.py`:

  ```python
  """ADK pipeline runner — wires the four agents together.

  Flow:
    1. structure_agent  → classifies raw data into sections (sequential)
    2. game_detail_agent + player_media_agent → enrich sections (parallel)
    3. synthesis_agent  → writes final prose + compiles output (sequential)
  """

  import asyncio
  import json
  import os

  from google.adk.runners import Runner
  from google.adk.sessions import InMemorySessionService
  from google.genai import types

  from nba_recap.agents.game_detail_agent import game_detail_agent, build_game_search_prompt
  from nba_recap.agents.player_media_agent import player_media_agent, build_player_search_prompt
  from nba_recap.agents.structure_agent import structure_agent, build_structure_prompt
  from nba_recap.agents.synthesis_agent import synthesis_agent, parse_synthesis_response
  from nba_recap.collect import CollectedData


  def _make_runner(agent, session_id: str) -> Runner:
      return Runner(
          agent=agent,
          app_name="nba_recap",
          session_service=InMemorySessionService(),
      )


  async def _run_agent(agent, prompt: str, session_id: str) -> str:
      """Run a single ADK agent and return the final text response."""
      runner = _make_runner(agent, session_id)
      content = types.Content(role="user", parts=[types.Part(text=prompt)])
      final_text = ""
      async for event in runner.run_async(
          user_id="pipeline",
          session_id=session_id,
          new_message=content,
      ):
          if event.is_final_response():
              for part in event.content.parts:
                  if hasattr(part, "text") and part.text:
                      final_text += part.text
      return final_text


  async def _run_structure(data: CollectedData) -> dict:
      """Phase 2: classify raw data into sections."""
      print("  🧠 Structure agent running...")
      prompt = build_structure_prompt(data)
      response = await _run_agent(structure_agent, prompt, "structure_session")
      try:
          return json.loads(response.strip())
      except json.JSONDecodeError:
          print("  ⚠️  Structure agent returned invalid JSON, using empty sections")
          return {"sections": []}


  async def _enrich_game_section(section: dict, date: str) -> dict:
      """Run game_detail_agent for a game_of_night section."""
      home = section.get("home_team", "")
      away = section.get("away_team", "")
      if not home or not away:
          return {**section, "media": {"recap_url": None, "highlight_url": None}}
      prompt = build_game_search_prompt(home, away, date)
      response = await _run_agent(game_detail_agent, prompt, f"game_{home}_{away}")
      try:
          media = json.loads(response.strip())
      except json.JSONDecodeError:
          media = {"recap_url": None, "highlight_url": None}
      return {**section, "media": media}


  async def _enrich_player_section(section: dict) -> dict:
      """Run player_media_agent for each player in a player_spotlight section."""
      players = section.get("players", [])
      enriched_players = []
      tasks = []
      for player in players[:3]:
          prompt = build_player_search_prompt(
              player.get("name", ""),
              player.get("team", ""),
              player.get("line", ""),
          )
          tasks.append(_run_agent(player_media_agent, prompt, f"player_{player.get('name','').replace(' ','_')}"))
      results = await asyncio.gather(*tasks, return_exceptions=True)
      for player, result in zip(players[:3], results):
          if isinstance(result, Exception):
              media = {"headshot_url": None, "interview_url": None}
          else:
              try:
                  media = json.loads(result.strip())
              except (json.JSONDecodeError, AttributeError):
                  media = {"headshot_url": None, "interview_url": None}
          enriched_players.append({**player, "media": media})
      return {**section, "players": enriched_players, "media": {}}


  async def _enrich_sections(sections: list[dict], date: str) -> tuple[list[dict], int]:
      """Phase 3: enrich all sections in parallel. Returns (enriched_sections, subagents_spawned)."""
      print(f"  🔍 Enriching {len(sections)} sections via subagents...")
      tasks = []
      subagents_spawned = 0
      for section in sections:
          if section.get("type") == "game_of_night":
              tasks.append(_enrich_game_section(section, date))
              subagents_spawned += 1
          elif section.get("type") == "player_spotlight":
              tasks.append(_enrich_player_section(section))
              subagents_spawned += min(3, len(section.get("players", [])))
          else:
              tasks.append(asyncio.coroutine(lambda s=section: s)())
      enriched = await asyncio.gather(*tasks)
      return list(enriched), subagents_spawned


  async def _run_synthesis(enriched_sections: list[dict]) -> dict:
      """Phase 4: write final narrative and compile output."""
      print("  ✍️  Synthesis agent running...")
      payload = json.dumps({"sections": enriched_sections}, indent=2)
      prompt = f"Write final narrative for this recap:\n\n{payload}"
      response = await _run_agent(synthesis_agent, prompt, "synthesis_session")
      return parse_synthesis_response(response)


  async def run_pipeline(data: CollectedData) -> tuple[dict, int]:
      """Execute all four phases. Returns (synthesized_dict, subagents_spawned)."""
      structured = await _run_structure(data)
      sections = structured.get("sections", [])
      enriched_sections, subagents_spawned = await _enrich_sections(sections, data.date)
      synthesized = await _run_synthesis(enriched_sections)
      return synthesized, subagents_spawned
  ```

- [ ] **Step 2: Verify the pipeline module imports cleanly**

  ```bash
  python -c "from nba_recap.pipeline import run_pipeline; print('pipeline OK')"
  ```

  Expected: `pipeline OK`

- [ ] **Step 3: Commit**

  ```bash
  git add nba_recap/pipeline.py
  git commit -m "feat: implement ADK pipeline runner (all four phases)"
  ```

---

## Task 6: CLI Entry Point

**Files:**
- Create: `nba_recap/main.py`

- [ ] **Step 1: Implement main.py**

  Create `nba_recap/main.py`:

  ```python
  #!/usr/bin/env python3
  """
  NBA Daily Recap Generator — Google ADK Pipeline

  Usage:
      python nba_recap/main.py YYYY-MM-DD [--dry-run] [--no-agents]

  Options:
      --dry-run     Print collected game data, skip all LLM phases
      --no-agents   Run collect + structure only, skip enrichment and synthesis
  """

  import asyncio
  import json
  import os
  import sys
  import time
  from pathlib import Path

  from dotenv import load_dotenv

  load_dotenv(Path(__file__).parent.parent / ".env")

  from nba_recap.collect import collect
  from nba_recap.pipeline import run_pipeline
  from nba_recap.synthesize import build_final_output, render_markdown


  _OUTPUT_DIR = Path(__file__).parent.parent / "data" / "nba_recaps"


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
          print("Usage: python nba_recap/main.py YYYY-MM-DD [--dry-run] [--no-agents]")
          sys.exit(1)

      target_date = args[0]
      dry_run = "--dry-run" in args

      if not os.getenv("GOOGLE_API_KEY") and not dry_run:
          print("❌ GOOGLE_API_KEY not set. Get a free key at https://aistudio.google.com/app/apikey")
          sys.exit(1)

      start = time.time()

      # Phase 1: Collect (pure Python, no LLM)
      data = collect(target_date)

      if dry_run:
          print(f"\n[dry-run] {len(data.games)} games on {target_date}:")
          for g in data.games:
              ot = " (OT)" if g.overtime else ""
              print(f"  {g.away_team} {g.away_score} @ {g.home_team} {g.home_score}{ot}")
          return

      # Phases 2-4: ADK agents
      print(f"🤖 Running ADK pipeline (Gemini 2.0 Flash)...")
      synthesized, subagents_spawned = asyncio.run(run_pipeline(data))

      generation_time = time.time() - start
      output = build_final_output(data, synthesized, generation_time, subagents_spawned)
      _save(output, target_date)
      print(f"\n🏀 Done in {generation_time:.1f}s ({subagents_spawned} subagents)")


  if __name__ == "__main__":
      main()
  ```

- [ ] **Step 2: Verify CLI help**

  ```bash
  python nba_recap/main.py
  ```

  Expected:
  ```
  Usage: python nba_recap/main.py YYYY-MM-DD [--dry-run] [--no-agents]
  ```

- [ ] **Step 3: Smoke test dry-run**

  ```bash
  python nba_recap/main.py 2026-04-30 --dry-run
  ```

  Expected: Prints game list for 2026-04-30 (or "0 games" if NBA API is temporarily down — that is acceptable).

- [ ] **Step 4: Commit**

  ```bash
  git add nba_recap/main.py
  git commit -m "feat: add CLI entry point for nba-daily-recap"
  ```

---

## Task 7: GitHub Actions Workflow

**Files:**
- Create: `.github/workflows/nba_recap.yml`

- [ ] **Step 1: Create workflow**

  Create `.github/workflows/nba_recap.yml`:

  ```yaml
  name: NBA Daily Recap

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

    # Run at 8 AM ET (12 UTC) after all games from previous night are complete
    # Uncomment when ready for production:
    # schedule:
    #   - cron: '0 12 * * *'

  permissions:
    contents: write

  jobs:
    generate_nba_recap:
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

        - name: Generate NBA recap
          env:
            GOOGLE_API_KEY: ${{ secrets.GOOGLE_API_KEY }}
            BALLDONTLIE_API_KEY: ${{ secrets.BALLDONTLIE_API_KEY }}
          run: |
            ARGS="${{ steps.date.outputs.target }}"
            if [ "${{ github.event.inputs.dry_run }}" = "true" ]; then
              ARGS="$ARGS --dry-run"
            fi
            python nba_recap/main.py $ARGS

        - name: Commit recap data
          run: |
            git config user.name "github-actions[bot]"
            git config user.email "github-actions[bot]@users.noreply.github.com"
            DATE="${{ steps.date.outputs.target }}"
            git add "data/nba_recaps/${DATE}.json" "data/nba_recaps/${DATE}.md" || true
            git diff --staged --quiet || git commit -m "NBA recap: ${DATE}"
            git push
  ```

- [ ] **Step 2: Add GOOGLE_API_KEY to GitHub repo secrets**

  In the GitHub repo, go to **Settings → Secrets and variables → Actions** and add:
  - `GOOGLE_API_KEY` — your key from https://aistudio.google.com/app/apikey

- [ ] **Step 3: Validate YAML**

  ```bash
  python -c "import yaml; yaml.safe_load(open('.github/workflows/nba_recap.yml').read()); print('YAML valid')"
  ```

  Expected: `YAML valid`

- [ ] **Step 4: Commit**

  ```bash
  git add .github/workflows/nba_recap.yml
  git commit -m "feat: add GitHub Actions workflow for NBA daily recap"
  ```

---

## Task 8: Full Test Suite

- [ ] **Step 1: Run all tests**

  ```bash
  python -m pytest tests/unit/ -v -o "addopts="
  ```

  Expected: All existing tests (21+) plus the 23 new nba_recap tests PASS. Zero failures.

- [ ] **Step 2: Verify all imports**

  ```bash
  python -c "
  from nba_recap.collect import collect, build_game_record, select_top_performers, RawGameData
  from nba_recap.agents.structure_agent import structure_agent, build_structure_prompt
  from nba_recap.agents.game_detail_agent import game_detail_agent, build_game_search_prompt
  from nba_recap.agents.player_media_agent import player_media_agent, build_player_search_prompt
  from nba_recap.agents.synthesis_agent import synthesis_agent, parse_synthesis_response
  from nba_recap.pipeline import run_pipeline
  from nba_recap.synthesize import build_final_output, render_markdown, validate_output
  print('All imports OK')
  "
  ```

  Expected: `All imports OK`

- [ ] **Step 3: Live end-to-end test (requires GOOGLE_API_KEY)**

  ```bash
  python nba_recap/main.py 2026-04-30
  ```

  Expected:
  ```
  📊 Collecting NBA data for 2026-04-30...
    ✅ N games, M standings entries
  🤖 Running ADK pipeline (Gemini 2.0 Flash)...
    🧠 Structure agent running...
    🔍 Enriching N sections via subagents...
    ✍️  Synthesis agent running...
  ✅ data/nba_recaps/2026-04-30.json
  ✅ data/nba_recaps/2026-04-30.md
  🏀 Done in ~Xs (N subagents)
  ```

---

## Self-Review

**Spec coverage:**

| Spec requirement | Where implemented |
|-----------------|------------------|
| NBA API (scoreboard, box scores, standings) | `collect.py` |
| Content classification into 5 section types | `structure_agent.py` + structure prompt |
| GameDetailFetcher subagent with web search | `game_detail_agent.py` (ADK + google_search) |
| PlayerMediaFinder subagent with web search | `player_media_agent.py` (ADK + google_search) |
| Parallel subagent execution | `pipeline.py` → `asyncio.gather` |
| Final JSON output with schema | `synthesize.py` + `schemas/recap_output.json` |
| Markdown output | `synthesize.py` → `render_markdown` |
| CLI (YYYY-MM-DD arg, --dry-run) | `main.py` |
| GitHub Actions cron at 8 AM ET | `nba_recap.yml` |
| Google ADK throughout | All `agents/` modules |
| Gemini 2.0 Flash (free tier) | All `Agent(model="gemini-2.0-flash")` |
| No Claude / no Anthropic API | ✅ removed from this module |

**Out of scope (from spec's optional/future sections):**
- StorylineResearcher subagent (needs news API key — add as follow-up)
- VisualAssetFinder subagent (player_media_agent covers core need)
- WhatsApp / Telegram distribution (external service setup, separate task)
- Root orchestrator as an ADK parent agent (the pipeline.py module fills this role functionally; wrapping in ADK adds complexity without clear benefit given the sequential nature of phases 1→2→3→4)
