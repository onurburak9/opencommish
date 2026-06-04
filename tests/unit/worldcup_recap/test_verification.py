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
