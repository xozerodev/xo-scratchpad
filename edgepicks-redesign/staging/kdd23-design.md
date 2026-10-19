# KDD-002 and KDD-003: assessment and design for the BFF and the app

Oct 20, 2026 · @Tze Liang

**Subject:** KDD-002 (old and new app versions coexist on one source of truth) and KDD-003 (the new app shows legacy and v4 picks through one response shape), in `staging/kdds.md`. Read together with the snapshot API contract (`staging/bff-to-app-contract.md`) and `coexistence-approach.md`.

**Method:** read against the code as it stands:
- mobile-server `develop` at `fffcc9e`, including the uncommitted v4 work in that working tree (`src/functions/edge-picks-v4.ts`, `src/lib/edge-picks/`, `src/contracts/edge-picks/`);
- mobile-app `main` at `137f2f61`, plus `origin/develop`, the branch `origin/feat/XTP-125-Edge-Picks-Redesign-Oct26` and the untracked `app/services/edgePicks/type.ts`.

`origin/develop` of mobile-server has moved to `e25c6ff` and was not fetched, so check the citations below against it before building.

---

## 1. Verdict

**KDD-002 and KDD-003 fit together and are the right pair.** KDD-002 keeps older builds on today's documents. KDD-003 lets the new build ship before any league has v4 records. Most of what they need already exists in the code: the v4 route, its contract types, free-user locking, the legacy readers and the release gate. Five things have to change before they work as written:

