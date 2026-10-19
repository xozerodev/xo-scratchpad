# Edge Picks redesign — independent assessment

**Subject:** `edgepicks-redesign/` — `specs.md` (654 lines), `canonical-data-model.md` (746), `canonical-data-verification-plan.md` (171), `coexistence-cutover-plan.md` (120). All four dated 16–17 Oct 2026, author @Tze Liang.
**Assessment date:** 19 Oct 2026. **Revision 3** (19 Oct, evening): Part 2 (§13–§16) reviews the first revision of `specs.md` and the author's first rebuttal; Part 3 (§17–§20) verifies the two engine findings, reviews the second revision, and supersedes Parts 1–2 where they differ. Two Part 1 findings are retracted, three reclassified and one method claim corrected (§13); one Part 2 finding is conceded (§17 E5) and one clone-staleness cause acknowledged (§17 E4). All corrections are applied in place below.
**Method:** four independent verification streams against the deploying branches of the real estate, plus a red-team pass over the documents' own arithmetic and internal logic. ~180 commit-pinned verdicts. Evidence files (paths relative to the scratchpad root, `xo-scratchpad/`): `.verify/assessment/specs-findings.md`, `model-findings.md`, `plans-findings.md`, `redteam-findings.md`, `redteam-audit.md`, `azure-tst-check.md`.

---

## 1. Verdict

**The thinking is good. The evidence base is not, and the folder is not one plan.**

Three of these four documents are unusually disciplined for design proposals: they carry worked examples that recompute exactly, "verified against" columns, explicit "not yet checked" lists, and a review-response table that concedes nine previous findings. That is rare and it should be said first.

It does not survive contact with the estate. Of 82 discrete claims in `specs.md` checked against the deploying refs, **13 are genuinely refuted** and 27 only partly hold (a further four were requirements misread as claims about today — §13 C3). The failures cluster precisely where the schedule is: the two rows with hard dates rest on an unmerged feature branch and on a misreading of which branch deploys. The canonical model treats a settlement write-back that does not exist as today's mechanism and books its cost at zero. And the folder contains **two mutually incompatible migration mechanisms** — the canonical model dual-publishes into shared containers, the cutover plan forbids exactly that — on top of **three different timelines** for the same cutover, and a frozen id contract that both of the others say must change.

**The two 19 Oct revisions of `specs.md` fix 11 of the 13 and accept the rest** (§14, §18). It is now a materially better document: the edge-basis error, the id contradiction, the null-line rule, the status reality, the branch basis, the unbuilt-conformance observations and all six cross-document conflicts are corrected or deferred, and new acceptance criteria close the test gaps. What remains is small, listed in §15 and §19 — and the largest of it is no longer in the document: **the NBA player-pick engine changed direction on 16 Oct**, deleting picks a re-run no longer produces and blending the published probability toward the market (§17). Both are deliberate, both are dev-only so far, and both are disagreements to settle with another team rather than lines to fix in a spec.

| Document | Verdict | One line |
| --- | --- | --- |
| `specs.md` | **GO as the app-facing contract, after two revisions** | Part 1's "revise, do not reject" was right; the revisions landed 11 of the 13 genuine fixes and closed all six §5.2 conflicts on the spec side. Remaining items are in §15 and §19. |
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
| `specs.md` | §3 availability matrix (24 cells), §4 contract, §5 status mapping, §7 overlays, §8 producer contract, X1–X14 | `mobile-server` `origin/develop@95733012`, `app-data` `origin/tst-blue@a1c16f43` and `feat/nba-2026@54214ec3`, `live-odds` `origin/dev@e2c04ca1`, `live-scores` `origin/main@62b1b2b6`/`dev@8757f3f1`/`tst@d94828e5`, `mobile-app` `origin/develop@352bde30`, `nba_bet_engine` `dev@621ab3c1` | 30 confirmed / 27 partly / **17 refuted — 4 of them requirements misread as claims (§13 C3), and one live-scores refutation retracted (§13 C1)** / 8 unverifiable |
| `canonical-data-model.md` | 52 "today/exists" observations, identity, migration, numerics | same refs + Confluence 717914114, 717029379, 725123074 (live REST), read-only Databricks SQL on dev/tst | 39 / 4 / **8 refuted** / 1; 24 divergences from `specs.md` |
| The two plans | 14 rule families, every cutover step, tool citations | repo capability checks + web verification of all four cited tools | 10 ranked defects; 8 date/gate contradictions; 1 factual error in tooling claims |
| Red team | all arithmetic, 18 cross-document contradictions, 5 internal falsifications | independent scripts (`decimal`, 64-config enumeration, deterministic grids) | arithmetic correct except one unreproducible statistic; 1 "most likely wrong implementation" |
| Azure (X14) | tst subscription resource inventory | read-only `az` as the VM UAMI | **Confirmed**, with a positive control in dev |

**Three method notes that matter for anyone re-running this, one of which cost this assessment a finding.**

