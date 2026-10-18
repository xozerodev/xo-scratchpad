# Edge Picks redesign — independent assessment

**Subject:** `edgepicks-redesign/` — `specs.md` (654 lines), `canonical-data-model.md` (746), `canonical-data-verification-plan.md` (171), `coexistence-cutover-plan.md` (120). All four dated 16–17 Oct 2026, author @Tze Liang.
**Assessment date:** 19 Oct 2026.
**Method:** four independent verification streams against the deploying branches of the real estate, plus a red-team pass over the documents' own arithmetic and internal logic. ~180 commit-pinned verdicts. Evidence files (paths relative to the scratchpad root, `xo-scratchpad/`): `.verify/assessment/specs-findings.md`, `model-findings.md`, `plans-findings.md`, `redteam-findings.md`, `azure-tst-check.md`.

---

## 1. Verdict

**The thinking is good. The evidence base is not, and the folder is not one plan.**

Three of these four documents are unusually disciplined for design proposals: they carry worked examples that recompute exactly, "verified against" columns, explicit "not yet checked" lists, and a review-response table that concedes nine previous findings. That is rare and it should be said first.

It does not survive contact with the estate. Of 82 discrete claims in `specs.md` checked against the deploying refs, **17 are refuted and 27 only partly hold**. The failures cluster precisely where the schedule is: the two rows with hard dates rest on an unmerged feature branch and on a misreading of which branch deploys. The canonical model treats a settlement write-back that does not exist as today's mechanism and books its cost at zero. And the folder contains **two mutually incompatible migration mechanisms** — the canonical model dual-publishes into shared containers, the cutover plan forbids exactly that — on top of **three different timelines** for the same cutover, and a frozen id contract that both of the others say must change.

| Document | Verdict | One line |
| --- | --- | --- |
| `specs.md` | **Revise, do not reject** | The best-specified contract in the folder; the least reliable account of the systems it describes. |
| `canonical-data-model.md` | **Approve the direction, defer the build** | Genuine model improvements; 20 substantive divergences from `specs.md` and a large build booked at zero cost. |
| `canonical-data-verification-plan.md` | **Cut to a v1 or fund it as a programme** | Right rule decomposition, right test strategy, no owners, no dates, foundation lands after 1A. |
| `coexistence-cutover-plan.md` | **Adopt as the migration design, then write the runbook** | The most accurate evidence table in the folder and the least complete plan. |

**Do not approve any of the four as a build instruction.** Approve the *direction*, then close the six contract conflicts in §5.2 before a line of producer code is written.

---

## 2. What holds up

This section is not padding. These are the parts that should survive the rewrite.

1. **The arithmetic is correct — all of it.** Every worked example in `specs.md` recomputes exactly in decimal arithmetic: E1–E11 (including the boundary cases E6/E8/E10/E11), D-1–D-10, AC-12, AC-21, AC-24, AC-28 (35 cells), AC-29, AC-30, the `b`/`m` definitions and the `d ≤ b ⇔ p·d−1 ≤ t` biconditional (0 counterexamples over a 4 dp grid). The canonical model's pricing example, its push-aware EV examples (over 2.0 goals at 1.80 → `ev` 0.096, `edge_prob` 0.071111, break-even 1.595745), the NFL −3 case (0.044545 vs naive −0.045455) and the R2 break-even table all reproduce exactly. Independently recomputed by the Lead and by the red-team stream.
2. **The precision discipline in `specs.md` §5.3/§6.1 is the best thing in the folder.** Rounding `b` *down* so a published break-even price never carries an edge above `t`, comparing at 4 dp, and stating the boundary cases as test vectors is exactly how to make two implementations agree. The 4 dp/6 dp boundary is a real seam with the canonical model (see the coverage holes in §7.1) but the rule itself is right.
3. **The mirror-leak rule (`specs.md` §6.2) is correct and self-consistent.** Across all 64 flag combinations exactly one of {probability, odds, edge} is visible in 48 configurations and zero or three in the rest — never two. A hidden value is never recoverable from the two shown. AC-21 and AC-37 agree with the written rule in every configuration.
4. **The canonical model's core separations are right.** *Selection vs pick* genuinely fixes the "a line move deletes the pick" failure that the v4 card cannot live with; *projection vs probability vs pick* and *XO's grade vs the user's position* are the correct boundaries. Push-aware EV from a five-way outcome split is not a nicety: on whole-number lines `p × d − 1` is simply wrong (−0.154 where the truth is +0.096), and the model is the only document in the folder that says so.
5. **The R2 insight is important and correct.** `specs.md`'s `(1+t)/p` is the right break-even only when the engine selects on EV. For an engine selecting on probability edge (NBA does — `edge = bet_probability − implied_prob`, `nba_bet_engine@621ab3c1` `_ps_engine.py:224-225`), the break-even is `1/(p−t)`: at t = 0.03 that is 1.9230 rounded down (1.9231 is the first price above it), not 1.8727. The model's table is right and the difference is a wrong number on a user-visible card.
6. **The cutover plan's read-path diagnosis is accurate and evidenced.** Seven of its file:line citations were checked at `mobile-server@origin/develop 95733012` and all are substantively correct (two are off by one line): the unfiltered `SELECT *` schedule query (`matches-top-predictions-v3.ts:135`), `choosePredictionDoc` returning null for a v3-only game (`canonical/docs.ts:62`), `choosePlayerDocs` ignoring `player_projections` (`:104-118`), the `xoProbability: 1, marketOdds: 0` placeholder fallback (`resolve-my-picks-list.ts:289-290`), the key-name-only stripper (`strip-helpers.ts:19,21,26`), the cache key with no family epoch (`response-cache-keys.ts:43`), and the app's follow key (`TopPicksScreen/_components/TopPicksList.tsx:95`; the plan cites `:94`). This is the most trustworthy table in the folder.
7. **The validation plan's rule decomposition and test strategy are the right answer to a real problem.** One rule definition, three runtimes, one shared vector set, generated rather than hand-written, is exactly how to stop the drift that produced the 6 dp identity failure. The rule-language survey reaches the correct conclusion (code + vectors for numeric/identity rules; JSON Schema for shape; generated lookups for taxonomy; CEL only later; CUE authoring-only), and three of its four external citations are accurate.
8. **All four documents are honest about their own gaps** — the availability key, the "Required, not built" marks, the "Not yet checked, because no implementation exists" list, the risk that Gate 1 stays optional. That honesty is why this assessment could be done in a day.