1. **The BFF's contract code is an older draft than the contract page.** `v4.schema.ts` still has `odds_source`, `edge_threshold`, status `locked`, edge states `available` and `gone`, and no `overlay_key`, `push`, `current.source` or `era`. The app's untracked `type.ts` copies that older draft. Bring both into line with the 4.0.0 draft and add `era` before building anything else (§4.1).
2. **The BFF should decide a game's era from the data, not from a date.** KDD-003 point 2 makes the BFF apply the league's v4 start date. The Publish Engine already decides which games get records. The coexistence assessment recommends it pin by first publish rather than by start date, and the BFF cannot see first publish. If the BFF instead treats a game as v4 when it has producer records (and the league's switch is on), the two systems can never disagree. Because KDD-002 point 8 gives derived documents the same ids, a game whose records arrive late changes era without changing its ids (§4.3).
3. **Some contract rules don't fit legacy picks.** Legacy documents break three of them:
   - **`picked_at`** must never change, but a legacy pick's timestamp is the latest engine run's.
   - **Persistence:** a pick, once served, must be served until graded. Legacy documents drop picks on line moves and re-runs.
   - **Partial responses:** the app drops any pick a newer response leaves out. A response missing one source would make that source's picks disappear.

   Each needs an explicit rule (§4.2, §4.7).
4. **Pick ids reveal the pick to free users.** The contract never hides `id`. NBA and v4 ids contain the market, side and line (`…|spread_t1|t1|-4.5|…`), so a locked pick's id gives away what it backs. Legacy routes have the same leak today. The v4 contract's free-user rule makes the leak explicit, and it needs a decision (§4.6).
5. **The v4 route has no `api_version` handling.** `edge-picks-v4.ts` installs no `apiVersionMiddleware`. Any reuse of the legacy choosers would then withhold every staged league (`nba:2026` in dev and tst) from every caller, because no version context counts as the oldest version (`gate.ts:87-93`).

The app side is mostly new code. The Edge Picks tab exists, but nothing calls `/v4/edge-picks`, pick data is untyped (`[key: string]: any`), and slips, follows and the moneyline rule all read legacy field names. The design gives the app one adapter from a v4 pick to those inputs, so it does not need a second parser (§5).

**What it buys:** the app can launch on an all-legacy BFF as soon as the legacy translators exist, before the bet engine and Publish Engine deliver v4 records. Each league then moves to v4 on its own, with no app change.

---

## 2. KDD-002 and KDD-003 in brief

| | KDD-002 | KDD-003 |
| --- | --- | --- |
| Problem | Older builds can't be forced to update, and a second pipeline would drift | The new app has to work for every league, whichever stage the league is at |
| Decision | The Publish Engine derives legacy documents from v4 records under the same pick ids (Stage A). The BFF moves legacy routes to adapters later (Stage B) | `/v4/edge-picks` serves legacy picks translated into the snapshot shape, marked `era: legacy`. The app draws a limited card for them |
| Who builds | Mostly data engineering and the Publish Engine; the BFF only for Stage B | Mostly the BFF and the app |
| What it leans on from the other | — | Point 6 (switch fallback) needs derived documents under v4 ids (KDD-002 point 8). Point 8 (saved ids) needs legacy ids to stay unchanged |

KDD-003 doesn't depend on KDD-002 being finished. With no league on v4, KDD-003 is just "translate today's documents". KDD-002 only matters to KDD-003 when a league switches over, and then only through ids and the switch fallback.

The coexistence assessment (`coexistence-approach.md`) lists KDD-002's prerequisites P1 to P9: first-publish pinning, `c-outcome` results, the release gate's `season` field, slip snapshots and the others. They stand, and this document doesn't repeat them. Three of them affect the new app directly:
- **P3:** slips saved without a snapshot go blank when their pick leaves the documents.
- **P4:** first-publish pinning, which §4.3 builds on.
- **P6:** the follow-topic `|` bug, which hits every v4 id in both builds.

---

## 3. What the code looks like today

### 3.1 BFF (mobile-server)

| Area | State | Evidence |
| --- | --- | --- |
| `/v4/edge-picks` | The route exists with middleware for errors, auth and entitlement. It validates the whole response with zod, and one bad pick returns a 500. `EDGE_PICKS_SOURCE=mock` serves fixtures. `live` throws `EdgePicksLiveUnavailableError` (503). `EDGE_PICKS_LIVE_SPORTS` limits which sports are served. **Not committed**: untracked in the develop working tree | `src/functions/edge-picks-v4.ts:76-162`, `src/lib/edge-picks/source.ts` |
| Contract types | zod schema at 4.0.0, older than the contract page (§4.1). `script/export-edge-picks-contract.ts` exports the JSON Schema and sample responses to `docs/edge-picks-v4/` | `src/contracts/edge-picks/v4.schema.ts` |
| Derived values | Edge (`p × d − 1`), threshold, current edge, odds conversion, engine status and outcome mapping, reason copy | `src/contracts/edge-picks/derive.ts` |
| Free-user access | Field groups mapped to `show_*` flags. Unlock-N per sport over the whole day, ranked by `model.probability`. Completed picks unlocked. Fields nulled after the pick is built. **No** two-of-three leak rule yet | `src/lib/edge-picks/access.ts:125-163` |
| Ordering | Game start, then entry edge. **No** id tie-break | `src/lib/edge-picks/order.ts` |
| Legacy pick funnel | `getAllAvailableTopPicksForGame` serves seven callers. Per game, NBA `game_edge_picks` / `player_edge_picks` win; Format A `top_picks` / `player_top_picks` are the fallback. Drops `cancelled`. Output is display-shaped `any` | `src/lib/match/common.ts:133-253` |
| Document choosers | `pickDoc` (last of a doc type), `choosePredictionDoc`, `choosePlayerDocs`, `visibleDocs`, `groupByGameSk` | `src/lib/match/canonical/docs.ts` |
| Today's Edge Picks list | `GET /v3/matches/:date/top-predictions`. Day window `T00:00:00` to `T23:59:59`, shifted by the offset (−12 to 14). `game_sk IN (…)` matches only numeric ids | `src/functions/matches-top-predictions-v3.ts:92-181` |
| Release gate | `STAGED_LEAGUES` (env) and `RELEASE_API_VERSION_MAJOR = 6` (a constant). No version context means withheld | `src/lib/match/canonical/gate.ts:69-93`, `middleware/api-version-middleware.ts` |
| League configuration | No registry. Settings are scattered across env vars (in Terraform `app_settings.tf`), `LEAGUE_PARSER_RULES` and `FreemiumSportKey`. A Redis runtime switch exists as precedent (`mvm-switch.ts`) | |
| Caching | Redis response cache for free users only: 60 s, no single-flight, endpoint union limited to `v3-matches` and `v3-top-predictions`. In-memory and Redis `getOrLoad` for entitlement and freemium config. **No Redis locks. No ETag or 304 anywhere** | `src/freemium/cache/response-cache*.ts`, `src/lib/redis.ts` |
| Monitoring | `console.warn` traces picked up by the Functions host. `alertMissingContent` with 30-minute de-duplication is the house pattern for content gaps | `src/lib/match/canonical/alerts.ts:22-67` |
| Tests | jest against a seeded Cosmos emulator. Seeds in `src/scenarios/*` and `script/db-seeds/*.json` | `jest.config.ts`, `src/test-setup.ts` |

### 3.2 App (mobile-app)

| Area | State | Evidence |
| --- | --- | --- |
| Screen | The `topPicks` tab is labelled "Edge Picks". `TopPicksScreen` → `useTopPredictions` → `/v3/matches/:date/top-predictions?offset&api_version`. Filters by league and kind (all, player, game) and sorts on the device | `TabsNavigator.tsx:231-235`, `topPredictions.hook.ts` |
| Card | `TopPickCard.tsx` (522 lines). The live pill comes from game `status === "InProgress"` | `TopPickHeaderRow.tsx:37` |
| Types | Untyped (`TopPredictions { [key: string]: any }`). No zod, no generated client. The untracked `app/services/edgePicks/type.ts` hand-copies the BFF's older v4 draft and has no `era` | `topPredictions/type.ts:18-20` |
| Transport | apisauce with a 10 s timeout and a bearer token per call. Retries once after a token refresh. **No ETag handling.** TanStack Query with `staleTime` 60 s and refetch on focus. **No polling** | `services/api/index.ts:21,83-175`, `app.tsx:260-266` |
| api_version | `DEFAULT_API_VERSION = "v6"`, hardcoded. The server's `/config.api_version` is ignored. The time-zone offset is sent as `offset`, not `tz_offset` | `useAppConfig.ts:42`, `AppConfigContext.tsx:48` |
| Free users | List-level `locks` plus item `locked`, applied by blurring. Add Pick is disabled for every free user | `resolveLocks.ts:35-58`, `TopPickCard.tsx:311` |
| Slip | `POST /my-picks-v2` with `{id, predictionId, gameId}`, where `id = predictionId = pick.id`. Combined odds come from `newOdds.decimal_odds` | `PickSelectionContext.tsx:151-172` |
| Moneyline rule | `isH2hPick`: `bet_type` is `h2h`, or the id contains `h2h`. `GamePick.tsx:68` and `GameCard.tsx:111-119` copy the rule | `utils.ts:263-272` |
| Follows | Key `${prediction_type.toLowerCase()}:${id}`. targetType is `match` or `player` | `TopPicksList.tsx:94-95` |
| Remote switches | `GET /config` (`enable_top_picks` affects only GamesScreen), MVM enabled, `ForceUpdateGate`. No general feature-flag system | `useAppConfig.ts`, `ForceUpdateGate.tsx` |
| Realtime | None: no Firestore, Realtime Database or sockets. FCM is used for notifications only | `package.json:42-46` |
| Parallel work | Branch XTP-125 adds a placeholder `EdgePicksCard` into `TopPicksList`. It still takes the legacy `TopPickCardData` | `origin/feat/XTP-125-…` (d9ed31d6) |

---

## 4. BFF design

### 4.1 Step zero: one contract, in code, on both sides

1. **Commit the v4 work** that is untracked on develop.
2. **Bring `v4.schema.ts` into line with the 4.0.0 contract page:**
   - `entry.source` replaces `odds_source`;
   - `edge_holds_above` replaces `edge_threshold`;
   - add `overlay_key`, `current.source`, `current.observed_at` and `current.is_closing` (in place of `updated_at`);
   - status `awaiting_result` replaces `locked`;
   - result gains `push`;
   - edge states become live, narrowing, closed, suspended and unknown;
   - game states gain `delayed` and `interrupted`;
   - `tz_offset` accepts fractions;
   - error bodies follow the contract.
3. **Add the KDD-003 field and its null rules** (§4.2).
4. **Rebuild the mock fixtures and the test vectors (E1–E13, D-1–D-11, W-1–W-2) against the new schema.** The vectors become CI tests.
5. **Export the JSON Schema** with `script/export-edge-picks-contract.ts`. The app generates its types from that file (§5.1), so nobody keeps the app's types in step by hand.

### 4.2 Contract additions for KDD-003

| Field or rule | Proposal | Why |
| --- | --- | --- |
| `era` | Required, `legacy` or `v4`. **An unknown value is handled as `legacy`**, which shows less | KDD-003 point 4. A safe fallback for a future value |
| Null rules when `era` is `legacy` | `current`, `edge_holds_above`, `overlay_key` and `action` are null. `edge_state` is `unknown`. `status_reason` is null unless `game_void`. `model.projection` is null (4.0) | KDD-003 point 5. The schema checks it with an `if era = legacy then …` clause |
| `picked_at` | **Nullable, null exactly when `era` is `legacy`** | The contract defines `picked_at` as first publish, never changing. A legacy document's timestamp is the latest run's, so sending it would break that rule. KDD-003 already says the card shows no time for legacy picks |
| Persistence rule | Add: "A pick with `era` `legacy` can stop appearing before it is graded, because its source documents drop picks; the app drops it like any pick a newer response no longer contains" | The current exception covers only withdrawn picks |
| `status` for legacy | `open` before the start. `awaiting_result` after it, while ungraded. `settled` with `won` or `lost` from `bet_outcome` 1 or 0. `void` with result `void` from `bet_outcome` 2, or when the game is postponed or cancelled (reason `game_void`). Legacy `cancelled` is **left out**, as every legacy route leaves it out | Legacy `2` can't tell push from void. The payout is the same (stake back). Older builds already hide cancelled picks, and NFL reinstates some |

The `era` change is additive, but the contract is still a draft, so it goes into 4.0.0 rather than 4.1.

### 4.3 Era resolution: data decides, the switch can only downgrade

```
era(game) = v4      if the league's v4 switch is on AND the pick store has ≥1 record for (region, game_sk)
          = legacy  otherwise (picks come from today's documents: legacy-native or derived)
```

- **The bet engine and Publish Engine own "which games are v4".** They own the v4 start date and the first-publish pin (assessment I1, P4). The BFF reads only the outcome: whether records exist. It holds no copy of the date, so it can never disagree with the Publish Engine. That is KDD-002's C1 rule ("never disagree about a game's family") enforced by construction rather than by sharing a configuration.
- **A late record is harmless.** A v4-era game whose records are not written yet shows its derived documents as legacy picks. When the records land, the same ids get full cards (KDD-002 point 8).
- **The switch is one-way.** Turning it off makes v4 games fall back to their derived documents (KDD-003 point 6). Turning it on can't make a legacy game v4, because legacy games have no records.
- **Guard rails, which alert only and never change the era:**
  - A game has records and also legacy documents not derived from records. This needs derived documents to carry a document-level marker such as `source_family: "v4"`. Older readers ignore it, because it is added at document level, outside any pick that `canonical/picks.ts` spreads.
  - A game has records but starts more than the league's publish horizon before the configured v4 date.
- **One loss in fallback.** Format A leagues hold one game pick per region in `game_prediction.top_picks`. With the switch off, a v4 game in such a league shows only the slot pick; the other game picks disappear until the switch is back on. NBA's array documents lose nothing. Product should know this before it uses the switch.

This **amends KDD-003 point 2**: "the era is set per game by the league's v4 start date" becomes "the era is set per game by whether the Publish Engine has written records for it, and the start date is the Publish Engine's rule". Record this in KDD-003 before it is accepted.

### 4.4 League registry and switch

There is no registry today. Add one small module, `src/lib/edge-picks/leagues.ts`, as the only place league state is read for this route:

| Setting | Home | Purpose |
| --- | --- | --- |
| `EDGE_PICKS_SOURCE` | Env (exists) | `mock` or `live`. Unchanged |
| `EDGE_PICKS_V4_LEAGUES` | Env, Terraform `app_settings.tf`, parsed like `STAGED_LEAGUES` (`nba,nfl`) | Baseline: leagues whose v4 switch is on. **Replaces `EDGE_PICKS_LIVE_SPORTS`**. Under KDD-003 every sport is served; this only turns on v4 cards |
| `edge-picks:v4-off:<league>` | Redis, after the `mvm-switch.ts` pattern. Fails open to the env baseline | Kill switch that acts in seconds, without a Terraform change. It can only turn v4 **off** |
| `source_family` marker | Document field written by the Publish Engine | Guard-rail alerts only (§4.3) |

The v4 start date stays a Publish Engine setting. If it later moves into the shared registry from the co-existence plan, the BFF reads it only for the guard-rail alert.

### 4.5 The read path

```
GET /v4/edge-picks?date&tz_offset&sport&api_version
  │  globalError → auth → apiVersion("v1") → entitlement            (add apiVersion: §1 point 5)
  ▼
① day window [local midnight, next local midnight) from date + tz_offset (contract W-1/W-2)
② schedule (c-sch): games in the window, release gate applied (scheduleLeagueFilterSql)
③ in parallel, per region:
     a. PickRecordSource   → shared cache, keyed by region and game_sk → new container (KDD-001)
     b. LegacyPickSource   → shared cache, keyed by region and game_sk → c-wltp / c-ps documents
④ per game: era(game) → take drafts from (a) or (b), never both
⑤ finalise(draft): entry.edge, edge_holds_above, edge_state, overlay_key, labels, AU wording
⑥ per-pick schema check → drop and report failures
⑦ applyEdgePickAccess (one path, both eras) → order (start, edge, id)
⑧ ETag over body minus generated_at → 304 or 200
```

**Internal model.** Both sources produce a `PickDraft`: the snapshot pick before access and before derived fields, plus internal-only fields that never leave the server: `era`, `basis` and `threshold` (v4 only), the unrounded entry decimal, and `legacy_family` for reporting. Derived numbers are computed once, in `finalise`, for both eras. That is what makes "everything else is one code path" (KDD-003 point 7) true in the code.

**PickRecordSource** (v4) is KDD-001's guardrail 1. It reads producer records for the day's `game_sk` values from one query per region, through the shared Redis cache with a rebuild lock (§4.8). It maps records field by field (`record → PickDraft`), using `derive.ts` for odds and edge on the display basis. It drops `withdrawn`.

**LegacyPickSource** has three typed translators: NBA canonical (game and player edge picks), Format A game (`top_picks`, per league) and Format A player (`player_top_picks`). They follow the KDD-003 mapping table, with three rules:
- **Choose documents exactly as the legacy routes do.** Reuse `groupByGameSk`, `pickDoc`, `choosePredictionDoc`, `choosePlayerDocs` and `visibleDocs`, and the per-game precedence (edge documents win, Format A is the fallback, `common.ts:186-246`). Then the new screen and an older build's Edge Picks list show the same set of picks, which KDD-003 validation 2 requires.
- **Don't reuse the display generators.** `generateWLTPFromEdgePicks`, `generatePlayerTopPicks` and the rest spread raw picks and return display-shaped `any`. The translators read raw fields with their own types and reuse only the classification helpers (`classifyGamePick`, `edgePickSlot`, `parseOddsNumber`, `resolve-league-rules.ts`) to find the market and side.
- **Parse loosely, emit strictly.** Accept `bet_outcome` as `"1.0"`, `player_sk` and `position` as a number or a string, `bookmaker` as an object or an array, `top_picks` as an object, an array or a region map, and a missing `edge` or `bet_price`. Emit only contract types.

Fields the documents don't hold and the BFF has to look up:

| Snapshot field | Gap | Proposal |
| --- | --- | --- |
| `game.home`, `away`, `label`, `state` | Not on pick documents | From the schedule row and team details (`team-details.ts`, already used by the legacy routes). Game state from the schedule status |
| `selection.label` | Legacy `pickDescription` is built for display, inconsistently | Composed by the BFF from market, side, line, team or player and stat, the same as for v4. The two eras then read alike |
| `entry.source` | Format A `bookmaker.name` can be null. Only a slug elsewhere | A bookmaker display-name map in the BFF. AU follows the region wording rule (Avg. Odds). An unknown slug is reported and the pick is served with the title-cased slug, never dropped |
| `entry.edge` | Legacy `edge` is on per-league bases, or missing | Ignored. Always computed from probability and price (KDD-003) |
| `picked_at` | Not first publish | null (§4.2) |

**What the legacy source does not include:** the BFF-minted featured moneyline pick (`h2h:` ids from `game-h2h.ts`). Today's Edge Picks list doesn't include it either (it belongs to match detail).

**Day window.** The v4 window is the contract's `[midnight, next midnight)` with fractional offsets from −14 to 14. v3 uses `T23:59:59` and −12 to 14. Use `gameSkInClause` (`my-pick.ts:39-51`), not `game_sk IN (…)`, which misses string ids. The coverage comparison (§6) has to allow for the one-second edge and the offset range.

### 4.6 Free users

Both eras use one path: `applyEdgePickAccess` on the finished pick. Three changes:

1. **Implement the two-of-three leak rule** from the contract: if the flags would hide exactly one of probability, odds or edge, hide a second as well. It is missing in `access.ts`.
2. **Decide what `id` shows on a locked pick.** Ids carry the selection (NBA and v4: market, side, line; Format A: market and side). Options:
   - (a) Accept the leak: today's routes have it, and the app never shows ids.
   - (b) **Recommended:** serve a locked pick's `id` as an opaque, stable token, `lk_` plus a truncated HMAC of the pick id with a server secret. Free users can't add picks (`TopPickCard.tsx:311`), and following a locked pick is disabled, so nothing on a locked card needs the real id. When the user subscribes, the app refetches (contract: "when the user's entitlement changes, it requests at once"), and the real ids replace the tokens.

   Either way, record it in the contract's free-user section.
3. **Unlock-N agrees across eras but not across surfaces.** v4 ranks per sport over the whole day; the legacy My Picks create path ranks peers per game and league (`apply/my-picks.ts:90-95`). The app blocks free-user saves, so no user sees the mismatch today. Note it in the freemium rules so nobody enables free saves without lining the two up.

### 4.7 Failures and reporting

- **A source failure fails the response, never part of it.** If the schedule, the pick store or the legacy containers fail, return 503 `unavailable`. The app keeps its last response, marked as not updated. Serving only the sources that answered would make the app drop every pick from the missing source, because the contract tells it to drop picks a newer response leaves out.
- **One bad pick drops one pick.** Replace today's whole-response 500 (`edge-picks-v4.ts:145-149`) with a check on each pick. A pick that fails is left out and reported, and the response check stays as a final guard. Report through a `reportUnmappablePick(family, league, pickId, reason)` that follows `alertMissingContent`: structured `console.warn` with 30-minute de-duplication per (family, league, reason). That report is what KDD-003's coverage criterion counts.
- **Omission must be deterministic.** A pick that fails must fail on every request, or it flickers in and out of the app. The translators are pure functions of the documents, so this holds as long as no translator reads the clock.

### 4.8 Caching, ETag and cost

| Layer | Key | Contents | Lifetime |
| --- | --- | --- | --- |
| Pick records (KDD-001 guardrail 1) | `ep:rec:{region}:{game_sk}` | Producer records, before redaction | Rebuilt at most every 60 s under a lock |
| Legacy drafts (new) | `ep:leg:{region}:{game_sk}:{released}` | Translated `PickDraft`s, before redaction. `released` is the release-gate outcome for the request, because staged documents differ by version | 60 s, rebuilt under a lock |
| Per instance | `getOrLoad` in memory, in front of both | Same | A few seconds. Absorbs bursts and covers Redis being down |
| Response | — | Not cached. The response is per user (contract: shared caches must not store it) | — |

- **Rebuild lock (new).** `SET ep:lock:<key> <instance> NX PX 10000`. The winner rebuilds; the others wait briefly and then serve the previous value. Redis is optional in this codebase, so if Redis is down, fail open to the per-instance cache and read Cosmos directly. That costs more but stays correct.
- **The switch is not in any cache key.** Both caches hold their source's drafts whatever the switch says, and the era is chosen when the response is assembled (§4.5 step ④). A switch flip therefore takes effect on the next request, with no flush. That covers the co-existence plan's C9 for this route.
- **ETag (new to the BFF).** A strong ETag is a hash of the serialised body without `generated_at`, computed after redaction and ordering. `If-None-Match` gives 304. It saves bandwidth and app rendering, not server work. A content version per cache key, combined with the user's access fingerprint, could make 304s cheap later; skip it in the first release.
- **Cost.** The legacy cache holds a region-day's documents once per minute for all users, instead of today's per-request reads (free users have a 60 s body cache; subscribers have none). It should cost less than v3's top-predictions route at the same traffic. The pick-record figures are KDD-001's.

### 4.9 BFF work items

| # | Item | Depends on |
| --- | --- | --- |
| B1 | Commit the v4 work; align the schema with 4.0.0; add `era` and the null rules; test vectors in CI; export the JSON Schema | — |
| B2 | `apiVersionMiddleware("v1")` on the route; release-gate test for a staged league at v5 and v6 | B1 |
| B3 | `PickDraft`, `finalise`, per-pick check, `reportUnmappablePick`, all-or-nothing source failure | B1 |
| B4 | LegacyPickSource: schedule window, document choice, NBA and Format A translators, team and bookmaker lookups. Fixtures per family from `script/db-seeds` | B3 |
| B5 | Redis rebuild lock and the legacy draft cache | B4 |
| B6 | League registry, `EDGE_PICKS_V4_LEAGUES`, Redis kill switch, era resolution and guard-rail alerts | B3 |
| B7 | PickRecordSource and the pick-record cache (KDD-001) | B5, B6, the KDD-001 container |
| B8 | Leak rule; locked-id decision | B1 |
| B9 | ETag and 304 | B3 |
| B10 | Mock scenarios `legacy_only`, `mixed_day` and `switch_off`, so the app can build both cards before live data exists | B1 |

**Release order.** B1–B5 plus B8 and B10 let the BFF serve `EDGE_PICKS_SOURCE=live` with every league legacy. That is enough for the new app to launch. B6–B7 follow when the first league (NBA) has records in dev.

---

## 5. App design

### 5.1 Data layer

- **Types are generated from the BFF's exported JSON Schema** (`docs/edge-picks-v4/edge-picks-v4.schema.json`, through `json-schema-to-typescript`) into `app/services/edgePicks/type.ts`, replacing the hand-written untracked copy. Regenerate on every contract change.
- **Light runtime checks, not a full validator.** Accept any `contract_version` 4.x. Turn unknown enum values into their contract fallbacks in one `normaliseEdgePicks` function: unknown sport hides the pick, unknown status hides it, unknown era is treated as `legacy`, and so on. The app has no zod today. One small function of fallbacks is enough, and the BFF already validates every pick.
- **Service:** add `edgePicks` to the `APIs` route table. `getEdgePicks(date)` sends `GET /v4/edge-picks?date&tz_offset&api_version`. Note `tz_offset`, not `offset`; use the existing fractional-offset helper (`utils.ts:90-93`).
- **Hook:** `useEdgePicks(date)` with TanStack Query key `["edge-picks", date, region, apiVersion]`. Every refetch sends `If-None-Match` with the last ETag, and a 304 returns the cached data.
  - apisauce, through axios, treats 304 as an error by default. Handle status 304 explicitly.
  - Check on Android whether OkHttp's own HTTP cache turns 304s into 200s before the app sees them.
- **Refresh:** `refetchInterval: 60_000` only while the screen is focused (`useIsFocused`). Refetch on focus and pull-to-refresh as today. Invalidate the key when the entitlement changes (subscription context) and when the region changes (`invalidateRegionDependentQueries`). On a 503 or a network error, keep the last data and show "not updated".
- **Day window:** keep `PredictionsContext`'s selected date. Add a midnight rollover while the screen is open; today the date never rolls over.

### 5.2 Screen and cards

- **One screen** (`EdgePicksScreen`) behind the existing `topPicks` tab. Filters stay on the device: league from `sport`, All / Player / Game from `kind`. Use the server's order; re-sort only for display options the design asks for.
- **One card component, `EdgePickCard`, with the variant chosen from `era` and nothing else:**

| Section | v4 (`era: v4`) | Legacy (`era: legacy`) |
| --- | --- | --- |
| Header, teams, selection, status chip, result | Shared | Shared |
| Model probability, projection, stake, entry edge | Shared (lock where `access.hidden` says) | Shared |
| Entry price | "Entry" with the picked-at time | "Published price" with no time (copy from product, KDD-003 open item) |
| Current price, edge state, "Edge holds above", stale marker | Shown | Not rendered |
| Live indicator | From `game.state` and the overlay later | From `game.state` only (the game is live), never an edge indicator |
| Cancel reason | From `status_reason` | Only `game_void` |

- **Locks:** one helper, `isHidden(pick, group)`, reads `access.hidden`. A hidden field shows a lock and never a derived value. The legacy `locks` map and the blur logic stay with the old screen. (Separately, `resolveLocks.ts:53` has a `topPicks`/`edgePicks` key bug in the old screen.)
- **Realtime overlays later.** The contract leaves room for Firebase overlays on v4 picks. Build the card so a v4 market block can take updates from the overlay later, but ship the first release on polling only: the app has no Firebase data dependency yet, and `overlay_key` is still Provisional (due Nov 2). Legacy picks never subscribe (`overlay_key` is null).

### 5.3 One adapter into existing features

Slips, follows and the moneyline rule stay on their current field names. One function maps a v4 pick into them, so the old data model doesn't spread into the new screen:

| Feature | Today reads | From an `EdgePick` |
| --- | --- | --- |
| Slip item | `id`, `predictionId`, `gameId` | `pick.id`, `pick.id`, `pick.game.id`. Unchanged ids for legacy picks (KDD-003 point 8) and one id for v4 picks (KDD-002 point 8) |
| Combined odds | `newOdds.decimal_odds` | `entry.odds.decimal` (legacy: the published price) |
| Moneyline rule | `bet_type === "h2h"`, or the id contains `h2h` | Set `bet_type: "h2h"` when `selection.market === "moneyline"`. The new build then never depends on the id substring, which removes the assessment's I4 dependency for new builds |
| Follow key and target type | `${prediction_type}:${id}`, `match` or `player` | `kind` game → `match`, player → `player`, so existing follows keep their keys |
| Game detail ("More") | `gameId`, `gameDate` | `game.id`, the local date of `game.starts_at` |

Locked picks go through the same adapter. If the opaque id option is chosen (§4.6), the buttons that would use the id are already disabled for free users.

### 5.4 Rollout and kill switch in the app

- **The new build replaces the screen.** The BFF's per-league switch handles data problems: it degrades cards and never empties the screen. So the app needs no per-league logic.
- **Keep the old screen for one release behind `/config.edge_picks_v4_enabled`** (default true). It is the kill switch for a problem in the new screen itself. Wire the key through `AppConfigContext`, which today ignores server values other than the two flags it reads. Remove it once the new screen is stable.
- **api_version:** the new build sends `v6` (already the default on main), which releases staged leagues under `RELEASE_API_VERSION_MAJOR = 6`. No change is needed. The route serves only new builds, so it needs no version routing of its own.
- **Coordinate with XTP-125.** Its `EdgePicksCard` takes `TopPickCardData`. Move it onto `EdgePick` before more card work lands, or the screen will be built twice.

### 5.5 App work items

| # | Item | Depends on |
| --- | --- | --- |
| A1 | Generated types, `normaliseEdgePicks` fallbacks, service and hook (ETag, 304, focused polling, invalidation) | B1 |
| A2 | `EdgePickCard` with the v4 and legacy variants, `isHidden` locks, status and result chips; built against the B10 mock scenarios | A1, B10 |
| A3 | Adapter into slips, follows, the moneyline rule and game detail | A1 |
| A4 | `EdgePicksScreen`, filters, empty and error states, midnight rollover | A2 |
| A5 | `/config.edge_picks_v4_enabled` wired through `AppConfigContext`; the old screen kept for one release | — |
| A6 | Merge or retarget XTP-125 | — |

---

## 6. Validation

KDD-003's six validation items stand. Ways to run them, plus items they don't cover:

1. **Fixtures per legacy family.** NBA game, NBA player, and Format A game and player per league, taken from `script/db-seeds` and today's live documents. Each translation validates against the schema and matches the mapping table. Include the loose types from §4.5.
2. **Coverage harness (automated).** For a date and region, run v3 `top-predictions` and v4 in-process against the same seeded or dev data. Check that every pick id v3 lists appears in v4 as a legacy pick, or in the unmappable report. Run it nightly in dev over the past seven days to catch document drift.
3. **Era resolution.** A game with records → v4. A game with records but switch off → legacy, same ids. A game with derived documents but no records yet → legacy, then v4 once a record lands, ids unchanged. A legacy-native game → legacy whatever the switch says.
4. **Release gate.** A staged league is withheld at `api_version` v5 and released at v6 on `/v4/edge-picks`. With no `api_version`, it is withheld.
5. **Free users.** Run the leak sweep on both eras: no hidden group has a value, the leak rule holds, and a locked id reveals nothing if option (b) is chosen. Unlock-N is the same across a mixed day.
6. **Failure.** Take down each source in turn and check for a 503, never a partial body. Fault-inject a bad legacy pick: the pick is dropped, the others are served, and one report is written.
7. **Cache and switch.** With several instances, there is one rebuild per key per minute. A Redis kill-switch flip takes effect on the next request. Redis down: correct responses, higher Cosmos reads.
8. **App.** Snapshot tests of both card variants for every status and hidden-group combination. 304 handling on iOS and Android. A slip saved in the new build from a legacy pick resolves in an older build, and the reverse.

---

## 7. Proposed amendments to the KDDs

| KDD | Point | Amendment |
| --- | --- | --- |
| KDD-003 | 2 | The era is decided per game by whether producer records exist (and the switch is on). The v4 start date and the first-publish pin are the Publish Engine's (§4.3) |
| KDD-003 | 4 | An unknown `era` is handled as `legacy` |
| KDD-003 | 5 | `picked_at` is null for legacy picks. Legacy `cancelled` is left out. The status mapping is the table in §4.2 |
| KDD-003 | 7 | A failed source fails the response with 503. A bad pick is dropped and reported (§4.7) |
| KDD-003 | new | A legacy pick may stop appearing before it is graded, and the contract's persistence rule says so |
| KDD-003 | new | Format A leagues lose their non-slot game picks while the switch is off (§4.3); product accepts this, or the fallback is limited to NBA-style documents |
| KDD-003 | Open items | Add: what a locked pick's id shows (§4.6). The bookmaker display-name map and its owner |
| KDD-002 | 4 | Already amended by KDD-003. Also: the Redis kill switch only turns v4 off |
| KDD-002 | 6 | Derived documents carry a document-level `source_family: "v4"` marker (for monitoring only) |
| KDD-002 | Open items | The switch lives in BFF env plus Redis (§4.4). The v4 start date stays with the Publish Engine |

---

## 8. Risks and open items

| # | Risk or open item | Owner | Handling |
| --- | --- | --- | --- |
| R1 | The v4 BFF work is uncommitted, and `origin/develop` has moved on | BFF | Commit first (B1); recheck citations at `e25c6ff` |
| R2 | Two copies of the contract drift (Confluence page, zod, app types) | Contract owner, BFF, app | zod is the source of truth in code, the JSON Schema is exported, the app generates from it, and Confluence is rendered from it (overview "How to publish" step 1) |
| R3 | Legacy document shapes vary more than the fixtures show | BFF, data engineering | Loose parsing, the unmappable report and the nightly coverage harness |
| R4 | Locked pick ids leak the selection | Product, BFF | Decide (a) or (b) in §4.6 before launch |
| R5 | The switch fallback loses Format A non-slot game picks | Product | Accept, or block the switch for Format A leagues |
| R6 | Slips from older builds go blank when a pick leaves the documents (assessment P3) | App, BFF | Not a KDD-003 change, but it decides whether cross-version validation (§6 item 8) can pass |
| R7 | The follow-topic `|` bug hits every v4 id (assessment P6) | BFF | Fix before any league moves to v4 |
| R8 | 304 behaviour differs between iOS and Android networking stacks | App | Test early (A1). ETag is an optimisation, so fall back to plain 200s if needed |
| R9 | The XTP-125 branch builds the card on the legacy shape | App | A6 |
| R10 | Copy for the limited card ("Published price"), and whether legacy picks show an edge | Product | KDD-003 open item; due before A2 is finished |
