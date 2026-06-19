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


from worldcup_recap.providers.espn import (
    parse_scoreboard_event,
    parse_timeline,
    parse_player_stats,
    derive_top_performers,
    parse_news,
)


def _event():
    # Mirrors ESPN /scoreboard events[] shape
    return {
        "id": "401864055",
        "date": "2026-06-11T19:00Z",
        "name": "Sweden at Norway",
        "shortName": "SWE @ NOR",
        "status": {"type": {"name": "STATUS_FULL_TIME"}},
        "competitions": [{
            "venue": {"fullName": "Ullevaal Stadion"},
            "notes": [{"headline": "Group A"}],
            "competitors": [
                {"homeAway": "home", "score": "3", "team": {"displayName": "Norway"}},
                {"homeAway": "away", "score": "1", "team": {"displayName": "Sweden"}},
            ],
        }],
    }


def test_parse_scoreboard_event():
    r = parse_scoreboard_event(_event())
    assert r["match_id"] == "401864055"
    assert r["home_team"] == "Norway"
    assert r["away_team"] == "Sweden"
    assert r["home_score"] == 3
    assert r["away_score"] == 1
    assert r["status"] == "STATUS_FULL_TIME"
    assert r["stage"] == "Group A"
    assert r["venue"] == "Ullevaal Stadion"


def test_parse_scoreboard_event_missing_fields():
    r = parse_scoreboard_event({"id": "x", "competitions": [{}]})
    assert r["match_id"] == "x"
    assert r["home_team"] == ""
    assert r["home_score"] == 0
    assert r["stage"] == ""


def test_parse_timeline_filters_and_maps():
    key_events = [
        {"type": {"text": "Kickoff"}, "clock": {"displayValue": ""},
         "text": "First Half begins.", "scoringPlay": False},
        {"type": {"text": "Goal - Header"}, "clock": {"displayValue": "8'"},
         "text": "Goal! Norway 1, Sweden 0. Jørgen Strand Larsen header.",
         "scoringPlay": True,
         "participants": [{"athlete": {"displayName": "Jørgen Strand Larsen"}}]},
        {"type": {"text": "Yellow Card"}, "clock": {"displayValue": "40'"},
         "text": "Booking.", "scoringPlay": False,
         "participants": [{"athlete": {"displayName": "Some Player"}}]},
    ]
    tl = parse_timeline(key_events)
    # Kickoff is filtered out; goal + card kept
    assert len(tl) == 2
    goal = tl[0]
    assert goal["type"] == "Goal - Header"
    assert goal["minute"] == "8'"
    assert goal["player"] == "Jørgen Strand Larsen"
    assert goal["scoring_play"] is True


def test_parse_player_stats():
    rosters = [{
        "team": {"displayName": "Norway"},
        "formation": "4-4-2",
        "roster": [{
            "athlete": {"displayName": "Ørjan Nyland"},
            "position": {"abbreviation": "G"},
            "starter": True,
            "stats": [
                {"name": "saves", "displayValue": "3"},
                {"name": "goalsConceded", "displayValue": "1"},
            ],
        }],
    }]
    ps = parse_player_stats(rosters)
    assert len(ps) == 1
    assert ps[0]["name"] == "Ørjan Nyland"
    assert ps[0]["team"] == "Norway"
    assert ps[0]["position"] == "G"
    assert ps[0]["stats"]["saves"] == "3"


def test_derive_top_performers_counts_goals_and_gk():
    timeline = [
        {"type": "Goal - Header", "player": "Jørgen Strand Larsen", "scoring_play": True},
        {"type": "Goal", "player": "Antonio Nusa", "scoring_play": True},
        {"type": "Goal - Header", "player": "Jørgen Strand Larsen", "scoring_play": True},
    ]
    player_stats = [
        {"name": "Ørjan Nyland", "team": "Norway", "position": "G",
         "stats": {"saves": "3"}},
    ]
    perf = derive_top_performers(timeline, player_stats)
    names = [p["name"] for p in perf]
    assert "Jørgen Strand Larsen" in names
    larsen = next(p for p in perf if p["name"] == "Jørgen Strand Larsen")
    assert larsen["goals"] == 2
    # GK with saves is included
    assert any(p["name"] == "Ørjan Nyland" and p.get("saves") == 3 for p in perf)


def test_parse_news():
    articles = [
        {"headline": "Norway thrash Sweden", "published": "2026-06-11T21:00Z",
         "links": {"web": {"href": "https://espn.com/story/1"}}},
    ]
    news = parse_news(articles)
    assert news[0]["headline"] == "Norway thrash Sweden"
    assert news[0]["url"] == "https://espn.com/story/1"