---

## 3. How this was verified

| Stream | Scope | Evidence base | Result |
| --- | --- | --- | --- |
| `specs.md` | §3 availability matrix (24 cells), §4 contract, §5 status mapping, §7 overlays, §8 producer contract, X1–X14 | `mobile-server` `origin/develop@95733012`, `app-data` `origin/tst-blue@a1c16f43` and `feat/nba-2026@54214ec3`, `live-odds` `origin/dev@e2c04ca1`, `live-scores` `origin/main@62b1b2b6`/`dev@8757f3f1`/`tst@d94828e5`, `mobile-app` `origin/develop@352bde30`, `nba_bet_engine` `dev@621ab3c1` | 30 confirmed / 27 partly / **17 refuted** / 8 unverifiable |
| `canonical-data-model.md` | 52 "today/exists" observations, identity, migration, numerics | same refs + Confluence 717914114, 717029379, 725123074 (live REST), read-only Databricks SQL on dev/tst | 39 / 4 / **8 refuted** / 1; 24 divergences from `specs.md` |
| The two plans | 14 rule families, every cutover step, tool citations | repo capability checks + web verification of all four cited tools | 10 ranked defects; 8 date/gate contradictions; 1 factual error in tooling claims |
| Red team | all arithmetic, 18 cross-document contradictions, 5 internal falsifications | independent scripts (`decimal`, 64-config enumeration, deterministic grids) | arithmetic correct except one unreproducible statistic; 1 "most likely wrong implementation" |
| Azure (X14) | tst subscription resource inventory | read-only `az` as the VM UAMI | **Confirmed**, with a positive control in dev |

**Two method notes that matter for anyone re-running this.** First, two local working trees are *behind* the deploying refs — `mobile-server` (worktree `8c47ee68`, 13 Oct; `origin/develop` `95733012`, 15 Oct) and `mobile-app` (worktree `6fcf5f5a`, 9 Sep; `origin/develop` `352bde30`, 15 Oct). Every BFF/app citation here is from the remote ref. Second, `app-data`'s deploying branch is **`tst-blue`**, not `tst` — the `tst` branch is stale at June. Both facts are load-bearing for the findings below.

---

## 4. Errors about the estate

These are claims the deploying refs contradict. They are listed first because they are the cheapest to fix and the most expensive to build on.

### 4.1 The status validator in X1/§8.4 does not exist on the branch that deploys

`specs.md:428` describes "the list the Publish Engine accepts for NBA today" as `scheduled, active, pending, won, lost, push, void, cancelled, rescheduled, abandoned`. That tuple is `VALID_PICK_STATUSES` in `databricks/publisher/canonical_transformations.py`, which exists **only on `feat/nba-2026@54214ec3`** — not an ancestor of `tst-blue@a1c16f43` (verified: 0 files on `tst-blue`, 2 on the feature branch, `git merge-base --is-ancestor` → no). On the deploying branch, `nba_wltp.py:233-239` *synthesises* status from `bet_bookie_outcome` and `nba_ps.py:403-407` passes any value through lowercased; nothing validates it.

**Why it matters:** X1 is one of the two rows with a hard date (31 Oct) and its required action is "ship the new status list and the Publish Engine's accepted list together". There is no accepted list to update on the deploying branch. D5 (due 21 Oct, two days from now) is not reconciling two existing lists — one of them is hypothetical.

### 4.2 The id contract cannot be implemented as written, and the conflict is internal

`specs.md` §8.1 (`:384`) adopts the NBA split documents as the target — "picks keyed by lowercase region (`au`, `us`), as the NBA split documents already do". §8.2 (`:390-391`) then freezes ids as `{game_sk}_{bet_type}_{region}` and `{game_sk}|{player_sk}|{stat}|{type}|{region}`. Those are the **legacy** shapes (`transformations_library.py:682,498`). The NBA canonical documents §8.1 points at use 7- and 8-field line-aware ids (`nba_wltp.py:241-250`, `nba_ps.py:409-420`).

Worse, §8.2 (`:396`) bans `.` in ids "so they can be realtime database keys", while those NBA ids contain a dot on **every line-bearing pick** — `line_token = F.coalesce(line.cast("string"), F.lit("null"))` produces `-4.5`, and §7.2/AC-13 place that id inside an RTDB path (`{sport}_{id}`). Two of the document's own MUSTs cannot both hold for the format it adopts, and the overlay design — the headline live feature — depends on the resolution. The canonical model reaches the right answer (opaque `overlay_key`, ids keep their dots) but that is a change to this document, not a clarification.

