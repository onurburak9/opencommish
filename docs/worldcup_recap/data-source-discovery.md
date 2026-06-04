# World Cup 2026 — Data Source Discovery

> Read-only endpoint probing performed 2026-06-03 to ground the `worldcup_recap`
> pipeline data model. WC 2026 runs **2026-06-11 → 2026-07-19** (48 teams, 104
> matches across USA/Canada/Mexico).

## Summary / Recommendation

| Need | ESPN (keyless) | API-Football v3 (paid) |
|------|----------------|------------------------|
| Fixtures / schedule | ✅ all 104 WC matches already loaded | ✅ (paid plan only for 2026) |
| Live + final scores | ✅ | ✅ |
| Goal/card/sub timeline w/ assists | ✅ rich (`keyEvents`) | ✅ (`fixtures/events`) |
| Per-player match stats | ✅ basic (`rosters`) | ✅✅ deep (rating, passes, duels…) |
| Team advanced stats (possession, pass %, shots map) | ⚠️ limited | ✅✅ full (`fixtures/statistics`) |
| Player ratings | ❌ | ✅ |
| xG / goals-prevented | ❌ | ⚠️ field exists, populated for top comps |
| Highlight videos | ✅ (`videos`, populated for big matches) | ❌ |
| News articles | ✅ (`news`) | ❌ |
| Standings / groups | ✅ | ✅ |
| Cost | Free, no key | Free plan blocks 2026 — **paid required** |

**Recommendation:** ESPN as the **primary** source (keyless, covers fixtures +
results + timeline + media + news in one `summary` call). Add API-Football as an
**optional advanced-stats enricher** (player ratings, possession, pass accuracy)
behind a paid key — designed as a pluggable provider so it can be enabled later
without reworking the collect phase.

---

## ESPN — endpoints verified

Base: `https://site.api.espn.com/apis/site/v2/sports/soccer/{league}`
WC league slug: **`fifa.world`**. Friendlies (used for live testing): `fifa.friendly`.

### Scoreboard — fixtures & live scores
`GET /fifa.world/scoreboard?dates=YYYYMMDD-YYYYMMDD`
- Returns `events[]`: `id`, `date`, `name` ("South Africa at Mexico"),
  `shortName` ("RSA @ MEX"), `status.type.name` (`STATUS_SCHEDULED` /
  `STATUS_FULL_TIME` / live), `competitions[0].competitors[]` (team, homeAway,
  score, winner), `venue`, `broadcasts`, `links`.
- ✅ Probed: all **100+ WC fixtures** returned for `20260611-20260719`.
- Alternative richer feed: `https://cdn.espn.com/core/soccer/scoreboard?xhr=1&league=fifa.world`
  — bundles `content.sbData.events`, plus a `nowFeed` (25 news/now items) and `news`.

### Match detail — the recap goldmine
`GET /fifa.world/summary?event={id}` — top-level keys verified:
`boxscore, broadcasts, commentary, format, gameInfo, hasOdds, headToHeadGames,
header, keyEvents, news, odds, pickcenter, rosters, standings, videos`.

- **`keyEvents[]`** — full timeline. Each entry: `type.text` ("Goal - Header",
  "Substitution", "Yellow Card"), `clock.displayValue` ("8'"), `scoringPlay`,
  field-position coords, and narrative `text`
  (*"Goal! Norway 1, Sweden 0. Jørgen Strand Larsen header… Assisted by Julian
  Ryerson."*). Excellent prose source.
- **`rosters[]`** — per team: `formation` ("4-4-2"), `roster[]` with
  `athlete.displayName`, `position`, `starter`, and `stats[]` (appearances,
  fouls committed/suffered, yellow/red, subIns, goalsConceded, saves,
  shotsFaced, goalAssists, …).
- **`header`** — final score + `winner` flag per competitor.
- **`gameInfo`** — `venue.fullName`, `attendance`, `officials[]`.
- **`videos[]`** — highlight clips (`headline`, `duration`, `links.source.href`,
  `thumbnail`). Empty for the probed friendly; ESPN populates this for marquee
  matches (WC expected to have them).
- **`news[]`** + **`commentary[]`** — article links and play-by-play text.

### Other
- `GET /fifa.world/standings` → 200 (group tables)
- `GET /fifa.world/teams` → 200 (squad/team metadata)
- `GET /fifa.world/news` → 200 — `articles[]` with `headline`, `type`,
  `published`, `links.web.href`, `images[].url`.

---

## API-Football v3 — endpoints verified

Base: `https://v3.football.api-sports.io` · header `x-apisports-key` · WC league id **1**.

- **`GET /status`** ✅ — confirmed key valid: **Free** plan, 100 req/day.
- **Free-plan limitation (critical):** season 2026 is **blocked** —
  *"Free plans do not have access to this season, try from 2022 to 2024."*
  Date queries are restricted to a rolling current window
  (*"try from 2026-06-03 to 2026-06-05"*). **A paid plan is required to serve WC
  2026 data.**

Advanced depth confirmed on a real international friendly (Netherlands 0-1
Algeria, fixture 1536930) within the allowed window:

- **`GET /fixtures/statistics?fixture={id}`** — team-level: Ball Possession (52%),
  Total/On/Off/Blocked shots, Shots inside/outside box, Total passes (505),
  Passes accurate (442), Passes % (88%), Corners, Offsides, Fouls, GK saves,
  `expected_goals`, `goals_prevented` (xG fields present; null here, populated
  for top competitions).
- **`GET /fixtures/players?fixture={id}`** — per-player: `games.rating` (6.9),
  `minutes`, `captain`, `passes` (total/key/accuracy), `shots`, `goals`
  (incl. assists/saves), `tackles`, `duels`, `dribbles`, `fouls`, `cards`.
- Other documented: `/fixtures/events`, `/fixtures/lineups`, `/standings`,
  `/players`, `/teams`.

**Conclusion:** API-Football's differentiator is **player ratings + team
possession/passing/shot analytics + xG** — none of which ESPN exposes. Worth
wiring as an optional enricher once a paid key is available.

---

## News & media sources (post-ESPN exploration)

ESPN's `summary.news` + `summary.videos` + `/fifa.world/news` cover a lot. For
breadth, candidates to evaluate later: GNews / NewsAPI (article search by
team/player), YouTube Data API (official FIFA highlight channel), and Google
News RSS. All discovered links flow through the **verification subagent** before
inclusion (see design).
