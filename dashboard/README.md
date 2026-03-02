# 🏀 OpenCommish Dashboard

A Streamlit dashboard for analyzing Yahoo NBA Fantasy Basketball data.

## 🚀 Quick Start

```bash
cd dashboard
pip install -r requirements.txt
streamlit run app.py
```

Opens at `http://localhost:8501`

---

## 📊 Pages

### 📊 Overview

Daily and weekly snapshot of the league.

**Key Metrics (Week-level)**
- Week number, start date, and end date
- Leading fantasy team for the current week (by total active points)
- Top NBA player of the week (highest individual fantasy points), their fantasy team, and total score

**Filters**
- Date selector (all dates in current week, or pick a specific day)
- Per-day breakdown toggle

**Charts & Tables**
- Stacked bar chart: active vs bench points per team, per day of the current week
- Daily points breakdown table: each team's points per date
- Top performers today and for the full week
- Player drill-down: select a player to see their per-date trend line

---

### 🏆 Team Rankings

Leaderboard scoped to the **current week**.

**Filters**
- Team selector: choose one or more teams to compare side by side
- Week selector (if historical weeks are available)

**Standings**
- Ranked list with medal icons (1st, 2nd, 3rd) ordered by active points for the selected week
- Comparison panel when multiple teams are selected: active points, bench points, bench %, roster breakdown

**Per-Team Cards**
- Active player count, bench player count
- Active points, bench points, bench %
- Best active player, best bench player

**Stats Table**
- `team_name`, `active_points`, `bench_points`, `total_points`, `bench_percentage`

---

### ⭐ Player Analysis

Individual player deep-dive with flexible filtering.

**Filters** (all multi-select)
- Date (single date or range)
- Team
- Position — note: `Util` and `BN` are roster slots, not positions; actual positions are `PG`, `SG`, `SF`, `PF`, `C`, `G`, `F`

**Top 20 Players Per Position**
- One horizontal bar chart per real position group (not Util/BN)
- Bars colored by fantasy team
- Aggregated across selected date range

**Position Breakdown**
- Bar chart: total fantasy points distribution by position
- Bar chart: average points per position

**Team Breakdown**
- Bar chart: total points contributed per fantasy team

**Full Player Table**
- All filtered players with: `name`, `team`, `roster_position`, `fantasy_points`, `date`

---

### 📈 Trends

Historical performance tracking over time.

**Filters**
- Fantasy team selector (multi-select, default: all)
- NBA player search/selector (overlay individual player trend on team chart)
- Date range selector

**Charts**
- Line chart: daily active points per fantasy team (last 14 days, markers on each data point)
- Optionally overlay an individual NBA player's daily points on the same chart

**Last 5 Games Summary Table**
- Columns: `date`, per-team active points
- Rows are the 5 most recent dates with data

**7-Day Summary Table**
- Per team: `average`, `min`, `max`, `std_dev` (lower std = more consistent)
- Bar chart visualizing consistency

**Bench Efficiency Trend**
- Line chart: bench % per team over time (lower = better lineup decisions)

---

### 💔 Bench Efficiency

Lineup optimization analysis, fully filterable.

**Filters**
- Team selector (multi-select)
- Date range selector

**Team Efficiency Ranking**
- Bar chart: bench % per team, color-coded green (low bench %) to red (high bench %)

**Missed Opportunities**
- Per-date, per-team: identifies days where a bench player outscored an active player
- Shows the point delta (points left on the table)
- Filterable by team and date

**Best Bench Players**
- Top 15 bench players who had the highest fantasy points while sitting on the bench
- Horizontal bar chart colored by team

**Team-by-Team Breakdown**
- Expandable section per team
- Active roster table: `player`, `position`, `fantasy_points`, `date`
- Bench roster table: `player`, `fantasy_points`, `date`

---

### 📉 Projected Stats Comparison

Compare projected vs actual performance at the team and player level.

**Filters**
- Date range selector
- Team selector (multi-select)
- Player search

**Per-Team Charts**
- Grouped bar chart: projected points vs actual points per team for each date
- Delta chart: actual minus projected (positive = outperformed, negative = underperformed)

**Per-Player Charts**
- Scatter plot: projected points (x-axis) vs actual points (y-axis); dots above the diagonal line outperformed projections
- Bar chart: top 20 players by projection delta (largest over/underperformers)

**Summary Table**
- Columns: `player`, `team`, `date`, `projected_points`, `actual_points`, `delta`, `delta_%`
- Sortable and filterable

---

## 🛠️ Requirements

- Python 3.8+
- `streamlit >= 1.30.0`
- `pandas >= 2.0.0`

## 📝 Data Sources

| Data | Path |
|------|------|
| Daily stats | `data/daily_stats/league_*.json` |
| Projected stats | `data/projected_stats/league_*.json` |

## 📱 Share / Deploy

```bash
# Local network access
streamlit run app.py --server.port 8501 --server.address 0.0.0.0
```

Or deploy to [Streamlit Cloud](https://streamlit.io/cloud) for free hosting.
