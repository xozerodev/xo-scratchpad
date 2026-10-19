# Contract: Edge Picks snapshot API (BFF to app)

GET /v4/edge-picks returns every Edge Pick for the signed-in user's local day in one response, with free-user locking already applied. The app draws the Edge Picks screen from this response alone; between responses, realtime updates may replace the current-market values under the rules in "Values that change after the response".

## About this contract

|  |  |
| --- | --- |
| Version | 4.0.0 |
| Status | Draft. Values marked Provisional can still change; each is listed under "Not yet decided" |
| Producer | BFF (mobile-server Azure Functions) |
| Consumer | Mobile app: the Edge Picks screen and the pick receipt |
| Contract owner | App team; the BFF team signs as producer |
| Behind the BFF | Pick records written by the bet engine and Publish Engine, game and team data, the live edge monitor. The app never reads these directly; everything it needs is on this page |

### Conventions on this page

- Every field defined here is present in every response. null means "no value", and each field says when it can be null. A field never goes missing to mean null. Arrays are never null; an empty array means none.
- Numbers are JSON numbers, never strings. Decimal odds and edges have at most 4 decimal places.
- Probabilities and edges are fractions: 0.042 means 4.2%.
- American odds are integers: 150 means +150, -110 means −110.
- Times are ISO 8601 UTC with Z and milliseconds: 2026-10-22T18:05:12.341Z. Converting to local time is the app's job.
- Ids are opaque strings. Never parse them: they can contain |, ., - and other punctuation.
- Enum values are lowercase. A value the app does not know is handled as the fallback listed with that enum, never as an error.
- The app ignores fields it does not know. The BFF sends no field this page does not define.
- Within 4.x, a new optional field or a new enum value is a minor version and is shipped only after the app handles it (or its fallback is acceptable). A rename, removal, type change or change of meaning is version 5 on a new route, with both routes served until the app has moved.

## Calling the API

One GET per day and region; no paging.

```http
GET /v4/edge-picks?date=2026-10-22&tz_offset=-4&api_version=v6
Authorization: Bearer <Firebase ID token>
If-None-Match: "<ETag from the last 200>"
```

| Parameter | Type | Required | Meaning |
| --- | --- | --- | --- |
| date | YYYY-MM-DD | Yes | The user's local calendar day |
| tz\_offset | Hours, -14 to 14; fractions allowed (5.5) | Yes | The user's UTC offset on that day. The BFF serves picks whose game starts in \[local midnight, next local midnight) of that day |
| sport | nba, nfl, mlb, wnba or epl | No | Only that sport's picks |
| api\_version | v plus an integer, such as v6 | No; default v1 | The app build's API version. A league staged for a new season is served only to v6 and later; earlier versions do not see its picks |

What the server decides, not the request:

- **Identity** from the Firebase ID token. Missing or invalid gives 401.
- **Region** (us or au) from the user's profile on the server. It decides which picks and bookmakers are served.
- **Plan** from the server's entitlement check. It decides which field groups are hidden (see "Free users and locked fields").

On success:

- 200 with the body defined on this page. Every pick validates against the schema below; a pick that would not is left out and reported to the BFF's monitoring, and the rest are served.
- Picks are sorted by game.starts\_at ascending, then entry.edge descending with nulls last, then id ascending. The app may re-sort for display.
- An ETag header covers the whole body except generated\_at. A request whose If-None-Match matches gets 304 with no body, and the app keeps its copy. When to refetch is the app's choice; an unchanged day costs a 304.
- The response is for one user. Shared caches must not store it.

| HTTP | Body | When | The app |
| --- | --- | --- | --- |
| 400 | {"error": "invalid\_query", "details": {"field": "tz\_offset"}} | A required parameter is missing or malformed, or sport is unknown | Fixes the request; never retries it unchanged |
| 401 | {"error": "Unauthorized"} | No valid token | Refreshes the token and retries once, then sends the user to sign in |
| 503 | {"error": "unavailable"} | The pick store or another dependency is down | Keeps the last response on screen, marked as not updated, and retries with backoff |

## Fields

Every field below is always present; "Null when" lists the only cases it may be null.

### Response

