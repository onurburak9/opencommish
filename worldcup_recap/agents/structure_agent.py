"""ADK Agent: classifies raw World Cup data into narrative sections.

Uses Gemini 2.5 Flash (free tier) for the MVP. Future iteration may switch to a
stronger model / agent harness (e.g. Claude) — the build_*_prompt seam and the
plain text-in/JSON-out contract keep that swap localized.
"""

import json
from dataclasses import asdict
from pathlib import Path

from google.adk.agents import Agent

from worldcup_recap.providers.base import CollectedData

_SYSTEM_PROMPT = (Path(__file__).parent.parent / "prompts" / "structure.md").read_text()

structure_agent = Agent(
    name="wc_structure_agent",
    model="gemini-2.5-flash",
    instruction=_SYSTEM_PROMPT,
)


def build_structure_prompt(data: CollectedData) -> str:
    """Build the user-turn message for the structure agent."""
    payload = {
        "date": data.date,
        "matches": [
            {
                "stage": m.stage,
                "home_team": m.home_team,
                "away_team": m.away_team,
                "score": f"{m.home_score}-{m.away_score}",
                "status": m.status,
                "timeline": m.timeline,
                "top_performers": m.top_performers,
                "venue": m.venue,
            }
            for m in data.matches
        ],
        "standings": data.standings[:8],
        "upcoming": [asdict(p) for p in data.upcoming],
    }
    return f"Structure this World Cup match-day data:\n\n{json.dumps(payload, indent=2, ensure_ascii=False)}"
