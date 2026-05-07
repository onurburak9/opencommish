"""ADK pipeline runner — wires all four agents together.

Flow:
  1. structure_agent  → classifies raw data into sections (sequential)
  2. Direct API enrichment → ESPN recap URLs, NBA CDN headshots (parallel, no LLM)
  3. synthesis_agent  → writes final prose (sequential)
"""

import asyncio
import json

import httpx
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from nba_recap.agents.structure_agent import structure_agent, build_structure_prompt
from nba_recap.agents.synthesis_agent import synthesis_agent, parse_synthesis_response
from nba_recap.collect import CollectedData

_ESPN_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
_NBA_HEADSHOT_CDN = "https://cdn.nba.com/headshots/nba/latest/1040x760/{player_id}.png"


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


def _strip_fences(text: str) -> str:
    """Strip markdown code fences that LLMs commonly wrap JSON in."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        inner = lines[1:]
        if inner and inner[-1].strip() == "```":
            inner = inner[:-1]
        text = "\n".join(inner).strip()
    return text


async def _run_structure(data: CollectedData) -> dict:
    """Phase 1: classify raw data into sections."""
    print("  🧠 Structure agent running...")
    prompt = build_structure_prompt(data)
    response = await _run_agent(structure_agent, prompt, "structure_session")
    try:
        return json.loads(_strip_fences(response))
    except json.JSONDecodeError:
        print("  ⚠️  Structure agent returned invalid JSON, using empty sections")
        return {"sections": []}


def _abbr_matches(espn_abbr: str, nba_abbr: str) -> bool:
    """ESPN uses shorter abbreviations (NY vs NYK, SA vs SAS). Match on prefix."""
    return nba_abbr.startswith(espn_abbr) or espn_abbr.startswith(nba_abbr)


async def _fetch_all_espn_games(date: str) -> list[dict]:
    """Fetch all games for a date from ESPN's public API. Called once and shared.

    Returns list of dicts with home_abbrs, away_abbrs, recap_url, highlight_url.
    """
    date_compact = date.replace("-", "")
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(_ESPN_SCOREBOARD, params={"dates": date_compact})
            resp.raise_for_status()
            games = []
            for event in resp.json().get("events", []):
                competitors = event.get("competitions", [{}])[0].get("competitors", [])
                home_abbr, away_abbr = "", ""
                for c in competitors:
                    if c.get("homeAway") == "home":
                        home_abbr = c["team"]["abbreviation"]
                    else:
                        away_abbr = c["team"]["abbreviation"]
                recap_url = next(
                    (lnk["href"] for lnk in event.get("links", []) if "summary" in lnk.get("rel", [])),
                    None,
                )
                games.append({
                    "home_abbr": home_abbr,
                    "away_abbr": away_abbr,
                    "recap_url": recap_url,
                })
            return games
        except Exception as e:
            print(f"  ⚠️  ESPN API failed: {e}")
    return []


def _find_espn_game(espn_games: list[dict], home_team: str, away_team: str, date: str) -> dict:
    """Find matching ESPN game entry and return media URLs."""
    for g in espn_games:
        home_match = _abbr_matches(g["home_abbr"], home_team)
        away_match = _abbr_matches(g["away_abbr"], away_team)
        if home_match and away_match:
            return {
                "recap_url": g["recap_url"],
                "highlight_url": (
                    f"https://www.youtube.com/results"
                    f"?search_query={away_team}+vs+{home_team}+highlights+NBA+{date}"
                ),
            }
    return {"recap_url": None, "highlight_url": None}


async def _enrich_game_section(section: dict, espn_games: list[dict], date: str) -> dict:
    """Enrich game_of_night with ESPN recap URL and YouTube search link."""
    home = section.get("home_team", "")
    away = section.get("away_team", "")
    if not home or not away:
        return {**section, "media": {"recap_url": None, "highlight_url": None}}
    media = _find_espn_game(espn_games, home, away, date)
    return {**section, "media": media}


def _parse_teams_from_matchup(matchup: str) -> tuple[str, str]:
    """Extract (away, home) abbreviations from a matchup string like 'PHI 102 @ NYK 108'."""
    import re
    m = re.match(r"([A-Z]{2,3})\s+\d+\s+@\s+([A-Z]{2,3})", matchup)
    if m:
        return m.group(1), m.group(2)
    return "", ""


async def _enrich_quick_hits_section(section: dict, espn_games: list[dict], date: str) -> dict:
    """Add ESPN game URLs to each game in the quick_hits section."""
    enriched_games = []
    for game in section.get("games", []):
        matchup = game.get("matchup", "")
        away, home = _parse_teams_from_matchup(matchup)
        media = _find_espn_game(espn_games, home, away, date) if home and away else {}
        enriched_games.append({**game, "recap_url": media.get("recap_url")})
    return {**section, "games": enriched_games, "media": {}}


async def _enrich_storylines_section(section: dict) -> dict:
    """Add a Google News search URL to each story based on its headline."""
    enriched_stories = []
    for story in section.get("stories", []):
        headline = story.get("headline", "")
        search_url = (
            f"https://news.google.com/search?q={headline.replace(' ', '+').replace(',', '')}+NBA"
            if headline else None
        )
        enriched_stories.append({**story, "news_url": search_url})
    return {**section, "stories": enriched_stories, "media": {}}


async def _enrich_looking_ahead_section(section: dict, date: str) -> dict:
    """Add ESPN game page URLs to upcoming games using the next day's ESPN scoreboard."""
    from datetime import date as date_type, timedelta
    next_date = (date_type.fromisoformat(date) + timedelta(days=1)).isoformat()
    espn_games_tomorrow = await _fetch_all_espn_games(next_date)

    enriched_upcoming = []
    for upcoming in section.get("upcoming", []):
        home = upcoming.get("home", "")
        away = upcoming.get("away", "")
        media = _find_espn_game(espn_games_tomorrow, home, away, next_date)
        enriched_upcoming.append({**upcoming, "espn_url": media.get("recap_url")})
    return {**section, "upcoming": enriched_upcoming, "media": {}}


