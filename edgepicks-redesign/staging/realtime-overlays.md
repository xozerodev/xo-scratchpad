# Contract: Edge Picks realtime overlays (live services to app)

Two Firebase Realtime Database feeds update an Edge Pick between snapshot responses: the edge overlay carries one pick's live price, line and edge state, and the live game card carries one game's state while it is in progress. Servers write them; the app only reads.

## About this contract

|  |  |
| --- | --- |
| Version | 4.0.0 |
| Status | Draft. Values marked Provisional can still change; each is listed under "Not yet decided" |
| Producers | Live edge monitor (edge overlay); live scores service (live game card) |
| Consumers | Mobile app (reads both); BFF (computes the overlay key with the same function as the monitor) |
| Contract owner | App team; the monitor and live scores teams sign as producers |
| Transport | Firebase Realtime Database, one project per environment |

### What the app already holds

The app learns about picks from the Edge Picks snapshot response. These are the snapshot values the feeds on this page update, so this page can be read alone:

| Snapshot value | Meaning |
| --- | --- |
| id | The pick's opaque id |
| overlay\_key | Key of the pick's edge overlay; null means do not subscribe |
| current.odds | Last observed price, as {decimal, american} |
| current.line | Last observed line |
| current.edge | Edge at the entry probability and the current price; null after a line move |
| current.observed\_at | When that price was observed |
| edge\_state | live, narrowing, closed, suspended or unknown |
| game.id, game.state | The game's id, and upcoming, live, delayed, interrupted, final, postponed or cancelled |
| status | open, awaiting\_result, cancelled, settled or void. Feeds matter only while open |
| access.hidden | Field groups (selection, odds, probability, projection, stake, edge) hidden from this user |

### Conventions on this page

- Times are ISO 8601 UTC. Producers write Z with milliseconds (2026-10-22T18:58:40.000Z); the app accepts any valid RFC 3339 offset and precision.
- Decimal odds are numbers greater than 1 with at most 4 decimal places. Edges are fractions (0.0725 means 7.25%).
- Lines follow the line rule: a spread from the backed side's view, negative when it gives points; a total or player threshold as a positive number; null for markets with no line.
- The app ignores fields it does not know and treats an unknown enum value as the listed fallback, never as an error.

## Edge overlay

Each open pick a monitor covers has two nodes under the same key: a small summary every visible card subscribes to, and a detail node read when a card is expanded.

|  |  |
| --- | --- |
| Summary path | /edgePickStatus/{overlay\_key} |
| Detail path | /edgePicks/{overlay\_key} |
| Written | From the monitor's first observation while the pick is open and its game has not started, at every observation after that |
| Deleted | Both nodes, when the game starts or the pick stops being open. The next snapshot carries the closing values |
| Writer | Live edge monitor, server only. Today it covers NFL; any producer that covers a sport follows this page |

### Key derivation

overlay\_key = the sport, an underscore, then the pick id's UTF-8 bytes in base64url with the = padding removed (Provisional). The result contains only A–Z, a–z, 0–9, - and \_, so it is always a legal database key. The BFF and the monitor call one shared function; neither builds keys any other way.

```python
import base64

def overlay_key(sport: str, pick_id: str) -> str:
    return sport + "_" + base64.urlsafe_b64encode(pick_id.encode("utf-8")).decode("ascii").rstrip("=")

# overlay_key("nba", "40021717862|spread_t1|t1|-4.5|main|full|us")
#   == "nba_NDAwMjE3MTc4NjJ8c3ByZWFkX3QxfHQxfC00LjV8bWFpbnxmdWxsfHVz"
```

### Fields

| Field | Node | Type | Null when | Meaning | Updates in the app |
| --- | --- | --- | --- | --- | --- |
| edge\_status | both | live, narrowing, closed, suspended | never | Edge state at this observation, computed by the monitor (rules below). No observation means no node, never unknown | edge\_state |
| as\_of | both | date-time | never | When the price was observed at the book. Never goes backwards for a key | current.observed\_at |
| pick\_id | detail | string | never | Equal to the snapshot id, byte for byte | none; a check only |
| live\_price | detail | decimal odds | the book has pulled the price (edge\_status is then suspended) | Latest price. The app derives American odds from it | current.odds |
| live\_point | detail | number | the market has no line, or the price is pulled | Latest line, per the line rule | current.line |
| live\_edge | detail | number, fraction | the line has moved, or the price is pulled | p × live\_price − 1, p being the pick's entry probability | current.edge |
| next\_update\_due | detail | date-time | never | When the monitor expects to write next | none; used for staleness |

The summary and the detail are written in one multi-path update, so their edge\_status and as\_of always agree.

### How the monitor computes edge\_status

Inputs from the pick record: the entry probability p, the entry decimal price, the entry line, the selection basis (expected value or probability) and the threshold t on that basis. The first matching rule wins:

1. No observation: write nothing.
2. No current price, or the book has pulled it: suspended.
3. Entry and current lines both present and different: closed.
4. Current price ≤ b: closed.
5. Entry price > b and current price ≤ m: narrowing.
6. Otherwise: live.

