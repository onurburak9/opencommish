# Fetch Projected Stats Script

## Overview

`fetch_projected_stats.py` scrapes Yahoo Fantasy Basketball projected stats for all teams in a league by:
1. Using yfpy to authenticate and find the target league
2. Getting all teams in the league
3. Making HTTP requests to Yahoo's roster page endpoints
4. Parsing the HTML to extract projected stats for each player

## Automated Schedule

This script runs automatically via GitHub Actions:
- **Schedule**: Daily at 12:00 PM PST (8:00 PM UTC)
- **Workflow**: `.github/workflows/projected_stats.yml`
- **Trigger**: Automatic via cron schedule, or manual via GitHub UI

The workflow:
1. Runs the projection collection script
2. Commits the new JSON files to the repository
3. Pushes changes to the main branch

You can also trigger it manually from the GitHub Actions tab.

## Output Format

The script generates JSON files in `data/projected_stats/` with this structure:

```json
{
  "date": "2026-02-09",
  "league_id": "93905",
  "league_key": "nba.l.93905",
  "league_name": "teletabi ligi",
  "teams": [
    {
      "team_id": "1",
      "team_key": "nba.l.93905.t.1",
      "team_name": "Ankara Tinercileri",
      "players": [
        {
          "player_id": "6212",
          "player_name": "Ty Jerome",
          "roster_position": "SG",
          "opponent": "@GSW",
          "games_played": 1,
          "fantasy_points": 23.05,
          "stats": {
            "PTS": 12.6,
            "REB": 3.0,
            "AST": 3.7,
            "ST": 0.9,
            "BLK": 0.1,
            "TO": 1.7
          }
        }
      ]
    }
  ]
}
```

## Player Data Fields

- `player_id`: Yahoo player ID
- `player_name`: Full player name
- `roster_position`: Position slot (PG, SG, G, SF, PF, F, C, Util, BN, IL, IL+)
- `opponent`: Opponent team (e.g., "@GSW", "ATL", or empty if no game)
- `games_played`: Number of games scheduled (0 or 1 typically for daily view)
- `fantasy_points`: Total projected fantasy points
- `stats`: Dictionary with stat categories:
  - `PTS`: Points scored
  - `REB`: Total rebounds
  - `AST`: Assists
  - `ST`: Steals
  - `BLK`: Blocked shots
  - `TO`: Turnovers

## HTML Parsing Logic

The parser follows these steps:

1. **Find the stats table**: Looks for `<table id="statTable0">`
2. **Parse headers**: Reads the second `<thead><tr>` row to get column names
3. **Map columns**: Creates indices for: Pos, Players, GP*, Opp, Fan Pts, PTS, REB, AST, ST, BLK, TO
4. **Extract rows**: Iterates through `<tbody><tr>` elements
5. **Parse each cell**: 
   - Position from `<span class="pos-label">`
   - Player name and ID from `<a class="name">`
   - Stats from corresponding `<td>` cells
   - Handles empty/zero values (often wrapped in `<span class="F-faded">`)

## Usage

### Manual Run

```bash
cd /Users/onuryildirim/Documents/workspace/opencommish
python cron/fetch_projected_stats.py
```

### Environment Variables Required

```bash
YAHOO_ACCESS_TOKEN=your_access_token
YAHOO_CONSUMER_KEY=your_consumer_key
YAHOO_CONSUMER_SECRET=your_consumer_secret
YAHOO_GUID=your_guid
YAHOO_REFRESH_TOKEN=your_refresh_token
YAHOO_TOKEN_TIME=timestamp
YAHOO_TOKEN_TYPE=bearer
```

## Expected Output

```
================================================================================
PROJECTED STATS COLLECTION
================================================================================
✅ Authenticated with Yahoo API
Current game key: 428

Found 1 league(s)
✅ Target league found: teletabi ligi
Fetching projected stats for 2026-02-09
Processing 8 teams...

Team [1/8] Ankara Tinercileri (ID: 1)
  Fetching: https://basketball.fantasysports.yahoo.com/nba/93905/1/team?&date=2026-02-09&stat1=P&stat2=P&&ajaxrequest=1
  ✅ Retrieved HTML content (150234 chars)
  Column headers: ['Pos', 'Players', 'Action', '', 'GP*', 'Opp', 'Fan Pts', ...]
  ✅ Parsed 15 players
    - Jalen Brunson (PG): 0.0 pts | PTS:0.0 REB:0.0 AST:0.0
    - Ty Jerome (SG): 23.05 pts | PTS:12.6 REB:3.0 AST:3.7
    - Cooper Flagg (G): 0.0 pts | PTS:0.0 REB:0.0 AST:0.0

✅ Saved projected stats snapshot to: data/projected_stats/league_93905_2026-02-09.json
   Total teams: 8
   Total players: 120
```

## Testing the Parser

A test script is provided to verify the parsing logic:

```bash
python cron/test_parser.py
```

## Dependencies

- `yfpy>=17.0.0` - Yahoo Fantasy API wrapper
- `beautifulsoup4>=4.12.0` - HTML parsing
- `requests>=2.31.0` - HTTP requests

Install with:
```bash
pip install -r requirements.txt
```

## Notes

- The script uses Pacific timezone for date consistency with Yahoo Fantasy
- Players with no games scheduled (GP* = 0) will have zero stats
- The `Fan Pts` column contains the total projected fantasy points
- Bench (BN) and injured list (IL, IL+) players are included
- The script makes one HTTP request per team, so rate limiting is minimal
