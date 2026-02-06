# Data Directory

This directory contains collected fantasy basketball data.

## Structure

- `daily_stats/` - Daily player statistics for all teams in the league
  - Files named: `league_{league_id}_{YYYY-MM-DD}.json`
  - Collected automatically via GitHub Actions at 11:30 PM PST

## Data Format

Each JSON file contains:
- Date and week number
- League information
- All teams in the league
- For each team:
  - Team info (id, key, name)
  - All players on roster
  - For each player:
    - Player info (id, key, name, roster position)
    - Daily stats with fantasy point calculations
    - Total fantasy points for the day

## Collection Schedule

Data is collected daily at 11:30 PM PST via GitHub Actions workflow.
