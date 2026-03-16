"""
Unit tests for projected stats collection and validation.

These tests verify:
- Scraped JSON data structure matches expected schema
- All required fields are present
- Roster positions are valid
- Stats values are numeric and within expected ranges
"""

import json
import pytest
from pathlib import Path
from datetime import datetime


class TestProjectedStatsSchema:
    """Tests for projected stats JSON schema validation."""
    
    REQUIRED_TOP_LEVEL_FIELDS = ["date", "league_id", "league_key", "league_name", "teams"]
    REQUIRED_TEAM_FIELDS = ["team_id", "team_key", "team_name", "players"]
    REQUIRED_PLAYER_FIELDS = [
        "player_id", "player_name", "roster_position", 
        "opponent", "games_played", "fantasy_points", "stats"
    ]
    
    def test_top_level_structure(self, sample_projected_stats):
        """Verify top-level JSON structure has all required fields."""
        for field in self.REQUIRED_TOP_LEVEL_FIELDS:
            assert field in sample_projected_stats, f"Missing required field: {field}"
    
    def test_date_format(self, sample_projected_stats):
        """Verify date is in YYYY-MM-DD format."""
        date_str = sample_projected_stats["date"]
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            pytest.fail(f"Date '{date_str}' is not in YYYY-MM-DD format")
    
    def test_league_id_matches_filename(self, sample_projected_stats, sample_projected_stats_file):
        """Verify league_id in data matches the filename."""
        filename = Path(sample_projected_stats_file).stem
        parts = filename.split("_")
        expected_league_id = parts[1]
        assert sample_projected_stats["league_id"] == expected_league_id, \
            f"League ID mismatch: {sample_projected_stats['league_id']} vs {expected_league_id}"
    
    def test_teams_array_not_empty(self, sample_projected_stats):
        """Verify teams array is not empty."""
        teams = sample_projected_stats["teams"]
        assert isinstance(teams, list), "Teams should be a list"
        assert len(teams) > 0, "Teams array should not be empty"


class TestProjectedTeamStructure:
    """Tests for team data structure in projected stats."""
    
    def test_team_has_required_fields(self, sample_projected_stats):
        """Verify each team has all required fields."""
        for team in sample_projected_stats["teams"]:
            for field in TestProjectedStatsSchema.REQUIRED_TEAM_FIELDS:
                assert field in team, f"Team missing required field: {field}"
    
    def test_team_name_not_empty(self, sample_projected_stats):
        """Verify team_name is not empty."""
        for team in sample_projected_stats["teams"]:
            assert team["team_name"] and len(team["team_name"].strip()) > 0, \
                "team_name should not be empty"


class TestProjectedPlayerStructure:
    """Tests for player data structure in projected stats."""
    
    VALID_ROSTER_POSITIONS = {"PG", "SG", "G", "SF", "PF", "F", "C", "Util", "BN", "IL", "IL+"}
    REQUIRED_STAT_KEYS = {"PTS", "REB", "AST", "ST", "BLK", "TO"}
    
    def test_player_has_required_fields(self, sample_projected_stats):
        """Verify each player has all required fields."""
        for team in sample_projected_stats["teams"]:
            for player in team["players"]:
                for field in TestProjectedStatsSchema.REQUIRED_PLAYER_FIELDS:
                    assert field in player, \
                        f"Player {player.get('player_name', 'UNKNOWN')} missing field: {field}"
    
    def test_roster_position_is_valid(self, sample_projected_stats):
        """Verify roster_position is a valid fantasy position."""
        for team in sample_projected_stats["teams"]:
            for player in team["players"]:
                position = player["roster_position"]
                assert position in self.VALID_ROSTER_POSITIONS, \
                    f"Invalid roster position '{position}' for player {player['player_name']}"
    
    def test_player_stats_is_dict(self, sample_projected_stats):
        """Verify player stats is a dictionary with expected keys."""
        for team in sample_projected_stats["teams"]:
            for player in team["players"]:
                stats = player["stats"]
                assert isinstance(stats, dict), \
                    f"stats should be a dict for player {player['player_name']}"
                
                for stat_key in self.REQUIRED_STAT_KEYS:
                    assert stat_key in stats, \
                        f"Missing stat '{stat_key}' for player {player['player_name']}"
    
    def test_stat_values_are_numeric(self, sample_projected_stats):
        """Verify all stat values are numeric."""
        for team in sample_projected_stats["teams"]:
            for player in team["players"]:
                for stat_name, stat_value in player["stats"].items():
                    assert isinstance(stat_value, (int, float)), \
                        f"Stat '{stat_name}' should be numeric for {player['player_name']}"
    
    def test_no_duplicate_players_in_team(self, sample_projected_stats):
        """Verify no duplicate player_ids within a team."""
        for team in sample_projected_stats["teams"]:
            player_ids = [p["player_id"] for p in team["players"]]
            assert len(player_ids) == len(set(player_ids)), \
                f"Duplicate players found in team {team['team_name']}"


