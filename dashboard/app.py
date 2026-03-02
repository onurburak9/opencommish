import streamlit as st
import json
import glob
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
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

# Data loading functions
@st.cache_data(ttl=300)
def load_latest_data():
    """Load the most recent day's data."""
    data_dir = PROJECT_ROOT / "data/daily_stats"
    stats_files = sorted(data_dir.glob("league_*.json"))
    if not stats_files:
        return None

    latest_file = stats_files[-1]
    with open(latest_file) as f:
        return json.load(f)

@st.cache_data(ttl=300)
def load_all_data(days=30):
    """Load last N days of data."""
    data_dir = PROJECT_ROOT / "data/daily_stats"
    stats_files = sorted(data_dir.glob("league_*.json"))[-days:]

    all_data = []
    for stats_file in stats_files:
        with open(stats_file) as f:
            data = json.load(f)
            all_data.append(data)
    return all_data

@st.cache_data(ttl=300)
def load_opponent_lookup(days=30):
    """Return {(player_name, date): opponent_abbr} from projected stats files.

    The projected stats HTML scraper captures the NBA opponent for each player
    on each day. The Yahoo API itself doesn't expose opponent in its roster
    endpoint, so this is the reliable source for that field.
    """
    data_dir = PROJECT_ROOT / "data/projected_stats"
    files = sorted(data_dir.glob("league_*.json"))[-days:]
    lookup = {}
    for f in files:
        with open(f) as fh:
            data = json.load(fh)
        date_str = data['date']
        for team in data['teams']:
            for p in team['players']:
                lookup[(p['player_name'], date_str)] = p.get('opponent', '')
    return lookup

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
            data = json.load(f)
        if data['week'] == current_week:
            week_data.append(data)
    return week_data

def calculate_week_team_metrics(week_data):
    """Aggregate active/bench points per team across all days in a week."""
    from collections import defaultdict
    team_active = defaultdict(float)
    team_bench = defaultdict(float)
    team_meta = {}

    for day in week_data:
        for team in day['teams']:
            name = team['team_name']
            team_meta[name] = {'team_id': team['team_id']}
            for p in team['players']:
                if p['roster_position'] == 'BN':
                    if p['fantasy_points'] != 0:
                        print(day['date'])
                        print(name)
                        print(p['name'])
                        print(p['fantasy_points'])
                        print(p['roster_position'])
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

def calculate_team_metrics(data):
    """Calculate metrics for all teams."""
    teams = []
    for team in data['teams']:
        total_points = sum(p['fantasy_points'] for p in team['players'])
        active_players = [p for p in team['players'] if p['roster_position'] != 'BN']
        bench_players = [p for p in team['players'] if p['roster_position'] == 'BN']

        active_points = sum(p['fantasy_points'] for p in active_players)
        bench_points = sum(p['fantasy_points'] for p in bench_players)

        # Find best bench and worst active
        best_bench = max(bench_players, key=lambda x: x['fantasy_points']) if bench_players else None
        worst_active = min(active_players, key=lambda x: x['fantasy_points']) if active_players else None

        teams.append({
            'team_name': team['team_name'],
            'team_id': team['team_id'],
            'total_players': len(team['players']),
            'active_players': len(active_players),
            'bench_players': len(bench_players),
            'total_points': total_points,
            'active_points': active_points,
            'bench_points': bench_points,
            'bench_percentage': (bench_points / total_points * 100) if total_points > 0 else 0,
            'best_bench_player': best_bench['name'] if best_bench else None,
            'best_bench_points': best_bench['fantasy_points'] if best_bench else 0,
            'worst_active_player': worst_active['name'] if worst_active else None,
            'worst_active_points': worst_active['fantasy_points'] if worst_active else 0,
        })
    return pd.DataFrame(teams)

def get_all_players(data):
    """Get all players from all teams."""
    players = []
    for team in data['teams']:
        for player in team['players']:
            player_info = {
                'name': player['name'],
                'team': team['team_name'],
                'team_id': team['team_id'],
                'roster_position': player['roster_position'],
                'fantasy_points': player['fantasy_points'],
                'is_bench': player['roster_position'] == 'BN',
                'is_active': player['roster_position'] != 'BN'
            }
            # Add individual stats if available
            if player.get('stats'):
                for stat in player['stats']:
                    player_info[stat['display_name']] = stat['value']
            players.append(player_info)
    return pd.DataFrame(players)

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
                'total_points': active_points + bench_points
            })
    return pd.DataFrame(trend_data)

# Sidebar
st.sidebar.image("https://upload.wikimedia.org/wikipedia/commons/thumb/7/7a/Basketball.png/220px-Basketball.png", width=100)
st.sidebar.title("🏀 OpenCommish")
st.sidebar.markdown("---")

