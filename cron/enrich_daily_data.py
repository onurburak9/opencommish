#!/usr/bin/env python3
"""
Enrich daily fantasy data by merging actual stats with projections,
computing missed opportunities, achievements, and daily awards.

Usage:
    python cron/enrich_daily_data.py YYYY-MM-DD

Reads:
    data/daily_stats/league_93905_{date}.json
    data/projected_stats/league_93905_{date}.json

Writes:
    data/analysis/enriched_{date}.json
"""

import json
import sys
from pathlib import Path

ACTIVE_POSITIONS = {"PG", "SG", "G", "SF", "PF", "F", "C", "Util"}
INACTIVE_POSITIONS = {"BN", "IL", "IL+"}

# Which active roster slots each position abbreviation can fill.
POSITION_COMPATIBILITY = {
    "PG": {"PG", "G", "Util"},
    "SG": {"SG", "G", "Util"},
    "SF": {"SF", "F", "Util"},
    "PF": {"PF", "F", "Util"},
    "C": {"C", "Util"},
    "G": {"PG", "SG", "G", "Util"},
    "F": {"SF", "PF", "F", "Util"},
    "Util": {"PG", "SG", "G", "SF", "PF", "F", "C", "Util"},
}


def classify_player(roster_position: str) -> str:
    """Return 'active' or 'inactive' based on roster position."""
    if roster_position in ACTIVE_POSITIONS:
        return "active"
    return "inactive"


def had_game(player: dict) -> bool:
    """Determine if a player had an NBA game that day."""
    return bool(player.get("opponent"))


def detect_achievements(stats: dict) -> list[str]:
    """Detect double-double, triple-double from stat categories.

    Only PTS, REB, AST, ST, BLK count (standard NBA categories for multi-doubles).
    """
    double_digit_cats = sum(
        1 for cat in ["PTS", "REB", "AST", "ST", "BLK"]
        if stats.get(cat, 0) >= 10
    )
    if double_digit_cats >= 3:
        return ["triple-double"]
    if double_digit_cats >= 2:
        return ["double-double"]
    return []


def find_missed_opportunities(
    players: list[dict],
    eligible_positions: dict[str, list[str]] | None = None,
) -> list[dict]:
    """Find cases where an inactive player outscored a swappable active player.

    Args:
        players: All players on a team with roster_position, fantasy_points, opponent.
        eligible_positions: Map of player name -> list of position abbreviations they
            can play. If not provided, falls back to POSITION_COMPATIBILITY lookup.

    Returns:
        List of missed opportunity dicts.
    """
    active = [p for p in players if classify_player(p["roster_position"]) == "active"]
    inactive = [p for p in players if classify_player(p["roster_position"]) == "inactive"]

    opportunities = []
    used_active = set()

    # Sort inactive by points descending — greedily assign best bench player first
    inactive_with_games = [p for p in inactive if had_game(p) and p["fantasy_points"] > 0]
    inactive_with_games.sort(key=lambda p: p["fantasy_points"], reverse=True)

    for bench_p in inactive_with_games:
        bench_name = bench_p["name"]
        bench_pos = bench_p["roster_position"]
        is_il = bench_pos in ("IL", "IL+")

        # Determine which active slots this player could fill
        if eligible_positions and bench_name in eligible_positions:
            elig = set()
            for ep in eligible_positions[bench_name]:
                elig.update(POSITION_COMPATIBILITY.get(ep, set()))
        else:
            # Fallback: use Util compatibility (can replace any active slot)
            elig = POSITION_COMPATIBILITY.get("Util", set())

        # Find the worst active player at a compatible position
        worst_active = None
        worst_pts = float("inf")
        for act_p in active:
            if act_p["name"] in used_active:
                continue
            if act_p["roster_position"] in elig and act_p["fantasy_points"] < bench_p["fantasy_points"]:
                if act_p["fantasy_points"] < worst_pts:
                    worst_pts = act_p["fantasy_points"]
                    worst_active = act_p

        if worst_active:
            points_lost = round(bench_p["fantasy_points"] - worst_active["fantasy_points"], 2)
            used_active.add(worst_active["name"])
            opportunities.append({
                "bench_player": bench_name,
                "bench_position": bench_pos,
                "bench_points": round(bench_p["fantasy_points"], 2),
                "active_player_replaced": worst_active["name"],
                "active_position": worst_active["roster_position"],
                "active_points": round(worst_active["fantasy_points"], 2),
                "points_lost": points_lost,
                "swap_feasible": not is_il,
            })

    return opportunities


