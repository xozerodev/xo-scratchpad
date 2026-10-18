# Semi-SDUI ("server-driven content, native layout") — independent assessment

Oct 17, 2026 · Lead synthesis · assesses `SDUI/sdui-proposal.md` (commit `e9244ec`, "XO Mobile Data Lineage & SDUI Assessment", 320 lines)

**How to read this.** Section 1 is the decision. Sections 2–3 say how the review was done and what survived. Section 4 is the finding that changes the plan. Sections 5–8 are the evidence in detail, the design objections, the risks and the sequencing. Section 9 is what to do next. Every factual statement traces to one of the four verification files in `reviews/` or to a named section of a source document.

---

## 1. Verdict

**The direction is right and the diagnosis is largely confirmed. The plan as scoped should not be approved yet — three conditions (Section 9) move it to a clean approval; if the first two are refused, it should be rejected.**

Three findings decide this:

1. **The pilot premise is false.** The proposal's BFF section is built on `/v4/edge-picks` — "the one contract that already composes labels server-side, declares field groups and access, and validates at runtime" (`sdui-proposal.md:219`). That route does not exist: not at the cited commit, on any of the 37 remote branches, or at today's `develop` tip; `EDGE_PICKS_SOURCE`, `loadLiveEdgePicks`, `edge_threshold` and `overlay_key` appear nowhere in `mobile-server` or GitHub code search (Lead-verified independently). There is also no `EdgePick` type in the app. The only Edge Picks v4 artefact in existence is the specification `edgepicks-redesign/specs.md`. The Edge Picks pilot is therefore **greenfield work against a spec, not "wiring, not design"** (`sdui-proposal.md:219`).
2. **The architecture is sound but the seam has no contract.** "Server-driven content, native layout" is the correct cut, and `{value, display}` at the BFF→app boundary does **not** contradict the v4 contract — specs.md's "no display copy" rule binds producers, not the BFF (`specs.md:22,42`). But per-component `props` remain an open bag, so the "no generic layout DSL" line (`sdui-proposal.md:129`) is prose only: nothing stops the next prop being `padding` or `fontSize`. With no payload `registry_version`, no capability-aware cache key, no per-section failure state and no release-free rollback, a server-side mistake reaches 100% of users with no escape hatch.
3. **The diagnosis is real and, if anything, understated in places.** Display decisions are duplicated across four layers; `api_version` really is triple-purposed; the Publish Engine really has no validation, swallows Cosmos write failures ("errors += 1") and still ignores CDF deletes for every transform except `player_top_picks` — defects the new NBA canonical path inherits; the app really does discard the `api_version` and `enabled_leagues` the BFF already sends. The proposal's 13 defects are real (7/7 app rows confirmed at the exact cited lines, plus BFF, PE and live-odds rows).

**Recommended shape of an approval:** codegen first, then a **content-only** runtime payload; keep the league release gate beside capability negotiation; merge the Edge Picks pilot into the specs.md app release rather than running a second one; redefine Gate C. Concretely, "semi-SDUI" should mean *copy, locks, section order, league visibility and asset keys from the server; component identity and props compile-time* — not server-chosen components in Phase 1.

---

## 2. How this assessment was made

Four independent tracks, ~130 claims, each with a verdict (Confirmed / Partly / Refuted / Unverifiable), pinned to a branch and commit, with the counting method published beside any count.

| Track | File | Evidence base |
| --- | --- | --- |
| App (mobile-app) | [01-app-verification.md](../reviews/01-app-verification.md) | `main` `ca9cf8f0` (the cited commit), diffed against `main` tip `137f2f61` and `develop` tip `0e4f686d` |
| BFF + Publish Engine | [02-bff-pe-verification.md](../reviews/02-bff-pe-verification.md) | mobile-server `develop` `95733012` (tip `b2431435`); app-data `dev` `2b6f998` **and** production-serving `tst-blue` `a1c16f4` |
| Live overlays / transport | [03-live-overlay-verification.md](../reviews/03-live-overlay-verification.md) | live-odds `dev` (remote `30e05ce`); live-scores remote `dev` `11599f1`; Firebase + Microsoft primary sources |
| Design fit | [04-design-fit-review.md](../reviews/04-design-fit-review.md) | the five documents in this repo (proposal, specs.md, canonical v3, validation plan, cutover plan) |

