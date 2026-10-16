# Edge Picks v4 — App-first Data Contract

Oct 16, 2026 · @Tze Liang

This specification defines what the Edge Picks redesign needs from every system involved, and how each implementation is checked. It is implementation-neutral: any team can build any part of it, and section 10 lists the acceptance criteria an implementation must pass.

**Status:** draft for review (contract version 4.0.0). **Reading the rules:** MUST and MUST NOT are requirements; SHOULD is a strong recommendation that needs a stated reason to skip; MAY is optional. Statements about existing systems describe them as of 16 Oct 2026 and are marked as observations, not requirements.

**Inputs:** [Edge Picks redesign](https://xosports.atlassian.net/wiki/spaces/PB/pages/726237185/Edge+Picks+redesign) (product requirements and designs), [Bet Engine Roadmap](https://claude.ai/artifact/FX29b7SibKX5gx1SiyLpvH) (Phases 1A, 1B, 2), the live edge monitor design (live-odds), the live scores app integration guide (live-scores), and the Publish Engine container references.

## 1. Purpose, scope and principles

The app defines the data it needs; upstream systems produce it. This reverses the past pattern where backend document shapes dictated app logic, and lets each layer be built, replaced or audited on its own.

**In scope:** the Edge Picks screen (collapsed and expanded cards, Market Movement, cancelled cards, filters, sort, sport colours), free-user locking, US and AU regions, live updates to the price and edge, and the data each upstream system must supply for them.

**Out of scope:** My Picks slip storage, push notifications, the WordPress feed, the live in-game score screens (covered by the live scores integration guide), and model training.

**Principles** (each is enforced by acceptance criteria in section 10)

1. **Consumer-defined contract.** The app-facing contract in section 4 is the source of truth. Upstream schemas exist to satisfy it, and changes to it are reviewed by the app team first.
2. **Facts and decisions upstream, presentation downstream.** Producers send typed, structured values (market, side, line, odds, probability, status codes). They never send display copy or encoded strings that need parsing.
3. **One owner per value.** Every number and state shown on the card is computed in exactly one system. Other systems map it; they never recompute it.
4. **Explicit mapping.** The BFF builds each response field from a defined source. An upstream field that this spec does not define never reaches the app.
5. **Shape-stable live data.** The fields that describe the current market keep the same names and meaning however they are delivered (snapshot or realtime overlay), so delivery can change without a contract change.
6. **Additive change.** New optional fields are allowed at any time. Renames, removals or changes of meaning need a new major version.

## 2. System context and ownership

Six components take part. The app gets everything through two paths: one snapshot from the BFF, and realtime overlays it merges on top by id.

&#91;embedded content: System context · 6 components, 2 delivery paths\]

The dashed link is the one piece of plumbing this spec adds: the edge monitor's latest observation per pick reaches Cosmos through the Publish Engine, which stays the only writer of edge pick documents. The snapshot, and receipts after kickoff, can then carry it without the BFF reading the realtime database.

| Component | Owns | Must not |
| --- | --- | --- |
| Bet engine (ML team) | Picks, probability, projection, entry odds and line, entry edge, stake units, pick status and reason code, audit trail | Write display copy; change a pick's selection or stake after publish |
| Publish Engine (data engineering) | Moving bet engine output, and the edge monitor's latest observations, into Cosmos documents as their only writer; enforcing the producer schema (section 8) | Silently pass values outside the agreed vocabulary |
| Live edge monitor | Current price and line per pick before kickoff; edge state; closing value at kickoff | Use a pick id different from the Cosmos one; write to edge pick documents |
| Live scores service | Authoritative in-game state and completed-game records | — |
| BFF | Joining picks with games and teams, region rules, display copy for codes, free-user locking, ordering, contract validation, versioning | Recompute any value owned upstream; pass through undefined fields |
| Mobile app | Rendering, local time, odds format by region, dollar amounts from the user's standard bet, merging overlays | Business rules: edge, state or status logic |

## 3. Design requirements mapped to the contract

Every element of the redesigned card maps to one contract field and one owner. The card core is available today or in Phase 1A; the Market Movement box has a source only for NFL before kickoff, which section 11 escalates.

Availability key: **Today** = served now · **1A** = Bet Engine Phase 1A (31 Oct) · **Ask** = addition this spec requests · **1B** = one standard schema (1 Dec) · **None** = no committed source.

| Design element | Contract field(s) | Owner | Available |
| --- | --- | --- | --- |
| Sport chip and card colour | `sport` | BFF | Today |
| Pick title ("Cade Cunningham Over 24.5 PTS") | `selection.label`, `market`, `side`, `stat`, `team`, `player`, `entry.line` | BFF composes from producer fields | Today by parsing codes; structured fields: Ask (1B) |
| Game line ("Pistons @ Nuggets · 10:00pm") | `game.label`, `game.starts_at` | BFF | Today |
| Upcoming / Live / Final chip | `game.state` | Live scores service, schedule | Live scores in dev only (X14); schedule status in tst |
| "Picked at 2:40 PM" | `picked_at` | Bet engine | 1A; WNBA player picks have no publish time: Ask |
| Probability wheel | `model.probability` | Bet engine | Today |
| XO Projection | `model.projection` | Bet engine | Today |
| Bookmaker name or "Avg. Odds" | `entry.source`, `current.source` | Bet engine (book id), BFF (name) | 1A names one book; a book per price: Ask; true AU average: None |
| Entry odds and line | `entry.odds`, `entry.line` | Bet engine | 1A |
| Entry edge ("+9% Edge") | `entry.edge` | Bet engine | 1A |
| Rec. Bet Size ($) | `entry.stake_units` | Bet engine (units); app (dollars) | 1A |
| Payout ($) | from stake and `entry.odds` | App | 1A |
| "This edge stays positive above −125" | `edge_holds_above` | Edge owner (D3) | Once D3 is settled |
| Market Movement: current line | `current.line` | Live edge monitor | NFL in dev only (X14); others: None |
| Market Movement: current odds | `current.odds`, `current.source`, `current.observed_at` | Live edge monitor; bet engine hourly | 1A hourly, with observation time (required); NFL monitor in dev only (X14) |
| Market Movement: current edge | `current.edge` | Edge owner | Same line: derivable; moved line: None |
| Edge still in play / closed | `edge_state` | Live edge monitor | NFL in dev only (X14); others: None |
| Rec. Action (Play / Watch / Pass) | `action` | Product thresholds, engine computes | None: null until decided (D4) |
| Cancelled card and reason | `status`, `status_reason` | Bet engine (code); BFF (copy) | Status 1A; reason: Ask |
| Prediction Correct / Incorrect / Void / Push | `result` | Bet engine settlement | Today (push: confirm) |
| Receipt after kickoff (closing price) | `current` with `is_closing` | Live edge monitor history | Required, not built |
| All / Player / Game filter | `kind` | BFF | Today |
| Sort by Edge / Probability / Odds | `entry.edge`, `model.probability`, `entry.odds.decimal` | App | 1A |
| Locked card (free users) | `access` | BFF | Today |

## 4. Snapshot API contract (app ↔ BFF)

One authenticated call returns every pick for the user's local day: `GET /v4/edge-picks`. There is no paging; the app filters and sorts on the device.

### 4.1 Request

| Parameter | Type | Required | Meaning |
| --- | --- | --- | --- |
| `date` | `YYYY-MM-DD` | Yes | The user's local calendar day |
| `tz_offset` | number, hours, −14 to 14 | Yes | The user's UTC offset, used to turn the local day into a UTC window |
| `sport` | `nba`, `nfl`, `mlb`, `wnba`, `epl` | No | Return one sport only |

The day contains every pick whose `game.starts_at` falls between local midnight and the next local midnight at `tz_offset`. Offsets may be fractional (5.5, 5.75); the app MUST send its offset, because the default of 0 is wrong for most users. Authentication, entitlement, the user's region and `api_version` are handled exactly as on the existing match routes. Region is never a request parameter outside mock mode. Team, player and stat display data come from the BFF's existing reference data.

### 4.2 Response

Notation: TypeScript-style types. Every field is always present; `| null` marks the fields that may be empty.

```typescript
EdgePicksResponse {
  contract_version: string      // "4.<minor>.<patch>"
  source: "live" | "mock"
  date: string                  // YYYY-MM-DD; echoes the request
  region: "us" | "au"
  generated_at: string          // ISO 8601 UTC; not part of the ETag
  picks: EdgePick[]
}

EdgePick {
  id: string                    // 8.2; same id in Cosmos, overlays and My Picks
  overlay_key: string | null    // key of this pick's edge overlay nodes (7.2); null if none or not readable by this user
  sport: "nba" | "nfl" | "mlb" | "wnba" | "epl"
  kind: "game" | "player"
  game: Game
  selection: Selection | null   // null when hidden for a free user
  picked_at: string             // first publish, ISO UTC; never changes
  model: {                      // model output at entry; never changes
    probability: number | null; projection: Projection | null
  }
  entry: {                      // fixed at first publish
    odds: Odds | null; line: number | null; edge: number | null
    stake_units: number | null; source: OddsSource
  }
  current: {                    // the market now, or at close
    odds: Odds | null; line: number | null; edge: number | null
    source: OddsSource | null; observed_at: string; is_closing: boolean
  } | null                      // null until a market has been observed
  edge_holds_above: Odds | null // price at which the edge falls to the threshold t (break-even when t = 0)
  edge_state: "live" | "narrowing" | "closed" | "suspended" | "unknown"
  action: "play" | "watch" | "pass" | null
  status: "open" | "awaiting_result" | "cancelled" | "settled" | "void"
  status_reason: { code: ReasonCode; message: string } | null
  result: "won" | "lost" | "push" | "void" | null
  access: { locked: boolean; hidden: FieldGroup[] }
}

Game {
  id: string                    // the game_sk, as a decimal string
  starts_at: string             // ISO UTC
  label: string                 // "Pistons @ Nuggets"
  state: "upcoming" | "live" | "delayed" | "interrupted" | "final" | "postponed" | "cancelled"
  home: Team; away: Team
}
Selection {
  label: string                 // "Cade Cunningham Over 24.5 PTS"
  market: "moneyline" | "spread" | "total" | "draw" | "btts" | "player_prop"
  stat: { code: string; label: string } | null
  side: "home" | "away" | "over" | "under" | "yes" | "no" | "draw"
  team: Team | null
  player: { id: string; name: string; team_id: string } | null
}
Team { id: string; name: string; short_name: string; abbreviation: string; image_code: string }
Projection { value: number; unit: string; label: string }
Odds { decimal: number /* > 1, 4 dp */; american: integer }
OddsSource { kind: "bookmaker" | "market_average"; id: string | null; name: string }
ReasonCode = "probability_moved" | "market_moved" | "line_moved" | "lineup_change" | "withdrawn" | "game_void"
FieldGroup = "selection" | "odds" | "probability" | "projection" | "stake" | "edge"
```

### 4.3 Field rules

- Edge values are fractions (0.09 = +9%). Probability is 0 to 1 and is the model's value at entry. Times are ISO 8601 UTC; the app converts to local time.
- Odds always carry both formats; the app shows American for US and decimal for AU.
- `entry` never changes after first publish. `current.is_closing` is true once the game has started and `current` holds the last observation before kickoff.
- `current.line` different from `entry.line` means the line has moved. `current.edge` after a move comes only from the edge owner; otherwise it is null. When a producer guarantees that its current odds are at the entry line (Phase 1A), the BFF sets `current.line` equal to `entry.line`. Current odds without an observation time are never shown: the BFF sets `current` to null and never infers a time.
- `status_reason` is present only for `cancelled` and `void`, and MAY be null there until producers send reason codes. `result` is present only for `settled` and `void`.
- `action` stays null until product thresholds exist (D4). The app MUST hide the Rec. Action slot when it is null.
- `overlay_key` is null when the pick has no overlay or the user may not read it (7.4); the app MUST use it as given and never build keys itself.
- `game.state` and `status` are independent; section 5 defines both and how the card combines them.

**Line sign convention**

| Market | `entry.line` / `current.line` | Example |
| --- | --- | --- |
| Spread | From the backed side's view; negative when the backed side gives points | Chiefs −3.5 |
| Total | The total, positive | Over 215.5 |
| Player prop (threshold) | The threshold, positive | Over 24.5 PTS |
| Moneyline, draw, BTTS, yes/no props | null | Arsenal Moneyline |

### 4.4 Ordering, versioning and release gating

- Picks are ordered by `game.starts_at` ascending, then `entry.edge` descending with null edges last, then `id` in code-point order.
- The app's own sorts (Edge, Probability, Odds) default to descending, put nulls last in both directions, and break ties by game start, then `id`.
- The route's major version (`/v4`) changes only for breaking changes. `contract_version` changes its minor number for additive fields and its patch number for clarifications.
- Clients MUST ignore unknown fields and show a neutral fallback for unknown enum values.
- The existing league release gate applies: picks for a staged league or season are withheld from app builds below the release `api_version`, exactly as on the other match screens.

### 4.5 Caching and errors

- Responses MUST carry an `ETag` computed over everything except `generated_at`; a request with a matching `If-None-Match` gets `304 Not Modified`. Responses differ only by date, offset, sport, region, access tier and `api_version`, so the server MAY cache them on those keys.
- Error responses have the body `{ "error": <code>, "details": <optional> }`. Codes: `invalid_query` (400), `unavailable` (503); authentication errors as on other routes.
- A pick that fails contract validation is left out and reported to monitoring. The server MUST NOT send an off-contract pick.

### 4.6 Mock mode

The BFF SHOULD offer a non-production mock mode so the app can be built ahead of upstream work. Mock responses set `source` to `mock` and serve the scenarios in section 10.6. Mock mode MAY accept extra parameters (scenario, forced free-user view, region). It MUST be impossible to enable in production: the production configuration rejects it at startup, and a production response with `source` set to `mock` is a defect.

## 5. State model

A card combines four independent states: the pick's lifecycle, its result, the game's state and the edge state. Each has one owner and a fixed mapping from upstream values, so two implementations given the same inputs must show the same card.

### 5.1 Pick status

| Status | Meaning | Next states |
| --- | --- | --- |
| `open` | Published; before the cutoff; the market is still watched | `awaiting_result`, `cancelled`, `void` |
| `awaiting_result` | Cutoff passed; no result yet | `settled`, `void` |
| `cancelled` | Withdrawn before the start | none |
| `settled` | Result known | none |
| `void` | Game postponed or cancelled, or the market voided | none |

**Cutoff** is the authoritative game start (`game.starts_at`, or the actual start when the game state source reports it) unless D13 sets it earlier. The producer owns transitions; the BFF maps the current upstream value on every request and keeps no state of its own. A pick published in error (`removed` upstream) is never sent and never counts in records or ROI.

**Mapping from upstream values.** The BFF MUST apply this table and nothing else; an unlisted value drops the pick and raises an alert.

| Upstream value (where it appears today) | Contract `status` | Contract `result` |
| --- | --- | --- |
| `active` (roadmap), `Scheduled` (NFL today), `scheduled`, `pending` (NBA split documents) | `open`; `awaiting_result` once the cutoff has passed | null |
| `expired` (roadmap) | `awaiting_result` | null |
| `cancelled` | `cancelled` | null |
| `settled` with outcome 1 / 0 / push | `settled` | `won` / `lost` / `push` |
| `won`, `lost`, `push` (NBA split documents) | `settled` | same value |
| `void`, `abandoned`, or outcome 2 | `void` | `void` |
| `rescheduled` | `open` | null |
| `removed` | not sent | — |
| Any other value | not sent; the BFF raises an alert | — |

### 5.2 Game state

Game state comes from authoritative status, never from the clock alone.

| Source signal | `game.state` |
| --- | --- |
| Scheduled and not started | `upcoming` |
| Live scores `live` | `live` |
| Live scores `delayed` | `delayed` |
| Live scores `suspended` (play stopped, may resume) | `interrupted` |
| Live scores `completed`, or a completed-game record | `final` |
| `postponed` | `postponed` |
| `canceled`, `not_necessary` | `cancelled` |

The contract says `interrupted` rather than `suspended` so a stopped game is never confused with a suspended market. For sports the live scores service does not cover yet, the BFF uses schedule and outcome status, and MUST move a game from `upcoming` to `live` once `starts_at` has passed and no source reports `postponed`, `cancelled` or `final`. The clock never overrides an authoritative status.

### 5.3 Edge state

The live edge monitor owns edge state. Any other system that computes it for sports the monitor does not cover MUST use these rules and pass the examples in section 10.3. Rules are checked in order; the first match wins.

1. `unknown`: no market observation yet.
2. `suspended`: no current price, or the book has pulled the outcome. This means "we don't know", never "the edge closed".
3. `closed`: the current line differs from the entry line, in either direction (D2 may narrow this to adverse moves only).
4. `closed`: the current decimal price is at or below the break-even price *b*.
5. `narrowing`: the entry price is above *b* and the current price is at or below the midpoint *m* between the entry price and *b*.
6. `live`: otherwise.

```latex
b = \frac{1 + t}{p} \qquad m = \frac{d_{\text{entry}} + b}{2}
```

Here *p* is the model probability at entry, *t* is the expected-value threshold the bet engine publishes picks with (0 today), and *d* is a decimal price. Rules apply only while `status` is `open` and the game has not started. After that, `edge_state` is the state of the closing observation (`is_closing`) and is shown only as part of the receipt.

**Precision.** *b* and *m* are computed from unrounded inputs, then rounded to 4 decimal places: b down (toward zero), so a price at the published b never has an edge above t; m half away from zero. Prices are compared at 4 decimal places. Line equality is numeric (24.5 equals 24.50). Without a fixed precision, two correct implementations can disagree at the boundaries.

**Staleness.** The Market Movement box always shows when its price was observed ("as of 14:05", local time). The observation is stale when `current.observed_at` is more than 2 hours old (twice Phase 1A's hourly cadence) or, for an overlay, when its `next_update_due` passed more than 15 minutes ago. A stale box keeps its price and time, is marked stale, and hides the edge state indicator. The app evaluates staleness on its own clock, so an open screen goes stale without a new request; a fresh observation clears it. The 2-hour limit is revised when a producer's cadence changes (Phase 2).

### 5.4 How the card combines them

Apply the first rule that matches; together they cover every combination of status and game state.

1. `cancelled`: greyed out with the reason (if present); no Add Pick; no payout.
2. `void`: Prediction Void chip; no payout.
3. `settled`: Correct, Incorrect or Push chip; payout as in 6.1.
4. Otherwise (`open` or `awaiting_result`): full colour, with the chip for `game.state` (Upcoming, Live, Delayed, Interrupted, Final, Postponed, Cancelled).
5. Market Movement updates only while `status` is `open` and `game.state` is `upcoming`; in every other case it shows the closing or last values, frozen.
6. Add Pick is enabled only while `status` is `open` and `game.state` is `upcoming`.

Edge state treatment: `live` and `narrowing` in green ("still in play"), `closed` in red ("outside edge"), `suspended` neutral ("no current price"), `unknown` with no indicator. Product confirms the copy and colours (D11).

## 6. Derived values, ownership and free-user access

Every derived number has one formula and one owner. A layer that is not the owner MAY compute a value only where this section allows it, and then MUST produce exactly the owner's result.

### 6.1 Formulas

```latex
\text{edge} = p \times d - 1 \qquad \text{edge} \le t \iff d \le b
```

The edge definition is provisional until the bet engine confirms it (D3). It is consistent with the edge monitor's break-even rule: because *b* is rounded down (5.3), a 4-decimal price at or below *b* is exactly a price whose edge, computed from unrounded inputs, is at or below the publishing threshold *t*. With p = 0.55 and t = 0, 1.8181 gives an edge of −0.000045 (closed) and 1.8182 gives +0.00001 (narrowing).

| Value | Rule | Owner | Who else MAY compute it |
| --- | --- | --- | --- |
| `entry.edge` | p × entry price − 1, at first publish | Bet engine | Nobody |
| `edge_holds_above` | *b* = (1 + t) / p, as odds | Edge owner | BFF, only with *t* supplied by the producer, never hard-coded |
| `current.edge`, line unchanged | p × current price − 1 | Edge owner | BFF, same formula |
| `current.edge`, line moved | P(selection at the new line) × current price − 1 | Edge owner | Nobody; null if not supplied |
| `edge_state` | Section 5.3 | Live edge monitor | Another system for uncovered sports, passing section 10.3 |
| `action` | Product thresholds on current edge | Bet engine | Nobody; null until D4 |
| `status_reason.message` | Copy for each reason code | BFF | Nobody |
| `entry.source.name, current.source.name` | Book display name; "Avg. Odds" for a market average | BFF | Nobody |
| Bet size ($) | `stake_units` × the user's standard bet | App | Nobody (D9 confirms 1 unit = standard bet) |
| Payout ($) | Won: bet size × entry decimal price (total return). Push or void: the bet size back. Lost: nothing | App | Nobody |

**Odds conversion.** Decimal *d* ≥ 2 gives American +round((d − 1) × 100); *d* < 2 gives round(−100 / (d − 1)). American *a* > 0 gives 1 + a / 100; *a* < 0 gives 1 + 100 / −a. Rounding is half away from zero throughout, except b, which is rounded down (5.3): decimal odds to 4 places (the app displays 2), American odds to whole numbers, dollars to cents.

### 6.2 Free-user access

Which picks a free user sees in full follows the existing freemium rules unchanged: subscribers see everything; completed picks (status settled or void, or game final) are unlocked; for each enabled sport, the top picks by probability (within the configured range and count, ranked over the whole day) are unlocked; all other picks are locked. What a locked pick hides is set by these field groups.

| Group | Fields set to null | Freemium flag |
| --- | --- | --- |
| `selection` | `selection`, `entry.line`, `current.line` | `show_pick_description` |
| `odds` | `entry.odds`, `current.odds`, `edge_holds_above` | `show_market_odds` |
| `probability` | `model.probability`, `edge_holds_above` | `show_xo_probability` |
| `projection` | `model.projection` | `show_projection` |
| `stake` | `entry.stake_units` | `show_stake` |
| `edge` | `entry.edge`, `current.edge`, `action`; `edge_state` becomes `unknown` | `show_xo_edge` |

- A group is hidden when its flag is not explicitly true. A field in a hidden group MUST be null in the response; the app shows a lock, never a zero.
- Probability, odds and edge are linked by edge = p × d − 1 (current edge and current odds the same way), so any two give away the third. Either none of these three groups is hidden, or at least two are. When exactly one would be hidden, the BFF also hides the edge group if that one is probability or odds, and the probability group if that one is edge. Groups added this way are listed in `access.hidden`.
- The BFF applies this rule to every response, whatever the configuration, so a settings change cannot reintroduce the leak. Because a configuration that hides exactly one of the three groups then displays differently from what it says, the freemium settings review SHOULD warn about such a configuration.
- `access.locked` is true when any group is hidden, and `access.hidden` lists every hidden group.
- `entry.source` and `current.source` (the book name) belong to no group, so a locked card still shows which book the pick is against. Product confirms this in D11.
- `overlay_key` is null for a locked pick unless the overlay owner enforces the same groups (7.4).
- The same rules bind every realtime overlay (7.3 and 7.4).

## 7. Live updates

The snapshot is required for every sport; realtime overlays are added sport by sport where a live producer exists. Both carry the same `current` fields, so the app's card logic does not depend on which one delivered them.

### 7.1 Delivery modes

| Mode | Scope | How the app gets updates |
| --- | --- | --- |
| Snapshot | All sports, required | Re-request on screen focus and pull-to-refresh. While the screen is visible, no more than once every 60 seconds, always with `If-None-Match`. |
| Edge overlay | Sports the live edge monitor covers (NFL; dev only today, X14) | Subscribe to the summary node of every visible card and the detail node of the expanded card; unsubscribe when they leave. |
| Live game overlay | Sports the live scores service covers (NFL, NBA, MLB, WNBA; dev only today, X14) | Subscribe per visible game while it is in progress. |

### 7.2 Edge overlay contract

Observation: the live edge monitor writes two nodes per pick in the realtime database and deletes both at kickoff. This spec adopts that shape and adds requirements.

| Node | Fields | Maps to |
| --- | --- | --- |
| `/edgePickStatus/{league}_{id}` | `edge_status`, `as_of` | `edge_state`, `current.observed_at` |
| `/edgePicks/{league}_{id}` | `pick_id`, `live_price`, `live_point`, `edge_status`, `as_of`, `next_update_due` | `current.odds` (decimal; American derived per 6.1), `current.line`, `edge_state`, `current.observed_at` |

- Overlay nodes are published under the snapshot's `overlay_key`. While D6 keeps readable keys, that key is `{sport}_{id}` with `id` exactly equal to `EdgePick.id`. Overlay records that match no snapshot key are ignored.
- `edge_status` takes only the four values `live`, `narrowing`, `closed` and `suspended`, with the meanings in 5.3. Any other value is treated as `unknown`.
- `next_update_due` is the overlay's staleness signal: once it has passed by more than 15 minutes, the app treats the overlay as stale (5.3, AC-42). The app MUST NOT use it for anything else.
- The overlay watches the book the pick was published against, so `current.source` after a merge is `entry.source` unless the overlay names another book.
- Ask: add `live_edge` (the current edge, same formula as 6.1) to the detail node. Until it exists, the app shows no current edge once an overlay price is newer than the snapshot.

### 7.3 Merge rules for the app

1. Merge each node on its own, using that node's `as_of`. The summary node can change only `edge_state`; the detail node changes `current.odds`, `current.line`, `current.edge` (from `live_edge`) and `edge_state`.
2. A node's values apply only when its `as_of` is later than `current.observed_at`. If the snapshot's `current` is null, the detail node creates it with `source` = `entry.source`, `is_closing` false, and `edge` from `live_edge` or null.
3. A missing node means "no newer data": keep the snapshot. Absence never means closed or cancelled.
4. Overlays never change `status`, `result`, `entry` or `access`, and never set a field in a group listed in `access.hidden`. With the edge group hidden, `edge_state` stays `unknown` and `current.edge` stays null; with odds hidden, `current.odds` stays null; with selection hidden, `current.line` stays null.
5. When nodes are deleted at kickoff, keep the last merged values until the next snapshot, which then carries the closing values with `is_closing` true.
6. The live game overlay sets `game.state` through the mapping in 5.2. `game.id` is the game's `game_sk`, so the overlay key is `{sport}_{game.id}`.

### 7.4 Security

These rules apply to edge overlays, which carry premium data.

- Reads MUST require a signed-in user, and listing a node's parent (for example, all of `/edgePicks`) MUST be denied.
- A free user MUST NOT be able to read an overlay field that section 6.2 hides for that pick. Pick ids are predictable, so denying listing alone is not enough; per-pick authorisation is needed. How (opaque keys issued in the snapshot only for readable picks, or entitlement claims checked by database rules) is the overlay owner's choice (D6).
- When the app learns that the user's entitlement has changed (purchase, expiry, restore, sign-out), it MUST re-request the snapshot at once and drop subscriptions for every pick whose `overlay_key` is now null. The 60-second limit in 7.1 is a rate cap, not a refresh guarantee, so it does not bound this case; the server-side control chosen in D6 bounds any remaining window by its key or token lifetime.
- Writes are server-only.

### 7.5 Live game overlay contract

Observation: the live scores service writes `/liveGameCards/{sport}_{game_sk}` while a game is in progress and deletes it shortly after it ends. This screen uses one field.

| Field | Maps to | Rule |
| --- | --- | --- |
| `st` | `game.state` | Through the table in 5.2 |

This screen reads only `st`, the game's status, which no freemium flag gates, so any signed-in user may read it. The same node also carries scores, which the `show_live_score` freemium flag gates; any screen that shows them MUST apply that flag. A missing node means the game is not in progress: keep the snapshot's `game.state`.

## 8. Producer contract (BFF ↔ upstream)

Upstream systems deliver one typed record per pick per region, with the same field names and meanings for all five sports and for game and player picks. The BFF builds section 4 from these records and nothing else.

### 8.1 Where records land

Target: one Cosmos document per game for game picks and one for player picks, with picks keyed by lowercase region (`au`, `us`), as the NBA split documents already do. Each sport moves to this shape in Phase 1B. Until a sport has moved, the BFF reads its existing documents and applies the same mappings.

### 8.2 Pick identifiers

| Pick kind | Id format | Example |
| --- | --- | --- |
| Game | `{game_sk}_{bet_type}_{region}`, region lowercase | `300019484_FAV_SPR<_au` |
| Player | `{game_sk}\|{player_sk}\|{stat}\|{type}\|{region}` | `300019484\|300123456\|RecYDs\|player_over\|us` |

- The same id MUST be used by every system: Cosmos documents, the audit log, edge overlay keys, My Picks and the snapshot.
- An id MUST NOT change when the price or line moves, and MUST be unique within a region and day.
- If two picks could share game, market (or player and stat) and side at different lines, for game picks such as alternate spreads as well as player picks, the producer MUST add the line to the id before that can happen.
- Ids MUST NOT contain `.`, `$`, `#`, `[`, `]`, `/` or control characters, so they can be realtime database keys. They may contain `<` and `|`, and are URL-encoded wherever they appear in a URL.
- Ids are frozen in this format through Phase 2; the structured fields in 8.3 do not change them. Any later change is breaking for every system, and users' saved My Picks slips reference ids, so it needs an agreed migration plan before any producer changes.

### 8.3 Fields

| Field | Type | Meaning | Status |
| --- | --- | --- | --- |
| `pick_id`, `game_sk`, `region` | string, integer, `au`/`us` | Identity (8.2) | Exists |
| `pick_kind` | `game` / `player` | Kind, not inferred from the container | Ask (1B) |
| `market`, `side` | enums as in 4.2 | Replace encoded codes such as `FAV_SPR<` and `T1_9.5_1.95` | Ask (1B) |
| `line` | number or null | Entry line, sign convention in 4.3 | Ask (1B) |
| `team_sk`, `player_sk`, `stat_code` | integer, integer, string | Backed team or player's team; one stat code list for all sports | Partly exists |
| `probability`, `projection_value`, `projection_unit` | number, number, string | Model output at the entry line | Exists |
| `pick_date_time` | ISO UTC | First publish, on every pick including player picks | 1A; WNBA player picks: Ask |
| `entry_decimal_odds`, `entry_american_odds` | number, integer | Price at first publish | 1A |
| `entry_edge`, `ev_threshold` | number, number | Edge at entry; the threshold *t* the pick was published under | 1A; `ev_threshold`: Ask |
| `stake_units` | number | Fixed at first publish | 1A |
| `odds_source_kind`, `entry_bookmaker_id` | enum, lowercase id | `bookmaker` with an id such as `fanduel`, or `market_average` with null | Ask (1A) |
| `current_decimal_odds`, `current_american_odds`, `current_line`, `current_odds_source_kind, current_bookmaker_id` | number, integer, number, enum, lowercase id | Latest observed market for this selection | 1A sends odds only; line and book: Ask |
| `observed_at`, `is_closing` | ISO UTC, boolean | When observed; is\_closing marks the last observation before kickoff and is derived by the Publish Engine | `observed_at`: 1A, required wherever current odds are sent; `is_closing`: derived, 1B |
| `current_edge`, `edge_status` | number or null, enum | Edge and edge state at the latest observation (5.3) | Ask; NFL from the edge monitor |
| `rec_action` | enum or null | After D4 | Ask (later) |
| `pick_status`, `status_reason` | enums (statuses in 8.4; reason codes as in 4.2) | Lifecycle and closed reason code, including `lineup_change` | 1A; sending the reason: Ask |
| `outcome` | `won`, `lost`, `push`, `void`, null | Settled on entry odds | Exists as 0/1/2; explicit values: Ask |
| `schema_version` | string | See 8.5 | Exists |

The latest observation (`current_*`, `observed_at`, `current_edge`, `edge_status`) reaches Cosmos through the Publish Engine, which publishes it into the edge pick document from the edge monitor's history table. The Publish Engine stays the only writer of edge pick documents; the monitor MUST NOT write to them, because two writers on one document bring back the lock contention the split-document design removed. The publish delay of 1 to 3 minutes is acceptable because realtime overlays carry the live value.

This requires the history table to have its change data feed enabled (the Publish Engine is triggered by change feeds) and the Publish Engine's service principal to have read access to it. `is_closing` is derived by the Publish Engine, not sent by the monitor: it is true on the last observation made before the game's start, and false otherwise.

### 8.4 Status vocabulary

Producers MUST send only values from one agreed list, and every system that checks or filters on status MUST accept that list before any producer sends a new value. The roadmap's list (`active`, `cancelled`, `expired`, `settled`, `void`, `removed`) and the list the Publish Engine accepts for NBA today (`scheduled`, `active`, `pending`, `won`, `lost`, `push`, `void`, `cancelled`, `rescheduled`, `abandoned`) differ; D5 picks one. The BFF maps either through section 5.1.

### 8.5 Schema rules

1. Every value is typed and stands alone: numbers as numbers, no strings to parse, no display copy.
2. A sport that cannot fill a field sends null; it never sends a different field.
3. Adding a field does not change `schema_version`. Changing it requires the readers to be updated first, in a coordinated release. Consumers MUST NOT branch on an exact `schema_version` value.

### 8.6 Conformance

1. Producers publish a machine-readable schema for each document type, generated from or checked against this section.
2. The Publish Engine's CI validates sample output against that schema and fails on any mismatch, so a non-conforming record fails a build, not production.
3. Before a sport switches to live data, the producer publishes test documents covering every status, edge state and market in that sport, and the BFF's contract tests pass against them.
4. Changes start as a reviewed change to this spec, agreed by the app team, before any producer changes.

## 9. Cross-system dependencies and release coupling

Several existing systems would break, or silently disagree, if one side changed without the others. Each row records an observation, the date it was last verified and what it was verified against, plus the requirement it forces. Tst serves production; there is no separate production environment, so observations are checked against each repository's `dev` and `tst` branches (the deploying branches), the deployment scripts and the data, never a default branch or a README. Owners re-verify their rows at every phase gate; progress on each action lives in the team tracker, not here. X1, X13 and X14 have hard dates.

| # | Observation (verified 16 Oct) | Verified against | Risk if ignored | Required action | Owner | By |
| --- | --- | --- | --- | --- | --- | --- |
| X1 | The Publish Engine rejects unknown status values on the NBA path and fails the whole batch; the older path for other sports passes any value unchecked. The edge monitor watches only picks whose status is exactly `Scheduled` (case-sensitive) and deletes the overlays of every other pick. | Publish Engine code; monitor `dev` branch | Any new value, even lowercase `scheduled`, deletes every NFL overlay; `expired`, `settled` or `removed` stop NBA publishing | Ship together: the new status list, the Publish Engine's accepted list, a check on the older path, and a case-insensitive monitor filter driven by the agreed vocabulary, with a test. Unknown values alert, and the pick stays watched: its overlay is neither deleted nor frozen (D5, AC-31). The BFF does not send picks with unlisted statuses (5.1), and the staleness rule (5.3) is the backstop if an overlay stops updating | Bet engine, data engineering, monitor owner | Oct 31, 2026 |
| X2 | The monitor builds game pick ids as `{bet_id}\|{region}` (`300019484_FAV_SPR<\|AU`); Cosmos uses `300019484_FAV_SPR<_au`. | Monitor `dev` branch; Publish Engine code | Game-pick overlays never match their cards | Monitor adopts the id rule in 8.2 (AC-32) | Monitor owner | Before overlays reach users |
| X3 | The monitor discovers new picks once a day at 06:00 UTC. | Monitor `dev` branch | Picks published later in the day get no live state; mid-day cancellations linger | Discover at the publish cadence (hourly) or on publish (AC-33) | Monitor owner | Before overlays reach users |
| X4 | In dev the monitor reads and writes the dev data catalog and the dev realtime database. Its tst configuration is incomplete (X14). Its prd settings are placeholders, which matters only once a separate production exists. | Monitor deployment script | A deployment with missing values runs against the wrong data or fails late | Deployments fail on any unset or placeholder value (AC-34) | Monitor owner | Before overlays reach users |
| X5 | Realtime read rules for edge overlays are not defined in the monitor's repository; live scores allows any signed-in user to read at the root. | Both repositories | Free users can read every pick's live price and see which picks are locked | Meet 7.4 (D6) | Monitor owner, app team | Before overlays reach users |
| X6 | Live data producers differ by sport and by branch; see the table below. | Deploying branches | Market Movement and live game state missing for most sports | Owners confirm what is deployed in tst per sport; coverage plan for edge state (D7); snapshot fallback meanwhile | Monitor owner, live scores owner, product | 1B planning |
| X7 | NBA split documents carry the region map (fixed 8 Oct), but missing `edge` and other values pass through as null without failing. | Publish Engine code | Cards show no edge with no alert | Conformance checks in 8.6; pin the live catalog | Bet engine, data engineering | 1A |
| X8 | MLB picks are decided on one book and struck at the best of three on the same line (in tst since 1 Oct). | Confluence decision record | One book name shown for a price from another book | Send a book per price (8.3) | Bet engine | 1A |
| X9 | The WNBA player pick table has no publish time. | Table schema | No "Picked at" for WNBA player cards | Add `pick_date_time` | Bet engine | 1B |
| X10 | A true AU average needs AU odds ingested first. | Roadmap | "Avg. Odds" shows US prices indefinitely | Plan AU odds ingestion; until then the label stays "Avg. Odds" over the US price (roadmap rule) | Data engineering, product | Phase 2 planning |
| X11 | The league release gate applies per route. | BFF code | A staged season leaks through the new route | Apply the gate to `/v4/edge-picks` (4.4) | BFF | Before release |
| X12 | The monitor's design rejects writing into Publish Engine documents (two writers, lock contention) and defers persisting final state to Cosmos. | Monitor design document | Snapshot current values and receipts have no source | The Publish Engine publishes the monitor's latest observation from its history table, with change data feed and a read grant (8.3, AC-35, AC-41) | Data engineering, monitor owner | 1B |
| X13 | Phase 1A refreshes current odds hourly, but the document timestamp is the first publish time and no observation time is sent. | Roadmap | Stale odds look fresh; overlay merges compare against the wrong time | Send `observed_at` with current odds in 1A (AC-36); the app shows it and applies the staleness rule in 5.3 (AC-42) | Bet engine | Oct 31, 2026 |
| X14 | Neither live service has code on the branch that deploys to tst, which serves production. The live scores `tst` branch holds only a README (30 Jun); its `dev` branch has MLB, NBA, NFL and WNBA. The edge monitor has no `tst` branch, and its tst settings are placeholders for the subscription, App Insights, managed identity and realtime database URL. The tst Azure subscription has no live scores or edge monitor resources: its resource groups are two for Data Factory and one each for inference, subscription reconciliation and subscription status. The tst Firebase project exists (the BFF's tst settings name it), but no one owns a realtime database in it for overlays and live scores. | Deploying branches; deployment scripts; tst Azure subscription; BFF tst settings | Market Movement, edge state and live game state cannot reach users; this is new infrastructure in tst, not a promotion of something already running | Name the owner of the tst realtime database; provision both services in tst (subscription, App Insights, managed identity, realtime database) and deploy them from their `tst` branches with complete configuration (AC-40); commit a delivery date. Blocks D1 option A (not A′), D7 and live game state | Monitor owner, live scores owner; realtime database owner to be named | Plan by Oct 23, 2026 Delivery date: to be committed |

**X6 detail: live data producers by sport** (tst serves production)

| Sport | Edge monitor code | Live scores code | Deployed in tst | Wired to this screen |
| --- | --- | --- | --- | --- |
| NFL | `dev` only | `dev` only | To confirm | No |
| NBA | None | `dev` only | To confirm | No |
| MLB | None | `dev` only | To confirm; if running, deployed outside the branch flow | No |
| WNBA | None | `dev` only | To confirm | No |
| EPL | None | None | No | No |

No sport is wired to this screen yet: the app has no realtime database client, and the snapshot has no source for live values until X12 lands.

## 10. Acceptance criteria and worked examples

An implementation conforms when it passes every criterion below for its part of the system; 10.9 maps each criterion to the component that must pass it and the phase gate it blocks. The worked examples are exact: inputs and expected outputs to 4 decimal places, usable directly as test cases.

### 10.1 Snapshot API (BFF)

1. **AC-1** One request returns every pick for the user's local day, with no paging.
2. **AC-2** Every response validates against section 4. A pick that fails is left out and reported; no off-contract pick is ever sent.
3. **AC-3** An upstream field that section 8 does not define never appears in the response. Test: add an unknown field to a producer record; it is absent from the response.
4. **AC-4** Picks are ordered by game start, then entry edge descending (null last), then id.
5. **AC-5** A repeated request with the returned `ETag` gets `304`.
6. **AC-6** Picks of a staged league are withheld from app builds below the release `api_version`.
7. **AC-7** While AU shows US prices (roadmap rule), the BFF presents every AU source as `market_average` named "Avg. Odds", and moneyline wording is "Win". US users see the book's display name and "Moneyline".
8. **AC-8** Every row of the mapping table in 5.1 produces the stated `status` and `result`; an unlisted value drops the pick and raises an alert; `removed` never appears.
9. **AC-9** A postponed or cancelled game never shows `live`, whatever the time.

### 10.2 Free-user access (BFF)

10. **AC-10** Subscribers: `access.hidden` is empty on every pick.
11. **AC-11** Completed picks are unlocked for everyone; within each enabled sport, the configured number of top picks by probability is unlocked.
12. **AC-12** Example: flags with only `show_market_odds` true. A locked pick has `hidden` = selection, probability, projection, stake, edge; `selection`, `entry.line`, `current.line`, `model.probability`, `model.projection`, `entry.stake_units`, `entry.edge`, `current.edge`, `action` and `edge_holds_above` are null; `entry.odds` is present; `edge_state` is `unknown`.

### 10.3 Edge state (any system computing it)

Inputs for E1–E9 and E11: p = 0.55, t = 0, entry line 24.5, entry price 2.0000 (+100). So b = 1.8181 (−122) and m = 1.9091 (−110).

All comparisons use the 4-decimal precision rule in 5.3; E6, E8 and E11 test the boundaries.

| Case | Observation | Expected `edge_state` | Why |
| --- | --- | --- | --- |
| E1 | None yet | `unknown` | Rule 1 |
| E2 | Book has pulled the price | `suspended` | Rule 2 |
| E3 | Line 25.5, price 2.1000 | `closed` | Line moved (rule 3), even at a better price |
| E4 | Line 24.5, price 2.2000 | `live` | Above m |
| E5 | Line 24.5, price 1.9500 | `live` | Above m |
| E6 | Line 24.5, price 1.9091 | `narrowing` | At m |
| E7 | Line 24.5, price 1.8500 | `narrowing` | Between b and m |
| E8 | Line 24.5, price 1.8181 | `closed` | At b |
| E9 | Moneyline (no line), price 1.7000 | `closed` | Below b; rule 3 does not apply |
| E10 | As E7 but t = 0.02, so b = 1.8545 | `closed` | 1.8500 is below b |
| E11 | Line 24.5, price 1.8182 | `narrowing` | One step above b: edge +0.00001 |

### 10.4 Derived values

| Case | Input | Expected |
| --- | --- | --- |
| D-1 | American −110 | decimal 1.9091 |
| D-2 | American −115 | decimal 1.8696 |
| D-3 | American +150 | decimal 2.5000 |
| D-4 | Decimal 1.9091 | American −110 |
| D-5 | p 0.58, price 1.9091 | entry edge 0.1073 |
| D-6 | p 0.55, t 0 | `edge_holds_above` 1.8181 / −122 |
| D-7 | p 0.55, same line, current price 1.9500 | current edge 0.0725 |
| D-8 | p 0.55, line moved, no producer value | current edge null |
| D-9 | 2 units, standard bet $10, entry −115 | bet size $20.00, payout $37.39 |
| D-10 | 1 unit, standard bet $10, entry −110 | bet size $10.00, payout $19.09 |

### 10.5 Realtime overlays (overlay owner and app)

13. **AC-13** For every monitored pick with a non-null overlay\_key, overlay nodes are published under the snapshot's overlay\_key; while D6 keeps readable keys, that key is `{sport}_{id}` with `id` byte-for-byte equal to the snapshot's.
14. **AC-14** The app applies an overlay value only when it is newer than `current.observed_at`, and keeps the snapshot value when a node is missing.
15. **AC-15** A signed-in user cannot list `/edgePicks` or `/edgePickStatus`; a free user cannot read an overlay field hidden for that pick by 6.2.
16. **AC-16** After kickoff the overlay nodes are gone and the next snapshot carries the last pre-kickoff observation with `is_closing` true.

### 10.6 Mock scenarios (BFF mock mode)

A conforming mock mode serves these scenarios, with every record internally consistent (entry edge = p × entry price − 1, at 4 decimal places):

- **Full design day:** all five sports; game and player picks; every `status`; every `edge_state`; a moved line with a producer edge; a same-line price move; a pick with no observation yet; a cancellation with `lineup_change`; a void with `game_void`; a push; an `awaiting_result` pick in a live game.
- **Phase 1A day:** the same picks limited to what Phase 1A supplies: current line equal to the entry line wherever current odds are present, no current odds for picks whose line moved, no producer current edge, `action` and `status_reason` null, `observed_at` taken from the producer's observation time (one pick more than 2 hours old, so stale), and current null where a producer sends none.
- **Empty day:** no picks.
- **Free-user view and AU region** of the full design day.

### 10.7 Producers

17. **AC-17** Publish Engine CI validates sample output against the producer schema and fails on a mismatch.
18. **AC-18** Only status values from the agreed list are sent, and every consumer accepted that list in the same or an earlier release.
19. **AC-19** Numbers are numbers; no field needs string parsing; ids do not change when price or line moves.
20. **AC-20** Before a sport goes live, its test documents cover every status, edge state and market, and the BFF's contract tests pass against them.

### 10.8 Further criteria

21. **AC-21** With `show_market_odds` and `show_xo_edge` true but `show_xo_probability` false, a locked pick also hides the edge group: `entry.edge` and `current.edge` are null and `access.hidden` includes `edge`.
22. **AC-22** The production configuration refuses mock mode at startup; no production response has `source` set to `mock`.
23. **AC-23** The app hides Rec. Action when `action` is null, and shows no current edge when an overlay price is newer than the snapshot and carries no `live_edge`.
24. **AC-24** Entry line 24.5 and current line 24.50 count as the same line.
25. **AC-25** Pick ids are unique within a region and day and contain none of the forbidden characters in 8.2.
26. **AC-26** A client write to any overlay node is rejected.
27. **AC-27** While the screen is visible, the app requests the snapshot at most once every 60 seconds and always sends `If-None-Match`.
28. **AC-28** For every combination of the 5 statuses and 7 game states, the card follows the rules in 5.4 (a table-driven test over all 35 combinations).
29. **AC-29** Payout: won, 2 units, $10 standard bet, entry −115 → $37.39; push → $20.00 back; lost → nothing.
30. **AC-30** With `tz_offset` 11 and date 2026-10-21, a game starting 2026-10-21T12:30Z is included and one starting 2026-10-21T13:30Z is not.

31) **AC-31** Monitor status filter: picks with status `Scheduled`, `scheduled`, `active` or `ACTIVE` are all watched; a `cancelled` pick is unwatched and its overlay deleted; an unrecognised value raises an alert and the pick stays watched, its overlay neither deleted nor frozen.
32) **AC-32** Joining one day's overlay keys to that day's Cosmos edge pick ids matches 100% of monitored picks, game and player.
33) **AC-33** A pick published at any time is watched within one publish cycle (60 minutes), and a cancellation clears its overlay within one cycle.
34) **AC-34** In each environment the monitor reads and writes only that environment's data catalog and realtime database; a deployment with an unset or placeholder value fails.
35) **AC-35** Only the Publish Engine writes edge pick documents; the monitor's credentials have no write access to them.
36) **AC-36** Every producer record with current odds carries `observed_at`; a record without it fails producer CI, and the BFF never shows such odds.
37) **AC-37** Mirror leaks: with probability and edge shown but odds hidden, the edge group is hidden too; with probability and odds shown but edge hidden, the probability group is hidden too. In both cases `access.hidden` lists the added group.
38) **AC-38** A locked pick whose edge group is hidden keeps `edge_state` `unknown` and `current.edge` null after any overlay update.

