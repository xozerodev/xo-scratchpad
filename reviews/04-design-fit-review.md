# 04 — Design-fit review: "semi-SDUI" (server-driven content, native layout)

Oct 17, 2026 · design-reviewer (task-4) · architecture review, not code verification

**Question:** does the SDUI proposal's design hold up against the Edge Picks v4 contract, the v3 canonical model, the validation plan and the coexistence/cutover plan?

**Documents read in full** (citations below are `file:line` shorthand):

- [sdui-proposal.md](../SDUI/sdui-proposal.md) — the proposal (320 lines)
- [specs.md](../edgepicks-redesign/specs.md) — Edge Picks v4 app-first data contract (654)
- [canonical-data-model.md](../edgepicks-redesign/canonical-data-model.md) — XO Canonical Data Model v3 (746)
- [canonical-data-verification-plan.md](../edgepicks-redesign/canonical-data-verification-plan.md) (171)
- [coexistence-cutover-plan.md](../edgepicks-redesign/coexistence-cutover-plan.md) (120)

**Out of scope:** verification of the proposal's code claims (owned by the app, BFF/PE and live-overlay verifiers). Where I cite repository files below (`mobile-app/app/...`) it is read-only grounding for a design position, not a verification, and I say so where it appears.

**Verdict at a glance:** **approve with conditions — approve the seam and the direction, reject the plan as scoped for Phase 1.** The seam is the right one and the diagnosis is correct; the plan contradicts the live contract in four places it never names, rests on artefacts already scheduled elsewhere, and has no governance, rollback, metrics or exit criteria in text. Three conditions in §8 would move this to a clean approval; if the first two are not accepted, it becomes a reject.

---

## 1. The seam: where it is, whether it holds, and what breaks at it

### Position 1.1 — The seam is in the right place, but only half of it is specified.

The seam is the `sections[]` envelope: `id`, `component@N`, `title`, `props`, `access`, plus a top-level `actions` map (sdui-proposal.md:138-159). That is the correct cut — it is the same cut specs.md already makes for one screen (specs.md:106-155), generalised to all screens.

But the actual coupling between BFF and app lives in the **per-component props schema**, and none exists. The sketch's `props` is an open object (sdui-proposal.md:145-155); the catalogue names 15 components and what they replace, not what they accept (sdui-proposal.md:161-176). `stat_table@1` already carries `columns[{key,label,tooltip}]` chosen server-side (sdui-proposal.md:155) — that is table layout, not content. With no props schema, the next prop can be `padding`, `fontSize` or `animation` and nothing in the contract, the registry or CI marks it as a change of kind. Compare specs.md, where every field has a type, a nullability rule and an owner (specs.md:106-155, :51-76), and canonical v3, where a rule that no generated validator checks "is a comment, not a contract" (canonical-data-model.md:33). **The proposal is right about the seam and incomplete about the thing that makes it a contract.**

### Position 1.2 — The line against a layout DSL is held in prose, not in the contract.

Principle 1 says "there is no generic layout DSL" and allows only a small fixed set per component, e.g. `pick_list` as `list` or `carousel` (sdui-proposal.md:129). Nothing enforces it. Because props are free-form and versioned only by a component major, a layout DSL can arrive one prop at a time without any contract change, review gate or version bump. The proposal's own risk list names over-reach as a risk (sdui-proposal.md:297) but supplies no mechanism against it. The mechanism that would hold the line is cheap and missing: props schemas in the registry plus a CI rule that props may not contain style, spacing, colour or animation keys.

### Position 1.3 — "Native layout" understates what the server controls; `actions` is the weak part of the seam.

The server picks **component identity and order** (sdui-proposal.md:129), **section composition**, **table columns** (:155) and **annotation content** (:197). What remains native is styling, animation and interaction. That is a defensible split, but "content vs layout" mislabels it: the app's freedom is thinner than "native layout" implies, and a bad structural choice now needs a server change to fix. The app team should price that loss explicitly.

Worse, `actions` (`{"open_paywall": {"type": "native", "route": "Paywall"}}`, sdui-proposal.md:157) plus `access.upgrade.action` (:153) is already a **navigation DSL**: the server names a native route. specs.md deliberately keeps behaviour out of the contract (specs.md:43, "Business rules: edge, state or status logic"; :42 BFF "must not recompute"). A server-composed route name is a new attack and QA surface (see §7.6) and needs an allowlist, not a free string.

### Position 1.4 — What breaks at the seam, item by item.

