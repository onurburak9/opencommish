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

# Third-party helper for Yahoo API client.
from yfpy.query import YahooFantasySportsQuery, Team, League


def to_str(value):
    """Convert bytes to string, or return value as-is."""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def main() -> None:
    # Header output so the script's purpose is clear in the terminal.
    print("=" * 80)
    print("DAILY FANTASY STATS COLLECTION")
    print("=" * 80)

    target_league_name = "teletabi ligi"

    # Read Yahoo OAuth credentials from environment variables.
    # These should be set in the environment before running the script.
    client_id = os.getenv("YAHOO_CONSUMER_KEY")
    client_secret = os.getenv("YAHOO_CONSUMER_SECRET")
    refresh_token = os.getenv("YAHOO_REFRESH_TOKEN")

    if not client_id or not client_secret or not refresh_token:
        print("❌ Missing Yahoo API credentials in environment variables")
        print("   Required: YAHOO_CONSUMER_KEY, YAHOO_CONSUMER_SECRET, YAHOO_REFRESH_TOKEN")
        return

    # Baseline NBA settings.
    game_code = "nba"
    target_league: League = None

    # Use cron directory for token storage.
    token_dir = Path(__file__).parent

    # Initialize YahooFantasySportsQuery.
    query = YahooFantasySportsQuery(
        auth_dir=token_dir,
        league_id="temp",
        game_code=game_code,
        game_id=None,
        consumer_key=client_id,
        consumer_secret=client_secret,
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
        stat_info = stat['stat']
        stat_id_to_name[str(stat_info.stat_id)] = {
            "display_name": to_str(stat_info.display_name),
            "name": to_str(stat_info.name),
        }

    # Fetch leagues for the authenticated user and find target league.
    leagues = query.get_user_leagues_by_game_key(game_code)
    print(f"\nFound {len(leagues)} league(s)")

    for league in leagues:
        league_info = league['league']
        league_name = league_info.name
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
    for modifier in league_settings.stat_modifiers.stats:
        stat_id = int(modifier['stat'].stat_id)
        stat_modifiers[stat_id] = float(modifier['stat'].value)

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
        "league_id": to_str(target_league.league_id),
        "league_key": to_str(target_league.league_key),
        "league_name": to_str(target_league.name),
        "teams": [],
    }

    print(f"Processing {len(league_teams)} teams...")

    for idx, team in enumerate(league_teams, 1):
        team_info = team['team']
        team_name = to_str(team_info.name)
        team_id = to_str(team_info.team_id)
        team_key = to_str(team_info.team_key)

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
            player_info = player['player']
            player_name = to_str(player_info.name.full)
            player_id = to_str(player_info.player_id)
            player_key = to_str(player_info.player_key)
            player_roster_position = to_str(player_info.selected_position.position)

            # Fetch per-player stats for today.
            player_with_stats = query.get_player_stats_by_date(
                player_key,
                today_str
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
                    stat_info = stat['stat']
                    stat_id = int(stat_info.stat_id)
                    stat_value = float(stat_info.value)
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
