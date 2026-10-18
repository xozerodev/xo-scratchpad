# BFF (mobile-server) and Publish Engine (app-data) — evidence verification

Task `task-2`. Verifies every mobile-server (BFF) and app-data (Publish Engine, PE) factual claim in
`SDUI/sdui-proposal.md` §"Publish Engine (app-data)", §"BFF (mobile-server)", the BFF/PE columns of
§"Where display decisions live today", the routes in §"Screen by screen", and the PE/BFF rows of the
defect table in §"Risks and open questions". Read against the Edge Picks v4 contract
(`edgepicks-redesign/specs.md`, §4, §5.1, §6.2, §7, §8).

**Verdict key.** Confirmed / Partly / Refuted / Unverifiable. Evidence is `file:line` at the commit
named in that row. "local" = read from a local git object; "API" = read through `gh api` / `git ls-remote`.

## 1. Branch and commit actually inspected

| Repo | Proposal cites | State of the cited commit | Branch that deploys today | Read how |
| --- | --- | --- | --- | --- |
| mobile-server | `develop` `95733012` | 2026-10-15. Local `develop` is `8c47ee6` (13 Oct), 8 commits **behind** it; `95733012` was the tip when this workstation last fetched (15 Oct 21:52). All claims below are read at `95733012` (local object). | `origin/develop`, tip **`b2431435`** (16 Oct 13:15) = `95733012` + 3 commits (`86c65371`, `296291a9`, `b2431435` — all DS-463 Key Vault / TST Terraform). No functional BFF commit between the cited SHA and the tip. | local objects; tip + delta via `gh api` (API) |
| app-data | `dev` `e1980822` | Author date **7 Sep 2026** 17:23 +1000 (the proposal's "8 Sep" is a timezone artefact). Ancestor of `origin/dev` (`2b6f998`, 12 Oct) but **not** of `origin/tst-blue` (`a1c16f4`, 13 Oct), which branched from `20b3488`. | `origin/dev` `2b6f998` (12 Oct) and `origin/tst-blue` `a1c16f4` (13 Oct, the production-serving slot per `specs.md` §9). Both confirmed current by `git ls-remote` on 17 Oct. `transformations_library.py` is **byte-identical** between dev and tst-blue. | local objects; heads via `git ls-remote` (API) |

**Constraint.** `git fetch` cannot write `.git/FETCH_HEAD` (repository trees are read-only for this
sandbox), so no new objects could be downloaded. Everything is either a local object or a read-only
API call. Consequently `b2431435` (mobile-server dev tip) could not be opened file-by-file; the three
commits it adds over the cited SHA were read as commit metadata only, and none of them touch BFF
runtime code.

**Headline structural finding.** `/v4/edge-picks` — the route the proposal's BFF section is built
around — **does not exist in mobile-server at the cited commit, on any of the 37 remote branches, or at
the current develop tip.** No branch, tag or ref in the fetched repository contains
`EDGE_PICKS_SOURCE`, `loadLiveEdgePicks`, `edge_threshold`, `edge_holds_above` or `overlay_key`
(`git grep` over every ref, local). GitHub code search over the repo returns 0 hits for both symbols
(API). Every `/v4/...` string in `src/` is Qonversion's external API (`qonversion-repo.ts:150`); the
only v4 *route* concept in the BFF is the `api_version` **major** `v4` used to gate EPL. The in-tree
"edge-picks" mentions are all about NBA canonical `game_edge_picks` **Cosmos documents**
(e.g. `docs/schema-migration/canonical-vs-legacy-assessment.md:87`, untracked scratch files, `dist/`),
not an HTTP route. The proposal has conflated the Edge Picks v4 *contract* with a BFF implementation
of it.

## 2. BFF claims (mobile-server, read at `95733012` unless stated)

| # | Claim | Verdict | Evidence | Note |
| --- | --- | --- | --- | --- |
| B1 | `/v4/edge-picks` route exists | **Refuted** | No match at `95733012` or any ref. Route registrations are only `match/{id}`, `matches/{date}`, `matches/{date}/top-predictions`, `my-picks*`, `v3/*` (`src/functions/*.ts` `route:` lines, e.g. `matches-v3.ts:209`, `match-v3.ts:168`) | Also absent at the 16 Oct develop tip and in GitHub code search. See §1 |
| B2 | `EDGE_PICKS_SOURCE=live` always returns 503 because `loadLiveEdgePicks` throws | **Refuted** | Neither symbol exists (`git grep` all refs; `gh api search/code` = 0) | Cannot be "always 503" if the adapter does not exist |
| B3 | Its zod schema uses `edge_threshold` (not `edge_holds_above`) and omits `overlay_key` | **Refuted** | No `edge_threshold`, no `edge_holds_above`, no `overlay_key` anywhere in the repo | The *spec* does use both terms (`specs.md:125` `edge_holds_above`, `:108` `overlay_key`). The statement "the implementation lags the spec" is trivially true because there is no implementation |
| B4 | It is "the one contract that already composes labels server-side, declares field groups and access, and validates at runtime" | **Refuted** | as B1 | The reusable parts that do exist are the freemium registry (`freemium/registry/field-groups.ts`) and request-body zod — neither is a v4 edge-picks contract |
| B5 | 57 league branches across 10 files | **Partly** | See counting note §2.5 | My counts: **40 branch sites across 9 non-test files** (switch arms + league-literal comparisons + `is*League` predicates), or 30 lines / 34 lines incl. secondary leagues. 57/10 is not reproducible; the shape of the claim (a few dozen sites in a handful of files) is right |
| B6 | `api_version` majors are overloaded: v4 adds EPL, v5 adds NFL **and** response shape, v6 staged-season release | **Confirmed** | `match/api-version.ts:57-62` (NFL v5+), `:68-73` (split match-list locks v5+), `:79-84` (sectioned rosters v4+), `:108-122` (schedule SQL per major), `:128-151` (hide EPL/NFL per major); `canonical/gate.ts:16-31,78` (`RELEASE_API_VERSION_MAJOR = 6`) | Three independent axes off one query parameter, exactly as claimed |
| B7 | An approved league registry with `minApiVersion` per league is documented but not built | **Confirmed** | Documented: `docs/EPL/api-alignment-and-backward-compat.md:35-38,53,73`; `docs/superpowers/specs/2026-08-03-epl-schema-alignment-design.md:69-73,92,115` ("Add `src/lib/leagues/league-registry.ts`"). Not built: `git ls-tree 95733012 -- src/lib/leagues` is empty; the equivalent logic is hardcoded in `api-version.ts` | `docs/EPL/README.md:41` restates it as the intended design |
| B8 | Canonical NBA 2026 documents are chosen by **shape**: `doc_type`, `schema_version`, id pattern, or `league === "nba"` | **Confirmed** | `canonical/wltp.ts:15-20` — an OR of `doc_type === "game_prediction"`, `schema_version === "1.23"`, `schema_version === "2.0.0"`, `id.includes("\|game_prediction\|")`, `league === "nba"`; second independent marker at `parsers/sections/index.ts:76-77` | Exactly the four markers claimed, and the second marker is separate — "no single switch" is fair. The gate doc adds that producers write `doc_type`/`schema_version`/id identically for legacy and canonical, so shape cannot gate a season (`canonical/gate.ts:37-43`) |
| B9 | `normaliseWltp` lifts nested canonical fields back onto legacy flat names | **Confirmed** | `canonical/wltp.ts:46-93` (`Prediction_team_1`, `WinLoss_Prediction`, `predicted_team_1_score`, `WinLoss_Probability`, `game_odds`, `is_top_pick`, …); applied in the shared mappers, e.g. `map-match-list-detail.ts:46` | Legacy names do become the internal model for readers; comment at `wltp.ts:78-79` says so explicitly for soccer consumers |
| B10 | Freemium has per-screen field groups and a `show_*` policy; enforcement is a key-name denylist plus hand-written per-endpoint mutations | **Confirmed** | `freemium/registry/strip-helpers.ts:3-50` (`STAKE_FIELD_KEYS`, `MARKET_ODDS_FIELD_KEYS`, `XO_PROBABILITY_FIELD_KEYS`, `PROJECTION_FIELD_KEYS`, `XO_EDGE_FIELD_KEYS`), `registry/field-groups.ts`, `registry/global-show-map.ts`, `apply/*` | The file comments record three separate leak bugs caused by a *new alias* not being added to the denylist (`bet_stake`, `bet_price`, `xo_probability`) — direct evidence for the fragility claim |
| B11 | New leagues are always locked for free users because `LEAGUE_TO_SPORT_KEY` is hardcoded | **Confirmed** | `freemium/policy/screen-policy-resolver.ts:28-39` (5 leagues), `:55-63` (`DISABLED_SPORT_DEFAULT`), `apply/sport-availability.ts:14-23` | Stronger than stated: a missing sport key makes `isFreemiumSportEnabled` false, and `shouldOmitDisabledSportItem` then **omits** the item for free users rather than only locking it (`sport-availability.ts:38-51`) |
| B12 | Mappers return `any` and pass whole upstream objects through (`outcome`, `game`, `...pick`) | **Confirmed** (spread) / Partly (typing) | `...pick` at `match-data-mapper.ts:44,47,49,243,384,455`, `match/common.ts:270`, `map-match-detail.ts:448`, `top-picks/top-pick.ts:343,745,799`. Loose typing: `: any` × 46 in `map-match-detail.ts`, × 30 in `match-data-mapper.ts`, × 18 in `parsers/sections/index.ts` | I did **not** find `...outcome` or `...game` spread literals; outcome/game travel as constructed objects (`match-data-mapper.ts:196,221,801`). The substance — new Cosmos fields reach the app unreviewed — holds via `...pick` and `any` |
| B13 | Only `/v4/edge-picks` has a zod schema, runtime validation and an exported JSON Schema | **Refuted** as stated | No `/v4/edge-picks`; no response schema anywhere; no `toJSONSchema`/`ajv`/`json-schema` in `src/` or `script/`; `jsons/signupResponse.json` is a captured sample payload, not a schema; no schema script in `package.json` | The defensible version is much stronger than the proposal's: **there is no response contract of any kind.** zod ^4.1.5 is present and used for **request** bodies in `src/lib/validation/{devices,feedback,follow,my-picks,users}.ts` + `man-vs-machine.ts` |
| B14 | v1 and non-v3 routes remain and duplicate the v3 loaders almost line for line | **Partly** | Separate handlers exist (`matches.ts:270` vs `matches-v3.ts:209`, `match.ts:275` vs `match-v3.ts:168`, `matches-top-predictions.ts:391` vs `…-v3.ts:326`, `my-picks*.ts`). Identical-line share vs the v3 file: `my-picks-update-v2`→`-v3` 126 lines (93% of v3), `my-picks-delete` 78%, `match` 50%, `matches` 38%, `my-picks` 35%, `top-predictions` 27% | The **loaders are shared library imports**, not duplicated: both `matches.ts` and `matches-v3.ts` import `mapMatchListDetails` and `choosePredictionDoc`. What is duplicated is query-building + response shaping. "v1" is not a separate route path — it is a value of `api_version` inside the shared handlers (`api-version.ts:112-114`) |
| B15 | Routes the app uses all exist: `/v3/matches/{date}`, `/v3/match/{id}`, `/v3/matches/{date}/top-predictions`, `/my-picks-v2`, `/config`, `/user/profile`, `/target/follow`, `/user/devices`, `/feedback`, `/man-vs-machine`, `/entitlement/activate` | **Confirmed** | `route:` registrations at `matches-v3.ts:209`, `match-v3.ts:168`, `matches-top-predictions-v3.ts:326`, `my-picks-v2.ts:404`, `config.ts:141`, `user-profile.ts:57`, `target-follow.ts:106,116`, `user-devices.ts:213,224,235`, `submit-feedback.ts:93`, `man-vs-machine.ts:188`, `entitlement-activate.ts:122` | `/summary` also exists (`summary.ts:68`) and has no v2/v3 variant — "not shown anywhere today" is an app-side claim, out of my scope |
| B16 | There are three generations of mappers | **Confirmed** | Generation 1 `lib/match-data-mapper.ts`; generation 2 `lib/match/map-match-detail.ts` + `map-match-list-detail.ts`; generation 3 `lib/match/canonical/{picks,wltp,outcome,team-injuries,lifecycle}.ts` | The legacy files are still imported by the deployed routes |
| B17 | Adding a league touches 11 areas of the BFF, incl. "version gating in three files" and "the v4 sport enums" | **Partly** | Version gating is spread over **10 non-test files** that call the version predicates/gates: 6 route handlers (`matches.ts`, `matches-v3.ts`, `match.ts`, `match-v3.ts`, `matches-top-predictions.ts`, `matches-top-predictions-v3.ts`) + `lib/match/api-version.ts`, `lib/match/canonical/gate.ts`, `lib/match/map-match-detail.ts`, `freemium/apply/match-list.ts`. There is **no v4 sport enum in the BFF** (that type, `EdgePickSport`, is an app type) | The parser rules (`parsers/leagues/*/rules.ts`), `LEAGUE_DISPLAY`, the two decimal switches (`top-pick-utils.ts:93,120`), `TEAM_DETAILS`, `STAT_NAME_BY_ID` (`constants.ts:56`), `NFL_STAT_MAP` (`lib/nfl/stat-map.ts:15`), `LEAGUE_PARSER_RULES`, `LEAGUE_TO_SPORT_KEY`, `INJ_TEAM_LEAGUES` (`getInjurieslist.ts:58`), `enabled_leagues` and seeds all exist as named. Two of the eleven named touch points are wrong in detail |
| B18 | `/config` serves `api_version` and `enabled_leagues` | **Confirmed** | `config.ts:121-122`; default list `constants.ts:45` = `["NBA","WNBA","MLB","EPL","NFL"]` | The claim that the app ignores them is app-side and out of scope |
| B19 | BFF-column rows of "Where display decisions live today" | **Confirmed** | `InProgress` computed from start time: `match/common.ts:56-57`. `STAT_NAME_BY_ID` `constants.ts:56`, `NFL_STAT_MAP` `lib/nfl/stat-map.ts:15`. Pick wording built from `code`/`bet_line`, incl. `player_milestone` (`canonical/picks.ts:656`). Region odds + 2 dp: `top-pick.ts:334-340`, `extractRegionMarketOdds` (`freemium/resolve/locked-pick-response.ts:175`). `LEAGUE_DISPLAY` + per-league decimal switches `top-pick-utils.ts:12,93,120`. Locks/strips `freemium/apply/*` | One correction of detail: `TEAM_DETAILS` is **exactly 128 entries** (31 nba, 29 mlb, 32 nfl, 15 wnba, 13 epl + 8 unquoted keys), so "128 rows: colour, code" is right; the sibling claim "team colour lookup not lowercased" is separately confirmed (B20) |
| B20 | Defect: team colour lookup is not lowercased, so list cards get the default colour — `lib/match/map-match-list-detail.ts:29-30` | **Confirmed end-to-end** | `map-match-list-detail.ts:29-30` calls `getTeamInfo(\`${league}_${team1Name}\`)`; `team-details.ts:334-335` indexes `TEAM_DETAILS[teamKey]` with **no** lowercasing and falls back to `{color:"#007A33", code:""}` (Celtics green). Keys are lowercase (`team-details.ts:7` `"nba_atlanta hawks"`), and seed documents carry `league:"nba"` + `team_1_full_name:"Charlotte Hornets"` (`script/db-seeds/data-c-sch-dev-v4.json`) → key `"nba_Charlotte Hornets"` misses. Siblings do lowercase: `getTeamImageCode` `team-details.ts:337-340`, `getTeamMatchName` `:343-351` | Exact line numbers in the proposal are right. `my-pick.ts:248,254` has the same bug |
| B21 | Defect: placeholder push copy "We went 4/6 today…" — `functions/service-bus-push-events.ts:261` | **Confirmed verbatim** | `service-bus-push-events.ts:261` = `"Your Top Picks results are in! We went 4/6 today, earning a profit of $X and an ROI of 25%. Tap to review the breakdown"` | The copy is a hardcoded `DAILY_DIGEST_READY` body; no data is interpolated |
| B22 | NBA alone is on the 2026 canonical documents; MLB/WNBA/NFL/EPL are on legacy Format A, so the BFF carries both paths | **Confirmed** | Dual paths coexist in one file: `canonical/wltp.ts:11-44` (canonical detector) vs the legacy branches it falls back to; `canonical/docs.ts:39-90` (modular `doc_type` pick, then legacy last-wins fallback); `parsers/sections/index.ts:76-77` applies canonical aliases for NBA only | `docs.ts:69-75` records that an earlier `\|\| league === "nba"` clause silently discarded games' only prediction across 14 callers — the two-path split has already produced one BFF regression |
| B23 | "No response contracts outside v4 edge picks" | **Confirmed**, but for a different reason | See B13 | True statement is "no response contracts at all" |

### 2.5 How the BFF counts were made

* **League branches (B5).** Script over every non-test `src/**.ts` at `95733012`, counting (a) each
  `case "<league>"` arm, (b) each league-literal `===`/`!==` comparison, (c) each `is*League(...)`
  call, (d) `[...leagues].includes(league)`. Result **40 sites / 9 files**, concentrated in
  `top-picks/top-pick-utils.ts` (16), `top-picks/top-pick.ts` (11), `parsers/sections/index.ts` (5).
  A line-based variant (one per line) gives 30; adding nhl/mls/soccer/college literals gives 34.
  Including `src/types/*.ts` property declarations inflates it to 60/10, which is likely how 57/10 was
  reached — those are type declarations, not branches. Same 9 files either way.
* **Version-gating files (B17).** `git grep -l` for callers of `scheduleLeagueFilterSql`,
  `shouldHideEplForVersion`, `shouldHideNflForVersion`, `isMatchDetailSectionsVersion`,
  `isSplitMatchListLocksVersion`, `isNflVisibleForVersion`, `stagedReleasedFor`, `seasonGateSql`,
  excluding `__tests__`: 10 files.
* **Route duplication (B14).** `diff` of each legacy handler against its v3 counterpart; shared lines =
  legacy line count − lines unique to legacy; reported as a share of the v3 file. This measures textual
  overlap, not semantic duplication, and deliberately does not count the shared library loaders.

## 3. Publish Engine claims (app-data)

PE findings are stated at the cited commit `e1980822` **and** re-checked at
`origin/dev` `2b6f998` and `origin/tst-blue` `a1c16f4`. §4 says which hold today.

| # | Claim | Verdict | Evidence | Note |
| --- | --- | --- | --- | --- |
| P1 | A generic CDF-to-Cosmos pipeline wrapped around one 2,900-line library of hand-written per-league transforms | **Confirmed** | `databricks/publisher/transformations_library.py` = **2,929 lines**, 20 top-level/nested defs at `e1980822` (`:7,255,284,498,1241,2292,2564,2691`); **2,937 lines / 20 defs** at dev and tst-blue | The library changed by 13 insertions / 5 deletions between the cited commit and today |
| P2 | It has no schema checks and no tests | **Confirmed**, still true | No `jsonschema`, `pandera`, `great_expectations` or schema-validation call anywhere in the repo at dev (grep, 0 hits). Test-like files are only `docs/…EPL Integration Test…md`, `publisher/docs/PRJ04_PE_feature_testing_guide.md` and two **seeder utilities** | "Validation" is column-presence branching only (P3) |
| P3 | 65 column-presence checks | **Confirmed (66)** | 66 literal `"<name>" in …` membership tests in the library; 56 `.columns` mentions; 37 `in …columns`; the only helper is `_first_existing(col_names, candidates)` (`transformations_library.py:1285-1289`) | Identical count at dev and tst-blue — the NBA work changed none of them |
| P4 | About 26 league branches | **Confirmed (25–27)** | 25 `league (== \| != \| in [)` comparisons + 2 `.lower()` variants, e.g. `:58,142,346,405,533,655,994,1373,1594,1631,1925,2315,2336,2374,2609,2777,2860` | Identical at dev/tst-blue |
| P5 | 13 start-version overrides | **Partly (12)** | `starting_version_overrides` in `generic_cdf_to_cosmos_pipeline.ipynb` cell 6 at `e1980822` has **12** keys (4 MLB, 3 WNBA, 2 EPL, 2 NFL dev + 2 tst) | Today: **6** on dev (all NBA), **10** on tst-blue (dev+tst NBA). The legacy entries were **replaced**, not extended — a legacy table needing an override now has none |
| P6 | Three router jobs fire on Delta table updates (MLB; WNBA; NFL and EPL) with a 60 s debounce, reading a JSON-literal map, fanning out to a worker per container | **Confirmed** at the cited commit; **superseded** | `databricks/resources/jobs/` at `e1980822` = `publish_engine_router_01/02/03.yml` + `publish_engine_worker.yml`. Router 02 = WNBA tables with `wait_after_last_change_seconds: 60`; per-container `run_job_task` blocks in parallel. Map = `build_transformation_map.ipynb` cell 4 | Today dev/tst-blue have **10 routers** (`router_01…05`, `_epl`, `_mlb`, `_nba`, `_nfl`, `_wnba`) + 6 workers. "Three" describes the legacy set accurately |
| P7 | Blue and green slots have separate containers and switching the BFF between them is manual | **Confirmed** | `databricks.yml` `slot` = "blue"/"green" with per-slot `ps_container`/`outcomes_container`/`sch_container`/`injuries_container`/`wltp_container` (+ `injuries_team_container`); dev-green active on `c-*-dev-01`, dev-blue commented out; `slot_pause` per slot. BFF reads container names from environment with defaults: `mobile-server src/lib/cosmos.ts:22,27` (`COSMOS_CONT_SCH \|\| "c-sch-dev-v3"`, `COSMOS_CONT_GAME_PRED \|\| "c-wltp-dev-v3"`) | Nothing pairs the two sides automatically: the slot is an app-setting/Terraform value on each side |
| P8 | Format A documents only for MLB, WNBA, NFL and EPL: `schedule`, `game_prediction`, `player_predictions`, `player_top_picks`, `outcome`, `injuries` | **Confirmed** | `doc_type` per transform: `:39` schedule, `:327` injuries, `:516` game_prediction, `:1264` player_predictions, `:2323` outcome, `:2591` player_top_picks | The proposal omits a seventh: NFL also emits `game_top_pick` (`:2715`, PRJ03 two-document split) |
| P9 | NBA publishes the NBA 2026 canonical documents in production; that code is newer than the checkout, so it is not assessed | **Partly** | The code exists and is on the production-serving branch: `databricks/publisher/nba/{nba_wltp,nba_ps,nba_schedule_outcome_injuries,constants}.py` + `router_nba/04/05` present on `origin/tst-blue`; `20b3488` (12 Oct) "PE NBA game_prediction: comply with 2.4" touched only `nba_wltp.py` | "Not assessed" is too generous. The canonical transforms are dispatched by the **same** `generic_cdf_to_cosmos_pipeline` cell 4 as the legacy ones, so the write-path defects P12/P13/P15 apply to NBA canonical output unchanged |
| P10 | The EPL 1.40 split and `game_edge_picks` are spec only | **Confirmed** | Spec docs exist: `databricks/docs/containers/epl_containers/EPL game_prediction c-wltp v1.40.md` and `EPL game_edge_picks c-wltp v1.10.md`. Code emits `epl_schema_version = "1.31"` (`transformations_library.py:996`, and `"1.10"` at `:1927`) and `game_edge_picks` appears **nowhere** in the library (grep, 0 hits) | Three specs (v1.30, v1.31, v1.40) coexist in the docs for one container while the code emits 1.31 — see P18 |
| P11 | No validation: documents are built from whichever columns exist | **Confirmed**, still true | P2/P3 | — |
| P12 | Silent loss: a failed Cosmos write only increments a counter and the checkpoint still advances | **Confirmed**, still true | Write path catches `CosmosHttpResponseError` into `errors += 1` and continues (`e1980822` cell 4 **L218-222**; dev cell 4 **L296-300**), then only logs the totals (L239-241 / L317-319). No raise, so `foreachBatch` returns normally and Structured Streaming commits the offset under `checkpoint_path/commits/` | The `commits/`-directory check (dev cell 5) only protects a batch that throws; a partial failure that completes still advances and is never retried. Malformed rows are also dropped silently (`if not item_body.get("id"): continue`, cell 4 L180-181 / L258-259) |
| P13 | CDF deletes are discarded for every transform except `player_top_picks` | **Confirmed**, still true | Deletes are filtered out up front (`_change_type.isin("insert","update_postimage")`, cell 4 L16 / L32), and delete handling exists only inside `if transformation_name == "transform_pstp"`, both for delete-only batches (e1980822 L26-46; dev L42-63) and mixed batches (L100-116 / L154-170) | The new NBA canonical transforms get **no** delete handling either, so canonical NBA documents are equally delete-blind |
| P14 | `delete_stale_epl_wltp_docs.py` patches the delete gap by hand | **Confirmed at the cited commit — and the script is gone today** | `databricks/delete_stale_epl_wltp_docs.py` present at `e1980822` (a notebook that lists stale EPL WLTP docs in `c-wltp-dev-01` and deletes them) | Absent from `origin/dev` **and** `origin/tst-blue`. The manual remedy has been removed while the delete gap it patched remains |
| P15 | No ordering: several CDF versions in one batch resolve last-write-wins, and MLB patches and upserts the same document from two tables | **Confirmed**, still true | Writer applies `patch_item` or `upsert_item` per record in batch order with no version comparison (cell 4 L267-294 dev). `transform_wltp_top_picks` sets `isPatch=True` for the predictions-only path (`transformations_library.py:883`) and full-upserts otherwise; **two** MLB tables map to the same transform/container/doc id — `mlb_all_models_sportsmodel_pofs` and `mlb_gold_bets.wltp_top_picks_agg` → `transform_wltp_top_picks` → `c-wltp-container`, partition `/game_sk` (`build_transformation_map.ipynb` cell 4), and `pitcher_pof` + `batter_pof` are two separate tasks for the same `player_predictions` doc id | The dedup key in the map builder is `(table, container, transformation)`, so the same document can be written by two tasks in the same run |
| P16 | Display data is written into documents: status words, stat labels, 2 dp strings, NFL top-N per position, position buckets | **Confirmed**, still true and extended | Status words `"Final"/"Scheduled"/"Canceled"` `:189-191`, `"confirmed"` `:1851,2113`, `"Completed"` `:2346,2386,2399`; 2 dp via `_fmt_double` = `format_string("%.2f")` `:1291-1292` called **21×**; stat labels `:1752-1756` (`"passing yards"`); NFL top-N `top_n_map = {"QB":1,"RB":2,"WR":3,"TE":1}` `:1723` with `row_number()` ranking; position bucket filter `player_position.isin("QB","RB","WR","TE")` `:1653` | The NBA work **adds** display vocabulary: `publisher/common/helpers.py:18-23` `OUTCOME_STATUS_MAP = {"final":"Completed","scheduled":"Scheduled","postponed":"Postponed","cancelled":"Cancelled"}` |
| P17 | Not the only writer: live-scores, seeders and a laptop injector also write to the same Cosmos account | **Partly / Unverifiable** | In-repo seeders confirmed: `databricks/utilities/pe_test_data_seeder.py`, `pe_test_data_seeder_wltp.py`, plus `cosmos_backup_restore*.ipynb` and `cosmos_container_viewer.py` all construct a `CosmosClient` (grep at dev). live-scores is a **different repository** (out of my scope); "laptop injector" has **no** in-repo evidence | Marked Unverifiable for the two external writers rather than inferred |
| P18 | Contracts are prose; container specs disagree with the code on versions, doc types, ids and partition keys; there is no PE-to-BFF contract | **Confirmed** | Docs are markdown only (no machine-readable schema anywhere in the repo). Concrete version drift: EPL `game_prediction` specs at v1.30, v1.31 and v1.40 in `databricks/docs/containers/`, code emits `1.31`. Doc/code drift **today**: `build_transformation_map.ipynb` cell 0 documents `{env}_mlb.mlb_gold_pred.mlb_all_models_sportsmodel_pofs` under `c-wltp-container`, but the code map in cell 4 at dev no longer contains it | `specs.md` §8.6 (producer publishes a machine-readable schema, CI validates samples) is unmet on both counts |
| P19 | The WNBA player document is a `select("*")` of its source table | **Confirmed** | `transformations_library.py:1594-1607` — `if league in ["nba","wnba"]: ps = cdf_batch_df.select("*", <id>, <doc_type>, <schema_version>)`, then `select("id","game_sk",publish_obj,*remaining_cols)` at `:1620` | Shared with the legacy NBA path. Identical at dev |
| P20 | Adding a league touches about 8 places, and the first test is a dev deploy | **Confirmed (≈8–10)** | Enumerated: router YAML `table_names`; `build_transformation_map` doc table (cell 0); `TABLE_TRANSFORMATION_MAP` (cell 4); container widget read (cell 2); `container_map` (cell 6); router `run_job_task` block + worker YAML (only if a container is new); `transformations_library.py` league branches (~26) and a new transform function; pipeline cell 4 dispatch branch; optionally a `starting_version_overrides` entry. The notebook itself warns `ALL_CONTAINERS` "must match trigger job's run_job_task blocks" (cell 7) | "First test is a dev deploy" follows from the absence of any test harness (P2). The `c-injuries-team-container` added by the NBA work shows the exact 5-place edit path |
| P21 | A rescheduled game writes a second schedule document (partition is `/game_date`) | **Partly — legacy yes, NBA fixed today** | At `e1980822`: `transform_game_data` writes one `schedule` doc per `game_sk` (`:39`) into `c-sch-container` partitioned `/game_date` (map cell 4), so a `game_date` change moves the partition and orphans the old doc; nothing emits a delete for it. At dev the pipeline gained a synthetic delete for exactly this, **only for NBA**: cell 4 **L172-194** (`detect_cdf_column_changes(batch__df, "game_sk", _src_date_col)` → delete markers on the old `game_date`) | The new code carries its own TODO: "legacy sports (SCD2) also have the orphan problem but are not addressed yet (`transform_game_data`)" (dev cell 4 L177-178). So the defect still holds for MLB/WNBA/NFL/EPL |

### 3.5 How the PE counts were made

* **Library size (P1).** `git show <ref>:databricks/publisher/transformations_library.py | wc -l` and
  `grep -cE '^def |^    def '`.
* **Column-presence checks (P3).** Regex for literal membership tests (`"<name>" in <expr>`) over the
  library: 66 at `e1980822`, dev and tst-blue. Narrower readings (`in …columns`) give 37.
* **League branches (P4).** Regex for `league (== | != | .lower() == | in [)` plus `case "<league>"` arms
  plus `is_*league*()` helpers: 25–27, identical at all three refs.
* **Start-version overrides (P5).** Parsed the `starting_version_overrides` dict literal out of the
  notebook JSON and counted top-level keys: 12 / 6 / 10 for `e1980822` / dev / tst-blue.
* **Doc-vs-code drift (P18).** Compared the markdown tables in `build_transformation_map.ipynb` cell 0
  against the `TABLE_TRANSFORMATION_MAP` literal in cell 4 at the same ref.

## 4. Publish Engine: still true today vs fixed or superseded

`transformations_library.py` is 2,937 lines at dev and **byte-identical** on tst-blue; the whole delta
from the cited commit is 13 insertions / 5 deletions (EPL BTTS source, one NFL label case). The NBA
2026 work landed as a **new module** (`publisher/nba/`) plus new dispatch branches — it did not
refactor the legacy paths, and it did not touch the shared write path.

**Still true today, unchanged**

* No schema validation, no tests (P2, P11).
* 66 column-presence checks and 25–27 league branches in the library (P3, P4).
* Write errors swallowed into a counter; the batch commits (P12).
* CDF deletes discarded for every transform but `transform_pstp` — now including the new NBA
  transforms (P13).
* No ordering; last-write-wins; MLB writes one document from two tables (P15).
* Display data (status words, stat labels, 2 dp strings, NFL top-N, position buckets) still written by
  the PE, and the canonical module adds new display vocabulary (P16).
* Prose-only contracts; no machine-readable schema; doc/code drift persists at dev (P18).
* WNBA/NBA legacy player document is still `select("*")` (P19).

**Fixed, superseded, or newly worsened**

* **Rescheduled-game orphan (P21) — fixed for NBA only.** The pipeline now emits delete markers when
  `game_date` changes (dev cell 4 L172-194). Legacy `transform_game_data` (MLB/WNBA/NFL/EPL) is
  explicitly left unaddressed in the same commit's TODO.
* **Start-version overrides (P5) — superseded.** 12 legacy entries were replaced by 6 NBA entries on
  dev; the legacy tables no longer have overrides. Mitigating: the new `_build_cdf_reader` **raises**
  when there is no checkpoint, no timestamp and no override (dev cell 5), instead of the old
  "will start from latest" warning — a fail-loud improvement on one silent-loss path.
* **Routers (P6) — superseded.** 3 → 10 routers (a per-league router now exists, incl. `router_nba`
  and Router 04 for NBA canonical), which is more orchestration to change per league, not less.
* **Hand delete patch (P14) — removed without replacement.** `delete_stale_epl_wltp_docs.py` is gone
  from dev and tst-blue.
* **NBA canonical (P9) — added, sharing the same defects.** The canonical transforms inherit P12/P13/P15
  unchanged, so "not assessed" understates the exposure of the newest production path.

**Does the stale checkout weaken the proposal's conclusions?** No for the legacy findings — they are
numerically and textually intact today. It weakens two things: (a) the claim that rescheduling is
broken everywhere (NBA is fixed), and (b) the implicit comfort that only "legacy paths" carry the
write-path defects, when the shared pipeline applies them to the newest canonical documents too. The
stale checkout's real cost is that it makes the PE look *more* fixed than it is in the other direction:
the script that worked around the delete gap is gone, and the delete gap is not.

## 5. What this means for the assessment

* **The BFF half of the evidence does not support the "SDUI is nearly free because Edge Picks v4 already
  did it" argument.** `/v4/edge-picks`, its live adapter, its zod response schema and its exported JSON
  Schema do not exist in mobile-server at the cited commit, at any other branch, or at today's develop
  tip. The only real v4 contract is the specification in `edgepicks-redesign/specs.md`. Treat the
  "pilot is wiring, not design" claim (proposal §"Edge Picks redesign fit") as unproven: the pilot
  starts from a spec and a mock contract that is not in the repo.
* **What does exist is a strong freemium foundation.** Named field groups, a `show_*` global map,
  path/key redaction and lock/count primitives are real and reusable (`freemium/registry/*`,
  `freemium/apply/*`). That is the one BFF building block the proposal can stand on — but it is
  denylist-based, and its own comments record three leaks caused by a single new field alias.
* **The composition load is real and mostly already carried by the BFF.** The BFF already computes
  status words (`InProgress`), honouring league-specific decimals, parses pick `code` into display
  wording, maps odds by region, holds 128 team rows and NFL section titles. Moving *more* composition
  server-side is incremental for content, but the current code is league-conditional in ~40 places
  across 9 files, so SDUI does not remove the league-branch problem on its own — it relocates it into a
  registry that does not exist yet.
* **`api_version` is a genuine overloaded seam (three axes: leagues, response shape, staged-season
  release).** The proposal's "capability negotiation replaces league gating" is well aimed, but note
  the release gate was *deliberately* built on `api_version` six days before the proposal and its design
  note says the goal of never needing an app release "no longer holds". Retiring the majors is a
  negotiated migration with the release gate, My Picks (`api_version=v3` hardcoded in the route) and
  push/WP exceptions — not a clean swap.
* **The canonical NBA path has no single switch, and the BFF has already been burned by it.** Five
  shape markers decide canonical-ness (`wltp.ts:15-20`) plus a second marker in the section parser, and
  `docs.ts` records a past regression where a `league === "nba"` clause silently dropped a game's only
  prediction for 14 callers. Any SDUI composition layer inherits this document-selection logic verbatim,
  so it must be resolved before composition, not during it.
* **Response contracts are weaker than the proposal says — which strengthens the Phase 0 case.** There
  is no response validation and no exported schema anywhere in the BFF; zod covers request bodies only.
  If SDUI payloads become the app's rendering input, the "one contract, generated" principle is not an
  enhancement to something that exists, it is the first contract the BFF will have.
* **Two live BFF defects are confirmed and cheap.** The team-colour lookup returns the default green for
  every list card whenever league/team case differs from the lowercase `TEAM_DETAILS` keys
  (`map-match-list-detail.ts:29-30` + `team-details.ts:334-335`; seeds carry Title Case), and the daily
  digest push ships literal "We went 4/6 today… $X" copy (`service-bus-push-events.ts:261`). Both are
  in user-visible paths today and neither needs SDUI to fix.
* **The PE is not a safe producer for SDUI on any league, including NBA.** Failed writes are counted and
  lost while the checkpoint advances; CDF deletes are ignored for every transform except
  `player_top_picks`; there is no schema validation and no tests; several CDF versions in one batch
  resolve last-write-wins. An SDUI screen that reads PE-published documents inherits all of it.
* **The PE writes presentation, which is exactly the layer SDUI wants to own.** Status words, stat
  labels, 2 dp strings, NFL top-N per position and position buckets are produced by the PE today, and
  the newest NBA module adds more (`OUTCOME_STATUS_MAP` with "Postponed"/"Cancelled"). The PE/BFF
  ownership boundary in the proposal's "Who owns what" table requires *removing* these from the PE —
  which is a producer change on the critical path, not a BFF-only refactor.
* **The PE's "adding a league" cost is structural, not incidental.** A new league touches the router
  trigger list, the map notebook's documentation table, its JSON map, the container fan-out in
  several places and the library's ~26 league branches; the multi-place edit is codified in the
  notebook's own comment that `ALL_CONTAINERS` "must match trigger job's run_job_task blocks". The
  registry the proposal puts in `xo-contracts` must therefore own the PE's table→(transform, container,
  partition key) map, or the PE keeps its own league list.