### 4.3 The live-scores coverage table is wrong about NBA

`specs.md:462` (X14) says the live scores `dev` branch "has MLB, NBA, NFL and WNBA". It does not: `origin/dev` top level is `mlb`, `nfl`, `shared`, `wnba` — **there is no NBA module on any branch**, and the repo's own README lists MLB (active), WNBA (in development) and NFL (stub) only. X6's table (`:466-472`) contradicts X14 by claiming NBA live-scores code is "`dev` only".

The nuance matters and should not be lost: a `fa-live-scores-nba-dev-01` function app **does** exist in the dev Azure subscription (confirmed read-only), so NBA live scores is deployed in dev from a ref that is not present in this clone — no commit in any fetched ref has ever touched an `nba/` path. The document's *conclusion* (NBA live coverage exists only in dev) survives; its *stated evidence* is unreproducible, and the branch that would deploy NBA is not identified anywhere in the folder.

Additionally, both live services' deploy workflows derive the environment from the branch and accept only `dev|tst|prd`. `live-odds` has no `tst` branch and `live-scores`' `tst` branch contains only a README (`d94828e5`, 30 Jun). So for both services a tst deployment is **impossible today, not merely unconfigured** — a stronger statement than X14 makes, and one that strengthens its conclusion.

### 4.4 X7 understates its own risk

`specs.md:455` says "missing `edge` and other values pass through as null without failing". The code does the opposite: `nba_wltp.py:307-308` filters to picks where `edge` is not null, so a null-edge game pick is **silently dropped** and the document ships with an empty `edge_picks.au[]`. If the `edge` field is *absent* from the source struct rather than null, the same filter dereferences it unconditionally and fails analysis — while a nearby comment claims it "falls back gracefully when absent". For a launch gate this is the difference between a degraded card and a game with no picks at all.

### 4.5 The release gate is a chokepoint at `api_version` 6, not a per-route dial

`specs.md:459` (X11) says "the league release gate applies per route". It is a chokepoint gate (`gate.ts`), and staged content is served only from `RELEASE_API_VERSION_MAJOR = 6` (`gate.ts:78`); the app's `DEFAULT_API_VERSION` is `"v6"` at `origin/develop`. Three meanings of "v4" now coexist in the estate: the route major, the `api_version` query value, and a legacy feature flag. A new `/v4/edge-picks` route reading Cosmos directly inherits **nothing** from the gate — the action is right, the reason is wrong, and a client that sends `api_version=v4` (the natural reading of a `/v4` route) sits below the v6 release major.

### 4.6 §3's availability key understates what already ships

Five cells are inverted: entry odds, entry line, entry edge and stake are marked **1A**, but all four ship today on the NBA canonical path (`canonical/picks.ts:427-430,467-468,500-503`; produced at `nba_wltp.py:183,266-272,288`). "Picked at" is marked 1A for all sports but exists for NBA game and player picks today; only WNBA player picks lack it (X9, correctly). The cancelled-card row is marked "status 1A" though `cancelled` is already in the producer vocabulary — what is missing today is that the BFF **drops** cancelled picks rather than serving a card (`my-pick.ts:9-25`).

This cuts in the redesign's favour: the core card is closer to shippable than the document claims. It also means the phase plan is building things that exist, which is a schedule risk in the other direction.

### 4.7 Smaller refutations, each verified

- **§8.3 `projection_value`/`projection_unit` "Exists"** — absent from both `app-data@tst-blue` and `mobile-server@origin/develop`; player projections ship as `predicted[] {stat, stat_name, value: "27.80"}` (a 2 dp string). A field the BFF must map "from these records and nothing else" has no producer.
- **§8.5 "consumers MUST NOT branch on an exact `schema_version`"** — the consuming BFF already does (`api-version.ts:113`, `canonical/wltp.ts:15-20`). Enforcing the rule as written means rewriting document selection, which the spec does not budget.
- **§8.6 / AC-17 "the Publish Engine's CI validates sample output against that schema"** — no such check exists on `tst-blue`; the transformation map dispatches by name with no schema validation.
- **§6.2's mirror-leak rule is presented as existing behaviour** ("follows the existing freemium rules unchanged") but is **unimplemented**: `top-picks-screen.registry.ts:15-49` strips each group from its own flag independently, with no cross-group logic. The default configuration hides two of three groups by luck, not by enforcement. AC-21/AC-37 are new build, not regression tests.
- **`specs.md:445`'s stated method** — "checked against each repository's `dev` and `tst` branches (the deploying branches)" — is not the estate's branch model. That sentence is the root cause of 4.1 and 4.4.
- **`canonical-data-model.md:51`** attributes the four "threes" labels to Jira `XPRB-45`; that ticket is "Missing XO Projection Value for MLB Top Pick Cards", status Done — unrelated.
- **`canonical-data-model.md:479`** says MLB/NFL player values are "raw today"; both container contracts specify 2 dp strings and the legacy PE formats `%.2f`.
- **`canonical-data-model.md:117`** cites `settle_from: fact_player_stats.pitching_hits`; there is no `fact_player_stats` in `dev_mlb` — the column lives in `mlb_silver.fact_player_game_stats`. The NBA analogue does exist.
- **`canonical-data-model.md:255`** calls 10–15 RU per match view "as NBA 2026 measured"; the Schema Specification states it as a *budget*.
- **`canonical-data-model.md:427`** says "pick status and event status never share values" — both lists contain `cancelled` (`:423`/`:427`), and the claim is the stated justification for keeping the two enums separate.
- **`canonical-data-model.md:411`** makes `variant` "not identity" on the argument that "the line already separates them". Today's NBA id *does* carry `variant` (`nba_wltp.py:241-249`), so two alternate lines at the *same* line collide in v3 where they are distinguishable today. Small, but it is a genuine loss of identity, not a simplification.

