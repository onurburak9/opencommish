#!/usr/bin/env python3
"""World Cup Daily Recap Generator — Google ADK Pipeline.

Usage:
    python worldcup_recap/main.py YYYY-MM-DD [--dry-run] [--no-agents]

Options:
    --dry-run     Collect + print matches, skip all LLM phases
    --no-agents   Collect + structure only (skip enrich + synthesis)
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

from worldcup_recap.collect import collect
from worldcup_recap.pipeline import run_pipeline
from worldcup_recap.synthesize import build_final_output, render_markdown

_OUTPUT_DIR = Path(__file__).parent.parent / "data" / "worldcup_recaps"


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
        print("Usage: python worldcup_recap/main.py YYYY-MM-DD [--dry-run] [--no-agents]")
        sys.exit(1)

    target_date = args[0]
    dry_run = "--dry-run" in args

    if not os.getenv("GOOGLE_API_KEY") and not dry_run:
        print("❌ GOOGLE_API_KEY not set. Get a free key at https://aistudio.google.com/app/apikey")
        sys.exit(1)

    start = time.time()
    data = collect(target_date)

    if dry_run:
        print(f"\n[dry-run] {len(data.matches)} matches on {target_date}:")
        for m in data.matches:
            print(f"  {m.away_team} {m.away_score} @ {m.home_team} {m.home_score} ({m.status})")
        print(f"[dry-run] {len(data.upcoming)} upcoming fixtures")
        return

    print("🤖 Running ADK pipeline (Gemini 2.5 Flash)...")
    synthesized, verification = asyncio.run(run_pipeline(data))

    generation_time = time.time() - start
    output = build_final_output(data, synthesized, generation_time, verification)
    _save(output, target_date)
    print(f"\n⚽ Done in {generation_time:.1f}s (verification: {verification})")


if __name__ == "__main__":
    main()
