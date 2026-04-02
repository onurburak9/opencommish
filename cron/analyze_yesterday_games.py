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


def fetch_yesterday_stats(target_date: date) -> tuple[dict, YahooFantasySportsQuery]:
    """Fetch yesterday's stats from Yahoo API.

    Returns tuple of (daily_snapshot_data, query_object) so query can be reused.
    """
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

    return daily_snapshot, query


def fetch_matchup_scores(target_date: date, query: YahooFantasySportsQuery | None = None) -> list[dict] | None:
    """Fetch matchup scores and projections for the week containing target_date.

    If query is None, will create a new connection (requires env vars).
    Returns list of matchups with team scores and projected scores, or None if error.
    Projections come from the Yahoo API (team_projected_points) and fall back to
    scraping the Yahoo Fantasy matchup page if not available.
    """
    try:
        if query is None:
            load_env_file()

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
                print("⚠️ Missing Yahoo API credentials for matchup fetch")
                return None

            query = YahooFantasySportsQuery(
                league_id="93905",
                game_code="nba",
                game_id=None,
                yahoo_access_token_json=access_token_json,
            )

        # Get the week number for the target date
        game_info = query.get_current_game_info()
        game_weeks = query.get_game_weeks_by_game_id(game_info.game_id)

        target_week = None
        for gw in game_weeks:
            week_start = date.fromisoformat(to_str(gw.start))
            week_end = date.fromisoformat(to_str(gw.end))
            if week_start <= target_date <= week_end:
                target_week = int(to_str(gw.week))
                break

        if target_week is None:
            print(f"⚠️ Could not find week for {target_date}")
            return None

        # Fetch scoreboard for that week
        scoreboard = query.get_league_scoreboard_by_week(target_week)

        matchups = []
        has_any_projections = False
        for matchup in scoreboard.matchups:
            # Get teams in this matchup
            teams_data = []
            for team in matchup.teams:
                tp = getattr(team, 'team_points', None)
                team_points = float(to_str(tp.total)) if tp and hasattr(tp, 'total') else 0.0

                # Extract projected points from API
                tpp = getattr(team, 'team_projected_points', None)
                projected_points = None
                if tpp and hasattr(tpp, 'total'):
                    try:
                        projected_points = float(to_str(tpp.total))
                        has_any_projections = True
                    except (ValueError, TypeError):
                        pass

                teams_data.append({
                    "team_name": to_str(team.name),
                    "team_key": to_str(team.team_key),
                    "points": team_points,
                    "projected_points": projected_points,
                    "games_played": None,
                    "games_remaining": None,
                })

            if len(teams_data) == 2:
                matchups.append({
                    "matchup_id": matchup.matchup_id if hasattr(matchup, 'matchup_id') else None,
                    "week": target_week,
                    "team_1": teams_data[0],
                    "team_2": teams_data[1],
                    "winner": teams_data[0]["team_name"] if teams_data[0]["points"] > teams_data[1]["points"]
                              else teams_data[1]["team_name"] if teams_data[1]["points"] > teams_data[0]["points"]
                              else "Tie",
                })

        # Scrape Yahoo Fantasy roster pages for game counts and projections fallback
        all_team_ids = set()
        for m in matchups:
            for key in ("team_1", "team_2"):
                tk = m[key].get("team_key", "")
                tid = tk.rsplit(".t.", 1)[-1] if ".t." in tk else ""
                if tid:
                    all_team_ids.add(tid)

        if all_team_ids:
            scraped = scrape_team_weekly_stats("93905", all_team_ids)
            if scraped:
                _merge_scraped_team_stats(matchups, scraped, has_any_projections)

        proj_count = sum(
            1 for m in matchups
            if m["team_1"].get("projected_points") is not None
        )
        print(f"🔮 Matchup projections: {proj_count}/{len(matchups)} matchups have projections")

        return matchups

    except Exception as e:
        print(f"⚠️ Could not fetch matchup scores: {e}")
        return None


