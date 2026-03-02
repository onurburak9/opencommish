#!/usr/bin/env python3
"""
Fetch projected stats for all teams in league by scraping Yahoo Fantasy roster pages.
This script:
1. Finds the target league by name using yfpy
2. Gets all teams in the league
3. Makes HTTP requests to Yahoo Fantasy roster endpoints to get projected stats HTML
4. Parses the HTML to extract projected stats data
"""

import os
import sys
import json
import requests
from pathlib import Path
from datetime import datetime, date
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from yfpy.query import YahooFantasySportsQuery, Team, League


def to_str(value):
    """Convert bytes to string, or return value as-is."""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def parse_projected_stats_html(html_content: str) -> list:
    """
    Parse Yahoo Fantasy projected stats HTML to extract player data.
    
    Returns list of player dictionaries with:
    - player_id: Yahoo player ID
    - player_name: Full player name
    - roster_position: Position slot (PG, SG, G, SF, PF, F, C, Util, BN, IL, IL+)
    - opponent: Opponent team abbreviation
    - games_played: Number of games (GP*)
    - fantasy_points: Projected fantasy points
    - stats: Dictionary of stat categories (PTS, REB, AST, ST, BLK, TO)
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Find the main stats table
    table = soup.find('table', {'id': 'statTable0'})
    if not table:
        print("  ⚠️  Could not find stats table")
        return []
    
    # Parse the header row to get column positions
    thead = table.find('thead')
    if not thead:
        print("  ⚠️  Could not find table header")
        return []
    
    # Get the second header row which has the actual column names
    header_rows = thead.find_all('tr')
    if len(header_rows) < 2:
        print("  ⚠️  Could not find header row with column names")
        return []
    
    header_row = header_rows[1]  # Second row has column names
    headers = []
    header_cells = header_row.find_all('th')
    
    for idx, th in enumerate(header_cells):
        # Get the text content, handling nested divs
        div = th.find('div')
        if div:
            text = div.get_text(strip=True)
        else:
            text = th.get_text(strip=True)
        
        # Handle empty headers or &nbsp; - use column position as fallback
        if not text or text == '\xa0' or text == '':
            # Check for title attribute which might have the column name
            title = th.get('title', '')
            if title:
                text = title
            else:
                text = f"col_{idx}"  # Fallback to column index
        
        # Check if this header has colspan
        colspan = int(th.get('colspan', 1))
        
        # Add the header once for each column it spans
        for i in range(colspan):
            if i == 0:
                headers.append(text)
            else:
                # For additional columns from colspan, add numbered suffix
                headers.append(f"{text}_{i}" if text != f"col_{idx}" else f"col_{idx}_{i}")
    
    print(f"  Column headers ({len(headers)} total): {headers}")
    
    # Map header names to indices
    try:
        pos_idx = headers.index('Pos')
        players_idx = headers.index('Players')
        gp_idx = headers.index('GP*')
        opp_idx = headers.index('Opp')
        fan_pts_idx = headers.index('Fan Pts')
        pts_idx = headers.index('PTS')
        reb_idx = headers.index('REB')
        ast_idx = headers.index('AST')
        st_idx = headers.index('ST')
        blk_idx = headers.index('BLK')
        to_idx = headers.index('TO')
    except ValueError as e:
        print(f"  ⚠️  Could not find required column: {e}")
        return []
    
    # Parse player rows from tbody
    tbody = table.find('tbody')
    if not tbody:
        print("  ⚠️  Could not find table body")
        return []
    
    players = []
    for row in tbody.find_all('tr'):
        cells = row.find_all('td')
        if len(cells) < len(headers):
            continue
        
        # Extract roster position
        pos_cell = cells[pos_idx]
        pos_span = pos_cell.find('span', {'class': 'pos-label'})
        if not pos_span:
            continue
        roster_position = pos_span.get_text(strip=True)
        
        # Extract player name and ID
        player_cell = cells[players_idx]
        player_link = player_cell.find('a', {'class': 'name'})
        if not player_link:
            continue
        
        player_name = player_link.get_text(strip=True)
        player_id = player_link.get('data-ys-playerid', '')
        
        # Extract opponent
        opp_cell = cells[opp_idx]
        opponent = opp_cell.get_text(strip=True)
        
        # Extract games played
        gp_cell = cells[gp_idx]
        gp_text = gp_cell.get_text(strip=True)
        try:
            games_played = int(gp_text) if gp_text and gp_text != '0' else 0
        except ValueError:
            games_played = 0
        
        # Extract fantasy points
        fan_pts_cell = cells[fan_pts_idx]
        fan_pts_text = fan_pts_cell.get_text(strip=True)
        try:
            fantasy_points = float(fan_pts_text) if fan_pts_text else 0.0
        except ValueError:
            fantasy_points = 0.0
        
        # Extract stat values
        def extract_stat(cell):
            """Extract stat value, handling F-faded (0 values) spans"""
            text = cell.get_text(strip=True)
            # If text is '0' or empty or contains 'F-faded', it's likely 0
            if not text or text == '0':
                return 0.0
            try:
                return float(text)
            except ValueError:
                return 0.0
        
        pts = extract_stat(cells[pts_idx])
        reb = extract_stat(cells[reb_idx])
        ast = extract_stat(cells[ast_idx])
        st = extract_stat(cells[st_idx])
        blk = extract_stat(cells[blk_idx])
        to = extract_stat(cells[to_idx])
        
        player_data = {
            "player_id": player_id,
            "player_name": player_name,
            "roster_position": roster_position,
            "opponent": opponent,
            "games_played": games_played,
            "fantasy_points": fantasy_points,
            "stats": {
                "PTS": pts,
                "REB": reb,
                "AST": ast,
                "ST": st,
                "BLK": blk,
                "TO": to,
            }
        }
        
        players.append(player_data)
    
    return players


def main() -> None:
    print("=" * 80)
    print("PROJECTED STATS COLLECTION")
    print("=" * 80)

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

    # Allow passing a specific date via CLI arg (YYYY-MM-DD), defaulting to today PST.
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

    print(f"Fetching projected stats for {today_str}")

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

        # Construct the Yahoo Fantasy roster URL
        league_id = to_str(target_league.league_id)
        url = f"https://basketball.fantasysports.yahoo.com/nba/{league_id}/{team_id}/team?&date={today_str}&stat1=P&stat2=P&&ajaxrequest=1"

        print(f"  Fetching: {url}")

        try:
            # Make the HTTP request
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            # Parse JSON response
            data = response.json()
            
            if "content" not in data:
                print(f"  ⚠️  No 'content' field in response")
                continue

            html_content = data["content"]
            print(f"  ✅ Retrieved HTML content ({len(html_content)} chars)")

            # Parse the HTML to extract player projected stats
            players = parse_projected_stats_html(html_content)
            
            if not players:
                print(f"  ⚠️  No players found in HTML")
                continue
            
            print(f"  ✅ Parsed {len(players)} players")
            
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

        except requests.exceptions.RequestException as e:
            print(f"  ❌ Error fetching data: {e}")
            continue
        except Exception as e:
            print(f"  ❌ Error parsing data: {e}")
            continue

    # Save snapshot to JSON
    output_dir = Path(__file__).parent.parent / "data" / "projected_stats"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"league_{target_league.league_id}_{today_str}.json"

    with output_path.open("w", encoding="utf-8") as output_file:
        json.dump(projected_snapshot, output_file, indent=2, ensure_ascii=False)

    print(f"\n✅ Saved projected stats snapshot to: {output_path}")
    print(f"   Total teams: {len(projected_snapshot['teams'])}")
    print(f"   Total players: {sum(len(t['players']) for t in projected_snapshot['teams'])}")


if __name__ == "__main__":
    main()
