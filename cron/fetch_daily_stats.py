#!/usr/bin/env python3
"""
Daily fantasy stats collection - fetches player stats for all teams in league.
Runs via GitHub Actions cron job at 11:30 PM PST daily.
"""

# Standard library imports for env access and path handling.
import os
import sys
import json
import requests
from pathlib import Path
from datetime import datetime, date
from zoneinfo import ZoneInfo

# Third-party helper for Yahoo API client.
from yfpy.query import YahooFantasySportsQuery, Team, League


def load_env_file() -> None:
    """Load .env file from project root into os.environ if running locally."""
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, value = line.partition('=')
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


def to_str(value):
    """Convert bytes to string, or return value as-is."""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def fetch_nba_opponent_map(date_str: str) -> dict:
    """Return {team_abbr: opponent_abbr} for every NBA game on the given date.

    Uses the BallDontLie API. If the call fails, returns an empty dict so the
    rest of the fetch continues without opponent data.
    """
    api_key = os.getenv("BALLDONTLIE_API_KEY", "")
    if not api_key:
        print("⚠️  BALLDONTLIE_API_KEY not set, skipping opponent lookup")
        return {}

    try:
        resp = requests.get(
            "https://api.balldontlie.io/v1/games",
            params={"dates[]": date_str, "per_page": 100},
            headers={"Authorization": api_key},
            timeout=10,
        )
        resp.raise_for_status()
        games = resp.json().get("data", [])
    except Exception as e:
        print(f"⚠️  BallDontLie request failed: {e}")
        return {}

    opponent_map = {}
    for game in games:
        home = game["home_team"]["abbreviation"]
        away = game["visitor_team"]["abbreviation"]
        opponent_map[home] = away
        opponent_map[away] = home

    print(f"✅ BallDontLie: {len(games)} games on {date_str}, {len(opponent_map)} teams with opponents")
    return opponent_map


