# Edge Picks v4: delivery options

Oct 20, 2026 · @Tze Liang

**Status: decided.** Option B (`api_version` v7 on the existing route) ships first, because of time; option A (a new route) is a later cleanup. The implementation plan is [option-b-plan.md](option-b-plan.md). This document is the comparison the decision was based on, kept as it was discussed with the team.

Both options keep the old app working exactly as today. The choice is about the new app: a new, typed route costs about 3–4 app days and gives a clean contract; a version-gated block on the existing route costs about 1 app day and keeps the new app on today's response shape.

## At a glance

The old app's path is the same in both options. The options differ only in the route the new app uses to read the same two stores.

```
                      Publish Engine: one decision per pick
                       │ writes                  │ derives, same pick ids
                       ▼                         ▼
              ┌──────────────────┐      ┌────────────────────────┐
              │ v4 producer      │      │ Legacy documents       │
              │ records          │      │ (c-wltp, c-ps,         │
              │ one per pick     │      │  c-outcome)            │
              └──────────────────┘      └────────────────────────┘
                    ▲      ▲               ▲        ▲        ▲
   Option A ────────┘      │               │        │        │
   /v4/edge-picks ─────────┼───────────────┘        │        │
                           │                        │        │
   Option B ───────────────┘                        │        │
   /v3 top-predictions, v7 ─────────────────────────┘        │
                                                             │
   Old app (v5, v6): /v3 top-predictions, unchanged ─────────┘
```

| Caller | Route | Reads legacy documents | Reads v4 producer records |
| --- | --- | --- | --- |
| Old app (store build v5, main v6) | `/v3/matches/:date/top-predictions` | Yes, as today | No |
| New app, option A | `/v4/edge-picks` | Yes: legacy-era picks, translated into the typed contract | Yes: v4-era picks |
| New app, option B | `/v3/matches/:date/top-predictions?api_version=v7` | Yes: the list itself, as today | Yes: joined to each listed pick by id to build its `edge_pick` |

## What stays the same in both

The coexistence design (KDD-002 and KDD-003 in [kdds.md](kdds.md)) is the same under either option. Only the way the new app receives its data changes.

