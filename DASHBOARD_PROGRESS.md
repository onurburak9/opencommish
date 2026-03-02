# Dashboard UI Progress

Tracks all planned and completed changes to `dashboard/app.py` and related files.

---

## Status Legend
- ✅ Done
- 🔄 In Progress
- ⬜ Pending

---

## Global Changes

| # | Change | Status |
|---|--------|--------|
| G1 | Remove `import plotly.express as px` and `import plotly.graph_objects as go` | ✅ |
| G2 | Remove unused `import glob` | ✅ |
| G3 | Add global sidebar date range filter (drives all pages) | ✅ |
| G4 | Add `get_all_players_multi(all_data)` helper (multi-day, includes `date` column) | ✅ |
| G5 | Add `calculate_team_metrics_multi(all_data)` helper (aggregates across days) | ✅ |
| G6 | Remove `print()` debug calls from `calculate_week_team_metrics` | ✅ |

---

## Overview Page

| # | Change | Status |
|---|--------|--------|
| O1 | Show week number, start date, and end date as key metrics | ✅ |
| O2 | Leading team metric based on week totals (not single day) | ✅ |
| O3 | Top NBA player metric: name, fantasy team, total score | ✅ |
| O4 | Replace Plotly stacked bar with `st.bar_chart(stack=True, horizontal=True)` | ✅ |
| O5 | Replace Plotly daily breakdown bar with `st.bar_chart` pivot | ✅ |
| O6 | Add `date` column to top player tables | ✅ |
| O7 | Replace Plotly player trend bar with `st.bar_chart` | ✅ |

---

## Team Rankings Page

| # | Change | Status |
|---|--------|--------|
| T1 | Scope rankings to selected date range (use `calculate_team_metrics_multi`) | ✅ |
| T2 | Add team multi-select filter for side-by-side comparison | ✅ |
| T3 | Show comparison panel when multiple teams selected | ✅ |
| T4 | Add date range caption | ✅ |

---

## Player Analysis Page

| # | Change | Status |
|---|--------|--------|
| P1 | Exclude `Util` and `BN` from position filter (roster slots ≠ positions) | ✅ |
| P2 | Top 20 players per real position (one chart per position group) | ✅ |
| P3 | Replace Plotly top-20 bar with `st.bar_chart(horizontal=True)` | ✅ |
| P4 | Replace Plotly pie chart with horizontal `st.bar_chart` | ✅ |
| P5 | Replace Plotly avg-by-position bar with `st.bar_chart` | ✅ |
| P6 | Add team breakdown bar chart (total points per fantasy team) | ✅ |
| P7 | Ensure `date` column visible in full player table | ✅ |

---

## Trends Page

| # | Change | Status |
|---|--------|--------|
| TR1 | Replace Plotly active-points line with `st.line_chart` pivot | ✅ |
| TR2 | Add NBA player search to overlay individual trend on team chart | ✅ |
| TR3 | Add "Last 5 Games" summary table with dates | ✅ |
| TR4 | Replace Plotly 7-day average bar with `st.bar_chart` | ✅ |
| TR5 | Replace Plotly bench efficiency line with `st.line_chart` pivot | ✅ |
| TR6 | Fix 7-day cutoff to use last date in filtered data, not `datetime.now()` | ✅ |

---

## Bench Efficiency Page

| # | Change | Status |
|---|--------|--------|
| B1 | Add team multi-select filter | ✅ |
| B2 | Use `calculate_team_metrics_multi(filtered_data)` | ✅ |
| B3 | Replace Plotly bench % bar with `st.bar_chart` | ✅ |
| B4 | Replace Plotly best-bench bar with `st.bar_chart(horizontal=True)` | ✅ |
| B5 | Include `date` column in team expander tables | ✅ |
| B6 | Add date range caption | ✅ |

---

## Projected Stats Comparison Page (New)

| # | Change | Status |
|---|--------|--------|
| PS1 | Add `load_projected_data(days)` loader for `data/projected_stats/` | ✅ |
| PS2 | Add `build_comparison_df(daily_data, projected_data)` helper | ✅ |
| PS3 | Add page to navigation | ✅ |
| PS4 | Date range + team + player filters | ✅ |
| PS5 | Per-team grouped bar: projected vs actual | ✅ |
| PS6 | Per-team delta bar: actual − projected | ✅ |
| PS7 | Top 20 over/underperformers bar charts | ✅ |
| PS8 | Summary table: `player`, `team`, `projected`, `actual`, `delta`, `delta_%` | ✅ |
| PS9 | Per-player per-date detail table | ✅ |

---

## Completed — 2026-03-02

All items above implemented in a single pass. Key decisions:

- **No more Plotly** — all charts use native `st.bar_chart` / `st.line_chart`
- **Global date range filter** in sidebar drives every page via `filtered_data`
- **`get_all_players_multi`** replaces the old single-day `get_all_players`
- **`calculate_team_metrics_multi`** replaces the old single-day `calculate_team_metrics`
- `BN` / `Util` excluded from Player Analysis position filter (they are roster slots, not basketball positions)
- Projected stats comparison matches players by `(date, player_name)` join key
- README cleaned up — scratch/planning notes removed, Plotly removed from requirements
