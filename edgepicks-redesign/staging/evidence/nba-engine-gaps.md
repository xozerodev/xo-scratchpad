# NBA Bet Engine → Edge Picks v4 producer record: implementation gap analysis

**Task:** what a bet engine must do to emit the Edge Picks v4 producer pick record, using the NBA bet engine as reference.
**Analyst:** nba-engine (read-only investigation; no repo edits).
**Contract:** `xo-scratchpad/edgepicks-redesign/staging/conf-schema-contracts.md` — v4.0.0 draft, 37-field record, producer Rules 1–6, deterministic `pick_id`, forward-only lifecycle. Line references below are to that file.
**Engine checked:** `github/nba_bet_engine` @ **dev / d36b2d1** (2026-10-20, "pause WLTP and PS jobs in dev and tst"); contrasted with **main / af145bd** (the 2025 notebook engine).
**PE checked:** `github/app-data` @ **tst-blue / a1c16f4** (the deployed 1.00 `nba_wltp.py`/`nba_ps.py` shape) and `origin/feat/nba-2026` @ **54214ec** (`canonical_transformations.py`, the "Format B" canonical path). The checkout is deliberately on `tst-blue`; canonical content was read with `git show` and is cited as such.
**Live data:** `dev_nba.nba_gold_bets.*` via read-only Databricks profile `dev` (warehouse `5ff1c07517da5ba4`), queried 2026-10-21. No writes, no job triggers.
**Confluence:** `PB/720142351` *NBA Bet Engine — Output Contract (Data Model Format)* v6 and `PB/717914114` *NBA 2026 — Schema Specification* v6, both fetched 2026-10-21.
**Evidence tags:** **[V]** verified in code/data/spec at the cited revision; **[A]** assumed/inferred, not directly observed; **[D]** stated by a design document but not re-measured.

---

## 0. Verdict in one paragraph

The NBA engine cannot emit the v4 record today, and the gap is structural rather than a field rename. It produces **one state-snapshot row per game** (`wltp_top_picks_agg`, a nested `edge_picks` array; `ps_top_picks_agg` a team tree) that is **rebuilt and overwritten on every trigger**, with edge in **percentage points**, no `pick_status`/lifecycle, no observation fields, no edge basis/threshold, and no stable record identity (`bet_id = {game_sk}_{bet_type}`). The pipeline deliberately **deletes** rows it no longer backs (selector purge, PS `replace_game_sks`, region re-replication, PE whole-document replace), which is the exact behaviour Rule 2 forbids. The engine does already hold most of the **raw inputs** for a correct record (model probability, numeric line, decimal/American odds, bookmaker, stake units, market, team/player keys) and the current PE already mints a v4-shaped `pick_id` for game picks — so the work is (a) make the record an explicit, persisted, per-pick-per-region object with frozen entry fields, and (b) give it lifecycle/observation state. Both require decisions the contract does not yet make (record store ownership, observation writer, cancellation policy), so **contract decisions are on the critical path before engine code**.

---

## 1. What the engine produces today

### 1.1 Pipeline and tables (WLTP, game markets)

`resources/jobs.yml:37–106` runs four tasks chained on a table-update trigger over `nba_gold_pred.nba_sportsmodel_pofs` and `nba_silver.fact_game_odds` (`jobs.yml:19–24`; both jobs PAUSED since 2026-10-20, `conf/dev.yml:10–12`):

| Task | Writes | Merge semantics |
|---|---|---|
| `wltp_engine` | `{catalog}.nba_gold_bets.wltp_top_picks_adj_{engine}_{version}` (dev: `..._nba_c5_tuned_0_1_0`) | `upsert_delta` merge on `(game_sk, bet_id, bet_bookie_region, bet_bookie_line)`, **`whenMatchedUpdateAll`** (`wltp_engine.py:289–296`, `_common.py:194–230`) |
| `update_outcomes` | same table + `wltp_top_picks_adj_live_app` | merge **only** `bet_bookie_outcome`/`status` where the outcome is currently NULL (`_update_outcomes.py:54–69`) |
| `pick_selector` | `wltp_top_picks_adj_live_app`, `wltp_top_picks_adj_audit` (append) | **DELETE** purged rows, then merge update-all (`wltp_pick_selector.py:245–300`) |
| `aggregation` | `nba_gold_bets.wltp_top_picks_agg` | merge on `game_sk` only (`wltp_aggregation.py:122`), replacing the whole nested array |

The PS job (`jobs.yml:140–200`) is `ps_engine` → `ps_update_outcomes` → `ps_aggregation`, writing `ps_top_picks` (merge on `game_sk,bet_id,bet_bookie_region` with **`whenNotMatchedBySourceDelete` for every game the run evaluated** — `ps_engine.py:116–124`, `_common.py:227–230`) and `ps_top_picks_agg` (merge on `game_sk`).

### 1.2 Published table shapes (live, verified)

`dev_nba.nba_gold_bets.wltp_top_picks_agg` — 31 columns; `edge_picks` is
`array<struct<bet_type, bet_id, bet_probability, bet_bookie_name, bet_bookie_region, bet_bookie_stake, bet_bookie_position, bet_bookie_line, bet_code, bet_price, bet_decimal_odds, bet_american_odds, bet_bookie_outcome, edge, market_last_update, variant>>` (16 fields; matches `_schemas.py:136–153` and the live `DESCRIBE`). `top_picks` is a **boolean** now (repurposed); `game_datetime`, `pick_date_time` are **strings**; `taxonomy_version` = `"1.0"`; `picks_run_id` bigint; `record_hash` string; no `picks_updated_at`.

Representative live row (game 40021717855, first two slots — AU and US are byte-identical apart from region):

```
UD_SPR< | 40021717855_UD_SPR< | 0.6251932116614132 | BetMGM | AU | 1.0 | 1.5 | T1_spread_over | T1_1.5_1.87 | 1.87 | 1.87 | -115.0 | null | 9.0434 | 2026-10-19T04:59:27.000Z | main
UD_SPR< | 40021717855_UD_SPR< | 0.6251932116614132 | BetMGM | US | 1.0 | 1.5 | T1_spread_over | T1_1.5_1.87 | 1.87 | 1.87 | -115.0 | null | 9.0434 | 2026-10-19T04:59:27.000Z | main
```

Totals row: `lower_TP | ... | 235.5 | bookie_total_line_under | Under_235.5_1.91 | ...` — note `bet_bookie_line` for totals is the **literal string** `bookie_total_line_under` (the derivation at `_wltp_engine.py:131–139` emits a constant instead of the column value), and the numeric line survives only in `bet_bookie_position` / `bet_code`.

Aggregate state at query time: **17 rows / 17 games** (game_date 2026-10-20…24), 34 pick slots (2 per game — the AU copy and the US original), 0 placeholder rows. `live_app` holds 28 rows / 17 games and **only `bet_bookie_region='us'`**; the engine table holds 53 rows / 29 games; the audit table holds 358 appended rows / 17 games. **No row has `bet_bookie_outcome`** and `status` is `scheduled` on every row even though the 2026-10-20 games are `final` in `dim_all_games` (the settlement task has not run since the pause at 2026-10-20 18:08 +11 / 07:08 UTC; this is a paused-job artefact, not a code result).

### 1.3 PS shape (code-only; tables empty)

`ps_top_picks` and `ps_top_picks_agg` are **0 rows** (PS disabled: `conf/dev.yml:12` `ps_picks_enabled=false`; `ps_engine.py:19–21`/`_common.py:227–230` clear picks). The shape is therefore taken from `_schemas.py:199–296` and `_ps_engine.py`:

- one row per pick with `bet_id = {game_sk}_{player_sk}_{stat_type}_{bet_type}` (line **not** in the id — `_ps_engine.py:337–341`), `bet_bookie_line` = numeric line as string, `bet_code = {stat_type}_{bet_type}_{line}`, `edge` in percentage points, `variant` literal `"main"`;
- aggregation nests `edge_picks → team_1/team_2[] → picks[] → items[] → bookmaker[]`, and derives a per-pick `pick_status` from `bet_bookie_outcome`/game status: `won|lost|cancelled|void(final)|scheduled|active` (`_ps_aggregation.py:19–33`). A push and a DNP are indistinguishable because both store NULL — the code comment says so explicitly (`_ps_aggregation.py:19–24`).

### 1.4 Market/odds source facts that constrain region handling

- `nba_silver.fact_game_odds` for 2026 contains **only `bookmakers_region='us'`** (11 books: DraftKings, FanDuel, Caesars, BetMGM, BetRivers, Bovada, BetOnline.ag, LowVig.ag, Fanatics, MyBookie.ag, BetUS). There is no NBA AU bookmaker feed in silver.
- The engine's `engine_regions` widget still defaults to an AU list (`Betr, Dabble AU, Neds, SportsBet`) — **not wired into jobs.yml/databricks.yml**, so the default is used — but no AU bookmaker exists in the odds table, so the AU branch would emit nothing.
- The only thing that makes AU records is aggregation-time replication: `priority_region: "us"` (`databricks.yml:75–77`, wired at `jobs.yml:103–104`), `_replicate_priority_pick` copies the US pick into every display region and **upper-cases `bet_bookie_region`** (`_wltp_aggregation.py:39–43, 51–60, 127–141`). The live data confirms: AU slots carry US bookmakers (DraftKings/BetMGM/Caesars/FanDuel).
- The live-odds adapter that would fetch NBA prices is **US-only by design**: `DEFAULT_REGIONS = ("us",)` with the comment "NBA 2026 publishes US-derived odds to both au and us (Bet Types Spec §4.1)" (`_live_odds.py:32`).

