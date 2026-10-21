# Publish Engine v4 analysis

## Architecture, design and implementation review — blank-canvas assessment and recommended target

**Date:** 20 October 2026
**Status:** Draft for technical review
**Subject:** The XO Sports Publish Engine (PE): the `app-data` Databricks publisher that turns Delta
silver/gold tables into Cosmos DB documents for the BFF and app.
**Why now:** the Edge Picks v4 redesign (`edgepicks-redesign/staging/option-b-plan.md`) needs the PE to
carry a new producer-record container, derived legacy documents and sub-5-minute observations. This is
the opportunity to ask what the PE should be, not only what it should add.

**Review basis.** Read-only review of the `app-data` repository at `tst-blue` `a1c16f4` (13 Oct 2026),
compared with `origin/dev` `56e4ca7` (19 Oct 2026) and `origin/feat/nba-2026` `54214ec` (17 Sep 2026);
the Edge Picks v4 contract corpus; live read-only Databricks and Azure Monitor evidence pulled on
20 Oct 2026; and four prior in-repo investigations (`nba-pe-publishing-investigation.md` 7 Oct,
`bluegreen_assessment.md` 16 Sep, `pe-exit-criteria*.md`, `pe-flow-doc-review.md`). Four workstream
analyses underpin this document (an independent adversarial verification pass checked the load-bearing
claims; its corrections are folded in, and the remaining gaps are in `.analysis/v4/verification.md`):

| Workstream | File | What it establishes |
| --- | --- | --- |
| Architecture, control plane, deployment | `app-data/.analysis/v4/arch-deploy.md` | 18 findings A-1…A-18; control-plane topology, cutover reality, CI/CD |
| Data-plane code, contracts, testability | `app-data/.analysis/v4/code-data.md` | 18 findings C-1…C-18; write semantics, three transform generations, metrics |
| Runtime evidence | `app-data/.analysis/v4/runtime.md` | Measured write volume/RU, failure catalogue F1–F14, anti-claims list |
| Edge Picks v4 requirements | `app-data/.analysis/v4/v4-requirements.md` | 41 requirements R-A…R-E, 24-row gap matrix, 13 hidden work items |

Paths in this document are relative to the `app-data` checkout unless they start with
`edgepicks-redesign/` or `staging/`. Repo citations use `file:line` at `tst-blue` `a1c16f4` unless a
branch is named. Where evidence is old, the as-of date is stated. The runtime section deliberately
separates **measured**, **prior** and **inferred** facts; Appendix A lists what could not be verified.

## Contents

- **0. Executive summary** — verdict, the ten findings, the recommendation, what it buys, decisions needed
- **1. The engine as built** — inventory, runtime shape, write path, three transform generations, contracts, deployment, blue/green, runtime snapshot
- **2. Assessment** — scorecard, strengths to keep, findings by dimension, fitness for purpose
- **3. What Edge Picks v4 requires** — requirement groups, the 24-gap matrix, hidden work, launch critical path
- **4. Blank-canvas options** — the five design axes, option packages A–E, scoring and recommendation
- **5. Recommended target architecture** — principles, reference design, components C1–C9, write semantics, v4 flows, requirement mapping, simplification, costs
- **6. Migration plan** — four phases, critical path, gates, risks, open questions, first ten days
- **7. Appendices** — method and limits, full finding register, option scoring, component responsibilities, glossary, references
- **8. Bottom line**

---

## 0. Executive summary

### 0.1 Verdict

**The Publish Engine works, but it is an ETL-shaped publisher that has outgrown its design.** It is a
stateless, document-oriented, trigger-fan-out pipeline: a table change wakes a router job, a notebook
turns a task list into per-container worker tasks, and a shared notebook streams Delta CDF through a
transform and writes whole documents to Cosmos one row at a time. For the world it was built for —
five leagues, one document per game per pick type, "latest engine output wins" — it has delivered for
months. It is now being asked to carry a different product: **Edge Picks v4 makes publication a
stateful, contract-bound, concurrency-sensitive, multi-family write problem with a five-minute
observation SLA.**

Assessed against that, the gap is architectural, not a missing feature:

1. **The write path has no correctness boundary.** Cosmos errors are counted and swallowed, a row
   without an `id` is skipped silently, patch mode structurally cannot work (Cosmos allows 10 patch
   operations per request; the transforms emit 18–27, and patch cannot null a field anyway), deletes are
   handled for 3 of 31 mappings, and nothing validates a document before it is written
   (`code-data.md` C-1…C-5, C-7). A green run is not evidence that publishing happened. The patch-mode
   failure is code-level certain; its production frequency is inferred and needs a job-log check.
2. **The engine re-publishes the world rather than the change.** There is no content diff and no stored
   state. Measured on 13–20 Oct 2026: `c-sch-tst-02` holds ≈3,560 documents and received **857,649
   upserts in seven days** (≈6,650/hour; the whole container ≈45 times a day) while its source table
   committed **three times in three days** (`runtime.md` §3.3). Cosmos RU is cheap at this scale
   (≈US$35–60/month for tst), but the mechanism poisons change detection, push cadence, reconciliation,
   and every "write only on change" rule the v4 contracts introduce.
3. **The control plane is hand-operated and latent.** The tst release path runs ~10 job definitions (five
   sport routers + five workers; mainline retired the workers on 19 Oct and runs five), a 60-second
   trigger debounce, a task-list step and queued whole-job runs. Latency is not measured today; the last measured dev study
   put 66% of MLB prediction publishes within 60 minutes of the source commit — and that is a coarse hourly-bucket figure, not an SLO (`runtime.md` §4).
   The v4 design budgets five minutes, end to end.
4. **Three transform generations coexist and are diverging across branches.** The branch CI deploys to
   tst has a 2,937-line monolith plus ≈1,240 lines of newer NBA modules and **zero tests**; the only
   tested implementation (`canonical_transformations.py`, 61 tests) lives on an unmerged branch that
   predates the modules (`code-data.md` C-6, C-17). The tested code is not the code that branch deploys;
   the workspace's currently running revision is unverified because PE jobs are not visible to the
   review identity.
5. **Contracts are prose.** 54 Markdown contract documents, schema versions from `1.00` to `2.0.0`,
   several superseded documents still present, no machine-readable schema anywhere (`code-data.md`
   C-7, C-8). v4's "validate before write" has nothing to validate against.
6. **The documented blue/green cutover was never built.** The live pointer is split across PE job
   parameters, Container App environment variables (verified) and BFF Function App settings (five
   containers, per the 16 Sep prior review; not re-verified); `COSMOS_LIVE_CONFIG` is
   read by nothing but the backup notebook, its dev value names the container set the writer does not
   write, and tst double-published into two container sets from the 13 Oct restore catch-up until
   18 Oct 21:53Z (≈5.5–6.7 days) during the last cutover
   (`arch-deploy.md` A-1…A-6; `runtime.md` F10). There is no pre-cutover gate and no atomic rollback.
7. **The v4 gap is 9 blockers and 11 highs.** No record store, no etag-guarded whole-record write, no
   pre-write validation, no observation→record path, no settlement→result path, no content diff, no
   dependency-driven rebuilds, no shadow/reconciliation (`v4-requirements.md` §2). The largest hidden
   work item is the settlement path, which no v4 document budgets.

**The good news:** the ingredients are largely present and worth keeping — change-data-feed triggering,
per-container isolation, deterministic document ids, versioned container specs, an NBA modular refactor
that is genuinely cleaner, and a tested canonical registry that points at the right builder shape.
What is missing is a **publication substrate**: a contract layer, a durable publish log, a single
writer with real guarantees, and a control plane simple enough to operate.

### 0.2 Recommendation in one paragraph

**Rebuild the PE around a contract-first, record-first design: a declarative stream catalogue and pure
builders produce document "intents" into a durable Delta publish log; one applier per environment is
the only writer to Cosmos, validating against JSON Schema and applying whole-document writes with
etag/version guards, content-diff skipping, retries, audit and a dead-letter queue. Edge Picks v4 then
lays its record-first flows over the same substrate: a fast observation lane and a slow
projection/settlement lane, both writing through the one applier, with a reconciliation job that makes
"records and derived documents agree" a property rather than a hope.** The control plane collapses from
~10 job definitions on the tst release path (five on mainline after 19 Oct) to one job driven by a checked-in catalogue; three transform generations
become one; 54 prose contracts become a schema registry; blue/green slot duplication is replaced by a
single cutover pointer and an immutable release artefact.

This is best delivered in four phases (section 6), starting with a two-week "stop silent failures"
phase that is independently valuable: fail-loud writes, delete handling, content-hash skipping, schema
validation and CI gates remove the highest-severity defects before any v4 work rides on them.

### 0.3 Ten findings that matter

| # | Finding | Severity | Evidence |
| --- | --- | --- | --- |
| 1 | Write failures are swallowed; a run can be green with documents missing | Critical | `code-data.md` C-1; `pipeline.ipynb` c4:279–319 |
| 2 | Patch mode cannot work (18–27 ops vs Cosmos 10-op limit; cannot null; errors swallowed); production impact inferred, pending a job-log check | Critical | `code-data.md` C-2; Cosmos PDUB FAQ |
| 3 | No schema validation before write; malformed documents are the BFF's problem to discover | High | `code-data.md` C-7 |
| 4 | No content diff/state: whole-container re-emit per trigger (857k upserts/7d into a 3.5k-doc container; ~45 rewrites/day) | High | `runtime.md` §3.3 |
| 5 | Deletes dropped for 28 of 31 mappings (3 can delete); retired rows leave zombie documents | High | `code-data.md` C-3 |
| 6 | Control plane: ~10 jobs on the tst release path, 60 s debounce, task-list step, queued runs; latency unmeasured | High | `arch-deploy.md` A-7; `runtime.md` §4 |
| 7 | Multi-input documents never re-triggered (one source table per task) — blocks v4 projections | High | `code-data.md` C-12; `v4-requirements.md` G-07 |
| 8 | Tested code is not the code CI deploys; the deploy branches have zero tests and CI runs none | High | `code-data.md` C-6, C-17; `arch-deploy.md` A-16 |
| 9 | Cutover pointer split across 3 systems; inert/inverted live rule; 5.5-day duplicate publishing | Critical (change safety) | `arch-deploy.md` A-1, A-2; `runtime.md` F10 |
| 10 | State/replay is "pin in code + checkpoint on disk + human clears it"; wrong and expired pins caused repeated stream outages | High | `runtime.md` F1–F6; `nba-pe-publishing-investigation.md` |

Full register: Appendix B. The v4-specific gap matrix: section 3.2.

### 0.4 What this buys, and what it costs

| Outcome | Today | Target |
| --- | --- | --- |
| Silent write failures | Possible by design | Not possible: fail-loud, DLQ, audit |
| Changed-document writes | ~45 full-container rewrites/day in one tst container | Write only when content hash changes |
| Control plane | ~10 job definitions on tst (5 on mainline), router→worker fan-out | 1 job/env driven by one catalogue |
| Transform code | 3 generations across 3 branches, 2,937-line monolith | 1 builder library, one contract registry |
| Contracts | 54 prose docs, no schema | Versioned JSON Schemas + generated types/docs |
| Deploy/rollback | Delete-and-reupload, auto-unpause, 4-system rollback | Immutable artefact, deploy paused, one pointer |
| v4 readiness | 9 blockers / 11 highs | Record-first flows expressible on the substrate |

**Effort (order of magnitude; ranges are person-weeks unless an elapsed time is stated):** Phase 0
stop-the-bleeding 3–4 (~2–3 weeks elapsed); Phase 1 consolidation + contracts 5–8; Phase 2 record-first
v4 substrate 16–22 (~10–16 weeks elapsed with two engineers), plus 3–5 data-engineering weeks for the
settlement path; Phase 3 simplification/decommission 4–8. Edge Pick v4's
launch-critical path uses Phase 0 + the record writer and Stage A projection from Phase 2. These are
planning ranges, not commitments; they exclude product decisions and BFF/app work.

### 0.5 Why not just add v4 to the current engine?

A "record writer beside the existing pipeline" would be the cheapest short-term option, and it is
rejected as the primary route because it fails the properties that make v4 safe:

- the observation SLA cannot survive a 60-second debounce plus queued whole-job runs;
- one-writer, validation and write-on-change are not add-ons to `mapInPandas` + unconditional
  `upsert_item` — they are a different write primitive with a read path (etag, content hash);
- the derived legacy documents need dependency-driven rebuilds and reconciliation, which the
  one-table→one-task mapping cannot express;
- the settlement path needs a producer and a status lifecycle that no current transform has;
- the current cutover model cannot safely ship a new writer while both families of documents are live.

It remains a valid **staging step** (Phase 0–1), and this document sequences it that way.

### 0.6 Decisions needed

| # | Decision | Recommendation | Owner |
| --- | --- | --- | --- |
| D1 | Adopt the contract-first, record-first target and the four-phase sequence | Yes | PE/DE leadership, architecture |
| D2 | One codebase/branch as the base; stop branch-per-environment | Adopt the canonical registry pattern + current NBA modules; retire the fork | PE lead |
| D3 | Settlement → record → `c-outcome` path and its owner (`settled_at`, push/void semantics) | Data engineering + bet engine own the table; PE owns the write and projection | BE, DE |
| D4 | One writer per document family, enforced by construction; settlement write-back routed through PE | Yes; retire the "second writer" designs | DE, BE |
| D5 | One cutover pointer consumed by writer and generated app config; delete or make authoritative `COSMOS_LIVE_CONFIG` | One manifest, generated outputs, CI parity test | Platform, DE, app |
| D6 | Applier runtime: Databricks job first, external (ACA) later if SLA/ops demand | Databricks for Phases 1–2; revisit at the Phase 2 latency gate | PE, platform |
| D7 | Validation-failure semantics for a live slate | Validate whole batch in Spark; quarantine invalid records with an alert; fail the run when a producer contract is broken | PE, product |
| D8 | Contract artefact ownership, versioning rule and sign-off | One repo (PE), JSON Schema as source, generated consumers | App/BE/DE |

