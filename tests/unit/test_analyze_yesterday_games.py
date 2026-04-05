#!/usr/bin/env python3
"""
Unit tests for analyze_yesterday_games.py
"""

import json
import pytest
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add parent to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "cron"))

from analyze_yesterday_games import (
    to_str,
    analyze_yesterday_games,
    load_daily_stats,
)


class TestToStr:
    """Tests for to_str helper function."""
    
    def test_converts_bytes_to_str(self):
        """Test that bytes are decoded to string."""
        assert to_str(b"hello") == "hello"
    
    def test_handles_regular_string(self):
        """Test that regular strings pass through."""
        assert to_str("hello") == "hello"
    
    def test_handles_int(self):
        """Test that integers are converted to string."""
        assert to_str(123) == "123"


class TestAnalyzeYesterdayGames:
    """Tests for analyze_yesterday_games function."""
    
    @pytest.fixture
    def sample_data(self):
        """Create sample data for testing."""
        return {
            "date": "2026-03-07",
            "week": 19,
            "league_id": "93905",
            "league_key": "466.l.93905",
            "league_name": "teletabi ligi",
            "teams": [
                {
                    "team_id": "1",
                    "team_key": "466.l.93905.t.1",
                    "team_name": "Team A",
                    "players": [
                        {
                            "player_id": "1",
                            "player_key": "466.p.1",
                            "name": "Player One",
                            "nba_team": "LAL",
                            "roster_position": "PG",
                            "stats": [],
                            "fantasy_points": 45.5,
                        },
                        {
                            "player_id": "2",
                            "player_key": "466.p.2",
                            "name": "Player Two",
                            "nba_team": "LAL",
                            "roster_position": "SG",
                            "stats": [],
                            "fantasy_points": 32.0,
                        },
                        {
                            "player_id": "3",
                            "player_key": "466.p.3",
                            "name": "Player Three",
                            "nba_team": "LAL",
                            "roster_position": "SF",
                            "stats": [],
                            "fantasy_points": 8.5,
                        },
                    ],
                },
                {
                    "team_id": "2",
                    "team_key": "466.l.93905.t.2",
                    "team_name": "Team B",
                    "players": [
                        {
                            "player_id": "4",
                            "player_key": "466.p.4",
                            "name": "Player Four",
                            "nba_team": "GSW",
                            "roster_position": "PG",
                            "stats": [],
                            "fantasy_points": 52.0,
                        },
                        {
                            "player_id": "5",
                            "player_key": "466.p.5",
                            "name": "Player Five",
                            "nba_team": "GSW",
                            "roster_position": "C",
                            "stats": [],
                            "fantasy_points": 28.5,
                        },
                        {
                            "player_id": "6",
                            "player_key": "466.p.6",
                            "name": "Player Six",
                            "nba_team": "GSW",
                            "roster_position": "PF",
                            "stats": [],
                            "fantasy_points": 5.0,
                        },
                    ],
                },
            ],
        }
    
    def test_returns_correct_structure(self, sample_data, capsys):
        """Test that the function returns the expected structure."""
        results = analyze_yesterday_games(sample_data)
        
        assert "date" in results
        assert "league_name" in results
        assert "summary" in results
        assert "team_totals" in results
        assert "top_5_overall" in results
        assert "best_per_team" in results
        assert "worst_per_team" in results
    
    def test_team_totals_sorted_by_points(self, sample_data, capsys):
        """Test that team totals are sorted by fantasy points."""
        results = analyze_yesterday_games(sample_data)
        
        # Team A total: 45.5 + 32.0 + 8.5 = 86.0
        # Team B total: 52.0 + 28.5 + 5.0 = 85.5
        # Team A should be first
        assert results["team_totals"][0]["team_name"] == "Team A"
        assert results["team_totals"][0]["total_fantasy_points"] == 86.0
        assert results["team_totals"][1]["team_name"] == "Team B"
        assert results["team_totals"][1]["total_fantasy_points"] == 85.5
    
    def test_top_5_overall_sorted_correctly(self, sample_data, capsys):
        """Test that top 5 overall are sorted by fantasy points."""
        results = analyze_yesterday_games(sample_data)
        
        top_5 = results["top_5_overall"]
        assert len(top_5) == 5
        
        # Should be sorted descending: 52.0, 45.5, 32.0, 28.5, 8.5
        assert top_5[0]["name"] == "Player Four"
        assert top_5[0]["fantasy_points"] == 52.0
        assert top_5[1]["name"] == "Player One"
        assert top_5[1]["fantasy_points"] == 45.5
    
    def test_best_per_team_returns_top_2(self, sample_data, capsys):
        """Test that best_per_team returns top 2 performers per team."""
        results = analyze_yesterday_games(sample_data)
        
        team_a_best = results["best_per_team"]["Team A"]
        assert len(team_a_best) == 2
        assert team_a_best[0]["name"] == "Player One"  # 45.5
        assert team_a_best[1]["name"] == "Player Two"  # 32.0
        
        team_b_best = results["best_per_team"]["Team B"]
        assert len(team_b_best) == 2
        assert team_b_best[0]["name"] == "Player Four"  # 52.0
        assert team_b_best[1]["name"] == "Player Five"  # 28.5
    
    def test_worst_per_team_returns_bottom_2(self, sample_data, capsys):
        """Test that worst_per_team returns bottom 2 performers per team."""
        results = analyze_yesterday_games(sample_data)
        
        team_a_worst = results["worst_per_team"]["Team A"]
        assert len(team_a_worst) == 2
        # Sorted with lowest first: Player Three (8.5), Player Two (32.0)
        assert team_a_worst[0]["name"] == "Player Three"
        assert team_a_worst[0]["fantasy_points"] == 8.5
        assert team_a_worst[1]["name"] == "Player Two"
        assert team_a_worst[1]["fantasy_points"] == 32.0
    
    def test_excludes_players_with_zero_points(self, capsys):
        """Test that players with 0 fantasy points are excluded."""
        data = {
            "date": "2026-03-07",
            "week": 19,
            "league_id": "93905",
            "league_key": "466.l.93905",
            "league_name": "teletabi ligi",
            "teams": [
                {
                    "team_id": "1",
                    "team_key": "466.l.93905.t.1",
                    "team_name": "Team A",
                    "players": [
                        {
                            "player_id": "1",
                            "player_key": "466.p.1",
                            "name": "Active Player",
                            "nba_team": "LAL",
                            "roster_position": "PG",
                            "stats": [],
                            "fantasy_points": 25.0,
                        },
                        {
                            "player_id": "2",
                            "player_key": "466.p.2",
                            "name": "Zero Player",
                            "nba_team": "LAL",
                            "roster_position": "SG",
                            "stats": [],
                            "fantasy_points": 0.0,
                        },
                    ],
                },
            ],
        }
        
        results = analyze_yesterday_games(data)
        
        # Should only have 1 player in totals
        assert results["summary"]["total_players_with_stats"] == 1
        
        # Top 5 should only have 1 player
        assert len(results["top_5_overall"]) == 1
        assert results["top_5_overall"][0]["name"] == "Active Player"


class TestLoadDailyStats:
    """Tests for load_daily_stats function."""
    
    def test_returns_none_when_file_not_exists(self, tmp_path):
        """Test that None is returned when file doesn't exist."""
        fake_file = tmp_path / "cron" / "fake.py"
        fake_file.parent.mkdir(parents=True)
        fake_file.touch()
        with patch("analyze_yesterday_games.__file__", str(fake_file)):
            result = load_daily_stats(date(2026, 3, 7))
            assert result is None

    def test_returns_data_when_file_exists(self, tmp_path):
        """Test that data is loaded when file exists."""
        data_dir = tmp_path / "data" / "daily_stats"
        data_dir.mkdir(parents=True)
        test_file = data_dir / "league_93905_2026-03-07.json"
        test_data = {"date": "2026-03-07", "teams": []}
        test_file.write_text(json.dumps(test_data))

        fake_file = tmp_path / "cron" / "fake.py"
        fake_file.parent.mkdir(parents=True, exist_ok=True)
        fake_file.touch()
        with patch("analyze_yesterday_games.__file__", str(fake_file)):
            result = load_daily_stats(date(2026, 3, 7))
            assert result is not None
            assert result["date"] == "2026-03-07"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
