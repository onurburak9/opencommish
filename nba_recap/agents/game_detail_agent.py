"""ADK Agent: searches the web for game recap articles and highlight links."""

from google.adk.agents import Agent
from google.adk.tools import google_search


_INSTRUCTION = """
You are a sports researcher. Given an NBA game matchup and date, use google_search to find:
1. An official game recap article URL (ESPN, NBA.com, or The Athletic)
2. A YouTube highlight video URL for the game

Return a JSON object with exactly these keys:
{
  "recap_url": "<url or null>",
  "highlight_url": "<url or null>",
  "source": "<site name>"
}

Only return real URLs you found — never fabricate them. If not found, use null.
Return ONLY the JSON object, no explanation, no markdown fences.
"""


game_detail_agent = Agent(
    name="nba_game_detail_fetcher",
    model="gemini-2.0-flash",
    instruction=_INSTRUCTION,
    tools=[google_search],
)


def build_game_search_prompt(home_team: str, away_team: str, date: str) -> str:
    """Build the user-turn message for the game detail agent."""
    return (
        f"Find recap article and highlight video for NBA game: "
        f"{away_team} @ {home_team} on {date}. "
        f"Search: '{away_team} vs {home_team} {date} NBA recap highlights'."
    )
