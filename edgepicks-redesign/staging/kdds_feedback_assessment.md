# Assessment of `kdds_feedback.md` (review of KDD-001 and KDD-002)

Oct 19, 2026 · reviewed against `staging/kdds.md` (287 lines, commit c06d8c6), the four v4 contract pages, `coexistence-cutover-plan.md`, `reqs/nba/kdd_schema.md`, and the code at mobile-server `develop`, app-data `dev`, live-odds `dev` (local checkouts).

## Verdict

The feedback points at real problems, and roughly two thirds of its findings survive verification. It is not reliable as written, though:

- **It quotes text that is not in `kdds.md`.** Six quotations, including the two it builds its KDD-002 findings on, appear in no version of the file in git history (180, 182 and 287 lines). They read as paraphrases presented as quotes.
- **It misstates the v4 contract.** It defines `withdrawn` as "the edge dropped below threshold" (the contract says "published in error"), uses `won`/`lost`/`void` as `pick_status` values (they are `outcome` values under `settled`), and lists mutable fields that do not exist.
- **About a third of its code citations are wrong or overstated** (table in section 1.3).
- **It misses the most consequential issues.** The biggest: `pick_id` is only unique within a region but becomes the Cosmos `id` in a partition shared by both regions (N1). KDD-002 also creates its own id-bridge problem (N2), and it reverses more of the Oct 17 plan than the C5 rule it names (N3).

Don't apply its summary table (section 4) as written. Use the revised list in section 4 below.

---

## 1. Reliability of the feedback

### 1.1 Quotations that do not exist in `kdds.md`

| Feedback | What it quotes | What `kdds.md` actually says |
| --- | --- | --- |
| §2.2, "line 26" | "Create a new Cosmos container … shared across all sports." | "Producer pick records go into a new Cosmos container, separate from the existing `c-wltp-*` and `c-ps-*` containers." Sports are not mentioned. |
| §2.3, "line 31" | "The BFF must cache the day's pick records per `(region, day)` for 30 to 60 seconds…" | "The BFF reads Cosmos once per region and day into a shared cache, never once per app request…" No 30–60 s figure appears in Decision. |
| §2.3, "line 79" | "Four regions cached for 60 seconds … about 23,000 queries a day (~$17/month)" | The model is 2 regions × 3 days, about 3.4M RU/day and about $25/month (lines 75–79). The contract has only `au` and `us`. The "4 × 1,440" critique attacks a model the KDD does not use. |
| §2.4, "line 121" | "one point read and a partial update of the `current_*` fields" | Line 121 is Validation step 2 (record the RU of an insert, a replace and a partial update). |
| §3.2, "line 197" | Row "A withdrawn or settled pick … Mapped to scheduled (withdrawn) or final (settled)" | No such row. Line 197 is the `awaiting_result → scheduled` row. **KDD-002 says nothing about `withdrawn` or `settled`.** That is the real gap. |
| §2.2 | `overlay_key = lower(sport) + ":" + pick_id` (realtime-overlays.md:59) | `sport + "_" + base64url(pick_id)` |
| §3.1 | `POST /v4/my-picks` | No such route in the contracts or the BFF. The routes are `my-picks`, `my-picks-v2` and `v3/my-picks`. |

### 1.2 Contract errors

