# Critical Review & Technical Assessment of `option-b-plan.md`

**Reviewed Document:** [option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md) (862 lines)  
**Sibling Specifications Cross-Checked:**
- [delivery-options.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/delivery-options.md)
- [conf-schema-contracts.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/conf-schema-contracts.md) (Producer Pick Record `4.0.0`)
- [kdds.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/kdds.md) (KDD-001, KDD-002, KDD-003)
- [coexistence-approach.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/coexistence-approach.md) (Prerequisites P1–P9, Invariants I1–I8)

**Codebases & Datasets Verified:**
- **BFF (`mobile-server`):** `/mnt/devel/xosports/github/mobile-server` on `feat/edge-picks` at `35f6f44`
- **App (`mobile-app`):** `/mnt/devel/xosports/github/mobile-app` on `main` at `137f2f61`, `origin/feat/XTP-125-Edge-Picks-Redesign-Oct26` at `88de3461`, and store tag `main/1.1.66`
- **Datasets:** [nba_mock_data_2weeks.json](file:///mnt/devel/xosports/reqs/nba/tools/nba_mock_data_2weeks.json) (673 docs, 107 games, 1,070 picks) and `/mnt/devel/xosports/github/mobile-server/script/db-seeds/*.json`

---

## 1. Executive Summary & Overall Verdict

[option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md) is a strong, deeply researched implementation plan. Unlike abstract architecture documents, it is grounded in actual line-level inspection of `mobile-server` (`35f6f44`), `mobile-app` (`137f2f61`, `88de3461`, and `main/1.1.66`), Terraform app settings, and Cosmos seed files. Its core architectural choices—attaching an additive `edge_pick` block on `GET /v3/matches/:date/top-predictions`, keeping `locks` untouched (`V-INV-1`), decoupling the remote-config `API_VERSION` from `v6` (`VG-1`/`VG-2`), fixing the `1.1.66` My Picks `NaN` odds/returns (`MP-1`–`MP-5`), and fixing the FCM pipe-in-topic mismatch (`MP-6`)—are sound and well-justified.

However, our verification against the live code, the Producer Pick Record `4.0.0` contract ([conf-schema-contracts.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/conf-schema-contracts.md)), and the actual mock/seed JSON datasets uncovered **12 technical defects and omissions** that will cause security regressions, test failures, or broken UI states if not resolved before implementation:

| ID | Severity | Area | Summary |
|---|---|---|---|
| **F-01** | **CRITICAL** | Security / Freemium (`§6 MP-1`, `MP-4`, `§3 D3`) | Combining unconditional snapshot capture on `POST /my-picks-v2` (`MP-1`) with showing any snapshot-backed or locked-peer item to its owner on `GET /my-picks-v2?api_version=v3` (`MP-4`) creates a **complete freemium bypass oracle**: any free user can unlock every locked pick on the platform by posting its unredacted `pick.id` to `POST /my-picks-v2`. |
| **F-02** | **HIGH** | Generator & Schema (`§4.4 R6`, `§8.3`, `§10.1 V-UNIT-5`) | In [nba_mock_data_2weeks.json](file:///mnt/devel/xosports/reqs/nba/tools/nba_mock_data_2weeks.json), **760 of 1,070 picks (71%)** have `bookmaker.bet_odds.american_odds` that do **not** match `decimalToAmerican(decimal_odds)` (e.g., `1.85` paired with `-111` instead of `-118`), and `script/db-seeds/*.json` has 16-decimal-place floats, `bookmaker.name: null`, and `bet_stake: 0`. Copying prices/probabilities "as written" (`R6`, `§8.3` step 3) while enforcing §9.1 invariants (`§8.3` step 11, `V-UNIT-5`) will throw on 71% of NBA mock picks and all MLB seed player picks. |
| **F-03** | **HIGH** | Generator (`§8.3` steps 7–8, `§8.4`) | Step 7 restricts scenario assignment to *"status `open` and the game not started"*, leaving started/completed games (including all 7 games on golden day `2026-10-22`) with **no scenario assigned** for Step 8; worse, if a started game has `observed_at: null`, Step 8's rule *"For started games the observation has `is_closing: true`"* directly violates §9.1 Invariant #4 (`observed_at === null` $\implies$ `is_closing === false`). |
| **F-04** | **HIGH** | Legacy Selection Mapping (`§5.2`, `Appendix A.5`) | Three concrete mismatches against `script/db-seeds/*.json`: (a) `2002_FAV_SPR_us` in [data-c-nfl-wltp-dev.json](file:///mnt/devel/xosports/github/mobile-server/script/db-seeds/data-c-nfl-wltp-dev.json) has an already-signed negative `position: "-6.5"` (not an unsigned magnitude), and `31679_FAV_SPR<` in [data-c-nba-wltp-dev-v2.json](file:///mnt/devel/xosports/github/mobile-server/script/db-seeds/data-c-nba-wltp-dev-v2.json) has `code: "T1_9.5_1.95"` vs. `bet_line: "T2_spread_under"`; (b) `2002_player_TD_au`/`us` in [data-c-nfl-ps-dev.json](file:///mnt/devel/xosports/github/mobile-server/script/db-seeds/data-c-nfl-ps-dev.json) has `type: "player_yes"`, which `Appendix A.5` does not handle (`edge_pick: null`); (c) `37_H2H` has `bet_line: null` and requires `pick.code` fallback. |
| **F-05** | **HIGH** | Freemium / Cancelled Injection (`§5.3`, `Appendix A.3`) | `injectCancelledPicks` sets `locked: true` on pre-game cancelled picks for free users and `attachEdgePicks` redacts `edge_pick`, **but `Appendix A.3` never calls `nullifyLockedPickFields` on the injected item's top-level fields**, leaking unredacted `pickDescription`, `probability`, `bookmaker.bet_odds`, and `market_odds` over the wire (`SEC-R-002`). |
| **F-06** | **HIGH** | App Integration (`§7.1 FE-3`, `FE-6`, `§2.2`, `§10.1 V-FE-1`) | Three missing edits in [EdgePicksCard.tsx](file:///mnt/devel/xosports/github/mobile-app/app/screens/TopPicksScreen/_components/EdgePicksCard.tsx) on `XTP-125`: (a) `bookmakerOddsPick` (lines 92–100) is constructed with an explicit property whitelist that omits `edge_pick: pick.edge_pick`, so `FE-3` in `bookmakerOdds.ts` never receives `pick.edge_pick`; (b) `CardOutcomeFooterRow` (line 281) hardcodes `outcome={null}` (noted in `§2.2` line 108 and tested in `V-FE-1`, but omitted from `§7.1`); (c) `FE-6` leaves Add-to-Slip enabled on `Postponed` games (`edge_pick.status === "open"` per `D7`) and on completed/cancelled fallback cards where `edge_pick` is `null`. |
| **F-07** | **HIGH** | My Picks Settlement & UI (`§6 MP-5`, `§2.2`, `§7.1`) | (a) `MP-5(c)` targets `my-picks-v2.ts:177–218`, but `GET /my-picks-v2?api_version=v3` actually computes slip `status`, `totalOdds`, and `returnAmount` in [`buildMyPickSlipResponse`](file:///mnt/devel/xosports/github/mobile-server/src/lib/my-pick/my-pick.ts#L162-L213); (b) [`buildMyPickSlipResponse`](file:///mnt/devel/xosports/github/mobile-server/src/lib/my-pick/my-pick.ts#L196) requires `item.status === "Completed"` for every leg, so slips with a pre-game cancelled leg or a `"Cancelled"` game never settle (`status: false` forever); (c) [MyPicksItem.tsx](file:///mnt/devel/xosports/github/mobile-app/app/components/MyPicks/MyPicksItem.tsx#L101) (`pick.outcome ? "tick" : "close_red"`) and [PickGroupCard.tsx](file:///mnt/devel/xosports/github/mobile-app/app/screens/MyPicksScreen/components/PickGroupCard.tsx#L57) treat `outcome === 2` (truthy!) as a **Won** pick with a green checkmark because no `FE-*` item updates them. |
| **F-08** | **MEDIUM** | Lifecycle & Schema (`§4.3`, `§5.5`, `Appendix A.4`) | `Appendix A.4` maps `pickOutcome` `0`/`1`/`2` to `settled`/`void` before checking whether the game is completed, while [`isMatchCompleted`](file:///mnt/devel/xosports/github/mobile-server/src/freemium/apply/completed-bypass.ts#L52-L63) only checks game status. Any pick graded before game completion (e.g., mid-game or `100077296` in `data-c-nba-ps-dev-v2.json`) gets `edge_pick.status: "settled"` with `access.locked: true`, violating `EdgePickBlockSchema` (`settled` and `void` picks are never locked). |
| **F-09** | **MEDIUM** | Lifecycle & My Picks (`§6 MP-5(b)`, `Appendix A.4`) | Both `Appendix A.4` (line 761) and `MP-5(b)` (line 385) restrict `outcome = "push"` on `pickOutcome === 2` to *"spread or total on a whole-number line"*, contradicting [conf-schema-contracts.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/conf-schema-contracts.md#L98-L100) §4.2 which explicitly includes whole-number `player_prop` lines. |
| **F-10** | **MEDIUM** | App Title & Badge (`§7.1 FE-2`, `FE-4`) | (a) In `edgePickTitle.ts` (`XTP-125`), `selectionTeam` does not handle `selection: "draw" | "yes" | "no"` (or canonical `"t1"`/`"t2"`), rendering lowercase `"no"` or `"draw"` as the card title for EPL `btts` / 3-way moneyline draw picks; (b) `EdgeValueBadge.tsx` uses `Math.abs(value) <= 1 ? value * 100 : value` (which misformats any EV edge $> 1.0$, i.e. $> 100\%$) and uses the same orange downward-arrow styling for `closed` as for `narrowing`. |
| **F-11** | **MEDIUM** | Legacy Route & Cache (`§5.4`, `§9.1`, `Appendix A.3`) | (a) `§5.4` (line 280) says to wire the block builder into the legacy `GET /matches/:date/top-predictions` route (`matches-top-predictions.ts:171`), which does not run `attachEdgePicks` or `injectCancelledPicks`; (b) `Appendix A.3` sets `type: record.market === "player_prop" ? "player" : "match"` on injected cancelled picks, whereas [`filterTopPredictionsByType.ts`](file:///mnt/devel/xosports/github/mobile-app/app/screens/TopPicksScreen/filterTopPredictionsByType.ts#L8-L13) in `mobile-app` checks `prediction_type` **before** `type` (`pick.prediction_type ?? pick.type`) — if `prediction_type` is omitted on injected rows, `TopPickCard` / `EdgePicksCard` follow/analytics (`String(props.prediction_type ?? "match")`) misclassifies every injected cancelled player prop as `"match"`! |
| **F-12** | **LOW** | Citations & Line Numbers (`§2.1`, `§2.2`, `§3`, `§6`) | Minor file/line citation drift in four places (`target-follow.ts:62` $\to$ `63`; `EdgePicksCard.tsx:218–224` $\to$ `278–286`; `src/lib/match/parsers/sections.ts` $\to$ `src/lib/match/parsers/sections/index.ts`; `my-picks-v2.ts:195` $\to$ `src/lib/my-pick/my-pick.ts:196`). |

---

## 2. Verification of Code Citations & Baseline Claims (§2.1, §2.2, §8.2)

We verified every code citation and factual claim in [option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md) against `mobile-server` (`35f6f44`), `mobile-app` (`137f2f61`, `88de3461`, `main/1.1.66`), and the data files.

### 2.1 Verified & Accurate Claims
- **Version Gate & Cache Keys (`§2.1` lines 53–59):**
  - [`releaseStagedContentMiddleware`](file:///mnt/devel/xosports/github/mobile-server/src/lib/middleware/api-version-middleware.ts#L50-L58) runs [`withStagedContentAllowed(isStagedContentReleased(request), handler)`](file:///mnt/devel/xosports/github/mobile-server/src/lib/middleware/api-version-middleware.ts#L55).
  - [`RELEASE_API_VERSION_MAJOR = 6`](file:///mnt/devel/xosports/github/mobile-server/src/lib/match/canonical/gate.ts#L78) and [`parseApiVersionMajor`](file:///mnt/devel/xosports/github/mobile-server/src/lib/match/canonical/gate.ts#L91-L97) gate `STAGED_LEAGUES` (`nba:2026` in [infra/envs/dev/app_settings.tf](file:///mnt/devel/xosports/github/mobile-server/infra/envs/dev/app_settings.tf#L71)).
  - [`buildFreemiumCacheKey`](file:///mnt/devel/xosports/github/mobile-server/src/freemium/cache/response-cache-keys.ts#L16-L43) includes `apiVersion`, and [`withFreemiumResponseCache`](file:///mnt/devel/xosports/github/mobile-server/src/freemium/cache/response-cache.ts#L48-L117) caches pre-freemium responses before [`applyIfFreemium`](file:///mnt/devel/xosports/github/mobile-server/src/functions/matches-top-predictions-v3.ts#L303-L309) clones and mutates them per caller.
  - [`MAX_FREEMIUM_RESPONSE_CACHE_BYTES = 512 * 1024`](file:///mnt/devel/xosports/github/mobile-server/src/freemium/cache/ttl-cache.ts#L10) is enforced in [`TtlCache.set`](file:///mnt/devel/xosports/github/mobile-server/src/freemium/cache/ttl-cache.ts#L120-L129).
- **Freemium Lock & Strip Behavior (`§2.1` lines 60–65):**
  - [`applyFreemiumToTopPicksResponse`](file:///mnt/devel/xosports/github/mobile-server/src/freemium/apply/top-picks.ts#L116-L162) sets `pick.locked = false` on completed games ([`isMatchCompleted`](file:///mnt/devel/xosports/github/mobile-server/src/freemium/apply/completed-bypass.ts#L52-L63)) and on the top $K$ unlocked picks per enabled sport ([`selectTopKUnlockedIds`](file:///mnt/devel/xosports/github/mobile-server/src/freemium/apply/pick-freemium-helpers.ts#L98-L113)), and `pick.locked = true` on all remaining active picks.
  - [`nullifyLockedPickFields`](file:///mnt/devel/xosports/github/mobile-server/src/freemium/resolve/locked-pick-response.ts#L206-L246) strips [`TOP_PICK_STRIP_PATHS`](file:///mnt/devel/xosports/github/mobile-server/src/freemium/registry/strip-helpers.ts#L169-L196) and nulls [`LOCKED_PICK_IDENTITY_KEYS`](file:///mnt/devel/xosports/github/mobile-server/src/freemium/resolve/locked-pick-response.ts#L67-L84), while preserving `id`.
- **1.1.66 Store Build vs. `main` App Behavior (`§2.2` lines 101–115):**
  - On `main/1.1.66`, `PickGroupCard.tsx` (lines 60–72, 156) computes `const odds = pick.bookmaker?.bet_odds?.decimal_odds` without `resolveBookmaker`. Because canonical NBA picks set `bookmaker: [bm]` (an array, in [`canonical/picks.ts`](file:///mnt/devel/xosports/github/mobile-server/src/lib/match/canonical/picks.ts#L524)) and [`hydratePickFromSnapshot`](file:///mnt/devel/xosports/github/mobile-server/src/lib/my-pick/snapshot.ts#L332-L373) omits `bookmaker` altogether, `odds` is `undefined` and `acc.totalOdds * odds` evaluates to `NaN` (`$NaN` in the summary row on `1.1.66`).
  - On `main` (`137f2f61`), [`AppConfigContext.tsx`](file:///mnt/devel/xosports/github/mobile-app/app/context/AppConfigContext.tsx#L48) sets `const apiVersion = DEFAULT_API_VERSION` where [`DEFAULT_API_VERSION = "v6"`](file:///mnt/devel/xosports/github/mobile-app/app/hooks/useAppConfig.ts#L42), whereas `main/1.1.66` calls `resolveApiVersion(appConfig)` and reads `api_version` from `GET /config` (`API_VERSION = "v5"` in [infra/envs/dev/app_settings.tf](file:///mnt/devel/xosports/github/mobile-server/infra/envs/dev/app_settings.tf#L28)).

### 2.2 Inaccurate Citations & Misidentified Code Locations
1. **`src/functions/my-picks-v2.ts:177–218` (`status: true`, `my-picks-v2.ts:195`) in `§6 MP-5` (line 385):**
   - **Plan claim (line 385):** *"On a settled slip (`status: true`, `my-picks-v2.ts:195`), set `returnAmount: 0` when any leg has `outcome === 0`"*
   - **Actual code:** In [my-picks-v2.ts](file:///mnt/devel/xosports/github/mobile-server/src/functions/my-picks-v2.ts#L89-L111), `GET /my-picks-v2?api_version=v3` returns early at line 107 after calling [`resolveMyPicksListForUser`](file:///mnt/devel/xosports/github/mobile-server/src/lib/my-pick/resolve-my-picks-list.ts#L71-L322), which calls [`buildMyPickSlipResponse`](file:///mnt/devel/xosports/github/mobile-server/src/lib/my-pick/my-pick.ts#L162-L213) at line 317. Line 196 of [`src/lib/my-pick/my-pick.ts`](file:///mnt/devel/xosports/github/mobile-server/src/lib/my-pick/my-pick.ts#L196) (not `my-picks-v2.ts`!) is where `const status = sortedActiveItems.every((item) => item.status === "Completed")` and `returnAmount: totalOdds * myPick.stake` (line 211) live for `v3`. (See **F-07** for the full impact.)
2. **`EdgePicksCard.tsx:218–224` (`XTP-125`) in `§2.2` (line 108):**
   - **Plan claim (line 108):** *"`EdgePicksCard.tsx:218–224` (`XTP-125`) | Footer `outcome` is hardcoded `null`; Add button checks only `status === GAME_STATUS.COMPLETED`"*
   - **Actual code on `88de3461`:** `FooterComponent` and `CardOutcomeFooterRow` (`outcome={null}` and `status === GAME_STATUS.COMPLETED`) are at **lines 278–286** of `EdgePicksCard.tsx` on `origin/feat/XTP-125-Edge-Picks-Redesign-Oct26`.
3. **`src/lib/match/parsers/sections.ts` in `§3 D5` (line 139):**
   - **Plan claim (line 139):** *"Match Detail (`src/lib/match/parsers/sections.ts`) uses `GamePick.tsx`"*
   - **Actual path:** [`src/lib/match/parsers/sections/index.ts`](file:///mnt/devel/xosports/github/mobile-server/src/lib/match/parsers/sections/index.ts) (there is no `sections.ts` file).
4. **`src/functions/target-follow.ts:62` in `§2.1` (line 81) and `§6 MP-6` (line 387):**
   - **Actual line:** Line **63** of [`src/functions/target-follow.ts`](file:///mnt/devel/xosports/github/mobile-server/src/functions/target-follow.ts#L63) (`const topic = `${validPayload.targetType}-${validPayload.targetId?.replace(/\|/g, "_")}`;`).

---

## 3. Detailed Technical Findings (Critical & High Severity)

### F-01 [CRITICAL]: `MP-1` + `MP-4` Creates a Complete Freemium Bypass Oracle for All Locked Picks

#### Plan Quotations
- **[option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md#L62) (§2.1, line 62):**
  > "**Lock and null (`src/freemium/resolve/locked-pick-response.ts`).** `nullifyLockedPickFields` (line 206) walks `TOP_PICK_STRIP_PATHS` (`strip-helpers.ts:169–196`) and nulls `LOCKED_PICK_IDENTITY_KEYS` (`locked-pick-response.ts:67–84`, including `line`, `selection`, `threshold_k`, `player_full_name`, `team_full_name`). **`id` is in no strip list** (`strip-helpers.ts:28–75, 169–196`)."
- **[option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md#L135) (§3 Decision D3, line 135):**
  > "| Is a pick that was saved while open and later cancelled or locked still returned in the user's My Picks? | **Yes, to its owner.** A saved slip item resolved from its create-time snapshot (`is_snapshot: true`) or from a now-locked peer is shown to the user who saved it. Only an item with neither a snapshot nor a peer stays fail-closed (`src/freemium/apply/my-picks.ts:86–94`). |"
- **[option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md#L381) (§6 `MP-1` & `MP-4`, lines 381, 384):**
  > "| `MP-1` | `src/functions/my-picks-create-v2.ts:24–29` | Load peers with `loadMyPicksPeersByGameIds` (`resolve-my-picks-list.ts:392–451`) and write `snapshot: capturePickSnapshot(found)` (`snapshot.ts:120–159`) per item, matching `my-picks-create-v3.ts:64–118`. Peers load once per game; match by `id` or `bet_id`. If the peer load fails, store the item without a snapshot and log (no new validation, no new failure mode). |"
  > "| `MP-4` | `src/freemium/apply/my-picks.ts:86–94` | Owner visibility (decision D3): a saved item resolved from its snapshot (`is_snapshot: true` on the resolved row, `snapshot.ts:372`) is shown to its owner, and so is a listed item whose peer is locked. Without a snapshot and without a peer, keep today's fail-closed rule |"

#### Proof of Vulnerability
1. On `GET /v3/matches/:date/top-predictions`, every locked pick (`locked: true`) still exposes its unredacted `id` (`pick_id`) and `game_sk` to free users.
2. Unlike [`my-picks-create-v3.ts`](file:///mnt/devel/xosports/github/mobile-server/src/functions/my-picks-create-v3.ts#L92-L107) (which runs `entitlementMiddleware` and rejects locked picks for free users via `findUnavailableMyPickItemIds` with `403 PICK_LOCKED`), [`my-picks-create-v2.ts`](file:///mnt/devel/xosports/github/mobile-server/src/functions/my-picks-create-v2.ts#L16-L44) (`POST /my-picks-v2`) has **no entitlement middleware and no locked-pick check**.
3. Under `MP-1` (*"no new validation, no new failure mode"*), when a free user sends `POST /my-picks-v2` with `{ stake: 10, items: [{ id: "1", predictionId: "<locked_pick_id>", gameId: "<game_sk>" }] }`:
   - `POST /my-picks-v2` loads the **unredacted** peer pick via [`loadMyPicksPeersByGameIds`](file:///mnt/devel/xosports/github/mobile-server/src/lib/my-pick/resolve-my-picks-list.ts#L327-L451), builds `snapshot: capturePickSnapshot(found)` containing the unredacted `description`, `line`, `odds_decimal`, `odds_american`, `probability`, `player_full_name`, and `team_full_name`, persists it to `c-mypicks-v2`, **and returns `my_pick` (including the unredacted `snapshot`) directly in the `201` response body** ([`my-picks-create-v2.ts:32-35`](file:///mnt/devel/xosports/github/mobile-server/src/functions/my-picks-create-v2.ts#L32-L35))!
4. Then, under `MP-4`, when that free user calls `GET /my-picks-v2?api_version=v3`, [`isMyPickItemFreemiumAvailable`](file:///mnt/devel/xosports/github/mobile-server/src/freemium/apply/my-picks.ts#L69-L106) returns `true` because `MP-4` makes both `is_snapshot: true` items and *"a listed item whose peer is locked"* visible to a free-user owner!
5. Consequently, any free user can unmask every locked pick across all sports simply by submitting its `id` and `game_sk` to `POST /my-picks-v2`.

#### Required Fix
1. **Gate `POST /my-picks-v2` (`MP-1`) with `entitlementMiddleware`:** In the mobile app ([EdgePicksCard.tsx:118](file:///mnt/devel/xosports/github/mobile-app/app/screens/TopPicksScreen/_components/EdgePicksCard.tsx#L118), [TopPickCard.tsx:188](file:///mnt/devel/xosports/github/mobile-app/app/screens/TopPicksScreen/_components/TopPickCard.tsx#L188)), adding picks to a slip is gated on `isActiveSubscription`. On the server, `POST /my-picks-v2` must run `entitlementMiddleware` and check `findUnavailableMyPickItemIds` for free users (or at minimum, refuse to capture a snapshot or allow saving when `!getEntitlementContext().isSubscriber` and the peer pick is locked), and strip raw `snapshot` from the `POST /my-picks-v2` response.
2. **Tighten `MP-4` (`src/freemium/apply/my-picks.ts:86–94`):** A free user should only see a saved item whose live peer is now locked or absent if the item carries a server-captured `snapshot` (`item.snapshot != null`, which is only written after passing the create-time entitlement/unlock check). Never return an un-snapshotted item whose live peer is locked to a free user.

---

### F-02 [HIGH]: `R6` / `§8.3` ("Entry Price as Written") Directly Contradicts `§8.3` Step 11 / `V-UNIT-5` (§9.1 Invariants) on 71% of `nba_mock_data_2weeks.json` and on `script/db-seeds/*.json`

#### Plan Quotations
- **[option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md#L214) (§4.4 Rule `R6`, line 214):**
  > "`R6` | Both come from the same price. In the generator (§8.3), `record.entry_decimal_odds` and `record.entry_american_odds` are copied from the derived document's bookmaker price, so the top-level fields and `edge_pick.entry` carry the exact same number."
- **[option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md#L450) (§8.3 steps 3 & 11, lines 450, 476):**
  > "3. **Entry price.** `entry_decimal_odds` and `entry_american_odds` = the document's price as written (R6); `entry_captured_at` = game start minus 24 hours."
  > "11. **Self-check.** Validate every record with `producer-record.schema.ts`. Mock records skip the id-formula invariant (`checkIdFormula: false`) because ids are reused as they are (Format A ids such as `2001_H2H_us`, NBA milestone ids); phantom records check it. A failure is a generator bug: throw in tests, report in dev."
- **[option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md#L533) (§10.1 `V-UNIT-5`, line 533):**
  > "`V-UNIT-5` | `producer-record.schema.test.ts` | Producer schema and §9.1 invariants: the contract's five example records pass; one broken invariant each fails; `checkIdFormula: false` skips only the id check"
- **[conf-schema-contracts.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/conf-schema-contracts.md#L642-L643) (§9.1 Invariants #2 & #3, lines 642–643):**
  > "2. `probability`, `entry_decimal_odds`, `entry_edge`, `current_decimal_odds`, and `current_edge` are rounded to at most 4 decimal places."
  > "3. `entry_edge`, `current_edge`, `edge_status`, `entry_american_odds`, and `current_american_odds` match the formulas in Section 5."

#### Empirical Verification Against the Actual Datasets
We ran the §5 / §9.1 formulas across every pick in [nba_mock_data_2weeks.json](file:///mnt/devel/xosports/reqs/nba/tools/nba_mock_data_2weeks.json) and `/mnt/devel/xosports/github/mobile-server/script/db-seeds/*.json`:

1. **`nba_mock_data_2weeks.json` — 760 out of 1,070 picks (71.0%) violate `entry_american_odds === decimalToAmerican(entry_decimal_odds)`:**
   - `40021717855|h2h_t1|t1|null|main|full|us`: `decimal_odds: 1.85`, `american_odds: -111` (contract §5.3 formula gives `-118`).
   - `40021717855|400000000383|reb|player_under|8.5|main|full|au`: `decimal_odds: 1.95`, `american_odds: -118` (formula gives `-105`).
   - `40021717855|400003547276|ast|player_milestone|6|main|full|au`: `decimal_odds: 2.1`, `american_odds: 115` (formula gives `110`).
   - If `generator.ts` copies `entry_american_odds` "as written" per `R6` and `§8.3` step 3, **760 records fail `producer-record.schema.ts` in Step 11 (`throw in tests`)**.
   - Conversely, if `generator.ts` recomputes `entry_american_odds = decimalToAmerican(entry_decimal_odds)` without updating the derived document, then for US users (`region = "US"`), `edge_pick.entry.odds_american` (`-118`) **disagrees** with the top-level `bookmaker.bet_odds.american_odds` (`-111`), violating `R6`.
2. **`script/db-seeds/*.json` — Multiple §9.1 and §6.3 Violations When Copied "As Written":**
   - **16–17 decimal places on `probability` and `decimal_odds` (violates §9.1 Invariant #2):**
     - [data-c-wltp-dev-v4.json](file:///mnt/devel/xosports/github/mobile-server/script/db-seeds/data-c-wltp-dev-v4.json): `2_lower_TP_au`/`us` (`probability: 0.6222770468217342`), `7_lower_TP_au`/`us` (`0.5952879574416123`), `1122_higher_TP_au` (`0.6626083270082992`).
     - [data-c-epl-wltp-dev.json](file:///mnt/devel/xosports/github/mobile-server/script/db-seeds/data-c-epl-wltp-dev.json): `500000123_BTTS_NO_au`/`us` (`probability: 0.43253035022173436`).
     - [data-c-nba-ps-dev-v2.json](file:///mnt/devel/xosports/github/mobile-server/script/db-seeds/data-c-nba-ps-dev-v2.json): all 7 MLB player picks have 16-digit `probability` (e.g., `0.6770568744981647`) and 16-digit `decimal_odds` (`1.7874015748031495`, `1.6666666666666667`).
   - **`bookmaker.name: null` and `bet_stake: 0` in [data-c-nba-ps-dev-v2.json](file:///mnt/devel/xosports/github/mobile-server/script/db-seeds/data-c-nba-ps-dev-v2.json):** All 7 MLB player picks have `bookmaker.name: null` (violating non-empty `bookmaker`), and `100076741|11013473|R|player_under|au` and `100076740|11001961|HR|player_under|au` have `bet_stake: 0` (violating `stake_units > 0` for non-withdrawn picks).
   - **Null-placeholder object in [data-c-wltp-dev-v4.json](file:///mnt/devel/xosports/github/mobile-server/script/db-seeds/data-c-wltp-dev-v4.json) (`game_sk: 100076740`)** where `top_picks.au` and `top_picks.us` are `{ id: null, type: null, code: null, probability: null }`.
   - **Duplicate pick ID and cross-region ID in [data-c-nba-ps-dev-v2.json](file:///mnt/devel/xosports/github/mobile-server/script/db-seeds/data-c-nba-ps-dev-v2.json):** `100077282` contains two identical `100077282|11005503|R|player_under|au` entries in `team_1.picks`, and `100077296` uses `id: "100077296|11007152|HR|player_under|au"` inside both the `au` and `us` buckets (so indexing by `pick_id` alone without `region` overwrites `au` with `us`).

#### Required Fix
Update `§8.3` (steps 2–5, 11) and `R6` so that:
1. `entry_decimal_odds = round4(d)` and `probability = round4(p)` are always rounded to 4 decimal places.
2. Either (a) `producer-record.schema.ts` accepts `checkEntryAmericanFormula: false` alongside `checkIdFormula: false` for legacy/mock records so `entry_american_odds` can preserve the document's written American price (`R6`), **or** (b) `entry_american_odds = decimalToAmerican(entry_decimal_odds)` and `buildBlock` / seed normalization uses the same formula so `R6` and Invariant #3 both hold.
3. Default missing `bookmaker.name` to `"SportsBet"` (`au`) / `"DraftKings"` (`us`), default `bet_stake <= 0` to `1.0`, skip picks with `id == null`, and key the in-memory record store by `${region}:${pick_id}` (with fallback to `pick_id`).

---

### F-03 [HIGH]: `§8.3` Steps 7 & 8 Leave Started/Completed Games Without an Observation Scenario and Risk Violating §9.1 Invariant #4 (`observed_at: null` with `is_closing: true`)

#### Plan Quotations
- **[option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md#L454-L473) (§8.3 steps 7 & 8, lines 454–473):**
  > "7. **Scenario.** Eligible picks: status `open` and the game not started. On a day with $N \ge 6$ eligible picks per region, assign the first six (sorted by `pick_id`) to the six required scenarios so every state is represented at least once; assign the rest by `hash(pick_id) mod 100`: `live` 35, `narrowing` 20, `closed` 12, `moved` 13, `no_observation` 10, `cancelled` 10. On smaller days, assign in priority order: `live`, `narrowing`, `moved`, `cancelled`, `closed`, `no_observation`."
  > "8. **Observation.** ... `observed_at` = min(now, start − 1 min) − rng × 30 min. For started games the observation has `is_closing: true`."
- **[option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md#L482) (§8.4 Golden Day `2026-10-22`, line 482):**
  > "| `2026-10-22` | 7 completed | Settled won / lost / push, completed-game freemium bypass, My Picks settlement |"

#### Proof of Defect
1. On `2026-10-20`, `2026-10-21`, `2026-10-22` (golden day), and `2026-10-23`, **100% of the games in [nba_mock_data_2weeks.json](file:///mnt/devel/xosports/reqs/nba/tools/nba_mock_data_2weeks.json) are completed (`status: "final"`) and 100% of their picks have `bet_outcome` `0` or `1` (`pick_status = "settled"` from Step 6)**.
2. Because Step 7 defines eligible picks as *"status `open` and the game not started"*, **none** of the settled/void/awaiting_result picks are assigned a scenario in Step 7.
3. Step 8 then defines observation fields (`current_line`, `current_decimal_odds`, `current_american_odds`, `current_edge`, `edge_status`, `observed_at`) strictly per Step 7 scenario table, and adds at line 473: *"For started games the observation has `is_closing: true`."*
4. Two failures result:
   - Settled/started picks have no scenario from Step 7 to determine which observation row in Step 8 applies.
   - For any started/settled game assigned to `no_observation` (`observed_at: null`), setting `is_closing: true` violates [conf-schema-contracts.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/conf-schema-contracts.md#L644) §9.1 Invariant #4 (*"When `observed_at` is `null`: ... `is_closing` is `false`, and `edge_status` is `'unknown'`"*) and [`v4.schema.ts:242-255`](file:///mnt/devel/xosports/github/mobile-server/src/contracts/edge-picks/v4.schema.ts#L242-L255) (`CurrentBlockSchema` only exists when `observed_at` is non-null).

#### Required Fix
In `§8.3` Steps 7 & 8:
- Keep Step 7's 6-scenario coverage rule (including `cancelled`) for `open` pre-game picks.
- For non-`open` or already-started picks (`settled`, `void`, `awaiting_result`), assign one of the 5 non-cancelled observation scenarios (`live`, `narrowing`, `closed`, `moved`, `no_observation`) deterministically via `hash(pick_id) mod 90` (`live` 35, `narrowing` 20, `closed` 12, `moved` 13, `no_observation` 10).
- In Step 8, set `is_closing: gameStarted && observed_at !== null` (never `true` when `observed_at === null`).

---

### F-04 [HIGH]: Legacy Selection Mapping (`§5.2` & `Appendix A.5`) Fails on Real Format A Spreads, `player_yes` Props, and Null-`bet_line` H2H Picks in `script/db-seeds/`

#### Plan Quotations
- **[option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md#L779-L781) (Appendix A.5, lines 779–781):**
  > "| Format A H2H | `bet_type` `H2H`/`h2h`, `bet_line` `T1_h2h`/`T2_h2h`/`Draw` | `moneyline` | `home` / `away` / `draw` | `null` |"
  > "| Format A spread | `bet_type` `FAV_SPR<`, `FAV_SPR>`, `UD_SPR<`, `UD_SPR>`, `spread_fav`, `spread_dog`; slot from `bet_line` prefix; `position` is an unsigned magnitude | `spread` | from the slot | favourite ⇒ `−magnitude`, underdog ⇒ `+magnitude` (confirm the `</>` meaning, §12.3) |"
  > "| Format A player | `bet_type` `player_over`/`player_under`; `position` | `player_prop` | `over` or `under` | `Number(position)` |"

#### Proof Against `script/db-seeds/*.json` and `src/lib/top-picks/top-pick.ts`
1. **Format A Spread (`2002_FAV_SPR_us` and `31679_FAV_SPR<`):**
   - In [data-c-nfl-wltp-dev.json](file:///mnt/devel/xosports/github/mobile-server/script/db-seeds/data-c-nfl-wltp-dev.json) (`game_sk: 2002`, US), the pick is:
     ```json
     {
       "type": "FAV_SPR<",
       "code": "T1_-6.5_1.91",
       "id": "2002_FAV_SPR_us",
       "bookmaker": { "position": "-6.5", "bet_line": "T1_spread_under" }
     }
     ```
     `bookmaker.position` is `"-6.5"` — **already signed negative**, not an unsigned magnitude! Negating `Number(position)` without `Math.abs` flips `-6.5` to `+6.5`.
   - Furthermore, in [`generateBetTypeDescription`](file:///mnt/devel/xosports/github/mobile-server/src/lib/top-picks/top-pick.ts#L170-L243) (which builds the top-level `pickDescription`), the BFF does **not** use `bookmaker.bet_line` or `bookmaker.position` for Format A spreads—it parses `const [teamIdentifier, positionIdentifier] = pick.code.split("_")` (`top-pick.ts:170, 225, 241`). In [data-c-nba-wltp-dev-v2.json](file:///mnt/devel/xosports/github/mobile-server/script/db-seeds/data-c-nba-wltp-dev-v2.json) (`game_sk: 31679`), `code` is `"T1_9.5_1.95"` while `bet_line` is `"T2_spread_under"`. Reading `bet_line` in `legacy-selection.ts` makes `edge_pick` say `away -9.5` while `pickDescription` on the same card says `Home +9.5 PTS`.
2. **Format A Player Prop `player_yes` (`2002_player_TD_au` and `2002_player_TD_us` in [data-c-nfl-ps-dev.json](file:///mnt/devel/xosports/github/mobile-server/script/db-seeds/data-c-nfl-ps-dev.json)):**
   - In `nfl 2002`, Christian McCaffrey's touchdown prop has `type: "player_yes"`, `stat: "TD"`, `stat_name: "any touchdown"`, `bookmaker: { position: 0.5, bet_line: "yes" }`.
   - [`top-pick.ts:696-698, 725-727`](file:///mnt/devel/xosports/github/mobile-server/src/lib/top-picks/top-pick.ts#L696-L727) explicitly maps `player_yes` / `bet_line: "yes"` to `"Over"` (`"Christian McCaffrey Over 0.5 Any Touchdown"`), and preserves `bet_type: "player_yes"` (line 748).
   - Because `Appendix A.5` only matches `player_over`/`player_under`, `legacy-selection.ts` returns `null` for `2002_player_TD_au` and `2002_player_TD_us`.
3. **Format A H2H with `bet_line: null` (`37_H2H` in [data-c-nba-wltp-dev-v2.json](file:///mnt/devel/xosports/github/mobile-server/script/db-seeds/data-c-nba-wltp-dev-v2.json)):**
   - `37_H2H` has `code: "T2_null_2.15"` and `bookmaker.bet_line: null`. [`resolveBookmakerBetLine`](file:///mnt/devel/xosports/github/mobile-server/src/lib/top-picks/top-pick.ts#L115-L122) falls back to `pick.code.split("_")[0]` (`"T2"` $\to$ `"T2_h2h"`). `Appendix A.5` must use the same fallback.

#### Required Fix
Update `Appendix A.5` (`legacy-selection.ts`):
- **Format A spread:** Parse slot (`T1` $\to$ `home`, `T2` $\to$ `away`) and signed line from `pick.code.split("_")` when `pick.code` is present (and apply `-Math.abs(line)` for `FAV_SPR*`/`spread_fav` or `+Math.abs(line)` for `UD_SPR*`/`spread_dog` only when `code`'s line is unsigned and conflicts with `FAV_`); fall back to `bet_line` prefix + `±Math.abs(Number(position))` when `pick.code` is absent.
- **Format A player:** Accept `bet_type` in `["player_over", "player_under", "player_yes"]` (or `bet_line` in `["over", "under", "yes"]`), mapping `player_yes`/`yes` with numeric `position` (`0.5`) to `market: "player_prop"`, `selection: "over"`, `line: Number(position)`.
- **Format A H2H:** Use `resolveBookmakerBetLine(pick, bookmaker.bet_line)` so `bet_line: null` falls back to `pick.code` prefix (`T1_`/`T2_`).

---

### F-05 [HIGH]: `injectCancelledPicks` (`§5.3` & `Appendix A.3`) Fails to Null Top-Level Locked Fields on Pre-Game Cancelled Picks (`SEC-R-002` Leak)

#### Plan Quotations
- **[option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md#L262) (§5.3, line 262):**
  > "`injectCancelledPicks` runs inside the `applyIfFreemium` callback (`matches-top-predictions-v3.ts:303`), **after** `applyFreemiumToTopPicksResponse` so free-user `selectTopKUnlockedIds` ranking and `locks` are computed on listed picks only, and **before** `attachEdgePicks` so injected picks get their `edge_pick` redacted by the same function."
- **[option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md#L738-L750) (Appendix A.3, lines 738–750):**
  > "- `pickDescription`: built from the record (`{Player} Over {line} {Stat}`, `{Team} {±line}`, `Over/Under {line}`, `{Team}` for moneyline)
  > - `probability`: `record.probability`
  > - `bookmaker`: `{ name: record.bookmaker, bet_stake: record.stake_units, bet_price: record.entry_decimal_odds, bet_odds: { decimal_odds: record.entry_decimal_odds, american_odds: record.entry_american_odds } }`
  > - `market_odds`: `record.entry_decimal_odds`
  > - `locked`: free user and game not completed ⇒ `true`; otherwise absent
  > - `edge_pick`: `buildBlock(record, game, outcomeDoc, now)`"

#### Proof of Defect
1. For listed picks, [`applyFreemiumToTopPicksResponse`](file:///mnt/devel/xosports/github/mobile-server/src/freemium/apply/top-picks.ts#L132-L144) calls [`nullifyLockedPickFields`](file:///mnt/devel/xosports/github/mobile-server/src/freemium/resolve/locked-pick-response.ts#L206-L246) on every pick with `locked: true`, stripping `pickDescription`, `probability`, `bookmaker`, `market_odds`, and identity keys (`player_full_name`, `team_full_name`, `line`, `selection`).
2. Because `injectCancelledPicks` runs **after** `applyFreemiumToTopPicksResponse` and `attachEdgePicks` only redacts the nested `pick.edge_pick` block (`§5.5` lines 318–328), **the top-level fields of a locked injected cancelled pick (`pickDescription`, `probability`, `bookmaker`, `market_odds`, `player_full_name`) are sent completely unredacted over the wire to free users!**
3. Even worse: if all *listed* picks on that day are completed or within the free $K$ quota (`anyActiveLocked === false` in [`top-picks.ts:165`](file:///mnt/devel/xosports/github/mobile-server/src/freemium/apply/top-picks.ts#L165)), `body.locks` is `undefined`, or if `locks` is present, any field fallback in the client (or network inspection) sees the full unredacted top-level pick fields (`SEC-R-002`).

#### Required Fix
In `Appendix A.3` (`inject-cancelled.ts`), when an injected cancelled pick is created for a free user on an uncompleted game (`locked: true`), pass the constructed top-level item through [`nullifyLockedPickFields(item, getFreemiumConfig(), false)`](file:///mnt/devel/xosports/github/mobile-server/src/freemium/resolve/locked-pick-response.ts#L206) before `attachEdgePicks` runs.

---

### F-06 [HIGH]: Three App Integration Bugs in `EdgePicksCard.tsx` (`FE-3`, `FE-6`, and Missing Settled `outcome` Wiring)

#### Plan Quotations
- **[option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md#L108) (§2.2, line 108):**
  > "| `EdgePicksCard.tsx:218–224` (`XTP-125`) | Footer `outcome` is hardcoded `null`; Add button checks only `status === GAME_STATUS.COMPLETED` — not disabled when `edge_pick.status === "cancelled"`. |"
- **[option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md#L400-L403) (§7.1 `FE-3` & `FE-6`, lines 400, 403):**
  > "| `FE-3` | Read original and current odds from `edge_pick`: `app/screens/TopPicksScreen/bookmakerOdds.ts:56–89` | Original: `pick.edge_pick?.entry` (`odds_american` / `odds_decimal`) before `bookmaker?.bet_odds`. Current: when `pick.edge_pick?.current` is non-null **and** `pick.edge_pick.edge_state !== "moved"` (`R5`), format `{ american_odds: current.odds_american, decimal_odds: current.odds_decimal }` and show when different from original; when `edge_state === "moved"` or `current` is null, `currentOdds: null`. Bookmaker name: `pick.edge_pick?.bookmaker ?? bookmaker?.name` |"
  > "| `FE-6` | Cancelled state (`status === "cancelled"`, reason pill, disabled Add): `EdgePicksCard.tsx` | ... Chip and footer Add button enabled only when `edge_pick` is null or `edge_pick.status === "open"` |"
- **[option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md#L554) (§10.1 `V-FE-1`, line 554):**
  > "| `V-FE-1` | `EdgePicksCard.test.tsx`, `bookmakerOdds.test.ts` | Card renders: `live` (single price), `narrowing`/`closed` (struck original + current + pill), `moved` (entry price + moved pill, no cross-line current price), `cancelled` (reason pill + disabled Add), `settled` (`won`/`lost`/`push`), locked free card (blurred, no leak) |"

#### Proof Against `origin/feat/XTP-125-Edge-Picks-Redesign-Oct26` (`88de3461`)
1. **Bug 6a (`FE-3` never receives `pick.edge_pick`):**
   Look at `EdgePicksCard.tsx` lines 92–100 on `88de3461`:
   ```tsx
   const bookmakerOddsPick: BookmakerOddsPick = {
     bookmaker: pick.bookmaker,
     american_odds: pick.american_odds,
     decimal_odds: pick.decimal_odds,
     market_odds: pick.market_odds,
     current_odds: pick.current_odds,
     current_american_odds: pick.current_american_odds,
     current_decimal_odds: pick.current_decimal_odds,
   }
   ```
   `EdgePicksCard.tsx` passes `bookmakerOddsPick` (not `pick`) to `<BookmakerOddsChip pick={bookmakerOddsPick} />`. Because `bookmakerOddsPick` does not include `edge_pick: pick.edge_pick`, `pick.edge_pick` inside `bookmakerOddsView(pick, ...)` is **always `undefined`**! `FE-3` must also update `EdgePicksCard.tsx:92–100` (and `BookmakerOddsPick` in `bookmakerOdds.ts:15–23`) to pass `edge_pick: pick.edge_pick`.
2. **Bug 6b (Settled `outcome` is hardcoded `null` on `EdgePicksCard.tsx:281` and `"push"` is missing from `PredictionOutcome`):**
   `§2.2` line 108 diagnoses that `EdgePicksCard.tsx` hardcodes `outcome={null}` on `CardOutcomeFooterRow` (line 281), and `V-FE-1` (line 554) tests that `EdgePicksCard` renders `settled` (`won`/`lost`/`push`). However, **`§7.1` (`FE-1`..`FE-8`) has no work item to replace `outcome={null}` in `EdgePicksCard.tsx` or to add `"push"` to [`PredictionOutcome`](file:///mnt/devel/xosports/github/mobile-app/app/utils/predictionOutcome.ts#L1) and [`PredictionOutcomeIndicator.tsx`](file:///mnt/devel/xosports/github/mobile-app/app/components/common/PredictionOutcomeIndicator.tsx#L12-L22)!**
3. **Bug 6c (`FE-6` Add-to-Slip button enabled on `Postponed` games and completed fallback picks):**
   - Under `§3 D7` and `Appendix A.4` (line 763), a `Postponed` game (such as `40021717949` on `2026-10-25`) has top-level `status: "Postponed"` and `edge_pick.status: "open"`.
   - Under `FE-6` (*"Chip and footer Add button enabled only when `edge_pick` is null or `edge_pick.status === "open"`"*), both the odds chip and footer Add button remain **enabled** on a `Postponed` game, and on any completed/cancelled card where `edge_pick` is `null` (`BookmakerOddsChip` on `EdgePicksCard.tsx:172` currently only checks `disabled={isActiveSubscription === null}`, not game status!).

#### Required Fix
- In `FE-3`: Add `edge_pick?: EdgePickBlock | null` to `BookmakerOddsPick` and pass `edge_pick: pick.edge_pick` in `EdgePicksCard.tsx:92–100`.
- In `FE-6`: Define `const canAddPick = (status === GAME_STATUS.SCHEDULED || status === GAME_STATUS.UPCOMING || !status) && (pick.edge_pick == null || pick.edge_pick.status === "open")` and gate both `BookmakerOddsChip` and the footer Add button on `canAddPick`.
- Add `FE-9` to `§7.1`: Wire `outcome` in `EdgePicksCard.tsx:281` from `pick.edge_pick?.outcome` (`"won" -> "correct"`, `"lost" -> "incorrect"`, `"push" -> "push"`, `"void" -> "void"`, falling back to `isGameCompleted ? mapPickOutcome(pick.pickOutcome) : null`), and add `"push"` to [`predictionOutcome.ts`](file:///mnt/devel/xosports/github/mobile-app/app/utils/predictionOutcome.ts) and [`PredictionOutcomeIndicator.tsx`](file:///mnt/devel/xosports/github/mobile-app/app/components/common/PredictionOutcomeIndicator.tsx).

---

### F-07 [HIGH]: My Picks Settlement (`MP-5`) Targets the Wrong File for `v3`, Leaves Cancelled-Leg Slips Unsettled Forever, and Renders `outcome: 2` (Push/Void) as a Green Win Checkmark in `MyPicksItem.tsx` & `PickGroupCard.tsx`

#### Plan Quotations
- **[option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md#L112) (§2.2, line 112):**
  > "| `MyPicksItem.tsx` | Line 50 uses `resolveBookmaker(pick.bookmaker)` (already handles object or array). Line 101 renders `pick.outcome ? "tick" : "close_red"` — binary only, no push/void state, and live rows currently omit `outcome` (`§2.1`). |"
- **[option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md#L385) (§6 `MP-5`, line 385):**
  > "| `MP-5` | `src/lib/my-pick/resolve-my-picks-list.ts:303–314`, `src/lib/my-pick/snapshot.ts:332–373`, `src/functions/my-picks-v2.ts:177–218` | (a) On live rows (`resolve-my-picks-list.ts:303–314`), set `outcome: resolvedPick.outcome ?? resolvedPick.pickOutcome ?? null` (`hydratePickFromSnapshot` already sets it at `snapshot.ts:371`). (b) For `outcome === 2`, expose `outcome_label: "push"` when the market is a spread or total on a whole-number line, else `"void"` (contract §4.2, §7.6). (c) On a settled slip (`status: true`, `my-picks-v2.ts:195`), set `returnAmount: 0` when any leg has `outcome === 0`; for a `push`/`void` leg, treat its decimal odds factor as `1.0` in the slip return. (d) When `c-outcome` has no row, take the outcome from the producer record by pick id once a record source exists |"

#### Three Concrete Bugs
1. **Bug 7a (`MP-5(c)` edits `my-picks-v2.ts`, which `GET /my-picks-v2?api_version=v3` bypasses):**
   - Both `GET /my-picks-v2?api_version=v3` ([`my-picks-v2.ts:89-111`](file:///mnt/devel/xosports/github/mobile-server/src/functions/my-picks-v2.ts#L89-L111)) and `GET /v3/my-picks` ([`my-picks-v3.ts:66-86`](file:///mnt/devel/xosports/github/mobile-server/src/functions/my-picks-v3.ts#L66-L86)) call [`resolveMyPicksListForUser`](file:///mnt/devel/xosports/github/mobile-server/src/lib/my-pick/resolve-my-picks-list.ts#L317), which delegates slip total calculation to [`buildMyPickSlipResponse`](file:///mnt/devel/xosports/github/mobile-server/src/lib/my-pick/my-pick.ts#L162-L213) in `src/lib/my-pick/my-pick.ts`!
   - Also note two existing bugs in [`buildMyPickSlipResponse`](file:///mnt/devel/xosports/github/mobile-server/src/lib/my-pick/my-pick.ts#L183-L194):
     - Line 186 reads `item.decimal_odds ?? item.marketOdds`, which is `undefined` (`0`) on live rows without a snapshot (they carry `market_odds` and `bookmaker.bet_odds.decimal_odds`).
     - Line 190 reads `item.xoProbability` (which is never set on `v3` rows; they set `item.probability`), so `combinedProbability` is always `1`!
2. **Bug 7b (Slips with a cancelled game or pre-game cancelled leg never settle):**
   - In [`resolve-my-picks-list.ts:312`](file:///mnt/devel/xosports/github/mobile-server/src/lib/my-pick/resolve-my-picks-list.ts#L312), `item.status` is set to `schedule?.outcome?.game_status ?? ""`, and in [`my-pick.ts:196`](file:///mnt/devel/xosports/github/mobile-server/src/lib/my-pick/my-pick.ts#L196), slip `status` is `sortedActiveItems.every((item) => item.status === "Completed")`.
   - If a game in a slip is `"Cancelled"` (e.g., `40021717950` on `2026-10-25`, where `outcome.game_status === "Cancelled"`) or if a pick was cancelled/voided and hydrated from snapshot (`outcome === 2`), `item.status === "Completed"` is `false`, so the slip remains `status: false` (stuck in the "Current" tab forever instead of moving to "Completed").
   - A leg is settled when `item.status === "Completed" || item.status === "Cancelled" || item.status === "Canceled" || item.status === "Abandoned" || item.outcome === 0 || item.outcome === 1 || item.outcome === 2`.
3. **Bug 7c (`MyPicksItem.tsx:101` and `PickGroupCard.tsx:57` treat `outcome: 2` as Won):**
   - In [`MyPicksItem.tsx:101`](file:///mnt/devel/xosports/github/mobile-app/app/components/MyPicks/MyPicksItem.tsx#L101): `icon={pick.outcome ? "tick" : "close_red"}` and `color={pick.outcome ? colors.palette.green : colors.palette.red}`.
   - In [`PickGroupCard.tsx:56-60`](file:///mnt/devel/xosports/github/mobile-app/app/screens/MyPicksScreen/components/PickGroupCard.tsx#L56-L60): `const overallOutcome = isCompleted ? group.items?.some((p) => !p.outcome) ? false : true : undefined`.
   - Because `2` is truthy in JavaScript (`Boolean(2) === true`, `!2 === false`), a voided/pushed leg (`outcome: 2`) renders with a **green win checkmark (`tick`)** on `MyPicksItem`, and a completed slip whose legs are `outcome: 1` and `outcome: 2` (or a single-leg voided slip with `outcome: 2`) renders with a green Won badge in `PickGroupCard`!

#### Required Fix
1. In `MP-5`: Target [`src/lib/my-pick/my-pick.ts:162–213`](file:///mnt/devel/xosports/github/mobile-server/src/lib/my-pick/my-pick.ts#L162-L213) (`buildMyPickSlipResponse`) in addition to `my-picks-v2.ts:355–400`:
   - Read leg odds from `item.decimal_odds ?? item.market_odds ?? item.marketOdds ?? item.bookmaker?.bet_odds?.decimal_odds` (and use factor `1.0` when `item.outcome === 2`).
   - Read leg probability from `item.probability ?? item.xoProbability`.
   - Set slip `status = sortedActiveItems.every((item) => item.status === "Completed" || item.outcome !== null && item.outcome !== undefined)`.
   - When `status` is `true` and any leg has `item.outcome === 0`, set `returnAmount: 0`.
2. In `§7.1`: Add a frontend task (`FE-10`) to update [`MyPicksItem.tsx:98–105`](file:///mnt/devel/xosports/github/mobile-app/app/components/MyPicks/MyPicksItem.tsx#L98-L105) and [`PickGroupCard.tsx:56–60`](file:///mnt/devel/xosports/github/mobile-app/app/screens/MyPicksScreen/components/PickGroupCard.tsx#L56-L60) so `pick.outcome === 2` renders a neutral dash/minus (or `pick.outcome_label` `"Push"` / `"Void"`) instead of a green win tick, and `PickGroupCard` only marks `overallOutcome` as won when at least one leg has `outcome === 1` and no leg has `outcome === 0` (neutral/push when all legs have `outcome === 2`).

---

## 4. Medium & Low Severity Findings

### F-08 [MEDIUM]: `legacyLifecycle` (`Appendix A.4`) vs. `isMatchCompleted` Can Produce `status: "settled" | "void"` with `access.locked: true`, Failing `EdgePickBlockSchema`
- **Where:** `§4.3` (line 205), `§5.5` (lines 321–325), `Appendix A.4` (lines 759–762).
- **Issue:** In `Appendix A.4`, rows 2–5 map `pickOutcome` `0`, `1`, `2` to `status: "settled"` or `"void"` regardless of whether the game is completed. Meanwhile, [`applyFreemiumToTopPicksResponse`](file:///mnt/devel/xosports/github/mobile-server/src/freemium/apply/top-picks.ts#L123) uses [`isMatchCompleted(pick)`](file:///mnt/devel/xosports/github/mobile-server/src/freemium/apply/completed-bypass.ts#L52-L63), which only checks `pick.status` / `pick.outcome.game_status` (the **game** status). In [data-c-nba-ps-dev-v2.json](file:///mnt/devel/xosports/github/mobile-server/script/db-seeds/data-c-nba-ps-dev-v2.json) (`game_sk: 100077296`), pick `100077296|11007152|HR|player_under|au` has `bet_outcome: 0` while the game is still `"scheduled"`, and in production a player prop can be voided (`dnp`) or settled before the game's final whistle. That produces `edge_pick.status: "settled"` or `"void"` while `pick.locked === true` (`edge_pick.access.locked: true`), which fails the [`v4.schema.ts:442-449`](file:///mnt/devel/xosports/github/mobile-server/src/contracts/edge-picks/v4.schema.ts#L442-L449) refinement (*"settled, void, and completed-game picks are never locked"*).
- **Fix:** In `attachEdgePicks` (`§5.5`), treat `const isUnlockedTerminal = raw.status === "settled" || raw.status === "void"` as unlocked (`locked = false`, `pick.locked = false`), or in [`isMatchCompleted`](file:///mnt/devel/xosports/github/mobile-server/src/freemium/apply/completed-bypass.ts#L52-L63) / `legacyLifecycle` gate `settled` on game completion.

### F-09 [MEDIUM]: Whole-Number `player_prop` Push Excluded in `Appendix A.4` (Line 761) and `MP-5(b)` (Line 385)
- **Where:** `Appendix A.4` (lines 761–762) and `§6 MP-5(b)` (line 385).
- **Issue:** Both places state that `pickOutcome === 2` maps to `settled` / `push` only when *"the market is a spread or total on a whole-number line, else `void`"*. However, [conf-schema-contracts.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/conf-schema-contracts.md#L98-L100) §4.2 explicitly includes whole-number player props:
  > "Use `pick_status = "settled"` with `outcome = "push"` when the game and prop were validly played to completion and the final result landed **exactly on a whole-number entry `line`** (e.g., spread `-3.0` with a 3-point margin, total `220.0` with 220 combined points, or a whole-number player prop `line` with the player finishing on that exact stat total)."
- **Fix:** Allow `market === "player_prop"` with a whole-number `line` (`Number.isInteger(line)`) and `record?.status_reason == null` to map `pickOutcome === 2` to `settled` / `push`.

### F-10 [MEDIUM]: `edgePickTitle.ts` (`FE-2`) and `EdgeValueBadge.tsx` (`FE-4`) Edge Cases
- **Where:** `§7.1 FE-2` (line 399) and `FE-4` (line 401).
- **Issues:**
  1. In `edgePickTitle.ts` (`origin/feat/XTP-125-Edge-Picks-Redesign-Oct26`), `selectionTeam(pick)` (lines 76–85) only ignores `over` and `under` (`if (!selection || key === "over" || key === "under") return ""`). When `FE-2` feeds `pick.edge_pick?.selection` into `edgePickTitle.ts`:
     - For EPL `btts` (`market: "btts"`, `selection: "yes" | "no"`, e.g. `500000123_BTTS_NO_us` in [data-c-epl-wltp-dev.json](file:///mnt/devel/xosports/github/mobile-server/script/db-seeds/data-c-epl-wltp-dev.json)), `marketKind` returns `"other"` and `selectionTeam` returns `"no"`, producing title `"no"` instead of `"Both Teams To Score - No"` / `"BTTS - No"`.
     - For EPL 3-way moneyline draw (`market: "moneyline"`, `selection: "draw"`), `selectionTeam` returns lowercase `"draw"` instead of `"Draw"`.
     - On fallback cards (`edge_pick: null`) for canonical NBA game picks, top-level `pick.selection` is `"t1"` or `"t2"`, which `selectionTeam` does not map to `teamSideName(pick, 1 | 2)` (it only checks `"home" | "team_1" | "team1"`).
  2. In `EdgeValueBadge.tsx` (line 17), `toEdgePercent(value)` is `Math.abs(value) <= 1 ? value * 100 : value`. Because `edge_pick.entry.edge` is always a fraction (`EdgeFractionSchema` in `[-1, 10]`), any high-odds EV pick with `edge > 1.0` (i.e. $> 100\%$ EV) is not multiplied by `100` and displays `+1.2%` instead of `+120%`. Furthermore, when `edge_state === "closed"`, `EdgeValueBadge` uses the same `colors.palette.orange` downward arrow as `narrowing` even when `current.edge <= 0`.
- **Fix:**
  - In `FE-2` (`edgePickTitle.ts`): Map `"t1"` $\to$ side 1, `"t2"` $\to$ side 2, `"draw"` $\to$ `"Draw"`, and handle `market === "btts"` (`selection: "yes" | "no"` $\to$ title `"Both Teams To Score: Yes/No"`, subtitle `"BTTS"`).
  - In `FE-4` (`EdgeValueBadge.tsx`): Since `FE-4` passes `edge_pick.entry.edge` and `edge_pick.current.edge` (which are always fractions), multiply by `100` unconditionally (or pass a `unit="fraction"` prop), and style `edge_state === "closed"` with muted/neutral or red tone distinct from `narrowing`.

### F-11 [MEDIUM]: Injected Cancelled Picks Missing `prediction_type` (`Appendix A.3`) and Legacy Route Wiring (`§5.4`)
- **Where:** `Appendix A.3` (line 739) and `§5.4` (line 280).
- **Issues:**
  1. `Appendix A.3` (line 739) sets `type: record.market === "player_prop" ? "player" : "match"` on injected cancelled picks, but omits `prediction_type` (and for player props, omits `player_full_name: record.player_name`, `stat_type: record.stat`, `stat_name: record.stat_name`). In `mobile-app`, [`transformTopPickData`](file:///mnt/devel/xosports/github/mobile-app/app/services/topPredictions/transformer.ts#L32) sets `prediction_type: apiData?.prediction_type ?? apiData?.type` (which works), **but** for player props [`formatEdgePickLines`](file:///mnt/devel/xosports/github/mobile-app/app/screens/TopPicksScreen/edgePickTitle.ts#L48-L54) reads `pick.player_full_name ?? pick.player_name ?? pick.playerName` and `pick.stat ?? pick.stat_name`! Because `Appendix A.3` only sets `pickDescription` and does not copy `player_full_name: record.player_name`, `stat: record.stat`, `stat_name: record.stat_name`, or `team_full_name: record.team_name` onto the injected row, an unlocked injected player prop renders on `EdgePicksCard` **without the player's team jersey (`logoTeam`) and with degraded title/subtitle parsing**!
  2. `§5.4` (line 280) says to wire `buildBlock` into [`src/functions/matches-top-predictions.ts:171`](file:///mnt/devel/xosports/github/mobile-server/src/functions/matches-top-predictions.ts#L171) (the legacy non-`/v3/` route). That route does not run `applyFreemiumToTopPicksResponse`, `injectCancelledPicks`, or `attachEdgePicks`. Clarify in `§5.4` that on the legacy route `buildBlock` already sets `access: { locked: false, hidden: [] }` (since the legacy route is ungated) and does not inject cancelled picks.

### F-12 [LOW]: Minor File & Line Reference Corrections
- `§2.1` (line 81) & `§6 MP-6` (line 387): `src/functions/target-follow.ts:62` $\to$ [`src/functions/target-follow.ts:63`](file:///mnt/devel/xosports/github/mobile-server/src/functions/target-follow.ts#L63).
- `§2.2` (line 108): `EdgePicksCard.tsx:218–224` $\to$ `EdgePicksCard.tsx:278–286` (on `origin/feat/XTP-125-Edge-Picks-Redesign-Oct26` at `88de3461`).
- `§3 D5` (line 139): `src/lib/match/parsers/sections.ts` $\to$ [`src/lib/match/parsers/sections/index.ts`](file:///mnt/devel/xosports/github/mobile-server/src/lib/match/parsers/sections/index.ts).
- `§6 MP-5` (line 385): `src/functions/my-picks-v2.ts:177–218` (`my-picks-v2.ts:195`) $\to$ [`src/lib/my-pick/my-pick.ts:183–212`](file:///mnt/devel/xosports/github/mobile-server/src/lib/my-pick/my-pick.ts#L183-L212) (`my-pick.ts:196`) for `api_version=v3` and `my-picks-v2.ts:355–400` for legacy `v2`.

---

## 5. Prioritized Action Plan to Update `option-b-plan.md`

Before starting Phase 1 implementation, apply the following targeted revisions to [option-b-plan.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/option-b-plan.md):

1. **Close the `MP-1` + `MP-4` Freemium Bypass (`§3 D3`, `§6 MP-1`, `MP-4`, `§10.1 V-INT-3`) [CRITICAL]:**
   - Add `entitlementMiddleware` and `findUnavailableMyPickItemIds` (or subscriber/unlocked check) to `POST /my-picks-v2` (`MP-1`) before capturing `snapshot`, and do not return raw `snapshot` in the `POST` response.
   - In `MP-4` ([`src/freemium/apply/my-picks.ts:86–94`](file:///mnt/devel/xosports/github/mobile-server/src/freemium/apply/my-picks.ts#L86-L94)), allow a free user to view an item whose live peer is locked or absent **only** when the item carries a server-captured `snapshot` (`is_snapshot: true` or `item.snapshot != null`), and add a negative security test in `V-INT-3` verifying that a free user cannot unlock a locked pick via `POST /my-picks-v2`.
2. **Reconcile `R6` / `§8.3` Generator Math with `producer-record.schema.ts` §9.1 Invariants (`§4.4 R6`, `§8.3`, `§10.1 V-UNIT-5`) [HIGH]:**
   - Round `probability` and `entry_decimal_odds` with `round4`, default missing `bookmaker.name` and `stake_units <= 0` on legacy seed docs, skip null-id placeholders (`100076740`), key the store by `${region}:${pick_id}` (with fallback to `pick_id`), and either normalize `american_odds = decimalToAmerican(round4(d))` in the mock/seed inputs or pass `checkEntryAmericanFormula: false` for legacy/mock records.
   - In `§8.3` Steps 7 & 8, assign non-cancelled observation scenarios (`live`, `narrowing`, `closed`, `moved`, `no_observation`) to started/settled/void picks and set `is_closing: gameStarted && observed_at !== null`.
3. **Fix `legacy-selection.ts` (`§5.2`, `Appendix A.5`) for Format A Spreads, `player_yes`, and H2H Fallback [HIGH]:**
   - Parse Format A spread slot and signed line from `pick.code` first (matching [`top-pick.ts:170`](file:///mnt/devel/xosports/github/mobile-server/src/lib/top-picks/top-pick.ts#L170)) and use `Math.abs(Number(position))` when applying sign from `FAV_`/`UD_`.
   - Map Format A `player_yes` (`bet_line: "yes"`, `position: 0.5` on `2002_player_TD_au`/`us`) to `market: "player_prop"`, `selection: "over"`, `line: 0.5`.
   - Use [`resolveBookmakerBetLine`](file:///mnt/devel/xosports/github/mobile-server/src/lib/top-picks/top-pick.ts#L115-L122) for Format A H2H so `bet_line: null` (`37_H2H`) falls back to `pick.code`.
4. **Fix `injectCancelledPicks` Top-Level Redaction and Player Fields (`§5.3`, `Appendix A.3`) [HIGH]:**
   - Copy `prediction_type`, `player_full_name: record.player_name`, `stat: record.stat`, `stat_name: record.stat_name`, and `team_full_name: record.team_name` onto injected rows, and run [`nullifyLockedPickFields`](file:///mnt/devel/xosports/github/mobile-server/src/freemium/resolve/locked-pick-response.ts#L206) when `locked === true`.
5. **Complete the `mobile-app` Table (`§7.1`) and My Picks Settlement (`§6 MP-5`) [HIGH]:**
   - Pass `edge_pick: pick.edge_pick` into `bookmakerOddsPick` in `EdgePicksCard.tsx:92–100` (`FE-3`).
   - Disable Add-to-Slip on `Postponed`, `Completed`, `Cancelled`, `Abandoned`, and `In Progress` games even when `edge_pick` is `null` or `edge_pick.status === "open"` (`FE-6`).
   - Add `FE-9` to wire `outcome` on `EdgePicksCard.tsx:281` and support `"push"` in [`predictionOutcome.ts`](file:///mnt/devel/xosports/github/mobile-app/app/utils/predictionOutcome.ts) / [`PredictionOutcomeIndicator.tsx`](file:///mnt/devel/xosports/github/mobile-app/app/components/common/PredictionOutcomeIndicator.tsx).
   - Add `FE-10` to update [`MyPicksItem.tsx:101`](file:///mnt/devel/xosports/github/mobile-app/app/components/MyPicks/MyPicksItem.tsx#L101) and [`PickGroupCard.tsx:57`](file:///mnt/devel/xosports/github/mobile-app/app/screens/MyPicksScreen/components/PickGroupCard.tsx#L57) so `outcome === 2` (`push`/`void`) renders neutrally instead of as a green win tick, and target [`src/lib/my-pick/my-pick.ts:162–213`](file:///mnt/devel/xosports/github/mobile-server/src/lib/my-pick/my-pick.ts#L162-L213) (`buildMyPickSlipResponse`) in `MP-5(c)`.

