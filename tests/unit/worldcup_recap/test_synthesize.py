"""Tests for worldcup_recap/synthesize.py."""

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


def test_render_markdown_results_roundup_and_looking_ahead():
    out = build_final_output(
        _data(),
        {
            "headline": "h", "summary": "s",
            "sections": [
                {"type": "results_roundup", "title": "Other Results",
                 "games": [{"matchup": "Brazil 2-1 Serbia", "note": "late winner"}]},
                {"type": "looking_ahead", "title": "Looking Ahead",
                 "upcoming": [{"home": "France", "away": "Peru",
                               "kickoff": "2026-06-12T19:00Z", "storyline": "Group D opener"}]},
            ],
        },
        generation_time=1.0,
        verification={"searched": 0, "accepted": 0, "rejected": 0, "dropped": 0},
    )
    md = render_markdown(out)
    assert "Brazil 2-1 Serbia" in md
    assert "late winner" in md
    assert "Peru @ France" in md
    assert "Group D opener" in md


def test_render_markdown_match_of_day_without_media_has_no_stray_blank():
    out = build_final_output(
        _data(),
        {"headline": "h", "summary": "s",
         "sections": [{"type": "match_of_day", "title": "Match of the Day",
                       "narrative": "Tight game.", "score": "1-0", "media": {}}]},
        generation_time=1.0,
        verification={"searched": 0, "accepted": 0, "rejected": 0, "dropped": 0},
    )
    md = render_markdown(out)
    assert "[Full recap]" not in md
    assert "[Highlights]" not in md
    # no triple newline (stray double blank line) introduced by the empty media block
    assert "\n\n\n" not in md


def test_render_markdown_empty_sections():
    out = build_final_output(
        _data(), {"headline": "Quiet day", "summary": "No games.", "sections": []},
        generation_time=0.5,
        verification={"searched": 0, "accepted": 0, "rejected": 0, "dropped": 0},
    )
    md = render_markdown(out)
    assert "# Quiet day" in md
    assert "No games." in md


def test_render_player_profile_link_and_photo():
    out = build_final_output(
        _data(),
        {"headline": "h", "summary": "s", "sections": [
            {"type": "player_spotlight", "title": "Standout Players", "players": [
                {"name": "Raúl Jiménez", "line": "1 goal", "context": "opener",
                 "media": {"profile_url": "https://espn.com/p/1", "headshot_url": "https://espn.com/h/1.png"}},
            ]},
        ]},
        generation_time=1.0,
        verification={"searched": 0, "accepted": 0, "rejected": 0, "dropped": 0},
    )
    md = render_markdown(out)
    assert "[Raúl Jiménez](https://espn.com/p/1)" in md
    assert "[Photo](https://espn.com/h/1.png)" in md


def test_build_final_output_has_source_pointer_not_embedded():
    out = build_final_output(_data(), _synth(), 1.0,
                             {"searched": 0, "accepted": 0, "rejected": 0, "dropped": 0})
    assert "source_data" not in out
    assert out["source_data_file"] == "2026-06-11.source.json"
    assert out["metadata"]["timezone"] == ""  # _data() sets no tz


def test_build_source_data_contains_matches():
    from worldcup_recap.providers.base import RawMatch
    m = RawMatch(match_id="1", stage="", home_team="A", away_team="B", home_score=1, away_score=0,
                 status="FT", timeline=[{"minute": "10'", "type": "Goal", "player": "X", "text": "", "scoring_play": True}],
                 top_performers=[], player_stats=[], venue="V", attendance=None,
                 espn_recap_url=None, espn_videos=[], news=[])
    data = CollectedData(date="2026-06-14", matches=[m], standings=[{"x": 1}], upcoming=[],
                         sources_used=["espn"], timezone="America/Los_Angeles")
    from worldcup_recap.synthesize import build_source_data
    src = build_source_data(data)
    assert src["timezone"] == "America/Los_Angeles"
    assert src["matches"][0]["match_id"] == "1"
    assert src["standings"] == [{"x": 1}]