| Seam concern | Position | Evidence |
| --- | --- | --- |
| **Offline** | Regresses silently and is not discussed. Today 127 logos are bundled, so a cached screen renders offline (sdui-proposal.md:115). Principle 4 moves logos, league icons and backgrounds to Front Door (sdui-proposal.md:132), so offline screens lose art unless the image cache holds it, and a cached payload can contradict the user's current entitlement (locked/unlocked). The word "offline" appears in the proposal only about the Firebase client's cache (sdui-proposal.md:246). | sdui-proposal.md:115, :132, :246 |
| **Caching / ETag** | specs.md has a complete policy — ETag over everything but `generated_at`, 304, cache keyed on date/offset/sport/region/tier/`api_version` (specs.md:187), AC-5 (:486), AC-27 (:564). SDUI adds **two cache-key dimensions no document names**: the negotiated capability set and the registry/message version. Without them a payload composed for build N can be served to build N−1 and vice versa. And the payload carries no `registry_version` (sdui-proposal.md:140) although every v3 document does (canonical-data-model.md:300) and Gate 3 compares rendered copy to golden fixtures (canonical-data-verification-plan.md:17). Consequence: a copy defect cannot be traced to the payload that caused it, and rollback cannot be targeted. | specs.md:187; sdui-proposal.md:140; canonical-data-model.md:300 |
| **Deterministic composition** | Not stated, and it is a hard requirement: if section order or map iteration is non-deterministic, the ETag churns on every request and every 60-second poll returns a full body (specs.md:331). | specs.md:187, :331 |
| **Payload size** | Never sized in any of the five documents. `{value, display, format}` per price plus per-pick `access` and per-section `access` duplicates data the client can already derive (sdui-proposal.md:130, :150-153), against a contract that explicitly has **no paging** and expects the app to filter and sort on device (specs.md:80, AC-1 :482). The proposal's own answer — cursors and server grouping (sdui-proposal.md:198) — contradicts AC-1 and §4.4 ordering (specs.md:179-180). No payload budget exists anywhere. | specs.md:80, :482; sdui-proposal.md:198 |
| **Skeleton / empty / error** | `empty_state` is a component (sdui-proposal.md:174) but there is **no section-level failure state**. A section omitted because the app lacks a capability (:131) and a pick dropped because it failed contract validation (specs.md:189, AC-2 :483) look identical to the client. Without an explicit per-section state (`ok`/`degraded`/`unavailable`) the app cannot tell "empty day" from "BFF failed", and neither can support. | sdui-proposal.md:131, :174; specs.md:189 |
| **Accessibility** | The proposal does not mention accessibility at all (verified: zero occurrences). Grounding, not verification: the app has five a11y annotations under `app/`, all in profile/social/video (`app/components/Screen.tsx:225`, `app/components/SocialIcon/SocialIcon.tsx:17`, `app/components/HomeCarousel/VideoSlide.tsx:243`, `app/components/FollowUsRow/FollowUsRow.tsx:106`, `app/screens/ProfileScreen/components/CloseAccountRow.tsx:35`), so content cards carry none. Once structure and copy are server-side, a11y labels, roles and reading order can only be added via props — there is no props field for them, and the app can only guess from display strings. | sdui-proposal.md (no occurrence); `mobile-app/app/` |
| **Analytics** | Grounding: events are app-side typed constants fired at known affordances (`app/services/appEvents/events.ts:94-675`, `app/lib/facebook/facebook.constants.ts:18-54`), including the freemium funnel. With server-composed sections, the event name and its params must derive from `section.id`/component — but nothing states that section ids are stable, unique, analytics-safe or immutable across registry edits, and there is no experiment or placement field in the payload. | sdui-proposal.md:138-158, :185 |
| **A/B testing** | Not representable. No `variant`, `experiment` or `placement` field anywhere in the payload (verified: zero occurrences of "experiment"); the app has no Remote Config client to piggyback on (sdui-proposal.md:119). Server-composed screens could A/B section order and copy, but with no variant id in the payload there is no attribution, and the client cannot distinguish an experiment from a rollout. | sdui-proposal.md:119, :138-158 |
| **i18n / localisation** | Principle/ownership puts wording and locale formatting in the BFF (sdui-proposal.md:184), but **no locale input exists**: the payload context carries `region` (sdui-proposal.md:141); specs.md's request has no locale parameter and states region "is never a request parameter outside mock mode" (specs.md:90), with `region` a two-value enum (specs.md:102). Canonical v3's V8 — "who renders localised copy" — is still open until 6 Nov (canonical-data-model.md:715) and `messages/<locale>.yaml` is product-owned (canonical-data-model.md:530). Consequence: the app's typed i18n with US/AU overlays (sdui-proposal.md:117) and the registry messages become two copy pipelines with no stated authority, and the region→locale mapping is undefined. | sdui-proposal.md:117, :141, :184; specs.md:90, :102; canonical-data-model.md:715 |
| **Live merge** | Correctly kept app-side (sdui-proposal.md:185; specs.md:350-357 §7.3), but principle 2's formatter set (:130) **re-creates the app-side formatting the proposal set out to delete** (sdui-proposal.md:45, :52). It also creates a second implementation with its own precision: specs.md stores/compares odds at 4 dp and displays 2 (specs.md:151, :300), canonical v3 stores derived prices at 6 dp and says 4 dp "is not enough" (canonical-data-model.md:372). The proposal cites neither. | sdui-proposal.md:45, :130, :185; specs.md:151, :300; canonical-data-model.md:372 |
| **Live-merge cost coupling** | The overlay cost lever is "listen only to picks on screen and detach on blur" (sdui-proposal.md:261). With server-chosen paging and grouping (:198), the on-screen set is now server-determined, so the cost lever moves server-side. The two decisions are treated as independent; they are not. | sdui-proposal.md:198, :261 |
| **Deep links** | The navigation shell stays native (:187), so screen routes are safe. Pick-level identity is not: the payload uses the v3 `pick_id` form `nba:…:spread:full:-:-:c1:-4.5\|us\|1` (sdui-proposal.md:149), while the contract the pilot is built from freezes the legacy id format through Phase 2 (specs.md:397) and bans `.` in ids (specs.md:562, AC-25). canonical v3 changes the id and the ban (canonical-data-model.md:398, :414, :601-602). SDUI inherits an unresolved identity decision — see §3.5. | sdui-proposal.md:149; specs.md:397, :562; canonical-data-model.md:398 |
| **Push copy** | The registry owns "messages" (sdui-proposal.md:183), but push is explicitly out of scope in specs.md (specs.md:17), the proposal never says the push function reads the registry, and the known placeholder push copy defect (sdui-proposal.md:291) is untouched. Push has no locale source at send time. | sdui-proposal.md:183, :291; specs.md:17 |

### Position 1.5 — The seam moves failure from compile time to run time, and no rule covers the new failure mode.

The app is typed loosely against the BFF today (`[key: string]: any`, sdui-proposal.md:105), so drift goes unnoticed; that is an argument for generated types, not automatically for runtime composition. After SDUI, a wrong section/props combination is a **runtime payload**, and the app must tolerate it. specs.md has the rule for enums ("clients MUST ignore unknown fields and show a neutral fallback for unknown enum values", specs.md:182); the proposal has no equivalent for an unknown **component**, an unknown **prop**, or an unknown `contract_version` major (sdui-proposal.md:140, :143). This is the single most important missing rule at the seam, because "no app release" is only safe if old builds are guaranteed to degrade predictably.

