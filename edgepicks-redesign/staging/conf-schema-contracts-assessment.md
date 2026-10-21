# Edge Picks v4 producer pick record — assessment against the redesign and the bet-engine build

**Document under review:** `edgepicks-redesign/staging/conf-schema-contracts.md` — *Edge Picks v4: Producer Pick Record Schema & Contract Specification*, contract `4.0.0`, Draft, 898 lines, signed by nobody yet.

**Requirement under test:** Confluence PB **726237185** *Edge Picks redesign*, **v6** (2026-10-19, adds the *Historical Edge Picks* section), cross-checked against the baseline page PB **769687553** *02. Edge Picks* (v5).

**Review date:** 2026-10-21 · **Method:** read-only. Contract read end-to-end; its JSON Schema executed against all examples, test vectors, `pick_id` rules and probes; requirements page re-fetched at v6 (screenshots inspected); the NBA bet engine inspected at `nba_bet_engine@dev d36b2d1` with live `dev_nba` table data; the Publish Engine (PE), BFF, monitor and KDD/option-B plan read for the consumer seam.

**Revision (2026-10-21, second pass):** independent re-check of the verdicts against the contract and Confluence v6. Corrections folded into §0, §2.1 (positive-edge threshold, edge availability, updated edge), §3.3 (re-issue), §3.4 X7 (AU source truthfulness), §3.5 items 13–16, §6 and Appendix A. No verdict changed direction.

---

## 0. Verdict

**Question 1 — does the schema support the Edge Picks redesign requirements?**
**Partially: it carries the card's data model well, but it cannot support the redesign as written, and two of the gaps are baked into the schema itself, not just missing fields.**

- **Supported at record level:** identity and selection (`pick_kind`, `market`, `side`, `line`, `team_sk`/`player_sk`/`stat_code`), XO probability, projection (optional), stake units, entry decimal + American odds, entry edge on a declared basis with threshold, live current odds/line/observation time/closing flag, `edge_status` (edge-availability state), cancelled with reason codes (`lineup_change` etc.), and persistence/frozen-entry rules. The ordinary card, probability wheel, Edge %, bookmaker (as an id), current odds, movement line, cancelled card, All/Player/Game filter and the entry-based sorts are implementable.
- **Blocked by the schema as written:** (1) **updated Edge after a line move** — `current_edge` is forced to `null` and `edge_status` to `"closed"` whenever `current_line != line`, and no probability-at-new-line field exists, so the `+3% after the move` card in the design cannot be produced; (2) **Recommended Action** — `rec_action` is typed `null` for all of 4.0.x, with no Play/Watch/Pass mapping anywhere.
- **Blocked by contract scope, not shape:** (3) **Historical/pre-redesign picks** — a pre-v4 pick cannot be a conformant 37-field record (required non-null timestamps/edge), and the page has no scope rule for picks that predate the cutover. The right fix is **not** a new record field: the consumer contract's `era` (KDD-003) plus a scope/coexistence section here. The decided option-B delivery plan already carries `era` in its v7 block; the option-A snapshot page on disk does not yet.
- **Conditional on product scope:** (4) EPL *Anytime Goalscorer*, *Asian Handicap* and WNBA player props are outside the 4.0.0 market/stat vocabulary. Whether that is a gap depends on resolving the baseline/redesign contradiction (baseline says EPL publishes no picks) — but WNBA player props do exist in production.
- Everything else that looks missing (bookmaker **display** names, game details/status, UI status labels, day windows, free-user locking, dollar stake amounts) is consumer-side by design and lives (or should live) in the BFF snapshot/v7 contracts — not producer-record defects.

**Question 2 — what must the Bet Engine consider?**
**Not a field rename: a change of record model.** Today's engine emits a **per-run snapshot** (one row per game, nested pick array, **overwritten every trigger**, edge in percentage points, no per-pick status, no observations, no frozen entry). The v4 record is a **persistent, per-pick-per-region object with a lifecycle**. Using the NBA engine as the reference check:

