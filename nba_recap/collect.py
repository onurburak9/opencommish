"""Phase 1: NBA data collection — fetches scoreboard, box scores, standings via nba_api.

No LLM involved. nba_api uses public stats.nba.com endpoints — no API key required.
"""

import time
from dataclasses import dataclass, field
from datetime import date, timedelta

_API_SLEEP_S = 0.6  # NBA API rate-limit buffer


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


def build_game_record(game: dict) -> dict:
    """Normalize a ScoreboardV3 game dict into a flat game record.

    ScoreboardV3 nests team info under homeTeam/awayTeam objects.
    """
    home = game.get("homeTeam", {})
    away = game.get("awayTeam", {})
    home_score = home.get("score") or 0
    away_score = away.get("score") or 0
    status = game.get("gameStatusText", "")
    return {
        "game_id": game.get("gameId", ""),
        "home_team": home.get("teamTricode", ""),
        "away_team": away.get("teamTricode", ""),
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


def _fetch_scoreboard(game_date: str) -> list[dict]:
    from nba_api.stats.endpoints import ScoreboardV3
    time.sleep(_API_SLEEP_S)
    try:
        board = ScoreboardV3(game_date=game_date, timeout=30)
        data = board.get_dict()
        return data.get("scoreboard", {}).get("games", [])
    except Exception as e:
        print(f"  ⚠️  Scoreboard fetch failed for {game_date}: {e}")
        return []


def _fetch_box_score_performers(game_id: str) -> list[dict]:
    from nba_api.stats.endpoints import BoxScoreTraditionalV2
    time.sleep(_API_SLEEP_S)
    try:
        box = BoxScoreTraditionalV2(game_id=game_id, timeout=30)
        d = box.player_stats.get_dict()
        players = [dict(zip(d["headers"], row)) for row in d["data"]]
        result = []
        for p in players:
            min_val = p.get("MIN")
            if not min_val or min_val == "0:00":
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
        print(f"  Warning: Box score failed for {game_id}: {e}")
        return []


def _fetch_standings() -> tuple[list[dict], list[dict]]:
    from nba_api.stats.endpoints import LeagueStandingsV3
    time.sleep(_API_SLEEP_S)
    try:
        s = LeagueStandingsV3(timeout=30)
        d = s.standings.get_dict()
        all_teams = [dict(zip(d["headers"], row)) for row in d["data"]]
        east = [parse_standings_entry(t) for t in all_teams if t.get("Conference") == "East"]
        west = [parse_standings_entry(t) for t in all_teams if t.get("Conference") == "West"]
        return east, west
    except Exception as e:
        print(f"  Warning: Standings failed: {e}")
        return [], []


def _fetch_upcoming(target_date: str) -> list[dict]:
    from nba_api.stats.endpoints import ScoreboardV3
    next_day = (date.fromisoformat(target_date) + timedelta(days=1)).isoformat()
    time.sleep(_API_SLEEP_S)
    try:
        board = ScoreboardV3(game_date=next_day, timeout=30)
        data = board.get_dict()
        games = data.get("scoreboard", {}).get("games", [])
        return [
            {
                "home": g.get("homeTeam", {}).get("teamTricode", ""),
                "away": g.get("awayTeam", {}).get("teamTricode", ""),
                "game_id": g.get("gameId", ""),
            }
            for g in games
        ]
    except Exception as e:
        print(f"  Warning: Upcoming games failed: {e}")
        return []


def collect(target_date: str) -> CollectedData:
    """Fetch all NBA data for target_date (YYYY-MM-DD). No LLM calls."""
    print(f"Collecting NBA data for {target_date}...")
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
    print(f"  {len(games)} games, {len(east)+len(west)} standings entries")
    return CollectedData(
        date=target_date,
        games=games,
        standings_east=east,
        standings_west=west,
        upcoming_games=upcoming,
        sources_used=["nba_api"],
    )