Open questions that are not decisions yet are in section 6.5 and `v4-requirements.md` §5.

---

## 1. The engine as built

### 1.1 Inventory

| Layer | What exists | Where |
| --- | --- | --- |
| Deployment unit | Databricks Asset Bundle `publisher-router-worker`; 2 targets on `tst-blue` (`dev-green`, `tst-blue`), 1 on mainline (`dev-green`) | `databricks/databricks.yml` |
| Job definitions | 16 YAML files: 5 legacy routers (deprecated), 5 per-sport routers, 5 per-sport workers, 1 generic worker. On `tst-blue` routers call workers; mainline (19 Oct) folded the work into the router's own `for_each_task` and emptied the worker files | `databricks/resources/jobs/*.yml` |
| Trigger | `table_update` on the sport's source tables, `ANY_UPDATED`, `wait_after_last_change_seconds: 60` | e.g. `publish_engine_router_nba.yml:20–40` |
| Routing | `build_transformation_map.ipynb` turns `updated_tables` into per-container task lists (25 source tables, 31 mappings, 14 transforms) | `databricks/publisher/build_transformation_map.ipynb` |
| Execution | `generic_cdf_to_cosmos_pipeline.ipynb` — widgets → CDF stream → string dispatch → transform → `mapInPandas` writer | `databricks/publisher/generic_cdf_to_cosmos_pipeline.ipynb` |
| Transforms | Generation 1: `transformations_library.py` (2,937 LOC, 8 transforms, largest 1,047 LOC). Generation 2: `nba/*` modules (1,239 LOC, 3 modules + helpers). Generation 3: `canonical_transformations.py` (1,407 LOC, 7 builders + `dispatch`) only on `feat/nba-2026` | `databricks/publisher/…`; `origin/feat/nba-2026` |
| Sink | Azure Cosmos DB (serverless), one container per document family; documents keyed `<league>\|<doc_type>\|<key>`; partition keys per container | `docs/containers/`, `common/helpers.py:49–61` |
| Compute | Databricks serverless (`performance_target: PERFORMANCE_OPTIMIZED`); no cluster spec in the bundle | `resources/jobs/*.yml` |
| Credentials | Databricks secret scope `publish_engine` holds the Cosmos account endpoint and **master key** | `pipeline.ipynb` c1 |
| CI/CD | One GitHub Actions workflow per branch; OIDC → AAD token; delete + re-import the workspace folder; `bundle validate`; `bundle deploy` | `.github/workflows/deploy-bundle.yml` |
| Tests | None on `tst-blue` or `origin/dev`. `origin/feat/nba-2026`: 61 pytest/Spark tests (3,113 LOC) | `databricks/tests/` on feat |
| Contract docs | 54 Markdown files under `docs/pe/container_structure/` and `docs/containers/`; no machine-readable schema | repo tree |

### 1.2 Runtime shape

```
 Delta silver/gold tables (25 source tables across 5 leagues)
        │  any write
        ▼
 [router job per sport]  ◄── table_update trigger, ANY_UPDATED, 60 s debounce
        │  build_transformation_map (updated_tables → per-container task lists)
        ├──────────────┬──────────────┬──────────────┬──────────────┐
        ▼              ▼              ▼              ▼              ▼
   PS container   Outcomes       Schedule       Injuries         WLTP        (parallel tasks;
   task_list      task_list      task_list      task_list        task_list    one job run per
        │              │              │              │              │         container on
        └──────────────┴──────────────┴──────┬───────┴──────────────┘         tst-blue; inline
                                             ▼                               for_each on mainline)
                              generic_cdf_to_cosmos_pipeline (per task)
                              Delta CDF read (readChangeFeed=true)
                                     │
                              transform (string dispatch; pure select or table reads)
                                     │
                              mapInPandas → azure-cosmos Python SDK
                              upsert_item / patch_item / delete_item  (one call per document)
                                     │
                                     ▼
                              Cosmos DB containers (serverless)
                                     │
                                     ▼
                              BFF (mobile-server) → app
```

Two facts about this diagram matter more than the boxes:

- **The trigger is per-table-change, but the unit of write is a whole document set.** Each container
  task re-emits its documents from the batch; with a whole-document upsert and no content compare, a
  source commit can rewrite an entire container. This is what the measured 857,649 upserts/7d into a
  3,560-document container reflects (`runtime.md` §3.3).
- **The pipeline is stateless between runs except for the checkpoint.** There is no "current state of
  document X" anywhere; the only durable state is the Delta CDF offset. Everything the v4 design calls
  state (first publish, frozen fields, previous observation, slot incumbent, reconciliation) has no
  home in this picture.

### 1.3 Write path — the details that matter

The writer is a closure inside the notebook (`pipeline.ipynb` c4:25–323). Per micro-batch it:

1. filters to `insert`/`update_postimage` (deletes are dropped except for `transform_pstp` and an NBA
   schedule partition-move special case);
2. dispatches to one of 14 transforms by **string name** in an `if/elif` chain;
3. drops `_change_type`/`_commit_version`/`_commit_timestamp` and hands the remaining columns to
   `mapInPandas`;
4. in each partition, converts pandas rows to dicts and calls the Cosmos SDK **one document at a time**:
   `upsert_item` for whole documents, `patch_item` when the transform set `isPatch`, `delete_item` for
   markers;
5. counts `upserts`/`deletes`/`errors` and returns them; the driver sums and **logs** them. It never
   raises on a Cosmos error; a missing `id` is `continue`d without being counted as an error at all.

Consequences:

- **A green run is not a correctness signal.** Throttles, 400s from patches, schema mismatches and
  missing ids are indistinguishable from success at the job level.