def test_parse_timeline_excludes_goal_kick():
    key_events = [
        {"type": {"text": "Goal Kick"}, "clock": {"displayValue": "12'"},
         "text": "Goal kick.", "scoringPlay": False},
        {"type": {"text": "Goal"}, "clock": {"displayValue": "15'"},
         "text": "Goal! 1-0.", "scoringPlay": True,
         "participants": [{"athlete": {"displayName": "Scorer"}}]},
    ]
    tl = parse_timeline(key_events)
    types = [e["type"] for e in tl]
    assert "Goal Kick" not in types
    assert "Goal" in types
    assert len(tl) == 1


def test_derive_top_performers_excludes_own_goal():
    timeline = [
        {"type": "Own Goal", "player": "Unlucky Defender", "scoring_play": True},
        {"type": "Goal", "player": "Real Scorer", "scoring_play": True},
    ]
    perf = derive_top_performers(timeline, [])
    names = [p["name"] for p in perf]
    assert "Unlucky Defender" not in names
    assert "Real Scorer" in names


from worldcup_recap.providers.espn import parse_team_meta


def test_parse_player_stats_adds_profile_and_headshot():
    rosters = [{
        "team": {"displayName": "Mexico"},
        "roster": [{
            "athlete": {"displayName": "Raúl Rangel", "id": "290899",
                        "links": [{"href": "https://www.espn.com/soccer/player/_/id/290899/raul-rangel"}]},
            "position": {"abbreviation": "G"}, "starter": True,
            "stats": [{"name": "saves", "displayValue": "2"}],
        }],
    }]
    ps = parse_player_stats(rosters)
    assert ps[0]["id"] == "290899"
    assert ps[0]["profile_url"] == "https://www.espn.com/soccer/player/_/id/290899/raul-rangel"
    assert ps[0]["headshot_url"] is None


from worldcup_recap.providers.espn import parse_athlete_headshot


def test_parse_athlete_headshot_present_and_absent():
    assert parse_athlete_headshot({"athlete": {"headshot": {"href": "https://espn/h.png"}}}) == "https://espn/h.png"
    assert parse_athlete_headshot({"athlete": {}}) is None
    assert parse_athlete_headshot({}) is None


def test_parse_team_meta():
    summary = {"header": {"competitions": [{"competitors": [
        {"team": {"id": "203", "displayName": "Mexico",
                  "logos": [{"href": "https://a.espncdn.com/i/teamlogos/countries/500/mex.png"}],
                  "links": [{"href": "https://www.espn.com/soccer/team/_/id/203/mexico"}]}},
    ]}]}}
    meta = parse_team_meta(summary)
    assert meta["Mexico"]["logo_url"] == "https://a.espncdn.com/i/teamlogos/countries/500/mex.png"
    assert meta["Mexico"]["profile_url"] == "https://www.espn.com/soccer/team/_/id/203/mexico"


def test_derive_top_performers_carries_profile():
    timeline = [{"type": "Goal", "player": "Raúl Jiménez", "scoring_play": True}]
    player_stats = [{"name": "Raúl Jiménez", "team": "Mexico", "position": "F",
                     "profile_url": "https://espn.com/p/1", "headshot_url": "https://espn.com/h/1.png",
                     "stats": {}}]
    perf = derive_top_performers(timeline, player_stats)
    j = next(p for p in perf if p["name"] == "Raúl Jiménez")
    assert j["profile_url"] == "https://espn.com/p/1"
    assert j["headshot_url"] == "https://espn.com/h/1.png"


def test_build_verifier_prompt_includes_channel():
    from worldcup_recap.agents.media_verifier_agent import build_verifier_prompt
    p = build_verifier_prompt({"kind": "highlights"},
                              {"url": "u", "title": "t", "channel": "SuperSport", "source": "s"})
    assert "channel=SuperSport" in p


from worldcup_recap.providers.espn import event_local_date


def test_event_local_date_pst_rolls_back_a_day():
    # 04:00 UTC June 14 == 21:00 PDT June 13
    assert event_local_date("2026-06-14T04:00Z", "America/Los_Angeles") == "2026-06-13"


def test_event_local_date_pst_same_day():
    # 20:00 UTC June 14 == 13:00 PDT June 14
    assert event_local_date("2026-06-14T20:00Z", "America/Los_Angeles") == "2026-06-14"


def test_event_local_date_empty_and_bad():
    assert event_local_date("", "UTC") == ""
    assert event_local_date("not-a-date", "UTC") == ""


def test_parse_group_map():
    from worldcup_recap.providers.espn import parse_group_map
    payload = {"content": {"standings": {"groups": [
        {"name": "Group A", "standings": {"entries": [
            {"team": {"displayName": "Mexico"}},
            {"team": {"displayName": "Czechia"}},
        ]}},
    ]}}}
    gm = parse_group_map(payload)
    assert gm == {"Mexico": "Group A", "Czechia": "Group A"}
