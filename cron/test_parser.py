#!/usr/bin/env python3
"""
Test script to verify the HTML parsing logic for projected stats.
"""

import json
import requests
from bs4 import BeautifulSoup


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


def main():
    print("=" * 80)
    print("TESTING HTML PARSER FOR PROJECTED STATS")
    print("=" * 80)

    url= "https://basketball.fantasysports.yahoo.com/nba/93905/1?date=2026-02-09&stat1=P&ajaxrequest=1"

    # Load the real Yahoo response
    try:
         # Make the HTTP request
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            # Parse JSON response
            data = response.json()

            if "content" not in data:
                print(f"  ⚠️  No 'content' field in response")

            html_content = data["content"]
            print(f"  ✅ Retrieved HTML content ({len(html_content)} chars)")
    except FileNotFoundError:
        print("\n⚠️  Real Yahoo response not found at /tmp/yahoo_response.json")
        print("Run this command first:")
        print("  curl -s \"https://basketball.fantasysports.yahoo.com/nba/93905/1?stat1=P&ssort=D&ajaxrequest=1\" -o /tmp/yahoo_response.json")
        return

    players = parse_projected_stats_html(html_content)

    print(f"\n✅ Found {len(players)} players:\n")

    players_with_games = [p for p in players if p['fantasy_points'] > 0]
    if players_with_games:
        print(f"  Players with projected stats ({len(players_with_games)} players):")
        for player in players_with_games:
            print(f"    {player['player_name']} ({player['roster_position']}): "
                  f"{player['fantasy_points']} pts | "
                  f"PTS:{player['stats']['PTS']} REB:{player['stats']['REB']} AST:{player['stats']['AST']}")
    else:
        print("  ⚠️  No players have games scheduled for this date")

    # Look for Ty Jerome specifically
    print("\n🔍 Looking for Ty Jerome:")
    ty_found = False
    for player in players:
        if 'Jerome' in player['player_name']:
            ty_found = True
            print(f"  ✅ Found: {player['player_name']}")
            print(f"     Fantasy Points: {player['fantasy_points']}")
            print(f"     PTS: {player['stats']['PTS']}")
            print(f"     REB: {player['stats']['REB']}")
            print(f"     AST: {player['stats']['AST']}")
            if player['fantasy_points'] == 0.0:
                print(f"     ⚠️  Player has no game scheduled for this date")

    if not ty_found:
        print("  ⚠️  Ty Jerome not found in results")


if __name__ == "__main__":
    main()