- **Patch mode is broken twice over.** The code emits one `set` operation per non-null field and cannot
  set null (Cosmos patch semantics), and it exceeds Cosmos's limit of 10 patch operations per request
  ([Azure Cosmos DB PDUB FAQ](https://learn.microsoft.com/azure/cosmos-db/partial-document-update-faq)).
  The MLB/EPL transforms that use it emit 18–27 candidate operations; the 400 is counted as an error and swallowed. The
  documented "predictions arrive, picks patch in later" lifecycle is therefore unlikely to be applied at
  all (`code-data.md` C-2, marked as inferred pending runtime log confirmation).
- **Deletes are effectively unsupported.** Retired games, removed injuries and deleted picks leave
  documents in Cosmos forever; no reconciliation job exists to find them.
- **Ordering/idempotency inside a batch is undefined.** A mixed update/delete batch is unioned with no
  precedence; there is no per-document version guard, so replay can apply an older document over a newer
  one.
- **There is no read path.** No component reads a document before writing it, so etag, content diff and
  "latest observation wins" cannot be implemented without a new primitive.

### 1.4 Transform code: three generations, three branches

| Generation | Size | Structure | Where | Tests |
| --- | --- | --- | --- | --- |
| 1 — monolith | 2,937 LOC, 29 defs | 8 top-level transforms; largest function 1,047 LOC (`build_player_prediction_documents`); 18 `league ==` branches; 7 hand-copied publish structs; 239 LOC dead | `tst-blue`, `origin/dev` | none |
| 2 — NBA modules | ≈1,240 LOC, 24 defs | Pure `select` builders, shared helpers, per-container version constants, `keep_latest_run`; good shape but only 7 of 31 mappings | `tst-blue`, `origin/dev` | none |
| 3 — canonical registry | 1,407 LOC, 25 defs | Uniform handler signature, table-driven `dispatch()`, output guards, `normalize_transformation_name`; 3,113 LOC of tests | `origin/feat/nba-2026` only | 61 tests |

The branches are not converging: `feat/nba-2026` predates the modular refactor (the branch has no
`nba/*` or `common/*` directory) and already differs in published values (NFL stat token `RuYDs` vs
`RuYds`, EPL BTTS fallback) (`code-data.md` C-6). The branch CI deploys to tst is untested; the branch
that is tested is not the one CI deploys.

### 1.5 Contracts and documents

Each document family has a prose "container structure" spec in `docs/`: id formula, partition key,
field tables, `schema_version` and `taxonomy_version`, examples. The specs are good contract material —
better than most internal documentation — but they are not executable, and they have drifted:

- 54 documents for 5 leagues, with schema versions `1.00`, `1.10`, `1.20`, `1.21`, `1.30`, `1.31`,
  `1.40`, `2.0.0` and three inconsistent version formats.
- EPL `game_prediction` alone has four contract documents (v1.21/1.30/1.31/1.40) while the code writes
  `1.21`; no document says which is authoritative (`code-data.md` C-8).
- The NBA schedule spec describes a join the code does not do; the map notebook's Markdown lists
  mappings the code does not have; superseded Format A docs for NBA are still present (some marked
  superseded only on the feat branch).
- There is **no JSON Schema, pydantic model or column assertion anywhere** in the repository
  (`grep pydantic|jsonschema` = 0 hits under `databricks/`). Validation is impossible today.

### 1.6 Deployment and environments

The model is "branch = environment": push to `dev` deploys `dev-green`; push to `tst-blue` deploys the
`tst-blue` target. The workflow deletes the workspace folder and re-imports every file
(`deploy-bundle.yml:171–194`), then runs `bundle validate` and `bundle deploy`. Jobs reference the
absolute workspace path `/Workspace/Deployments/publish_engine/{env}_{slot}/…`, so the code is an
artefact separate from the job definitions that use it.

Properties of this model, verified:

- **Not atomic.** A deploy while a job is starting can run against a half-synced folder; rollback is
  "revert git, redeploy, re-point container variables, decide what to do about checkpoints" — four
  manual systems.
- **Auto-live.** `slot_pause: UNPAUSED` is the committed value in both live targets, so deploying
  resumes publishing. Pausing one league means editing variables and redeploying.
- **Forked.** `tst-blue` differs from mainline by 23 files (+1,385/−1,311) and includes a control-plane
  refactor (mainline: inline `for_each_task`, workers retired; tst: five separate child job runs per
  router). The branch CI deploys to tst is therefore a six-day-old fork of mainline; whether the tst
  workspace currently runs it is unverified (PE job state is not visible to the review identity), but the
  release path is from the fork.
- **No promotion or parity.** There is no PR workflow, no test gate, no migration mechanism and no
  dev/tst parity check. `bundle validate` currently reports 40 warnings from five half-commented
  deprecated router files (`arch-deploy.md` A-5, A-14, A-16, A-17).

### 1.7 Blue/green: the documented design versus the built one

The repository and Confluence describe a blue/green deployment: back up the live container set, restore
into the idle set, start the idle PE from the backup timestamp, validate, then flip the live pointer and
pause the old slot. The built mechanism is a container-suffix slot switch with none of the safety
machinery:

- **The pointer is not one object.** PE job parameters (baked at `bundle deploy`), BFF Function App
  settings for the remaining five containers (per the 16 Sep prior review; not re-verified), and
  `svc-partner-api` Container App env vars for two containers (verified in the switch workflow) are all
  updated separately. `COSMOS_LIVE_CONFIG`, the documented source of truth, is read only by the backup
  notebook; nothing in the app tier reads it.
- **The live rule is stale/inverted.** On 20 Oct the active dev rule named `c-*-dev-02` while the only
  dev target writes `c-*-dev-01`; tst held four rows for the same key (`arch-deploy.md` A-2).
- **The last cutover double-published.** tst wrote both the old and new container sets at near-identical
  rates from the 12/13 Oct restore catch-up until the old set's last upsert at 21:53Z on 18 Oct
  (≈5.5–6.7 days) (`runtime.md` §3.1, F10).
- **There is no gate or atomic rollback.** The only check is a manual runbook; the backup is not a
  consistent snapshot; and start-version pins/checkpoints defeat "start from T" for several streams
  (`nba-pe-publishing-investigation.md` §2; `bluegreen_assessment.md` §4).

### 1.8 Runtime evidence snapshot (20 Oct 2026 unless stated)

| Fact | Value | Source |
| --- | --- | --- |
| Written container sets today | dev `c-*-dev-01`; tst `c-sch/outcomes/ps/injuries/injuries-team-tst-02`, `c-wltp-tst-01` | Azure Monitor, measured |
| tst write volume, 7 days | 857,649 upserts into `c-sch-tst-02`; 429,303 into `c-outcomes-tst-02`; ≈9k upserts/h averaged over the window (≈10–13k/h in steady state) | measured |
| Container size vs write volume | `c-sch-tst-02` ≈3,560 docs, ≈6,650 upserts/h (≈45 full rewrites/day); source `dim_all_games` 3 commits in 3 days | measured/inferred |
| tst RU, 7 days | ≈33.6M RU (both sets); ≈US$35–60/month estimate at serverless rates | measured RU, estimated price |
| Dev RU, 7 days | ≈2.3M RU | measured |
| Trigger-to-Cosmos latency | not measured today. Config floor: 60 s debounce; Sept dev study: 184/645 MLB pofs→c-wltp within 15 min, 427/645 (66%) within 60 min | prior |
| PE jobs visible to the read-only SP | none in either workspace (permission boundary, not absence); no run history, cluster or compute cost visible | measured |
| Failure modes seen in production | wrong CDF pin (12 vs CDF-at-14; stream failed every trigger until fixed); expired pin (168 h retention); missing table breaks trigger; SDP full refresh/CTAS invalidates streams; manual checkpoint resets and pause/unpause cycles around rebuilds; 5.5-day duplicate publishing; zero-write green runs | prior (7 Oct) + measured (cutover) |

The anti-claims list in `runtime.md` §11 is binding for this document: no current latency SLO, no
current failure rate, no compute cost, and no claim that tst is still double-publishing.

---

## 2. Assessment

### 2.1 Scorecard

| Dimension | Rating | One-line judgement |
| --- | --- | --- |
| Change detection (CDF/trigger) | **Good idea, weak execution** | CDF is the right primitive; the trigger→task-list→fan-out pipeline turns it into full-container re-emits |
| Write semantics | **Poor** | Errors swallowed, patch broken, no validation, no etag, deletes dropped |
| State and idempotency | **Poor** | No stored document state, no content diff, undefined batch ordering, replay can regress |
| Transform architecture | **Mixed** | NBA modules and canonical registry are materially better; the monolith is still load-bearing |
| Contracts | **Weak** | 54 prose specs, no machine-readable schema, version sprawl and drift |
| Control plane | **Poor** | ~10 jobs on tst (5 on mainline), 60 s debounce, queued runs, no concurrency policy, latency unmeasured |
| Deployment/cutover | **Poor** | Non-atomic deploy, auto-unpause, split pointer, no gate, duplicate publishing |
| Observability | **Poor** | Job failure webhook only; green runs can mean zero writes; non-owners cannot see jobs |
| Testability/CI | **Poor** | Deployed branches have no tests; CI deploys without tests |
| Cost | **Acceptable today** | Cosmos RU is cheap; compute is unmeasured and the main suspected driver |
| Security | **Mixed** | OIDC and SP hygiene are good; Cosmos master key and no write audit are weak |
| Fitness for Edge Picks v4 | **Not ready** | 9 blockers and 11 highs, including the whole record-first layer and settlement path |

### 2.2 Strengths to keep

These are not consolation prizes; several are hard-won and should survive the rebuild.

| # | Strength | Evidence |
| --- | --- | --- |
| S1 | **Change-data-feed publication is the right primitive** for this estate: Delta CDF, idempotent whole-document upserts by deterministic id, no bespoke CDC infrastructure | `pipeline.ipynb` c5; `common/helpers.py:49–61` |
| S2 | **Per-container isolation and sport tagging** limits blast radius and matches the Cosmos read model | `resources/jobs/*.yml` tags/tasks |
| S3 | **Definitions are code** (DAB), deployed by CI with Azure OIDC federation, a dedicated SP and `run_as` — no clicked-in jobs, no long-lived cloud secrets | `arch-deploy.md` W-1…W-4 |
| S4 | **Deterministic ids and a publish envelope** (`<league>\|<doc_type>\|<key>`, `publish.engine_version`, `published_at_utc`) give consumers a stable identity and an audit anchor | `common/helpers.py:49–77` |
| S5 | **Versioned container contracts with `schema_version` vs `taxonomy_version`** are a sound idea and the best starting material for a schema registry | `docs/containers/nba_containers/00 - NBA Containers Overview.md` |
| S6 | **Careful CDF start-point discipline**: refuses to start from "latest", records the applied start version in a marker, detects stale checkpoints instead of silently skipping | `pipeline.ipynb` c5 |
| S7 | **The NBA modular refactor is genuinely cleaner** (pure `select` builders, shared helpers, 1,239 LOC vs a single 1,047-LOC monolith function) and is the right style for the target | `nba/*.py`; `code-data.md` W-4 |
| S8 | **The canonical registry on `feat/nba-2026`** has the right builder shape and 61 tests — the only real regression suite in the estate | `origin/feat/nba-2026:databricks/publisher/canonical_transformations.py`, `tests/` |
| S9 | **Serverless compute and per-container serialisation** avoid idle clusters and reduce intra-container write races | `resources/jobs/publish_engine_worker_nba.yml:21–46` |
| S10 | **Cosmos is not the cost problem**: measured ≈33.6M RU/7d for tst and ≈2.3M for dev; serverless pricing makes this tens of dollars a month | `runtime.md` §8 |

### 2.3 Findings by dimension

The register below consolidates the four workstreams into one severity scale: **Critical** = data
loss/incorrect data reachable in normal operation, or a change-safety property that can corrupt live
serving; **High** = silent wrongness or a structural blocker for v4; **Medium** = maintainability,
recurring operational risk; **Low** = hygiene. Appendix B carries the full table with source IDs
(A-, C-, F-, G-, R-) and evidence.

#### 2.3.1 Publication correctness (the write path)

| ID | Sev | Finding | Evidence | What good looks like |
| --- | --- | --- | --- | --- |
| PE-01 | **Critical** | Cosmos write errors are counted and logged, never raised; missing-`id` rows are skipped silently. A run can be green with documents missing. | `code-data.md` C-1; `pipeline.ipynb` c4:279–319 | Fail the batch on non-retryable errors; DLQ for retryable; per-doc audit row |
| PE-02 | **Critical** | Patch mode cannot work as written: one op per non-null field (18–27 candidate operations) vs Cosmos's 10-op limit, cannot set null, and the resulting 400 is swallowed. The documented partial-update lifecycle is probably not applied in production (inferred; needs a job-log check). | `code-data.md` C-2; Cosmos PDUB FAQ | Delete patch mode; whole-document upsert with etag/version guard |
| PE-03 | **High** | No validation of any kind between Spark `Row` and `upsert_item`; no JSON Schema/pydantic exists in the repo. Malformed documents are discovered by the BFF. | `code-data.md` C-7 | Schema registry; validate before write; fail or quarantine with alert |
| PE-04 | **High** | Deletes are dropped for 28 of 31 mappings; only both `transform_pstp` mappings and the NBA schedule partition move emit tombstones. Retired rows leave zombie documents; there is no reconciliation. | `code-data.md` C-3 | Generic delete policy per doc type + periodic key reconciliation |
| PE-05 | **High** | No optimistic concurrency: `upsert_item` without etag, last-write-wins. "Single writer per document" is a design statement, not an enforced invariant — patch mode, the designed settlement write-back and live-odds' deferred writer all contradict it. | `code-data.md` C-11; `v4-requirements.md` G-02/G-22 | One writer per document family, enforced; etag `If-Match` for read-modify-write |
| PE-06 | **Medium** | Batch ordering is undefined: mixed update/delete rows are unioned without precedence, and replay can apply an older document over a newer one. No source version is written into the document. | `code-data.md` C-10 | Deterministic precedence (delete > newest commit version); version in document/audit |

#### 2.3.2 State, write amplification and replay

| ID | Sev | Finding | Evidence | What good looks like |
| --- | --- | --- | --- | --- |
| PE-07 | **High** | No content diff and no stored state. Every CDF event re-upserts the whole document with a fresh `published_at_utc`. Measured: 857,649 upserts/7d into a 3,560-doc container while its source committed 3 times in 3 days (≈45 full rewrites/day). | `runtime.md` §3.3; `code-data.md` C-4 | Canonical content hash excluding volatile fields; skip unchanged; audit writes |
| PE-08 | **High** | The engine is a stateless document builder; v4 needs a stateful per-pick store (first publish, frozen fields, previous observation, status history, slot incumbent). There is nowhere to put that state. | `v4-requirements.md` §3.1; `code-data.md` C-5 | Record-first store; durable publish log; document state table |
| PE-09 | **Medium** | Transforms are impure: they read silver/gold tables inside `foreachBatch`, with `_safe_table` swallowing failures into null names. A batch is a function of current table state, not its input events; replay is not deterministic; this contradicts the "PE is join-free" docstring. | `code-data.md` C-5; `nba/constants.py:5–7` | Pure builders over declared inputs; injected dimension snapshots; fail hard on missing lookups |
| PE-10 | **High** | Start state is "pin in code + checkpoint on disk + human clears it". Wrong pins (12 vs CDF-at-14) failed every trigger until a code change; a pin older than 168 h is unreadable; checkpoints have automatic wipe/replay paths; `p_start_timestamp` loses to pins/checkpoints. | `runtime.md` F1–F6; `bluegreen_assessment.md` §4; `code-data.md` C-13 | Resolve start state at runtime; record watermarks in a control table; explicit, audited replay |
| PE-11 | **Medium** | Environment-specific configuration lives in code: literal `dev_*`/`tst_*` table names, absolute Delta versions and incident comments in the shared notebook; `checkpoint_version` bumps are manual; `failOnDataLoss=false` can skip silently. | `code-data.md` C-9, C-13 | Stream catalogue with per-env overlays; start policy as data; fail on data loss by default |

#### 2.3.3 Control plane and latency

| ID | Sev | Finding | Evidence | What good looks like |
| --- | --- | --- | --- | --- |
| PE-12 | **High** | ~10 live job definitions on the tst release path (five sport routers + five workers; five on mainline after 19 Oct), each trigger fans out to child job runs (up to 5 per container task set), a `Build_Task_List` step, a 60 s debounce and queued whole-job runs. No explicit `max_concurrent_runs`; no trigger-fire metrics. Mainline's 19 Oct "redesign pe jobs for cost savings" folded workers into router `for_each_task` — direct evidence that job compute/start-up is the pain. | `arch-deploy.md` A-7; `runtime.md` §2.3; `origin/dev` `57825b9` | One job per environment (or per sport where isolation is justified) driven by a stream catalogue; explicit lane/concurrency policy |
| PE-13 | **High** | The trigger model is "one source table → tasks", not a dependency graph. A document with two inputs is never rebuilt when only the other input changes: predictions vs picks (`game_prediction`), results vs picks (`c-outcome`), injuries/team names embedded in schedule. The records and settlement tables are not in any trigger. | `code-data.md` C-12; `v4-requirements.md` G-07 | Declared dependencies per document family; rebuild affected documents on any input change |
| PE-14 | **Medium** | Latency is not measured; the only figure is a Sept dev study (184/645 MLB pofs→c-wltp publishes within 15 min; 427/645, or 66%, within 60 min). The v4 requirement is 5 minutes end to end, including the 60 s debounce. KDD-001 itself records 1–3 min measured with "little margin". | `runtime.md` §4; `edgepicks-redesign/staging/kdds.md:44` | Per-stream freshness metric with an alert; two-speed lanes; SLO in the contract |
| PE-15 | **Medium** | Pause/unpause is a deploy-time config value and every deploy auto-resumes. Trigger table lists are hand-edited per branch (tst comments out `ps_top_picks_agg`; mainline enables it, with "do not merge back" notes). A missing table breaks the trigger. | `arch-deploy.md` A-11, A-12 | Deploy paused by default; pause/resume as an audited runtime action; config validated in CI |

#### 2.3.4 Transform layer and codebase

| ID | Sev | Finding | Evidence | What good looks like |
| --- | --- | --- | --- | --- |
| PE-16 | **High** | Three transform generations coexist and are diverging, not migrating. The branch CI deploys to tst has no tests; the tested branch is not the one CI deploys and predates the newer modules. Published values already differ between branches. | `code-data.md` C-6, C-17 | One builder library; one branch; tests on the deployed path |
| PE-17 | **Medium** | The monolith is 2,937 LOC with a 1,047-LOC function (36% of the file), 18 league branches, 7 duplicate publish structs, 3 duplicated helpers, 239 LOC dead code, and an id-format inconsistency (`transform_ps_top_picks_nba_1_00` sets `id = game_sk`). | `code-data.md` C-6, C-16 | Delete after migration; consolidate helpers; one id formula |
| PE-18 | **Medium** | The application is a notebook: ≈726 lines in six cells, a nested 298-line writer, string dispatch, no package boundary, no type hints, no lint, file-by-file sync. Review of the highest-risk code happens in notebook JSON diffs. | `code-data.md` C-14 | `publish_engine/` package; notebook is a thin launcher; lint/types/tests in CI |
| PE-19 | **Medium** | Dead and half-wired code: `transform_game_top_picks` (239 LOC) has no map entry and would raise `Unknown transformation_name`; `pof_source_rule` is unused; `_resolve_tables` ignores its argument; the five deprecated router files emit 40 bundle warnings. | `code-data.md` C-16; `arch-deploy.md` A-14 | Delete dead code and files; `bundle validate --strict` in CI |

#### 2.3.5 Contracts and schemas

| ID | Sev | Finding | Evidence | What good looks like |
| --- | --- | --- | --- | --- |
| PE-20 | **High** | No machine-readable schema; 54 prose documents; schema versions in three formats across `1.00`–`2.0.0`; four EPL `game_prediction` contracts with no authority; several superseded documents still present; docs drift from code. | `code-data.md` C-7, C-8; `v4-requirements.md` H5 | One JSON Schema per `doc_type` version, in repo, as the source of truth; generated types/docs; CI drift check |
| PE-21 | **Medium** | No compatibility rule, no per-document owner, no consumer register. The v4 contract corpus itself is still in flux (status vocabulary, reason codes, engine persistence). | `v4-requirements.md` H5, G-21; `staging/conf-schema-contracts.md` open decisions | Semantic versioning with explicit breaking rules; owner per contract; reader/writer register |
| PE-22 | **Medium** | Validation-like guards exist only on the unmerged feat branch and are Spark-column assertions, not schema validation; prose invariants (19 of them) are not encoded. | `v4-requirements.md` G-13; `edgepicks-redesign/staging/feedback_g4.md:57–91` | Encode cross-field invariants in schema/code tests; published-document conformance tests |

#### 2.3.6 Testing and CI

| ID | Sev | Finding | Evidence | What good looks like |
| --- | --- | --- | --- | --- |
| PE-23 | **High** | Zero tests on the branches CI deploys; CI has no PR workflow, no lint, no schema check, no notebook smoke test. `bundle validate` runs only after code has already been synced, on the deploy branch. | `arch-deploy.md` A-16; `code-data.md` C-15 | PR gate: unit + contract + mapping parity + bundle validate; deploy only from green |
| PE-24 | **Medium** | The only tests (61 on feat) are Spark `local[1]` integration tests with hand-built schemas, no golden JSON fixtures, no Cosmos writer double, and test seams (`_test_table_map`) leak into production signatures. | `code-data.md` C-17 | Pure builder tests + golden documents + contract validation + in-memory writer |
| PE-25 | **Medium** | No published-document conformance test exists; the PE exit criteria that require byte-shape comparison, idempotent re-run and regression tests are not covered by the deployed pipeline. | `pe-exit-criteria.md` #27–32 | Fixture → DataFrame → document → schema; one golden document per doc_type/version |

#### 2.3.7 Deployment, cutover and rollback

| ID | Sev | Finding | Evidence | What good looks like |
| --- | --- | --- | --- | --- |
| PE-26 | **Critical** (change safety) | The cutover pointer is split across PE job parameters (deploy-time), BFF Function App settings (five containers; prior review, not re-verified) and Container App env vars (two containers); `COSMOS_LIVE_CONFIG` is read by nothing but the backup notebook and is stale/inverted in dev; the last tst cutover double-published for ≈5.5 days; there is no pre-cutover gate and no atomic rollback. | `arch-deploy.md` A-1, A-2, A-6; `runtime.md` F8, F10 | One manifest consumed by writer and generated app config; pre-cutover gate (counts, freshness, sampled validation, shadow compare); rollback = revert one value |
| PE-27 | **High** | Deploy is delete-and-reupload then `bundle validate`/`deploy`; jobs use absolute workspace paths; there is no immutable artefact, no workspace-host binding, and no promotion model. `tst-blue` is a six-day-old fork of mainline including a control-plane refactor. | `arch-deploy.md` A-3, A-5, A-15, A-17 | Immutable release artefact per commit; promote the same artefact dev→tst; deploy paused; verify then resume |
| PE-28 | **Medium** | Environments are kept in sync by hand ("do not merge this back to dev" comments, commented targets); no dev/tst parity test; no migration/backfill mechanism. | `arch-deploy.md` A-18; `runtime.md` §2.3 | Rendered-bundle parity check with an allow-list for variables; migrations as code |

#### 2.3.8 Observability, operations and access

| ID | Sev | Finding | Evidence | What good looks like |
| --- | --- | --- | --- | --- |
| PE-29 | **High** | The only failure signal is a job-level webhook. No per-stream freshness, write counts, validation rejects, lag, etag conflicts or DLQ depth; a wrong catalog completes green with zero writes; non-owners cannot even list the jobs (permission boundary). | `arch-deploy.md` A-8; `runtime.md` §7, F11; `pe-exit-criteria.md` #38 | Per-stream metrics in a Delta ops table; alerts on write age and zero-write; SLO dashboard; reader visibility |
| PE-30 | **Medium** | Operators cannot answer "which Delta version produced this document?" or "what is live in container X?" — no lineage, no publish audit, no watermark record. The Oct-7 investigation had to reconstruct the state from audit logs and checkpoints. | `runtime.md` §9; `code-data.md` C-18 | `publish_audit` table (doc id, version, hash, op, status); control table of watermarks |
| PE-31 | **Medium** | Cosmos is accessed with the account **master key** from a Databricks secret scope; no managed identity/RBAC per container, no write audit, no per-document ownership enforcement. Read-only monitors cannot see job definitions. | `pipeline.ipynb` c1; `arch-deploy.md` A-8 | Managed-identity/RBAC data-plane access; writer SP scoped per container family; write audit |
| PE-32 | **Medium** | Recurring operational failure modes are structural: wrong/expired CDF pins, upstream SDP full refresh/CTAS invalidating streams, manual checkpoint resets, pause/unpause around rebuilds, container flips mid-run. Each incident is recovered by a code change or filesystem surgery. | `runtime.md` F1–F9; `nba-pe-publishing-investigation.md` §2 | Runtime start resolution; a rebuild/refresh runbook encoded as a job; control table; no pins in code |

### 2.4 Verdict on fitness for purpose

The PE is **fit for a document-per-game, best-effort, single-writer content feed**. It is **not fit for
a record-per-pick, contract-enforced, concurrency-sensitive, latency-bounded publication service**, and
the distance is not closing: measured write amplification is increasing (+72% dev, +54–102% tst versus
September), the control plane has already been refactored once for cost, and the transform/test base has
forked across three branches.

The next section quantifies what Edge Picks v4 specifically requires and what is missing. The rest of
the document is the blank-canvas answer.

---

## 3. What Edge Picks v4 requires

### 3.1 The requirement set

The v4 corpus (`edgepicks-redesign/staging/kdds.md` KDD-001/002/003, `producers-to-bff.md`,
`conf-schema-contracts.md`, `option-b-plan.md`, and `edgepicks-redesign/coexistence-approach.md`) puts
five groups of requirements on the PE. The full 41-item list with tests is in
`v4-requirements.md` §1; this is the condensed form.

| Group | Requirements | What it means for the PE |
| --- | --- | --- |
| **A. Record store and write path** (R-A1…R-A10) | New container, one document per pick per region, document id = `pick_id`, `/game_sk` partition; whole-record upsert guarded by etag; validate against JSON Schema before write and fail the run on failure; write on change; one writer and only source of pick values; persistence and frozen-field rules; forward-only lifecycle; 37-field closed record schema with deterministic ids; 1k–5k records/day; replay/idempotency | The PE becomes a **stateful record writer** with a read path, optimistic concurrency, schema validation and change tracking — none of which exists today |
| **B. Observation path** (R-B1…R-B3) | Monitor observations reach the record only through the PE; `is_closing` derived by the PE; observation feed first-class and monitored; observation→record p95 ≤ 5 min | A **fast lane** separate from the slow document pipeline, with a CDF-enabled observation source and lag telemetry |
| **C. Derived legacy documents (Stage A)** (R-C1…R-C12) | One deterministic projection *replaces* the live transforms; per-league document unions; join non-pick content; write only on projected content change; `c-outcome` result rows for every settled/void record incl. out-of-slot picks; release-gate envelope; one id in both families; history-dependent one-pick slots; per-league fidelity fixtures; shadow; per-league rollout/rollback; ordering and reconciliation | The PE must gain a **projection engine with dependency-driven rebuilds, stored state and reconciliation**, not just a new transform |
| **D. Coexistence invariants** (R-D1…R-D8) | First-publish pinning; one id; byte-level reader compatibility; id constraints; saved slips resolve; one writer, content-diffed writes and record↔document reconciliation; record as recovery point; complete reader/writer register | **Ownership and observability** become architectural requirements, not documentation |
| **E. Operational expectations** (R-E1…R-E8) | Pre-write validation as a gate; published-document conformance tests; measured latency SLOs and alerts; reconciliation; replay as a first-class operation; bulk write capability; reader/writer register; zero-write runs attributable | The PE needs an **ops surface** (audit, DLQ, SLO, replay) that today is a log line |

### 3.2 The gap, grouped

The full matrix is `v4-requirements.md` §2 (24 gaps). Grouped by what it takes to close:

| Gap group | Severity in the group | Current state | What closing looks like |
| --- | --- | --- | --- |
| **Record-first data model** (G-01, G-06, G-12, G-20; G-14) | 4 blockers + 1 high | Whole-game documents with au mirrored from us; wholesale rebuild per run; no state, no lifecycle, no two-phase consistency | New record container; per-pick merge of engine/observation/settlement inputs; two-phase publish with durable pending-projection marker |
| **Write guarantees** (G-02, G-03, G-04; G-08) | 3 blockers + 1 high | No etag, no validation, no content diff, no observation latency path | Applier with read-modify-write/etag, schema gate, content hash, fast lane |
| **Settlement/results** (G-05) | 1 blocker | Empty stubs; no table; no `settled_at`; no trigger; design conflicts with single-writer | Data-engineering-owned settlement feed; PE status update and `c-outcome` projection; push/void semantics decided |
| **Dependency graph / multi-input** (G-07) | 1 blocker | One source table per task; records/observation/settlement not in the map | Declared dependencies; rebuild driver; full-state builders where cheaper |
| **Projection fidelity and gates** (G-09, G-10, G-11, G-23; G-16) | 4 highs + 1 medium | Format A documents lack `season` (gate fails open); ids re-minted; no slot state; per-league fixtures not specified | Envelope fixtures; id contract; slot-state read; signed-off fixture set |
| **Replay, shadow, rollback, reconciliation** (G-19; G-18) | 1 high + 1 medium | No shadow; no reconciliation; start-version model fragile; single container set per env/slot | Container-set parameterisation, shadow harness, re-projection job, runtime start resolution |
| **Contract and test infrastructure** (G-13, G-21, G-22) | 3 highs | No schema artefact; no deployed tests; 19 prose invariants unencoded; writer register/ownership unenforced | Schema registry; conformance tests; CI gate; ownership registry |
| **Observability** (G-17) | 1 high | Green means nothing; no SLO, lag, write accounting | Metrics/audit/DLQ/SLO as first-class components |
| **Scale/cost and observation semantics** (G-24; G-15) | 2 mediums | Per-row SDK writes; run-per-burst; write amplification; read-before-write RU not budgeted; `is_closing` ownership undefined | Bulk/conditional writes; measured capacity plan; lane separation; PE owns derivation |

**Severity count (v4 view): 9 blockers, 11 highs, 4 mediums.** The blockers are: four in the record/
write model (G-01, G-06, G-12, G-20), three in write guarantees (G-02, G-03, G-04), one dependency-graph
blocker (G-07), and one absent producer (G-05, settlement). The rest are high/medium capability gaps.

Every gap G-01…G-24 appears in exactly one row above.

### 3.3 Hidden work the v4 corpus under-books

`coexistence-approach.md` lists nine prerequisites P1–P9 as gates; `v4-requirements.md` §4 sizes them
and finds thirteen workstreams that no v4 document budgets at zero. The ones that matter most:

1. **Settlement → record → `c-outcome`** (largest): no producer, no table in dev/tst, no `settled_at` on
   the record, grading semantics for push/void/cancelled/DNP/out-of-slot undecided, and the outcome spec
   designs a second writer into pick documents (`v4-requirements.md` H1; `coexistence-approach.md` §1).
2. **Projection inputs not on the record**: model predictions, game result/scores/injuries, per-league
   status words and casing, `type`/`code` tokens, bookmaker display name, team abbreviation position,
   stat/player/team names, legacy stat tokens, per-league odds rounding, run metadata, slot incumbent
   (H2). KDD-002 books this at zero; it is per-league fixture-and-mapping work.
3. **Validation-failure semantics and partial writes**: a validate-all-then-write boundary is required;
   the current writer commits per document inside `mapInPandas`, so one failure leaves a partially
   written container (H3).
4. **Five-minute latency versus a path that is growing**: the design adds validation, read-before-write
   and etag retries to the same path that already debounces 60 s and queues runs; the KDD's own fallback
   is a dedicated observation writer, which is a new job (H4).
5. **Schema drift between the two normative contracts and the code**, including open decisions on status
   vocabulary and reason codes due 21–30 Oct (H5).
6. **Id determinism** (`main`/`full` pinning, re-issue suffixes, cross-sport `game_sk` uniqueness, no
   `h2h` outside moneyline) is a producer obligation the PE must validate, and the current PE writes the
   source `variant` instead of the pinned token (H6).
7. **au/us independence**: today au documents mirror us picks; v4 requires one record per pick per
   region, so the engine must produce independently and the PE must not mirror (H7).
8. **`sport` semantics collide**: record `sport` is the league token (`nba`), legacy documents carry
   `sport = basketball` + `league`; the BFF and projection join on these (H8).
9. **Write-on-change vs joined content vs push**: the content-diff key must be the whole projected
   document; observation-only batches must not trigger projections; the push producer is still
   unidentified (H9).
10. **Shadow, seeded state and comparison harness** (H10), **re-projection/recovery mechanics** (H11),
    **observability as a v4 blocker** (H12), and **the two-implementation decision** (H13).

### 3.4 Where the PE sits on the v4 launch critical path

The option-B delivery plan (BFF-led) can ship P1–P3 — v7 blocks with mock data, slip safety, app
integration — without the live PE. The live-v4 phase (P4, "Live v4 data, NBA first") cannot start
without the PE: it needs the KDD-001 record container and the KDD-002 Stage A derived documents, and
option B explicitly requires each league's derived documents to be live before its v4 picks appear.
KDD-002's Stage A is therefore **on the product critical path, not just a backward-compatibility
concern**.

```
BFF P1/P2/P3 (mock v7, slips, app)  ──────────────►  app ready
                                                     │
PE Phase 0 (stop silent failures) ──► PE Phase 1 ──► PE Phase 2a record writer + validation
                                                     │
KDD-001 container + observer feed ───────────────────┤
                                                     ▼
settlement feed (DE/BE) ────────────────────────► PE Phase 2b Stage A projection + shadow
                                                     │
                                                     ▼
                                         P4 live v4, league by league
```

The practical consequence: **Phase 0 and the settlement decision should start now**, in parallel with
the BFF work. Phase 0 also removes the highest-severity defects (silent failures, broken patch mode,
zombie documents) from every league, not just v4.

---

## 4. Blank-canvas options

### 4.1 You are choosing five things, not one architecture

The current stack bundles five decisions that can be separated. Most "options" in circulation are
really positions on these axes.

| Axis | Today | What else is possible |
| --- | --- | --- |
| **A. Control-plane topology** | Per-sport router jobs, table-trigger, task-list step, worker/`for_each` fan-out per container | One job per environment driven by a declarative catalogue; one job per sport with the same catalogue; a Lakeflow/lakehouse pipeline |
| **B. Write path** | Spark `mapInPandas` → Cosmos Python SDK, one call per document | A durable publish log plus a single applier (in Databricks or external) owning validation, concurrency, retries and audit; the Cosmos Spark connector or bulk executor inside Spark |
| **C. Data model** | Stateless document builder: transform changed rows → replace whole documents | Record-first store + projections: per-entity state merged from several inputs, documents derived from it |
| **D. Contract source** | Prose Markdown specs, manual conformance | Machine-readable JSON Schema registry, generated types/docs, validation at build and write |
| **E. Deployment/cutover** | Branch = environment, container-slot duplication, pointer split across systems | Immutable release artefact, promotion, one manifest/pointer, pre-cutover gate |

A recommendation that only addresses A (collapse the jobs) or only B (fix the writer) will still fail
v4. The options below are coherent packages across the axes.

### 4.2 Option packages

#### Option A — Harden in place

Keep the router/worker topology, the notebook and the current transforms. Fix the writer (fail-loud,
generic deletes, content hash, audit), add schema validation and tests, delete dead config.

- **Effort:** 3–5 person-weeks. **Risk:** low. **Wins:** PE-01…PE-04, PE-07, PE-17, PE-23, PE-30; large
  reduction in silent failure, write amplification and zombie documents.
- **Leaves unfixed:** the stateless data model (PE-08), multi-input rebuilds (PE-13), control-plane
  latency/simplicity (PE-12, PE-14), the record-first v4 layer and settlement path (section 3), shadow
  and reconciliation. It is a good Phase 0, not an answer.

#### Option B — Consolidate: catalogue + one job + builder library + schema registry

Everything in A, plus: replace the router/task-list/fan-out with a **stream catalogue** executed by
**one job per environment**; extract the pipeline into a package; adopt a builder registry; add the
contract registry; keep the current document model.

- **Effort:** 6–10 person-weeks. **Risk:** medium (touches every stream). **Wins:** adds PE-12, PE-14,
  PE-16…PE-21, PE-23…PE-25, PE-27, PE-28; cuts the operator surface by an order of magnitude and makes the
  pipeline testable and observable.
- **Leaves unfixed:** record-first v4 semantics, observation fast lane, settlement, projection and
  reconciliation. This is the natural Phase 1 and the substrate for Option C.

#### Option C — Record-first publication substrate (recommended)

Everything in B, plus a durable **publish log** and a single **applier**, and the v4 flows expressed on
top: a per-pick record store, a fast observation lane, a slow projection/settlement lane, deterministic
derived documents and a reconciliation job. See section 5.

- **Effort:** 16–22 person-weeks for the PE side (≈10–16 weeks elapsed with two engineers), sequenced
  after/with B (not additive to B; B's work is reused), plus the settlement path (3–5 data-engineering
  weeks) and product decisions.
- **Risk:** medium; the applier and record semantics are new, but each is small, testable and
  independently replayable.
- **Wins:** addresses all nine v4 blockers structurally (eight in the PE); G-05 additionally needs the
  settlement feed and D3. Makes write-on-change, one-writer, validation,
  replay, shadow and reconciliation structural; leaves room for the remaining leagues to migrate at
  their own pace.

#### Option D — Platform-native transform layer (Lakeflow/SDP) + applier

Use Lakeflow Spark Declarative Pipelines (formerly DLT) for the builder/materialisation layer: streaming
tables or materialised views per document family, `APPLY CHANGES`, expectations, lineage and the event
log; keep the publish log and applier from Option C. Databricks now supports ForEachBatch sinks in
pipelines, so the applier can also live in the pipeline graph
([ForEachBatch sinks](https://docs.databricks.com/aws/en/ldp/for-each-batch)).

- **Effort:** 8–12 additional weeks over C (port 25 source tables/31 mappings and the monolith).
- **Risk:** medium-high: a new paradigm, and Cosmos is still not a first-class sink, so the hardest
  component does not disappear.
- **When it is right:** if the team is standardising on Lakeflow anyway, and if v4 is the moment to
  rebuild the transform layer. Not required for any v4 blocker; a candidate for Phase 3.

#### Option E — External publication service (Databricks builders → Delta outbox → ACA/Function applier)

Same as C, but the applier is a small Container App / Function App reading the Delta publish log (via
Databricks SQL/JDBC or an exported outbox) and owning the Cosmos credential, container manifest,
etag/upsert, retries, audit and cutover pointer.

- **Effort:** +4–6 weeks over C for service scaffolding, identity, CI/CD and Delta access.
- **Risk:** medium; another runtime to operate, but a familiar one in this estate (BFF/partner API are
  Container Apps/Functions), and it gives the best latency/operability and the cleanest cutover story.
- **When it is right:** after Phase 2 measures whether a Databricks job can hold the 5-minute SLA and
  after the contract stabilises. It is the long-term home of the write path, not a prerequisite.

### 4.3 Comparison and recommendation

Scoring: ●●●●● best → ● poor. "Addresses v4 blockers" counts the nine blockers in section 3.2 that the option
can close structurally; G-05 (settlement) always needs its data-engineering feed and D3 sign-off.

| Criterion | A harden | B consolidate | C record-first | D Lakeflow + C | E external applier |
| --- | --- | --- | --- | --- | --- |
| Addresses v4 blockers | ● (0–1) | ●● (2–3) | ●●●●● (8 + settlement feed) | ●●●●● (8 + settlement feed) | ●●●●● (8 + settlement feed) |
| Control-plane simplicity | ●● | ●●●●● | ●●●●● | ●●●●● | ●●●●● |
| Write correctness / concurrency | ●● | ●●● | ●●●●● | ●●●●● | ●●●●● |
| Latency headroom (5 min SLA) | ●● | ●●● | ●●●● | ●●●●● | ●●●●● |
| Testability | ●● | ●●●●● | ●●●●● | ●●●●● | ●●●●● |
| Operability / observability | ●● | ●●●● | ●●●●● | ●●●● | ●●●●● |
| Blast radius | ●●● | ●●● | ●●●● | ●●● | ●●●●● |
| Migration cost / risk | ●●●●● | ●●● | ●●● | ●● | ●● |
| Databricks-compute cost | ● | ●●●●● | ●●●●● | ●●● | ●●●●● |
| Fit with the existing team/skills | ●●●●● | ●●●● | ●●●● | ●● | ●●● |

**Recommendation: C, delivered as A → B → C, with E as an explicit Phase 3 option and D evaluated only
if the org is already moving to Lakeflow.** The reasons are not aesthetic:

- C is the smallest shape that makes the v4 requirements *expressible*: record state, observations,
  settlement, projections and reconciliation all fall out of the same log-and-applier substrate.
- It fixes the two findings that make the current engine dangerous regardless of v4: silent partial
  publishes and write amplification.
- It simplifies the estate: ~10 jobs on tst (5 on mainline) → 1–2 per environment; three transform generations → one builder
  library; 54 prose contracts → one schema per document family; one cutover pointer instead of three.
- It does not require throwing away the good parts: CDF, ids, container specs and the NBA modular /
  canonical builder style all survive.

**Rejected as primary routes:** keeping the router/worker fan-out (it cannot meet the latency budget or
the write guarantees without becoming C anyway); adopting Lakeflow as the control plane (it does not
provide a Cosmos sink, validation of documents or record semantics, and it front-loads a paradigm
migration); replacing Cosmos with direct lakehouse reads (app-scale read cost/latency and BFF rework
make it a worse trade), and an event-bus/Kafka mesh (over-engineering for 1–5k records/day; a Delta
publish log is already durable, ordered and replayable).

---

## 5. Recommended target architecture

### 5.1 Principles

1. **Contract first.** A document shape is a versioned machine-readable schema in the repository, not a
   Markdown description. Contracts are validated in CI, at the transform boundary and before the write.
2. **Records, not just documents.** For pick-family content, the per-entity state is the source of truth;
   documents are projections. For pure reference content (schedule, injuries, outcomes), the document
   can remain the state.
3. **One writer per document family, enforced by construction.** No component other than the applier
   writes Cosmos documents. Fast and slow lanes are priorities over the same writer, not two writers.
4. **Durable intent, then apply.** Builders never talk to Cosmos. They write intents to a Delta publish
   log; the applier turns intents into Cosmos writes. This gives replay, shadow, audit and
   reconciliation for free.
5. **Diff before write.** A document is written only when its canonical content hash changes (or a
   force/replay explicitly asks). Volatile fields (publish timestamp, Cosmos `_ts`) are excluded from
   the hash.
6. **Declarative control plane.** Streams, targets, schemas, lanes and start policies are data in a
   checked-in catalogue; jobs are generic engines that read it. Deploy validates the catalogue.
7. **Observable by default.** Every applied intent produces an audit row and metrics; every stream has a
   freshness watermark; zero-write and validation-reject conditions alert.
8. **Replay is a feature, not an incident.** Any range of intents or source versions can be replayed
   idempotently; a bad record is fixed forward by re-publishing.

### 5.2 Reference architecture

```
                    ┌─────────────────────────── Databricks ───────────────────────────┐
 Delta silver/gold  │  one job per environment (fast lane + slow lane + reconcile)      │
 tables + new       │                                                                   │
 observation feed   │  stream catalogue (YAML, validated at deploy)                     │
        │           │        │                                                          │
        └──────────►│  CDF readers per stream (own checkpoint; start policy from        │
                    │  catalogue; runtime-resolved, no pins in code)                    │
                    │        │                                                          │
                    │        ▼                                                          │
                    │  builders (pure functions; registry; declared input deps)         │
                    │        │  validate against C1 schema                            │
                    │        ▼                                                          │
                    │  publish intents  ── MERGE on doc_id ── content-hash diff         │
                    │  (Delta: publish_intents)                                         │
                    │        │                                                          │
                    │        ▼                                                          │
                    │  applier (the only Cosmos writer)                                 │
                    │   validate → read current (pk) → etag/version guard → upsert/     │
                    │   delete → audit → ack; retry/DLQ; fast lane prioritised          │
                    └────────┬──────────────────────────────────────────────────────────┘
                             │  bulk/conditional writes, retries, metrics
                             ▼
                    Cosmos DB (record container + legacy document containers)
                             │
                             ▼
                    BFF → app; push/WordPress/partner readers

  Side subsystems: C7 reconciliation & shadow (reads publish_intents + Cosmos),
                   C8 manifest-driven cutover (one pointer), C9 audit/metrics/SLO.
```

### 5.3 Components

#### C1 — Contract registry

- `contracts/<family>/<semver>.schema.json` (JSON Schema 2020-12) is the source of truth for every
  document family, including the v4 producer record and the derived legacy documents.
- `contracts/registry.yml` maps `doc_type → schema, container family, partition key, id formula,
  envelope fields, owner, consumers, compatibility rule`.
- Generated artefacts: pydantic models for builders, TypeScript types for the app/BFF, human-readable
  docs generated from the schema. One source, many renderings.
- CI: validate golden documents per version; reject breaking changes without a major version; check that
  every `doc_type` in the catalogue resolves to a schema, and that every schema has an owner.
- Cosmos envelope: validate the record/document body **before** adding `id`; strip Cosmos `_rid/_ts/
  _etag/_attachments` on read before validating. Cross-record invariants that JSON Schema cannot express
  (persistence, frozen fields, forward-only status, id reconstruction, arithmetic) live in a small typed
  rules module and run in the same validation step.

#### C2 — Stream catalogue

One checked-in YAML per environment overlay, loaded and validated at job start and at deploy:

```yaml
version: 4
streams:
  - id: nba.game_edge_picks
    lane: slow
    sources:
      - table: "{env}_nba.nba_gold_bets.wltp_top_picks_agg"
        start: cdf
    builder: nba.game_edge_picks@1.0.0
    inputs: [dim_all_games]
    target: { family: game_edge_picks, container_key: wltp, pk: /game_sk }
    write: { mode: whole_document, diff: content_hash, conflict: version_guard }
    delete_policy: tombstone
  - id: nba.pick_observations
    lane: fast
    sources:
      - table: "{env}_nba.nba_edge_monitor.pick_observations"
        start: cdf
    builder: nba.pick_merge@1.0.0
    target: { family: pick_record, container_key: edge_picks, pk: /game_sk }
```

- Start policy is data (`cdf`, `timestamp`, `version`, `earliest_available`), resolved at runtime
  against the actual table history; no environment-specific pins in code.
- At deploy, the catalogue is validated against schemas, builder registry, existing tables/containers,
  and the target manifest. A missing table or builder fails the deploy, not the trigger.

#### C3 — Builder library

- `publish_engine/` Python package; `builders/` has one module per document family, written in the style
  of `nba/*` and `canonical_transformations`: pure `select`/transformation functions over the input
  batch plus injected context.
- A registry decorator binds `family@version` to the function. No string dispatch in a notebook.
- Builders return `(doc_id, pk, body, content_hash, op, source_version, deps)` and declare their **input
  dependencies**; they never call `spark.table` themselves. Dimension snapshots (teams, players) are
  loaded once per run and injected; a missing dimension fails loudly, not into null names.
- Unit tests run on JSON fixtures without a cluster where possible; Spark is only needed for CDF shape
  and window logic.

#### C4 — Publish log (Delta outbox)

`publish_intents` (Delta) is the durable contract between building and writing:

| Column | Purpose |
| --- | --- |
| `doc_id`, `family`, `container_key`, `pk_json` | identity and routing |
| `op` (`upsert`/`delete`) | tombstone support |
| `body_json` | the canonical document body (or a reference to a Delta staging table for large bodies) |
| `content_hash` | canonical hash excluding volatile fields; the diff key |
| `source_table`, `source_version` | lineage: which Delta commit produced this intent |
| `deps`, `lane` | dependency-driven rebuilds and prioritisation |
| `status`, `attempts`, `error_code`, `updated_at`, `seq` | apply state, retry and ordering |
| `target_override` | shadow runs (container set override), replay and dual-run |

- MERGE on `doc_id`: keep the newest intent; if the new `content_hash` equals the stored published hash,
  mark `skipped` and do not write Cosmos.
- The log is append-friendly and replayable by `seq`; it is also the natural audit substrate and the
  input to reconciliation.
- Storage is tiny (≈1–2 KB × writes/day).

#### C5 — Applier (the only writer)

One library and one job per environment (or one task per container family inside the job):

1. Read pending intents, fast lane first.
2. Validate `body_json` against the schema for `family@version`; an invalid body goes to
   `publish_dlq` with the validation error and alerts. Validation is a gate, not a warning.
3. Canonical hash compare against the last applied hash; skip if unchanged.
4. Apply: point-read the current document by id/pk; if absent, `create`; if present with the same
   content, ack; otherwise replace with an `If-Match: <etag>` precondition. A 412 (or 409) re-reads,
   re-merges the intent with the current body's frozen fields and retries with a bounded backoff. For
   records, the merge rule is "frozen fields from first publish win; live fields from the newest intent
   win"; the applier enforces it.
5. Ack: mark the intent applied and write a `publish_audit` row (`doc_id`, `family`, `source_version`,
   `content_hash`, `op`, `status`, `error_code`, `applied_at`).
6. Retry policy: 429/5xx exponential with jitter; 400/validation no retry; dead-letter after N attempts
   with an alert.
7. Bulk: per-partition batching and the Cosmos Spark connector or transactional batch where it fits
   (same partition, ≤100 ops); otherwise the applier is I/O-bound but write-on-change keeps the volume
   low. The design target is one read + at most one write per changed document, not per document per
   trigger.

The applier is intentionally a **library plus a thin job**, so it can be moved to an external service
(Option E) without changing callers.

#### C6 — Two lanes, one writer

| Lane | Inputs | Cadence target | Content |
| --- | --- | --- | --- |
| **Fast** (observations) | observation feed CDF; engine status changes | ≤60 s processing cadence; p95 observation→record ≤5 min end to end | record `current_*`, `observed_at`, `is_closing`, `edge_status`; status transitions; late cancellations |
| **Slow** (projection/lifecycle) | engine batch output, settlement feed, dim tables | 1–2 min cadence or trigger-driven | first publish, frozen fields, settlement/outcome, derived legacy documents, schedule/outcomes/injuries |

Both lanes write intents to the same log and go through the same applier code and credentials; the
applier processes fast-lane intents first. "One writer" is therefore a property of the code path and
ownership, not of there being a single process — the v4 KDD's intent is preserved without making the
fast lane wait behind a slow projection.

#### C7 — Reconciliation and shadow

- **Reconcile** (nightly and on demand): for every family, compare the newest intent hash with the
  Cosmos document's stored hash, and for records compare the record store with the derived documents
  keyed by `pick_id`. Missing/divergent documents are repaired by replaying the intent; unresolvable
  drift is reported. This is also how "delete a derived document and restore it" is tested.
- **Shadow** (per league, before Stage A): run the same builders and applier with `target_override` to a
  container set no user reads; seed state from production; run a comparison harness that hashes each
  document and diffs legacy routes at every `api_version` in use, with an explicit allow-list of intended
  differences (the `coexistence-approach.md` gate).
- **Backfill/replay**: replay intents by `seq`/time range, or rebuild a family from source full state
  (for full-state builders); both are idempotent.

#### C8 — Control plane, deployment and cutover

- **One bundle job** per environment (or a small number if sport isolation is a hard requirement):
  `publisher` with tasks for fast lane, slow lane and reconciliation. All streams are catalogue-driven,
  so adding a league or document family is data, not a new job.
- **Immutable artefact**: a Python wheel (builders/applier) plus a config revision (catalogue/schemas)
  plus the bundle; promoted dev→tst by deploying the same artefact with a different target env. No
  branch-per-environment for code.
- **Deploy paused**: the job is deployed paused, the catalogue and target are validated, then a separate
  audited action unpauses. Deploying never silently resumes publishing.
- **One cutover pointer**: `publish-manifest.yml` (env → container per family, per-league feature flags,
  shadow on/off). The writer reads it directly; the BFF/partner app settings are generated from it (or a
  CI parity test asserts they match). Delete `COSMOS_LIVE_CONFIG` or make it a generated view of the same
  manifest — one truth, not four copies.
- **Pre-cutover gate**: per-container document counts, max write age, sampled schema validation and a
  shadow diff; fail closed. Rollback is redeploying the previous artefact/manifest revision; the old
  container set's checkpoints are untouched.
- **CI gates**: `ruff`/`mypy`, unit + fixture tests, schema validation, catalogue validation, mapping
  parity, `bundle validate --strict`, rendered-bundle env parity.

#### C9 — Observability and SLOs

- `publish_audit` Delta table and a per-stream metrics record: source commit → intent created → applied
  (freshness), documents written/skipped, validation rejects, etag conflicts, DLQ depth, zero-write
  streams, retry counts.
- Alerts: stream stale beyond family SLO; validation reject rate; DLQ non-empty; zero-write run on a
  table that changed; cutover gate failure.
- Dashboards: per family/league freshness and write rate; a "what is live" view from the manifest plus
  last applied intent per container.
- SLOs in the contract: observation→record p95 (5 min), document freshness by family (e.g. schedule
  10 min, picks 5 min), zero silent failures.

### 5.4 Write semantics and guarantees

| Property | Guarantee | Mechanism |
| --- | --- | --- |
| Idempotency | Replaying any intent is safe | Whole-document upserts keyed by deterministic id + content hash |
| Concurrency | Concurrent writes to one document do not lose frozen fields or observations | Read–merge–replace with `_etag` precondition; bounded re-read/re-merge/retry; status/frozen merge rules in the applier |
| One writer | Only the applier writes a document family | Single writer library/credential; settlement/monitor/other producers write intents, not Cosmos |
| Validation | Invalid documents never reach Cosmos | Schema gate in the builder output and again in the applier; DLQ + alert |
| Write-on-change | Unchanged documents are not rewritten | Canonical content hash excluding volatile fields |
| Deletes | Tombstones are applied and reconciled | `op=delete` intents + audit + reconciliation |
| Replay | Any range is reproducible | Publish log by `seq`; source version recorded |
| Ordering | Newer intents win per document | `seq` ordering in MERGE + version guard at apply |
| Visibility | Every write attributable | `publish_audit`: doc, family, source version, hash, status |
| Shadow | Same code path, different target | `target_override` in the intent |
| Failure isolation | One bad family does not stop others | Per-stream error policy; DLQ; job continues after quarantine |

### 5.5 The v4 flows on this architecture

| v4 flow | Builders/lane | Target | Notes |
| --- | --- | --- | --- |
| Engine publishes picks (frozen fields) | `pick_publish` builder from engine CDF; slow lane | record container | First-publish detection from the record store; persistence rule enforced by merging, never deleting siblings |
| Monitor observes market | `pick_merge` builder; fast lane | record container | Writes only `current_*`/`observed_at`/`is_closing`/`edge_status`; content hash prevents noise |
| Settlement grades picks | `pick_settle` builder from settlement feed; slow lane | record container + `c-outcome` result rows | Terminal status + outcome; one id; `settled_at`; push/void decided by product/DE |
| Derived legacy documents (Stage A) | projections from record store + joined inputs; slow lane | legacy containers | Rebuilt when the record or any declared input changes; content hash gates writes; release-gate envelope fixture-enforced |
| Reference content (schedule, injuries, outcomes) | existing-style builders; slow lane | current containers | Can remain document-shaped; same log/applier so deletes and validation are uniform |
| Per-league rollback | manifest flag per league; re-run projections | — | Turning v4 off hides it for the new app; records and derived docs untouched; fix-forward by re-publishing |

### 5.6 How the design maps to the v4 requirements

| Requirement group | How the target satisfies it | Phase |
| --- | --- | --- |
| R-A1 record container, one doc/pick/region | New family `pick_record` in the catalogue; id = `pick_id`; pk `/game_sk`; applier whole-record write | 2 |
| R-A2 etag whole-record upsert; no patch | Applier read-merge-replace with `If-Match`; patch mode deleted | 2 |
| R-A3 validate before write, fail on failure | C1 schema gate in builder output + applier; DLQ/alert; no silent skip | 1–2 |
| R-A4 write-on-change, cadence ceiling | C4 hash skip; fast-lane observation builder writes only changed observations; final pre-game write forced | 2 |
| R-A5/R-A6/R-A7 one writer, persistence, frozen/forward-only | Applier is the only writer; merge rules in `pick_merge`; status transition validator; record store retains history | 2 |
| R-A8 record schema/id | C1 contract registry; producer CI validates ids; PE validates on write | 1–2 |
| R-A9 scale/cost | Write-on-change + bulk/conditional writes; measured capacity plan before Stage A | 2 |
| R-A10 replay | Intents replayable by seq; record re-publish re-drives projections | 1–2 |
| R-B1/R-B2 observation path + `is_closing` | Fast lane; PE derives `is_closing`; observation feed in catalogue | 2 |
| R-B3 feed first-class and monitored | Catalogue stream with freshness SLO and alert | 2 |
| R-C1…R-C4 projection, unions, joins, write-on-change | Projection builders declared with input dependencies; intent log; hash gate | 2 |
| R-C5 settlement result rows | Settlement builder + `c-outcome` family; settlement feed dependency | 2 (+DE) |
| R-C6 envelope/gate | Contract registry enforces envelope; fixtures for `league`/`season` | 1–2 |
| R-C7/R-C8 id and slot rule | Projection copies `pick_id`; slot state read from prior intents/document; fixtures | 2 |
| R-C9/R-C10 fidelity and shadow | Per-league fixture set; shadow via `target_override`; comparison harness | 2 |
| R-C11/R-C12 rollout, reconciliation | Manifest per-league flags; reconciliation job; re-projection | 2–3 |
| R-D1…R-D8 invariants | Enforced by C1 schemas, C5 merge rules, audit/ownership registry | 1–3 |
| R-E1…R-E8 ops expectations | CI gates, conformance tests, SLO metrics, reconciliation, replay, reader/writer register | 1–3 |

### 5.7 What this simplifies

| Today | Target | Reduction |
| --- | --- | --- |
| 16 job YAMLs; 10 live definitions on tst (5 on mainline), 5 routers + fan-out | 1 bundle job/env (fast + slow + reconcile tasks) + 1 catalogue | ~10× fewer moving parts |
| 3 transform generations, 5,500+ LOC across branches, 2,937-LOC monolith | 1 builder library (~1,500–2,000 LOC) + registry | 3 → 1; monolith deleted |
| 54 prose contract docs, 8 schema versions, no schema | ~10–12 versioned JSON Schemas + registry + generated docs/types | one source of truth |
| Router→task-list→worker chain, 60 s debounce, queued runs | Catalogue-driven streams; trigger/cadence chosen per lane | latency floor removed |
| Hardcoded pins/maps/env logic in the notebook | Catalogue + runtime start resolution + manifest | no code change to re-anchor a stream |
| Branch-per-environment, delete/re-upload deploy, auto-unpause | Immutable artefact, promotion, deploy paused, one pointer | one release process |
| "Did this document change? Which row wrote it?" | Content hash + `publish_audit` per intent | answerable |
| Blue/green duplicate job sets and split pointers | One manifest + pre-cutover gate + revision rollback | one cutover operation |

### 5.8 What it costs, and where it does not help

- **New concepts to learn:** publish log, applier, catalogue, manifest. They are small and each replaces
  a worse mechanism; the team already knows Spark, Delta and Cosmos.
- **An extra point read per changed document** (for etag/diff). At 1–5k records/day plus projections this
  is negligible RU, but it must be measured and budgeted (KDD-001's cost table does not include it).
- **More tables:** intents, audit, DLQ, control/watermarks. Storage is trivial; governance is not free —
  these need owners and retention rules.
- **A migration, not a big bang:** one family at a time, with the old path frozen and a shadow compare.
  The hardest part is not the new code; it is retiring the old paths and the branch/topology they live in.
- **It does not fix the BFF read model, app contracts or product behaviour.** Those remain owned by the
  BFF/app workstreams; the PE's job is to make their inputs correct, fresh and auditable.
- **It does not remove the need for the settlement producer.** No PE design can grade picks without a
  settlement feed and a decision on push/void/cancelled semantics; that is the largest external
  dependency in the programme.

### 5.9 Implementation choices (the "how", not just the "what")

| Concern | Recommendation | Why | Alternative considered |
| --- | --- | --- | --- |
| **Packaging** | `publish_engine/` Python package (`config`, `builders`, `applier`, `contracts`); the notebook becomes a ~15-line launcher; versioned wheel + catalogue revision | Static analysis, unit tests, reviewable diffs, immutable artefact | Keep notebook-hosted code (rejected: no test surface, JSON diffs) |
| **Validation** | JSON Schema 2020-12 as the source, pydantic v2 models generated/checked against it, exported TypeScript types for BFF/app | One source, three consumers; CI catches drift | Avro/Protobuf (heavier for the contract consumers), hand-written checks (drift) |
| **Write client** | Cosmos Python SDK in the applier: point read + conditional replace/create, per-partition batching, bounded retry; evaluate the Cosmos Spark connector or `execute_item_batch` for bulk projections. Never `patch_item` | Correct concurrency and null semantics; measured volume is small | Cosmos Spark connector end-to-end (good for bulk, poor for per-document conditional logic); patch mode (removed) |
| **Configuration** | `catalogue.yml` + `publish-manifest.yml`, validated against a JSON Schema at deploy and job start | Adding a stream/league is data, not code; no pins in code | Hardcoded map notebook (rejected), Unity Catalog config tables (possible later if runtime editing is needed) |
| **State** | Delta tables `publish_intents`, `publish_audit`, `publish_dlq`, `publish_watermarks`; retention policy per table | Replay, audit, reconciliation, SLOs; cheap storage | Cosmos-only state (no replay/audit), checkpoint-only state (current, insufficient) |
| **Orchestration** | One DAB job per env with fast, slow and reconcile tasks; cadence per lane (e.g. fast `availableNow` every 1 min, slow 1–2 min or trigger) | Meets the 5-minute budget with measured headroom; simple to operate | Per-sport jobs (more isolation, more duplication); continuous cluster (cost, unless SLA demands) |
| **Testing** | pytest + JSON/Arrow fixtures; pure builder tests; golden-document contract tests; Cosmos emulator or in-memory writer double; one Spark-local CDF edge-case suite | Fast feedback; contract conformance, not self-comparison | Current feat-branch suite (right idea, wrong place, no golden docs) |
| **Deployment** | Bundle deploy of the job + wheel, deployed paused; environment target selects the manifest; promotion of the same artefact | Atomic, reversible, no branch-per-env | Current delete-and-reimport + auto-unpause (rejected) |
| **Identity/access** | Workspace managed identity or a dedicated SP with Cosmos data-plane RBAC per container family; no account master key in the job | Least privilege, write audit, revocable | Current master key in Databricks secret scope (interim only) |
| **Read model** | Keep Cosmos as the serving store; the applier owns document shape; the BFF may cache but does not write | No app/BFF re-platform; the PE's job is correctness/freshness | Direct lakehouse reads (cost/latency at app scale), a new serving store (unjustified) |

---

## 6. Migration plan

### 6.1 Phases

The sequence is designed so that each phase is independently useful, each leaves the estate working,
and the v4-critical path is front-loaded. Estimates are for one experienced PE engineer unless stated;
they exclude BFF/app/product work.

#### Phase 0 — Stop silent failures (weeks 0–2)

**Objective:** make the current engine honest and safe before any new capability rides on it.

| Work package | Fixes | Effort |
| --- | --- | --- |
| Fail-loud writer: raise on non-retryable Cosmos errors; count and report every skipped row; write a per-batch audit row | PE-01, PE-03 (partial), PE-30 | 3–4 d |
| Remove patch mode; if any partial-update story is genuinely required, implement it as read-merge-replace with etag, never as Cosmos patch | PE-02 | 1–2 d |
| Generic delete handling: delete policy per mapping (id + partition key); tombstone path shared by all transforms; reconciliation query for existing zombies | PE-04 | 3–4 d |
| Content-hash skip on write (canonical hash excluding `publish.published_at_utc`/`timestamp`/Cosmos system fields); report skipped/written counts | PE-07 | 2–3 d |
| Delete the five deprecated router files and commented targets; `bundle validate --strict`; delete dead code (`transform_game_top_picks`, unused parameters) | PE-19, PE-28 | 1 d |
| Fix or delete `COSMOS_LIVE_CONFIG` and document the real pointer; deploy paused by default; add an explicit unpause action | PE-26, PE-15 | 2 d |
| CI PR workflow: `ruff` + `pytest` + `bundle validate`; port the 61 feat tests to the branch CI deploys as a baseline; add a mapping-parity test | PE-16, PE-23 | 3–4 d |
| Alerts: zero-write run, stream stale beyond 30 min, any write errors, DLQ non-empty | PE-29 | 2 d |

**Exit criteria:** no write error can pass silently; deletes produce tombstones; a no-change trigger
produces zero writes and says so; CI blocks a merge on tests/validate; one documented cutover pointer.
**Effort: 3–4 person-weeks (≈2–3 weeks elapsed).**

#### Phase 1 — Consolidate the engine and the contracts (weeks 2–6)

**Objective:** one engine, one catalogue, one codebase, schemas as code.

| Work package | Fixes | Effort |
| --- | --- | --- |
| Extract `publish_engine/` package from the notebook: config, builders, writer, contracts; notebook becomes a thin launcher | PE-18 | 4–5 d |
| Builder registry replacing the 14-branch string dispatch; per-family modules in the `nba/*`/`canonical_*` style | PE-16, PE-17 | 4–5 d |
| Stream catalogue (YAML) replacing `build_transformation_map.ipynb` and its duplicated Markdown; validated at deploy | PE-12, PE-15 | 3–4 d |
| One job per environment (fast/slow/reconcile tasks; adopt mainline's 19 Oct `for_each` direction and retire the worker jobs everywhere) | PE-12 | 2–3 d |
| Contract registry v1 for existing document families: JSON Schema per `doc_type`/version, golden documents, generated docs/types, CI validation | PE-20, PE-22, PE-25 | 5–6 d |
| Unify branches: rebase `tst-blue` onto mainline topology; one workflow with environment selected by target; immutable artefact (wheel + bundle) and promotion | PE-27, PE-28 | 3–4 d |
| Env parity and catalogue validation in CI; `workspace.host` per target; pin tool versions | PE-28 | 1–2 d |

**Exit criteria:** 1 job/env; every family published through the catalogue; PR gates green; contract
registry owns every document; tst runs the mainline topology; bundle validates with zero warnings.
**Effort: 5–8 person-weeks.**

#### Phase 2 — Record-first v4 substrate (weeks 6–14)

**Objective:** close the v4 blockers with the publish-log + applier design.

| Work package | Fixes | Effort |
| --- | --- | --- |
| Publish log (`publish_intents`) + applier with validation, content hash, etag/version guard, audit, DLQ, retry; pilot on one reference family (schedule) | PE-05, PE-06, PE-07, PE-26 (new writer), R-E1/R-E4 | 3–4 wk |
| Record container + record builders (publish/merge/settle); frozen-field and forward-only merge rules | R-A1, R-A2, R-A5…R-A8 | 3–4 wk |
| Observation feed + fast lane; `is_closing`/`edge_status` derivation; freshness SLO | R-A4, R-B1…R-B3 | 2 wk |
| Settlement feed and `c-outcome` result rows (with data engineering/bet engine) | R-C5, PE-13 | 2 wk (PE) + 3–5 wk (DE) |
| Stage A derived legacy documents: projections with declared input dependencies, per-league fixtures, shadow via `target_override`, comparison harness | R-C1…R-C4, R-C7…R-C10, PE-13 | 4–5 wk |
| Reconciliation job + re-projection path; cutover gate; per-league manifest flags | R-C11, R-C12, PE-26 | 1–2 wk |
| Capacity/load test at 5k records/day; measure observation p95 and compute cost; decide D6 (external applier) | R-A9, R-E3, R-E6 | 1 wk |

**Exit criteria:** record container live in dev and tst; NBA Stage A runs in shadow with a clean diff
across every reader/version; observation→record p95 measured within 5 min; reconciliation and
re-projection tested; load test passes; product/DE sign-off on the league gate list.
**Effort: 16–22 person-weeks (PE; ≈10–16 weeks elapsed with two engineers) + 3–5 person-weeks (DE
settlement) + fixtures/product time.**

#### Phase 3 — Simplify and decommission (weeks 12–20, parallel after Phase 1)

**Objective:** remove the old world rather than maintain both.

| Work package | Fixes | Effort |
| --- | --- | --- |
| Migrate the remaining leagues (MLB/WNBA/NFL/EPL) off the monolith to builders; delete `transformations_library.py` and patch paths | PE-16, PE-17 | 3–5 wk |
| Retire per-sport slot job duplication and the old backup/restore flow; manifest-driven cutover only | PE-26, PE-27 | 1–2 wk |
| Stage B BFF adapters per route (with BFF team); stop writing a legacy document when nothing reads it | R-D5, R-E7 | BFF-owned |
| Evaluate externalising the applier (Option E) based on Phase 2 latency/cost/ops evidence | D6 | 1 wk decision |
| Cost tuning: cadence, clustering of streams, RU budget, retention of intents/audit | PE-29 | 1 wk |
| Documentation: generated contracts, runbooks for replay/rebuild/shadow/cutover, on-call alerts | all | 1–2 wk |

**Exit criteria:** one builder library; monolith and patch mode deleted; one branch/promotion model; one
cutover operation; all v4 leagues on Stage A; runbooks exercised.
**Effort: 4–8 person-weeks.**

### 6.2 Critical path and sequencing

- **Start now:** Phase 0 and the settlement decision (D3). They are the only items that block v4 and do
  not depend on the target design being approved.
- **Phase 1 must precede Phase 2** because the publish log/applier need the package boundary, catalogue
  and schema registry; attempting them inside the notebook re-creates the current problems.
- **The BFF workstream is independent** until P4 (live v4): it can ship v7 blocks with mock and legacy
  data against the current BFF. Do not delay it for the PE.
- **The PE record writer and Stage A are on the P4 critical path.** If Phase 0 starts in week 0 and
  Phase 2 in week 6, the first league's shadow could be in week 12–14 — before that, P4 cannot begin.
- **Do not run Phase 3 before Phase 2 is proven**, and do not retire a legacy path until its reader
  register is complete.

### 6.3 Acceptance gates

| Gate | Must be true |
| --- | --- |
| G0 (end Phase 0) | No swallowed write errors in a 2-week dev window; a zero-write run alerts; CI blocks merges on tests; one documented pointer |
| G1 (end Phase 1) | One job/env; catalogue validated at deploy; every family has a schema and golden document; tst == mainline topology; one promotion workflow |
| G2a (record writer) | Record container in dev; concurrent status+observation survives; invalid record fails/quarantines with an alert; no `patch_item` in the codebase |
| G2b (Stage A) | Shadow diff clean across the reader register at every `api_version`; write count ≤ today; record↔document reconciliation restores a deleted document |
| G2c (latency) | Observation→record p95 ≤ 5 min over a live slate; per-stream freshness metrics and alerts live |
| G3 (decommission) | Monolith deleted; all leagues on builders; one cutover operation exercised; runbooks signed off |

### 6.4 Risks and mitigations

| # | Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- | --- |
| R1 | Settlement producer/`settled_at` never lands or is owned by nobody | High | Blocks Stage A results and out-of-slot My Picks | Make D3 a week-1 decision with a named owner and a minimal table contract; build the PE side against a fixture feed so it is not blocked |
| R2 | Contract drift continues (status vocabulary, reason codes, `sport` semantics) | High | Validation gate encodes the wrong thing; rework | Contract owner + change log; freeze 4.x fields before Phase 2; schema compatibility CI |
| R3 | Migration happens while the live product ships | High | Split attention, partial migrations | Phase 0/1 are backward-compatible; Stage A per league in shadow; never retire a path until its reader register is complete |
| R4 | `tst-blue` fork is not reconciled before v4 | Medium | v4 signed off on non-mainline software | Phase 1 exit gate; no v4 deploy from a fork |
| R5 | Latency SLA not met by a Databricks job | Medium | v4 promises 5 min and misses | Two-lane design; measure in Phase 2; decision gate D6 to external applier |
| R6 | One-writer rule violated by an existing design (settlement write-back, live-odds) | Medium | Data races, lost observations | Ownership registry; route writes through PE; remove second-writer designs from specs |
| R7 | Validation rejects a producer's live output and blacks out a slate | Medium | User-visible | Quarantine mode for launch (alert + fallback to last good document), fail the run only for contract violations after sign-off |
| R8 | Cosmos/Spark/Delta version or API changes (patch semantics, connector) | Low | Rework | Pin versions; contract tests; avoid patch mode (removed) |
| R9 | Team capacity/competing priorities | High | Delay | Phase 0 is small and independently fundable; Phase 2 can follow the BFF milestone rather than block it |
| R10 | The reader/writer register is incomplete (push producer unidentified) | Medium | Write-on-change changes push cadence; silent consumer break | Make register completion a Stage A gate (as `coexistence-approach.md` requires); instrument where possible |

### 6.5 Open questions for the next review

These are unresolved facts or decisions that change the plan; each has an owner to name.

| # | Question | Why it matters | Recommended owner |
| --- | --- | --- | --- |
| Q1 | Who owns the settlement table and its schema (`pick_id`, `outcome`, `settled_at`, `reason`, scope)? | Blocks the largest hidden work item and P4 results | Bet engine + DE |
| Q2 | Is the record container part of the PE, or a separate service the PE writes into? Who builds the fast observation writer? | Decides the PE's boundary and the 5-min path | Architecture + DE |
| Q3 | Which implementation is the v4 base — deployed `nba/*` modules or the feat-branch canonical registry? | Building on the wrong base doubles the work | PE lead |
| Q4 | What does "first publish" mean operationally and where is the publication record stored? | Projection filtering and rollback depend on it | PE + BFF |
| Q5 | Does a push producer read the legacy documents, and what is its identity? | Write-on-change changes push cadence; register completion | DE + platform |
| Q6 | Is `sport` in the record the league token, and how do records join legacy documents? | Silent join failure in BFF/projection | Contract owner |
| Q7 | Validation policy: fail the whole run or quarantine per record at launch? | Determines live-slate blast radius | PE + product |
| Q8 | Is the 5-minute SLA measured monitor-write→record or observation→record? | KDD-001's wording is ambiguous; it changes the budget | Product + DE |
| Q9 | Where are the new environments/containers and who reads them (BFF cache identity/RBAC)? | KDD-001 leaves container names and read identity open | DE + BFF |
| Q10 | Are the five legacy leagues in scope for the target, or NBA-only first? | Determines how long the monolith survives | PE + product |

### 6.6 What to verify next (read-only, cheap)

If the team wants to validate this assessment before committing:

1. **Confirm the patch-mode failure in production** — read the `Errors:` counts in recent EPL/MLB PE
   job logs; any non-zero error count on an `isPatch` stream confirms PE-02. (The PE jobs are not
   visible to the read-only SP; a job owner must pull the logs.)
2. **Read one document per family from Cosmos** and validate it against the docs; sample sizes and `_ts`
   values confirm the write-amplification and body-size estimates.
3. **Identify the push producer** by grepping the estate for readers of `c-wltp`/`c-ps`/`c-outcome` and
   checking Service Bus subscriptions — this closes the largest reader-register gap.
4. **Confirm settlement-table ownership** with the bet engine team and check whether `nba_pick_settlements`
   exists in any environment.
5. **Measure current end-to-end latency** on one family with a source commit and Cosmos `_ts` sample
   (requires job-owner access or a temporary read identity).
6. **Enumerate compute cost** from Databricks billing/`system.billing` with a workspace admin identity —
   the only way to size the cost case for the control-plane simplification.

### 6.7 The first ten working days

| Day | Action |
| --- | --- |
| 1–2 | Approve D1/D2 direction in principle; name owners for D3 (settlement), D5 (pointer), D8 (contracts) |
| 2–3 | Phase 0 work package 1 (fail-loud writer) and the CI PR workflow in parallel |
| 3–5 | Remove patch mode, add generic deletes and content-hash skip behind flags; measure the write-count delta on dev |
| 5–7 | Delete dead router files/targets; fix or delete `COSMOS_LIVE_CONFIG`; deploy-paused change |
| 7–9 | Port the 61 tests; add schema registry skeleton for the two most-used families (schedule, game_prediction) |
| 9–10 | Review the Phase 0 evidence, choose the Phase 1 start date, and lock the settlement contract with BE/DE |

---

## 7. Appendices

### A. Method, evidence basis and limitations

**Reviewed:** `app-data` at `tst-blue` `a1c16f4` (13 Oct 2026), `origin/dev` `56e4ca7` (19 Oct 2026,
moved during the review), `origin/feat/nba-2026` `54214ec` (17 Sep 2026); the Edge Picks v4 corpus
(`kdds.md`, `producers-to-bff.md`, `conf-schema-contracts.md`, `option-b-plan.md`,
`coexistence-approach.md`, `specs.md`); live read-only Databricks and Azure Monitor on 20 Oct 2026; the
prior in-repo investigations. Every workstream file in `.analysis/v4/` carries its own finding IDs,
evidence and verified-vs-assumed split.

**What is measured as of 20 Oct 2026:** container write volumes/RU (Azure Monitor, 7-day window),
current written container sets, upstream commit cadence (Delta history), serverless Cosmos account mode,
job visibility/permission boundaries, and repo/branch state.

**What is prior evidence, not re-measured:** job run counts (Sept audit logs), end-to-end latency
(Sept dev study), CDF pin incidents and checkpoint resets (7 Oct), the blue/green findings (16 Sep).
Those dates are attached wherever they are used.

**What cannot be verified from this VM:** PE job definitions, runs, durations, failure counts, concurrency
and cluster/compute cost (permission boundary); Cosmos document contents and `_ts` values (no data-plane
credential); alert delivery history; Log Analytics (not configured for this session). Document sizes are
`DataUsage/DocumentCount` estimates including index, not body measurements.

**Anti-claims respected in this document:** no current PE job count/pause state claimed as verified; no
latency SLO claimed as met or failed; no Databricks compute cost; no claim that tst is still
double-publishing (it stopped 18 Oct 21:53Z); no claim that the deployed code equals `tst-blue` or
`origin/dev`; no "no throttling" claim (absence of `Http429` metric is a monitoring gap).

**How the workstreams were commissioned:** four independent analyses (architecture/deployment, data-plane
code/contracts, runtime evidence, v4 requirements) with their own evidence and open questions; this
document reconciles them, resolves overlaps, and adds the target design, options and migration plan.
Disagreements and limits are noted rather than smoothed over.

### B. Consolidated finding register

Source IDs: A-* = `arch-deploy.md`; C-* = `code-data.md`; F-*/§ = `runtime.md`; G-*/H-*/R-* =
`v4-requirements.md`.

| ID | Dimension | Severity | Finding | Source |
| --- | --- | --- | --- | --- |
| PE-01 | Write path | Critical | Write errors counted, never raised; missing-id rows skipped silently | C-1 |
| PE-02 | Write path | Critical | Patch mode exceeds 10-op limit, cannot null, errors swallowed | C-2 |
| PE-03 | Write path | High | No pre-write validation of any kind | C-7 |
| PE-04 | Write path | High | Deletes dropped for 28/31 mappings (3 can delete); no reconciliation | C-3 |
| PE-05 | Write path | High | No etag/optimistic concurrency; single-writer unenforced | C-11 |
| PE-06 | Write path | Medium | Batch ordering/precedence undefined; replay can regress | C-10 |
| PE-07 | State | High | No content diff/state; measured 45 full-container rewrites/day | C-4; runtime §3.3 |
| PE-08 | State | High | Stateless document builder cannot express record lifecycle | C-5; G-01/G-12/G-14 |
| PE-09 | State | Medium | Transforms impure; per-batch table reads; fail-open lookups | C-5 |
| PE-10 | State | High | Replay/start state depends on hardcoded pins and checkpoint surgery | C-13; F1–F6 |
| PE-11 | State | Medium | Environment-specific pins/config in code; `failOnDataLoss=false` | C-9, C-13 |
| PE-12 | Control plane | High | ~10 job definitions on tst (5 on mainline), fan-out, 60 s debounce, queued runs | A-7, F7 |
| PE-13 | Control plane | High | One-input-per-task routing; multi-input documents never rebuilt | C-12, G-07 |
| PE-14 | Control plane | Medium | Latency unmeasured; last measured study: 66% within 60 min for one MLB family | runtime §4; KDD-001 |
| PE-15 | Control plane | Medium | Pause/unpause via deploy; trigger tables hand-edited per branch | A-11, A-12 |
| PE-16 | Codebase | High | Three diverging transform generations; tested ≠ deployed | C-6, C-17 |
| PE-17 | Codebase | Medium | Monolith complexity, duplication, dead code | C-16 |
| PE-18 | Codebase | Medium | Notebook-as-application; no package/types/lint | C-14 |
| PE-19 | Codebase | Medium | Dead/half-wired code and deprecated router files | C-16; A-14 |
| PE-20 | Contracts | High | No machine-readable schema; 54 prose docs; version sprawl/drift | C-7, C-8 |
| PE-21 | Contracts | Medium | No compatibility rule/owner/consumer register | H5, G-21 |
| PE-22 | Contracts | Medium | Guards only on unmerged branch; prose invariants unencoded | G-13; feedback_g4 |
| PE-23 | Testing/CI | High | Zero tests on the branches CI deploys; CI deploys without tests | A-16; C-15 |
| PE-24 | Testing/CI | Medium | Feat tests are Spark integration tests; no golden fixtures | C-17 |
| PE-25 | Testing/CI | Medium | No published-document conformance tests | pe-exit-criteria #27–32 |
| PE-26 | Deploy/cutover | Critical | Split pointer, inert live rule, no gate, 5.5-day duplicate publish | A-1, A-2, A-6; F10 |
| PE-27 | Deploy/cutover | High | Non-atomic deploy, auto-unpause, no artefact/promotion, tst fork | A-3, A-5, A-15, A-17 |
| PE-28 | Deploy/cutover | Medium | Hand-maintained env parity; no migration mechanism | A-18; F4 |
| PE-29 | Observability | High | Only failure webhook; zero-write green; no SLO/audit; jobs invisible | A-8; F11 |
| PE-30 | Observability | Medium | No lineage/watermarks/publish audit | C-18 |
| PE-31 | Access | Medium | Cosmos master key; no RBAC/write audit/ownership enforcement | pipeline c1; A-8 |
| PE-32 | Operations | Medium | Structural failure modes (pins, rebuilds, resets, flips) recur | F1–F9; investigation §2 |

### C. Option scoring detail

Weights used in section 4.3 (judgement, not science): v4 blockers 30%; write correctness 20%;
migration cost/risk 15%; control-plane simplicity 10%; latency headroom 10%; testability 5%;
operability 5%; cost 5%. Under those weights, C scores highest, B second, E third (E is C plus an
external applier and therefore inherits C's scores except migration cost/operability), D fourth (C plus
a paradigm migration), A fifth. The ranking is stable if "v4 blockers" and "write correctness" stay
above 40% combined — which is the point: the choice is driven by the v4 requirements, not by aesthetics.

### D. Target component responsibilities

| Component | Owns | Consumes | Fails how | Tests |
| --- | --- | --- | --- | --- |
| C1 Contract registry | Schemas, compatibility, generated types/docs | Contract changes | Breaking change blocked in CI | Schema validate + golden documents |
| C2 Stream catalogue | Stream definitions, start policy, targets, lanes | Env manifest | Deploy fails on invalid stream | Catalogue validation + parity |
| C3 Builders | Canonical document construction, deps | CDF batch + injected dimensions | Throws; run fails; DLQ row | Pure unit + fixture tests |
| C4 Publish log | Durable intents, content hash, ordering, replay | Builder output | MERGE conflict retried; log is append-only | MERGE/idempotency tests |
| C5 Applier | Cosmos writes, validation, concurrency, retry, audit, DLQ | Intents | Retries; dead-letters; alerts | In-memory Cosmos double + emulator integration |
| C6 Lanes | Priority and cadence | Catalogue | Fast lane degrades first; alerts | Load/latency tests |
| C7 Reconcile/shadow | Drift detection, repair, comparison | Intents + Cosmos + readers | Reports, never silently repairs beyond replay | Scenario tests (delete/restore) |
| C8 Control plane/deploy | One job, immutable artefact, paused deploy, manifest pointer, gate | Git + manifest | Deploy fails closed; old revision still serving | Deploy dry-run + cutover rehearsal |
| C9 Observability | Audit, metrics, SLO, alerts | Intents/applier/audit | Alerts on missing metrics (dead-man) | Metric contract tests |

### E. Glossary

| Term | Meaning |
| --- | --- |
| **CDF** | Delta Change Data Feed; `readChangeFeed=true` streaming read of insert/update/delete rows |
| **DAB** | Databricks Asset Bundle; declarative job/pipeline definitions deployed by `databricks bundle deploy` |
| **Applier** | The single component that validates and writes intents to Cosmos |
| **Publish log / outbox** | Delta table of durable document intents (`publish_intents`) with hash, op, source version and status |
| **Content hash** | Canonical hash of a document body excluding volatile fields; the write-on-change key |
| **Lane** | Fast (observations) or slow (projection/lifecycle); same writer, different priority/cadence |
| **Record store** | The per-pick-per-region Cosmos container proposed by KDD-001 |
| **Stage A / Stage B** | KDD-002: derived legacy documents written at publish time / BFF adapters reading records directly |
| **Manifest** | One checked-in mapping of env → container per family + feature flags; the cutover pointer |
| **SLO** | Service-level objective; here freshness and failure-rate targets per stream/family |

### F. References

**Internal (v4 corpus):** `edgepicks-redesign/staging/kdds.md` (KDD-001/002/003);
`staging/producers-to-bff.md`; `staging/conf-schema-contracts.md`; `staging/option-b-plan.md`;
`staging/delivery-options.md`; `staging/feedback_g4.md`; `staging/kdds_feedback.md`;
`edgepicks-redesign/coexistence-approach.md`; `edgepicks-redesign/specs.md`;
`edgepicks-redesign/canonical-data-model.md`.

**Internal (PE evidence):** `app-data/.analysis/v4/*.md`;
`app-data/nba-pe-publishing-investigation.md`; `app-data/bluegreen_assessment.md`;
`app-data/pe-exit-criteria.md`; `app-data/pe-exit-criteria-programme.md`; `app-data/pr-issues.md`;
`app-data/pe-flow-doc-review.md`; `app-data/databricks/docs/pe/container_structure/`;
`app-data/databricks/docs/containers/`.

**External platform references:**

- [Azure Cosmos DB partial document update FAQ](https://learn.microsoft.com/azure/cosmos-db/partial-document-update-faq)
  — 10-operation limit per patch request, and why patch cannot set a field to null.
- [Databricks Lakeflow: ForEachBatch sinks](https://docs.databricks.com/aws/en/ldp/for-each-batch) —
  custom sinks in declarative pipelines, relevant to Option D.
- [Databricks compute types](https://learn.microsoft.com/azure/databricks/compute/choose-compute)
  — serverless compute start-up (seconds) versus classic job clusters, relevant to the latency and cost
  discussion.
- [Azure Cosmos DB Spark connector](https://github.com/Azure/azure-sdk-for-java/blob/main/sdk/cosmos/azure-cosmos-spark_3_2-12/docs/migration.md)
  — write strategies and bulk batch size (`spark.cosmos.write.strategy`, `spark.cosmos.write.bulk.maxBatchSize`),
  relevant to the applier's bulk path.

---

## 8. Bottom line

The Publish Engine is not a bad system; it is a **good small system carrying a large product**. Its
core insight — publish from Delta change data into Cosmos under deterministic ids — remains right. What
has accumulated around it (stateless whole-document rewrites, swallowed failures, three code
generations, prose contracts, a hand-operated slot switch) is the cost of growing without a publication
substrate.

Edge Picks v4 is the forcing function. It needs a record store, validation, concurrency, a five-minute
observation path, settlement results and derived legacy documents that are provably consistent with the
records. Those are not features to add to `mapInPandas`; they are properties of a different publication
model.

**Recommendation:** approve the contract-first, record-first target (Option C), fund Phase 0
immediately, decide the settlement path in week 1, and treat Phase 1 (one job, one catalogue, schemas)
as the bridge that makes the v4 work safe. The result is a simpler engine — one job instead of ten, one
builder library instead of three generations, one contract registry instead of 54 prose documents, and
one cutover pointer instead of three — with the guarantees the product is about to promise.

