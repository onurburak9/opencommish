"""Tests for worldcup_recap/synthesize.py."""

import pytest

from worldcup_recap.providers.base import CollectedData, RawMatch
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
             "home_team": "Norway", "away_team": "Sweden",
             "narrative": "A dominant night.", "score": "3-1",
             "media_needs": [{"kind": "highlights"}]},
            {"type": "player_spotlight", "title": "Standout Players",
             "players": [{"name": "Larsen", "line": "2 goals", "context": "brace",
                          "media": {"interview_url": "https://youtube.com/i"}}]},
        ],
    }


def _match(**kw):
    """Build a RawMatch with sensible Germany-Curaçao defaults."""
    base = dict(
        match_id="760423", stage="Group A", home_team="Germany", away_team="Curaçao",
        home_score=7, away_score=1, status="FT",
        timeline=[{
            "minute": "23'", "type": "Goal", "player": "Havertz",
            "text": "", "scoring_play": True,
        }],
        top_performers=[],
        player_stats=[{"name": "Havertz", "profile_url": "https://espn/h"}],
        venue="V", attendance=None,
        espn_recap_url="https://espn/recap",
        espn_videos=[
            {"web": "https://espn/video", "url": "https://espn/mp4"},
        ],
        news=[{"headline": "n", "url": "https://espn/n", "published": ""}],
        team_meta={
            "Germany": {"logo_url": "https://espn/ger.png", "profile_url": "https://espn/ger"},
            "Curaçao": {"logo_url": "https://espn/cur.png", "profile_url": "https://espn/cur"},
        },
    )
    base.update(kw)
    return RawMatch(**base)


# ---------------------------------------------------------------------------
# Unchanged core tests
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Updated tests — MOTD + roundup links now come from content.games
# ---------------------------------------------------------------------------

def test_render_markdown_includes_headline_and_player():
    """Headline, section title, and player name appear; MOTD links come from content.games."""
    data = CollectedData(
        date="2026-06-11", matches=[], standings=[], upcoming=[], sources_used=["espn"],
    )
    out = build_final_output(data, _synth(), generation_time=1.0,
                             verification={"searched": 0, "accepted": 0, "rejected": 0, "dropped": 0})
    md = render_markdown(out)
    assert "# Norway stun Sweden" in md
    assert "Match of the Day" in md
    assert "Larsen" in md
    # No section.media on MOTD (stripped by _clean_sections), no games match Norway/Sweden
    # So no highlight link emitted — that's correct new behavior.
    assert "[Full recap]" not in md


def test_render_markdown_results_roundup_and_looking_ahead():
    """Roundup game labels and looking-ahead storylines appear; game links come from content.games."""
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


def test_render_markdown_match_of_day_without_games_has_no_stray_blank():
    """MOTD with no matching game in content.games emits no link lines, no triple newlines."""
    out = build_final_output(
        _data(),
        {"headline": "h", "summary": "s",
         "sections": [{"type": "match_of_day", "title": "Match of the Day",
                       "home_team": "X", "away_team": "Y",
                       "narrative": "Tight game.", "score": "1-0"}]},
        generation_time=1.0,
        verification={"searched": 0, "accepted": 0, "rejected": 0, "dropped": 0},
    )
    md = render_markdown(out)
    assert "[Full recap]" not in md
    assert "[Highlights]" not in md
    # no triple newline (stray double blank line) introduced by missing media
    assert "\n\n\n" not in md


# ---------------------------------------------------------------------------
# New focused tests
# ---------------------------------------------------------------------------

def test_build_games_full_shape():
    from worldcup_recap.synthesize import build_games
    data = CollectedData(
        date="2026-06-14", matches=[_match()], standings=[], upcoming=[], sources_used=["espn"],
    )
    g = build_games(data)[0]
    assert g["match_id"] == "760423"
    assert g["home"]["score"] == 7 and g["away"]["score"] == 1
    assert g["home"]["logo_url"] == "https://espn/ger.png"
    assert g["media"]["recap_url"] == "https://espn/recap"
    assert g["media"]["highlight_url"] == "https://espn/video"   # prefers web key
    assert g["scorers"][0]["player"] == "Havertz"
    assert g["scorers"][0]["profile_url"] == "https://espn/h"
    assert len(g["news"]) == 1


def test_clean_sections_links_and_strips():
    from worldcup_recap.synthesize import _clean_sections
    data = CollectedData(
        date="2026-06-14", matches=[_match()], standings=[], upcoming=[], sources_used=["espn"],
    )
    sections = [
        {"type": "match_of_day", "title": "MOTD", "home_team": "Germany", "away_team": "Curaçao",
         "score": "7-1", "media_needs": [{"kind": "highlights"}], "media": {"x": 1}},
        {"type": "results_roundup", "title": "R",
         "games": [{"matchup": "Curaçao 1-7 Germany", "note": "n"}]},
    ]
    out = _clean_sections(sections, data)
    assert out[0]["match_id"] == "760423"
    assert "media_needs" not in out[0]
    assert "media" not in out[0]
    assert out[1]["games"][0]["match_id"] == "760423"


