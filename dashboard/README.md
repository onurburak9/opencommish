# 🏀 OpenCommish Dashboard

A beautiful Streamlit dashboard for analyzing Yahoo NBA Fantasy Basketball data.

## 🚀 Quick Start

```bash
# 1. Navigate to dashboard directory
cd dashboard

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the dashboard
streamlit run app.py
```

The dashboard will open in your browser at `http://localhost:8501`

## 📊 Features

### 📈 Overview
- Key metrics at a glance
- Team performance comparison
- Top players and bench performers

### 🏆 Team Rankings
- Ranked team standings
- Active vs bench points breakdown
- Detailed statistics table

### ⭐ Player Analysis
- Filter by team and position
- Top performers visualization
- Position breakdown analysis

### 📈 Trends
- 14-day performance tracking
- 7-day rolling averages
- Bench efficiency over time

### 💔 Bench Efficiency
- Identify missed opportunities
- Best bench performers
- Team-by-team lineup analysis

## 🛠️ Requirements

- Python 3.8+
- streamlit
- pandas
- plotly

## 📝 Data Source

The dashboard reads from:
```
data/daily_stats/league_*.json
```

Make sure your data collection is running to see the latest stats!

## 🎨 Customization

Edit `app.py` to:
- Change color schemes
- Add new visualizations
- Modify date ranges
- Add custom metrics

## 📱 Access Anywhere

To share the dashboard:

```bash
streamlit run app.py --server.port 8501 --server.address 0.0.0.0
```

Then access via your machine's IP address.

Or deploy to Streamlit Cloud for free hosting!