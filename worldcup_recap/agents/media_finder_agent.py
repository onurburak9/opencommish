"""ADK Agent: finds a single best media URL for a declared media need.

Uses Gemini 2.5 Flash + google_search (free tier) for the MVP; a future iteration
may switch to a stronger model / agent harness with real page-fetch verification.
"""

from pathlib import Path

from google.adk.agents import Agent
from google.adk.tools import google_search

_INSTRUCTION = (Path(__file__).parent.parent / "prompts" / "media_finder.md").read_text()

media_finder_agent = Agent(
    name="wc_media_finder",
    model="gemini-2.5-flash",
    instruction=_INSTRUCTION,
    tools=[google_search],
)


def build_finder_prompt(need: dict, feedback: str | None = None) -> str:
    """Build the finder user-turn message from a media need (+ optional feedback)."""
    kind = need.get("kind", "media")
    subject = need.get("subject", "")
    context = need.get("context", "")
    base = (
        f"Find a {kind} link for World Cup: subject='{subject}', context='{context}'. "
        f"Search for the official {kind} for this."
    )
    if feedback:
        base += f"\nPrevious attempt was rejected: {feedback}. Refine the search accordingly."
    return base
