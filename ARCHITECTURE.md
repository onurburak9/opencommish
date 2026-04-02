# Architecture

This document describes the high-level architecture of OpenCommish. If you want to familiarize yourself with the codebase, you are in the right place.

See also the project guide in `AGENTS.md` for development rules, coding standards, and implementation phases.

## Bird's Eye View

OpenCommish is a Yahoo NBA Fantasy Basketball analytics platform. It ingests data from the Yahoo Fantasy API, enriches it with computed insights (missed lineup opportunities, projection accuracy, achievements), and presents it through a web interface with LLM-generated daily recaps.

The system has three layers:

1. **Data Collection** — GitHub Actions cron jobs that fetch daily stats, projected stats, and league metadata from Yahoo Fantasy API. Output is JSON files committed to the repo.

2. **Data Enrichment & Intelligence** — Python scripts that merge raw data, compute analytics (missed opportunities, projection diffs, achievements), and generate LLM-powered Turkish-language recaps via Claude API.

3. **Web Application** (planned) — FastAPI backend serving a REST API backed by PostgreSQL, consumed by a Next.js frontend with interactive dashboards and visualizations.

```
Yahoo Fantasy API ──→ Data Collection (GitHub Actions cron)
                          │
                          ├── data/daily_stats/     (actual player stats)
                          ├── data/projected_stats/ (Yahoo projections)
                          │
                          ▼
                     Data Enrichment
                          │
                          ├── enriched analysis JSON
                          ├── league context JSON
                          │
                          ▼
                     LLM Recap (Claude API) ──→ data/recaps/
                          │
                          ▼
                     FastAPI Backend ←──→ PostgreSQL
                          │
                          ▼
                     Next.js Frontend ──→ End Users
```

Today, the top half (collection + enrichment + recaps) is production-ready and runs daily. The bottom half (FastAPI + Next.js) is the next build target.

## Code Map

### `cron/`

Data collection and processing scripts. Each script is a standalone CLI tool that reads from Yahoo API or local JSON files and writes output to `data/`.

**Key scripts:**

- `fetch_daily_stats` — Fetches actual fantasy points for all players across all teams for a given date. Uses yfpy for Yahoo API auth. Also queries BallDontLie API for NBA opponent data. Runs daily at 3AM PST via GitHub Actions. Output: `data/daily_stats/league_93905_{date}.json`

- `fetch_projected_stats` — Scrapes Yahoo Fantasy roster pages to extract projected stats. Parses HTML from Yahoo's roster endpoint. Output: `data/projected_stats/league_93905_{date}.json`

- `fetch_projected_stats_api` — Alternative projection fetcher using official Yahoo API instead of scraping. Used for validation against the scraper.

- `enrich_daily_data` — Core enrichment engine. Merges daily stats with projections, classifies players as active/inactive, computes missed lineup opportunities with position compatibility, detects double-doubles/triple-doubles, calculates projection diffs, and generates daily awards. Output: `data/analysis/enriched_{date}.json`

- `fetch_league_context` — Fetches league standings, weekly matchup scores with projections, and computes week metadata (Turkish day names, day-of-week position). Output: `data/analysis/context_{date}.json`

- `generate_recap` — Orchestrator script. Checks what data exists, runs enrichment and context scripts as needed, assembles a structured prompt, calls Claude API, and saves the Turkish-language recap. Supports `--dry-run`, `--no-llm`, and `--force` flags. Output: `data/recaps/recap_{date}.md`

- `analyze_yesterday_games` — DEPRECATED. Replaced by the enrichment pipeline above.

**Architecture Invariant:** Every cron script is a standalone CLI that can run independently with `python cron/<script>.py YYYY-MM-DD`. Scripts communicate only through JSON files on disk, never through in-memory state or shared databases. This makes the pipeline debuggable and replayable.

**Architecture Invariant:** The enrichment layer never calls Yahoo API. It only reads from `data/daily_stats/` and `data/projected_stats/`. Only `fetch_*` scripts touch external APIs.

### `data/`

File-based data store. All collected and computed data lives here as JSON files. This is the current "database" — it will be migrated to PostgreSQL when the backend is built, but the files remain as the source of truth for the collection pipeline.

- `daily_stats/` — One JSON file per date. Contains all 8 teams, ~12 players each, with full stat breakdowns (PTS, REB, AST, ST, BLK, TO), fantasy points, roster positions, and opponent info.

- `projected_stats/` — Same structure as daily_stats but with projected values. Includes `games_played` count.

- `projected_stats_api/` — API-sourced projections for validation against scraped data.

- `analysis/` — Enriched outputs: `enriched_{date}.json`, `context_{date}.json`, `recap_payload_{date}.md`

- `recaps/` — Final LLM-generated recaps in markdown.

**Architecture Invariant:** Data files are append-only and immutable after creation. A file for a given date is written once and never modified. If reprocessing is needed, the enrichment layer regenerates from raw sources.

### `llm/`

LLM prompt templates and configuration.

- `daily-recap-prompt.md` — System prompt for the Turkish-language daily recap. Contains detailed rules for roster position logic (active vs IL/BN), missed opportunity interpretation, weekly matchup tone (early/mid/late week), award criteria, and output structure. This is the single source of truth for how recaps are generated.

