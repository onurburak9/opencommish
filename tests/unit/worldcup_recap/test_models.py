"""Tests for worldcup_recap/models.py — the recap JSON contract."""

from worldcup_recap.models import Game, RecapOutput


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
