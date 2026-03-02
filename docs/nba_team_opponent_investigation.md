# NBA Team & Opponent Data Investigation

## Problem Statement

When a player is traded mid-season, the `nba_team` and `opponent` fields saved in daily stats can be wrong for historical dates. The Zubac case is the concrete example: he played for LAC on Feb 2 (vs PHI), but the saved file shows `nba_team: "IND"` and `opponent: "HOU"` — because by the time the script ran, Yahoo had already updated him to Indiana, and IND happened to play HOU on Feb 2.

---

## What Each Source Returns

### Yahoo Fantasy API (`editorial_team_abbr`)

- Returns the player's **current** NBA team at the moment the API is called — not the team they were on for a historical date.
- This is always up-to-date but **not historical**. If Zubac was traded on Feb 3, any backfill run after Feb 3 will show `IND` even for Feb 2.
- **Free tier: YES** — included in every `get_team_roster_player_info_by_date` response.
- There is no `as_of_date` parameter to get historical team membership.

### BallDontLie Free Tier — `/v1/games`

- Returns all NBA games on a given date with `home_team.abbreviation` and `visitor_team.abbreviation`.
- Gives us a **set of teams that played that day** → the opponent map.
- Does **not** tell us which players played in which game.
- **Free tier: YES.**

### BallDontLie Free Tier — `/v1/players/{id}`

- Returns the player's **current** team — same problem as Yahoo. Zubac shows `IND` even today.
- **Free tier: YES**, but useless for historical accuracy.

### BallDontLie Paid Tier — `/v1/stats`

- Returns per-player per-game stats including `team.abbreviation` from that actual game.
- This is the **only source that gives the correct historical team** for a given date.
- Returns 401 on the free tier.
- **Free tier: NO.**

### BallDontLie Paid Tier — `/v1/box_scores`

- Returns full box score per game with team rosters as they played.
- Also gives correct historical team per player.
- Returns 401 on the free tier.
- **Free tier: NO.**

---

## Confirmed Facts About the Bug

From the saved files and API calls:

| Field | Feb 2 file | Feb 7 file |
|---|---|---|
| `nba_team` | `"IND"` (wrong — he played for LAC) | `""` (correct — 0 pts, traded) |
| `opponent` | `"HOU"` (wrong — IND played HOU, not LAC) | `""` (correct) |
| `fantasy_points` | 23.8 (scored for LAC vs PHI) | 0.0 |
| `roster_position` | `Util` | `IL` |

Games on Feb 2: `NOP @ CHA`, `HOU @ IND`, `MIN @ MEM`, **`PHI @ LAC`**