### 1.5 What PE does to engine rows today

On the deployed branch (`tst-blue`), `databricks/publisher/nba/nba_wltp.py` flattens the legacy `bet_*` struct into the 16-field canonical pick and writes one document per game (`nba|game_edge_picks|<game_sk>`, `/game_sk`) with a region map `{au:[…], us:[…]}`:

- it **builds the v4-shaped game `pick_id`** from engine fields — `{game_sk}|{type}|{selection}|{line}|{variant}|full|{region}` (`nba_wltp.py:242–253`), line token `"null"` for h2h, variant from the engine (`main`);
- it derives `pick_status` from `bet_bookie_outcome` 1/0/2 else `"scheduled"` (`:231–238`); derives `bookmaker.bookmaker_id` by stripping non-alphanumerics from the display name (`:255`); maps `bet_bookie_line`/`bet_code` back to market/selection/line (`:200–230`);
- it **silently drops any pick whose `edge` is null** (`_game_edge_picks_by_region`, `:290–296`) and drops the empty placeholder struct;
- it mirrors **US picks into both AU and US** blocks (`_PRIMARY_REGION = "us"`, `:84–88, 290–300`) — PE performs the same mirroring as aggregation, so region is a display key, not a pricing source;
- it carries `record_hash` → `picks_hash`, `pick_date_time` → `picks_updated_at`, `picks_run_id` cast to string, `schema_version "1.00"`, `taxonomy_version "1.0"`.

On `feat/nba-2026`, canonical PE expects the **source table to already contain the region-keyed canonical pick struct** (id, pick_status, bookmaker object): `canonical_transformations.py:199–223` (`_guard_edge_picks`) raises `ValueError` if any pick has a null/blank `id` or a `pick_status` outside its 9-value enum, and `_game_edge_picks` (`:737–900`) only re-normalises `bookmaker.bet_line` and the document envelope. It also filters documents to games within `-7d…+14d` **or having a graded pick** (`:742–749`), so a finished game outside the window stops being republished unless its picks are already graded. The generic writer skips a row with no `id` without counting it, and its patch mode cannot set a field to null (`generic_cdf_to_cosmos_pipeline.ipynb`, code cell lines 258–259 and 278 — **[V]**, matching the corpus analysis).

So today the **engine emits legacy shaped rows and PE invents/derives the canonical pick fields**. The contract moves the values upstream (`producers-to-bff.md` 1: "Bet engines compute the values; the Publish Engine is the only writer of pick documents"), which is a division-of-labour change, not just a schema change.

---

## 2. Current → v4 field mapping (all 37 fields)

Legend: **OK** = value exists and is semantically compatible; **CONVERT** = recoverable but needs unit/type/enum/identity work; **MISSING** = no source anywhere in engine output; **DERIVE** = requires a rule/decision beyond field mapping.

| # | v4 field | Current source (engine column / code) | Conversion / gap | Status |
|---|---|---|---|---|
| 1 | `schema_version` | none; agg has `taxonomy_version="1.0"` (`_wltp_aggregation.py:172`); PE writes `"1.00"` (`nba_wltp.py:350`) | new literal `"4.0.0"`; producer must stamp it | MISSING |
| 2 | `pick_id` | `bet_id = {game_sk}_{bet_type}` (`_wltp_engine.py:181`; PS `_ps_engine.py:337–341`) | must be rebuilt per §8: `{game_sk}\|{market_token}_{selection}\|{selection}\|{line}\|main\|full\|{region}`. `bet_type` contains `<`/`>` (e.g. `UD_SPR<`) which are **illegal** in the id charset; `bet_id` is region-less and line-less. PE builds a v4-shaped id for game picks, but it is a fired-at-display derivation: the engine itself derives no v4 id and nothing stores one | CONVERT (identity work) |
| 3 | `region` | `bet_bookie_region`: `"us"` in engine/live_app; `"AU"`/`"US"` after aggregation replication (`_wltp_aggregation.py:39–43`) | lower-case; must be a real region-scoped record, not a copied US one (see §5.4) | CONVERT |
| 4 | `sport` | agg `sport="basketball"`, `league="nba"` (`conf/dev.yml:18–19`; `_wltp_engine.py:170–202`) | v4 `sport="nba"` — `sport` is the **league code** in v4; NBA engine's "sport" is the sport family in engine terms | CONVERT |
| 5 | `game_sk` | `game_sk` bigint | OK; cross-sport uniqueness is a contract/store precondition, unverified here | OK |
| 6 | `pick_kind` | implicit in engine choice (WLTP = game, PS = player) | literal `"game"`/`"player"` per pipeline | DERIVE |
| 7 | `market` | `market_type` is used throughout the engine (h2h/totals/spreads) but never selected into the pick struct; only encoded indirectly in `bet_type`, `bet_bookie_line`, `bet_code` (`_wltp_engine.py:131–166`) | map `h2h→moneyline`, `totals→total`, `spreads→spread`, PS→`player_prop`; pick struct must carry it explicitly | CONVERT |
| 8 | `side` | `bet_type` (6 codes) + `bet_code` `T1`/`T2` + `outcome_name` (`_probability.py:147–180`, `_wltp_engine.py:131–166`) | game: `home`/`away` from backed team slot; **needs venue/home-away source** — `dim_all_games` has no venue/home column (verified `DESCRIBE`), so team_1=home is an unverified convention; totals: `higher_TP/lower_TP → over/under`; PS `bet_type=player_over|player_under` | CONVERT + DERIVE |
| 9 | `line` | not a column. Numeric line recoverable from `bet_bookie_position` for spread/total (it is `outcome_point` cast to string, `_wltp_engine.py:159–166`) or segment 2 of `bet_code`; PS `bet_bookie_line` is the numeric line string (`_ps_engine.py:344`) | parse to JSON number; `null` for h2h; must emit the shortest decimal token (contract §8.2 `line_token`) | CONVERT |
| 10 | `team_sk` | top-level `team_1_sk`/`team_2_sk` + `T1`/`T2` in `bet_code`; not in the pick struct | resolve backed team key; null for totals | CONVERT |
| 11 | `player_sk` | PS has `player_sk` bigint | OK for PS; n/a for game | OK (PS) |
| 12 | `stat_code` | PS `stat_type` ∈ {points, rebounds, assists, threes} (`_config.py:46–55`) | v4 codes are `pts`, `reb`, `ast`, `threes` (`conf-schema-contracts.md:282`) | CONVERT |
| 13 | `probability` | `bet_probability` fraction (e.g. 0.62519) — already the oriented model probability of the picked side (`_wltp_engine.py:182`; `h2h_prob_expr` at `_wltp_engine.py:473–480`) | OK on unit; contract does not cap decimals, but entry_edge must be recomputed from the written p | OK |
| 14 | `projection_value` | **game markets:** `total_points` (model total) and `point_spread` (model margin) exist at agg top level (`_schemas.py:171–172`), not at pick level. **PS:** POF `expected` is joined and used to price (`_ps_engine.py:254–281`) but **is not selected into `PS_ENGINE_OUTPUT`** (final select `:324–366`) | carry per pick: totals→projected total, spread→projected margin, props→expected stat; h2h→null (decision) | MISSING (must be carried) |
| 15 | `projection_unit` | none | literal per market/stat: `points`, `rebounds`, `assists`, `three_pointers` (values themselves are a contract decision) | MISSING |
| 16 | `pick_date_time` | `pick_date_time = run timestamp`, format `"YYYY-MM-DD HH:MM:SS"` with no `T`/`Z` (`_wltp_engine.py:199`; PS `:358`) | must be **first-publish** UTC ISO-8601 ms `Z`, frozen; today it is rewritten on every run (audit shows 10–15 distinct values per pick) | CONVERT (semantics change) |
| 17 | `entry_decimal_odds` | `bet_decimal_odds` = `round(outcome_decimal_odds, 2)` (`_wltp_engine.py:189`; PS `:349`) | 2 dp → up to 4 dp; contract test vectors use 4 dp (1.9091); must be `>1` | CONVERT |
| 18 | `entry_american_odds` | `bet_american_odds` stored as **double** rounded to 2 dp (`_wltp_engine.py:190`) | contract requires integer derived from `entry_decimal_odds` by the §5.2 formula; recompute, don't cast the rounded double | CONVERT |
| 19 | `entry_edge` | `edge = round((our_prob − 1/decimal_odds) × 100, 4)` — **percentage points**, probability basis (`_wltp_engine.py:197`; PS `:360`; schema comments `_schemas.py:87, 227`) | divide by 100 **and** recompute from written `probability` + written 4 dp `entry_decimal_odds` (contract §5.1/§7.2.6: must reproduce exactly from written values); define edge rounding (see §5.1) | CONVERT |
| 20 | `edge_basis` | none persisted. Dev strategy `tiered` selects on the **probability** edge (`_strategy_tiered.py:68–72`); `calibrated_ev_flat` uses EV bounds (`_wltp_engine.py:292–300, 455–457, 596–612`); PS uses probability edge (`_ps_engine.py:287–294`) | derive from the active strategy per pick and persist (`"prob"` for dev/tiered); the BFF/monitor needs it to compute b/m | MISSING (derivable) |
| 21 | `edge_threshold` | none persisted. Tiered minimum edge is **8.0 percentage points** (`_strategy_tiered.py:38–44`); PS minimum is **3.0** (`_config.py:77`); `calibrated_ev_flat` EV bounds are 0.05–0.40 H2H / 0–0.15 totals/spreads (`_wltp_engine.py:292–300`) | persist as a fraction on the chosen basis. Watch the strictness: engine filters `>= 8.0` (`_strategy_tiered.py:71–72`) but the contract requires `entry_edge > edge_threshold`; an edge exactly at threshold violates the contract | MISSING (derivable) |
| 22 | `stake_units` | `bet_bookie_stake = stake_dollars / STAKE_DIVISOR` (`_wltp_engine.py:185`; PS `:344`) — tiered 1.0/2.5/3.5/5.0 units (`_strategy_tiered.py:38–43`), PS flat 1.0 (`_config.py:76–78`), kelly strategies scale dollars/10 | OK as units; must be **frozen** (today it changes across runs — audit shows up to 3 distinct stakes for one pick) | CONVERT (freeze) |
| 23 | `odds_source_kind` | none | derive: NBA prices are per-bookmaker (`bookmaker`), but an AU mirror of a US book is neither honest `bookmaker` for AU nor a computed `market_average` — contract decision (§5.4) | MISSING |
| 24 | `entry_bookmaker_id` | only display name `bet_bookie_name` ("DraftKings", "BetMGM"); PE slugs it with `lower(regexp_replace(name,'[^A-Za-z0-9]',''))` (`nba_wltp.py:255`) | XO needs a canonical slug map (contract examples: `fanduel`, `draftkings`, `sportsbet`); slug rule ownership is a contract decision | MISSING (mapping) |
| 25 | `current_decimal_odds` | none for the published pick. `market_last_update` is the **entry quote's** feed timestamp, consumed as a staleness filter (`_wltp_engine.py:114, 195, 411`) | live observation, null at first publish | MISSING (observation path) |
| 26 | `current_american_odds` | none | null at first publish | MISSING |
| 27 | `current_line` | none | null at first publish | MISSING |
| 28 | `current_odds_source_kind` | none | null | MISSING |
| 29 | `current_bookmaker_id` | none | null | MISSING |
| 30 | `observed_at` | none. `market_last_update` is the feed's update time of the **entry** quote, not an observation of the published pick | observation timestamp; see §3 Rule 4 | MISSING |
| 31 | `is_closing` | none | observation path sets it; engine cannot (cutoff means it never sees the last pre-tip price) | MISSING |
| 32 | `current_edge` | none | observation path | MISSING |
| 33 | `edge_status` | none | observation path / derived | MISSING |
| 34 | `rec_action` | none | literal `null` in 4.0.x | OK (literal) |
| 35 | `pick_status` | no pick status in WLTP. `status` column = **game** status copied from `dim_all_games` (`_wltp_engine.py:191`) and set to `"final"` by settlement (`_update_outcomes.py:51`). PS derives a per-pick status only at aggregation (`_ps_aggregation.py:19–33`) | new lifecycle state machine; game status is an input, not the pick status | MISSING (new state) |
| 36 | `status_reason` | none — the engine never cancels a pick anywhere (`grep` across `src/`: no `cancelled`/`withdrawn`/`status_reason` in the WLTP path) | cancellation policy + reason mapping; state required (Rule 1 re-issue, Rule 2 terminal records) | MISSING (new state) |
| 37 | `outcome` | `bet_bookie_outcome` 1/0/NULL (`_wltp_engine.py:201`; `_update_outcomes.py:45–69`); push and void are both NULL and are **dropped** by `.where(isNotNull())`, so they are never persisted (`_scoring.py:34–43`; `_ps_update_outcomes.py:45–56`) | map 1→`won`, 0→`lost`, add distinct push (2) and void semantics so `outcome` can be `push`/`void`; grade on frozen entry line/side (the +line settlement heuristic at `_scoring.py:39–43` is wrong — see §5.7) | CONVERT (semantics + push/void) |