def _build_player_media(player: dict, player_id_lookup: dict[str, int]) -> dict:
    """Build player media URLs from NBA CDN and YouTube search (no API calls needed)."""
    name = player.get("name", "")
    player_id = player.get("player_id") or player_id_lookup.get(name)
    headshot_url = (
        _NBA_HEADSHOT_CDN.format(player_id=player_id) if player_id else None
    )
    interview_url = (
        f"https://www.youtube.com/results?search_query={name.replace(' ', '+')}+post+game+interview+NBA+2026"
        if name else None
    )
    return {**player, "media": {"headshot_url": headshot_url, "interview_url": interview_url}}


async def _enrich_player_section(section: dict, player_id_lookup: dict[str, int]) -> dict:
    """Build media URLs for up to 3 players using NBA CDN + YouTube search."""
    players = section.get("players", [])
    enriched_players = [_build_player_media(p, player_id_lookup) for p in players[:3]]
    return {**section, "players": enriched_players, "media": {}}


async def _passthrough(section: dict) -> dict:
    """Pass a section through unchanged, adding an empty media dict."""
    return {**section, "media": {}}


async def _enrich_sections(
    sections: list[dict], date: str, player_id_lookup: dict[str, int]
) -> tuple[list[dict], int]:
    """Phase 3: enrich all sections in parallel. Returns (enriched_sections, subagents_spawned)."""
    print(f"  🔍 Enriching {len(sections)} sections...")

    # Fetch ESPN game data once — shared by game_of_night and quick_hits
    espn_games = await _fetch_all_espn_games(date)

    tasks = []
    subagents_spawned = 0

    for section in sections:
        section_type = section.get("type", "")
        if section_type == "game_of_night":
            tasks.append(_enrich_game_section(section, espn_games, date))
            subagents_spawned += 1
        elif section_type == "player_spotlight":
            player_count = min(3, len(section.get("players", [])))
            tasks.append(_enrich_player_section(section, player_id_lookup))
            subagents_spawned += player_count
        elif section_type == "quick_hits":
            tasks.append(_enrich_quick_hits_section(section, espn_games, date))
        elif section_type == "storylines":
            tasks.append(_enrich_storylines_section(section))
        elif section_type == "looking_ahead":
            tasks.append(_enrich_looking_ahead_section(section, date))
        else:
            print(f"  ⚠️  Unknown section type '{section_type}' — passing through unchanged")
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
    # Build name→player_id lookup from collected box score data
    player_id_lookup: dict[str, int] = {}
    for game in data.games:
        for p in game.top_performers:
            if p.get("name") and p.get("player_id"):
                player_id_lookup[p["name"]] = p["player_id"]

    structured = await _run_structure(data)
    sections = structured.get("sections", [])
    enriched_sections, subagents_spawned = await _enrich_sections(sections, data.date, player_id_lookup)
    synthesized = await _run_synthesis(enriched_sections)
    return synthesized, subagents_spawned
