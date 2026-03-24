#!/usr/bin/env python3
"""
Fetch projected stats for all teams using Yahoo Fantasy API (not scraping).

This script uses the official Yahoo Fantasy API via yfpy to fetch projected
stats for validation purposes. The data is saved in the same format as
fetch_projected_stats.py (scraping) for easy comparison.

Usage:
    python cron/fetch_projected_stats_api.py [YYYY-MM-DD]

Environment Variables Required:
    YAHOO_CONSUMER_KEY - Yahoo API client ID
    YAHOO_CONSUMER_SECRET - Yahoo API client secret
    YAHOO_ACCESS_TOKEN - OAuth access token
    YAHOO_REFRESH_TOKEN - OAuth refresh token
    YAHOO_TOKEN_TIME - Token timestamp
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime, date
from zoneinfo import ZoneInfo
from yfpy.query import YahooFantasySportsQuery, League


def to_str(value):
    """Convert bytes to string, or return value as-is."""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


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


def get_stat_modifiers(query) -> dict:
    """Fetch stat modifiers from league settings for fantasy points calculation."""
    league_settings = query.get_league_settings()
    stat_modifiers = {}
    for stat_info in league_settings.stat_modifiers.stats:
        stat_id = int(stat_info.stat_id)
        stat_modifiers[stat_id] = float(stat_info.value)
    return stat_modifiers


def get_stat_categories(query, game_info) -> dict:
    """Build mapping of stat_id to stat names from game info."""
    stat_categories = game_info.stat_categories
    stat_id_to_name = {}
    for stat_info in stat_categories.stats:
        stat_id_to_name[str(stat_info.stat_id)] = {
            "display_name": to_str(stat_info.display_name),
            "name": to_str(stat_info.name),
        }
    return stat_id_to_name


def calculate_fantasy_points(stats, stat_modifiers) -> tuple:
    """
    Calculate fantasy points from player stats.
    
    Returns:
        tuple: (fantasy_points, stats_list)
    """
    fantasy_points = 0.0
    stats_output = {}
    
    for stat_item in stats:
        stat_id = int(stat_item.stat_id)
        stat_value = stat_item.value
        modifier = stat_modifiers.get(stat_id, 0.0)
        stat_points = stat_value * modifier
        fantasy_points += stat_points
        
        # Store stat with display name
        # We'll map these later based on stat_id
        stats_output[stat_id] = {
            "value": stat_value,
            "points": stat_points,
            "modifier": modifier,
        }
    
    return fantasy_points, stats_output


def fetch_projected_stats_from_api(query, team_id, target_date, stat_modifiers, stat_categories) -> list:
    """
    Fetch projected stats for a team using Yahoo API.
    
    Yahoo API doesn't have a direct "projected stats" endpoint, but we can get
    roster player info which includes upcoming matchup projections.
    
    For NBA, we use get_team_roster_player_info_by_date with future dates
    which returns projected stats.
    """
    players = []
    
    try:
        # Try to get roster info for the target date (future dates return projections)
        roster_players = query.get_team_roster_player_info_by_date(team_id, chosen_date=target_date)
        
        for player_info in roster_players:
            player_name = to_str(player_info.name.full)
            player_id = to_str(player_info.player_id)
            player_key = to_str(player_info.player_key)
            roster_position = to_str(player_info.selected_position.position)
            
            # Get player stats for the target date (projected)
            player_stats_data = player_info.player_stats
            
            if player_stats_data and player_stats_data.stats:
                stats_items = player_stats_data.stats
                fantasy_points = 0.0
                stats_dict = {}
                
                for stat_item in stats_items:
                    stat_id = int(stat_item.stat_id)
                    stat_value = stat_item.value
                    modifier = stat_modifiers.get(stat_id, 0.0)
                    stat_points = stat_value * modifier
                    fantasy_points += stat_points
                    
                    # Map stat_id to display name
                    stat_data = stat_categories.get(str(stat_id), {"display_name": f"Stat_{stat_id}"})
                    display_name = stat_data["display_name"]
                    
                    stats_dict[display_name] = stat_value
                
                # Ensure all expected stats exist (default to 0)
                expected_stats = ["PTS", "REB", "AST", "ST", "BLK", "TO"]
                for stat_name in expected_stats:
                    if stat_name not in stats_dict:
                        stats_dict[stat_name] = 0.0
                
                # Get opponent info from upcoming matchup if available
                opponent = ""
                if hasattr(player_info, 'opponent') and player_info.opponent:
                    opponent = to_str(player_info.opponent)
                
                player_data = {
                    "player_id": player_id,
                    "player_name": player_name,
                    "roster_position": roster_position,
                    "opponent": opponent,
                    "games_played": 1,  # Assume 1 game for projections
                    "fantasy_points": round(fantasy_points, 2),
                    "stats": {
                        "PTS": round(stats_dict.get("PTS", 0), 1),
                        "REB": round(stats_dict.get("REB", 0), 1),
                        "AST": round(stats_dict.get("AST", 0), 1),
                        "ST": round(stats_dict.get("ST", 0), 1),
                        "BLK": round(stats_dict.get("BLK", 0), 1),
                        "TO": round(stats_dict.get("TO", 0), 1),
                    }
                }
                players.append(player_data)
            else:
                # No stats available - still include player with zero projections
                players.append({
                    "player_id": player_id,
                    "player_name": player_name,
                    "roster_position": roster_position,
                    "opponent": "",
                    "games_played": 0,
                    "fantasy_points": 0.0,
                    "stats": {
                        "PTS": 0.0,
                        "REB": 0.0,
                        "AST": 0.0,
                        "ST": 0.0,
                        "BLK": 0.0,
                        "TO": 0.0,
                    }
                })
    
    except Exception as e:
        print(f"  ⚠️  Error fetching projected stats: {e}")
    
    return players


def main() -> None:
    print("=" * 80)
    print("PROJECTED STATS COLLECTION (API-BASED)")
    print("=" * 80)

    load_env_file()
    target_league_name = "teletabi ligi"

    # Read Yahoo OAuth credentials from environment variables
    access_token_json = {
        "access_token": os.getenv("YAHOO_ACCESS_TOKEN"),
        "consumer_key": os.getenv("YAHOO_CONSUMER_KEY"),
        "consumer_secret": os.getenv("YAHOO_CONSUMER_SECRET"),
        "guid": os.getenv("YAHOO_GUID"),
        "refresh_token": os.getenv("YAHOO_REFRESH_TOKEN"),
        "token_time": float(os.getenv("YAHOO_TOKEN_TIME", "0")),
        "token_type": os.getenv("YAHOO_TOKEN_TYPE", "bearer"),
    }

    # Validate required fields
    if not access_token_json["consumer_key"] or not access_token_json["consumer_secret"]:
        print("❌ Missing Yahoo API credentials in environment variables")
        print("   Required: YAHOO_CONSUMER_KEY, YAHOO_CONSUMER_SECRET, YAHOO_REFRESH_TOKEN, etc.")
        return

    # Allow passing a specific date via CLI arg (YYYY-MM-DD), defaulting to today PST
    if len(sys.argv) > 1:
        try:
            today_pacific = date.fromisoformat(sys.argv[1])
        except ValueError:
            print(f"❌ Invalid date format '{sys.argv[1]}'. Use YYYY-MM-DD.")
            return
    else:
        pacific_tz = ZoneInfo("America/Los_Angeles")
        today_pacific = datetime.now(pacific_tz).date()
    today_str = today_pacific.strftime("%Y-%m-%d")

    print(f"Fetching projected stats via API for {today_str}")

    # Initialize yfpy for NBA
    game_code = "nba"
    target_league: League = None

    query = YahooFantasySportsQuery(
        league_id="temp",
        game_code=game_code,
        game_id=None,
        yahoo_access_token_json=access_token_json,
    )

    print("✅ Authenticated with Yahoo API")

    # Get current game info
    game_info = query.get_current_game_info()
    current_game_key = game_info.game_key
    print(f"Current game key: {current_game_key}")

    # Find the target league
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

    # Set league context
    query.league_id = target_league.league_id
    query.league_key = target_league.league_key

    # Get stat modifiers and categories for fantasy points calculation
    stat_modifiers = get_stat_modifiers(query)
    stat_categories = get_stat_categories(query, game_info)
    print(f"Loaded {len(stat_modifiers)} stat modifiers")

    # Get all teams in the league
    league_teams = query.get_league_teams()
    print(f"Processing {len(league_teams)} teams...")

    projected_snapshot = {
        "date": today_str,
        "league_id": to_str(target_league.league_id),
        "league_key": to_str(target_league.league_key),
        "league_name": to_str(target_league.name),
        "teams": [],
    }

    for idx, team_info in enumerate(league_teams, 1):
        team_name = to_str(team_info.name)
        team_id = to_str(team_info.team_id)
        team_key = to_str(team_info.team_key)

        print(f"\nTeam [{idx}/{len(league_teams)}] {team_name} (ID: {team_id})")

        # Fetch projected stats via API
        players = fetch_projected_stats_from_api(
            query, team_id, today_str, stat_modifiers, stat_categories
        )
        
        print(f"  ✅ Retrieved {len(players)} players")
        
        # Display first few players as verification
        for player in players[:3]:
            print(f"    - {player['player_name']} ({player['roster_position']}): "
                  f"{player['fantasy_points']} pts | "
                  f"PTS:{player['stats']['PTS']} REB:{player['stats']['REB']} AST:{player['stats']['AST']}")

        team_entry = {
            "team_id": team_id,
            "team_key": team_key,
            "team_name": team_name,
            "players": players,
        }

        projected_snapshot["teams"].append(team_entry)

    # Save snapshot to JSON
    output_dir = Path(__file__).parent.parent / "data" / "projected_stats_api"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"league_{target_league.league_id}_{today_str}.json"

    with output_path.open("w", encoding="utf-8") as output_file:
        json.dump(projected_snapshot, output_file, indent=2, ensure_ascii=False)

    print(f"\n✅ Saved projected stats snapshot to: {output_path}")
    print(f"   Total teams: {len(projected_snapshot['teams'])}")
    print(f"   Total players: {sum(len(t['players']) for t in projected_snapshot['teams'])}")


if __name__ == "__main__":
    main()
