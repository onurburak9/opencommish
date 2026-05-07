"""Output helpers: build final JSON, render Markdown, validate schema."""

from datetime import datetime, timezone

from nba_recap.collect import CollectedData


_REQUIRED_KEYS = {"recap_id", "date", "generated_at", "metadata", "content"}


def build_recap_id(date_str: str) -> str:
    return f"nba-daily-{date_str}"


def validate_output(output: dict) -> None:
    """Raise ValueError if any required top-level key is missing."""
    missing = _REQUIRED_KEYS - set(output.keys())
    if missing:
        raise ValueError(f"Missing required field(s): {', '.join(sorted(missing))}")


def _render_section(section: dict) -> list[str]:
    """Render a single section to Markdown lines."""
    lines: list[str] = []
    section_type = section.get("type", "")
    lines.append(f"## {section.get('title', '')}")
    lines.append("")

    if section.get("narrative"):
        lines.append(section["narrative"])
        lines.append("")

    media = section.get("media", {})

    if section_type == "game_of_night":
        if media.get("recap_url"):
            lines.append(f"[Full recap]({media['recap_url']})")
        if media.get("highlight_url"):
            lines.append(f"[Highlights]({media['highlight_url']})")
        if media.get("recap_url") or media.get("highlight_url"):
            lines.append("")

    elif section_type == "player_spotlight":
        for player in section.get("players", []):
            name = player.get("name", "")
            line = player.get("line", "")
            context = player.get("context", "")
            player_media = player.get("media", {})
            headshot = player_media.get("headshot_url")
            interview = player_media.get("interview_url")
            # Name as link to headshot if available
            name_md = f"[{name}]({headshot})" if headshot else name
            parts = [f"**{name_md}**", line, context]
            lines.append(" — ".join(p for p in parts if p))
            if interview:
                lines.append(f"  [Post-game interview]({interview})")
        lines.append("")

    elif section_type == "storylines":
        for story in section.get("stories", []):
            headline = story.get("headline", "")
            summary = story.get("summary", "")
            news_url = story.get("news_url")
            headline_md = f"[{headline}]({news_url})" if news_url else headline
            lines.append(f"**{headline_md}** — {summary}")
        lines.append("")

    elif section_type == "quick_hits":
        for game in section.get("games", []):
            matchup = game.get("matchup", "")
            note = game.get("note", "")
            recap_url = game.get("recap_url")
            matchup_md = f"[{matchup}]({recap_url})" if recap_url else matchup
            lines.append(f"- {matchup_md} — {note}")
        lines.append("")

    elif section_type == "looking_ahead":
        for upcoming in section.get("upcoming", []):
            home = upcoming.get("home", "")
            away = upcoming.get("away", "")
            time_et = upcoming.get("time_et", "")
            storyline = upcoming.get("storyline", "")
            lines.append(f"- **{away} @ {home}** {time_et} — {storyline}")
        lines.append("")

    return lines


def render_markdown(output: dict) -> str:
    """Render the final output dict as a Markdown string."""
    content = output.get("content", {})
    date_str = output.get("date", "")
    lines = [
        f"# {content.get('headline', 'NBA Daily Recap')}",
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
    subagents_spawned: int,
) -> dict:
    output = {
        "recap_id": build_recap_id(data.date),
        "date": data.date,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "metadata": {
            "games_count": len(data.games),
            "sources_used": data.sources_used,
            "subagents_spawned": subagents_spawned,
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
