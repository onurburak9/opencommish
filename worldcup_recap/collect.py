"""Phase 1: World Cup data collection. Pure orchestration over a StatsProvider.

No LLM. ESPN is the only provider in Phase 1; the StatsProvider seam lets a
second source (e.g. API-Football) be added later without changing this file.
"""

import os

from worldcup_recap.providers.base import CollectedData, StatsProvider
from worldcup_recap.providers.espn import EspnProvider


def get_provider() -> StatsProvider:
    """Return the active stats provider. ESPN-only for now."""
    return EspnProvider()


def collect(target_date: str, tz: str | None = None) -> CollectedData:
    """Fetch all World Cup data for target_date (YYYY-MM-DD) in timezone tz. No LLM."""
    tz = tz or os.getenv("WC_TZ", "America/Los_Angeles")
    print(f"Collecting World Cup data for {target_date} ({tz})...")
    provider = get_provider()
    matches = provider.matches_for_date(target_date, tz)
    upcoming = provider.upcoming(target_date, tz)
    standings = provider.standings()
    print(f"  {len(matches)} matches, {len(upcoming)} upcoming fixtures")
    return CollectedData(
        date=target_date,
        matches=matches,
        standings=standings,
        upcoming=upcoming,
        sources_used=[provider.name],
        timezone=tz,
    )
