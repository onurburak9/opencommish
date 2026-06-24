"""Output helpers: build final JSON, validate, render Markdown."""

import logging
import re
from dataclasses import asdict
from datetime import datetime, timezone

from worldcup_recap.models import RecapOutput, coerce_sections
from worldcup_recap.providers.base import CollectedData

logger = logging.getLogger(__name__)


def build_recap_id(date_str: str) -> str:
    return f"worldcup-daily-{date_str}"


def validate_output(output: dict) -> None:
    """Validate a recap dict against the RecapOutput contract (raises on irreparable input).

    Note: a few deterministic-core fields (e.g. TeamSide.score, TimelineEvent.minute)
    have before-validators that coerce common bad values rather than raise.
    """
    RecapOutput.model_validate(output)


# ---------------------------------------------------------------------------
# Normalisation helpers for team-name matching
# ---------------------------------------------------------------------------

def _norm(s: str) -> str:
    """Normalize a team name for matching (lowercase, letters only)."""
    return re.sub(r"[^a-z]", "", (s or "").lower())


def _match_id_for(home: str, away: str, data: "CollectedData") -> str | None:
    """Find the collected match_id for a home/away pair (orientation-independent)."""
    want = {_norm(home), _norm(away)}
    for m in data.matches:
        if {_norm(m.home_team), _norm(m.away_team)} == want:
            return m.match_id
    return None


def _match_id_from_text(text: str, data: "CollectedData") -> str | None:
    """Find a match_id by checking which collected match's both team names appear in text."""
    n = _norm(text)
    for m in data.matches:
        if _norm(m.home_team) and _norm(m.away_team) and _norm(m.home_team) in n and _norm(m.away_team) in n:
            return m.match_id
    return None


def _scorers_for(match) -> list[dict]:
    """Goal events from the timeline with the scorer's profile link."""
    profile = {p.get("name"): p.get("profile_url") for p in match.player_stats}
    out = []
    for ev in match.timeline:
        t = ev.get("type", "")
        if "Goal" in t and "Own Goal" not in t and ev.get("player"):
            out.append({
                "player": ev["player"],
                "minute": ev.get("minute", ""),
                "profile_url": profile.get(ev["player"]),
            })
    return out


def _top_performers_for(match) -> list[dict]:
    """Top performers with the player's profile link enriched from player_stats."""
    profile = {p.get("name"): p.get("profile_url") for p in match.player_stats}
    out = []
    for p in match.top_performers or []:
        tp = dict(p)
        if not tp.get("profile_url") and profile.get(p.get("name")):
            tp["profile_url"] = profile[p["name"]]
        out.append(tp)
    return out


def build_games(data: "CollectedData") -> list[dict]:
    """Deterministic, complete per-game objects for ALL of the day's matches."""
    games = []
    for m in data.matches:
        tm = m.team_meta or {}
        home_meta = tm.get(m.home_team, {})
        away_meta = tm.get(m.away_team, {})
        highlight = None
        for v in m.espn_videos or []:
            if v.get("web") or v.get("url"):
                highlight = v.get("web") or v.get("url")
                break
        games.append({
            "match_id": m.match_id,
            "stage": m.stage,
            "status": m.status,
            "home": {
                "team": m.home_team,
                "score": m.home_score,
                "logo_url": home_meta.get("logo_url"),
                "team_url": home_meta.get("profile_url"),
            },
            "away": {
                "team": m.away_team,
                "score": m.away_score,
                "logo_url": away_meta.get("logo_url"),
                "team_url": away_meta.get("profile_url"),
            },
            "venue": m.venue,
            "attendance": m.attendance,
            "media": {"recap_url": m.espn_recap_url, "highlight_url": highlight},
            "scorers": _scorers_for(m),
            "top_performers": _top_performers_for(m),
            "timeline": m.timeline,
            "news": (m.news or [])[:3],
        })
    return games


def _summarize_odds(odds: dict | None, home: str, away: str) -> dict | None:
    """Compact odds for the recap: favorite, line, over/under. Drops raw provider/team noise."""
    if not odds:
        return None
    favorite = None
    if (odds.get("homeTeamOdds") or {}).get("favorite"):
        favorite = home
    elif (odds.get("awayTeamOdds") or {}).get("favorite"):
        favorite = away
    summary = {
        "favorite": favorite,
        "line": odds.get("details"),
        "over_under": odds.get("overUnder"),
    }
    summary = {k: v for k, v in summary.items() if v is not None}
    return summary or None


def _enrich_upcoming(upcoming_list: list[dict], data: "CollectedData") -> list[dict]:
    """Add odds + top news to looking_ahead upcoming entries from the collected preview."""
    out = []
    for up in upcoming_list:
        e = dict(up)
        want = {_norm(up.get("home", "")), _norm(up.get("away", ""))}
        for pm in data.upcoming:
            if {_norm(pm.home_team), _norm(pm.away_team)} == want:
                summarized = _summarize_odds(pm.odds, up.get("home", ""), up.get("away", ""))
                if summarized:
                    e["odds"] = summarized
                if pm.news:
                    rel = [
                        n for n in pm.news
                        if (_norm(pm.home_team) and _norm(pm.home_team) in _norm(n.get("headline", "")))
                        or (_norm(pm.away_team) and _norm(pm.away_team) in _norm(n.get("headline", "")))
                    ]
                    if rel:
                        e["news"] = [{"headline": n.get("headline"), "url": n.get("url")} for n in rel[:2]]
                break
        out.append(e)
    return out


