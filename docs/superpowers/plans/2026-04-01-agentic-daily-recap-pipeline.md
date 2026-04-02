# Agentic Daily Recap Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an agentic pipeline that enriches daily fantasy data (missed opportunities, achievements, projections vs actuals, league context), then feeds it to an LLM to generate a Turkish-language daily recap for WhatsApp/email distribution.

**Architecture:** Three-layer pipeline: (1) data enrichment script that merges daily stats + projected stats + matchup data into a single enriched JSON, (2) league context script that adds standings/streaks/schedule, (3) orchestrator that chains everything and calls the LLM. Each layer is a standalone script that reads/writes JSON files, composable via CLI or the orchestrator.

**Tech Stack:** Python 3.11, existing yfpy integration, OpenAI-compatible LLM API (Anthropic Claude), GitHub Actions for scheduling.

---

## File Structure

```
cron/
├── fetch_daily_stats.py          # EXISTS — daily stats collection
├── fetch_projected_stats.py      # EXISTS — projected stats scraping
├── analyze_yesterday_games.py    # EXISTS — will be replaced by enrich_daily_data.py
├── enrich_daily_data.py          # NEW — merges daily + projected, computes missed opps, achievements
├── fetch_league_context.py       # NEW — standings, streaks, games remaining, week metadata
├── generate_recap.py             # NEW — orchestrator: gathers data → enriches → calls LLM → outputs recap
llm/
├── daily-recap-prompt.md         # UPDATED (already done above)
data/
├── daily_stats/                  # EXISTS
├── projected_stats/              # EXISTS
├── analysis/                     # EXISTS — will contain enriched JSON output
├── recaps/                       # NEW — final LLM-generated recaps
.github/workflows/
├── daily_recap.yml               # NEW — orchestrates the full pipeline
```

---

### Task 1: `enrich_daily_data.py` — Core Enrichment Script

This is the heart of the pipeline. Takes raw daily stats + projected stats and produces enriched analysis JSON with missed opportunities, achievements, and proper active/inactive classification.

**Files:**
- Create: `cron/enrich_daily_data.py`
- Create: `tests/test_enrich_daily_data.py`
- Read: `data/daily_stats/league_93905_2026-03-31.json` (sample input)
- Read: `data/projected_stats/league_93905_2026-03-31.json` (sample input)

#### Input/Output Contract

**Inputs (files on disk):**
- `data/daily_stats/league_93905_{date}.json` — actual stats per player per team
- `data/projected_stats/league_93905_{date}.json` — projected stats per player per team

**Output (file on disk):**
- `data/analysis/enriched_{date}.json`

**Output schema:**

```json
{
  "date": "2026-03-31",
  "week": 23,
  "league_name": "teletabi ligi",
  "teams": [
    {
      "team_name": "Ankara Tinercileri",
      "team_id": "1",
      "daily_active_points": 269.5,
      "daily_total_points_all": 300.0,
      "players": [
        {
          "name": "Jalen Brunson",
          "nba_team": "NYK",
          "opponent": "HOU",
          "roster_position": "PG",
          "is_active_position": true,
          "had_game": true,
          "fantasy_points": 31.2,
          "projected_fantasy_points": 40.05,
          "projection_diff": -8.85,
          "projection_diff_pct": -22.1,
          "stats_summary": {"PTS": 12, "REB": 6, "AST": 8, "ST": 1, "BLK": 0, "TO": 3},
          "achievements": []
        }
      ],
      "missed_opportunities": [
        {
          "bench_player": "Miles Bridges",
          "bench_position": "BN",
          "bench_points": 43.0,
          "active_player_replaced": "Collin Gillespie",
          "active_position": "G",
          "active_points": 21.9,
          "points_lost": 21.1,
          "swap_feasible": true
        }
      ]
    }
  ],
  "top_5_active": [...],
  "daily_awards": {
    "mvp": {"name": "...", "team": "...", "points": 0},
    "biggest_disappointment": {"name": "...", "team": "...", "points": 0, "projected": 0, "diff_pct": 0},
    "biggest_surprise": {"name": "...", "team": "...", "points": 0, "projected": 0, "diff_pct": 0},
    "worst_missed_opportunity": {"team": "...", "bench_player": "...", "points_lost": 0}
  }
}
```

- [ ] **Step 1: Write failing tests for active/inactive classification**

```python
# tests/test_enrich_daily_data.py
import pytest
from cron.enrich_daily_data import classify_player, ACTIVE_POSITIONS, INACTIVE_POSITIONS


def test_active_positions():
    for pos in ["PG", "SG", "G", "SF", "PF", "F", "C", "Util"]:
        assert classify_player(pos) == "active"


def test_inactive_positions():
    for pos in ["BN", "IL", "IL+"]:
        assert classify_player(pos) == "inactive"


def test_had_game_with_opponent():
    # Player has opponent field populated → had a game
    player = {"opponent": "HOU", "fantasy_points": 0.0}
    assert had_game(player) is True


def test_no_game_empty_opponent():
    player = {"opponent": "", "fantasy_points": 0.0}
    assert had_game(player) is False
```

