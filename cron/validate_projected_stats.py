#!/usr/bin/env python3
"""
Validate projected stats by comparing scraped data vs API-fetched data.

This script compares the output of:
- fetch_projected_stats.py (scraping Yahoo UI)
- fetch_projected_stats_api.py (Yahoo API)

Usage:
    python cron/validate_projected_stats.py [YYYY-MM-DD]

Output:
    - Summary of differences between scraped and API data
    - Per-team comparison statistics
    - Player-level discrepancies
"""

import json
import sys
from pathlib import Path
from datetime import datetime, date
from zoneinfo import ZoneInfo
from collections import defaultdict


def load_stats_file(data_dir: Path, league_id: str, target_date: str) -> dict:
    """Load stats file from the specified directory."""
    file_path = data_dir / f"league_{league_id}_{target_date}.json"
    if not file_path.exists():
        return None
    with open(file_path, 'r') as f:
        return json.load(f)


def compare_players(scraped_player: dict, api_player: dict) -> dict:
    """Compare a single player between scraped and API data."""
    differences = []
    
    # Compare fantasy points
    scraped_fp = scraped_player.get("fantasy_points", 0)
    api_fp = api_player.get("fantasy_points", 0)
    fp_diff = abs(scraped_fp - api_fp)
    if fp_diff > 0.1:  # Allow small floating point differences
        differences.append({
            "field": "fantasy_points",
            "scraped": scraped_fp,
            "api": api_fp,
            "diff": fp_diff,
        })
    
    # Compare stats
    scraped_stats = scraped_player.get("stats", {})
    api_stats = api_player.get("stats", {})
    
    for stat_name in ["PTS", "REB", "AST", "ST", "BLK", "TO"]:
        scraped_val = scraped_stats.get(stat_name, 0)
        api_val = api_stats.get(stat_name, 0)
        stat_diff = abs(scraped_val - api_val)
        if stat_diff > 0.1:
            differences.append({
                "field": f"stats.{stat_name}",
                "scraped": scraped_val,
                "api": api_val,
                "diff": stat_diff,
            })
    
    # Compare roster position
    if scraped_player.get("roster_position") != api_player.get("roster_position"):
        differences.append({
            "field": "roster_position",
            "scraped": scraped_player.get("roster_position"),
            "api": api_player.get("roster_position"),
        })
    
    return differences


def validate_team(scraped_team: dict, api_team: dict) -> dict:
    """Validate a single team's data between scraped and API sources."""
    result = {
        "team_name": scraped_team.get("team_name"),
        "players_compared": 0,
        "players_missing_in_api": [],
        "players_missing_in_scraped": [],
        "discrepancies": [],
    }
    
    # Create lookup by player_id
    scraped_players = {p["player_id"]: p for p in scraped_team.get("players", [])}
    api_players = {p["player_id"]: p for p in api_team.get("players", [])}
    
    # Find missing players
    scraped_ids = set(scraped_players.keys())
    api_ids = set(api_players.keys())
    
    missing_in_api = scraped_ids - api_ids
    missing_in_scraped = api_ids - scraped_ids
    
    result["players_missing_in_api"] = list(missing_in_api)
    result["players_missing_in_scraped"] = list(missing_in_scraped)
    
    # Compare common players
    common_ids = scraped_ids & api_ids
    result["players_compared"] = len(common_ids)
    
    for player_id in common_ids:
        scraped_player = scraped_players[player_id]
        api_player = api_players[player_id]
        
        differences = compare_players(scraped_player, api_player)
        if differences:
            result["discrepancies"].append({
                "player_id": player_id,
                "player_name": scraped_player.get("player_name", "Unknown"),
                "differences": differences,
            })
    
    return result


