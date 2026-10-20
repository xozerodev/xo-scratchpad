# Critical Review & Assessment (Round 2): `option-b-plan.md`

**Reviewed Document:** [option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md) (Round 2 revision, 871 lines)
**Cross-Referenced Against:**
- Sibling contract & design documents in `staging/`:
  - [conf-schema-contracts.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/conf-schema-contracts.md) (updated to 37-field schema)
  - [producers-to-bff.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/producers-to-bff.md)
  - [bff-to-app-contract.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/bff-to-app-contract.md)
  - [kdds.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/kdds.md)
  - [delivery-options.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/delivery-options.md)
- **`mobile-server`** repository (`/mnt/devel/xosports/github/mobile-server`, branch `feat/edge-picks` at `35f6f44` and `main` at `9b1f710`)
- **`mobile-app`** repository (`/mnt/devel/xosports/github/mobile-app`, branch `main` at `137f2f61`, `origin/feat/XTP-125-Edge-Picks-Redesign-Oct26` at `88de3461`, and store tag `main/1.1.66` at `581d6c5d`)
- **Upstream NBA mock dataset & seed files:**
  - [nba_mock_data_2weeks.json](file:///mnt/devel/xosports/reqs/nba/tools/nba_mock_data_2weeks.json) (107 games, 1,070 canonical picks across `au`/`us`)
  - `/mnt/devel/xosports/github/mobile-server/script/db-seeds/*.json` (107 seed documents across Format A, Format B, and Format C)

---

## 1. Executive Assessment

The Round 2 revision of [option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md) is a major step forward. **All 12 Round 1 findings (`F-01` through `F-12`) were directly addressed** in the plan and in [conf-schema-contracts.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/conf-schema-contracts.md):
- The My Picks freemium & snapshot security model (`MP-1`..`MP-4`, `FE-6`, `FE-7`) is now architecturally sound (`captured_for: "subscriber" | "free_unlocked" | "backfill"`, `releaseStagedContentMiddleware` + `entitlementMiddleware` on `POST /my-picks-v2`, stripping `snapshot` from the 200 response).
- The `api_version` gate has been bumped from `v6` to `v7` (`TOP_PREDICTIONS_V3_EDGE_PICK_BLOCK_MIN_MAJOR = 7`), eliminating the collision with `mobile-app` `main` (`API_VERSION = "v6"`).
- `EdgePickBlockSchema` now adopts the group-based `access.hidden` redaction contract from [v4.schema.ts](file:///mnt/devel/xosports/github/mobile-server/src/contracts/edge-picks/v4.schema.ts#L455-L539), and the mock generator (`§8.3`) now includes `round4` normalization, closing observation flags (`is_closing`), and boundary-safe `deriveEdgeState` math (verified: **0** `m - b < 0.0002` collisions across all 1,070 NBA picks).

However, simulating the updated plan step-by-step against the actual `mobile-server` / `mobile-app` codebases and running the updated §8.3 generator logic against the real 107-game NBA dataset and the 107 `script/db-seeds/*.json` documents uncovered **8 remaining issues (`R2-01` through `R2-08` — 5 High, 2 Medium-High, 1 Medium)** that will cause runtime schema rejections, generator failures, or broken UI states if not tightened before implementation:

1. **`R2-01` (HIGH — `EdgePickBlockSchema` Completed-Unlock Invariant Collides with `completed-bypass.ts` on Postponed Games and Pre-Graded `Scheduled` Seed Picks):** `EdgePickBlockSchema` ([option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md#L206), [v4.schema.ts](file:///mnt/devel/xosports/github/mobile-server/src/contracts/edge-picks/v4.schema.ts#L480-L495)) requires `access.locked === false` whenever `edge_pick.status` is `"settled"` or `"void"`. However, `shouldSkipFreemiumForGameStatus` ([completed-bypass.ts](file:///mnt/devel/xosports/github/mobile-server/src/freemium/apply/completed-bypass.ts#L33)) intentionally keeps `"postponed"` games locked for free users (`pick.locked = true`), while `Appendix A.4` sets `edge_pick.status = "void"`. Furthermore, 5 seed picks in `script/db-seeds/` have `schedule.status = "Scheduled"` alongside `bet_outcome: "1.0"` or `"0"`, which `Appendix A.4` and `§8.3` step 6 grade as `status = "settled"` while `applyFreemiumToTopPredictionsBody` sets `pick.locked = true`. In both cases, `attachEdgePicks` produces `{ status: "void" | "settled", access: { locked: true } }`, failing `EdgePickBlockSchema` and causing `BE-6` to strip `edge_pick` and fail `V-INT-1` / `V-MOCK-3`.
2. **`R2-02` (HIGH — `ProducerRecordSchema` Enforces the Strict Canonical v4 `pick_id` Regex in JSON Schema §9, Rejecting 336 NBA Picks and 100% of Format A/B Seed Picks, Plus Seed Data Quirks):** In [conf-schema-contracts.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/conf-schema-contracts.md#L460-L464), the strict canonical `pick_id` regex is embedded inside `properties.pick_id.pattern` of the §9 JSON Schema itself (not just §9.1 `recordInvariantViolations`). Because `§8.3` step 1 preserves `pick_id` as the v3 list emits it, `ProducerRecordSchema` rejects **336 of 1,070 NBA picks** (300 `player_milestone` picks and 36 `alternate` game picks) and **100% of Format A/B seed picks**. Additionally, 3 seed data quirks (null placeholder picks, a string `player_sk`, and duplicate/cross-region `pick_id`s) and the external path of `nba_mock_data_2weeks.json` need explicit handling in `§8.2`/`§8.3`.
3. **`R2-03` (HIGH — `legacy-selection.ts` (`Appendix A.5`) Inspects `pick.type` and `pick.code`, Which Are Overwritten or Stripped on Derived v3 Picks in `matches-top-predictions-v3.ts`, and Misses `buildFeaturedH2hDetailPick`):** In `matches-top-predictions-v3.ts`, `buildBlock` receives **derived v3 picks** where `pick.type` is always `"match"` or `"player"` (the upstream type is moved to `pick.bet_type`), `pick.code` on Format B player picks is overwritten with the team abbreviation (e.g., `"CHC"`), `pick.code` on Format C picks is stripped, and `buildFeaturedH2hDetailPick` (`id: "h2h:<league>:<gameSk>:<teamSk>"`) has neither `bet_type` nor `code` nor `bet_line`.
4. **`R2-04` (HIGH — Execution Order in `§5.1` Runs `NEW ②` `attachEdgePicks` Before `NEW ③` `injectCancelledPicks`, Leaving Injected Picks Unredacted, Unvalidated, and Uncounted in `body.count`):** Running `injectCancelledPicks` after `attachEdgePicks` bypasses `EdgePickBlockSchema` validation and group redaction on the injected picks' `edge_pick` blocks, and leaves `originBody.count` (computed before `applyIfFreemium`) out of sync with `body.top_picks.length`.
5. **`R2-05` (HIGH — `era: "legacy"` Sets `edge_pick.selection = null`, Contradicting `§4.3` Line 204, `V-UNIT-3`, and `FE-6` Moneyline Exclusivity in P1):** Setting `selection = null` on all `era: "legacy"` blocks violates the group visibility rule in `§4.3` line 204, makes `V-UNIT-3` impossible to pass for legacy blocks, and breaks `FE-6` moneyline exclusivity in P1 (`EDGE_PICK_RECORD_SOURCE=none`) unless `legacy-selection.ts` populates `selection` (and `EdgePicksCard` forwards `bet_type` on `SelectedPick`).
6. **`R2-06` (MEDIUM-HIGH — `§8.3` Step 7 Scenario Fallthrough Can Drop `line_moved` (`V-MOCK-2`), and Date Bucketing Needs an Explicit `schedule.game_date` Rule):** If the pick at index 3 of a day (`line_moved`, which requires `line !== null`) is a moneyline or yes/no pick (`line === null`), falling through to index 4's scenario (`suspended`) leaves zero picks with `line_moved` on that day, failing `V-MOCK-2`. Step 7 should swap index 3 with the next open pick that has `line !== null`.
7. **`R2-07` (MEDIUM-HIGH — My Picks `MP-5(b)` & `FE-9` Reference Non-Existent Files in `mobile-app` and Miss Live-Resolved `pickOutcome`, Format A/B `line`, and `loadByGameSks` in `mobile-server`):** `FE-9` points to `app/services/myPicks/myPicks.adapter.ts` and `app/components/PredictionStatus.tsx`, neither of which exists in `mobile-app` (actual files: [MyPicksItem.tsx](file:///mnt/devel/xosports/github/mobile-app/app/components/MyPicks/MyPicksItem.tsx#L98-L105), [PickGroupCard.tsx](file:///mnt/devel/xosports/github/mobile-app/app/screens/MyPicksScreen/components/PickGroupCard.tsx#L56-L60), [type.ts](file:///mnt/devel/xosports/github/mobile-app/app/services/my-picks-v2/type.ts#L4-L22)). On the backend, live-resolved picks in `resolve-my-picks-list.ts` carry `pickOutcome` (not `outcome`), Format A/B snapshots have `line: null` unless populated via `legacy-selection.ts`, and `RecordSource` needs `loadByGameSks(gameSks, region)`.
8. **`R2-08` (MEDIUM — `EdgePicksCard.tsx` (`88de3461`) Hardcodes `outcome={null}`, Hides `<BookmakerOddsChip>` on Locked Picks, and Gates `<ProbabilityBar>` to NBA Only):** Three concrete UI gaps on the existing `88de3461` branch should be explicitly called out in `FE-3` and `FE-4` so they are not missed during implementation.

---

## 2. Round 1 Resolution Audit (`F-01` .. `F-12`)

| Round 1 ID | Summary of Round 1 Finding | Status in Updated Plan | Notes / Residual Items |
| :--- | :--- | :--- | :--- |
| **`F-01`** | My Picks freemium leak & snapshot/live race | **Resolved** | Fixed in `§3.5`, `§6` (`MP-1`..`MP-4`), `FE-6`, `FE-7`. Added `captured_for`, middleware on `POST /my-picks-v2`, stripped `snapshot` from 200 response, and gated `readAccessLocked`. |
| **`F-02`** | `api_version=v6` collision with `mobile-app` `main` | **Resolved** | Fixed across `§3.1`, `§4.1`, `§7.1` (`FE-1`), `§9` (`V-INT-1`). Bumped gate to `api_version=v7` (`TOP_PREDICTIONS_V3_EDGE_PICK_BLOCK_MIN_MAJOR = 7`). |
| **`F-03`** | `generate-mock-edge-picks.ts` violates `ProducerRecordSchema` on seed files | **Mostly Resolved** | Fixed float rounding (`round4`), null bookmaker (`odds_source_kind = "market_average"`), `stake_units >= 0`, and invariant flags (`checkIdFormula`, `checkEntryAmericanFormula`). **Residual:** `properties.pick_id.pattern` in §9 JSON Schema still rejects 336 NBA picks and all Format A/B picks — see **`R2-02`**. |
| **`F-04`** | Closing observations never generated on started/completed games | **Resolved** | Fixed in `§8.3` step 8 via `rng(pickId, "c")` and `is_closing = gameStarted && observed_at !== null`. |
| **`F-05`** | `deriveEdgeState` boundary collisions (`1e-4` and `round(1.03/d, 4)`) | **Resolved** | Fixed in `§8.3` step 4 (`p = min(0.95, round4(1.03 / d))`) and step 8 (`[b4 + 0.0001, m]` and `m + max(0.01, ...)`). Verified 0 boundary collisions across all 1,070 NBA picks. |
| **`F-06`** | `legacy-selection.ts` spread side/sign in `code`, null `bet_line`, `player_yes` | **Mostly Resolved** | Fixed in `Appendix A.5` for raw seed fields, and `player_yes`/`player_no` added to `conf-schema-contracts.md` (`37` fields). **Residual:** `matches-top-predictions-v3.ts` mutates `pick.type` and `pick.code` on derived v3 picks before `buildBlock` runs — see **`R2-03`**. |
| **`F-07`** | `EdgePickBlockSchema` locked invariants & injected cancelled picks | **Mostly Resolved** | Adopted `v4.schema.ts` group-based redaction (`access.hidden`) and `stripAsLockedTopPick` (`Appendix A.3`). **Residual:** `status: "void" \| "settled"` vs `locked: true` collision on postponed & pre-graded scheduled games (`R2-01`) and `NEW ②`/`NEW ③` ordering (`R2-04`). |
| **`F-08`** | `EdgePicksCard.tsx` `bookmakerOddsPick` omits `edge_pick` | **Resolved** | Fixed in `§7.1` `FE-3` (line 403). |
| **`F-09`** | Moneyline exclusivity on `EdgePicksCard` | **Mostly Resolved** | Fixed in `§7.1` `FE-6` (line 406). **Residual:** `era: "legacy"` sets `selection = null` and `EdgePicksCard` omits `bet_type` from `SelectedPick` — see **`R2-05`**. |
| **`F-10`** | My Picks `MyPicksItem.tsx` & `PickGroupCard.tsx` reading live odds | **Resolved** | Fixed in `§7.1` `FE-7` (line 407) and `§6.4` `MP-5(a)`. |
| **`F-11`** | `FE-9` settled `outcome` (`"push"`) vs `MyPickV2Item.outcome` (`0\|1\|2\|null`) | **Partially Resolved** | Addressed in `MP-5(b)` and `FE-9`, but `FE-9` cites non-existent files in `mobile-app` and `MP-5(b)` misses live-resolved `pickOutcome` — see **`R2-07`**. |
| **`F-12`** | P2–P4 scope in `§5.2` / `§9` (`cosmos-source.ts`, `reconcile-snapshots.ts`) | **Resolved** | Added `cosmos-source.ts`, `inject-cancelled.ts`, `reconcile-snapshots.ts`, and `V-P4-1`/`V-P4-2`. |

---

## 3. Detailed Round 2 Findings & Required Fixes

### `R2-01` [HIGH] `EdgePickBlockSchema` Completed-Unlock Invariant Collides with `completed-bypass.ts` on Postponed Games and Pre-Graded `Scheduled` Seed Picks

#### Where in `option-b-plan.md`
- `§4.3` ([option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md#L180-L186) & [L206](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md#L206))
- `§8.3` step 6 ([option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md#L458))
- `Appendix A.4` ([option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md#L766-L780))

#### Evidence & Failure Mechanism
`EdgePickBlockSchema` ([option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md#L206), matching [v4.schema.ts](file:///mnt/devel/xosports/github/mobile-server/src/contracts/edge-picks/v4.schema.ts#L480-L495)) enforces the completed-unlock invariant:
> *"Completed unlock: `status` in `settled | void` or game final ⇒ `locked = false`, `hidden = []`."*

Meanwhile, in `§4.3` ([option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md#L180-L186)), `attachEdgePicks` sets `edge_pick.access.locked = true` whenever the v3 pick has `pick.locked === true` (which was set by `applyFreemiumToTopPredictionsBody` in [top-picks.ts](file:///mnt/devel/xosports/github/mobile-server/src/freemium/apply/top-picks.ts#L103)).

There are **two concrete collisions** between how `applyFreemiumToTopPredictionsBody` decides `pick.locked` and how `Appendix A.4` / `§8.3` step 6 decide `edge_pick.status`:

1. **Collision 1 — Postponed games (`status === "void"` vs `pick.locked === true`):**
   - In [completed-bypass.ts](file:///mnt/devel/xosports/github/mobile-server/src/freemium/apply/completed-bypass.ts#L28-L53):
     ```ts
     export const FREEMIUM_LOCKED_TERMINAL_STATUSES = [
       "postponed",
     ] as const satisfies readonly GameLifecycleStatus[];
     ```
     `shouldSkipFreemiumForGameStatus("Postponed")` returns **`false`** by design (see comment at [completed-bypass.ts](file:///mnt/devel/xosports/github/mobile-server/src/freemium/apply/completed-bypass.ts#L28-L32): *"Postponed games are rescheduled and keep picks locked"*).
   - Consequently, for a free user on a postponed game, non-winner picks have `pick.locked = true`.
   - Meanwhile, `Appendix A.4` ([option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md#L778)) maps `postponed | canceled | cancelled` to `edge_pick.status = "void"`.
   - `attachEdgePicks` then produces `{ status: "void", result: "void", access: { locked: true, hidden: ["selection", "odds", "edge"] } }`, which **fails `EdgePickBlockSchema`** (`status === "void"` requires `locked === false, hidden = []`)! `BE-6` then logs `edge_pick.schema_violation` and strips `edge_pick` from the response.

2. **Collision 2 — Pre-graded `Scheduled` games in `script/db-seeds/*.json` (`status === "settled"` vs `pick.locked === true`):**
   - In the actual seed files under `/mnt/devel/xosports/github/mobile-server/script/db-seeds/`, 5 picks have `schedule.status = "Scheduled"` (`outcome.game_status = "Scheduled"`) **and** a non-null `bookmaker.bet_outcome` (`"1.0"` or `"0"`):
     - [data-c-epl-wltp-dev.json](file:///mnt/devel/xosports/github/mobile-server/script/db-seeds/data-c-epl-wltp-dev.json): `500000123_BTTS_NO_au` and `500000123_BTTS_NO_us` (`schedule.status: "Scheduled"`, `bookmaker.bet_outcome: "1.0"`).
     - [data-c-nba-ps-dev-v2.json](file:///mnt/devel/xosports/github/mobile-server/script/db-seeds/data-c-nba-ps-dev-v2.json): `100077282|11005503|R|player_under|au` (`outcome.game_status: "Scheduled"`, `bet_outcome: "0"`), `100077287|11006868|HR|player_under|au` (`outcome.game_status: "Scheduled"`, `pick_status: "final"`, `bet_outcome: 0`), and `100077296|11007152|HR|player_under|au` (`outcome.game_status: "Scheduled"`, `pick_status: "scheduled"`, `bet_outcome: 0`).
   - Because `schedule.status` is `"Scheduled"`, `shouldSkipFreemiumForGameStatus("Scheduled")` returns `false` and `applyFreemiumToTopPredictionsBody` sets `pick.locked = true` on non-winner picks.
   - Meanwhile, `Appendix A.4` ([option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md#L769-L770)) and `§8.3` step 6 ([option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md#L458)) inspect `bet_outcome` (`1` or `0`) *first* without checking whether the game is completed (`shouldSkipFreemiumForGameStatus(schedule?.status)`), so they set `edge_pick.status = "settled"`.
   - When `attachEdgePicks` runs for a free user, it sets `edge_pick.access.locked = true` on a pick with `edge_pick.status = "settled"`, **violating `EdgePickBlockSchema`** and breaking `V-INT-1` and `V-MOCK-3`!

#### Concrete Fix for `option-b-plan.md`
1. **In `Appendix A.4` (lines 766–780) and `§8.3` step 6 (line 458):**
   - Only map `outcomeCode` (`1`, `0`, `2`, `-1`) to `status = "settled" | "void"` when the game itself is in a completed/unlocked terminal status (`shouldSkipFreemiumForGameStatus(schedule?.status) === true`, i.e., `Final`, `F/OT`, `Completed`, `Full Time`, `Ended`, `AET`, `PEN`, `Canceled`, `Cancelled`, `Abandoned` — **not** `Scheduled` or `Postponed`), OR when a v4 producer record explicitly carries `settlement_status === "settled" | "void"` on a completed game.
   - For `"postponed"` games (where `shouldSkipFreemiumForGameStatus` is `false` so picks stay locked for free users), map `edge_pick.status` to `"suspended"` (`availability_reason: "line_suspended"`, `result: null`) rather than `"void"`, **or** if `status = "void"` is desired on postponed games, add `"postponed"` to `FREEMIUM_UNLOCKED_TERMINAL_STATUSES` in [completed-bypass.ts](file:///mnt/devel/xosports/github/mobile-server/src/freemium/apply/completed-bypass.ts#L23-L33). Keeping `"postponed"` locked (`status = "suspended"`) matches existing `completed-bypass.ts` behavior without changing freemium policy.
2. **In `§4.3` (`attachEdgePicks`, lines 180–186):**
   - Add a defensive guard: if `block.status === "settled" || block.status === "void"`, force `access: { locked: false, hidden: [] }` (or if `pick.locked === true` on a non-final game, coerce `block.status` to `"open"` / `"suspended"` with `result: null`) so `attachEdgePicks` can **never** emit `{ status: "settled" | "void", access: { locked: true } }`.

---

### `R2-02` [HIGH] `ProducerRecordSchema` Enforces the Strict Canonical v4 `pick_id` Regex in JSON Schema §9, Rejecting 336 NBA Picks and 100% of Format A/B Seed Picks, Plus Seed Data Quirks

#### Where in `option-b-plan.md`
- `§5.2` `BE-1` ([option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md#L243))
- `§8.2` & `§8.3` step 1 ([option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md#L446-L454))
- `§9` `V-MOCK-1` ([option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md#L539))
- Cross-ref: [conf-schema-contracts.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/conf-schema-contracts.md#L460-L464)

#### Evidence & Failure Mechanism
1. **Strict `pick_id` regex inside §9 JSON Schema (`ProducerRecordSchema`):**
   - `§5.2` line 243 states:
     > *"Validate `ProducerRecordSchema` (37 fields; `conf-schema-contracts.md` §6, §9)... `recordInvariantViolations(rec, { checkIdFormula?, checkEntryAmericanFormula? })` covers the §9.1 cross-field rules; both optional flags default to `true` (strict for P3 Cosmos) and are passed as `false` for mock-generated records whose `pick_id` and `entry_american_odds` are preserved verbatim from seed data (§8.3)."*
   - However, in [conf-schema-contracts.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/conf-schema-contracts.md#L460-L464), the §9 JSON Schema itself defines:
     ```json
     "pick_id": {
       "type": "string",
       "pattern": "^[1-9][0-9]*\\|(?:(?:moneyline|spread_t[12]|total_(?:over|under)|team_total_t[12]_(?:over|under))\\|(?:t1|t2|over|under)\\|(?:na|-?(?:0|[1-9][0-9]*)(?:\\.[0-9]+)?)|[1-9][0-9]*\\|[a-z0-9_]+\\|player_(?:over|under|yes|no)\\|(?:na|-?(?:0|[1-9][0-9]*)(?:\\.[0-9]+)?))\\|main\\|(?:full|reg|1h|2h|1q|2q|3q|4q|1p|2p|3p|f5)\\|(?:au|us)$"
     }
     ```
   - We ran this regex against every pick in `/mnt/devel/xosports/reqs/nba/tools/nba_mock_data_2weeks.json` (1,070 picks) and `/mnt/devel/xosports/github/mobile-server/script/db-seeds/*.json`:
     - **In `nba_mock_data_2weeks.json`, 336 out of 1,070 picks FAIL `properties.pick_id.pattern`:**
       - **300 `player_milestone` picks** (e.g., `40021717855|400003547276|ast|player_milestone|6|main|full|us`), because `§8.3` step 1 preserves `pick_id` verbatim (containing `|player_milestone|6|`) while step 2 normalizes `bet_type` to `"player_over"` and `entry_line` to `5.5`.
       - **36 `alternate` game picks** (e.g., `40021717857|spread_t1|t1|-7.5|alternate|full|us`), because `pick_id` contains `|alternate|` whereas the regex hardcodes `\|main\|`.
     - **In `script/db-seeds/*.json`, 100% of Format A and Format B picks (137 picks across MLB, NFL, EPL, AFL, NRL, CPL, Squash, TD, Legacy NBA) FAIL `properties.pick_id.pattern`** (e.g., `2001_H2H_us`, `100076741|11013473|R|player_under|au`, `2001_player_PaTDs_us`).
   - Because `properties.pick_id.pattern` is in `ProducerRecordSchema` (§9) rather than gated by `checkIdFormula` (§9.1), `ProducerRecordSchema.safeParse(rec)` rejects all 336 NBA picks and all 137 Format A/B seed picks!

2. **Four concrete seed/file quirks in `§8.2` / `§8.3`:**
   - **External path of `nba_mock_data_2weeks.json`:** `§8.2` line 446 refers to `nba_mock_data_2weeks.json` without a path. It resides at `/mnt/devel/xosports/reqs/nba/tools/nba_mock_data_2weeks.json` (outside both `xo-scratchpad` and `mobile-server`). The generator should accept `--nba-mock <path>` (defaulting to `/mnt/devel/xosports/reqs/nba/tools/nba_mock_data_2weeks.json` if present, or copying it into `mobile-server/script/db-seeds/`).
   - **Null placeholder `top_picks` in `script/db-seeds/`:** In [data-c-wltp-dev-v4.json](file:///mnt/devel/xosports/github/mobile-server/script/db-seeds/data-c-wltp-dev-v4.json) (`id: "nba|game_prediction|4"`) and [data-c-nba-wltp-dev-v2.json](file:///mnt/devel/xosports/github/mobile-server/script/db-seeds/data-c-nba-wltp-dev-v2.json) (`id: "1072"`), `au.top_picks[0]` is a placeholder object `{ id: null, type: null, probability: null, decimal_odds: null, ... }`. `generateTopPicks` in [top-pick.ts](file:///mnt/devel/xosports/github/mobile-server/src/lib/top-picks/top-pick.ts#L316) skips picks missing `type` or `decimal_odds`; the §8.3 generator must do the same (`if (!pick.id || !pick.type || pick.decimal_odds == null) continue`).
   - **String `player_sk` in `data-c-nba-ps-dev-v2.json`:** In [data-c-nba-ps-dev-v2.json](file:///mnt/devel/xosports/github/mobile-server/script/db-seeds/data-c-nba-ps-dev-v2.json) (`id: "mlb|player_top_picks|100077296"`), `player_sk` is `"11007152"` (a string, whereas `ProducerRecordSchema` requires `integer | null`). Step 1 of `§8.3` must coerce `player_sk` via `Number(raw.player_sk)`.
   - **Duplicate and cross-region `pick_id`s in `script/db-seeds/`:**
     - `100077282|11005503|R|player_under|au` appears **twice** in `au.team_1.picks` of `mlb|player_top_picks|100077282` ([data-c-nba-ps-dev-v2.json](file:///mnt/devel/xosports/github/mobile-server/script/db-seeds/data-c-nba-ps-dev-v2.json)).
     - `100077296|11007152|HR|player_under|au` is used inside **both** `au` and `us` of `mlb|player_top_picks|100077296` ([data-c-nba-ps-dev-v2.json](file:///mnt/devel/xosports/github/mobile-server/script/db-seeds/data-c-nba-ps-dev-v2.json)).
     - `992_lower_TP` (no region suffix) is used inside **both** `au` and `us` of `id: "992"` ([data-c-wltp-dev-v3.json](file:///mnt/devel/xosports/github/mobile-server/script/db-seeds/data-c-wltp-dev-v3.json)).
     Therefore, `mock-source.ts` (`§5.4`) and `generate-mock-edge-picks.ts` (`§8.3`) must key records by **`(region, pick_id)`** (not `pick_id` alone) and deduplicate identical `(region, pick_id)` entries within the same document.

#### Concrete Fix for `option-b-plan.md`
1. **In `§5.2` `BE-1` (line 243) and `§8.3` (line 454):**
   - Relax `pick_id` in `ProducerRecordSchema` to `z.string().min(1)` (matching `v4.schema.ts:276`), and enforce the strict canonical v4 `pick_id` regex **inside `recordInvariantViolations` when `checkIdFormula === true`** (alongside the `build_pick_id()` reconstruction check). That way, P3 Cosmos (`checkIdFormula: true`) enforces both the regex and the reconstruction formula, while P2 Mock (`checkIdFormula: false`) validates all 37 fields and all numerical/state invariants without rejecting preserved legacy/milestone/alternate `pick_id` strings.
2. **In `§5.4` (`mock-source.ts`, line 276) and `§8.3` (lines 451–454):**
   - Index mock records by `${region}:${pick_id}` (or two maps `au` and `us` keyed by `pick_id`), skip null placeholder picks (`!pick.id || !pick.type || pick.decimal_odds == null`), deduplicate repeated `(region, pick_id)` entries, and coerce `player_sk` with `Number(raw.player_sk)`.

---

### `R2-03` [HIGH] `legacy-selection.ts` (`Appendix A.5`) Inspects `pick.type` and `pick.code`, Which Are Overwritten or Stripped on Derived v3 Picks in `matches-top-predictions-v3.ts`, and Misses `buildFeaturedH2hDetailPick`

#### Where in `option-b-plan.md`
- `§5.1` ([option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md#L219-L228))
- `§5.2` `BE-5` ([option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md#L247))
- `Appendix A.1` ([option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md#L700-L725))
- `Appendix A.5` ([option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md#L784-L819))

#### Evidence & Failure Mechanism
In `matches-top-predictions-v3.ts`, `getAllAvailableTopPicksForGame` ([common.ts](file:///mnt/devel/xosports/github/mobile-server/src/lib/match/common.ts#L133-L253)) transforms raw Cosmos documents into **derived v3 picks** before returning them to the handler:
1. **`pick.type` is overwritten with `"match"` or `"player"`:**
   - In `generateTopPicks` ([top-pick.ts](file:///mnt/devel/xosports/github/mobile-server/src/lib/top-picks/top-pick.ts#L343-L345)), `generatePlayerTopPicks` ([top-pick.ts](file:///mnt/devel/xosports/github/mobile-server/src/lib/top-picks/top-pick.ts#L746-L748)), `mapCanonicalGamePick` ([picks.ts](file:///mnt/devel/xosports/github/mobile-server/src/lib/match/canonical/picks.ts#L465-L466)), and `mapCanonicalPlayerPick` ([picks.ts](file:///mnt/devel/xosports/github/mobile-server/src/lib/match/canonical/picks.ts#L690-L691)), the derived v3 pick sets:
     ```ts
     bet_type: pick.type,
     type: "match", // or "player"
     ```
   - `Appendix A.5` ([option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md#L788-L807)) switches on `pick.type` (`"H2H"`, `"UND_SPR+"`, `"player_over"`, etc.). When called from `buildBlock` on a derived v3 pick, `pick.type` is `"match"` or `"player"`, so **every single branch in `Appendix A.5` fails to match** unless it reads `const rawType = pick.bet_type ?? pick.type`!
2. **`pick.code` is overwritten on Format B player picks and stripped on Format C picks:**
   - In `generatePlayerTopPicks` ([top-pick.ts](file:///mnt/devel/xosports/github/mobile-server/src/lib/top-picks/top-pick.ts#L744-L753)):
     ```ts
     const teamInfo = getTeamInfo(sport, teamKey, scheduleData);
     return {
       ...pick,
       ...
       code: teamInfo.code,
     };
     ```
     For Format B player picks (where `pick.type` in the seed was `"player_over"` / `"player_under"` and `pick.code` was `"R"`, `"HR"`, `"H"`, `"SO"`, `"RBI"`, `"PTS"`, etc.), the derived v3 pick has **`pick.code` overwritten with the team abbreviation** (e.g., `"CHC"`, `"ATL"`), and the original stat code only survives inside the 3rd pipe segment of `pick.id` (`100076741|11013473|R|player_under|au`) or in `pick.shortPickDescription` / `pick.pickDescription`!
   - In `mapCanonicalGamePick` ([picks.ts](file:///mnt/devel/xosports/github/mobile-server/src/lib/match/canonical/picks.ts#L447)) and `mapCanonicalPlayerPick` ([picks.ts](file:///mnt/devel/xosports/github/mobile-server/src/lib/match/canonical/picks.ts#L604)), `code: _code` is destructured and **stripped** from the returned v3 pick (`stat_code` is also stripped in `mapCanonicalPlayerPick` at line 607, surviving only in the 3rd pipe segment of `pick.id` or `pick.statType`).
   - In `generateTopPicks` ([top-pick.ts](file:///mnt/devel/xosports/github/mobile-server/src/lib/top-picks/top-pick.ts#L337-L347)), `...pick` preserves `pick.code` on Format A game picks (so `code: "DAL -7.0"` is still present on Format A derived game picks).
3. **Featured H2H picks (`buildFeaturedH2hDetailPick`) are unshifted in `matches-top-predictions-v3.ts`:**
   - At [matches-top-predictions-v3.ts](file:///mnt/devel/xosports/github/mobile-server/src/functions/matches-top-predictions-v3.ts#L229-L239), when `wltp?.is_top_pick === true` on a non-canonical game (which occurs on 25 legacy seed games in `script/db-seeds/`), the handler unshifts `buildFeaturedH2hDetailPick(...)` ([game-h2h.ts](file:///mnt/devel/xosports/github/mobile-server/src/lib/match/game-h2h.ts#L223-L297)).
   - That object has `id: "h2h:<league>:<gameSk>:<teamSk>"` (when odds exist), `type: "match"`, `pick: "<Team Name>"`, `pickDescription: "<Team Name> to Win"`, `probability`, `american_odds`, `decimal_odds`, `market_odds`, and `bookmaker: { name, odds, american_odds, decimal_odds, url }` — **no `bet_type`, no `code`, no `bet_line`, and no `stake_units`/`bet_stake`**.
   - Even worse, if `hasTeamGameOdds(odds)` is `false` or `winLoss` is draw ([game-h2h.ts](file:///mnt/devel/xosports/github/mobile-server/src/lib/match/game-h2h.ts#L240-L261)), `buildFeaturedH2hDetailPick` returns an object with **no `id` and no odds at all**!

#### Concrete Fix for `option-b-plan.md`
Update `Appendix A.5` (`legacy-selection.ts`) and `Appendix A.1` (`build-block.ts`) so `legacy-selection.ts` works identically whether passed a **raw seed pick** (in `generate-mock-edge-picks.ts`) or a **derived v3 pick** (in `buildBlock` / `capturePickSnapshot` / `resolve-my-picks-list.ts`):
1. Read `const rawType = pick.bet_type ?? pick.type`.
2. For Format B/C player picks where `pick.code` was overwritten by `teamInfo.code` or stripped, extract `stat_code` from:
   - `pick.stat_code` (if present on raw Format C), else
   - the 3rd pipe segment of `pick.id` (`pick.id.split("|")[2]`) when `pick.id` is pipe-delimited (`Format B` / `Format C`), else
   - `pick.code` (for Format A `player_<STAT>` picks where `pick.type === "player"` in raw seed and `pick.code` is `"PaTDs"`, `"RecYds"`, etc.).
3. Handle `buildFeaturedH2hDetailPick` (`typeof pick.id === "string" && pick.id.startsWith("h2h:")` or `rawType === "match" && !pick.bet_type && /to Win$/i.test(pick.pickDescription ?? "")`):
   - Map to `{ market: "moneyline", side: pick.team_sk === schedule?.team_1_sk ? "t1" : "t2", line: null, stat_code: null }`.
   - In `Appendix A.1`, if a featured H2H pick has no `id` or no `decimal_odds` (the odds-less fallback in `game-h2h.ts:240-261`), skip attaching `edge_pick` (leave `edge_pick` omitted) so `EdgePickBlockSchema` is never called with `id: undefined` or `odds: null` on an unlocked pick.

---

### `R2-04` [HIGH] Execution Order in `§5.1` Runs `NEW ②` `attachEdgePicks` Before `NEW ③` `injectCancelledPicks`, Leaving Injected Picks Unredacted, Unvalidated, and Uncounted in `body.count`

#### Where in `option-b-plan.md`
- `§4.2` ([option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md#L154))
- `§5.1` ([option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md#L219-L228))
- `Appendix A.3` ([option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md#L747-L764))

#### Evidence & Failure Mechanism
In `§5.1` ([option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md#L220-L227)), the pipeline inside `matches-top-predictions-v3.ts` is ordered as:
```text
├── build originBody = { count, top_picks }
├── NEW ① if apiVersionMajor >= 7:
│     records = recordSource.load({ date, tzOffset, region, sport })
│     blocks  = Map<pickId, EdgePickBlock> via buildBlock(pick, records.get(pick.id), ctx)
├── applyIfFreemium(originBody)  ── existing freemium pass (unchanged)
├── NEW ② attachEdgePicks(body, blocks, freemiumCtx): redact per pick, validate (BE-6)
├── NEW ③ inject cancelled v4 picks not in the list (P4) (BE-11)
└── responseCache.getOrSet(cacheKey, ...)
```
Look at what happens when `NEW ③` (`injectCancelledPicks`) runs **after** `NEW ②` (`attachEdgePicks`):
1. `Appendix A.3` ([option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md#L754-L756)) says:
   > *"When `locked === true`, the v3 fields are nulled with the same `stripAsLockedTopPick(synthesisedPick)` helper that `src/freemium/apply/top-picks.ts` uses (`locked: true`, `CENSORED_PICK_FIELDS` set to `null`) and `edge_pick` is redacted by the same `attachEdgePicks` rule."*
   And `§4.2` ([option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md#L154)) says:
   > *"`count` counts every item in `top_picks`, injected picks included."*
2. If `NEW ③` runs after `NEW ②`, `attachEdgePicks` has already finished! Unless `injectCancelledPicks` duplicates `attachEdgePicks` (group redaction + `EdgePickBlockSchema` validation) and manually mutates `body.count = body.top_picks.length`, injected cancelled picks will skip `attachEdgePicks` and `body.count` will be stale.
3. Furthermore, if `injectCancelledPicks` runs **before** `attachEdgePicks` (or if `injectCancelledPicks` synthesizes the cancelled v3 pick + unredacted `EdgePickBlock` into `blocks` before `attachEdgePicks` runs, and updates `body.count = body.top_picks.length`), then `attachEdgePicks` handles redaction and `EdgePickBlockSchema` validation uniformly in one place for both regular and injected picks.

#### Concrete Fix for `option-b-plan.md`
Swap `NEW ②` and `NEW ③` in `§5.1` (lines 226–227):
- **`NEW ②` `injectCancelledPicks(body, records, blocks, schedulesByGameSk, freemiumCtx)`:** For any record in `records` with `availability_status === "cancelled"` whose `pick_id` is not in `body.top_picks`, synthesize the v3 pick (applying `stripAsLockedTopPick` if `freemiumCtx.isFreemium && !shouldSkipFreemiumForGameStatus(schedule?.status)`), add its unredacted `EdgePickBlock` to `blocks`, append the pick to `body.top_picks`, and set `body.count = body.top_picks.length`.
- **`NEW ③` `attachEdgePicks(body, blocks, freemiumCtx)`:** Redact each pick's block according to `pick.locked` and `hiddenGroupsFor(pick, block)`, and validate every block against `EdgePickBlockSchema` (logging `edge_pick.schema_violation` and omitting `edge_pick` on failure).

---

### `R2-05` [HIGH] `era: "legacy"` Sets `edge_pick.selection = null` (`§4.3` & `Appendix A.1`), Contradicting `§4.3` Line 204, `V-UNIT-3` Line 536, and `FE-6` Moneyline Exclusivity in P1

#### Where in `option-b-plan.md`
- `§4.3` ([option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md#L167), [L203-L204](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md#L203-L204))
- `§7.1` `FE-6` ([option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md#L406))
- `§9` `V-UNIT-3` ([option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md#L536))
- `Appendix A.1` ([option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md#L710-L715))

#### Evidence & Failure Mechanism
In `§4.3` (line 167 & 203) and `Appendix A.1` (line 715), when `era === "legacy"` (i.e., `EDGE_PICK_RECORD_SOURCE=none` in P1, or a pick has no matching v4 record), `buildBlock` sets `edge_pick.selection = null`.

This causes **three contradictions** across the plan:
1. **Contradicts `§4.3` line 204 (`EdgePickBlockSchema` group visibility rule):**
   - Line 204 states: *"Groups: each hidden group's fields null; each visible group's values set, except legacy `entry.line` and `entry.source`, which may be null."*
   - In [v4.schema.ts](file:///mnt/devel/xosports/github/mobile-server/src/contracts/edge-picks/v4.schema.ts#L502-L505), `EdgePickBlockSchema` specifically had to add `if (val.era === "v4" && val.selection === null)` to avoid rejecting legacy blocks with `selection: null`.
2. **Contradicts `V-UNIT-3` (`§9` line 536):**
   - `V-UNIT-3` requires:
     > *"For every pick produced across the 9 seed files, `buildBlock(pick, undefined, ctx)` (legacy path) and `buildBlock(pick, mockRecord, ctx)` (v4 path) both validate against `EdgePickBlockSchema`, and **the block's side and line agree with the pick's `pickDescription`**."*
   - On the legacy path (`buildBlock(pick, undefined, ctx)`), if `selection` is `null`, the block has **no `side`** (`block.selection` is `null`), making `V-UNIT-3`'s assertion impossible on the legacy path!
3. **Breaks `FE-6` moneyline exclusivity in P1 for Format A `H2H` picks:**
   - `FE-6` ([option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md#L406)) states:
     > *"Pass `bet_type` (or `edge_pick.selection.market`) into `SelectedPick` on `EdgePicksCard` so the moneyline exclusivity check in `GamePick.tsx:68-79` (`isH2hPick`, replacing opposite-team H2H pick in the slip) fires for EdgePicksCard just like TopPickCard — keyed on `edge_pick.selection.market === 'moneyline'` with fallback `isH2hPick`."*
   - In P1 (`tst` and `prod` have `EDGE_PICK_RECORD_SOURCE=none`), every pick has `era: "legacy"`. If `edge_pick.selection` is `null`, `edge_pick.selection?.market` is `undefined`. And in `GamePick.tsx:68-79` ([GamePick.tsx](file:///mnt/devel/xosports/github/mobile-app/app/screens/PredictionsScreen/PredictionsDetailScreen/_components/GamePick.tsx#L68-L79)), `isH2hPick(pick)` checks `pick.bet_type?.toUpperCase() === "H2H" || pick.bet_type?.toLowerCase() === "moneyline" || pick.id.startsWith("h2h:")`. So `FE-6` **must** pass both `bet_type: pick.edge_pick?.selection?.market ?? pick.bet_type` into `SelectedPick` on `EdgePicksCard.tsx:148-161` AND populate `selection` on `era: "legacy"` blocks using `legacy-selection.ts`!

Notice that `Appendix A.1` ([option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md#L710)) **already calls `legacy-selection.ts`** on the legacy path to compute `entry.line`! Populate `selection: legacySelection(pick, schedule)` (when non-null) on the legacy path in `Appendix A.1` as well.

#### Concrete Fix for `option-b-plan.md`
1. **In `Appendix A.1` (line 715) and `§4.3` (lines 167, 203–204):**
   - On the legacy path (`era: "legacy"`), set `selection: legacySelection(pick, schedule)` (which returns `{ market, side, line, stat_code }` or `null` only if unparseable, and gets nulled by `attachEdgePicks` when `"selection"` is in `access.hidden`).
   - This makes `V-UNIT-3` pass on both legacy and v4 paths and gives the app `edge_pick.selection.market` even in P1 when `EDGE_PICK_RECORD_SOURCE=none`.
2. **In `§7.1` `FE-6` (line 406):**
   - Explicitly specify that `EdgePicksCard.tsx:148-161` adds `bet_type: edgePick?.selection?.market ?? pick.bet_type` to the `SelectedPick` object passed to `addPick`, and `isH2hPick` in `GamePick.tsx:68-79` matches `"moneyline"` as well as `"H2H"`.

---

### `R2-06` [MEDIUM-HIGH] `§8.3` Step 7 Scenario Fallthrough Can Drop `line_moved` (`V-MOCK-2`), and Date Bucketing Needs an Explicit `schedule.game_date` Rule

#### Where in `option-b-plan.md`
- `§8.3` step 7 ([option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md#L459-L473))
- `§9` `V-MOCK-2` ([option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md#L540))

#### Evidence & Failure Mechanism
1. **`line_moved` scenario can be skipped by fallthrough:**
   - `§8.3` step 7 ([option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md#L459)) states:
     > *"Within a day, open picks (`settlement_status === "pending"` and game not started) are sorted by `pick_id`: the first nine take the nine scenarios in table order (covering every status × edge_state × signal combination on any day with ≥ 9 open picks), and the rest select via `rng(pickId, "s")` with the weights below. If a pick isn't eligible for its scenario (table below), it takes the next scenario it is eligible for."*
   - Look at index `3` in the 9-scenario table: `line_moved` (`Requires: line !== null`).
   - All subsequent scenarios in indices `4..8` (`suspended`, `withdrawn`, `cancelled`, `stale`, `mean_rev`) have `Requires: any`.
   - Therefore, if the pick at sorted index `3` happens to be a `moneyline` pick (`line === null`), it is ineligible for `line_moved` and falls through to `suspended` (`Requires: any`). Meanwhile, the pick at index `4` (even if it has `line !== null`) is assigned scenario `4` (`suspended`), NOT `line_moved`!
   - Result: if the remaining open picks on that day (weighted at only `8%` for `line_moved`) don't randomly roll `line_moved`, that day has **0 `line_moved` picks**, failing `V-MOCK-2` (*"Every day in the 2-week NBA window with ≥ 9 open picks exercises all 9 scenarios"*)!
2. **Date bucketing key in step 7 (`schedule.game_date` vs UTC date of `game_datetime`):**
   - For US NBA games tipping off at 7:30 PM – 10:30 PM ET (`23:30Z` – `03:30Z` next day), `schedule.game_date` is the US slate date (e.g., `"2026-03-19"`), whereas `game_datetime.slice(0, 10)` in UTC splits a single US slate across two UTC dates.
   - In `nba_mock_data_2weeks.json`, grouping by `schedule.game_date` gives 15 slate dates (`2026-03-19` through `2026-04-02`), where every future slate date with games (`2026-03-26` through `2026-04-02`, 8 days) has between 30 and 100 open picks per region (`≥ 9` open picks on every future day).

#### Concrete Fix for `option-b-plan.md`
In `§8.3` step 7 (line 459):
- Specify that "within a day (grouped by `(region, schedule.game_date ?? game_datetime.slice(0, 10))`)" open picks are sorted by `pick_id`.
- Instead of falling through when the pick at index `3` (`line_moved`) has `entry_line === null`, **swap** it with the first open pick at index `j > 3` (or `j < 3` not requiring `line !== null`) that has `entry_line !== null`. Since every NBA game has spread, total, and player over/under picks (`entry_line !== null`), a swap is guaranteed to succeed on any day with ≥ 9 open picks, guaranteeing 100% coverage of all 9 scenarios (`V-MOCK-2`).

---

### `R2-07` [MEDIUM-HIGH] My Picks `MP-5(b)` & `FE-9` Reference Non-Existent Files in `mobile-app` and Miss Live-Resolved `pickOutcome`, Format A/B `line`, and `loadByGameSks` in `mobile-server`

#### Where in `option-b-plan.md`
- `§5.4` ([option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md#L276))
- `§6.4` `MP-1` & `MP-5(b)` ([option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md#L384-L388))
- `§7.1` `FE-9` ([option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md#L409))

#### Evidence & Failure Mechanism
1. **Frontend `FE-9` references two files that do not exist in `mobile-app`:**
   - `§7.1` `FE-9` ([option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md#L409)) lists:
     - `app/services/myPicks/myPicks.adapter.ts:69-89`
     - `app/components/PredictionStatus.tsx:10`
   - Neither file exists on `main` (`137f2f61`) or `origin/feat/XTP-125-Edge-Picks-Redesign-Oct26` (`88de3461`).
   - In the actual `mobile-app` codebase:
     - `GET /my-picks-v2` is typed in [app/services/my-picks-v2/type.ts](file:///mnt/devel/xosports/github/mobile-app/app/services/my-picks-v2/type.ts#L4-L22) (`export interface MyPickV2Item { ... outcome?: number | null; ... }`) and fetched directly via [app/services/myPicks/myPicks.service.ts](file:///mnt/devel/xosports/github/mobile-app/app/services/myPicks/myPicks.service.ts#L60-L65) and [app/services/myPicks/myPicks.hook.ts](file:///mnt/devel/xosports/github/mobile-app/app/services/myPicks/myPicks.hook.ts#L48-L65) with no adapter file.
     - Single-pick outcome icons on the My Picks screen are rendered in [app/components/MyPicks/MyPicksItem.tsx](file:///mnt/devel/xosports/github/mobile-app/app/components/MyPicks/MyPicksItem.tsx#L98-L105):
       ```tsx
       {type === 'completed' && (
         <View style={styles.statusContainer}>
           <AppIcon
             name={pick.outcome ? 'tick' : 'close_red'}
             size={pick.outcome ? 20 : 12}
           />
         </View>
       )}
       ```
       Note the existing bug: when `pick.outcome === 2` (push/void), `Boolean(2)` is `true`, so `MyPicksItem.tsx` renders a **green `'tick'`**!
     - Group/multibet outcome status on the My Picks screen is computed in [app/screens/MyPicksScreen/components/PickGroupCard.tsx](file:///mnt/devel/xosports/github/mobile-app/app/screens/MyPicksScreen/components/PickGroupCard.tsx#L56-L60) and [L84-L97](file:///mnt/devel/xosports/github/mobile-app/app/screens/MyPicksScreen/components/PickGroupCard.tsx#L84-L97):
       ```tsx
       const status = useMemo(() => {
         if (type === 'upcoming') return undefined;
         return group.items?.some((p) => !p.outcome) ? false : true;
       }, [group.items, type]);
       ```
       Which also treats `outcome: 2` as won (`!2 === false`)!
     - Meanwhile, on the Top Picks screen (`TopPickCard` / `EdgePicksCard`), outcome pills are rendered by [app/utils/predictionOutcome.ts](file:///mnt/devel/xosports/github/mobile-app/app/utils/predictionOutcome.ts#L1-L34) (`export type PredictionOutcome = "correct" | "incorrect" | "void"`) and [app/components/common/PredictionOutcomeIndicator.tsx](file:///mnt/devel/xosports/github/mobile-app/app/components/common/PredictionOutcomeIndicator.tsx#L12-L22).

2. **Backend `MP-5(b)` misses three concrete details in `resolve-my-picks-list.ts`:**
   - **Live-resolved picks have `pickOutcome`, not `outcome`:** In [resolve-my-picks-list.ts](file:///mnt/devel/xosports/github/mobile-server/src/lib/my-pick/resolve-my-picks-list.ts#L52-L58), `lookupResolvedPick` returns a live pick from `availableIndex` (`picksForGame`) whenever the pick is still in the current Cosmos top-picks doc; it only falls back to `hydratePickFromSnapshot` when the pick has disappeared from the live doc. A live pick from `picksForGame` has **`pickOutcome: 0 | 1 | 2 | null`** (set by `mapOutcomeToResult` in [top-pick.ts](file:///mnt/devel/xosports/github/mobile-server/src/lib/top-picks/top-pick.ts#L55-L67) or `mapSettlementOutcome` in [picks.ts](file:///mnt/devel/xosports/github/mobile-server/src/lib/match/canonical/picks.ts#L313-L329)), whereas `hydratePickFromSnapshot` ([snapshot.ts](file:///mnt/devel/xosports/github/mobile-server/src/lib/my-pick/snapshot.ts#L220)) sets **`outcome: 0 | 1 | 2 | null`**, and `hydrateGameH2hMyPickItem` ([resolve-my-picks-list.ts](file:///mnt/devel/xosports/github/mobile-server/src/lib/my-pick/resolve-my-picks-list.ts#L28-L50)) sets **neither** (relying on the client or `schedule.outcome.result`)!
     Therefore, `MP-5(b)` in `resolve-my-picks-list.ts` must read `const rawCode = resolvedPick.outcome ?? resolvedPick.pickOutcome`, and ensure `outcome: rawCode` is populated on the returned `MyPickV2Item` for both live-resolved and snapshot-hydrated items.
   - **Whole-number `line` check for `push` vs `void` on Format A/B picks:** `MP-5(b)` ([option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md#L388)) distinguishes `"push"` from `"void"` on code `2` *"when the market has a whole-number line"*. However, on Format A and Format B picks, `pick.line` is `undefined` (the line is in `bookmaker.bet_line` or `pick.code`), so `capturePickSnapshot` ([snapshot.ts](file:///mnt/devel/xosports/github/mobile-server/src/lib/my-pick/snapshot.ts#L129)) stores `line: null`. `MP-1` (`capturePickSnapshot`) and `MP-5(b)` should fall back to `legacySelection(pick, schedule)?.line` when `pick.line == null`.
   - **`RecordSource` needs `loadByGameSks(gameSks, region)`:** `§5.4` ([option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md#L276)) defines `RecordSource` with only `load({ date, tzOffset, region, sport }): Promise<Map<string, ProducerRecord>>`. While `matches-top-predictions-v3` and `POST /my-picks-v2` (`createMyPickV3` has the game schedule's date/sport) can query by date or `game_sk`, `GET /my-picks-v2` (`resolve-my-picks-list.ts`) and `reconcile-snapshots.ts` (`BE-12`) load user slips spanning **arbitrary historical `game_sk`s across multiple dates and sports**. Adding `loadByGameSks(gameSks: number[], region: "au" | "us"): Promise<Map<string, ProducerRecord>>` to `RecordSource` makes `MP-5(b)` and `BE-12` clean and O(1) on both `mock-source.ts` and `cosmos-source.ts`.

#### Concrete Fix for `option-b-plan.md`
1. **In `§5.4` (line 276):** Add `loadByGameSks(gameSks: number[], region: "au" | "us"): Promise<Map<string, ProducerRecord>>` to the `RecordSource` interface.
2. **In `§6.4` `MP-1` & `MP-5(b)` (lines 384, 388):**
   - In `MP-1` (`capturePickSnapshot`), populate `snapshot.line` via `pick.line ?? legacySelection(pick, schedule)?.line ?? null`.
   - In `MP-5(b)` (`resolve-my-picks-list.ts`), normalize `outcome: resolvedPick.outcome ?? resolvedPick.pickOutcome ?? null` on every returned item, and derive `result: "won" | "lost" | "push" | "void" | null` from the v4 record's `settlement_result` (via `recordSource.loadByGameSks`) or from `outcome` + `(resolvedPick.line ?? legacySelection(resolvedPick, schedule)?.line)`.
3. **In `§7.1` `FE-9` (line 409):** Replace the non-existent `myPicks.adapter.ts` and `PredictionStatus.tsx` paths with the actual files:
   - [app/services/my-picks-v2/type.ts](file:///mnt/devel/xosports/github/mobile-app/app/services/my-picks-v2/type.ts#L4-L22): add `result?: 'won' | 'lost' | 'push' | 'void' | null;` to `MyPickV2Item`.
   - [app/components/MyPicks/MyPicksItem.tsx](file:///mnt/devel/xosports/github/mobile-app/app/components/MyPicks/MyPicksItem.tsx#L98-L105) & [app/screens/MyPicksScreen/components/PickGroupCard.tsx](file:///mnt/devel/xosports/github/mobile-app/app/screens/MyPicksScreen/components/PickGroupCard.tsx#L56-L60): render `"won"` (`outcome === 1`), `"lost"` (`outcome === 0`), and `"push" | "void"` (`outcome === 2`) distinctly instead of `pick.outcome ? 'tick' : 'close_red'`.

---

### `R2-08` [MEDIUM] `EdgePicksCard.tsx` (`88de3461`) Hardcodes `outcome={null}`, Hides `<BookmakerOddsChip>` on Locked Picks, and Gates `<ProbabilityBar>` to NBA Only

#### Where in `option-b-plan.md`
- `§7.1` `FE-3` & `FE-4` ([option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md#L403-L404))
- `§7.2` ([option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md#L413-L433))

#### Evidence & Failure Mechanism
Inspecting [EdgePicksCard.tsx](file:///mnt/devel/xosports/github/mobile-app/app/screens/TopPicksScreen/_components/EdgePicksCard.tsx) and [BookmakerOddsChip.tsx](file:///mnt/devel/xosports/github/mobile-app/app/screens/TopPicksScreen/_components/BookmakerOddsChip.tsx) on `origin/feat/XTP-125-Edge-Picks-Redesign-Oct26` (`88de3461`) reveals three concrete UI gaps that `FE-3` and `FE-4` should explicitly call out:

1. **`CardOutcomeFooterRow` in `EdgePicksCard.tsx:283` hardcodes `outcome={null}`:**
   - At `EdgePicksCard.tsx:282-290` (`88de3461`):
     ```tsx
     <CardOutcomeFooterRow
       outcome={null}
       matchStatus={matchStatus}
       ...
     />
     ```
     Unlike `TopPickCard.tsx:231` (which passes `outcome={mapPickOutcome(pick.pickOutcome)}`), `EdgePicksCard.tsx` passes `outcome={null}`, so completed picks never display a Won / Lost / Push / Void indicator in the card footer!
   - Furthermore, [app/utils/predictionOutcome.ts](file:///mnt/devel/xosports/github/mobile-app/app/utils/predictionOutcome.ts#L1-L21) currently defines `export type PredictionOutcome = "correct" | "incorrect" | "void"` and [PredictionOutcomeIndicator.tsx](file:///mnt/devel/xosports/github/mobile-app/app/components/common/PredictionOutcomeIndicator.tsx#L12-L22) only renders `"correct"`, `"incorrect"`, and `"void"`. To satisfy `§7.2` (*"Settled (`status = settled`): result pill (`Won` / `Lost` / `Push`); Void (`status = void`): muted `Void` pill"*), `predictionOutcome.ts` and `PredictionOutcomeIndicator.tsx` need `"push"` added (`mapEdgePickResult(edgePick?.result) ?? mapPickOutcome(pick.pickOutcome)`).
2. **`BookmakerOddsChip` disappears completely on locked picks instead of rendering blurred odds with the unredacted bookmaker label:**
   - In `bookmakerOdds.ts:70-75` (`88de3461`), `bookmakerOddsView` returns `null` whenever `original == null` (`entry.odds` and `bookmaker`/`american_odds`/`decimal_odds` are all nulled by the BFF when `"odds"` is in `access.hidden`).
   - In `BookmakerOddsChip.tsx:24-25` (`88de3461`), `const view = bookmakerOddsView(pick, oddsFormat); if (!view) return null;` — so the entire `<BookmakerOddsChip>` component disappears on locked picks (`locked === true`), even though `BookmakerOddsChip.tsx:66-76` has `<CensoredValue blurred={blurred} placeholder="-110" compact>` ready to render blurred odds and `§4.3` specifically keeps `edge_pick.entry.source` (`{ kind, code, name }`) **unredacted** on locked picks!
3. **`ProbabilityBar` in `EdgePicksCard.tsx:271` is gated to `LEAGUES.NBA` and ignores `edge_pick.probability`:**
   - At `EdgePicksCard.tsx:271-278` (`88de3461`), `<ProbabilityBar>` is wrapped in `{leagueName.toLowerCase() === LEAGUES.NBA && (...)}` and reads `pick.probability ?? pick.xoProbability` instead of `edgePick?.probability ?? pick.probability ?? pick.xoProbability`. Since `edge_pick.probability` is populated for all 9 leagues (EPL, MLB, NFL, NBA, AFL, NRL, CPL, Squash, TD), gating the probability bar to NBA hides it on the other 8 sports.

#### Concrete Fix for `option-b-plan.md`
Update `§7.1` `FE-3` and `FE-4` (lines 403–404) to explicitly include:
- **`FE-3` (`bookmakerOdds.ts` & `BookmakerOddsChip.tsx`):** When `pick.locked || pick.edge_pick?.access.locked` is true and odds are redacted (`original == null`), `bookmakerOddsView` still returns `{ sourceLabel: resolveBookmakerSourceLabel(pick), original: "-110", current: null, arrow: null }` so `BookmakerOddsChip` renders the unredacted bookmaker label alongside `<CensoredValue blurred placeholder="-110" compact>`.
- **`FE-4` (`EdgePicksCard.tsx`, `predictionOutcome.ts`, `PredictionOutcomeIndicator.tsx`):** Wire `outcome={mapEdgePickOutcome(edgePick?.result, pick.pickOutcome)}` into `<CardOutcomeFooterRow>` at `EdgePicksCard.tsx:283` (supporting `"correct" | "incorrect" | "push" | "void"`), and read `edgePick?.probability ?? pick.probability ?? pick.xoProbability` in `<ProbabilityBar>` across all sports.

---

## 4. Summary Verification Matrix & Readiness Verdict

| Area | Round 1 Status | Round 2 Status | Remaining Action Before Coding |
| :--- | :---: | :---: | :--- |
| **API Version Gating (`api_version=v7`)** | Blocked (`F-02`) | **Ready** | None — `v7` gate is clean across BFF and app. |
| **My Picks Security & Snapshot Contract (`MP-1`..`MP-4`, `FE-6`, `FE-7`)** | Blocked (`F-01`, `F-09`, `F-10`) | **Ready (with `R2-05` & `R2-07` tweaks)** | Add `bet_type` to `SelectedPick` on `EdgePicksCard` (`R2-05`); fix file paths in `FE-9` and read `pickOutcome` in `MP-5(b)` (`R2-07`). |
| **`EdgePickBlockSchema` & Freemium Redaction (`BE-2`, `BE-6`)** | Blocked (`F-07`) | **Needs `R2-01` & `R2-05` fixes** | Align `Appendix A.4` / `§8.3` step 6 with `shouldSkipFreemiumForGameStatus` (`R2-01`); populate `selection` on `era: "legacy"` (`R2-05`). |
| **P4 Cancelled-Pick Injection (`BE-11`, `Appendix A.3`)** | Missing (`F-07`, `F-12`) | **Needs `R2-04` fix** | Swap `NEW ②` and `NEW ③` in `§5.1` so injected picks run through `attachEdgePicks` and update `body.count` (`R2-04`). |
| **Legacy Selection Parser (`BE-5`, `Appendix A.5`)** | Blocked (`F-06`) | **Needs `R2-03` fix** | Read `pick.bet_type ?? pick.type`, parse `stat_code` from `pick.id` when `pick.code` is overwritten/stripped, and handle `h2h:` picks (`R2-03`). |
| **Mock Generator & Seed Coverage (`§8.3`, `V-MOCK-1`..`3`)** | Blocked (`F-03`..`F-05`) | **Needs `R2-02` & `R2-06` fixes** | Move `pick_id` regex check under `checkIdFormula` (`R2-02`), handle the 3 seed quirks (`R2-02`), and swap `line_moved` at index 3 when `line === null` (`R2-06`). |
| **`EdgePicksCard` & `BookmakerOddsChip` UI (`FE-3`, `FE-4`)** | Blocked (`F-08`) | **Needs `R2-08` fix** | Wire `outcome` into `CardOutcomeFooterRow`, keep `BookmakerOddsChip` visible when `blurred`, and ungate `ProbabilityBar` (`R2-08`). |
