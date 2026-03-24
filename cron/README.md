# Cron Jobs

Scheduled scripts for automated data collection.

## Scripts

### `fetch_daily_stats.py`

Collects daily fantasy basketball stats for all teams in the league.

**What it does:**
- Authenticates with Yahoo Fantasy API
- Fetches current week roster for each team
- Retrieves player stats for today
- Calculates fantasy points using league scoring settings
- Saves to `data/daily_stats/league_{league_id}_{date}.json`

**Schedule:**
- Runs daily at 11:30 PM PST via GitHub Actions
- Workflow: `.github/workflows/daily_stats.yml`

**Manual Run:**
```bash
python3 cron/fetch_daily_stats.py
```

**Requirements:**
- Yahoo API credentials (CLIENT_ID, CLIENT_SECRET)
- OAuth refresh token (generated on first auth)
- See `requirements.txt` for Python dependencies

**Configuration:**
- League name is hardcoded: "teletabi ligi"
- Game code: "nba"
- Output directory: `data/daily_stats/`

### `analyze_yesterday_games.py`

Analyzes fantasy performance from yesterday's games with detailed breakdowns.

**What it does:**
- Loads daily stats from local cache or fetches from Yahoo API if missing
- Calculates total fantasy points per team
- Ranks all NBA players by fantasy points scored
- Identifies top 5 best performers overall
- Shows best 2 and worst 2 performers per fantasy team
- Saves analysis results to `data/analysis/`

**Manual Run:**
```bash
# Defaults to yesterday (PST)
python3 cron/analyze_yesterday_games.py

# Specify a date
python3 cron/analyze_yesterday_games.py 2026-03-23
```

**Output:**
- Console: formatted summary with rankings and team breakdowns
- File: `data/analysis/yesterday_analysis_{date}.json`

**Requirements:**
- Yahoo API credentials (`YAHOO_CLIENT_ID`, `YAHOO_CLIENT_SECRET`)
- OAuth refresh token
- Pre-fetched daily stats in `data/daily_stats/` (or will fetch live)