def main() -> None:
    # Header output so the script's purpose is clear in the terminal.
    print("=" * 80)
    print("DAILY FANTASY STATS COLLECTION")
    print("=" * 80)

    load_env_file()

    # Allow passing a specific date via CLI arg (YYYY-MM-DD), defaulting to today PST.
    if len(sys.argv) > 1:
        try:
            target_date = date.fromisoformat(sys.argv[1])
        except ValueError:
            print(f"❌ Invalid date format '{sys.argv[1]}'. Use YYYY-MM-DD.")
            return
    else:
        pacific_tz = ZoneInfo("America/Los_Angeles")
        target_date = datetime.now(pacific_tz).date()

    target_league_name = "teletabi ligi"

    # Read Yahoo OAuth credentials from environment variables.
    # For yfpy 17.0.0+, we use yahoo_access_token_json parameter for headless auth.
    access_token_json = {
        "access_token": os.getenv("YAHOO_ACCESS_TOKEN"),
        "consumer_key": os.getenv("YAHOO_CLIENT_ID"),
        "consumer_secret": os.getenv("YAHOO_CLIENT_SECRET"),
        "guid": os.getenv("YAHOO_GUID"),
        "refresh_token": os.getenv("YAHOO_REFRESH_TOKEN"),
        "token_time": float(os.getenv("YAHOO_TOKEN_TIME", "0")),
        "token_type": os.getenv("YAHOO_TOKEN_TYPE", "bearer"),
    }

    # Validate required fields.
    if not access_token_json["consumer_key"] or not access_token_json["consumer_secret"]:
        print("❌ Missing Yahoo API credentials in environment variables")
        print("   Required: YAHOO_CLIENT_ID, YAHOO_CLIENT_SECRET, YAHOO_REFRESH_TOKEN, etc.")
        return

    # Baseline NBA settings.
    game_code = "nba"
    target_league: League = None

    # Initialize YahooFantasySportsQuery with yahoo_access_token_json (yfpy 17.0.0+).
    query = YahooFantasySportsQuery(
        league_id="temp",
        game_code=game_code,
        game_id=None,
        yahoo_access_token_json=access_token_json,
    )

    print("✅ Authenticated with Yahoo API")

    # Current game info.
    game_info = query.get_current_game_info()
    current_game_key = game_info.game_key
    print(f"Current game key: {current_game_key}")

    # Stat categories for mapping stat IDs to names.
    stat_categories = game_info.stat_categories
    stat_id_to_name = {}
    for stat_info in stat_categories.stats:
        stat_id_to_name[str(stat_info.stat_id)] = {
            "display_name": to_str(stat_info.display_name),
            "name": to_str(stat_info.name),
        }

    # Fetch leagues for the authenticated user and find target league.
    leagues = query.get_user_leagues_by_game_key(game_code)
    print(f"\nFound {len(leagues)} league(s)")

    for league_info in leagues:
        league_name = to_str(league_info.name)
        if league_name == target_league_name:
            target_league = league_info
            print(f"✅ Target league found: {league_name}")
            break

    if not target_league:
        print(f"❌ Target league '{target_league_name}' not found")
        return

    # Set league context.
    query.league_id = target_league.league_id
    query.league_key = target_league.league_key

    # Load league settings to get scoring modifiers for stat-based points.
    league_settings = query.get_league_settings()
    stat_modifiers = {}
    for stat_info in league_settings.stat_modifiers.stats:
        stat_id = int(stat_info.stat_id)
        stat_modifiers[stat_id] = float(stat_info.value)

    print(f"Loaded {len(stat_modifiers)} stat modifiers")

    today_str = target_date.strftime("%Y-%m-%d")
    # Find the exact week that contains target_date by scanning all game weeks.
    league_meta = query.get_league_metadata()
    current_week = league_meta.current_week

    try:
        game_weeks = query.get_game_weeks_by_game_id(game_info.game_id)
        week_by_num = {int(to_str(gw.week)): gw for gw in game_weeks}
        matched_week = None
        for week_num, gw in week_by_num.items():
            week_start = date.fromisoformat(to_str(gw.start))
            week_end = date.fromisoformat(to_str(gw.end))
            if week_start <= target_date <= week_end:
                matched_week = week_num
                print(f"Week {week_num} scoring period: {week_start} → {week_end}")
                break
        if matched_week is not None:
            current_week = matched_week
        else:
            print(f"⚠️  No game week found containing {today_str}, falling back to current_week={current_week}")
    except Exception as e:
        print(f"⚠️  Could not look up week for {today_str}: {e}")

    print(f"Collecting stats for {today_str} (Week {current_week})")

    # Build a daily snapshot for all teams in the target league.
    league_teams = query.get_league_teams()
    daily_snapshot = {
        "date": today_str,
        "week": current_week,
        "league_id": to_str(target_league.league_id),
        "league_key": to_str(target_league.league_key),
        "league_name": to_str(target_league.name),
        "teams": [],
    }

    # Fetch NBA game schedule for today so we can record each player's opponent.
    opponent_map = fetch_nba_opponent_map(today_str)

    print(f"Processing {len(league_teams)} teams...")

    for idx, team_info in enumerate(league_teams, 1):
        team_name = to_str(team_info.name)
        team_id = to_str(team_info.team_id)
        team_key = to_str(team_info.team_key)

        print(f"Team [{idx}/{len(league_teams)}] {team_name}")

        # get_team_roster_player_info_by_date returns each player's selected_position
        # and player_stats as-of the target date, so positions are correct for that day
        # (not today's lineup). This is the correct method for historical backfill too.
        players = query.get_team_roster_player_info_by_date(team_id, chosen_date=today_str)

        team_entry = {
            "team_id": team_id,
            "team_key": team_key,
            "team_name": team_name,
            "players": [],
        }

        for player_info in players:
            player_name = to_str(player_info.name.full)
            player_id = to_str(player_info.player_id)
            player_key = to_str(player_info.player_key)
            player_roster_position = to_str(player_info.selected_position.position)

            stat_items = player_info.player_stats.stats if player_info.player_stats else []
            fantasy_points = 0.0
            stats_output = []

            for stat_info in stat_items:
                stat_id = int(stat_info.stat_id)
                stat_value = stat_info.value
                stat_data = stat_id_to_name.get(
                    str(stat_id),
                    {"display_name": f"Stat {stat_id}", "name": f"Stat {stat_id}"},
                )
                modifier = stat_modifiers.get(stat_id, 0.0)
                stat_points = stat_value * modifier
                fantasy_points += stat_points
                stats_output.append({
                    "stat_id": stat_id,
                    "display_name": to_str(stat_data["display_name"]),
                    "name": to_str(stat_data["name"]),
                    "value": stat_value,
                    "modifier": modifier,
                    "points": stat_points,
                })

            yahoo_team = to_str(getattr(player_info, 'editorial_team_abbr', '') or '')
            # Only populate opponent when the player actually scored AND Yahoo's
            # current team abbr was playing that day. If points == 0 we can't
            # distinguish "no game", "DNP", or "traded today" — leave opponent
            # blank to avoid showing wrong matchup data (e.g. a just-traded player
            # whose Yahoo team is already updated but whose stats are from the old team).
            if fantasy_points > 0 and yahoo_team in opponent_map:
                nba_team = yahoo_team
                opponent = opponent_map[yahoo_team]
            else:
                nba_team = yahoo_team if fantasy_points > 0 else ''
                opponent = ''

            team_entry["players"].append({
                "player_id": player_id,
                "player_key": player_key,
                "name": player_name,
                "nba_team": nba_team,
                "opponent": opponent,
                "roster_position": player_roster_position,
                "stats": stats_output,
                "fantasy_points": fantasy_points,
            })

        daily_snapshot["teams"].append(team_entry)

    # Save daily snapshot to JSON in data directory.
    output_dir = Path(__file__).parent.parent / "data" / "daily_stats"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"league_{target_league.league_id}_{today_str}.json"

    with output_path.open("w", encoding="utf-8") as output_file:
        json.dump(daily_snapshot, output_file, indent=2, ensure_ascii=False)

    print(f"\n✅ Saved daily snapshot to: {output_path}")
    print(f"   Total teams: {len(daily_snapshot['teams'])}")
    print(f"   Total players: {sum(len(t['players']) for t in daily_snapshot['teams'])}")


if __name__ == "__main__":
    main()