```latex
b_{\text{ev}} = \frac{1 + t}{p} \qquad b_{\text{prob}} = \frac{1}{p - t} \;(\text{none if } p \le t) \qquad m = \frac{d_{\text{entry}} + b}{2}
```

- b uses the basis the pick was selected on. With no b (p ≤ t on the probability basis), rules 4 and 5 are skipped.
- b and m come from unrounded inputs, then 4 decimal places: b rounded down, m half away from zero. Prices compare at 4 places; lines compare as numbers (24.5 equals 24.50).
- A pick with no probability on record gets no node: the app then shows unknown, never a guessed live.
- Edge state describes the market against the pick as entered. A line move never cancels the pick; it shows closed while the pick stays open.

Test vectors; the monitor must reproduce each in CI. Unless stated: p = 0.55, t = 0, expected-value basis, entry line 24.5, entry price 2.0000, so b = 1.8181 and m = 1.9091.

| Case | Observation | edge\_status | Why |
| --- | --- | --- | --- |
| E1 | None yet | no node | Rule 1 |
| E2 | Book has pulled the price | suspended | Rule 2 |
| E3 | Line 25.5, price 2.1000 | closed | Line moved, even at a better price |
| E4 | Line 24.5, price 2.2000 | live | Above m |
| E5 | Line 24.5, price 1.9500 | live | Above m; live\_edge 0.0725 |
| E6 | Line 24.5, price 1.9091 | narrowing | At m |
| E7 | Line 24.5, price 1.8500 | narrowing | Between b and m |
| E8 | Line 24.5, price 1.8181 | closed | At b |
| E9 | Moneyline, price 1.7000 | closed | Below b; rule 3 does not apply |
| E10 | As E7, with t = 0.02 so b = 1.8545 | closed | 1.8500 is below b |
| E11 | Line 24.5, price 1.8182 | narrowing | One step above b |
| E12 | Moneyline, price 2.0000 | live | No line, so rule 3 is skipped; above m |
| E13 | Line 24.5, price 1.9000; probability basis, t = 0.03, so b = 1.9230 | closed | Below b; on expected value b would be 1.8727 and the state narrowing |

### How the app applies it

- Subscribe to the summary for each visible pick whose overlay\_key is not null, and to the detail only while that card is expanded. Never read or list /edgePickStatus or /edgePicks themselves.
- Apply a node only when the pick's status is open, the game has not started, and as\_of is newer than the current.observed\_at the app holds. Ignore a detail node whose pick\_id differs from the snapshot id.
- Map fields as in the table above. American odds from live\_price: d ≥ 2 gives +round((d − 1) × 100), d < 2 gives round(−100 / (d − 1)), half away from zero.
- Never let an overlay change status, result, the entry values or access, and never set a field in a group listed in access.hidden (live\_price is the odds group, live\_point the selection group, edge\_status and live\_edge the edge group).
- An unknown edge\_status is shown as unknown: no indicator.
- A missing node keeps the snapshot's values. A node deleted at kickoff leaves the last applied values on screen until the next snapshot, which always wins.
- Stale: as\_of more than 2 hours old, or next\_update\_due passed more than 15 minutes ago. A stale card keeps the price and its time and hides the edge-state indicator.

### Security

Only signed-in users read; no client writes; parents cannot be listed.

```json
{
  "rules": {
    "edgePickStatus": {"$key": {".read": "auth != null"}, ".write": false},
    "edgePicks": {"$key": {".read": "auth != null"}, ".write": false}
  }
}
```

The BFF withholds overlay\_key from a user who may not see the line, the price or the edge. Because a key can be derived from a pick id, this does not yet stop a determined free user; see "Not yet decided".

### JSON Schemas

Summary node:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://contracts.xosports.ai/edge-picks/v4/overlay-summary.schema.json",
  "title": "Edge overlay summary node 4.0.0",
  "type": "object",
  "required": ["edge_status", "as_of"],
  "properties": {
    "edge_status": {"enum": ["live", "narrowing", "closed", "suspended"]},
    "as_of": {"type": "string", "format": "date-time"}
  }
}
```

Detail node:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://contracts.xosports.ai/edge-picks/v4/overlay-detail.schema.json",
  "title": "Edge overlay detail node 4.0.0",
  "type": "object",
  "required": ["pick_id", "live_price", "live_point", "edge_status", "as_of", "next_update_due", "live_edge"],
  "properties": {
    "pick_id": {"type": "string", "minLength": 1},
    "live_price": {"type": ["number", "null"], "exclusiveMinimum": 1},
    "live_point": {"type": ["number", "null"]},
    "edge_status": {"enum": ["live", "narrowing", "closed", "suspended"]},
    "as_of": {"type": "string", "format": "date-time"},
    "next_update_due": {"type": "string", "format": "date-time"},
    "live_edge": {"type": ["number", "null"]}
  },
  "allOf": [
    {"if": {"properties": {"live_price": {"type": "null"}}},
     "then": {"properties": {"edge_status": {"const": "suspended"}, "live_edge": {"type": "null"}}}}
  ]
}
```

