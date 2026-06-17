"""Shared data model + StatsProvider interface for the World Cup recap pipeline.

Dataclasses live here (not in collect.py) so both espn.py and collect.py can
import them without a circular dependency.
"""

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class RawMatch:
    match_id: str
    stage: str
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    status: str
    timeline: list[dict]        # {minute, type, player, text, scoring_play}
    top_performers: list[dict]  # {name, team, goals, saves, note}
    player_stats: list[dict]    # {name, team, position, starter, stats: {name: value}}
    venue: str
    attendance: int | None
    espn_recap_url: str | None
    espn_videos: list[dict]     # {headline, url, thumbnail, duration}
    news: list[dict]            # {headline, url, published}
    team_meta: dict = field(default_factory=dict)


@dataclass
class PreviewMatch:
    match_id: str
    stage: str
    home_team: str
    away_team: str
    kickoff: str                # ISO datetime
    odds: dict | None
    head_to_head: list[dict]    # historical meetings
    home_form: list[str]        # recent results e.g. ["W","D","L"]
    away_form: list[str]
    news: list[dict]


@dataclass
class CollectedData:
    date: str
    matches: list[RawMatch]
    standings: list[dict]
    upcoming: list[PreviewMatch]
    sources_used: list[str] = field(default_factory=list)


class StatsProvider(Protocol):
    """A pluggable data source. ESPN is the only implementation in Phase 1."""

    name: str

    def matches_for_date(self, date: str, tz: str) -> list[RawMatch]: ...
    def upcoming(self, date: str, tz: str) -> list[PreviewMatch]: ...
    def standings(self) -> list[dict]: ...