- **`withdrawn`** (feedback §3.2): the contract defines it as "Published in error | BFF never serves it" (producers-to-bff.md:45). An edge that drops leaves the pick `open` with `edge_status: closed` (:47, :61). A market that moves past the edge gives `cancelled`, reason `market_moved`. The feedback's reasoning is wrong, but its fix is still right, for a stronger reason: the legacy BFF filters only `"cancelled"` (my-pick.ts:9–25) and passes any other status through (`pick.pick_status ?? "active"`, canonical/picks.ts:479). A projected `withdrawn` would be served to older builds as a live pick.
- **Settlement** (§3.3): v4 has `pick_status: settled` with `outcome` won, lost or push, plus `void`. The feedback's mapping leaves out **push**. Today NBA game picks store a push as no outcome, so it stays `scheduled`, and snapshot.ts:314 renders a found result with a null outcome as `"void"`. Push needs an explicit legacy mapping.
- **Mutable fields** (§2.4): `current_price`, `current_stake`, `current_direction`, `current_bookmaker`, `withdrawn_at` and `updated_at` do not exist. The live set (rule 3) is nine observation fields (`current_decimal_odds`, `current_american_odds`, `current_line`, `current_odds_source_kind`, `current_bookmaker_id`, `observed_at`, `is_closing`, `current_edge`, `edge_status`) plus `pick_status`, `status_reason`, `outcome`, `rec_action` and `schema_version`. An observation with a status change is therefore 11 or more patch ops, so the 10-op concern is *stronger* than stated.
- **`sport` enum** (§2.2): `ncaab` appears nowhere in the contracts. The leagues are nba, nfl, mlb, wnba and epl.

### 1.3 Code citations

| Feedback claim | Checked | Note |
| --- | --- | --- |
| Publisher skips items with no `id` | ✔ | `if not item_body.get("id"): continue`. Silent: not even counted as an error. |
| Patch builds one op per non-null field | ✔ | It also **drops `None` values, so a patch can never set a field to null.** The v4 schema requires nulls (`current_edge` after a line move, prices when pulled). The feedback missed this. |
| Non-404 patch errors are swallowed with `pass` | ✗ / ~ | They are counted in `errors` and logged. The batch does not fail, so the practical effect is similar. |
| Notebook emits Service Bus push events (ipynb:685–693) | ✗ | The notebook has no Service Bus code. The BFF says the notification producer is "external to this repo" (service-bus-push-events.ts:24–27). The push concern stands, but its source is unknown, so this is an open item, not a citation. |
| Router launches child workers serially (`concurrency: 1`) | ✗ | The five `run_job_task` children depend only on `Build_Task_List` and run in parallel. `queue: enabled` with the default single concurrent run means whole runs queue. The 60 s debounce is correct. |
| L3 response cache is freemium-only and post-redaction | ✔ | response-cache.ts:18–30, 95–99. ENTITLEMENT_CACHE_DECISIONS: "Premium: Never", "My-picks: Never". Also **no singleflight** (see 2.3 below). |
| Cache keys include the timezone offset | ✔ | response-cache-keys.ts. Note that `/v4/edge-picks` also takes `tz_offset` (edge-picks-v4.ts:80). |
| Legacy BFF filters `cancelled` everywhere | ✔ | All five cited lines confirmed. |
| `pickStatus`/`pickOutcome` derived from `bet_outcome` | ✔ | canonical/picks.ts:426, 478–480 |
| Settled slips resolve from `c-outcome` by id | ✔ | snapshot.ts:303–315 |
| Three My Picks handlers all delegate to `resolve-my-picks-list.ts` | ✗ | `my-picks.ts` (v1) reads a different container (`getMyPickContainer`) with its own resolution. `my-picks-v2.ts` uses the shared resolver only when `api_version` is v3. There are more resolution paths than the feedback says. |
| Format A `top_picks` holds one pick per region | ✔ | match-data-mapper.ts:53–73: a region-keyed object becomes `[pick]` |
| A prior KDD-001 rejected per-pick documents | ✔ | reqs/nba/kdd_schema.md:109–111, Option D "Rejected for now", revisit trigger S3 |
| live-odds: "~55–65 polls over 96 h, ~2% change", so KDD writes are ~10× too high | ✗ | The cadence table (EDGE_PICKS_LIVE_ODDS_DESIGN.md §5) gives about 120–160 polls over 96 h. About 58–66 is the **final 12 h**. No 2% figure was found. KDD-001 assumes 144 observations in 12 h, but picks are watched for up to 96 h, so lifetime observations land in the same range. The KDD estimate is about right, not 10× high. |

---