---

## 2. Contradictions and overlaps with specs.md

### Position 2.1 — `{value, display}` does **not** contradict specs.md principle 2. This is the proposal's strongest claim and it is correct.

specs.md principle 2 binds **producers**: "Producers send typed, structured values… They never send display copy or encoded strings that need parsing" (specs.md:22). It does not bind the BFF. specs.md's own ownership table gives the BFF "display copy for codes" (specs.md:42), and §3's owner column has "BFF composes from producer fields" (:54), "BFF (copy)" (:71), "BFF (name)" (:60). The proposal's "who owns what" table says the same thing (sdui-proposal.md:182-184). So the `{value, display}` rule at the BFF→app boundary is consistent with the v4 contract, and the claim that v4 "is the right template" (sdui-proposal.md:7) is right. The real conflicts are elsewhere and are not named in the proposal.

### Position 2.2 — Conflict A: who formats odds — and specs.md is already split on it, so SDUI forces a decision specs.md owes anyway.

specs.md §2 assigns the app "odds format by region" (specs.md:43) and §4.3 says "the app shows American for US and decimal for AU" (:160) — but the conformance matrix assigns D-1..D-8, the odds-conversion worked examples, to the **BFF** (:588). SDUI principle 2 resolves that split toward the server and goes further: the app does not format odds at all (sdui-proposal.md:130). Functionally the server can produce the same strings because it knows `region` (sdui-proposal.md:141). Two real consequences remain: the app loses the format *selection* (any local override, and the AU/US switch becomes a server property), and "the app never formats" is unachievable as stated because the app still owns payout and stake in dollars (specs.md:64, :297-298, D-9/D-10 :590). This is the one place where the proposal does specs.md a service — it forces an ambiguity to be closed — and it should be recorded as such.

### Position 2.3 — Conflict B: sorting and grouping.

specs.md owns sorting in the app (specs.md:75, :180) and fixes BFF order in AC-4 (:485). SDUI's Phase 2 prerequisite 4 wants server-chosen grouping and cursors (sdui-proposal.md:198). `{value, display}` retains the raw value, so client sorting survives — but server grouping does not compose with §4.4's single ordering rule, and a sort affordance that requires a round trip breaks the instant-sort UX the contract assumes.

### Position 2.4 — Conflict C: the release gate. Capability negotiation removes a compliance requirement and replaces only one of three functions.

specs.md §4.4: "The existing league release gate applies: picks for a staged league or season are withheld from app builds below the release `api_version`" (specs.md:183), enforced by AC-6 (:487) and owed by X11, owner BFF, "before release" (:459). SDUI principle 3 says capability negotiation "retires the `api_version` majors that today gate EPL, NFL and staged seasons" (sdui-proposal.md:131). The proposal correctly diagnoses that `api_version` conflates three jobs — league visibility, response shape, staged-season release (sdui-proposal.md:91) — but supplies a replacement for **one** of them (shape). League visibility (`enabled_leagues`, which the app ignores today, sdui-proposal.md:111) and staged-season withholding have **no replacement mechanism**. Capability negotiation answers "can this build render it?", not "may this build see it yet?" — two orthogonal gates. As written, principle 3 makes AC-6 and X11 unsatisfiable by design.

### Position 2.5 — Conflict D: field groups and access semantics are mis-specified.

specs.md defines six named groups (specs.md:154), a mirror-leak algebra (§6.2 :316, AC-37 :575), null-not-zero (:315), `edge_state` → `unknown` when edge is hidden (AC-38 :576), and `overlay_key` null for locked picks unless the overlay enforces the same groups (:320). SDUI's sketch writes `hidden: ["price", "edge"]` (sdui-proposal.md:152): `price` is not a field group, and `edge` alone is an illegal combination under the mirror rule unless probability or odds is also hidden. More importantly, principle 5 claims access works "as v4 edge picks already does" (sdui-proposal.md:133) — but v4 serves mock fixtures only, its live adapter throws (sdui-proposal.md:99, :223), and production freemium is a key-name denylist with hand-written mutations (sdui-proposal.md:95). **The proposal generalises from a route that has never served a live response, and from an access model (per section) that is coarser than the spec's (per pick, per group).**

### Position 2.6 — Which parts of specs.md become redundant, and which do not.

If SDUI lands as sketched:

- **Changed/duplicated:** §2 app-owned "odds format by region" (:43) and §4.3 "the app shows American/decimal" (:160) move to the server, resolving the split with §10.9 (:588); the formatter set (sdui-proposal.md:130) becomes a second conversion implementation alongside the BFF's; §4.4's app sorts (:180) partly move under server grouping; AC-1's no-paging (:482) is superseded by cursors; §10.6's hand-made mock scenarios (:540-547) are superseded by the v3 generator, which already emits "the v4 Edge Picks mock scenarios" and SDUI payloads (canonical-data-verification-plan.md:84, :87).
- **Untouched and still binding on the pilot:** §4.5 ETag/errors (:187-189), §5 state model (:195-273), §6.1 formulas (:279-300), §6.2 freemium (:302-321), §7 overlays (:323-376), §8 producer contract (:378-441), §9 dependencies incl. X11/X14 (:443-474), §10.1-10.5 and 10.7-10.9 (:480-597), §11 phasing and D1 (:599-621).
- **Drift understated:** the proposal names two drifts — `edge_threshold` instead of `edge_holds_above`, and missing `overlay_key` (sdui-proposal.md:99, :224). canonical v3 requests **six** changes to v4 before build (canonical-data-model.md:599-606): line-aware ids (§8.2), AC-25 moved to `overlay_key`, `side: at_least` for milestones, `half_won`/`half_lost` results, `edge` → `ev` + `edge_prob`, and the meaning of `model.probability`. Adopting v4 as the SDUI template inherits all six, not two.