1. Two local working trees are *behind* their remote refs — `mobile-server` (worktree `8c47ee68`, 13 Oct) and `mobile-app` (worktree `6fcf5f5a`, 9 Sep). Every BFF/app citation in Part 1 is from `git show origin/<branch>`, not the worktree.
2. **The BFF branch that serves users is `main`, not `develop`.** `prod-deploy.yml` triggers on `push: branches: [main]` and targets `environment: tst`; `develop` targets dev and `staging` targets stg. Part 1 verified BFF claims at `origin/develop`, which is the *dev* branch — the same "which branch deploys" error this assessment charges the spec with. The load-bearing findings were re-verified at `origin/main` (`9aaae555`) and hold: no `v4/…` route, no ETag/`If-None-Match`/`Cache-Control`, `gate.ts:78` `RELEASE_API_VERSION_MAJOR = 6` (that file is byte-identical between the two refs), the freemium flags, `canonical/picks.ts` serving odds/edge/stake, and the per-flag stripper. See §13 C2.
3. **A stale *remote-tracking ref* produced a false finding.** `git ls-tree origin/dev` in `live-scores` reads the local ref; the local ref was `8757f3f` (18 Sep) while `git ls-remote` — run in the same session — already showed the true `dev` at `11599f1`. The reconciliation was never made, and §4.3 of Part 1 was wrong as a result. Always reconcile `ls-remote` against the local ref before reading a tree; a fresh `ls-remote` is not evidence about a stale clone. See §13 C1.

For the record, `app-data`'s deploying ref was **not** stale: local `origin/tst-blue` and the remote both resolve to `a1c16f43`, so the Publish Engine findings were checked at the deploying commit. See §13 C6.

---

## 4. Errors about the estate

These are claims the deploying refs contradict. They are listed first because they are the cheapest to fix and the most expensive to build on.

### 4.1 The status validator in X1/§8.4 does not exist on the branch that deploys

`specs.md:428` describes "the list the Publish Engine accepts for NBA today" as `scheduled, active, pending, won, lost, push, void, cancelled, rescheduled, abandoned`. That tuple is `VALID_PICK_STATUSES` in `databricks/publisher/canonical_transformations.py`, which exists **only on `feat/nba-2026@54214ec3`** — not an ancestor of `tst-blue@a1c16f43` (verified: 0 files on `tst-blue`, 2 on the feature branch, `git merge-base --is-ancestor` → no). On the deploying branch, `nba_wltp.py:233-239` *synthesises* status from `bet_bookie_outcome` and `nba_ps.py:403-407` passes any value through lowercased; nothing validates it.

**Why it matters:** X1 is one of the two rows with a hard date (31 Oct) and its required action is "ship the new status list and the Publish Engine's accepted list together". There is no accepted list to update on the deploying branch. D5 (due 21 Oct, two days from now) is not reconciling two existing lists — one of them is hypothetical.

*Fixed in the 19 Oct revision: §8.4 now says the list was "reported on an NBA feature branch" and is not on app-data dev, and X1 states what dev actually does (§14 row 4).*

### 4.2 The id contract cannot be implemented as written, and the conflict is internal

`specs.md` §8.1 (`:384`) adopts the NBA split documents as the target — "picks keyed by lowercase region (`au`, `us`), as the NBA split documents already do". §8.2 (`:390-391`) then freezes ids as `{game_sk}_{bet_type}_{region}` and `{game_sk}|{player_sk}|{stat}|{type}|{region}`. Those are the **legacy** shapes (`transformations_library.py:682,498`). The NBA canonical documents §8.1 points at use 7- and 8-field line-aware ids (`nba_wltp.py:241-250`, `nba_ps.py:409-420`).

Worse, §8.2 (`:396`) bans `.` in ids "so they can be realtime database keys", while those NBA ids contain a dot on **every line-bearing pick** — `line_token = F.coalesce(line.cast("string"), F.lit("null"))` produces `-4.5`, and §7.2/AC-13 place that id inside an RTDB path (`{sport}_{id}`). Two of the document's own MUSTs cannot both hold for the format it adopts, and the overlay design — the headline live feature — depends on the resolution. The canonical model reaches the right answer (opaque `overlay_key`, ids keep their dots) but that is a change to this document, not a clarification.

*Fixed in the 19 Oct revision: §8.2 makes ids opaque strings, moves the RTDB constraint onto a derived `overlay_key`, adds the NBA split-document formats as observations, and replaces the freeze with a migration rule (§14 row 2). One ambiguity remains — §15.1.*

### 4.3 Live-scores coverage — **retracted and corrected**

Part 1 claimed `specs.md`'s X14/X6 were wrong about NBA live scores. **They were right and this assessment was wrong.** `live-scores` `origin/dev` at its true remote commit `11599f1` has `mlb`, `nba`, `nfl`, `shared`, `tests`, `wnba`; NBA was added on 14 Oct. Part 1 read `git ls-tree origin/dev` against a local tracking ref that was five weeks stale (`8757f3f`, 18 Sep) while `git ls-remote` in the same session already reported `11599f1`. The repo's `README.md` still lists only MLB, WNBA and NFL, which is what misled the read. X6 and X14 do not contradict each other. See §13 C1.