**Evidence limits, stated plainly.**
- The DSH sandbox makes the estate clones read-only, so `git fetch` fails on `FETCH_HEAD`. Heads and tips were read with `git ls-remote` and the GitHub REST API; content came from local objects (app-verifier additionally built a bare store under `.verify/` with the clone as an `alternates` source to reach the cited commit). Nothing in the estate was modified.
- The scratchpad `xo-scratchpad` **was** pulled to `14d60c8` before this review began — that is where the SDUI proposal and its three sibling documents came from.
- `main` is not established as *the* app shipping branch: the repo has no release automation binding a build to a branch, both lines carry release tags, and `develop` is the default and leads on Android versionCode. Every load-bearing file the proposal cites is byte-identical at `ca9cf8f0`, `main` tip and `develop` tip, so the findings do not depend on resolving that.
- Live-scores evidence is a point-in-time read of remote `dev` `11599f1` (the local `origin/dev` is 25 commits stale), not a local object.
- External claims (Firebase limits/pricing, Web PubSub limits/pricing, Front Door) were checked against Firebase docs, Microsoft Learn and the Azure Retail Prices API; the proposal's flagged third-party Web PubSub figure turned out to be correct.
- **Lead spot-checks** reproduced, independently of the track owners: the absence of any v4 edge-picks route and symbols across the estate; live-odds' `tst_nfl` catalog default, the `next_update_due` omission at its only production call site, and `edge_status` never emitting `unknown`; the app's `AppConfigContext` hardcodings; the absence of an `EdgePick` type; and the `MyPicksItem` void-as-win ternary.

**Track scoreboards** (rows checked, not opinions): app 36 C / 4 P / 1 R / 1 U (plus 7/7 defect rows confirmed); BFF 15 C / 3 P / 5 R / 0 U; Publish Engine 17 C / 4 P / 0 R / 1 part-U; live + transport 38 C / 5 P / 0 R / 1 U (+2 sub-claims); design review: 8 positions, 14 contradictions, 14 open questions (no code verdicts by design).

---

## 3. What holds up

- **The four-layer duplication diagnosis is confirmed.** The app rebuilds player-prop labels from an NBA-only stat map (`playerPropLabel.ts:1-11,105-123`), reformats odds by region (`utils/odds.ts:32-46`), recomputes `combinedProbability` (`PickGroupCard.tsx:64-67`) and wagers (`TopPickCard.tsx:98-103`); the BFF composes status words, section titles and odds (`match/common.ts:56-57`, `top-pick-utils.ts:12,93,120`); the Publish Engine writes display vocabulary into documents (`"Final"/"Scheduled"/"Canceled"`, `"passing yards"`, `%.2f` strings, NFL top-N) and the new NBA module adds more (`OUTCOME_STATUS_MAP`). One decision, several owners — exactly the problem.
- **`api_version` is genuinely overloaded** with three axes in one parameter (leagues: v4 EPL, v5 NFL; response shape: v4 sectioned rosters, v5 split locks; staged-season release: `RELEASE_API_VERSION_MAJOR = 6`), and the documented `minApiVersion` league registry is not built (`src/lib/leagues` is empty).
- **The Publish Engine is not a safe producer today, for any league.** No schema validation (66 literal column-presence checks, no tests); Cosmos write errors caught into a counter while the batch commits; CDF deletes discarded for every transform but `player_top_picks`; last-write-wins within a batch with two MLB tables writing one document; prose-only contracts with doc/code drift. The NBA canonical transforms share the same pipeline cell, so they inherit all of it — "not assessed" (`sdui-proposal.md:71`) understates the exposure of the newest production path.
- **The app is a thick client that ignores the server** — verified at the exact lines: `AppConfigContext.tsx:44,49` replace `api_version` with `"v6"` and `enabled_leagues` with a bundled list; `resolveApiVersion()` is dead code; `locks.upgrade.cta`, `subscription_features` and `freeTrialDays` are parsed and dropped. 127 bundled logos and 128 abbreviation keys are exact counts; the catalogue's reuse inventory (cards, tabs, filter bar, status badges, lock/blur, a player table already driven by `predicted[]`/`sections`) is real.
- **The 13 defects are real, and Phase 0's "fix the defects first" is well founded.** App 7/7 confirmed at the cited lines, including the `EXPO_PUBLIC_` entitlement-invalidate key shipped in the bundle (server-side blast radius), the calendar that ends 31 Dec 2026, void (`2`) rendered as a win, game outcome overriding per-pick results, the missing-status default of "Completed", edge-pick blur reading `locks.topPicks`, and the share text attaching scores to the wrong team. BFF: team-colour lookup proven end-to-end to return Celtics green for every Title-Case team on list cards; push copy "We went 4/6 today… $X" verbatim. PE: silent loss and delete blindness as above. live-odds: `DATABRICKS_CATALOG` defaults to `tst_nfl` (the production-serving catalog) when unset.
- **The transport analysis survives, and the proposal was too modest about its own numbers.** Firebase facts (200k connections/database, 360 MB/day then $1/GB, 3.5 KB handshake, rules cannot revoke at a child path, 1-hour ID tokens) and the Web PubSub facts ($1.61 per Standard unit-day, $1 per 1M messages, per-recipient broadcast billing) all check out against primary sources; Front Door is correctly ruled out twice (no SSE; 3,000-connection/2-hour WebSocket cap). The 3–9× cost claim holds and RTDB is cheaper in every modelled row. Two arithmetic corrections favour Azure, not Firebase: the Web PubSub column is priced at ~62.5% utilisation while the table says 80%, and its implied unit counts (8, 32) are not purchasable Standard/P1 counts (nearest allowed: 10 and 50, i.e. $489 and $2,447/month).
- **The seam and the refusal of a layout DSL are the right calls**, and principle 6 ("one contract, generated") is the same instrument the canonical v3 model already commits to (registry → Spark schemas, JSON Schema, TypeScript, app config, golden fixtures). SDUI is an increment on committed work, not a parallel investment.
- **The proposal's own honesty points are real**: the v3-document dependency is stated, over-reach is named as the main risk, and the overlay transport is left open with a stated revisit trigger.

