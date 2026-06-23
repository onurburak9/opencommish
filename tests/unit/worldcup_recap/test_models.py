"""Tests for worldcup_recap/models.py — the recap JSON contract."""

from worldcup_recap.models import Content, Game, RecapOutput, coerce_sections


def test_recap_output_fills_defaults_for_missing_fields():
    """A nearly-empty input still dumps a complete, predictable shape."""
    out = RecapOutput.model_validate({"recap_id": "worldcup-daily-2026-06-11"}).model_dump(mode="json")
    assert out["recap_id"] == "worldcup-daily-2026-06-11"
    assert out["date"] == ""
    assert out["generated_at"] == ""
    assert out["source_data_file"] == ""
    # nested defaults present
    assert out["metadata"]["matches_count"] == 0
    assert out["metadata"]["sources_used"] == []
    assert out["metadata"]["verification"] == {
        "searched": 0, "accepted": 0, "rejected": 0, "dropped": 0, "details": [],
    }
    assert out["content"]["headline"] == ""
    assert out["content"]["games"] == []
    assert out["content"]["sections"] == []


def test_recap_output_preserves_unknown_fields():
    """extra='allow' keeps anything useful instead of silently dropping it."""
    out = RecapOutput.model_validate(
        {"recap_id": "x", "future_field": "keep me",
         "content": {"headline": "h", "experimental": [1, 2]}}
    ).model_dump(mode="json")
    assert out["future_field"] == "keep me"
    assert out["content"]["experimental"] == [1, 2]


def test_game_coerces_string_score_to_int():
    """A stringy score like '3' is coerced to the int 3."""
    g = Game.model_validate({"match_id": "1", "home": {"team": "A", "score": "3"},
                             "away": {"team": "B", "score": 1}})
    assert g.home.score == 3
    assert g.away.score == 1


def test_verification_round_trips_real_shape():
    """The verification dict the pipeline emits round-trips into the model and back."""
    v = {
        "searched": 1, "accepted": 1, "rejected": 0, "dropped": 0,
        "details": [{
            "owner": "match_of_day",
            "need": {"kind": "highlights", "subject": "Germany vs Curaçao", "context": ""},
            "status": "accepted", "accepted_url": "https://x/v",
            "attempts": [{"attempt": 1, "raw_url": "https://x/raw", "resolved_url": "https://x/v",
                          "outcome": "accepted", "reason": "ok"}],
        }],
    }
    out = RecapOutput.model_validate({"metadata": {"verification": v}}).model_dump(mode="json")
    assert out["metadata"]["verification"]["details"][0]["need"]["kind"] == "highlights"
    assert out["metadata"]["verification"]["details"][0]["attempts"][0]["outcome"] == "accepted"


def test_content_validates_sections_as_discriminated_union():
    """Content's `list[Section]` wiring + model_rebuild() resolves end-to-end."""
    c = Content.model_validate(
        {"headline": "h", "sections": [{"type": "group_watch", "title": "G", "notes": "n"}]}
    )
    assert c.sections[0].type == "group_watch"
    assert c.sections[0].notes == "n"


def test_coerce_sections_validates_all_known_types():
    """One of each section type validates and keeps its `type` discriminator."""
    raw = [
        {"type": "match_of_day", "title": "MOTD", "home_team": "Germany",
         "away_team": "Curaçao", "score": "7-1", "facts": "f", "match_id": "1"},
        {"type": "results_roundup", "title": "R",
         "games": [{"matchup": "A 1-0 B", "note": "n", "match_id": "2"}]},
        {"type": "player_spotlight", "title": "P",
         "players": [{"name": "X", "team": "T", "line": "1 goal", "context": "c",
                      "media": {"profile_url": "https://p"}}]},
        {"type": "group_watch", "title": "G", "notes": "some notes"},
        {"type": "storylines", "title": "S",
         "stories": [{"headline": "h", "summary": "s"}]},
        {"type": "looking_ahead", "title": "L",
         "upcoming": [{"home": "France", "away": "Peru", "kickoff": "t",
                       "storyline": "opener",
                       "odds": {"favorite": "France", "line": "FRA -1", "over_under": 2.5},
                       "news": [{"headline": "preview", "url": "u"}]}]},
    ]
    out = coerce_sections(raw)
    assert [s.type for s in out] == [
        "match_of_day", "results_roundup", "player_spotlight",
        "group_watch", "storylines", "looking_ahead",
    ]


def test_coerce_sections_drops_unknown_type():
    """A section with an unrecognised `type` is dropped, not fatal."""
    out = coerce_sections([
        {"type": "match_of_day", "title": "keep"},
        {"type": "mystery_meat", "title": "drop me"},
    ])
    assert len(out) == 1
    assert out[0].type == "match_of_day"


def test_coerce_sections_drops_malformed_but_keeps_siblings():
    """A malformed section (wrong shape) is dropped while valid siblings survive."""
    out = coerce_sections([
        {"type": "results_roundup", "title": "ok", "games": [{"matchup": "A 1-0 B"}]},
        {"type": "results_roundup", "title": "bad", "games": "not-a-list"},
        {"type": "storylines", "title": "also ok", "stories": []},
    ])
    titles = [s.title for s in out]
    assert titles == ["ok", "also ok"]


def test_coerce_sections_drops_section_without_type():
    """A section missing the `type` discriminator is dropped."""
    out = coerce_sections([{"title": "no type here"}])
    assert out == []


def test_section_preserves_unknown_fields():
    """extra='allow' keeps per-section extras (e.g. a section-level narrative variant)."""
    out = coerce_sections([
        {"type": "group_watch", "title": "G", "notes": "n", "future_field": "keep"},
    ])
    assert out[0].model_dump(mode="json")["future_field"] == "keep"


def test_committed_schema_matches_models():
    """The committed recap_output.json must equal the freshly generated schema."""
    import sys
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(repo_root))
    from scripts.gen_schema import generate_schema, _SCHEMA_PATH

    committed = _SCHEMA_PATH.read_text()
    assert committed == generate_schema(), (
        "recap_output.json is stale — regenerate with: uv run python scripts/gen_schema.py"
    )