What survives from this row, and it is the substance of X14: **neither live service can deploy to tst today.** Both deploy workflows derive the environment from the branch name and accept only `dev|tst|prd` (`live-scores` `.github/workflows/deploy-mlb.yml`, verified at `11599f1`: `dev→dev`, `tst→tst`, `main→prd`); `live-odds` has no `tst` branch at all, and `live-scores`' `tst` branch contains only a README (`d94828e5`, 30 Jun). So the blocker is not configuration alone — no branch exists that can put either service into the tst environment. That is a stronger statement than X14 makes, and it strengthens its conclusion.

### 4.4 X7 understates its own risk

`specs.md:455` says "missing `edge` and other values pass through as null without failing". The code does the opposite: `nba_wltp.py:307-308` filters to picks where `edge` is not null, so a null-edge game pick is **silently dropped** and the document ships with an empty `edge_picks.au[]`. If the `edge` field is *absent* from the source struct rather than null, the same filter dereferences it unconditionally and fails analysis — while a nearby comment claims it "falls back gracefully when absent". For a launch gate this is the difference between a degraded card and a game with no picks at all.

*Fixed in the 19 Oct revision: X7 now states the drop, the failing run and the empty document (§14 row 4). Re-verified at both `tst-blue@a1c16f43` and `dev@2b6f998` — §13 C6.*

### 4.5 The release gate is a chokepoint at `api_version` 6, not a per-route dial

`specs.md:459` (X11) says "the league release gate applies per route". It is a chokepoint gate (`gate.ts`), and staged content is served only from `RELEASE_API_VERSION_MAJOR = 6` (`gate.ts:78`); the app's `DEFAULT_API_VERSION` is `"v6"` at `origin/develop`. Three meanings of "v4" now coexist in the estate: the route major, the `api_version` query value, and a legacy feature flag. A new `/v4/edge-picks` route reading Cosmos directly inherits **nothing** from the gate — the action is right, the reason is wrong, and a client that sends `api_version=v4` (the natural reading of a `/v4` route) sits below the v6 release major.

*Fixed in the 19 Oct revision: §4.4 and X11 now describe the chokepoint, require the route to call it, and separate `api_version` from the route major (§14 row 6). Re-verified at `main` — `gate.ts` is byte-identical there and in `develop` (§13 C2).*

### 4.6 §3's availability key understates what already ships

Five cells are inverted: entry odds, entry line, entry edge and stake are marked **1A**, but all four ship today on the NBA canonical path (`canonical/picks.ts:427-430,467-468,500-503`; produced at `nba_wltp.py:183,266-272,288`). "Picked at" is marked 1A for all sports but exists for NBA game and player picks today; only WNBA player picks lack it (X9, correctly). The cancelled-card row is marked "status 1A" though `cancelled` is already in the producer vocabulary — what is missing today is that the BFF **drops** cancelled picks rather than serving a card (`my-pick.ts:9-25`).

This cuts in the redesign's favour: the core card is closer to shippable than the document claims. It also means the phase plan is building things that exist, which is a schedule risk in the other direction.

*Fixed in the 19 Oct revision: the §3 cells now read "NBA: today" for those rows and the cancelled row explains the BFF drop (§14 row 5).*

### 4.7 Smaller refutations, each verified

- **§8.3 `projection_value`/`projection_unit` "Exists"** — absent from both `app-data@tst-blue` and `mobile-server@origin/develop`; player projections ship as `predicted[] {stat, stat_name, value: "27.80"}` (a 2 dp string). A field the BFF must map "from these records and nothing else" has no producer. *Fixed in the 19 Oct revision: the cell now reads "Probability exists. Projection value and unit: Ask", and says the BFF derives projections and drops any producer value.*
- **§8.6 / AC-17 — a requirement, not a claim (reclassified, §13 C3).** The spec requires producer CI to validate output against a schema; it does not say that exists today. The finding that survives is a costing one: no such check exists on `tst-blue` (the transformation map dispatches by name with no schema validation), so AC-17/AC-20 are new CI work — and the revision now records exactly that as an observation at §8.6.
- **§6.2's mirror-leak rule — a requirement, not a claim (reclassified, §13 C3).** "Follows the existing freemium rules unchanged" governs *which picks* are unlocked; the mirror rule that follows is stated as something the BFF must apply. It is **unimplemented** (`top-picks-screen.registry.ts` strips each group from its own flag independently, verified at both `main` and `develop`), so it is new build rather than a regression test — and the default configuration hides two of three groups by luck, not by enforcement.
- **§8.5's "consumers MUST NOT branch on an exact `schema_version`" — a requirement, not a claim (reclassified, §13 C3).** The consuming BFF does branch on it today (`api-version.ts:113`, `canonical/wltp.ts:15-20`), so the rule holds only after that work is done. The revision now records that as an observation at §8.5.
- **`specs.md:445`'s stated method** — "checked against each repository's `dev` and `tst` branches (the deploying branches)" — is not the estate's branch model. That sentence is the root cause of 4.1 and 4.4.
- **`canonical-data-model.md:51`** attributes the four "threes" labels to Jira `XPRB-45`; that ticket is "Missing XO Projection Value for MLB Top Pick Cards", status Done — unrelated.
- **`canonical-data-model.md:479`** says MLB/NFL player values are "raw today"; both container contracts specify 2 dp strings and the legacy PE formats `%.2f`.
- **`canonical-data-model.md:117`** cites `settle_from: fact_player_stats.pitching_hits`; there is no `fact_player_stats` in `dev_mlb` — the column lives in `mlb_silver.fact_player_game_stats`. The NBA analogue does exist.
- **`canonical-data-model.md:255`** calls 10–15 RU per match view "as NBA 2026 measured"; the Schema Specification states it as a *budget*.
- **`canonical-data-model.md:427`** says "pick status and event status never share values" — both lists contain `cancelled` (`:423`/`:427`), and the claim is the stated justification for keeping the two enums separate.
- **`canonical-data-model.md:411`** makes `variant` "not identity" on the argument that "the line already separates them". Today's NBA id *does* carry `variant` (`nba_wltp.py:241-249`), so two alternate lines at the *same* line collide in v3 where they are distinguishable today. Small, but it is a genuine loss of identity, not a simplification.

