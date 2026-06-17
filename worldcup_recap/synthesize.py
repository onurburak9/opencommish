"""Output helpers: build final JSON, validate, render Markdown."""

from dataclasses import asdict
from datetime import datetime, timezone

from worldcup_recap.providers.base import CollectedData

_REQUIRED_KEYS = {"recap_id", "date", "generated_at", "metadata", "content"}


def build_recap_id(date_str: str) -> str:
    return f"worldcup-daily-{date_str}"


def validate_output(output: dict) -> None:
    """Raise ValueError if any required top-level key is missing."""
    missing = _REQUIRED_KEYS - set(output.keys())
    if missing:
        raise ValueError(f"Missing required field(s): {', '.join(sorted(missing))}")


def _render_section(section: dict) -> list[str]:
    """Render a single section to Markdown lines."""
    lines: list[str] = [f"## {section.get('title', '')}", ""]
    section_type = section.get("type", "")
    if section.get("narrative"):
        lines.append(section["narrative"])
        lines.append("")

    media = section.get("media", {})
    if section_type == "match_of_day":
        if media.get("recap_url"):
            lines.append(f"[Full recap]({media['recap_url']})")
        if media.get("highlight_url"):
            lines.append(f"[Highlights]({media['highlight_url']})")
        if media.get("recap_url") or media.get("highlight_url"):
            lines.append("")
        if media.get("home_team_url") or media.get("away_team_url"):
            teams_line = []
            if media.get("home_team_url"):
                teams_line.append(f"[{section.get('home_team', 'Home')}]({media['home_team_url']})")
            if media.get("away_team_url"):
                teams_line.append(f"[{section.get('away_team', 'Away')}]({media['away_team_url']})")
            lines.append("Teams: " + " vs ".join(teams_line))
            lines.append("")
    elif section_type == "results_roundup":
        for game in section.get("games", []):
            lines.append(f"- {game.get('matchup', '')} — {game.get('note', '')}")
        lines.append("")
    elif section_type == "player_spotlight":
        for player in section.get("players", []):
            name = player.get("name", "")
            profile = player.get("media", {}).get("profile_url")
            name_md = f"[{name}]({profile})" if profile else f"**{name}**"
            line = player.get("line", "")
            context = player.get("context", "")
            parts = [name_md, line, context]
            lines.append(" — ".join(p for p in parts if p))
            pmedia = player.get("media", {})
            links = []
            if pmedia.get("headshot_url"):
                links.append(f"[Photo]({pmedia['headshot_url']})")
            if pmedia.get("interview_url"):
                links.append(f"[Interview]({pmedia['interview_url']})")
            if links:
                lines.append("  " + " · ".join(links))
        lines.append("")
    elif section_type == "storylines":
        for story in section.get("stories", []):
            lines.append(f"**{story.get('headline', '')}** — {story.get('summary', '')}")
        lines.append("")
    elif section_type == "looking_ahead":
        for up in section.get("upcoming", []):
            matchup = f"{up.get('away', '')} @ {up.get('home', '')}"
            lines.append(f"- **{matchup}** {up.get('kickoff', '')} — {up.get('storyline', '')}")
        lines.append("")
    return lines


def render_markdown(output: dict) -> str:
    """Render the final output dict as a Markdown string."""
    content = output.get("content", {})
    date_str = output.get("date", "")
    lines = [
        f"# {content.get('headline', 'World Cup Daily Recap')}",
        f"*{date_str}*",
        "",
        content.get("summary", ""),
        "",
    ]
    for section in content.get("sections", []):
        lines.extend(_render_section(section))
    return "\n".join(lines)


def build_final_output(
    data: CollectedData,
    synthesized: dict,
    generation_time: float,
    verification: dict,
) -> dict:
    """Assemble the schema-valid final recap dict from collected + synthesized data."""
    output = {
        "recap_id": build_recap_id(data.date),
        "date": data.date,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "metadata": {
            "matches_count": len(data.matches),
            "sources_used": data.sources_used,
            "timezone": data.timezone,
            "verification": verification,
            "generation_time_seconds": round(generation_time, 1),
        },
        "content": {
            "headline": synthesized.get("headline", ""),
            "summary": synthesized.get("summary", ""),
            "sections": synthesized.get("sections", []),
        },
        "source_data_file": f"{data.date}.source.json",
    }
    validate_output(output)
    return output


def build_source_data(data: CollectedData) -> dict:
    """The full collected game data, written to a standalone {date}.source.json file."""
    return {
        "date": data.date,
        "timezone": data.timezone,
        "sources_used": data.sources_used,
        "matches": [asdict(m) for m in data.matches],
        "standings": data.standings,
        "upcoming": [asdict(p) for p in data.upcoming],
    }