# Navigation
page = st.sidebar.radio("Navigation", [
    "📊 Overview",
    "🏆 Team Rankings",
    "⭐ Player Analysis",
    "📈 Trends",
    "💔 Bench Efficiency"
])

st.sidebar.markdown("---")

# Load data
data = load_latest_data()
if data is None:
    st.error("❌ No data found! Make sure data collection is running.")
    st.stop()

# Sidebar info
st.sidebar.info(f"📅 Data Date: {data['date']}\n\n🏆 League: {data['league_name']}\n\n📊 Week: {data['week']}")

# Calculate metrics
df_teams = calculate_team_metrics(data)
df_players = get_all_players(data)
all_data = load_all_data(days=14)
df_trends = get_trend_data(all_data)
week_data = load_current_week_data()
df_week_teams = calculate_week_team_metrics(week_data)

# MAIN CONTENT
if page == "📊 Overview":
    st.markdown('<h1 class="main-header">🏀 OpenCommish Dashboard</h1>', unsafe_allow_html=True)
    st.markdown(f"### {data['league_name']} - Week {data['week']}")

    # Key metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Teams", len(data['teams']))
    with col2:
        total_players = sum(len(t['players']) for t in data['teams'])
        st.metric("Total Players", total_players)
    with col3:
        top_team = df_teams.loc[df_teams['active_points'].idxmax()]
        st.metric("Leading Team", top_team['team_name'], f"{top_team['active_points']:.1f} pts")
    with col4:
        top_player = df_players.loc[df_players['fantasy_points'].idxmax()]
        st.metric("Top Player", top_player['name'], f"{top_player['fantasy_points']:.1f} pts")

    st.markdown("---")

    # Team performance chart
    st.subheader("🏆 Team Performance Overview")
    st.caption(f"Week {data['week']} cumulative totals ({len(week_data)} days collected so far)")

    df_week_sorted = df_week_teams.sort_values('total_points', ascending=True)
    fig = go.Figure()

    fig.add_trace(go.Bar(
        name='Active Points',
        y=df_week_sorted['team_name'],
        x=df_week_sorted['active_points'],
        orientation='h',
        marker_color='steelblue',
        text=df_week_sorted['active_points'].round(1),
        textposition='inside',
    ))

    fig.add_trace(go.Bar(
        name='Bench Points',
        y=df_week_sorted['team_name'],
        x=df_week_sorted['bench_points'],
        orientation='h',
        marker_color='coral',
        text=df_week_sorted['bench_points'].apply(lambda v: f'+{v:.1f}' if v > 0 else ''),
        textposition='inside',
    ))

    # Annotate total at the end of each stacked bar
    for _, row in df_week_sorted.iterrows():
        fig.add_annotation(
            y=row['team_name'],
            x=row['total_points'],
            text=f"  <b>{row['total_points']:.1f}</b>",
            showarrow=False,
            xanchor='left',
            font=dict(size=12),
        )

    fig.update_layout(
        barmode='stack',
        title=f'Week {data["week"]} Total Fantasy Points by Team (Active + Bench)',
        xaxis_title='Fantasy Points',
        yaxis_title='Team',
        height=400
    )

    st.plotly_chart(fig, use_container_width=True)

    # Per-day breakdown
    st.subheader("📅 Daily Points by Team")
    df_daily = get_week_daily_breakdown(week_data)
    if not df_daily.empty:
        fig2 = px.bar(
            df_daily,
            x='date',
            y='total_points',
            color='team',
            barmode='group',
            text_auto='.1f',
            title=f'Week {data["week"]} — Points Per Day Per Team',
            labels={'total_points': 'Fantasy Points', 'date': 'Date', 'team': 'Team'},
            height=400,
        )
        st.plotly_chart(fig2, use_container_width=True)

    # Top performers
    st.subheader("🏅 Top Performers")
    perf_tab1, perf_tab2 = st.tabs([f"Today ({data['date']})", f"Week {data['week']} (all days)"])

    with perf_tab1:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Top 10 Players**")
            top_players = df_players.nlargest(10, 'fantasy_points')[['name', 'team', 'roster_position', 'fantasy_points']]
            st.dataframe(top_players, use_container_width=True, hide_index=True)
        with col2:
            st.markdown("**Top Bench Performers**")
            bench_stars = df_players[df_players['is_bench']].nlargest(10, 'fantasy_points')[['name', 'team', 'fantasy_points']]
            st.dataframe(bench_stars, use_container_width=True, hide_index=True)

    with perf_tab2:
        # Build per-player, per-date data from week_data
        week_player_rows = []
        for day in week_data:
            for team in day['teams']:
                for player in team['players']:
                    week_player_rows.append({
                        'date': day['date'],
                        'name': player['name'],
                        'team': team['team_name'],
                        'roster_position': player['roster_position'],
                        'fantasy_points': player['fantasy_points'],
                        'is_bench': player['roster_position'] == 'BN',
                    })
        df_week_players = pd.DataFrame(week_player_rows)

        if df_week_players.empty:
            st.info("No week data available yet.")
        else:
            # Aggregated week totals
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
                st.dataframe(top_week, use_container_width=True, hide_index=True)
            with col2:
                st.markdown("**Top Bench Performers (week total)**")
                bench_week = week_agg[week_agg['is_bench']].head(10)[['name', 'team', 'fantasy_points']]
                st.dataframe(bench_week, use_container_width=True, hide_index=True)

            # Per-date breakdown for selected player
            st.markdown("**Per-Date Breakdown**")
            all_players_sorted = week_agg.sort_values('fantasy_points', ascending=False)['name'].unique().tolist()
            selected_player = st.selectbox("Select player", all_players_sorted, key="top_perf_player")

            player_daily = (
                df_week_players[df_week_players['name'] == selected_player]
                [['date', 'name', 'team', 'roster_position', 'fantasy_points']]
                .sort_values('date')
            )
            st.dataframe(player_daily, use_container_width=True, hide_index=True)

            fig_p = px.bar(
                player_daily,
                x='date',
                y='fantasy_points',
                text_auto='.1f',
                title=f"{selected_player} — Points Per Day (Week {data['week']})",
                labels={'fantasy_points': 'Fantasy Points', 'date': 'Date'},
                color='roster_position',
            )
            st.plotly_chart(fig_p, use_container_width=True)