### Position 2.7 — Overlap: two proposals define one repository, `xo-contracts`, with different owners.

SDUI's registry row is "Registry (`xo-contracts`) — Leagues, sport profiles, stats, markets, messages, units, asset keys, component versions; owned by platform" (sdui-proposal.md:183). canonical v3 uses the same name for the schema + taxonomy repo (canonical-data-model.md:501; V7 "a new `xo-contracts` repo", :714) and assigns its files differently: `leagues.yaml` → product, `sports/<sport>.yaml` and `stats/<sport>.yaml` → sport owners, `messages/` → product with product PR approval for every user-visible string (canonical-data-model.md:86-94, :530). I confirmed read-only that no `xo-contracts` checkout exists under `/mnt/devel/xosports/github`, so both proposals are describing a repo that does not exist, under one name, with two ownership models. This must be settled before registry v1.0, which canonical v3 needs by 23 Oct (canonical-data-model.md:583).

### Position 2.8 — Overlap: the proposal does not cite the validation plan, which already contains most of its missing test and mock strategy.

The validation plan already (a) names SDUI in a rule family — "BFF and SDUI responses match their zod schemas" (canonical-data-verification-plan.md:36); (b) generates SDUI payloads via the `preview` command (:98); (c) previews the component catalogue in the workbench (:107); (d) names the Gate C rehearsal explicitly (:112); (e) defines golden rendered-copy fixtures for BFF and app CI (:72; canonical-data-model.md:509); and (f) generates "Consumer shapes: Delta rows, Cosmos documents, SDUI payloads, RTDB overlay nodes" (:87). The proposal re-invents mock and test strategy at lower fidelity and misses that its own Gate C already has a rehearsal mechanism. **Right but incomplete; the fix is a merge, not new work.**

### Contradictions table

| # | Item | specs.md rule | SDUI proposal rule | Consequence | Who must decide |
| --- | --- | --- | --- | --- | --- |
| CT-1 | Odds-format ownership | §2 app owns "odds format by region" (:43); §4.3 app shows American US / decimal AU (:160) — but §10.9 assigns D-1..D-8 conversion to the BFF (:588): an internal split | Principle 2: app never formats odds; display comes from the server (:130) | Resolves an existing ambiguity toward the server; app loses format selection and local override; payout/stake money still app-formatted (:297-298) | App + BFF (product via D11) |
| CT-2 | Sort and grouping | §3 sort owned by App (:75); §4.4 app sorts, nulls last (:180); AC-4 BFF order (:485) | Phase 2 prereq 4: server-chosen grouping, cursors (:198) | Two orderings must agree, or sorting becomes a round trip; grouping contradicts §4.4 | Product + app |
| CT-3 | Paging | §4 "no paging; the app filters and sorts on the device" (:80); AC-1 (:482) | Sections need cursors for busy days (:198) | AC-1 must be rewritten, or SDUI grouping is impossible for a 100+ game CBB Saturday | BFF + app (spec owner) |
| CT-4 | Release gate | §4.4 league release gate (:183); AC-6 (:487); X11 owner BFF, before release (:459) | Principle 3: capability negotiation retires `api_version` majors (:131) | Staged leagues/seasons lose their mechanism; AC-6 and X11 unsatisfiable | BFF + product |
| CT-5 | Field-group vocabulary | `FieldGroup` = six groups (:154); mirror-leak algebra §6.2 (:316); AC-37/38 (:575-576) | Sketch `hidden: ["price","edge"]` (:152) | `price` is not a group; `edge` alone is illegal; a new group is a v4 contract change (§1 principle 6, :26) | BFF + app (D11) |
| CT-6 | Access granularity | Per pick, per field group; hidden fields MUST be null, never zero (:315) | "Access per section and field group" (:133) | A section-level lock cannot express a per-pick hidden group; composer must apply §6.2 per item | BFF |
| CT-7 | Odds precision | 4 dp stored, 2 displayed (:151, :300) | `{value, display}` from BFF plus app-side format keys (:130) | Two formatting paths at 4 dp vs 6 dp (canonical-data-model.md:372) can disagree at boundaries | BFF + app |
| CT-8 | Pick identity | §8.2 format frozen through Phase 2 (:397); AC-25 bans `.` (:562) | Payload uses v3 `pick_id` with `:` and `\|` (:149) | Pilot adopts an id the spec it pilots says is frozen; affects overlay keys and saved slips | BFF + data engineering (V2, R4, R5) |
| CT-9 | Copy locale | `region` is `us\|au` (:102) and never a request parameter (:90) | BFF composes wording per locale (:184) | No locale input defined; region ≠ locale; V8 open until 6 Nov (canonical-data-model.md:715) | App + BFF (V8) |
| CT-10 | Freemium evidence | §6.2 flags and named groups (:304-313) | "as v4 edge picks already does" (:133) | v4 serves mocks only; production freemium is a key-name denylist (sdui-proposal.md:95, :99) | BFF |
| CT-11 | Registry ownership | product owns leagues and messages; sport owners own profiles and stats (:86-94, :530) | Platform owns leagues, profiles, stats, markets, messages (:183) | One repo, two owners; merge-blocking copy review unassigned; registry v1.0 due 23 Oct | Platform + product + sport owners |
| CT-12 | My Picks identity bridge | — (specs.md does not cover) | "My Picks … no app release" (:208) | canonical v3 keeps `legacy_ids[]` (canonical-data-model.md:590) while cutover C5 says no bridge (coexistence-cutover-plan.md:45) — the claim rests on an open decision | BFF + data engineering |
| CT-13 | Push copy | out of scope (:17) | Registry owns messages (:183) | Push copy has no registry reader named and no locale at send time; placeholder defect stays open | Product + BFF |
| CT-14 | `action` naming | `action` = Rec. Action play/watch/pass (:127, D4 :643) | `access.upgrade.action` and top-level `actions` (:153, :157) | Same name, three meanings in one payload namespace | BFF + app |

