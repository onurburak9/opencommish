"""Tests for nba_recap/synthesize.py — output compilation helpers."""

import pytest
from nba_recap.synthesize import (
    build_recap_id,
    render_markdown,
    validate_output,
    build_final_output,
)
from nba_recap.collect import CollectedData


def test_build_recap_id():
    assert build_recap_id("2026-05-05") == "nba-daily-2026-05-05"


def test_render_markdown_headline():
    output = {
        "content": {"headline": "Celtics Win", "summary": "Boston wins.", "sections": []},
        "date": "2026-05-05",
    }
    md = render_markdown(output)
    assert "Celtics Win" in md
    assert "2026-05-05" in md


def test_render_markdown_section_narrative():
    output = {
        "content": {
            "headline": "Test",
            "summary": "Summary.",
            "sections": [
                {
                    "order": 1,
                    "type": "game_of_night",
                    "title": "Game of the Night",
                    "narrative": "Epic game.",
                    "media": {"recap_url": "https://espn.com/test"},
                }
            ],
        },
        "date": "2026-05-05",
    }
    md = render_markdown(output)
    assert "Game of the Night" in md
    assert "Epic game." in md
    assert "https://espn.com/test" in md


def test_render_markdown_no_recap_url():
    output = {
        "content": {
            "headline": "Test",
            "summary": "Summary.",
            "sections": [
                {
                    "order": 1,
                    "type": "game_of_night",
                    "title": "Game of the Night",
                    "narrative": "Epic game.",
                    "media": {"recap_url": None},
                }
            ],
        },
        "date": "2026-05-05",
    }
    md = render_markdown(output)
    assert "None" not in md  # null recap_url should not appear as the string "None"


def test_validate_output_valid():
    output = {
        "recap_id": "nba-daily-2026-05-05",
        "date": "2026-05-05",
        "generated_at": "2026-05-05T08:00:00Z",
        "metadata": {"games_count": 5, "sources_used": ["nba_api"], "generation_time_seconds": 45.0},
        "content": {"headline": "Test", "summary": "Summary.", "sections": []},
    }
    validate_output(output)  # should not raise


def test_validate_output_missing_key_raises():
    with pytest.raises(ValueError, match="Missing required field"):
        validate_output({"recap_id": "x", "date": "2026-05-05"})


def test_build_final_output_structure():
    data = CollectedData(
        date="2026-05-05",
        games=[],
        standings_east=[],
        standings_west=[],
        upcoming_games=[],
        sources_used=["nba_api"],
    )
    synthesized = {"headline": "Big Night", "summary": "Good games.", "sections": []}
    result = build_final_output(data=data, synthesized=synthesized, generation_time=30.5, subagents_spawned=4)
    assert result["recap_id"] == "nba-daily-2026-05-05"
    assert result["metadata"]["subagents_spawned"] == 4
    assert result["content"]["headline"] == "Big Night"
    assert result["metadata"]["generation_time_seconds"] == 30.5
