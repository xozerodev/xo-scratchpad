# Edge Picks v7: mock records in Cosmos (plan)

Status: draft for review, 2026-10-20. Nothing here is built yet.

This plan covers serving the Edge Picks redesign's mock data **from Cosmos**, through the BFF code that will later read real producer records. The mock records go into a new container. It is layer L2 of [option-b-plan.md](option-b-plan.md) §8.5 and §8.7, brought forward from P4, together with the parts of BE-9 and BE-10 it needs (§5.6, §10.4).

## 1. Summary

- **What:** a new Cosmos container in the existing dev content database (`app-read-dev`) that holds mock producer pick records, one per document, in the KDD-001 layout ([kdds.md](kdds.md), KDD-001). A seeding tool writes them, generated from the dev documents the BFF already serves, and a new `cosmos` record source reads them. The app team gets `era: v4` blocks served from Cosmos on the dev BFF at `api_version=v7`.
- **Why Cosmos and not only the in-memory mock:** it runs the read path, validation, consistency checks and caching that live data will use. It keeps records stable between requests and lets us change one pick's state on request. It is also the dev rehearsal of KDD-001's container.
- **Reading two containers side by side** (legacy documents and new records) is what the route already does with four containers; §4.0 sets out why it is safe.
- **What it costs:** about 6 BFF days for what the app team needs (§6), plus a container and at most two role assignments in the dev Cosmos account. A further 3 days add the cache's rebuild lock and an automatic refresh; P4 needs the lock anyway.
- **The decisions needed** are listed in §10. D-M1 is decided: no separate database. D-M2 (who creates the container) blocks the start.

## 2. Where we are, and the order of next steps

The P1 and P2 code is committed on `mobile-server` `feat/edge-picks-v7`, not pushed and not deployed. The dev settings in `infra/envs/dev/app_settings.tf` already select the in-memory mock (`EDGE_PICK_SOURCE=mock`, layer L1), but nothing is applied.

Recommended order:

| # | Step | Unblocks | Effort |
| --- | --- | --- | --- |
| 1 | Push `feat/edge-picks-v7`, open the PR, review, deploy to dev, apply the dev settings | The app team gets v7 blocks on the dev BFF **now**, from the in-memory mock (L1), with the mock parameters for every state | Review time, plus a deploy |
| 2 | Hand the app team `docs/edge-picks-v7/` (JSON Schema, samples, README) | Building cards before step 1 lands | Done, needs sharing |
| 3 | Build this plan (L2): the container, the seeder, the `cosmos` source | v4 blocks from Cosmos, stable and editable states, the real read path tested | About 6 days (§6) |
| 4 | Run the P2 jobs in dev, then tst (snapshot backfill, re-subscribe), dry run first | My Picks fixes on existing slips | ½ day |
| 5 | Update `kdd23-design.md` and KDD-003 to option B once the team has agreed | Docs match the code | ½ day |

Step 1 does not depend on this plan, and this plan does not replace it: L1 stays available, so the app team keeps the mock parameters (`edge_pick_scenario` and the others) while L2 is built, and afterwards through a per-request switch (§4.3).

## 3. What L2 adds over L1, and what it does not

| | L1: in-memory mock (built) | L2: records in Cosmos (this plan) |
| --- | --- | --- |
| Where records come from | Generated on every request from the listed picks | Read from a Cosmos container, written by the seeder |
| Code path | Mock source; no I/O | The `cosmos` source live data will use: query, validation, consistency checks, cache, failure handling |
| States over time | Recomputed from `now` on every request | Advance when the refresh runs, and follow the persistence rule (a cancelled pick stays cancelled) |
| Changing one pick's state | Query parameters change every eligible pick | Pin a state on a chosen pick (§4.4); the app team sees it on every device |
| What the app team can rely on | Every state on demand | The same records for everyone, as live data will behave |
| Rehearses KDD-001 | No | Layout, partition key, indexing, request charges, cache |
| Needs infrastructure | No | A container and role assignments |

L2 does not make the data real. The records are still generated from the dev NBA documents by the same generator, and the dev documents end on 2026-11-03 (§9, R-1).