---

## 3. Dependency on the v3 canonical model and competition with the cutover plan

### Position 3.1 — The plan is honest about *what* it depends on, and not about *when*.

Honest: the pilot table lists "v3 canonical documents for the pilot leagues" as a prerequisite (sdui-proposal.md:229), and the three facts say NBA alone is on canonical documents while MLB, WNBA, NFL and EPL are on Format A (:13). Not honest about timing: canonical v3 puts v3 documents for NBA and WNBA/MLB in Phase 1B on 1 Dec (canonical-data-model.md:585) and NFL/EPL in Phase 2 in January (canonical-data-model.md:586, V5 :712). SDUI's migration section says "No dates are set; phase lengths depend on team capacity" (sdui-proposal.md:272), which reads as though SDUI controls its own schedule. It does not: if the Edge Picks pilot includes anything beyond NBA, its start is January.

### Position 3.2 — SDUI Phase 1 must merge with the Edge Picks v4 app release, or pay for a second release of the same screen.

specs.md binds AC-1..AC-12, D-9, D-10, AC-23, AC-27..AC-29, AC-39 and AC-42 to "App release of the new screen" (specs.md:588-590). SDUI's Phase 1 is "the screen that is being redesigned anyway" (sdui-proposal.md:272) — the same screen, the same release. Two releases of one screen in the same quarter would be a self-inflicted coordination cost. The proposal does not say which it intends.

### Position 3.3 — The cutover plan is a prerequisite, not a parallel track, and the proposal never mentions it.

- C2 requires the BFF to ship v3 readers and doc-type-filtered queries **before** any producer writes v3 (coexistence-cutover-plan.md:39).
- C3 requires one internal model that "every response shape (the v1 to v3 routes, `/v4/edge-picks`, later SDUI screens) renders from" (:41) — SDUI is explicitly **downstream** of C3.
- C4 moves free-user redaction into that model (:43) — the same rule as SDUI principle 5.
- C9 keys caches by family epoch (:55) — the SDUI ETag/capability key must extend it.

So SDUI's Phase 0 ("removes the defects and gives every route a contract", sdui-proposal.md:272) edits the same BFF files as C2/C3, for the same team, with C2/C3 having priority because a v3 document landing in a shared container today produces duplicate games, blank predictions or a randomly chosen outcome (coexistence-cutover-plan.md:5-6).

### Position 3.4 — Capacity: four documents name the same teams; SDUI names none.

The BFF team is committed by specs.md X11 (specs.md:459), cutover C2/C3 (coexistence-cutover-plan.md:39-41), canonical v3 V8 (canonical-data-model.md:715) and SDUI's composer, capability negotiation and registry wiring. Data engineering is committed by specs.md X1/X12/X14 and AC-41 (specs.md:449, :460, :462, :580), canonical v3's dual-publish with "Cosmos throughput and PE runtime roughly double per league for about a month" (canonical-data-model.md:585-586, :732), the cutover shadow (:47, :91), and SDUI's "PE maps history to current observations" (sdui-proposal.md:228). Platform is committed by canonical v3 V7 plus the validation plan's library, CLI and workbench (canonical-data-verification-plan.md:91-99) **and** by SDUI's registry. SDUI's only capacity statement is "phase lengths depend on team capacity" (sdui-proposal.md:272). That is not a plan; §7.5 lists what is missing.

### Position 3.5 — One inconsistency SDUI inherits and must help settle.

canonical v3 keeps `legacy_ids[]` plus a rewrite job for saved slips (canonical-data-model.md:415, :590, R4 :664); the cutover plan says "No id bridge… `legacy_ids[]` can be dropped" because no game is published in both families (coexistence-cutover-plan.md:45). SDUI's claim that My Picks needs no app release (sdui-proposal.md:208) depends on which is true.

---

## 4. Governance of the new `xo-contracts` registry

### Position 4.1 — The registry is a new production system with a one-PR blast radius to 100% of users, and the proposal gives it no versioning, review, rollback or kill switch.

canonical v3 already specifies what is needed: registry semver, a change path (registry PR → product and sport-owner review → CI → release → consumers upgrade → producers may emit), `registry_version` on every document, and neutral fallbacks for unknown values (canonical-data-model.md:526-531). SDUI should adopt that verbatim and add the two things v3 does not need: a payload-stamped registry version and a server-side composition switch.

### Position 4.2 — Blast radius: a bad registry or composition change is strictly worse than a bad app release.

A bad app release is gated by store review, staged rollout and the force-update gate (sdui-proposal.md:296), reaches only users who take the build, and is superseded by shipping again. A bad copy or composition change reaches **every user on the next request**, including users on builds the server cannot roll back, and because copy arrives as a `display` string (sdui-proposal.md:130) the client has nothing to fall back to. specs.md's neutral-fallback rule protects unknown **enum values**, not sentences (specs.md:182); canonical v3's fallback rule has the same limitation (canonical-data-model.md:529). The realistic mitigations — per-league/per-screen composition flag, registry version pinned and alerted per response, last-known-good copy bundle, app ability to skip a section — appear nowhere in the proposal.

### Position 4.3 — Copy review is unowned and its volume is unestimated.

canonical v3 makes product approve **every** user-visible string by PR (canonical-data-model.md:530), with per-locale message completeness enforced by registry CI (canonical-data-verification-plan.md:35). SDUI adds section titles, tooltips, empty-state text, paywall CTAs (`access.upgrade.label`, sdui-proposal.md:153) and push candidates. Product becomes a merge-blocking reviewer for all copy in all locales, and SDUI assigns the whole registry to platform instead (sdui-proposal.md:183; CT-11). That is a throughput decision, not just an ownership label.

### Position 4.4 — Capability negotiation renames one gate, removes another, and adds an untested one.

