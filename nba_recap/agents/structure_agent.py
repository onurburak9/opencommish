"""ADK Agent: classifies raw NBA data into narrative sections."""

import json
from pathlib import Path

from google.adk.agents import Agent

from nba_recap.collect import CollectedData


_SYSTEM_PROMPT = (Path(__file__).parent.parent / "prompts" / "structure.md").read_text()


structure_agent = Agent(
    name="nba_structure_agent",
    model="gemini-2.5-flash",
    instruction=_SYSTEM_PROMPT,
)


def build_structure_prompt(data: CollectedData) -> str:
    """Build the user-turn message for the structure agent."""
    games_list = []
    for g in data.games:
        games_list.append({
            "game_id": g.game_id,
            "home_team": g.home_team,
            "away_team": g.away_team,
            "home_score": g.home_score,
            "away_score": g.away_score,
            "status": g.status,
            "margin": g.margin,
            "overtime": g.overtime,
            "top_performers": g.top_performers[:5],
        })
    payload = {
        "date": data.date,
        "games": games_list,
        "standings_east": data.standings_east[:5],
        "standings_west": data.standings_west[:5],
        "upcoming_games": data.upcoming_games,
    }
    return f"Structure this NBA data:\n\n{json.dumps(payload, indent=2)}"