**Status of this list.** The four `specs.md` items are fixed or reclassified in the 19 Oct revision (§14). The six `canonical-data-model.md` items are untouched — that document has not been revised, and they remain open against it.

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
2. **`edge_holds_above` belongs to two field groups** (odds and probability, `:309-310`) — **the leak claim is retracted (§13 C4).** Because it is in the probability group, the §6.2 MUST ("a field in a hidden group MUST be null") nulls it whenever probability is hidden, so `b = (1+t)/p` cannot recover a hidden `p`. The real gap was that AC-21/AC-37 named only `entry.edge` and `current.edge`, so nothing tested it; the 19 Oct revision closes that (AC-37 now states "model.probability and edge_holds_above null", and AC-21 adds `action` null and `edge_state` unknown).
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
| X6/X14 live-scores coverage | **Correct** (Part 1 retracted) | `dev` at true remote `11599f1` has `mlb nba nfl shared tests wnba`; NBA added 14 Oct; the README lists three sports (stale) |
| X7 null-edge pass-through | **Refuted** | picks are dropped, not nulled (`nba_wltp.py:307-308`) |
| X8 MLB one-book rule | **Unverifiable** | decision record not locatable |
| X9 WNBA player publish time | **Confirmed** | `wnba_bet_engine@df918025` `_ps_engine.py:191-207` |
| X11 gate per route | **Refuted** | chokepoint gate, `RELEASE_API_VERSION_MAJOR = 6` |
| X12 monitor defers Cosmos final state | **Confirmed** | `EDGE_PICKS_LIVE_ODDS_DESIGN.md:214,222` |
| X13 no observation time sent | **Partly** | `market_last_update` already ships for NBA |
| X14 tst has no live resources | **Confirmed** (Azure) | 5 RGs / 47 resources; dev positive control |
| X14 live-scores `dev` has NBA | **Correct** (Part 1 refutation withdrawn) | see §4.3 and §13 C1 |
| BFF findings at the branch that serves tst | **Confirmed at `main` `9aaae555`** | no `v4/…` route; no ETag/`If-None-Match`/`Cache-Control`; `gate.ts:78` = 6 (file identical in `main`/`develop`); freemium flags; `canonical/picks.ts` serves odds/edge/stake; per-flag stripper |
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

This is a folder of good ideas with a bad evidence base and no owner. The contract is carefully specified and its arithmetic is exact; the canonical model's identity separation and push-aware EV are real improvements; the cutover plan correctly diagnoses the read paths that make coexistence dangerous; the validation plan is the right programme. But 13 of 82 checked claims in the contract are genuinely refuted (four more were requirements misread as claims), concentrated in the rows that carry the hard dates — and the 19 Oct revision fixes 11 of the 13; the model treats a settlement write-back that does not exist as today's behaviour and books its cost at zero; the folder carries two incompatible migration mechanisms and 20 substantive field-level divergences between two documents that both claim to define the same producer contract; and nothing in it has an owner, an estimate or a durable schedule. Approve the direction, close the six conflicts, fix the evidence, pick one migration, and re-plan the dates — in that order. Building from this folder as it stands will produce a system that passes its own acceptance criteria and is wrong in ways the criteria cannot see. **Part 2 updates this for the 19 Oct revision: `specs.md` has moved from "revise" to "GO as the app-facing contract", subject to §15; the other three documents have not changed.**

---

# Part 2 — the 19 Oct revision and the author's rebuttal

`specs.md` was revised and committed on 19 Oct (`53054b6`, 96 insertions / 63 deletions), with a point-by-point rebuttal. This part records what the reviewer got wrong, what the revision fixes, and what is left.