## 2. Finding-by-finding verdict

| # | Feedback | Verdict | Revised severity | What to do |
| --- | --- | --- | --- | --- |
| 2.1 | Cosmos `id` vs a closed schema | **Valid, overstated.** "Producer CI validates stored documents as they are" is false: stored documents carry `id` and `_rid`, `_etag` and the other system fields. | Medium | Validate the record before write. The Publish Engine sets `id` and the reader strips `_*`. Keep `id` out of the record schema: the contract deliberately does not fix the store. Correct the KDD wording. |
| 2.2 | `sport` indexed but absent | **Valid as an internal contradiction.** Line 29 indexes `sport`, while line 95 says "no extra field is needed". The monitor's per-sport sweep (realtime-overlays.md:49, "deletes any key for its sport that matches no open pick") needs open picks by sport. | High, not blocking | Recommended: add `sport` as a 4.1 minor version, because the container is shared and nothing states that `game_sk` is unique across sports. Otherwise, drop it from the index and document lookup through the schedule's game list. |
| 2.3 | Cache mischaracterised | **Valid.** The existing cache is freemium-only, post-redaction, and has no singleflight: "multiple instances may rebuild". The cost model of one rebuild per key per minute holds only with a lock or singleflight. | Medium | Specify a new pre-redaction pick-record cache in Redis, keyed by `(region, game_sk)` or by slate, not by user day or offset, with singleflight. |
| 2.4 | Publish Engine mechanics | **Partly valid.** The patch path is unfit (10 ops, and it cannot write nulls). Latency is real. "Serial children" and the notebook push citation are wrong. | Medium–High | Require a full-record upsert from one merged Delta row, or a bounded, etag-guarded patch that can set nulls. Measure end-to-end observation latency. Whether legacy documents are rewritten per observation depends on N5c. |
| 2.5 | Supersedes and arithmetic | **Supersedes: valid.** The arithmetic checks out, but the feedback misses that the per-game comparison is biased (N6). Its live-odds nuance is wrong. | Low | Reference reqs/nba KDD-001 and answer its objection (N8). |
| 3.1 | My Picks in the reverse direction | **Real problem, misframed.** The resolver is shared server code that reads legacy documents for **every** build. In Stage A, any slip saved with a v4 id misses the live index and falls back to its snapshot. Wager fields survive (BFF-EC-7), but the result never resolves unless `c-outcome` carries the v4 id. | High | Prefer N2, which removes most of the problem. Otherwise My Picks must use an adapter on day one (N4). |
| 3.2 | `withdrawn` mapped to `scheduled` | **The gap is valid** (KDD-002 is silent), **the reasoning is wrong, the fix is right.** | High | Omit `withdrawn` from legacy documents (preferred, since it was published in error), or map it to `cancelled`. Never pass it through. |
| 3.3 | Settled picks need `bet_outcome` and `c-outcome` | **Valid and important.** `c-outcome` is not among the Stage A documents, so results would come from a second source. That breaks Decision 2, one source of truth. | High | Add `c-outcome` (`result.match[]` and `result.player[]`) to the projection. Map won 1, lost 0, void null, and decide push explicitly. |
| 3.4 | Format A cannot be derived alone; one pick per region | **Valid.** `game_prediction` also holds model predictions, so two inputs write one document and the whole-document replace race returns unless they are joined into one write. | Medium–High | State the join, and the selection rule for more than one open pick (for example highest `entry_edge`, then `pick_id`). |
| 3.5 | Incomplete reader list | **Valid, but the feedback's own list is also wrong** (see 1.3). | Low–Medium | List `my-picks.ts` (separate container), `my-picks-v2.ts`, `my-picks-v3.ts`, `resolve-my-picks-list.ts`, the create routes' peer check (`loadMyPicksPeersByGameIds`), `target-follow.ts` (follows keyed `${prediction_type}:${id}`) and `wp-cron-sync.ts`. |

---

## 3. What the feedback missed