It replaces the **shape** function of `api_version` (sdui-proposal.md:131) and removes the league release gate (CT-4). It also introduces a failure mode with no rule: capability is **self-declared** — an app that advertises `scoreboard@2` but renders it wrongly is trusted. And the first-launch case (an app that advertises nothing) must fall back to the native screen, which means **both renderers ship for at least one release cycle**. That cost is not budgeted.

### Position 4.5 — What governance should look like (the minimum that makes this approvable).

Copy and registry changes reviewed by product **and** app; message changes as registry minors; every payload stamped with `registry_version` and `contract_version`; composition behind a per-league flag defaulting off; rollback = registry revert plus flag off, with no app release; an alert when a response carries a version the app does not expect; and a stated deprecation window for component versions (e.g. `component@N` supported for two app releases).

---

## 5. Cost/benefit versus generated client code from one registry

### Position 5.1 — The cost claim is credible as a count but the wrong unit.

"~8 PE places, ~11 BFF areas, ~11 app files, plus a store release" (sdui-proposal.md:5) counts edit sites. The binding constraints are the store release and the coordination, and the proposal itself lists six client prerequisites before the benefit exists (sdui-proposal.md:193-200). The honest claim is narrower than the headline: SDUI removes the **release**, not the work.

### Position 5.2 — The case for runtime SDUI.

Only runtime composition removes the store release; only it can change league visibility, locks, section order and copy per user or per rollout; it directly fixes the app-ignores-the-server defects (sdui-proposal.md:111-113); it can collapse the double formatting (sdui-proposal.md:45) if the formatter set stays small; and the registry it needs is required anyway — canonical v3 already generates "App config (leagues, features, colours, crests, sections)" for the app build (canonical-data-model.md:508) and TypeScript for the BFF and app from one source (:18, :507). SDUI is therefore an increment on work that is already committed, not a parallel investment. The proposal is also right that the benefit is bounded: new **leagues and markets**, not new screen types — brackets need a new component (sdui-proposal.md:212), and the catalogue cannot foresee new screens (:191).

### Position 5.3 — The case for codegen with compile-time layout.

canonical v3 already commits to generating app config and TypeScript from the registry (canonical-data-model.md:507-508), and to turning the app's `isEpl`/`isNba`/`isNfl` branches into profile lookups (:445). That mechanically removes the 10 hand-edited maps and the 11-file league touch, with compile-time checking — which is the direct fix for the app's real defect, being typed `[key: string]: any` against the BFF (sdui-proposal.md:105). Layout stays reviewable and testable at build time; no new cache-key dimensions; no capability negotiation; no 100%-user copy blast radius; offline, a11y and analytics unchanged; and the validation plan's golden rendered-copy fixtures plus Gate 5 app CI (canonical-data-verification-plan.md:17, :72) can compare rendered copy at build time. What codegen cannot do: change a string, a league's visibility or a section's presence without a release.

### Position 5.4 — Recommendation: codegen first, then a **content-only** runtime payload. This is the single change that most improves the proposal.

The asymmetry is decisive. The set of things that genuinely must change without a release is small and enumerable: league visibility, copy, locks, section order, asset keys. The set of things that should stay compile-time is most of the catalogue: component identity, props shapes, table columns, annotations, interaction. The proposal's sketch already puts component identity, columns and annotations server-side (sdui-proposal.md:143, :155, :197) — that is more than "content", and it is where the interpreter risk lives. So:

1. **Phase 0 = registry + codegen** (the v3 `xo-contracts` work: registry v1.0, generated TS types/config, golden rendered-copy fixtures, registry CI).
2. **Phase 1 = Edge Picks v4 live**, merged into the specs.md app release, with copy/locks/section order served from the registry but **components and props compile-time**, per-component props schemas in the registry, and no server-chosen component identity.
3. Only after that, generalise to server-chosen components for the screens that need it.

This captures most of the release-free benefit — copy, locks, league visibility, section order — at a fraction of the risk, and it is what "semi-SDUI" should mean. **SDUI is not the cheapest way to cut the 11 app files; it is the only way to cut the store release. Sell it on the release.**

---

## 6. The college football/basketball test case and Gate C

### Position 6.1 — Gate C as stated is not a fair test of SDUI; it is a test of five workstreams at once.

Gate C is "a new league lands through registry and BFF changes alone" (sdui-proposal.md:272). NCAAB needs feeds, models, bet-engine output, PE canonical documents, ~500 team reference entries and a compliance review — the proposal says so itself (sdui-proposal.md:215). A Gate C failure therefore cannot tell you whether SDUI failed or the data workstreams did, and the one variable SDUI controls (the app release) is the cheapest of the six. **Fix:** define Gate C as the **second** league through the platform, with the first counted as platform build-out, or decompose it into sub-gates with the non-SDUI workstreams separately scheduled and owned.

### Position 6.2 — The ~500 teams are reference data, not registry, and the asset dependency is a merge blocker.

canonical v3: "Adding a league in an existing sport (LaLiga, UCL) is one line in `leagues` plus its teams in reference data" (canonical-data-model.md:481); the registry has no teams file (canonical-data-model.md:86-94). So "about 500 team entries in the registry" (sdui-proposal.md:215) names the wrong artefact. The 135 FBS / 360 Division I logo counts (sdui-proposal.md:210) are asset curation plus licensing, owned by product, with no date — and registry CI fails a merge when an `asset_key` is missing from storage (canonical-data-verification-plan.md:35). The registry PR cannot merge before the assets are uploaded and licensed.

### Position 6.3 — US state betting restrictions are not representable in the current contract.

`region` is a two-value enum (specs.md:102) and "is never a request parameter outside mock mode" (specs.md:90). canonical v3 puts jurisdictions on **venues** for handoff (canonical-data-model.md:573, V13 :720), not on users. The proposal's "drop ineligible picks by the user's region and state claims" (sdui-proposal.md:215) needs a jurisdiction source and a pick-eligibility rule that no document defines. It also collides with the contract's own integrity rules: a dropped pick is a defect reported to monitoring (specs.md:189, AC-2 :483), and an absent card is unexplainable to the user where a locked card is not.