---

## 5. The folder is not one plan

### 5.1 Two migration mechanisms and three timelines

| Source | Mechanism | Where the documents live |
| --- | --- | --- |
| `canonical-data-model.md:585-586` | NBA **dual-publishes**; "publishes v3 **beside** NBA 2026"; BFF reads v3 behind a per-league flag | Same containers (partition keys kept, `:255`) |
| `coexistence-cutover-plan.md:12,47` | "There is no production overlap"; "Production never holds both families for one game"; shadow into containers no user reads, then a clean switch on a date | Shadow containers |
| `specs.md:397` + `:609` | Ids "frozen in this format through Phase 2"; 1B (1 Dec) = "one schema for all sports" | A third timeline for the same cutover |

The two mechanisms cannot both be built. The cutover plan's design is the more defensible one — it enumerates the read paths that a shared container would corrupt (§2 finding 6), and those paths are real. But the model's plan is the one with a phase date attached, and `specs.md` §11.1's 1B reads like a third, simpler switch that neither of the others schedules. **Someone must pick one, and the pick determines whether `legacy_ids[]` is needed at all** — the model requires it (`:415,590,664`) and the cutover plan says it "can be dropped" (`:45`). Dropping it before the slip-rewrite job exists is a one-way door for every saved `predictionId`.

### 5.2 The six conflicts that must be closed before any producer is written

Each is a decision, not a bug; each has an owner already named somewhere in the folder; none has a single answer today.

| # | Conflict | `specs.md` says | The other document says | Why it blocks |
| --- | --- | --- | --- | --- |
| 1 | **Document layout** | region-keyed map is the target (`:384`) | flat `picks[]` with a `region` field (`canonical-data-model.md:56,333`) | The BFF parses the region map today (`canonical/picks.ts:366,540`). Two mutually exclusive shapes under the same doc types, and it is invisible if either document is read alone. |
| 2 | **Status vocabulary (D5)** | "Keep the roadmap list" (`:644`); mapping table at `:213-223` | "producers publish the five v4 statuses plus `withdrawn`" — "this settles D5" (`:419,645`) | Opposite resolutions, same owners, same 21 Oct date. The monitor filter, PE accept-list and BFF mapping are all built from this answer. |
| 3 | **Pick id** | frozen through Phase 2 (`:397`) | `{selection_key}\|{region}\|{seq}`, "amend §8.2 before build" (`:397,601`) | Saved My Picks slips and follows reference ids; the app's follow key is `${type}:${id}` (`TopPicksList.tsx:95`). |
| 4 | **Edge definition and break-even** | `edge = p × d − 1`, `b = (1+t)/p`, D3 to confirm (`:282,253,642`) | `ev` and `edge_prob` from the outcome split; `(1+t)/p` is "the wrong price" for a probability-edge engine (`:373,629-641`) | The card's headline number and the "edge holds above" price. The model is right on the maths; `specs.md` is right that the decision is D3's. |
| 5 | **`withdrawn` has no home** | §5.1's table is exhaustive; "an unlisted value drops the pick and raises an alert" (`:211`) | `withdrawn` is a status (`:423`) | Every withdrawn pick raises a false alert and AC-8 fails. |
| 6 | **Phase 1B** | one schema for all sports, 1 Dec (`:609`) | NFL/EPL cut over in January, ~a month later (`:585-586,593,712`) | Acknowledged by the model and unacknowledged by `specs.md`. |

### 5.3 Field-level divergence is wider than the six

The model and the contract carry **20 substantive divergences** (the source table has 24 rows; four are explicitly recorded as compatible, acknowledged or non-contradictions) including names for the same concept (`pick_status` vs `status`, `outcome` vs `result`, `edge_status` vs `edge_state`, `schema_version` vs `schema`), different value sets (`sport` ∈ {nba,nfl,…} vs `sport: soccer` + `league: epl`; `market`/`side` vs `market`/`outcome`), and different meanings for the same field name (`probability` = "model output at entry" vs "the value the pick was selected on"). One field carries **three names in two documents** — `issued_at` (`canonical-data-model.md:341`), `picked_at` (`:584`), `pick_date_time` (`specs.md:409`). The model acknowledges many of these and asks v4 to change; that is a healthy process, but until it happens the folder is two contracts, not one.

### 5.4 The cutover plan depends on things no document contains

`coexistence-cutover-plan.md` requires (a) a per-league cutover entry "in the registry", (b) an `event` field `family` "so the BFF knows before it reads anything else" (`:37`), and (c) response-cache keys with a family epoch (`:55`). The canonical model — which owns the registry (`:84-94`) and every document (`:244-253`) — contains **zero occurrences** of "family", "cutover", "epoch" or "shadow". The model's own Gate 1 would reject a document carrying an unregistered key. And a *required* `family` field is a **major** version change under the model's own rule (`:528`), not the additive change the plan assumes.