## 4. Design

### 4.0 Legacy and new data in two containers: can the BFF read both?

Yes. The question is whether the BFF can serve one response from the legacy documents (today's schema, in today's containers) and from producer records (the v4 schema, in a new container). It can, for these reasons:

1. **It is the pattern the route already uses.** `GET /v3/matches/:date/top-predictions` reads four containers in `app-read-dev` with four queries: the schedule (`c-sch-dev-01`), game documents (`c-wltp-dev-01`), player documents (`c-ps-dev-01`) and outcomes (`c-outcomes-dev-01`). It joins them in memory by `game_sk` (`src/functions/matches-top-predictions-v3.ts`, around line 217; each container comes from `getReadOnlyDatabase().container(name)` in `src/lib/cosmos.ts`). The records container is a fifth query through the same client, database and identity.
2. **The two schemas never mix in one document.** The list of picks still comes from the legacy documents, unchanged. A record only adds the `edge_pick` block to the listed pick with the same `pick_id`. Old documents keep the old schema; new records keep the new one.
3. **Each audience reads only what it needs.** At `api_version` 6 and below the route never queries the records container (the v7 gate runs before the read), so old app builds see exactly what they see today. At v7 the route reads both. This is the coexistence KDD-002 asks for, with the legacy containers untouched.
4. **No transaction is needed across containers.** The two are read separately and can disagree for a moment, for example during a data reload. The existing per-pick consistency check (`recordMismatch`: region, `game_sk`, entry price) catches that, and the pick gets a legacy block. A disagreement can hide a v4 block; it can never show wrong data.
5. **`game_sk` types.** The content documents store `game_sk` as a number in some containers and a string in others, which is why `gameSkInClause` matches both. Records store it as an integer (producer schema), the seeder writes integers, and the records query uses numbers only.
6. **Cost and latency.** One more query per uncached request, at most once per region and `game_sk` every 60 seconds through the cache (§4.3.1), with a 2-second limit after which the response uses legacy blocks. A region-day of records is a few hundred RU and tens of milliseconds.
7. **It is how live data will be read.** The real KDD-001 container is expected in the same content database (`app-read-<env>`), so this setup rehearses production's layout. Moving from mock to real records changes `EDGE_PICK_RECORDS_CONTAINER` and `EDGE_PICK_RECORD_CHECKS`, not code.

What a shared database changes, and how the plan handles it:

| Concern | Handling |
| --- | --- |
| `app-read-dev` belongs to data engineering, and the Publish Engine writes its containers | Ask data engineering to agree to the container and to confirm their tooling never drops or recreates containers it does not know (D-M2) |
| The seeder could write to a content container by mistake | The write guard tests the **container** name (it must contain both `edge` and `mock`) and refuses any container the BFF reads content from (`COSMOS_CONT_*` and `COSMOSDB_*_CONTAINER` settings) (§4.4) |
| If the database has shared throughput, a seeding burst takes RU from the content containers the BFF reads | The seeder throttles its writes (about 50 a second) and backs off on 429. A full seed is about 2,000 upserts, about 20,000 RU |
| Role assignments | The BFF identity's existing read role on `app-read-dev` covers the new container if it is scoped to the database or the account. Write access for the seeder is scoped to the new container only (§4.1) |
| KDD-001's Validation section names "the dev Cosmos database set aside for the parallel setup" | Out of date once this is decided; update KDD-001's wording with the docs pass (§2, step 5) |

### 4.1 The container