## 13. Corrections to Revision 1

| # | Part 1 said | Status | Evidence |
| --- | --- | --- | --- |
| **C1** | X14/X6 are wrong: live-scores has no NBA module on any branch | **Retracted — the author is right** | `live-scores` `dev` at the true remote `11599f1` contains `nba/` (added 14 Oct). Part 1 read `git ls-tree origin/dev` against a stale local tracking ref (`8757f3f`, 18 Sep) while `git ls-remote` in the same session already reported `11599f1`. The `README.md` still lists three sports, which is what misled the read. X6 and X14 do not contradict each other. |
| **C2** | BFF findings verified at the deploying branch | **Corrected — the author is right** | `prod-deploy.yml` triggers on `push: branches: [main]` and targets `environment: tst`; `develop` → dev, `staging` → stg. Part 1 cited `develop`, which is the *dev* branch. Every load-bearing BFF finding was re-verified at `origin/main` (`9aaae555`) and holds: no `v4/…` route, no `ETag`/`If-None-Match`/`Cache-Control`, `gate.ts:78` `RELEASE_API_VERSION_MAJOR = 6` (that file is byte-identical in both refs), the six freemium flags, `canonical/picks.ts` serving odds/edge/stake, and the per-flag stripper. |
| **C3** | §8.6/AC-17, §6.2's mirror rule and §8.5 "are refuted" | **Reclassified — the author is right** | All three are requirements, not claims about today. They are unbudgeted new work, not false statements. Applied in §4.7; the headline count drops from 17 to 13 genuine refutations. |
| **C4** | `edge_holds_above` can leak a hidden probability | **Retracted — the author is right** | It belongs to the probability group, so §6.2's MUST ("a field in a hidden group MUST be null") nulls it whenever probability is hidden. Only the test coverage was missing; AC-37 in the revision now asserts it. |
| **C5** | "17 refuted" | **Recount: 13 genuine, 2 still open** | Of the 17: four were requirements misread (C3). Of the 13 genuine, **11 are fixed or accepted** in the 19 Oct revision (ids, projection, entry fields, status validator, §9 method, the three §3 availability cells, X7, X11) and **2 remain acknowledged gaps** (the BFF drops cancelled picks — now noted in §3; `is_closing` — already marked "required, not built"). |
| **C6** | *(the author's claim)* the reviewer's app-data clone is stale, so the Publish Engine findings cannot be relied on | **Contested — the clone is current for the deploying ref** | Local `origin/tst-blue` and the remote both resolve to `a1c16f43` (checked 19 Oct). The PE findings were taken at the deploying commit, and the author's own revised X1 and X7 now state the same facts. Independently re-verified at the author's new basis too — `app-data` `dev` `2b6f998` via the GitHub API: no `canonical_transformations.py`; `nba_wltp.py:307-308` filters null-`edge` picks out; `nba_wltp.py:213` `line_token = F.coalesce(line.cast("string"), F.lit("null"))`; `pick_id` built with `concat_ws("|", …)`. |

**What the rebuttal gets right beyond the specific points.** Turning the reviewer's own stale-branch critique back on the reviewer is the correct instinct, and it landed twice out of three attempts. The method lesson is in §3: a fresh `ls-remote` is not evidence about a stale clone, and "which branch deploys" has to be answered per repository (for the BFF: `main` → tst, `develop` → dev) rather than assumed from the branch name.

## 14. What the 19 Oct revision fixes

Verified against the new text; the arithmetic of the new examples was recomputed.

| # | Part 1 finding | Change in the revision | Verdict |
| --- | --- | --- | --- |
| 1 | **The edge formula is wrong for NBA** (the biggest one) | §5.3 now defines both break-evens (`b_ev = (1+t)/p`, `b_prob = 1/(p−t)`), requires each producer to declare its selection basis and *t*, and skips rules 4–5 when `p ≤ t`. §6.1 defines the two bases, makes the card's display basis a D3 decision, and has the BFF convert basis **and units** from `p` and the price. §8.3 adds `edge_basis`/`edge_threshold`; D3 rewritten; E13, D-11 and D-12 added. | **Fixed.** E13 verified: `b_prob` = 1.9230 → `closed` at 1.9000, and on the EV basis `b_ev` = 1.8727 → `narrowing`. D-11 = 0.0562 ✓, D-12 = 0.0500 / 0.1000 ✓. |
| 2 | **§8.2 contradicts itself on ids** | §8.2 rewritten: today's formats are labelled observations and the NBA split-document formats are added; ids are **opaque strings**, may contain `.`, `<`, `|`, are URL-encoded in URLs and **never used directly as RTDB keys**; the overlay key is derived by one shared function whose output is a valid RTDB key; migration keeps old ids resolvable (`legacy_ids`) until slips are rewritten; AC-25 now tests the overlay key. | **Fixed**, with one residual ambiguity — §15.1. |
| 3 | **Rule 3 undefined for null lines** | §5.3 rule 3 now says the rule applies only when both lines are present, and E12 was added (moneyline, price 2.0000 → `live`). | **Fixed.** E12 verified: `b` 1.8181, `m` 1.9091, 2.0000 > `m` → `live` ✓. |
| 4 | **X1/§8.4's status premise** | §8.4 now says the validator list is "reported on an NBA feature branch", that it is not on app-data dev, and what dev actually does (game picks synthesise from the outcome; player picks pass through). X1 rewritten to match, and a new **X15** records the deeper problem: each engine run rebuilds a pick list, so superseded picks vanish. §5.1 gains a **Persistence** paragraph, a `withdrawn` row and a split `cancelled` (engine withdrawal vs cancelled game); AC-8 and new AC-45 cover it. | **Fixed**, and X15 is a genuinely good addition — it is the producer-side statement of the same defect the canonical model fixes with `selection_key`. |
| 5 | **§3 availability key understates what ships** | NBA cells now read "NBA: today" for picked-at, entry odds/line, edge, stake, payout and sort; the cancelled row explains that the BFF drops cancelled picks today and must serve them; projection corrected to "Ask; today the BFF derives projections and drops any producer value". | **Fixed.** |
| 6 | **X11's gate mechanism** | §4.4 and X11 rewritten: the gate is applied in shared document readers, a route reading Cosmos directly inherits nothing and MUST call it, and `api_version` is unrelated to the `/v4` route major. | **Fixed.** |
| 7 | **The method sentence named the wrong branches** | §9 gains a **Basis** paragraph and a per-repository table (dev branch, promotion path to tst, last-checked commit) for all five repositories. | **Fixed** — see §15.3 for the one refinement it still needs. |
| 8 | **Requirements read as claims** | §8.5 and §8.6 now carry explicit observations that the BFF branches on `schema_version` today and that none of the conformance checks exists. | **Fixed** (C3). |
| 9 | **The roadmap citation is not shareable** | The header now says the claude.ai artifact may be unopenable by other teams and that **every phase date is provisional** until it is in Confluence. | **Fixed.** |
| 10 | **Principles had no criteria; principle 3 was false** | Each principle now names its criteria (AC-2, AC-19, 10.3/10.4/AC-35, AC-3, AC-43, AC-44), and principle 3 now permits exactly the recomputation §6.1 allows. | **Fixed.** |
| 11 | **Test gaps** | AC-11 is now falsifiable (names the settings, adds a worked example); AC-21 and AC-37 enumerate the full field set as AC-12 does; AC-43/44/45 added; AC-13 rewritten to the shared key function; AC-8 covers `withdrawn`. | **Fixed.** AC-11's example verified: range 0.55–0.95 leaves 0.80 and 0.70, count 1 unlocks 0.80 ✓. |
| 12 | **D6's key had no lifetime** | D6 now prefers entitlement claims bounded by the token lifetime, and requires any opaque key to expire (HMAC with a daily epoch). | **Fixed** — matches §7.4. |
| 13 | **D2 pre-decided / `line_moved` reason** | D2 now states a line move never cancels a pick, and `line_moved` was removed from `ReasonCode`. | **Fixed.** |
| 14 | **X14's Firebase claim** | Now says whether the tst project has a realtime database, and who owns it, is **not verified**. | **Fixed** — matches the reviewer's own limit. |

## 15. What is still wrong or unfinished in the revised spec

Small, but each one is cheap now and expensive later.

1. **§8.2 still reads as two contradictory rules.** "An id MUST NOT change when the price or line moves" sits beside "An id MUST include the line wherever two picks could share…". They are reconcilable — a new line is a *new* pick with a new id, and the old pick's id is never re-keyed — but that is the canonical model's semantics and §8.2 does not state it. Add the sentence; AC-45 already implies it.
2. **AC-45's gate disagrees with X15's date.** X15's required action says "before 1A ships cancelled status" and §11.1's 1A row promises cancelled status, but the §10.9 conformance matrix gates AC-45 at "each sport's switch to live data". Pick one — and cost it: keeping a record of every published pick with its frozen entry and merging each run into it is real producer work that no phase row currently lists.
3. **§9's Basis paragraph presents dev-branch observations as today's behaviour.** That is the right basis for designing the change, but it is not the branch that serves users: for the BFF that is `main` (prod-deploy → tst). Every finding I re-checked happens to agree across both refs (`gate.ts` is byte-identical), but that is luck, not method. Add a "serves tst" column, or tag each row with the branch it was checked on.
4. **X14 still says "Blocks D1 option A (not A′)" while §11.2 says "Options A and B both depend on X14".** Option B has no source in tst either, so it is blocked too. Fix one of the two.
5. **AC-5 (ETag/304) still gates the app release without appearing in §3's availability key.** Either add it as an unbuilt capability or move it to a later gate.
6. **§5.3's new selection-basis observation is not reproducible from the checkout I hold.** "NBA player picks on a probability edge of at least 3 percentage points" cites dev at 19 Oct; the `nba_bet_engine` clone I have (`dev` `621ab3c1`, 8 Oct) filters the player engine on `edge > 0.0`. Cite the commit, as the branch table does elsewhere.
7. **Unchanged from Part 1 and still open:** AC-28's 35 cells include six unreachable and 21 decorative cells; the branch table's mobile-server row (`develop` at `9573301`, 16 Oct) is already behind (`develop` is `b2431435` today), so the table needs a refresh rule — the same staleness that produced the reviewer's error.

## 16. Recommendation on the proposed fixes

**Yes, apply them** — items 1–9, the `withdrawn` row, the X14 wording and the branch table. The committed revision already covers most of that list; the remaining work is small. Three amendments before publishing:

- **(a) Do not park X1, X7 or the NBA id format as "reported, not yet re-verified."** They are verified at both refs that matter: `app-data` `tst-blue` `a1c16f43` (deploying; local ref equals remote) and `app-data` `dev` `2b6f998` (the revision's own basis). Evidence in §13 C6. Record both commit pins and mark them verified.
- **(b) Fix §8.2's id pair and reconcile AC-45's gate with X15's date before publishing**, or the persistence requirement will be read as 1B work and missed at 1A.
- **(c) Add the "serves tst" column (or a per-row branch tag) to the branch table**, and say in §9 that a dev-branch observation describes the code under change rather than what users receive today.

With those three, `specs.md` is the strongest document in the folder and safe to build the app contract against. The canonical model, the verification plan and the cutover plan still need the §5.2 conflicts closed and the §11 actions — none of which this revision touched.

# Part 3 — the second revision, and two engine findings that change the picture

`specs.md` was revised again on 19 Oct (`4b6b3ab`, 21 insertions / 20 deletions) in response to Part 2. This part verifies the two engine findings the author raised, records what the revision fixes, and states what is left — which is now mostly on the other side of the seam.

## 17. Verification of the two engine findings

Both are real. Both are more precisely scoped than reported, and one of them is narrower and one is broader than the spec implies.

**E1 — the player-pick engine replaces picks per evaluated game (`45f6f4f`, 16 Oct 02:30). Confirmed.** `upsert_delta` gained a `replace_game_sks` argument and applies `whenNotMatchedBySourceDelete(condition="t.game_sk IN (…)")`; the scope comes from `games_in_scope(...)` — games **before the pre-game cutoff** that have *both* odds and projections. So the behaviour is narrower than "each run deletes what it no longer produces":

- a game the run did not evaluate is untouched — past the cutoff it is frozen, and with no odds or projections it is not evaluated at all, so **a feed outage cannot wipe its picks** (the docstring says this explicitly);
- a game the run *did* evaluate loses any row the new output does not contain.

That scoping makes the engine team's rationale visible and reasonable: anti-staleness, outage-safe. It also means the conflict with AC-45 is a **design disagreement with a stated rationale**, not an oversight — and AC-45's own test ("publish a pick, move its line and drop its edge below the threshold in the next run; the pick is still present") is red against it for exactly the re-evaluated case. One more fact the spec should carry: the three 16 Oct commits are **not in `tst`** (tip `0430eb5`, 13 Oct), so the conflict is not yet user-visible — it becomes so at the next promotion, and that, not 23 Oct, is the real deadline.

**E2 — the published player-pick probability is blended toward the market (`0d6a59b`, 16 Oct 03:50). Confirmed, and broader than "product should confirm".** The mechanism: no-vig market probability from the same (game, player, stat, bookmaker, line) pair — raw implied divided by the pair sum, one-sided quotes falling back to `1/odds` — then `w = exp(−|ln(1/p_model) − ln(1/p_market)| / k)`, `p = w·p_model + (1−w)·p_market`, with `k = 1.0` (the POF reference default is 0.5) and a hard drop at a disagreement of 0.30 or more. The published `probability`, `edge = p − 1/d`, and therefore `model.probability` and the break-even `b`, are all the blended value. Two consequences beyond the author's:

- **The blend is strongest exactly where the model disagrees with the market** (`w → 0` as the gap grows), and the largest disagreements are dropped outright. The card's "XO Edge" is no longer a model-disagreement signal; it is a market-corroborated price-shopping signal with a capped disagreement. That is a product-positioning question, not a display-basis one.
- **The 0.30 cap is not expressible in the producer contract.** §8.3's `edge_threshold` cannot describe it, so no consumer — and no validation rule — can reproduce why a pick exists from the published fields.

**E3 — the 3 percentage-point floor (`8cba698`, 16 Oct 03:56). Confirmed, and my §15.6 challenge is resolved.** The floor arrived on 16 Oct, exactly as the author said; my clone was at 8 Oct. Two details the spec should carry:

- it is implemented as the lowest **staking tier** (`PS_TIER_THRESHOLDS`, lowest `(3.0, 1, 1.0)`) with `.where(tier > 0)`, so the selection floor and the stake ladder are one table — a staking change silently moves which picks exist;
- the game-pick engine is unchanged: `_wltp_engine.py:633` still selects on `edge > 0.0`, so §5.3's two statements ("NBA game picks above 0, NBA player picks at least 3 percentage points") are both accurate, verified at the engine rather than inferred.

**E4 — my clone, again. Acknowledged.** `nba_bet_engine` `dev` is locally `621ab3c1` (8 Oct) against a remote `362fb7e2`. §15.6 said the claim "is not reproducible from the checkout I hold" and asked for a commit pin, which was the right hedge — but the cause was a stale clone for the third time in two rounds (live-scores, mobile-server, now nba_bet_engine). That pattern is the strongest argument for the revision's own rule: re-read a row from a fresh fetch before a gate relies on it.

**E5 — AC-28. Conceded.** A settled pick on a game that is not final is reachable when the outcome and live-score feeds lag each other, and §5.4's first-match rules give a deterministic rendering, so the criterion tests something real. My "six unreachable cells" assumed a single consistent source. The revision's wording is the right fix.

## 18. What the second revision fixes

All seven §15 items and §16(a) are in: §8.2's clarifying sentence; AC-45's own conformance row; the §11.1 1A note; the "Serves tst (production) from" column with per-repository commits and the dev-observation caveat; X14 and the conformance matrix at "options A and B (not A′)"; the §4.5 ETag observation; the `8cba698` pin plus the blended-probability record; X1 pinned to `tst-blue` `a1c16f4`; and AC-28's rationale.

It also closes the remaining spec-side cross-document conflicts: **D5 now recommends the canonical model's R3 vocabulary**, §8.1 defers the document layout to the decision record, and §11.1's 1B is per-league. That is **all six conflicts in §5.2 closed on the spec side**. What remains is that the decision record does not exist yet, and the other three documents have not been revised.

## 19. What is still open

1. **AC-45 is red against the current NBA player engine, and §11.1 still promises cancelled status on 31 Oct.** The revision records the conflict in X15 and notes the published-pick record is not in the roadmap — but the 1A row still *delivers* cancelled status. Make it conditional in that row (delivered when X15 lands) or move the card treatment to 1B. As written, 1A's date depends on a cross-team reversal of a three-day-old deliberate change.
2. **A′'s current edge needs a definition, not a disclaimer.** §5.3 now says a BFF-derived current edge "can differ from the engine's own re-evaluation". True — and it will differ in **both** directions, because the BFF holds `p` at the entry blend while the engine re-blends toward the market at the new price (and re-applies the 3% floor and the 0.30 cap). Two honest options: define the A′ current edge as a *contract quantity* — frozen entry `p` × current price, labelled as such — or wait for the engine's own value through the X12/1B path. What must not ship is an unexplained divergence at the `edge_state` boundary, where the card reads `live` while the engine's own re-evaluation would read `closed`. That is the headline feature being wrong, not a rounding difference.
3. **The blend changes what "Edge" means on the card** (§17 E2). D3's new sentence asks product to confirm the card may show a blended probability; the larger question is whether an edge that is pulled toward the market, and capped at 0.30 disagreement, still supports the redesign's "still in play" framing.
4. **The 3% floor is a staking tier** (§17 E3). Record the coupling so D14's cancel thresholds and any future stake change know they move the selection boundary.
5. **The 0.30 disagreement cap has no field** (§17 E2). Add one, or state that not every selection rule is expressible; otherwise the validation plan's `PRB` family ("the entry satisfies its own `selection_rule`") cannot check it.
6. **X15 needs the engine team's *reason*, not just agreement.** The docstring shows a deliberate anti-staleness, outage-safe design. The persistence rule should answer it in the engine's own terms — keep the pick and mark it `cancelled` with a reason, which is what the card wants and what AC-45 tests — rather than assert that the engine must merge.
7. **Minor:** the branch table's `tst` commits are promotion state, not evidence. `nba_bet_engine` `tst` at `0430eb5` (13 Oct) means the two engine findings are dev-only; X15 should say so, so nobody reads the AC-45 conflict as live behaviour.

## 20. Verdict after the second revision

| Document | Status | Condition |
| --- | --- | --- |
| `specs.md` | **GO as the app-facing contract** | Three conditions: reconcile AC-45 with §11.1's 1A promise; define the A′ current edge (or gate it on the engine's own value); open the engine-team conversation with the promotion date as the deadline. |
| `canonical-data-model.md` | **Unchanged — direction GO, build NO-GO** | Cost the settlement write-back; accept §8.1's deferral and settle the decision record; keep `legacy_ids[]`. |
| `canonical-data-verification-plan.md` | **Unchanged — NO-GO as written** | Cut to a v1 or fund it as a programme; the 0.30 cap is a fresh example of a rule that cannot be checked without a producer field. |
| `coexistence-cutover-plan.md` | **Unchanged — GO as the migration design, NO-GO as a runbook** | Owners, dates, a production one-family invariant check, and a rollback trigger. |

The spec has converged faster than the rest of the folder, and its remaining risk has moved from *documentation* to *coordination*: the two engine findings are disagreements with another team, and the decision record it now defers to three times does not exist. Neither is fixable inside `specs.md`.

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
