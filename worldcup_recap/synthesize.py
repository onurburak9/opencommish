"""Output helpers: build final JSON, validate, render Markdown."""

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
        lines.append("")
    elif section_type == "results_roundup":
        for game in section.get("games", []):
            lines.append(f"- {game.get('matchup', '')} — {game.get('note', '')}")
        lines.append("")
    elif section_type == "player_spotlight":
        for player in section.get("players", []):
            name = player.get("name", "")
            line = player.get("line", "")
            context = player.get("context", "")
            parts = [f"**{name}**", line, context]
            lines.append(" — ".join(p for p in parts if p))
            interview = player.get("media", {}).get("interview_url")
            if interview:
                lines.append(f"  [Interview]({interview})")
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
    output = {
        "recap_id": build_recap_id(data.date),
        "date": data.date,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "metadata": {
            "matches_count": len(data.matches),
            "sources_used": data.sources_used,
            "verification": verification,
            "generation_time_seconds": round(generation_time, 1),
        },
        "content": {
            "headline": synthesized.get("headline", ""),
            "summary": synthesized.get("summary", ""),
            "sections": synthesized.get("sections", []),
        },
    }
    validate_output(output)
    return output
