# Co-existence and cutover

Oct 17, 2026 · @Tze Liang

Yes, three schema families can run side by side with no disruption users can see, but not with the BFF as it is today. Every content query is `SELECT *` by date or `game_sk`, with no `doc_type` filter, and documents are chosen by shape with last-wins precedence. The first v3 document written into a shared container would therefore produce duplicate games, blank predictions or a randomly chosen outcome.

Seamless co-existence needs five things, in this order:

1. Each game is pinned by its scheduled start to one schema family for its whole life; historical games stay on the schema they were published in, with no backfill.
2. The BFF ships v3 readers and doc-type-filtered queries before any producer writes v3.
3. Every family is normalised into one internal model before rendering, so the app and every response shape stay unchanged.
4. Each league is shadow-run on production inputs into containers no user reads and compared, then cut over cleanly on a date. There is no production overlap.
5. The cutover date lives in the registry, and both the Publish Engine and the BFF read it, so they never disagree about a game's family. Rollback moves that date.

One change is an intended product change, so it should be announced rather than hidden: picks now survive a line move.

## What breaks today if a v3 document lands

v3 reuses the same containers (`event` in `c-sch`, `game_projections` and `game_picks` in `c-wltp`, `player_projections` and `player_picks` in `c-ps`, `event_result` in `c-outcomes`) with new doc types. That keeps ids from colliding, but every current read path sees the new documents.

| Read path | What happens | Evidence |
| --- | --- | --- |
| Match list and top predictions: schedule by `game_datetime` window | v3 `event` documents either appear as a second copy of each game (if they carry `game_datetime`) or are missed entirely (if not) | `SELECT *` with a league filter only: `matches-v3.ts`, `matches-top-predictions-v3.ts:135` |
| Game prediction chooser | Looks only for `game_prediction`; with v3-only documents, `hasModular` is true and no legacy document exists, so it returns null: the game shows no prediction, silently | `lib/match/canonical/docs.ts`, `choosePredictionDoc` |
| Player chooser | Looks for `player_predictions` or a `teams[]` shape; `player_projections` is ignored, so player tables are empty | same file, `choosePlayerDocs` |
| Outcomes by `game_sk IN (...)` | Returns both a legacy `outcome` and a v3 `event_result` for the same game; the mapper keeps whichever comes last | `matches-top-predictions-v3.ts:166-180` |
| Match detail by `game_sk` (number or string) | Every document for the game comes back; which one each mapper uses depends on result order | `match-v3.ts:104-127` |
| Free-user redaction | Strippers match key names (`decimal_odds`, `market_odds`, …); v3 names such as `entry.price`, `outcome_probs`, `edge_prob`, `ev` are not on the lists, so premium values would reach free users | `freemium/registry/strip-helpers.ts` |
| My Picks | Slips store legacy `predictionId`s; v3 `pick_id`s differ, so items fall back to the creation snapshot (stale odds) or to placeholders (`xoProbability: 1`, `marketOdds: 0`) | `lib/my-pick/resolve-my-picks-list.ts:247-296` |
| Follows and deep links | Pick follows are keyed `${prediction_type}:${id}`, so a new id breaks them; game follows and push topics use `game_sk`, which stays stable | app `TopPicksList.tsx:94`, BFF `service-bus-push-events.ts:152` |
| Response cache | Bodies cached for 60 s by endpoint, date and api version keep serving pre-switch content across a flip | `freemium/cache/response-cache-keys.ts:43` |

The same exposure already exists between Format A and NBA 2026, which is why the choosers carry migration-overlap comments (CR-10, CR-15). Adding a third family to shape-based selection multiplies those cases instead of removing them.

## Design rules for seamless co-existence

**C1. Pin each event to one family for its whole life.** The registry holds a cutover per league, for example `{ league: nfl, family: v3, from_event_start: <date> }`. The Publish Engine decides an event's family once, from its scheduled start, and writes every document for that event (schedule, projections, picks, results) in that family. A postponed game keeps its family. This removes the hardest cases: a game with a legacy schedule but v3 picks, or a pick issued under one model and settled under another. The event document carries `family` so the BFF knows before it reads anything else.

**C2. Readers first.** The BFF ships v3 readers and changes every content query to name its doc types (`c.doc_type IN (...)`, with a single explicit legacy branch for Format A documents that lack one) before the Publish Engine writes any v3 document. Selection by shape and last-wins goes; selection is by `family` and `doc_type`, with a deterministic order (`ORDER BY c._ts`) wherever two versions could exist.

**C3. One internal model, many adapters.** Format A and NBA 2026 documents are translated into the v3 internal model at read time; v3 documents pass through. Every response shape (the v1 to v3 routes, `/v4/edge-picks`, later SDUI screens) renders from that one model. This reverses today's `normaliseWltp`, which turns canonical documents back into legacy names. Old app builds keep exactly the responses they get now.

**C4. Redact the model, not the document.** Free-user locks apply by field group to the internal model after translation, as `/v4/edge-picks` already does. A new source shape then cannot leak a premium field.

**C5. No id bridge.** With a clean cutover no game is ever published in both families, so every saved slip and follow resolves against its own game's documents, old or new. `legacy_ids[]` can be dropped from the v3 pick. Game ids need no bridge either, because `event_sk` equals `game_sk`.

**C6. Shadow before production, then a clean cutover.** For each in-season league, the Publish Engine runs v3 from production inputs into containers no user reads (the idle blue/green slot, or a dedicated shadow set). A staging BFF pointed at them renders every route, and a diff job compares its responses with what production served for the same games. When a full slate cycle is clean, the league cuts over: games scheduled on or after its cutover date are published in v3 only. Production never holds both families for one game, and the production BFF never reads two versions of anything.

