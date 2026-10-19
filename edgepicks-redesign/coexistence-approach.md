# Coexistence of legacy and v4 — analysis, assessment and approach

**Subject:** KDD-002, *Old and new app versions coexist on one source of truth* (`edgepicks-redesign/staging/kdds.md`, lines 164–329), its Stage A projection rules, and the published producer contract (`edgepicks-redesign/staging/conf-schema-contracts.md`).
**Date:** 19 Oct 2026.
**Method:** independent verification against `mobile-server` (`origin/develop` `fffcc9e`; pick-path files identical at `origin/main` `9aaae555`), `mobile-app` (`origin/develop` `352bde30`, `origin/main` `d8a324bd`), `app-data` (`origin/tst-blue` `a1c16f43`, `origin/dev` `2b6f998`), the five bet engines, `live-odds`, `api-partners` and `push-the-bet-server`, plus read-only Databricks SQL. Evidence files: `.verify/coexistence/bff-findings.md`, `app-findings.md`, `producer-findings.md`.

---

## 1. Verdict

**KDD-002's direction is right. It is not yet safe to execute, and the work it implies is roughly twice what the document describes.**

The direction — one source of truth, one id across both families, write-time projection at launch and read-time adapters later, per route — is the correct answer to the problem. It is the only option on the table that removes drift by construction rather than by discipline, and rejecting option D′ (a second id plus a bridge) was right.

What is missing is the part that makes it safe:

1. **The projection is a rewrite of the live writer, not a parallel projector.** Format A `game_prediction` carries the model predictions as well as the picks; the legacy display fields (`type`, `code`, the per-league `pick_status` word, `bookmaker.name`/`position`, stat and player names, per-league odds rounding, run metadata) are not on the record; the one-pick slot rule needs the previous document's state; and the Publish Engine's router only re-runs a document when *its own* source table changed. A separate projector running beside today's transforms produces two-writer clobbering, a stale-document window and false shadow diffs. The KDD does not name this.
2. **`c-outcome` pick results have no producer at all.** No league writes result entries today: NBA writes empty `result.match[]`/`result.player[]` stubs pending an `nba_pick_settlements` table that does not exist in dev or tst, and MLB/NFL/WNBA/EPL's outcome schema has no `result` field. Point 6's "a result row for every settled or void record" and point 8's out-of-slot My Picks resolution both depend on a settlement → record → Publish Engine → `c-outcome` path that must be built, on a `settled_at` field the contract does not carry, and on a new trigger into a document that today only reacts to `dim_all_games` changes. **This is the largest hidden work item in the KDD.**
3. **The release gate fails open, and today's legacy shape is not gate-compatible.** Withholding requires a *string* `league` and a *numeric* `season` on the document (`gate.ts:230-255,287-305`). The canonical NBA documents carry both; today's Format A documents carry `league` but not `season` in the shapes checked. Point 6's "write them exactly as today's documents write them, so `STAGED_LEAGUES` withholds or releases derived documents as it does today" is therefore unsafe as written.
4. **The pin must be by first publish, not by game start.** Picks are published ahead of their game, so at a league's v4 start date there is always a band of games that already have legacy picks — and possibly saved slips — but start after the boundary. Point 5's date rule does not cover them, and the only clean answer is a drain rule (or the `legacy_pick_ids` bridge the KDD rejected).
5. **The old-build path that resolves a slip when a pick leaves the live documents does not exist.** The app creates slips through `POST /my-picks-v2`, which stores no snapshot; only `POST /v3/my-picks` captures one, and the app never calls it. Point 8's "resolves from its saved snapshot" is false for every slip today's users create — exactly in the cases the decision makes more common (cancelled picks, picks outside a one-pick slot).

Two more that are smaller but user-visible: the legacy `success = !!outcome` field reads a void/push (`outcome: 2`) as a **win** on the v1 and v3 routes, and the app's My Picks renders the same value as a win; and the FCM topic builder that keeps `|` becomes a *universal* follow bug under v4, because every v4 `pick_id` contains `|`.