def scrape_team_weekly_stats(league_id: str, team_ids: set[str]) -> dict[str, dict] | None:
    """Scrape weekly projected stats for each team from Yahoo Fantasy roster pages.

    Uses the same roster page format as fetch_projected_stats.py (stat1=P&stat2=P)
    but without a date parameter to get the full-week view.

    Returns dict mapping team_key -> {projected_points, games_played, games_remaining}
    where games_played/games_remaining count active roster slots only (excludes BN/IL/IL+).
    """
    import requests
    from bs4 import BeautifulSoup

    BENCH_POSITIONS = {"BN", "IL", "IL+"}
    results: dict[str, dict] = {}

    print(f"🔮 Scraping weekly projections for {len(team_ids)} teams...")

    for team_id in sorted(team_ids):
        url = (
            f"https://basketball.fantasysports.yahoo.com/nba/{league_id}/{team_id}"
            f"/team?stat1=P&stat2=P&ajaxrequest=1"
        )

        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()

            html_content = data.get("content", "")
            if not html_content:
                continue

            players = _parse_roster_projections_html(html_content)
            if not players:
                continue

            total_projected = 0.0
            games_played = 0
            games_remaining = 0

            for p in players:
                if p["roster_position"] in BENCH_POSITIONS:
                    continue
                total_projected += p["fantasy_points"]
                gp = p["games_played"]  # GP* from Yahoo = games left to play
                if gp > 0:
                    games_remaining += gp
                # Players with 0 GP* but nonzero projected points already played
                # (Yahoo zeroes out GP* once a game is completed)
                if p["fantasy_points"] > 0 and gp == 0:
                    games_played += 1

            team_key = f"466.l.{league_id}.t.{team_id}"
            results[team_key] = {
                "projected_points": round(total_projected, 2),
                "games_played": games_played,
                "games_remaining": games_remaining,
            }
            print(f"  Team {team_id}: proj={total_projected:.1f}, GP={games_played}, GR={games_remaining}")

        except Exception as e:
            print(f"  ⚠️ Could not scrape team {team_id}: {e}")
            continue

    return results if results else None


