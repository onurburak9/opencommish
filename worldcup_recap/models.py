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

from pydantic import BaseModel, ConfigDict, Field

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
    sections: list = Field(default_factory=list)  # replaced with list[Section] in Task 2


class RecapOutput(BaseModel):
    model_config = _CONFIG
    recap_id: str = ""
    date: str = ""
    generated_at: str = ""
    metadata: Metadata = Field(default_factory=Metadata)
    content: Content = Field(default_factory=Content)
    source_data_file: str = ""