**N1. [Blocking] `pick_id` is not unique enough to be the Cosmos `id`.** Contract rule 1: "pick\_id is unique within a region". KDD-001 sets `id = pick_id` in a `/game_sk` partition that holds both regions. Cosmos enforces `id` uniqueness per logical partition, so an `au` and a `us` record with the same `pick_id` would overwrite each other on upsert, with no error. Today's ids carry a region suffix, but the contract says ids are opaque, and the id format is listed as undecided. The same assumption sits under `overlay_key` and under My Picks' `predictionId` lookup.
*Fix:* change rule 1 to "unique across regions and sports", or define `id = region + "|" + pick_id`. Do this before the KDD-001 write test.

**N2. [High] KDD-002's id bridge is mostly self-inflicted.** The derived legacy documents keep legacy ids, and `legacy_pick_ids` is then added to reconcile them. If the projection writes **`pick_id` as the legacy pick `id`** for games published under v4, both builds save the same id and no bridge is needed. Games published before launch stay legacy and resolve against their own documents (Oct 17 rule C7). The contract's own examples are already legacy-shaped (`40021717862|spread_t1|…|us`, `500000123_DRAW_au`). Under this option, `legacy_pick_ids` is needed only for games that straddle launch, and not at all if C1's per-game pinning is kept.
*Precondition:* confirm that nothing parses legacy ids: follows, the WordPress feed, push, the app.
*Action:* add this to KDD-002 as option E.

**N3. [High] KDD-002 reverses more of the Oct 17 plan than C5.**

- Its Context says the plan "covers producer families, not app versions". In fact C3 covers old builds explicitly ("Old app builds keep exactly the responses they get now", and the "Old app builds | Yes | C3" row). Option C, rejected in KDD-002, is essentially C3.
- Stage A writes both families for every game. That reverses C6 ("Production never holds both families for one game").
- KDD-002 does not say whether C1 (pin each game to one family) or C9 (cache keys by cutover epoch) still hold.

*Action:* list every rule it supersedes, and say what replaces C6's shadow run on production inputs. A fixture replay is weaker evidence.

**N4. [High] My Picks cannot stay "unchanged" in Stage A.** Decision 6 has My Picks resolve by `pick_id` and then by `legacy_pick_ids`, which means reading the new records. Decision 5 says today's routes read legacy documents unchanged in Stage A. The resolver is shared across builds, so My Picks moves to an adapter at launch, which is Stage B for that route on day one. Say so, or adopt N2.

**N5. [High] The list of behaviour changes older builds will see is incomplete.**

- **(a) New cancellations.** Today the engines never cancel (NBA game: "never cancelled"). v4 cancels for `probability_moved`, `market_moved` and `lineup_change`, and the legacy BFF hides cancelled picks. Picks will disappear from older builds for reasons that did not exist before, and their saved slips fall back to snapshots.
- **(b) Cardinality.** v4 can publish several game picks per game. Today NBA has at most one per game, and Format A one per region. Format B arrays will show more picks than old screens have ever rendered.
- **(c) Prices.** Today picks are rebuilt each run, so legacy odds refresh. The projection must decide whether to write entry or current prices. That one choice decides whether legacy documents, and possibly push, are rewritten on every observation, which is feedback 2.4's concern. Recommended: entry prices only, and write legacy documents only when the projected content changes.
- **(d) Region copies.** NBA `au` picks are copies of the `us` picks today, and they may differ under v4.
- **(e) Push.** The mapping for push outcomes is undecided (see 1.2).

**N6. [Medium] The "7× cheaper" claim compares unlike cases.** The per-game column charges a 75 RU rewrite per changed pick. The Publish Engine writes per run, though, so one game document is rewritten once per tick whatever changed in it. At 1,000 records a day (about 50 games, 2 pick documents per game, 30% change per pick, so at least one change in about 97% of ticks), that is about 1.05M RU/day against 0.46M for one document per pick: **about 2×, not 7×**. Option D's real advantages are persistence by construction and no contention, both strong, and absolute costs are tiny either way. Rewrite "Why D" to lead with those.
Also check the autoscale figure: autoscale bills at 1.5× the standard rate, so a 1,000 RU/s maximum is about $88 a month at peak and about $9 at its 100 RU/s floor, not $58.

