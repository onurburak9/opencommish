"""ADK pipeline runner — wires the four phases together.

Flow:
  1. structure_agent          → classify raw data into sections (sequential)
  2. deterministic media      → attach ESPN recap/video/news links directly
  3. find/verify loop         → searched media (highlights, interviews) w/ retry (parallel)
  4. synthesis_agent          → write final English prose (sequential)
"""

import asyncio
import json
import uuid
from typing import Awaitable, Callable

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from worldcup_recap.agents.structure_agent import structure_agent, build_structure_prompt
from worldcup_recap.agents.synthesis_agent import synthesis_agent, parse_synthesis_response
from worldcup_recap.agents.media_finder_agent import media_finder_agent, build_finder_prompt
from worldcup_recap.agents.media_verifier_agent import media_verifier_agent, build_verifier_prompt
from worldcup_recap.providers.base import CollectedData

_MAX_ATTEMPTS = 3

# Type aliases for the injectable loop dependencies
Finder = Callable[[dict, str | None], Awaitable[dict | None]]
Verifier = Callable[[dict, dict], Awaitable[dict]]


async def _run_agent(agent, prompt: str, session_id: str) -> str:
    """Run a single ADK agent and return its final text response."""
    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name="worldcup_recap", user_id="pipeline", session_id=session_id
    )
    runner = Runner(agent=agent, app_name="worldcup_recap", session_service=session_service)
    content = types.Content(role="user", parts=[types.Part(text=prompt)])
    final_text = ""
    async for event in runner.run_async(
        user_id="pipeline", session_id=session_id, new_message=content
    ):
        if event.is_final_response() and event.content and event.content.parts:
            for part in event.content.parts:
                if getattr(part, "text", None):
                    final_text += part.text
    return final_text


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        inner = lines[1:]
        if inner and inner[-1].strip() == "```":
            inner = inner[:-1]
        text = "\n".join(inner).strip()
    return text


def _parse_json(text: str, default: dict) -> dict:
    try:
        return json.loads(_strip_fences(text))
    except json.JSONDecodeError:
        return default


async def find_and_verify(
    need: dict, finder: Finder, verifier: Verifier, max_attempts: int = _MAX_ATTEMPTS
) -> dict:
    """Find a media link and verify it, retrying with feedback up to max_attempts.

    Returns {need, media, confidence?, attempts, status} where status is
    'accepted' or 'dropped'. Pure orchestration — finder/verifier are injectable.
    """
    feedback: str | None = None
    attempts = 0
    for attempt in range(1, max_attempts + 1):
        attempts = attempt
        candidate = await finder(need, feedback)
        if not candidate or not candidate.get("url"):
            feedback = "no result found; broaden the search"
            continue
        verdict = await verifier(need, candidate)
        if verdict.get("relevant"):
            return {
                "need": need,
                "media": candidate,
                "confidence": verdict.get("confidence"),
                "attempts": attempt,
                "status": "accepted",
            }
        feedback = verdict.get("reason", "not relevant")
    return {"need": need, "media": None, "attempts": attempts, "status": "dropped"}


# --- Agent-backed finder/verifier (used by the real pipeline) ---

async def _agent_finder(need: dict, feedback: str | None) -> dict | None:
    prompt = build_finder_prompt(need, feedback)
    resp = await _run_agent(media_finder_agent, prompt, f"finder_{uuid.uuid4().hex}")
    parsed = _parse_json(resp, {"url": None})
    return parsed if parsed.get("url") else None


async def _agent_verifier(need: dict, candidate: dict) -> dict:
    prompt = build_verifier_prompt(need, candidate)
    resp = await _run_agent(media_verifier_agent, prompt, f"verifier_{uuid.uuid4().hex}")
    return _parse_json(resp, {"relevant": False, "confidence": 0.0, "reason": "unparseable verdict"})


def _collect_media_needs(sections: list[dict]) -> list[tuple[int, str, dict]]:
    """Gather (section_index, owner, need) tuples from sections + their players."""
    needs = []
    for i, section in enumerate(sections):
        for need in section.get("media_needs", []) or []:
            needs.append((i, "section", need))
        for j, player in enumerate(section.get("players", []) or []):
            for need in player.get("media_needs", []) or []:
                needs.append((i, f"player:{j}", need))
    return needs