### Example

The open Celtics -4.5 pick (p 0.55, entry 2.0000) after its price eased to 1.9500 on the same line:

```json
{
  "edgePickStatus": {
    "nba_NDAwMjE3MTc4NjJ8c3ByZWFkX3QxfHQxfC00LjV8bWFpbnxmdWxsfHVz": {
      "edge_status": "live", "as_of": "2026-10-22T18:58:40.000Z"
    }
  },
  "edgePicks": {
    "nba_NDAwMjE3MTc4NjJ8c3ByZWFkX3QxfHQxfC00LjV8bWFpbnxmdWxsfHVz": {
      "pick_id": "40021717862|spread_t1|t1|-4.5|main|full|us",
      "live_price": 1.95, "live_point": -4.5, "live_edge": 0.0725,
      "edge_status": "live", "as_of": "2026-10-22T18:58:40.000Z",
      "next_update_due": "2026-10-22T19:03:40.000Z"
    }
  }
}
```

## Live game card

The live scores service owns this node and its full shape. Edge Picks reads one field, st, to update game.state; this section fixes only that field.

|  |  |
| --- | --- |
| Path | /liveGameCards/{sport}\_{game.id}, for example /liveGameCards/nba\_40021717862 |
| Present | From the moment the game starts until a few minutes after it ends. No node before the start; a missing node is normal, not an error |
| Writer | Live scores service, server only |
| Read rule | "liveGameCards": {".read": "auth != null", ".write": false} |

| st | game.state in the app | Notes |
| --- | --- | --- |
| scheduled | upcoming | Not normally written; handled in case |
| live | live | The normal case |
| delayed | delayed | Can be the first value seen |
| suspended | interrupted | The game stopped and may resume |
| completed | final | Shown for a few minutes, then the node is deleted |
| postponed | postponed |  |
| canceled | cancelled | Note the spelling change |
| not\_necessary | cancelled | Game not needed, for example a clinched series |
| abandoned | cancelled (Provisional) | Written for NBA and WNBA only |
| anything else | keep the current game.state |  |

- Apply st only while the pick's game.state is not final, postponed or cancelled; the snapshot's terminal state wins over the feed.
- A terminal st (completed, canceled, postponed, not\_necessary, abandoned) or the node vanishing means the game is over, whichever comes first; keep showing the last state until the next snapshot.
- Scores on the same node are gated by the show\_live\_score flag. The Edge Picks screen does not read them.
- Edge state stops changing once the game starts; the live game card never changes edge\_state, status or result.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://contracts.xosports.ai/edge-picks/v4/live-game-card.schema.json",
  "title": "Live game card, the field Edge Picks reads, 4.0.0",
  "type": "object",
  "required": ["st"],
  "properties": {
    "st": {"type": "string", "minLength": 1}
  }
}
```

Other fields on the node are allowed and ignored here. st is a free string in this schema on purpose: the mapping table, not the schema, decides what an unknown value does.

## Today against this contract

Observations, not requirements: what the dev branches did when checked. Each line is a gap the producer closes before this page is agreed.

| Area | Observed (repository, branch, commit) | Gap |
| --- | --- | --- |
| Keys | live-odds dev e2c04ca: key is {league}\_{pick id}, with the monitor's own id ({bet id}\|{REGION}, region uppercase) | Matches no snapshot id, so no app can find the node. Use the shared key function |
| Coverage | live-odds dev e2c04ca: NFL only, and only picks whose status is Scheduled | Other sports have no overlay; overlay\_key is null for them |
| Times | live-odds dev e2c04ca: Python isoformat(), giving microseconds and +00:00 | Write Z with milliseconds. The app's lenient parsing covers it meanwhile |
| next\_update\_due | live-odds dev e2c04ca: written only when known | Always write it |
| live\_edge | live-odds dev e2c04ca: not written | Write it |
| Basis and threshold | live-odds dev e2c04ca: expected-value basis only, t fixed at 0 | Read basis and t from the pick record |
| Rounding | live-odds dev e2c04ca: b and m compared unrounded | Round as above; vectors E8 and E11 depend on it |
| No probability | live-odds dev e2c04ca: writes live | Write no node |
| st values | live-scores dev 11599f1: NBA values other than scheduled and final were unverified for NBA at that commit | Confirm against live games |

## Not yet decided

| Item | Provisional value on this page | What could change | Decision due |
| --- | --- | --- | --- |
| Overlay key format and read rules | sport\_ + base64url(id), readable by any signed-in user | Keys that expire or rules per user, so a free user cannot read a locked pick's overlay by deriving its key | Nov 2, 2026 |
| abandoned | Maps to cancelled | Could map to interrupted if such games can resume | With the live scores team |

## Change log

| Date | Version | Change | Signed by |
| --- | --- | --- | --- |
| Oct 19, 2026 | 4.0.0 draft | First self-contained draft | App team: pending. Edge monitor: pending. Live scores: pending |