**N7. [Medium] One writer service is not one writer process.** "No conflict retries, because no two writers share a document" fails when a batch publish and an observation-driven run overlap, or when a queued run writes from a stale read. A status change and an observation can then lose each other's update.
*Fix:* require etag (`If-Match`) on writes, or a single serialised merge in Delta before upsert.
*Also:* the live-odds design rejected writing through the Publish Engine's Delta change-feed path because of latency (60 s debounce plus 1–3 min, EDGE_PICKS_LIVE_ODDS_DESIGN.md:111–114). Contract rule 5 now forces that path, so KDD-001 should reconcile with live-odds D7, and its validation should measure observation-to-record latency.

**N8. [Medium] Answer the prior KDD's objection to Option D.** reqs/nba KDD-001 rejected per-pick documents because they "turn every list/detail read into a fan-out and break the partition-by-game model". The new KDD partitions by `game_sk`, which keeps game locality, and the shared cache absorbs the fan-out. The persistence rule is effectively that KDD's revisit trigger S3. Say this, and mark that KDD as superseded for Edge Picks.

**N9. [Low] Validation gaps.**

- KDD-001 measures RU only. Add:
  - observation-to-record latency of 5 minutes or less;
  - a concurrent status and observation write to the same pick;
  - `au` and `us` records with the same `pick_id`;
  - cache rebuilds across N BFF instances.
- KDD-002: keep C6's shadow run on production inputs for Stage A.

**N10. [Low] Lookup by `legacy_pick_ids`.**

- **Lookup cost.** The indexing policy leaves `legacy_pick_ids` out. That is fine, because slips carry `gameId` (resolve-my-picks-list.ts:95–107): the lookup is partition-scoped and done in memory. State this so nobody later adds a cross-partition `ARRAY_CONTAINS`.
- **Ambiguity.** NFL, MLB, WNBA and EPL legacy ids have no line, so one legacy id can match several v4 records over a game's life, for example a cancelled spread pick and a later pick on another line. Define which record wins: the one open at save time, otherwise the earliest `pick_date_time`.

---

## 4. Recommended edits, in order

1. **Contract (producers-to-bff.md):** make `pick_id` unique across regions and sports, or define the Cosmos `id` composition (N1). Decide `sport` (2.2).
2. **KDD-001:**
   - validate the record before write, with the Publish Engine setting `id` (2.1);
   - make the cache a pre-redaction Redis cache with singleflight, keyed by game rather than user day (2.3);
   - specify the write mechanics: full upsert or etag-guarded patch that can write nulls (2.4, N7);
   - restate the cost rationale (N6);
   - reference and supersede reqs/nba KDD-001 (2.5, N8);
   - extend Validation (N9).
3. **KDD-002:**
   - add option E, projecting `pick_id` as the legacy id (N2);
   - add a projection table covering every v4 status and outcome, including withdrawn, push and void, onto legacy `pick_status`, `bet_outcome` and `c-outcome` (3.2, 3.3);
   - add `c-outcome` to Stage A (3.3);
   - specify the Format A join and selection rule (3.4);
   - decide entry vs current price and write legacy documents only when projected content changes (N5c);
   - identify the push producer (2.4);
   - list every Oct 17 rule superseded (N3);
   - make My Picks' day-one adapter explicit (N4);
   - complete the behaviour-change table (N5) and the reader list (3.5).
4. **Discard from the feedback:**
   - its `sport` enum (`ncaab`);
   - the won/lost/void status mapping as written;
   - the "withdrawn = edge dropped" rationale;
   - the live-odds "10× conservative" claim;
   - the "serial children" and notebook-push citations;
   - every quotation in section 1.1.
