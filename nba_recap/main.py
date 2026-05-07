#!/usr/bin/env python3
"""
NBA Daily Recap Generator — Google ADK Pipeline

Usage:
    python nba_recap/main.py YYYY-MM-DD [--dry-run] [--no-agents]

Options:
    --dry-run     Print collected game data, skip all LLM phases
    --no-agents   Run collect + structure only, skip enrichment and synthesis
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

# Ensure project root is on sys.path when running as a script
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

from nba_recap.collect import collect
from nba_recap.pipeline import run_pipeline
from nba_recap.synthesize import build_final_output, render_markdown


_OUTPUT_DIR = Path(__file__).parent.parent / "data" / "nba_recaps"


def _save(output: dict, date_str: str) -> None:
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = _OUTPUT_DIR / f"{date_str}.json"
    md_path = _OUTPUT_DIR / f"{date_str}.md"
    json_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    md_path.write_text(render_markdown(output))
    print(f"✅ {json_path}")
    print(f"✅ {md_path}")


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0].startswith("--"):
        print("Usage: python nba_recap/main.py YYYY-MM-DD [--dry-run] [--no-agents]")
        sys.exit(1)

    target_date = args[0]
    dry_run = "--dry-run" in args

    if not os.getenv("GOOGLE_API_KEY") and not dry_run:
        print("❌ GOOGLE_API_KEY not set. Get a free key at https://aistudio.google.com/app/apikey")
        sys.exit(1)

    start = time.time()

    # Phase 1: Collect (pure Python, no LLM)
    data = collect(target_date)

    if dry_run:
        print(f"\n[dry-run] {len(data.games)} games on {target_date}:")
        for g in data.games:
            ot = " (OT)" if g.overtime else ""
            print(f"  {g.away_team} {g.away_score} @ {g.home_team} {g.home_score}{ot}")
        return

    # Phases 2-4: ADK agents (structure → enrich → synthesize)
    print(f"🤖 Running ADK pipeline (Gemini 2.0 Flash)...")
    synthesized, subagents_spawned = asyncio.run(run_pipeline(data))

    generation_time = time.time() - start
    output = build_final_output(data, synthesized, generation_time, subagents_spawned)
    _save(output, target_date)
    print(f"\n🏀 Done in {generation_time:.1f}s ({subagents_spawned} subagents)")


if __name__ == "__main__":
    main()