**Assessment:** accept the decision in principle, and gate Stage A on the nine prerequisites in §5. Do not start a league's Stage A until the gate list in §6 is green.

---

## 2. What the decision gets right

- **One source removes the failure mode that option A guarantees.** Two pipelines writing the same pick *will* drift; the NBA engine's dev and tst branches already differ in how they select picks.
- **One id removes the bridge, and the bridge is where the cost was.** Every saved-id consumer — My Picks at four versions, follows, push topics, `c-outcome` results, the WordPress payload — would otherwise need to resolve two ids for life.
- **Stage A keeps the legacy surface byte-compatible, so no legacy code changes at launch.** Option C (adapters from the start) concentrates every route's equivalence proof at launch and depends on a push producer nobody has identified; deferring it is right.
- **The switch is data-free.** Turning a league off for the new build hides the screen; the records and the derived documents are untouched. The record is the recovery point: one fix reaches every build.
- **The `h2h` id dependency survives the change.** The app's moneyline test (`utils.ts:263-271`: `bet_type` lowercased to `h2h`, else a case-insensitive substring `h2h` on `id`/`predictionId`) is satisfied by the v4 moneyline id (`…|h2h_t1|…`), by today's NBA id, and by today's non-NBA id (`…_H2H_au`). The contract's market token for moneyline is `h2h` and it appears nowhere else (`conf-schema-contracts.md:325`). This is the single riskiest-looking claim in the KDD and it holds.
- **The cost figures are the right order.** The storage and RU comparison in KDD-001 is a small number either way; the decision should not turn on it, and it doesn't.

---

## 3. The invariants coexistence must hold

These are the properties that make "both families keep working" true. Each is testable, and each has an owner. The rest of this document is organised around them.

| # | Invariant | Why it exists |
| --- | --- | --- |
| **I1** | **One source per pick, for life.** A pick's family is fixed at its *first publish* and never changes, whatever happens to the game's start time. | A pick that changes family changes id (see I2) and breaks every saved reference to it. |
| **I2** | **One id per pick, in both families.** The derived legacy document carries the record's `pick_id`, and `c-outcome` result entries are keyed by it. | This is what removes the bridge. It fails if any id is minted outside the record (the BFF's `h2h:` featured pick) or if the projection re-keys anything. |
| **I3** | **Derived documents are reader-compatible**: same document ids, `doc_type`, `schema_version`, `league`/`sport`/`season`, `publish`; same field names; same per-league status words *and casing*; same per-league `type`/`code` tokens; same odds rounding. | "Older builds keep working" is a statement about bytes the readers already parse, not about intent. |
| **I4** | **No reader parses a pick id**, with one bounded exception: the moneyline test. The exception is safe only while no producer emits `h2h` outside the moneyline market token. | The id format changes for every non-NBA league; any parser is a break waiting to happen. |
| **I5** | **Every saved slip and follow resolves in every build**, including when the pick is cancelled, withdrawn, or never in a one-pick slot. | Users' saved picks are the one thing a data migration cannot repair silently. |
| **I6** | **One writer per document**, writes are content-diffed, and records and derived documents are reconciled. | Point 6 promises both; the Publish Engine's current trigger model delivers neither. |
| **I7** | **The switch is reversible and data-free; the record is the recovery point.** | A rollback that moves data cannot be rehearsed, and a fix that must be applied per family will be applied to one of them. |
| **I8** | **Every reader and writer is enumerated**, inside and outside the estate, before a league switches. | The KDD's own open item (the push producer) is the shape of this risk; two undisclosed readers already exist. |

---

## 4. Where each invariant is at risk today

### I1 — pinning: use first publish, not game start

Point 5 pins a game's family by its **scheduled start**: games starting on or after the league's v4 start date are v4; earlier games stay legacy. Picks publish ahead of their games, so on the switch date there is a band of games that already have legacy picks (and possibly saved slips) and start after it. Re-projecting those under v4 ids changes their ids and breaks the saved references — the exact failure the decision exists to prevent. The producer verification names this explicitly (`producer-findings.md` W4).

