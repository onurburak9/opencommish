"""Tests for worldcup_recap/providers."""

from worldcup_recap.providers.base import RawMatch, PreviewMatch, CollectedData


def test_raw_match_structure():
    m = RawMatch(
        match_id="401864055",
        stage="Group A",
        home_team="Norway",
        away_team="Sweden",
        home_score=3,
        away_score=1,
        status="STATUS_FULL_TIME",
        timeline=[],
        top_performers=[],
        player_stats=[],
        venue="Ullevaal Stadion",
        attendance=0,
        espn_recap_url=None,
        espn_videos=[],
        news=[],
    )
    assert m.match_id == "401864055"
    assert m.home_score == 3
    assert m.venue == "Ullevaal Stadion"


def test_collected_data_defaults():
    data = CollectedData(date="2026-06-11", matches=[], standings=[], upcoming=[])
    assert data.sources_used == []
    assert data.matches == []


def test_preview_match_structure():
    p = PreviewMatch(
        match_id="760415",
        stage="Group A",
        home_team="Mexico",
        away_team="South Africa",
        kickoff="2026-06-11T19:00Z",
        odds={"favorite": "Mexico"},
        head_to_head=[],
        home_form=["W", "D"],
        away_form=["L"],
        news=[],
    )
    assert p.home_team == "Mexico"
    assert p.home_form == ["W", "D"]
