"""ESPN soccer parsing + provider. Endpoint shapes verified 2026-06-03.

Parse functions are pure (no network) so they unit-test with inline dicts.
The EspnProvider wraps them with httpx fetches.
"""

import httpx

from worldcup_recap.providers.base import (
    RawMatch,
    PreviewMatch,
    StatsProvider,
)

_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world"
_TIMELINE_KEEP = ("Goal", "Card", "Substitution", "Penalty", "VAR")


def _int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def parse_scoreboard_event(event: dict) -> dict:
    """Flatten a /scoreboard events[] entry into a flat dict."""
    comp = (event.get("competitions") or [{}])[0]
    home_name = away_name = ""
    home_score = away_score = 0
    for c in comp.get("competitors", []):
        if c.get("homeAway") == "home":
            home_name = c.get("team", {}).get("displayName", "")
            home_score = _int(c.get("score"))
        else:
            away_name = c.get("team", {}).get("displayName", "")
            away_score = _int(c.get("score"))
    notes = comp.get("notes") or []
    stage = notes[0].get("headline", "") if notes else ""
    return {
        "match_id": event.get("id", ""),
        "date": event.get("date", ""),
        "home_team": home_name,
        "away_team": away_name,
        "home_score": home_score,
        "away_score": away_score,
        "status": event.get("status", {}).get("type", {}).get("name", ""),
        "stage": stage,
        "venue": comp.get("venue", {}).get("fullName", ""),
    }


def parse_timeline(key_events: list[dict]) -> list[dict]:
    """Keep goals/cards/subs/VAR; map to {minute, type, player, text, scoring_play}."""
    out = []
    for ev in key_events or []:
        type_text = ev.get("type", {}).get("text", "")
        if not any(k in type_text for k in _TIMELINE_KEEP):
            continue
        participants = ev.get("participants") or []
        player = participants[0].get("athlete", {}).get("displayName", "") if participants else ""
        out.append({
            "minute": ev.get("clock", {}).get("displayValue", ""),
            "type": type_text,
            "player": player,
            "text": ev.get("text", ""),
            "scoring_play": bool(ev.get("scoringPlay")),
        })
    return out


def parse_player_stats(rosters: list[dict]) -> list[dict]:
    """Flatten summary.rosters[].roster[] into per-player stat dicts."""
    out = []
    for team_block in rosters or []:
        team_name = team_block.get("team", {}).get("displayName", "")
        for entry in team_block.get("roster", []):
            stats = {
                s.get("name", ""): s.get("displayValue", s.get("value", ""))
                for s in entry.get("stats", [])
            }
            out.append({
                "name": entry.get("athlete", {}).get("displayName", ""),
                "team": team_name,
                "position": entry.get("position", {}).get("abbreviation", ""),
                "starter": bool(entry.get("starter")),
                "stats": stats,
            })
    return out


def derive_top_performers(timeline: list[dict], player_stats: list[dict]) -> list[dict]:
    """Goalscorers (from timeline) first, then the busiest goalkeeper."""
    goals: dict[str, int] = {}
    for ev in timeline:
        if "Goal" in ev.get("type", "") and ev.get("player"):
            goals[ev["player"]] = goals.get(ev["player"], 0) + 1

    name_to_team = {p["name"]: p.get("team", "") for p in player_stats}
    performers = []
    for name, count in sorted(goals.items(), key=lambda kv: kv[1], reverse=True):
        note = "hat-trick" if count >= 3 else ("brace" if count == 2 else "")
        performers.append({
            "name": name,
            "team": name_to_team.get(name, ""),
            "goals": count,
            "note": note,
        })

    keepers = [
        p for p in player_stats
        if p.get("position") == "G" and _int(p.get("stats", {}).get("saves")) > 0
    ]
    if keepers:
        best = max(keepers, key=lambda p: _int(p["stats"].get("saves")))
        performers.append({
            "name": best["name"],
            "team": best.get("team", ""),
            "goals": 0,
            "saves": _int(best["stats"].get("saves")),
            "note": "goalkeeper",
        })
    return performers


def parse_news(articles: list[dict]) -> list[dict]:
    """Flatten ESPN news articles[] to {headline, url, published}."""
    out = []
    for a in articles or []:
        out.append({
            "headline": a.get("headline", ""),
            "url": a.get("links", {}).get("web", {}).get("href", ""),
            "published": a.get("published", ""),
        })
    return out