| Field | Type | Null when | Meaning |
| --- | --- | --- | --- |
| contract\_version | string, 4.x.y | never | Version of this contract the response follows. The app accepts any 4.x.y |
| source | live, mock | never | mock only from non-production environments |
| date | YYYY-MM-DD | never | The requested date, echoed |
| region | us, au | never | The region this response was built for |
| generated\_at | date-time | never | When the BFF built the response; not covered by the ETag |
| picks | array of Pick | never; \[\] when the day has none | The day's picks |

### Pick

| Field | Type | Null when | Meaning |
| --- | --- | --- | --- |
| id | string | never | The pick's id, also used in My Picks and support logs. A price or line move never changes it |
| overlay\_key | string | the pick has no live overlay (not open, game started, or no monitor covers the sport); or selection, odds or edge is hidden for this user | Key of the pick's realtime edge overlay. Provisional format |
| sport | enum | never | League of the game |
| kind | game, player | never | game: a team or game market. player: a player prop |
| game | Game | never | The game the pick is on |
| selection | Selection | selection hidden | What the pick backs |
| picked\_at | date-time | never | First publish. Never changes |
| model.probability | number, 0 to 1 | probability hidden | The model's probability that the selection wins, at entry. Never changes |
| model.projection | Projection | projection hidden, or the market has no projection | The model's projected stat or score |
| entry.odds | Odds | odds hidden | Price at first publish. Never changes |
| entry.line | number | the market has no line, or selection hidden | Line at first publish, per the line rule. Never changes |
| entry.edge | number | edge hidden, or the producer sent none | Edge at entry: model.probability × entry decimal − 1 (Provisional basis). Never changes |
| entry.stake\_units | number ≥ 0 | stake hidden | Recommended stake in units. Never changes |
| entry.source | OddsSource | never | Where the entry price came from. Never hidden |
| current | object | no market observation yet | The market as last observed. Once the game starts, the last observation before the start |
| current.odds | Odds | odds hidden, or the book has pulled the price | Last observed price |
| current.line | number | the market has no line, or selection hidden | Last observed line; differs from entry.line after a line move |
| current.edge | number | edge hidden, or current.line differs from entry.line | model.probability × current decimal − 1 |
| current.source | OddsSource | not known | Where the current price was observed |
| current.observed\_at | date-time | never (inside current) | When the price was observed at the book, not when the BFF read it |
| current.is\_closing | boolean | never (inside current) | true for the last observation before the game started |
| edge\_holds\_above | Odds | probability or odds hidden, or no price clears the threshold | Break-even price b: the pick keeps an edge while the price stays above it. Shown as "Edge holds above −122" |
| edge\_state | enum | never | The market against the pick as entered; see "Edge state" |
| action | play, watch, pass | always null in 4.0 (Provisional) | Recommended action. The app hides the slot while it is null |
| status | enum | never | Where the pick is in its life; see "Pick lifecycle" |
| status\_reason | object | status is not cancelled or void, or the producer gave no reason | code (enum) and message (copy written by the BFF, ready to show) |
| result | won, lost, push, void | status is not settled or void | Grade on the entry odds |
| access.locked | boolean | never | true exactly when access.hidden is not empty |
| access.hidden | array of field groups | never; \[\] for subscribers | Field groups set to null for this user |

### Objects inside a pick

| Object | Fields (all always present) | Notes |
| --- | --- | --- |
| Game | id (string of digits), starts\_at (date-time), label ("Knicks @ Celtics", away @ home), state (enum), home (Team), away (Team) | starts\_at is the cutoff: the moment a pick stops being open |
| Team | id, name ("Boston Celtics"), short\_name ("Celtics"), abbreviation ("BOS"), image\_code ("nba\_BOS") | image\_code is the key of the app's bundled team logo |
| Selection | label, market, stat, side, team, player | label is display-ready ("Celtics -4.5", "Tyrese Maxey over 26.5 points"). stat is {code, label} for player props, else null. team is the backed team for moneyline and spread, else null. player is {id, name, team\_id} for player props, else null |
| Odds | decimal (> 1, 4 places), american (integer) | Always both. american is derived from decimal by the conversion rule |
| OddsSource | kind (bookmaker, market\_average), id, name | id is the bookmaker id ("draftkings"), null for a market average. name is display-ready |
| Projection | value (number), unit ("points"), label ("28.3 pts") | label is display-ready |

### Values and fallbacks