def build_stats_summary(stats_list: list[dict]) -> dict:
    """Convert detailed stats list to simple {display_name: value} dict."""
    return {s["display_name"]: s["value"] for s in stats_list}


def merge_projection(player: dict, projected_players: dict) -> dict:
    """Add projection data to a player dict."""
    proj = projected_players.get(str(player.get("player_id", "")))
    if proj is None:
        proj = projected_players.get(player.get("name"))
    if proj:
        player["projected_fantasy_points"] = proj["fantasy_points"]
        diff = player["fantasy_points"] - proj["fantasy_points"]
        player["projection_diff"] = round(diff, 2)
        pct = (diff / proj["fantasy_points"] * 100) if proj["fantasy_points"] else 0
        player["projection_diff_pct"] = round(pct, 1)
    else:
        player["projected_fantasy_points"] = None
        player["projection_diff"] = None
        player["projection_diff_pct"] = None
    return player


def enrich(daily_data: dict, projected_data: dict | None) -> dict:
    """Main enrichment: merge, classify, compute missed opps, achievements, awards."""
    # Build projection lookup: player_id -> projected player data, per team
    proj_lookup_by_team: dict[str, dict] = {}
    if projected_data:
        for team in projected_data.get("teams", []):
            team_proj = {}
            for p in team.get("players", []):
                pid = p.get("player_id") or p.get("player_name")
                team_proj[str(pid)] = p
                if "player_name" in p:
                    team_proj[p["player_name"]] = p
            proj_lookup_by_team[team["team_name"]] = team_proj

    enriched_teams = []
    all_active_players = []

    for team in daily_data["teams"]:
        team_name = team["team_name"]
        proj_players = proj_lookup_by_team.get(team_name, {})

        enriched_players = []
        for p in team["players"]:
            ep = {
                "name": p["name"],
                "player_id": p.get("player_id"),
                "nba_team": p.get("nba_team", ""),
                "opponent": p.get("opponent", ""),
                "roster_position": p["roster_position"],
                "is_active_position": classify_player(p["roster_position"]) == "active",
                "had_game": had_game(p),
                "fantasy_points": round(p["fantasy_points"], 2),
                "stats_summary": build_stats_summary(p.get("stats", [])),
                "achievements": detect_achievements(build_stats_summary(p.get("stats", []))),
            }
            ep = merge_projection(ep, proj_players)
            enriched_players.append(ep)

            if ep["is_active_position"] and ep["had_game"]:
                all_active_players.append({**ep, "team_name": team_name})

        # Missed opportunities
        missed_opps = find_missed_opportunities(team["players"])

        active_pts = sum(
            p["fantasy_points"] for p in enriched_players if p["is_active_position"]
        )
        total_pts = sum(p["fantasy_points"] for p in enriched_players)

        enriched_teams.append({
            "team_name": team_name,
            "team_id": team.get("team_id"),
            "daily_active_points": round(active_pts, 2),
            "daily_total_points_all": round(total_pts, 2),
            "players": enriched_players,
            "missed_opportunities": missed_opps,
        })

    # Top 5 active performers
    all_active_players.sort(key=lambda p: p["fantasy_points"], reverse=True)
    top_5 = all_active_players[:5]

    # Awards
    awards = compute_awards(all_active_players, enriched_teams)

    return {
        "date": daily_data["date"],
        "week": daily_data.get("week"),
        "league_name": daily_data.get("league_name", "teletabi ligi"),
        "teams": enriched_teams,
        "top_5_active": [
            {
                "name": p["name"],
                "team_name": p["team_name"],
                "nba_team": p["nba_team"],
                "fantasy_points": p["fantasy_points"],
                "roster_position": p["roster_position"],
                "stats_summary": p["stats_summary"],
                "achievements": p["achievements"],
            }
            for p in top_5
        ],
        "daily_awards": awards,
    }