---

## 4. The finding that changes the plan: the pilot route does not exist

| Claim in the proposal | Verdict | Evidence |
| --- | --- | --- |
| `/v4/edge-picks` exists (`sdui-proposal.md:11,99,223`) | **Refuted** | No such route in `mobile-server` at `95733012`, on any of 37 remote branches, or at the 16 Oct `develop` tip. Route registrations are `match/{id}`, `matches/{date}`, `matches/{date}/top-predictions`, `my-picks*`, `v3/*`. Every `/v4/...` string in `src/` is Qonversion's external API. Lead-verified. |
| `EDGE_PICKS_SOURCE=live` returns 503 because `loadLiveEdgePicks` throws (`:99`) | **Refuted** | Neither symbol exists anywhere; GitHub code search 0 hits. |
| Its zod schema uses `edge_threshold` and omits `overlay_key` (`:99,224`) | **Refuted** | Neither identifier exists in the repo. The terms are from the *spec* (`specs.md:108,125`). |
| "The full `EdgePick` v4 type exists but nothing imports it" (`:117,225`) | **Refuted** | No `EdgePick` type, no `EdgePickSport`, no `field_groups`/`overlay_key` text at `ca9cf8f0`, `main` tip or `develop` tip. Only `EdgePicksTypeFilter` (a UI filter union) and `blurEdgePicks`. Lead-verified. |
| "The work left is wiring, not design" (`:219`) | **Unsupported** | Six of the seven pilot rows are unbuilt: live adapter, contract alignment, app renderer, all-sport monitor, RTDB client + rules, PE history reader (`:223-229`). Only "producer documents" has a partial path (NBA). |

**Consequences.** (a) The pilot's cost, sequence and risk are all larger than the proposal states; it is the first implementation of a contract, not the last mile of one. (b) The §"Edge Picks redesign fit" argument — "it is the one contract that already composes labels server-side… and validates at runtime" — loses its factual basis; the *case* for piloting on Edge Picks survives on different grounds (it is the screen being redesigned anyway, and specs.md is the most complete contract in the estate). (c) Anything built on this premise inherits a schedule risk that is invisible in the document.

**Action:** before this proposal is circulated further, ask the author where the described implementation lives. If it exists outside this estate (a branch, a fork, an environment), cite it; if it does not, correct §"BFF (mobile-server)" and the pilot table, and re-baseline the pilot as greenfield.

---

## 5. Where the proposal overstates or is incomplete