| Enum | Values | If the app meets another value |
| --- | --- | --- |
| sport | nba, nfl, mlb, wnba, epl | Hides the pick |
| kind | game, player | Uses the game-pick layout |
| selection.market | moneyline, spread, total, draw, btts (both teams to score), player\_prop | Shows selection.label only |
| selection.side | home, away, over, under, yes, no, draw | Shows selection.label only |
| game.state | upcoming; live; delayed (start pushed back, not begun); interrupted (stopped after starting, for example rain); final; postponed; cancelled | Shows starts\_at only |
| status | open, awaiting\_result, cancelled, settled, void | Hides the pick |
| status\_reason.code | probability\_moved (the model no longer backs it), market\_moved (the price moved past the edge), lineup\_change, withdrawn, game\_void (the game or market was voided). Provisional list | Shows message, which is always present with a code |
| result | won, lost, push, void | Shows a neutral "Result" chip |
| edge\_state | live, narrowing, closed, suspended, unknown | Treats it as unknown: no indicator |
| action | play, watch, pass | Hides the slot |
| access.hidden items | selection, odds, probability, projection, stake, edge | Treats the unknown group as hidden |

## Rules for the values

### Pick lifecycle

| status | Meaning | result | status\_reason | The app shows |
| --- | --- | --- | --- | --- |
| open | Published; the game has not started | null | null | The live card: current market, edge state, live updates |
| awaiting\_result | The game has started; not graded yet | null | null | The closing market; no further edge-state changes |
| cancelled | The engine stopped backing the pick before the game started | null | usually set | The pick marked cancelled, with the message; it does not count in results |
| settled | Graded on the entry odds | won, lost or push | null | The result and payout |
| void | The game was postponed or cancelled, or the market was voided | void | set when known | Void; the stake is returned |

- Status only moves forward: open to awaiting\_result, cancelled or void; awaiting\_result to settled or void.
- A pick, once served for a date, is served in every later response for that date until it is settled or void. The one exception is a pick withdrawn because it was published in error: it stops appearing, and the app drops a pick that a newer response no longer contains.
- A line move never cancels a pick. The pick stays open and its edge\_state becomes closed.

### Line rule

- Spread: from the backed side's view; negative when the side gives points (Celtics -4.5), positive when it receives them.
- Total and player prop: the threshold, positive (over 26.5 gives 26.5).
- Moneyline, draw, btts and yes/no props: null.
- Lines compare as numbers: 24.5 equals 24.50.

### Free users and locked fields

The BFF hides whole field groups for a user who may not see them; the hidden fields are null and the groups are listed in access.hidden. A group is hidden unless its flag is explicitly true for the user's plan and region.

| Group | Fields set to null | Flag that shows it |
| --- | --- | --- |
| selection | selection, entry.line, current.line | show\_pick\_description |
| odds | entry.odds, current.odds, edge\_holds\_above | show\_market\_odds |
| probability | model.probability, edge\_holds\_above | show\_xo\_probability |
| projection | model.projection | show\_projection |
| stake | entry.stake\_units | show\_stake |
| edge | entry.edge, current.edge, action; edge\_state is set to unknown | show\_xo\_edge |

- Probability, odds and edge give each other away: any two give the third. So either none of the three is hidden or at least two are. When the flags would hide exactly one, the BFF also hides the next in the order edge, probability, odds and lists both.
- overlay\_key is null when selection, odds or edge is hidden, because the overlay carries the line, the price and the edge state.
- entry.source and current.source are in no group and are never hidden.
- The app shows a lock in place of each hidden field, never derives a hidden value from the visible ones, and ignores any live update to a field in a hidden group.

### Edge state

| edge\_state | Meaning | Card indicator |
| --- | --- | --- |
| live | The price is still well above break-even | Edge live |
| narrowing | The price has fallen to between break-even and the midpoint | Edge narrowing |
| closed | The price is at or below break-even, or the line has moved: the pick as entered is gone | Edge closed |
| suspended | The book has pulled the price | Suspended |
| unknown | No observation yet, or edge hidden | None |

The BFF computes it from the pick's probability p, the producer's threshold t and selection basis, the entry price and the current observation, using b and m below. The first matching rule wins:

1. No observation: unknown.
2. No current price, or the book has pulled it: suspended.
3. Both lines present and different: closed.
4. Current price ≤ b: closed.
5. Entry price > b and current price ≤ m: narrowing.
6. Otherwise: live.