So Zubac played in `PHI @ LAC`. The correct values would be `nba_team: "LAC"`, `opponent: "PHI"`. The script instead looked up `IND` (Yahoo's current team), found IND did play that day (vs HOU), and wrote that instead.

---

## Why the Current "0 points = blank" Fix Is Incomplete

The current logic:
```python
if fantasy_points > 0 and yahoo_team in opponent_map:
    nba_team = yahoo_team
    opponent = opponent_map[yahoo_team]
else:
    nba_team = yahoo_team if fantasy_points > 0 else ''
    opponent = ''
```

This helps for the **zero-points case** (player didn't play / no game / DNP). But the Zubac bug is a **non-zero points + traded player** case — he scored 23.8 points but his Yahoo team was already wrong. The fix doesn't catch this because both conditions are true: `fantasy_points > 0` ✓ and `yahoo_team ("IND") in opponent_map` ✓.

---

## Approaches to Investigate (No Paid API)

### Option A — Cross-check team against game participation

**Idea:** On days a player scores > 0 points, their real team must have played. We already know which teams played (`opponent_map` keys). If `yahoo_team` is NOT in `opponent_map`, we know for sure Yahoo is wrong (traded). If `yahoo_team` IS in the map, we currently trust it — but it could be a false positive (like IND playing HOU while Zubac actually played for LAC).

**Limitation:** We cannot distinguish "yahoo_team played AND the player was on that team" from "yahoo_team played but the player was recently traded away." The false-positive case (traded player, new team also plays that day) is exactly the Zubac scenario.

**Verdict:** Catches the easy case (new team has no game), misses the hard case (new team also has a game).

---

### Option B — Store `nba_team` from Yahoo only for today's run, never for backfill

**Idea:** Only trust `editorial_team_abbr` when `target_date == today`. For any backfill run (historical date), leave `nba_team` and `opponent` blank unless we have a reliable source.

**What to validate:**
- Is `editorial_team_abbr` reliable when fetching today's date (same day as the game)? Most trades happen in the morning before games, so even same-day could be wrong for a trade day.
- Does Yahoo update `editorial_team_abbr` immediately when a trade is processed, or with a delay?

**Verdict:** Reduces the window of incorrect data significantly. The only wrong case would be a trade that happens on the exact day of a game, which is rare but does happen (trade deadline day).

---

### Option C — Use Yahoo's `player_notes_last_timestamp` or status fields

**Idea:** Yahoo's player object includes `status` and `player_notes_last_timestamp`. If a player was recently traded, their notes timestamp would be very recent. We could flag players with a very recent note timestamp as "team uncertain."

**What to validate:**
- Does Yahoo set `status` or `player_notes_last_timestamp` at the time of a trade?
- Is this timestamp accessible via `get_team_roster_player_info_by_date`?
- What exactly does the `status_full` field say for a traded player?

---

### Option D — Infer `nba_team` from game data without stats API

**Idea:** We know the player's stats (PTS, REB, etc.) and we know all games played that day. If only one game was played where those stats are feasible (e.g. checking the game score makes sense), we could narrow it down. But this is unreliable — multiple centers could have 8pts/9reb on the same day.

**Verdict:** Too fragile. Not worth pursuing.

---

### Option E — Cache `nba_team` from the first fetch and never update it from Yahoo

**Idea:** Once we've saved a player's `nba_team` for a given date, never overwrite it on a re-run. On the first run for a date, use Yahoo's value. On any subsequent run (backfill), skip updating `nba_team` if a value already exists.

**What to validate:**
- Does the script ever re-run for the same date? (It does — manual backfill.)
- Does the output file get overwritten or appended to? (Currently overwritten.)
- Would this fix the Zubac case? Only if the original Feb 2 run happened before the trade was processed in Yahoo's system.

---

### Option F — Build a local team history cache

**Idea:** Maintain a separate file `data/player_team_history.json` that maps `{player_id: [{team, from_date, to_date}]}`. On each daily run, record `player_id → nba_team → date`. When building the opponent lookup, use the team from this history for the target date rather than Yahoo's current value.

**What to validate:**
- Does Yahoo's `editorial_team_abbr` on the day of the trade reflect the old or new team?
- Can we reliably detect team changes by comparing today's `editorial_team_abbr` against the last recorded value for that player?
- How quickly does Yahoo update the team abbreviation after a trade?

**Verdict:** This is the most robust free-tier solution. It self-corrects over time and doesn't require any paid API. The key unknown is whether Yahoo's same-day value is old team or new team.

---

## Key Questions to Answer Before Implementing a Fix

1. **When exactly does Yahoo update `editorial_team_abbr` after a trade?**
   - Same day? Next morning? After the player's first game for the new team?
   - Need to check: what did the Feb 2 run show for Zubac on that actual day vs. what it shows now on a backfill.

2. **Is `player_notes_last_timestamp` or `status_full` set at trade time?**
   - If yes, we can use it as a signal that the team value may be stale.

3. **Does the script have a record of what `editorial_team_abbr` was on each past run?**
   - Currently no — the team field in saved files is always the value from the most recent run, not the original.
   - The Feb 2 file now shows `IND` because the script was re-run for that date after the trade. The original Feb 2 run would have shown `LAC`.

4. **On trade deadline day (or any trade day), does Yahoo reflect old team or new team for a player who already played that day?**
   - This determines whether Option B (only trust today's run) is sufficient.

5. **How many players in our league have been traded this season?**
   - Helps scope the actual impact. If it's 1-2 players on specific dates, the bug is cosmetic.

---

## Recommended Next Steps

1. **Do nothing to `nba_team`/`opponent` for files already saved** — they reflect historical backfill runs and the team data was wrong at save time.

2. **Validate Option F** — run the script live (today's date) for a few days and check if `editorial_team_abbr` is consistent with the actual game played. This tells us if Yahoo's same-day value is reliable.

3. **Validate Option C** — inspect the Yahoo player object for a recently traded player to see if `status_full` or notes fields indicate a trade.

4. **If Option F looks viable**, implement the player team history cache as the long-term fix. It's self-correcting and requires no external API beyond what we already use.
