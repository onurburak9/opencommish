"""ADK Agent: searches the web for player headshots and post-game interviews."""

from google.adk.agents import Agent
from google.adk.tools import google_search


_INSTRUCTION = """
You are a sports media researcher. Given an NBA player's name, team, and stat line, use google_search to find:
1. An official player headshot or action photo URL (prefer cdn.nba.com or espn.com)
2. A post-game interview or highlight clip URL (prefer YouTube or ESPN)

Return a JSON object with exactly these keys:
{
  "headshot_url": "<url or null>",
  "interview_url": "<url or null>"
}

Only return real URLs you found — never fabricate them. If not found, use null.
Return ONLY the JSON object, no explanation, no markdown fences.
"""


player_media_agent = Agent(
    name="nba_player_media_finder",
    model="gemini-2.0-flash",
    instruction=_INSTRUCTION,
    tools=[google_search],
)


def build_player_search_prompt(player_name: str, team: str, stat_line: str) -> str:
    """Build the user-turn message for the player media agent."""
    return (
        f"Find headshot image and post-game interview for NBA player: "
        f"{player_name} ({team}), who had {stat_line} tonight. "
        f"Search: '{player_name} NBA headshot' and '{player_name} post-game interview 2026'."
    )