**Fix (recommended):** pin by **first publish**. A pick's family is decided the first time it is published and never revisited. Games already published by the legacy pipeline keep their legacy documents and ids for life, whatever their start time; only games whose first publish happens after the switch are v4. This subsumes the postponement rule the Oct 17 plan already has, removes the boundary band, and needs no bridge.

**Alternative (if the date rule is kept):** a drain rule — do not switch a league until every game within the legacy publish horizon has started, i.e. set the v4 start date beyond the furthest forward publish, and verify it against the engine's own horizon rather than assuming it. The rejected option D′ (a `legacy_pick_ids` bridge) is the third answer; the KDD rejected it for good reasons and the drain rule is cheaper than reopening it.

### I2 — one id: two id families exist, and the projection changes ids for most leagues

- **The BFF mints a second pick-id family.** `game-h2h.ts:87` builds `h2h:{league}:{gameSk}:{teamSk}` for the featured moneyline pick, derived from `game_prediction.is_top_pick` + `game_odds`, not from any pick document. It has no `pick_id` and no `c-outcome` row, and it is what an older build saves in a slip (`game-h2h.ts:290,354-355,376-406`). Under Stage A the same selection may also appear as a projected moneyline pick from `game_edge_picks` — one selection, two ids in one response family, which is the failure mode option D′ was rejected for. **Fixture required:** assert that a featured moneyline pick and a projected moneyline pick for the same selection do not both appear, or define which one wins.
- **Every non-NBA id changes format.** Today: game picks in Format A are `{game_sk}_{bet_type}_{region}` with a per-league middle token (NFL `spread_dog`, MLB/WNBA `FAV_SPR<`, EPL `BTTS_NO`); NFL/MLB player picks are *already* pipe ids with 5 segments and no line (`300019546|300016597|REC|player_under|au`). Under Stage A every non-NBA game pick and every NFL/MLB player pick changes id — the player picks gain `line|main|full`, and the legacy stat token (`REC`, `RecYDs`) must be reproduced from the contract's `stat_code` (`receptions`, `rec_yds`) through a mapping that does not exist yet.
- **NBA is contract-identical only while `variant == "main"`.** The contract pins the literal segment `main`; the PE writes the source `variant` (`nba_wltp.py:241-250`). Live data is all `main`, so they coincide today — but the guarantee is the engine's behaviour, not the formula.
- **The id must not be parsed.** Verified exhaustively on the BFF: no `.substring`, no `.indexOf`, no `.split` on a pick id; comparisons are exact string equality (`resolve-my-picks-list.ts:52-54,227-233`; `snapshot.ts:309-310`; `my-picks-create-v3.ts:111-115`). The only regex parser is the BFF's own `h2h:` id (`game-h2h.ts:24`). The app substrings ids for the moneyline test (twice, with different rules) and uses ids as follow/topic keys. **Producer-side constraint required:** no `stat_code` and no future market token may contain `h2h`; the JSON Schema accepts `[a-z][a-z0-9_]*` and `[a-z0-9]+` respectively, so a code like `h2h_wins` would validate *and* silently delete a user's other moneyline leg.

### I3 — reader compatibility: the projection needs inputs the record does not carry

