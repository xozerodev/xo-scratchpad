# Edge Picks v4, option B: implementation plan

Oct 20, 2026 · @Tze Liang

**Decision:** deliver the Edge Picks redesign through `api_version` v7 on the existing `GET /v3/matches/:date/top-predictions` route (option B). The separate `/v4/edge-picks` route (option A) is a later cleanup. Comparison and trade-offs: [delivery-options.md](delivery-options.md).

**Who this is for:** the BFF (mobile-server) and app (mobile-app) implementers, data engineering for the parts it owns, and QA. Each work item has an id, the files it touches, what done looks like, and how it is tested. Follow the design rules in §3 exactly; they are what keeps the old app safe.

**Code checked:** mobile-server `feat/edge-picks` at `35f6f44` (develop `fffcc9e` plus the v4 contract work), mobile-app `main` at `137f2f61`, `origin/feat/XTP-125-Edge-Picks-Redesign-Oct26` at `88de3461`, store build tag `main/1.1.66`, dev Cosmos layout from `docs/nba-2026-bff-handover.md` and `infra/envs/*/app_settings.tf`, dev NBA data from `reqs/nba/tools/`. The plan was reviewed adversarially against that code; corrections are folded in. Line numbers drift: search for the named function if a line has moved.

---

## Contents

1. Outcome and phases
2. Assessment of option B
3. Design rules
4. The v7 contract: what the app receives
5. BFF design
6. My Picks and slip fixes
7. App design
8. Mock data
9. Validation
10. Work breakdown
11. Rollout and rollback
12. Decisions, risks and open items
13. Appendices: mappings, examples, references

---

## 1. Outcome and phases

When this plan is done:

- The new app build sends `api_version=v7`. On the Edge Picks screen every pick carries an `edge_pick` block, so the app draws the redesign card: entry and current price, edge, edge state, "Edge holds above", cancelled with a reason, push and void results.
- Store builds (v5, v6) receive byte-for-byte what they receive today.
- Before any league has v4 data, every block is `era: "legacy"`, built from today's documents, and the limited card shows real data in every environment.
- In dev, a mock source turns the dev pick documents into realistic v4 blocks, so the app team builds and tests every state now, on the games and pick ids the dev BFF already serves, without waiting for the bet engine.
- Slips stay correct when a pick is cancelled, withdrawn or drops out of the list.

| Phase | What ships | Unblocks | Depends on |
| --- | --- | --- | --- |
| **P1. v7 blocks, mock in dev** | v7 branch on the route; legacy blocks everywhere; v4 blocks from the mock source in dev; offline samples | App team builds the redesign against real shapes and ids | Nothing outside the BFF |
| **P2. Slip safety** | Snapshot on save, store-build-safe My Picks rows, results, follow-topic and region fixes | Every build; prerequisite for P4 | Nothing outside the BFF (parallel with P1) |
| **P3. App integration** | The app reads `edge_pick`, sends v7, slip and My Picks changes | Release of the new build | Samples from P1 (end of week 1), dev deploy |
| **P4. Live v4 data, NBA first** | Producer-record source from the KDD-001 container, cancelled-pick injection | Real v4 cards | Data engineering: KDD-001 container, KDD-002 Stage A for NBA |
| **P5. Follow-ups** | Extra Format A game picks, product decisions applied | Fuller cards for NFL, MLB, WNBA, EPL | P2, P4 |
| **Later: option A** | `/v4/edge-picks` assembled from the same blocks | Retiring the v3 shape | Old builds retired |

---

## 2. Assessment of option B

### 2.1 What holds, verified in code

| Claim | Evidence |
| --- | --- |
| Store builds never send v7; each build pins its version in the binary | App: `DEFAULT_API_VERSION` (`app/hooks/useAppConfig.ts:42`) is used directly (`AppConfigContext.tsx:48`); tag `main/1.1.66` pins `v5`, main pins `v6` |
| Raising to v7 changes nothing on the list routes without v7 logic | BFF exact version checks: `=== "v1"` (`matches.ts:146`, `match.ts:110`, `my-picks-v2.ts:212`), `!== "v1"` (`matches-top-predictions.ts:171`), `=== "v3"` (`my-picks-v2.ts:89`) and `getRequestApiVersion(request, "") === "v3"` in `entitlementWhenApiVersionV3` (`lib/middleware/entitlement-middleware.ts:171`, used by My Picks). The last two matter only if My Picks is ever sent v7 (rule R5, MP-6). All other gates are `>=` (EPL ≥4, NFL ≥5, sections ≥4, split locks ≥5, staged seasons ≥6) |
| v7 releases staged seasons on the route | `apiVersionMiddleware("v3")` reads `api_version`; `RELEASE_API_VERSION_MAJOR = 6` (`canonical/gate.ts:78`) |
| The free-user response cache cannot mix v6 and v7 bodies | Key includes the normalised `apiVersion` (`freemium/cache/response-cache-keys.ts`) |
| `id` and `locked` survive the free-user step | `id` is in no strip list; locked picks keep `locked: true`, unlocked active picks get `locked: false`, completed and subscriber picks have no `locked` (`freemium/apply/top-picks.ts:116-162`) |
| Slips use the list's pick id unchanged | App sets `id = predictionId = pick.id` (`TopPickCard.tsx:141-154`, XTP-125 `EdgePicksCard.tsx:149-162`); My Picks matches with `String()` equality (`resolve-my-picks-list.ts:227-233`) |
| Both builds read My Picks the same way | App hard-codes `api_version=v3` for My Picks (`myPicks.service.ts:25`) in every build |
| B1 code is reusable for the block | Formulas (`contracts/edge-picks/derive.ts`), field groups and leak rule (`lib/edge-picks/access.ts`), sub-schemas (`contracts/edge-picks/v4.schema.ts`) |

### 2.2 What breaks unless this plan handles it

| # | Problem | Handled in |
| --- | --- | --- |
| 1 | The v3 free-user strip nulls top-level keys (and one level inside `match_prediction`/`player_prediction`) only (`freemium/registry/strip-helpers.ts`); a nested block would leak on locked picks | R1–R3, BE-6 |
| 2 | The legacy strip always nulls `bookmaker` on locked picks (`resolve/locked-pick-response.ts:202-217`), so a block that keeps its odds source would reveal more than today | §4.3 (sources null when locked), BE-6, V-SEC-1 |
| 3 | The pick funnel drops `cancelled` picks (`common.ts:252`, `canonical/picks.ts:529,757`), so the redesign's cancelled card can't come from documents | BE-11 (P4); mock scenario in P1 |
| 4 | `POST /my-picks-v2` stores no snapshot and checks nothing (`my-picks-create-v2.ts:24-29`); an item whose pick leaves the list becomes a placeholder with `decimal_odds 0`, which makes the whole slip's odds and return 0 (`resolve-my-picks-list.ts:277-296`, `my-pick.ts:183-206`) | MP-1, MP-2 |
| 4a | `POST /my-picks-v2` has no entitlement check, and locked picks keep their `id` on the list. If the save captured a snapshot and returned it, or My Picks showed locked items to their owner, a free user could post any locked id and read the pick | MP-1, MP-4, V-SEC-3 |
| 5 | Store build 1.1.66 multiplies `item.bookmaker.bet_odds.decimal_odds` on the device (`PickGroupCard.tsx:60-72` at `main/1.1.66`); snapshot rows have no `bookmaker`, and live NBA 2026 rows carry an array `bookmaker`, so it shows NaN | MP-2 |
| 6 | My Picks reads `item.outcome` (`MyPicksItem.tsx:101`), but live rows carry only `pickOutcome`; only snapshot and placeholder rows set `outcome` (`snapshot.ts:371`). Completed live legs therefore render as a cross. Void and push share code 2 and render as a tick on snapshot rows | MP-5, FE-7 |
| 7 | Free and lapsed users lose a saved item whose pick is missing (`freemium/apply/my-picks.ts:65`) or listed but locked (`:86-94`) | MP-4 |
| 8 | My Picks sent anything but exactly `v3` skips entitlement and free-user filtering (`my-picks-v2.ts:89`, `entitlement-middleware.ts:171`) | MP-6, R5 |
| 9 | Format A leagues hold one game pick per region (`game_prediction.top_picks[region]`) | P5 (BE-14) |
| 10 | Pick-id follow topics keep `\|` on device re-registration (`queue-fcm-device.ts:40,54`) | MP-7 |
| 11 | My Picks defaults the region to `us` (`resolve-my-picks-list.ts:89`); the list uses the token region | MP-8 |

### 2.3 Costs accepted with option B

- The new app stays on the untyped v3 pick shape until option A.
- The app keeps its title heuristics (`edgePickTitle.ts`); a display label is not part of the block (decision of Oct 20).
- v4-era picks reach the route only through KDD-002's derived legacy documents. A league moves to v4 cards only after its Stage A is live.
- Legacy top-level fields don't follow the v4 leak rule (a locked pick can show probability and odds while hiding edge). The block follows it; the top-level fields keep today's behaviour. Product may tighten the legacy flags separately.

---

## 3. Design rules

These are requirements. A change that breaks one needs a decision recorded in this document first.

| Rule | Requirement | Why |
| --- | --- | --- |
| **R1** | Every redesign field lives inside `edge_pick` (and the response-level `edge_pick_meta`). No new top-level key on a listed pick | The v3 free-user strip only knows top-level keys |
| **R2** | Build each block **before** the free-user step, from the unredacted pick. Attach it **after** the free-user step, redacted for that pick | Locked picks have already lost odds and identity fields after the free-user step |
| **R3** | A block's lock comes from the pick's legacy result (`locked === true`), never from a second ranking | Two rankings disagree (per league over the day vs per sport; completed vs void rules) |
| **R4** | At v6 and below the response is byte-identical to today. At v7, removing every `edge_pick`, `edge_pick_meta` and injected item gives the v6 body, with `count` recomputed (test V-INV-1, conditions in §9.1) | Coexistence guarantee |
| **R5** | My Picks stays on `api_version=v3` in the app; v7 is for the list, `/games` and `/game` only | `my-picks-v2.ts:89`, `entitlement-middleware.ts:171` |
| **R6** | The slip uses the entry price, never the current price. A legacy block's entry price is the document's price, decimal **and** American as written | The saved price must match what the card, slip and My Picks show |
| **R7** | Ids are opaque and unchanged; the block never renames or re-keys a pick | Slips, follows and results key on the id |
| **R8** | A block that fails its schema becomes `edge_pick: null` and is reported; it never fails the response | One bad document must not take the screen down |
| **R9** | The mock source and mock query parameters can't run in production | Guarded by environment (§5.3) and by test V-SEC-2 |
| **R10** | The mock source is deterministic: the same documents, `now` (to the 5-minute bucket) and seed give the same blocks; `picked_at` never changes between requests | Golden files, reproducible bugs, the contract's "never changes" |

---

## 4. The v7 contract: what the app receives

### 4.1 Request

Unchanged route and parameters; only the version changes:

```http
GET /v3/matches/2026-10-25/top-predictions?offset=11&api_version=v7
Authorization: Bearer <Firebase ID token>
```

Mock parameters, honoured only when `EDGE_PICK_MOCK_PARAMS=on` (never in production, R9). Without that setting they are ignored, and they don't affect caching.

| Parameter | Values | Effect |
| --- | --- | --- |
| `edge_pick_scenario` | `mixed` (default), `live`, `narrowing`, `closed`, `line_moved`, `suspended`, `no_observation`, `cancelled`, `settled_push`, `void` | Forces every eligible pick into one scenario (§8.4) |
| `edge_pick_era` | `legacy`, `v4` | Forces every block to one era (`v4` only for picks the mock source can map) |
| `edge_pick_seed` | integer | Reshuffles the `mixed` assignment |
| `edge_pick_now` | ISO time | Evaluates lifecycle, scenarios and drift as of that time |

When honoured, a request carrying any of these bypasses the free-user response cache.

### 4.2 Response

Today's body, plus at v7:

```json
{
  "top_picks": [ { "...today's pick fields...": "...", "edge_pick": { } } ],
  "offset": 11,
  "count": 23,
  "locks": { "...today's locks, free users only...": true },
  "edge_pick_meta": { "version": "1.0.0", "source": "mock" }
}
```