**Architecture Invariant:** Prompts are versioned in git alongside the code. The orchestrator reads prompts from this directory at runtime, never from hardcoded strings.

### `dashboard/`

Streamlit-based analytics dashboard. Currently functional but will be replaced by the Next.js frontend.

- `app.py` — 5-page interactive dashboard (Overview, Team Rankings, Player Analysis, Trends, Bench Efficiency). Reads directly from `data/` JSON files.

**Note:** This is being replaced by `frontend/` (Next.js). Kept for reference during the transition.

### `backend/` (planned)

FastAPI application serving the REST API.

**Planned structure:**
- `app/api/v1/` — Versioned API endpoints (teams, matchups, analytics, auth)
- `app/core/` — Configuration, security, Yahoo OAuth
- `app/db/` — SQLAlchemy models, session management
- `app/services/` — Business logic (yahoo client, analytics calculations, LLM service)
- `app/schemas/` — Pydantic request/response models
- `alembic/` — Database migrations

**API Boundary:** The backend exposes a REST API under `/api/v1/`. The frontend communicates exclusively through this API. The backend never serves HTML or static assets.

### `frontend/` (planned)

Next.js application with React, TypeScript, and Tailwind CSS.

**Planned structure:**
- `src/app/` — App Router pages (dashboard, matchups, analytics, recaps)
- `src/components/` — React components (charts, tables, cards)
- `src/lib/` — API client, utilities
- `src/types/` — TypeScript type definitions

**API Boundary:** The frontend only communicates with the FastAPI backend. It never directly reads from `data/` files or calls Yahoo API.

### `tests/`

Test suite organized by type.

- `unit/` — Pure logic tests. Test enrichment calculations, position classification, missed opportunity detection, achievement detection, week metadata. These run without API credentials or network.

- `integration/` — Playwright browser tests for the dashboard. Require a running Streamlit instance.

**Architecture Invariant:** Unit tests never touch the network or file system. They test pure functions with in-memory data. Integration tests are clearly separated and require explicit setup.

### `.github/workflows/`

GitHub Actions automation. Three production pipelines run daily in sequence:

1. `daily_stats.yml` — 3:00 AM PST: Fetch yesterday's actual stats
2. `projected_stats.yml` — 12:00 PM PST: Fetch today's projections
3. `daily_recap.yml` — 5:00 AM PST: Enrich + generate LLM recap

Supporting workflows: `integration-tests.yml`, `scrape-tests.yml`, `claude-code.yml`

**Architecture Invariant:** Workflows commit directly to main for data files. Code changes always go through PRs.

### `scripts/`

Utility scripts for development safety.

- `safe-git.sh` — Shell wrapper that blocks `gh pr merge` when running under AI agents. Prevents accidental PR merges during automated development sessions.

## Cross-Cutting Concerns

### Yahoo API Authentication

All Yahoo API access uses OAuth 2.0 via yfpy. Credentials are stored as environment variables (locally in `.env`, in CI as GitHub secrets). Token refresh is handled by yfpy automatically. The league is identified by `league_id=93905` and `game_code=nba`.

**When the backend is built:** Yahoo OAuth will be managed by the backend's auth service. The cron scripts will continue using env-var-based auth for data collection.

### Fantasy Scoring Model

Fantasy points are calculated as: `sum(stat_value * stat_modifier)` for each stat category. The stat modifiers are fetched from Yahoo's league settings API. Current modifiers: PTS=1.0, REB=1.2, AST=1.5, ST=3.0, BLK=3.0, TO=-1.0.

This scoring model is applied in `fetch_daily_stats` (for actuals) and `fetch_projected_stats_api` (for projections). The enrichment layer receives pre-calculated fantasy points and does not recalculate them.

### Roster Position Logic

This is the most nuanced domain concept. Fantasy rosters have:
- **Active positions** (PG, SG, G, SF, PF, F, C, Util) — contribute to team score
- **Inactive positions** (BN, IL, IL+) — do not contribute

A "missed opportunity" is when an inactive player scored more than a swappable active player at a compatible position. Position compatibility is defined in `enrich_daily_data.POSITION_COMPATIBILITY`. IL/IL+ swaps are flagged as `swap_feasible: false` because they require a roster transaction, not just a lineup change.

### Testing

Unit tests use pytest with `-o "addopts="` to override playwright flags in `pytest.ini`. Tests are in `tests/unit/` and cover enrichment logic, position classification, missed opportunities, achievements, and week metadata. Run with:

```
python -m pytest tests/unit/ -v -o "addopts="
```

### Error Handling

Cron scripts follow a "best effort" pattern: if optional data (projections, opponent info, league context) fails to load, the pipeline continues with degraded output rather than failing entirely. Required data (daily stats) causes a hard failure with `sys.exit(1)`.

### Data Freshness

The pipeline assumes data is collected in order: daily stats first, then projections, then enrichment. If daily stats for a date don't exist, the enrichment script fails. If projections don't exist, enrichment proceeds without them (projection fields are null). The orchestrator (`generate_recap.py`) handles this dependency chain.
