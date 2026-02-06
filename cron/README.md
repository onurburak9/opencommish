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
