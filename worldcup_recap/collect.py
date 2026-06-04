"""Phase 1: World Cup data collection. Pure orchestration over a StatsProvider.

No LLM. ESPN is the only provider in Phase 1; the StatsProvider seam lets a
second source (e.g. API-Football) be added later without changing this file.
"""

from worldcup_recap.providers.base import CollectedData, StatsProvider
from worldcup_recap.providers.espn import EspnProvider


def get_provider() -> StatsProvider:
    """Return the active stats provider. ESPN-only for now."""
    return EspnProvider()


def collect(target_date: str) -> CollectedData:
    """Fetch all World Cup data for target_date (YYYY-MM-DD). No LLM calls."""
    print(f"Collecting World Cup data for {target_date}...")
    provider = get_provider()
    matches = provider.matches_for_date(target_date)
    upcoming = provider.upcoming(target_date)
    standings = provider.standings()
    print(f"  {len(matches)} matches, {len(upcoming)} upcoming fixtures")
    return CollectedData(
        date=target_date,
        matches=matches,
        standings=standings,
        upcoming=upcoming,
        sources_used=[provider.name],
    )