39. **AC-39** When the user's entitlement changes, the app re-requests the snapshot at once and holds no subscription for a pick whose `overlay_key` is null.
40. **AC-40** Each live service in use is deployed to tst from its `tst` branch with no placeholder settings, and a tst smoke test shows a monitored pick's price and a live game's state updating.
41. **AC-41** A new row in the monitor's history table reaches the edge pick document within 5 minutes, and `is_closing` is true only on the last observation before the game's start.
42. **AC-42** The app shows the observation time in Market Movement, and marks the box stale and hides the edge state indicator when `current.observed_at` is more than 2 hours old or an overlay's `next_update_due` passed more than 15 minutes ago; a fresh observation clears the stale mark.

### 10.9 Conformance matrix

| Criteria | Component that must pass | Phase gate it blocks |
| --- | --- | --- |
| 10.6 scenarios | BFF mock mode | Start of the app build (now) |
| AC-1 to AC-9, AC-22, AC-30, D-1 to D-8 | BFF | App release of the new screen |
| AC-10 to AC-12, AC-21, AC-37 | BFF free-user access | App release of the new screen |
| D-9, D-10, AC-23, AC-27 to AC-29, AC-39, AC-42 | App | App release of the new screen |
| AC-36 | Bet engine, Publish Engine | Phase 1A (31 Oct) |
| AC-17 to AC-20, AC-25, AC-35 | Bet engine, Publish Engine | Each sport's switch to live data |
| AC-24, AC-41 | Publish Engine, BFF | Receipts after kickoff (1B) |
| AC-40 | Edge monitor, live scores service | Launch gate X14: blocks D1 option A (not A′), D7 and live game state |
| E1 to E11 | Edge monitor, and any other edge-state producer (the BFF under option A′) | Showing edge state for that sport |
| AC-13, AC-15, AC-16, AC-26, AC-31 to AC-34 | Edge monitor (overlay owner) | Overlays reaching users |
| AC-14, AC-38 | App overlay merge | Overlays reaching users |

