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
from datetime import date
from pathlib import Path

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

    print(f"📅 Week {week_number}: {week_start} → {week_end}")

    # Week metadata
    week_meta = get_week_metadata(target_date, week_start, week_end, week_number)

    # Standings
    standings_raw = query.get_league_standings()
    standings = []
    for team in standings_raw.teams:
        ts = team.team_standings
        streak_val = ""
        if hasattr(ts, "streak") and ts.streak:
            streak_obj = ts.streak
            if hasattr(streak_obj, "value"):
                streak_val = to_str(streak_obj.value)
            elif isinstance(streak_obj, dict):
                streak_val = str(streak_obj.get("value", ""))

        pf = 0.0
        if hasattr(ts, "points_for"):
            try:
                pf = float(to_str(ts.points_for))
            except (ValueError, TypeError):
                pass

        pa = 0.0
        if hasattr(ts, "points_against"):
            try:
                pa = float(to_str(ts.points_against))
            except (ValueError, TypeError):
                pass

        standings.append({
            "team_name": to_str(team.name),
            "rank": int(to_str(ts.rank)),
            "wins": int(to_str(ts.outcome_totals.wins)),
            "losses": int(to_str(ts.outcome_totals.losses)),
            "streak": streak_val,
            "points_for": pf,
            "points_against": pa,
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

            # games_remaining from Yahoo API
            remaining = None
            trg = getattr(team, "team_remaining_games", None)
            if trg:
                if hasattr(trg, "total"):
                    try:
                        rg_obj = trg.total
                        if hasattr(rg_obj, "remaining_games"):
                            remaining = int(to_str(rg_obj.remaining_games))
                        else:
                            remaining = int(to_str(rg_obj))
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
    print(f"   Standings: {len(standings)} teams")
    print(f"   Matchups: {len(matchups)}")


if __name__ == "__main__":
    main()
