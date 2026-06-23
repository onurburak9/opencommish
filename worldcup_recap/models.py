"""Pydantic v2 contract models for the World Cup daily recap JSON.

Single source of truth for `schemas/recap_output.json`. Every model allows
extra fields (so nothing useful is silently dropped) and gives every field an
empty/`None` default (so a dumped recap always has the complete, predictable
shape downstream HTML/video renderers rely on).

Sections (the polymorphic, LLM-generated parts) live below the deterministic
core and are added/validated via `coerce_sections`.
"""

from __future__ import annotations

import logging

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

logger = logging.getLogger(__name__)

_CONFIG = ConfigDict(extra="allow")


# ---------------------------------------------------------------------------
# Verification telemetry (built deterministically by the pipeline)
# ---------------------------------------------------------------------------

class VerificationAttempt(BaseModel):
    model_config = _CONFIG
    attempt: int = 0
    raw_url: str | None = None
    resolved_url: str | None = None
    outcome: str = ""
    reason: str = ""


class VerificationNeed(BaseModel):
    model_config = _CONFIG
    kind: str = ""
    subject: str = ""
    context: str = ""


class VerificationDetail(BaseModel):
    model_config = _CONFIG
    owner: str = ""
    need: VerificationNeed = Field(default_factory=VerificationNeed)
    status: str = ""
    accepted_url: str | None = None
    attempts: list[VerificationAttempt] = Field(default_factory=list)


class Verification(BaseModel):
    model_config = _CONFIG
    searched: int = 0
    accepted: int = 0
    rejected: int = 0
    dropped: int = 0
    details: list[VerificationDetail] = Field(default_factory=list)


class Metadata(BaseModel):
    model_config = _CONFIG
    matches_count: int = 0
    sources_used: list[str] = Field(default_factory=list)
    timezone: str = ""
    verification: Verification = Field(default_factory=Verification)
    generation_time_seconds: float = 0.0


# ---------------------------------------------------------------------------
# Games (deterministic + inclusive: timeline, top performers, attendance)
# ---------------------------------------------------------------------------

class TeamSide(BaseModel):
    model_config = _CONFIG
    team: str = ""
    score: int = 0
    logo_url: str | None = None
    team_url: str | None = None


class GameMedia(BaseModel):
    model_config = _CONFIG
    recap_url: str | None = None
    highlight_url: str | None = None


class Scorer(BaseModel):
    model_config = _CONFIG
    player: str = ""
    minute: str = ""
    profile_url: str | None = None


class Performer(BaseModel):
    model_config = _CONFIG
    name: str = ""
    team: str = ""
    goals: int = 0
    saves: int = 0
    note: str = ""
    profile_url: str | None = None
    headshot_url: str | None = None


class TimelineEvent(BaseModel):
    model_config = _CONFIG
    minute: str = ""
    type: str = ""
    player: str = ""
    text: str = ""
    scoring_play: bool = False


class NewsItem(BaseModel):
    model_config = _CONFIG
    headline: str = ""
    url: str | None = None
    published: str = ""


class Game(BaseModel):
    model_config = _CONFIG
    match_id: str = ""
    stage: str = ""
    status: str = ""
    home: TeamSide = Field(default_factory=TeamSide)
    away: TeamSide = Field(default_factory=TeamSide)
    venue: str = ""
    attendance: int | None = None
    media: GameMedia = Field(default_factory=GameMedia)
    scorers: list[Scorer] = Field(default_factory=list)
    top_performers: list[Performer] = Field(default_factory=list)
    timeline: list[TimelineEvent] = Field(default_factory=list)
    news: list[NewsItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Content + top-level document
# Sections (content.sections) are appended in Task 2.
# ---------------------------------------------------------------------------

class Content(BaseModel):
    model_config = _CONFIG
    headline: str = ""
    summary: str = ""
    games: list[Game] = Field(default_factory=list)
    sections: list[Section] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Sections (polymorphic, discriminated union on `type`)
# ---------------------------------------------------------------------------

class _SectionBase(BaseModel):
    model_config = _CONFIG
    title: str = ""
    narrative: str = ""


class MatchOfDaySection(_SectionBase):
    type: Literal["match_of_day"] = "match_of_day"
    home_team: str = ""
    away_team: str = ""
    score: str = ""
    facts: str = ""
    match_id: str | None = None


class ResultGame(BaseModel):
    model_config = _CONFIG
    matchup: str = ""
    note: str = ""
    match_id: str | None = None


class ResultsRoundupSection(_SectionBase):
    type: Literal["results_roundup"] = "results_roundup"
    games: list[ResultGame] = Field(default_factory=list)


class PlayerMedia(BaseModel):
    model_config = _CONFIG
    profile_url: str | None = None
    headshot_url: str | None = None
    interview_url: str | None = None


class SpotlightPlayer(BaseModel):
    model_config = _CONFIG
    name: str = ""
    team: str = ""
    line: str = ""
    context: str = ""
    media: PlayerMedia = Field(default_factory=PlayerMedia)


class PlayerSpotlightSection(_SectionBase):
    type: Literal["player_spotlight"] = "player_spotlight"
    players: list[SpotlightPlayer] = Field(default_factory=list)


class GroupWatchSection(_SectionBase):
    type: Literal["group_watch"] = "group_watch"
    notes: str = ""


class Story(BaseModel):
    model_config = _CONFIG
    headline: str = ""
    summary: str = ""


class StorylinesSection(_SectionBase):
    type: Literal["storylines"] = "storylines"
    stories: list[Story] = Field(default_factory=list)


class OddsSummary(BaseModel):
    model_config = _CONFIG
    favorite: str | None = None
    line: str | None = None
    over_under: float | None = None


class UpcomingFixture(BaseModel):
    model_config = _CONFIG
    home: str = ""
    away: str = ""
    kickoff: str = ""
    storyline: str = ""
    odds: OddsSummary | None = None
    news: list[NewsItem] = Field(default_factory=list)


class LookingAheadSection(_SectionBase):
    type: Literal["looking_ahead"] = "looking_ahead"
    upcoming: list[UpcomingFixture] = Field(default_factory=list)


Section = Annotated[
    Union[
        MatchOfDaySection,
        ResultsRoundupSection,
        PlayerSpotlightSection,
        GroupWatchSection,
        StorylinesSection,
        LookingAheadSection,
    ],
    Field(discriminator="type"),
]

_SECTION_ADAPTER = TypeAdapter(Section)


def coerce_sections(raw_sections: list[dict]) -> list[Section]:
    """Validate each section on its own; drop (and log) any that can't be repaired.

    An unknown `type`, a missing `type`, or an otherwise-invalid section is
    dropped so a single malformed LLM section never fails the whole document.
    """
    coerced: list[Section] = []
    for raw in raw_sections or []:
        try:
            coerced.append(_SECTION_ADAPTER.validate_python(raw))
        except ValidationError as exc:
            logged_type = (
                raw.get("type") if isinstance(raw, dict)
                else f"<non-dict {type(raw).__name__}>"
            )
            logger.warning(
                "Dropping invalid recap section (type=%r): %s",
                logged_type, exc,
            )
    return coerced


class RecapOutput(BaseModel):
    model_config = _CONFIG
    recap_id: str = ""
    date: str = ""
    generated_at: str = ""
    metadata: Metadata = Field(default_factory=Metadata)
    content: Content = Field(default_factory=Content)
    source_data_file: str = ""


RecapOutput.model_rebuild()
Content.model_rebuild()