| # | Proposal says | Correction | Why it matters |
| --- | --- | --- | --- |
| 1 | Pilot is wiring (`:219`) | Greenfield (Section 4) | Cost, sequence, staffing |
| 2 | 37 app decision points, NBA-heavy (`:63`) | ~66 league-conditional sites (~45 excluding style-only), EPL-heavy | The status quo is worse than stated; the per-league split is not reproducible |
| 3 | 57 BFF league branches in 10 files (`:62`) | 40 branch sites in 9 non-test files (a 60/10 count includes type declarations) | Direction right, number not reproducible |
| 4 | "438 source files" (`:313`) | 513 files under `app/` (437 non-test code) | Citation hygiene |
| 5 | 65 column-presence checks, 13 start-version overrides (`:61`) | 66 checks; 12 overrides at the cited commit, 6 today (legacy entries replaced, not extended) | The legacy tables have lost their overrides |
| 6 | PE canonical path "not assessed" (`:71`) | The canonical transforms share the same write path and inherit silent loss + delete blindness | "Not assessed" understates the newest production path |
| 7 | Rescheduling writes a second document everywhere (`:290`) | Fixed for NBA today (synthetic partition deletes); still true for legacy `transform_game_data` per its own TODO | A live defect claim that is now half-fixed |
| 8 | Web PubSub column "sized at 80%" (`:242,252`) | Effective ~62.5%; implied units not purchasable | The error favours the proposal's own recommendation, which invites attack |
| 9 | Access "as v4 edge picks already does" (`:133`) | v4 does not exist; production freemium is a key-name denylist whose own comments record three leaks | The reusable asset is real but weaker and coarser than claimed |
| 10 | Capability negotiation "retires the `api_version` majors" (`:131`) | It replaces one of three jobs; league visibility and staged-season withholding have no replacement, so specs.md AC-6 and X11 become unsatisfiable | A compliance gate silently disappears |
| 11 | College leagues "could ship with no app release" (`:191`) | Only after six client prerequisites (`:193-200`), each a release; Gate C then means prerequisite release + zero further releases | Otherwise Gate C cannot fail honestly |
| 12 | ~500 college teams "in the registry" (`:215`) | Teams are reference data, not registry (canonical v3), and 495 logos are curation + licensing with no owner or date | Wrong artefact named; asset licensing is a merge blocker |
| 13 | Live overlays "built" (`:12-13`) | Server-side writers exist; no client package, no security rules, `next_update_due` never written, game-pick ids cannot match the Cosmos rule, discovery is once a day, tst settings are `TODO-` | The overlay half is unstarted end-to-end |
| 14 | PE "not the only writer… laptop injector" (`:80`) | In-repo seeders confirmed; live-scores is another repo; "laptop injector" has no evidence | Unverifiable, should be marked as such |

