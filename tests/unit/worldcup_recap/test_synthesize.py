"""Tests for worldcup_recap/synthesize.py."""

import json

import pytest

from worldcup_recap.providers.base import CollectedData
from worldcup_recap.synthesize import (
    build_recap_id,
    validate_output,
    build_final_output,
    render_markdown,
)


def _data():
    return CollectedData(date="2026-06-11", matches=[], standings=[], upcoming=[],
                         sources_used=["espn"])


def _synth():
    return {
        "headline": "Norway stun Sweden",
        "summary": "Norway ran riot.",
        "sections": [
            {"type": "match_of_day", "title": "Match of the Day",
             "narrative": "A dominant night.", "score": "3-1",
             "media": {"highlight_url": "https://youtube.com/x", "recap_url": "https://espn.com/y"}},
            {"type": "player_spotlight", "title": "Standout Players",
             "players": [{"name": "Larsen", "line": "2 goals", "context": "brace",
                          "media": {"interview_url": "https://youtube.com/i"}}]},
        ],
    }


def test_build_recap_id():
    assert build_recap_id("2026-06-11") == "worldcup-daily-2026-06-11"


def test_validate_output_missing_key():
    with pytest.raises(ValueError):
        validate_output({"date": "2026-06-11"})


def test_build_final_output_shape():
    out = build_final_output(
        _data(), _synth(), generation_time=1.23,
        verification={"searched": 2, "accepted": 1, "rejected": 1, "dropped": 0},
    )
    assert out["recap_id"] == "worldcup-daily-2026-06-11"
    assert out["metadata"]["matches_count"] == 0
    assert out["metadata"]["sources_used"] == ["espn"]
    assert out["metadata"]["verification"]["accepted"] == 1
    assert out["content"]["headline"] == "Norway stun Sweden"
    # validate_output ran without raising
    validate_output(out)


def test_render_markdown_includes_headline_and_links():
    out = build_final_output(
        _data(), _synth(), generation_time=1.0,
        verification={"searched": 0, "accepted": 0, "rejected": 0, "dropped": 0},
    )
    md = render_markdown(out)
    assert "# Norway stun Sweden" in md
    assert "Match of the Day" in md
    assert "https://youtube.com/x" in md
    assert "Larsen" in md
