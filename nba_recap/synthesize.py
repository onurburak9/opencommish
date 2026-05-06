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
        lines.append(f"## {section.get('title', '')}")
        lines.append("")
        if section.get("narrative"):
            lines.append(section["narrative"])
            lines.append("")
        media = section.get("media", {})
        if media.get("recap_url"):
            lines.append(f"[Full recap]({media['recap_url']})")
            lines.append("")
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
