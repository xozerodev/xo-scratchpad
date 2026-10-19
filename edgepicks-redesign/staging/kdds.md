# Edge Picks v4: Key Design Decisions

This log records the key design decisions (KDDs) behind the Edge Picks v4 contracts: what was decided, why, what else was considered, and what it costs. Each KDD is one section, numbered in order and never renumbered. A superseded KDD stays in the log, marked with the KDD that replaces it.

| KDD | Decision | Status | Owners | Date |
| --- | --- | --- | --- | --- |
| [KDD-001](#kdd-001-store-producer-pick-records-one-per-document-in-a-new-cosmos-container) | Store producer pick records one per document, in a new Cosmos container | Proposed | Bet engine, data engineering | 2026-10-19 |
| [KDD-002](#kdd-002-old-and-new-app-versions-coexist-on-one-source-of-truth) | Old and new app versions coexist on one source of truth; legacy documents are derived from the new records, never written independently | Proposed | BFF, app team, data engineering, bet engine | 2026-10-19 |

Statuses: **Proposed** (written, not yet agreed), **Accepted** (every owner has agreed, with the date), **Superseded** (replaced by a later KDD, named in its status), **Rejected** (considered and turned down; kept so it is not proposed again without new facts).

---

## KDD-001: Store producer pick records one per document in a new Cosmos container

| | |
| --- | --- |
| Status | Proposed |
| Date | 2026-10-19 |
| Owners | Bet engine, data engineering (decide); BFF, live edge monitor (consulted) |
| Contract affected | Edge Picks producer pick record 4.0.0, open decision "Document layout and id format" |
| Supersedes | None |

### Decision

1. Producer pick records go into a **new Cosmos container**, separate from the existing `c-wltp-*` and `c-ps-*` containers.
2. Each document holds **one pick in one region**: exactly one producer pick record, with the document `id` equal to `pick_id`.
3. The partition key is **`/game_sk`**.
4. The indexing policy indexes only the paths that are queried: `game_sk`, `region`, `sport`, `pick_status` and `pick_kind`.
5. Three guardrails are part of the decision, not optional tuning:
   - The **BFF reads Cosmos once per region and day into a shared cache**, never once per app request, and applies each user's locking in memory.
   - The **monitor writes an observation only when the price, line or edge state changed**, and at most every 5 minutes per pick.
   - **`pick_id` must not contain `/`, `\`, `?` or `#`**, the characters Cosmos does not allow in a document id.
6. This container is the **only source of pick values**. The documents older app versions read are derived from it, as set out in KDD-002.

### Context

- **Today's layout** (app-data dev 2b6f998): one document per game per pick type (`nba|game_edge_picks|<game_sk>`, `nba|player_edge_picks|<game_sk>`), partitioned on `/game_sk`, with a region map inside the document. Prediction documents share the same containers. Every Publish Engine run replaces the whole document.
- **The whole-document replace is what drops picks.** A pick the engine does not produce on a later run disappears from the document. That breaks the contract's persistence rule: once published, a pick stays until it is settled or void.
- **The contract has one writer.** Only the Publish Engine writes pick documents, and the monitor's observations reach them through it within 5 minutes. With one document per game, every price change on any pick rewrites the whole game document, and concurrent updates to one game conflict.
- **Older app versions keep working for as long as they are supported**, which is open-ended (KDD-002). The store build sends API version 5 and reads the existing documents.
- **Scale is growing.** More than 10 leagues are planned, so 1,000 or more pick records a day (a record is one pick in one region), and plausibly 5,000.

### Options considered

| Option | Summary | Verdict |
| --- | --- | --- |
| A. Keep one document per game in the existing containers, in the new shape | Change the existing documents to hold v4 records | Rejected: breaks the current app before cutover; keeps the whole-document replace that drops picks; every observation rewrites the game |
| B. New document type in the existing containers, one per pick | v4 records beside today's documents, told apart by `doc_type` | Rejected: the existing readers, feeds and backfills would all have to learn to skip the new type; indexing and retention policies stay shared with documents of a different shape; rollback means deleting documents rather than ignoring a container |
| C. New container, one document per game and region | v4 shape, still grouped by game | Rejected: same write amplification and contention as A for observations; persistence still depends on every run rewriting every pick correctly |
| **D. New container, one document per pick** | One producer record per document | **Proposed** |

### Why D

- **Persistence holds by construction.** Upserting one pick cannot drop its siblings. A pick leaves only by changing its own status to cancelled, void or withdrawn.
- **Writes are about 7 times cheaper** than rewriting a game document on every change (cost table below), and writes for different picks never contend.
- **The schema applies directly.** One document is one producer record, so producer CI validates documents against the contract's JSON Schema as they are.
- **Old and new app versions are served side by side.** Older builds keep reading the existing containers, whose pick documents are derived from the new records in the same Publish Engine run (KDD-002). Turning the new screen off for new builds needs no data change.
- **It fits the dev-isolation rule**, which already asks for a separate Cosmos database for the parallel setup in dev.

### Cost and performance

Prices are Microsoft's published US example rates: serverless $0.25 per million request units (RU), provisioned $0.008 per 100 RU/s per hour, storage $0.25 per GB per month. Region and current rates vary, so check the pricing page before budgeting. Whether the account is serverless or provisioned was not found in the repositories, so both are shown.

A producer record is about 930 bytes of JSON, about 1.2 KB once stored with Cosmos's own fields.

**Writes.** Assumptions: each record gets about 3 writes for publish, status changes and settlement. It is observed every 5 minutes for the 12 hours before its game, and 30% of observations change something worth writing. A write of one ~1.2 KB document is taken as about 10 RU, and a rewrite of a ~15 KB game document as about 75 RU.

| Records a day | Writes a day | One per pick | One per game |
| --- | --- | --- | --- |
| 1,000 | 46,000 | 0.5M RU/day, ~$3/month, ~5 RU/s average | 3.5M RU/day, ~$26/month, ~40 RU/s |
| 3,000 | 139,000 | 1.4M RU/day, ~$10/month, ~16 RU/s | 10.4M RU/day, ~$78/month, ~120 RU/s |
| 5,000 | 231,000 | 2.3M RU/day, ~$17/month, ~27 RU/s | 17.3M RU/day, ~$130/month, ~200 RU/s |

**Reads.** The bytes read for a region's day are the same in either layout, so read cost depends on how often the BFF goes to Cosmos, not on the layout. One region-day read is about 390 RU at 1,000 records a day and about 1,950 RU at 5,000. Assumptions for the comparison: 2 regions, 3 days in view (yesterday, today and tomorrow), and 2,000 active users each refreshing once a minute for 3 hours a day.

| BFF read pattern | 1,000 records a day | 5,000 records a day |
| --- | --- | --- |
| Shared cache per region and day, rebuilt every 60 seconds | ~3.4M RU/day, ~$25/month | ~16.8M RU/day, ~$126/month |
| Cosmos read on every app request | ~140M RU/day, ~$1,050/month | ~700M RU/day, ~$5,300/month |

Rebuilding the shared cache only when picks have changed, rather than every 60 seconds, cuts the cached figure further. The BFF already keeps a 60-second response cache for freemium responses (mobile-server develop, `src/freemium/cache`), so the pattern exists.

**Throughput mode.** The 5,000-a-day case averages under 30 RU/s plus the cache rebuilds, with short bursts after each engine run. That fits serverless, or provisioned 400 RU/s at about $23 a month (1,000 RU/s autoscale at about $58 a month for headroom).

**Storage.** At 3,000 records a day: about 1.8 GB a year, about $0.45 a month. No time-to-live is set, because settled picks feed the track record.

**Performance.**

| Aspect | Expectation |
| --- | --- |
| Partitions | About 20 documents per game, so no hot partitions. The container stays in one physical partition for years, so a query across games costs the same as one within a partition |
| Read latency | A region-day of up to 2,500 records is a few pages of query results, tens of milliseconds, and normally served from the BFF's cache |
| Write latency | Single-digit milliseconds per document; no conflict retries, because no two writers share a document |
| BFF query | Find the day's games from the schedule the BFF already reads, then query picks by those `game_sk` values and the region. No extra field is needed in the record |

### Consequences

**Positive**

- The persistence and one-writer rules hold without depending on every engine run behaving.
- Write cost and contention fall by about 7 times compared with game documents.
- Producer CI validates stored documents directly against the contract schema.
- Older app versions keep working without a migration in place (KDD-002).

**Negative, and what handles it**

| Cost | Handling |
| --- | --- |
| The BFF needs a new read path (query instead of point reads) | Built once, behind the shared region-day cache |
| The Publish Engine also writes the legacy documents, derived from the new records, for as long as any supported app version reads them | The legacy writes cost what they cost today, so nothing is added; they are retired league by league and route by route under KDD-002 |
| My Picks entries and follows saved in an older build carry legacy ids | Each record carries the ids older builds saved (`legacy_pick_ids`, KDD-002) |
| Per-request Cosmos reads would be expensive | Guardrail 1: the shared cache is part of this decision |
| Frequent monitor updates add write volume | Guardrail 2: write on change only, at most every 5 minutes |

### Validation

Before this KDD is accepted, run in the dev Cosmos database set aside for the parallel setup:

1. Write 3,000 sample producer records that validate against the producer schema, using the proposed indexing policy.
2. Record Cosmos's reported request charge for an insert, a full replace and a partial update of the `current_*` fields.
3. Record the request charge and latency of one region-day query (about 1,500 records).
4. Replace the estimates above with the measured figures. Accept if the measured cost at 5,000 records a day stays within twice the estimate.

### Open items

- Whether the Cosmos account is serverless or provisioned (data engineering).
- The container name for each environment, following the existing `c-<name>-<env>-<nn>` pattern.
- Adding the id-character restriction to rule 1 of the producer pick record contract.

### Sources

- [Understand your Azure Cosmos DB bill](https://learn.microsoft.com/en-gb/azure/cosmos-db/understand-your-bill) (example rates)
- [Request units in Azure Cosmos DB](https://learn.microsoft.com/azure/cosmos-db/request-units) (what drives RU charges)
- [Azure Cosmos DB serverless pricing](https://azure.microsoft.com/en-us/pricing/details/cosmos-db/serverless/) (current rates)
- app-data dev 2b6f998: `databricks/publisher/nba/nba_wltp.py`, `nba_ps.py`, `build_transformation_map.ipynb` (today's documents and containers)
- mobile-server develop: `src/freemium/cache/ENTITLEMENT_CACHE_DECISIONS.md` (the BFF's 60-second response cache)

---

## KDD-002: Old and new app versions coexist on one source of truth

| | |
| --- | --- |
| Status | Proposed |
| Date | 2026-10-19 |
| Owners | BFF, app team, data engineering, bet engine (decide); product (consulted on retirement and on behaviour changes older builds will see) |
| Contract affected | Edge Picks producer pick record: adds `legacy_pick_ids` in a 4.x minor version. Snapshot API: none |
| Supersedes | Rule C5 ("no id bridge") of the Oct 17 co-existence plan, for app versions only |

### Decision

1. **Coexistence is open-ended.** No date is assumed by which users have moved to the new app. Every app version still supported keeps getting the responses it gets today, until its routes are retired under point 7.
2. **One source of truth.** Producer pick records (KDD-001) are the only place a pick's values are decided. Everything an older build reads about picks is derived from them. Nothing writes pick values for older builds independently.
3. **Version routing stays in the BFF.** Every request already carries `api_version`, and the BFF already serves staged content only from version 6 (`gate.ts`). The new Edge Picks screen calls `GET /v4/edge-picks`; older builds keep calling today's routes and receive today's shapes.
4. **A server-side switch per league** turns the new screen's data on or off for new builds without an app release. Turning it off returns nothing from `/v4/edge-picks` for that league; older builds are unaffected either way.
5. **Two stages per league:**
   - **Stage A, derived legacy documents.** In the same run, the Publish Engine writes the new records and projects them into the legacy documents (`game_prediction.top_picks`, `game_edge_picks`, `player_edge_picks`, `player_top_picks`). It uses one deterministic projection, tested against fixtures. Today's BFF routes read those documents unchanged.
   - **Stage B, BFF adapters.** A legacy route moves to reading the new records through an adapter once its responses are proven equivalent (Validation). Legacy documents for a league stop being written only when no route and no other reader (push fan-out, WordPress feed, partner API) still reads them.
6. **An identity bridge.** Each record carries the ids older builds saved for it, so a slip or follow made in one build resolves in the other. This adds `legacy_pick_ids` (array of strings, empty when none) to the producer pick record in a 4.x minor version. My Picks resolves a saved id by `pick_id` first, then by `legacy_pick_ids`.
7. **Retirement is a product decision made on data.** A legacy route is retired only when the oldest supported app version no longer calls it. That is decided from the share of active users on each `api_version` (for example, under 1% for 30 days), or by a forced update if the app supports one.

### Context

- **Users cannot be forced onto the new build.** The release is a gradual rollout, so for weeks most users stay on the old build, and some never update.
- **The store build sends `api_version` v5.** `RELEASE_API_VERSION_MAJOR = 6` in `src/lib/match/canonical/gate.ts` (mobile-server develop) already withholds staged content from earlier versions. The push fan-out and the WordPress feed carry no client version and are not gated.
- **Today's readers of pick documents** (mobile-server develop): `match.ts`, `match-v3.ts`, `matches.ts`, `matches-top-predictions.ts`, `matches-top-predictions-v3.ts`, `my-picks-v2.ts` and `service-bus-push-events.ts`. No minimum-version or forced-update check was found in the BFF.
- **The Oct 17 co-existence plan covers producer families,** not app versions. Each game is pinned to one schema family, with no id bridge (its C5). That still holds for producer families. But the same game is shown to old and new builds at the same time, so the same pick is seen under two ids, and a bridge is needed.
- **Legacy pick ids** differ from v4 ids. NFL, MLB, WNBA and EPL use `{game_sk}_{bet_type}_{region}`, without the line. NBA uses `{game_sk}|{market}_{selection}|…|{region}` (app-data dev 2b6f998).

### Options considered

| Option | Summary | Verdict |
| --- | --- | --- |
| A. Independent dual write | Keep today's pipeline for older builds; add the new pipeline for the new build | Rejected: two sources drift. The same game would show different picks, prices or results in the two apps. The NBA engine's dev and tst branches already differ in how they select picks |
| B. Clean cutover with forced upgrade | Switch each league once; require the new build | Rejected: upgrades cannot be forced, and the rollout is gradual |
| C. BFF adapters from the start | Stop legacy documents when the new records start; serve every older route through adapters | Rejected for launch: every legacy route has to be proven equivalent before any league moves, which concentrates the risk at launch. Readers outside the versioned routes (push, WordPress, partner API) would break |
| **D. Derived legacy documents, then adapters, league by league** | Stage A at launch, Stage B per route when proven | **Proposed** |

### Why D

- **One truth, two presentations.** Both apps show the same entry price, probability, stake and result for the same pick, because both come from one record.
- **Nothing changes for older builds on day one.** Their routes read the same documents in the same shape, now produced by a projection instead of a separate pipeline.
- **Risk is spread over time.** Each route moves to an adapter when it is proven, not all at launch.
- **Rollback is a switch.** Turning a league off for the new build leaves the records, the derived documents and older builds untouched.
- **Retirement stays in our hands,** based on usage data, not on when users choose to update.

### What older builds will see

The derived documents carry the same fields and words as today. Some behaviour follows the new records:

| Behaviour | Older build today | Older build under D | Handling |
| --- | --- | --- | --- |
| A line move | NBA: the pick disappears | The pick stays at its entry line | An intended fix; product to confirm and announce |
| An engine re-run that would drop a pick | The pick disappears | The pick stays until it is cancelled | An intended fix (persistence rule) |
| A cancelled pick | Hidden (the BFF drops `cancelled`) | Hidden | No change |
| `awaiting_result` | Not a known word | Written as the legacy word for a started, ungraded pick (`scheduled`) | Projection rule |
| Free-user locks | Per-flag stripping on the legacy route | Unchanged | No change. The new leak rule applies only to `/v4/edge-picks` |
| Push alerts | From the legacy documents | From the derived documents, same content | No change |

### Cost and performance

- **Writes:** the derived legacy documents are the writes the Publish Engine already makes today, so Stage A adds nothing. The new records add the KDD-001 figures: about $3 to $17 a month at 1,000 to 5,000 records a day.
- **Reads:** older builds keep today's read costs. The new build adds the shared-cache reads in KDD-001.
- **Stage B** removes one legacy write path per league as routes move over.

### Consequences

**Positive**

- No user is forced to update, and none sees a picks experience that disagrees with another user's.
- Saved slips and follows survive an upgrade.
- Older builds can be retired on evidence, route by route.

**Negative, and what handles it**

| Cost | Handling |
| --- | --- |
| The Publish Engine maintains a projection to every legacy document shape | One projection, fixture-tested; retired shape by shape in Stage B |
| The BFF serves two response families for a long time | Both read one source; Stage B shrinks the legacy family over time |
| The contract gains `legacy_pick_ids` | A 4.x minor version, shipped readers-first |
| Older builds see two behaviour changes (picks survive a line move or a re-run) | Listed above; product confirms and announces them with the redesign |

### Validation

1. **Projection equivalence.** For each league, replay a full slate through the new records and the projection. Compare every legacy route, at every `api_version` in use, with what today's pipeline serves for the same games. Only the differences listed above are allowed.
2. **Cross-version identity.** Save a pick in an older build, open My Picks in the new build, and the reverse. Both resolve to the same pick, with the same entry values and result.
3. **Switch.** Turn a league off and on for the new build during a live slate. Older builds' responses do not change at any point.
4. **Mixed population.** Run the mock with users split across versions 5 and 6 on one day. Both views agree on picks, prices and results.

### Open items

- Whether the app can force an update or enforce a minimum version (app team).
- Whether the partner API (`api-partners`) or any other service reads the pick containers directly (data engineering).
- Where the per-league switch lives. The co-existence plan's registry is the likely home (BFF).
- The usage threshold and notice period for retiring a legacy route (product).
- Adding `legacy_pick_ids` to the producer pick record contract (contract owner).

### Sources

- mobile-server develop: `src/lib/match/canonical/gate.ts` (version gate), and the functions listed under Context (readers of pick documents)
- app-data dev 2b6f998: `databricks/publisher/transformations_library.py`, `nba/nba_wltp.py`, `nba/nba_ps.py` (legacy documents and ids)
- `edgepicks-redesign/coexistence-cutover-plan.md`, Oct 17 (producer-family co-existence, rules C1 to C9)

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