### 2.1 Current fields the v4 record doesn't have, but which today's consumers use

`taxonomy_version` (dropped in v4), `market_last_update` (no v4 field), `variant` (always `"main"`; contract freezes `main`/`full` in 4.x), `bet_code` display grammar (`T1_-4.5_1.91`), `bet_type` tokens, `bet_price` duplicate of `bet_decimal_odds`, `picks_run_id`/`record_hash`/`run_id` (ops/change-detection). With `additionalProperties:false` the record cannot carry an engine run id; the spec must decide where operational provenance lives (the prior schema-conformance audit worried about the `picks_run_id` format; v4 drops the field entirely). The PE document currently uses `pick_date_time` as `picks_updated_at`; v4 has no update timestamp at all.

---

## 3. Rule 1–6 compliance gap analysis

### Rule 1 — deterministic, region-scoped `pick_id` (+ re-issue suffix)

**Requirement** (`conf-schema-contracts.md:46–51, 313–402`): one canonical formula, region-suffixed, line-aware, stable across price movement; a re-recommendation after a cancelled/withdrawn pick gets `|r2`, `|r3`; legal Cosmos id characters.

**Today [V]:**
- `bet_id = {game_sk}_{bet_type}` (`_wltp_engine.py:181`) — not region-scoped, not line-scoped, and `bet_type` values contain `<`/`>` (`FAV_SPR<`, `UD_SPR<`, `_probability.py:147–180`; live value `40021717855_UD_SPR<`), illegal under the v4 charset.
- The human-readable "id" consumers see is built by PE (`nba_wltp.py:242–253`; player equivalent `nba_ps.py:410–420`) from engine fields and is v4-shaped for game picks today. Nothing persists that id in the engine, so Rule 1 on the engine side is satisfied only by delegating identity to PE — and PE rebuilds it each run from the current row, so any line/selection change silently yields a different id under the same document.
- No re-issue concept exists anywhere; nothing records a cancelled/withdrawn pick, so `r2+` cannot be minted.
- The live merge key `(game_sk, bet_id, bet_bookie_region, bet_bookie_line)` cannot distinguish lines: `bet_bookie_line` for a spread is `T1_spread_under` regardless of the number, so a **line change overwrites the same row** (audit data: same key with 2 distinct `bet_bookie_position` values).
- Totals picks on one game collapse: `bet_id` is `{game_sk}_lower_TP` for every total line (`_probability.py:169–170`), and the selector's merge/dedup keys on `bet_bookie_line` = constant `bookie_total_line_under`, so only one row can survive. (The current strategy emits one pick per game, so this is masked today; it will surface as soon as multiple picks per game are allowed — which persistence requires.)

**What breaks today:** any line move can re-key or overwrite a pick; two picks can share an id shape; no re-issue counter; the id cannot be validated by the producer test suite.

**Work split:** **Engine** — construct and persist the v4 id (needs market token, selection, team slot, line token, lower-case region; §8.4 reference generator exists). **New store/decision** — who owns the re-issue counter and the previous-state lookup (Rule 2 store, below). **PE** — validate id (canonical PE already does) and stop rebuilding it.

### Rule 2 — persistence, no silent drops

**Requirement** (`:52–56`): once published, present in every later publish until terminal; unbacked open picks become `cancelled` with a reason; error picks become `withdrawn`; re-running/pausing must not delete or overwrite published picks.

**Today [V] — the pipeline is explicitly replace/delete-based:**
- `pick_selector` **deletes live_app rows for every future game being refreshed** before merging the new picks: "Purge stale engine-pick rows for FUTURE games being refreshed", `DELETE FROM … WHERE game_sk IN (SELECT … FROM _purge_games …)`, `wltp_pick_selector.py:245–256`. A pick that a later run no longer selects simply disappears.
- Suppressed-team cleanup deletes rows (`wltp_pick_selector.py:205–215`); auto-deduplication rewrites the whole live_app table in `overwrite` mode (`:219–232`).
- The selector merges `whenMatchedUpdateAll` (`:268–300`), i.e. re-published picks get new values rather than frozen ones.
- Aggregation replaces the **whole** `edge_picks` array per game on every run (`_wltp_aggregation.py:121–141`, merge key `game_sk` only), and when the priority region has no pick it writes the single all-null placeholder struct (`_placeholder_edge_picks`, `:46–48`) — i.e. a region can go from a published pick to a zero-value placeholder in one run.
- PS: "Each run replaces the picks of every game it evaluated … a pick the model no longer supports (or a flipped Over/Under) is removed, not left beside the new one" (`ps_engine.py:116–119`), implemented by `replace_game_sks` → `whenNotMatchedBySourceDelete` (`_common.py:227–230`); the disabled switch clears evaluated games by design (`ps_engine.py:19–21`, `_config.py:67–69`).
- Engine table: `upsert_delta` `whenMatchedUpdateAll` (`wltp_engine.py:289–296`, `_common.py:219–226`); audit table is append-only (`wltp_pick_selector.py:288–300`) but is a diagnostic, not a published record and has no frozen-field semantics.
- Nothing writes a terminal record: no `cancelled`, `withdrawn`, `void`, no `status_reason`.

**What breaks today:** Rule 2 is violated by construction on every model revision or config change; the audit table proves history exists but is not the publish stream (358 appended rows vs 28 current live_app rows). There is no place a terminal pick could live even if the code wanted to keep it.

