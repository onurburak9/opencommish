#!/usr/bin/env python3
"""
Daily fantasy stats collection - fetches player stats for all teams in league.
Runs via GitHub Actions cron job at 11:30 PM PST daily.
"""

# Standard library imports for env access and path handling.
import os
import json
from pathlib import Path
from datetime import date

# Third-party helpers for .env loading and Yahoo API client.
from dotenv import load_dotenv
from yfpy.query import YahooFantasySportsQuery, Team, League


def main() -> None:
    # Header output so the script's purpose is clear in the terminal.
    print("=" * 80)
    print("DAILY FANTASY STATS COLLECTION")
    print("=" * 80)

    target_league_name = "teletabi ligi"

    # Load credentials from the project-level .env file (for local runs).
    # In GitHub Actions, these come from environment variables.
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)

    # Read Yahoo OAuth client credentials from environment.
    client_id = os.getenv("YAHOO_CLIENT_ID") or os.getenv("YAHOO_CONSUMER_KEY")
    client_secret = os.getenv("YAHOO_CLIENT_SECRET") or os.getenv("YAHOO_CONSUMER_SECRET")

    if not client_id or not client_secret:
        print("❌ Missing Yahoo API credentials")
        return

    # Baseline NBA settings (used for auth context).
    game_code = "nba"
    target_league: League = None

    # Initialize YahooFantasySportsQuery; token data is saved into .env for reuse.
    # For GitHub Actions, use cron directory for token storage.
    token_dir = Path(__file__).parent
    query = YahooFantasySportsQuery(
        "temp",
        game_code,
        game_id=None,
        yahoo_consumer_key=client_id,
        yahoo_consumer_secret=client_secret,
        env_file_location=token_dir,
        save_token_data_to_env_file=True,
    )

    print("✅ Authenticated with Yahoo API")

    # Current game info.
    game_info = query.get_current_game_info()
    current_game_key = game_info.game_key
    print(f"Current game key: {current_game_key}")

    # Stat categories for mapping stat IDs to names.
    stat_categories = game_info.stat_categories
    stat_id_to_name = {}
    for stat in stat_categories.stats:
        stat_id_to_name[str(stat.stat_id)] = {
            "display_name": stat.display_name,
            "name": stat.name,
        }

    # Fetch leagues for the authenticated user and find target league.
    leagues = query.get_user_leagues_by_game_key(game_code)
    print(f"\nFound {len(leagues)} league(s)")
    
    for league in leagues:
        league_name = str(league.name, "utf-8")
        if league_name == target_league_name:
            target_league = league
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
    for modifier in league_settings.stat_modifiers.stats:
        stat_id = int(modifier.stat.stat_id)
        stat_modifiers[stat_id] = float(modifier.stat.value)

    print(f"Loaded {len(stat_modifiers)} stat modifiers")

    # Get today's stats for players on every team in the target league.
    today_str = date.today().strftime("%Y-%m-%d")
    league_meta = query.get_league_metadata()
    current_week = league_meta.current_week

    print(f"Collecting stats for {today_str} (Week {current_week})")

    # Build a daily snapshot for all teams in the target league.
    league_teams = query.get_league_teams()
    daily_snapshot = {
        "date": today_str,
        "week": current_week,
        "league_id": target_league.league_id,
        "league_key": target_league.league_key,
        "league_name": str(target_league.name, "utf-8"),
        "teams": [],
    }

    print(f"Processing {len(league_teams)} teams...")

    for idx, team in enumerate(league_teams, 1):
        team_name = str(team.name, "utf-8")
        team_id = team.team_id
        team_key = team.team_key

        print(f"  [{idx}/{len(league_teams)}] {team_name}")

        # Pull current-week roster to get player keys and positions.
        roster = query.get_team_roster_by_week(team_id, chosen_week=current_week)
        players = roster.players

        team_entry = {
            "team_id": team_id,
            "team_key": team_key,
            "team_name": team_name,
            "players": [],
        }

        for player in players:
            player_name = player.name.full
            player_id = player.player_id
            player_key = player.player_key
            player_roster_position = player.selected_position.position

            # Fetch per-player stats for today.
            player_with_stats = query.get_player_stats_by_date(
                player_key,
                today_str,
                limit_to_league_stats=False
            )

            if not player_with_stats or not player_with_stats.player_stats:
                team_entry["players"].append({
                    "player_id": player_id,
                    "player_key": player_key,
                    "name": player_name,
                    "roster_position": player_roster_position,
                    "stats": [],
                    "fantasy_points": 0.0,
                })
                continue

            stat_items = player_with_stats.player_stats.stats
            fantasy_points = 0.0
            stats_output = []

            if stat_items:
                # Compute fantasy points using league stat modifiers.
                for stat in stat_items:
                    stat_id = int(stat.stat_id)
                    stat_value = float(stat.value)
                    stat_info = stat_id_to_name.get(
                        str(stat_id),
                        {"display_name": f"Stat {stat_id}", "name": f"Stat {stat_id}"},
                    )
                    modifier = stat_modifiers.get(stat_id, 0.0)
                    stat_points = stat_value * modifier
                    fantasy_points += stat_points
                    stats_output.append({
                        "stat_id": stat_id,
                        "display_name": stat_info["display_name"],
                        "name": stat_info["name"],
                        "value": stat_value,
                        "modifier": modifier,
                        "points": stat_points,
                    })

            team_entry["players"].append({
                "player_id": player_id,
                "player_key": player_key,
                "name": player_name,
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