Two further gaps are absences rather than errors, and they are the ones a decision-maker will feel: **no payload budget** (specs.md has no paging and expects on-device sort, while SDUI's Phase 2 wants cursors and server grouping) and **no named owner or date anywhere** ("phase lengths depend on team capacity", `:272`), where every sibling document carries both.

---

## 6. Design objections (adopted from the design review)

1. **The seam is right; its contract is missing.** `props` is open, so the no-DSL guarantee is unenforceable. Fix: per-component props schemas in the registry, plus CI rejecting style/spacing/colour/animation keys.
2. **The failure mode is new and uncovered.** An unknown component, unknown prop or unknown payload major has no stated behaviour, where specs.md at least defines neutral fallbacks for unknown enum values. "No app release" is only safe if old builds degrade predictably.
3. **Caching and traceability.** The payload carries no `registry_version`, and the ETag/cache key does not include the negotiated capability set or registry version — so a defect cannot be traced to the payload that caused it, and a stale payload can be served to a build it was not composed for. Composition must also be deterministic or the ETag churns every 60 seconds.
4. **Governance and blast radius.** A bad registry or composition change reaches every user on the next request, including builds the server cannot roll back; copy arrives as a `display` string with no client fallback. Needed: per-league/per-screen composition flag defaulting off, registry revert without an app release, version-mismatch alerting, and an agreed deprecation window for component versions.
5. **One repository, two ownership models.** The proposal gives all of `xo-contracts` to platform; canonical v3 gives `leagues.yaml` and `messages/` to product (with product approving every user-visible string) and sport profiles/stats to sport owners. Registry v1.0 is due 23 Oct for the canonical work.
6. **Capacity is four programmes on the same people, and the proposal names none.** specs.md X1/X11/X12/X14, cutover C2/C3 (which explicitly puts SDUI downstream of the BFF's one internal model), canonical v3 phases 1A/1B/2 with dual-publish, and SDUI Phase 0/1 all land on the same BFF, data-engineering and platform teams.
7. **Gate C is not a fair test.** It bundles feeds, models, bet-engine output, reference data, asset licensing and compliance into one binary; NCAAB is the easiest case (same sport profile) and tests neither a new sport nor a new market. Redefine it as the *second* league after the six prerequisites, with the other workstreams owned and scheduled separately.
8. **Unaddressed at the seam:** accessibility (the app has 41 a11y usages, none on content cards), analytics (72 `log*` helpers fired from inside the components being replaced), experiment attribution, offline (see the disagreement below), i18n authority between the app's 9 locales and registry messages, and `actions` naming a native route from the server without an allowlist.

**One disagreement between reviewers, surfaced rather than averaged.** The design review says offline regresses silently when art and labels move server-side. The app verification shows the app has **no query persistence and a 10 s timeout**, so a cold offline start already renders nothing; the regression is narrower and real nonetheless — a *warm* screen keeps its payload but loses the bundled art and labels that today make it legible, and entitlement state in a cached payload can contradict a fresh purchase. Plan for a cached last-known-good payload plus bundled fallback art, not for "offline is unchanged".

---

## 7. Risks, with owners

| Risk | Evidence | Owner | Before |
| --- | --- | --- | --- |
| No RTDB security rules exist anywhere in the estate; the only documented ruleset grants `.read: auth != null` at the root, and under it `/edgePicks` has no grant at all (default-deny) | live-verification §B5–B6 | Monitor owner + app team (specs.md D6) | Overlays reach users |
| Overlay keys are predictable (`{league}_{pick_id}`, ids derivable from the payload); no opaque `overlay_key` exists | live-verification §A15 | Monitor owner + BFF | Overlays reach users |
| Game-pick overlay ids (`{bet_id}\|{region}`, uppercase) cannot match the Cosmos `_au` rule; `next_update_due` never written; discovery once a day at 06:00 UTC | live-verification §A6–A9 | Monitor owner | Overlays reach users |
| PE writes can be lost silently while the checkpoint advances; CDF deletes ignored; newest NBA path inherits both | BFF/PE verification §P12–P13 | Data engineering | Any SDUI screen reading PE output |
| Pilot route and contract do not exist; the app has no v4 types | Section 4 | BFF + app | Pilot start |
| Release gate (AC-6/X11) has no replacement under capability negotiation | design review CT-4 | BFF + product | Any retirement of `api_version` majors |
| Registry ownership conflict and unassigned copy-review throughput | design review CT-11 | Platform + product | Registry v1.0 (23 Oct) |
| Four programmes, one set of teams, no capacity statement | design review §3.4 | Programme lead | Phase 0 kickoff |
| Confirmed user-visible defects shipping today (entitlement key in the bundle; calendar ends 31 Dec 2026; void shown as a win; team colour; push copy) | app verification D1–D7; BFF/PE §B20–B21 | App + BFF | Independent of SDUI |

---

## 8. What this means for sequencing

The sibling documents already fix the calendar that SDUI must fit:

- specs.md: Phase 1A on 31 Oct (NBA 2026 documents, additive fields, **no v3 dependency**); 1B on 1 Dec; D1 (does Market Movement ship at launch) due 23 Oct.
- Canonical v3: decide by 23 Oct; 1A 31 Oct; 1B 1 Dec (WNBA/MLB v3, NBA dual-publish); NFL/EPL Phase 2 Dec–Jan.
- Cutover: BFF ships v3 readers **before** any producer writes v3 (C2); one internal model that every response shape — explicitly including "later SDUI screens" — renders from (C3); NBA's flip follows the Edge Picks v4 live launch.
- SDUI: no dates, and a dependency on v3 documents that arrives between 1 Dec and January.

The honest reading: **SDUI is downstream of cutover C3, not parallel to it**, and its Edge Picks pilot should be the *same* app release as the specs.md Edge Picks work, not a second one. Anything else pays twice for one screen and competes for the BFF and data teams while the canonical transition is in flight.

---

## 9. Recommendation and the three conditions

**Approve the direction; rework Phase 1. Conditions 1 and 2 are gating; condition 3 is the sequencing that makes it deliverable.**

**Condition 1 — Make the seam a contract.** Per-component props schemas in the registry with an enforced no-style/no-layout-key rule; `contract_version` **and** `registry_version` on every payload; a cache/ETag key that includes the negotiated capability set and registry version; deterministic section ordering; an explicit per-section state (`ok` / `degraded` / `unavailable`) so "empty day" and "BFF failure" are distinguishable; a written list of the specs.md ownership rows that move (odds formatting, sort/grouping, AC-6/X11); and neutral-fallback behaviour for an unknown component or prop.
*Without this, it is an interpreter with an open props bag and an untraceable payload.*

**Condition 2 — Keep the release gate, and define release-free rollback.** Capability negotiation is added **beside** the league release gate, with a named replacement for league visibility and staged-season withholding so AC-6 and X11 stay satisfiable; every copy/composition change is revertible without an app release (per-league/per-screen flag defaulting off, last-known-good copy, registry revert, version-mismatch alerting); `actions` route names come from an allowlist.
*Without this, one PR can put a wrong paywall CTA in front of every user with no way back.*

**Condition 3 — Sequence and staff it.**
1. **Phase 0 — registry + codegen, merged with the canonical v3 `xo-contracts` work**: registry v1.0, generated TypeScript and app config, golden rendered-copy fixtures, registry CI. Fix the confirmed defects first (they are cheap and independent).
2. **Phase 1 — Edge Picks v4 live, inside the specs.md app release**: the runtime payload carries **content only** — sections, order, copy, locks, asset keys — with component identity and props compile-time. This is what "semi-SDUI" should mean in the first release.
3. **Phase 2 — generalise** to server-chosen components for the screens that need it, once the props contract, rollback and metrics exist.
4. **Gate C** = the *second* new league after the six prerequisite client capabilities, with reference data, assets/licensing, compliance, feeds/models and PE documents costed and owned separately.

**In parallel, correct the proposal:** the §"BFF (mobile-server)" v4 claims and the app `EdgePick` claim; the Web PubSub column (state 80% and purchasable units); Gate C's wording; the college "no app release" claim; and add owners, dates, success metrics (new-league lead time, releases avoided, payload size p95, contract-validation failure rate) and phase exit criteria in text rather than in an embedded graphic.

**Outcome if approved this way:** XO gets the release-free changes that matter (copy, locks, league visibility, section order, asset keys) on top of work the canonical model already requires, without betting the redesign on a runtime component interpreter, and without retiring a compliance gate to do it.

---

## 10. Questions to put back to the author

1. Where does the `/v4/edge-picks` implementation described at `sdui-proposal.md:99` live? If it exists, cite the branch; if not, the BFF section and pilot table need correcting.
2. Which of `main`/`develop` is the release line (the repo does not say), and does the pilot target one of them?
3. Is Phase 1 the same release as the specs.md Edge Picks app release (AC-1…AC-12, D-9/D-10, AC-23, AC-27…AC-29, AC-39, AC-42), or a second release of the same screen?
4. Is `xo-contracts` one repository with one owner (platform, as the proposal says) or the canonical model's split (product owns `messages/` and `leagues.yaml`, sport owners own profiles and stats)?
5. What replaces `enabled_leagues` and staged-season withholding once the `api_version` majors are retired?
6. Is specs.md D6 resolved as opaque per-pick keys or entitlement claims — and who derives the key on the monitor side?
7. What is the payload size ceiling for a day screen, and what happens on a slate that exceeds it?
8. Who is on the critical path for the registry, and how many people for how long?

---

## Evidence index

- Proposal: [sdui-proposal.md](sdui-proposal.md) · Edge Picks v4 contract: [specs.md](../edgepicks-redesign/specs.md) · Canonical model v3: [canonical-data-model.md](../edgepicks-redesign/canonical-data-model.md) · Validation plan: [canonical-data-verification-plan.md](../edgepicks-redesign/canonical-data-verification-plan.md) · Cutover plan: [coexistence-cutover-plan.md](../edgepicks-redesign/coexistence-cutover-plan.md)
- Verifications: [app](../reviews/01-app-verification.md) · [BFF + PE](../reviews/02-bff-pe-verification.md) · [live overlays and transport](../reviews/03-live-overlay-verification.md) · [design fit](../reviews/04-design-fit-review.md)
- External facts were taken from Firebase pricing/billing/limits/security-rules docs, Microsoft Learn (Web PubSub billing model, Front Door WebSocket) and the Azure Retail Prices API; URLs are listed in the live-overlay verification.