**Work split:** **New store/decision** (a per-`pick_id` record store that survives runs; KDD-001 proposes the Cosmos container written by PE) + **engine** (stop deleting; emit a status update — `cancelled` + reason — instead of omission; keep emitting terminal records; PS switch must stop clearing) + **PE** (whole-record upsert by `pick_id`, no whole-document replace; validate before write).

### Rule 3 — frozen entry state

**Requirement** (`:57–58, 645`): 23 identity/selection/model/entry fields frozen at first publish; later writes may only change `schema_version`, `current_*`, `observed_at`, `is_closing`, `edge_status`, `rec_action`, `pick_status`, `status_reason`, `outcome`.

**Today [V] — every entry field is recomputed and overwritten on every run:**
- `wltp_engine._derive_final_output` derives `bet_probability`, `bet_decimal_odds`/`bet_american_odds`, `bet_bookie_stake`, `bet_bookie_position`, `pick_date_time` from the current run (`_wltp_engine.py:131–202`), then the table merge is update-all (`wltp_engine.py:293–296`, `_common.py:219–226`). The selector re-merges all columns to live_app (`wltp_pick_selector.py:268–300`).
- **Data evidence [V]:** the audit table shows the same `(game_sk, bet_id, bet_bookie_region, bet_bookie_line)` key across **10–15 runs** with `bet_decimal_odds` moving 1.87→1.95, **two different numeric lines** under the same `bet_bookie_line` token, **3 distinct stake values**, and `pick_date_time` moving 2026-10-16 → 2026-10-20. Every one of those is a Rule 3 violation on fields that must be frozen.
- `pick_date_time` is the run timestamp, not first-publish (`_wltp_engine.py:199`); no first-publish timestamp is stored anywhere.
- No field-level freeze enforcement, no previous-state comparison, no "update only allowed columns" merge anywhere in the engine (nor in PE: the writer upserts the whole document).

**What breaks today:** a consumer computing b, m or the display edge from the record gets values that change each run; the monitor's entry baseline would silently move; audit/replay is impossible; Rule 3 is unfalsifiable without a store.

