"""
Pytest fixtures for unit tests.

Loads sample data from the data/ directory for testing.
"""

import json
import pytest
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.parent.parent


# Mock data for CI environments without real data files
MOCK_DAILY_STATS = {
    "date": "2026-02-01",
    "week": 15,
    "league_id": "93905",
    "league_key": "466.l.93905",
    "league_name": "teletabi ligi",
    "teams": [
        {
            "team_id": "1",
            "team_key": "466.l.93905.t.1",
            "team_name": "Test Team 1",
            "players": [
                {
                    "player_id": "12345",
                    "player_key": "466.p.12345",
                    "name": "Test Player",
                    "nba_team": "LAL",
                    "opponent": "GSW",
                    "roster_position": "PG",
                    "stats": [
                        {"stat_id": 12, "display_name": "PTS", "name": "Points Scored", "value": 25.0, "modifier": 1.0, "points": 25.0},
                        {"stat_id": 15, "display_name": "REB", "name": "Total Rebounds", "value": 5.0, "modifier": 1.2, "points": 6.0},
                        {"stat_id": 16, "display_name": "AST", "name": "Assists", "value": 7.0, "modifier": 1.5, "points": 10.5},
                        {"stat_id": 17, "display_name": "ST", "name": "Steals", "value": 2.0, "modifier": 3.0, "points": 6.0},
                        {"stat_id": 18, "display_name": "BLK", "name": "Blocked Shots", "value": 1.0, "modifier": 3.0, "points": 3.0},
                        {"stat_id": 19, "display_name": "TO", "name": "Turnovers", "value": 3.0, "modifier": -1.0, "points": -3.0},
                    ],
                    "fantasy_points": 47.5
                }
            ]
        },
        {
            "team_id": "2",
            "team_key": "466.l.93905.t.2",
            "team_name": "Test Team 2",
            "players": [
                {
                    "player_id": "67890",
                    "player_key": "466.p.67890",
                    "name": "Another Player",
                    "nba_team": "BOS",
                    "opponent": "NYK",
                    "roster_position": "SG",
                    "stats": [
                        {"stat_id": 12, "display_name": "PTS", "name": "Points Scored", "value": 20.0, "modifier": 1.0, "points": 20.0},
                        {"stat_id": 15, "display_name": "REB", "name": "Total Rebounds", "value": 4.0, "modifier": 1.2, "points": 4.8},
                        {"stat_id": 16, "display_name": "AST", "name": "Assists", "value": 5.0, "modifier": 1.5, "points": 7.5},
                        {"stat_id": 17, "display_name": "ST", "name": "Steals", "value": 1.0, "modifier": 3.0, "points": 3.0},
                        {"stat_id": 18, "display_name": "BLK", "name": "Blocked Shots", "value": 0.0, "modifier": 3.0, "points": 0.0},
                        {"stat_id": 19, "display_name": "TO", "name": "Turnovers", "value": 2.0, "modifier": -1.0, "points": -2.0},
                    ],
                    "fantasy_points": 33.3
                }
            ]
        }
    ] + [
        # Add 6 more empty teams to match expected 8-team league
        {
            "team_id": str(i),
            "team_key": f"466.l.93905.t.{i}",
            "team_name": f"Test Team {i}",
            "players": []
        }
        for i in range(3, 9)
    ]
}


MOCK_PROJECTED_STATS = {
    "date": "2026-02-08",
    "league_id": "93905",
    "league_key": "466.l.93905",
    "league_name": "teletabi ligi",
    "teams": [
        {
            "team_id": "1",
            "team_key": "466.l.93905.t.1",
            "team_name": "Test Team 1",
            "players": [
                {
                    "player_id": "12345",
                    "player_name": "Test Player",
                    "roster_position": "PG",
                    "opponent": "GSW",
                    "games_played": 1,
                    "fantasy_points": 25.5,
                    "stats": {"PTS": 20.0, "REB": 5.0, "AST": 3.0, "ST": 1.0, "BLK": 0.0, "TO": 2.0}
                }
            ]
        }
    ] + [
        {
            "team_id": str(i),
            "team_key": f"466.l.93905.t.{i}",
            "team_name": f"Test Team {i}",
            "players": []
        }
        for i in range(2, 9)
    ]
}


def get_latest_data_file(data_dir: Path, pattern: str) -> Path:
    """Get the most recent data file matching the pattern."""
    files = sorted(data_dir.glob(pattern))
    if not files:
        return None
    return files[-1]


@pytest.fixture
def sample_daily_stats_file():
    """Return path to the most recent daily stats file."""
    data_dir = PROJECT_ROOT / "data" / "daily_stats"
    return get_latest_data_file(data_dir, "league_*.json")


@pytest.fixture
def sample_daily_stats(sample_daily_stats_file):
    """Load and return the most recent daily stats data."""
    if sample_daily_stats_file:
        with open(sample_daily_stats_file, 'r') as f:
            return json.load(f)
    # Return mock data if no files found
    return MOCK_DAILY_STATS


@pytest.fixture
def sample_projected_stats_file():
    """Return path to the most recent projected stats file."""
    data_dir = PROJECT_ROOT / "data" / "projected_stats"
    return get_latest_data_file(data_dir, "league_*.json")


@pytest.fixture
def sample_projected_stats(sample_projected_stats_file):
    """Load and return the most recent projected stats data."""
    if sample_projected_stats_file:
        with open(sample_projected_stats_file, 'r') as f:
            return json.load(f)
    # Return mock data if no files found
    return MOCK_PROJECTED_STATS