elif page == "🏆 Team Rankings":
    st.title("🏆 Team Rankings")

    # Sort teams by active points
    df_sorted = df_teams.sort_values('active_points', ascending=False).reset_index(drop=True)
    df_sorted.index = df_sorted.index + 1  # Start ranking at 1

    # Display teams
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
                st.markdown(f"Active: {row['active_players']} | Bench: {row['bench_players']}")

            with col3:
                st.metric("Active Points", f"{row['active_points']:.2f}")

            with col4:
                st.metric("Bench Points", f"{row['bench_points']:.2f}",
                         f"{row['bench_percentage']:.1f}% of total")

            st.markdown("---")

    # Detailed stats
    st.subheader("Detailed Team Statistics")
    display_cols = ['team_name', 'active_points', 'bench_points', 'total_points', 'bench_percentage']
    st.dataframe(df_sorted[display_cols], use_container_width=True)

elif page == "⭐ Player Analysis":
    st.title("⭐ Player Analysis")

    # Build multi-day player dataset from all loaded data
    all_player_rows = []
    for day_data in all_data:
        for team in day_data['teams']:
            for player in team['players']:
                all_player_rows.append({
                    'date': day_data['date'],
                    'name': player['name'],
                    'team': team['team_name'],
                    'roster_position': player['roster_position'],
                    'fantasy_points': player['fantasy_points'],
                    'is_bench': player['roster_position'] == 'BN',
                    'is_active': player['roster_position'] != 'BN',
                })
    df_all_players = pd.DataFrame(all_player_rows)

    available_dates = sorted(df_all_players['date'].unique(), reverse=True)

    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        date_options = ["All Dates"] + available_dates
        selected_date = st.selectbox("Filter by Date", date_options)
    with col2:
        selected_team = st.selectbox("Filter by Team", ["All Teams"] + list(df_teams['team_name'].unique()))
    with col3:
        all_positions = df_all_players['roster_position'].unique().tolist()
        position_filter = st.multiselect("Filter by Position", all_positions, default=all_positions)

    # Filter data
    if selected_date == "All Dates":
        # Aggregate across all dates
        filtered_players = (
            df_all_players.groupby(['name', 'team', 'roster_position', 'is_bench', 'is_active'])['fantasy_points']
            .sum()
            .reset_index()
        )
    else:
        filtered_players = df_all_players[df_all_players['date'] == selected_date].drop(columns='date').copy()

    if selected_team != "All Teams":
        filtered_players = filtered_players[filtered_players['team'] == selected_team]
    filtered_players = filtered_players[filtered_players['roster_position'].isin(position_filter)]

    # Top performers chart
    date_label = selected_date if selected_date != "All Dates" else f"Last {len(all_data)} Days"
    st.subheader(f"Top Performers — {date_label}")
    top_20 = filtered_players.nlargest(20, 'fantasy_points')

    fig = px.bar(top_20,
                 x='fantasy_points',
                 y='name',
                 color='team',
                 orientation='h',
                 text_auto='.1f',
                 title=f'Top 20 Players by Fantasy Points ({date_label})',
                 labels={'fantasy_points': 'Fantasy Points', 'name': 'Player'})
    fig.update_layout(height=600)
    st.plotly_chart(fig, use_container_width=True)

    # Position breakdown
    st.subheader("Points by Position")
    position_stats = filtered_players.groupby('roster_position').agg({
        'fantasy_points': ['mean', 'sum', 'count']
    }).reset_index()
    position_stats.columns = ['Position', 'Avg Points', 'Total Points', 'Player Count']

    col1, col2 = st.columns(2)

    with col1:
        fig = px.pie(position_stats, values='Total Points', names='Position',
                     title='Total Points Distribution by Position')
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = px.bar(position_stats, x='Position', y='Avg Points',
                     text_auto='.1f',
                     title='Average Points per Position',
                     color='Position')
        st.plotly_chart(fig, use_container_width=True)

    # Full player table
    st.subheader("All Players")
    st.dataframe(filtered_players.sort_values('fantasy_points', ascending=False),
                 use_container_width=True, hide_index=True)

