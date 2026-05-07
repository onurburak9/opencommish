"""ADK Agent: writes final narrative prose and compiles the JSON output."""

import json
from pathlib import Path

from google.adk.agents import Agent


_SYSTEM_PROMPT = (Path(__file__).parent.parent / "prompts" / "synthesis.md").read_text()


synthesis_agent = Agent(
    name="nba_synthesis_agent",
    model="gemini-2.0-flash",
    instruction=_SYSTEM_PROMPT,
)


def parse_synthesis_response(response_text: str) -> dict:
    """Parse the synthesis agent's JSON response, stripping markdown fences if present."""
    text = response_text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # Strip opening fence line and closing fence line
        inner_lines = lines[1:]
        if inner_lines and inner_lines[-1].strip() == "```":
            inner_lines = inner_lines[:-1]
        text = "\n".join(inner_lines).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {
            "headline": "NBA Daily Recap",
            "summary": "A full night of NBA action.",
            "sections": [],
        }