class TestProjectedStatsValues:
    """Tests for projected stats value validation."""
    
    def test_fantasy_points_is_numeric(self, sample_projected_stats):
        """Verify fantasy_points is a number."""
        for team in sample_projected_stats["teams"]:
            for player in team["players"]:
                assert isinstance(player["fantasy_points"], (int, float)), \
                    f"fantasy_points should be numeric for {player['player_name']}"
    
    def test_fantasy_points_not_negative(self, sample_projected_stats):
        """Verify fantasy_points is not negative."""
        for team in sample_projected_stats["teams"]:
            for player in team["players"]:
                assert player["fantasy_points"] >= 0, \
                    f"fantasy_points should not be negative for {player['player_name']}"
    
    def test_games_played_is_integer(self, sample_projected_stats):
        """Verify games_played is an integer (0, 1, or 2 for back-to-backs)."""
        for team in sample_projected_stats["teams"]:
            for player in team["players"]:
                gp = player["games_played"]
                assert isinstance(gp, int), \
                    f"games_played should be integer for {player['player_name']}"
                assert 0 <= gp <= 2, \
                    f"games_played should be 0-2 for {player['player_name']}, got {gp}"
    
    def test_opponent_format(self, sample_projected_stats):
        """Verify opponent is a valid 3-letter team abbreviation or empty."""
        valid_teams = {
            "ATL", "BOS", "BKN", "CHA", "CHI", "CLE", "DAL", "DEN", "DET", "GSW",
            "HOU", "IND", "LAC", "LAL", "MEM", "MIA", "MIL", "MIN", "NOP", "NYK",
            "OKC", "ORL", "PHI", "PHX", "POR", "SAC", "SAS", "TOR", "UTA", "WAS"
        }
        for team in sample_projected_stats["teams"]:
            for player in team["players"]:
                opponent = player["opponent"]
                # Opponent can be empty or a valid 3-letter abbreviation
                if opponent:
                    assert len(opponent) == 3 and opponent.upper() == opponent, \
                        f"Invalid opponent format '{opponent}' for {player['player_name']}"


class TestProjectedDataConsistency:
    """Tests for overall projected data consistency."""
    
    EXPECTED_TEAM_COUNT = 8  # Based on "teletabi ligi" league
    
    def test_expected_team_count(self, sample_projected_stats):
        """Verify we have the expected number of teams."""
        actual_count = len(sample_projected_stats["teams"])
        assert actual_count == self.EXPECTED_TEAM_COUNT, \
            f"Expected {self.EXPECTED_TEAM_COUNT} teams, got {actual_count}"
    
    def test_all_teams_have_players(self, sample_projected_stats):
        """Verify every team has at least one player."""
        for team in sample_projected_stats["teams"]:
            assert len(team["players"]) > 0, \
                f"Team {team['team_name']} has no players"
    
    def test_league_name_matches_expected(self, sample_projected_stats):
        """Verify league name matches expected value."""
        expected_name = "teletabi ligi"
        assert sample_projected_stats["league_name"] == expected_name, \
            f"League name mismatch: {sample_projected_stats['league_name']} vs {expected_name}"