Two further internal defects in the cutover plan:

- **C4's precedent does not exist.** "Free-user locks apply by field group to the internal model after translation, **as `/v4/edge-picks` already does**" (`:43`). There is no `/v4/edge-picks` route anywhere in the estate — the highest BFF route is `v3/…`. The *direction* is right (and the leak claim is verified: the stripper lists `decimal_odds`, `market_odds`, `bet_price`, `edge`, but not `entry`, `outcome_probs`, `edge_prob` or `ev`); the precedent is not.
- **Rollback contradicts the invariant it protects.** C6 says "production never holds both families for one game"; C6a then re-publishes not-yet-started games in the legacy family while their v3 documents remain, ignored by a date rule (`:47-49`). C1 says the family is decided once for a game's whole life; C6a re-decides it. There is no delete path for the orphaned v3 documents, no trigger, no owner and no threshold. The intent (fix forward, never strand a saved slip) is right; the invariant statement is false and needs to become "no *served* overlap", with an explicit exception to C1.

### 5.5 The canonical model treats a non-existent mechanism as today's

`canonical-data-model.md:62` keeps "the settlement write-back" as a **Keep** verdict, `:287` says "the PE then writes `status`, `result` and `settled_at` into every pick … as NBA 2026's write-back loop does today", and `:413` builds the per-selection grading rule on it. On `tst-blue` the outcome transform writes **empty** settlement arrays with a `TODO` (`nba_schedule_outcome_injuries.py:88-89,114-118`); no PE code writes grades back into picks; and neither `nba_pick_settlements` nor `nba_settlement_rejections` exists in the readable dev/tst catalogs (they are precreate tasks: `reqs/nba/implementation_todo.md:100`). The per-selection grading design is sound. Its cost is booked at zero, and it is the half of the model the Edge Picks receipts depend on.

---

## 6. Defects inside `specs.md` that are not about the estate

1. **Rule 3 is undefined for null lines, and the test suite cannot catch the misreading.** §5.3 rule 3 compares "the current line" with "the entry line"; §4.3 says moneyline, draw, BTTS and yes/no props have `null` lines (`:175`). The comparison is never defined for nulls. E9 is the only no-line case and it expects `closed` — which rule 4 produces anyway at 1.7000 ≤ b. So an implementation that treats a missing line as a moved line classifies every moneyline at 2.0000 as `closed` (red, "outside edge") instead of `live`, and passes E1–E11, AC-24 and AC-28. The fix is one sentence plus one case (no line, price above `m`).
2. **`edge_holds_above` belongs to two field groups** (odds and probability, `:309-310`), and `b = (1+t)/p` recovers the hidden probability whenever `t` is known — and D3 recommends publishing `t` with every pick. AC-21/AC-37 name only `entry.edge`, `current.edge` and the added group, so an implementation can pass both while returning a real `edge_state` and a non-null `edge_holds_above` for a pick whose edge is hidden. AC-12 is the only criterion that enumerates the full field set; the other two should copy it.
3. **The D6 recommendation cannot satisfy §7.4.** §7.4 requires the entitlement window to be bounded "by its key or token lifetime"; D6's recommended static `HMAC(secret, pick_id)` has no lifetime — its only rotation is the secret. The alternative in the same sentence (entitlement claims checked by database rules) does bound it.
4. **Principles 1, 3, 5 and 6 have no acceptance criterion**, though §1 says "each is enforced by acceptance criteria in section 10". Principle 3 ("other systems map it; they never recompute it") is also contradicted by §6.1's own "Who else MAY compute it" column.
5. **AC-11 cannot fail** — "the configured number of top picks by probability" is defined nowhere in the document.
6. **AC-28 proves less than it looks**: rules 1–3 ignore `game.state`, so 21 of the 35 cells are decorative, and 6 cells (`settled` × a game state that is not `final`) are unreachable under §5.1's own transitions.
7. **`(1+t)/p` is only right for an EV-threshold engine** (§2 finding 5, §5.2 row 4). This is the single most valuable correction in the canonical model and it is currently a D3 recommendation in `specs.md`, i.e. optional.
8. **`specs.md`'s phase dates rest on a session-scoped artifact.** The "Bet Engine Roadmap" is cited as `https://claude.ai/artifact/FX29b7SibKX5gx1SiyLpvH` (`:9,654`) — not in Confluence (title and full-text searches empty), not in any repository. The Confluence Edge Picks redesign page (726237185, v5, 9 Oct) has requirements but no phases and no dates. **Every 1A/1B date and every D-deadline in the folder is uncorroborated from the estate.**

---

## 7. The two plans, assessed as plans

### 7.1 `canonical-data-verification-plan.md`

**Right shape, wrong size, no schedule.** The 14-family decomposition is sound and the diagnosis of today's gates (checks without ids, no history, no set-level view, one failure action, settlement not re-derived) is accurate. But:

- **Nothing is owned or dated.** Ownership is one role sentence; there is no per-family owner, no work breakdown, no estimate, and no reference to 1A (31 Oct), 1B (1 Dec) or X14 (23 Oct). It cannot be staffed or accepted as written.
- **Its foundation lands after the first gate it must protect.** The plan presupposes `xo-contracts`; the repository does not exist (GitHub 404) and its creation is decided 6 Nov — a week after 1A. The registry v1.0 draft is due 23 Oct with no named author.
- **Two of 14 families use severities outside the plan's own four-value scheme** ("Merge blocked" for `REG`, "Drop and alert" for `CON`), and the plan's own promise at `:48` that "a failure never silently changes what users see" is false for a **first publish**: Block drops a new card with no last-good version to fall back to — the common case in 1A/1B.
- **Replay is a second writer into published documents** (`:59`), bypassing the engine gate the plan itself calls "the only one that prevents bad data". Report-mode rows share the triage quarantine table.
- **Report-only first is not executable on the stated inputs.** It requires running the families over today's NBA 2026 and Format A output "mapped to v3 by an adapter" — no such adapter exists, and today's canonical path runs the *inverse* (`normaliseWltp`). Step 1 needs the v3 model, the registry and two adapters, none of which is scheduled.
- **Coverage holes with no family**: `overlay_key` derivation and entitlement, `is_closing`, status-reason and settlement-fraction vocabulary, `event_result` period sums and grading uniqueness, the entire position ledger and `venue_listing`, adapter semantics, and the **4 dp/6 dp seam** — the exact cross-runtime drift class the plan exists to prevent.
- **Tooling citations**: three accurate, one factual error, one overstated. The error: `dependencies` is not a JSON Schema 2020-12 keyword — it is `dependentRequired`/`dependentSchemas`. The overstatement: the `@bufbuild/cel` source link is not stale — `github.com/hudlow/cel-es` resolves and documents the package; only the npm `repository` field points at `bufbuild/cel-es`. Also understated: `cuelang-js` is deprecated and archived since 2021, not merely "old".

**Assessment:** the right programme, roughly a quarter of engineering across three runtimes, a CLI and a web workbench — presented as a document with no cost. Either cut it to a v1 (`SHP`, `IDN`, `PRC`, `CON` + the shared vectors) that can land before 1B, or fund it explicitly as a programme with a named owner and a date.

### 7.2 `coexistence-cutover-plan.md`

**The best evidence and the weakest procedure.** Its read-path table is accurate (7/7 citations verified). Its five design rules are the right ones, and C6a's "fix forward first, never strand a saved slip" is the right instinct for an irreversible step. But:

- **No owners, no dates, no sizing.** The cutover dates for NBA/NFL/EPL, the shadow's clean criterion, the legacy-transform lifetime and all five open items are unowned. X14's third owner is "to be named".
- **The shadow assumes an idle blue/green slot that does not exist as assumed.** The tracked evidence is that BFF container targeting is per-environment env vars (`cosmos.ts:21-31`) whose deployed values are not in git, while `api-partners` sets its own slot independently (`switch-cosmos-slot.yml:117`) — so there is no single coherent slot to point a shadow at and no authoritative record of which containers are live. The stronger claims (no safety gate, inverted live-config rule, CDF replay hazard, standby never having run current code) come from `app-data/bluegreen_assessment.md`, which is an **untracked working-tree file** (16 Sep, self-described as an AI review of `dev @ e198082`) — not evidence at `tst-blue@a1c16f43`, and it must be re-derived at the deploying ref or dropped (see §10).
- **"Format A documents lack `doc_type`" is false** (`gate.ts:37-43` says the id, `doc_type` and `schema_version` are written identically by legacy and canonical producers), and v3 **reuses** the `injuries` doc_type — so C2's `doc_type IN (…)` filter cannot separate families there.
- **Unlisted consumers break.** The **partner API** is declared out of scope (`:113`) but reads the same containers directly (`api-partners` `internal/cosmos/client.go:79`, `repository.go:1196`), maps legacy field names (`team_1_sk`, `game_datetime`) that a v3 `event` does not carry, and can be pinned to a different Cosmos slot. The injuries panel (`getInjurieslist.ts:38`, no `doc_type` filter) and the WordPress payload (`build-daily-match-payload.ts:369`, selects on `IS_DEFINED(c.schema_version)` which v3's envelope does not set) are also unlisted. "Out of scope" is not "unaffected".
- **No production invariant check** that one game has one family — the plan's central claim is never monitored. No post-cutover reconciliation of My Picks, track record or ROI. No freeze window, no rollback trigger, no go/no-go owner, no comms, no runbook.
- **§11.3's isolation rules are never cited**, though C47's "staging BFF pointed at shadow containers" is exactly the parallel setup those rules govern.

**Assessment:** adopt it as the migration design of record — it is the only one of the three that survives the read-path evidence — then write the runbook, name the owners and delete the dual-publish plan from the model.

---

## 8. What this means for the launch decision

1. **Option A′ is the only launch-viable choice, and it is not free.** The headline feature has a live source for one sport in dev only, and the snapshot path that would carry current values to all sports is a hand-off the monitor has **explicitly deferred** (`EDGE_PICKS_LIVE_ODDS_DESIGN.md:222` "Longer term (not built) … deliberately deferred"; X12 is confirmed). A′ is described as needing "nothing beyond 1A" (`:616`) but it depends on D3 — the threshold `t` published with every pick — and on the staleness contract. (`:616` does assign the same-line edge and edge state for uncovered sports to the BFF, which §6.1's ownership table permits, so D7 is not an additional dependency.)
2. **X14 is a delivery programme, not a plan-by date.** The Azure check confirms the tst subscription holds exactly five resource groups (2× Data Factory, inference, subscription-status, subscription-reconciler) and 47 resources with no live-scores or edge-monitor compute, no App Insights, no managed identity — while the dev counterpart has `fa-live-scores-{mlb,nba,nfl,wnba}-dev-01` and `fa-edge-monitor-nfl-dev-01`. Combined with the branch facts in §4.3, both services must be provisioned *and* given a branch that can deploy to tst. That is new infrastructure, and 23 Oct is four days away.
3. **The decision queue is the real bottleneck.** `specs.md` lists 13 open decisions (D1–D13), **eight** of them due on or before 23 Oct (D5 on 21 Oct); the model adds 17 more (V1–V17), six due on or before 23 Oct, four on the 1A critical path. Several have the same owners (bet engine, data engineering, monitor owner) and two — D5 and V1 — are the *same* decision with opposite recommendations. Thirty decisions across roughly four weeks — fourteen of them before 30 Oct — with the folder's own documents disagreeing on the answers, is not a schedule; it is a queue that will be cleared by whoever implements first.
4. **The dates cannot all hold.** Under the cutover plan's own rules no league can be on the 1B date (a shadow of 1–2 slate cycles per league precedes any flip), while `specs.md` §11.1 promises one schema for all sports on 1 Dec and the model defers NFL/EPL to January. Pick the date or pick the method.
5. **What is genuinely close to shippable:** the core card for NBA. Odds, line, edge, stake, book name, probability, projection, publish time, the cancelled status and the freemium lock all ship today. The redesign's *app* work can start against mock data now; the *data* work is where the risk is.

---

## 9. Verification ledger (summary)

| Area | Verdict | Key evidence |
| --- | --- | --- |
| All arithmetic in `specs.md` §5.3/§6.1/§10.3/§10.4 | **Correct** | recomputed independently in `decimal`; 0 discrepancies |
| All arithmetic in `canonical-data-model.md` §Pick/§Validation/R2 | **Correct** | 900/900, 8,100 fails from −1023, 99/99, push-aware EV, R2 table |
| `ev = d × edge_prob` "fails in 68.9%" | **Unreproducible** | generator-dependent; reproductions 28.6%–83.0%; mechanism confirmed |
| X1 monitor half (`Scheduled`, deletes others) | **Confirmed** | `live-odds` `collapse.py:16,22`, `nfl/function_app.py:294-298` |
| X1 PE half (status validator) | **Refuted** | validator only on `feat/nba-2026@54214ec3`, not `tst-blue` |
| X2 monitor id `{bet_id}\|{region}` uppercase | **Confirmed** | `pick_reader.py:35`, `test_stores.py:99` |
| X3 06:00 UTC discovery | **Confirmed** | `nfl/function_app.py:239,243` |
| X4 dev/tst/prd settings | **Confirmed** | `infra/deploy.ps1:29-69`; AC-34 not implemented |
| X5 RTDB read rules | **Partly** | rule text exists in docs only; no rules artefact checked in |
| X6 live-scores coverage | **Partly** | no `nba/` on any branch; `main` also lacks `nfl/` |
| X7 null-edge pass-through | **Refuted** | picks are dropped, not nulled (`nba_wltp.py:307-308`) |
| X8 MLB one-book rule | **Unverifiable** | decision record not locatable |
| X9 WNBA player publish time | **Confirmed** | `wnba_bet_engine@df918025` `_ps_engine.py:191-207` |
| X11 gate per route | **Refuted** | chokepoint gate, `RELEASE_API_VERSION_MAJOR = 6` |
| X12 monitor defers Cosmos final state | **Confirmed** | `EDGE_PICKS_LIVE_ODDS_DESIGN.md:214,222` |
| X13 no observation time sent | **Partly** | `market_last_update` already ships for NBA |
| X14 tst has no live resources | **Confirmed** (Azure) | 5 RGs / 47 resources; dev positive control |
| X14 live-scores `dev` has NBA | **Refuted** | no `nba/` on `dev`, `main` or `tst` |
| §7 overlay node paths and fields | **Confirmed** | `firebase_writer.py:47-59`, delete paths `:14-31` |
| §7.5 `/liveGameCards` + `st` | **Confirmed** | `firebase_mappers.py:40,53` |
| §8.1 region-keyed target | **Confirmed** | `nba_wltp.py:303-316`, `nba_ps.py:476-511` |
| §8.2 id formats | **Refuted** | legacy shapes; NBA ids are line-aware and dotted |
| Freemium flag names | **Confirmed** | `global-show-map.ts:16-21`, `settings.ts:57-63` |
| Mirror-leak rule implemented | **Refuted** | `top-picks-screen.registry.ts:15-49` |
| `/v4/edge-picks` route | **Does not exist** | highest route is `v3/…` |
| ETag / `If-None-Match` / 304 | **Does not exist** | `git grep -il etag origin/develop -- 'src/**'` → 0 |
| Cutover plan read-path table (7 citations) | **Accurate** | substantively correct at `origin/develop@95733012`; two citations off by one line |
| Cutover `family` / registry cutover / cache epoch | **Absent from the model** | 0 occurrences in `canonical-data-model.md` |
| `xo-contracts` repository | **Does not exist** | `gh api repos/XOSports-ai/xo-contracts` → 404; no repo in the org matches `registry`; creation decided 6 Nov |
| Validation-plan tool citations | **3 accurate, 1 error** | JSON Schema `dependencies`; `cuelang-js` deprecated |

---

## 10. What could not be verified

1. **The Bet Engine Roadmap** (`claude.ai/artifact/…`) — session-scoped, not in Confluence or any repo. Every 1A/1B date and D-deadline is therefore uncorroborated.
2. **The 16 Oct review** that `canonical-data-model.md` responds to — not in this workspace, so its "reviewer reports 78%" cannot be checked.
3. **Firebase/GCP side of X14** — whether `xosports-predictor-app-tst` exists and owns a realtime database, and the "no one owns an RTDB" statement. No GCP credential on this VM; the Azure half is confirmed, this half is not.
4. **Whether the monitor writes a history row at or after kickoff** — decides whether `is_closing`/AC-41 is implementable. The documents are silent; the monitor's design defers it.
5. **X8's MLB decision record** and the Confluence pages' current content beyond the three read live (717914114, 717029379, 725123074).
6. **The app's payout/slip arithmetic** (S12) — not traceable at the refs read.
7. **The `68.9%` and `78%` figures** — the sample is undisclosed; the mechanism is confirmed, the numbers are not.
8. **`app-data/bluegreen_assessment.md`'s six blue/green findings** — the file is untracked, appears in no fetched ref, and self-describes as a 16 Sep review of `dev @ e198082`, not of `tst-blue@a1c16f43`. Its conclusions are plausible and the two tracked legs of that argument (`cosmos.ts:21-31`, `api-partners`' slot map) hold, but the six findings themselves need re-derivation at the deploying ref before the cutover plan relies on them.

Where a claim rests on absence rather than contradiction, this assessment says so. The Databricks checks were read-only, and one catalog (`dev_etl`) is hidden from the read-only service principal — absence there is a permissions boundary, not proof of absence.

---

## 11. Recommended actions, in order

1. **Close the six conflicts in §5.2 in one decision record, this week, with named owners.** D5/V1 and the id format first: they are the same decisions taken twice with opposite answers, and both are dated 21 Oct.
2. **Re-verify the §9 X-table and the §3 availability matrix at the deploying refs** (`app-data` `tst-blue`, `mobile-server` `origin/develop`, `live-odds` `dev`, `live-scores` `dev`/`main`), and fix `specs.md:445`'s method sentence. Two of the errors in §4 came directly from that sentence.
3. **Replace the claude.ai roadmap citation with a durable source**, or mark every date in the folder as provisional. A schedule that cannot be read by the people who must meet it is not a schedule.
4. **Adopt the cutover plan's clean-cutover design and delete the dual-publish plan from the model** — then add the two things it is missing: a production invariant check that one game has one family, and a rollback runbook with a trigger and an owner.
5. **Amend the canonical model to carry what the cutover needs** (`family`, the registry cutover entry, the cache epoch) and settle `legacy_ids[]` in favour of keeping it until the slip rewrite has run.
6. **Treat X14 as a programme**: named owner, provisioning list, a `tst` branch that can actually deploy for both services, and a committed date. Until then, plan option A′ and say so in the launch plan.
7. **Cut the validation plan to a v1 that can land before 1B** (`SHP`, `IDN`, `PRC`, `CON`, shared vectors, golden documents per league), and fund the rest — registry, three runtimes, CLI, workbench — as a separate programme with its own owner and dates.
8. **Add the missing acceptance criteria**: rule 3 for null lines (with a case), the full field set on AC-21/AC-37 (copy AC-12), a bounded lifetime on the D6 key, and a day-window boundary case for AC-30.

---

## 12. The one-paragraph version

This is a folder of good ideas with a bad evidence base and no owner. The contract is carefully specified and its arithmetic is exact; the canonical model's identity separation and push-aware EV are real improvements; the cutover plan correctly diagnoses the read paths that make coexistence dangerous; the validation plan is the right programme. But 17 of 82 checked claims in the contract are refuted, concentrated in the rows that carry the hard dates; the model treats a settlement write-back that does not exist as today's behaviour and books its cost at zero; the folder carries two incompatible migration mechanisms and 20 substantive field-level divergences between two documents that both claim to define the same producer contract; and nothing in it has an owner, an estimate or a durable schedule. Approve the direction, close the six conflicts, fix the evidence, pick one migration, and re-plan the dates — in that order. Building from this folder as it stands will produce a system that passes its own acceptance criteria and is wrong in ways the criteria cannot see.

---

### Appendix — artefacts produced by this assessment

All paths relative to the scratchpad root, `xo-scratchpad/`.

| File | Contents |
| --- | --- |
| `.verify/assessment/specs-findings.md` | 82 commit-pinned verdicts on `specs.md` (44 section findings, 24 availability cells, X1–X14) |
| `.verify/assessment/model-findings.md` | 52 verdicts on `canonical-data-model.md`, 24 divergences from `specs.md`, 7 internal inconsistencies |
| `.verify/assessment/plans-findings.md` | Per-family verdict table (14 families), per-step cutover reversibility, tool-citation verification, 8 date/gate contradictions |
| `.verify/assessment/redteam-findings.md` | Recomputed arithmetic, 18 cross-document contradictions, 5 internal falsifications, ranked defects |
| `.verify/assessment/redteam-audit.md` | Adversarial audit of all four streams and of this assessment; the source of the corrections applied above |
| `.verify/assessment/azure-tst-check.md` | Read-only Azure inventory confirming X14, with the dev positive control |
| `.verify/assessment/scripts/` | The red team's recomputation scripts and raw output |