## 11. Phasing and the Market Movement escalation

The contract unblocks the app today, but it does not by itself deliver the redesign: the Market Movement box, the design's headline feature, has a committed source only for NFL before kickoff. D1 must decide whether it ships with launch.

### 11.1 What each phase delivers

| Phase | Delivers | The card shows |
| --- | --- | --- |
| Now | This contract and the mock scenarios (10.6) | The full design, built against mock data |
| 1A (31 Oct) | Publish time, entry odds and edge, stake, cancelled status, current odds hourly at the entry line with their observation time | Core card complete; Market Movement shows current odds and their observation time only while the line is unchanged; edge state only for NFL, once X1–X3 are fixed and the monitor runs in tst (X14) |
| 1B (1 Dec) | One schema for all sports, structured selection, a book per price, reason codes (if not sent in 1A), latest observation in Cosmos | Cancel reasons, correct book names, receipts after kickoff |
| Phase 2 (Dec–Jan) | Odds every few minutes | Fresher Market Movement; no contract change |

### 11.2 The decision (D1)

| Option | What it takes | Result at launch |
| --- | --- | --- |
| A′. Ship Market Movement on 1A data | Nothing beyond 1A: current price, observation time and book at the entry line. For sports with no monitor, the BFF derives the same-line current edge (6.1) and edge state by the rules of 5.3 except rule 3, which needs the current line; both subject to the staleness rule. Becomes A with no contract change | Price and its age on every sport, edge state at hourly freshness; nothing live until X14 |
| A. Ship Market Movement | `current_line`, `observed_at` and the book in 1A; edge state for all sports by 1B (extend the monitor, or compute it in the engine's runs to section 5.3) | Line, price and edge state shown; Rec. Action hidden until D4 |
| B. Ship it per sport | Nothing new; show the box only where a source exists | NFL cards differ from the rest |
| C. Defer the box | Nothing new | The redesign launches without its headline feature |

Recommendation: A′ now, staged into A once X14 has a delivery date. A′ needs nothing beyond 1A and shows every sport's price with its age, going stale honestly when data stops. A adds the line after a move, live updates and monitor edge state with no contract change. Options A and B both depend on X14: the live services must be provisioned and deployed in tst, which serves production, and until X14 has a committed delivery date A cannot be a launch commitment.

### 11.3 Iterating in dev

Tst serves real users, so parallel work happens in dev, which is also used for testing. Any parallel setup (separate bet engine output tables, a second Publish Engine instance, a second BFF instance) MUST meet these isolation rules:

1. Content goes to a separate Cosmos database, so a misconfigured target fails instead of overwriting dev data.
2. It sends no events to the dev notification queue, and a second BFF instance does not consume that queue.
3. Caches are not shared with the dev BFF, or use a separate key prefix.
4. My Picks data written against new pick ids goes to separate containers; user accounts and subscriptions stay shared.
5. Any live edge monitor feeding it reads and writes dev data only (X4).
6. It has an end date: once 1B passes the acceptance criteria, dev switches to the new shape and the parallel setup is removed.

## 12. Open decisions

Thirteen decisions shape the build; D5 is the most urgent because the status change ships on 31 Oct. Until a decision is made, mocks and implementations follow the recommendation.

| # | Decision | Recommendation | Owner | Needed by |
| --- | --- | --- | --- | --- |
| D1 | Does Market Movement ship at launch? (11.2) Options A and B are blocked by X14; A′ is not | A′ now; staged into A once X14 has a delivery date | Product, bet engine | Oct 23, 2026 |
| D2 | Line move rule: `closed` on any move, or only on a move against the pick? | Decide from worked examples in both directions; the design's +2% Play after a move needs the engine's edge at the new line | Product, monitor owner | Oct 23, 2026 |
| D3 | Exact edge formula and the threshold *t* | Confirm p × d − 1 and publish *t* with every pick | Bet engine | Oct 23, 2026 |
| D4 | Play / Watch / Pass thresholds, or drop Rec. Action from launch | Product sets thresholds on current edge; null until then | Product | Nov 2, 2026 |
| D5 | One status vocabulary (8.4) | Keep the roadmap list; update the Publish Engine list and monitor filter in the same release (X1) | Bet engine, data engineering, monitor owner | Oct 21, 2026 |
| D6 | How overlays enforce free-user access (7.4) | Opaque per-pick keys issued in the snapshot only for unlocked picks. These need a key derivation shared by the BFF and the monitor (for example an HMAC of the pick id with a shared secret); entitlement claims in the read rules need no such coupling | Monitor owner, app team | Nov 2, 2026 |
| D7 | Who supplies edge state for NBA, MLB, WNBA and EPL | Extend the monitor; otherwise the engine computes it to 5.3 and passes 10.3 | Monitor owner, bet engine | Nov 2, 2026 |
| D8 | NBA data path | Split documents; pin the live catalog and add conformance checks (X7) | Bet engine, data engineering | Oct 23, 2026 |
| D9 | Stake units | 1 unit = the user's standard bet | Product | Oct 23, 2026 |
| D10 | Show the cancel reason on the card | Yes, as in the design; send `status_reason` from 1A | Product | Oct 23, 2026 |
| D11 | Card treatment matrix (5.4), edge state copy and colours, and whether locked cards show the book name (6.2) | Adopt 5.4: only cancelled is greyed out; locked cards show the book name | Product, design | Oct 30, 2026 |
| D12 | Free users when a sport is switched off | Show cards fully locked, per the freemium rules | Product | Oct 30, 2026 |
| D13 | Cutoff that moves a pick to `awaiting_result` | At game start, matching when the monitor stops | Product, bet engine | Oct 23, 2026 |

**Sources:** [Edge Picks redesign](https://xosports.atlassian.net/wiki/spaces/PB/pages/726237185/Edge+Picks+redesign) (Confluence, updated 9 Oct) · [Bet Engine Roadmap](https://claude.ai/artifact/FX29b7SibKX5gx1SiyLpvH) (13 Oct) · live edge monitor design and repository (live-odds, `dev` branch, 3 Oct) · live scores mobile integration guide (live-scores, `main`) · Publish Engine container references and NBA split-document code (app-data, as of 16 Oct).
