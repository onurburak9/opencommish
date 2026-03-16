"""
Unit tests for daily stats collection and validation.

These tests verify:
- JSON data structure matches expected schema
- Fantasy points calculations are correct
- Required fields are present
- Data consistency (no duplicates, all teams present)
"""

import json
import pytest
from pathlib import Path
from datetime import datetime


class TestDailyStatsSchema:
    """Tests for daily stats JSON schema validation."""
    
    REQUIRED_TOP_LEVEL_FIELDS = ["date", "week", "league_id", "league_name", "teams"]
    REQUIRED_TEAM_FIELDS = ["team_id", "team_key", "team_name", "players"]
    REQUIRED_PLAYER_FIELDS = ["player_id", "player_key", "name", "roster_position", "stats", "fantasy_points"]
    REQUIRED_STAT_FIELDS = ["stat_id", "display_name", "name", "value", "modifier", "points"]
    
    def test_top_level_structure(self, sample_daily_stats):
        """Verify top-level JSON structure has all required fields."""
        for field in self.REQUIRED_TOP_LEVEL_FIELDS:
            assert field in sample_daily_stats, f"Missing required field: {field}"
    
    def test_date_format(self, sample_daily_stats):
        """Verify date is in YYYY-MM-DD format."""
        date_str = sample_daily_stats["date"]
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            pytest.fail(f"Date '{date_str}' is not in YYYY-MM-DD format")
    
    def test_week_is_positive_integer(self, sample_daily_stats):
        """Verify week is a positive integer."""
        week = sample_daily_stats["week"]
        assert isinstance(week, int), f"Week should be integer, got {type(week)}"
        assert week > 0, f"Week should be positive, got {week}"
    
    def test_league_id_matches_filename(self, sample_daily_stats, sample_daily_stats_file):
        """Verify league_id in data matches the filename."""
        # Extract league_id from filename (format: league_{id}_{date}.json)
        filename = Path(sample_daily_stats_file).stem
        parts = filename.split("_")
        expected_league_id = parts[1]
        assert sample_daily_stats["league_id"] == expected_league_id, \
            f"League ID mismatch: {sample_daily_stats['league_id']} vs {expected_league_id}"
    
    def test_teams_array_not_empty(self, sample_daily_stats):
        """Verify teams array is not empty."""
        teams = sample_daily_stats["teams"]
        assert isinstance(teams, list), "Teams should be a list"
        assert len(teams) > 0, "Teams array should not be empty"


class TestTeamStructure:
    """Tests for team data structure."""
    
    def test_team_has_required_fields(self, sample_daily_stats):
        """Verify each team has all required fields."""
        for team in sample_daily_stats["teams"]:
            for field in TestDailyStatsSchema.REQUIRED_TEAM_FIELDS:
                assert field in team, f"Team missing required field: {field}"
    
    def test_team_id_is_string(self, sample_daily_stats):
        """Verify team_id is a string."""
        for team in sample_daily_stats["teams"]:
            assert isinstance(team["team_id"], str), \
                f"team_id should be string, got {type(team['team_id'])}"
    
    def test_team_name_not_empty(self, sample_daily_stats):
        """Verify team_name is not empty."""
        for team in sample_daily_stats["teams"]:
            assert team["team_name"] and len(team["team_name"].strip()) > 0, \
                "team_name should not be empty"


class TestPlayerStructure:
    """Tests for player data structure."""
    
    def test_player_has_required_fields(self, sample_daily_stats):
        """Verify each player has all required fields."""
        for team in sample_daily_stats["teams"]:
            for player in team["players"]:
                for field in TestDailyStatsSchema.REQUIRED_PLAYER_FIELDS:
                    assert field in player, f"Player {player.get('name', 'UNKNOWN')} missing field: {field}"
    
    def test_player_stats_structure(self, sample_daily_stats):
        """Verify player stats array has correct structure."""
        for team in sample_daily_stats["teams"]:
            for player in team["players"]:
                stats = player["stats"]
                assert isinstance(stats, list), f"stats should be a list for player {player['name']}"
                for stat in stats:
                    for field in TestDailyStatsSchema.REQUIRED_STAT_FIELDS:
                        assert field in stat, f"Stat missing field {field} for player {player['name']}"
    
    def test_no_duplicate_players_in_team(self, sample_daily_stats):
        """Verify no duplicate player_ids within a team."""
        for team in sample_daily_stats["teams"]:
            player_ids = [p["player_id"] for p in team["players"]]
            assert len(player_ids) == len(set(player_ids)), \
                f"Duplicate players found in team {team['team_name']}"


class TestFantasyPointsCalculation:
    """Tests for fantasy points calculation accuracy."""
    
    def test_fantasy_points_sum_matches(self, sample_daily_stats):
        """Verify fantasy_points equals sum of (value * modifier) for each stat."""
        for team in sample_daily_stats["teams"]:
            for player in team["players"]:
                expected_points = sum(
                    stat["value"] * stat["modifier"] 
                    for stat in player["stats"]
                )
                # Allow small floating point differences
                actual_points = player["fantasy_points"]
                assert abs(actual_points - expected_points) < 0.01, \
                    f"Fantasy points mismatch for {player['name']}: " \
                    f"expected {expected_points}, got {actual_points}"
    
    def test_fantasy_points_is_numeric(self, sample_daily_stats):
        """Verify fantasy_points is a number."""
        for team in sample_daily_stats["teams"]:
            for player in team["players"]:
                assert isinstance(player["fantasy_points"], (int, float)), \
                    f"fantasy_points should be numeric for {player['name']}"


class TestStatCategories:
    """Tests for stat category coverage."""
    
    KEY_STATS = ["PTS", "REB", "AST", "ST", "BLK", "TO"]
    
    def test_key_stat_categories_present(self, sample_daily_stats):
        """Verify key stat categories (PTS, REB, AST, ST, BLK, TO) are present."""
        # Get all unique display_names from first player of first team
        first_team = sample_daily_stats["teams"][0]
        first_player = first_team["players"][0]
        available_stats = {stat["display_name"] for stat in first_player["stats"]}
        
        for stat in self.KEY_STATS:
            assert stat in available_stats, f"Key stat '{stat}' not found in data"


class TestDataConsistency:
    """Tests for overall data consistency."""
    
    EXPECTED_TEAM_COUNT = 8  # Based on "teletabi ligi" league
    
    def test_expected_team_count(self, sample_daily_stats):
        """Verify we have the expected number of teams."""
        actual_count = len(sample_daily_stats["teams"])
        assert actual_count == self.EXPECTED_TEAM_COUNT, \
            f"Expected {self.EXPECTED_TEAM_COUNT} teams, got {actual_count}"
    
    def test_all_teams_have_players(self, sample_daily_stats):
        """Verify every team has at least one player."""
        for team in sample_daily_stats["teams"]:
            assert len(team["players"]) > 0, \
                f"Team {team['team_name']} has no players"
    
    def test_league_name_matches_expected(self, sample_daily_stats):
        """Verify league name matches expected value."""
        expected_name = "teletabi ligi"
        assert sample_daily_stats["league_name"] == expected_name, \
            f"League name mismatch: {sample_daily_stats['league_name']} vs {expected_name}"
