"""ADK pipeline runner — wires all four agents together.

Flow:
  1. structure_agent  → classifies raw data into sections (sequential)
  2. game_detail_agent + player_media_agent → enrich sections (parallel)
  3. synthesis_agent  → writes final prose (sequential)
"""

import asyncio
import json

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from nba_recap.agents.game_detail_agent import game_detail_agent, build_game_search_prompt
from nba_recap.agents.player_media_agent import player_media_agent, build_player_search_prompt
from nba_recap.agents.structure_agent import structure_agent, build_structure_prompt
from nba_recap.agents.synthesis_agent import synthesis_agent, parse_synthesis_response
from nba_recap.collect import CollectedData


async def _run_agent(agent, prompt: str, session_id: str) -> str:
    """Run a single ADK agent and return the final text response."""
    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name="nba_recap", user_id="pipeline", session_id=session_id
    )
    runner = Runner(
        agent=agent,
        app_name="nba_recap",
        session_service=session_service,
    )
    content = types.Content(role="user", parts=[types.Part(text=prompt)])
    final_text = ""
    async for event in runner.run_async(
        user_id="pipeline",
        session_id=session_id,
        new_message=content,
    ):
        if event.is_final_response():
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if hasattr(part, "text") and part.text:
                        final_text += part.text
    return final_text


async def _run_structure(data: CollectedData) -> dict:
    """Phase 2: classify raw data into sections."""
    print("  🧠 Structure agent running...")
    prompt = build_structure_prompt(data)
    response = await _run_agent(structure_agent, prompt, "structure_session")
    try:
        return json.loads(response.strip())
    except json.JSONDecodeError:
        print("  ⚠️  Structure agent returned invalid JSON, using empty sections")
        return {"sections": []}


async def _enrich_game_section(section: dict, date: str) -> dict:
    """Run game_detail_agent for a game_of_night section."""
    home = section.get("home_team", "")
    away = section.get("away_team", "")
    if not home or not away:
        return {**section, "media": {"recap_url": None, "highlight_url": None}}
    prompt = build_game_search_prompt(home, away, date)
    session_id = f"game_{home}_{away}_{date}".replace("-", "")
    response = await _run_agent(game_detail_agent, prompt, session_id)
    try:
        media = json.loads(response.strip())
    except json.JSONDecodeError:
        media = {"recap_url": None, "highlight_url": None}
    return {**section, "media": media}


async def _enrich_single_player(player: dict) -> dict:
    """Run player_media_agent for one player."""
    name = player.get("name", "")
    team = player.get("team", "")
    line = player.get("line", "")
    prompt = build_player_search_prompt(name, team, line)
    session_id = f"player_{name.replace(' ', '_')}"
    response = await _run_agent(player_media_agent, prompt, session_id)
    try:
        media = json.loads(response.strip())
    except json.JSONDecodeError:
        media = {"headshot_url": None, "interview_url": None}
    return {**player, "media": media}


async def _enrich_player_section(section: dict) -> dict:
    """Run player_media_agent for up to 3 players in a player_spotlight section."""
    players = section.get("players", [])
    tasks = [_enrich_single_player(p) for p in players[:3]]
    enriched = await asyncio.gather(*tasks, return_exceptions=True)
    result_players = []
    for player, res in zip(players[:3], enriched):
        if isinstance(res, Exception):
            result_players.append({**player, "media": {"headshot_url": None, "interview_url": None}})
        else:
            result_players.append(res)
    return {**section, "players": result_players, "media": {}}


async def _passthrough(section: dict) -> dict:
    """Pass a section through unchanged, adding an empty media dict."""
    return {**section, "media": {}}


async def _enrich_sections(sections: list[dict], date: str) -> tuple[list[dict], int]:
    """Phase 3: enrich all sections in parallel. Returns (enriched_sections, subagents_spawned)."""
    print(f"  🔍 Enriching {len(sections)} sections via subagents...")
    tasks = []
    subagents_spawned = 0

    for section in sections:
        section_type = section.get("type", "")
        if section_type == "game_of_night":
            tasks.append(_enrich_game_section(section, date))
            subagents_spawned += 1
        elif section_type == "player_spotlight":
            player_count = min(3, len(section.get("players", [])))
            tasks.append(_enrich_player_section(section))
            subagents_spawned += player_count
        else:
            tasks.append(_passthrough(section))

    enriched = await asyncio.gather(*tasks, return_exceptions=True)
    result = []
    for section, res in zip(sections, enriched):
        if isinstance(res, Exception):
            print(f"  ⚠️  Enrichment failed for section '{section.get('type')}': {res}")
            result.append({**section, "media": {}})
        else:
            result.append(res)

    return result, subagents_spawned


async def _run_synthesis(enriched_sections: list[dict]) -> dict:
    """Phase 4: write final narrative prose."""
    print("  ✍️  Synthesis agent running...")
    payload = json.dumps({"sections": enriched_sections}, indent=2)
    prompt = f"Write final narrative for this recap:\n\n{payload}"
    response = await _run_agent(synthesis_agent, prompt, "synthesis_session")
    return parse_synthesis_response(response)


async def run_pipeline(data: CollectedData) -> tuple[dict, int]:
    """Execute all four phases. Returns (synthesized_dict, subagents_spawned)."""
    structured = await _run_structure(data)
    sections = structured.get("sections", [])
    enriched_sections, subagents_spawned = await _enrich_sections(sections, data.date)
    synthesized = await _run_synthesis(enriched_sections)
    return synthesized, subagents_spawned