def compute_awards(all_active: list[dict], teams: list[dict]) -> dict:
    """Compute daily awards from enriched data."""
    awards = {}

    # MVP — highest scoring active player
    if all_active:
        mvp = all_active[0]
        awards["mvp"] = {
            "name": mvp["name"],
            "team": mvp["team_name"],
            "points": mvp["fantasy_points"],
        }

    # Biggest disappointment — active player with worst projection_diff_pct (who had a game)
    with_proj = [
        p for p in all_active
        if p.get("projected_fantasy_points") and p["projected_fantasy_points"] > 20
    ]
    if with_proj:
        worst = min(with_proj, key=lambda p: p["projection_diff_pct"] or 0)
        if worst.get("projection_diff_pct", 0) < -25:
            awards["biggest_disappointment"] = {
                "name": worst["name"],
                "team": worst["team_name"],
                "points": worst["fantasy_points"],
                "projected": worst["projected_fantasy_points"],
                "diff_pct": worst["projection_diff_pct"],
            }

    # Biggest surprise — active player with best projection_diff_pct
    if with_proj:
        best = max(with_proj, key=lambda p: p["projection_diff_pct"] or 0)
        if best.get("projection_diff_pct", 0) > 25:
            awards["biggest_surprise"] = {
                "name": best["name"],
                "team": best["team_name"],
                "points": best["fantasy_points"],
                "projected": best["projected_fantasy_points"],
                "diff_pct": best["projection_diff_pct"],
            }

    # Worst missed opportunity across all teams
    worst_miss = None
    for team in teams:
        for opp in team.get("missed_opportunities", []):
            if worst_miss is None or opp["points_lost"] > worst_miss["points_lost"]:
                worst_miss = {**opp, "team": team["team_name"]}
    if worst_miss:
        awards["worst_missed_opportunity"] = worst_miss

    return awards


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python cron/enrich_daily_data.py YYYY-MM-DD")
        sys.exit(1)

    target_date = sys.argv[1]
    data_dir = Path(__file__).parent.parent / "data"

    # Load daily stats
    daily_path = data_dir / "daily_stats" / f"league_93905_{target_date}.json"
    if not daily_path.exists():
        print(f"❌ Daily stats not found: {daily_path}")
        sys.exit(1)
    with open(daily_path) as f:
        daily_data = json.load(f)

    # Load projected stats (optional)
    proj_path = data_dir / "projected_stats" / f"league_93905_{target_date}.json"
    projected_data = None
    if proj_path.exists():
        with open(proj_path) as f:
            projected_data = json.load(f)
        print(f"✅ Loaded projections from {proj_path.name}")
    else:
        print(f"⚠️ No projections found for {target_date}, enriching without projections")

    result = enrich(daily_data, projected_data)

    # Save enriched output
    output_dir = data_dir / "analysis"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"enriched_{target_date}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"✅ Enriched analysis saved to {output_path}")
    print(f"   Teams: {len(result['teams'])}")
    missed_total = sum(len(t["missed_opportunities"]) for t in result["teams"])
    print(f"   Missed opportunities: {missed_total}")
    achiev_total = sum(
        1 for t in result["teams"] for p in t["players"] if p["achievements"]
    )
    print(f"   Achievements: {achiev_total}")


if __name__ == "__main__":
    main()