def generate_report(scraped_data: dict, api_data: dict, team_results: list) -> str:
    """Generate a human-readable validation report."""
    lines = []
    lines.append("=" * 80)
    lines.append("PROJECTED STATS VALIDATION REPORT")
    lines.append("=" * 80)
    lines.append(f"Date: {scraped_data.get('date')}")
    lines.append(f"League: {scraped_data.get('league_name')} (ID: {scraped_data.get('league_id')})")
    lines.append("")
    
    # Summary statistics
    total_teams = len(team_results)
    teams_with_discrepancies = sum(1 for r in team_results if r["discrepancies"])
    total_players_compared = sum(r["players_compared"] for r in team_results)
    total_discrepancies = sum(len(r["discrepancies"]) for r in team_results)
    total_missing_api = sum(len(r["players_missing_in_api"]) for r in team_results)
    total_missing_scraped = sum(len(r["players_missing_in_scraped"]) for r in team_results)
    
    lines.append("-" * 40)
    lines.append("SUMMARY")
    lines.append("-" * 40)
    lines.append(f"Teams compared: {total_teams}")
    lines.append(f"Players compared: {total_players_compared}")
    lines.append(f"Teams with discrepancies: {teams_with_discrepancies}")
    lines.append(f"Players with discrepancies: {total_discrepancies}")
    lines.append(f"Players missing in API data: {total_missing_api}")
    lines.append(f"Players missing in scraped data: {total_missing_scraped}")
    lines.append("")
    
    # Per-team details
    lines.append("-" * 40)
    lines.append("PER-TEAM DETAILS")
    lines.append("-" * 40)
    
    for result in team_results:
        lines.append(f"\n📊 {result['team_name']}")
        lines.append(f"   Players compared: {result['players_compared']}")
        
        if result["players_missing_in_api"]:
            lines.append(f"   ⚠️  Players missing in API: {len(result['players_missing_in_api'])}")
        
        if result["players_missing_in_scraped"]:
            lines.append(f"   ⚠️  Players missing in scraped: {len(result['players_missing_in_scraped'])}")
        
        if result["discrepancies"]:
            lines.append(f"   ❌ Players with discrepancies: {len(result['discrepancies'])}")
            for disc in result["discrepancies"][:3]:  # Show first 3
                lines.append(f"      - {disc['player_name']}:")
                for diff in disc["differences"]:
                    lines.append(f"         {diff['field']}: scraped={diff['scraped']}, api={diff['api']}, diff={diff.get('diff', 'N/A')}")
            if len(result["discrepancies"]) > 3:
                lines.append(f"      ... and {len(result['discrepancies']) - 3} more")
        else:
            lines.append("   ✅ All players match")
    
    lines.append("")
    lines.append("=" * 80)
    lines.append("END OF REPORT")
    lines.append("=" * 80)
    
    return "\n".join(lines)


def main():
    print("=" * 80)
    print("PROJECTED STATS VALIDATION")
    print("=" * 80)
    
    # Get target date
    if len(sys.argv) > 1:
        try:
            target_date = date.fromisoformat(sys.argv[1])
        except ValueError:
            print(f"❌ Invalid date format '{sys.argv[1]}'. Use YYYY-MM-DD.")
            return
    else:
        pacific_tz = ZoneInfo("America/Los_Angeles")
        target_date = datetime.now(pacific_tz).date()
    
    today_str = target_date.strftime("%Y-%m-%d")
    print(f"Validating projected stats for {today_str}")
    
    # Load both data sources
    project_root = Path(__file__).parent.parent
    scraped_dir = project_root / "data" / "projected_stats"
    api_dir = project_root / "data" / "projected_stats_api"
    
    # Try to find the league_id from existing files
    scraped_files = list(scraped_dir.glob("league_*.json"))
    if not scraped_files:
        print("❌ No scraped stats files found")
        return
    
    # Extract league_id from first file
    first_file = scraped_files[0]
    league_id = first_file.stem.split("_")[1]
    
    scraped_data = load_stats_file(scraped_dir, league_id, today_str)
    api_data = load_stats_file(api_dir, league_id, today_str)
    
    if not scraped_data:
        print(f"❌ Scraped data not found for {today_str}")
        print(f"   Expected: {scraped_dir}/league_{league_id}_{today_str}.json")
        return
    
    if not api_data:
        print(f"❌ API data not found for {today_str}")
        print(f"   Expected: {api_dir}/league_{league_id}_{today_str}.json")
        print("   Run: python cron/fetch_projected_stats_api.py")
        return
    
    print(f"✅ Loaded scraped data: {len(scraped_data['teams'])} teams")
    print(f"✅ Loaded API data: {len(api_data['teams'])} teams")
    print("")
    
    # Compare teams
    scraped_teams = {t["team_id"]: t for t in scraped_data.get("teams", [])}
    api_teams = {t["team_id"]: t for t in api_data.get("teams", [])}
    
    team_results = []
    for team_id in scraped_teams:
        if team_id in api_teams:
            result = validate_team(scraped_teams[team_id], api_teams[team_id])
            team_results.append(result)
        else:
            team_results.append({
                "team_name": scraped_teams[team_id].get("team_name"),
                "error": "Team missing in API data",
            })
    
    # Generate and print report
    report = generate_report(scraped_data, api_data, team_results)
    print(report)
    
    # Save report to file
    report_dir = project_root / "data" / "validation_reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"validation_{today_str}.txt"
    
    with open(report_path, 'w') as f:
        f.write(report)
    
    print(f"\n✅ Report saved to: {report_path}")
    
    # Exit with error code if there are discrepancies
    total_discrepancies = sum(len(r.get("discrepancies", [])) for r in team_results)
    if total_discrepancies > 0:
        print(f"\n⚠️  Found {total_discrepancies} discrepancies!")
        sys.exit(1)
    else:
        print("\n✅ All data matches!")
        sys.exit(0)


if __name__ == "__main__":
    main()