def _attach_deterministic_media(sections: list[dict], data: CollectedData) -> None:
    """Attach trusted ESPN links (recap/highlight) to match_of_day in place."""
    by_pair = {
        (m.home_team, m.away_team): m for m in data.matches
    }
    for section in sections:
        if section.get("type") != "match_of_day":
            section.setdefault("media", {})
            continue
        match = by_pair.get((section.get("home_team"), section.get("away_team")))
        media = section.setdefault("media", {})
        if match:
            media.setdefault("recap_url", match.espn_recap_url)
            if match.espn_videos and match.espn_videos[0].get("url"):
                media.setdefault("highlight_url", match.espn_videos[0]["url"])
            home_meta = match.team_meta.get(section.get("home_team"), {})
            away_meta = match.team_meta.get(section.get("away_team"), {})
            if home_meta.get("logo_url"):
                media.setdefault("home_logo_url", home_meta["logo_url"])
            if home_meta.get("profile_url"):
                media.setdefault("home_team_url", home_meta["profile_url"])
            if away_meta.get("logo_url"):
                media.setdefault("away_logo_url", away_meta["logo_url"])
            if away_meta.get("profile_url"):
                media.setdefault("away_team_url", away_meta["profile_url"])
        else:
            print(
                f"  ⚠️  match_of_day has no matching collected match "
                f"(home={section.get('home_team')!r} away={section.get('away_team')!r})"
            )


def _apply_verified_media(sections: list[dict], results: list[dict], needs: list[tuple]) -> None:
    """Write accepted searched media back onto the owning section/player."""
    for (idx, owner, _need), result in zip(needs, results):
        if result["status"] != "accepted":
            continue
        url = result["media"]["url"]
        kind = result["need"].get("kind", "media")
        key = "highlight_url" if kind == "highlights" else f"{kind}_url"
        if owner == "section":
            sections[idx].setdefault("media", {})[key] = url
        elif owner.startswith("player:"):
            j = int(owner.split(":")[1])
            players = sections[idx].get("players", [])
            if j < len(players):
                players[j].setdefault("media", {})[key] = url


def _attach_player_media(sections: list[dict], data: CollectedData) -> None:
    """Attach deterministic ESPN profile/headshot URLs to player_spotlight players by name."""
    meta: dict[str, dict] = {}
    for m in data.matches:
        for p in m.player_stats:
            if p.get("name"):
                meta[p["name"]] = {"profile_url": p.get("profile_url"), "headshot_url": p.get("headshot_url")}
    for section in sections:
        if section.get("type") != "player_spotlight":
            continue
        for player in section.get("players", []) or []:
            pm = meta.get(player.get("name", ""))
            if not pm:
                continue
            media = player.setdefault("media", {})
            if pm.get("profile_url"):
                media.setdefault("profile_url", pm["profile_url"])
            if pm.get("headshot_url"):
                media.setdefault("headshot_url", pm["headshot_url"])


async def _enrich(sections: list[dict], data: CollectedData) -> dict:
    """Phase 2+3: deterministic attach + searched find/verify loop. Returns telemetry."""
    _attach_deterministic_media(sections, data)
    _attach_player_media(sections, data)
    needs = _collect_media_needs(sections)
    print(f"  🔍 Verifying {len(needs)} searched media link(s)...")
    results = await asyncio.gather(
        *[find_and_verify(need, _agent_finder, _agent_verifier) for (_, _, need) in needs],
        return_exceptions=True,
    )
    clean = []
    for (_, _, need), r in zip(needs, results):
        if isinstance(r, Exception):
            clean.append({"need": need, "status": "dropped", "media": None, "attempts": 0})
        else:
            clean.append(r)
    _apply_verified_media(sections, clean, needs)
    accepted = sum(1 for r in clean if r["status"] == "accepted")
    dropped = sum(1 for r in clean if r["status"] == "dropped")
    # rejected = verifier rejections: all attempts for dropped needs; attempts-minus-winner for accepted
    rejected = sum(max(0, r.get("attempts", 0) - (1 if r["status"] == "accepted" else 0)) for r in clean)
    return {"searched": len(needs), "accepted": accepted, "rejected": rejected, "dropped": dropped}


async def _run_synthesis(enriched_sections: list[dict]) -> dict:
    payload = json.dumps({"sections": enriched_sections}, indent=2, ensure_ascii=False)
    response = await _run_agent(
        synthesis_agent, f"Write the final recap for:\n\n{payload}", "synthesis_session"
    )
    return parse_synthesis_response(response)


async def run_pipeline(data: CollectedData) -> tuple[dict, dict]:
    """Execute all phases. Returns (synthesized_dict, verification_telemetry)."""
    print("  🧠 Structure agent running...")
    structured = _parse_json(
        await _run_agent(structure_agent, build_structure_prompt(data), "structure_session"),
        {"sections": []},
    )
    sections = structured.get("sections", [])

    verification = await _enrich(sections, data)

    print("  ✍️  Synthesis agent running...")
    synthesized = await _run_synthesis(sections)
    return synthesized, verification