- **One source of truth.** The Publish Engine decides each pick once, as a v4 producer record. Legacy documents for the old app are derived from those records in the same run, never written separately.
- **One id per pick.** A derived legacy pick carries the record's `pick_id`, so slips and follows saved in either app name the same pick.
- **The old app is untouched.** Each build hard-codes its `api_version` (store build v5); its routes and response shapes do not change.
- **Per-league switch.** Turning v4 off for a league degrades the new app's cards to the limited form; it never empties the screen and never affects the old app.
- **Every pick carries `era`.** `v4` gets the full card; `legacy` (games published before a league's v4 start) gets the limited card with no live price or edge state.
- **KDD-002's prerequisites still gate each league:** slip snapshots in the old app, pick results in `c-outcome`, and pinning a game's family at first publish ([coexistence-approach.md](../coexistence-approach.md)).

## Side by side

Effort figures are rough estimates for one developer who knows the codebase.

| Dimension | A. New route `/v4/edge-picks` | B. `api_version` v7 on `/v3/.../top-predictions` |
| --- | --- | --- |
| How the new app gets picks | Calls a new route that returns the typed snapshot contract | Keeps calling today's route with `api_version=v7`; each pick gains a nested `edge_pick` block |
| Old app (v6 and earlier) | Unchanged; never calls the new route | Unchanged; the v7 branch never runs for it |
| Precedent in the BFF | New versioned route (`/v3/*` exists) | Version-gated content and shape on existing routes (EPL v4, NFL v5, staged seasons v6, match-detail sections v4, split locks v5) |
| App effort beyond the redesign UI | ~3–4 days: new hook, types, one adapter into the existing card props | ~1 day: bump to v7, read `edge_pick` instead of the guessed `current_*` fields |
| Fit with XTP-125 | Card keeps its props via the adapter; the data source changes | Card, slips, follows, filters and locks keep working as written |
| BFF effort | Legacy translators for NBA and Format A documents (riskiest item) + producer-record source | No legacy translators; producer-record cache + join by pick id + v7 branch on one route |
| Free-user locking | One path (v4 field groups + leak rule) on a typed response | v4 rules applied to the `edge_pick` block as a whole; must never sit beside the v3 key-name denylist, which has missed new fields before (CR-9) |
| Contract | Typed, validated per pick, JSON Schema exported for the app | Typed and validated for the block only; the rest of the pick stays today's untyped shape |
| Pick title and labels | BFF composes `selection.label`; app could drop its title heuristics | App keeps `edgePickTitle.ts` heuristics on legacy fields |
| Game picks in Format A leagues (NFL, MLB, WNBA, EPL) | Every v4 pick shown, read from the records | One game pick per game and region (the `game_prediction` slot), unless documents gain arrays or the v7 branch adds record-only picks |
| Depends on derived legacy documents | No; reads records directly | Yes; v4-era picks reach the route only through them |
| Long-term shape of the new app | Clean contract; v3 can retire with the old builds | New app stays on the legacy v3 shape; moving off it later is another app change |
| Work already done (B1) | Is the route and contract | Formulas, free-user field groups and mocks reused for the block |

## Pros and cons

### A. New route `/v4/edge-picks`

**Pros**

- Clean, typed contract that the BFF validates on every pick; the app can generate its types from the exported JSON Schema.
- One free-user locking path built for the new fields, including the leak rule.
- Shows every v4 pick in every league, read straight from the producer records.
- Display-ready values (title, odds in both formats, edges as fractions, AU wording) remove guesswork from the app.
- The legacy v3 shape can retire with the old builds; nothing new is built on it.

**Cons**

- More app work now: a new hook, types and an adapter (~3–4 days).
- The BFF must translate legacy documents (NBA and Format A) into the new shape before the route can replace v3; this is the riskiest BFF item.
- A new pattern next to the established `api_version` practice.
- XTP-125 has to switch its data source, although the adapter keeps its card props.

### B. `api_version` v7 on the existing route

**Pros**

- Least app work (~1 day); XTP-125 keeps its data flow, slips, follows, filters and locks.
- Follows how the BFF has always enabled new content and shapes (v4, v5, v6).
- No legacy translators in the BFF; the route already reads the legacy documents.
- Legacy-era picks get the limited card almost for free: no producer record means `era: legacy` with live fields null.

**Cons**

- The new app is built on today's untyped v3 shape for good; moving off it later is another app change.
- Format A leagues show only one game pick per game and region until their documents list every pick or the BFF adds record-only picks.
- Relies on KDD-002's derived documents being live for a league before its v4 picks appear in the new app.
- Free-user safety depends on keeping every new field inside the `edge_pick` block; the v3 denylist has leaked new fields before.
- The app keeps its title heuristics (`edgePickTitle.ts`, ~300 lines) on loose legacy fields.
- Raising to v7 affects every route; routes without v7 logic behave as at v6, which needs checking once.

## Questions for the team

The answers to these decide between the options; neither is unsafe for the old app.

1. **Is the redesign the long-term base of the app?** If yes, building it on the v3 shape (B) means a second app change later; A avoids it.
2. **How much app time is there before launch?** B saves about 2–3 app days now; A spends them up front.
3. **Do NFL, MLB, WNBA and EPL need more than one game pick per game in the new app at launch?** If yes, B needs extra BFF work (arrays in derived documents, or record-only picks on the v7 branch); A has it by default.
4. **Who owns the risk in the BFF?** A puts it in the legacy translators; B puts it in keeping every new field inside one redacted block on a route with a denylist history.
5. **Should the BFF compose card titles?** A can, and the app drops its heuristics; B leaves them in the app.

A middle path is possible: ship B for launch and plan A as a later cleanup, accepting the second app change. **This is the path chosen.**

## Option B: round-trip anomalies and fixes

Every anomaly found in the list → slip → My Picks → result round trip can be fixed or contained, and most fixes are server-only, so they reach the store build without a release. Ids and cross-version resolution already hold: both builds read My Picks at `api_version` v3 with the same pick ids. "Old app" says whether the fix reaches store builds (1.1.66, v5) with no app release. Effort is a rough estimate for one developer.

The implementation plan refines these fixes after a code review; where they differ, [option-b-plan.md](option-b-plan.md) §6 (MP-1 to MP-8) is authoritative.

| # | Anomaly | Fix | Where | Old app | Effort |
| --- | --- | --- | --- | --- | --- |
| 1 | A slip item whose pick leaves the list makes the whole slip show odds and return 0; free and lapsed users lose the item | Snapshot on `POST /my-picks-v2` (reuse `/v3/my-picks` code). On read, fall back to the snapshot, with `bookmaker.bet_odds`, `probability` and `outcome` on every row (1.1.66 multiplies `bookmaker.bet_odds.decimal_odds` on the device). With no snapshot, mark the row unavailable and send null totals, never 0. A missing peer with a snapshot still shows to its owner | BFF | Yes | 2–3 days |
| 1e | Existing slips have no snapshot | One-off job writing snapshots for every slip item whose pick still resolves; run before each league's Stage A, and soon anyway (NBA line moves drop picks today) | BFF script | Yes | 1–2 days |
| 2 | A nested `edge_pick` survives the v3 free-user strip, which nulls top-level keys only | Attach after the free-user step; take the lock from the pick's legacy `locked` flag; redact with the v4 field groups; leak test in CI | BFF | Not affected | ½ day |
| 3 | Cancelled picks never reach the v7 card (the pick funnel drops them) | Add cancelled v4 picks from the records after the free-user step, read-only; app disables Add unless `edge_pick.status` is open | BFF + app | Not affected | 1–2 days BFF, ¼ day app |
| 4 | Void and push (code 2) show as a win | New app reads 2 as void plus a new additive `result` field (push or void). Server computes `returnAmount` with void and push legs at 1.0 for every build | BFF + app | Payout only | ½ day BFF, ½ day app |
| 5 | Snapshot-only rows are never graded (no `c-outcome` results) | Interim: My Picks reads the producer record's outcome by pick id. Long term: the settlement path into `c-outcome` | BFF now, data engineering later | Yes, in My Picks | 1–2 days |
| 6 | The card shows a current price; the slip uses the entry price | Product rule: the slip is at the entry price; the Add button shows it; the app never puts `current` into the slip | App + product | Not affected | ¼ day |
| 7 | Format A leagues (NFL, MLB, WNBA, EPL) show one game pick per game | At v7 only, add record-only picks for v4-era games, after #1 and #5 | BFF | Not affected | 1–2 days |
| 8 | My Picks sent v7 would skip free-user filtering (exact `=== "v3"` check) | Change to `>= 3`, or keep the app hard-coded at v3 and guard it with a BFF test | BFF | Not affected | ¼ day |
| 9 | The list and My Picks unlock different picks for free users | Product rule first; recommended: a slip you saved always shows to you | BFF + product | Yes | ½–1 day |
| 10 | Follow topics keep `\|` on device re-registration and fail | Replace `\|` with `_` in `queue-fcm-device.ts`; one-off re-subscribe | BFF | Yes | 1 day |
| 11 | My Picks defaults the region to `us` | Use `resolveUserRegion` in the My Picks resolver | BFF | Yes | ½ day |
| 12 | Free users can see an `edge_pick` up to 60 s stale | Accept; locked picks show few live values and subscribers aren't cached | — | — | — |

Suggested order:

1. With the v7 release: #2, #6, #8 (part of building option B).
2. As soon as possible, server-only: #1, #1e, #10, #11 (they fix today's problems for every build).
3. Before any league's derived documents go live: #3, #4, #5, #9 and the product decisions below.
4. After that: #7, if Format A leagues need more than one game pick.

Roughly 10–14 BFF days and about one app day on top of the option B work.

## What can't be fully fixed

Three residuals remain after the fixes above; each needs a product decision.

- **Prices already lost.** Slips saved without a snapshot whose pick has already dropped out (NBA line moves today) can't get their price back: the documents were overwritten. With #1 they show as unavailable instead of zero.
- **Push in the store build.** 1.1.66 draws an item as `outcome ? tick : cross` and a group as lost if any item is falsy. A push or void sent as 2 shows a tick; sending null would show a loss, which is worse. #4 makes the payout correct, but the old app cannot label a push. Decide: accept the tick (stake back, not lost) or leave push ungraded where the old build can't show it.
- **Grading a slip leg whose pick XO cancelled.** The user's real bet with the bookmaker still settles; XO only stopped backing the pick, and the producer record for a cancelled pick has no outcome. Decide whether My Picks grades that leg on the actual result (the engine would have to settle the selection) or treats it as void. Until then: cancelled in the new app, void in the old app.

## Based on

- mobile-server `feat/edge-picks` (`35f6f44`): `src/functions/edge-picks-v4.ts`, `src/contracts/edge-picks/`, `src/lib/edge-picks/`; `src/lib/match/api-version.ts` (version gates); `src/freemium/registry/strip-helpers.ts` (v3 key-name denylist)
- mobile-app `main` (`137f2f61`) and `origin/feat/XTP-125-Edge-Picks-Redesign-Oct26` (`88de3461`): `useTopPicksScreen.ts`, `EdgePicksCard.tsx`, `bookmakerOdds.ts`, `edgePickTitle.ts`, `useAppConfig.ts` (`DEFAULT_API_VERSION`)
- This folder: [kdds.md](kdds.md) (KDD-001 to KDD-003), [kdd23-design.md](kdd23-design.md), [bff-to-app-contract.md](bff-to-app-contract.md), [option-b-plan.md](option-b-plan.md); and [../coexistence-approach.md](../coexistence-approach.md)