When there is no break-even (p ≤ t on the probability basis), rules 4 and 5 are skipped. The state is computed only while the pick is open and the game has not started; after that it stays at the value from the last observation before the start. Edge state describes the market, never the model: when the engine stops backing a pick, the status becomes cancelled instead.

### Formulas

p is the model probability at entry, d a decimal price, t the producer's threshold on its basis.

```latex
\text{edge} = p \times d - 1 \qquad b_{\text{ev}} = \frac{1 + t}{p} \qquad b_{\text{prob}} = \frac{1}{p - t} \;(\text{null if } p \le t) \qquad m = \frac{d_{\text{entry}} + b}{2}
```

- edge is on the expected-value display basis (Provisional) for every sport. A producer that selects on the probability basis (p − 1/d, sometimes in percentage points) is converted by the BFF from p and the price; the app never converts.
- b uses the basis the producer selected the pick on: b\_ev for expected value, b\_prob for probability. edge\_holds\_above is b.
- Precision: b and m come from unrounded inputs, then 4 decimal places, b rounded down and m half away from zero. Prices compare at 4 places.
- current.edge uses the entry probability and the current price, and only when the line has not moved. After a line move it is null.
- Decimal to American: d ≥ 2 gives +round((d − 1) × 100); d < 2 gives round(−100 / (d − 1)). American to decimal: a > 0 gives 1 + a/100; a < 0 gives 1 + 100/(−a). Rounding is half away from zero; decimals to 4 places.
- The app computes money. Bet size = entry.stake\_units × the user's standard bet. Payout: won, bet size × entry decimal; push or void, the bet size back; lost, nothing. Round to cents only for display.

### Staleness

The app marks current as stale when observed\_at is more than 2 hours old, or when the overlay's next\_update\_due passed more than 15 minutes ago. A stale card keeps its price and time ("as of 3:05 pm") and hides the edge-state indicator. Staleness applies only to open picks before the game starts.

### Values that change after the response

Until the next response, two realtime feeds may update an open pick:

- The edge overlay at overlay\_key updates current.odds, current.line, current.edge, current.observed\_at and edge\_state, already computed by the producer with the rules above.
- The live game card updates game.state.

The app applies an update only when its observation time is newer than current.observed\_at, keeps the response's value when a feed has nothing, and never lets a feed change status, result, status\_reason, entry, model or access. The next response always wins over anything a feed delivered before it.

### Test vectors

The BFF must reproduce every case exactly in CI; the app reproduces the payout cases.

Edge state. Unless stated: p = 0.55, t = 0, expected-value basis, entry line 24.5, entry price 2.0000, so b = 1.8181 (−122) and m = 1.9091 (−110).

| Case | Observation | edge\_state | Why |
| --- | --- | --- | --- |
| E1 | None yet | unknown | Rule 1 |
| E2 | Book has pulled the price | suspended | Rule 2 |
| E3 | Line 25.5, price 2.1000 | closed | Line moved, even at a better price |
| E4 | Line 24.5, price 2.2000 | live | Above m |
| E5 | Line 24.5, price 1.9500 | live | Above m |
| E6 | Line 24.5, price 1.9091 | narrowing | At m |
| E7 | Line 24.5, price 1.8500 | narrowing | Between b and m |
| E8 | Line 24.5, price 1.8181 | closed | At b |
| E9 | Moneyline, price 1.7000 | closed | Below b; rule 3 does not apply |
| E10 | As E7, with t = 0.02 so b = 1.8545 | closed | 1.8500 is below b |
| E11 | Line 24.5, price 1.8182 | narrowing | One step above b |
| E12 | Moneyline, price 2.0000 | live | No line, so rule 3 is skipped; above m |
| E13 | Line 24.5, price 1.9000; probability basis, t = 0.03, so b = 1.9230 | closed | Below b; on expected value b would be 1.8727 and the state narrowing |

Derived values.

| Case | Input | Expected |
| --- | --- | --- |
| D-1 | American −110 | decimal 1.9091 |
| D-2 | American −115 | decimal 1.8696 |
| D-3 | American +150 | decimal 2.5000 |
| D-4 | Decimal 1.9091 | American −110 |
| D-5 | p 0.58, entry price 1.9091 | entry.edge 0.1073 |
| D-6 | p 0.55, t 0, expected-value basis | edge\_holds\_above 1.8181 / −122 |
| D-7 | p 0.55, same line, current price 1.9500 | current.edge 0.0725 |
| D-8 | p 0.55, line moved | current.edge null |
| D-9 | 2 units, standard bet $10, entry −115, won | bet size $20.00, payout $37.39 |
| D-10 | 1 unit, standard bet $10, entry −110, won | bet size $10.00, payout $19.09 |
| D-11 | Producer on probability basis sends edge 5.0 (percentage points), p 0.55, entry 2.0000 | entry.edge 0.1000 |

