#!/usr/bin/env python3
"""
Agentic Daily Recap Generator — Orchestrates data gathering and LLM recap generation.

This script is the single entry point for generating a daily recap. It:
1. Checks which data files exist for the target date
2. Runs enrichment and context scripts as needed
3. Assembles the LLM prompt payload from enriched data + context
4. Calls the LLM (Claude API) with the system prompt from llm/daily-recap-prompt.md
5. Saves the generated recap to data/recaps/

Usage:
    python cron/generate_recap.py YYYY-MM-DD [--dry-run] [--no-llm] [--force]

Options:
    --dry-run   Print what would be done without executing scripts
    --no-llm    Run enrichment/context but skip LLM call (outputs assembled payload)
    --force     Re-run enrichment even if enriched file already exists
"""

import json
import subprocess
import sys
from pathlib import Path


DATA_DIR = Path(__file__).parent.parent / "data"
LLM_DIR = Path(__file__).parent.parent / "llm"
RECAP_DIR = DATA_DIR / "recaps"


def file_exists(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


def ensure_enriched_data(target_date: str, force: bool = False) -> dict:
    """Ensure enriched data exists for the target date. Run enrichment if missing."""
    enriched_path = DATA_DIR / "analysis" / f"enriched_{target_date}.json"

    if file_exists(enriched_path) and not force:
        print(f"✅ Enriched data already exists: {enriched_path.name}")
        with open(enriched_path) as f:
            return json.load(f)

    # Check prerequisites
    daily_path = DATA_DIR / "daily_stats" / f"league_93905_{target_date}.json"
    if not file_exists(daily_path):
        print(f"❌ Daily stats missing for {target_date}. Run fetch_daily_stats.py first.")
        sys.exit(1)

    print(f"🔄 Running enrichment for {target_date}...")
    result = subprocess.run(
        [sys.executable, "cron/enrich_daily_data.py", target_date],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"❌ Enrichment failed:\n{result.stderr}")
        sys.exit(1)
    print(result.stdout.strip())

    with open(enriched_path) as f:
        return json.load(f)


def ensure_league_context(target_date: str, force: bool = False) -> dict | None:
    """Ensure league context exists. Fetch if missing. Returns None if unavailable."""
    context_path = DATA_DIR / "analysis" / f"context_{target_date}.json"

    if file_exists(context_path) and not force:
        print(f"✅ League context already exists: {context_path.name}")
        with open(context_path) as f:
            return json.load(f)

    print(f"🔄 Fetching league context for {target_date}...")
    result = subprocess.run(
        [sys.executable, "cron/fetch_league_context.py", target_date],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"⚠️ League context fetch failed (non-fatal):\n{result.stderr}")
        return None
    print(result.stdout.strip())

    if file_exists(context_path):
        with open(context_path) as f:
            return json.load(f)
    return None


def load_system_prompt() -> str:
    """Load the system prompt from llm/daily-recap-prompt.md.

    Extracts content between the first pair of ``` markers in the ## System Prompt section.
    """
    prompt_path = LLM_DIR / "daily-recap-prompt.md"
    with open(prompt_path) as f:
        content = f.read()

    in_block = False
    lines = []
    for line in content.split("\n"):
        if line.strip() == "```" and not in_block:
            in_block = True
            continue
        if line.strip() == "```" and in_block:
            break
        if in_block:
            lines.append(line)

    return "\n".join(lines)


def _format_team_detail(team: dict) -> list[str]:
    """Format a single team's player table and missed opportunities."""
    parts = []
    parts.append(f"\n### {team['team_name']}")
    parts.append(f"Günlük Aktif Puan: **{team['daily_active_points']:.1f}**")

    parts.append("\n| Oyuncu | Pozisyon | Puan | Projeksiyon | Maç | Takım |")
    parts.append("|--------|----------|------|-------------|-----|-------|")
    for p in sorted(team["players"], key=lambda x: x["fantasy_points"], reverse=True):
        game_indicator = f"vs {p.get('opponent', '')}" if p["had_game"] else "❌ maç yok"
        proj = (
            f"{p['projected_fantasy_points']:.1f}"
            if p.get("projected_fantasy_points")
            else "-"
        )
        achiev = " ".join(f"🏅{a}" for a in p.get("achievements", []))
        parts.append(
            f"| {p['name']} {achiev} | {p['roster_position']} | "
            f"{p['fantasy_points']:.1f} | {proj} | {game_indicator} | {p['nba_team']} |"
        )

    if team["missed_opportunities"]:
        parts.append("\n**🚨 Missed Opportunities:**")
        for opp in team["missed_opportunities"]:
            feasible = (
                "" if opp["swap_feasible"] else " ⚠️ IL — roster hamlesi gerekirdi"
            )
            parts.append(
                f"- **{opp['bench_player']}** (BN: {opp['bench_points']:.1f} pts) → "
                f"**{opp['active_player_replaced']}** ({opp['active_position']}: "
                f"{opp['active_points']:.1f} pts) yerine konabilirdi. "
                f"**{opp['points_lost']:.1f} puan kayıp!**{feasible}"
            )
    return parts


def assemble_user_message(enriched: dict, context: dict | None) -> str:
    """Assemble the user message payload for the LLM from enriched data + context."""
    parts = []
    target_date = enriched["date"]

    parts.append("İşte günlük fantasy NBA verisi. Bu veriye göre günlük recap yazısını hazırla:\n")

    # Header
    if context:
        parts.append(f"**Tarih:** {target_date}")
        parts.append(
            f"**Haftanın Günü:** {context.get('day_name', '?')} "
            f"(Haftanın {context.get('week_day_number', '?')}. günü — "
            f"hafta {context.get('week_start', '?')} - {context.get('week_end', '?')})"
        )
        if context.get("is_playoffs"):
            parts.append("\n**⚠️ LİG PLAYOFF MODUNDA!**")
            if context.get("eliminated_teams"):
                parts.append(
                    f"Elenen takımlar (recap'te detaylı analiz YAPMA): "
                    f"{', '.join(context['eliminated_teams'])}"
                )
    else:
        parts.append(f"**Tarih:** {target_date}")

    # Build team lookup
    teams_by_name = {t["team_name"]: t for t in enriched["teams"]}
    playoff_teams = set(context.get("playoff_teams", [])) if context else set()
    matchups = context.get("matchups", []) if context else []

    # Matchup-oriented structure
    parts.append("\n## Matchup Detayları")
    if matchups:
        for i, m in enumerate(matchups, 1):
            t1, t2 = m["team_1"], m["team_2"]
            parts.append(f"\n---\n## Matchup {i}: {t1['team_name']} vs {t2['team_name']}")
            parts.append(f"- Haftalık Skor: {t1['points']:.1f} - {t2['points']:.1f}")
            diff = abs(t1["points"] - t2["points"])
            leader = t1["team_name"] if t1["points"] > t2["points"] else t2["team_name"]
            parts.append(f"- Fark: {diff:.1f} puan ({leader} önde)")
            if t1.get("projected_points"):
                proj2 = t2.get("projected_points", 0) or 0
                parts.append(f"- Projeksiyon: {t1['projected_points']:.1f} - {proj2:.1f}")
            if t1.get("games_remaining") is not None:
                parts.append(
                    f"- Kalan maç: {t1['team_name']}: {t1['games_remaining']}, "
                    f"{t2['team_name']}: {t2.get('games_remaining', '?')}"
                )

            # Team 1 detail
            team1_data = teams_by_name.get(t1["team_name"])
            if team1_data:
                parts.extend(_format_team_detail(team1_data))

            # Team 2 detail
            team2_data = teams_by_name.get(t2["team_name"])
            if team2_data:
                parts.extend(_format_team_detail(team2_data))
    else:
        parts.append("(Matchup verisi mevcut değil)")
        # Fallback: show all teams if no matchup data
        parts.append("\n## Takım Detayları")
        for team in enriched["teams"]:
            parts.extend(_format_team_detail(team))

    # Eliminated teams — brief summary only
    eliminated_names = set(context.get("eliminated_teams", [])) if context else set()
    eliminated_teams_data = [
        t for t in enriched["teams"] if t["team_name"] in eliminated_names
    ]
    if eliminated_teams_data:
        parts.append("\n---\n## Elenen Takımlar (kısa özet)")
        for team in eliminated_teams_data:
            parts.append(
                f"- **{team['team_name']}**: Günlük {team['daily_active_points']:.1f} puan"
            )

    # Top 5 + Awards
    parts.append("\n## Günün İstatistik Özetleri")
    parts.append("\n**Top 5 Aktif Performans:**")
    for i, p in enumerate(enriched.get("top_5_active", []), 1):
        achiev = f" ({', '.join(p['achievements'])})" if p.get("achievements") else ""
        stats_str = ", ".join(
            f"{k}: {int(v) if v == int(v) else v}"
            for k, v in p.get("stats_summary", {}).items()
            if v > 0
        )
        parts.append(
            f"{i}. **{p['name']}** ({p['team_name']}) — {p['fantasy_points']:.1f} pts{achiev}"
        )
        if stats_str:
            parts.append(f"   {stats_str}")

    awards = enriched.get("daily_awards", {})
    if awards:
        parts.append("\n**Ödül Adayları (veri bazlı):**")
        if "mvp" in awards:
            parts.append(
                f"- MVP: {awards['mvp']['name']} ({awards['mvp']['points']:.1f} pts)"
            )
        if "biggest_disappointment" in awards:
            d = awards["biggest_disappointment"]
            parts.append(
                f"- Hayal Kırıklığı: {d['name']} "
                f"({d['points']:.1f} pts, proj: {d['projected']:.1f}, {d['diff_pct']:.0f}%)"
            )
        if "biggest_surprise" in awards:
            s = awards["biggest_surprise"]
            parts.append(
                f"- Sürpriz: {s['name']} "
                f"({s['points']:.1f} pts, proj: {s['projected']:.1f}, +{s['diff_pct']:.0f}%)"
            )
        if "worst_missed_opportunity" in awards:
            m = awards["worst_missed_opportunity"]
            parts.append(
                f"- En büyük roster faciası: {m['team']} — "
                f"{m['bench_player']} bench'te {m['points_lost']:.1f} puan çürüttü"
            )

    # Standings
    if context and context.get("standings"):
        parts.append("\n## Liga Bağlamı")
        parts.append("\n**Sıralama:**")
        parts.append("| # | Takım | W | L | Streak |")
        parts.append("|---|-------|---|---|--------|")
        for s in sorted(context["standings"], key=lambda x: x["rank"]):
            parts.append(
                f"| {s['rank']} | {s['team_name']} | {s['wins']} | {s['losses']} "
                f"| {s.get('streak', '')} |"
            )

    return "\n".join(parts)


def call_llm(system_prompt: str, user_message: str) -> str:
    """Call Claude API to generate the recap."""
    import anthropic

    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    return response.content[0].text


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0].startswith("--"):
        print("Usage: python cron/generate_recap.py YYYY-MM-DD [--dry-run] [--no-llm] [--force]")
        sys.exit(1)

    target_date = args[0]
    dry_run = "--dry-run" in args
    no_llm = "--no-llm" in args
    force = "--force" in args

    print(f"{'='*60}")
    print(f"🏀 DAILY RECAP GENERATOR — {target_date}")
    print(f"{'='*60}")

    if dry_run:
        print("\n🔍 DRY RUN — checking data availability:")
        for label, path in [
            ("Daily stats", DATA_DIR / "daily_stats" / f"league_93905_{target_date}.json"),
            ("Projected stats", DATA_DIR / "projected_stats" / f"league_93905_{target_date}.json"),
            ("Enriched data", DATA_DIR / "analysis" / f"enriched_{target_date}.json"),
            ("League context", DATA_DIR / "analysis" / f"context_{target_date}.json"),
        ]:
            status = "✅" if file_exists(path) else "❌"
            print(f"  {status} {label}: {path.name}")
        return

    # Step 1: Ensure enriched data
    enriched = ensure_enriched_data(target_date, force=force)

    # Step 2: Ensure league context
    context = ensure_league_context(target_date, force=force)

    # Step 3: Assemble prompt
    system_prompt = load_system_prompt()
    user_message = assemble_user_message(enriched, context)

    if no_llm:
        print(f"\n📝 Assembled user message ({len(user_message)} chars, --no-llm mode)")
        # Save the payload for inspection
        payload_path = DATA_DIR / "analysis" / f"recap_payload_{target_date}.md"
        with open(payload_path, "w", encoding="utf-8") as f:
            f.write(user_message)
        print(f"💾 Payload saved to {payload_path}")
        print(f"\n{'='*60}")
        print("PAYLOAD PREVIEW (first 1000 chars):")
        print(f"{'='*60}")
        print(user_message[:1000])
        return

    # Step 4: Call LLM
    print("\n🤖 Calling LLM to generate recap...")
    recap = call_llm(system_prompt, user_message)

    # Step 5: Save recap
    RECAP_DIR.mkdir(parents=True, exist_ok=True)
    recap_path = RECAP_DIR / f"recap_{target_date}.md"
    with open(recap_path, "w", encoding="utf-8") as f:
        f.write(recap)

    print(f"\n✅ Recap saved to {recap_path}")
    print(f"\n{'='*60}")
    print("PREVIEW (first 500 chars):")
    print(f"{'='*60}")
    print(recap[:500])


if __name__ == "__main__":
    main()
