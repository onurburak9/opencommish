"""ADK Agent: writes engaging English prose and compiles the recap JSON.

Uses Gemini 2.5 Flash (free tier) for the MVP; a future iteration may switch to a
stronger model. parse_synthesis_response keeps the JSON-out contract stable.
"""

import json
from pathlib import Path

from google.adk.agents import Agent

_SYSTEM_PROMPT = (Path(__file__).parent.parent / "prompts" / "synthesis.md").read_text()

synthesis_agent = Agent(
    name="wc_synthesis_agent",
    model="gemini-2.5-flash",
    instruction=_SYSTEM_PROMPT,
)


def parse_synthesis_response(response_text: str) -> dict:
    """Parse the synthesis JSON, stripping markdown fences if present."""
    text = response_text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        inner = lines[1:]
        if inner and inner[-1].strip() == "```":
            inner = inner[:-1]
        text = "\n".join(inner).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {
            "headline": "World Cup Daily Recap",
            "summary": "A full day of World Cup action.",
            "sections": [],
        }
