# World Cup Agentic System — Product Roadmap

**Date:** 2026-06-03
**Status:** Roadmap / product planning
**Related:** [`agentic-system-overview.md`](./agentic-system-overview.md) ·
[daily-recap design](../superpowers/specs/2026-06-03-worldcup-daily-recap-design.md)

## The big idea

Don't build "a recap script." Build a **pluggable agentic pipeline engine** and
make the daily recap its first product. Everything — data fetchers, enrichers,
verifier loops, LLM agents, custom scripts, and delivery channels (email, Slack,
web) — is a **plug-in step** wired together by a small runner. New capabilities
become new steps in a config file, not rewrites.

```
   ┌─────────────────────── Pipeline Engine ───────────────────────┐
   │   pipeline.yaml  ──▶  Runner  ──▶  ordered/parallel Steps      │
   │                          │                                     │
   │   Step registry: [ Fetch | Agent | Enrich | Verify-loop |      │
   │                     Script | Sink/Deliver ]                    │
   │                          │                                     │
   │   PipelineContext (shared blackboard) + telemetry + run store  │
   └────────────────────────────────────────────────────────────────┘
        ▲ plug in any step          ▲ schedule it        ▲ deliver anywhere
```

## How the three product questions get answered

### 1. How do we run the whole thing?

A single entrypoint executes a **declarative pipeline**:

```bash
python -m wc_pipeline run --pipeline pipelines/daily_recap.yaml --date 2026-06-11
#   flags: --dry-run  --resume-from <step>  --only <step>  --backfill <start>..<end>
```

The pipeline file *is* the wiring — reorder, add, or drop steps without touching
the engine:

```yaml
# pipelines/daily_recap.yaml
steps:
  - fetch_espn_matches          # FetchStep  (deterministic)
  - structure_sections          # AgentStep  (Gemini)
  - group: [find_verify_media]  # VerifyStep (find -> verify -> retry loop)
    parallel: true
  - synthesize_recap            # AgentStep  (Gemini)
  - render_outputs              # OutputStep (json + md)
  - deliver_email               # SinkStep   (optional)
```

Every step implements one tiny contract, so a step can be a Python function, an
**ADK agent**, or an **external script**:

```python
class Step(Protocol):
    name: str
    requires: list[str]      # context keys it reads
    provides: list[str]      # context keys it writes
    async def run(self, ctx: PipelineContext) -> PipelineContext: ...
```

- `AgentStep` wraps an ADK/Gemini agent.
- `ScriptStep` shells out to any script/binary (`requires`/`provides` map stdin/stdout
  or files) — this is how you "plug in a script."
- `VerifyStep` encapsulates the find → verify → bounded-retry loop as one reusable
  node.

### 2. How do we schedule jobs?

Two tiers, adopt as scale demands:

- **Tier 1 — GitHub Actions cron (now).** Already this repo's pattern. One
  workflow per pipeline, `workflow_dispatch` for manual runs, a matrix for
  backfilling a date range. Zero new infra.
- **Tier 2 — a real orchestrator (later).** When we need retries, dependencies,
  backfills, and a run UI: **Prefect** or **Dagster** (Pythonic, lightweight DAGs +
  built-in UI) or **Temporal** (durable execution; already used elsewhere in your
  stack). The `Runner` stays the same — the scheduler just invokes it.

### 3. How do we create integrations (email, Slack, …)?

Delivery is just **sink steps** appended to the pipeline tail. Each sink renders
the recap through a channel-specific template:

| Sink | Tech | Notes |
|------|------|-------|
| **Email** | Resend / SendGrid / SMTP | render MD → responsive HTML digest; secret `RESEND_API_KEY` |
| Slack / Discord / Telegram | incoming webhook | summary + top media links |
| Web publish | commit to static site, or push to the planned FastAPI backend | feeds the future frontend |
| RSS / social | feed file / X API | broadcast |
| Database | Postgres (Phase 1 backend) | queryable archive |

Adding a channel = add one sink to `pipeline.yaml` + its secret. No engine change.

---

## Phase-by-phase plan

### Phase 1 — Vertical slice: Daily Recap MVP  *(next)*
**Build:** the 4-stage daily recap exactly as specced (collect → structure →
enrich+verify → synthesize), hardcoded wiring, JSON+MD output, GitHub Actions cron.
**You can achieve:** a real, grounded, media-verified daily recap for the opening
match (2026-06-11). Proves the FIND → VERIFY → CREATE value end-to-end.
**Exit:** green tests; one live recap committed; CI workflow runs on dispatch.

### Phase 2 — Pluggable pipeline engine
**Build:** extract `Step` / `PipelineContext` / `StepRegistry` / `Runner` and a
declarative `pipeline.yaml`. Wrap the Phase-1 stages as steps. Add `ScriptStep` and
`AgentStep` adapters. Telemetry per step.
**You can achieve:** reorder/add/remove steps via config; plug in your own
scripts or agents without touching the runner; the same engine can drive
`nba_recap` too.
**Exit:** daily recap runs entirely from `pipeline.yaml`; a custom "hello-world"
step plugged in purely via config.

### Phase 3 — Orchestration & scheduling
**Build:** run history + artifact store, idempotent re-runs, `--backfill` over a
date range, `--resume-from`. Keep GH Actions cron; evaluate Prefect/Dagster/Temporal.
**You can achieve:** reliable unattended daily runs; backfill the entire group
stage in one command; see what ran, when, and why it failed.
**Exit:** scheduled daily run live; a successful backfill of multiple past dates.

### Phase 4 — Integrations / delivery sinks
**Build:** `SinkStep` interface + channel templating. Email digest first, then
Slack/Discord, then web publish.
**You can achieve:** the recap lands in your inbox/channel automatically each
morning; new channels are one-line config additions.
**Exit:** a formatted daily email with verified media arrives on schedule.

### Phase 5 — More outputs & intelligence
**Build (reusing collect+verify):** match **preview** mode, single-**match report**
mode, **news digest** mode. Optional: API-Football advanced stats (paid), Turkish
(multi-language) synthesis, human-in-the-loop approval, narrative critic loop.
**You can achieve:** multiple content products from one engine; richer analytics;
editorial control before publish.
**Exit:** ≥2 output modes shipping from the same pipeline engine.

### Phase 6 — Productization / control plane
**Build:** a dashboard to compose pipelines, manage schedules + integrations, and
browse run history; secrets management; (optional) multi-league / multi-sport /
multi-tenant.
**You can achieve:** non-engineers compose and operate agentic pipelines; the
system becomes a product, not a script.
**Exit:** a pipeline created, scheduled, and delivered end-to-end from the UI.

---

## Sequencing notes

- **Decided:** build the **Phase 1 MVP first** (hardcoded wiring), prove value on a
  live recap, **then extract the Phase 2 engine** from working code. Lower risk than
  designing the abstraction up front; the real wiring informs the `Step`/`Runner`
  boundaries.
- Phases 1 → 4 are the **critical path** to "automated daily recap in my inbox."
- Phase 2 (the engine) is the highest-leverage investment — it's what makes
  "plug in different steps/agents/scripts" real and unlocks everything after.
- Phase 5/6 are value-expansion and can be reordered based on product priorities.
- Each phase ships something usable on its own; nothing requires the next phase to
  deliver value.