| Missing input | Needed by | Source |
| --- | --- | --- |
| Model predictions (`WinLoss_Prediction`, `WinLoss_Probability`, `Prediction_team_*`, `total_points`, `point_spread`, `is_top_pick`, `game_odds`, EPL's win/draw/BTTS payload and `isPatch`) | Format A `game_prediction` | `<league>_gold_bets.wltp_top_picks_agg` — a join, in the PE's reach |
| Game result, scores, injuries, `game_date`/`season` | `c-outcome` | `dim_all_games`, `fact_player_injuries` — in reach |
| Per-league status word **and its source** | Format A, `player_top_picks` | MLB takes it from the pick's own status; NFL/WNBA/EPL take it from the **game** status; EPL's Format A pick struct has no `pick_status` field at all |
| `type` / `code` tokens, per league | Format A pick fields the app branches on | A maintained per-league map (favourite/underdog encoding, uppercase labels) |
| `bookmaker.name` (display) | All pick documents | Only a slug is on the record; needs a slug→display-name map. `market_average` has no display name |
| `bookmaker.position` | H2H picks | The team abbreviation — needs a team-dim join |
| `stat_name`, player and team names, legacy stat tokens | All pick documents | Dim joins + a legacy↔contract stat map |
| Odds rounding per league | All pick documents | NFL/MLB round to 2 dp; NBA carries the source; `player_top_picks` carries full float precision (`1.8771929824561404`) while the contract caps at 4 dp — so a projected player-pick price cannot be byte-equal |
| `picks_hash`, `picks_run_id`, `taxonomy_version`, `picks_updated_at`, `market_last_update` | NBA documents | Bet-engine run metadata; not on the record |
| `settled_at` | `c-outcome` result entries | **No contract field and no source** — add it, or define the fallback |
| The Format A slot incumbent | Format A | The previous document's state; the "filled slot keeps its pick" rule is history-dependent |

None of this is a reason not to project. All of it is work the KDD books at zero, and all of it is fixture-testable per league.

**Also required:** every derived document must carry `league` (string) and `season` (numeric) or it is invisible to the release gate. "Exactly as today" is not sufficient — today's Format A shape does not carry `season`.

### I4 — the moneyline exception is safe but unguarded

Covered under I2. The app's two copies of the test differ (`utils.ts:263-271` lowercases and falls back to `predictionId`; `GamePick.tsx:68` is case-sensitive and has no fallback) — a latent inconsistency worth fixing while the app is open, not a v4 blocker.

### I5 — saved slips: the resolution path the decision relies on is not written

- The app creates slips with `POST /my-picks-v2`, which stores items **without** a snapshot; `POST /v3/my-picks` is the only route that captures one and the app never calls it. The resolver's fallback is snapshot-only (`resolve-my-picks-list.ts:48-70`), so a pick that leaves the live index renders as a blank row (`title: ""`, `outcome: null`).
- Under Stage A the cases that produce a miss become **more** common, not less: a cancelled pick is listed but hidden by every legacy route; a withdrawn pick is omitted; a pick outside a one-pick slot is not listed at all. The KDD's point 8 and its validation item 3 assume the snapshot is there.
- **Prerequisite:** before any league's Stage A, either move the app's create path to the v3 route (which writes the snapshot) or make the v2 route capture the snapshot server-side. This is a BFF/app change with its own release, and it must reach the field *before* the switch — not with it.
- **`c-outcome` result matching is exact-string** at every seam (`snapshot.ts` coerces with `String()`, `match-data-mapper.ts` and `map-match-detail.ts` do not). The projection must therefore emit pick ids and result-entry ids as strings, and a fixture should pin it.

### I6 — one writer, content-diffed, reconciled: none of the three exists yet

- **The projection must replace the live transform, not sit beside it.** `transform_wltp_top_picks` writes Format A `game_prediction` for every game today; a parallel projector would be clobbered on the next legacy run. The legacy transform must be filtered to pre-v4 games (by first publish, per I1) *inside the same transform*.
- **Multi-input documents are not re-triggered.** `build_transformation_map.ipynb` maps each *updated table* to tasks, and the router's trigger list contains only tables whose change feed moved. A document with two inputs — picks from the record store plus predictions from `wltp_top_picks_agg`, or a game result plus a settlement — is not rewritten when only one input changes. The router, the map and the worker task lists must all gain the record table (and a settlement table).
- **Write-on-change does not exist.** Every CDF row upserts the whole document. The contract's frozen-field rule is what makes a content diff feasible (only `current_*`, `observed_at`, `edge_status`, `is_closing` are live, and none are projected), but the diff and its stored state must be built.
- **A second writer is already designed.** The NBA outcome specification's "Settlement Write-Back Loop" writes `pick_status`/`bet_outcome` back into `game_edge_picks`/`player_edge_picks`; `live-odds` keeps a deferred second-writer option. Under KDD-002 that path must be routed through the record and the projection, or point 6's "no other job writes those documents" is false by design.
- **One writer per document, not per container.** `c-wltp` and `c-ps` each have two PE tasks today. State the rule per document type.
- **Ordering.** Records and derived documents are separate Cosmos documents; a run that writes records and fails before projecting leaves the families divergent. The reconciliation must be driven by *record* changes, not only by the legacy source tables.

### I7 — reversibility: the switch is clean, the boundary is not

The switch itself is data-free and reversible. The irreversibility sits at the boundary: once a pick is projected under a v4 id, a rollback cannot restore its legacy id without breaking the slips saved against it. That is the same argument as I1, and it is why the drain/first-publish rule is not optional.

**Recovery model to state explicitly:** the record is the recovery point; a bad record is fixed by re-publishing it, which re-drives the projection; turning a league off hides the new screen and changes nothing for older builds; returning a league to the legacy pipeline is only possible for games that have no published record yet.

### I8 — the register is incomplete

The KDD's reader list is missing at least these, all verified in the BFF:

| Omitted | What it does |
| --- | --- |
| `lib/match/common.ts` — `getAllAvailableTopPicksForGame` | The shared pick funnel for six routes **and** the My Picks peer path; decides legacy-vs-canonical fallback and applies the season gate |
| `lib/match/map-match-detail.ts` | v3 detail mapper: `c-outcome` id match, `!!outcome` success, the featured H2H pick |
| `lib/match-data-mapper.ts` | The v1 mapper — the Format A "one pick per region" reader, plus three more id→`c-outcome` matchers and `generateMyPicksResponse` |
| `matches-top-predictions{,-v3}.ts` v1 branches | A second container read on a different code path |
| `lib/my-pick/resolve-my-picks-list.ts:327-452` | The create-time peer load: a cross-container join on every create |
| `lib/match/game-h2h.ts` | Mints `h2h:` ids; hydrates featured slips from `game_prediction` |
| `lib/match/canonical/wltp.ts:19` | `id.includes("|game_prediction|")` — a **document**-id shape dependency; Stage A must keep the document id format |
| `target-unfollow.ts:51` | The second `|`→`_` topic builder |
| `freemium/apply/my-picks.ts` | The peer matcher and availability ranking |
| `src/scenarios/*`, `script/db-seed*` | In-repo writers of all four containers (dev only) |
| **`push-the-bet-server`** | Resolves picks by exact id from `c-wltp`/`c-ps` |
| **`api-partners`** | Point-reads `game_prediction` by document id and reads `c-sch`; **not** season-gated |

And one correction: **`target-follow.ts` is not a pick-document reader** — it reads follows and devices; only its FCM topic derives from a target id. That matters because point 7's retirement condition is phrased as "no route and no other reader still reads them", and a follow topic is not a document read.

The push **producer** remains genuinely unidentified, and it is the one open item that Stage A cannot proceed without: if it watches the legacy documents, write-on-change changes its cadence; if it reads the record store, it needs the new schema.

---

## 5. The approach

### Stage 0 — prerequisites (all of them, per league unless stated)

| # | Prerequisite | Owner | Why it blocks |
| --- | --- | --- | --- |
| P1 | Close the reader/writer register (I8) and get the push producer identified | data engineering, BFF | Point 7's retirement condition and the shadow's coverage both depend on it |
| P2 | Every derived document carries string `league` + numeric `season`; fixture test that a document missing either fails | data engineering | The gate is fail-open; without this, staged content reaches v5 through My Picks and the peer loader, which are deliberately ungated |
| P3 | The old-build slip path captures a snapshot: move the app's create to `POST /v3/my-picks`, or make `POST /my-picks-v2` write the snapshot server-side | app, BFF | Otherwise every cancelled or out-of-slot slip goes blank in the field, and validation 3 cannot pass |
| P4 | Pin by **first publish** (I1), with a drain rule if the date rule is kept | BFF, data engineering, bet engine | The boundary band breaks saved slips, and the bridge that would fix it was rejected |
| P5 | Build the settlement → record → `c-outcome` path (results), including `settled_at` on the record and a trigger into the outcome document | bet engine, data engineering | Results for older builds have no producer; point 8's out-of-slot resolution depends on them |
| P6 | Fix the FCM topic builder (`queue-fcm-device.ts:40,54`) | BFF | Every v4 `pick_id` contains `|`; today the bug hits NBA follows, under v4 it hits all of them, in both builds |
| P7 | Freeze the per-league projection fixture set (I3): status word *and casing*, `type`/`code` tokens, odds rounding, bookmaker display name, stat tokens, document ids and metadata | data engineering, product | The projection is not derivable from the record; the fixtures are the specification |
| P8 | Make the projection the single writer: filter the legacy transform by first publish, add the record table (and settlement) to the router/map triggers, add content-diff write-on-change, add a record-driven reconciliation | data engineering | A parallel projector clobbers and diverges |
| P9 | Id constraints: no `h2h` outside the moneyline token; freeze the `stat_code` vocabulary; require `variant == main` or amend the formula | bet engine, platform | The app's moneyline test is a substring; the id guarantee is producer-side |

### Stage A — derived documents, per league

1. **Build the projection as the existing transforms' replacement**, per P8, writing the per-league document set — which is a **union, not a uniform list**: NFL/MLB have Format A + `player_top_picks` + outcome; NBA has `game_edge_picks` + `player_edge_picks` + outcome (its `game_prediction` v2.0.0 has no `top_picks`); EPL has Format A + `player_predictions` + outcome; WNBA has Format A + an untyped PS passthrough + `player_predictions` + outcome.
2. **Shadow per league**: project from production inputs into containers no user reads, for a full slate cycle, **seeded from production state** (the slot rule needs the incumbent) and compared across **every reader in the register**, at every `api_version` in use — not just the six routes the KDD lists. Include the ungated surfaces (My Picks, the peer loader, push, WordPress) and `api-partners`.
3. **Switch per league** on a date with no games in the boundary band (P4), with the new screen's switch as a separate, independent lever.
4. **Keep the legacy switch and the release gate separate.** While `STAGED_LEAGUES` holds a league, v5 gets **nothing** for it on gated routes — so the v5 population's first sight of the projection is the gate release, one environment change, measured only by the shadow. Say that in the plan.

### Stage B — adapters, per route

Move a legacy route to read the records directly once its responses are proven equivalent, in this order: the routes with the fewest id and result dependencies first (list/detail), My Picks and the create path last (they carry saved ids and results). Stop writing a legacy document only when no route **and no external reader** (push, WordPress, `api-partners`, `push-the-bet-server`) reads it.

### Retirement

Per route, on usage evidence (`api_version` share), with the caveat the BFF verification found: a forced update does not change a build's `api_version` — the version is pinned in the binary (`DEFAULT_API_VERSION`), and the server-side `API_VERSION` env is a latent lever only for builds that read it. Retirement must measure the *route*, not the app version.

---

## 6. Gate list — do not switch a league until all of these are green

1. The reader/writer register is complete and the push producer is identified (P1).
2. Every derived document carries `league` + numeric `season`, proven by fixture (P2).
3. A slip created in the oldest supported build resolves after its pick leaves the live index, tested end to end (P3).
4. The family pin is by first publish, and a game published before the switch keeps its legacy ids for life (P4).
5. `c-outcome` carries result entries for settled and void picks in the shadow, or the plan states what older builds lose instead (P5).
6. The `|` topic fix is deployed (P6).
7. The per-league fixture set is signed off by data engineering and product (P7).
8. The shadow diff is clean across every reader at every version, with only the listed behaviour differences (Stage A step 2).
9. The behaviour-difference list is confirmed by product — including the two the KDD states wrongly: a void/push reads as a **win** on the v1/v3 `success` field and in My Picks (not "shown as void"), and the one-pick slot rule can change **which pick is free** for a free user, not just which is listed.

---

## 7. Rollback and recovery

- **Record-level:** re-publish the record; the projection re-drives both families. This is the primary recovery and it must be exercised in the shadow.
- **League-level (new build only):** turn the switch off; records, derived documents and older builds are untouched.
- **League-level (back to legacy):** possible only for games with no published record yet. Move the v4 start later *and* accept that already-published games stay v4 and are fixed forward. With the first-publish pin (P4), "already published" is unambiguous, which is the point.
- **Document-level:** the derived documents are regenerable from the records plus joined inputs, so a corrupted derived document is repaired by re-projecting, not by restoring a backup. State the re-projection job and its trigger as part of P8.

---

## 8. Validation, beyond the KDD's list

The KDD's six items are the right shape. Add:

7. **Cross-version slip matrix**: save and follow in v5, resolve in v6, and the reverse, for (a) a pick in a one-pick slot, (b) a pick outside it, (c) a cancelled pick, (d) a withdrawn pick, (e) a settled pick, (f) a void/push. Every case must resolve in both builds; (b)–(f) are the ones that fail today.
8. **Boundary test**: a game whose picks were published before the switch and whose start is after it — assert its ids do not change and its saved slips still resolve.
9. **Gate test**: a staged league's derived documents are withheld from v5 on every route, including the ungated surfaces; and a derived document missing `season` is caught by the fixture, not by production.
10. **Id-equality test per league**: for a sample of live picks, the projected legacy id equals the record's `pick_id`, and the `c-outcome` entry is keyed by the same string.
11. **Moneyline test**: for each league, a moneyline pick's derived id satisfies both app predicates, and no non-moneyline id in the league's vocabulary contains `h2h`.
12. **Reader-parity harness**: run the register (I8) as a table-driven comparison at v1/v3/v5/v6 for one shadow slate, with an explicit allow-list of intended differences.
13. **Write-count test**: over a shadow slate, the number of legacy document writes is at or below today's, and no write is triggered by an observation alone.
14. **Reconciliation test**: delete a derived document in the shadow and confirm the record-driven job restores it.

---

## 9. Open decisions

| # | Decision | Recommendation | Owner |
| --- | --- | --- | --- |
| C1 | Pin by first publish or by game start | **First publish** | BFF, data engineering, bet engine |
| C2 | The per-league legacy status word, its source, and its casing | Per-league fixtures from live documents, not a uniform rule | data engineering |
| C3 | Whether a push is projected as void or left ungraded for leagues where it is ungraded today | **Leave ungraded** where the old build cannot be fixed; a push rendered as a win is worse than an ungraded pick | product |
| C4 | `game_odds` — the All Games moneyline chip and the odds copied into a slip — has no source under Stage A | Assign it explicitly: joined live value (diverges from the frozen entry price) or frozen entry value (chips stop moving) | product, BFF |
| C5 | The featured `h2h:` pick's relationship to a projected moneyline pick | One of them wins; assert it in a fixture | BFF, data engineering |
| C6 | `settled_at` on the record, or a fallback | Add it | bet engine, platform |
| C7 | Whether `market_last_update` and the run metadata fields are preserved, recomputed or dropped | Preserve shape, accept new values | data engineering |
| C8 | The shadow's clean criterion and the drain date rule | Both written before the first league switches | product, data engineering |

---

## 10. What this assessment verified, and what it did not

**Verified** (commit-pinned in the three findings files): the moneyline predicate and its id sets in both app builds; the BFF's complete reader/writer inventory and its id-handling surface; the status/result derivations, including the `success = !!outcome` inversion; the release gate's mechanism and its fail-open condition; the freemium mechanics and the slot rule's interaction with unlock-N; the Publish Engine's writer chain for all five document types; the per-league id formats from live data; the absence of a settlement table and of `c-outcome` result entries; the `h2h` exclusivity in the contract formula; and two undisclosed external readers.

**Not verified:** live Cosmos contents (the `season` presence on production Format A documents is inferred from code, seeds and the gate's tests, not observed); the push producer's identity and what it watches; the installed-version share of builds carrying `ForceUpdateGate`; and any service outside the eleven repositories inspected.