- The engine already holds most **raw inputs** (probability, numeric line, decimal/American odds, bookmaker name, stake units, team/player keys) — conversion work, not model work.
- It does **not** hold the **state**: first-publish values, previous status, re-issue counter, cancellation decisions, settled/void/push outcomes, or observations. Those need a published-pick store and a **single-writer Publish Engine** (KDD-001's new Cosmos container), plus an observation path from the live monitor. Rules 2/3/5/6 of the contract **cannot be satisfied by the engine's output alone**.
- Concrete NBA evidence: `wltp_top_picks_agg` currently holds **17 rows / 17 games / 34 pick slots** (a US pick copied into AU), the audit table shows the **same pick rewritten 10–15 times** with odds moving 1.87→1.95, two different lines and three stakes, and `ps_top_picks_agg` is **empty** because the PS job clears evaluated games; `edge` is **percentage points** (e.g. 9.0434); `pick_date_time` is the **run timestamp**; settlement drops pushes and DNP voids; the engine never cancels a pick.
- Six of the twelve contract decisions in §4.7 are **on the engine's critical path** (writer/store, observation owner, cancellation policy, region/AU semantics, rounding/threshold strictness, projection semantics). Building before they are made means rebuilding.

---

## 1. What was checked, and how far to trust it

| Area | Evidence used |
| --- | --- |
| Contract text and normative schema | Full read of all 898 lines. Extracted the Draft 2020-12 JSON Schema and ran it with `jsonschema` against the five §10 example records; re-computed P-1…P-9 test vectors, decimal↔American conversion, break-even/midpoint rounding, and rebuilt all example `pick_id`s with the §8.4 reference generator; probed the schema with 10 mutated records to find prose rules it does not enforce. |
| Requirements | PB/726237185 re-fetched through the Confluence API (v6, 2026-10-19T04:30:29Z; body converted and diffed against the earlier v5 capture — the substantive addition is the *Historical Edge Picks* block, plus a presentation-only change under "New Design"), including the five embedded design screenshots; baseline PB/769687553 v5 fetched and compared (`EP-13` sort, EPL empty state, WNBA props, projection semantics). |
| Bet engine | `nba_bet_engine@dev d36b2d1` code path, plus live `dev_nba.nba_gold_bets` tables via the read-only `dev` profile (2026-10-21), plus the engine's own 2026 conformance audit/fix-plan notes re-verified at this commit. |
| Publish Engine / consumers | `app-data` deployed `nba_wltp.py`/`nba_ps.py` (tst-blue a1c16f4) and `feat/nba-2026` canonical transforms; `mobile-server@develop fffcc9e`; `live-odds@dev e2c04ca`; KDD-001/002/003, option-B plan, and the sibling snapshot/overlay contracts. |

**Verification I did first-hand:** the schema/example/vector results in §3.1; the engine's live table shapes, row counts, edge values, region mirroring, totals-line defect and audit drift; `fact_game_odds` being US-only; `dim_all_games` having no venue/home column; the selector's DELETE and PS `replace_game_sks` code; the scoring heuristic; PE's id derivation and null-edge drop; the baseline requirements claims; and the KDD/option-B statements quoted below.

---

## 2. Requirements coverage

### 2.1 The redesign (v6) against the 37-field record

| Redesign element (page) | Verdict | Binding evidence / constraint |
| --- | --- | --- |
| New card layout; collapsed/expanded states; sport colours; calendar | **Out of scope (UI)** | Presentation only; data for the slots is mapped below. `sport` enum covers colour routing. |
| Probability visualisation ("74%") | **Supported** | `probability` fraction, frozen. Percent/2-dp formatting is the BFF's. |
| Edge % ("+9% Edge") | **Partial** | `entry_edge` is carried, but on the **producer's** `edge_basis` (`ev` or `prob`), while the app displays one display basis (provisional EV, specs D3). Sorting across sports needs conversion; no rounding rule for edges is stated (see §3.5). |
| Bookmaker name (US); AU "Avg. Odds" | **Partial** | Record carries a lowercase slug (`entry_bookmaker_id`) and `odds_source_kind`; **no display name** and no slug registry owner — BFF/reference-data work. AU "Avg. Odds" is a consumer region rule (snapshot contract already masks AU as `market_average`/"Avg. Odds"). |
| Prediction timestamp | **Partial** | `pick_date_time` is "when the pick was **first published**", frozen; the page asks for "when it was **generated**". Usually the same engine run, not guaranteed; no `generated_at`. |
| **Recommended Action (Play/Watch/Pass)** | **Not supported** | `rec_action` field #34 and schema L496: always `null` in 4.0.x, "reserved". No mapping from `edge_status` is defined; product thresholds open (specs D4, due Nov 2). §2.6 (enum addition = minor) contradicts a `null`-typed field — populating it later is a **major** change unless the schema is fixed now. |
| Live/current odds + line; "ideally real time" | **Partial** | `current_decimal_odds`, `current_american_odds`, `current_line`, `current_odds_source_kind/id`, `observed_at`, `is_closing` all carried; Rule 5 sets a 5-minute delivery rule. Cadence is a producer/roadmap matter. **But the same box shows the "updated Edge", which is nulled on a line move (below).** |
| **Updated Edge after a line move** ("recalculated based on the new line and odds") | **Not supported** | §5.1/§5.3/field #32: `current_edge` must be `null` and `edge_status` `"closed"` whenever `current_line != line`; §10.5 demonstrates it; there is no probability-at-new-line field, so no consumer can derive it either. The page's mock shows exactly the case (entry 23.5 → current 25.5, current odds −125, **"+3% Edge"** and Play); specs D2 says the design needs "the engine's edge at the new line". *Note:* specs D2 quotes the same mock as "+2% Play"; the figure differs between sources (the Confluence markdown export drops images, so it could not be re-checked on the second pass). The blocker does not depend on the number. |
| Positive Edge odds threshold ("stays positive above −125") | **Supported (derivable)**, with a semantic trap | The zero-edge price is `1/probability` on **both** bases (EV: `p·d > 1` ⇔ prob: `p > 1/d`), so any consumer can derive "stays positive above" from `probability` alone — no basis conversion needed. The trap: the contract's `b` (§5.1) is the price at which edge equals the threshold `t`, which equals `1/p` only when `t = 0`. A consumer that labels `b` as "stays positive above" is wrong for every `t > 0` producer. Tied to the entry line, so it cannot follow a move. |
| Cancelled predictions (lineup change) | **Supported** (representation) | `pick_status="cancelled"` + `status_reason="lineup_change"`; persistence rule. Detection policy/thresholds are open (contract §11, due Oct 30; specs D14); `status_reason` may legally be null on a cancelled record (soft "should be set"). |
| All/Player/Game filter; sort Edge/Probability/Odds | **Partial** | `pick_kind`/`sport` filter data supported; sort fields present (`entry_edge`, `probability`, `entry_decimal_odds`); no sort semantics (entry vs current edge, basis, null ordering) in the record — consumer side. Content gaps: EPL Anytime Goalscorer and Asian Handicap (below). |
| Edge availability ("edge no longer available") | **Partial** | Two mismatches with requirement 9 ("compare current odds against the **positive** edge threshold"): (a) `edge_status = "closed"` fires at `current_decimal_odds <= b`, i.e. when edge falls to `t`, not to zero — for a prob-basis `t = 0.03` pick (vector P-5, `p = 0.55`) the card would say "edge gone" at 1.9230 while the edge stays positive down to 1.8182; (b) on a line move it collapses to `closed` regardless of the true edge, conflating "line moved" with "edge gone". Product must pick zero or `t` as the availability boundary; if zero, the BFF must not map `edge_status` straight to the UI. |
| Existing statuses (Upcoming/Live/Final/Correct/Incorrect/Void) | **Partial** | Maps to `pick_status` + `outcome`, but "Live/Final" are game states not carried by the record; no mapping table in this contract (the earlier edition had one — see §3.2). |
| XO Projection | **Partial** | `projection_value`/`projection_unit` exist and are co-nullable; optional, and the contract does not define game-margin sign/format (baseline says game picks show projected margin, e.g. "Team by 5"; player picks show projected stat). Producer/BFF convention needed. |
| Recommended Bet Size | **Supported** | `stake_units` ≥ 0; dollar conversion is app-side (1 unit = Standard Bet, specs D9). |
| **Historical Edge Picks** (v6 section) | **Not supported by this contract's scope; shape needs no change** | Pre-v4 picks cannot be conformant records (all 37 fields required; `pick_date_time`, `entry_edge`, `probability` never null), and no cut-off/vintage field exists. Correct design: the record is *never created* for historical picks; the consumer marks era (`era: legacy|v4`, KDD-003) and serves a limited card. The contract must say this (scope + coexistence); see §2.3. |
| EPL Anytime Goalscorer; Asian Handicap | **Not supported in 4.0.0** | EPL player props are "None in 4.0.0"; no `asian_handicap` market token (closed enum); quarter lines explicitly excluded. Conditional on product resolving the baseline ("EPL publishes no picks"). |
| WNBA player props | **Not supported in 4.0.0** | §7.3 says "None in 4.0.0", but baseline v5 and a WNBA design screenshot include WNBA player props, and a WNBA PS engine exists. Product/scope decision needed. |

### 2.2 What is genuinely absent from the 37 fields

Only four data categories are missing, as opposed to consumer presentation:

1. **Updated edge/probability at the current line** — blocks the redesign's headline "market movement" interaction (BLK-1).
2. **Recommended-action value** — `rec_action` forced null (BLK-2).
3. **A historical/era signal** — deliberately absent from the producer record; must exist on the consumer contract (BLK-3, consumer-side).
4. **Game start time / game state / display names** — only `game_sk`, `team_sk`, `player_sk`, `stat_code` are carried; schedule/reference joins are consumer-side by design (not a defect, but the *owner* of the join for `is_closing`/`awaiting_result` is unassigned — see §3.3).

### 2.3 Historical picks — the precise split

- The Confluence v6 requirement says picks published **before the release** keep the original UI, "don't have the new data points", are **not backfilled or recalculated**, and must show "no blank or placeholder fields".
- KDD-003 (2026-10-20) is the matching consumer decision: every pick carries `era: legacy|v4`; the app picks the card from `era`, "never from which fields happen to be null"; legacy picks are translated by the BFF and get a limited card. The decided option-B plan puts `era` in its v7 `edge_pick` block. **The snapshot contract page on disk (19 Oct) predates KDD-003 and does not yet carry `era`.**
- Therefore: **no new field is needed on the producer record**, but this page is currently wrong in two ways: (a) its opening claim "Every Edge Pick is published as one strongly typed record" is universal and false for historical picks; (b) it never says the record family starts at a league cutover, that historical picks keep legacy documents/ids, that absence of a record means legacy, or that Rule 2's persistence cannot be read as a backfill mandate.
- Two decisions still needed outside this page: the cutover boundary conflicts (product cuts over by **publish date**; KDD-002 by **game start** — recommend "family pinned at first publish", already a KDD-002 prerequisite), and whether a legacy card may show a **recomputed** edge (KDD-003 would derive it on the v4 display basis, while the requirement says no recalculation — KDD-003 flags it as open product wording).

**Requirements verdict.** The record schema is **necessary and mostly sufficient** for the redesigned card, but not sufficient for the redesign as written until: (BLK-1) the moved-line edge is either added to the record or descoped by product (D2); (BLK-2) `rec_action` is enabled with product thresholds (D4) or descoped; (BLK-3) the contract gains the historical scope/coexistence rules and the consumer contract carries `era`; (BLK-4) product resolves EPL/WNBA/Asian-handicap scope. All four are decisions, not foundation-layer rewrites.

---

## 3. Contract quality and internal coherence ("go through this document")

### 3.1 Mechanical validation — the normative content is sound

Executed against the contract as written (`validate_out.txt`): **0 failures, 39 checks passed, 9 prose rules not enforced by the schema.**

| Check | Result |
| --- | --- |
| JSON Schema is valid Draft 2020-12; 37 required = 37 properties; `additionalProperties:false`; 23 frozen fields all present | **Pass** |
| All 5 §10 example records validate | **Pass** (0 errors) |
| All 9 §5.5 vectors (P-1…P-9) recompute exactly (edges to 4 dp, break-even floored, midpoint half-away, decimal↔American) | **Pass** |
| All 10 concrete `pick_id`s in §8.3 match the schema regex; `pick_id` rebuilt from each example's fields equals the written id; corruptions rejected | **Pass** |
| §10 arithmetic/status invariants (edge from written p/odds, American odds, `b`/`m`, `current_edge`, `edge_status`) | **Pass** for all five examples |
| Rules the JSON Schema does **not** enforce: sport↔market matrix (§7.3), positive `team_sk`, `is_closing` vs `pick_status`, settled-with-`is_closing:false`, cancelled-without-reason, basis/edge arithmetic consistency, current-edge-on-moved-line | **Gap** — some are covered by the §9.1 producer-test invariants (arithmetic, id rebuild, frozen, forward-only), some by nothing (see §3.5) |

So the **field-level** contract is unusually well built: the examples and vectors are correct, and the id formula works. The weaknesses are in **semantics that cross records or writers**, and in the contract's scope/ownership statements — not in the record's field types.

### 3.2 The rewrite regressed the seam

`conf-schema-contracts.md` (10:35, 19 Oct) is a newer, self-contained rewrite of `producers-to-bff.md` (09:54, 19 Oct, 610 lines). It is better as a standalone record spec and **worse as the document teams build against**, because it dropped every "how this connects" section:

| Dropped from the earlier edition | Why it matters |
| --- | --- |
| "Bet engines **compute** the values; **the Publish Engine is the only writer** of pick documents" (`:11`) and Rule 5's "Only the Publish Engine writes … the edge monitor's observation reaches them through the Publish Engine, never by a direct write" (`:33`) | This is the single-writer premise of KDD-001 and its etag/merge design. The new §1 lists "bet engines **and** the Publish Engine" as producers and Rule 5 says observations/status/settlement "update the same record" — **three unassigned writers**, and no statement of who owns `current_*`, `observed_at`, `is_closing`, `awaiting_result`, `outcome`. |
| **Store row** (new Cosmos container per KDD-001; `id = pick_id`; partitioned by `game_sk`; page fixes shape/id, not container) | The new page defines no storage at all. With `id = pick_id` in a shared container, the *also-dropped* CI rule "`game_sk` must never be used by two sports" becomes a cross-sport overwrite risk; KDD-001 still lists global key ranges as open. |
| **"Today against this contract"** (per-producer gaps with commit stamps) | The overview promised this page would ship "today's gaps by sport"; Status is now just "Draft Specification". A reader cannot tell that no producer currently emits this. |
| **"Values the BFF accepts until producers write this page's statuses"** crosswalk | The only sanctioned mapping from today's words (`scheduled/active/pending/won/lost/push/void/cancelled/rescheduled/abandoned`, `bet_outcome` 0/1/2, mixed-case Format A) to the v4 enum. **KDD-003's legacy mapping table cites this table by name** — a dangling reference. |
| Per-league "how today's tokens map" guidance; "written today as" stat codes; `h2h` id rule; cross-sport uniqueness CI check; "schema validates the record, the reader strips Cosmos `id`/`_*`" note | Each is a concrete transition/implementation guard. Several are now needed again (see §3.4/§3.5). |

### 3.3 Writer and merge semantics are the biggest implementation defects

- **Writers unassigned.** Contract: engines + PE are producers; BFF/monitor/settlement are consumers — yet Rule 5 makes observations, status transitions and settlement updates to the record, and Rule 3 says later writes may update 14 named fields. No component is named for `current_*`/`observed_at`/`is_closing`/`awaiting_result`/`outcome`. The state diagram says `open → awaiting_result` "(Game starts (`is_closing = true`))" — but no writer/trigger is defined, and a record can be schema-valid in `awaiting_result` with no observation at all.
- **The earlier/KDD model is coherent but not in the contract:** single writer = PE; monitor observations arrive through PE within 5 minutes; `is_closing` derived at game start; settlement writes outcomes. KDD-001's guardrails (PE merges batch output + latest observation into one Delta row, writes the whole record with etag retry, validates before write) are the intended machinery — and they are all "Proposed", in a different file the contract does not reference.
- **Merge/ordering undefined:** precedence of status/settlement over observations; reject observations when `pick_status != open`; monotonic `observed_at`; `is_closing` monotonicity (can a delayed start un-set it?); idempotent re-publish (same `pick_id` must not re-mint `r2` or move `pick_date_time`); what happens when batch output, observation and settlement arrive in one PE run; post-terminal updates (may `current_*` change after settled/void?); retention after terminal (terminal ends Rule 2's *obligation*, not the record's life).
- **Re-issue needs state the contract does not assign:** `n` is a parameter of `build_pick_id(record, team_slot, reissue)` and is not a record field. Checking is fine — a producer test can read `n` back from the id's `|r{n}` suffix, so §9.1 invariant 1 should say so rather than "from the record and schedule". The real gap is **minting**: choosing `n` needs a lookup of prior cancelled/withdrawn records for the same selection/region, i.e. a store. Needs an explicit "1 + highest prior re-issue for the same selection/region" rule and a state owner. Related: a re-run that re-recommends the same still-open selection+line must be the same record (idempotent upsert); the contract only defines re-issue after cancelled/withdrawn.
- **Persistence scope:** "every subsequent publish" presumes a per-game/per-publish document set, but the agreed store is one record per document. Restate as "a later run/store write must never delete or fail to upsert an existing record"; name the explicit cancellation signal (absence from a run must not cancel, or a partial run would cancel live picks).

### 3.4 Cross-contract conflicts a team will hit

| # | Conflict | Evidence |
| --- | --- | --- |
| X1 | **Edge authority is computed in at least three places on two bases.** Record stores `entry_edge`/`current_edge`/`edge_status` on the producer's basis; snapshot recomputes `entry.edge`/`current.edge` and `edge_state` on the EV display basis; overlay recomputes `live_edge`; the v7 plan recomputes and reports `edge_state_mismatch`. "Single source of truth" is not what consumers do. A probability-basis producer's `entry_edge` (e.g. 0.0562) differs from the app's displayed edge (0.1073). | contract §5; `bff-to-app-contract.md:94,100,187-206`; `realtime-overlays.md`; `option-b-plan.md:304` |
| X2 | **`sport` means two different things.** v4 `sport="nba"` = league code; today's canonical documents write `sport="basketball"` under the same field name. | contract §6.1; `app-data .../canonical_transformations.py:20,290` |
| X3 | **Status vocabulary collision.** Canonical PE guards `scheduled, active, pending, won, lost, push, void, cancelled, rescheduled, abandoned` under the same `pick_status` name; v4 uses `open, awaiting_result, cancelled, settled, void, withdrawn`. No crosswalk in this contract (dropped). | `canonical_transformations.py:42-46`; KDD-003 cites the removed table |
| X4 | **Identity compatibility claim overstated.** §8.2's note says the id preserves existing pick identifiers; the v7 plan measured **336 of 1,070** dev NBA ids failing the v4 pattern (300 `player_milestone`, 36 `alternate`), and all Format A ids fail. Old ids are never rewritten; the claim must be scoped, and the `h2h` moneyline-detection rule (older app builds look for `h2h` in the id) restored. | contract §8.2/§8.3; `option-b-plan.md:246`; KDD-002 point 8 |
| X5 | **No game start time/state.** Snapshot `game.starts_at` is the open/closed cutoff, overlay stops at kickoff, settlement grades after the game, and `is_closing`/`awaiting_result` derive from the start. The record has only `pick_date_time`. The schedule join is mandatory and its owner is unstated. | contract fields; `bff-to-app-contract.md:117` |
| X6 | **Taxonomy versioning dropped.** Canonical pick rows carry `taxonomy_version`; v4 has only `schema_version` and folds market/stat enums into the schema. Either keep a vocabulary version or state that a new market/stat is a 4.x *schema* bump that changes the closed enum. | `canonical_transformations.py:793`; contract §2.6 |
| X7 | **Consumer seams with no owner:** bookmaker slug → display name (only examples); `stat_code` → label registry (BFF's is NBA-only: `pts,reb,ast,stl,blk,threes,pra,pr,pa`); AU source rule (is an AU record a real book, a US mirror, or a market average? the current engine mirrors a US book but the snapshot masks AU as `market_average`/"Avg. Odds"); identity source of `team_sk`/`player_sk`. **AU truthfulness:** the record can already state an honest AU source (`odds_source_kind = "market_average"`), but option-B plan L173/L294 labels every AU pick `{market_average, "Avg. Odds"}` regardless of the record — with today's engine cloning a US book into AU, the card would call a FanDuel price an average. The AU decision is a producer one (what price, and therefore what `entry_edge`/`b`, an AU record carries), not only display masking. | `mobile-server/src/lib/constants.ts:56-66`; `bff-to-app-contract.md:185`; `option-b-plan.md:173,294` |
| X8 | **Historical cutover rule conflict:** product (publish date) vs KDD-002 (game start). Plus KDD-003 would recompute a legacy edge while the requirement says "no recalculation". | Confluence v6 Historical block; `kdds.md:181,394,428-431` |

### 3.5 Smaller normative defects (worth fixing before sign-off)

1. **`rec_action` type contradiction:** §2.6 says a new enum value is a minor bump, but the schema types the field `null`, so adding play/watch/pass is a **major** change. Fix the schema to an enum including `null` now (nothing can emit values yet), then populate under D4.
2. **`awaiting_result` vs closing:** the diagram/§4.2 imply a closing observation, but a record can be valid in `awaiting_result` with no observation (`observed_at: null` ⇒ `is_closing:false`). State the fallback.
3. **`is_closing` can be `true` while `pick_status="open"`**, and is mutable, so a delayed start could flip it back. Add the pairing rule / monotonicity.
4. **Rounding not stated for edges or probability.** Odds are ≤4 dp; edges are shown to 4 dp in every example/vector, but the text only says "unitless fraction". Since §7.2.6 requires `entry_edge` to be recomputed "as written" and §9.1 invariant 3 requires exact arithmetic consistency, pin the rounding (4 dp, half away from zero, recomputed from written p and odds).
5. **Threshold strictness:** engine filters are `>= threshold` (e.g. tiered 8.0 pp) while the contract requires `entry_edge > edge_threshold`. Either the filter becomes `>` or the producer writes a threshold just below the filter. NBA's tiered threshold is 8 pp; PS is 3 pp.
6. **`status_reason` is soft:** cancelled "should be set", but schema allows null and no invariant requires it — while the redesign shows the cancel reason on the card.
7. **Push/void are not representable in the current pipeline and the probability semantics on whole-number lines are ambiguous:** totals probabilities exclude pushes (`P(over)+P(under)<1` on integer lines); spreads use an unconditional normal. The contract should say what `probability` means when a push exists and what `b`/`m` mean.
8. **Sport↔market↔stat matrix not enforced** by schema or invariant (any `[a-z0-9_]` stat code validates; an `nba`+`draw` record passes); §7.3 is provisional. Producer CI needs the vocabulary check.
9. **`team_sk` sign/positivity and side↔slot↔id consistency unenforced** (a record with `side:"home"` but a team_sk in the t2 slot passes; §9.1 invariant 1 would rebuild a different id only if the producer test does the slot lookup).
10. **Periods/quarters:** moved from "not yet decided" to a firm "full game only" rule, without saying that adding periods later is a **major** change and a new id segment (previous edition was more honest).
11. **Alternative-line collapse:** `variant` is dropped from v4 (0.0.0 writes literal `main`/`full`); today's engine hardcodes `variant="main"` anyway, but existing alternate ids (36/1,070) are legacy-only.
12. **Editorial:** the requirements page numbers two items "5." (Current Odds, Recommended Action) — the contract should refer to them unambiguously when validating scope; §4.3's `market_moved` vs "a line move never cancels" distinction is under-specified.

### 3.6 Recommended edits, in priority order

**Before sign-off (blocking):**
1. Restore §1 "Storage, writer and coexistence": single writer = PE; engines/monitor/settlement are value sources; one record per document in the KDD-001 container, `id = pick_id`, pk `game_sk`; cross-sport `game_sk` uniqueness is a hard prerequisite; Cosmos `id`/`_*` stripped before validation.
2. Restore Rule 5's writer statement and add a **field-group ownership matrix** (source → writer): entry fields (engine → PE), observations (`current_*`, `observed_at`, `is_closing`: monitor → PE), lifecycle transitions and settlement (`outcome`: settlement path → PE), `game_sk` schedule join for `is_closing`/`awaiting_result`.
3. Add merge/ordering semantics: terminal precedence, reject observations after terminal/`!= open`, monotonic `observed_at`, `is_closing` monotonicity, idempotent re-publish, explicit cancellation signal (absence from a run is not one), post-terminal `current_*` frozen, retention forever (no TTL).
4. Restate Rule 2 for the one-record-per-document store and add the historical scope rules: family pinned at first publish/league cutover; no backfill, conversion, placeholder or recalculation; legacy ids/documents untouched; `era` is a consumer field, never inferred from nulls.
5. Fix `rec_action` to an enum (`play|watch|pass|null`) and either define the mapping/thresholds (D4) or mark it explicitly deferred with a date.
6. Restore the status/outcome crosswalk and fix the KDD-003 dangling reference.
7. Decide the derived-edge authority (stored vs recomputed) and, if recompute stays, state the display-basis conversion explicitly.
8. Resolve re-issue: rule (`1 + max prior n`), state owner, and how it satisfies §9.1 invariant 1.
9. Scope the id backward-compatibility claim; restore `h2h`-only-for-moneyline and "old ids are never rewritten"; restore the cross-sport uniqueness CI check.
10. Name the owner/registry for bookmaker slug→name, stat_code→label, AU source semantics; state that `sport` is the league code and `team_sk`/`player_sk` are the canonical schedule/player keys.

**High:** restore a "Today against this contract" section or link; restore per-league token mappings; add missing invariants to §9.1 (output+store uniqueness, side↔slot, `pick_status`↔`is_closing`, stat vocabulary membership, re-issue rebuild); state what `pick_date_time` means (engine recommendation vs PE write) and how it survives the PE merge; decide taxonomy versioning; cross-reference the decided option-B/v7 consumer seam and KDD-001/002/003.

---

## 4. What the Bet Engine needs to consider — NBA reference check

### 4.1 Division of labour, and why it changes the engine's job in kind

The contract (and the earlier edition) intends: **bet engines compute values; the Publish Engine writes the record**. KDD-001 makes that concrete: PE merges each pick's batch output and latest monitor observation into one Delta row, validates the record against this JSON Schema, and upserts the whole document with an etag guard. That means a bet engine's compliant output is **one row per pick per region** (a record), not one row per game with a nested array, and it must be produced in a way that supports **insert-once frozen fields**, **status transitions**, and **observations supplied by someone else**.

Two consequences the engine team must internalise:

1. **The record is not "the engine's latest output" anymore.** It is summed across runs (persistence) and across sources (entry + observations + settlement). That requires state outside the engine's current stateless recompute.
2. **The engine cannot satisfy Rules 4–5 on its own.** It stops writing a game 5 minutes before tip and never re-observes a published pick; therefore `observed_at`/`is_closing`/`current_*` must come from a monitor through PE. The engine's job is to expose the frozen entry facts the monitor needs: `pick_id`, `probability`, entry price/line, `edge_basis`, `edge_threshold`, `region`.

### 4.2 What the NBA engine produces today (reference baseline)

Verified at `nba_bet_engine@dev d36b2d1` and in `dev_nba.nba_gold_bets` on 2026-10-21:

| Aspect | Current NBA reality | v4 requirement |
| --- | --- | --- |
| Output object | `wltp_top_picks_agg`: one row per game; `edge_picks` = `array<struct<16 fields>>` with a separate AU copy and US copy; `ps_top_picks_agg`: nested region→team→picks→items tree (0 rows today; PS disabled) | One record per pick per region, 37 flat fields |
| Run semantics | Rebuilt every trigger; selector **DELETE**s stale future-game rows, aggregation replaces the whole array; PS `replace_game_sks` deletes picks of evaluated games | Persist; never delete; transition to cancelled instead |
| Identity | `bet_id = {game_sk}_{bet_type}` (no region, no line, and `bet_type` contains illegal `<`/`>`); PE builds a v4-shaped id for game picks from row fields but rebuilds it each run | Producer mints the deterministic, region-scoped, line-aware `pick_id`; stable across price movement |
| Entry state | Recomputed every run: probability, 2-dp decimal odds, American odds as `double`, stake, line, `pick_date_time` = run timestamp | Frozen at first publish; 4-dp odds; integer American; edge recomputed from written values |
| Edge | `(our_prob − 1/decimal_odds) × 100` — **percentage points**, probability basis; no basis/threshold persisted | Fraction; `edge_basis` and `edge_threshold` per pick |
| Status/outcome | Header `status` = **game** status; settlement writes `bet_bookie_outcome` 1/0 and drops NULL pushes; PS derives `scheduled|won|lost|void|cancelled` at aggregation; no `awaiting_result`, no `withdrawn`, no `status_reason`, no cancellation | Full forward-only lifecycle with reasons |
| Observations | None. `market_last_update` is the entry quote's feed time, not an observation of a published pick | `current_*`, `observed_at`, `is_closing`, `edge_status` |
| Region | US odds only in silver (`fact_game_odds`: 2,794 rows, all `us`); aggregation clones the US pick into AU and upper-cases the region, keeping the US bookmaker | Separate region records with honest `odds_source_kind`/bookmaker; product says AU shows "Avg. Odds" |
| Projection | Game total/spread predictions exist at table level; PS expected stat is used for pricing but **not output** | `projection_value`/`projection_unit` per pick |
| Other gaps | No venue/home column in `dim_all_games` (side home/away must be resolved or a convention agreed); totals `bet_bookie_line` is a constant string (`bookie_total_line_under`) with the numeric line only in `position`/`code`; `variant` hardcoded `main`; one pick per game by strategy | Explicit `side`/`line`; `main`/`full` literals acceptable; multi-pick handled by persistence |

### 4.3 The 37 fields, by type of work

- **Present and semantically compatible (small conversion):** `game_sk`, `probability`, `player_sk` (PS), `stake_units` (already units after `stake_dollars / STAKE_DIVISOR`), `rec_action` (literal null).
- **Present but needs conversion (unit/type/enum/identity):** `region` (lowercase; real region records), `sport` ("basketball" → "nba"), `pick_kind` (implicit), `market`/`side`/`line`/`team_sk` (derivable from `bet_type`/`bet_code`/`bet_bookie_position`/`outcome_point`; totals have a line bug to fix), `stat_code` (`points→pts`, `rebounds→reb`, `assists→ast`, `threes→threes`), `entry_decimal_odds` (2→4 dp), `entry_american_odds` (double→integer computed from written decimal), `entry_edge` (pp→fraction recomputed from written p and odds), `pick_date_time` (run timestamp→first-publish ISO-8601 ms Z), `outcome` (1/0/NULL→won/lost/push/void with pushes persisted), `edge_basis`/`edge_threshold` (derive per active strategy: tiered=prob/8 pp, PS=prob/3 pp, EV strategy=ev bounds).
- **Missing — no source in today's engine output:** `schema_version`, `entry_edge`'s frozen first-publish semantics (needs a store), `projection_value`/`projection_unit` (carry at pick level; PS add one column), `odds_source_kind`, `entry_bookmaker_id` (slug map needed), the nine observation fields, `pick_status`, `status_reason`, `outcome` in v4 terms (see above).

### 4.4 Rules 1–6: what the engine can and cannot fix alone

| Rule | Engine work | Needs from elsewhere |
| --- | --- | --- |
| **1 identity** | Mint the v4 id (market token, selection, team slot, line token, lower-case region); resolve team slot and venue side; stop leaking `bet_type` tokens | Contract: id ownership/venue source; store: re-issue counter |
| **2 persistence** | Stop deleting/purging; emit terminal records instead of omissions; stop the PS switch clearing picks; per-pick output | **Store** (where a terminal record lives) + contract cancellation policy + PE whole-record upsert |
| **3 frozen entry** | Write-once path for 23 fields; `pick_date_time` once; allow-listed updates only; never re-derive on re-runs | **Store**/PE first-write-wins; contract definition of "first publish" |
| **4 observation timestamp** | Expose frozen entry facts for the observer; never fabricate `observed_at` | Monitor → PE observation path |
| **5 one record + closing** | Keep one logical record per `pick_id`; perform/trigger `open→awaiting_result` at game start (schedule join) | **Store**, PE writer, monitor; contract assignment |
| **6 forward-only lifecycle** | State machine; cancellation/withdrawn emission; re-issue counter; settlement grading on frozen entry line/side; push/void/DNP persistence | **Store** (previous status), contract status policy, settlement owner |

### 4.5 Domain modelling the engine must get right (beyond fields)

1. **Edge unit/basis/threshold/rounding.** Do not divide the stored 4-dp percentage by 100: emit 4-dp odds and **recompute** edge from written p and written odds (contract §5.1/§7.2.6). Persist the basis and threshold actually used by the active strategy, and reconcile `>=` filters with the contract's strict `>`.
2. **Projections.** Totals → projected total, spreads → projected margin, props → expected stat, moneyline → null. Define units (`points`, `rebounds`, `assists`, `three-pointers`); the current PS output drops `expected`.
3. **Bookmaker and region.** `fact_game_odds` has no AU books; today AU is a clone of a US book. Product/contract must decide AU = mirror, market average, or a new feed; the record cannot honestly say `bookmaker` + an AU region while pointing at a US book. A canonical slug map is needed either way.
4. **Status/outcome.** Push and void are currently invisible (NULL filtered out); PS DNP is indistinguishable from push; the plus-line spread heuristic in `_scoring.py` is not spread settlement; game-cancelled maps to `cancelled` in PS aggregation but should be `void`/`game_void` in v4. Grading must use frozen entry line/side.
5. **Cancellation.** The engine never cancels today and has no lineup/injury input; `lineup_change` needs a feed and a rule; "one pick per game" plus persistence means a replacement must cancel the old record and mint a new one (not overwrite).
6. **Cutoff vs closing.** The pre-game cutoff (5 minutes in dev/tst) means the engine's last write is before the last pre-tip price; `is_closing` therefore belongs to the monitor/PE path, not the engine.
7. **Alternates/periods.** `variant` is main-only today; alternate lines are collapsed before selection, and v4 freezes `main`/`full`. Existing milestone/alternate ids must stay legacy-only.
8. **Cross-sport uniqueness.** `id = pick_id` in a shared container makes `game_sk` uniqueness across sports a hard prerequisite (data-engineering commitment or CI check).

### 4.6 Prioritised engine work list

**Blocking — complete before any compliant record can be emitted:**
- **E1. Contract decisions** (writer/store, observation owner, cancellation policy, AU semantics, rounding/threshold, projection semantics). Nothing below should be built before these are fixed.
- **E2. Emit the 37-field record object per pick per region** (likely a new Delta table + new `_schemas.py` structs; explode pick × region; replace the nested-array output).
- **E3. Identity and selection fields**: `pick_id`, `market`, `side`, `line`, `team_sk`/`player_sk`, `stat_code`, team-slot/venue resolution, line token; stop leaking `bet_type`.
- **E4. Edge conversion and disclosure**: 4-dp odds, integer American, fraction edge recomputed from written values, `edge_basis`/`edge_threshold` per pick.
- **E5. Persistence and freeze**: insert-once frozen fields, allow-listed updates, no purges/deletes/PS clears, terminal records retained; previous-state lookup.
- **E6. Lifecycle state machine**: `open → awaiting_result → settled|void`; pre-game `cancelled`/`withdrawn` with reasons; forward-only guard; re-issue `|r2…`.
- **E7. Settlement correctness**: push persisted, void/DNP/game-void, grade on frozen entry line/side, fix the plus-line heuristic and NULL filter. (Can start independently — it is a scoring fix on today's tables.)
- **E8. Carry projections** (game total/margin at pick level; PS expected stat).
- **E9. Bookmaker/region export**: slug + source kind; honest AU semantics.
- **E10. Producer CI gate**: validate every emitted record against this JSON Schema and the §9.1 invariants in CI (the repo currently only runs `databricks bundle validate`).

**Later:** observation-path integration on the engine side (leave fields null, never touch them); alternate-lines policy; multi-pick-per-game policy; retire legacy columns after PE/BFF migration; backfill/replay tooling from the audit table; verify season parameterisation has no remaining magic dates.

### 4.7 Decisions the contract must make before engine work starts

1. **Producer/writer/store model** — engines supply, PE writes, record store owns first-publish state and terminal records.
2. **Observation owner and transport** — who computes `current_*`/`current_edge`/`edge_status`, who sets `observed_at`/`is_closing`, and which feed carries them into PE.
3. **Frozen-field enforcement point** and the exact definition of "first publish".
4. **Re-issue semantics** — counter rule, owner, and whether a cancelled pick may reopen (contract §11 open item).
5. **Cancellation policy and reason mapping** — which re-evaluations cancel, per sport; lineup-change feed ownership (contract §11, due Oct 30).
6. **Region/odds-source semantics** — what an AU record means when prices are US-sourced.
7. **Rounding/precision rules** — edge 4 dp, threshold strictness, whole-number-line push semantics, probability precision.
8. **Projection semantics/units** per market and stat.
9. **Status/outcome details** — DNP void reason (`status_reason` enum has no DNP code), game-cancelled mapping, who emits `awaiting_result`/settled.
10. **Settlement grading rule** — entry line/side, plus-line spread definition, whole-number totals push, postponed games.
11. **`sport` semantics and cross-sport `game_sk` uniqueness**.
12. **Where dropped metadata lives** — `taxonomy_version`, entry feed timestamp, run id/hash, `variant` (the closed record cannot carry them).

### 4.8 Cross-sport note

NBA is the most advanced implementation and still needs everything above. The earlier "Today against this contract" survey shows the other engines are further behind: NFL/MLB/WNBA/EPL game picks carry no structured line/edge at all (edge not published, line/odds inside strings), status vocabularies are mixed-case and game-level, and NFL cancellation is reversible (`Scheduled ↔ cancelled`), which conflicts with v4's forward-only rule. The contract is a cross-sport target; the NBA work is the template, not the whole programme.

---

## 5. Direct answers

1. **Does the schema support the Edge Picks redesign requirements?**
   **Mostly at the data level, not yet overall.** All card fields except the two explicit conflicts (updated edge after a line move; Recommended Action) and the consumer-side seam (historical `era`) are present or derivable. Of the remaining gaps, three are contract/decision fixes (BLK-1, BLK-2, BLK-3) and one is product scope (EPL/WNBA/AH vocabulary). The schema itself is mechanically sound — no example, vector or id failure — but its "all 37 fields, closed shape" premise must be scoped to v4-era picks so it cannot be read as a backfill mandate.
2. **What does the Bet Engine need to consider?**
   **State, ownership and lifecycle, not fields.** The NBA reference check shows an engine that rebuilds and overwrites game snapshots, tracks no per-pick status or first-publish state, never observes a published pick and never cancels one. To emit this record it needs a per-pick-per-region output with deterministic identity; a published-pick store with insert-once frozen fields, terminal records and re-issue state; a lifecycle state machine fed by a game-start clock and settlement; conversions for edge unit/basis/threshold, projections, bookmaker slugs and region semantics; and a PE single-writer/observation path that does not exist yet. The model and selection logic are mostly reusable; the record pipeline is new.
3. **What should happen next (recommended order)?**
   (a) Fix the contract before publishing: restore writer/store/coexistence scope, add merge semantics, enable `rec_action`, scope historical picks, fix the internal contradictions (§3.6). (b) Take the five open decisions — D2 (moved-line edge), D3 (display basis), D4 (action), D14 (cancellation policy), and the store/writer decision (KDD-001) — because each changes engine work. (c) Start NBA engine work only on the independent pieces: settlement correctness (push/void/grading) and the producer-record output/identity, behind a contract test gate. (d) Update the consumer contract adopted for delivery (option-B v7 block) with `era` and the historical rules; update the option-A snapshot page later per KDD-003.

---

## 6. Limits and uncertainty

- **Draft status:** the contract is 4.0.0 Draft with every sign-off pending and five open decisions (targets Oct 21/Oct 30), so verdicts are against the text as of 2026-10-21.
- **Design mocks are non-normative and partly stale** (e.g. "Polymarket", "Picked at", old layout); the prose is authoritative. The one load-bearing design fact — a positive recomputed edge after a line move — is corroborated by three screenshots and by specs D2.
- **PS shape is code-only:** both PS tables are empty because the job is paused and clears evaluated games; shape claims are from `_schemas.py`/`_ps_engine.py`, not live data.
- **Deploy state of PE/monitor paths:** `app-data` local checkout is `tst-blue`; canonical Format-B transforms were read from `feat/nba-2026` via `git show`; the v7 BFF implementation is not committed in `mobile-server@develop` (plan says P1/P2 uncommitted). The read-only Databricks SP cannot see ML job state, so prod/tst deploy revisions are assumed from docs.
- **`team_1 = home` convention** is unverified (no venue column in `dim_all_games`); the engine and PE assume it today. Resolve before minting v4 ids/`side`.
- **Cross-sport `game_sk` uniqueness** was not measured; it is a hard prerequisite for `id = pick_id`, not a detail.

---

## Appendix A — mechanical validation, exact result

`python validate_contract.py` (jsonschema 4.26.0, Draft 2020-12) → **0 FAIL, 9 GAP, 39 PASS**. The 9 GAPs are prose rules the schema does not enforce: sport↔market mismatch, negative/zero `team_sk`, `current_edge` non-null on a moved line, wrong `current_edge` arithmetic, `is_closing:true` with `pick_status:"open"`, settled with `is_closing:false`, cancelled with null reason, `edge_basis` inconsistent with `entry_edge`, and a `pick_id` whose token and selection disagree. Several of these are covered by the §9.1 producer-test invariants (arithmetic, id rebuild, frozen, forward-only); the sport/market vocabulary, `team_sk` positivity, `pick_status`↔`is_closing` pairing, cancel-reason presence and cancelled-token/id consistency are not covered anywhere and should be added to §9.1 and producer CI.

## Appendix B — evidence index (selected)

- Contract: `conf-schema-contracts.md` — scope §1 (L3, L13–16); conventions §2 (L28–38); Rules §3 (L42–64); lifecycle §4 (L68–116); edge §5 (L120–176); fields §6 (L179–243); markets §7 (L247–309); id §8 (L313–402); schema §9 (L406–646); examples §10 (L650–877); open decisions/sign-off §11 (L881–897).
- Earlier edition: `producers-to-bff.md` — writer L11, Rule 5 L33, store L14, today L562–576, crosswalk L578–590, not-yet-decided L592–604.
- Consumer/decision corpus: `kdds.md` KDD-001 L15–163 (guardrails L33–35), KDD-002 L165–332, KDD-003 L333–440 (`era` L348); `bff-to-app-contract.md` fields L78–170, edge state/formulas L187–206, AU rule L185; `realtime-overlays.md` L59–64; `option-b-plan.md` L5 (option B decision), L156–212 (v7 block incl. `era`), L626–640 (P4); `delivery-options.md`; `overview.md`.
- NBA engine, `dev d36b2d1`: `_schemas.py` (output structs L53–90, L136–153, L199–296); `_wltp_engine.py:131–202, 289–296, 405–421, 470–560`; `_probability.py:82–116, 147–180`; `_strategy_tiered.py:24–93`; `_config.py:16–99`; `wltp_pick_selector.py:205–300`; `_wltp_aggregation.py:39–60, 121–141`; `ps_engine.py:110–124`; `_ps_engine.py:250–366`; `_ps_aggregation.py:19–33`; `_update_outcomes.py:29–81`; `_scoring.py:12–55`; `_ps_update_outcomes.py:24–96`; `_common.py:194–230`; `_live_odds.py:27–32`; `resources/jobs.yml`; `conf/dev.yml`; `AGENTS.md`.
- PE: `app-data@tst-blue a1c16f4` `databricks/publisher/nba/nba_wltp.py:84–88, 200–300, 340–373`, `nba_ps.py:396–430`; `feat/nba-2026@54214ec` `databricks/publisher/canonical_transformations.py:20, 42–46, 199–223, 737–900`.
- Live data (`dev` profile, 2026-10-21): `dev_nba.nba_gold_bets.wltp_top_picks_agg` (DESCRIBE + exploded samples: 17 rows/17 games, AU/US slots, edge 9.0434 pp, totals line constant, status `scheduled` on final games); `ps_top_picks(_agg)` row counts 0; `wltp_top_picks_adj_audit` (358 rows; same pick 10–15 runs, odds 1.87→1.95, two lines, three stakes); `nba_silver.fact_game_odds` (2,794 rows, `bookmakers_region='us'` only); `nba_silver.dim_all_games` (no venue/home column; status values `scheduled/in_progress/final`).
- Requirements: Confluence PB/726237185 v6 (2026-10-19; Historical block at end); PB/769687553 v5 (EP-13 sort L113–115; EPL empty state L215; WNBA player props L200–206); `specs.md` (AC-1…AC-45 at L507–613; decisions D1–D14 at L669–686).