- [ ] **Step 2: Run tests — expect FAIL (module doesn't exist yet)**

```bash
cd /Users/onuryildirim/Documents/workspace/opencommish
python -m pytest tests/test_enrich_daily_data.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Write failing tests for missed opportunity detection**

```python
# tests/test_enrich_daily_data.py (append)
from cron.enrich_daily_data import find_missed_opportunities


def _make_player(name, pos, pts, opponent="OPP"):
    return {
        "name": name,
        "roster_position": pos,
        "fantasy_points": pts,
        "opponent": opponent,
        "nba_team": "TST",
        "stats": [],
        "player_id": "1",
        "player_key": "466.p.1",
    }


def test_missed_opp_bench_higher_than_active():
    """BN player scored more than a compatible active player → missed opportunity."""
    players = [
        _make_player("Active Guy", "G", 20.0),
        _make_player("Bench Star", "BN", 45.0),
    ]
    # Bench Star is a guard who could have replaced Active Guy at G
    opps = find_missed_opportunities(players, eligible_positions={"Bench Star": ["PG", "SG", "G"]})
    assert len(opps) == 1
    assert opps[0]["bench_player"] == "Bench Star"
    assert opps[0]["points_lost"] == 25.0


def test_no_missed_opp_bench_lower_than_active():
    """BN player scored less than all active players → no missed opportunity."""
    players = [
        _make_player("Active Guy", "G", 45.0),
        _make_player("Bench Scrub", "BN", 10.0),
    ]
    opps = find_missed_opportunities(players, eligible_positions={"Bench Scrub": ["PG", "SG", "G"]})
    assert len(opps) == 0


def test_no_missed_opp_bench_no_game():
    """BN player had no game → no missed opportunity."""
    players = [
        _make_player("Active Guy", "G", 20.0),
        _make_player("Bench NoGame", "BN", 0.0, opponent=""),
    ]
    opps = find_missed_opportunities(players, eligible_positions={"Bench NoGame": ["PG", "SG", "G"]})
    assert len(opps) == 0


def test_no_missed_opp_il_no_swap_possible():
    """IL+ player scored high but IL players can't be directly swapped into active slots."""
    players = [
        _make_player("Active Guy", "G", 20.0),
        _make_player("IL Star", "IL+", 60.0),
    ]
    # IL+ players need a roster move first — this is flagged differently
    opps = find_missed_opportunities(players, eligible_positions={"IL Star": ["PG", "SG", "G"]})
    # IL+ should still show up but with swap_feasible=False
    assert len(opps) == 1
    assert opps[0]["swap_feasible"] is False
```

- [ ] **Step 4: Write failing tests for achievement detection**

```python
# tests/test_enrich_daily_data.py (append)
from cron.enrich_daily_data import detect_achievements


def test_double_double():
    stats = {"PTS": 20, "REB": 12, "AST": 3, "ST": 1, "BLK": 0}
    assert "double-double" in detect_achievements(stats)


def test_triple_double():
    stats = {"PTS": 20, "REB": 12, "AST": 11, "ST": 1, "BLK": 0}
    achievements = detect_achievements(stats)
    assert "triple-double" in achievements
    assert "double-double" not in achievements  # triple-double supersedes


def test_no_achievement():
    stats = {"PTS": 15, "REB": 4, "AST": 3, "ST": 1, "BLK": 0}
    assert detect_achievements(stats) == []
```

- [ ] **Step 5: Implement `enrich_daily_data.py`**

```python
#!/usr/bin/env python3
"""
Enrich daily fantasy data by merging actual stats with projections,
computing missed opportunities, achievements, and daily awards.

Usage:
    python cron/enrich_daily_data.py YYYY-MM-DD

Reads:
    data/daily_stats/league_93905_{date}.json
    data/projected_stats/league_93905_{date}.json

Writes:
    data/analysis/enriched_{date}.json
"""

import json
import sys
from pathlib import Path

ACTIVE_POSITIONS = {"PG", "SG", "G", "SF", "PF", "F", "C", "Util"}
INACTIVE_POSITIONS = {"BN", "IL", "IL+"}

# Which active roster slots each position abbreviation can fill.
# Used to determine if a bench player could have replaced an active player.
POSITION_COMPATIBILITY = {
    "PG": {"PG", "G", "Util"},
    "SG": {"SG", "G", "Util"},
    "SF": {"SF", "F", "Util"},
    "PF": {"PF", "F", "Util"},
    "C":  {"C", "Util"},
    "G":  {"PG", "SG", "G", "Util"},
    "F":  {"SF", "PF", "F", "Util"},
    "Util": {"PG", "SG", "G", "SF", "PF", "F", "C", "Util"},
}


def classify_player(roster_position: str) -> str:
    """Return 'active' or 'inactive' based on roster position."""
    if roster_position in ACTIVE_POSITIONS:
        return "active"
    return "inactive"


def had_game(player: dict) -> bool:
    """Determine if a player had an NBA game that day."""
    return bool(player.get("opponent"))


def detect_achievements(stats: dict) -> list[str]:
    """Detect double-double, triple-double from stat categories.

    Only PTS, REB, AST, ST, BLK count (standard NBA categories for multi-doubles).
    """
    double_digit_cats = sum(
        1 for cat in ["PTS", "REB", "AST", "ST", "BLK"]
        if stats.get(cat, 0) >= 10
    )
    if double_digit_cats >= 3:
        return ["triple-double"]
    if double_digit_cats >= 2:
        return ["double-double"]
    return []


def find_missed_opportunities(
    players: list[dict],
    eligible_positions: dict[str, list[str]] | None = None,
) -> list[dict]:
    """Find cases where an inactive player outscored a swappable active player.

    Args:
        players: All players on a team with roster_position, fantasy_points, opponent.
        eligible_positions: Map of player name → list of position abbreviations they
            can play. If not provided, uses the player's eligible_positions field
            or falls back to their roster_position.

    Returns:
        List of missed opportunity dicts with bench_player, active_player_replaced,
        points_lost, and swap_feasible.
    """
    active = [p for p in players if classify_player(p["roster_position"]) == "active"]
    inactive = [p for p in players if classify_player(p["roster_position"]) == "inactive"]

    opportunities = []
    used_active = set()  # track which active players we've already "swapped out"

    # Sort inactive by points descending — greedily assign best bench player first
    inactive_with_games = [p for p in inactive if had_game(p) and p["fantasy_points"] > 0]
    inactive_with_games.sort(key=lambda p: p["fantasy_points"], reverse=True)

    for bench_p in inactive_with_games:
        bench_name = bench_p["name"]
        bench_pos = bench_p["roster_position"]
        is_il = bench_pos in ("IL", "IL+")

        # Determine which active slots this player could fill
        if eligible_positions and bench_name in eligible_positions:
            elig = set(eligible_positions[bench_name])
        elif "eligible_positions" in bench_p:
            elig = set()
            for ep in bench_p["eligible_positions"]:
                elig.update(POSITION_COMPATIBILITY.get(ep, set()))
        else:
            elig = POSITION_COMPATIBILITY.get(bench_pos, {"Util"})

        # Find the worst active player at a compatible position
        worst_active = None
        worst_pts = float("inf")
        for act_p in active:
            if act_p["name"] in used_active:
                continue
            if act_p["roster_position"] in elig and act_p["fantasy_points"] < bench_p["fantasy_points"]:
                if act_p["fantasy_points"] < worst_pts:
                    worst_pts = act_p["fantasy_points"]
                    worst_active = act_p

        if worst_active:
            points_lost = round(bench_p["fantasy_points"] - worst_active["fantasy_points"], 2)
            used_active.add(worst_active["name"])
            opportunities.append({
                "bench_player": bench_name,
                "bench_position": bench_pos,
                "bench_points": round(bench_p["fantasy_points"], 2),
                "active_player_replaced": worst_active["name"],
                "active_position": worst_active["roster_position"],
                "active_points": round(worst_active["fantasy_points"], 2),
                "points_lost": points_lost,
                "swap_feasible": not is_il,  # IL/IL+ requires roster move, not just lineup swap
            })

    return opportunities


def build_stats_summary(stats_list: list[dict]) -> dict:
    """Convert detailed stats list to simple {display_name: value} dict."""
    return {s["display_name"]: s["value"] for s in stats_list}


def merge_projection(player: dict, projected_players: dict) -> dict:
    """Add projection data to a player dict."""
    proj = projected_players.get(player.get("player_id") or player.get("name"))
    if proj:
        player["projected_fantasy_points"] = proj["fantasy_points"]
        diff = player["fantasy_points"] - proj["fantasy_points"]
        player["projection_diff"] = round(diff, 2)
        pct = (diff / proj["fantasy_points"] * 100) if proj["fantasy_points"] else 0
        player["projection_diff_pct"] = round(pct, 1)
    else:
        player["projected_fantasy_points"] = None
        player["projection_diff"] = None
        player["projection_diff_pct"] = None
    return player


def enrich(daily_data: dict, projected_data: dict | None) -> dict:
    """Main enrichment: merge, classify, compute missed opps, achievements, awards."""
    # Build projection lookup: player_id → projected player data
    proj_lookup_by_team: dict[str, dict] = {}
    if projected_data:
        for team in projected_data.get("teams", []):
            team_proj = {}
            for p in team.get("players", []):
                pid = p.get("player_id") or p.get("player_name")
                team_proj[str(pid)] = p
                # Also index by name for fallback matching
                if "player_name" in p:
                    team_proj[p["player_name"]] = p
            proj_lookup_by_team[team["team_name"]] = team_proj

    enriched_teams = []
    all_active_players = []

    for team in daily_data["teams"]:
        team_name = team["team_name"]
        proj_players = proj_lookup_by_team.get(team_name, {})

        enriched_players = []
        for p in team["players"]:
            ep = {
                "name": p["name"],
                "player_id": p.get("player_id"),
                "nba_team": p.get("nba_team", ""),
                "opponent": p.get("opponent", ""),
                "roster_position": p["roster_position"],
                "is_active_position": classify_player(p["roster_position"]) == "active",
                "had_game": had_game(p),
                "fantasy_points": round(p["fantasy_points"], 2),
                "stats_summary": build_stats_summary(p.get("stats", [])),
                "achievements": detect_achievements(build_stats_summary(p.get("stats", []))),
            }
            ep = merge_projection(ep, proj_players)
            enriched_players.append(ep)

            if ep["is_active_position"] and ep["had_game"]:
                all_active_players.append({**ep, "team_name": team_name})

        # Missed opportunities
        missed_opps = find_missed_opportunities(team["players"])

        active_pts = sum(
            p["fantasy_points"] for p in enriched_players if p["is_active_position"]
        )
        total_pts = sum(p["fantasy_points"] for p in enriched_players)

        enriched_teams.append({
            "team_name": team_name,
            "team_id": team.get("team_id"),
            "daily_active_points": round(active_pts, 2),
            "daily_total_points_all": round(total_pts, 2),
            "players": enriched_players,
            "missed_opportunities": missed_opps,
        })

    # Top 5 active performers
    all_active_players.sort(key=lambda p: p["fantasy_points"], reverse=True)
    top_5 = all_active_players[:5]

    # Awards
    awards = compute_awards(all_active_players, enriched_teams)

    return {
        "date": daily_data["date"],
        "week": daily_data.get("week"),
        "league_name": daily_data.get("league_name", "teletabi ligi"),
        "teams": enriched_teams,
        "top_5_active": [
            {
                "name": p["name"],
                "team_name": p["team_name"],
                "nba_team": p["nba_team"],
                "fantasy_points": p["fantasy_points"],
                "roster_position": p["roster_position"],
                "stats_summary": p["stats_summary"],
                "achievements": p["achievements"],
            }
            for p in top_5
        ],
        "daily_awards": awards,
    }


def compute_awards(all_active: list[dict], teams: list[dict]) -> dict:
    """Compute daily awards from enriched data."""
    awards = {}

    # MVP — highest scoring active player
    if all_active:
        mvp = all_active[0]
        awards["mvp"] = {
            "name": mvp["name"],
            "team": mvp["team_name"],
            "points": mvp["fantasy_points"],
        }

    # Biggest disappointment — active player with worst projection_diff_pct (who had a game)
    with_proj = [p for p in all_active if p.get("projected_fantasy_points") and p["projected_fantasy_points"] > 20]
    if with_proj:
        worst = min(with_proj, key=lambda p: p["projection_diff_pct"] or 0)
        if worst.get("projection_diff_pct", 0) < -25:
            awards["biggest_disappointment"] = {
                "name": worst["name"],
                "team": worst["team_name"],
                "points": worst["fantasy_points"],
                "projected": worst["projected_fantasy_points"],
                "diff_pct": worst["projection_diff_pct"],
            }

    # Biggest surprise — active player with best projection_diff_pct
    if with_proj:
        best = max(with_proj, key=lambda p: p["projection_diff_pct"] or 0)
        if best.get("projection_diff_pct", 0) > 25:
            awards["biggest_surprise"] = {
                "name": best["name"],
                "team": best["team_name"],
                "points": best["fantasy_points"],
                "projected": best["projected_fantasy_points"],
                "diff_pct": best["projection_diff_pct"],
            }

    # Worst missed opportunity across all teams
    worst_miss = None
    for team in teams:
        for opp in team.get("missed_opportunities", []):
            if worst_miss is None or opp["points_lost"] > worst_miss["points_lost"]:
                worst_miss = {**opp, "team": team["team_name"]}
    if worst_miss:
        awards["worst_missed_opportunity"] = worst_miss

    return awards


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python cron/enrich_daily_data.py YYYY-MM-DD")
        sys.exit(1)

    target_date = sys.argv[1]
    data_dir = Path(__file__).parent.parent / "data"

    # Load daily stats
    daily_path = data_dir / "daily_stats" / f"league_93905_{target_date}.json"
    if not daily_path.exists():
        print(f"❌ Daily stats not found: {daily_path}")
        sys.exit(1)
    with open(daily_path) as f:
        daily_data = json.load(f)

    # Load projected stats (optional)
    proj_path = data_dir / "projected_stats" / f"league_93905_{target_date}.json"
    projected_data = None
    if proj_path.exists():
        with open(proj_path) as f:
            projected_data = json.load(f)
        print(f"✅ Loaded projections from {proj_path.name}")
    else:
        print(f"⚠️ No projections found for {target_date}, enriching without projections")

    result = enrich(daily_data, projected_data)

    # Save enriched output
    output_dir = data_dir / "analysis"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"enriched_{target_date}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"✅ Enriched analysis saved to {output_path}")
    print(f"   Teams: {len(result['teams'])}")
    missed_total = sum(len(t['missed_opportunities']) for t in result['teams'])
    print(f"   Missed opportunities: {missed_total}")
    achiev_total = sum(
        1 for t in result['teams'] for p in t['players'] if p['achievements']
    )
    print(f"   Achievements: {achiev_total}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Run tests — expect PASS**

```bash
python -m pytest tests/test_enrich_daily_data.py -v
```

- [ ] **Step 7: Integration test with real data**

```bash
python cron/enrich_daily_data.py 2026-03-31
cat data/analysis/enriched_2026-03-31.json | python -m json.tool | head -80
```

Verify:
- Luka Doncic (IL+) is NOT in `top_5_active`
- Miles Bridges (BN) shows up in Izmirin Boyozlari's `missed_opportunities` if applicable
- Players with empty `opponent` have `had_game: false`
- Double-doubles are detected (e.g., Cooper Flagg had 19 PTS + 10 REB)

- [ ] **Step 8: Commit**

```bash
git add cron/enrich_daily_data.py tests/test_enrich_daily_data.py
git commit -m "feat: add daily data enrichment with missed opportunities and achievements"
```

---

### Task 2: `fetch_league_context.py` — Standings, Streaks, Week Metadata

Fetches league-level context that gives the recap writer narrative material: who's winning the season, weekly schedule context, games remaining.

**Files:**
- Create: `cron/fetch_league_context.py`
- Create: `tests/test_fetch_league_context.py`

#### Output schema (merged into enriched JSON or standalone):

```json
{
  "date": "2026-03-31",
  "week": 23,
  "week_start": "2026-03-30",
  "week_end": "2026-04-05",
  "week_day_number": 2,
  "day_name": "Salı",
  "standings": [
    {
      "team_name": "Ankara Tinercileri",
      "rank": 1,
      "wins": 15,
      "losses": 7,
      "streak": "W3",
      "points_for": 12500.5,
      "points_against": 11200.3
    }
  ],
  "matchups": [
    {
      "team_1": {
        "team_name": "Ankara Tinercileri",
        "points": 559.9,
        "projected_points": 1659.67,
        "games_remaining": 12
      },
      "team_2": {
        "team_name": "Kozyatağı Korsanları",
        "points": 448.4,
        "projected_points": 1598.81,
        "games_remaining": 8
      }
    }
  ]
}
```

- [ ] **Step 1: Write failing tests for week metadata calculation**

```python
# tests/test_fetch_league_context.py
from datetime import date
from cron.fetch_league_context import get_week_metadata


def test_week_metadata_monday():
    meta = get_week_metadata(
        target_date=date(2026, 3, 30),
        week_start=date(2026, 3, 30),
        week_end=date(2026, 4, 5),
        week_number=23,
    )
    assert meta["week_day_number"] == 1
    assert meta["day_name"] == "Pazartesi"


def test_week_metadata_sunday():
    meta = get_week_metadata(
        target_date=date(2026, 4, 5),
        week_start=date(2026, 3, 30),
        week_end=date(2026, 4, 5),
        week_number=23,
    )
    assert meta["week_day_number"] == 7
    assert meta["day_name"] == "Pazar"
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
python -m pytest tests/test_fetch_league_context.py -v
```

- [ ] **Step 3: Implement `fetch_league_context.py`**

The script should:
1. Accept a date argument
2. Use yfpy to fetch: league standings (`get_league_standings()`), scoreboard for the week (`get_league_scoreboard_by_week()`), game weeks for date→week mapping
3. Calculate `games_remaining` per team by checking each roster player's remaining opponent schedule (this is the projected_stats data — count players with games on remaining week days)
4. Compute `week_day_number` from the week start/end dates
5. Compute team `streak` from historical analysis files in `data/analysis/`
6. Save to `data/analysis/context_{date}.json`

Key implementation detail for `games_remaining`: Use the projected stats for remaining days of the week. For each day from target_date+1 to week_end, load the projected stats and count how many active-position players have `games_played > 0`. If projected stats for future days don't exist yet, use the current day's remaining games count from Yahoo's scoreboard API (which includes this).

```python
#!/usr/bin/env python3
"""
Fetch league context: standings, matchups with projections, week metadata.

Usage:
    python cron/fetch_league_context.py YYYY-MM-DD

Writes:
    data/analysis/context_{date}.json
"""

import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

# Turkish day names for the recap
TURKISH_DAYS = {
    0: "Pazartesi",
    1: "Salı",
    2: "Çarşamba",
    3: "Perşembe",
    4: "Cuma",
    5: "Cumartesi",
    6: "Pazar",
}


def load_env_file() -> None:
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def to_str(value):
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def get_week_metadata(
    target_date: date, week_start: date, week_end: date, week_number: int
) -> dict:
    """Compute week position metadata."""
    day_in_week = (target_date - week_start).days + 1
    total_days = (week_end - week_start).days + 1
    return {
        "week": week_number,
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "week_day_number": day_in_week,
        "week_total_days": total_days,
        "day_name": TURKISH_DAYS[target_date.weekday()],
    }


def compute_team_streaks(data_dir: Path, team_names: list[str]) -> dict[str, str]:
    """Compute win/loss streaks from historical enriched analysis files.

    Looks at the most recent analysis files to determine current streak.
    Returns dict of team_name → streak string (e.g., "W3", "L2").
    """
    # This is a simplified version — full implementation reads from
    # weekly matchup results. For now, return empty streaks.
    # TODO: Implement when weekly result history is available.
    return {name: "" for name in team_names}


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python cron/fetch_league_context.py YYYY-MM-DD")
        sys.exit(1)

    target_date = date.fromisoformat(sys.argv[1])
    load_env_file()

    from yfpy.query import YahooFantasySportsQuery

    access_token_json = {
        "access_token": os.getenv("YAHOO_ACCESS_TOKEN"),
        "consumer_key": os.getenv("YAHOO_CLIENT_ID"),
        "consumer_secret": os.getenv("YAHOO_CLIENT_SECRET"),
        "guid": os.getenv("YAHOO_GUID"),
        "refresh_token": os.getenv("YAHOO_REFRESH_TOKEN"),
        "token_time": float(os.getenv("YAHOO_TOKEN_TIME", "0")),
        "token_type": os.getenv("YAHOO_TOKEN_TYPE", "bearer"),
    }

    query = YahooFantasySportsQuery(
        league_id="93905",
        game_code="nba",
        game_id=None,
        yahoo_access_token_json=access_token_json,
    )
    print("✅ Authenticated with Yahoo API")

    # Find week for target date
    game_info = query.get_current_game_info()
    game_weeks = query.get_game_weeks_by_game_id(game_info.game_id)
    week_number = None
    week_start = week_end = None

    for gw in game_weeks:
        ws = date.fromisoformat(to_str(gw.start))
        we = date.fromisoformat(to_str(gw.end))
        if ws <= target_date <= we:
            week_number = int(to_str(gw.week))
            week_start = ws
            week_end = we
            break

    if week_number is None:
        print(f"❌ Could not find week for {target_date}")
        sys.exit(1)

    # Week metadata
    week_meta = get_week_metadata(target_date, week_start, week_end, week_number)

    # Standings
    standings_raw = query.get_league_standings()
    standings = []
    for team in standings_raw.teams:
        ts = team.team_standings
        standings.append({
            "team_name": to_str(team.name),
            "rank": int(to_str(ts.rank)),
            "wins": int(to_str(ts.outcome_totals.wins)),
            "losses": int(to_str(ts.outcome_totals.losses)),
            "streak": to_str(getattr(ts, "streak", {}).get("value", "")) if hasattr(ts, "streak") else "",
            "points_for": float(to_str(ts.points_for)) if hasattr(ts, "points_for") else 0,
            "points_against": float(to_str(ts.points_against)) if hasattr(ts, "points_against") else 0,
        })

    # Matchups with projections
    scoreboard = query.get_league_scoreboard_by_week(week_number)
    matchups = []
    for matchup in scoreboard.matchups:
        teams_data = []
        for team in matchup.teams:
            tp = getattr(team, "team_points", None)
            points = float(to_str(tp.total)) if tp and hasattr(tp, "total") else 0.0
            tpp = getattr(team, "team_projected_points", None)
            proj = None
            if tpp and hasattr(tpp, "total"):
                try:
                    proj = float(to_str(tpp.total))
                except (ValueError, TypeError):
                    pass

            # games_remaining: count from team_remaining_games if available
            trg = getattr(team, "team_remaining_games", None)
            remaining = None
            if trg and hasattr(trg, "total"):
                try:
                    remaining = int(to_str(trg.total.remaining_games))
                except (ValueError, TypeError, AttributeError):
                    pass

            teams_data.append({
                "team_name": to_str(team.name),
                "team_key": to_str(team.team_key),
                "points": points,
                "projected_points": proj,
                "games_remaining": remaining,
            })
        if len(teams_data) == 2:
            matchups.append({"team_1": teams_data[0], "team_2": teams_data[1]})

    result = {
        "date": target_date.isoformat(),
        **week_meta,
        "standings": standings,
        "matchups": matchups,
    }

    data_dir = Path(__file__).parent.parent / "data" / "analysis"
    data_dir.mkdir(parents=True, exist_ok=True)
    output_path = data_dir / f"context_{target_date.isoformat()}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"✅ League context saved to {output_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
python -m pytest tests/test_fetch_league_context.py -v
```

- [ ] **Step 5: Integration test with real API**

```bash
python cron/fetch_league_context.py 2026-03-31
cat data/analysis/context_2026-03-31.json | python -m json.tool | head -50
```

- [ ] **Step 6: Commit**

```bash
git add cron/fetch_league_context.py tests/test_fetch_league_context.py
git commit -m "feat: add league context fetcher (standings, matchups, week metadata)"
```

---

### Task 3: `generate_recap.py` — LLM Orchestrator

The agentic orchestrator that:
1. Determines what data is needed for the target date
2. Runs enrichment if not already done
3. Runs league context fetch if not already done
4. Assembles the final prompt payload from the prompt template
5. Calls the LLM (Claude API)
6. Saves the recap to `data/recaps/`

**Files:**
- Create: `cron/generate_recap.py`

- [ ] **Step 1: Implement the orchestrator**

```python
#!/usr/bin/env python3
"""
Agentic Daily Recap Generator — Orchestrates data gathering and LLM recap generation.

This script is the single entry point for generating a daily recap. It:
1. Checks which data files exist for the target date
2. Runs enrichment and context scripts as needed
3. Assembles the LLM prompt payload from enriched data + context
4. Calls the LLM (Claude API) with the system prompt from llm/daily-recap-prompt.md
5. Saves the generated recap to data/recaps/

Usage:
    python cron/generate_recap.py YYYY-MM-DD [--dry-run] [--no-llm]

Options:
    --dry-run   Print what would be done without executing scripts
    --no-llm    Run enrichment/context but skip LLM call (outputs assembled payload)
    --force     Re-run enrichment even if enriched file already exists

Environment Variables:
    ANTHROPIC_API_KEY — Required for LLM call (unless --no-llm)
    YAHOO_* — Required for league context fetch
"""

import json
import subprocess
import sys
from datetime import date
from pathlib import Path


DATA_DIR = Path(__file__).parent.parent / "data"
LLM_DIR = Path(__file__).parent.parent / "llm"
RECAP_DIR = DATA_DIR / "recaps"


def file_exists(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


def ensure_enriched_data(target_date: str, force: bool = False) -> dict:
    """Ensure enriched data exists for the target date. Run enrichment if missing."""
    enriched_path = DATA_DIR / "analysis" / f"enriched_{target_date}.json"

    if file_exists(enriched_path) and not force:
        print(f"✅ Enriched data already exists: {enriched_path.name}")
        with open(enriched_path) as f:
            return json.load(f)

    # Check prerequisites
    daily_path = DATA_DIR / "daily_stats" / f"league_93905_{target_date}.json"
    if not file_exists(daily_path):
        print(f"❌ Daily stats missing for {target_date}. Run fetch_daily_stats.py first.")
        sys.exit(1)

    print(f"🔄 Running enrichment for {target_date}...")
    result = subprocess.run(
        [sys.executable, "cron/enrich_daily_data.py", target_date],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"❌ Enrichment failed:\n{result.stderr}")
        sys.exit(1)
    print(result.stdout)

    with open(enriched_path) as f:
        return json.load(f)


def ensure_league_context(target_date: str, force: bool = False) -> dict | None:
    """Ensure league context exists. Fetch if missing. Returns None if unavailable."""
    context_path = DATA_DIR / "analysis" / f"context_{target_date}.json"

    if file_exists(context_path) and not force:
        print(f"✅ League context already exists: {context_path.name}")
        with open(context_path) as f:
            return json.load(f)

    print(f"🔄 Fetching league context for {target_date}...")
    result = subprocess.run(
        [sys.executable, "cron/fetch_league_context.py", target_date],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"⚠️ League context fetch failed (non-fatal):\n{result.stderr}")
        return None
    print(result.stdout)

    if file_exists(context_path):
        with open(context_path) as f:
            return json.load(f)
    return None


def load_system_prompt() -> str:
    """Load the system prompt from llm/daily-recap-prompt.md."""
    prompt_path = LLM_DIR / "daily-recap-prompt.md"
    with open(prompt_path) as f:
        content = f.read()

    # Extract the system prompt between the first ``` blocks
    in_block = False
    lines = []
    for line in content.split("\n"):
        if line.strip() == "```" and not in_block:
            in_block = True
            continue
        if line.strip() == "```" and in_block:
            break
        if in_block:
            lines.append(line)

    return "\n".join(lines)


def assemble_user_message(enriched: dict, context: dict | None) -> str:
    """Assemble the user message payload for the LLM from enriched data + context."""
    parts = []
    target_date = enriched["date"]

    # Header
    if context:
        parts.append(f"**Tarih:** {target_date}")
        parts.append(f"**Haftanın Günü:** {context.get('day_name', '?')} "
                      f"(Haftanın {context.get('week_day_number', '?')}. günü — "
                      f"hafta {context.get('week_start', '?')} - {context.get('week_end', '?')})")
    else:
        parts.append(f"**Tarih:** {target_date}")

    # Matchups
    parts.append("\n## Haftalık Matchup Skorları")
    matchups = context.get("matchups", []) if context else []
    if matchups:
        for m in matchups:
            t1, t2 = m["team_1"], m["team_2"]
            parts.append(f"\n**{t1['team_name']}** vs **{t2['team_name']}**")
            parts.append(f"- Skor: {t1['points']:.1f} - {t2['points']:.1f}")
            if t1.get("projected_points"):
                parts.append(f"- Projeksiyon: {t1['projected_points']:.1f} - {t2.get('projected_points', 0):.1f}")
            if t1.get("games_remaining") is not None:
                parts.append(f"- Kalan maç: {t1['team_name']}: {t1['games_remaining']}, "
                              f"{t2['team_name']}: {t2.get('games_remaining', '?')}")
    else:
        parts.append("(Matchup verisi mevcut değil)")

    # Team details
    parts.append("\n## Takım Detayları")
    for team in enriched["teams"]:
        parts.append(f"\n### {team['team_name']}")
        parts.append(f"Günlük Aktif Puan: **{team['daily_active_points']:.1f}**")

        parts.append("\n| Oyuncu | Pozisyon | Puan | Projeksiyon | Maç | Takım |")
        parts.append("|--------|----------|------|-------------|-----|-------|")
        for p in sorted(team["players"], key=lambda x: x["fantasy_points"], reverse=True):
            game_indicator = p.get("opponent", "") if p["had_game"] else "❌ maç yok"
            proj = f"{p['projected_fantasy_points']:.1f}" if p.get("projected_fantasy_points") else "-"
            achiev = " ".join(f"🏅{a}" for a in p.get("achievements", []))
            parts.append(
                f"| {p['name']} {achiev} | {p['roster_position']} | "
                f"{p['fantasy_points']:.1f} | {proj} | {game_indicator} | {p['nba_team']} |"
            )

        if team["missed_opportunities"]:
            parts.append(f"\n**🚨 Missed Opportunities:**")
            for opp in team["missed_opportunities"]:
                feasible = "" if opp["swap_feasible"] else " ⚠️ IL — roster hamlesi gerekirdi"
                parts.append(
                    f"- **{opp['bench_player']}** (BN: {opp['bench_points']:.1f} pts) → "
                    f"**{opp['active_player_replaced']}** ({opp['active_position']}: "
                    f"{opp['active_points']:.1f} pts) yerine konabilirdi. "
                    f"**{opp['points_lost']:.1f} puan kayıp!**{feasible}"
                )

    # Top 5 + Awards
    parts.append("\n## Günün İstatistik Özetleri")
    parts.append("\n**Top 5 Aktif Performans:**")
    for i, p in enumerate(enriched.get("top_5_active", []), 1):
        achiev = f" ({', '.join(p['achievements'])})" if p.get("achievements") else ""
        stats_str = ", ".join(f"{k}: {v}" for k, v in p.get("stats_summary", {}).items() if v > 0)
        parts.append(f"{i}. **{p['name']}** ({p['team_name']}) — {p['fantasy_points']:.1f} pts{achiev}")
        if stats_str:
            parts.append(f"   {stats_str}")

    awards = enriched.get("daily_awards", {})
    if awards:
        parts.append("\n**Ödül Adayları (veri bazlı):**")
        if "mvp" in awards:
            parts.append(f"- MVP: {awards['mvp']['name']} ({awards['mvp']['points']:.1f} pts)")
        if "biggest_disappointment" in awards:
            d = awards["biggest_disappointment"]
            parts.append(f"- Hayal Kırıklığı: {d['name']} ({d['points']:.1f} pts, proj: {d['projected']:.1f}, {d['diff_pct']:.0f}%)")
        if "biggest_surprise" in awards:
            s = awards["biggest_surprise"]
            parts.append(f"- Sürpriz: {s['name']} ({s['points']:.1f} pts, proj: {s['projected']:.1f}, +{s['diff_pct']:.0f}%)")
        if "worst_missed_opportunity" in awards:
            m = awards["worst_missed_opportunity"]
            parts.append(f"- En büyük roster faciası: {m['team']} — {m['bench_player']} bench'te {m['points_lost']:.1f} puan çürüttü")

    # Standings
    if context and context.get("standings"):
        parts.append("\n## Liga Bağlamı")
        parts.append("\n**Sıralama:**")
        parts.append("| # | Takım | W | L | Streak |")
        parts.append("|---|-------|---|---|--------|")
        for s in sorted(context["standings"], key=lambda x: x["rank"]):
            parts.append(f"| {s['rank']} | {s['team_name']} | {s['wins']} | {s['losses']} | {s.get('streak', '')} |")

    return "\n".join(parts)


def call_llm(system_prompt: str, user_message: str) -> str:
    """Call Claude API to generate the recap."""
    import anthropic

    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    return response.content[0].text


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0].startswith("--"):
        print("Usage: python cron/generate_recap.py YYYY-MM-DD [--dry-run] [--no-llm] [--force]")
        sys.exit(1)

    target_date = args[0]
    dry_run = "--dry-run" in args
    no_llm = "--no-llm" in args
    force = "--force" in args

    print(f"{'='*60}")
    print(f"🏀 DAILY RECAP GENERATOR — {target_date}")
    print(f"{'='*60}")

    if dry_run:
        print("\n🔍 DRY RUN — checking data availability:")
        for label, path in [
            ("Daily stats", DATA_DIR / "daily_stats" / f"league_93905_{target_date}.json"),
            ("Projected stats", DATA_DIR / "projected_stats" / f"league_93905_{target_date}.json"),
            ("Enriched data", DATA_DIR / "analysis" / f"enriched_{target_date}.json"),
            ("League context", DATA_DIR / "analysis" / f"context_{target_date}.json"),
        ]:
            status = "✅" if file_exists(path) else "❌"
            print(f"  {status} {label}: {path.name}")
        return

    # Step 1: Ensure enriched data
    enriched = ensure_enriched_data(target_date, force=force)

    # Step 2: Ensure league context
    context = ensure_league_context(target_date, force=force)

    # Step 3: Assemble prompt
    system_prompt = load_system_prompt()
    user_message = assemble_user_message(enriched, context)

    if no_llm:
        print("\n📝 Assembled user message (--no-llm mode):\n")
        print(user_message)
        # Save the payload for inspection
        payload_path = DATA_DIR / "analysis" / f"recap_payload_{target_date}.md"
        with open(payload_path, "w", encoding="utf-8") as f:
            f.write(user_message)
        print(f"\n💾 Payload saved to {payload_path}")
        return

    # Step 4: Call LLM
    print("\n🤖 Calling LLM to generate recap...")
    recap = call_llm(system_prompt, user_message)

    # Step 5: Save recap
    RECAP_DIR.mkdir(parents=True, exist_ok=True)
    recap_path = RECAP_DIR / f"recap_{target_date}.md"
    with open(recap_path, "w", encoding="utf-8") as f:
        f.write(recap)

    print(f"\n✅ Recap saved to {recap_path}")
    print(f"\n{'='*60}")
    print("PREVIEW (first 500 chars):")
    print(f"{'='*60}")
    print(recap[:500])


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Test orchestrator in --no-llm mode with real data**

```bash
python cron/generate_recap.py 2026-03-31 --no-llm
```

Verify the assembled payload:
- Contains proper matchup tables with projections
- Team sections show active/inactive players correctly
- Missed opportunities are listed per team
- Awards section populated
- Standings table present

- [ ] **Step 3: Test orchestrator --dry-run mode**

```bash
python cron/generate_recap.py 2026-03-31 --dry-run
```

Verify it shows which data files exist/missing without running anything.

- [ ] **Step 4: Test full pipeline with LLM call**

```bash
ANTHROPIC_API_KEY=<key> python cron/generate_recap.py 2026-03-31
cat data/recaps/recap_2026-03-31.md
```

Verify the Turkish recap:
- IL/BN players are NOT in "Günün Yıldızları"
- Missed opportunities are called out per team
- Awards use correct logic (active players only for MVP)
- Week context (early/mid/late) influences tone

- [ ] **Step 5: Commit**

```bash
git add cron/generate_recap.py
git commit -m "feat: add agentic recap generator (orchestrator + LLM)"
```

---

### Task 4: GitHub Actions Workflow for Daily Recap

Wire the full pipeline into CI: after daily stats and projected stats are collected, run the recap generator.

**Files:**
- Create: `.github/workflows/daily_recap.yml`

- [ ] **Step 1: Create the workflow**

```yaml
# .github/workflows/daily_recap.yml
name: Daily Fantasy Recap

on:
  workflow_dispatch:
    inputs:
      date:
        description: 'Date to recap (YYYY-MM-DD, defaults to yesterday PST)'
        required: false
        default: ''
      no_llm:
        description: 'Skip LLM call (just generate payload)'
        required: false
        default: 'false'

  # Run after daily stats + projected stats are collected
  # daily_stats runs at 3AM PST (11 UTC), projected at 12PM PST (20 UTC)
  # Recap runs at 5AM PST (13 UTC) — gives time for both to complete
  schedule:
    - cron: '0 13 * * *'

permissions:
  contents: write

jobs:
  generate_recap:
    runs-on: ubuntu-latest

    steps:
    - name: Checkout repository
      uses: actions/checkout@v4

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
          echo "target=$(TZ='America/Los_Angeles' date -d 'yesterday' +'%Y-%m-%d')" >> $GITHUB_OUTPUT
        fi

    - name: Pull latest data
      run: git pull origin main

    - name: Run enrichment
      run: python cron/enrich_daily_data.py "${{ steps.date.outputs.target }}"

    - name: Fetch league context
      env:
        YAHOO_CLIENT_ID: ${{ secrets.YAHOO_CLIENT_ID }}
        YAHOO_CLIENT_SECRET: ${{ secrets.YAHOO_CLIENT_SECRET }}
        YAHOO_ACCESS_TOKEN: ${{ secrets.YAHOO_ACCESS_TOKEN }}
        YAHOO_REFRESH_TOKEN: ${{ secrets.YAHOO_REFRESH_TOKEN }}
        YAHOO_TOKEN_TIME: ${{ secrets.YAHOO_TOKEN_TIME }}
        YAHOO_TOKEN_TYPE: bearer
        YAHOO_GUID: None
      run: python cron/fetch_league_context.py "${{ steps.date.outputs.target }}"

    - name: Generate recap
      env:
        ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        YAHOO_CLIENT_ID: ${{ secrets.YAHOO_CLIENT_ID }}
        YAHOO_CLIENT_SECRET: ${{ secrets.YAHOO_CLIENT_SECRET }}
        YAHOO_ACCESS_TOKEN: ${{ secrets.YAHOO_ACCESS_TOKEN }}
        YAHOO_REFRESH_TOKEN: ${{ secrets.YAHOO_REFRESH_TOKEN }}
        YAHOO_TOKEN_TIME: ${{ secrets.YAHOO_TOKEN_TIME }}
        YAHOO_TOKEN_TYPE: bearer
        YAHOO_GUID: None
      run: |
        NO_LLM_FLAG=""
        if [ "${{ github.event.inputs.no_llm }}" = "true" ]; then
          NO_LLM_FLAG="--no-llm"
        fi
        python cron/generate_recap.py "${{ steps.date.outputs.target }}" $NO_LLM_FLAG

    - name: Commit results
      run: |
        git config --local user.email "github-actions[bot]@users.noreply.github.com"
        git config --local user.name "github-actions[bot]"
        git add data/analysis/ data/recaps/
        if git diff --staged --quiet; then
          echo "No changes to commit."
        else
          git commit -m "Daily recap: ${{ steps.date.outputs.target }}"
          git push origin main
        fi
```

- [ ] **Step 2: Add `anthropic` to requirements.txt if not already present**

```bash
grep -q "^anthropic" requirements.txt || echo "anthropic>=0.40.0" >> requirements.txt
```

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/daily_recap.yml requirements.txt
git commit -m "feat: add daily recap GitHub Actions workflow"
```

---

### Task 5: Clean Up — Deprecate Old Analysis Script

The old `analyze_yesterday_games.py` is replaced by the new pipeline. Update the old workflow to point to the new scripts or mark it as deprecated.

**Files:**
- Modify: `cron/analyze_yesterday_games.py` (add deprecation notice at top)
- Modify: `.github/workflows/yesterday_analysis.yml` (update to use new pipeline)

- [ ] **Step 1: Add deprecation notice to old script**

Add this to the top of `analyze_yesterday_games.py` docstring:

```python
"""
DEPRECATED: This script is replaced by the new enrichment pipeline:
    - cron/enrich_daily_data.py (enrichment + missed opportunities)
    - cron/fetch_league_context.py (standings + matchups)
    - cron/generate_recap.py (orchestrator + LLM)

This file is kept for backward compatibility. Use generate_recap.py instead.
"""
```

- [ ] **Step 2: Update yesterday_analysis workflow to use new pipeline**

Replace the analysis step in `.github/workflows/yesterday_analysis.yml` to call `enrich_daily_data.py` instead.

- [ ] **Step 3: Commit**

```bash
git add cron/analyze_yesterday_games.py .github/workflows/yesterday_analysis.yml
git commit -m "chore: deprecate old analysis script, point to new pipeline"
```

---

## Summary — Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                    generate_recap.py (orchestrator)                  │
│                                                                     │
│  1. Check: enriched_{date}.json exists?                            │
│     NO  → run enrich_daily_data.py                                 │
│           └── reads: daily_stats + projected_stats                  │
│           └── writes: enriched_{date}.json                         │
│                                                                     │
│  2. Check: context_{date}.json exists?                             │
│     NO  → run fetch_league_context.py                              │
│           └── calls: Yahoo API (standings, scoreboard)              │
│           └── writes: context_{date}.json                          │
│                                                                     │
│  3. Assemble user message from enriched + context                  │
│  4. Load system prompt from llm/daily-recap-prompt.md              │
│  5. Call Claude API → Turkish recap                                │
│  6. Save to data/recaps/recap_{date}.md                            │
└─────────────────────────────────────────────────────────────────────┘
```

**Scheduling:**
- 3:00 AM PST: `fetch_daily_stats.py` (yesterday's actuals)
- 12:00 PM PST: `fetch_projected_stats.py` (today's projections — used for tomorrow's enrichment)
- 5:00 AM PST: `generate_recap.py` (yesterday's recap using yesterday's actuals + projections)