| Field | Type | Meaning |
| --- | --- | --- |
| `edge_pick_meta.version` | string, semver | Version of the block contract (§4.3). Minor for additive changes |
| `edge_pick_meta.source` | `off`, `legacy`, `mock`, `live` | `off`: blocks disabled, every `edge_pick` null. `legacy`: blocks on, no v4 record source, every block `era: legacy`. `mock`: v4 blocks from the mock source. `live`: v4 blocks from the KDD-001 container |
| `top_picks[].edge_pick` | object or null | The block. Null when the source is `off`, or the block failed validation (R8). The app then draws today's card |

`edge_pick_meta` is also present on an empty day (the early return in the route). `count` counts every item in `top_picks`, injected picks included (P4).

### 4.3 The `edge_pick` block

Every field is always present; null only as stated.

| Field | Type | Null when | Meaning |
| --- | --- | --- | --- |
| `era` | `legacy`, `v4` | never | `v4`: from a producer record; full card. `legacy`: from today's documents; limited card. The app treats an unknown value as `legacy` |
| `status` | `open`, `awaiting_result`, `cancelled`, `settled`, `void` | never | Pick lifecycle (snapshot contract "Pick lifecycle") |
| `status_reason` | `{code, message}` | status is not cancelled or void, or no reason is known | `code`: `probability_moved`, `market_moved`, `lineup_change`, `withdrawn`, `game_void`; `message` is display-ready copy from the BFF |
| `result` | `won`, `lost`, `push`, `void` | status is not settled or void | Grade on the entry price |
| `picked_at` | ISO time | era is `legacy` | First publish. Never changes |
| `selection` | `{market, side, line, stat_code}` | selection hidden, or (legacy) the pick can't be mapped (Appendix A.5) | `market`: `moneyline`, `spread`, `total`, `draw`, `btts`, `player_prop`; `side`: `home`, `away`, `over`, `under`, `yes`, `no`, `draw`; `line` per the line rule; `stat_code` for player props, else null |
| `probability` | number, 0–1 exclusive | probability hidden | Model probability at entry |
| `entry.odds` | `{decimal, american}` | odds hidden | Entry price. v4: first publish. Legacy: the document's price as written (R6) |
| `entry.line` | number | the market has no line, the line is unknown (legacy), or selection hidden | Entry line, signed from the backed side's view for spreads |
| `entry.edge` | number (fraction) | edge hidden | `probability × entry.decimal − 1` (Provisional display basis) |
| `entry.stake_units` | number ≥ 0 | stake hidden | Recommended stake |
| `entry.source` | `{kind, id, name}` | the pick is locked, or a legacy document names no bookmaker | `kind`: `bookmaker` or `market_average`. AU always `market_average`, `"Avg. Odds"`. Null on locked picks because the legacy strip already hides the bookmaker |
| `current` | object | era is `legacy`, or no observation yet | The market as last observed |
| `current.odds` | Odds | odds hidden, or price pulled | |
| `current.line` | number | no line, selection hidden, or price pulled | |
| `current.edge` | number | edge hidden, price pulled, or line moved | |
| `current.source` | OddsSource | the pick is locked, or not known | |
| `current.observed_at` | ISO time | never inside `current` | When the price was observed at the book |
| `current.is_closing` | boolean | never inside `current` | Last observation before the start |
| `edge_holds_above` | Odds | era is `legacy`, probability or odds hidden, or no break-even exists | Break-even price b |
| `edge_state` | `live`, `narrowing`, `closed`, `suspended`, `unknown` | never | `unknown` for legacy, no observation, or edge hidden |
| `overlay_key` | string | always null in this plan | Reserved for realtime overlays |
| `action` | null | always | Reserved |
| `access.locked` | boolean | never | Mirrors the pick's legacy `locked` flag (R3) |
| `access.hidden` | array of `selection`, `odds`, `probability`, `stake`, `edge` (contract order) | never; `[]` when unlocked | Groups nulled in this block |

**Free-user groups inside the block:**

| Group | Nulls | When hidden on a locked pick |
| --- | --- | --- |
| `selection` | `selection`, `entry.line`, `current.line` | Always (the legacy strip already nulls line and identity, `LOCKED_PICK_IDENTITY_KEYS`) |
| `odds` | `entry.odds`, `current.odds`, `edge_holds_above` | `show_market_odds` is not `true` |
| `probability` | `probability`, `edge_holds_above` | `show_xo_probability` is not `true` |
| `stake` | `entry.stake_units` | `show_stake` is not `true` |
| `edge` | `entry.edge`, `current.edge`; `edge_state` → `unknown` | `show_xo_edge` is not `true` |

Also on every locked pick: `entry.source` and `current.source` are null. Leak rule: hide none of probability, odds and edge, or at least two (`withLeakRule`). A sport disabled for free users hides every group.

**Rules the block schema enforces** (BE-2):

