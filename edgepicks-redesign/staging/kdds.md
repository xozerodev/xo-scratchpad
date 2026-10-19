# Edge Picks v4: Key Design Decisions

This log records the key design decisions (KDDs) behind the Edge Picks v4 contracts: what was decided, why, what else was considered, and what it costs. Each KDD is one section, numbered in order and never renumbered. A superseded KDD stays in the log, marked with the KDD that replaces it. Numbers are local to this log: a decision from another log is cited with its prefix, for example NBA KDD-001 for `reqs/nba/kdd_schema.md`.

| KDD | Decision | Status | Owners | Date |
| --- | --- | --- | --- | --- |
| [KDD-001](#kdd-001-store-producer-pick-records-one-per-document-in-a-new-cosmos-container) | Store producer pick records one per document, in a new Cosmos container | Proposed | Bet engine, data engineering | 2026-10-19 |
| [KDD-002](#kdd-002-old-and-new-app-versions-coexist-on-one-source-of-truth) | Old and new app versions coexist on one source of truth; legacy documents are derived from the new records under the same pick ids, never written independently | Proposed | BFF, app team, data engineering, bet engine | 2026-10-19 |
| [KDD-003](#kdd-003-the-new-app-shows-legacy-and-v4-picks-through-one-response-shape) | The new app shows legacy and v4 picks through one response shape: the BFF translates legacy picks, marks each pick's era, and the app draws a full or a limited card | Proposed | BFF, app team (decide); product, data engineering | 2026-10-20 |

Statuses: **Proposed** (written, not yet agreed), **Accepted** (every owner has agreed, with the date), **Superseded** (replaced by a later KDD, named in its status), **Rejected** (considered and turned down; kept so it is not proposed again without new facts).

---

## KDD-001: Store producer pick records one per document in a new Cosmos container

| | |
| --- | --- |
| Status | Proposed |
| Date | 2026-10-19 |
| Owners | Bet engine, data engineering (decide); BFF, live edge monitor (consulted) |
| Contract affected | Edge Picks producer pick record 4.0.0: the open decision "Document layout and id format"; rule 1 and the "Pick id" formula (the NBA canonical id for every producer, unique across regions and sports) and the sport field, all added to the draft for this KDD |
| Supersedes | NBA KDD-001 (`reqs/nba/kdd_schema.md`, Sep 13, 2026), for Edge Picks pick documents only: its rejection of per-pick documents (Option D). The Oct 17 co-existence plan's layout for picks: v3 `game_picks` and `player_picks` doc types in the existing `c-wltp` and `c-ps` containers (option B below) |

### Decision

1. Producer pick records go into a **new Cosmos container**, separate from the existing `c-wltp-*` and `c-ps-*` containers.
2. Each document holds **one pick in one region**: exactly one producer pick record. The document `id` is the record's `pick_id`, which the contract makes unique across regions and sports and limits to characters Cosmos allows (rule 1). Two regions' records for the same selection therefore never share an id.
3. The partition key is **`/game_sk`**.
4. The indexing policy indexes only the paths that are queried: `game_sk`, `region`, `sport`, `pick_status` and `pick_kind`.
5. Four guardrails are part of the decision, not optional tuning:
   - **Shared pick-record cache.** The BFF reads pick records through a new cache in Redis, shared by every instance and by subscribers and free users alike. It holds records before any redaction, keyed by region and `game_sk`, so a user's date and time-zone offset only choose which keys to read. One instance at a time rebuilds the keys (a lock, so no two instances query Cosmos for the same keys), at most every 60 seconds, with one query per region covering the games in view. Each user's locking is applied in memory after the read. This is not the existing freemium response cache, which holds post-redaction bodies for free users only and has no lock.
   - **Whole-record writes, guarded.** The Publish Engine merges each pick's batch output and latest monitor observation into one row in Delta, then writes the whole record with an upsert guarded by the document's etag. A write that loses the etag check re-reads, re-merges and retries. The generic publisher's patch mode is not used: it turns every non-null field into one patch operation (Cosmos allows 10 per call) and cannot set a field to null, which the contract requires.
   - **Validate before write.** The Publish Engine validates every record against the contract's JSON Schema before writing it, then adds the Cosmos `id`. A record that fails, or has no `pick_id`, fails the run; it is never skipped silently.
   - **Write on change.** The monitor writes an observation only when the price, line or edge state changed, and at most every 5 minutes per pick. The last observation before the game is always written, changed or not, so `is_closing` is set. Rule 5's 5 minutes run from the monitor's write to the record.
6. This container is the **only source of pick values**. The documents older app versions read are derived from it, as set out in KDD-002. No push producer reads it.

### Context

- **Today's layout** (app-data dev 2b6f998): one document per game per pick type (`nba|game_edge_picks|<game_sk>`, `nba|player_edge_picks|<game_sk>`), partitioned on `/game_sk`, with a region map inside the document. Prediction documents share the same containers. Every Publish Engine run replaces the whole document.
- **The whole-document replace is what drops picks.** A pick the engine does not produce on a later run disappears from the document. That breaks the contract's persistence rule: once published, a pick stays until it is settled or void.
- **The contract has one writer.** Only the Publish Engine writes pick documents, and the monitor's observations reach them through it within 5 minutes. With one document per game, every run that sees any change rewrites the whole game document, and concurrent updates to one game conflict.
- **The generic publisher cannot write these records as it stands** (`generic_cdf_to_cosmos_pipeline.ipynb`, app-data dev). Its patch mode sends one operation per non-null field and drops nulls. It skips a row with no `id` without counting it. Other write errors are counted and logged but do not fail the run.
- **The Publish Engine trigger adds latency.** The NBA router (`publish_engine_router_nba.yml`) waits 60 seconds after the last table change, then runs a task-list step before its writers; whole runs queue behind each other. The live-odds design measured 1 to 3 minutes from a table commit to Cosmos (`EDGE_PICKS_LIVE_ODDS_DESIGN.md`, section 2), inside rule 5's 5 minutes but with little margin.
- **NBA KDD-001 rejected per-pick documents** because they "turn every list/detail read into a fan-out and break the partition-by-game model", and named per-pick lifecycle as the trigger to revisit (S3). The persistence rule is that trigger. Partitioning by `game_sk` keeps the game model, and the shared cache absorbs the fan-out.
- **Older app versions keep working for as long as they are supported**, which is open-ended (KDD-002). The store build sends API version 5 and reads the existing documents.
- **Scale is growing.** More than 10 leagues are planned, so 1,000 or more pick records a day (a record is one pick in one region), and plausibly 5,000.

### Options considered

| Option | Summary | Verdict |
| --- | --- | --- |
| A. Keep one document per game in the existing containers, in the new shape | Change the existing documents to hold v4 records | Rejected: breaks the current app before cutover; keeps the whole-document replace that drops picks; every change rewrites the game |
| B. New document type in the existing containers, one per pick | v4 records beside today's documents, told apart by `doc_type` | Rejected: the existing readers, feeds and backfills would all have to learn to skip the new type; indexing and retention policies stay shared with documents of a different shape; rollback means deleting documents rather than ignoring a container |
| C. New container, one document per game and region | v4 shape, still grouped by game. NBA KDD-001's preferred contingency | Rejected: persistence still depends on every run rewriting every pick correctly; a status write and an observation for different picks of one game still contend |
| **D. New container, one document per pick** | One producer record per document | **Proposed** |

### Why D

- **Persistence holds by construction.** Upserting one pick cannot drop its siblings. A pick's lifecycle changes only through its own status.
- **Writes for different picks never contend,** and the etag guard keeps two writes to the same pick from overwriting each other.
- **The schema applies to every write.** One document is one producer record, so the Publish Engine validates each record against the contract's JSON Schema before writing it, and a reader can validate a stored document once Cosmos's own fields are removed.
- **Old and new app versions are served side by side.** Older builds keep reading the existing containers, whose pick documents are derived from the new records in the same Publish Engine run (KDD-002). Turning the new screen off for new builds needs no data change.
- **It fits the dev-isolation rule**, which already asks for a separate Cosmos database for the parallel setup in dev.
- **Writes cost about half** of game documents (table below). Both are small; cost is not the reason for D.

### Cost and performance

Prices are Microsoft's published US example rates: serverless $0.25 per million request units (RU), provisioned $0.008 per 100 RU/s per hour, autoscale 1.5 times that, storage $0.25 per GB per month. Region and current rates vary, so check the pricing page before budgeting. Whether the account is serverless or provisioned was not found in the repositories, so both are shown.

A producer record is about 930 bytes of JSON, about 1.2 KB once stored with Cosmos's own fields.

**Writes.** Assumptions:

- Each record gets about 3 writes for publish, status changes and settlement.
- It is observed every 5 minutes for the 12 hours before its game (144 observations), and 30% of observations change something worth writing. The live-odds cadence is coarser near the game but starts up to 96 hours out, so a pick's lifetime count is similar.
- A write of one ~1.2 KB document is about 10 RU; a rewrite of a ~15 KB game document about 75 RU.
- For game documents, a game has about 20 records (both regions), held in 2 documents (game and player picks). The Publish Engine writes per run, so a document is rewritten once in any 5-minute window in which any of its ~10 picks changed (97% of windows), not once per changed pick.

| Records a day | One per pick | One per game |
| --- | --- | --- |
| 1,000 | 46,000 writes, 0.46M RU/day, ~$3.50/month, ~5 RU/s average | 14,000 writes, 1.07M RU/day, ~$8/month, ~12 RU/s |
| 3,000 | 139,000 writes, 1.39M RU/day, ~$10/month, ~16 RU/s | 43,000 writes, 3.22M RU/day, ~$24/month, ~37 RU/s |
| 5,000 | 231,000 writes, 2.31M RU/day, ~$17/month, ~27 RU/s | 71,000 writes, 5.36M RU/day, ~$40/month, ~62 RU/s |

**Reads.** The bytes read for a region's day are the same in either layout, so read cost depends on how often the BFF goes to Cosmos, not on the layout. One region-day read is about 390 RU at 1,000 records a day and about 1,950 RU at 5,000. Assumptions for the comparison: 2 regions, 3 days in view (yesterday, today and tomorrow), and 2,000 active users each refreshing once a minute for 3 hours a day.

| BFF read pattern | 1,000 records a day | 5,000 records a day |
| --- | --- | --- |
| Shared cache, one locked rebuild per region every 60 seconds | ~3.4M RU/day, ~$25/month | ~16.8M RU/day, ~$126/month |
| Cosmos read on every app request | ~140M RU/day, ~$1,050/month | ~700M RU/day, ~$5,300/month |

The cached figure holds only with the rebuild lock: without it, every instance whose key expires queries Cosmos itself. Rebuilding only when picks have changed, rather than every 60 seconds, cuts it further.

**Throughput mode.** Cache rebuilds, not writes, set the throughput. With rebuilds every 60 seconds, the 5,000-a-day case averages about 220 RU/s (about 195 for reads, 27 for writes), and about 45 RU/s at 1,000 a day. Each minute's rebuild is about 11,700 RU at 5,000 a day, so the rebuild spreads its query pages across the minute rather than bursting. That is about $145 a month serverless, or autoscale to 1,000 RU/s, which bills the highest RU/s reached in each hour at 1.5 times the provisioned rate, never below 100 RU/s: at most about $88 a month. Provisioned 400 RU/s (about $23 a month) fits only if rebuilds run when picks change rather than every minute; measure before choosing.

**Storage.** At 3,000 records a day: about 1.3 GB a year of documents, plus the index, about $0.40 a month. No time-to-live is set, because settled picks feed the track record.

**Performance.**

| Aspect | Expectation |
| --- | --- |
| Partitions | About 20 documents per game, so no hot partitions. The container stays in one physical partition for years, so a query across games costs the same as one within a partition |
| Read latency | A region-day of up to 2,500 records is a few pages of query results, tens of milliseconds, and normally served from the BFF's cache |
| Write latency | Single-digit milliseconds per document. A write that loses the etag check costs one re-read and retry |
| Observation latency | Monitor commit to Cosmos within 5 minutes (rule 5), through the router's 60-second wait and the writer run. Measured in Validation; if it does not hold, observations get a dedicated lightweight writer job |
| BFF query | Find the day's games from the schedule the BFF already reads, then query picks by those `game_sk` values, the region and the sport |

### Consequences

**Positive**

- The persistence and one-writer rules hold without depending on every engine run behaving.
- Writes for different picks never contend, and write cost is about half that of game documents.
- Every record is validated against the contract schema before it is written.
- Older app versions keep working without a migration in place (KDD-002).

**Negative, and what handles it**

| Cost | Handling |
| --- | --- |
| The BFF needs a new read path (query instead of point reads) | Built once, behind the shared pick-record cache |
| The generic publisher's patch mode cannot write these records | A pick writer that upserts whole records with an etag guard (guardrail 2); it is the Publish Engine's, so rule 5 still holds |
| Every producer adds `sport` and a pick\_id unique across regions and sports | Contract rule 1; producer CI checks uniqueness across the run's output and the store |
| The Publish Engine also writes the legacy documents, derived from the new records, for as long as any supported app version reads them | Written only when their projected content changes, so no more often than today; retired league by league and route by route under KDD-002 |
| Slips and follows saved in an older build before a league's v4 start carry legacy ids | Those games stay on their legacy documents for life, so the ids resolve where they were saved; games from the v4 start carry the same ids in both families (KDD-002) |
| Per-request Cosmos reads would be expensive | Guardrail 1: the shared cache and its rebuild lock are part of this decision |
| Frequent monitor updates add write volume | Guardrail 4: write on change only, at most every 5 minutes |

### Validation

Before this KDD is accepted, run in the dev Cosmos database set aside for the parallel setup:

1. Write 3,000 sample producer records that validate against the producer schema, using the proposed indexing policy.
2. Record Cosmos's reported request charge for an insert and a whole-record upsert.
3. Record the request charge and latency of one region-day query (about 1,500 records).
4. Write an au and a us record for the same selection: both exist afterwards.
5. Send a status change and an observation for the same pick at the same time: both survive, through the etag retry.
6. Over a live slate, measure monitor commit to Cosmos: 95% within 5 minutes.
7. Run the BFF with several instances against the cache: Cosmos sees one rebuild per region per minute, not one per instance.
8. Replace the estimates above with the measured figures. Accept if the measured cost at 5,000 records a day stays within twice the estimate.

### Open items

- Whether the Cosmos account is serverless or provisioned (data engineering).
- The container name for each environment, following the existing `c-<name>-<env>-<nn>` pattern (data engineering).
- Who builds the pick writer, and whether observations need their own lightweight job to meet 5 minutes (data engineering).
- That game\_sk ranges never overlap between sports, which the pick id relies on (data engineering).
- Market tokens for markets beyond 4.0, as they are added (bet engine).
- On acceptance, mark NBA KDD-001's Option D rejection, and the Oct 17 plan's pick layout, as superseded by this KDD for Edge Picks (decision owners).

### Sources

- [Understand your Azure Cosmos DB bill](https://learn.microsoft.com/en-gb/azure/cosmos-db/understand-your-bill) (example rates)
- [How to choose between standard and autoscale throughput](https://learn.microsoft.com/azure/cosmos-db/how-to-choose-offer) (autoscale at 1.5 times, 10% floor, billed on each hour's peak)
- [Request units in Azure Cosmos DB](https://learn.microsoft.com/azure/cosmos-db/request-units) (what drives RU charges)
- [Azure Cosmos DB serverless pricing](https://azure.microsoft.com/en-us/pricing/details/cosmos-db/serverless/) (current rates)
- app-data dev 2b6f998: `databricks/publisher/nba/nba_wltp.py`, `nba_ps.py`, `build_transformation_map.ipynb` (today's documents and containers); `databricks/publisher/generic_cdf_to_cosmos_pipeline.ipynb` (patch mode, id skip, error handling); `databricks/resources/jobs/publish_engine_router_nba.yml` (trigger and queueing)
- mobile-server develop: `src/freemium/cache/response-cache.ts`, `response-cache-keys.ts`, `ENTITLEMENT_CACHE_DECISIONS.md` (the existing freemium response cache)
- live-odds dev: `EDGE_PICKS_LIVE_ODDS_DESIGN.md` (propagation through the Publish Engine; cadence tiers)
- `reqs/nba/kdd_schema.md` (NBA KDD-001, Option D and revisit trigger S3)

---

## KDD-002: Old and new app versions coexist on one source of truth

| | |
| --- | --- |
| Status | Proposed |
| Date | 2026-10-19 |
| Owners | BFF, app team, data engineering, bet engine (decide); product (consulted on retirement and on behaviour changes older builds will see) |
| Contract affected | Producer pick record: none, no new field. Snapshot API: the pick's `id` is the producer's `pick_id` (stated in its field table) |
| Supersedes | Parts of the Oct 17 co-existence plan. **C6** (no production overlap): v4 games also have derived legacy documents; its shadow run is kept. **C3**: read-time adapters become Stage B, not launch. **C1** (one family per game): amended to one *source* per game; derived documents are a presentation of it, not a second family. **C5** (no id bridge): stands, now because both families share one id rather than because no game has both. **C4** (redact the model): applies to `/v4/edge-picks` at launch and to each legacy route as it moves to Stage B. **C6a** (rollback): amended under point 10. C2, C7, C8 and C9 stand |

### Decision

1. **Coexistence is open-ended.** No date is assumed by which users have moved to the new app. Every app version still supported keeps getting today's response shapes, with only the behaviour changes listed below, until its routes are retired under point 9.
2. **One source of truth.** Producer pick records (KDD-001) are the only place a pick's values and results are decided. Everything an older build reads about picks, including results in `c-outcome`, is derived from them. Nothing writes pick values for older builds independently.
3. **Version routing stays in the BFF.** Every request already carries `api_version`, and the BFF already serves staged content only from version 6 (`gate.ts`). The new Edge Picks screen calls `GET /v4/edge-picks`; older builds keep calling today's routes and receive today's shapes.
4. **A server-side switch per league** turns the new screen's data on or off for new builds without an app release. Turning it off returns nothing from `/v4/edge-picks` for that league; older builds are unaffected either way. *Amended by KDD-003: turning it off makes `/v4/edge-picks` serve that league's picks from the legacy documents as limited cards, instead of nothing.*
5. **Each game has one source for life** (C1, amended). A league's games that start on or after its v4 start date are published as producer pick records, with derived legacy documents. Earlier games stay on today's pipeline and documents until they settle (C7). `/v4/edge-picks` reads those earlier games through C7's read-only adapters.
6. **Stage A, derived legacy documents.** In the same Publish Engine write, the new records are projected into the legacy documents by one deterministic projection, the rules below, tested against fixtures. The documents are `game_prediction.top_picks` (Format A), `game_edge_picks`, `player_edge_picks`, `player_top_picks`, and the pick results in `c-outcome`.
   - Where a legacy document also carries other content (model predictions in `game_prediction`, the game result in `c-outcome`), the Publish Engine joins that input in and writes the whole document once. No other job writes those documents for v4 games.
   - A legacy document is written only when its projected or joined content changes, never because of an observation alone.
   - `c-outcome` carries a result row for every settled or void record, including picks not shown in a one-pick slot.
   - Document-level fields that readers and the release gate rely on (`season`, league, `doc_type`, the type of `game_sk`) are written exactly as today's documents write them, so `STAGED_LEAGUES` withholds or releases derived documents as it does today.
   - Today's BFF routes read the derived documents unchanged.
   - Before a league's Stage A goes live, it runs in shadow, keeping C6's shadow run: the projection from production inputs goes into containers no user reads, and is compared with today's pipeline over a full slate cycle.
7. **Stage B, BFF adapters.** A legacy route moves to reading the new records through an adapter once its responses are proven equivalent (Validation). Legacy documents for a league stop being written only when no route and no other reader (push, WordPress feed, partner API) still reads them.
8. **One id in both families.** The derived documents use `pick_id` as the legacy pick's id, in pick lists and in `c-outcome` results. `/v4/edge-picks` serves it as the pick's `id`. A slip or follow saved in any build therefore names the same pick. My Picks resolves it with no change, live from the derived documents when the pick is listed there. A slip on a pick not listed in an older build's documents (one outside a one-pick slot) resolves from its saved snapshot and its `c-outcome` row, as slips do today when a pick leaves the live documents. No id bridge is needed, so rule C5 stands and the record gains no `legacy_pick_ids`. No reader splits pick ids (BFF, WordPress feed and app checked), with one exception: older app builds recognise a moneyline pick by finding `h2h` in its id when its `bet_type` is not exactly `h2h`, and use that to keep only one side of a game's moneyline in a slip. The contract's pick id formula writes moneyline as `h2h` and uses it nowhere else, as the NBA id already does.
9. **Retirement is a product decision made on data.** A legacy route is retired only when the oldest supported app version no longer calls it. That is decided from the share of active users on each `api_version` (for example, under 1% for 30 days), or by a forced update if the app supports one.
10. **Rollback** (amends C6a). Turning a league's switch off hides the new screen only; derived documents keep serving older builds. A bad record reaches every build, so it is fixed forward by re-publishing the record. To return a league to today's pipeline, move its v4 start date later: games not yet published go back to legacy, and games whose records are published stay on v4 and are fixed forward.

### Context

- **Users cannot be forced onto the new build.** The release is a gradual rollout, so for weeks most users stay on the old build, and some never update.
- **The store build sends `api_version` v5.** `RELEASE_API_VERSION_MAJOR = 6` in `src/lib/match/canonical/gate.ts` (mobile-server develop) already withholds staged content from earlier versions. The push fan-out and the WordPress feed carry no client version and are not gated.
- **Today's readers of pick documents** (mobile-server develop):
  - match and list routes: `match.ts`, `match-v3.ts`, `matches.ts`, `matches-v3.ts`, `matches-top-predictions.ts`, `matches-top-predictions-v3.ts`;
  - My Picks: `my-picks.ts` (its own container and resolution), `my-picks-v2.ts` (the shared resolver only at `api_version` v3), `my-picks-v3.ts`, `lib/my-pick/resolve-my-picks-list.ts`, and the create routes' freemium peer check;
  - follows (`target-follow.ts`, whose push topic is the target id with `|` turned into `_`);
  - the WordPress feed (`wp-cron-sync.ts`);
  - push (`service-bus-push-events.ts`, fed by a producer outside the repository).

  The app has a forced update: `ForceUpdateGate` (mobile-app main) blocks the app with a store link when its version is below `minimum_app_version_required` from `GET /config`, which the BFF sets from environment variables (`config.ts`), so it can be raised without a release. Which builds in the field include the gate is not known.
- **How the legacy BFF reads status and results.** It hides only `pick_status` `cancelled` and passes any other word through as live (`my-pick.ts`, `canonical/picks.ts`). It derives a pick's result from `bet_outcome` (1 win, 0 loss, 2 void), and a saved slip's result from the `c-outcome` row whose id matches the saved id (`snapshot.ts`, where a matched row with no outcome reads as void). Format A's `game_prediction.top_picks` holds one pick per region (`match-data-mapper.ts`).
- **How pick ids are used today.** The BFF compares saved ids with document ids and never splits them; the only id it parses is its own `h2h:` id for featured win-loss picks (`game-h2h.ts`). The WordPress payload passes ids through. The app stores, compares and sends ids, and its share links, deep links and pushes carry only the game id. The one format dependency is moneyline detection: `isH2hPick` (`app/utils/utils.ts`) and `GamePick.tsx` look for `h2h` in the id. Follow topics are the target id with `|` turned into `_` (`target-follow.ts`), except when a device re-registers (`queue-fcm-device.ts`), which keeps `|`, an invalid topic character: the subscribe call fails and the remaining follows are not re-subscribed. That affects today's NBA ids already.
- **Today's legacy documents are rebuilt on each engine run**, so their odds refresh with every run. v4 entry values are frozen, and the current price lives in `current_*`.
- **The Oct 17 co-existence plan already covers older builds.** C3 translates every family into one model at read time and renders every route from it, and C6 forbids holding two families for one game in production. This KDD keeps the plan's per-game pinning (C1) and its id rule (C5), and changes the order: write-time projection at launch, read-time adapters per route afterwards.
- **Legacy pick ids** differ by league. NFL, MLB, WNBA and EPL use `{game_sk}_{bet_type}_{region}`, without the line. NBA uses `{game_sk}|{market}_{selection}|…|{region}` (app-data dev 2b6f998). Under point 8, games from a league's v4 start carry the v4 pick\_id in both families instead.

### Options considered

| Option | Summary | Verdict |
| --- | --- | --- |
| A. Independent dual write | Keep today's pipeline for older builds; add the new pipeline for the new build | Rejected: two sources drift. The same game would show different picks, prices or results in the two apps. The NBA engine's dev and tst branches already differ in how they select picks |
| B. Clean cutover with forced upgrade | Switch each league once; require the new build | Rejected: upgrades cannot be forced, and the rollout is gradual |
| C. BFF adapters from the start (rule C3 at launch) | Stop legacy documents when the new records start; serve every older route through adapters | Rejected for launch: every legacy route has to be proven equivalent before any league moves, which concentrates the risk at launch. Push events come from a producer outside the BFF, not yet identified; if it reads the legacy documents, it would break |
| D′. Derived legacy documents under legacy ids, bridged | As D, but the derived documents keep each league's legacy ids, and each record lists them in `legacy_pick_ids` | Rejected: the same pick has two ids for life, so every reader of saved ids (My Picks at every version, follows, push topics, `c-outcome`) needs the bridge, and My Picks needs an adapter at launch |
| **D. Derived legacy documents under v4 ids, then adapters, league by league** | Stage A at launch, Stage B per route when proven | **Proposed** |

### Why D

- **One truth, two presentations.** Both apps show the same entry price, probability, stake and result for the same pick, because both come from one record.
- **One id.** A pick saved or followed in either build is the same pick in the other, without a bridge.
- **Nothing changes in the BFF for older builds on day one.** Their routes read the same documents in the same shape, now produced by a projection instead of a separate pipeline.
- **Risk is spread over time.** Each route moves to an adapter when it is proven, not all at launch.
- **The new screen can be switched off.** Turning a league off for the new build leaves the records, the derived documents and older builds untouched. A wrong record is fixed forward for every build at once (point 10).
- **Retirement stays in our hands,** based on usage data, not on when users choose to update.

### Projection rules

Each record projects into its own region's slot; no region is copied into another. Values are the record's entry values: entry price and line, probability and stake. `current_*` fields are never projected. Values keep each league's legacy meaning (C8 in reverse): an edge is recomputed from probability and entry price on the league's legacy basis and units (NBA: probability basis, percentage points; NFL: expected value; MLB, WNBA and EPL publish none today), and odds are rounded as the league rounds them today (NBA: 2 places). Status words are the ones each league's documents use today, fixed per league by the fixtures.

| Record | Legacy pick | `bet_outcome` | `c-outcome` result row |
| --- | --- | --- | --- |
| open | Listed, with the league's word for a pick before the game (scheduled, Scheduled or active) | null | none |
| awaiting\_result | Listed, with the same word as open | null | none |
| cancelled | Listed with `cancelled`, which every legacy route hides | null | none |
| withdrawn | Omitted: it was published in error and is never served | none | none |
| settled, won | Listed, with the league's word for a graded pick | 1 | outcome 1 |
| settled, lost | As won | 0 | outcome 0 |
| settled, push | Listed, with the league's void word where it has one, otherwise its word for a graded pick | 2 | outcome 2 (stake returned, shown as void) |
| void | As push | 2 | outcome 2 |

**One-pick slots.** Where the legacy field holds one pick per region (Format A `game_prediction.top_picks`):

- Choosing a pick: the open pick with the highest `entry_edge`, then the earliest `pick_date_time`, then the lowest `pick_id`.
- An empty slot takes a pick by that order whenever one is open, including when several are published in the same run.
- A filled slot keeps its pick while it is not cancelled or withdrawn, including through settlement or void.
- When the slot's pick is cancelled or withdrawn, the slot takes the next pick by that order, or is empty if none is open.
- Other picks for that game appear only in the new build. Array fields (Format B) list every projected pick.

### What older builds will see

The derived documents carry the same fields and words as today. Some behaviour follows the new records:

| Behaviour | Older build today | Older build under D | Handling |
| --- | --- | --- | --- |
| A line move | NBA: the pick disappears | The pick stays at its entry line | An intended fix; product to confirm and announce |
| An engine re-run that would drop a pick | The pick disappears | The pick stays until it is cancelled | An intended fix (persistence rule) |
| The engine stops backing a pick before the game | Does not happen (engines never cancel, except NFL depth-chart changes) | The pick is cancelled and disappears; a saved slip keeps its saved values | Product to confirm and announce |
| A pick published in error | Not distinguished | Never shown (withdrawn) | Projection rule |
| Odds on a listed pick | Refresh with each engine run | The entry odds, fixed; the new build shows the current price beside them | Both apps show the same entry price; product to confirm |
| More than one game pick for a game and region | At most one | Arrays list all; a one-pick slot shows one by the slot rule | Projection rule; product to confirm |
| au picks | NBA copies the us pick into au | au has its own picks | Product to confirm |
| A cancelled pick | Hidden (the BFF drops `cancelled`) | Hidden | No change |
| `awaiting_result` | Not a known word | Written as the league's word for a started, ungraded pick (`scheduled`) | Projection rule |
| My Picks and follows | Ids of the pick shown | The same ids in both builds | No change |
| Free-user locks | Per-flag stripping on the legacy route | Unchanged | No change. The new leak rule applies only to `/v4/edge-picks` |
| Push alerts | From an external producer; the BFF ignores `game_edge_picks` and `player_edge_picks` triggers unless their product is `picks` | Unchanged if the producer watches the legacy documents, which are written only when their content changes | Push producer to be identified; the shadow counts events |
| A push (stake returned) | NBA game picks: stays ungraded | Shown as void | Projection rule; product to confirm |
| A void pick outside NBA player picks | Varies by league | Shown as void | Projection rule |

### Cost and performance

- **Writes:** derived documents are written on publish, status changes and settlement, never on an observation alone, so legacy writes are at or below today's, where every engine run rewrites them. The new records add the KDD-001 figures: about $3.50 to $17 a month at 1,000 to 5,000 records a day.
- **Reads:** older builds keep today's read costs. The new build adds the shared-cache reads in KDD-001.
- **Stage B** removes one legacy write path per league as routes move over.

### Consequences

**Positive**

- No user is forced to update, and none sees a picks experience that disagrees with another user's.
- Saved slips and follows resolve in every build, with no id bridge.
- Older builds can be retired on evidence, route by route.

**Negative, and what handles it**

| Cost | Handling |
| --- | --- |
| The Publish Engine maintains a projection to every legacy document shape, including `c-outcome` results | One projection, fixture-tested and shadow-run; retired shape by shape in Stage B |
| `game_prediction` and `c-outcome` also carry another producer's content | The Publish Engine joins it in and writes each document once; nothing else writes them for v4 games |
| The BFF serves two response families for a long time | Both read one source; Stage B shrinks the legacy family over time |
| Older builds see the behaviour changes listed above | Product confirms and announces them with the redesign |
| Ids of v4 games change format in older builds outside NBA (NFL, MLB, WNBA and EPL ids take the NBA format and gain the line) | Ids are opaque to every reader checked; the app team confirms the app |

### Validation

1. **Shadow.** For each league, run the projection from production inputs into containers no user reads for a full slate cycle. Compare every legacy route, at every `api_version` in use, with what today's pipeline serves for the same games. Only the differences listed above are allowed.
2. **Projection fixtures.** Every row of the projection table and the slot rule, per league, including a slot whose pick is cancelled and a push.
3. **Cross-version identity.** Save and follow a pick in a version 5 build, open My Picks in a version 6 build, and the reverse, in a league that version 5 is allowed to see. Both resolve to the same pick, with the same entry values and, once graded, the same result. Repeat for a pick outside a one-pick slot, saved in the new build: the older build shows its snapshot values and its result.
4. **Switch.** Turn a league off and on for the new build during a live slate. Older builds' responses do not change at any point.
5. **Mixed population.** Run the mock with users split across versions 5 and 6 on one day. Both views agree on picks, prices and results.
6. **Push.** Count push events per slate in the shadow and in production: the shadow sends no more.

### Open items

- Which app versions in the field include `ForceUpdateGate`, and so can be forced to update (app team).
- Replace `|` in follow topics in `queue-fcm-device.ts` as `target-follow.ts` does (BFF; a bug today, independent of v4).
- Which service produces push events, and what it watches (data engineering).
- Whether the partner API (`api-partners`) or any other service reads the pick containers directly (data engineering).
- Where the per-league switch and v4 start date live. The co-existence plan's registry is the likely home (BFF).
- Each league's legacy status words, for the projection fixtures (data engineering).
- The behaviour changes listed above (product).
- The usage threshold and notice period for retiring a legacy route (product).

### Sources

- mobile-server develop:
  - `src/lib/match/canonical/gate.ts` (version gate);
  - the functions listed under Context (readers of pick documents);
  - `src/lib/my-pick/my-pick.ts`, `resolve-my-picks-list.ts`, `snapshot.ts` (status filter, saved-id resolution, results);
  - `src/lib/match/canonical/picks.ts` (`bet_outcome`), `src/lib/match-data-mapper.ts` (one pick per region);
  - `src/lib/match/game-h2h.ts`, `src/functions/target-follow.ts`, `src/lib/wp-sync/build-daily-match-payload.ts` (id handling);
  - `src/functions/service-bus-push-events.ts` (push consumer).
- app-data dev 2b6f998: `databricks/publisher/transformations_library.py`, `nba/nba_wltp.py`, `nba/nba_ps.py` (legacy documents and ids)
- `edgepicks-redesign/coexistence-cutover-plan.md`, Oct 17 (rules C1 to C9)

---

## KDD-003: The new app shows legacy and v4 picks through one response shape

| | |
| --- | --- |
| Status | Proposed |
| Date | 2026-10-20 |
| Owners | BFF, app team (decide); product (card wording), data engineering (legacy document fields) (consulted) |
| Contract affected | Snapshot API 4.0.0 draft: adds `era` to every pick, with null rules for legacy picks and an example. Producer pick record: none |
| Supersedes | None. Amends KDD-002 point 4 (what the per-league switch does) and makes precise its point 5 (`/v4/edge-picks` reads earlier games through read-only adapters) |

### Decision

1. **The new app's Edge Picks screen shows every pick a user can see, from both eras.** It is not limited to picks published after a league's v4 start, so a league not yet on v4, or a day before its v4 start, still shows its picks.
2. **The era is set per game, by the league's v4 start date** (KDD-002 point 5). A game that starts before it is a legacy-era game; its picks come from today's documents, which are never converted or backfilled. A game that starts on or after it is a v4-era game; its picks come from producer pick records.
3. **The app gets one response shape.** `/v4/edge-picks` returns legacy-era picks translated by the BFF into the snapshot shape. The translation is read-only, follows the mapping below and keeps each league's meaning (C7, C8). The app never parses a legacy document or calls a legacy route for this screen.
4. **Each pick carries `era`: `legacy` or `v4`.** The app picks its card from `era`, never from which fields happen to be null. A v4 pick gets the full card. A legacy pick gets a limited card: no live indicator, no "Edge holds above", no current price beside the entry price, and its price labelled as published.
5. **A legacy pick fills what its documents hold, and nothing is invented.**
   - Always set: id, sport, kind, game, selection, probability, entry price, stake, status, result.
   - Computed by the BFF as for every pick: `entry.edge`, from probability and price, on the display basis.
   - Always null: `current`, `edge_holds_above`, `overlay_key`, `action`. `edge_state` is `unknown`.
   - `model.projection` is null in 4.0.
   - A legacy pick that cannot be mapped into a valid snapshot pick is left out and reported, as for any pick that fails the schema.
6. **The per-league switch falls back to legacy instead of going empty** (amends KDD-002 point 4). With a league's switch off, `/v4/edge-picks` serves that league's v4-era games from their derived legacy documents, as legacy picks. Turning v4 off for a league degrades its cards rather than emptying its screen.
7. **Everything else is one code path.** Ordering, the day window, free-user locking (field groups and the leak rule, redacting the translated model, C4), caching and ETags apply to legacy and v4 picks alike. A day can mix both eras.
8. **Saved ids keep working.** A legacy pick is served under its legacy id, which is what slips and follows saved before the league's v4 start hold. A v4-era pick has one id in both families (KDD-002 point 8).

### Context

- **The backend and the app are built at the same time,** and there is no safe big-bang switch. The backend writes producer pick records and legacy documents side by side (KDD-002), and the new app has to work whatever stage each league has reached.
- **Past games stay in legacy format.** Nothing is backfilled (C7 of the Oct 17 plan, kept by KDD-002).
- **The new screen's features are forward-looking.** Entry against current price, live edge state, "Edge holds above" and cancellation reasons need fields legacy documents do not have: no `current_*`, no `observed_at`, no edge basis or threshold (app-data dev 2b6f998).
- **Leagues will reach v4 at different times.** NBA first. MLB and WNBA end their seasons on Nov 1 on legacy. NFL and EPL follow later, and more leagues are coming. On launch day most leagues on the new screen are still legacy.
- **Legacy values are not entry values.** Today's documents are rebuilt on each engine run (KDD-002 Context). A legacy pick's price and time are those of the latest run, not of first publish, and a pick that disappeared on a line move is not in the documents at all.

### Options considered

| Option | Summary | Verdict |
| --- | --- | --- |
| A. Strictly forward-looking | The new screen shows only v4-era picks | Rejected: on launch day most leagues would show an empty screen, and a user who upgrades would lose the picks screen they had |
| B. The app reads both | The new app calls today's routes for legacy picks and `/v4/edge-picks` for v4 picks | Rejected: two parsers and two locking paths in the app; today's routes do not apply the leak rule; every new league or format change touches the app |
| C. Backfill legacy into producer records | Convert past documents into v4 records | Rejected: past games stay as they are. Legacy documents lack entry values and observations, so a backfill would invent them |
| **D. BFF translates legacy into the snapshot shape, marked by `era`** | One response shape, two card variants | **Proposed** |

### Why D

- **One shape for the app.** Legacy support lives in one place, the BFF, which already reads every legacy document for older builds.
- **The screen works for every league from launch,** whatever stage each league is at, and a league switched off falls back instead of emptying.
- **Nothing is invented.** A legacy pick shows only what its documents hold, and the card says so.
- **The free-user rules apply to every pick,** because locking redacts the translated model, not the document.

### Mapping legacy picks into the snapshot shape

| Snapshot field | Legacy source | Notes |
| --- | --- | --- |
| `id` | The legacy pick id | Unchanged, so saved slips and follows match |
| `kind`, `selection` | NBA: `market`, `selection`, `line`, `stat`, `player_sk`. Format A: `type`, `bet_line` (T1 or T2), the `code` string, `bookmaker.position` | Home or away from the schedule's team\_1 and team\_2; the market and side per the producer page's mapping table |
| `model.probability` | `probability` | A fraction in every league |
| `entry.odds` | `bookmaker.bet_odds` | Decimal and American; Format A player picks write strings, parsed as numbers |
| `entry.line` | NBA `line`; Format A `bookmaker.position` or the `code` | Per the line rule |
| `entry.stake_units` | `bookmaker.stake_units` or `bet_stake` | |
| `entry.source` | `bookmaker.name` | AU wording as for every pick |
| `entry.edge` | Computed from probability and the price | On the display basis, as for every pick; the legacy `edge` field (NBA percentage points) is not used |
| `picked_at` | The document's timestamp (`picks_updated_at` or `timestamp`) | The latest run's time, not first publish; the card shows no "picked at" time for legacy picks |
| `status`, `result` | `pick_status` and `bet_outcome` | By the producer page's table "Values the BFF accepts until producers write this page's statuses" |
| `current`, `edge_holds_above`, `overlay_key`, `action` | None | Null; `edge_state` is `unknown` |

### Consequences

**Positive**

- The new app works from launch, for every league, at every stage of the migration.
- Legacy history is shown without being converted or backfilled.
- The app has one response shape and one locking path.

**Negative, and what handles it**

| Cost | Handling |
| --- | --- |
| The BFF maintains read-only translators for NBA and Format A picks | The same documents it already reads for older builds; fixture-tested per league and frozen once a league's legacy games have settled (C7) |
| Legacy prices are the latest run's, not entry prices | The limited card labels the price as published and shows no picked-at time; product confirms the wording |
| The edge on a legacy card is on the v4 display basis, so it can differ from what an older build shows (NBA shows percentage points) | One basis on the new screen; product confirms |
| Picks that legacy documents dropped (line moves, re-runs) cannot be shown | They are not in the documents; nothing is invented |
| The contract gains `era` | Added to the 4.0.0 draft before agreement, with its null rules in the schema |

### Validation

1. **Fixtures.** For each legacy family (NBA game picks, NBA player picks, Format A per league, game and player), the translation of each fixture validates against the snapshot schema and matches the mapping table.
2. **Coverage.** For one day per league, every pick an older build shows also appears on the new screen as a legacy pick, or is in the BFF's unmappable-pick report.
3. **Mixed day.** A day with legacy and v4 picks of the same sport is ordered by the usual rules, and each card follows its `era`.
4. **Switch fallback.** With a v4 league's switch off, its v4-era games appear as legacy picks under the same ids, and turning the switch back on restores the full cards with no change of id.
5. **Free users.** The leak rule and field groups hold on legacy picks; a locked legacy pick shows no hidden value.
6. **Saved ids.** A slip saved in an older build before a league's v4 start opens in the new build on the same pick.

### Open items

- The limited card's wording for a published (not entry) price, and whether legacy picks show an edge at all (product).
- Whether legacy player picks show a projection, joined from the prediction documents (product, BFF).
- Each league's legacy fields and status words, for the fixtures (data engineering; shared with KDD-002).
- The name `era`, and adding it to the snapshot contract (contract owner).

### Sources

- KDD-002 points 4, 5 and 8, and its Context (legacy documents rebuilt on each run; id handling)
- `edgepicks-redesign/coexistence-cutover-plan.md`, Oct 17 (C4, C7, C8)
- Snapshot API contract 4.0.0 draft (field null rules, field groups, ordering); producer pick record contract (mapping table, legacy status table)
- app-data dev 2b6f998: `databricks/publisher/nba/nba_wltp.py`, `nba_ps.py`, `transformations_library.py` (legacy pick fields)

---

## Template for a new KDD

Copy this section, give it the next number, and add a row to the table at the top.

```markdown
## KDD-NNN: <decision in one line>

| | |
| --- | --- |
| Status | Proposed |
| Date | YYYY-MM-DD |
| Owners | <who decides>; <who is consulted> |
| Contract affected | <contract and section, or "none"> |
| Supersedes | <KDD number, or "None"> |

### Decision
<What is decided, as numbered, testable statements.>

### Context
<The facts that force a decision, each with where it was observed.>

### Options considered
| Option | Summary | Verdict |
| --- | --- | --- |

### Why this option
<The reasons, shortest first.>

### Cost and performance
<Figures, their assumptions and sources, when the decision has a cost.>

### Consequences
<Positive, and negative with how each is handled.>

### Validation
<What has to be measured or shown before the decision is accepted.>

### Open items
<What is still unknown, with an owner.>

### Sources
```