### Position 6.4 — Feeds, models, period and clock: the clock belongs to the overlay path, not the screen payload.

The test-case table already qualifies injuries with "Yes, if data exists" (sdui-proposal.md:207) and the text admits feeds, models and bet-engine output are still needed (:215). College basketball halves and college football quarters need profile `periods` — canonical v3 shows periods only for soccer (canonical-data-model.md:452) — plus overtime rules. And live text such as "2nd Half 12:40" is a **live value**: the BFF composes on request and the app polls at most once a minute (specs.md:331, AC-27 :564), so a snapshot-composed clock is stale by construction. Prerequisite 5 (sdui-proposal.md:199) crosses the snapshot/overlay boundary without saying which path carries the clock, and the live-scores integration is out of specs.md's scope (:17) and blocked on X14 (:462).

### Position 6.5 — Paging and grouping contradict the contract being piloted, and the Cosmos cost is unsized.

AC-1 has no paging (specs.md:482); §4.4 fixes one ordering (:179-180); SDUI wants cursors and server grouping (sdui-proposal.md:198). A 100+ game CBB Saturday also has a read cost the proposal never sizes: canonical v3 measures 10-15 RU per match view (canonical-data-model.md:255), and a day-level screen reads eight documents per game.

### Position 6.6 — "No app release" is achievable only for the second new league, and the proposal half-says so.

The proposal **is** honest that six client capabilities must be built first (sdui-proposal.md:193-200): open keys instead of closed unions, server-supplied navigation, annotation slots, paging, period/clock, colour and art by registry. Every one is a client-contract change, so at least one build is required. But the test-case heading says both leagues "could ship with no app release" (:191) and Gate C is presented as the test of the approach (:272). State it precisely: **Gate C = prerequisite build + zero additional releases**, and make the six prerequisites exit criteria of the preceding gate.

### Position 6.7 — NCAAB is the easiest case, not a representative one.

It is chosen because it reuses the basketball profile and stat keys (sdui-proposal.md:191). It therefore does not test a new sport profile, a new market type, a three-way market, a new Publish Engine container (:83) or a new document type. Gate C should state what it does not cover, or the team will read a pass as broader than it is.

---

## 7. What a decision-maker still lacks

1. **Success metrics.** None. The only quantified baselines are the 8/11/11 file count (sdui-proposal.md:5) and the RTDB/Web PubSub costs (:249-253), and even those are flagged "to replace with real analytics" (:255). No target for new-league lead time, releases avoided, payload size p95, screen TTI, payload-validation failure rate, copy-defect rate, or Gate C pass criteria.
2. **Phase exit criteria are not in the text.** The migration section defers to an embedded graphic (sdui-proposal.md:270); prose names only Phase 0, Phase 1 and Gate C (:272). Gates A and B and Phases 2-3 are unnamed and undefined. A plan whose exit criteria exist only in an image cannot be approved or tested.
3. **Registry migration, rollback and contract versioning policy.** The payload has `contract_version` and `component@N` (sdui-proposal.md:140, :143) with no rule for who bumps them, what an unknown component/prop/version does, or how a bad registry change is reverted. Copy the models that exist: specs.md §1 principle 6 and §4.4 (specs.md:26, :181-182) and canonical v3's versioning section (canonical-data-model.md:526-531).
4. **Test strategy.** Principle 6 says "contract tests in both CIs" (sdui-proposal.md:134) and nothing else. Missing: per-component props tests, capability-matrix tests (old build × new payload), visual regression on the catalogue, golden rendered-copy fixtures (already specified at canonical-data-verification-plan.md:17, :72), canary/rollout, and a regression test for "no app release". The validation plan answers all of this; the proposal does not reference it.
5. **Ownership and capacity.** "Platform owns the registry" is the only decision (sdui-proposal.md:303). No names, no capacity, no dates (:272) — where specs.md, canonical v3 and the cutover plan each carry owners and dates (specs.md:443-462, :634-652; canonical-data-model.md:702-724; coexistence-cutover-plan.md:105-119).
6. **Security review of server-composed content.** `actions` route names, `asset_key` URLs, paywall CTA copy and section copy are a new attack surface (sdui-proposal.md:152-157); the app bundle already leaks an entitlement-invalidate key (sdui-proposal.md:280); RTDB rules do not exist in any repo and overlay paths are predictable (:298; specs.md X5 :453, D6 :645). No review is scoped. "Security" appears in the proposal only about overlays.
7. **Interaction with the NBA 2026 transition.** NBA has been in season since 20 Oct (coexistence-cutover-plan.md:71), is the Edge Picks pilot, and its flip should follow the Edge Picks v4 live launch (:75). The proposal's PE evidence explicitly excludes the NBA 2026 path (sdui-proposal.md:67, :71), so the pilot league's producer path is unassessed; and Phase 0 edits the same BFF that is mid-transition, where `normaliseWltp` lifts canonical fields back onto legacy names (sdui-proposal.md:93) — the exact code cutover C3 deletes (coexistence-cutover-plan.md:41).
8. **The transport decision is unresolved and on the critical path** (sdui-proposal.md:305), and specs.md D6 — opaque keys versus entitlement claims — is open until 2 Nov (specs.md:645) although the pilot table already assumes opaque `overlay_key` (sdui-proposal.md:227).
9. **Compliance and licensing have no owner or date**: college betting restrictions (sdui-proposal.md:215), logo licensing (:210).
10. **Registry content volume is unestimated.** canonical v3's coverage table declares ~30 stat keys across five leagues, with EPL at zero player stats today (canonical-data-model.md:232-238). SDUI's registry inherits that authoring load plus messages, units, venues, assets and component versions.

---

## 8. Verdict

**Approve with conditions — approve the direction and the seam; reject the plan as scoped for Phase 1.** If conditions 1 and 2 below are not accepted, this becomes a reject.