def test_build_final_output_has_games_and_merges_searched_highlight():
    data = CollectedData(
        date="2026-06-14", matches=[_match()], standings=[], upcoming=[], sources_used=["espn"],
    )
    synth = {
        "headline": "h", "summary": "s",
        "sections": [
            {"type": "match_of_day", "title": "MOTD",
             "home_team": "Germany", "away_team": "Curaçao",
             "score": "7-1",
             "media": {"highlight_url": "https://youtube/official"}},
        ],
    }
    out = build_final_output(data, synth, 1.0,
                             {"searched": 1, "accepted": 1, "rejected": 0, "dropped": 0})
    assert out["content"]["games"][0]["match_id"] == "760423"
    # searched highlight overrides the ESPN video for the MOTD game
    assert out["content"]["games"][0]["media"]["highlight_url"] == "https://youtube/official"


def test_render_markdown_links_all_games_from_games_list():
    data = CollectedData(
        date="2026-06-14", matches=[_match()], standings=[], upcoming=[], sources_used=["espn"],
    )
    synth = {
        "headline": "Big Day", "summary": "s",
        "sections": [
            {"type": "results_roundup", "title": "Other Results",
             "games": [{"matchup": "Curaçao 1-7 Germany", "note": "rout"}]},
        ],
    }
    out = build_final_output(data, synth, 1.0,
                             {"searched": 0, "accepted": 0, "rejected": 0, "dropped": 0})
    md = render_markdown(out)
    assert "https://espn/recap" in md    # recap link rendered for a non-headline game
    assert "Havertz" in md              # scorer rendered


def test_enrich_upcoming_filters_generic_news():
    from worldcup_recap.synthesize import _enrich_upcoming
    from worldcup_recap.providers.base import CollectedData, PreviewMatch
    pm = PreviewMatch(match_id="1", stage="", home_team="Spain", away_team="Cape Verde",
                      kickoff="", odds={"x": 1},
                      head_to_head=[], home_form=[], away_form=[],
                      news=[{"headline": "Portugal held by Congo DR", "url": "u1"},
                            {"headline": "Spain name squad for opener", "url": "u2"}])
    data = CollectedData(date="d", matches=[], standings=[], upcoming=[pm])
    out = _enrich_upcoming([{"home": "Spain", "away": "Cape Verde"}], data)
    # {"x": 1} has no useful fields so _summarize_odds returns None → odds absent
    assert "odds" not in out[0]
    assert out[0]["news"] == [{"headline": "Spain name squad for opener", "url": "u2"}]  # generic one filtered out


def test_summarize_odds_extracts_useful_fields():
    from worldcup_recap.synthesize import _summarize_odds
    raw = {
        "provider": {"name": "DraftKings", "logos": [{"href": "x.svg"}]},
        "details": "CZE -0.5", "overUnder": 2.5, "spread": -0.5,
        "homeTeamOdds": {"favorite": True, "moneyLine": -150, "team": {"id": "1", "logos": []}},
        "awayTeamOdds": {"favorite": False, "moneyLine": 370, "team": {"id": "2", "logos": []}},
    }
    out = _summarize_odds(raw, home="Czechia", away="South Africa")
    assert out == {"favorite": "Czechia", "line": "CZE -0.5", "over_under": 2.5}
    # none of the raw noise survives
    assert "provider" not in out and "homeTeamOdds" not in out


def test_summarize_odds_none():
    from worldcup_recap.synthesize import _summarize_odds
    assert _summarize_odds(None, "A", "B") is None
    assert _summarize_odds({"foo": "bar"}, "A", "B") is None


def test_enrich_upcoming_summarizes_odds():
    from worldcup_recap.synthesize import _enrich_upcoming
    from worldcup_recap.providers.base import CollectedData, PreviewMatch
    pm = PreviewMatch(match_id="1", stage="", home_team="Czechia", away_team="South Africa",
                      kickoff="", odds={"details": "CZE -0.5", "overUnder": 2.5,
                                        "homeTeamOdds": {"favorite": True}, "awayTeamOdds": {"favorite": False},
                                        "provider": {"logos": [{"href": "x"}]}},
                      head_to_head=[], home_form=[], away_form=[], news=[])
    data = CollectedData(date="d", matches=[], standings=[], upcoming=[pm])
    out = _enrich_upcoming([{"home": "Czechia", "away": "South Africa"}], data)
    assert out[0]["odds"] == {"favorite": "Czechia", "line": "CZE -0.5", "over_under": 2.5}
    assert len(str(out[0]["odds"])) < 120  # compact, not the raw 16KB object


def test_enrich_upcoming_omits_news_when_none_relevant():
    from worldcup_recap.synthesize import _enrich_upcoming
    from worldcup_recap.providers.base import CollectedData, PreviewMatch
    pm = PreviewMatch(match_id="1", stage="", home_team="Spain", away_team="Cape Verde",
                      kickoff="", odds=None, head_to_head=[], home_form=[], away_form=[],
                      news=[{"headline": "Portugal held by Congo DR", "url": "u1"}])
    data = CollectedData(date="d", matches=[], standings=[], upcoming=[pm])
    out = _enrich_upcoming([{"home": "Spain", "away": "Cape Verde"}], data)
    assert "news" not in out[0]
