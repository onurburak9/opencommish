import streamlit as st
import json
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

# Page configuration
st.set_page_config(
    page_title="OpenCommish - Fantasy Basketball Dashboard",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 3rem !important;
        font-weight: 700 !important;
        color: #1f77b4 !important;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
    }
    .team-card {
        background: #f0f2f6;
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# Resolve data directory relative to the project root (parent of dashboard/)
PROJECT_ROOT = Path(__file__).parent.parent

# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300)
def load_latest_data():
    """Load the most recent day's data."""
    data_dir = PROJECT_ROOT / "data/daily_stats"
    stats_files = sorted(data_dir.glob("league_*.json"))
    if not stats_files:
        return None
    with open(stats_files[-1]) as f:
        return json.load(f)


@st.cache_data(ttl=300)
def load_all_data(days=30):
    """Load last N days of data."""
    data_dir = PROJECT_ROOT / "data/daily_stats"
    stats_files = sorted(data_dir.glob("league_*.json"))[-days:]
    all_data = []
    for stats_file in stats_files:
        with open(stats_file) as f:
            all_data.append(json.load(f))
    return all_data


@st.cache_data(ttl=300)
def load_current_week_data():
    """Load all days for the current (latest) week."""
    data_dir = PROJECT_ROOT / "data/daily_stats"
    stats_files = sorted(data_dir.glob("league_*.json"))
    if not stats_files:
        return []
    with open(stats_files[-1]) as f:
        latest = json.load(f)
    current_week = latest['week']
    week_data = []
    for stats_file in stats_files:
        with open(stats_file) as f:
            d = json.load(f)
        if d['week'] == current_week:
            week_data.append(d)
    return week_data


@st.cache_data(ttl=300)
def load_projected_data(days=30):
    """Load last N days of projected stats."""
    data_dir = PROJECT_ROOT / "data/projected_stats"
    proj_files = sorted(data_dir.glob("league_*.json"))[-days:]
    all_proj = []
    for pf in proj_files:
        with open(pf) as f:
            all_proj.append(json.load(f))
    return all_proj


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def calculate_week_team_metrics(week_data):
    """Aggregate active/bench points per team across all days in a week."""
    team_active = defaultdict(float)
    team_bench = defaultdict(float)
    team_meta = {}

    for day in week_data:
        for team in day['teams']:
            name = team['team_name']
            team_meta[name] = {'team_id': team['team_id']}
            for p in team['players']:
                if p['roster_position'] == 'BN':
                    team_bench[name] += p['fantasy_points']
                else:
                    team_active[name] += p['fantasy_points']

    rows = []
    for name in team_meta:
        active = team_active[name]
        bench = team_bench[name]
        total = active + bench
        rows.append({
            'team_name': name,
            'team_id': team_meta[name]['team_id'],
            'active_points': active,
            'bench_points': bench,
            'total_points': total,
            'bench_percentage': (bench / total * 100) if total > 0 else 0,
        })
    return pd.DataFrame(rows)


def get_week_daily_breakdown(week_data):
    """Return per-day, per-team total points (active + bench) for the current week."""
    rows = []
    for day in week_data:
        for team in day['teams']:
            total = sum(p['fantasy_points'] for p in team['players'])
            rows.append({
                'date': day['date'],
                'team': team['team_name'],
                'total_points': total,
            })
    return pd.DataFrame(rows)


def get_all_players_multi(all_data: list) -> pd.DataFrame:
    """Get all players across multiple days, including a 'date' column."""
    players = []
    for day_data in all_data:
        for team in day_data['teams']:
            for player in team['players']:
                player_info = {
                    'date': day_data['date'],
                    'name': player['name'],
                    'nba_team': player.get('nba_team', ''),
                    'opponent': player.get('opponent', ''),
                    'team': team['team_name'],
                    'roster_position': player['roster_position'],
                    'fantasy_points': player['fantasy_points'],
                    'is_bench': player['roster_position'] == 'BN',
                    'is_active': player['roster_position'] != 'BN',
                }
                if player.get('stats'):
                    for stat in player['stats']:
                        if isinstance(stat, dict):
                            player_info[stat['display_name']] = stat['value']
                players.append(player_info)
    return pd.DataFrame(players)


def calculate_team_metrics_multi(all_data: list) -> pd.DataFrame:
    """Aggregate active/bench points per team across multiple days."""
    team_active: dict = defaultdict(float)
    team_bench: dict = defaultdict(float)
    team_best_bench: dict = {}
    team_worst_active: dict = {}

    for day_data in all_data:
        for team in day_data['teams']:
            name = team['team_name']
            for p in team['players']:
                if p['roster_position'] == 'BN':
                    team_bench[name] += p['fantasy_points']
                    if name not in team_best_bench or p['fantasy_points'] > team_best_bench[name][1]:
                        team_best_bench[name] = (p['name'], p['fantasy_points'])
                else:
                    team_active[name] += p['fantasy_points']
                    if name not in team_worst_active or p['fantasy_points'] < team_worst_active[name][1]:
                        team_worst_active[name] = (p['name'], p['fantasy_points'])

    rows = []
    for name in team_active:
        active = team_active[name]
        bench = team_bench[name]
        total = active + bench
        bb = team_best_bench.get(name, (None, 0))
        wa = team_worst_active.get(name, (None, 0))
        rows.append({
            'team_name': name,
            'active_points': active,
            'bench_points': bench,
            'total_points': total,
            'bench_percentage': (bench / total * 100) if total > 0 else 0,
            'best_bench_player': bb[0],
            'best_bench_points': bb[1],
            'worst_active_player': wa[0],
            'worst_active_points': wa[1],
        })
    return pd.DataFrame(rows)


def get_trend_data(all_data):
    """Get trend data for teams over time."""
    trend_data = []
    for day_data in all_data:
        date = day_data['date']
        for team in day_data['teams']:
            active_players = [p for p in team['players'] if p['roster_position'] != 'BN']
            active_points = sum(p['fantasy_points'] for p in active_players)
            bench_players = [p for p in team['players'] if p['roster_position'] == 'BN']
            bench_points = sum(p['fantasy_points'] for p in bench_players)
            trend_data.append({
                'date': date,
                'team': team['team_name'],
                'active_points': active_points,
                'bench_points': bench_points,
                'total_points': active_points + bench_points,
            })
    return pd.DataFrame(trend_data)


def build_comparison_df(daily_data: list, projected_data: list) -> pd.DataFrame:
    """Join actual vs projected fantasy points per player per date."""
    # Build projected lookup: (date, player_name) -> projected_points
    proj_lookup: dict = {}
    for day in projected_data:
        date = day['date']
        for team in day['teams']:
            team_name = team['team_name']
            for p in team['players']:
                key = (date, p['player_name'])
                proj_lookup[key] = {
                    'projected_points': p['fantasy_points'],
                    'team': team_name,
                }

    rows = []
    for day in daily_data:
        date = day['date']
        for team in day['teams']:
            for p in team['players']:
                key = (date, p['name'])
                proj = proj_lookup.get(key)
                if proj is None:
                    continue
                actual = p['fantasy_points']
                projected = proj['projected_points']
                delta = actual - projected
                rows.append({
                    'date': date,
                    'player': p['name'],
                    'team': team['team_name'],
                    'roster_position': p['roster_position'],
                    'actual_points': actual,
                    'projected_points': projected,
                    'delta': delta,
                    'delta_%': (delta / projected * 100) if projected != 0 else 0,
                })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

st.sidebar.image(
    "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7a/Basketball.png/220px-Basketball.png",
    width=100,
)
st.sidebar.title("🏀 OpenCommish")
st.sidebar.markdown("---")

page = st.sidebar.radio("Navigation", [
    "📊 Overview",
    "🏆 Team Rankings",
    "⭐ Player Analysis",
    "📈 Trends",
    "💔 Bench Efficiency",
    "📉 Projected Stats",
])

st.sidebar.markdown("---")

# Load data
data = load_latest_data()
if data is None:
    st.error("❌ No data found! Make sure data collection is running.")
    st.stop()

all_data = load_all_data(days=30)

# Global date range filter
all_dates = sorted(set(d['date'] for d in all_data))
min_date = datetime.strptime(all_dates[0], '%Y-%m-%d').date()
max_date = datetime.strptime(all_dates[-1], '%Y-%m-%d').date()

date_range = st.sidebar.date_input(
    "Date range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date,
)
if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date = end_date = date_range

start_str = start_date.strftime('%Y-%m-%d')
end_str = end_date.strftime('%Y-%m-%d')

filtered_data = [d for d in all_data if start_str <= d['date'] <= end_str]

st.sidebar.info(
    f"📅 Latest data: {data['date']}\n\n"
    f"🏆 League: {data['league_name']}\n\n"
    f"📊 Week: {data['week']}"
)

# Build a week → list of day-dicts map from all loaded data
weeks_map: dict = defaultdict(list)
for _d in all_data:
    weeks_map[_d['week']].append(_d)
all_week_numbers = sorted(weeks_map.keys(), reverse=True)  # latest first
latest_week_number = data['week']

# ---------------------------------------------------------------------------
# OVERVIEW
# ---------------------------------------------------------------------------
if page == "📊 Overview":
    st.markdown('<h1 class="main-header">🏀 OpenCommish Dashboard</h1>', unsafe_allow_html=True)
    st.markdown(f"### {data['league_name']}")

    # Week selector — latest week is default
    selected_week = st.selectbox(
        "Week",
        options=all_week_numbers,
        index=0,  # latest week first
        format_func=lambda w: f"Week {w}" + (" (current)" if w == latest_week_number else ""),
        key="overview_week_select",
    )
    week_data = sorted(weeks_map[selected_week], key=lambda d: d['date'])
    df_week_teams = calculate_week_team_metrics(week_data)

    # Derive week date range
    if week_data:
        week_dates = sorted(d['date'] for d in week_data)
        week_start = week_dates[0]
        week_end = week_dates[-1]
    else:
        week_start = week_end = data['date']

    # Key metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Week", f"#{selected_week}", f"{week_start} → {week_end}")
    with col2:
        st.metric("Days collected", len(week_data))
    with col3:
        if not df_week_teams.empty:
            top_week_team = df_week_teams.loc[df_week_teams['active_points'].idxmax()]
            st.metric("Leading Team (week)", top_week_team['team_name'], f"{top_week_team['active_points']:.1f} pts")
    with col4:
        # Top NBA player this week
        if week_data:
            week_player_rows = []
            for day in week_data:
                for team in day['teams']:
                    for player in team['players']:
                        if player['roster_position'] != 'BN':
                            week_player_rows.append({
                                'name': player['name'],
                                'team': team['team_name'],
                                'fantasy_points': player['fantasy_points'],
                            })
            if week_player_rows:
                df_wp = pd.DataFrame(week_player_rows)
                df_wp_agg = df_wp.groupby(['name', 'team'])['fantasy_points'].sum().reset_index()
                top_player_row = df_wp_agg.loc[df_wp_agg['fantasy_points'].idxmax()]
                st.metric(
                    "Top Player (week)",
                    f"{top_player_row['name']} ({top_player_row['team']})",
                    f"{top_player_row['fantasy_points']:.1f} pts",
                )

    st.markdown("---")

    # Week team performance — stacked bar
    st.subheader("🏆 Week Team Performance")
    st.caption(f"Week {selected_week} cumulative totals ({len(week_data)} days)")

    if not df_week_teams.empty:
        df_week_sorted = df_week_teams.sort_values('total_points', ascending=True)
        df_stacked = df_week_sorted.set_index('team_name')[['active_points', 'bench_points']]
        st.bar_chart(df_stacked, stack=True, horizontal=True, x_label="Fantasy Points", y_label="Team")

    # Daily breakdown
    st.subheader("📅 Daily Points by Team")
    df_daily = get_week_daily_breakdown(week_data)
    if not df_daily.empty:
        df_daily_pivot = df_daily.pivot(index='date', columns='team', values='total_points').fillna(0)
        st.bar_chart(df_daily_pivot, stack=False, x_label="Date", y_label="Fantasy Points")

    # Top performers
    st.subheader("🏅 Top Performers")
    # "Today" tab shows the latest day of the selected week, not necessarily today
    latest_day_in_week = week_data[-1] if week_data else data
    perf_tab1, perf_tab2 = st.tabs([f"Latest day ({latest_day_in_week['date']})", f"Week {selected_week}"])

    with perf_tab1:
        df_today = get_all_players_multi([latest_day_in_week])
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Top 10 Players**")
            top_players = df_today[df_today['is_active']].nlargest(10, 'fantasy_points')[
                ['name', 'nba_team', 'opponent', 'team', 'roster_position', 'fantasy_points']
            ]
            st.dataframe(top_players, width="stretch", hide_index=True)
        with col2:
            st.markdown("**Top Bench Performers**")
            bench_stars = df_today[df_today['is_bench']].nlargest(10, 'fantasy_points')[
                ['name', 'nba_team', 'opponent', 'team', 'fantasy_points']
            ]
            st.dataframe(bench_stars, width="stretch", hide_index=True)

    with perf_tab2:
        df_week_players = get_all_players_multi(week_data)
        if df_week_players.empty:
            st.info("No week data available yet.")
        else:
            week_agg = (
                df_week_players.groupby(['name', 'team', 'is_bench'])['fantasy_points']
                .sum()
                .reset_index()
                .sort_values('fantasy_points', ascending=False)
            )

            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Top 10 Players (week total)**")
                top_week = week_agg[~week_agg['is_bench']].head(10)[['name', 'team', 'fantasy_points']]
                st.dataframe(top_week, width="stretch", hide_index=True)
            with col2:
                st.markdown("**Top Bench Performers (week total)**")
                bench_week = week_agg[week_agg['is_bench']].head(10)[['name', 'team', 'fantasy_points']]
                st.dataframe(bench_week, width="stretch", hide_index=True)

            st.markdown("**Per-Date Breakdown**")
            all_players_sorted = week_agg.sort_values('fantasy_points', ascending=False)['name'].unique().tolist()
            selected_player = st.selectbox("Select player", all_players_sorted, key="top_perf_player")

            player_daily = (
                df_week_players[df_week_players['name'] == selected_player]
                [['date', 'name', 'nba_team', 'opponent', 'team', 'roster_position', 'fantasy_points']]
                .sort_values('date')
            )
            st.dataframe(player_daily, width="stretch", hide_index=True)
            st.bar_chart(
                player_daily.set_index('date')[['fantasy_points']],
                x_label="Date",
                y_label="Fantasy Points",
            )

# ---------------------------------------------------------------------------
# TEAM RANKINGS
# ---------------------------------------------------------------------------
elif page == "🏆 Team Rankings":
    st.title("🏆 Team Rankings")
    st.caption(f"Data from {start_str} to {end_str}")

    df_teams = calculate_team_metrics_multi(filtered_data)
    all_team_names = sorted(df_teams['team_name'].tolist())

    selected_teams = st.multiselect(
        "Compare teams (leave empty to show all)",
        all_team_names,
        default=[],
    )

    df_display = df_teams if not selected_teams else df_teams[df_teams['team_name'].isin(selected_teams)]
    df_sorted = df_display.sort_values('active_points', ascending=False).reset_index(drop=True)
    df_sorted.index = df_sorted.index + 1

    if selected_teams and len(selected_teams) >= 2:
        st.subheader("Team Comparison")
        compare_cols = ['team_name', 'active_points', 'bench_points', 'total_points', 'bench_percentage']
        st.dataframe(df_sorted[compare_cols], width="stretch", hide_index=True)
        comparison_pivot = df_sorted.set_index('team_name')[['active_points', 'bench_points']]
        st.bar_chart(comparison_pivot, stack=False, x_label="Team", y_label="Fantasy Points")
        st.markdown("---")

    for idx, row in df_sorted.iterrows():
        with st.container():
            col1, col2, col3, col4 = st.columns([1, 3, 2, 2])
            with col1:
                if idx == 1:
                    st.markdown("🥇")
                elif idx == 2:
                    st.markdown("🥈")
                elif idx == 3:
                    st.markdown("🥉")
                else:
                    st.markdown(f"**#{idx}**")
            with col2:
                st.markdown(f"### {row['team_name']}")
                best_active = row.get('worst_active_player', '—')
                best_bench = row.get('best_bench_player', '—')
                st.markdown(f"Worst active: {best_active} | Best bench: {best_bench}")
            with col3:
                st.metric("Active Points", f"{row['active_points']:.2f}")
            with col4:
                st.metric(
                    "Bench Points",
                    f"{row['bench_points']:.2f}",
                    f"{row['bench_percentage']:.1f}% of total",
                )
            st.markdown("---")

    st.subheader("Detailed Team Statistics")
    display_cols = ['team_name', 'active_points', 'bench_points', 'total_points', 'bench_percentage']
    st.dataframe(df_sorted[display_cols], width="stretch")

# ---------------------------------------------------------------------------
# PLAYER ANALYSIS
# ---------------------------------------------------------------------------
elif page == "⭐ Player Analysis":
    st.title("⭐ Player Analysis")

    df_all_players = get_all_players_multi(filtered_data)

    REAL_POSITIONS = ['PG', 'SG', 'SF', 'PF', 'C', 'G', 'F']

    available_dates = sorted(df_all_players['date'].unique(), reverse=True)
    all_team_names = sorted(df_all_players['team'].unique())

    col1, col2, col3 = st.columns(3)
    with col1:
        date_options = ["All Dates"] + available_dates
        selected_date = st.selectbox("Filter by Date", date_options)
    with col2:
        selected_team = st.multiselect("Filter by Team", all_team_names, default=[])
    with col3:
        position_filter = st.multiselect(
            "Filter by Position",
            REAL_POSITIONS,
            default=REAL_POSITIONS,
        )

    # Date filter
    if selected_date == "All Dates":
        filtered_players = (
            df_all_players.groupby(['name', 'team', 'roster_position', 'is_bench', 'is_active'])['fantasy_points']
            .sum()
            .reset_index()
            .assign(nba_team='', opponent='', date='All Dates')
        )
    else:
        filtered_players = df_all_players[df_all_players['date'] == selected_date].copy()

    # Team filter
    if selected_team:
        filtered_players = filtered_players[filtered_players['team'].isin(selected_team)]

    # Position filter — apply only to real positions, keep rows that match
    filtered_players = filtered_players[filtered_players['roster_position'].isin(position_filter)]

    date_label = selected_date if selected_date != "All Dates" else f"Last {len(all_data)} Days"

    # Top performers overall
    st.subheader(f"Top Performers — {date_label}")
    top_20 = filtered_players.nlargest(20, 'fantasy_points')
    if not top_20.empty:
        st.bar_chart(
            top_20.set_index('name')[['fantasy_points']],
            horizontal=True,
            x_label="Fantasy Points",
        )

    # Top 20 per position
    st.subheader("Top 20 Per Position")
    for pos in REAL_POSITIONS:
        pos_df = filtered_players[filtered_players['roster_position'] == pos]
        if pos_df.empty:
            continue
        top_pos = pos_df.nlargest(20, 'fantasy_points')
        with st.expander(f"{pos} — Top {len(top_pos)}"):
            st.bar_chart(
                top_pos.set_index('name')[['fantasy_points']],
                horizontal=True,
                x_label="Fantasy Points",
            )

    # Position breakdown
    st.subheader("Points by Position")
    position_stats = filtered_players.groupby('roster_position').agg(
        Total_Points=('fantasy_points', 'sum'),
        Avg_Points=('fantasy_points', 'mean'),
        Count=('fantasy_points', 'count'),
    ).reset_index().rename(columns={'roster_position': 'Position'})

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Total Points by Position**")
        st.bar_chart(
            position_stats.set_index('Position')[['Total_Points']],
            horizontal=True,
            x_label="Total Points",
        )
    with col2:
        st.markdown("**Average Points by Position**")
        st.bar_chart(
            position_stats.set_index('Position')[['Avg_Points']],
            x_label="Position",
            y_label="Avg Points",
        )

    # Team breakdown
    st.subheader("Points by Fantasy Team")
    team_breakdown = (
        filtered_players.groupby('team')['fantasy_points']
        .sum()
        .reset_index()
        .sort_values('fantasy_points', ascending=False)
    )
    st.bar_chart(team_breakdown.set_index('team')[['fantasy_points']], x_label="Team", y_label="Total Points")

    # Full table
    st.subheader("All Players")
    show_cols = ['date', 'name', 'team', 'roster_position', 'fantasy_points']
    if 'nba_team' in filtered_players.columns:
        show_cols = ['date', 'name', 'nba_team', 'opponent', 'team', 'roster_position', 'fantasy_points']
    st.dataframe(
        filtered_players[show_cols].sort_values('fantasy_points', ascending=False),
        width="stretch",
        hide_index=True,
    )

# ---------------------------------------------------------------------------
# TRENDS
# ---------------------------------------------------------------------------
elif page == "📈 Trends":
    st.title("📈 Performance Trends")

    df_trends = get_trend_data(filtered_data)

    if len(filtered_data) < 2:
        st.warning("Not enough data for trend analysis. Expand the date range.")
    else:
        st.markdown(f"Showing trends over **{len(filtered_data)}** days ({start_str} → {end_str})")

        all_team_names = sorted(df_trends['team'].unique())
        all_player_names = sorted(
            get_all_players_multi(filtered_data)
            .query("is_active")['name']
            .unique()
            .tolist()
        )

        col_f1, col_f2 = st.columns(2)
        with col_f1:
            selected_teams = st.multiselect("Filter teams", all_team_names, default=all_team_names)
        with col_f2:
            player_overlay = st.selectbox("Overlay NBA player (optional)", ["None"] + all_player_names)

        df_filtered_trends = df_trends[df_trends['team'].isin(selected_teams)]

        # Active points line chart
        st.subheader("Team Active Points Over Time")
        if not df_filtered_trends.empty:
            active_pivot = df_filtered_trends.pivot(
                index='date', columns='team', values='active_points'
            ).fillna(0)

            if player_overlay != "None":
                df_player_trend = (
                    get_all_players_multi(filtered_data)
                    .query("name == @player_overlay and is_active")
                    .groupby('date')['fantasy_points']
                    .sum()
                    .reset_index()
                    .set_index('date')
                    .rename(columns={'fantasy_points': player_overlay})
                )
                active_pivot = active_pivot.join(df_player_trend, how='left')

            st.line_chart(active_pivot, x_label="Date", y_label="Active Points")

        # Last 5 games summary
        st.subheader("Last 5 Games")
        last_5_dates = sorted(df_filtered_trends['date'].unique())[-5:]
        df_last5 = df_filtered_trends[df_filtered_trends['date'].isin(last_5_dates)]
        if not df_last5.empty:
            last5_pivot = df_last5.pivot(
                index='date', columns='team', values='active_points'
            ).fillna(0).reset_index()
            st.dataframe(last5_pivot, width="stretch", hide_index=True)

        # N-day summary
        st.subheader(f"Last 7 Days Summary")
        last_date = max(d['date'] for d in filtered_data)
        cutoff = (datetime.strptime(last_date, '%Y-%m-%d') - timedelta(days=7)).strftime('%Y-%m-%d')
        recent_data = df_filtered_trends[df_filtered_trends['date'] >= cutoff]

        if not recent_data.empty:
            summary = recent_data.groupby('team').agg(
                Average=('active_points', 'mean'),
                Min=('active_points', 'min'),
                Max=('active_points', 'max'),
                Std_Dev=('active_points', 'std'),
            ).reset_index().rename(columns={'team': 'Team'})
            summary = summary.sort_values('Average', ascending=False)
            st.dataframe(summary.round(2), width="stretch", hide_index=True)
            st.bar_chart(
                summary.set_index('Team')[['Average']],
                x_label="Team",
                y_label="Avg Active Points",
            )

        # Bench efficiency trend
        st.subheader("Bench Efficiency Over Time")
        df_filtered_trends = df_filtered_trends.copy()
        df_filtered_trends['bench_pct'] = (
            df_filtered_trends['bench_points'] / df_filtered_trends['total_points'] * 100
        ).fillna(0)
        bench_pivot = df_filtered_trends.pivot(
            index='date', columns='team', values='bench_pct'
        ).fillna(0)
        st.line_chart(bench_pivot, x_label="Date", y_label="Bench %")

# ---------------------------------------------------------------------------
# BENCH EFFICIENCY
# ---------------------------------------------------------------------------
elif page == "💔 Bench Efficiency":
    st.title("💔 Bench Efficiency Analysis")
    st.markdown("Identify missed opportunities and points left on the bench.")
    st.caption(f"Data from {start_str} to {end_str}")

    df_teams = calculate_team_metrics_multi(filtered_data)
    df_all_players = get_all_players_multi(filtered_data)

    all_team_names = sorted(df_teams['team_name'].tolist())
    selected_teams = st.multiselect("Filter teams", all_team_names, default=all_team_names)

    df_teams = df_teams[df_teams['team_name'].isin(selected_teams)]
    df_all_players = df_all_players[df_all_players['team'].isin(selected_teams)]

    # Bench efficiency ranking
    st.subheader("Team Bench Efficiency Rankings")
    df_efficiency = df_teams.sort_values('bench_percentage', ascending=True)
    st.bar_chart(
        df_efficiency.set_index('team_name')[['bench_percentage']],
        x_label="Team",
        y_label="Bench %",
    )

    # Missed opportunities
    st.subheader("🚨 Missed Opportunities")
    missed_opportunities = []
    for _, team in df_teams.iterrows():
        if team['best_bench_points'] > team['worst_active_points']:
            diff = team['best_bench_points'] - team['worst_active_points']
            missed_opportunities.append({
                'team': team['team_name'],
                'bench_star': team['best_bench_player'],
                'bench_points': team['best_bench_points'],
                'active_underperformer': team['worst_active_player'],
                'active_points': team['worst_active_points'],
                'missed_points': diff,
            })

    if missed_opportunities:
        df_missed = pd.DataFrame(missed_opportunities).sort_values('missed_points', ascending=False)
        for _, opp in df_missed.iterrows():
            with st.container():
                st.error(f"### {opp['team']}")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Should've Started", opp['bench_star'], f"{opp['bench_points']:.2f} pts")
                with col2:
                    st.metric("Instead of", opp['active_underperformer'], f"{opp['active_points']:.2f} pts")
                with col3:
                    st.metric("Missed Points", f"{opp['missed_points']:.2f}")
                st.markdown("---")
    else:
        st.success("✅ No major missed opportunities in the selected period!")

    # Best bench players
    st.subheader("⭐ Best Bench Players (League-Wide)")
    bench_players = (
        df_all_players[df_all_players['is_bench']]
        .sort_values('fantasy_points', ascending=False)
        .head(15)
    )
    if not bench_players.empty:
        st.bar_chart(
            bench_players.set_index('name')[['fantasy_points']],
            horizontal=True,
            x_label="Fantasy Points",
        )

    # Team-by-team breakdown
    st.subheader("Team-by-Team Breakdown")
    for _, team in df_teams.iterrows():
        team_players = df_all_players[df_all_players['team'] == team['team_name']].sort_values(
            'fantasy_points', ascending=False
        )
        with st.expander(
            f"📊 {team['team_name']} — Bench: {team['bench_points']:.1f} pts ({team['bench_percentage']:.1f}%)"
        ):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Active Roster**")
                active = team_players[team_players['is_active']][
                    ['date', 'name', 'nba_team', 'opponent', 'roster_position', 'fantasy_points']
                ]
                st.dataframe(active, hide_index=True)
            with col2:
                st.markdown("**Bench**")
                bench = team_players[team_players['is_bench']][
                    ['date', 'name', 'nba_team', 'opponent', 'roster_position', 'fantasy_points']
                ]
                st.dataframe(bench, hide_index=True)

# ---------------------------------------------------------------------------
# PROJECTED STATS COMPARISON
# ---------------------------------------------------------------------------
elif page == "📉 Projected Stats":
    st.title("📉 Projected Stats Comparison")
    st.markdown("Compare projected vs actual fantasy points per team and player.")
    st.caption(f"Data from {start_str} to {end_str}")

    proj_data = load_projected_data(days=30)
    proj_filtered = [d for d in proj_data if start_str <= d['date'] <= end_str]

    df_comp = build_comparison_df(filtered_data, proj_filtered)

    if df_comp.empty:
        st.warning("No matching projected/actual data for the selected date range.")
        st.stop()

    # Filters
    all_teams = sorted(df_comp['team'].unique())
    all_players = sorted(df_comp['player'].unique())

    col1, col2, col3 = st.columns(3)
    with col1:
        sel_teams = st.multiselect("Filter by Team", all_teams, default=[])
    with col2:
        player_search = st.multiselect("Filter by Player", all_players, default=[])
    with col3:
        show_bench = st.checkbox("Include bench players", value=False)

    df_view = df_comp.copy()
    if not show_bench:
        df_view = df_view[df_view['roster_position'] != 'BN']
    if sel_teams:
        df_view = df_view[df_view['team'].isin(sel_teams)]
    if player_search:
        df_view = df_view[df_view['player'].isin(player_search)]

    # Per-team grouped bar: projected vs actual
    st.subheader("Projected vs Actual by Team")
    team_agg = (
        df_view.groupby('team')[['projected_points', 'actual_points']]
        .sum()
        .reset_index()
        .sort_values('actual_points', ascending=False)
    )
    if not team_agg.empty:
        st.bar_chart(
            team_agg.set_index('team')[['projected_points', 'actual_points']],
            stack=False,
            x_label="Team",
            y_label="Fantasy Points",
        )

    # Per-team delta
    st.subheader("Performance vs Projection (Actual − Projected) by Team")
    team_delta = team_agg.copy()
    team_delta['delta'] = team_delta['actual_points'] - team_delta['projected_points']
    st.bar_chart(
        team_delta.set_index('team')[['delta']],
        x_label="Team",
        y_label="Delta (Actual − Projected)",
    )

    # Per-player scatter (projected x, actual y) — approximated with a table + bar
    st.subheader("Top Overperformers & Underperformers")
    player_agg = (
        df_view.groupby(['player', 'team'])[['projected_points', 'actual_points', 'delta']]
        .sum()
        .reset_index()
    )
    player_agg['delta_%'] = (
        (player_agg['delta'] / player_agg['projected_points'].replace(0, float('nan'))) * 100
    ).round(1)

    top_over = player_agg.nlargest(20, 'delta')
    top_under = player_agg.nsmallest(20, 'delta')

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Top Overperformers (actual > projected)**")
        if not top_over.empty:
            st.bar_chart(
                top_over.set_index('player')[['delta']],
                horizontal=True,
                x_label="Delta (pts)",
            )
    with col2:
        st.markdown("**Top Underperformers (actual < projected)**")
        if not top_under.empty:
            st.bar_chart(
                top_under.set_index('player')[['delta']],
                horizontal=True,
                x_label="Delta (pts)",
            )

    # Scatter approximation: projected vs actual table with visual cue
    st.subheader("Projected vs Actual Scatter (sorted by projected)")
    scatter_df = player_agg.sort_values('projected_points', ascending=False)
    st.dataframe(
        scatter_df[['player', 'team', 'projected_points', 'actual_points', 'delta', 'delta_%']].round(2),
        width="stretch",
        hide_index=True,
    )

    # Full detail table
    st.subheader("Per-Player Per-Date Detail")
    detail_cols = ['date', 'player', 'team', 'roster_position', 'projected_points', 'actual_points', 'delta', 'delta_%']
    st.dataframe(
        df_view[detail_cols].sort_values(['date', 'delta'], ascending=[False, True]).round(2),
        width="stretch",
        hide_index=True,
    )

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.sidebar.markdown("---")
st.sidebar.markdown("Made with 🏀 by OpenCommish")
