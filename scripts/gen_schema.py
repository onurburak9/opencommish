#!/usr/bin/env python3
"""Generate worldcup_recap/schemas/recap_output.json from the Pydantic models.

The committed schema is the published contract for downstream HTML/video
renderers. Run this whenever the models change:

    uv run python scripts/gen_schema.py

A unit test (test_models.py) fails if the committed file drifts from the models.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from worldcup_recap.models import RecapOutput

_SCHEMA_PATH = (
    Path(__file__).parent.parent / "worldcup_recap" / "schemas" / "recap_output.json"
)


def generate_schema() -> str:
    """Return the indented JSON Schema string for RecapOutput (with trailing newline)."""
    return json.dumps(RecapOutput.model_json_schema(), indent=2, ensure_ascii=False) + "\n"


def main() -> None:
    _SCHEMA_PATH.write_text(generate_schema())
    print(f"✅ wrote {_SCHEMA_PATH}")


if __name__ == "__main__":
    main()
