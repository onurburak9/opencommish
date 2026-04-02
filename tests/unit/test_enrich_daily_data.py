"""Tests for cron/enrich_daily_data.py — enrichment logic."""

import pytest

from cron.enrich_daily_data import (
    classify_player,
    detect_achievements,
    find_missed_opportunities,
    had_game,
    enrich,
)


# --- classify_player ---

def test_active_positions():
    for pos in ["PG", "SG", "G", "SF", "PF", "F", "C", "Util"]:
        assert classify_player(pos) == "active", f"{pos} should be active"


def test_inactive_positions():
    for pos in ["BN", "IL", "IL+"]:
        assert classify_player(pos) == "inactive", f"{pos} should be inactive"


# --- had_game ---

def test_had_game_with_opponent():
    assert had_game({"opponent": "HOU", "fantasy_points": 0.0}) is True


def test_no_game_empty_opponent():
    assert had_game({"opponent": "", "fantasy_points": 0.0}) is False


def test_no_game_missing_opponent():
    assert had_game({"fantasy_points": 10.0}) is False


# --- detect_achievements ---

def test_double_double():
    stats = {"PTS": 20, "REB": 12, "AST": 3, "ST": 1, "BLK": 0}
    assert "double-double" in detect_achievements(stats)


def test_triple_double():
    stats = {"PTS": 20, "REB": 12, "AST": 11, "ST": 1, "BLK": 0}
    achievements = detect_achievements(stats)
    assert "triple-double" in achievements
    assert "double-double" not in achievements  # triple-double supersedes


def test_no_achievement():
    stats = {"PTS": 15, "REB": 4, "AST": 3, "ST": 1, "BLK": 0}
    assert detect_achievements(stats) == []


def test_double_double_steals_blocks():
    stats = {"PTS": 8, "REB": 4, "AST": 3, "ST": 10, "BLK": 12}
    assert "double-double" in detect_achievements(stats)


# --- find_missed_opportunities ---

def _make_player(name, pos, pts, opponent="OPP"):
    return {
        "name": name,
        "roster_position": pos,
        "fantasy_points": pts,
        "opponent": opponent,
        "nba_team": "TST",
        "stats": [],
        "player_id": "1",
        "player_key": "466.p.1",
    }


def test_missed_opp_bench_higher_than_active():
    """BN player scored more than a compatible active player."""
    players = [
        _make_player("Active Guy", "G", 20.0),
        _make_player("Bench Star", "BN", 45.0),
    ]
    opps = find_missed_opportunities(players)
    assert len(opps) == 1
    assert opps[0]["bench_player"] == "Bench Star"
    assert opps[0]["points_lost"] == 25.0
    assert opps[0]["swap_feasible"] is True


def test_no_missed_opp_bench_lower_than_active():
    """BN player scored less than all active players."""
    players = [
        _make_player("Active Guy", "G", 45.0),
        _make_player("Bench Scrub", "BN", 10.0),
    ]
    opps = find_missed_opportunities(players)
    assert len(opps) == 0


def test_no_missed_opp_bench_no_game():
    """BN player had no game → not a missed opportunity."""
    players = [
        _make_player("Active Guy", "G", 20.0),
        _make_player("Bench NoGame", "BN", 0.0, opponent=""),
    ]
    opps = find_missed_opportunities(players)
    assert len(opps) == 0


def test_il_player_swap_not_feasible():
    """IL+ player scored high but swap_feasible should be False."""
    players = [
        _make_player("Active Guy", "G", 20.0),
        _make_player("IL Star", "IL+", 60.0),
    ]
    opps = find_missed_opportunities(players)
    assert len(opps) == 1
    assert opps[0]["swap_feasible"] is False


def test_multiple_missed_opportunities_greedy():
    """Multiple bench players — best bench player matched first."""
    players = [
        _make_player("Low Active", "PG", 10.0),
        _make_player("Mid Active", "SG", 25.0),
        _make_player("High Bench", "BN", 50.0),
        _make_player("Med Bench", "BN", 30.0),
    ]
    opps = find_missed_opportunities(players)
    # High Bench (50) replaces Low Active (10) → 40 pts lost
    # Med Bench (30) replaces Mid Active (25) → 5 pts lost
    assert len(opps) == 2
    assert opps[0]["bench_player"] == "High Bench"
    assert opps[0]["active_player_replaced"] == "Low Active"
    assert opps[0]["points_lost"] == 40.0
    assert opps[1]["bench_player"] == "Med Bench"
    assert opps[1]["points_lost"] == 5.0


def test_bench_zero_points_with_game_not_missed():
    """BN player had a game but scored 0 → not a missed opportunity (0 > 0 is False)."""
    players = [
        _make_player("Active Guy", "G", 20.0),
        _make_player("Bench Zero", "BN", 0.0, opponent="LAL"),
    ]
    opps = find_missed_opportunities(players)
    assert len(opps) == 0


# --- enrich (integration) ---

def test_enrich_basic_structure():
    """enrich() produces correct top-level structure."""
    daily = {
        "date": "2026-03-31",
        "week": 23,
        "league_name": "teletabi ligi",
        "teams": [
            {
                "team_name": "Test Team",
                "team_id": "1",
                "players": [
                    _make_player("Star Player", "PG", 50.0),
                    _make_player("Bench Guy", "BN", 10.0, opponent=""),
                ],
            }
        ],
    }
    result = enrich(daily, None)
    assert result["date"] == "2026-03-31"
    assert len(result["teams"]) == 1
    assert result["teams"][0]["daily_active_points"] == 50.0
    assert len(result["top_5_active"]) == 1
    assert result["top_5_active"][0]["name"] == "Star Player"
    assert "mvp" in result["daily_awards"]


def test_enrich_il_player_not_in_top5():
    """IL+ player with high score must NOT appear in top_5_active."""
    daily = {
        "date": "2026-03-31",
        "week": 23,
        "league_name": "teletabi ligi",
        "teams": [
            {
                "team_name": "Test Team",
                "team_id": "1",
                "players": [
                    _make_player("Active Low", "PG", 20.0),
                    _make_player("IL Star", "IL+", 80.0),
                ],
            }
        ],
    }
    result = enrich(daily, None)
    top_names = [p["name"] for p in result["top_5_active"]]
    assert "IL Star" not in top_names
    assert "Active Low" in top_names
