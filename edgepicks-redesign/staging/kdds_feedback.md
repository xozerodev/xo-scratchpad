# Critical Assessment of `kdds.md` (Edge Picks v4: Key Design Decisions)

Reviewed document:
- [kdds.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/kdds.md#L1-L288) — *Edge Picks v4: Key Design Decisions* (`KDD-001` & `KDD-002`)

Cross-checked against:
- Sibling v4 contracts: [overview.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/overview.md), [bff-to-app-contract.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/bff-to-app-contract.md), [realtime-overlays.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/realtime-overlays.md), [producers-to-bff.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/producers-to-bff.md)
- Prior storage KDD: [reqs/nba/kdd_schema.md](file:///mnt/devel/xosports/reqs/nba/kdd_schema.md#L1-L429) (*KDD-001: Split vs Combined Documents for WLTP and PS*, 13 Sep 2026)
- Live repositories: `app-data@2b6f998`, `mobile-server@develop`, `live-odds@30e05ce`

---

## 1. Executive Verdict

Both KDDs make the right strategic call:
- **KDD-001** ([kdds.md:14-138](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/kdds.md#L14-L138)) — storing one producer pick record per Cosmos document, partitioned by `/game_sk`, with the Publish Engine as the sole writer — directly solves the 7× write-amplification and full-document replace race between batch notebooks and 5-minute monitor updates.
- **KDD-002** ([kdds.md:141-244](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/kdds.md#L141-L244)) — keeping a single source of truth across old and new mobile builds via a three-stage cutover (Stage A derived legacy documents $\to$ Stage B BFF legacy adapter $\to$ Stage C retirement) and bridging My Picks identity via `legacy_pick_ids` — prevents dual-pipeline drift between old and new builds.

However, cross-checking [kdds.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/kdds.md) against [producers-to-bff.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/producers-to-bff.md) and the repositories cited in its **References** sections exposes **4 blocking/high-severity contradictions in KDD-001** and **5 architectural/cutover gaps in KDD-002** that should be resolved before moving either KDD from `Proposed` to `Accepted`.

---

## 2. KDD-001 Critical Findings ([kdds.md:14-138](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/kdds.md#L14-L138))

### 2.1 [Blocking] Cosmos DB mandatory `"id"` field contradicts `"additionalProperties": false` in `producer-pick.schema.json`
- **Where:** [kdds.md:27, 57, 103](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/kdds.md#L27) vs. [producers-to-bff.md:236-274, 404](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/producers-to-bff.md#L236-L274)
- **What KDD-001 says:**
  - Decision #2 ([line 27](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/kdds.md#L27)): *"Each document holds one pick in one region: exactly one producer pick record, with the document `id` equal to `pick_id`."*
  - Rationale & Consequences ([lines 57, 103](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/kdds.md#L57)): *"The schema applies directly. One document is one producer record, so producer CI validates documents against the contract's JSON Schema as they are"* / *"Producer CI validates stored documents directly against the contract schema."*
- **Why this fails:**
  1. Azure Cosmos DB NoSQL API requires every document to carry a top-level `"id"` string property, and the cited publisher ([`generic_cdf_to_cosmos_pipeline.ipynb:477-479`](file:///mnt/devel/xosports/github/app-data/databricks/publisher/generic_cdf_to_cosmos_pipeline.ipynb#L477-L479)) silently skips any item missing `"id"` (`if not item_body.get("id"): continue`).
  2. In [producers-to-bff.md:236-274, 404](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/producers-to-bff.md#L236-L274), `producer-pick.schema.json` defines `"pick_id"`, **does not define `"id"`**, and sets `"additionalProperties": false`. Furthermore, documents read back from Cosmos also carry `"_rid"`, `"_self"`, `"_etag"`, `"_attachments"`, and `"_ts"`.
  3. Consequently, any real Cosmos document will **fail** validation against `producer-pick.schema.json`.
- **Fix:** Either:
  - Add `"id": { "type": "string", "minLength": 1 }` (equal to `pick_id`) to `producer-pick.schema.json` in [producers-to-bff.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/producers-to-bff.md) and state in KDD-001 that Cosmos system properties (`_*`) are stripped before schema validation; or
  - State that producer CI validates the pre-Cosmos Delta record against `producer-pick.schema.json` and the Publish Engine copies `pick_id` into Cosmos `"id"` on write.

---

### 2.2 [Blocking] KDD-001 indexes `sport`, which does not exist in `producers-to-bff.md`
- **Where:** [kdds.md:26, 29](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/kdds.md#L26) vs. [producers-to-bff.md:82-116, 236-274](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/producers-to-bff.md#L82-L116)
- **What KDD-001 says:**
  - Decision #1 ([line 26](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/kdds.md#L26)): *"Create a new Cosmos container for producer pick records, shared across all sports."*
  - Decision #4 ([line 29](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/kdds.md#L29)): *"The indexing policy indexes only the paths that are queried: `game_sk`, `region`, `sport`, `pick_status` and `pick_kind`."*
- **Why this fails:**
  - `sport` does **not** exist in [producers-to-bff.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/producers-to-bff.md) (neither in the Field Reference table at lines 82–116 nor in `producer-pick.schema.json` at lines 236–405), and `"additionalProperties": false` forbids adding it ad hoc.
  - Because the new container is shared across all sports, omitting `sport` from the producer pick record means:
    1. Indexing `/sport/?` in Cosmos indexes nothing.
    2. Per-sport monitor workers (e.g., `fa-edge-monitor-nfl-dev-01`) cannot query open picks for their sport (`WHERE c.sport = @sport AND c.pick_status = 'open'`) without already knowing every `game_sk`.
    3. Neither the monitor nor the BFF can construct `overlay_key(sport, pick_id) = lower(sport) + ":" + pick_id` ([realtime-overlays.md:59](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/realtime-overlays.md#L59)) from the pick document alone.
- **Fix:** Add `sport` (`"nba" | "nfl" | "mlb" | "wnba" | "ncaab" | "epl"`, frozen at creation) to the producer pick record and JSON Schema in [producers-to-bff.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/producers-to-bff.md).

---

### 2.3 [High] KDD-001 mischaracterizes `mobile-server`'s existing freemium Redis cache
- **Where:** [kdds.md:31, 82, 137](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/kdds.md#L31) vs. [`response-cache.ts`](file:///mnt/devel/xosports/github/mobile-server/src/freemium/cache/response-cache.ts#L20-L55) and [`ENTITLEMENT_CACHE_DECISIONS.md`](file:///mnt/devel/xosports/github/mobile-server/src/freemium/cache/ENTITLEMENT_CACHE_DECISIONS.md#L29-L86)
- **What KDD-001 says:**
  - Guardrail #1 ([line 31](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/kdds.md#L31)): *"The BFF must cache the day's pick records per `(region, day)` for 30 to 60 seconds and apply per-user locking in memory on read."*
  - Read-cost section ([line 82](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/kdds.md#L82)): *"The BFF already keeps a 60-second response cache for freemium responses (`mobile-server` `develop`, `src/freemium/cache`), so the pattern exists."*
- **Why this matters:**
  - [`withFreemiumResponseCache`](file:///mnt/devel/xosports/github/mobile-server/src/freemium/cache/response-cache.ts#L20-L55) (documented in [`ENTITLEMENT_CACHE_DECISIONS.md:31, 45, 85`](file:///mnt/devel/xosports/github/mobile-server/src/freemium/cache/ENTITLEMENT_CACHE_DECISIONS.md#L31)) is an **L3 post-redaction HTTP response cache for anonymous/freemium callers only** (`Premium | Never`: if the caller is a subscriber, `withFreemiumResponseCache` bypasses Redis completely and hits Cosmos on every request).
  - By contrast, KDD-001's cost model ([line 79](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/kdds.md#L79): *"Four regions cached for 60 seconds is at most four refreshes per minute across all traffic, about 23,000 queries a day (`~\$17/month`)"*) requires a **shared pre-redaction origin cache of pick records** per `(region, day)` that serves **both** subscribers and free users before `locked` redaction is applied in memory.
  - Additionally, KDD-001's `4 × 1,440 = 5,760` refreshes/day (`23,000 queries/day` across 4 regions/endpoints) understates key cardinality if the cache is keyed by `(region, date, timezone_offset)` as `v3` does today (`date=2026-07-22|offset=-5.00` in [`ENTITLEMENT_CACHE_DECISIONS.md:61`](file:///mnt/devel/xosports/github/mobile-server/src/freemium/cache/ENTITLEMENT_CACHE_DECISIONS.md#L61)), or when users browse yesterday/tomorrow tabs alongside today. Because the pick query is `WHERE c.game_sk IN (<day's game_sks>) AND c.region = @region`, caching pick records by `(region, game_sk)` (or canonical slate date) avoids multiplying cache keys by user timezone offset.
- **Fix:** Clarify in KDD-001 that this is a **new pre-redaction origin pick-record cache** shared by subscribers and free users (not the freemium-only post-redaction L3 HTTP response cache in [`response-cache.ts`](file:///mnt/devel/xosports/github/mobile-server/src/freemium/cache/response-cache.ts)), and key it so user timezone offsets do not fragment the cache.

---

### 2.4 [High] Publish Engine mechanics cannot currently deliver 5-minute partial updates (`isPatch`) or avoid Stage A write amplification
- **Where:** [kdds.md:32, 40, 67, 121, 158](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/kdds.md#L32) vs. [`publish_engine_router_nba.yml`](file:///mnt/devel/xosports/github/app-data/databricks/resources/jobs/publish_engine_router_nba.yml#L20-L60) and [`generic_cdf_to_cosmos_pipeline.ipynb`](file:///mnt/devel/xosports/github/app-data/databricks/publisher/generic_cdf_to_cosmos_pipeline.ipynb#L271-L290)
- **What KDD-001 says:**
  - *"Monitor observations are written to a Delta table in Databricks; the Publish Engine picks them up and updates the `current_*` fields in Cosmos within 5 minutes."* ([line 40](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/kdds.md#L40))
  - *"In the per-pick container, that is one point read and a partial update of the `current_*` fields."* ([line 121](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/kdds.md#L121))
- **Three concrete implementation gaps in `app-data` today:**
  1. **Broken `isPatch` path in `generic_cdf_to_cosmos_pipeline.ipynb`:** In [`generic_cdf_to_cosmos_pipeline.ipynb:271-290`](file:///mnt/devel/xosports/github/app-data/databricks/publisher/generic_cdf_to_cosmos_pipeline.ipynb#L271-L290), the existing patch mode builds one patch op per top-level field (which fails Azure Cosmos DB's hard limit of **10 operations per `patch_item` call** whenever a record has $>10$ non-null fields) and silently swallows non-404 `CosmosHttpResponseError` exceptions (`pass`). Note that updating `current_line`, `current_price`, `current_edge`, `current_stake`, `current_direction`, `current_bookmaker`, `pick_status`, `status_reason`, `withdrawn_at`, `updated_at` is **10 fields**—right on the Cosmos 10-op cliff if any 11th field is included. Because KDD-001 makes the Publish Engine the **sole writer** from Delta tables, either a full-document `upsert_item` of the complete pick row from Delta or a bounded patch restricted to the mutable field whitelist avoids the 10-op failure cleanly.
  2. **Databricks job trigger latency:** [`publish_engine_router_nba.yml`](file:///mnt/devel/xosports/github/app-data/databricks/resources/jobs/publish_engine_router_nba.yml#L20-L60) uses `table_update` with `wait_after_last_change_seconds: 60`, runs `Build_Task_List`, and then launches child `run_job_task` workers serially (`concurrency: 1`). If a monitor writes to Delta every 1–5 minutes during pre-game windows, `wait_after_last_change_seconds: 60` plus multi-task job startup will frequently exceed 5 minutes or queue behind batch runs unless the pick publisher runs as a warm streaming/micro-batch job or dedicated lightweight task.
  3. **Interaction with KDD-002 Stage A (Monitor ticks vs. Legacy projections):** In KDD-002 Stage A ([line 158](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/kdds.md#L158)), *"In the same run, the Publish Engine writes the new records and projects them into the legacy documents"*. If every 5-minute monitor observation triggers a Stage A projection into the legacy per-game documents (`game_prediction`, `game_edge_picks`, `player_edge_picks`, `player_top_picks`), then during Stage A you re-introduce the 7× per-game write amplification **and** risk firing `q-events-dev-v2` push notifications on every odds tick (since [`generic_cdf_to_cosmos_pipeline.ipynb:685-693`](file:///mnt/devel/xosports/github/app-data/databricks/publisher/generic_cdf_to_cosmos_pipeline.ipynb#L685-L693) emits Service Bus events whenever `game_prediction` is updated). KDD-001/002 should explicitly state that **monitor observation updates only update `current_*` (and `withdrawn` status) and do NOT re-trigger `q-events-dev-v2` push notifications**.

---

### 2.5 [Low] Metadata & Cost Table Notes in KDD-001
- **`Supersedes: None` ([kdds.md:22](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/kdds.md#L22)):** There is already a document titled `KDD-001` in [`reqs/nba/kdd_schema.md`](file:///mnt/devel/xosports/reqs/nba/kdd_schema.md#L109-L111) (*"KDD-001: Split vs Combined Documents for WLTP and PS"*, dated 13 Sep 2026) which explicitly rejected Option D (per-pick documents) in favor of Option B (`game_edge_picks` + `player_edge_picks`). [kdds.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/kdds.md) should either note that it supersedes `reqs/nba/kdd_schema.md` for Edge Picks or use a non-colliding KDD numbering scheme.
- **RU/s & cost arithmetic check ([kdds.md:67-81](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/kdds.md#L67-L81)):** The arithmetic in the table is internally consistent (`144 polls × 30% = 43.2 + 3 = 46.2 writes/record/day`; `46,200 / 138,600 / 231,000 writes/day`; `0.46M / 1.39M / 2.31M RU/day`; `5.3 / 16.0 / 26.7 avg RU/s`; `\$3.45 / \$10.40 / \$17.30 per month` at `\$0.25/M RU`). One helpful nuance worth noting: in [`live-odds/EDGE_PICKS_LIVE_ODDS_DESIGN.md`](file:///mnt/devel/xosports/github/live-odds/EDGE_PICKS_LIVE_ODDS_DESIGN.md) and [`poll_history.py`](file:///mnt/devel/xosports/github/live-odds/nfl/mappers/poll_history.py), polling uses an adaptive cadence (~55–65 polls over 96h, with ~2% changing price/line), so the 46.2 writes/pick/day figure in KDD-001 is a conservative upper bound (~10× higher than typical `live-odds` change rates), which makes the cost conclusion even stronger.

---

## 3. KDD-002 Critical Findings ([kdds.md:141-244](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/kdds.md#L141-L244))

### 3.1 [Blocking] Bidirectional My Picks resolution (`legacy_pick_ids`) fails in the "new build $\to$ older build" direction during Stage A
- **Where:** [kdds.md:155, 211-214, 227](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/kdds.md#L155) vs. [`resolve-my-picks-list.ts:43-58, 128-235`](file:///mnt/devel/xosports/github/mobile-server/src/lib/my-pick/resolve-my-picks-list.ts#L43-L58)
- **What KDD-002 promises:**
  - Guardrail #3 ([line 227](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/kdds.md#L227)): *"Test cross-version My Picks in CI. Save a pick in an older build, open My Picks in the new build, **and the reverse**. Both directions must resolve to the same pick."*
- **Why the reverse direction ("save in new build, open in older build / `/v2/my-picks` or `/v3/my-picks`") breaks in Stage A unless BFF resolution is updated in Stage A:**
  1. When a user saves a pick in the new v4 build, the saved slip item in `c-mypicks` stores `predictionId = <v4 pick_id>` (e.g., `"nba_20260416_lal_bos_p_tatum_pts_over_27_5_us"`).
  2. If that user opens My Picks on an older build (e.g., on a second device, iPad, or before upgrading all devices, hitting `GET /v1/my-picks`, `GET /v2/my-picks`, or `GET /v3/my-picks`) during **Stage A**, [`resolve-my-picks-list.ts`](file:///mnt/devel/xosports/github/mobile-server/src/lib/my-pick/resolve-my-picks-list.ts#L128-L235) reads the **legacy documents** (`game_prediction`, `game_edge_picks`, `player_edge_picks`, `player_top_picks`) and keys `availableIndex` by `pick.id` (the **legacy** ID, e.g., `"60699_moneyline_us"`).
  3. [`lookupResolvedPick`](file:///mnt/devel/xosports/github/mobile-server/src/lib/my-pick/resolve-my-picks-list.ts#L43-L58) looks up `availableIndex[item.predictionId]`. Because `availableIndex` only has the legacy key `"60699_moneyline_us"` and `item.predictionId` is the v4 `pick_id`, **live lookup misses**! Worse still, after game completion, [`hydratePickFromSnapshot`](file:///mnt/devel/xosports/github/mobile-server/src/lib/my-pick/snapshot.ts#L305-L315) looks up `outcomeDoc.result.match` / `result.player` by `id === item.predictionId`, which also misses if `c-outcome` is only keyed by the legacy ID.
- **Fix:** Specify in KDD-002 that:
  1. During Stage A, the derived legacy pick objects carry **both** `id: <legacy_pick_id>` and `v4_pick_id: <pick_id>` (or `legacy_pick_ids` is indexed in both directions in [`resolve-my-picks-list.ts`](file:///mnt/devel/xosports/github/mobile-server/src/lib/my-pick/resolve-my-picks-list.ts#L43-L58) from Day 1 of Stage A, not deferred to Stage B).
  2. When the new v4 `POST /v4/my-picks` endpoint writes a slip item to `c-mypicks`, it also populates the legacy snapshot fallback fields (or stores `legacy_pick_ids[0]`) so older `/v1`, `/v2`, and `/v3` My Picks readers can resolve both live picks and settled outcomes.

---

### 3.2 [High] Mapping `withdrawn` $\to$ `scheduled` in the Stage A legacy projection will make older builds recommend dead picks
- **Where:** [kdds.md:196-197](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/kdds.md#L196-L197) vs. [`my-pick.ts:9-25`](file:///mnt/devel/xosports/github/mobile-server/src/lib/my-pick/my-pick.ts#L9-L25)
- **What KDD-002 says ([line 197](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/kdds.md#L197)):**
  > `| A withdrawn or settled pick | Not represented; stays scheduled or final | Mapped to scheduled (withdrawn) or final (settled), or omitted by projection rule | New statuses appear only in the new endpoints |`
- **Why mapping `withdrawn` to `scheduled` is dangerous:**
  - Under [producers-to-bff.md:194-213](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/producers-to-bff.md#L194-L213), a pick becomes `withdrawn` when the live edge drops below threshold or the market moves past the fair price before tip-off.
  - Older app builds have no concept of `withdrawn` badges or `current_*` fields—they display any `scheduled` pick in `game_prediction.top_picks` or `game_edge_picks` as an active, recommended Edge Pick at its entry odds.
  - Conversely, as verified in [`src/lib/my-pick/my-pick.ts:9-25`](file:///mnt/devel/xosports/github/mobile-server/src/lib/my-pick/my-pick.ts#L9-L25), [`canonical/picks.ts:529, 757`](file:///mnt/devel/xosports/github/mobile-server/src/lib/match/canonical/picks.ts#L529), [`common.ts:252`](file:///mnt/devel/xosports/github/mobile-server/src/lib/match/common.ts#L252), and [`match-data-mapper.ts:521, 641`](file:///mnt/devel/xosports/github/mobile-server/src/lib/match-data-mapper.ts#L521), the legacy BFF **already filters out `pick_status === "cancelled"`** everywhere!
- **Fix:** In the Stage A legacy projection and Stage B legacy adapter, map both `cancelled` **and** `withdrawn` to `pick_status: "cancelled"` (or omit `withdrawn` from the legacy feed/match arrays) so older app builds stop recommending picks whose edge has evaporated, rather than mapping `withdrawn` to `scheduled`.

---

### 3.3 [High] Settled picks (`won` / `lost` / `void`) need `bet_outcome` and `c-outcome` projection, not just `pick_status: "final"`
- **Where:** [kdds.md:158, 197](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/kdds.md#L158) vs. [`canonical/picks.ts:426, 478-480`](file:///mnt/devel/xosports/github/mobile-server/src/lib/match/canonical/picks.ts#L426) and [`snapshot.ts:305-315`](file:///mnt/devel/xosports/github/mobile-server/src/lib/my-pick/snapshot.ts#L305-L315)
- **Why this matters:**
  - KDD-002 line 197 says settled picks are *"Mapped to ... `final` (settled)"*.
  - In `mobile-server`, legacy endpoints do **not** read `won` / `lost` / `void` from `pick_status`. Instead:
    1. [`canonical/picks.ts:426, 478-480`](file:///mnt/devel/xosports/github/mobile-server/src/lib/match/canonical/picks.ts#L426) derives `pickStatus` (`"win" | "loss" | "pending"`) and `pickOutcome` (`1 | 0 | null`) from `bookmaker.bet_outcome ?? pick.bet_outcome` (`1` = win, `0` = loss, `null` = pending/void).
    2. [`snapshot.ts:305-315`](file:///mnt/devel/xosports/github/mobile-server/src/lib/my-pick/snapshot.ts#L305-L315) and [`resolve-my-picks-list.ts:107-120`](file:///mnt/devel/xosports/github/mobile-server/src/lib/my-pick/resolve-my-picks-list.ts#L107-L120) resolve settled My Picks slips from the `outcome` document in `c-outcome` (`result.match[]` and `result.player[]`, where `outcome: 1 | 0 | null`).
- **Fix:** State explicitly in KDD-002 that Stage A / Stage B map `pick_status` (`won` $\to$ `bet_outcome: 1`, `lost` $\to$ `bet_outcome: 0`, `void` $\to$ `bet_outcome: null`) onto both the legacy pick's `bet_outcome` field and (while legacy My Picks snapshot hydration remains active) `c-outcome.result`.

---

### 3.4 [Medium] Format A (`game_prediction.top_picks`) cannot be derived from producer pick records alone and has a 1-pick-per-region cardinality limit
- **Where:** [kdds.md:158, 175](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/kdds.md#L158)
- **What KDD-002 says:**
  - *"Stage A, derived legacy documents. In the same run, the Publish Engine writes the new records and projects them into the legacy documents (`game_prediction.top_picks`, `game_edge_picks`, `player_edge_picks`, `player_top_picks`). It uses one deterministic projection."*
- **Two structural constraints not yet specified in KDD-002:**
  1. **`game_prediction` is a combined document in Format A (`NFL`, `MLB`, `WNBA`, `EPL`):** Unlike `game_edge_picks` (NBA Format B), `game_prediction` in `c-wltp` contains the game's win/loss/total/spread model predictions (`WinLoss_team_1`, `Prediction_team_1`, etc.) even when a game has **zero** Edge Picks (`top_picks: {"AU": null, "US": null}`). Therefore, `game_prediction` cannot be projected solely from the new pick records—the Publish Engine must join the game prediction row with the projected `top_picks` object (or migrate all sports onto Format B `game_edge_picks` first).
  2. **Multi-pick $\to$ single-pick tie-breaker for Format A `game_prediction.top_picks[region]`:** In v4 ([producers-to-bff.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/producers-to-bff.md)), a game can have multiple game picks in one region (e.g., a spread pick and a total pick). In Format B (`game_edge_picks.edge_picks[region]`), the legacy field is an array, so all active picks fit. In Format A (`game_prediction.top_picks[region]`), the legacy field is a **single object** (`null` or 1 pick). For Stage A to be a *"deterministic projection"*, KDD-002 must state the selection rule when $>1$ open game pick exists for `(game_sk, region)` (e.g., highest `entry_edge`, tie-broken by `pick_id`).

---

### 3.5 [Minor] Incomplete list of legacy My Picks readers in KDD-002 Context
- **Where:** [kdds.md:167, 239](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/kdds.md#L167)
- **What KDD-002 says:**
  - *"My Picks (`my-picks-v2.ts`), matching saved items against live documents by `predictionId`."*
- **Missing endpoints:** `mobile-server` has **three** My Picks read handlers—[`my-picks.ts`](file:///mnt/devel/xosports/github/mobile-server/src/functions/my-picks.ts) (`GET /v1/my-picks`), [`my-picks-v2.ts`](file:///mnt/devel/xosports/github/mobile-server/src/functions/my-picks-v2.ts) (`GET /v2/my-picks`), and [`my-picks-v3.ts`](file:///mnt/devel/xosports/github/mobile-server/src/functions/my-picks-v3.ts) (`GET /v3/my-picks`)—all delegating to [`resolve-my-picks-list.ts`](file:///mnt/devel/xosports/github/mobile-server/src/lib/my-pick/resolve-my-picks-list.ts). Mentioning `resolve-my-picks-list.ts` (and `/v1`, `/v2`, `/v3`) in KDD-002 ensures no legacy My Picks route is overlooked during Stage B cutover.

---

## 4. Summary of Recommended Edits

| Target File | Section | Recommended Change |
|---|---|---|
| [producers-to-bff.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/producers-to-bff.md) & [kdds.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/kdds.md) (KDD-001) | Producer schema & KDD-001 Decision #2, #4 | 1. Add `sport` (`"nba" \| "nfl" \| "mlb" \| "wnba" \| "ncaab" \| "epl"`, frozen at creation) to `producer-pick.schema.json` and the Field Reference table.<br>2. Reconcile Cosmos `"id"` vs. `"pick_id"` with `"additionalProperties": false` (either include `"id"` in `producer-pick.schema.json` or specify pre-Cosmos validation / system-property stripping). |
| [kdds.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/kdds.md) (KDD-001) | Guardrail #1 & Read Cost ([lines 31, 79-82](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/kdds.md#L31)) | Clarify that the 30–60s `(region, day)` cache is a **new pre-redaction origin pick-record cache** shared across subscribers and free users (distinct from the freemium-only post-redaction L3 HTTP response cache in [`response-cache.ts`](file:///mnt/devel/xosports/github/mobile-server/src/freemium/cache/response-cache.ts)). |
| [kdds.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/kdds.md) (KDD-001 & KDD-002) | Publish Engine & Stage A ([lines 40, 121, 158](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/kdds.md#L40)) | Specify that 5-minute monitor updates in the Publish Engine (a) use full-row upsert from Delta or a bounded `<10`-op patch (fixing [`generic_cdf_to_cosmos_pipeline.ipynb:271-290`](file:///mnt/devel/xosports/github/app-data/databricks/publisher/generic_cdf_to_cosmos_pipeline.ipynb#L271-L290)) and (b) do **not** emit `q-events-dev-v2` push notifications on odds ticks. |
| [kdds.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/kdds.md) (KDD-002) | Stage A Projection & Older Builds Table ([lines 158, 196-197](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/kdds.md#L158)) | 1. Map `withdrawn` $\to$ `cancelled` (or omit from active feed) in legacy projections so older builds do not recommend dead edges as `scheduled`.<br>2. Map `won`/`lost`/`void` $\to$ `bet_outcome: 1 / 0 / null` (and `c-outcome` results) in addition to `pick_status: "final"`.<br>3. Specify the deterministic tie-breaker (e.g., max `entry_edge`, then `pick_id`) when projecting multiple v4 game picks into a single Format A `game_prediction.top_picks[region]` slot. |
| [kdds.md](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/kdds.md) (KDD-002) | My Picks Identity Bridge ([lines 155, 211-214, 227](file:///mnt/devel/xosports/xo-scratchpad/edgepicks-redesign/staging/kdds.md#L155)) | Require bidirectional ID indexing (`pick_id` $\leftrightarrow$ `legacy_pick_ids`) in [`resolve-my-picks-list.ts`](file:///mnt/devel/xosports/github/mobile-server/src/lib/my-pick/resolve-my-picks-list.ts) starting in **Stage A** (not Stage B) so picks saved in v4 resolve when viewed on older builds (`GET /v1`, `/v2`, `/v3/my-picks`). |

