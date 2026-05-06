"""Tests for nba_recap/collect.py."""

import pytest
from nba_recap.collect import (
    build_game_record,
    select_top_performers,
    parse_standings_entry,
    RawGameData,
)


def test_build_game_record_basic():
    raw = {
        "GAME_ID": "0022600001",
        "HOME_TEAM_ABBREVIATION": "LAL",
        "VISITOR_TEAM_ABBREVIATION": "GSW",
        "PTS_HOME": 128,
        "PTS_AWAY": 112,
        "GAME_STATUS_TEXT": "Final",
    }
    result = build_game_record(raw)
    assert result["game_id"] == "0022600001"
    assert result["home_team"] == "LAL"
    assert result["away_team"] == "GSW"
    assert result["home_score"] == 128
    assert result["away_score"] == 112
    assert result["margin"] == 16
    assert result["overtime"] is False


def test_build_game_record_overtime():
    raw = {
        "GAME_ID": "0022600002",
        "HOME_TEAM_ABBREVIATION": "BOS",
        "VISITOR_TEAM_ABBREVIATION": "MIL",
        "PTS_HOME": 115,
        "PTS_AWAY": 113,
        "GAME_STATUS_TEXT": "Final/OT",
    }
    result = build_game_record(raw)
    assert result["overtime"] is True
    assert result["margin"] == 2


def test_select_top_performers_sorted_by_pts():
    performers = [
        {"name": "A", "pts": 20, "reb": 5, "ast": 3},
        {"name": "B", "pts": 40, "reb": 8, "ast": 6},
        {"name": "C", "pts": 30, "reb": 4, "ast": 2},
    ]
    result = select_top_performers(performers, n=2)
    assert len(result) == 2
    assert result[0]["name"] == "B"


def test_select_top_performers_triple_double_elevated():
    performers = [
        {"name": "Star", "pts": 40, "reb": 5, "ast": 3},
        {"name": "Triple", "pts": 18, "reb": 11, "ast": 10},
    ]
    result = select_top_performers(performers, n=2)
    names = [p["name"] for p in result]
    assert "Triple" in names


def test_select_top_performers_empty():
    assert select_top_performers([], n=5) == []


def test_parse_standings_entry():
    raw = {
        "TeamAbbreviation": "LAL",
        "TeamID": 1610612747,
        "WINS": 45,
        "LOSSES": 37,
        "Conference": "West",
    }
    result = parse_standings_entry(raw)
    assert result["team"] == "LAL"
    assert result["wins"] == 45
    assert result["conference"] == "West"


def test_raw_game_data_structure():
    game = RawGameData(
        game_id="0022600001",
        home_team="LAL",
        away_team="GSW",
        home_score=128,
        away_score=112,
        status="Final",
        margin=16,
        overtime=False,
        top_performers=[],
        injuries=[],
    )
    assert game.game_id == "0022600001"
    assert game.overtime is False
