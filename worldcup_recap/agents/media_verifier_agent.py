"""ADK Agent: verifies a found media link is relevant to the need.

Uses Gemini 2.5 Flash (free tier) for the MVP; a future iteration may switch to a
stronger model that fetches the page to verify content directly.
"""

from pathlib import Path

from google.adk.agents import Agent

_INSTRUCTION = (Path(__file__).parent.parent / "prompts" / "media_verifier.md").read_text()

media_verifier_agent = Agent(
    name="wc_media_verifier",
    model="gemini-2.5-flash",
    instruction=_INSTRUCTION,
)


def build_verifier_prompt(need: dict, candidate: dict) -> str:
    """Build the verifier user-turn message from the need + the found candidate."""
    return (
        "Need: " + str(need) + "\n"
        "Candidate: url=" + str(candidate.get("url"))
        + " | title=" + str(candidate.get("title"))
        + " | channel=" + str(candidate.get("channel"))
        + " | source=" + str(candidate.get("source")) + "\n"
        "Is this candidate relevant AND from an acceptable (official, non-AI) source? "
        "Respond with the JSON verdict."
    )
