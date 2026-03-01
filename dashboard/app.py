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

# Data loading functions
@st.cache_data(ttl=300)
def load_latest_data():
    """Load the most recent day's data."""
    data_dir = Path("data/daily_stats")
    stats_files = sorted(data_dir.glob("league_*.json"))
    if not stats_files:
        return None
    
    latest_file = stats_files[-1]
    with open(latest_file) as f:
        return json.load(f)

@st.cache_data(ttl=300)
def load_all_data(days=30):
    """Load last N days of data."""
    data_dir = Path("data/daily_stats")
    stats_files = sorted(data_dir.glob("league_*.json"))[-days:]
    
    all_data = []
    for stats_file in stats_files:
        with open(stats_file) as f:
            data = json.load(f)
            all_data.append(data)
    return all_data

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
    
    fig = go.Figure()
    
    # Active points
    fig.add_trace(go.Bar(
        name='Active Points',
        y=df_teams.sort_values('active_points', ascending=True)['team_name'],
        x=df_teams.sort_values('active_points', ascending=True)['active_points'],
        orientation='h',
        marker_color='steelblue'
    ))
    
    # Bench points
    fig.add_trace(go.Bar(
        name='Bench Points (Lost)',
        y=df_teams.sort_values('active_points', ascending=True)['team_name'],
        x=df_teams.sort_values('active_points', ascending=True)['bench_points'],
        orientation='h',
        marker_color='coral'
    ))
    
    fig.update_layout(
        barmode='stack',
        title='Total Fantasy Points by Team (Active vs Bench)',
        xaxis_title='Fantasy Points',
        yaxis_title='Team',
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Top performers
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🏅 Top 10 Players")
        top_players = df_players.nlargest(10, 'fantasy_points')[['name', 'team', 'roster_position', 'fantasy_points']]
        st.dataframe(top_players, use_container_width=True, hide_index=True)
    
    with col2:
        st.subheader("💔 Top Bench Performers")
        bench_stars = df_players[df_players['is_bench']].nlargest(10, 'fantasy_points')[['name', 'team', 'fantasy_points']]
        st.dataframe(bench_stars, use_container_width=True, hide_index=True)

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
    
    # Filters
    col1, col2 = st.columns(2)
    with col1:
        selected_team = st.selectbox("Filter by Team", ["All Teams"] + list(df_teams['team_name'].unique()))
    with col2:
        position_filter = st.multiselect("Filter by Position", 
                                        df_players['roster_position'].unique().tolist(),
                                        default=df_players['roster_position'].unique().tolist())
    
    # Filter data
    filtered_players = df_players.copy()
    if selected_team != "All Teams":
        filtered_players = filtered_players[filtered_players['team'] == selected_team]
    filtered_players = filtered_players[filtered_players['roster_position'].isin(position_filter)]
    
    # Top performers chart
    st.subheader("Top Performers")
    top_20 = filtered_players.nlargest(20, 'fantasy_points')
    
    fig = px.bar(top_20, 
                 x='fantasy_points', 
                 y='name',
                 color='team',
                 orientation='h',
                 title='Top 20 Players by Fantasy Points',
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
