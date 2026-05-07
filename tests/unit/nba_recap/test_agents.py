"""Tests for nba_recap/agents/ — ADK agent helpers (prompt builders and response parsers)."""

import pytest
from nba_recap.agents.structure_agent import build_structure_prompt
from nba_recap.agents.game_detail_agent import build_game_search_prompt
from nba_recap.agents.player_media_agent import build_player_search_prompt
from nba_recap.agents.synthesis_agent import parse_synthesis_response
from nba_recap.collect import CollectedData, RawGameData


def _make_data():
    game = RawGameData(
        game_id="0022600001",
        home_team="LAL", away_team="GSW",
        home_score=128, away_score=112,
        status="Final", margin=16, overtime=False,
        top_performers=[
            {"name": "LeBron James", "team": "LAL", "pts": 38, "reb": 8, "ast": 6},
        ],
        injuries=[],
    )
    return CollectedData(
        date="2026-05-05",
        games=[game],
        standings_east=[{"team": "BOS", "wins": 58, "losses": 24, "conference": "East"}],
        standings_west=[{"team": "OKC", "wins": 62, "losses": 20, "conference": "West"}],
        upcoming_games=[{"home": "DEN", "away": "OKC", "game_id": "0022600010"}],
        sources_used=["nba_api"],
    )


# --- build_structure_prompt ---

def test_build_structure_prompt_contains_date():
    data = _make_data()
    prompt = build_structure_prompt(data)
    assert "2026-05-05" in prompt


def test_build_structure_prompt_contains_game_id():
    data = _make_data()
    prompt = build_structure_prompt(data)
    assert "0022600001" in prompt


def test_build_structure_prompt_contains_teams():
    data = _make_data()
    prompt = build_structure_prompt(data)
    assert "LAL" in prompt and "GSW" in prompt


def test_build_structure_prompt_is_string():
    data = _make_data()
    prompt = build_structure_prompt(data)
    assert isinstance(prompt, str) and len(prompt) > 50


# --- build_game_search_prompt ---

def test_build_game_search_prompt_contains_teams():
    prompt = build_game_search_prompt("LAL", "GSW", "2026-05-05")
    assert "LAL" in prompt or "Lakers" in prompt
    assert "GSW" in prompt or "Warriors" in prompt


def test_build_game_search_prompt_contains_date():
    prompt = build_game_search_prompt("BOS", "MIL", "2026-05-05")
    assert "2026-05-05" in prompt or "May" in prompt


def test_build_game_search_prompt_mentions_recap():
    prompt = build_game_search_prompt("BOS", "MIL", "2026-05-05")
    assert any(w in prompt.lower() for w in ["recap", "highlight", "article"])


# --- build_player_search_prompt ---

def test_build_player_search_prompt_contains_name():
    prompt = build_player_search_prompt("LeBron James", "LAL", "38/8/6")
    assert "LeBron James" in prompt


def test_build_player_search_prompt_asks_for_image():
    prompt = build_player_search_prompt("Victor Wembanyama", "SAS", "35/15/5")
    assert any(w in prompt.lower() for w in ["image", "photo", "headshot"])


# --- parse_synthesis_response ---

def test_parse_synthesis_response_valid_json():
    response = '{"headline": "Big night", "summary": "Good games.", "sections": []}'
    result = parse_synthesis_response(response)
    assert result["headline"] == "Big night"
    assert result["sections"] == []


def test_parse_synthesis_response_strips_markdown_fences():
    response = '```json\n{"headline": "Test", "summary": "s", "sections": []}\n```'
    result = parse_synthesis_response(response)
    assert result["headline"] == "Test"


def test_parse_synthesis_response_invalid_returns_fallback():
    result = parse_synthesis_response("not json at all")
    assert "headline" in result
    assert "sections" in result
