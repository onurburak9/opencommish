"""Static FIFA World Cup 2026 phase/bracket schedule + group composition.

Group composition is also fetched live from ESPN (authoritative; see
providers/espn.py:fetch_group_map). This static GROUPS map is the fallback when the
live fetch is unavailable. Source: ESPN table endpoint (league=fifa.world), 2026.
"""


GROUPS: dict[str, list[str]] = {
    "Group A": ["Mexico", "South Korea", "Czechia", "South Africa"],
    "Group B": ["Switzerland", "Canada", "Qatar", "Bosnia-Herzegovina"],
    "Group C": ["Scotland", "Morocco", "Brazil", "Haiti"],
    "Group D": ["United States", "Australia", "Türkiye", "Paraguay"],
    "Group E": ["Germany", "Ivory Coast", "Ecuador", "Curaçao"],
    "Group F": ["Sweden", "Japan", "Netherlands", "Tunisia"],
    "Group G": ["New Zealand", "Iran", "Belgium", "Egypt"],
    "Group H": ["Uruguay", "Saudi Arabia", "Spain", "Cape Verde"],
    "Group I": ["Norway", "France", "Senegal", "Iraq"],
    "Group J": ["Argentina", "Austria", "Jordan", "Algeria"],
    "Group K": ["Colombia", "Congo DR", "Portugal", "Uzbekistan"],
    "Group L": ["England", "Ghana", "Panama", "Croatia"],
}

# Inclusive date windows (YYYY-MM-DD) -> phase. Source: FIFA WC 2026 schedule.
PHASE_SCHEDULE: list[tuple[str, str, str]] = [
    ("2026-06-11", "2026-06-27", "Group Stage"),
    ("2026-06-28", "2026-07-03", "Round of 32"),
    ("2026-07-04", "2026-07-07", "Round of 16"),
    ("2026-07-09", "2026-07-11", "Quarterfinal"),
    ("2026-07-14", "2026-07-15", "Semifinal"),
    ("2026-07-18", "2026-07-18", "Third-Place Play-off"),
    ("2026-07-19", "2026-07-19", "Final"),
]

# Knockout bracket progression (for phase/lookup downstream).
KNOCKOUT_ROUNDS: list[str] = [
    "Round of 32", "Round of 16", "Quarterfinal", "Semifinal", "Final",
]


def _static_group_for(team: str) -> str | None:
    for group, teams in GROUPS.items():
        if team in teams:
            return group
    return None


def phase_for_date(date_str: str) -> str | None:
    """Return the tournament phase for a YYYY-MM-DD date, or None if outside the schedule."""
    for start, end, phase in PHASE_SCHEDULE:
        if start <= date_str <= end:
            return phase
    return None


def stage_for(home: str, away: str, date_str: str,
              group_map: dict[str, str] | None = None) -> str:
    """Resolve a match's stage label.

    During the group stage returns 'Group X' (group_map from ESPN takes precedence over
    the static GROUPS fallback); during knockouts returns the round name; '' if unknown.
    """
    phase = phase_for_date(date_str)
    if phase == "Group Stage":
        gm = group_map or {}
        return (gm.get(home) or gm.get(away)
                or _static_group_for(home) or _static_group_for(away) or "Group Stage")
    return phase or ""
