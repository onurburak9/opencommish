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


async def test_agent_finder_drops_unresolved_grounding_redirect(monkeypatch):
    import worldcup_recap.pipeline as P
    redirect = "https://vertexaisearch.cloud.google.com/grounding-api-redirect/ABC"
    async def fake_run_agent(agent, prompt, sid):
        return '{"url": "' + redirect + '", "source": "x", "title": "t"}'
    async def fake_resolve(url):
        return url  # resolution failed -> still a grounding redirect
    monkeypatch.setattr(P, "_run_agent", fake_run_agent)
    monkeypatch.setattr(P, "_resolve_redirect", fake_resolve)
    result = await P._agent_finder({"kind": "highlights"}, None)
    assert result["url"] is None
    assert result["drop_reason"] == "unresolved_redirect"


async def test_find_and_verify_log_records_accept():
    async def finder(need, feedback):
        return {"url": "https://fifa.com/x", "raw_url": "https://redir/x", "source": "fifa", "title": "t"}
    async def verifier(need, cand):
        return {"relevant": True, "confidence": 0.9, "reason": "match"}
    res = await find_and_verify({"kind": "highlights"}, finder, verifier, max_attempts=3)
    assert res["status"] == "accepted"
    assert len(res["log"]) == 1
    entry = res["log"][0]
    assert entry["resolved_url"] == "https://fifa.com/x"
    assert entry["raw_url"] == "https://redir/x"
    assert entry["outcome"] == "accepted"


async def test_find_and_verify_log_records_reject_then_drop():
    async def finder(need, feedback):
        return {"url": "https://x/bad", "raw_url": "https://x/bad"}
    async def verifier(need, cand):
        return {"relevant": False, "confidence": 0.1, "reason": "wrong fixture"}
    res = await find_and_verify({"kind": "highlights"}, finder, verifier, max_attempts=3)
    assert res["status"] == "dropped"
    assert len(res["log"]) == 3
    assert all(e["outcome"] == "verifier_rejected" for e in res["log"])
    assert res["log"][0]["reason"] == "wrong fixture"


async def test_find_and_verify_log_records_finder_dropreason():
    async def finder(need, feedback):
        return {"url": None, "raw_url": "https://redir/x", "drop_reason": "unresolved_redirect"}
    async def verifier(need, cand):
        raise AssertionError("verifier should not be called")
    res = await find_and_verify({"kind": "highlights"}, finder, verifier, max_attempts=2)
    assert res["status"] == "dropped"
    assert [e["outcome"] for e in res["log"]] == ["unresolved_redirect", "unresolved_redirect"]
