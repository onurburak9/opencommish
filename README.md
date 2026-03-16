# 🏀 OpenCommish

> Yahoo NBA Fantasy Basketball Analytics Platform

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.30+-red.svg)](https://streamlit.io)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

OpenCommish is a comprehensive analytics platform for Yahoo NBA Fantasy Basketball leagues. It automatically collects daily player statistics, provides interactive visualizations, and delivers insights to help you optimize your fantasy lineup.

![Dashboard Preview](https://via.placeholder.com/800x400?text=OpenCommish+Dashboard)

## ✨ Features

### 📊 Data Collection (Automated)
- **Daily Stats**: Automatically fetches player stats every day at 11:30 PM PST
- **Projected Stats**: Collects Yahoo's projected stats daily at 12:00 PM PST
- **GitHub Actions**: Serverless automation - no server needed!
- **Historical Data**: 20+ days of data collected and stored

### 📓 Jupyter Notebook Analysis
- Team performance rankings
- Player statistics and comparisons
- Bench efficiency analysis (find missed opportunities!)
- 7-day trend visualizations
- Category breakdowns (PTS, REB, AST, etc.)

### 🖥️ Streamlit Dashboard
- **Interactive Web UI**: Beautiful, responsive dashboard
- **Real-time Visualizations**: Plotly charts and graphs
- **5 Analysis Pages**:
  - 📊 Overview - Key metrics at a glance
  - 🏆 Team Rankings - Standings and comparisons
  - ⭐ Player Analysis - Filter by team/position
  - 📈 Trends - 14-day performance tracking
  - 💔 Bench Efficiency - Identify missed opportunities

### 🧪 Testing & Validation
- **Docker Containerization**: Production-ready Dockerfile for the dashboard
- **Integration Tests**: Playwright browser automation tests
- **Data Validation**: Compare scraped vs API data for accuracy
- **Unit Tests**: Schema validation and calculation verification

### 🔮 Coming Soon
- FastAPI Backend with REST endpoints
- PostgreSQL Database for data storage
- Next.js Frontend for production web app
- Matchup predictions and win probability

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/onurburak9/opencommish.git
cd opencommish
```

### 2. Set Up Environment

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install base dependencies
pip install -r requirements.txt
```

### 3. Configure Yahoo API

1. Go to https://developer.yahoo.com/apps/create/
2. Create an application:
   - **Application Type**: Installed Application
   - **API Permissions**: Fantasy Sports (Read/Write)
   - **Redirect URI**: `http://localhost:8000/callback`
3. Copy credentials to `.env` file:

```bash
cp .env.example .env
# Edit .env and add your credentials:
# YAHOO_CLIENT_ID=your_client_id
# YAHOO_CLIENT_SECRET=your_client_secret
```

### 4. Run the Dashboard

#### Option A: Local Development

```bash
cd dashboard
pip install -r requirements.txt
streamlit run app.py
```

Open http://localhost:8501 in your browser.

#### Option B: Docker

```bash
# Build the image
cd dashboard
docker build -t opencommish-dashboard .

# Run with data directory mounted
docker run -p 8501:8501 \
  -v $(pwd)/../data:/app/data \
  opencommish-dashboard
```

Open http://localhost:8501 in your browser.

### 5. Use the Jupyter Notebook

```bash
cd notebooks
pip install -r requirements.txt
jupyter notebook analysis.ipynb
```

## 📁 Project Structure

```
opencommish/
├── 📁 .github/workflows/       # GitHub Actions automation
│   ├── daily_stats.yml         # Daily data collection
│   ├── projected_stats.yml     # Projected stats collection
│   ├── integration-tests.yml   # Docker + Playwright tests
│   └── scrape-tests.yml        # Data validation tests
├── 📁 cron/                    # Data collection scripts
│   ├── fetch_daily_stats.py    # Daily stats fetcher (API)
│   ├── fetch_projected_stats.py    # Projected stats scraper (UI)
│   ├── fetch_projected_stats_api.py # Projected stats fetcher (API)
│   ├── validate_projected_stats.py  # Data validation tool
│   └── VALIDATION.md           # Validation documentation
├── 📁 dashboard/               # Streamlit web app
│   ├── app.py                  # Main dashboard
│   ├── Dockerfile              # Docker image
│   ├── .dockerignore           # Docker ignore rules
│   └── requirements.txt        # Dashboard dependencies
├── 📁 data/                    # Collected data (JSON)
│   ├── daily_stats/            # Daily player statistics
│   ├── projected_stats/        # Yahoo projected stats (scraped)
│   ├── projected_stats_api/    # Yahoo projected stats (API)
│   └── validation_reports/     # Validation reports
├── 📁 notebooks/               # Jupyter analysis notebooks
│   ├── analysis.ipynb          # Main analysis notebook
│   └── requirements.txt        # Notebook dependencies
├── 📁 tests/                   # Test suite
│   ├── integration/            # Playwright browser tests
│   ├── unit/                   # Data validation tests
│   └── requirements.txt        # Test dependencies
├── 📁 scripts/                 # Utility scripts
│   └── safe-git.sh             # AI safety wrapper (see CLAUDE.md)
├── 📁 backend/                 # FastAPI backend (planned)
├── 📁 frontend/                # Next.js frontend (planned)
├── 📄 CLAUDE.md                # Project guide & coding standards
├── 📄 PROGRESS.md              # Development progress tracker
└── 📄 requirements.txt         # Base Python dependencies
```

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| **Data Collection** | Python 3.11+, yfpy, BeautifulSoup |
| **Automation** | GitHub Actions |
| **Dashboard** | Streamlit, Plotly |
| **Analysis** | Jupyter, Pandas, Matplotlib, Seaborn |
| **Testing** | pytest, Playwright |
| **Containerization** | Docker |
| **Storage** | JSON files (PostgreSQL planned) |
| **Backend** | FastAPI (planned) |
| **Frontend** | Next.js, TypeScript, Tailwind (planned) |

## 📊 Data Format

Each day's data is stored as JSON with the following structure:

```json
{
  "date": "2026-02-27",
  "week": 16,
  "league_id": "93905",
  "league_name": "teletabi ligi",
  "teams": [
    {
      "team_name": "Ankara Tinercileri",
      "players": [
        {
          "name": "LeBron James",
          "roster_position": "PF",
          "fantasy_points": 45.23,
          "stats": [...]
        }
      ]
    }
  ]
}
```

## 🧪 Testing

### Running Unit Tests

Validate data structure and calculations:

```bash
pip install -r tests/requirements.txt
pytest tests/unit/ -v
```

### Running Integration Tests

Test the dashboard with Playwright browser automation:

```bash
pip install -r tests/integration/requirements.txt
playwright install chromium
pytest tests/integration/ --browser chromium
```

### Data Validation

Compare scraped data vs API data to ensure accuracy:

```bash
# 1. Fetch data via both methods
python cron/fetch_projected_stats.py
python cron/fetch_projected_stats_api.py

# 2. Compare and validate
python cron/validate_projected_stats.py
```

See [cron/VALIDATION.md](cron/VALIDATION.md) for more details.

## 🎯 Use Cases

### Fantasy League Managers
- Track team performance over time
- Identify optimal lineup configurations
- Analyze bench efficiency
- Compare players across teams

### Data Enthusiasts
- Export data for custom analysis
- Build predictive models
- Create custom visualizations
- Track fantasy trends

## 🤝 Contributing

Contributions are welcome! Please read [CLAUDE.md](CLAUDE.md) for:
- Coding standards
- Project architecture
- Development workflow

### Development Setup

```bash
# Install development dependencies
pip install -r requirements.txt
pip install -r notebooks/requirements.txt
pip install -r dashboard/requirements.txt

# Run tests
pytest

# Start dashboard for development
cd dashboard
streamlit run app.py
```

## 📈 Roadmap

### ✅ Completed
- [x] Yahoo API integration (yfpy)
- [x] Automated data collection (GitHub Actions)
- [x] 20+ days of historical data
- [x] Jupyter analysis notebook
- [x] Streamlit interactive dashboard
- [x] Docker containerization for dashboard
- [x] Playwright browser integration tests
- [x] Data validation tooling (scraped vs API)
- [x] Unit tests for scrape jobs

### 🚧 In Progress
- [ ] FastAPI backend
- [ ] PostgreSQL database
- [ ] Next.js frontend

### 📋 Planned
- [ ] Matchup predictions
- [ ] Win probability calculator
- [ ] Waiver wire recommendations
- [ ] Trade analyzer
- [ ] Mobile app

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [yfpy](https://github.com/uberfastman/yfpy) - Yahoo Fantasy Sports API wrapper
- [Streamlit](https://streamlit.io/) - For the beautiful dashboard framework
- Yahoo Fantasy Sports - For the API and data

## 📬 Contact

Have questions or suggestions? Open an issue or reach out!

---

**Happy Fantasy Basketball! 🏀**