def _parse_roster_projections_html(html_content: str) -> list[dict]:
    """Parse Yahoo Fantasy roster HTML for projected stats.

    Reuses the same HTML table format as fetch_projected_stats.py.
    Returns list of player dicts with roster_position, fantasy_points, games_played.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html_content, 'html.parser')
    table = soup.find('table', {'id': 'statTable0'})
    if not table:
        return []

    thead = table.find('thead')
    if not thead:
        return []

    header_rows = thead.find_all('tr')
    if len(header_rows) < 2:
        return []

    headers = []
    for th in header_rows[1].find_all('th'):
        div = th.find('div')
        text = div.get_text(strip=True) if div else th.get_text(strip=True)
        if not text or text == '\xa0':
            text = th.get('title', '') or f"col_{len(headers)}"
        colspan = int(th.get('colspan', 1))
        for i in range(colspan):
            headers.append(text if i == 0 else f"{text}_{i}")

    try:
        pos_idx = headers.index('Pos')
        fan_pts_idx = headers.index('Fan Pts')
        gp_idx = headers.index('GP*')
    except ValueError:
        return []

    tbody = table.find('tbody')
    if not tbody:
        return []

    players = []
    for row in tbody.find_all('tr'):
        cells = row.find_all('td')
        if len(cells) <= max(pos_idx, fan_pts_idx, gp_idx):
            continue

        pos_span = cells[pos_idx].find('span', {'class': 'pos-label'})
        if not pos_span:
            continue
        roster_position = pos_span.get_text(strip=True)

        fan_pts_text = cells[fan_pts_idx].get_text(strip=True)
        try:
            fantasy_points = float(fan_pts_text) if fan_pts_text else 0.0
        except ValueError:
            fantasy_points = 0.0

        gp_text = cells[gp_idx].get_text(strip=True)
        try:
            games_played = int(gp_text) if gp_text and gp_text != '0' else 0
        except ValueError:
            games_played = 0

        players.append({
            "roster_position": roster_position,
            "fantasy_points": fantasy_points,
            "games_played": games_played,
        })

    return players


def _merge_scraped_team_stats(
    matchups: list[dict],
    scraped: dict[str, dict],
    has_api_projections: bool,
) -> None:
    """Merge scraped team stats (game counts, projections) into matchup data."""
    for matchup in matchups:
        for key in ("team_1", "team_2"):
            team = matchup[key]
            team_data = scraped.get(team.get("team_key", ""))
            if not team_data:
                continue
            team["games_played"] = team_data["games_played"]
            team["games_remaining"] = team_data["games_remaining"]
            if not has_api_projections and team.get("projected_points") is None:
                team["projected_points"] = team_data["projected_points"]


def _format_matchup_extras(team: dict) -> str:
    """Format projection and game count info for matchup display."""
    parts = []
    if team.get('projected_points') is not None:
        parts.append(f"proj: {team['projected_points']:.2f}")
    if team.get('games_played') is not None and team.get('games_remaining') is not None:
        parts.append(f"GP: {team['games_played']}, GR: {team['games_remaining']}")
    return f" ({', '.join(parts)})" if parts else ""


def analyze_yesterday_games(data: dict, matchup_scores: list[dict] | None = None) -> dict:
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
        "matchups": matchup_scores if matchup_scores else [],
        "top_5_overall": [],
        "best_per_team": {},
        "worst_per_team": {},
    }

    # Print matchup scores if available
    if matchup_scores:
        print("🏀 WEEKLY MATCHUP SCORES")
        print("-" * 80)
        for matchup in matchup_scores:
            t1 = matchup["team_1"]
            t2 = matchup["team_2"]
            winner = matchup["winner"]

            # Determine winner indicator
            if winner == "Tie":
                result = "TIE"
            elif winner == t1["team_name"]:
                result = f"{t1['team_name']} WINS"
            else:
                result = f"{t2['team_name']} WINS"

            # Format score lines with projections and game counts
            t1_extras = _format_matchup_extras(t1)
            t2_extras = _format_matchup_extras(t2)

            print(f"  {t1['team_name']}: {t1['points']:.2f}{t1_extras}")
            print(f"  {t2['team_name']}: {t2['points']:.2f}{t2_extras}")

            # Show projected winner if projections available
            if t1.get('projected_points') is not None and t2.get('projected_points') is not None:
                if t1['projected_points'] > t2['projected_points']:
                    proj_winner = t1['team_name']
                elif t2['projected_points'] > t1['projected_points']:
                    proj_winner = t2['team_name']
                else:
                    proj_winner = "Tie"
                print(f"  → Actual: {result} | Projected: {proj_winner}")
            else:
                print(f"  → {result}")
            print()
        print()

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

    query = None
    if data:
        print(f"✅ Loaded existing data from data/daily_stats/league_93905_{date_str}.json")
    else:
        print(f"🔄 Data not found locally. Fetching from Yahoo API...")
        try:
            data, query = fetch_yesterday_stats(target_date)
        except Exception as e:
            print(f"❌ Error fetching data: {e}")
            sys.exit(1)

    # Fetch matchup scores if we don't have them already
    matchup_scores = None
    if data and "week" in data:
        try:
            matchup_scores = fetch_matchup_scores(target_date, query)
        except Exception as e:
            print(f"⚠️ Could not fetch matchup scores: {e}")

    # Run analysis
    results = analyze_yesterday_games(data, matchup_scores)

    # Save results to file
    output_dir = Path(__file__).parent.parent / "data" / "analysis"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"yesterday_analysis_{date_str}.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n💾 Results saved to: {output_path}")


if __name__ == "__main__":
    main()
