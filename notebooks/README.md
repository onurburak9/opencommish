# 📓 OpenCommish Analysis Notebooks

Interactive Jupyter notebooks for analyzing Yahoo NBA Fantasy Basketball data.

## Quick Start

```bash
# 1. Install dependencies
pip install -r notebooks/requirements.txt

# 2. Launch Jupyter
jupyter notebook notebooks/analysis.ipynb
```

## Notebooks

### `analysis.ipynb` - Main Analysis Notebook

Comprehensive fantasy basketball analysis including:

- **Team Overview**: Standings, roster breakdowns, and performance rankings
- **Player Performance**: Top performers, stat leaders, and efficiency metrics
- **Bench Efficiency Analysis**: Identify points left on the bench and missed opportunities
- **Category Breakdown**: Deep dive into individual stat categories (PTS, REB, AST, etc.)
- **Multi-Day Trends**: Track team performance over time (7-day rolling analysis)

## Data Requirements

The notebook expects data in the following structure:
```
data/
└── daily_stats/
    └── league_{LEAGUE_ID}_YYYY-MM-DD.json
```

This data is automatically collected by the GitHub Actions workflows.

## Customization

Edit the configuration cell to adjust:
- `DATA_DIR`: Path to your stats data
- `LEAGUE_ID`: Your Yahoo league ID

## Example Output

```
🏆 TOP 10 PERFORMERS (All Players)
============================================================
LeBron James             Ankara Tinercileri   PF     45.23
Stephen Curry            Warriors Fan         PG     42.18
...

💔 TOP 5 BENCH PERFORMERS (Opportunity Cost)
============================================================
Kevin Durant             Brooklyn Ballers      38.92
...
```

## Extending

Use this notebook as a foundation for:
- Custom visualizations
- Predictive analytics
- Waiver wire recommendations
- Trade analysis