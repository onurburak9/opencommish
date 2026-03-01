# 📊 Add Interactive Data Analysis Notebook

## Summary

This PR introduces a Jupyter notebook that provides immediate analytical insights from the collected Yahoo NBA Fantasy Basketball data, while the full backend/frontend platform is still under development.

## What's Included

### 📓 `notebooks/analysis.ipynb`
A comprehensive analysis notebook featuring:

| Section | Description |
|---------|-------------|
| **Team Performance** | Rankings, roster breakdowns, active vs bench points |
| **Player Analysis** | Top performers, bench stars, opportunity cost |
| **Bench Efficiency** | Points left on bench, missed lineup opportunities |
| **Category Breakdown** | Deep dive into PTS, REB, AST, and other stats |
| **Trend Analysis** | 7-day performance tracking with visualizations |

### 📦 `notebooks/requirements.txt`
Dependencies needed to run the notebook:
- pandas ≥2.0.0 (data manipulation)
- matplotlib ≥3.7.0 (plotting)
- seaborn ≥0.12.0 (statistical visualizations)
- jupyter ≥1.0.0 (notebook server)
- notebook ≥7.0.0 (notebook interface)

### 📖 `notebooks/README.md`
Documentation with quick start guide and usage examples.

## How to Run

```bash
# 1. Navigate to project root
cd opencommish

# 2. Install dependencies
pip install -r notebooks/requirements.txt

# 3. Launch Jupyter
jupyter notebook notebooks/analysis.ipynb

# 4. Run all cells (Cell → Run All)
```

## Sample Output

```
🏆 TOP 10 PERFORMERS (All Players)
============================================================
LeBron James             Ankara Tinercileri   PF     45.23
Stephen Curry            Warriors Fan         PG     42.18
...

💔 TOP 5 BENCH PERFORMERS (Opportunity Cost)
============================================================
Kevin Durant             Brooklyn Ballers      38.92

🚨 MISOPPORTUNITY: Kevin Durant outscored Player X by 12.45 points!
```

## Why This Matters

Currently, OpenCommish has:
- ✅ Automated data collection (20+ days of data)
- ❌ No backend/frontend to view the data

This notebook bridges the gap by providing **immediate value** from existing data without requiring the full platform to be built first.

## Data Compatibility

The notebook reads from the existing data structure:
```
data/daily_stats/league_{LEAGUE_ID}_YYYY-MM-DD.json
```

No changes needed to existing data collection pipelines.

## Future Extensions

This notebook can be extended with:
- Matchup predictions
- Player consistency analysis  
- Waiver wire recommendations
- Trade value calculations

## Testing

- [x] Notebook runs without errors on latest data
- [x] All visualizations render correctly
- [x] Works with existing data format

---

**Note**: This is a standalone addition that doesn't modify any existing code. It's designed to provide value immediately while the main platform is being developed.