- Status and result: settled ⇒ won, lost or push; void ⇒ void; otherwise null. `status_reason` only on cancelled or void.
- Era: legacy ⇒ `picked_at`, `current`, `edge_holds_above` null, `edge_state` unknown, status never cancelled, reason only `game_void`; `selection` set when the legacy pick maps (Appendix A.5), else null. v4 ⇒ `picked_at` and (unless hidden) `selection` set.
- Groups: each hidden group's fields null; each visible group's values set, except legacy `selection`, `entry.line`, `entry.source` and `entry.stake_units`, which may be null (unmappable pick, no line, no named bookmaker, no stake in the document). `access.locked` false ⇒ `hidden` empty. Unlike the snapshot contract, the block schema has **no** "completed picks are never locked" rule: a settled or void pick may be locked when the legacy lock says so (the legacy bypass goes by game status, so a pick graded before its game ends, or a postponed game's pick, can stay locked; R3). Don't reuse `pickRuleViolations` from `v4.schema.ts` for blocks.
- Line rule (v4 era, selection visible): moneyline, draw, btts and yes/no props have no line; spread needs a line; over/under needs a positive line.
- Observation: no `current` ⇒ `edge_state` unknown; `suspended` ⇒ `current` with odds, line and edge null.

Examples are in Appendix B.

---

## 5. BFF design

### 5.1 Flow at v7

```
GET /v3/matches/:date/top-predictions?api_version=v7
  │ (unchanged) schedule → documents → getAllAvailableTopPicksForGame → topPicks[] → originBody
  │
  ├─ NEW ① if major ≥ 7 and blocks are on:
  │      records = recordSource.load({ region, picks: topPicks, games, docsByGame, now, mock })   (BE-4, MK-1, BE-10)
  │      blocks  = Map<pickId, UnredactedBlock>  via buildBlock(pick, records.get(pick.id), ctx)   (BE-5)
  │
  │ (unchanged) body = applyIfFreemium(originBody, applyFreemiumToTopPredictionsBody)
  │
  ├─ NEW ② (P4) inject cancelled v4 picks not in the list: append the stripped top-level      (BE-11)
  │        picks to body.top_picks, add their unredacted blocks to `blocks`,
  │        then body.count = body.top_picks.length
  │   NEW ③ attachEdgePicks(body, blocks, freemiumCtx): redact per pick, validate (listed and   (BE-6)
  │        injected picks alike, in one place)
  │   NEW ④ body.edge_pick_meta = { version, source }   (also on the empty-day early return)
  │
  │ (unchanged) withFreemiumResponseCache stores the body; key includes apiVersion
  │ (unchanged) sortGameListItems
  ▼
response
```

Everything new runs inside `loadOrigin` in `src/functions/matches-top-predictions-v3.ts`, so free-user bodies are cached with their blocks under the v7 key only. The cache refuses bodies over 512 KiB (`freemium/cache/ttl-cache.ts:10`); BE-8 measures v7 body sizes on the largest dev day and reports if any exceed it.

### 5.2 New and changed files

| File | Change |
| --- | --- |
| `src/contracts/edge-picks/edge-pick-block.schema.ts` | NEW. zod `EdgePickBlockSchema` from the v4 sub-schemas (`OddsSchema`, `OddsSourceSchema`, `CurrentSchema` with nullable `source`, the enums), plus `blockRuleViolations()` for §4.3 |
| `src/contracts/edge-picks/producer-record.schema.ts` | NEW. zod schema of the producer pick record 4.0.0 (37 fields, `conf-schema-contracts.md` §6, §9) and the §9.1 invariants as a separate `recordInvariantViolations(record, { checkIdFormula, checkEntryAmericanFormula })` (both default `true`). The contract's §9 JSON Schema puts the canonical `pick_id` **pattern** on the field itself (`conf-schema-contracts.md:460-464`); in the zod schema make `pick_id` a plain string (1–255 characters) and enforce the pattern inside the id-formula check, so `checkIdFormula: false` really exempts it. In the dev NBA data 336 of 1,070 ids fail the pattern (300 `player_milestone` ids, 36 `alternate`-variant ids), and every Format A id fails it |
| `src/lib/edge-picks/v7/config.ts` | NEW. Settings of §5.3; `blocksEnabledFor(apiVersionMajor)`, `recordSourceKind()`, `isV4League(league)` (env list plus Redis kill switch), `mockParams(request)` |
| `src/lib/edge-picks/v7/record-source.ts` | NEW. `PickRecordSource` interface and factory |
| `src/lib/edge-picks/v7/mock/generate.ts` | NEW. The generator of §8.3, shared by the mock source, the sample exporter and the seeding script |
| `src/lib/edge-picks/v7/mock/mock-record-source.ts` | NEW. Mock `PickRecordSource` that calls the generator |
| `src/lib/edge-picks/v7/cosmos-record-source.ts` | NEW (P4). Reads the KDD-001 container through the shared cache |
| `src/lib/edge-picks/v7/legacy-selection.ts` | NEW. Legacy v3 pick → `{market, side, line, stat_code}` (Appendix A.5). Reimplement the slot logic here: `classifyGamePick` and `edgePickSlot` in `canonical/picks.ts` are not exported, and `edgePickSlot` reads `code` and `type`, which the route's picks no longer carry in usable form |
| `src/lib/edge-picks/v7/lifecycle.ts` | NEW. One `legacyLifecycle(pick, game, now)` (Appendix A.4) used by both the block builder and the generator |
| `src/lib/edge-picks/v7/build-block.ts` | NEW. `buildLegacyBlock(pick, ctx)`, `buildV4Block(record, pick, ctx)` |
| `src/lib/edge-picks/v7/attach.ts` | NEW. `attachEdgePicks(body, blocks, freemiumCtx)`: lock mapping, redaction, validation, reporting |
| `src/lib/edge-picks/v7/inject-cancelled.ts` | NEW (P4). Record → top-level pick for cancelled v4 picks (Appendix A.3) |
| `src/lib/edge-picks/v7/report.ts` | NEW. `reportEdgePickProblem(kind, league, pickId, reason)` with 30-minute de-duplication, following `canonical/alerts.ts` |
| `src/lib/edge-picks/access.ts` | ADD `redactBlock(block, hidden, locked)` beside `redactEdgePick`; reuse `withLeakRule`, `hiddenGroupsFromGlobals` |
| `src/freemium/resolve/locked-pick-response.ts` | EXPORT `parseOddsNumber` (currently private) |
| `src/freemium/apply/top-picks.ts` | ADD an exported `stripAsLockedTopPick(pick, league, config)` that applies the same locked policy (`globalsPickPolicy` or `disabledPickPolicy`, both private today) and `redactLockedPickGameToTeamInfo`, for injected picks (P4) |
| `src/functions/matches-top-predictions-v3.ts` | The insertion points of §5.1; `edge_pick_meta` on the empty-day return; cache bypass only for honoured mock parameters |
| `script/edge-picks/export-v7-samples.ts` | NEW. Offline samples and the block JSON Schema for the app (§8.6) |
| `script/edge-picks/snapshot-cosmos-day.ts` | NEW. Read-only export of a day's content documents into a fixture (§8.2) |
| `script/edge-picks/seed-mock-records.ts` | NEW (P4 staging). Writes generated records to an isolated container (§8.7) |
| `infra/envs/dev/app_settings.tf` | `EDGE_PICK_BLOCKS = "on"`, `EDGE_PICK_SOURCE = "mock"`, `EDGE_PICK_MOCK_PARAMS = "on"`. tst and production: `EDGE_PICK_BLOCKS = "on"`, `EDGE_PICK_SOURCE = "none"` |

### 5.3 Configuration

| Setting | Values | Default | Meaning |
| --- | --- | --- | --- |
| `EDGE_PICK_BLOCKS` | `on`, `off` | `off` | Master switch. `off`: `edge_pick_meta.source` is `off` and every `edge_pick` is null at v7 |
| `EDGE_PICK_SOURCE` | `none`, `mock`, `cosmos` | `none` | Where v4 records come from. `none` ⇒ meta `legacy` (legacy blocks only); `mock` ⇒ meta `mock`; `cosmos` ⇒ meta `live` |
| `EDGE_PICKS_V4_LEAGUES` | comma list (`nba,nfl`) | empty | Leagues whose records may produce `era: v4` with `cosmos`. The mock source ignores it: every league can be v4 in mock unless `edge_pick_era=legacy` |
| Redis `edge-picks:v4-off:<league>` | `1` | absent | Kill switch, read in `isV4League`: forces `era: legacy` for that league. Fails open to the env value (pattern: `lib/mvm-switch.ts`). Takes effect on the next uncached request; free users may see the cached body for up to 60 s |
| `EDGE_PICK_MOCK_PARAMS` | `on` | absent | Honours the §4.1 mock parameters |
| `EDGE_PICK_MOCK_DRIFT` | `on` | absent | Mock current prices drift per 5-minute bucket (§8.3 step 9) |
| `EDGE_PICK_RECORDS_CONTAINER` | container name | — | KDD-001 container (P4) |

The minimum version is a constant, `EDGE_PICK_MIN_API_MAJOR = 7`, not a setting (a lower value would break R4).

**Production guard:** at startup, if the environment is production (use the BFF's existing environment-name setting; confirm which one in BE-1) and either `EDGE_PICK_SOURCE=mock` or `EDGE_PICK_MOCK_PARAMS` is set, log an error and behave as `EDGE_PICK_SOURCE=none` with mock parameters ignored.

The existing `EDGE_PICKS_SOURCE` and `EDGE_PICKS_LIVE_SPORTS` belong to the parked `/v4/edge-picks` route; leave them unset.

### 5.4 Building blocks (BE-5)

**Legacy era**, from the unredacted v3 pick (after the funnel and the route's mapping, before the free-user step). Mapping: Appendix A.1.

1. `probability = pick.probability ?? pick.xoProbability ?? pick.xo_probability`; must be in (0, 1).
2. `entry.odds`: decimal from `pick.decimal_odds` (else `bookmaker.bet_odds.decimal_odds`, else `bet_price`), rounded to 4 places; American from `pick.american_odds` (else `bookmaker.bet_odds.american_odds`) **as written**; derive only the missing one with the conversion rule (R6). Use the exported `parseOddsNumber` for numeric strings.
3. `entry.edge = computeEdge(probability, entry.odds.decimal)`.
4. `entry.stake_units = pick.stake` (the route already resolves it from `bet_stake`).
5. `selection` and `entry.line`: from `legacy-selection.ts` (Appendix A.5), which handles the per-family sign; `entry.line = selection.line`. Unmappable ⇒ both null (report `unmappable_legacy`). KDD-003 always sets the selection on legacy picks; populating it here also gives the app `selection.market` for moneyline exclusivity before any league has v4 records.
6. `entry.source`: AU ⇒ `{market_average, null, "Avg. Odds"}`; else `{bookmaker, bookmaker_id ?? slug(name), displayName(name)}`; null when the document names no bookmaker. `resolveBookmaker` handles object and array `bookmaker`.
7. `status`, `result`, `status_reason`: `legacyLifecycle` (Appendix A.4).
8. Everything else per the legacy null rules.

A legacy block that can't satisfy the schema (no probability, no price, no stake) becomes null and is reported (R8).

**v4 era**, when all hold: a record exists for `pick.id` in the user's region; the source is `mock`, or the source is `cosmos` and `isV4League(league)`; `edge_pick_era` is not `legacy`; the record's `pick_status` is not `withdrawn`. Mapping: Appendix A.2.

1. Selection, probability, entry, `picked_at` from the record's frozen fields.
2. `current` from `current_*`, `observed_at`, `is_closing` (null when `observed_at` is null).
3. `entry.edge`, `current.edge`, `edge_holds_above`, `edge_state` from `derive.ts` using the record's `edge_basis` and `edge_threshold`. If the record's `edge_status` disagrees with the derived `edge_state`, serve the derived value and report `edge_state_mismatch`.
4. `status`, `result` via `mapProducerStatus`; `status_reason` code from the record, message from `STATUS_REASON_MESSAGES`.

**Consistency checks between a listed pick and its record** (report `record_mismatch`, then fall back to a legacy block): record `game_sk` ≠ `pick.game_sk`; record region ≠ user region; record entry decimal differs from the document's decimal by more than 0.0001 (Stage A must copy entry values exactly). The mock source writes the document's price into the record, so mock never trips this except through the mock-only probability adjustment (§8.3 step 4), which changes probability, not price.

### 5.5 Attaching and redacting (BE-6)

```ts
// attach.ts (pseudocode)
// The block has no projection, so its groups are the v4 groups minus "projection".
const ALL_BLOCK_GROUPS = ["selection", "odds", "probability", "stake", "edge"] as const;

export function attachEdgePicks(body, blocks, ctx /* getFreemiumContext() */) {
  // ids whose copies differ in content (identical copies are allowed and share one block)
  const conflicting = idsWithDifferingCopies(body.top_picks);
  for (const pick of body.top_picks) {
    const raw = blocks.get(String(pick.id));
    if (!raw || conflicting.has(String(pick.id))) {
      if (raw) report("duplicate_id", pick);
      pick.edge_pick = null;
      continue;
    }
    const locked = !ctx.isSubscriber && pick.locked === true;
    const hidden = locked ? lockedGroups(pick, ctx) : [];
    const block = redactBlock(raw, hidden, locked);       // nulls per §4.3; sources null when locked
    block.access = { locked, hidden };
    const ok = EdgePickBlockSchema.safeParse(block);
    pick.edge_pick = ok.success ? ok.data : (report("block_invalid", pick, ok.error), null);
  }
}

function lockedGroups(pick, ctx) {
  const config = ctx.freemiumConfig ?? FREEMIUM_SETTINGS_CONFIG;
  if (!isFreemiumSportEnabled(pick.league, config)) return [...ALL_BLOCK_GROUPS];
  return withLeakRule([...hiddenGroupsFromGlobals(config), "selection"])
    .filter((g) => ALL_BLOCK_GROUPS.includes(g));
}
```

- Duplicate ids in one response (seen in seed `100077282`, where one player pick is listed twice): if every copy has identical content, attach the same block to each; if copies differ, attach null to all and report `duplicate_id`. Adjust the pseudocode's duplicate check accordingly.
- Completed picks and subscriber picks carry no `locked`; unlocked active picks carry `locked: false`. Both give unlocked blocks.
- Postponed games are not in the legacy bypass list (`completed-bypass.ts`), so a postponed game's pick can be locked. The block follows the legacy lock (R3).

### 5.6 Record sources

```ts
interface PickRecordSource {
  readonly kind: "mock" | "cosmos";
  /** Records for the given picks' games in one region, keyed by pick_id. Never throws for a missing record. */
  load(args: {
    region: "us" | "au";
    picks: readonly V3Pick[];                 // unredacted, after the funnel
    games: Record<string, Schedule>;          // the route's gamesMap (with outcome)
    docsByGame: Record<string, PickDocMeta>;  // per game: the chosen pick documents' picks_updated_at ?? timestamp
    now: Date;
    mock?: MockParams;
  }): Promise<Map<string, ProducerRecord>>;
  /**
   * Records for arbitrary games in one region, keyed by pick_id: used by My Picks (MP-5 part f),
   * whose slips span many dates and sports. Cosmos: the same query and cache as load(). Mock:
   * regenerates from the games' documents (read through the same funnel) and returns {} on failure.
   */
  loadForGames(gameSks: readonly number[], region: "us" | "au"): Promise<Map<string, ProducerRecord>>;
}
```

- **Mock** (P1): generates records from the picks (§8.3). No I/O.
- **Cosmos** (P4): `SELECT * FROM c WHERE c.region = @region AND ARRAY_CONTAINS(@gameSks, c.game_sk)` on the KDD-001 container, through a Redis cache keyed `ep:rec:{region}:{game_sk}`, rebuilt at most every 60 s under a lock (`SET ep:lock:<key> <instance> NX PX 10000`; others serve the previous value or wait up to 2 s). Redis down ⇒ per-instance in-memory cache (`getOrLoad`) and direct reads. Each record is validated with the producer schema including the id formula; an invalid record is skipped and reported (`record_invalid`), and its pick gets a legacy block.
- A source failure (Cosmos error, or slower than 2 s) serves legacy blocks for the whole response and reports `source_unavailable`. It never fails the request and never drops picks: the list still comes from the documents.

### 5.7 Reporting

`reportEdgePickProblem` writes one structured `console.warn` line per (kind, league, reason) at most every 30 minutes: `{"evt":"edge_pick_problem","kind":"block_invalid","league":"nba","pickId":"…","reason":"…","count":N}`. Kinds: `block_invalid`, `record_invalid`, `record_mismatch`, `edge_state_mismatch`, `duplicate_id`, `source_unavailable`, `unmappable_legacy`, `cache_skipped_size`. Add an App Insights query for these to the dev dashboard.

### 5.8 What must not change

- Any response at v6 and below (R4).
- The free-user ranking, the strip lists, the `locks` map, the sort.
- My Picks routes, except the P2 fixes in §6.
- The parked `/v4/edge-picks` route (keep its tests green).

---

## 6. My Picks and slip fixes (P2)

Server-only; every build benefits. Independent of v7; start now.

| Id | Change | Files | Done when |
| --- | --- | --- | --- |
| **MP-1** | `POST /my-picks-v2` captures a snapshot per item, safely. (1) First extract the inline peer-load, availability and snapshot logic of `my-picks-create-v3.ts:64-123` into a shared helper. (2) Add `releaseStagedContentMiddleware` and `entitlementMiddleware` to the v2 create route (today `[globalErrorMiddleware, authMiddleware]`, `my-picks-create-v2.ts:42`); without the first, staged NBA 2026 picks never get a snapshot (`common.ts:149`). (3) Load peers once per game; match by `id` or `bet_id`. (4) For a free user, compute `findUnavailableMyPickItemIds(items, peersByGameId)` (`freemium/apply/my-picks.ts`) and capture a snapshot **only** for available items; unavailable items are stored without a snapshot, as today (no new rejection, so no new failure mode for any build). Subscribers get a snapshot for every resolvable item. (5) Store the selection's line in the snapshot: `snapshot.line = pick.line ?? legacySelection(pick, game)?.line ?? null` (Format A picks carry no `line` field, so today's snapshots store null). Write `snapshot.captured_for` = `"subscriber"` or `"free_unlocked"` with each snapshot. (6) The response body never contains `snapshot`: strip it from `my_pick.items` before returning (the app checks only for status 200). (7) If the peer load fails, store the items without snapshots and log. Never accept a client-sent snapshot | `my-picks-create-v2.ts`, `my-picks-create-v3.ts`, new `lib/my-pick/capture-snapshot.ts` (also used by `POST /v3/my-picks`, which then writes `captured_for` too) | Subscribers' resolvable items have snapshots; a free user's locked item has none; no response contains `snapshot` (V-SEC-3) |
| **MP-2** | Store-build-safe rows. The snapshot fallback already exists (`lookupResolvedPick` → `hydratePickFromSnapshot`, `resolve-my-picks-list.ts:60-62`). Add: every My Picks row (live and snapshot) carries an object `bookmaker: { name, bet_odds: { decimal_odds, american_odds } }` built from the first bookmaker (keep `bookmaker_options` as is; main reads either shape through `resolveBookmaker`). An item with neither live pick nor snapshot is returned with `unavailable: true`, odds null, and the slip's `totalOdds`, `totalOddsAmerican`, `returnAmount` null instead of 0 | `resolve-my-picks-list.ts:274-296`, `snapshot.ts` (`hydratePickFromSnapshot`), `my-pick.ts:183-206` | 1.1.66 shows prices and totals for live NBA 2026, Format A and snapshot rows; main shows "—" for unknown totals (`pickGroupAmounts.ts` handles null) |
| **MP-3** | Backfill: one-off script writes a snapshot for every slip item without one whose pick still resolves, with `captured_for: "backfill"` (not eligible for MP-4's owner visibility, because no entitlement check ran). Dry run prints counts per league. Run in dev, tst, production, before each league's Stage A | `script/my-picks/backfill-snapshots.ts` | Before/after counts; no other field changed |
| **MP-4** | Owner visibility (decision D3), bound to what the user was entitled to see when they saved: an item whose live peer is missing or now locked is shown to its owner **only** if its stored snapshot carries `captured_for` `"subscriber"` or `"free_unlocked"` (written by MP-1 after the entitlement and availability check; `"backfill"` does not count). Items without such a snapshot keep today's rule: a free user sees an item only when its peer is an unlock winner (`freemium/apply/my-picks.ts:59-94`). The resolved row needs the flag: carry `snapshot_captured_for` onto the row in `hydratePickFromSnapshot` and onto live rows from the stored item | `freemium/apply/my-picks.ts:59-94`, `snapshot.ts`, `resolve-my-picks-list.ts` | A lapsed subscriber sees every item they saved while subscribed; a free user who posted a locked id sees nothing more than today (V-SEC-3) |
| **MP-5** | Results, completion and payout, in `buildMyPickSlipResponse` (`my-pick.ts:162-213`) and the row builders. (a) Set `outcome` on live rows from `pickOutcome` (0, 1, 2), so My Picks stops showing completed live legs as crosses. (b) Add an additive `result` per item: `won`, `lost`, `push`, `void`, `cancelled`, `pending`. Code 2 is `push` when the market has a whole-number line (spread, total or over/under prop, as A.4), else `void`; the line is `pick.line ?? snapshot.line ?? legacySelection(pick, game)?.line` (Format A rows have no `line` field); `cancelled` comes from the producer record (P4; never set `pick_status: "cancelled"`, because `buildMyPickSlipResponse` drops such items, `my-pick.ts:9-25`). (c) Slip completion: today a slip is complete only when every leg's game status is exactly `"Completed"` (`my-pick.ts:196`), so a slip with a `Cancelled` game never completes. A leg is finished when its game status is `Completed`, `Cancelled`, `Canceled` or `Abandoned`, or its `result` is not `pending`; the slip is complete when every leg is finished. (d) Compute `totalOdds` and `returnAmount` with void, push and cancelled legs at 1.0; keep `returnAmount` as the projected return (not zeroed on a loss), as today (D8). (e) Read leg probability as `probability ?? xoProbability` (live rows carry no `xoProbability`, so `combinedProbability` is always 1 today; both app builds recompute it on the device, so this is a correctness fix with no visible change). (f) When `c-outcome` has no row, take the outcome from the producer record by pick id, through `recordSource.loadForGames(gameSks, region)`, once a record source exists | `my-pick.ts`, `resolve-my-picks-list.ts`, `snapshot.ts:299-316` | A void leg counts as 1.0 in the footer return in both builds; a slip with a cancelled game moves to Completed. 1.1.66 computes the summary "Return" on the device (`PickGroupCard.tsx:156` at the tag), which keeps using item prices; accepted (D2) |
| **MP-6** | Make My Picks version-safe: change `apiVersion === "v3"` (`my-picks-v2.ts:89`) **and** `entitlementWhenApiVersionV3` (`entitlement-middleware.ts:171`) to `apiVersionMajor(...) >= 3` | both files | `?api_version=v7` takes the modern path with entitlement: subscribers unfiltered, free users filtered |
| **MP-7** | Follow topics: replace `\|` with `_` in `queue-fcm-device.ts:40,54` as `target-follow.ts:63` does; one-off job re-subscribes existing devices | `queue-fcm-device.ts`, `script/follows/resubscribe.ts` | Re-registering a device with a pick follow succeeds |
| **MP-8** | Region: pass the auth user into `resolveMyPicksListForUser` (signature change) and use `resolveUserRegion(authUser)` (token fallback) instead of `normalizeRegion(user?.region ?? "")` | `resolve-my-picks-list.ts:71-89` and callers | A user with no stored region resolves in their token region |

---

## 7. App design (P3)

Base: `feat/XTP-125-Edge-Picks-Redesign-Oct26`. The card, slip, follows and filters keep their data flow; only the inputs change.

| Id | Change | Files | Done when |
| --- | --- | --- | --- |
| **FE-1** | Types for `edge_pick` and `edge_pick_meta`, generated from mobile-server `docs/edge-picks-v7/edge-pick-block.schema.json` with `json-schema-to-typescript`. Add `edge_pick?: EdgePickBlock \| null` to `TopPickCardData` | new `app/services/edgePicks/edgePickBlock.ts` (the untracked `type.ts` on a local main checkout is not on XTP-125), `TopPickCard.types.ts` | Types compile; regenerated on each contract change |
| **FE-2** | Send v7: set `DEFAULT_API_VERSION = "v7"`. This moves top picks, `/games` and `/game` to v7 (the server treats v7 as v6 there). Keep My Picks hard-coded at v3 (R5); add a comment and a unit test asserting the My Picks URL contains `api_version=v3` | `useAppConfig.ts:42`, `myPicks.service.ts:25` | Games, game detail and My Picks regression tests pass |
| **FE-3** | Card inputs from the block when `edge_pick` is present: price chip original = `entry.odds`, current = `current.odds` (drop the guessed top-level `current_*` reads); probability bar = `edge_pick.probability` (XTP-125 shows the bar for NBA only, `EdgePicksCard.tsx:271`; with a block every league has a probability, so product and design decide whether to show it everywhere); `EdgeValueBadge` `edge = entry.edge`, `currentEdge = current.edge` (fractions; don't apply `toEdgePercent` heuristics to block values); edge-state indicator from `edge_state`; "Edge holds above" from `edge_holds_above`; status chip and message from `status`, `status_reason.message`; result chip from `result` | `EdgePicksCard.tsx`, `bookmakerOdds.ts`, `EdgeValueBadge.tsx`, `ProbabilityBar` usage. The chip receives a hand-built `bookmakerOddsPick` object (`EdgePicksCard.tsx:93-101` on XTP-125), not the pick: add `edge_pick` to `BookmakerOddsPick` (`bookmakerOdds.ts:16-24`) and pass `edge_pick: pick.edge_pick` there | Card matches the design for every scenario in §8.4 |
| **FE-4** | Variants: `edge_pick` missing or null ⇒ today's card; `era !== "v4"` ⇒ limited card (no current price, no edge state, no "holds above", price labelled "Published price", no picked-at time); `era === "v4"` ⇒ full card | `EdgePicksCard.tsx` | Snapshot tests for null, legacy and v4 |
| **FE-5** | Locks: for each group in `edge_pick.access.hidden` show a lock in place of the block's field; never compute a hidden value from visible ones. When `odds` is hidden, the price chip has no price and (on a locked pick) no source, so `bookmakerOddsView` returns null and the chip disappears, as it does for locked picks today; design decides whether to show a locked placeholder chip instead. Top-level `locked` and `locks` keep driving the legacy fields. Do **not** change `resolveLocks.ts:53` (`locks?.topPicks` is the key the server sends) | `EdgePicksCard.tsx` | Free-user snapshots show locks and no hidden values |
| **FE-6** | Slip: one `canAddPick` rule gates both the footer Add button and the price chip (today the chip is disabled only while the subscription is loading, `EdgePicksCard.tsx:260`, so it can add a completed game's pick). With a block: `edge_pick.status === "open"` (a postponed game stays open, D7). Without a block: today's footer rule (game status is not `Completed`), now applied to the chip too. `newOdds` = `edge_pick.entry.odds` as `{decimal_odds, american_odds}` when present, else today's `bookmaker.bet_odds`. Moneyline exclusivity: copy the removal logic of `GameScreen/_components/GamePick.tsx:68-79` into `EdgePicksCard`, keyed on `edge_pick.selection.market === "moneyline"` (fallback: `isH2hPick`), and pass `bet_type: "h2h"` | `EdgePicksCard.tsx:120-165, 256-287` | Can't add cancelled, settled or void picks; adding the other moneyline side of a game replaces the first; slip total equals the saved total |
| **FE-7** | My Picks: render `result` when present (else `outcome`): `won` tick, `lost` cross, `void`/`push`/`cancelled` neutral, `pending` none. Group badge on a completed slip: lost if any leg is lost; else won if at least one leg is won; else neutral (every leg void, push or cancelled); `unavailable: true` items show "Pick no longer available" with "—" odds | `MyPicksItem.tsx:101`, `PickGroupCard.tsx:56-60` | A slip with a void leg shows it neutral and grades the group on the rest |
| **FE-8** | Dev affordance: in dev builds only, a debug menu that appends `edge_pick_scenario`, `edge_pick_era`, `edge_pick_seed`, `edge_pick_now` to the top-picks request | dev menu, `toppicks.service.ts` | QA switches scenarios on device |
| **FE-9** | Settled outcome on the card: `CardOutcomeFooterRow` gets `outcome={null}` hard-coded (`EdgePicksCard.tsx:284` on XTP-125). Wire it from `edge_pick.result` (`won` ⇒ `correct`, `lost` ⇒ `incorrect`, `push` ⇒ `push`, `void` ⇒ `void`), falling back to `mapPickOutcome(pick.pickOutcome)` when there is no block. Add `push` to `PredictionOutcome` (`app/utils/predictionOutcome.ts`, today `correct`/`incorrect`/`void`) and to `PredictionOutcomeIndicator` | `EdgePicksCard.tsx`, `app/utils/predictionOutcome.ts`, `app/components/common/PredictionOutcomeIndicator.tsx` | Settled cards show won, lost, push and void |

The app must tolerate `edge_pick` missing entirely (an older BFF, or `source: off`). That makes the release order of BFF and app independent.

---

## 8. Mock data

### 8.1 Goals

1. Unblock the app team now, on the games and pick ids the dev BFF already serves.
2. Exercise the **same** code path live data will use: records → blocks → redaction → validation. Only the record source differs.
3. Cover every state the design has, on demand.
4. Give CI stable fixtures and golden files.

### 8.2 Sources of data

| Source | What it holds | Real? | Use |
| --- | --- | --- | --- |
| dev Cosmos `app-read-dev`: `c-sch-dev-01`, `c-wltp-dev-01`, `c-ps-dev-01`, `c-outcomes-dev-01` (what the dev BFF reads, `infra/envs/dev/app_settings.tf:41-51`) | NBA 2026 canonical documents, 107 games, 2026-10-20 to 2026-11-03, loaded from `reqs/nba/tools/nba_mock_data_2weeks.json` (golden game `40021717855`). Ids already follow the producer `pick_id` formula. Statuses: games before 10-25 `Completed`; 10-25 has 9 `Scheduled`, 1 `Postponed`, 1 `Cancelled`; later games `Scheduled` | Realistic synthetic | Primary source for the dev mock (L1) |
| `reqs/nba/tools/nba_mock_data_{sample,4days,2weeks}.json` | The same NBA documents as files | As above | CI fixtures |
| `mobile-server/script/db-seeds/*.json` with `_rid`/`_etag` | Real Cosmos exports: MLB `player_top_picks`, Format A `game_prediction` (incl. `FAV_SPR<` with unsigned `position`), schedules, outcomes; old NBA list shapes; `bet_outcome` as `"1.0"`, `"0"`, `1` | Real | CI fixtures for Format A and legacy variants |
| `db-seeds/data-c-{epl,nfl}-*.json` | EPL and NFL Format A | Synthetic | CI fixtures for EPL (draw, BTTS) and NFL (H2H) |
| tst Cosmos `app-read-tst` (`c-sch-tst-02`, `c-wltp-tst-01`, `c-ps-tst-02`, `c-outcomes-tst-02`) | Real current documents, all leagues | Real | Optional: `snapshot-cosmos-day.ts` exports a day's content documents read-only (Cosmos DB Built-in Data Reader). Content documents hold no user data. Needs data-engineering approval; output to a git-ignored folder until reviewed |

**Data facts the generator must cope with** (measured on the 2-week file):

- Game picks (214): probability 0.53–0.58. On the probability basis, 34% have an edge ≤ 0.02 and 8% ≤ 0.
- Player picks (856): probability 0.48 on 736 of them. On the probability basis, 56% have an edge ≤ 0, which a real engine would never publish.
- 300 player picks are milestones: `type` `player_milestone`, `line: null`, the threshold in `threshold_k` (also in the id, e.g. `…|ast|player_milestone|6|…`).
- No pick has `bet_outcome` 2 (no push, no outcome-based void).
- The data ends on 2026-11-03. After that, the dev BFF serves no NBA picks (MK-5).

### 8.3 Synthetic record generator

Module: `src/lib/edge-picks/v7/mock/generate.ts`, shared by the mock source (L1), the sample exporter (L3) and the seeding script (L2).

**Input:** the unredacted v3 picks for one region and day, the schedule rows with outcomes, the per-game document timestamps, `now`, `seed`, optional forced scenario or era.

**Determinism:** `rng(pickId, salt) = mulberry32(fnv1a(pickId + ":" + seed + ":" + salt))`. No clock reads except `now`.

**Per pick:**

1. **Selection:** `legacy-selection.ts` (Appendix A.5), the same function the legacy block uses. Unmappable ⇒ no record (legacy block with null selection); report `unmappable_legacy` once per `bet_type`.
2. **Identity:** `pick_id = pick.id` unchanged (R7); `region`, `sport = league`, `game_sk`, `pick_kind`, `team_sk`, `player_sk` (as an integer: some MLB seeds store it as a string, e.g. `"11007152"`; a value that isn't an integer means no record), `stat_code` (legacy stat mapped to the contract vocabulary, e.g. `pts`, `reb`, `ast`, `threes`; unknown ⇒ lower-cased legacy stat).
3. **Entry:** `entry_decimal_odds` = the document's decimal price rounded half away from zero to 4 places (db-seeds carry 16-decimal floats such as `1.7874015748031495`). `entry_american_odds` = the document's American price **as written** (R6: it is what the top-level fields, the slip and My Picks show), even where it does not match the conversion rule: in the dev NBA data 760 of 1,070 picks don't (e.g. 1.85 with −111, where the rule gives −118). `stake_units` = the pick's stake (0 is valid). `odds_source_kind` = `market_average` for AU; for US, `bookmaker` with `entry_bookmaker_id` = bookmaker id or slug when the document names a bookmaker, else `market_average` with no bookmaker id (MLB seeds have `bookmaker.name: null`; never invent a bookmaker name).
4. **Probability and basis.** `probability` = the document's probability rounded to 4 places. Default basis `ev`, threshold 0. For NBA game picks whose probability-basis edge (`p − 1/d`) exceeds 0.02, use basis `prob`, threshold 0.02, so the prob-basis break-even path is exercised. **Mock-only adjustment:** if `p × d − 1 ≤ 0.01` (no real edge at the document's price, common in the dev player data), set `probability = min(0.95, round4(1.03 / d))`. The block's probability then differs from the top-level legacy probability; the card uses the block's (FE-3). Count adjusted picks in a debug log.
5. **`pick_date_time`:** the game's document timestamp (`picks_updated_at ?? timestamp`) minus `rng(pickId,"t") × 2 h`. Fixed for the life of the data (R10).
6. **Lifecycle:** `legacyLifecycle(pick, game, now)` (Appendix A.4) gives the starting status and result. For code 2 the push/void rule of A.4 applies.
7. **Scenario.** Eligible picks: status `open` and the game not started. `mixed` assigns deterministically first, then by weight:
   - The "day" is the set of picks in this response: one region, the requested date and offset window. Sort its eligible picks by `pick_id`. Then, **for each** of the nine required scenarios in order (`live`, `narrowing`, `closed`, `line_moved`, `suspended`, `no_observation`, `cancelled` `probability_moved`, `cancelled` `market_moved`, `cancelled` `lineup_change`), assign the first not-yet-assigned pick that is eligible for it (table below). Assigning scenarios to picks, not picks to scenarios, means a moneyline pick at the front of the list can't crowd out `line_moved`: any day that has at least one eligible pick for a scenario gets that scenario.
   - The rest draw by weight with `rng(pickId,"s")`: live 30%, narrowing 15%, closed 10%, line_moved 10%, suspended 5%, no_observation 20%, cancelled 10%. If the drawn scenario isn't eligible, use the next eligible one in table order (`no_observation` is always eligible).
   - A forced `edge_pick_scenario` applies to every pick eligible for it.
   - **Started picks** (status `awaiting_result`, `settled` or `void` from step 6) get a closing observation too, so settled and in-play cards show a closing price: a scenario drawn with `rng(pickId,"c")` from live 35%, narrowing 20%, closed 15%, line_moved 15%, no_observation 15%, subject to the same eligibility. `cancelled` and `suspended` are never assigned to started picks. A forced observation scenario (`live`, `narrowing`, `closed`, `line_moved`, `no_observation`) also applies to started picks.
8. **Observation per scenario** (all prices rounded half away from zero to 4 places before use; `b4 = edgeHoldsAbove(...).decimal`, `m = roundHalfAway((entry + b) / 2, 4)` with unrounded b):

   | Scenario | Eligible when | Observation | Expected `edge_state` |
   | --- | --- | --- | --- |
   | `live` | entry > b4 | price = round4(max(entry, m) × (1.02 + rng × 0.05)), same line | live |
   | `narrowing` | entry > b4 and m − b4 ≥ 0.0002 | price = round4((b4 + m) / 2), same line | narrowing |
   | `closed` | b exists | price = b4, same line | closed |
   | `line_moved` | the market has a line | line + 1 (spread); over/under: line + 1, or line − 1 when the rng says down and line − 1 > 0; price = entry | closed |
   | `suspended` | always | price and line null (pulled) | suspended |
   | `no_observation` | always | none | unknown |
   | `cancelled` | always | as `closed`; status `cancelled` with the assigned reason | closed |
   | `settled_push` (forced only) | game completed, market with a line (spread, total, over/under prop) | status `settled`, result `push` | as observed |
   | `void` (forced only) | any | status `void`, result `void`, reason `game_void` | as observed |

   After building, check with `deriveEdgeState`; a mismatch is a generator bug (test V-MOCK-3).
   `observed_at` = min(now, start − 1 min) − rng × 30 min. `is_closing` = the game has started **and** an observation exists (`observed_at` not null); with no observation, `is_closing` is false (contract §9.1 invariant 4).
9. **Drift** (`EDGE_PICK_MOCK_DRIFT=on`): for `live` and `narrowing`, the price moves by ±0.0100 per 5-minute bucket of `now` (rng salted with the bucket), clamped inside its scenario band. Entry values never change.
10. **Phantom cancelled picks (for BE-11 in P4):** for one game in three (`fnv1a(game_sk) % 3 == 0`), one extra cancelled record copied from a listed game pick with a line market, its line moved by 1, and its `pick_id` rebuilt with the producer formula. These are not in the documents. The P1 mock source does not return them unless injection is built.
11. **Validate** every record with `producer-record.schema.ts`. Mock records skip two invariants, because they copy legacy values on purpose: the id formula (`checkIdFormula: false`; ids are reused as they are, e.g. Format A `2001_H2H_us`, NBA milestone ids, and one seed US bucket that holds an `|au` id) and the American-price formula for the **entry** price (`checkEntryAmericanFormula: false`; R6 keeps the document's American). Every other invariant applies, including the formula for `current_american_odds`, which the generator derives. Phantom records (step 10) check everything, with the entry American derived by the rule. A failure is a generator bug: throw in tests, report in dev.

### 8.4 Coverage guarantees

On a day with at least nine eligible picks in a region, including one with a line and one whose entry price is above its break-even, `mixed` yields every edge state and each cancel reason (step 7). Settled won/lost come from real outcomes; push and void come from the forced scenarios, the dev day's postponed and cancelled games, and a hand-written CI fixture. Test V-MOCK-2 asserts this on the golden day.

**Golden days:** 2026-10-25 (eligible picks, a postponed and a cancelled game) with `now = 2026-10-25T12:00:00Z`; 2026-10-22 (all completed: settled cards). 2026-10-20 has only two completed games and is not a mixed day.

### 8.5 Three layers of mock data

| Layer | What | Where | Who uses it | Phase |
| --- | --- | --- | --- | --- |
| **L1. Synthetic overlay** | `EDGE_PICK_SOURCE=mock`: records generated in memory from the dev documents on every request | dev BFF | App team on devices; QA | P1 |
| **L2. Seeded records container** | `seed-mock-records.ts` writes generated records to an isolated container; `EDGE_PICK_SOURCE=cosmos` points at it | a separate dev database (dev-isolation rule 1), e.g. `app-read-dev-edge` / `c-edge-picks-mock-dev-01` | Validation of the real Cosmos path, cache and lock | P4 |
| **L3. Offline samples and fixtures** | Golden responses and fixture days in the repo | `docs/edge-picks-v7/samples/`, `src/lib/edge-picks/v7/__fixtures__/` | App team before the dev deploy; CI | P1 |

### 8.6 Offline samples for the app team (L3, first deliverable)

`script/edge-picks/export-v7-samples.ts` runs the route handler in-process against the fixture days with the mock source, with the clock and Redis stubbed, and writes:

| File | Content |
| --- | --- |
| `docs/edge-picks-v7/edge-pick-block.schema.json` | JSON Schema of `edge_pick` and `edge_pick_meta` (shapes, enums; conditional rules listed in the README) |
| `docs/edge-picks-v7/samples/nba-2026-10-25-us-subscriber-mixed.json` | Golden mixed day: every scenario |
| `…-au-subscriber-mixed.json` | AU wording (Avg. Odds, "Win") |
| `…-us-free-mixed.json`, `…-us-free-nba-disabled.json` | Locks: unlocked winners, locked picks with hidden groups, null sources |
| `…-us-subscriber-legacy.json` | Every block `era: legacy` |
| `…-us-subscriber-<scenario>.json` | One per forced scenario, including `settled_push` and `void` |
| `nba-2026-10-22-us-subscriber-mixed.json` | Completed day: settled cards |
| `mlb-…-legacy.json`, `epl-…-legacy.json`, `nfl-…-legacy.json` | Format A legacy blocks from db-seeds |
| `…-v6.json` beside each | The same request at v6, showing what does not change |
| `docs/edge-picks-v7/README.md` | How to read the block, the card variants, the mock parameters |

Commit the outputs and regenerate them whenever the block, the generator or the fixtures change.

### 8.7 Seeded records container (L2)

`seed-mock-records.ts --from 2026-10-25 --to 2026-11-03 --region us,au --target-db <db> --container <c> [--replay]`:

1. Reads schedules and documents from the configured read database (dev by default), runs `getAllAvailableTopPicksForGame` per game and region inside `withStagedContentReleased`, generates records with §8.3, validates them, and upserts by `pick_id` with partition key `/game_sk` (KDD-001 layout).
2. Refuses to write to any database whose name does not contain `edge` or `mock`.
3. `--replay` regenerates observations every 5 minutes for open picks (drift on), so the BFF cache and app refresh see real changes.

---

## 9. Validation

### 9.1 Test catalogue

**Conditions for every route-level test:** freeze the clock (`getDisplayGameStatus` reads `new Date()`, `common.ts:55`; `sortGameListItems` reads `Date.now()`, `sort-by-game-status.ts:41`; and the plan's `now`), stub Redis (fake client, empty at start), and compare serialized JSON (`JSON.parse(JSON.stringify(body))`), because subscriber bodies are not JSON-cloned in-process and can hold `undefined` keys.

| Id | Test | Level | Phase |
| --- | --- | --- | --- |
| **V-UNIT-1** | Existing derive vectors (D-1…D-11, E1…E13) stay green | unit | P1 |
| **V-UNIT-2** | Block schema: every rule in §4.3 has a passing and a failing case; Appendix B examples validate | unit | P1 |
| **V-UNIT-3** | Legacy mapping per family: NBA canonical game and player (including milestones), Format A game per league (old NBA list shape, MLB, NFL H2H, EPL draw and BTTS; spreads from `code` including `2002_FAV_SPR_us` and `31679_FAV_SPR<`; `37_H2H` with null `bet_line`; the block's side and line agree with the pick's `pickDescription`), Format A player (MLB numeric `position`); legacy blocks carry the mapped `selection` (null only when unmappable); `bet_outcome` `"1.0"`, `"0"`, `1`, `2`; missing bookmaker name; American price kept as written | unit | P1 |
| **V-UNIT-4** | `attachEdgePicks` locks: subscriber, completed pick, unlocked active (`locked: false`), locked with sport enabled (each flag combination), sport disabled, missing config (fails closed); sources null when locked | unit | P1 |
| **V-UNIT-5** | Producer schema and §9.1 invariants: the contract's five example records pass; one broken invariant each fails; `checkIdFormula: false` and `checkEntryAmericanFormula: false` each skip only their own check | unit | P1 |
| **V-UNIT-6** | `legacyLifecycle` table (A.4), including postponed (stays open) and cancelled games, code 2 push/void rule | unit | P1 |
| **V-MOCK-1** | Determinism: two runs with the same fixture, `now` and seed are deep-equal; `picked_at` is identical for two different `now` values; a different seed changes the `mixed` assignment beyond the first nine | unit | P1 |
| **V-MOCK-2** | Coverage on the golden day: every edge state, every cancel reason; forced `settled_push` and `void` produce their states | unit | P1 |
| **V-MOCK-3** | Every generated record validates (with the two mock exemptions); every forced scenario yields its expected `edge_state` for every pick eligible for it; started picks have closing observations; no record has `is_closing: true` without `observed_at`; prices and probabilities have at most 4 decimals; entry American equals the document's | unit | P1 |
| **V-INV-1** | **Coexistence invariant:** for each fixture day × region × {subscriber, free with three flag sets, sport disabled}: v6 has no `edge_pick` or `edge_pick_meta` anywhere; the v7 body minus `edge_pick`, `edge_pick_meta` and injected items, with `count` recomputed, deep-equals the v6 body (`locks` included: injected picks must not change it) | integration (seeded emulator) | P1 |
| **V-INV-2** | Every non-null block validates; ids unique; `edge_pick.access.locked === (pick.locked === true && !subscriber)` | integration | P1 |
| **V-SEC-1** | **Leak sweep:** in every free-user response, no field of a hidden group is non-null in any block; sources null on locked picks; `selection` hidden on every locked pick; leak rule holds | integration | P1 |
| **V-SEC-2** | Mock parameters are ignored and don't bypass the cache unless `EDGE_PICK_MOCK_PARAMS=on`; the production guard (§5.3) forces `none` | unit | P1 |
| **V-SEC-3** | **Slip-save security:** a free user posts `POST /my-picks-v2` with the ids of locked picks (taken from a free-user v7 list): the response has no `snapshot` and no pick values; the stored items have no snapshot; `GET /my-picks-v2?api_version=v3` for that user returns no locked item's values. A subscriber doing the same gets snapshots stored and sees every item after lapsing to free | integration | P2 |
| **V-CACHE-1** | Free-user cache: v6 and v7 bodies under separate keys; an honoured mock-parameter request is neither served from nor written to the cache; body size of the largest fixture day under 512 KiB or reported | integration | P1 |
| **V-ERR-1** | Fault injection: a record source that throws ⇒ legacy blocks, status 200, one report; one invalid block ⇒ null for that pick only | unit | P1 |
| **V-REG-1** | `/games` and `/game` at v7 deep-equal v6 for the fixture days | integration | P1 |
| **V-RT-1** | **Round trip, list → slip → My Picks:** for every v7 pick in a fixture day, `POST /my-picks-v2` with its id, then `GET /my-picks-v2?api_version=v3`: the item resolves with the same id, the same entry price (decimal and American) and the list's game | integration | P2 |
| **V-RT-2** | Pick leaves the list after save (remove it from the document): the item resolves from its snapshot with an object `bookmaker.bet_odds`; slip totals not 0; a user who saved it while subscribed still sees it after lapsing to free (MP-4) | integration | P2 |
| **V-RT-3** | No snapshot and no live pick: `unavailable: true`, totals null | integration | P2 |
| **V-RT-4** | Results: live completed legs carry `outcome`; void and push legs count as 1.0 in `totalOdds` and `returnAmount`; `result` set, including push on a whole-number prop line; a slip with a `Cancelled` game and graded other legs is complete | integration | P2 |
| **V-RT-5** | Store-build contract: every My Picks row satisfies what 1.1.66 reads (`bookmaker.bet_odds.decimal_odds` number, `probability` number, `outcome` number or null) for live NBA 2026, Format A, snapshot and unavailable rows | integration | P2 |
| **V-RT-6** | `GET /my-picks-v2?api_version=v7` takes the modern path: a subscriber is not filtered, a free user is (MP-6) | integration | P2 |
| **V-APP-1** | App snapshot tests per card variant × scenario × lock state, from the §8.6 samples | app unit | P3 |
| **V-APP-2** | Settled card outcomes incl. push (FE-9); slip: Add disabled for non-open blocks and, without a block, for completed games (button and chip); moneyline exclusivity; slip total equals the entry product; My Picks `result`, void/push and unavailable rendering | app unit | P3 |
| **V-E2E-1** | Device QA on dev with L1 (checklist §9.3) | manual | P3 |
| **V-LIVE-1** | P4: L2 container with several BFF instances: one Cosmos rebuild per key per minute; kill switch flips a league to legacy on the next uncached request | integration on dev | P4 |
| **V-LIVE-2** | P4 shadow: for one week of NBA Stage A in the shadow containers, every derived-document pick has a record with the same id and entry price (`record_mismatch` = 0), and real records pass every invariant, including the entry American-price formula, so the derived documents' American prices also match the rule (the dev mock data's mismatches must not reach real data) | data check | P4 |

### 9.2 Acceptance criteria per phase

- **P1 done:** V-UNIT-*, V-MOCK-*, V-INV-*, V-SEC-1, V-SEC-2, V-CACHE-1, V-ERR-1, V-REG-1 pass in CI; dev BFF deployed with `EDGE_PICK_BLOCKS=on`, `EDGE_PICK_SOURCE=mock`; tst deployed with `EDGE_PICK_BLOCKS=on`, `EDGE_PICK_SOURCE=none`; samples committed; the app team confirms they can load every scenario.
- **P2 done:** V-RT-* and V-SEC-3 pass; MP-3 dry run reviewed and applied in dev and tst.
- **P3 done:** V-APP-*, V-E2E-1 pass; release build sends v7 and keeps My Picks at v3.
- **P4 done (per league):** V-LIVE-1, V-LIVE-2; KDD-002 gate list green for the league; product sign-off on the behaviour changes.

### 9.3 Device QA checklist (V-E2E-1)

For US subscriber, AU subscriber, US free (NBA enabled), US free (NBA disabled), on dev with L1, on a date with eligible picks (use `edge_pick_now` if the dev data's dates have passed):

1. `mixed`: every card variant appears; edge states match the badge; "Edge holds above" shows only on v4 cards that aren't hidden.
2. Each forced scenario: every eligible card shows that state.
3. `edge_pick_era=legacy`: limited cards only, "Published price", no picked-at time.
4. Locked cards show locks for exactly the groups in `access.hidden`; no hidden value anywhere, including the slip and the share sheet; no bookmaker name on locked cards.
5. Add (button and chip) is disabled for cancelled, settled and void; enabled for open; the slip total equals the entry prices' product; after save, My Picks shows the same total.
6. A slip containing a pick later forced to `cancelled` (change the scenario after saving) still shows its price in My Picks (after P2).
7. Moneyline exclusivity: adding the other side of the same game's moneyline replaces the first.
8. AU: "Avg. Odds" and "Win" wording.
9. Pull to refresh with `EDGE_PICK_MOCK_DRIFT=on`: current prices change, entry prices never do.

---

## 10. Work breakdown

Estimates are for one developer who knows the codebase. Branches: BFF `feat/edge-picks-v7` from `feat/edge-picks` (keeps B1); app from XTP-125.

### 10.1 BFF, P1

| Id | Task | Depends on | Estimate |
| --- | --- | --- | --- |
| BE-1 | Config module, settings, production guard, Redis kill-switch read (§5.3) | — | ½ d |
| BE-2 | `EdgePickBlockSchema`, `blockRuleViolations`, JSON Schema export | B1 | 1 d |
| BE-3 | `producer-record.schema.ts` and invariants; the contract's example records as tests | — | 1 d |
| BE-4 | `PickRecordSource` interface, factory, mock source shell | BE-1 | ½ d |
| BE-5 | `legacy-selection.ts`, `lifecycle.ts`, `build-block.ts`; export `parseOddsNumber` | BE-2, BE-3 | 2 d |
| BE-6 | `attach.ts`, `redactBlock`, reporting; route insertion points, empty-day meta, cache bypass rule | BE-5 | 1½ d |
| MK-1 | Generator §8.3 with determinism and coverage | BE-3, BE-5 (shares `legacy-selection`, `lifecycle`) | 2 d |
| MK-2 | Fixture days: NBA 2026-10-22 and 2026-10-25 from `nba_mock_data_2weeks.json`; real MLB and old-NBA Format A exports; EPL and NFL seeds; a hand-written push/void fixture | — | ½ d |
| MK-3 | `export-v7-samples.ts`, README, commit samples | BE-6, MK-1, MK-2 | 1 d |
| BE-7 | Tests V-UNIT-*, V-MOCK-*, V-INV-*, V-SEC-1, V-SEC-2, V-CACHE-1, V-ERR-1, V-REG-1 | all above | 2 d |
| BE-8 | Dev and tst deploy: Terraform settings, App Insights query, body-size check, smoke test on game `40021717855` | BE-7 | ½ d |
| MK-5 | Roll the dev NBA data forward before 2026-11-03 (re-run `build_nba_mock_14days.py` with a new start date and `inject_nba_mock_cosmos.py`), then every two weeks until real NBA data is in dev | data engineering or BFF | ½ d each time |

**P1 total: about 12½ days for one developer.** The critical path to the first samples is BE-3 → BE-5 → BE-6 and MK-1 → MK-3, about 6½ days. With two developers (one on BE-5/BE-6, one on MK-1/MK-2), samples reach the app team by the end of week 1. MK-2 can start on day 1.

### 10.2 BFF, P2 (parallel)

MP-1 (2½ d, incl. extracting the v3 helper, the entitlement check and `captured_for`), MP-2 (1½ d), MP-3 (1½ d), MP-4 (½ d), MP-5 (1½ d; part (f) after BE-10), MP-6 (½ d), MP-7 (1 d), MP-8 (½ d), tests V-RT-* and V-SEC-3 (2 d). **About 11½ days.**

### 10.3 App, P3

FE-1 (½ d), FE-2 (½ d), FE-3 (1 d), FE-4 (½ d), FE-5 (½ d), FE-6 (1 d), FE-7 (½ d), FE-8 (½ d), FE-9 (½ d), V-APP-* and QA (1 d). **About 6½ days**, starting when samples land.

### 10.4 BFF and data engineering, P4 (live, NBA first)

| Id | Task | Owner | Depends on |
| --- | --- | --- | --- |
| DE-1 | KDD-001 records container per environment; the Publish Engine writes validated records | data engineering | KDD-001 accepted |
| DE-2 | KDD-002 Stage A for NBA in shadow, then live (derived documents under `pick_id`) | data engineering | KDD-002 prerequisites P1–P9 |
| BE-9 | Records cache with rebuild lock (KDD-001 guardrail 1) | BFF | — |
| BE-10 | `cosmos-record-source.ts` (`load` and `loadForGames`), consistency checks (§5.4) | BFF | BE-9, DE-1 |
| BE-11 | `inject-cancelled.ts` (Appendix A.3) | BFF | BE-10, `stripAsLockedTopPick` |
| MK-4 | `seed-mock-records.ts` (L2) with the write guard and replay | BFF | MK-1 |
| BE-13 | V-LIVE-1, V-LIVE-2 | BFF, data engineering | all above |

### 10.5 P5 follow-ups

- **BE-14** Format A extra game picks at v7: for v4-era games, add record-only game picks (not in `top_picks[region]`) through BE-11's mapping and lock rule. Requires MP-1/MP-2 so saving one is safe. Product decides whether launch needs it (D5).
- Apply product decisions D1–D8 (§12).

---

## 11. Rollout and rollback

| Step | Environment | Settings | Check |
| --- | --- | --- | --- |
| 1 | dev | `EDGE_PICK_BLOCKS=on`, `EDGE_PICK_SOURCE=mock`, `EDGE_PICK_MOCK_PARAMS=on` | Smoke on game `40021717855`; samples match |
| 2 | dev | App debug build with v7 | §9.3 checklist |
| 3 | tst | `EDGE_PICK_BLOCKS=on`, `EDGE_PICK_SOURCE=none` | v7 returns legacy blocks on real data; V-REG-1 on real data; no `edge_pick_problem` spikes |
| 4 | tst | P2 fixes live; MP-3 backfill applied | V-RT-* with test accounts |
| 5 | production | As tst; app release with v7 | Old builds unaffected (error rate per `api_version`) |
| 6 | per league (P4) | `EDGE_PICK_SOURCE=cosmos`, league in `EDGE_PICKS_V4_LEAGUES` after its Stage A is live | `edge_pick_problem` near zero; product sign-off |

**Rollback levers, fastest first:**

1. Redis `edge-picks:v4-off:<league>` ⇒ that league's blocks become legacy on the next uncached request (free users within 60 s).
2. `EDGE_PICK_SOURCE=none` ⇒ every block legacy.
3. `EDGE_PICK_BLOCKS=off` ⇒ every block null; the app draws today's card.
4. Revert the BFF deploy: v7 requests are served as v6 (no blocks); the app tolerates that (FE-4).

None of these touches data or affects store builds.

---

## 12. Decisions, risks and open items

### 12.1 Product decisions (defaults used until decided)

| Id | Decision | Default |
| --- | --- | --- |
| D1 | Slip price: entry or current | Entry (R6) |
| D2 | Store build: a push or void leg can only show tick or cross, and its summary "Return" is computed on the device | Tick on snapshot rows, outcome 2 on live rows (also a tick); footer return correct (MP-5) |
| D3 | A saved slip item shows to its owner, even when now locked or no longer listed | Yes, but only items saved while the user was entitled to see them (snapshot with `captured_for`, MP-1/MP-4) |
| D4 | Grading a slip leg whose pick XO cancelled | `result: cancelled` in the new app (neutral), counted as 1.0; no grading until the engine settles cancelled selections |
| D5 | Format A leagues need more than one game pick per game at launch | No (BE-14 later) |
| D6 | Limited-card copy and whether legacy cards show an edge | "Published price"; edge shown |
| D7 | A postponed game's pick: open (the market stays live, as legacy treats it) or void | Open until the game is cancelled or graded (A.4) |
| D8 | A slip with a lost leg: show the projected return (today) or 0 | Projected return, unchanged (MP-5) |

### 12.2 Risks

| Risk | Handling |
| --- | --- |
| A nested block leaks on locked picks | R1–R3, sources null when locked, V-SEC-1 in CI |
| v6 responses change by accident | R4, V-INV-1 in CI on every PR touching the route |
| Mock reaches production | R9, production guard, V-SEC-2, Terraform review |
| Legacy documents vary more than the fixtures | Loose parsing, `unmappable_legacy` reports, optional tst snapshot (§8.2) |
| Stage A entry prices differ from records | Consistency check (§5.4), V-LIVE-2 |
| App and BFF deployed out of order | App tolerates a missing block; v7 on an older BFF behaves as v6 |
| XTP-125 continues on guessed fields | FE-3 replaces them; samples shared end of week 1 |
| Dev NBA data expires on 2026-11-03 | MK-5; `edge_pick_now` for older dates |
| v7 bodies exceed the 512 KiB cache limit | Measured in BE-8 and V-CACHE-1; if exceeded, cache uncompressed bodies only below the limit and report `cache_skipped_size` |

### 12.3 Open items

| Item | Owner |
| --- | --- |
| Whether the dev Publish Engine writes non-NBA leagues into the `*-dev-01` containers (affects L1 coverage beyond NBA) | data engineering |
| Approval for a read-only tst snapshot (§8.2) | data engineering |
| KDD-001 container name per environment and the BFF's read identity | data engineering |
| Bookmaker display-name map and its owner (slug → name) | BFF, product |
| What `FAV_SPR<`, `FAV_SPR>`, `UD_SPR<`, `UD_SPR>` mean, and why seed `code` and `bet_line` disagree on side (`31679_FAV_SPR<`). The plan follows `code`, as the card description does; confirm with the engine | BFF, bet engine |
| Update KDD-003 and `kdd23-design.md` to option B | contract owner |

---

## 13. Appendices

### A.1 Legacy v3 pick → legacy-era block

| Block field | Source on the unredacted v3 pick | Notes |
| --- | --- | --- |
| `era` | `"legacy"` | |
| `probability` | `probability ?? xoProbability ?? xo_probability` | Fraction in (0, 1) |
| `entry.odds.decimal` | `decimal_odds`, else `bookmaker.bet_odds.decimal_odds`, else `bet_price` | 4 places |
| `entry.odds.american` | `american_odds`, else `bookmaker.bet_odds.american_odds`; derived only if missing | As written (R6) |
| `entry.line` | `legacy-selection.ts` (A.5) | null when unknown |
| `entry.edge` | `computeEdge(probability, entry.odds.decimal)` | Legacy `edge` field ignored |
| `entry.stake_units` | `stake` | |
| `entry.source` | AU ⇒ market average; else `bookmaker_id ?? slug(name)` + display name, via `resolveBookmaker` | null when no bookmaker named; null when locked |
| `status`, `result`, `status_reason` | `legacyLifecycle` (A.4) | |
| `selection` | `legacy-selection.ts` (A.5) | null when unmappable; nulled when the selection group is hidden |
| `picked_at`, `current`, `edge_holds_above`, `overlay_key`, `action` | null | |
| `edge_state` | `"unknown"` | |

### A.2 Producer record → v4-era block

| Block field | Record field |
| --- | --- |
| `selection` | `{market, side, line, stat_code}` |
| `probability` | `probability` |
| `picked_at` | `pick_date_time` |
| `entry.odds` | `{entry_decimal_odds, entry_american_odds}` |
| `entry.line` | `line` |
| `entry.edge` | `computeEdge(probability, entry_decimal_odds)` (display basis; the record's `entry_edge` may be on the probability basis) |
| `entry.stake_units` | `stake_units` |
| `entry.source` | `odds_source_kind`, `entry_bookmaker_id`, display name; AU ⇒ market average; null when locked |
| `current` | null when `observed_at` is null; else `{odds: current_*_odds or null, line: current_line, edge: deriveCurrentEdge(...), source: from current_odds_source_kind/current_bookmaker_id (null when locked), observed_at, is_closing}` |
| `edge_holds_above` | `edgeHoldsAbove({probability, basis: edge_basis, threshold: edge_threshold})` |
| `edge_state` | `deriveEdgeState(...)`; compare with `edge_status`, report mismatch |
| `status`, `result` | `mapProducerStatus(pick_status, outcome)`; `withdrawn` ⇒ legacy block instead (the pick should not be listed) |
| `status_reason` | code + `STATUS_REASON_MESSAGES[code]` |

### A.3 Producer record → injected top-level pick (BE-11, P4)

Inject a cancelled v4 record when its `pick_id` is not in the list and its game is in the response. Injection runs after the free-user step and **before** `attachEdgePicks` (§5.1 step ②), so injected picks are excluded from the free-user ranking, never change `locks`, and get their blocks redacted and validated by the same `attachEdgePicks` pass. Recompute `body.count` after injecting.

| Top-level field | Source |
| --- | --- |
| `id` | `pick_id` |
| `type` | `"player"` for player picks, else `"match"` |
| `bet_type` | canonical tokens as listed NBA picks use them: `h2h_t1`/`h2h_t2`, `spread_t1`/`spread_t2`, `total_over`/`total_under`, `draw`, `btts_yes`/`btts_no`, `player_over`/`player_under`/`player_yes`/`player_no` |
| `market`, `selection`, `line` | canonical values (`h2h`/`spread`/`total`/`prop`, `t1`/`t2`/`over`/`under`, line) so the app's title heuristic works |
| `league`, `region`, `game_sk`, `game_datetime`, `game` | schedule row, as the route maps listed picks |
| `gameInfo`, `matchInfo`, `status` | `getGameInfo`, `getMatchInfo`, `getDisplayGameStatus`, as today |
| `pickDescription` | composed: team short name + line ("Celtics -4.5"), "Over 224.5", player name + side + line + stat label |
| `pick_team_sk`, `pick_team_name`, `team_sk`, `team_full_name` | record `team_sk` + schedule names |
| `player_sk`, `player_full_name`, `stat`, `stat_name` | record + the game's player documents |
| `probability`, `decimal_odds`, `american_odds`, `market_odds`, `stake` | record entry values |
| `bookmaker` | `[{ name, bet_line, bet_odds: { decimal_odds, american_odds }, bet_stake }]` |
| `pick_status` | `"cancelled"` |
| `locked` | free user and game not completed ⇒ `true`; otherwise absent |
| `edge_pick` | v4 block, status `cancelled`, redacted by the same `attachEdgePicks` rule |

For a locked injected pick, apply `stripAsLockedTopPick` (the same policy and game redaction as listed locked picks) before attaching the block.

### A.4 Legacy lifecycle (`legacyLifecycle`)

Inputs: the pick's `pickOutcome` (0, 1, 2 or null; from `bookmaker.bet_outcome`, string-safe), the raw `game.outcome.game_status` (dev words: `Scheduled`, `Completed`, `Postponed`, `Cancelled`; legacy bypass words also include `Canceled`, `Abandoned`), the market and line (A.5), `game_datetime`, `now`.

| Condition, first match wins | `status` | `result` | `status_reason` |
| --- | --- | --- | --- |
| Raw status `Cancelled`, `Canceled` or `Abandoned` | `void` | `void` | `game_void` |
| `pickOutcome` 1 | `settled` | `won` | null |
| `pickOutcome` 0 | `settled` | `lost` | null |
| `pickOutcome` 2, and the market has a line (spread, total, over/under player prop) that is a whole number | `settled` | `push` | null |
| `pickOutcome` 2, otherwise | `void` | `void` | null |
| Raw status `Postponed` | `open` (D7) | null | null |
| `now ≥ game_datetime` | `awaiting_result` | null | null |
| otherwise | `open` | null | null |

Legacy `cancelled` picks never reach the route (the funnel drops them), so legacy blocks are never cancelled.

### A.5 Legacy selection mapping (`legacy-selection.ts`)

On v3 picks, `type` is `"match"` or `"player"`; the legacy type is in **`bet_type`** (`top-pick.ts:345-346, 746-747`, `canonical/picks.ts:467-468`). Schedule `team_1` is home (`t1`), `team_2` away (`t2`).

| Family | Fields on the v3 pick | `market` | `side` | `line` |
| --- | --- | --- | --- | --- |
| NBA canonical game | `market` `h2h`/`spread`/`total`, `selection` `t1`/`t2`/`over`/`under`, `line` | moneyline / spread / total | `t1` ⇒ home, `t2` ⇒ away; over/under | `line` (already signed) |
| NBA canonical player | `market` `prop`, `selection` over/under, `line`, `stat` | player_prop | over/under | `line` |
| NBA canonical milestone | `bet_type` `player_milestone`, `threshold_k`, `line: null` | player_prop | over | `threshold_k − 0.5` (contract §7.2) |
| Format A moneyline | `bet_type` `H2H`; `bookmaker.bet_line` `T1_h2h`/`T2_h2h` when set, else the `code` prefix (`T2_null_2.15` ⇒ `T2`; real seed `37_H2H` has `bet_line: null`) | moneyline | `T1` ⇒ home, `T2` ⇒ away | null |
| Format A total | `bet_type` `higher_TP` / `lower_TP`; line from `code` (`Over_222.5_1.9` ⇒ 222.5), else `bookmaker.position` | total | `higher_TP` ⇒ over, `lower_TP` ⇒ under | number |
| Format A spread | `bet_type` `FAV_SPR<`, `FAV_SPR>`, `UD_SPR<`, `UD_SPR>`, `spread_fav`, `spread_dog`; side **and** line from `code` (`T1_-6.5_1.91` ⇒ `T1`, −6.5); only when `code` is missing, the `bet_line` prefix and `bookmaker.position` | spread | `T1` ⇒ home, `T2` ⇒ away | the `code` line as written; an unsigned value is positive (`T1_9.5_1.95` ⇒ +9.5) |
| Format A draw, BTTS | `bet_type` `DRAW`, `BTTS_YES`, `BTTS_NO` | draw / btts | draw / yes / no | null |
| Format A player | `bet_type` `player_over`/`player_under`/`player_yes`/`player_no`, `stat`, `position` | player_prop | over/under/yes/no | numeric `position`; null for yes/no |

**Why `code` first:** the card's `pickDescription` for Format A game picks is built from `code` (`generateBetTypeDescription`, `top-pick.ts:165-260`: team from the `T1`/`T2` prefix, line as written with `+` added when unsigned), so the block must agree with what the card already says. The data is not self-consistent: seed `2002_FAV_SPR_us` has a signed `position` `"-6.5"`, and the real export `31679_FAV_SPR<` has `code` `T1_9.5_1.95` but `bet_line` `T2_spread_under`. Never derive a sign from the `FAV`/`UD` token. `resolveBookmakerBetLine` returns only `bet_line` (no fallback), so implement the `code` fallback in `legacy-selection.ts`. Format A `player_yes`/`player_no` (e.g. NFL anytime touchdown) map to yes/no with no line, per the producer contract (§7.3), even though the seed's `position` is 0.5; the BFF's own description omits the line for these (`top-pick.ts:485`).

Anything else is unmappable: legacy block only, `selection` stays null and `entry.line` null. Per-league tokens: `src/lib/helpers.ts` (`BET_TYPES`), `docs/NFL/pick-mapping.md`, `docs/EPL/schema-diff-*.md`.

### B. Examples

**v4 open spread, subscriber** (inside today's pick object):

```json
"edge_pick": {
  "era": "v4", "status": "open", "status_reason": null, "result": null,
  "picked_at": "2026-10-25T13:05:00.000Z",
  "selection": { "market": "spread", "side": "home", "line": -3.5, "stat_code": null },
  "probability": 0.55,
  "entry": { "odds": { "decimal": 2.0, "american": 100 }, "line": -3.5, "edge": 0.1, "stake_units": 2,
             "source": { "kind": "bookmaker", "id": "draftkings", "name": "DraftKings" } },
  "current": { "odds": { "decimal": 1.95, "american": -105 }, "line": -3.5, "edge": 0.0725,
               "source": { "kind": "bookmaker", "id": "draftkings", "name": "DraftKings" },
               "observed_at": "2026-10-25T18:40:00.000Z", "is_closing": false },
  "edge_holds_above": { "decimal": 1.8181, "american": -122 },
  "edge_state": "live", "overlay_key": null, "action": null,
  "access": { "locked": false, "hidden": [] }
}
```

**Same pick, free user, locked** (sport enabled; `show_market_odds` true, other flags false):

```json
"edge_pick": {
  "era": "v4", "status": "open", "status_reason": null, "result": null,
  "picked_at": "2026-10-25T13:05:00.000Z",
  "selection": null, "probability": null,
  "entry": { "odds": { "decimal": 2.0, "american": 100 }, "line": null, "edge": null, "stake_units": null,
             "source": null },
  "current": { "odds": { "decimal": 1.95, "american": -105 }, "line": null, "edge": null,
               "source": null, "observed_at": "2026-10-25T18:40:00.000Z", "is_closing": false },
  "edge_holds_above": null, "edge_state": "unknown", "overlay_key": null, "action": null,
  "access": { "locked": true, "hidden": ["selection", "probability", "stake", "edge"] }
}
```

**Legacy settled moneyline** (before the league's v4 start; AU; American as written in the document):

```json
"edge_pick": {
  "era": "legacy", "status": "settled", "status_reason": null, "result": "won",
  "picked_at": null, "selection": { "market": "moneyline", "side": "home", "line": null, "stat_code": null },
  "probability": 0.62,
  "entry": { "odds": { "decimal": 1.85, "american": -118 }, "line": null, "edge": 0.147, "stake_units": 1,
             "source": { "kind": "market_average", "id": null, "name": "Avg. Odds" } },
  "current": null, "edge_holds_above": null, "edge_state": "unknown", "overlay_key": null, "action": null,
  "access": { "locked": false, "hidden": [] }
}
```

**v4 cancelled** (injected in P4, or the mock `cancelled` scenario):

```json
"edge_pick": {
  "era": "v4", "status": "cancelled",
  "status_reason": { "code": "probability_moved", "message": "Our model no longer backs this pick, so we cancelled it before the game." },
  "result": null, "picked_at": "2026-10-25T14:02:10.500Z",
  "selection": { "market": "moneyline", "side": "away", "line": null, "stat_code": null },
  "probability": 0.48,
  "entry": { "odds": { "decimal": 2.25, "american": 125 }, "line": null, "edge": 0.08, "stake_units": 1,
             "source": { "kind": "bookmaker", "id": "draftkings", "name": "DraftKings" } },
  "current": { "odds": { "decimal": 2.05, "american": 105 }, "line": null, "edge": -0.016,
               "source": { "kind": "bookmaker", "id": "draftkings", "name": "DraftKings" },
               "observed_at": "2026-10-25T18:41:00.000Z", "is_closing": false },
  "edge_holds_above": { "decimal": 2.0833, "american": 108 },
  "edge_state": "closed", "overlay_key": null, "action": null,
  "access": { "locked": false, "hidden": [] }
}
```

### C. References

- Decision: [delivery-options.md](delivery-options.md) (options A and B, pros and cons, round-trip anomalies).
- Coexistence and contracts: `edgepicks-redesign/staging/kdds.md` (KDD-001…003), `bff-to-app-contract.md` (formulas, groups, vectors), `conf-schema-contracts.md` (producer record), `coexistence-approach.md` (KDD-002 prerequisites P1–P9), `kdd23-design.md` (option A design; to be updated).
- BFF: `src/functions/matches-top-predictions-v3.ts`, `src/lib/match/common.ts`, `src/freemium/apply/top-picks.ts`, `src/freemium/apply/completed-bypass.ts`, `src/freemium/resolve/locked-pick-response.ts`, `src/freemium/registry/strip-helpers.ts`, `src/freemium/cache/*`, `src/lib/middleware/entitlement-middleware.ts`, `src/lib/my-pick/*`, `src/functions/my-picks-*.ts`, `src/lib/helpers.ts`, `src/lib/edge-picks/*`, `src/contracts/edge-picks/*`, `docs/nba-2026-bff-handover.md` §6.
- App: `app/screens/TopPicksScreen/*` (XTP-125), `app/screens/GameScreen/_components/GamePick.tsx`, `app/context/PickSelectionContext.tsx`, `app/components/MyPicks/MyPicksItem.tsx`, `app/screens/MyPicksScreen/components/*`, `app/services/myPicks/myPicks.service.ts`, `app/hooks/useAppConfig.ts`.
- Data: `reqs/nba/tools/` (dev NBA data and generators), `mobile-server/script/db-seeds/`.

---

## 14. Implementation status (mobile-server, branch `feat/edge-picks-v7`)

P1 and P2 are implemented and tested; nothing is committed or deployed. P4 is not built (below). Where the code differs from this plan, the code is right and this section says why.

### 14.1 Done

| Phase | What | Where |
| --- | --- | --- |
| P1 | v7 gate, `edge_pick` block, `edge_pick_meta`, legacy and mock sources, redaction, settings, kill switch, mock generator, samples, JSON Schema | `src/lib/edge-picks/v7/`, `src/contracts/edge-picks/`, `src/functions/matches-top-predictions-v3.ts`, `docs/edge-picks-v7/` |
| P2 | MP-1 to MP-8, the backfill and re-subscribe jobs | `src/lib/my-pick/` (`capture-snapshot.ts`, `leg.ts`, `backfill.ts`, `snapshot.ts`, `resolve-my-picks-list.ts`, `my-pick.ts`), `src/freemium/apply/my-picks.ts`, `src/functions/my-picks-*.ts`, `src/lib/follow-topic.ts`, `script/my-picks/backfill-snapshots.ts`, `script/follows/resubscribe.ts` |
| Tests | Every catalogue row for P1 and P2 (V-UNIT, V-MOCK, V-INV, V-SEC, V-CACHE, V-ERR, V-REG, V-RT) | `src/functions/__tests__/matches-top-predictions-v7.test.ts`, `my-picks-slip-safety.test.ts`, `matches-v7-regression.test.ts`, `src/lib/edge-picks/v7/__tests__/`, `src/lib/my-pick/__tests__/`, `src/contracts/edge-picks/__tests__/` |

The full suite passes (149 suites, 1,739 tests). The two security tests were checked by mutation: with the entitlement check on capture removed, five tests fail; with owner visibility removed, two fail.

### 14.2 Not done

- **P4:** the Cosmos record source (`EDGE_PICK_SOURCE=cosmos` logs "not built yet" and behaves as `none`), cancelled-pick injection (BE-11), BE-9 and BE-10, the L2 seeded records container, per-league live. They depend on the data engineering deliverables (KDD-001 container). MP-5 (f) waits for BE-10.
- **MP-3 and MP-7 jobs have not been run** in dev or tst (no environment access from this session). Both default to a dry run.
- **Docs:** `kdd23-design.md` and KDD-003 still describe option A.

### 14.3 Deviations from the plan

| Area | Plan | Implemented | Why |
| --- | --- | --- | --- |
| Legacy `entry.stake_units` | A number | Null when the legacy pick has no stake | Real legacy picks often have none (see §4.3) |
| Mock guard | "Production forces `none`" | Fail-closed: the mock needs positive evidence of a non-production environment (`NODE_ENV=test`, `EDGE_PICK_ENVIRONMENT` of dev, local, test, tst or stg, or such a marker in the database or Firebase project name); `prod` vetoes it | A missing setting must not turn the mock on in production |
| Cache bypass | Not specified | `withFreemiumResponseCache` takes `bypassCache`; an honoured mock-parameter request sets it | V-SEC-2: such a request is neither served from nor written to the cache |
| Mock scenarios | Nine required, then weighted | Plus an `unfinished` scenario for `edge-picks-v4` | The universal leak sweep requires every entitlement-gated endpoint to have a case |
| `settled_push` | Pushes at the picks' own lines | The mock rounds a completed pick's line to a whole number | Every dev line is x.5, so no push could occur |
| Mock time | Exact clock | Observation time is quantised to a 5-minute bucket | Determinism (V-MOCK-1) |
| MP-1 failure modes | v2 stores without snapshots on a failed peer load | Same. `POST /v3/my-picks` keeps its retry-then-throw and its 400 `freemium_pick_unavailable` | No new failure mode for any build |
| MP-2 unavailable row | Odds null, totals null | Also `bookmaker.bet_odds.decimal_odds: 1` and `probability: 1` | V-RT-5 (store build 1.1.66 reads them). Consequence: 1.1.66 shows the product of the other legs for a slip with an unavailable leg (it showed 0), main shows "—" |
| MP-3 region | Not specified | The job uses the stored user region (default `us`) | A user with no stored region and an AU token gets no backfill for AU picks (unresolved, counted), never wrong data |
| MP-4 | Owner sees the saved item | The item is shown as a live row with the snapshot's wager fields overlaid when its pick is still listed but locked | Known limitation: that owner also sees the pick's other live fields (such as other bookmakers' prices). A fix needs the snapshot row built beside the live one; left for the team to decide. `snapshot_captured_for` is exposed on the row (additive) |
| MP-5 (b) | `cancelled` from the producer record only | A leg on a cancelled, canceled or abandoned game is `void` | Appendix A.4 does the same for the block |
| MP-5 (d) | Void, push, cancelled at 1.0 | Also: a leg with no price makes the totals null | Honest unknown instead of 0. The legacy `v1` and `v2` My Picks branches share the builder, so a placeholder there now gives null totals as well |
| MP-8 | Signature change taking the auth user | `options.tokenRegion` (stored region, then token, then `us`) | Same order as `resolveUserRegion`, no second Cosmos read, and the existing callers' first argument is unchanged |
| MP-7 | `queue-fcm-device.ts` only | One `followTopic()` used by follow, unfollow and the device queue | The three must build the same name |

### 14.4 Found while implementing (existing behaviour, unchanged)

- **My Picks ranks unlock winners per game; the list ranks per day.** A free user can see an unlocked pick on the list that My Picks treats as unavailable (in the fixtures, one of the day's six unlocked NBA picks), so `POST /v3/my-picks` answers 400 `freemium_pick_unavailable` for it and `POST /my-picks-v2` stores it without a snapshot. The behaviour predates this work. It matters for FE-7: a free user can add such a pick to the slip but not keep it.
- **Tests that leave rows behind:** `my-picks-create`, `-delete`, `-delete-v2`, `-delete-all` and `-update-v2` fail on a second run against the same emulator, because they write fixed ids. `npm test` resets the database before and after; running jest directly needs `ts-node script/seed-test-cleanup.ts` and `script/seed-test.ts` first.
- Two lint errors remain in lines this work did not change (`target-follow.ts:65`, `target-unfollow.ts:55`, unused expressions).
