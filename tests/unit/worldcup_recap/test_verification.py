"""Tests for the find/verify feedback loop in worldcup_recap/pipeline.py."""

import pytest

from worldcup_recap.pipeline import find_and_verify

pytestmark = pytest.mark.asyncio


async def test_accepts_on_first_attempt():
    async def finder(need, feedback):
        return {"url": "https://youtube.com/official", "source": "FIFA", "title": "RSA vs MEX"}

    async def verifier(need, candidate):
        return {"relevant": True, "confidence": 0.9, "reason": "matches teams and day"}

    result = await find_and_verify({"kind": "highlights"}, finder, verifier, max_attempts=3)
    assert result["status"] == "accepted"
    assert result["attempts"] == 1
    assert result["media"]["url"] == "https://youtube.com/official"


async def test_retries_then_accepts_with_feedback():
    calls = {"n": 0, "feedbacks": []}

    async def finder(need, feedback):
        calls["n"] += 1
        calls["feedbacks"].append(feedback)
        return {"url": f"https://x/{calls['n']}", "source": "x", "title": "t"}

    async def verifier(need, candidate):
        # reject the first candidate, accept the second
        if candidate["url"].endswith("/1"):
            return {"relevant": False, "confidence": 0.2, "reason": "wrong fixture"}
        return {"relevant": True, "confidence": 0.8, "reason": "ok"}

    result = await find_and_verify({"kind": "highlights"}, finder, verifier, max_attempts=3)
    assert result["status"] == "accepted"
    assert result["attempts"] == 2
    # feedback from the rejection was passed into the second finder call
    assert calls["feedbacks"][1] == "wrong fixture"


async def test_drops_after_max_attempts():
    async def finder(need, feedback):
        return {"url": "https://x/always", "source": "x", "title": "t"}

    async def verifier(need, candidate):
        return {"relevant": False, "confidence": 0.1, "reason": "still wrong"}

    result = await find_and_verify({"kind": "highlights"}, finder, verifier, max_attempts=3)
    assert result["status"] == "dropped"
    assert result["attempts"] == 3
    assert result["media"] is None


async def test_drops_when_finder_returns_nothing():
    async def finder(need, feedback):
        return None

    async def verifier(need, candidate):
        raise AssertionError("verifier should not be called when finder returns None")

    result = await find_and_verify({"kind": "highlights"}, finder, verifier, max_attempts=2)
    assert result["status"] == "dropped"
    assert result["media"] is None
    assert result["attempts"] == 2


async def test_resolve_redirect_passthrough_non_grounding():
    from worldcup_recap.pipeline import _resolve_redirect
    url = "https://www.fifa.com/en/articles/highlights"
    assert await _resolve_redirect(url) == url


async def test_resolve_redirect_empty_returns_empty():
    from worldcup_recap.pipeline import _resolve_redirect
    assert await _resolve_redirect("") == ""


async def test_attach_player_media_attaches_real_headshot(monkeypatch):
    import worldcup_recap.pipeline as P
    from worldcup_recap.providers.base import CollectedData, RawMatch
    match = RawMatch(match_id="1", stage="", home_team="A", away_team="B",
        home_score=0, away_score=0, status="", timeline=[], top_performers=[],
        player_stats=[{"name": "Star", "id": "99", "profile_url": "https://espn/p", "headshot_url": None}],
        venue="", attendance=None, espn_recap_url=None, espn_videos=[], news=[])
    data = CollectedData(date="d", matches=[match], standings=[], upcoming=[])
    sections = [{"type": "player_spotlight", "players": [{"name": "Star"}]}]
    async def fake_headshot(aid): return "https://espn/h.png"
    monkeypatch.setattr(P, "_fetch_headshot", fake_headshot)
    await P._attach_player_media(sections, data)
    media = sections[0]["players"][0]["media"]
    assert media["profile_url"] == "https://espn/p"
    assert media["headshot_url"] == "https://espn/h.png"


async def test_attach_player_media_omits_headshot_when_absent(monkeypatch):
    import worldcup_recap.pipeline as P
    from worldcup_recap.providers.base import CollectedData, RawMatch
    match = RawMatch(match_id="1", stage="", home_team="A", away_team="B",
        home_score=0, away_score=0, status="", timeline=[], top_performers=[],
        player_stats=[{"name": "Star", "id": "99", "profile_url": "https://espn/p", "headshot_url": None}],
        venue="", attendance=None, espn_recap_url=None, espn_videos=[], news=[])
    data = CollectedData(date="d", matches=[match], standings=[], upcoming=[])
    sections = [{"type": "player_spotlight", "players": [{"name": "Star"}]}]
    async def fake_headshot(aid): return None
    monkeypatch.setattr(P, "_fetch_headshot", fake_headshot)
    await P._attach_player_media(sections, data)
    media = sections[0]["players"][0]["media"]
    assert media["profile_url"] == "https://espn/p"
    assert "headshot_url" not in media


async def test_is_youtube():
    from worldcup_recap.pipeline import _is_youtube
    assert _is_youtube("https://www.youtube.com/watch?v=abc")
    assert _is_youtube("https://youtu.be/abc")
    assert not _is_youtube("https://www.fifa.com/x")
    assert not _is_youtube("")