## JSON Schema

JSON Schema draft 2020-12, complete: it references nothing outside itself. Both the BFF's tests and the app's tests validate against it. Two rules are checked by tests rather than the schema: decimals have at most 4 places (multipleOf on floats gives different answers in different validators), and the field-group rules under "Free users and locked fields".

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://contracts.xosports.ai/edge-picks/v4/snapshot.schema.json",
  "title": "Edge Picks snapshot response 4.0.0",
  "type": "object",
  "required": ["contract_version", "source", "date", "region", "generated_at", "picks"],
  "properties": {
    "contract_version": {"type": "string", "pattern": "^4\\.\\d+\\.\\d+$"},
    "source": {"enum": ["live", "mock"]},
    "date": {"type": "string", "format": "date"},
    "region": {"enum": ["us", "au"]},
    "generated_at": {"type": "string", "format": "date-time"},
    "picks": {"type": "array", "items": {"$ref": "#/$defs/Pick"}}
  },
  "$defs": {
    "Pick": {
      "type": "object",
      "required": ["id", "overlay_key", "sport", "kind", "game", "selection", "picked_at", "model", "entry",
                   "current", "edge_holds_above", "edge_state", "action", "status", "status_reason", "result", "access"],
      "properties": {
        "id": {"type": "string", "minLength": 1},
        "overlay_key": {"type": ["string", "null"], "pattern": "^[^.$#\\[\\]/\\x00-\\x1f\\x7f]+$"},
        "sport": {"enum": ["nba", "nfl", "mlb", "wnba", "epl"]},
        "kind": {"enum": ["game", "player"]},
        "game": {"$ref": "#/$defs/Game"},
        "selection": {"oneOf": [{"$ref": "#/$defs/Selection"}, {"type": "null"}]},
        "picked_at": {"type": "string", "format": "date-time"},
        "model": {
          "type": "object",
          "required": ["probability", "projection"],
          "properties": {
            "probability": {"type": ["number", "null"], "minimum": 0, "maximum": 1},
            "projection": {"oneOf": [{"$ref": "#/$defs/Projection"}, {"type": "null"}]}
          }
        },
        "entry": {
          "type": "object",
          "required": ["odds", "line", "edge", "stake_units", "source"],
          "properties": {
            "odds": {"oneOf": [{"$ref": "#/$defs/Odds"}, {"type": "null"}]},
            "line": {"type": ["number", "null"]},
            "edge": {"type": ["number", "null"]},
            "stake_units": {"type": ["number", "null"], "minimum": 0},
            "source": {"$ref": "#/$defs/OddsSource"}
          }
        },
        "current": {
          "oneOf": [
            {"type": "null"},
            {
              "type": "object",
              "required": ["odds", "line", "edge", "source", "observed_at", "is_closing"],
              "properties": {
                "odds": {"oneOf": [{"$ref": "#/$defs/Odds"}, {"type": "null"}]},
                "line": {"type": ["number", "null"]},
                "edge": {"type": ["number", "null"]},
                "source": {"oneOf": [{"$ref": "#/$defs/OddsSource"}, {"type": "null"}]},
                "observed_at": {"type": "string", "format": "date-time"},
                "is_closing": {"type": "boolean"}
              }
            }
          ]
        },
        "edge_holds_above": {"oneOf": [{"$ref": "#/$defs/Odds"}, {"type": "null"}]},
        "edge_state": {"enum": ["live", "narrowing", "closed", "suspended", "unknown"]},
        "action": {"enum": ["play", "watch", "pass", null]},
        "status": {"enum": ["open", "awaiting_result", "cancelled", "settled", "void"]},
        "status_reason": {
          "oneOf": [
            {"type": "null"},
            {
              "type": "object",
              "required": ["code", "message"],
              "properties": {
                "code": {"enum": ["probability_moved", "market_moved", "lineup_change", "withdrawn", "game_void"]},
                "message": {"type": "string", "minLength": 1}
              }
            }
          ]
        },
        "result": {"enum": ["won", "lost", "push", "void", null]},
        "access": {
          "type": "object",
          "required": ["locked", "hidden"],
          "properties": {
            "locked": {"type": "boolean"},
            "hidden": {
              "type": "array",
              "uniqueItems": true,
              "items": {"enum": ["selection", "odds", "probability", "projection", "stake", "edge"]}
            }
          }
        }
      },
      "allOf": [
        {"if": {"properties": {"status": {"const": "settled"}}},
         "then": {"properties": {"result": {"enum": ["won", "lost", "push"]}}}},
        {"if": {"properties": {"status": {"const": "void"}}},
         "then": {"properties": {"result": {"const": "void"}}}},
        {"if": {"properties": {"status": {"enum": ["open", "awaiting_result", "cancelled"]}}},
         "then": {"properties": {"result": {"const": null}}}},
        {"if": {"properties": {"status": {"enum": ["open", "awaiting_result", "settled"]}}},
         "then": {"properties": {"status_reason": {"const": null}}}},
        {"if": {"properties": {"access": {"properties": {"hidden": {"minItems": 1}}}}},
         "then": {"properties": {"access": {"properties": {"locked": {"const": true}}}}},
         "else": {"properties": {"access": {"properties": {"locked": {"const": false}}}}}}
      ]
    },
    "Game": {
      "type": "object",
      "required": ["id", "starts_at", "label", "state", "home", "away"],
      "properties": {
        "id": {"type": "string", "pattern": "^[0-9]+$"},
        "starts_at": {"type": "string", "format": "date-time"},
        "label": {"type": "string"},
        "state": {"enum": ["upcoming", "live", "delayed", "interrupted", "final", "postponed", "cancelled"]},
        "home": {"$ref": "#/$defs/Team"},
        "away": {"$ref": "#/$defs/Team"}
      }
    },
    "Team": {
      "type": "object",
      "required": ["id", "name", "short_name", "abbreviation", "image_code"],
      "properties": {
        "id": {"type": "string"}, "name": {"type": "string"}, "short_name": {"type": "string"},
        "abbreviation": {"type": "string"}, "image_code": {"type": "string"}
      }
    },
    "Selection": {
      "type": "object",
      "required": ["label", "market", "stat", "side", "team", "player"],
      "properties": {
        "label": {"type": "string"},
        "market": {"enum": ["moneyline", "spread", "total", "draw", "btts", "player_prop"]},
        "stat": {
          "oneOf": [
            {"type": "null"},
            {"type": "object", "required": ["code", "label"],
             "properties": {"code": {"type": "string"}, "label": {"type": "string"}}}
          ]
        },
        "side": {"enum": ["home", "away", "over", "under", "yes", "no", "draw"]},
        "team": {"oneOf": [{"$ref": "#/$defs/Team"}, {"type": "null"}]},
        "player": {
          "oneOf": [
            {"type": "null"},
            {"type": "object", "required": ["id", "name", "team_id"],
             "properties": {"id": {"type": "string"}, "name": {"type": "string"}, "team_id": {"type": "string"}}}
          ]
        }
      }
    },
    "Projection": {
      "type": "object",
      "required": ["value", "unit", "label"],
      "properties": {"value": {"type": "number"}, "unit": {"type": "string"}, "label": {"type": "string"}}
    },
    "Odds": {
      "type": "object",
      "required": ["decimal", "american"],
      "properties": {"decimal": {"type": "number", "exclusiveMinimum": 1}, "american": {"type": "integer"}}
    },
    "OddsSource": {
      "type": "object",
      "required": ["kind", "id", "name"],
      "properties": {
        "kind": {"enum": ["bookmaker", "market_average"]},
        "id": {"type": ["string", "null"]},
        "name": {"type": "string"}
      }
    }
  }
}
```

## Examples

Both examples validate against the schema above. The values are illustrative; overlay\_key uses the provisional key format.

### A subscriber's day

Three picks for a US subscriber with tz\_offset -4: a settled player prop that won (its closing line had moved to 27.5, so current.edge is null and edge\_state closed), a moneyline the engine cancelled before the game, and an open spread whose price has eased from 2.0000 to 1.9500 but is still above the midpoint 1.9091, so edge\_state is live.

```json
{
  "contract_version": "4.0.0", "source": "live", "date": "2026-10-22", "region": "us",
  "generated_at": "2026-10-22T19:00:03.120Z",
  "picks": [
    {
      "id": "40021717850|50001234|pts|over|26.5|main|full|us",
      "overlay_key": null,
      "sport": "nba",
      "kind": "player",
      "game": {"id": "40021717850", "starts_at": "2026-10-22T16:00:00.000Z", "label": "Heat @ 76ers", "state": "final",
        "home": {"id": "40000022", "name": "Philadelphia 76ers", "short_name": "76ers", "abbreviation": "PHI", "image_code": "nba_PHI"},
        "away": {"id": "40000014", "name": "Miami Heat", "short_name": "Heat", "abbreviation": "MIA", "image_code": "nba_MIA"}},
      "selection": {"label": "Tyrese Maxey over 26.5 points", "market": "player_prop", "stat": {"code": "pts", "label": "Points"},
        "side": "over", "team": null, "player": {"id": "50001234", "name": "Tyrese Maxey", "team_id": "40000022"}},
      "picked_at": "2026-10-22T13:10:44.002Z",
      "model": {"probability": 0.6, "projection": {"value": 28.3, "unit": "points", "label": "28.3 pts"}},
      "entry": {"odds": {"decimal": 1.8696, "american": -115}, "line": 26.5, "edge": 0.1218, "stake_units": 2,
        "source": {"kind": "bookmaker", "id": "draftkings", "name": "DraftKings"}},
      "current": {"odds": {"decimal": 1.9091, "american": -110}, "line": 27.5, "edge": null,
        "source": {"kind": "bookmaker", "id": "draftkings", "name": "DraftKings"},
        "observed_at": "2026-10-22T15:59:30.000Z", "is_closing": true},
      "edge_holds_above": {"decimal": 1.6666, "american": -150},
      "edge_state": "closed", "action": null,
      "status": "settled", "status_reason": null, "result": "won",
      "access": {"locked": false, "hidden": []}
    },
    {
      "id": "40021717861|moneyline_t2|t2|null|main|full|us",
      "overlay_key": null,
      "sport": "nba",
      "kind": "game",
      "game": {"id": "40021717861", "starts_at": "2026-10-22T23:00:00.000Z", "label": "Lakers @ Nuggets", "state": "upcoming",
        "home": {"id": "40000007", "name": "Denver Nuggets", "short_name": "Nuggets", "abbreviation": "DEN", "image_code": "nba_DEN"},
        "away": {"id": "40000013", "name": "Los Angeles Lakers", "short_name": "Lakers", "abbreviation": "LAL", "image_code": "nba_LAL"}},
      "selection": {"label": "Lakers moneyline", "market": "moneyline", "stat": null, "side": "away",
        "team": {"id": "40000013", "name": "Los Angeles Lakers", "short_name": "Lakers", "abbreviation": "LAL", "image_code": "nba_LAL"},
        "player": null},
      "picked_at": "2026-10-22T14:02:10.500Z",
      "model": {"probability": 0.48, "projection": null},
      "entry": {"odds": {"decimal": 2.25, "american": 125}, "line": null, "edge": 0.08, "stake_units": 1,
        "source": {"kind": "bookmaker", "id": "draftkings", "name": "DraftKings"}},
      "current": {"odds": {"decimal": 2.05, "american": 105}, "line": null, "edge": -0.016,
        "source": {"kind": "bookmaker", "id": "draftkings", "name": "DraftKings"},
        "observed_at": "2026-10-22T18:41:00.000Z", "is_closing": false},
      "edge_holds_above": {"decimal": 2.0833, "american": 108},
      "edge_state": "closed", "action": null,
      "status": "cancelled",
      "status_reason": {"code": "probability_moved", "message": "Our model no longer backs this pick, so we cancelled it before the game."},
      "result": null,
      "access": {"locked": false, "hidden": []}
    },
    {
      "id": "40021717862|spread_t1|t1|-4.5|main|full|us",
      "overlay_key": "nba_NDAwMjE3MTc4NjJ8c3ByZWFkX3QxfHQxfC00LjV8bWFpbnxmdWxsfHVz",
      "sport": "nba",
      "kind": "game",
      "game": {"id": "40021717862", "starts_at": "2026-10-22T23:30:00.000Z", "label": "Knicks @ Celtics", "state": "upcoming",
        "home": {"id": "40000002", "name": "Boston Celtics", "short_name": "Celtics", "abbreviation": "BOS", "image_code": "nba_BOS"},
        "away": {"id": "40000020", "name": "New York Knicks", "short_name": "Knicks", "abbreviation": "NYK", "image_code": "nba_NYK"}},
      "selection": {"label": "Celtics -4.5", "market": "spread", "stat": null, "side": "home",
        "team": {"id": "40000002", "name": "Boston Celtics", "short_name": "Celtics", "abbreviation": "BOS", "image_code": "nba_BOS"},
        "player": null},
      "picked_at": "2026-10-22T18:05:12.341Z",
      "model": {"probability": 0.55, "projection": null},
      "entry": {"odds": {"decimal": 2.0, "american": 100}, "line": -4.5, "edge": 0.1, "stake_units": 2,
        "source": {"kind": "bookmaker", "id": "draftkings", "name": "DraftKings"}},
      "current": {"odds": {"decimal": 1.95, "american": -105}, "line": -4.5, "edge": 0.0725,
        "source": {"kind": "bookmaker", "id": "draftkings", "name": "DraftKings"},
        "observed_at": "2026-10-22T18:58:40.000Z", "is_closing": false},
      "edge_holds_above": {"decimal": 1.8181, "american": -122},
      "edge_state": "live", "action": null,
      "status": "open", "status_reason": null, "result": null,
      "access": {"locked": false, "hidden": []}
    }
  ]
}
```

### The open spread as a free user sees it

With show\_pick\_description and show\_xo\_edge false, the BFF hides selection and edge, and hides probability too, because the probability and the odds together would give away the edge. The odds stay visible, so the app can show the price with locks over the pick, the probability and the edge. overlay\_key is null because the overlay would reveal the line and the edge state.

```json
{
  "id": "40021717862|spread_t1|t1|-4.5|main|full|us",
  "overlay_key": null,
  "sport": "nba",
  "kind": "game",
  "game": {"id": "40021717862", "starts_at": "2026-10-22T23:30:00.000Z", "label": "Knicks @ Celtics", "state": "upcoming",
    "home": {"id": "40000002", "name": "Boston Celtics", "short_name": "Celtics", "abbreviation": "BOS", "image_code": "nba_BOS"},
    "away": {"id": "40000020", "name": "New York Knicks", "short_name": "Knicks", "abbreviation": "NYK", "image_code": "nba_NYK"}},
  "selection": null,
  "picked_at": "2026-10-22T18:05:12.341Z",
  "model": {"probability": null, "projection": null},
  "entry": {"odds": {"decimal": 2.0, "american": 100}, "line": null, "edge": null, "stake_units": 2,
    "source": {"kind": "bookmaker", "id": "draftkings", "name": "DraftKings"}},
  "current": {"odds": {"decimal": 1.95, "american": -105}, "line": null, "edge": null,
    "source": {"kind": "bookmaker", "id": "draftkings", "name": "DraftKings"},
    "observed_at": "2026-10-22T18:58:40.000Z", "is_closing": false},
  "edge_holds_above": null,
  "edge_state": "unknown", "action": null,
  "status": "open", "status_reason": null, "result": null,
  "access": {"locked": true, "hidden": ["selection", "probability", "edge"]}
}
```

## Not yet decided

Everything else on this page is the target. Build against the provisional values; a change to any of them is announced in the change log with its version.

| Item | Provisional value on this page | What could change | Decision due |
| --- | --- | --- | --- |
| Display basis for edges | Expected value: p × d − 1, for every sport | Values of entry.edge and current.edge; vectors D-5, D-7 and D-11 | Oct 23, 2026 |
| Reason codes | probability\_moved, market\_moved, lineup\_change, withdrawn, game\_void | withdrawn may be removed (a withdrawn pick is never served), and book\_pulled and competitor\_withdrawn added | Oct 21, 2026 |
| When the engine cancels a pick | The engine cancels when it stops backing a pick before the game; a line move alone never cancels | How often cancelled appears, and with which reasons | Oct 30, 2026 |
| Overlay key format | "{sport}\_" + base64url(id) with padding removed | The value of overlay\_key; possibly keys that expire, with per-user read rules | Nov 2, 2026 |
| action | Always null | When play, watch and pass start to appear | Not scheduled |

## Change log

| Date | Version | Change | Signed by |
| --- | --- | --- | --- |
| Oct 19, 2026 | 4.0.0 draft | First self-contained draft | App team: pending. BFF: pending |