| Item | Value | Why |
| --- | --- | --- |
| Account | `xo-sports-dev` (the dev BFF's account, `COSMOSDB_ACCOUNT_ENDPOINT`) | No new account or network path |
| Database | The existing content database `app-read-dev` (`COSMOSDB_READ_ONLY_DATABASE_NAME`) | Decided (D-M1): no separate database. The BFF already reads it; see §4.0 |
| Container | `c-edge-picks-mock-dev-01` | Says what it holds. The real KDD-001 container gets its own name later |
| Partition key | `/game_sk` | KDD-001 |
| Document `id` | The record's `pick_id` | KDD-001. The dev ids carry a region suffix (`…|us`, `…|au`), so a US and an AU record never collide. The seeder refuses to write if two regions would share an id (see the N1 finding in [kdds_feedback_assessment.md](kdds_feedback_assessment.md)) |
| Document body | Exactly one producer record (37 fields, [conf-schema-contracts.md](conf-schema-contracts.md)), plus Cosmos's own fields | A reader can validate a stored document once the Cosmos fields are removed |
| Indexing | Include `/game_sk/?`, `/region/?`, `/sport/?`, `/pick_status/?`, `/pick_kind/?`; exclude `/*` | KDD-001 |
| Throughput | 400 RU/s on the container if the database has dedicated per-container throughput; nothing if it has shared database throughput or the account is serverless (to be confirmed) | About 2,000 records of about 1.2 KB (the dev data has 1,070 picks; some leagues add more). A region-day query is a few hundred RU |
| Time to live | None | Settled records feed the track record. The seeder's `--reset` empties the container when needed |

Creating it (by whoever holds control-plane rights on the account; the repo's Terraform does not manage Cosmos):

```bash
az cosmosdb sql container create --account-name xo-sports-dev --resource-group <rg> --database-name app-read-dev --name c-edge-picks-mock-dev-01 --partition-key-path /game_sk --idx @edge-picks-indexing.json --throughput 400
```

Leave out `--throughput` if the database has shared throughput.

`edge-picks-indexing.json`:

```json
{
  "indexingMode": "consistent",
  "includedPaths": [
    { "path": "/game_sk/?" }, { "path": "/region/?" }, { "path": "/sport/?" },
    { "path": "/pick_status/?" }, { "path": "/pick_kind/?" }
  ],
  "excludedPaths": [{ "path": "/*" }]
}
```

Data-plane access:

| Principal | Role | Why |
| --- | --- | --- |
| The dev BFF identity (the managed identity whose client id is `AZURE_CLIENT_ID` in `infra/envs/dev/app_settings.tf`; the site has `mi-cosmodb-dev` and `mi-publish-eng-dev` attached, to be confirmed which) | Cosmos DB Built-in Data Reader (`00000000-0000-0000-0000-000000000001`) | The `cosmos` source reads. Nothing to add if its existing read role on `app-read-dev` is scoped to the database or account; otherwise assign it on the new container |
| Whoever runs the seeder (a named Entra group of BFF developers), and the BFF identity only if the timer refresh is chosen (D-M3) | Cosmos DB Built-in Data Contributor (`00000000-0000-0000-0000-000000000002`), scoped to the new container only | The seeder writes; no write access to the content containers |

```bash
az cosmosdb sql role assignment create --account-name xo-sports-dev --resource-group <rg> --role-definition-id 00000000-0000-0000-0000-000000000002 --principal-id <principal-id> --scope "/dbs/app-read-dev/colls/c-edge-picks-mock-dev-01"
```

### 4.2 What the records hold, and how they change

The seeder runs the generator of [option-b-plan.md](option-b-plan.md) §8.3 (`src/lib/edge-picks/v7/mock/generate.ts`) on the same listed picks the route serves, so every record matches a listed pick's id and entry price. That is what lets the BFF's consistency check (`recordMismatch`: region, `game_sk`, entry price) pass.

**The day.** The generator assigns the nine required scenarios per "day". L1's day is one response (one region, the requested date and offset). The seeder's day is one region and one UTC date of `game_datetime`, so every UTC day with at least nine eligible picks has every edge state and cancel reason. An app user in another offset still sees all of them over a few days. The equivalence test (§7) uses offset 0, where the two match exactly.

**Refresh.** A record written once goes stale: a pick seeded "open" stays open after its game starts. The seeder's refresh mode reruns the generator at the current time and merges the result into the stored record under rules a real producer must also follow:

| Field group | Rule on refresh |
| --- | --- |
| Identity and entry (`pick_id`, `region`, `sport`, `game_sk`, selection, `line`, `entry_*`, `probability`, `edge_basis`, `edge_threshold`, `stake_units`, `pick_date_time`) | Never changed. They are frozen at publish (contract persistence rule) |
| Status | Moves forward only: `open` → `awaiting_result` → `settled` or `void`. A record in `cancelled`, `settled` or `void` never changes status again, even if the generator would now pick something else (it assigns `cancelled` only to open picks, so without this rule a cancelled pick would reopen at kick-off) |
| Observation (`current_*`, `observed_at`, `is_closing`, `pulled`, `edge_status`) | Taken from the new run. With drift on, live and narrowing prices move every 5 minutes |
| Outcome | Taken from `c-outcomes` through the generator's lifecycle (Appendix A.4) |
| A pick no longer in the documents | The record stays (persistence rule). The BFF only builds blocks for listed picks, so it is not shown until cancelled-pick injection (BE-11) exists |
| A pick whose document price changed (a dev data reload) | Mock only: the record is rebuilt from the new price and the run logs it. A real producer would publish a new pick instead |

Every write is a whole-record upsert guarded by the document's etag (KDD-001 guardrail 2), validated before it is written.

**Pinned states.** A JSON file of pins, `script/edge-picks/mock-pins.json`, holds `{ "pick_id": "…", "scenario": "suspended" }` entries. The seeder applies them on every run, within the same status rules (a pin cannot reopen a settled pick). The app team asks for a state on a pick; a BFF developer adds a pin and runs the seeder. The file is in the repo, so every pin is reviewed and dated.

**Leagues.** NBA first (the dev NBA 2026 documents are the only canonical data). The seeder can also seed the Format A leagues in dev (NFL, EPL, MLB); `EDGE_PICKS_V4_LEAGUES` decides which leagues the BFF turns into `era: v4` blocks (D-M5).

### 4.3 The BFF read path (`cosmos` source)

New file `src/lib/edge-picks/v7/cosmos-record-source.ts`, behind the existing `PickRecordSource` interface (`src/lib/edge-picks/v7/record-source.ts`), returned by `createRecordSource("cosmos")` instead of today's "not built yet" null.

**`load(args)`:**

1. Take the `game_sk` values of the listed picks whose league is in `EDGE_PICKS_V4_LEAGUES` and not switched off by the Redis kill switch (the existing `config.ts` rules).
2. Read them through the cache (§4.3.1): `SELECT * FROM c WHERE c.region = @region AND ARRAY_CONTAINS(@gameSks, c.game_sk)`.
3. Strip Cosmos's fields (`_rid`, `_self`, `_etag`, `_attachments`, `_ts`, `id`), validate each document with `ProducerRecordSchema` and `recordInvariantViolations`. An invalid record is skipped and reported (`record_invalid`); its pick gets a legacy block.
4. Return the records keyed by `pick_id`. The existing `buildBlocks` then runs `recordMismatch` and builds v4 blocks; nothing downstream changes.

**Validation profile.** Mock records copy two legacy values on purpose: reused ids that do not follow the id formula, and the document's American entry price, which often does not match the conversion rule (§8.3 step 11). A new setting `EDGE_PICK_RECORD_CHECKS=mock` applies the same two exemptions as L1, and is honoured only where the existing production guard allows the mock (`isNonProductionEnvironment`). Anything else means full checks. It also sets `edge_pick_meta.source` to `mock`, so nobody mistakes seeded records for live ones; with full checks the source is `live`.

**Failure.** A Cosmos error, or no answer within 2 seconds, gives legacy blocks for the whole response and one `source_unavailable` report. The request never fails and no pick is dropped (§5.6).

**Settings** (new; the container is read from the content database, `COSMOSDB_READ_ONLY_DATABASE_NAME`):

| Setting | Dev value | Default |
| --- | --- | --- |
| `EDGE_PICK_SOURCE` | `cosmos` | `none` |
| `EDGE_PICK_RECORDS_CONTAINER` | `c-edge-picks-mock-dev-01` | none: the `cosmos` source is off without it, with a one-time error log |
| `EDGE_PICK_RECORD_CHECKS` | `mock` | `full` |
| `EDGE_PICKS_V4_LEAGUES` | `nba` | empty |

**Per-request source switch.** A new mock parameter, `edge_pick_source=mock|cosmos|none`, honoured only with `EDGE_PICK_MOCK_PARAMS=on` outside production, picks the source for one request. The app team keeps L1's `edge_pick_scenario` and the other parameters with `edge_pick_source=mock` while dev defaults to Cosmos. Such a request bypasses the free-user cache, like every honoured mock parameter today.

#### 4.3.1 Cache, in two steps

- **First (needed by the app team):** the existing `getOrLoad` helper (`src/freemium/cache/ttl-cache.ts`), keyed `ep:rec:{region}:{game_sk}` with a 60-second TTL. It is already a shared Redis cache, but it has no lock (two instances whose key expires together both read Cosmos) and no fallback (with Redis down, every request reads Cosmos). Both are acceptable on dev traffic.
- **Then (BE-9, needed before any live league):** a rebuild lock (`SET ep:lock:<key> <instance> NX PX 10000`; other instances serve the previous value or wait up to 2 seconds) and a per-instance in-memory cache as the fallback when Redis is down (KDD-001 guardrail 1, test V-LIVE-1).

### 4.4 The seeder

New script `script/edge-picks/seed-mock-records.ts`:

```
npx ts-node -r tsconfig-paths/register -P tsconfig.json script/edge-picks/seed-mock-records.ts \
  --from 2026-10-20 --to 2026-11-03 --region us,au --league nba \
  [--now <iso>] [--seed 0] [--drift] [--pins script/edge-picks/mock-pins.json] \
  [--apply] [--reset] [--watch 300]
```

1. **Reads** schedules, documents and outcomes from the configured read database (`COSMOSDB_READ_ONLY_DATABASE_NAME`, dev by default), and lists each game's picks per region with `getAllAvailableTopPicksForGame`, with staged content released (dev stages `nba:2026`; v7 sees it).
2. **Generates** records with §8.3, applies pins, merges with the stored records under the rules in §4.2, and validates every record with the mock profile.
3. **Writes** with an etag-guarded upsert, only with `--apply`. Without it, it is a dry run that prints, per league, region and day: records new, changed and unchanged, statuses, edge states, and any validation failures.
4. **Guards** before any write: the target container's name contains both `edge` and `mock`; it is not any container the BFF reads content from (`COSMOS_CONT_*`, `COSMOSDB_*_CONTAINER`); nothing in the environment says production (`isNonProductionEnvironment`, `EDGE_PICK_ENVIRONMENT`); no two regions share an id. Any failure stops the run before it writes.
5. **`--reset`** deletes every document in the target container, behind the same guards and a confirmation prompt.
6. **`--watch <seconds>`** repeats the refresh until stopped (the manual form of D-M3).

It writes only to the mock container, never to a content container, and throttles its writes (about 50 a second, backing off on 429) so it cannot starve the BFF's reads if the database's throughput is shared. The generator stays the single source of mock behaviour for L1, L2 and the offline samples (L3).

### 4.5 Keeping the records fresh (D-M3)

| Option | How | For | Against |
| --- | --- | --- | --- |
| **A. Manual** | A BFF developer runs the seeder after a data reload or a pin, or `--watch` on a dev machine | No new code paths deployed; nothing writes unattended | Records go stale when nobody runs it: games start and the cards still say open |
| **B. Timer function in the dev BFF** (recommended once the app team relies on L2 daily) | `edgePickMockRefresh`, every 5 minutes, runs the seeder's refresh. It is off unless `EDGE_PICK_MOCK_REFRESH=on`, and the seeder's guards apply | Fresh states all day, like the Publish Engine will produce | The BFF identity needs write access to the mock database; the function ships to tst and production too (switched off and guarded) |
| C. Scheduled GitHub workflow | A cron job runs the seeder with a federated identity | Nothing in the app | GitHub's 5-minute cron is best effort; needs a new federated credential |

Recommendation: start with A for the first drop, move to B when the app team starts device testing on L2.

### 4.6 Local runs and CI

The seeder and the `cosmos` source both work against the Cosmos emulator CI already runs (`.github/workflows/pull-request.yml`). A fixture mode (`--fixtures`) seeds from the repo fixtures (`src/lib/edge-picks/v7/__fixtures__/nba-dev-games.json` and the db-seeds) instead of a read database, so a developer can run v7 against L2 locally with no Azure access, and CI can test the whole path.

## 5. Files

| File | Change |
| --- | --- |
| `src/lib/edge-picks/v7/cosmos-record-source.ts` | New: query, validation profile, failure handling |
| `src/lib/edge-picks/v7/record-cache.ts` | New: the record cache on `getOrLoad`, later the lock and in-memory fallback |
| `src/lib/edge-picks/v7/record-source.ts` | Factory returns the `cosmos` source |
| `src/lib/edge-picks/v7/config.ts` | `EDGE_PICK_RECORDS_CONTAINER`, `EDGE_PICK_RECORD_CHECKS`, the `edge_pick_source` parameter |
| `src/lib/edge-picks/v7/build-blocks.ts` | Meta `source` from the profile; per-request source |
| `src/lib/cosmos.ts` | `getEdgePickRecordsContainer()` |
| `src/lib/edge-picks/v7/mock/merge.ts` | New: the refresh merge rules (§4.2), shared by the seeder and the timer |
| `script/edge-picks/seed-mock-records.ts`, `script/edge-picks/mock-pins.json` | New |
| `src/functions/edge-pick-mock-refresh.ts` | New, only if D-M3 is B |
| `infra/envs/dev/app_settings.tf` | The settings in §4.3 |
| `docs/edge-picks-v7/README.md` | How L2 works, how to ask for a pin, the source switch |
| Tests | §7 |

## 6. Work breakdown

| Id | Task | Owner | Depends on | Effort |
| --- | --- | --- | --- | --- |
| ML-1 | Container, indexing, role assignments in `app-read-dev` (§4.1) | Account owner (D-M2) | D-M2 | ½ d |
| ML-2 | `cosmos` source: query, validation profile, failure handling, settings, meta source | BFF | — | 1½ d |
| ML-3 | Record cache on `getOrLoad` (shared, 60 s, no lock yet) | BFF | ML-2 | ½ d |
| ML-4 | Seeder: read, generate, merge rules, pins, guards, dry run, reset, watch, fixture mode | BFF | — | 2 d |
| ML-5 | `edge_pick_source` per-request switch | BFF | ML-2 | ¼ d |
| ML-6 | Tests (§7) | BFF | ML-2 to ML-5 | 1 d |
| ML-7 | Dev rollout, smoke test, app-team handoff (§8) | BFF | ML-1 to ML-6 | ½ d |
| **Subtotal for the app team** | | | | **about 6 d** |
| ML-8 | Rebuild lock and in-memory fallback for the record cache (BE-9), V-LIVE-1 on dev | BFF | ML-3 | 2 d |
| ML-9 | Timer refresh (only if D-M3 is B) | BFF | ML-4, write role | 1 d |

ML-2 and ML-4 can run in parallel. ML-8 is P4 work brought forward; it does not change what the app team sees.

## 7. Validation

| Id | Test | Kind |
| --- | --- | --- |
| V-L2-1 | **Equivalence:** seed the emulator from the fixtures with a fixed `now`, seed and offset 0; the v7 response with `EDGE_PICK_SOURCE=cosmos` deep-equals the response with `mock`, for a subscriber and for the free-user contexts of V-INV-1 | Integration, emulator |
| V-L2-2 | Every v7 invariant and leak check that runs on the mock source (V-INV-1, V-INV-2, V-SEC-1) also passes on the `cosmos` source | Integration, emulator |
| V-L2-3 | An invalid stored record gives a legacy block for that pick and one `record_invalid`; a record whose price differs from the document gives a legacy block and `record_mismatch` | Unit |
| V-L2-4 | Cosmos throws, or answers after 2 seconds: legacy blocks, status 200, one `source_unavailable`; no picks dropped | Unit |
| V-L2-5 | `EDGE_PICK_RECORD_CHECKS=mock` is ignored where the production guard refuses the mock (full checks, meta `live`); a league outside `EDGE_PICKS_V4_LEAGUES`, or switched off in Redis, gets legacy blocks | Unit |
| V-L2-6 | Merge rules: entry fields never change; status never leaves `cancelled`, `settled` or `void`; a pin cannot reopen a settled pick; a pick missing from the documents keeps its record | Unit |
| V-L2-7 | Seeder guards: refuses a container whose name lacks `edge` or `mock`, any content container the BFF reads, a production marker, and an id shared by two regions; dry run writes nothing; writes are throttled and retried on 429 | Unit |
| V-L2-8 | With Redis, Cosmos is read once per region and `game_sk` per 60 seconds; with Redis down, the route still answers (direct reads) | Unit |
| V-L2-9 | Dev smoke: the golden day (2026-10-25) at v7 shows `era: v4` blocks with every edge state, and `edge_pick_meta.source` is `mock`; a pinned pick shows its pinned state after one cache period | Manual, dev |
| V-L2-10 | Record the request charge of a region-day query and of an upsert (KDD-001 Validation steps 2 and 3) | Manual, dev |

## 8. Rollout in dev, and what the app team gets

1. ML-1: create the container in `app-read-dev`; assign roles.
2. Dry run the seeder against dev; review the counts.
3. Seed with `--apply`.
4. Deploy the BFF with the §4.3 settings, keeping `EDGE_PICK_MOCK_PARAMS=on`.
5. Smoke test (V-L2-9) and record charges (V-L2-10).
6. Tell the app team: what changed, the pin process, `edge_pick_source=mock` for the scenario parameters, and the data window.

**Rollback:** `EDGE_PICK_SOURCE=mock` returns dev to L1 on the next request; `none` gives legacy blocks. No data changes are needed, and nothing outside dev is touched.

**For the app team:** nothing in the contract changes. The blocks, the JSON Schema and the samples stay as they are. What changes is that v4 blocks on the dev BFF now come from stored records that advance over time, and specific states can be pinned on request.

## 9. Risks

| Id | Risk | Handling |
| --- | --- | --- |
| R-1 | The dev NBA documents end on 2026-11-03. After that the dev BFF lists no NBA picks, so neither L1 nor L2 shows anything (MK-5) | Ask data engineering to load more weeks into dev before 2026-11-03, or to re-date the existing two weeks (D-M6). The BFF cannot invent listed picks |
| R-2 | No one on the BFF team has control-plane rights on `xo-sports-dev` | ML-1 goes to the account owner; the plan is unaffected otherwise |
| R-3 | A data reload changes document prices, so records no longer match (`record_mismatch`, legacy blocks) | The refresh rebuilds mismatched mock records (§4.2); run it after every reload |
| R-4 | Someone reads the mock container as real records | The container name says `edge` and `mock`; meta source is `mock` |
| R-7 | The mock container sits in data engineering's content database: a seeder bug could touch a content container, or their tooling could remove ours | The write guard refuses every content container and the seeder's write role covers only the mock container; data engineering confirms their tooling leaves unknown containers alone (D-M2) |
| R-5 | The mock profile reaches production | It is honoured only where the existing production guard allows the mock, and the setting is not in the tst or production settings |
| R-6 | Stale states if refresh is manual (D-M3 A) | The README says when to run it; option B removes the risk |

## 10. Decisions needed

| Id | Decision | Recommendation |
| --- | --- | --- |
| D-M1 | A separate database, or a container inside `app-read-dev` | **Decided 2026-10-20:** a container inside `app-read-dev`, no separate database (§4.0) |
| D-M2 | Who creates the container, and data engineering's agreement to a BFF-owned container in their database | Data engineering creates it and agrees; the BFF team owns the mock data in it |
| D-M3 | Refresh: manual, timer function, or scheduled workflow | Manual first, timer function once the app team tests on L2 daily |
| D-M4 | Keep L1 reachable per request (`edge_pick_source`) after dev switches to Cosmos | Yes: the app team keeps every state on demand |
| D-M5 | Leagues in L2 | NBA only to start; Format A leagues when product wants v4 cards for them |
| D-M6 | Extending the dev data past 2026-11-03 | Ask data engineering now; it affects L1 too |
| D-M7 | Deploy L1 to dev before L2 is built | Yes (§2, step 1) |

## 11. Out of scope

- The real KDD-001 container and Publish Engine writes (DE-1).
- Cancelled-pick injection (BE-11): seeded records for picks not in the documents stay hidden until it exists.
- `loadForGames` for My Picks results (MP-5 part f).
- tst and production: no mock records there, ever.

---

## 12. Implementation status (mobile-server, branch `feat/edge-picks-v7`)

Built and tested, uncommitted: ML-2 to ML-6 and the local part of ML-7. **Not done:** creating the container in dev (ML-1, D-M2), seeding it, and switching dev to `EDGE_PICK_SOURCE=cosmos`; ML-8 and ML-9.

| Plan item | Where |
| --- | --- |
| `cosmos` source, validation profile, 2 s limit | `src/lib/edge-picks/v7/cosmos-record-source.ts` |
| Record cache (shared Redis, 60 s, misses batched into one query, no lock) | `src/lib/edge-picks/v7/record-cache.ts` |
| Settings, `edge_pick_source`, meta source | `src/lib/edge-picks/v7/config.ts`, `src/functions/matches-top-predictions-v3.ts`, `src/lib/cosmos.ts` (`getEdgePickRecordsContainer`) |
| Refresh rules | `src/lib/edge-picks/v7/mock/merge.ts` |
| Seeder core, pins, guards | `src/lib/edge-picks/v7/mock/seed.ts`, `capture.ts`; CLI `script/edge-picks/seed-mock-records.ts`, `mock-pins.json` |
| Local container | `createEdgePickRecordsContainer` in `src/lib/cosmos.ts`, `script/edge-picks/create-records-container.ts` (emulator only) |
| Dev settings (inert while `EDGE_PICK_SOURCE=mock`) | `infra/envs/dev/app_settings.tf` |
| Tests | `matches-top-predictions-cosmos-source.test.ts` (V-L2-1, 2, 4, 5, 6, the source parameter), `cosmos-record-source.test.ts` (V-L2-3, 4, 5, 8), `merge-seed.test.ts` (V-L2-6, 7), `config.test.ts` |

Verified on the local emulator with the NFL seeds: dry run, apply, a second apply writing nothing, a refresh after kick-off moving statuses forward with etag-guarded replaces, and the guard refusing a content container.

**Differences from this plan**

| Plan | Built | Why |
| --- | --- | --- |
| Scenarios assigned over the picks open at `now` | A fixed `assignAt` (default: a day before the date) | Otherwise a refresh reshuffles scenarios as games start, and a live pick turns cancelled mid-day. `generateRecords` takes `assignAt`; L1 is unchanged |
| The seeder lists picks itself | It runs the real route in-process and reads the inputs of `buildBlocks` through a tool-only source override | One copy of the route's loading code, so the records match the route's picks exactly (V-L2-1 holds) |
| `--fixtures` mode | Not built | Local runs use the emulator with `db-migrate` and `db-seed`. Fixture mode can follow if wanted |
| One cache with lock and fallback | `getOrLoad`-style shared cache without lock or in-memory fallback | The lock and fallback are ML-8, as planned |
| Meta source `mock` for mock-checked records | Same | `live` appears only with full checks |

**Switching dev to the container** (after ML-1): run the seeder with `--apply`, set `EDGE_PICK_SOURCE=cosmos` in the dev settings (the other settings are already in `infra/envs/dev/app_settings.tf`), deploy, and smoke test.

**For review:** the environment guard treats a `tst` marker as non-production (`NON_PROD_MARKER` in `config.ts`), but `infra/README.md` calls TST production. A setting of `EDGE_PICK_SOURCE=mock` or `EDGE_PICK_RECORD_CHECKS=mock` on the TST app would therefore be honoured. Nothing sets them there now. Dropping `tst` from the markers closes it; the seeder's guard would then refuse TST too.