* **The blueprint exists, the implementation does not.** `specs.md` §8 already specifies the producer
  contract SDUI needs (typed values, no display copy, one id, machine-readable schema, CI conformance)
  and §6.2 already specifies field-group access. The gap between that spec and both repos is the whole
  of Phase 0.
* **Do not let the pilot depend on the Firebase overlay story.** `specs.md` §7.1 records the edge
  overlay as NFL-only and dev-only today, and the app has no RTDB client; SDUI's live sections would be
  the first consumer. That is a separate delivery risk from composition.
* **Anything read only from the workstation is now stale by construction.** The cited mobile-server SHA
  was already 3 commits behind develop on 16 Oct, and app-data's cited SHA is 5 weeks old and not even
  an ancestor of the production-serving `tst-blue`. The verification method that worked under the
  read-only sandbox was `git ls-remote` + `gh api` for heads/trees and local objects for content; any
  future gate should re-read the deploying branches rather than cite a checkout.

## 6. Verdict tally

| Area | Confirmed | Partly | Refuted | Unverifiable |
| --- | --- | --- | --- | --- |
| BFF (B1–B23) | 15 | 3 | 5 | 0 |
| PE (P1–P21) | 17 | 4 | 0 | 1 (part of P17) |

Most consequential confirmations: the `api_version` overload plus the documented-but-unbuilt league
registry (B6, B7); the PE's silent-loss write path and delete blindness surviving the NBA work (P12,
P13); the team-colour defect proven end-to-end (B20).

Most consequential refutations/uncertainties: the entire `/v4/edge-picks` evidence base (B1–B4, B13);
the rescheduled-game defect being NBA-fixed and legacy-only (P21); and the disappearance of
`delete_stale_epl_wltp_docs.py` without the underlying delete gap being closed (P13, P14).