### What the proposal gets wrong

1. **Principle 3** (sdui-proposal.md:131) — capability negotiation cannot replace the league release gate; it removes AC-6/X11 compliance (specs.md:487, :459) and replaces only one of the three jobs `api_version` does.
2. **"The work left is wiring, not design"** (sdui-proposal.md:219) — six of the seven pilot rows are unbuilt, including the live adapter, the RTDB client and rules, the PE history reader and all-sport monitor coverage (sdui-proposal.md:223-229).
3. **"Access per section and field group… as v4 edge picks already does"** (sdui-proposal.md:133) — v4 is mock-only and its live adapter throws (sdui-proposal.md:99, :223); production freemium is a key-name denylist (:95).
4. **"Both leagues… could ship with no app release"** (sdui-proposal.md:191) — true only after the six client prerequisites (:193-200), which are releases; Gate C must be restated.
5. **"About 500 team entries in the registry"** (sdui-proposal.md:215) — teams are reference data, not registry (canonical-data-model.md:481).

### What it gets right

The seam (content server-side, layout native) and the explicit rejection of a layout DSL (sdui-proposal.md:125-129, :297). The diagnosis that display decisions are duplicated across four layers (:45) and that `api_version` is overloaded (:91). Assets by key as the answer to the bundled-logo release (:132, :115). One generated contract (:134) — aligned with canonical v3 (:18, :507-508). The pilot dependency table's honesty about v3 documents (:229). Naming over-reach and overlay security as the top risks (:297-298). The transport comparison and its provisional conclusion (:235, :305).

### What it is right about but incomplete on

Governance, versioning, rollback, metrics, exit criteria, ownership, security, test strategy, accessibility, analytics, A/B, offline, and the four contract conflicts it does not name (CT-2 sort/group, CT-3 paging, CT-5 field-group vocabulary, CT-7 odds precision).

### The three conditions that change this answer

**Condition 1 — Make the seam a contract.** Per-component props schemas in the registry with an enforced rule that props may not carry style, spacing, colour or animation; `registry_version` and `contract_version` on every payload; a cache/ETag key that includes the negotiated capability set and the registry version; a deterministic composition order; an explicit per-section state for degraded/empty/unavailable; and a written list of the specs.md ownership rows that move (odds format, sort/group, AC-6/X11). *Without this, the proposal is an interpreter with an open props bag.*

**Condition 2 — Keep the release gate and define rollback.** Capability negotiation is added **beside** the league release gate, not instead of it, with a named replacement for league visibility and staged seasons; AC-6 and X11 remain satisfiable; and a bad registry or composition change is revertible without an app release (per-league/per-screen flag defaulting off, last-known-good copy, registry revert, version-mismatch alerting). *Without this, a single PR can put a wrong paywall CTA in front of every user with no escape hatch.*

**Condition 3 — Sequence and staff it.** Phase 0 = registry v1.0 + codegen + golden rendered-copy fixtures, owned and dated, merged with the v3 `xo-contracts` work; Phase 1 = Edge Picks v4 live merged into the specs.md app release, with the runtime payload limited to content (sections, order, copy, locks, asset keys) and components/props compile-time; Gate C = the **second** new league after the six prerequisites, with reference data, assets/licensing, compliance, feeds/models and PE documents costed and owned separately. *Without this, the plan competes with cutover C2/C3 and canonical 1B for the same people and slips behind them anyway.*

If all three are accepted, I would approve the direction cleanly, with codegen-first sequencing as the change that most improves it.

---

## Questions the proposal cannot answer about itself

1. What does the app render when it receives `component: "scoreboard@3"` that it does not implement — skip, fallback, or error?
2. What is the cache key for an SDUI response, and does it include the negotiated capability set and the registry version?
3. If a composed string is wrong for every user, what is the rollback, who can trigger it, and does it need an app release?
4. Which props are content and which are layout, and who arbitrates when a component needs a new prop — `stat_table` columns are already layout (sdui-proposal.md:155)?
5. Does the app keep its own i18n for server-composed strings, and which pipeline is authoritative on a conflict?
6. During the transition, do both renderers ship, and for how many releases?
7. What is Gate C's pass criterion, how is it measured, and does it count the six prerequisite releases?
8. Does `xo-contracts` mean the same repository in the SDUI proposal and canonical v3, and who owns which file?
9. What does the payload carry for analytics attribution and experiment variant?
10. What is the payload size ceiling for a screen, and what happens on a day that exceeds it when the contract has no paging (specs.md:482)?
11. Who is on the critical path for the registry — platform, product or sport owners — and how many people for how long?
12. What is the relationship between the SDUI payload and the `registry_version` stamped on every v3 document (canonical-data-model.md:300)?
13. What replaces `enabled_leagues` and staged-season withholding once `api_version` is retired?
14. Is `overlay_key` opaque (as the pilot table assumes, sdui-proposal.md:227) or entitlement-claim-based (specs.md D6, :645), and when is that decided?

---

## Appendix — method and limits

- **Verified absences** (grep over the proposal, case-insensitive): accessibility 0, experiment 0, localisation/localization 0, ETag 0, rollback 0, governance 0, "exit criteria" 0, success 0, canary 0, "visual regression" 0, jurisdiction 0. "Offline" appears once, about the Firebase client's cache (sdui-proposal.md:246); "cache" twice, about `/config` and the RTDB client (:107, :246); "security" three times, all about overlays (:227, :243, :298); "capacity" once, about team capacity (:272).
- **Read-only repository grounding** (not verification of the proposal's claims; those belong to the app, BFF/PE and live-overlay verifiers): `mobile-app/app/` a11y and analytics greps cited in Position 1.4; and the absence of a `xo-contracts` checkout under `/mnt/devel/xosports/github` cited in Position 2.7.
- **Not assessed:** whether the proposal's code claims are accurate, the correctness of the RTDB/Web PubSub cost model, and anything requiring a build, fetch or deploy.
