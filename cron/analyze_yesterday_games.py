#!/usr/bin/env python3
"""
Yesterday's Game Analysis - Fetches and analyzes fantasy performance from yesterday's games.

Fetches data from Yahoo Fantasy API and calculates:
- Total fantasy points per team from yesterday's games
- Total fantasy points per NBA player in those games
- Top 5 best performers overall
- Best 2 performers per fantasy team
- Worst 2 performers per fantasy team

Usage:
    python analyze_yesterday_games.py [YYYY-MM-DD]
    
If no date is provided, defaults to yesterday (PST).
"""

import json
import os
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from yfpy.query import YahooFantasySportsQuery


def load_env_file() -> None:
    """Load .env file from project root into os.environ if running locally."""
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


def to_str(value: Any) -> str:
    """Convert bytes to string, or return value as-is."""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def get_yesterday_pst() -> date:
    """Get yesterday's date in Pacific timezone."""
    pacific_tz = ZoneInfo("America/Los_Angeles")
    now_pst = datetime.now(pacific_tz)
    return (now_pst - timedelta(days=1)).date()


def load_daily_stats(target_date: date) -> dict | None:
    """Load daily stats from the data directory if already collected."""
    date_str = target_date.strftime("%Y-%m-%d")
    data_path = Path(__file__).parent.parent / "data" / "daily_stats" / f"league_93905_{date_str}.json"
    
    if data_path.exists():
        with open(data_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def fetch_yesterday_stats(target_date: date) -> dict:
    """Fetch yesterday's stats from Yahoo API."""
    load_env_file()
    
    target_league_name = "teletabi ligi"
    
    # Yahoo OAuth credentials
    access_token_json = {
        "access_token": os.getenv("YAHOO_ACCESS_TOKEN"),
        "consumer_key": os.getenv("YAHOO_CLIENT_ID"),
        "consumer_secret": os.getenv("YAHOO_CLIENT_SECRET"),
        "guid": os.getenv("YAHOO_GUID"),
        "refresh_token": os.getenv("YAHOO_REFRESH_TOKEN"),
        "token_time": float(os.getenv("YAHOO_TOKEN_TIME", "0")),
        "token_type": os.getenv("YAHOO_TOKEN_TYPE", "bearer"),
    }

    if not access_token_json["consumer_key"] or not access_token_json["consumer_secret"]:
        raise ValueError("Missing Yahoo API credentials in environment variables")
    
    game_code = "nba"
    target_league = None
    
    query = YahooFantasySportsQuery(
        league_id="temp",
        game_code=game_code,
        game_id=None,
        yahoo_access_token_json=access_token_json,
    )
    
    print("✅ Authenticated with Yahoo API")
    
    # Get current game info and stat categories
    game_info = query.get_current_game_info()
    stat_categories = game_info.stat_categories
    stat_id_to_name = {}
    for stat_info in stat_categories.stats:
        stat_id_to_name[str(stat_info.stat_id)] = {
            "display_name": to_str(stat_info.display_name),
            "name": to_str(stat_info.name),
        }
    
    # Find target league
    leagues = query.get_user_leagues_by_game_key(game_code)
    for league_info in leagues:
        league_name = to_str(league_info.name)
        if league_name == target_league_name:
            target_league = league_info
            break
    
    if not target_league:
        raise ValueError(f"Target league '{target_league_name}' not found")
    
    query.league_id = target_league.league_id
    query.league_key = target_league.league_key
    
    # Load stat modifiers
    league_settings = query.get_league_settings()
    stat_modifiers = {}
    for stat_info in league_settings.stat_modifiers.stats:
        stat_id = int(stat_info.stat_id)
        stat_modifiers[stat_id] = float(stat_info.value)
    
    # Determine the week for the target date
    date_str = target_date.strftime("%Y-%m-%d")
    league_meta = query.get_league_metadata()
    current_week = league_meta.current_week
    
    try:
        game_weeks = query.get_game_weeks_by_game_id(game_info.game_id)
        week_by_num = {int(to_str(gw.week)): gw for gw in game_weeks}
        for week_num, gw in week_by_num.items():
            week_start = date.fromisoformat(to_str(gw.start))
            week_end = date.fromisoformat(to_str(gw.end))
            if week_start <= target_date <= week_end:
                current_week = week_num
                break
    except Exception as e:
        print(f"⚠️ Could not look up week for {date_str}: {e}")
    
    print(f"📅 Fetching stats for {date_str} (Week {current_week})")
    
    # Fetch all teams and their rosters
    league_teams = query.get_league_teams()
    daily_snapshot = {
        "date": date_str,
        "week": current_week,
        "league_id": to_str(target_league.league_id),
        "league_key": to_str(target_league.league_key),
        "league_name": to_str(target_league.name),
        "teams": [],
    }
    
    print(f"🔄 Processing {len(league_teams)} teams...")
    
    for team_info in league_teams:
        team_name = to_str(team_info.name)
        team_id = to_str(team_info.team_id)
        team_key = to_str(team_info.team_key)
        
        players = query.get_team_roster_player_info_by_date(team_id, chosen_date=date_str)
        
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
            
            yahoo_team = to_str(getattr(player_info, "editorial_team_abbr", "") or "")
            
            team_entry["players"].append({
                "player_id": player_id,
                "player_key": player_key,
                "name": player_name,
                "nba_team": yahoo_team,
                "roster_position": player_roster_position,
                "stats": stats_output,
                "fantasy_points": fantasy_points,
            })
        
        daily_snapshot["teams"].append(team_entry)
    
    return daily_snapshot


def analyze_yesterday_games(data: dict) -> dict:
    """Analyze yesterday's games and return performance metrics."""
    date_str = data["date"]
    league_name = data["league_name"]
    
    print(f"\n{'='*80}")
    print(f"📊 YESTERDAY'S GAME ANALYSIS: {date_str}")
    print(f"🏀 League: {league_name}")
    print(f"{'='*80}\n")
    
    # Collect all players across all teams
    all_players = []
    team_performances = []
    
    for team in data["teams"]:
        team_name = team["team_name"]
        team_id = team["team_id"]
        
        # Calculate team total (only counting players who scored > 0)
        active_players = [p for p in team["players"] if p["fantasy_points"] > 0]
        team_total = sum(p["fantasy_points"] for p in active_players)
        
        team_performances.append({
            "team_id": team_id,
            "team_name": team_name,
            "total_points": team_total,
            "active_players": len(active_players),
            "players": team["players"],
        })
        
        for player in team["players"]:
            if player["fantasy_points"] > 0:  # Only include players who played
                all_players.append({
                    "name": player["name"],
                    "team_name": team_name,
                    "nba_team": player["nba_team"],
                    "fantasy_points": player["fantasy_points"],
                    "roster_position": player["roster_position"],
                    "stats": player["stats"],
                })
    
    # Sort all players by fantasy points (descending)
    all_players_sorted = sorted(all_players, key=lambda x: x["fantasy_points"], reverse=True)
    
    # Calculate team totals sorted
    team_totals_sorted = sorted(team_performances, key=lambda x: x["total_points"], reverse=True)
    
    # Build results
    results = {
        "date": date_str,
        "league_name": league_name,
        "summary": {
            "total_teams": len(data["teams"]),
            "total_players_with_stats": len(all_players),
            "date_analyzed": date_str,
        },
        "team_totals": [
            {
                "team_name": t["team_name"],
                "total_fantasy_points": round(t["total_points"], 2),
                "active_players": t["active_players"],
            }
            for t in team_totals_sorted
        ],
        "top_5_overall": [],
        "best_per_team": {},
        "worst_per_team": {},
    }
    
    # Top 5 best performers overall
    print("🏆 TOP 5 BEST PERFORMERS OVERALL")
    print("-" * 80)
    for i, player in enumerate(all_players_sorted[:5], 1):
        player_data = {
            "rank": i,
            "name": player["name"],
            "fantasy_team": player["team_name"],
            "nba_team": player["nba_team"],
            "fantasy_points": round(player["fantasy_points"], 2),
            "roster_position": player["roster_position"],
        }
        results["top_5_overall"].append(player_data)
        print(f"  {i}. {player['name']} ({player['nba_team']})")
        print(f"     Fantasy Team: {player['team_name']}")
        print(f"     Position: {player['roster_position']}")
        print(f"     Fantasy Points: {player['fantasy_points']:.2f}")
        print()
    
    # Best 2 and worst 2 per team
    print("\n📈 BEST & WORST PERFORMERS BY TEAM")
    print("=" * 80)
    
    for team in team_performances:
        team_name = team["team_name"]
        players = [p for p in team["players"] if p["fantasy_points"] > 0]
        
        if len(players) == 0:
            results["best_per_team"][team_name] = []
            results["worst_per_team"][team_name] = []
            continue
        
        # Sort by fantasy points
        players_sorted = sorted(players, key=lambda x: x["fantasy_points"], reverse=True)
        
        # Best 2
        best_2 = players_sorted[:2]
        best_2_data = []
        print(f"\n🏀 {team_name}")
        print(f"   Team Total: {team['total_points']:.2f} points")
        print(f"   ⭐ Best Performers:")
        for i, player in enumerate(best_2, 1):
            player_data = {
                "rank": i,
                "name": player["name"],
                "nba_team": player["nba_team"],
                "fantasy_points": round(player["fantasy_points"], 2),
                "roster_position": player["roster_position"],
            }
            best_2_data.append(player_data)
            print(f"      {i}. {player['name']} ({player['nba_team']}) - {player['fantasy_points']:.2f} pts [{player['roster_position']}]")
        results["best_per_team"][team_name] = best_2_data
        
        # Worst 2 (only if we have 2+ players)
        worst_2_data = []
        if len(players_sorted) >= 2:
            worst_2 = players_sorted[-2:]
            worst_2.reverse()  # Show lowest first
            print(f"   📉 Worst Performers:")
            for i, player in enumerate(worst_2, 1):
                player_data = {
                    "rank": i,
                    "name": player["name"],
                    "nba_team": player["nba_team"],
                    "fantasy_points": round(player["fantasy_points"], 2),
                    "roster_position": player["roster_position"],
                }
                worst_2_data.append(player_data)
                print(f"      {i}. {player['name']} ({player['nba_team']}) - {player['fantasy_points']:.2f} pts [{player['roster_position']}]")
        else:
            print(f"   📉 Worst Performers: Only 1 active player")
        results["worst_per_team"][team_name] = worst_2_data
    
    print("\n" + "=" * 80)
    print("✅ Analysis complete!")
    print("=" * 80)
    
    return results


def main() -> None:
    """Main entry point."""
    print("=" * 80)
    print("YESTERDAY'S GAME ANALYSIS")
    print("=" * 80)
    
    # Get target date (yesterday by default, or from CLI arg)
    if len(sys.argv) > 1:
        try:
            target_date = date.fromisoformat(sys.argv[1])
        except ValueError:
            print(f"❌ Invalid date format '{sys.argv[1]}'. Use YYYY-MM-DD.")
            sys.exit(1)
    else:
        target_date = get_yesterday_pst()
    
    date_str = target_date.strftime("%Y-%m-%d")
    print(f"📅 Target date: {date_str}")
    
    # Try to load existing data first
    data = load_daily_stats(target_date)
    
    if data:
        print(f"✅ Loaded existing data from data/daily_stats/league_93905_{date_str}.json")
    else:
        print(f"🔄 Data not found locally. Fetching from Yahoo API...")
        try:
            data = fetch_yesterday_stats(target_date)
        except Exception as e:
            print(f"❌ Error fetching data: {e}")
            sys.exit(1)
    
    # Run analysis
    results = analyze_yesterday_games(data)
    
    # Save results to file
    output_dir = Path(__file__).parent.parent / "data" / "analysis"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"yesterday_analysis_{date_str}.json"
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Results saved to: {output_path}")


if __name__ == "__main__":
    main()