**Work split:** **New store/decision** (first-publish values must be retrievable; either the engine owns a record table with insert-once semantics or PE's record store enforces it) + **engine** (split write path into insert vs update-allowed-columns; stamp `pick_date_time` once; stop re-deriving frozen fields on re-runs) + **PE** (write only the allowed live fields on updates, ideally etag-guarded — KDD-001).

### Rule 4 — `observed_at` is the observation time, not the write time

**Requirement** (`:59–60`): whenever a record carries a live observation, `observed_at` is when the price/pulled state was observed at the book/feed.

**Today [V]:** no observation fields exist in the engine or agg. The nearest field, `market_last_update`, is the **odds feed's** update timestamp for the entry quote — used to reject stale quotes before tip (`_wltp_engine.py:411`) and carried to the agg (`_schemas.py:88`, live value `2026-10-19T04:59:27.000Z`). It is not the time the record's pick was observed, and the engine never re-observes a published pick. PE carries it into the current doc as `market_last_update`; v4 has no such field, so even that proxy disappears.

**What breaks today:** nothing can populate `observed_at` truthfully from the current pipeline; the only honest observation source is a new monitor/observation feed (§4).

**Work split:** **Observation path** (monitor observes at the feed, PE writes) + **engine** must expose what the observer needs (stable `pick_id`, frozen entry p/d/line/basis/threshold) — no engine timestamp can substitute.

### Rule 5 — single coherent record stream and closing flag

**Requirement** (`:61–62`): entry publication, pre-game observations (≤5 min), status transitions and settlement update **the same logical record** without clobbering frozen fields; `is_closing` true only on the final pre-game observation when the game starts.

**Today [V]:**
- There is no single record: the same pick exists as up to four independent rows/documents — engine table row, live_app row, agg nested array element, audit row — plus a PE document keyed by game. Writes land at different times, with different keys, and the agg replaces the array wholesale (`_wltp_aggregation.py:121–141`).
- No `is_closing`; no closing observation at all: the engine will not touch a game within `cutoff_minutes` of tip (`_wltp_engine.py:411, 435`, dev cutoff 5 min, `conf/dev.yml:20`), so the last engine write is ≥5 minutes before tip and is an **entry recomputation**, not a closing observation.
- Settlement writes only `bet_bookie_outcome`+`status` on the engine/live_app row (`_update_outcomes.py:54–69`); it never updates a record keyed by pick.
- PE's writer replaces the whole document on every CDF row (`nba_wltp.py`/`nba_ps.py` select + upsert), so concurrent observation/status updates are not composable — there is no etag guard.

**What breaks today:** any attempt to bolt observations or cancellation onto the current tables will race the entry rewrite and be lost on the next run; the closing observation cannot exist in the engine's window; the record a consumer sees is whichever table was written last.

**Work split:** **New store/decision** (one logical per-`pick_id` record; KDD-001's Cosmos doc + PE whole-record etag upsert) + **observation path** (monitor → observation store → PE) + **engine** (write entry and lifecycle updates only, never re-derive; perform the `open→awaiting_result` transition or hand it to a scheduled task at tip-off) + **PE** (merge observation + batch output into the whole record).

### Rule 6 — forward-only lifecycle

**Required states** (`:70–100, 241–243`): `open → awaiting_result → settled|void`; pre-game `open → cancelled|void|withdrawn`; never backwards; `settled` carries `won|lost|push`; `void` carries `outcome=void`.

**Today [V]:**
- The engine has **no pick status at all** for game markets; its `status` column is the **game** status from `dim_all_games` (`_wltp_engine.py:191`; 2026 values observed: `scheduled`, `in_progress`, `final`) and settlement overwrites it with `"final"` when an outcome is computed (`_update_outcomes.py:51`).
- There is no `awaiting_result`: a game that starts simply stops being updated; `is_closing` doesn't exist.
- There is no `cancelled`, `withdrawn`, `void`, or `status_reason` in the WLTP code path (verified by grep across `src/`).
- PS derives a pick status only at aggregation time from game status + outcome (`_ps_aggregation.py:19–33`): `final`+NULL → `"void"` (so a **push is mislabelled void** and a genuinely unsettled final game is labelled void), `cancelled` game → `"cancelled"`, else `"scheduled"`/`"active"`. This vocabulary is not the v4 vocabulary and is lossy.
- Outcome semantics: `_scoring.py` returns 1/0/NULL; a spread landing exactly on the line returns NULL (`:34–36`), a totals push returns NULL (`:37–43` semantics), and `_update_outcomes` filters `.where(bet_bookie_outcome.isNotNull())` (`:49`) so pushes are never persisted; PS DNP and push both return NULL (`_ps_update_outcomes.py:45–56`) and are likewise never persisted. So `push` and `void` cannot be produced today. The plus-line spread win condition (`_scoring.py:39–43`, "picked team won OR margin < abs(line)") is a heuristic, not spread settlement — final grading would be wrong on some picks even if the vocabulary existed.
- Nothing prevents a backwards transition: status is re-derived from the current game row on every write.

**What breaks today:** a cancelled/postponed game leaves a pick that never terminates; pushes and DNP voids are invisible; `awaiting_result` never published; settlement can grade against a heuristic rather than the frozen entry line.

**Work split:** **Engine** (state machine + cancellation/withdrawal emission + game-start transition + settlement grading fixes; scoring fix is independent and can ship first) + **new store** (prior status for forward-only enforcement, terminal records, `pick_date_time`/entry freeze) + **PE** (validate status enum and forward transitions; canonical PE already raises on invalid enum, `canonical_transformations.py:199–223`) + **contract decision** (cancelled→open question, contract §11).

### Rule compliance summary

| Rule | Can the engine satisfy it by changing its own output only? | Blocking dependency |
|---|---|---|
| 1 identity | Mostly yes (build id; needs team slot/side/venue and line token) | contract: id ownership, venue source; store: re-issue counter |
| 2 persistence | No | **store** (where terminal records live) + contract (cancellation policy) |
| 3 frozen entry | No | **store** (first-publish values) + write-path redesign |
| 4 observed_at | No (needs observation source) | **observation path** (monitor) |
| 5 one record/closing | No | **store + observation path + PE writer** |
| 6 forward-only lifecycle | No | **store + status policy + settlement fixes** |

---

## 4. Who writes the live observation fields?

`current_decimal_odds`, `current_american_odds`, `current_line`, `current_odds_source_kind`, `current_bookmaker_id`, `observed_at`, `is_closing`, `current_edge`, `edge_status`.

**What the contract says [V]:** §1 lists the Live Edge Monitor as a consumer that "tracks live market prices and edge states for open picks"; §5.3 defines the `edge_status` decision table and says "whenever a record is written, `edge_status` is determined…"; §5.1 defines `current_edge`; Rule 4 defines `observed_at` semantics; Rule 5 says observations are "delivered within 5 minutes of observation" and `is_closing` becomes true "on the final pre-game market observation when the game starts". **Nowhere does the contract assign which component computes/owns these fields, where the observation arrives from, or who decides the final pre-game observation.** The word "producer" in §5.4 ("Additional producer calculation rules") is ambiguous between bet engine, monitor and PE.

**What the design corpus says [D]** (`producers-to-bff.md:33`; `kdds.md:35`; `realtime-overlays.md`): only the Publish Engine writes pick documents; the monitor computes `edge_status`/`observed_at` and its observations reach the record **through PE**; `is_closing` is "derived by the Publish Engine" (`producers-to-bff.md:576`). That is a coherent division but it is **not in the contract** — it is in a separate staging page and the KDDs are still "Proposed".

**Who is actually capable today [V]:**

| Field | Only party that can know it | Can the engine produce it? |
|---|---|---|
| `current_decimal_odds` / `current_american_odds` / `current_line` | live odds feed observer | **No** — engine stops 5 min before tip (`_wltp_engine.py:411`) and never re-observes after publish |
| `observed_at` | observer, at the feed | **No** (market_last_update is the entry quote's feed update time) |
| `is_closing` | observer + game-start clock | **No** — requires seeing the last pre-tip price, which is inside the engine's cutoff |
| `current_edge` | any party, from frozen p + observed price (formula in §5.1) — but must use the **stored entry** basis/threshold | Only if it receives observations; engine has no post-publish loop |
| `edge_status` | same | same |
| `current_odds_source_kind` / `current_bookmaker_id` | observer (which feed) | same |

**Current monitor reality [V]:** `live-odds` @ dev / e2c04ca covers **NFL only**; it reads published picks from the Delta output tables, builds its own ids as `{bet id}|{REGION}` (which match no v4 `pick_id`), computes an edge status from entry probability/EV threshold (`shared/edge_status.py`), and writes Cosmos **overlay** nodes, not pick records. Its design explicitly rejects writing engine tables or PE documents (`EDGE_PICKS_LIVE_ODDS_DESIGN.md` D7/section 2). An NBA monitor that feeds the record store does not exist yet [A].

**Consequence of the unassigned ownership:** (1) the engine cannot be held to Rules 4–5, and any engine-side attempt to populate these fields would be a guess; (2) PE has no declared observation input, so the record will carry nulls or stale entry values; (3) the monitor's own contract (ids, entry probability/line/price/basis/threshold, region) depends on fields the engine does not yet emit — in particular `edge_basis` and `edge_threshold`, without which the monitor cannot compute b/m or `edge_status` (it currently invents `t=0` and uses its own id scheme: `realtime-overlays.md` §"How the monitor computes edge_status"; `producers-to-bff.md` "Live edge monitor" row). **The engine work is therefore limited to (a) emitting the frozen entry fields the observer needs and (b) never overwriting them; the write path and the 5-minute rule need a contract assignment.**

---

## 5. Domain modelling gaps

### 5.1 Edge unit, basis, threshold, rounding

- **Unit:** engine `edge` is percentage points (`_wltp_engine.py:197`, `_ps_engine.py:360`, schema comments `_schemas.py:87/227`); live values 2.4–28.9. v4 wants a fraction (`conf-schema-contracts.md:33`, test vector P-3: 5.0 pts → 0.05). Naive `/100` of the persisted 4-dp value is not enough: the contract requires `entry_edge` to be recomputable from the **written** `probability` and **written** `entry_decimal_odds` (§5.1, §7.2.6). The engine rounds odds to 2 dp (`_wltp_engine.py:189`), so the emitted edge would not reproduce the 4-dp test vectors (P-1 uses 1.9091). **Recommendation: emit 4-dp odds and recompute edge from written p and written odds; do not divide the old stored edge.**
- **Basis:** the engine never persists which basis it selected on. Dev/tst run `tiered` (probability edge, `_strategy_tiered.py:68–72`); `calibrated_ev_flat` selects on EV with EV bounds (`_wltp_engine.py:292–300, 455–457, 596–612`); PS selects on probability edge (`_ps_engine.py:287–294`). A single `edge_basis` constant for "NBA" would be wrong the moment a strategy is switched; it must be emitted per pick from the active config.
- **Threshold:** similarly not persisted. Tiered minimum is 8.0 pts (`_strategy_tiered.py:44`), PS 3.0 pts (`_config.py:77`), half-kelly/kelly have no explicit minimum beyond edge>0 and Kelly>0, EV mode has per-market EV bounds. Also the tiered filter is `>=` while the contract requires `entry_edge > edge_threshold` — at exactly 8.0 pts the record would violate its own invariant unless the threshold is written slightly below the filter (or the filter becomes `>`).
- **Rounding:** the contract says entry/current edge are computed from written values but does not state the rounding of `entry_edge` itself or of `probability`; test vectors show 4 dp. Two producers will differ at the last digit unless this is pinned. Also `current_edge` may be negative (§6.4) while `entry_edge` must be `>0`.

### 5.2 Probability basis and push handling

- `probability` today is the oriented model probability of the picked side: `h2h_prob_expr` for moneyline (`_wltp_engine.py:473–480`) and CDF-based `our_prob` for totals/spreads (`:482–530`, `_probability.py`). Unit is already a fraction and semantics match v4 §6.3 ("model win probability on which the pick was selected").
- There is no probability smoothing towards the market in WLTP; PS explicitly removed it (`_ps_engine.py:285–286`, `_config.py:70–74`, "model probability used as priced"). So §5.4 blending rule is satisfiable with the raw value — a decision the record does not need to make.
- **Push subtlety:** totals probabilities are computed with pushes excluded by construction (`_probability.py:243–256`: Over = P(total > line), Under = P(total < line) on the grid, so Over+Under < 1 on integer lines); spread probabilities are a continuous normal at the line (`:82–116`). On whole-number lines (which v4 explicitly allows, §4.2) `probability` is therefore P(side wins) with the push mass not counted as a win for totals (so p + P(push) < 1 on an integer line), while the spread CDF treats the line as continuous and effectively ignores the push mass. If `entry_edge` is to mean anything across whole-number lines, the contract must state whether `probability` is P(win) (push excluded) or something else, and what b/m mean when a push exists. The engine's settlement side currently cannot represent push at all (§5.7).
- H2H: `win_loss_prediction` is an int 1/0 and `win_loss_probability` the probability of the predicted winner; the engine flips it for the other side. That's consistent, but note the record's `probability` is only defined for the **selected side**, so the producer must not emit the model's winner probability by mistake.

### 5.3 Stake units

- `bet_bookie_stake` is already in units after `stake_dollars / STAKE_DIVISOR` (`_wltp_engine.py:185`, `_ps_engine.py:344`); tiered 1/2.5/3.5/5.0 (`_strategy_tiered.py:38–43`), PS flat 1.0 (`_config.py:76–78`), kelly variants `stake_dollars = units × 10`. So the v4 `stake_units` maps cleanly — **but it is recomputed each run** and the audit shows up to 3 distinct stakes for one pick after tier thresholds moved the pick between tiers (a Rule 3 freeze violation). Also `stake_units` in v4 must be `>=0`; tiered Tier 0 (no bet) is filtered out before output, which is correct — a "no bet" must not become a 0-unit record.

### 5.4 Bookmaker and region (US bookmaker vs AU market_average)

This is the largest semantic gap after persistence.

- **Facts [V]:** silver `fact_game_odds` has only `bookmakers_region='us'`; the engine's AU candidate list has no prices; aggregation clones the US pick into AU and sets `bet_bookie_region="AU"` while keeping the US bookmaker name (`DraftKings`/`BetMGM`/…). The live table proves it (AU slots carry US books; AU and US slots are otherwise byte-identical). `_live_odds.py:32` documents the same intent for the live adapter ("US-derived odds to both au and us").
- **v4 semantics:** `region` is "Target region for which the pick and its sportsbook pricing were published"; `odds_source_kind ∈ {bookmaker, market_average}`; `entry_bookmaker_id` must be null iff `market_average`. A US-book price presented as an AU record's `bookmaker` entry is misleading (AU bettors cannot bet DraftKings), while `market_average` implies an average the engine does not compute. **The contract must decide what AU means for NBA** — mirrored US book (and then the record should say so), a market average over all US books, or genuinely AU-sourced prices (needs a new odds feed). The engine's current strategy cannot emit honest AU `entry_bookmaker_id`/`odds_source_kind` without that decision.
- Relates also to region-scoped `pick_id`: under a mirror model the AU record is a **separate pick** with its own id (§3 Rule 1) but identical numbers; under a real AU market it can differ. Persistence then has to handle both records independently.
- **Bookmaker id:** engine carries display names only; PE slugs by stripping non-alphanumerics (`nba_wltp.py:255`). If the engine becomes the producer, a canonical slug map must live somewhere (contract or a shared taxonomy). Contract examples use `fanduel`, `draftkings`, `sportsbet`; note `BetMGM → betmgm`, `BetOnline.ag → betonlineag`, `LowVig.ag → lowvigag`, `MyBookie.ag → mybookieag` under the current rule.

### 5.5 Projections

- **Game markets:** the engine computes `model_total`/`model_spread` (`_wltp_engine.py:340–390`; the agg table carries the floored `total_points`/`point_spread`) but the pick struct has no projection field. v4 wants the model's projected value **at the entry line**: totals → projected total (`total_points`, unit `points`), spreads → projected margin (`point_spread`, unit `points`), moneyline → no numeric projection (null) unless the contract wants predicted scores. Today's PE drops these from the pick document entirely.
- **Player props:** the projection exists upstream (`POF.props.<stat>.expected`, joined at `_ps_engine.py:254–281` and used to price) but is **not selected into `PS_ENGINE_OUTPUT`** (`:320–366`), so it is lost before aggregation/PE. The value is latent, not missing — add one column.
- `projection_unit` values for NBA are not defined anywhere (contract examples are generic `points`/`yards`/`runs`; §7.3 only fixes `stat_code`). Decide units per stat: likely `points` (pts), `rebounds` (reb), `assists` (ast), `three-pointers made`/`three_pointers` (threes). The engine also has no projection for H2H — must be null, and `projection_value`/`projection_unit` co-null per §6.3.

### 5.6 Cancellation (lineup change) vs line moves

- **Today [V]:** the engine never cancels; the pipeline's only response to "no longer the best pick" is to drop/replace (§3 Rule 2). There is no lineup/injury input to the engine at all (injuries live in `nba_silver.fact_team_injuries`, watched by PE but not read by either engine — grep across `src/` finds no injury read).
- **Contract [V]:** `status_reason` codes are `probability_moved`, `market_moved`, `lineup_change`, `withdrawn`, `game_void`; "a line move alone never cancels a pick" (`:114–116`), and the exact trigger policy is an **open decision** (`:891`, due Oct 30). `edge_status=closed` must never change `pick_status` on its own (`:116`).
- **Engine implication:** to emit `cancelled` the engine needs (a) the previous published pick state, (b) a re-evaluation rule that distinguishes "probability no longer clears threshold" from "price moved past break-even" from "player/team lineup change", and (c) a decision on whether the replacement recommendation is a new pick (`new pick_id`) with the old one cancelled — which is the only forward-only-compatible behaviour. `lineup_change` additionally requires an injury/lineup feed and a rule for which changes matter (starter scratch vs questionable); the engine has none today.
- **Interaction with one-pick-per-game:** today's strategies explicitly keep one bet per game (`_strategy_tiered.py:24–29` dedup one per game; AGENTS.md:87 "only a newer pick for the same game replaces it"; top5 `spreads_primary`). Under v4, replacing means cancel + new record. That doubles the record count per game over a day and requires the store (above). Alternatively the engine keeps one open pick and only cancels when it stops backing the same selection+line. This is a product/contract decision.

### 5.7 Status vocabulary mapping

| Today (engine/PS/PE) | Source | v4 mapping | Problem |
|---|---|---|---|
| `scheduled` (game status copied) | `_wltp_engine.py:191`; live rows | `open` | OK before tip |
| game `in_progress` (if a run happens) | `dim_all_games.status_state` observed values: scheduled/in_progress/final | `awaiting_result` | never written today: engine doesn't update after tip and agg only refreshes when the engine/live_app changes; PE's canonical branch only republishes within window or when graded (`canonical_transformations.py:743–748`) |
| `final` + outcome 1 | `_update_outcomes.py:51` | `settled` + `outcome=won` | OK |
| `final` + outcome 0 | same | `settled` + `outcome=lost` | OK |
| push = NULL, never persisted | `_scoring.py`, `_update_outcomes.py:49` | `settled` + `outcome=push` | **cannot be produced**: NULL is filtered out; no distinction from ungraded |
| DNP = NULL, never persisted (PS) | `_ps_update_outcomes.py:45–56` | `void` + `outcome=void` (+`status_reason` per policy — DNP is a market void, not `game_void`) | **cannot be produced**; contract's `status_reason` enum has no DNP code (open decision in §11 asks about adding codes) |
| game `cancelled`/`postponed` | `dim_all_games.status`/`postponed`; PS agg maps `cancelled→cancelled` | `void` + `status_reason=game_void` (contract) — **not** `cancelled` | PS agg maps it to the wrong status; WLTP has no path at all |
| `withdrawn` (published in error) | no path | `withdrawn` | no engine path; needs an operator/tooling decision |
| engine "no longer backs the same pick" | implicit row deletion | `cancelled` + reason | not implemented |
| PS `active`/`pending` | `_ps_aggregation.py:19–33` | `open`/`awaiting_result` | non-v4 vocabulary; `final`+NULL → `void` mislabels push |
| PE `pick_status` (published doc today) | `nba_wltp.py:231–238` maps 1→won, 0→lost, 2→push, else scheduled | matches v4 outcome partly | `2` never produced; final+NULL shows `scheduled` |

Also: the contract's `settled` grade must be evaluated against the **frozen entry line and side**; the current scoring uses `bet_code`/`bet_bookie_position` (frozen today only by accident) and has the plus-line heuristic (`_scoring.py:39–43`) that is not spread settlement.

### 5.8 Pre-game cutoff vs closing observation

- Engine cutoff is `cutoff_minutes=5` in dev/tst (`conf/dev.yml:20`; `_config.py:9` default 30) and it also requires the **quote** to be older than the cutoff before tip (`_wltp_engine.py:411`). Therefore the engine's last possible write is >5 min before tip — it can never observe the closing price, and a v4 record produced by the engine alone would have `is_closing=false` forever and no final pre-game observation.
- The monitor's 5-minute rule and `is_closing` therefore inherently belong after the engine's cutoff; whoever implements the observation path must run between the engine's last run and tip-off (and the contract's "delivered within 5 minutes of observation" applies to monitor→record, not engine→record). This is a real scheduling/architecture constraint the contract should state, because it determines that **the engine cannot be the `is_closing` writer**.

### 5.9 Alternate lines / variant

- Engine `variant` is hardcoded `"main"` in both engines (`_wltp_engine.py:202`, `_ps_engine.py:361`); no alternate is emitted.
- Silver odds do carry alternate lines (up to 22 distinct `outcome_point` values per game for spreads/totals), but the engine collapses them at the odds-window dedup (`_wltp_engine.py:414–421` partitions by `game_sk, bookmakers_name, market_type, outcome_name`, **not** `outcome_point`), then the strategy keeps one bet per game (highest edge). So alternates are discarded before pick selection.
- v4: alternates are represented by their `line` value with `main`/`full` literals fixed in 4.x (`:274`, §8.2). A future alternate-line pick is just a new `pick_id` with a different line token — supported by the id, but the engine would need to stop collapsing lines and the strategy would need an explicit alternate-lines policy. Not blocking for the first compliant record, but it conflicts with the current merge key (line-number-blind) and with the one-pick-per-game strategy. **Later work.**

### 5.10 One-pick-per-game strategy vs persistence

- Current strategy output is at most one pick per game per region: tiered dedups one bet per `game_sk` (`_strategy_tiered.py:77–86`), top5 spreads-primary deliberately suppresses totals when a spread exists (AGENTS.md:85–88), and the selector's default `multi_per_type` only keeps one per `(game, region, bet_type, line)` (`_wltp_pick_selector.py:128–137`) after the strategy's per-game dedup. Live data confirms 2 slots per game = 1 pick × 2 regions.
- v4 persistence means picks accumulate: every recommendation that was ever published must remain until terminal, so the store will hold several picks per game over the pre-game window. If the strategy keeps "one live pick per game", the engine must emit cancellation for the superseded pick **and** still republish the terminal record (Rule 2) — the strategy's dedup is a selection decision, but lifecycle is a record decision. If instead multiple picks per game are allowed, the id/store/selection all work, but the product's "one pick per game" display rule is a BFF concern (KDD-002's one-pick slot rule). Either way, **the engine's current "replace" behaviour cannot be carried into v4**.
- Effort driver: this changes the shape of the engine's output table (one row per pick vs one row per game) and the merge key (full pick identity incl. numeric line), not just a column.

### 5.11 Identity details the engine must resolve

- **Team slot / home-away:** v4 `side` is `home|away` from the **venue**, while `pick_id` uses the schedule slot `t1|t2`; the contract explicitly warns not to conflate them (§7.2.1, §8.2). `dim_all_games` has `team_1_sk`/`team_2_sk` and no venue/home column (verified `DESCRIBE`), so today's engine (and PE) implicitly treat `team_1 = home`. That is unverified [A] and needs either a schedule venue field or an explicit convention agreed with the consumers. The engine has the backed team's `team_sk` implicitly (outcome team name vs `team_1_full_name`), and the `bet_code` `T1`/`T2` prefix; it must explicitly carry `team_sk` and derive `side` from the venue source.
- **Line token:** the contract requires the shortest decimal that round-trips (`24.5`, `-4.5`, `3.0`, `220.0`, never `-0.0`). The engine's numeric line is a double cast to string for `bet_bookie_position` (Spark double→string yields `235.5`, `1.5`; whole numbers should be checked for `"3.0"` vs `"3"` in the deployed Spark version) and lives in `bet_code`. The producer should construct the token from a numeric double using the reference `line_token()` (§8.4), not from the existing string, to guarantee agreement.
- **Player ids:** current PS `bet_id` is `{game_sk}_{player_sk}_{stat_type}_{bet_type}` (no line, `_ps_engine.py:337–341`); PE's published player id adds line/variant/`full`/region but uses a `player_milestone` token and an integer threshold for milestones (`nba_ps.py:410–420`), while v4 normalises milestones to `side="over"` with `line = k − 0.5` (§7.2.3) and allows only `player_{side}` tokens. NBA's current PS scope is over/under main lines only, so nothing conflicts today, but the id/milestone rule must be settled before milestone props (BR-06a) are added.
- **Region case:** engine/live emit `us`, aggregation emits `US`/`AU`; v4 requires lower-case and the id suffix. Normalise at the record boundary.
- **`pick_id` length/characters:** all engine-derived tokens (`spread_t1`, `total_over`, `player_over`) satisfy the charset; `bet_type` does not (`<`/`>`), so it must not leak into identity.

### 5.12 Dropped metadata the engine currently relies on

The v4 record has no `taxonomy_version`, `market_last_update`, `variant`, `bet_code` or engine run id. Consequences: (a) the current PE document carries `taxonomy_version` "1.0" for the BFF; v4 replaces it with `schema_version` only, so anything that keys on taxonomy must be re-pointed (BFF/PE concern); (b) the entry quote's feed timestamp is lost — if consumers need to know how fresh the entry price was, the contract must add a field (breaking `additionalProperties:false`) or accept the loss; (c) operational provenance (run id/record hash) must live outside the record (Cosmos/DELTA envelope) and the record store needs its own change-detection.

---

## 6. Prioritised engine work list

Effort is expressed as **drivers**, not time estimates.

### Blocking — nothing compliant can be emitted until these land

| # | Work item | Why blocking | Depends on | Effort drivers |
|---|---|---|---|---|
| **B1** | **Contract decisions in §7** (record producer, store, observation owner, cancellation policy, region semantics) | Every item below encodes one of them; building first means rebuilding after | — | Review/sign-off cycle; the cancellation policy is one of the contract page's five open decisions (`:891`), while record/store ownership, observation ownership and region semantics are absent from §11 entirely |
| **B2** | **Emit the 37-field record as the engine's output** (one row/record per pick per region) rather than a game-state row with nested arrays; new/likely separate Delta table, new `_schemas.py` structs | Rules 1–3, 5, 6 all need a per-pick object; the current nested-row shape cannot carry per-pick lifecycle or freeze | B1 | New StructTypes; rewrite of `_wltp_engine` derivation select, `_wltp_aggregation` (explode pick × region instead of nested array), `_ps_engine`, `_ps_aggregation`; golden fixtures/tests; downstream PE task list |
| **B3** | **Deterministic, line-aware, region-scoped `pick_id` + all frozen identity/selection fields** (`market`, `side`, `line`, `team_sk`/`player_sk`, `stat_code`) | Rule 1, and Rule 3's frozen set; also what the monitor keys overlays on | B2; venue/home-away source | Field derivation from `bet_type`/`bet_code`/`outcome_point`; team-slot resolution; reference-generator tests (ids and line tokens: `3.0`, `-4.5`, `220.0`); edge cases (H2H null line, totals sign, player milestone normalization) |
| **B4** | **Edge basis/threshold + probability/odds/edge rounding discipline** (`edge_basis`, `edge_threshold` per pick; 4-dp decimal odds; integer American odds; `entry_edge` recomputed from written values) | Rules 1/3/5; the monitor and BFF cannot compute b/m/edge state without it; current pct-point edge is unusable | B2, B3 (written p/odds are inputs); contract rounding decision | Strategy-config → basis/threshold mapping per strategy (tiered/half_kelly/kelly/calibrated_ev_flat, PS flat); strict `>` vs `>=`; unit tests with the contract's P-1…P-9 vectors |
| **B5** | **Per-pick persistence and first-publish freeze** — insert-only frozen fields, allow-listed update columns, `pick_date_time` stamped once; stop update-all merges; stop purges/deletes; stop PS `replace_game_sks`; emit terminal records instead of dropping | Rules 2 and 3 are violated today by every run; audit data proves the drift | B1 (store ownership), B2 | New merge/write helper; previous-state lookup or write discipline (insert vs update); audit/history table semantics; PS switch behaviour; migration of current live rows; tests for "two consecutive runs → frozen fields identical" |
| **B6** | **Lifecycle state machine**: initial `open`; `open→awaiting_result` at tip; `open→cancelled` when the engine stops backing (with reason) or `withdrawn` on error; re-issue `|r2…` minting; forward-only guard | Rules 2, 6; also Rule 1's suffix | B5 (prior state), contract decision on cancellation/re-issue | State enum + transition table; cancellation rule from re-run diff (probability threshold vs market price vs lineup); game-start clock/scheduler; re-issue counter storage; tests for forward-only and re-issue |
| **B7** | **Settlement correctness for `outcome`** — push as a persisted value (contract push matrix), void/DNP/game-void as `void`, grade on frozen entry line/side, fix plus-line heuristic; fix `_update_outcomes` null filter | Rule 6 (`settled`/`push`, `void`); today push/void are dropped and the spread grade is wrong | Contract decision (push/void semantics, DNP reason); can ship independently of B2–B6 (it is a scoring fix on existing tables) — **start early** | `_scoring.py` rewrite + tests against the contract's push examples; `_ps_update_outcomes.py`; idempotent merge; historical backfill question |
| **B8** | **Carry the projections** (`projection_value`/`projection_unit`): moved total/spread at pick level; POF `expected` for props | Required non-null-when-projection-exists semantics; currently computed then discarded | B2; contract unit vocabulary decision | Small per engine (one column each) but touches POF join contract and fixtures |
| **B9** | **Bookmaker/region export**: canonical `entry_bookmaker_id` slug + `odds_source_kind`; region-scoped records that are honest about AU | Rule 2/3 per region; the AU mirror is semantically false today | B1 (AU pricing decision) | Slug map; region assignment; AU strategy (mirror vs market average vs new feed); possible new odds-feed work; PE/BFF coordination |
| **B10** | **Producer-side contract test gate**: validate every emitted record against the §9 JSON Schema and the six cross-record invariants (`:638–646`) in CI (golden fixtures); engine CI currently only runs `databricks bundle validate` (AGENTS.md:130) | The freeze/rounding/id rules are cross-record invariants that no single-record schema can catch; without a gate they will drift silently | B2–B5 | Test harness, golden fixtures per market/kind/region, CI wiring; small but continuous |

### Later / can follow the first compliant publish

| # | Work item | Notes |
|---|---|---|
| **L1** | Observation-path integration on the engine side: place `current_*`/`observed_at`/`is_closing`/`edge_status` columns null at publish and accept them from PE/observer; ensure re-runs never touch them | Depends on B1/B5 and the monitor contract; the engine should not own the observer |
| **L2** | Alternate lines policy: stop collapsing alternate `outcome_point` at odds dedup; decide whether alternates are ever emitted; merge by full numeric line | Not needed for v4 launch (`main` literal fixed); conflicts with one-pick-per-game |
| **L3** | Multi-pick-per-game selection policy (if product wants more than one live pick) | BFF slot rule is BFF-side (KDD-002); engine only needs to allow it in selection |
| **L4** | Remove/deprecate legacy fields (`bet_type`, `bet_code`, `bet_price` duplicate, `top_picks`, `record_hash`, `picks_run_id`), and align ops metadata storage | After PE/BFF migrate; avoid breaking the remaining legacy readers during coexistence |
| **L5** | Backfill/replay tooling for historical picks (audit table → records) and shadow validation against PE | Needed for rollout/rollback evidence; effort in tests + data QA, not engine logic |
| **L6** | season-parameterisation is already done (widget `season` 2026, `conf/dev.yml:17`) — verify no hardcoded dates remain (`engines_start_date` default 2026-05-01 in `_wltp_pick_selector.py:38/59`, still a magic date) | Small cleanup |

### Dependency order (high level)

`§7 decisions (B1)` → `B2 (record shape + identity)` and `B7 (settlement scoring)` in parallel → `B5 (persistence/freeze)` → `B6 (lifecycle/cancel/re-issue)` → `B3/B4` can start with B2 but must be frozen before B5 → `B8/B9/B10 (projections, region, CI gate)` → `L1 (observation)` → `L2–L6`.


---

## 7. What the contract must decide before engine work starts

| # | Decision | Why the engine is blocked | Provisional answer the engine could assume if forced |
|---|---|---|---|
| **D1** | **Who is the producer of the record and where does first-publish state live?** Engine emits the full record vs PE projects it from engine rows; owner of the published-pick store (engine Delta table / PE record store / Cosmos record container as KDD-001) | Rules 1–3 and 6 need previous-state lookup and a terminal-record home; the contract names "producers" as engines and PE as "only writer", but not who persists records between publishes | Engine emits a per-pick Delta record table keyed by `pick_id`; PE validates and writes Cosmos, preserving frozen fields (needs PE read-modify-write) |
| **D2** | **Observation fields owner + transport**: who computes `current_*`/`current_edge`/`edge_status`, who sets `observed_at`/`is_closing`, which table/page carries the observation into PE, and the id contract the monitor uses | Rule 4/5 and every `current_*` field in the record; engine has no post-publish loop and stops 5 min before tip, monitor ids don't match | Monitor computes, PE merges/writes (corpus default); contract must say so and define `is_closing` at game start |
| **D3** | **Frozen-field enforcement point** and the definition of "first publish" (first record write? first document write? first time a pick appears in a publish) | B5: whether the engine must be write-once or PE enforces first-write-wins changes the whole write path | Producer must not change frozen fields; writer preserves first values (defence in depth) |
| **D4** | **Re-issue (`r2+`) semantics** and whether a cancelled pick may reopen (contract's own open item, `:888`) | B6: the engine can only mint suffixes if the counter/rule exists | No reopen (forward-only); suffix minted on first re-recommendation after a terminal pre-game status |
| **D5** | **Cancellation policy and reason mapping** (which re-evaluations cancel; `probability_moved` vs `market_moved` vs `lineup_change`; what feeds lineup changes; line move alone never cancels) — contract open item due Oct 30 (`:891`) | B6: the engine cannot decide when to cancel or which reason without it | Tiered/top5 re-run diff: if the same selection+line no longer clears its threshold → `probability_moved`; if price below break-even → `market_moved`; lineup feed absent → no `lineup_change` at launch |
| **D6** | **Region/odds-source semantics for NBA** (AU = US mirror vs market average vs new AU feed; `odds_source_kind` for mirrors; `entry_bookmaker_id` nullability) | B9 and B3 (region in id); the current AU records misstate the bookmaker | AU record is a mirror of the US book: `odds_source_kind="bookmaker"`, `entry_bookmaker_id` = the US book, `region="au"`; contract should say so explicitly |
| **D7** | **Rounding/definitional rules**: edge rounding (entry/current), probability precision, 4-dp odds, American-odds derivation, `entry_edge > edge_threshold` strictness vs engine `>=`, whole-number line push treatment | B4: without it the engine cannot guarantee invariant #3 (`:643`) and test vectors P-1…P-9 across producers | 4-dp odds, entry_edge 4 dp recomputed from written values, threshold written as the filter's minimum minus one ulp or filter changed to `>`, push-excluded P(win) |
| **D8** | **Projection semantics/units for NBA** (game total/spread projection; h2h null; prop units; when projection must be non-null) | B8 | totals = projected total in points, spreads = projected margin in points, h2h null, props = expected stat in its natural unit, unit vocabulary fixed by contract |
| **D9** | **Status vocabulary details still open** (`withdrawn` reason code; `book_pulled`/`competitor_withdrawn`; DNP void reason; `awaiting_result` publisher; game cancelled vs postponed mapping) | B6/B7 | DNP → `void` with a DNP-specific reason once added; game cancelled/postponed → `void`/`game_void`; engine never emits `withdrawn` without an operator tool |
| **D10** | **Settlement grading rule**: grade on frozen entry `line`/`side`; plus-line spread settlement definition; whole-number totals push grading; PS DNP; postponed games | B7 | Contract's push/void definitions (§4.2) applied to the entry line/side; fix the current heuristic |
| **D11** | **`sport` semantics** (`sport="nba"`, `league` absent) and `game_sk` cross-sport uniqueness confirmation | B2/B3: the record's sport field is the league not the engine's "basketball" | `sport="nba"`; lease a game_sk namespace check in the store |
| **D12** | **Where dropped metadata lives** (`taxonomy_version`, `market_last_update`, variant, run id, hash) | B2/B4/ops: record is closed (`additionalProperties:false`); consumers currently read taxonomy and feed timestamp | Not in the record; PE/Cosmos envelope or BFF derivation; contract must confirm loss is acceptable |

---

## 8. Unverified / inferred items

1. **`team_1 = home` convention [A].** No home/away/venue column exists in `dev_nba.nba_silver.dim_all_games` (verified `DESCRIBE`); the engine and PE implicitly treat slot 1 as home. Whether the schedule feed guarantees it — and who resolves it for v4 `side`/`team_sk` — is unverified.
2. **`game_sk` cross-sport uniqueness [A].** Contract requires it (`:191`) and the corpus lists it as an open item; no cross-sport check was run here.
3. **Production/tst deploy state [A].** The corpus says tst production runs `nba_bet_engine 0430eb5`; the read-only SP cannot view ML jobs, so the deployed revision could not be confirmed. Local `dev` is d36b2d1; `tst` config targets `tst_nba` per `conf/tst.yml`.
4. **PS data shape [A for data].** Both PS tables are empty (picks disabled), so PS shapes are verified from code only.
5. **PE branch note [V].** `app-data` local checkout is `tst-blue` @ a1c16f4, not `feat/nba-2026`; canonical files were read via `git show feat/nba-2026:…` @ 54214ec (2026-09-17). Whether the v4 record will be written by the tst-blue 1.00 transforms or the canonical Format-B path is undecided in the material read; both shapes differ from v4.
6. **Monitor [A].** `live-odds` @ dev is NFL-only per its design doc and code scan; an NBA observation path does not exist yet. No NBA monitor job/table was found (job visibility is restricted for the read-only SP).
7. **Push probability semantics [V code, A interpretation].** The push-excluded totals CDF and unconditional spread CDF are verified; how the contract wants `probability` defined on whole-number lines is unresolved.
8. **`wltp_top_picks_adj_audit` drift sample [V data]** is from dev only; it demonstrates the mechanism (re-run overwrite) rather than a production count.
9. **Freshness of Confluence vs code.** `720142351` v6 still describes a 13-field `edge_picks` struct and lists `pick_status`, `bet_entry_price`, `bet_entry_ts`, `edge_threshold` as contract fields; the live/dev engine emits 16 fields and none of those. That page is stale relative to `nba_bet_engine` d36b2d1 (commits `291a3d5`, `a32ce26` added `edge`/`market_last_update`/`variant` after the page). The v4 record is a new contract, not an update of that page.

---

## 9. Evidence index

- Contract: `xo-scratchpad/edgepicks-redesign/staging/conf-schema-contracts.md` v4.0.0 (rules `:42–64`; lifecycle `:68–116`; edge formulas `:120–176`; fields `:179–243`; pick_id `:313–402`; schema `:406–646`; open decisions `:881–891`).
- Engine code, `nba_bet_engine` @ d36b2d1: `src/bet_engine/_schemas.py:53–90, 136–153, 155–188, 199–296`; `_wltp_engine.py:131–202, 159–166, 289–296, 340–435, 473–530`; `_probability.py:82–116, 147–180, 233–256`; `_strategy_tiered.py:38–93`; `_strategy_filters.py:1–20`; `_config.py:9–10, 46–78`; `_wltp_pick_selector.py:112–137`; `wltp_pick_selector.py:205–232, 245–300`; `_wltp_aggregation.py:39–60, 121–141, 172`; `wltp_engine.py:289–296`; `wltp_aggregation.py:122`; `ps_engine.py:116–124, 19–21`; `_ps_engine.py:250–366`; `_ps_aggregation.py:19–33`; `_update_outcomes.py:29–81`; `_scoring.py:12–43`; `_ps_update_outcomes.py:24–96`; `_common.py:194–230, 300–325`; `_live_odds.py:27–32`; `resources/jobs.yml:15–106, 140–200`; `conf/dev.yml:10–12, 17–29`; `databricks.yml:60–99`; `AGENTS.md:43–44, 60–69, 85–88, 130`.
- Engine `main` @ af145bd (2025): `src/bet_engine/01_run_wltp_top_picks.ipynb` (SEASON 2025, `bet_id` formula, edge calc), `02_update_pick_outcomes.ipynb`, `03_pick_selector.ipynb`, `04_pick_aggregation.ipynb` (PRIORITY_TOP_PICK_REGION rule + replication). Contrast: same `bet_id`/edge-unit design, merge on `(game_sk, bet_bookie_region)` — 2025 was even more explicitly single-pick-per-game/region; dev added `edge`/`market_last_update`/`variant` and multi-per-type keys but kept the overwrite semantics.
- PE code, `app-data` @ tst-blue a1c16f4: `databricks/publisher/nba/nba_wltp.py:84–88, 200–300, 340–373`; `nba_ps.py:396–430`; `generic_cdf_to_cosmos_pipeline.ipynb` code cell (skip no-id rows, patch mode drops nulls). `feat/nba-2026` @ 54214ec: `databricks/publisher/canonical_transformations.py:199–223, 737–900`; `nba2026_transformations.py`. Container contract: `databricks/docs/containers/nba_containers/NBA game_edge_picks c-wltp v1.00.md`; `NBA player_edge_picks c-ps v1.00.md`.
- Docs: engine `AGENTS.md` (2026-10-06); repo analysis notes `nba-2026-schema-conformance-audit.md`, `nba-2026-canonical-fix-plan.md` (untracked, used as leads; their code claims re-verified against d36b2d1 — the conformance audit's priority-region "never activates" finding is **superseded**: `priority_region` is wired in `databricks.yml:75–77`/`jobs.yml:103–104` and AU replication is live in `wltp_top_picks_agg`).
- v4 corpus (design, not contract): `producers-to-bff.md:11, 30–34, 151, 556–606`; `kdds.md:20–70, 248`; `realtime-overlays.md` (monitor fields, edge_status rules); `option-b-plan.md:304, 737–741` (BFF edge derivation).
- Confluence: `PB/720142351` v6 (NBA Bet Engine — Output Contract, fetched 2026-10-21); `PB/717914114` v6 (NBA 2026 — Schema Specification, §3 canonical pick struct / §2.5–2.7 upstream table shapes).
- Live SQL (dev, 2026-10-21): `SHOW TABLES IN dev_nba.nba_gold_bets`; `DESCRIBE` of `wltp_top_picks_agg`, `ps_top_picks_agg`, `nba_silver.dim_all_games`; pick-slot aggregation (17 games / 34 slots / 0 placeholders / regions AU+US); audit-vs-live_app key drift (10–15 runs, odds 1.87→1.95, 2 lines, 3 stakes); `ps_top_picks`/`ps_top_picks_agg` row counts 0; `fact_game_odds` region/bookmaker list (us only); `dim_all_games` 2026 status values.