def _clean_sections(sections: list[dict], data: "CollectedData") -> list[dict]:
    """Strip internal media_needs / empty section media; add match_id links; enrich look-ahead."""
    cleaned = []
    for raw in sections:
        s = {k: v for k, v in raw.items() if k != "media_needs"}
        s.pop("media", None)  # game media now lives in content.games; player media stays on players
        t = s.get("type")
        if t == "match_of_day":
            s["match_id"] = _match_id_for(s.get("home_team", ""), s.get("away_team", ""), data)
        elif t == "results_roundup":
            s["games"] = [
                {**{k: v for k, v in g.items()}, "match_id": _match_id_from_text(g.get("matchup", ""), data)}
                for g in s.get("games", [])
            ]
        elif t == "player_spotlight":
            s["players"] = [{k: v for k, v in p.items() if k != "media_needs"} for p in s.get("players", [])]
        elif t == "looking_ahead":
            s["upcoming"] = _enrich_upcoming(s.get("upcoming", []), data)
        cleaned.append(s)
    return cleaned


def build_final_output(
    data: CollectedData,
    synthesized: dict,
    generation_time: float,
    verification: dict,
) -> dict:
    """Assemble the schema-valid final recap dict from collected + synthesized data."""
    games = build_games(data)
    games_by_id = {g["match_id"]: g for g in games}
    all_sections = synthesized.get("sections", [])
    raw_sections = [s for s in all_sections if isinstance(s, dict)]
    dropped_non_dict = len(all_sections) - len(raw_sections)
    if dropped_non_dict:
        logger.warning(
            "Dropped %d non-dict element(s) from sections list before processing.",
            dropped_non_dict,
        )
    # Prefer the verified/searched highlight for the match_of_day game when present.
    for s in raw_sections:
        if s.get("type") == "match_of_day":
            mid = _match_id_for(s.get("home_team", ""), s.get("away_team", ""), data)
            searched = (s.get("media") or {}).get("highlight_url")
            if mid in games_by_id and searched:
                games_by_id[mid]["media"]["highlight_url"] = searched
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
            "games": games,
            "sections": coerce_sections(_clean_sections(raw_sections, data)),
        },
        "source_data_file": f"{data.date}.source.json",
    }
    return RecapOutput.model_validate(output).model_dump(mode="json")


# ---------------------------------------------------------------------------
# Markdown renderer
# ---------------------------------------------------------------------------

def _fmt_matchup(game: dict) -> str:
    h, a = game["home"], game["away"]
    return f"{a['team']} {a['score']}-{h['score']} {h['team']}"


def _game_link_lines(game: dict) -> list[str]:
    lines: list[str] = []
    media = game.get("media", {})
    parts = []
    if media.get("recap_url"):
        parts.append(f"[Recap]({media['recap_url']})")
    if media.get("highlight_url"):
        parts.append(f"[Highlights]({media['highlight_url']})")
    if parts:
        lines.append(" · ".join(parts))
    if game.get("scorers"):
        scs = ", ".join(f"{s['player']} {s['minute']}".strip() for s in game["scorers"])
        lines.append(f"⚽ {scs}")
    return lines


def _render_section(section: dict, games_by_id: dict) -> list[str]:
    """Render a single section to Markdown lines, pulling game links from content.games."""
    lines: list[str] = [f"## {section.get('title', '')}", ""]
    section_type = section.get("type", "")
    if section.get("narrative"):
        lines.append(section["narrative"])
        lines.append("")

    if section_type == "match_of_day":
        game = games_by_id.get(section.get("match_id"))
        if game:
            lines.extend(_game_link_lines(game))
            home_meta = game["home"]
            away_meta = game["away"]
            team_links = []
            if home_meta.get("team_url"):
                team_links.append(f"[{home_meta['team']}]({home_meta['team_url']})")
            if away_meta.get("team_url"):
                team_links.append(f"[{away_meta['team']}]({away_meta['team_url']})")
            if team_links:
                lines.append("Teams: " + " vs ".join(team_links))
            lines.append("")
    elif section_type == "results_roundup":
        for g in section.get("games", []):
            game = games_by_id.get(g.get("match_id"))
            label = g.get("matchup", "") or (_fmt_matchup(game) if game else "")
            recap = game.get("media", {}).get("recap_url") if game else None
            label_md = f"[{label}]({recap})" if recap else label
            lines.append(f"- {label_md} — {g.get('note', '')}")
            if game and game.get("scorers"):
                scs = ", ".join(f"{s['player']} {s['minute']}".strip() for s in game["scorers"])
                lines.append(f"  ⚽ {scs}")
        lines.append("")
    elif section_type == "player_spotlight":
        for player in section.get("players", []):
            name = player.get("name", "")
            profile = player.get("media", {}).get("profile_url")
            name_md = f"[{name}]({profile})" if profile else f"**{name}**"
            parts = [name_md, player.get("line", ""), player.get("context", "")]
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
            for n in up.get("news", []):
                if n.get("url"):
                    lines.append(f"  [{n.get('headline', 'Preview')}]({n['url']})")
        lines.append("")
    return lines


def render_markdown(output: dict) -> str:
    """Render the final output dict as a Markdown string."""
    content = output.get("content", {})
    games_by_id = {g.get("match_id"): g for g in content.get("games", [])}
    date_str = output.get("date", "")
    lines = [
        f"# {content.get('headline', 'World Cup Daily Recap')}",
        f"*{date_str}*",
        "",
        content.get("summary", ""),
        "",
    ]
    for section in content.get("sections", []):
        lines.extend(_render_section(section, games_by_id))
    return "\n".join(lines)


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
