"""
Pytest fixtures for unit tests.

Loads sample data from the data/ directory for testing.
"""

import json
import pytest
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.parent.parent


def get_latest_data_file(data_dir: Path, pattern: str) -> Path:
    """Get the most recent data file matching the pattern."""
    files = sorted(data_dir.glob(pattern))
    if not files:
        pytest.skip(f"No data files found in {data_dir}")
    return files[-1]


@pytest.fixture
def sample_daily_stats_file():
    """Return path to the most recent daily stats file."""
    data_dir = PROJECT_ROOT / "data" / "daily_stats"
    return get_latest_data_file(data_dir, "league_*.json")


@pytest.fixture
def sample_daily_stats(sample_daily_stats_file):
    """Load and return the most recent daily stats data."""
    with open(sample_daily_stats_file, 'r') as f:
        return json.load(f)


@pytest.fixture
def sample_projected_stats_file():
    """Return path to the most recent projected stats file."""
    data_dir = PROJECT_ROOT / "data" / "projected_stats"
    return get_latest_data_file(data_dir, "league_*.json")


@pytest.fixture
def sample_projected_stats(sample_projected_stats_file):
    """Load and return the most recent projected stats data."""
    with open(sample_projected_stats_file, 'r') as f:
        return json.load(f)


@pytest.fixture
def mock_yahoo_league_response():
    """Return a mock Yahoo API league response."""
    return {
        "league_id": "93905",
        "league_key": "428.l.93905",
        "name": "teletabi ligi",
        "num_teams": 8,
    }


@pytest.fixture
def mock_yahoo_team_response():
    """Return a mock Yahoo API team response."""
    return {
        "team_id": "1",
        "team_key": "428.l.93905.t.1",
        "name": "Test Team",
    }


@pytest.fixture
def mock_yahoo_player_response():
    """Return a mock Yahoo API player response."""
    return {
        "player_id": "12345",
        "player_key": "428.p.12345",
        "name": {"full": "Test Player"},
        "editorial_team_abbr": "LAL",
        "selected_position": {"position": "PG"},
        "player_stats": {
            "stats": [
                {"stat_id": "12", "value": 25.0},  # PTS
                {"stat_id": "13", "value": 5.0},   # REB
                {"stat_id": "14", "value": 7.0},   # AST
            ]
        }
    }