**C6a. Rollback.** Fix forward first: correct the producer and re-publish the affected games from their gold tables. If that is not quick enough, move the league's cutover date later. The Publish Engine re-publishes the games not yet started in the legacy family, and the BFF, reading the same date, ignores their v3 documents. The new date must fall after every game whose v3 picks are already published, so no saved slip points at a pick that disappears; those games stay on v3 and are fixed forward. This needs the legacy transforms kept deployable for a few weeks after each cutover.

**C7. History stays where it was published.** Games that started before their league's cutover keep their Format A or NBA 2026 documents for good, and the BFF reads them through read-only adapters. Nothing is backfilled. This is safe because a settled game's documents stop changing, so each adapter is tested once against frozen fixtures and then left alone. The costs are small: the adapters live as long as the app shows that history, and the legacy writers stay on until the last legacy-pinned game has settled, plus any scoring corrections.

**C8. Keep meaning, not just shape.** Adapters translate semantics: NFL's legacy `edge` is EV and maps to `ev`, NBA's to `edge_prob`; legacy status words map to the v3 lifecycle; `player_sk` arrives as a number or a string and is normalised. A historical pick must show the same number after the switch as before it.

**C9. Flush and key caches by family epoch.** Response-cache keys include the league's cutover epoch, so a flip never serves a mixed body.

## One league's cutover

&#91;embedded content: one league's cutover · 5 phases, 4 lanes\]

The shadow in phase 2 runs outside production, so users are never exposed to it. Phase 3 is a single switch per league, keyed on scheduled start, and with a clean shadow it should change nothing users see. In phase 5 nothing is migrated: past games simply stay on their original schema.

## League by league

The season calendar decides how much co-existence each league needs. A league switched in its off-season has no live data to protect, so it can backfill and move outright.

| League | Today | Season status | Approach | Legacy reads afterwards |
| --- | --- | --- | --- | --- |
| WNBA | Format A | Ends 1 Nov | No co-existence: the season ends on Format A; any next season starts on v3 | Format A adapter for past games |
| MLB | Format A | Ends 1 Nov | Same as WNBA | Format A adapter for past games |
| NBA | NBA 2026 canonical | Season began 20 Oct | Shadow for at least one full week of games, then cut over on a light slate, after Edge Picks v4 is live | NBA 2026 adapter for earlier games |
| NFL | Format A | Mid-season, weekly slates | Shadow for at least two full weeks (Thursday to Monday), then cut over at a week boundary | Format A adapter for earlier weeks |
| EPL | Format A | Mid-season | Shadow for at least two match weeks, then cut over at an international break | Format A adapter for earlier match weeks |

So live co-existence matters for three leagues only: NBA, NFL and EPL. NBA is the riskiest, because it is in season, on a different family from the others, and is the Edge Picks pilot. Its flip date should follow the Edge Picks v4 live launch, not precede it.

## What can be invisible and what cannot

| Area | Invisible to users? | Condition |
| --- | --- | --- |
| Game lists and details | Yes | C1, C2, C3 |
| Pick cards, live and past | Yes | C3; clean shadow (C6) |
| Old app builds | Yes | The BFF keeps every response shape (C3) |
| Historical games and their numbers | Yes | Read in place through adapters (C7), meaning kept (C8) |
| My Picks slips and pick follows | Yes | Each resolves against its own game's family (C5) |
| Track record and ROI | Yes | Legacy games keep their legacy grades; v3 grading applies only to v3-pinned games; totals combine both |
| Rollback | Mostly | Not-yet-started games move back to legacy (C6a); games whose v3 picks are published are fixed forward |
| Free-user locks | Only with C4 | Without it, premium fields leak |
| Line-move behaviour | No, by design | v3 keeps a pick after a line move, while NBA 2026 drops it. It applies from each league's cutover and should be announced with the Edge Picks redesign |

The shadow costs Cosmos throughput and Publish Engine runtime in the shadow containers for its duration, not in the containers users read, and needs no production BFF code beyond the readers.

## Tests that prove it

- **Equivalence.** The mock generator emits the same games in every family. Every BFF route, at every `api_version`, must return identical responses for a game whatever family it was published in, apart from a listed set of intended differences.
- **Straddle scenarios.** Each of these is a named scenario in the generator:
  - a game postponed across its league's cutover date;
  - a day whose games span the cutover date in a user's time zone;
  - a free user viewing a v3 game (the leak sweep extended to v3 shapes);
  - a cached response across the cutover;
  - a rollback that moves the cutover date later.
- **Mixed day.** One date with games from all three families on the list, the Edge Picks tab and My Picks.
- **Shadow diff.** Per-league reports of differences by field between the shadow and production, with the clean criterion agreed before the shadow starts.

## Open decisions

Decided on 17 Oct:

- The cutover key is each game's scheduled start.
- Historical games stay on their original schema; nothing is backfilled.
- Legacy games keep their legacy grades in the track record.
- WNBA and MLB end on 1 Nov and need no co-existence.
- The partner API is out of scope.

Still open:

- Recommended: shadow, then a clean cutover, with no production overlap (C6). Needs sign-off.
- The clean criterion for each league's shadow, for example no unexplained differences across a full slate cycle.
- The cutover date for each of NBA, NFL and EPL.
- How long the legacy transforms stay deployable after each cutover.