elif page == "📈 Trends":
    st.title("📈 Performance Trends")

    if len(all_data) < 2:
        st.warning("Not enough historical data for trend analysis. Need at least 2 days.")
    else:
        st.markdown(f"Showing trends over **{len(all_data)}** days")

        # Team trends
        st.subheader("Team Performance Over Time")

        fig = px.line(df_trends,
                      x='date',
                      y='active_points',
                      color='team',
                      title='Active Points by Team (Last 14 Days)',
                      markers=True)
        fig.update_layout(height=500)
        st.plotly_chart(fig, use_container_width=True)

        # 7-day averages
        st.subheader("7-Day Performance Summary")

        # Get last 7 days
        recent_data = df_trends[df_trends['date'] >= (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')]

        if not recent_data.empty:
            summary = recent_data.groupby('team').agg({
                'active_points': ['mean', 'min', 'max', 'std']
            }).reset_index()
            summary.columns = ['Team', 'Average', 'Min', 'Max', 'Std Dev']
            summary = summary.sort_values('Average', ascending=False)

            st.dataframe(summary.round(2), use_container_width=True, hide_index=True)

            # Consistency chart
            fig = px.bar(summary, x='Team', y='Average',
                         error_y='Std Dev',
                         text_auto='.1f',
                         title='7-Day Average with Variance',
                         color='Average',
                         color_continuous_scale='Viridis')
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)

        # Bench efficiency trends
        st.subheader("Bench Efficiency Trends")
        df_trends['bench_pct'] = (df_trends['bench_points'] / df_trends['total_points'] * 100).fillna(0)

        fig = px.line(df_trends,
                      x='date',
                      y='bench_pct',
                      color='team',
                      title='Bench Points % Over Time (Lower is Better)',
                      markers=True)
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)

elif page == "💔 Bench Efficiency":
    st.title("💔 Bench Efficiency Analysis")
    st.markdown("Identify missed opportunities and points left on the bench.")

    # Calculate bench efficiency metrics
    st.subheader("Team Bench Efficiency Rankings")

    # Sort by bench percentage (ascending - lower is better)
    df_efficiency = df_teams.sort_values('bench_percentage', ascending=True)

    fig = px.bar(df_efficiency,
                 x='team_name',
                 y='bench_percentage',
                 text_auto='.1f',
                 title='Bench Points % by Team (Lower = Better)',
                 color='bench_percentage',
                 color_continuous_scale='RdYlGn_r')
    fig.update_layout(height=400)
    st.plotly_chart(fig, use_container_width=True)

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
                'missed_points': diff
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
        st.success("✅ No major missed opportunities today! All teams optimized their lineups.")

    # Best bench players across all teams
    st.subheader("⭐ Best Bench Players (League-Wide)")

    bench_players = df_players[df_players['is_bench']].sort_values('fantasy_points', ascending=False).head(15)

    fig = px.bar(bench_players,
                 x='fantasy_points',
                 y='name',
                 color='team',
                 orientation='h',
                 text_auto='.1f',
                 title='Top 15 Bench Performers (Could Have Helped!)',
                 labels={'fantasy_points': 'Fantasy Points', 'name': 'Player'})
    fig.update_layout(height=500)
    st.plotly_chart(fig, use_container_width=True)

    # Team-by-team breakdown
    st.subheader("Team-by-Team Breakdown")

    for _, team in df_teams.iterrows():
        with st.expander(f"📊 {team['team_name']} - Bench: {team['bench_points']:.1f} pts ({team['bench_percentage']:.1f}%)"):
            # Get players for this team
            team_players = df_players[df_players['team'] == team['team_name']].sort_values('fantasy_points', ascending=False)

            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**Active Roster**")
                active = team_players[team_players['is_active']][['name', 'roster_position', 'fantasy_points']]
                st.dataframe(active, hide_index=True)

            with col2:
                st.markdown("**Bench**")
                bench = team_players[team_players['is_bench']][['name', 'roster_position', 'fantasy_points']]
                st.dataframe(bench, hide_index=True)

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("Made with 🏀 by OpenCommish")
