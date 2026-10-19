# Contract: Edge Picks producer pick record (bet engine and Publish Engine to BFF)

Every Edge Pick is stored as one typed record per pick per region, with the same field names, units and meanings for every sport and for game and player picks. The BFF builds what the app sees from these records and nothing else, so a value the record does not carry cannot reach the app.

## About this contract

|  |  |
| --- | --- |
| Version | 4.0.0 |
| Status | Draft target. "Today against this contract" shows how far each producer is from it |
| Producers | Bet engines compute the values; the Publish Engine is the only writer of pick documents |
| Consumers | BFF (builds the app's Edge Picks response); live edge monitor (reads ids, entry values, probability, basis and threshold); settlement |
| Contract owner | App team; the bet engine and data engineering teams sign as producers, the BFF and monitor teams as consumers |
| Store | Pick documents in Cosmos. The layout is proposed in KDD-001 (kdds.md): one record per document in a new container, partitioned by game\_sk, with the document id equal to pick\_id. This page fixes the record shape and the id rule, not the container |

### Conventions on this page

- Every field is present in every record. null means "no value", and each field says when it can be null. A field never goes missing to mean null.
- snake\_case names. A field means the same thing in every sport.
- Numbers are JSON numbers, never strings. Decimal odds carry at most 4 decimal places; American odds are integers.
- Probabilities and edges are fractions: 0.05, never 5 or "5%". A producer that works in percentage points divides by 100 before writing.
- Times are ISO 8601 UTC with Z and milliseconds: 2026-10-22T18:05:12.341Z.
- Ids are opaque to every consumer. No consumer parses pick\_id. Producers build it with one formula ("Pick id").
- Enum values are lowercase. Consumers ignore fields they do not know; producers write no field this page does not define.
- Within 4.x a new optional field or enum value is a minor version, shipped only after every consumer handles it. A rename, removal, type change or change of meaning is version 5, written alongside 4 until consumers have moved.

## Rules a producer keeps

1. **Identity.** pick\_id is built by the formula under "Pick id", which makes it unique across every record, in every sport and region: records for the same selection in au and us have different ids. It never changes when the price or line moves. A pick on a new line is a new pick with its own id, and a selection recommended again after its pick was cancelled or withdrawn gets a re-issue suffix. It is at most 255 characters from A–Z, a–z, 0–9 and `_ . ~ | -`, so it is always a legal Cosmos document id and, once the BFF turns `|` into `_`, a legal push-topic name for pick follows.
2. **Persistence.** Once published, a pick appears in every later publish of its document until it is settled or void. A pick the engine no longer backs becomes cancelled, with a reason; one published in error becomes withdrawn. Rebuilding picks from scratch on each run must not drop earlier picks, and pausing or switching a producer off stops new picks without removing published ones.
3. **Frozen entry.** pick\_date\_time, probability, stake\_units and every entry\_ field keep their first-publish values for the pick's life. Later runs update only current\_ fields, observed\_at, is\_closing, edge\_status, pick\_status, status\_reason and outcome.
4. **Observation time.** A record with a current price carries observed\_at, the time the price was seen at the book, not the time the record was written.
5. **One writer.** Only the Publish Engine writes pick documents. The edge monitor's latest observation reaches them through the Publish Engine, never by a direct write. A new observation reaches the record within 5 minutes, and is\_closing is true only on the last observation before the game starts.
6. **Forward only.** pick\_status moves open to awaiting\_result, cancelled, void or withdrawn, and awaiting\_result to settled or void. Nothing moves backwards. Whether a cancelled pick may return to open before the game starts is still open (see "Not yet decided").

### Statuses and reasons

| pick\_status | Meaning | outcome | status\_reason | What consumers do |
| --- | --- | --- | --- | --- |
| open | Published; the game has not started | null | null | BFF serves it; the monitor watches it |
| awaiting\_result | The game has started; not graded | null | null | BFF serves it with the closing market; the monitor stops |
| cancelled | The engine stopped backing the pick before the game started | null | should be set | BFF serves it as cancelled, with copy for the reason; the monitor stops and deletes its overlay |
| settled | Graded on the entry odds | won, lost or push | null | BFF serves the result |
| void | The game was postponed or cancelled, or the market voided | void | set when known, usually game\_void | BFF serves it as void |
| withdrawn | Published in error | null | optional | BFF never serves it; the monitor stops |

Reason codes (Provisional): probability\_moved (the model no longer backs the pick), market\_moved (the price moved past the edge), lineup\_change, withdrawn, game\_void (the game or market was voided). A line move alone is never a reason to cancel: the pick stays open and its edge\_status becomes closed.

### Edge basis, threshold and formulas

A pick is published because its entry edge clears a threshold on the producer's chosen basis. The record states both, because the monitor and the BFF derive the break-even price b, the edge state and the app's edge from them. p is probability, d a decimal price, t edge\_threshold.

```latex
\text{ev: } \text{edge} = p \times d - 1, \; b = \frac{1 + t}{p} \qquad \text{prob: } \text{edge} = p - \frac{1}{d}, \; b = \frac{1}{p - t} \;(\text{none if } p \le t) \qquad m = \frac{d_{\text{entry}} + b}{2}
```

- entry\_edge is on edge\_basis, as a fraction, and is greater than edge\_threshold.
- probability is the probability the pick was selected on. If the engine blends its model toward the market before selecting, it writes the blended value.
- current\_edge is on edge\_basis at the current price, and only while current\_line equals line. After a line move it is null.
- b and m are computed from unrounded inputs, then 4 decimal places: b rounded down, m half away from zero.
- edge\_status, when written, follows these rules, first match wins: no current price or book pulled, suspended; lines differ, closed; current price ≤ b, closed; entry price > b and current price ≤ m, narrowing; otherwise live. No observation leaves it null.
- Other selection rules, such as a cap on disagreement with the market or stake bands, decide whether a pick exists and how much to stake, not its break-even price. They stay the producer's to define and are published in its run metadata.
- Producers never convert to the app's display basis; the BFF does that from probability and the price.
- American odds come from the decimal: d ≥ 2 gives +round((d − 1) × 100); d < 2 gives round(−100 / (d − 1)), half away from zero.

| Case | Input | Expected |
| --- | --- | --- |
| P-1 | ev basis, p 0.58, entry 1.9091 | entry\_edge 0.1073 |
| P-2 | prob basis, p 0.58, entry 1.9091 | entry\_edge 0.0562 |
| P-3 | Engine computes 5.0 percentage points on prob basis | entry\_edge written as 0.05 |
| P-4 | ev basis, p 0.55, t 0 | b 1.8181 (−122) |
| P-5 | prob basis, p 0.55, t 0.03 | b 1.9230 |
| P-6 | prob basis, p 0.40, t 0.03, entry 3.0000 | entry\_edge 0.0667, b 2.7027 (+170), m 2.8514 |
| P-7 | ev basis, p 0.55, entry 2.0000 line 24.5; current 1.9500 line 24.5 | current\_edge 0.0725, edge\_status live |
| P-8 | As P-7, current line 25.5 | current\_edge null, edge\_status closed |
| P-9 | Decimal 1.8696 | American −115 |

## Fields

Frozen fields keep their first-publish value; live fields change as later runs observe the market or grade the pick.

| Field | Type | Null when | Meaning | Changes |
| --- | --- | --- | --- | --- |
| schema\_version | string, 4.x.y | never | Version of this contract the record follows | per write |
| pick\_id | string | never | Identity (rule 1) | frozen |
| region | au, us | never | Region the pick is published for | frozen |
| sport | nba, nfl, mlb, wnba, epl | never | League of the game, the same value the app's sport field carries | frozen |
| game\_sk | integer | never | The game | frozen |
| pick\_kind | game, player | never | Stated, never inferred from the container | frozen |
| market | moneyline, spread, total, draw, btts, player\_prop | never | player\_prop exactly when pick\_kind is player | frozen |
| side | home, away, over, under, yes, no, draw | never | The backed side | frozen |
| line | number | the market has no line | Line at entry. Spread from the backed side's view, negative when giving points; total or player threshold positive | frozen |
| team\_sk | integer | the market backs no team (total, draw, btts, player prop) | The backed team | frozen |
| player\_sk | integer | not a player pick | The player | frozen |
| stat\_code | string, such as pts | not a player pick | The stat | frozen |
| probability | number, between 0 and 1 | never | Probability the pick was selected on | frozen |
| projection\_value, projection\_unit | number, string such as points | the model makes no projection for the market | Projection at the entry line | frozen |
| pick\_date\_time | date-time | never | First publish | frozen |
| entry\_decimal\_odds, entry\_american\_odds | number, integer | never | Price at first publish | frozen |
| entry\_edge | number, fraction | never | Edge at entry on edge\_basis | frozen |
| edge\_basis | ev, prob | never | Basis the pick was selected on | frozen |
| edge\_threshold | number ≥ 0, fraction | never | Threshold t the entry edge cleared | frozen |
| stake\_units | number ≥ 0 | never | Recommended stake | frozen |
| odds\_source\_kind | bookmaker, market\_average | never | Where the entry price came from | frozen |
| entry\_bookmaker\_id | string, lowercase such as draftkings | odds\_source\_kind is market\_average | The entry bookmaker | frozen |
| current\_decimal\_odds, current\_american\_odds | number, integer | no observation yet, or the book has pulled the price | Latest observed price | live |
| current\_line | number | no observation yet, the market has no line, or the price is pulled | Latest observed line | live |
| current\_odds\_source\_kind, current\_bookmaker\_id | as the entry pair | no observation yet; the id also for a market average | Where the latest price was observed | live |
| observed\_at | date-time | no observation yet | When the latest price was observed at the book | live |
| is\_closing | boolean | never; false with no observation | true for the last observation before the game started | live |
| current\_edge | number, fraction | no current price, or current\_line differs from line | Edge on edge\_basis at the latest price | live |
| edge\_status | live, narrowing, closed, suspended | no observation yet | Edge state at the latest observation | live |
| rec\_action | play, watch, pass | always in 4.0 | Recommended action, not yet produced | live |
| pick\_status | open, awaiting\_result, cancelled, settled, void, withdrawn | never | Lifecycle | live |
| status\_reason | reason code | pick\_status is open, awaiting\_result or settled; or no reason is known | Why cancelled, void or withdrawn | live |
| outcome | won, lost, push, void | until settled or void | Grade on the entry odds | live |

## Game picks and player picks

One record shape carries both game picks (WLTP: moneyline, spread, total, draw, both teams to score) and player picks (PS: player props). pick\_kind says which; market, side, line and the team, player and stat fields say exactly what is backed, so no consumer decodes a type string, a code or a bookmaker field.

| market | pick\_kind | side | line | team\_sk | player\_sk and stat\_code |
| --- | --- | --- | --- | --- | --- |
| moneyline | game | home or away | null | the backed team | null |
| spread | game | home or away | from the backed side's view; negative when it gives points | the backed team | null |
| total | game | over or under | the total, positive | null | null |
| draw | game | draw | null | null | null |
| btts | game | yes or no | null | null | null |
| player\_prop | player | over or under | the threshold, positive | null | the player and the stat |
| player\_prop | player | yes or no | null | null | the player and the stat |

- **Home and away come from the game**, not from team\_1 and team\_2 order. A producer that works in t1/t2 or favourite/underdog writes the side of the team it backs, and that team's team\_sk.
- **Three-way moneyline.** In a sport with draws (epl), moneyline loses on a draw, and the draw is its own market.
- **Milestone props** ("25+ points") are written as over with line k − 0.5 (over 24.5). **Yes/no props** (anytime touchdown) are yes or no with a null line.
- **Full game, one line per pick.** 4.0 has no halves, quarters or periods. A pick on an alternate line is a pick with that line; nothing flags it. Quarter lines (Asian handicap 0.25 steps) are not allowed, because they split the stake.
- **entry\_edge comes from entry\_decimal\_odds as written** (at most 4 places), so a consumer recomputing it gets the same number. Rounding the price after computing the edge breaks this.

### Stat codes (Provisional)

| Sport | stat\_code | Stat | Written today as |
| --- | --- | --- | --- |
| nba | pts, reb, ast, threes | points, rebounds, assists, three-pointers made | the same. The publisher also allows stl, blk, pra, pr and pa; none is produced |
| nfl | pass\_yds, pass\_tds, rush\_yds, rec\_yds, receptions | passing yards, passing touchdowns, rushing yards, receiving yards, receptions | PaYDs, PaTDs, RuYDs, RecYDs, REC |
| nfl | anytime\_td | anytime touchdown, a yes/no prop | TD, as player\_yes or player\_no with line 0.5 |
| mlb | hits, runs, home\_runs, rbi | batter hits, runs, home runs, runs batted in | H, R, HR, RBI |
| mlb | strikeouts, hits\_allowed, earned\_runs | pitcher strikeouts, hits allowed, earned runs | K, HA, ER. One doc example uses H for both hits and hits allowed |
| wnba, epl | none | no player picks are produced |  |

### How each league's picks map onto the record

Checked at app-data dev 2b6f998 and nba\_bet\_engine dev 3bfbb8b. NBA player picks are suspended there for now and will be reinstated; the mapping is unchanged.

| League and type | Written today | Becomes |
| --- | --- | --- |
| NBA game (WLTP) | market h2h, spread or total; selection t1, t2, over or under; line as a number | moneyline, spread or total; t1 or t2 becomes home or away of that team; over and under unchanged |
| NBA player (PS) | market prop; type player\_over or player\_under; stat pts, reb, ast or threes; line as a number | player\_prop; over or under; stat\_code unchanged |
| NFL game | type H2H, spread\_fav, spread\_dog, higher\_TP or lower\_TP; the team only in bet\_line (T1\_... or T2\_...); the line as a string in bookmaker.position | moneyline; spread on the side of the team in bet\_line; total over or under |
| MLB game | type H2H, higher\_TP or lower\_TP | moneyline; total |
| WNBA game | type H2H, higher\_TP or lower\_TP | moneyline; total |
| EPL game | type H2H, DRAW, BTTS\_YES, BTTS\_NO, higher\_TP, lower\_TP, spread\_fav or spread\_dog | moneyline (three-way), draw, btts yes or no, total, spread |
| NFL player | type player\_over, player\_under, player\_yes or player\_no; stat PaYDs and others; the line as a string in bookmaker.position | player\_prop; over, under, yes or no; stat\_code per the table; null line for yes and no |
| MLB player | type player\_over or player\_under; stat H, R, HR, RBI, K, HA or ER | player\_prop; stat\_code per the table |
| WNBA player | Written as a raw copy with no document type; no consumer reads it | Nothing until produced |
| EPL player | None | Nothing |

### Examples

| # | Pick | pick\_kind | market | side | line | team\_sk | player\_sk | stat\_code | pick\_id |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| G1 | NBA: Celtics -4.5, Celtics at home | game | spread | home | -4.5 | Celtics | null | null | `{game_sk}\|spread_t1\|t1\|-4.5\|main\|full\|{region}` |
| G2 | NBA: over 224.5 total points | game | total | over | 224.5 | null | null | null | `{game_sk}\|total_over\|over\|224.5\|main\|full\|{region}` |
| G3 | NBA: Knicks to win, Knicks away | game | moneyline | away | null | Knicks | null | null | `{game_sk}\|h2h_t2\|t2\|null\|main\|full\|{region}` |
| G4 | EPL: draw | game | draw | draw | null | null | null | null | `{game_sk}\|draw_draw\|draw\|null\|main\|full\|{region}` |
| G5 | EPL: both teams to score, no | game | btts | no | null | null | null | null | `{game_sk}\|btts_no\|no\|null\|main\|full\|{region}` |
| G6 | EPL: home team to win (loses on a draw) | game | moneyline | home | null | home team | null | null | `{game_sk}\|h2h_t1\|t1\|null\|main\|full\|{region}` |
| G7 | NFL: underdog +6.5, underdog away | game | spread | away | 6.5 | underdog | null | null | `{game_sk}\|spread_t2\|t2\|6.5\|main\|full\|{region}` |
| G8 | MLB: under 8.5 runs | game | total | under | 8.5 | null | null | null | `{game_sk}\|total_under\|under\|8.5\|main\|full\|{region}` |
| P1 | NBA: Jayson Tatum over 24.5 points | player | player\_prop | over | 24.5 | null | Tatum | pts | `{game_sk}\|{player_sk}\|pts\|player_over\|24.5\|main\|full\|{region}` |
| P2 | NBA: under 9.5 rebounds | player | player\_prop | under | 9.5 | null | the player | reb | `{game_sk}\|{player_sk}\|reb\|player_under\|9.5\|main\|full\|{region}` |
| P3 | NFL: over 14.5 receiving yards | player | player\_prop | over | 14.5 | null | the player | rec\_yds | `{game_sk}\|{player_sk}\|rec_yds\|player_over\|14.5\|main\|full\|{region}` |
| P4 | NFL: anytime touchdown | player | player\_prop | yes | null | null | the player | anytime\_td | `{game_sk}\|{player_sk}\|anytime_td\|player_yes\|null\|main\|full\|{region}` |
| P5 | MLB: Aaron Judge over 0.5 home runs | player | player\_prop | over | 0.5 | null | Judge | home\_runs | `{game_sk}\|{player_sk}\|home_runs\|player_over\|0.5\|main\|full\|{region}` |
| P6 | NBA: 25+ points milestone (supported, not produced today) | player | player\_prop | over | 24.5 | null | the player | pts | `{game_sk}\|{player_sk}\|pts\|player_over\|24.5\|main\|full\|{region}` |

In these examples the home team is the schedule's team\_1; the slot in a real id always comes from the schedule ("Pick id"). A milestone (P6) is written as over k − 0.5, so its id has the over form, not NBA's `player_milestone` form, which 4.x does not use.

Two complete records, both valid against the schema below. P1, an NBA player pick on the probability basis (p 0.6565 at 1.87 gives 0.6565 − 1/1.87 = 0.1217), not yet observed by the monitor:

```json
{
  "schema_version": "4.0.0",
  "pick_id": "40021717862|400000000434|pts|player_over|24.5|main|full|us",
  "region": "us", "sport": "nba", "game_sk": 40021717862,
  "pick_kind": "player", "market": "player_prop", "side": "over", "line": 24.5,
  "team_sk": null, "player_sk": 400000000434, "stat_code": "pts",
  "probability": 0.6565, "projection_value": null, "projection_unit": null,
  "pick_date_time": "2026-10-22T03:00:00.000Z",
  "entry_decimal_odds": 1.87, "entry_american_odds": -115, "entry_edge": 0.1217,
  "edge_basis": "prob", "edge_threshold": 0.03, "stake_units": 1,
  "odds_source_kind": "bookmaker", "entry_bookmaker_id": "fanduel",
  "current_decimal_odds": null, "current_american_odds": null, "current_line": null,
  "current_odds_source_kind": null, "current_bookmaker_id": null,
  "observed_at": null, "is_closing": false, "current_edge": null, "edge_status": null,
  "rec_action": null, "pick_status": "open", "status_reason": null, "outcome": null
}
```

G4, an EPL draw on the expected-value basis (0.30 × 3.60 − 1 = 0.08) for the au region:

```json
{
  "schema_version": "4.0.0",
  "pick_id": "500000123|draw_draw|draw|null|main|full|au",
  "region": "au", "sport": "epl", "game_sk": 500000123,
  "pick_kind": "game", "market": "draw", "side": "draw", "line": null,
  "team_sk": null, "player_sk": null, "stat_code": null,
  "probability": 0.3, "projection_value": null, "projection_unit": null,
  "pick_date_time": "2026-10-22T06:00:00.000Z",
  "entry_decimal_odds": 3.6, "entry_american_odds": 260, "entry_edge": 0.08,
  "edge_basis": "ev", "edge_threshold": 0, "stake_units": 0.5,
  "odds_source_kind": "bookmaker", "entry_bookmaker_id": "sportsbet",
  "current_decimal_odds": null, "current_american_odds": null, "current_line": null,
  "current_odds_source_kind": null, "current_bookmaker_id": null,
  "observed_at": null, "is_closing": false, "current_edge": null, "edge_status": null,
  "rec_action": null, "pick_status": "open", "status_reason": null, "outcome": null
}
```

## Pick id

Every producer builds pick\_id with one formula: the NBA canonical id (NBA 2026 Schema Specification §3.9), extended for markets NBA does not have. NBA ids already published keep their exact spelling. Consumers still never parse pick\_id; the formula exists so every producer mints the same id for the same pick, and so the id meets rule 1.

| Pick | pick\_id |
| --- | --- |
| Game pick | `{game_sk}\|{market}_{selection}\|{selection}\|{line}\|main\|full\|{region}` |
| Player prop | `{game_sk}\|{player_sk}\|{stat_code}\|player_{side}\|{line}\|main\|full\|{region}` |
| Either, re-issued | The same, followed by `\|r{n}` |

| Part | Value |
| --- | --- |
| game\_sk, player\_sk, stat\_code, region | The record's own values |
| market | The market token: `h2h` for moneyline; `spread`, `total`, `draw` and `btts` as the record's market. A new market adds its token here, in lowercase letters and digits only, with no `_` or `\|` |
| selection | `t1` or `t2` for the backed team: its slot in the schedule (team\_1 or team\_2), found from team\_sk, never from home or away. Otherwise the record's side: `over`, `under`, `yes`, `no` or `draw` |
| selection, multi-way (reserved) | `k{competitor_sk}` for one team, player or pair among several (a tournament winner), and `p{player_sk}` for one player among a game's players (first touchdown scorer). The record cannot yet carry these picks; the side value and competitor field they need come in a 4.x minor version with the first such market |
| side | The record's side, for player props: `over`, `under`, `yes` or `no`. Milestones are over k − 0.5, so NBA's `player_milestone` form is not used in 4.x |
| line | `null` when the record's line is null. Otherwise the shortest decimal that reads back as the same number, with at least one digit after the point: `24.5`, `-4.5`, `3.0`, `220.0`, `-0.25`; zero is `0.0`, never `-0.0`. This is what Python's `repr` of a float and Spark's cast of a double to string both write |
| `main`, `full` | Fixed in 4.x. The record has no variant or period, so an alternate line is the same pick as a main line at that line, and full game is the only period |
| `r{n}` | Only on a re-issue: the engine recommends a selection again after its earlier pick in that region was cancelled or withdrawn. The first re-issue is `r2`, then `r3`. A first issue has no suffix |

Rules:

- **Checked by rebuilding.** Producer CI rebuilds each pick\_id from the record's fields and the schedule and rejects a record whose id differs.
- **`h2h` marks moneyline, and nothing else.** Older app builds recognise a moneyline pick by `h2h` in its id and keep only one side of a game's moneyline in a slip. No other token contains `h2h`.
- **Unique across sports.** game\_sk must never be used by two sports. Until data engineering confirms that the key ranges cannot overlap, producer CI rejects a game\_sk the store already holds for another sport.
- **The selection is the id without its region.** Removing `|{region}` and any `|r{n}` gives the selection, which au and us picks on the same line share and which settlement grades once.
- **Re-issue and reopening.** If cancelled picks may return to open (see "Not yet decided"), the cancelled record reopens under its own id and no re-issue is minted.
- **Follow topics.** Market tokens contain no `_`, and each form has a fixed number of parts, so two ids never differ only by `|` against `_`, which would give them the same follow topic.

| Pick | pick\_id |
| --- | --- |
| NBA spread on the team\_1 side (as published today) | `40021717862\|spread_t1\|t1\|-4.5\|main\|full\|us` |
| NBA moneyline (as published today) | `40021717862\|h2h_t1\|t1\|null\|main\|full\|au` |
| NBA player prop (as published today) | `40021717862\|400000000434\|pts\|player_over\|24.5\|main\|full\|us` |
| NFL spread on a whole line | `300019484\|spread_t2\|t2\|3.0\|main\|full\|us` |
| EPL draw | `500000123\|draw_draw\|draw\|null\|main\|full\|au` |
| EPL both teams to score, no | `500000123\|btts_no\|no\|null\|main\|full\|au` |
| NFL anytime touchdown | `300019484\|300123456\|anytime_td\|player_yes\|null\|main\|full\|us` |
| NBA total re-issued after a cancellation | `40021717862\|total_over\|over\|224.5\|main\|full\|us\|r2` |
| Reserved: golf tournament winner | `7001234\|winner_k3301\|k3301\|null\|main\|full\|us` |
| Reserved: NFL first touchdown scorer | `300019484\|firsttd_p300123456\|p300123456\|null\|main\|full\|us` |

Reference implementation (Python); producers in other languages must produce the same strings:

```python
MARKET_TOKEN = {"moneyline": "h2h", "spread": "spread", "total": "total", "draw": "draw", "btts": "btts"}

def line_token(line):
    if line is None:
        return "null"
    x = float(line)
    return repr(0.0 if x == 0 else x)  # 24.5, -4.5, 3.0, 220.0, -0.25

def pick_id(record, team_slot=None, reissue=1):
    """team_slot: "t1" or "t2", the backed team's slot in the schedule; needed when team_sk is set."""
    r = record
    if r["pick_kind"] == "player":
        parts = [r["game_sk"], r["player_sk"], r["stat_code"], "player_" + r["side"]]
    else:
        selection = team_slot if r["team_sk"] is not None else r["side"]
        parts = [r["game_sk"], MARKET_TOKEN[r["market"]] + "_" + selection, selection]
    parts += [line_token(r["line"]), "main", "full", r["region"]]
    if reissue > 1:
        parts.append(f"r{reissue}")
    return "|".join(str(p) for p in parts)
```

## JSON Schema

JSON Schema draft 2020-12, complete: it references nothing outside itself. It is closed (no field it does not define) and encodes the null rules for observations, pulled prices, sources, game and player picks, markets, lines and projections, so producer CI rejects any record that breaks them. Consumers do not validate at runtime and ignore fields they do not know, so a later 4.x that adds a field never breaks an older consumer. Rules 1 to 3 and 6 compare a record with its earlier versions or with other records, so producer CI checks them against the run's whole output and the previous publish (pick\_id unique across the output and the store; frozen fields unchanged; status forward only); the 4-decimal limit is also a test, not a schema keyword. The schema validates the record, not the stored document: the Publish Engine adds the Cosmos id when it writes, and a reader removes Cosmos's own fields (id and those starting with \_) before validating a document read back.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://contracts.xosports.ai/edge-picks/v4/producer-pick.schema.json",
  "title": "Edge Picks producer pick record 4.0.0",
  "type": "object",
  "required": ["schema_version", "pick_id", "region", "sport", "game_sk", "pick_kind", "market", "side", "line", "team_sk", "player_sk", "stat_code", "probability", "projection_value", "projection_unit", "pick_date_time", "entry_decimal_odds", "entry_american_odds", "entry_edge", "edge_basis", "edge_threshold", "stake_units", "odds_source_kind", "entry_bookmaker_id", "current_decimal_odds", "current_american_odds", "current_line", "current_odds_source_kind", "current_bookmaker_id", "observed_at", "is_closing", "current_edge", "edge_status", "rec_action", "pick_status", "status_reason", "outcome"],
  "properties": {
    "schema_version": {"type": "string", "pattern": "^4\\.\\d+\\.\\d+$"},
    "pick_id": {"type": "string", "maxLength": 255, "pattern": "^(\\d+\\|[a-z0-9]+_(t1|t2|over|under|yes|no|draw|k\\d+|p\\d+)\\|(t1|t2|over|under|yes|no|draw|k\\d+|p\\d+)\\|(null|0\\.0|-?[1-9]\\d*\\.(0|\\d*[1-9])|-?0\\.\\d*[1-9])\\|main\\|full\\|(au|us)(\\|r([2-9]|[1-9]\\d+))?|\\d+\\|\\d+\\|[a-z0-9_]+\\|player_(over|under|yes|no)\\|(null|0\\.0|-?[1-9]\\d*\\.(0|\\d*[1-9])|-?0\\.\\d*[1-9])\\|main\\|full\\|(au|us)(\\|r([2-9]|[1-9]\\d+))?)$"},
    "region": {"enum": ["au", "us"]},
    "sport": {"enum": ["nba", "nfl", "mlb", "wnba", "epl"]},
    "game_sk": {"type": "integer"},
    "pick_kind": {"enum": ["game", "player"]},
    "market": {"enum": ["moneyline", "spread", "total", "draw", "btts", "player_prop"]},
    "side": {"enum": ["home", "away", "over", "under", "yes", "no", "draw"]},
    "line": {"type": ["number", "null"]},
    "team_sk": {"type": ["integer", "null"]},
    "player_sk": {"type": ["integer", "null"]},
    "stat_code": {"type": ["string", "null"], "pattern": "^[a-z][a-z0-9_]*$"},
    "probability": {"type": "number", "exclusiveMinimum": 0, "exclusiveMaximum": 1},
    "projection_value": {"type": ["number", "null"]},
    "projection_unit": {"type": ["string", "null"]},
    "pick_date_time": {"type": "string", "format": "date-time"},
    "entry_decimal_odds": {"type": "number", "exclusiveMinimum": 1},
    "entry_american_odds": {"type": "integer"},
    "entry_edge": {"type": "number"},
    "edge_basis": {"enum": ["ev", "prob"]},
    "edge_threshold": {"type": "number", "minimum": 0},
    "stake_units": {"type": "number", "minimum": 0},
    "odds_source_kind": {"enum": ["bookmaker", "market_average"]},
    "entry_bookmaker_id": {"type": ["string", "null"], "pattern": "^[a-z0-9_]+$"},
    "current_decimal_odds": {"type": ["number", "null"], "exclusiveMinimum": 1},
    "current_american_odds": {"type": ["integer", "null"]},
    "current_line": {"type": ["number", "null"]},
    "current_odds_source_kind": {"enum": ["bookmaker", "market_average", null]},
    "current_bookmaker_id": {"type": ["string", "null"], "pattern": "^[a-z0-9_]+$"},
    "observed_at": {"type": ["string", "null"], "format": "date-time"},
    "is_closing": {"type": "boolean"},
    "current_edge": {"type": ["number", "null"]},
    "edge_status": {"enum": ["live", "narrowing", "closed", "suspended", null]},
    "rec_action": {"type": "null"},
    "pick_status": {"enum": ["open", "awaiting_result", "cancelled", "settled", "void", "withdrawn"]},
    "status_reason": {"enum": ["probability_moved", "market_moved", "lineup_change", "withdrawn", "game_void", null]},
    "outcome": {"enum": ["won", "lost", "push", "void", null]}
  },
  "allOf": [
    {
      "if": {"properties": {"current_decimal_odds": {"type": "number"}}},
      "then": {"properties": {"observed_at": {"type": "string"}, "current_american_odds": {"type": "integer"}}}
    },
    {
      "if": {"properties": {"observed_at": {"type": "null"}}},
      "then": {
        "properties": {
          "current_decimal_odds": {"type": "null"},
          "current_american_odds": {"type": "null"},
          "current_line": {"type": "null"},
          "current_odds_source_kind": {"type": "null"},
          "current_bookmaker_id": {"type": "null"},
          "current_edge": {"type": "null"},
          "edge_status": {"type": "null"},
          "is_closing": {"const": false}
        }
      },
      "else": {"properties": {"edge_status": {"type": "string"}, "current_odds_source_kind": {"type": "string"}}}
    },
    {
      "if": {"properties": {"odds_source_kind": {"const": "bookmaker"}}},
      "then": {"properties": {"entry_bookmaker_id": {"type": "string"}}},
      "else": {"properties": {"entry_bookmaker_id": {"type": "null"}}}
    },
    {
      "if": {"properties": {"pick_status": {"const": "settled"}}},
      "then": {"properties": {"outcome": {"enum": ["won", "lost", "push"]}}}
    },
    {
      "if": {"properties": {"pick_status": {"const": "void"}}},
      "then": {"properties": {"outcome": {"const": "void"}}}
    },
    {
      "if": {"properties": {"pick_status": {"enum": ["open", "awaiting_result", "cancelled", "withdrawn"]}}},
      "then": {"properties": {"outcome": {"const": null}}}
    },
    {
      "if": {"properties": {"pick_status": {"enum": ["open", "awaiting_result", "settled"]}}},
      "then": {"properties": {"status_reason": {"const": null}}}
    },
    {
      "if": {"properties": {"pick_kind": {"const": "player"}}},
      "then": {
        "properties": {
          "market": {"const": "player_prop"},
          "player_sk": {"type": "integer"},
          "stat_code": {"type": "string"}
        }
      },
      "else": {
        "properties": {
          "market": {"not": {"const": "player_prop"}},
          "player_sk": {"type": "null"},
          "stat_code": {"type": "null"}
        }
      }
    },
    {
      "if": {"properties": {"market": {"enum": ["moneyline", "spread"]}}},
      "then": {"properties": {"side": {"enum": ["home", "away"]}, "team_sk": {"type": "integer"}}}
    },
    {
      "if": {"properties": {"market": {"enum": ["spread", "total"]}}},
      "then": {"properties": {"line": {"type": "number"}}}
    },
    {
      "if": {"properties": {"market": {"enum": ["moneyline", "draw", "btts"]}}},
      "then": {"properties": {"line": {"type": "null"}}}
    },
    {
      "if": {"properties": {"market": {"const": "total"}}},
      "then": {"properties": {"side": {"enum": ["over", "under"]}, "team_sk": {"type": "null"}}}
    },
    {
      "if": {"properties": {"market": {"const": "draw"}}},
      "then": {"properties": {"side": {"const": "draw"}, "team_sk": {"type": "null"}}}
    },
    {
      "if": {"properties": {"market": {"const": "btts"}}},
      "then": {"properties": {"side": {"enum": ["yes", "no"]}, "team_sk": {"type": "null"}}}
    },
    {
      "if": {"properties": {"market": {"const": "player_prop"}}},
      "then": {"properties": {"side": {"enum": ["over", "under", "yes", "no"]}, "team_sk": {"type": "null"}}}
    },
    {
      "if": {"properties": {"market": {"const": "player_prop"}, "side": {"enum": ["over", "under"]}}},
      "then": {"properties": {"line": {"type": "number"}}}
    },
    {
      "if": {"properties": {"side": {"enum": ["yes", "no"]}}},
      "then": {"properties": {"line": {"type": "null"}}}
    },
    {
      "if": {"properties": {"observed_at": {"type": "string"}, "current_decimal_odds": {"type": "null"}}},
      "then": {
        "properties": {
          "current_american_odds": {"type": "null"},
          "current_line": {"type": "null"},
          "current_edge": {"type": "null"},
          "edge_status": {"const": "suspended"}
        }
      }
    },
    {
      "if": {"properties": {"edge_status": {"const": "suspended"}}},
      "then": {"properties": {"current_decimal_odds": {"type": "null"}}}
    },
    {
      "if": {"properties": {"current_odds_source_kind": {"const": "bookmaker"}}},
      "then": {"properties": {"current_bookmaker_id": {"type": "string"}}},
      "else": {"properties": {"current_bookmaker_id": {"type": "null"}}}
    },
    {
      "if": {"properties": {"market": {"enum": ["total", "player_prop"]}, "side": {"enum": ["over", "under"]}}},
      "then": {"properties": {"line": {"exclusiveMinimum": 0}, "current_line": {"exclusiveMinimum": 0}}}
    },
    {
      "if": {"properties": {"line": {"type": "null"}}},
      "then": {"properties": {"current_line": {"type": "null"}}}
    },
    {
      "if": {"properties": {"projection_value": {"type": "null"}}},
      "then": {"properties": {"projection_unit": {"type": "null"}}},
      "else": {"properties": {"projection_unit": {"type": "string"}}}
    }
  ],
  "additionalProperties": false
}
```

## Example record

An open NBA spread selected on the expected-value basis with threshold 0: entry 2.0000 at p 0.55 gives entry\_edge 0.1000; the latest price 1.9500 on the same line gives current\_edge 0.0725, above the midpoint 1.9091, so edge\_status is live.

```json
{
  "schema_version": "4.0.0",
  "pick_id": "40021717862|spread_t1|t1|-4.5|main|full|us",
  "region": "us",
  "sport": "nba",
  "game_sk": 40021717862,
  "pick_kind": "game", "market": "spread", "side": "home", "line": -4.5,
  "team_sk": 40000002, "player_sk": null, "stat_code": null,
  "probability": 0.55, "projection_value": null, "projection_unit": null,
  "pick_date_time": "2026-10-22T18:05:12.341Z",
  "entry_decimal_odds": 2.0, "entry_american_odds": 100, "entry_edge": 0.1,
  "edge_basis": "ev", "edge_threshold": 0,
  "stake_units": 2,
  "odds_source_kind": "bookmaker", "entry_bookmaker_id": "draftkings",
  "current_decimal_odds": 1.95, "current_american_odds": -105, "current_line": -4.5,
  "current_odds_source_kind": "bookmaker", "current_bookmaker_id": "draftkings",
  "observed_at": "2026-10-22T18:58:40.000Z", "is_closing": false,
  "current_edge": 0.0725, "edge_status": "live",
  "rec_action": null,
  "pick_status": "open", "status_reason": null, "outcome": null
}
```

## Today against this contract

Observations, not requirements: what the dev branches did when checked. Production (tst) runs nba\_bet\_engine 0430eb5, which has none of the dev-only engine changes below.

| Producer | Checked at | Pick id today | Status today | Edge today | Gaps |
| --- | --- | --- | --- | --- | --- |
| NBA game picks (WLTP) | app-data dev 2b6f998; nba\_bet\_engine dev 3bfbb8b | {game\_sk}\|{market}\_{selection}\|{selection}\|{line}\|{variant}\|full\|{region} | won or lost from the bet outcome, otherwise scheduled. A push is stored as no outcome, so it stays scheduled | Probability basis, in percentage points; odds rounded to 2 places | At most one pick per game; in dev spreads come first and a total is picked only when a game has no spread market; moneyline needs both teams to have played 10 games; the US pick is copied into au; never cancelled; picks with no edge are dropped; picks are rebuilt each run (rule 2) |
| NBA player picks (PS) | same | {game\_sk}\|{player\_sk}\|{stat}\|{type}\|{line}\|{variant}\|full\|{region} | won or lost; void when the game is final with no outcome (push or did not play); cancelled when the game was cancelled; otherwise scheduled | Probability basis, in percentage points; model probability no longer blended toward the market (the 0.30 model-vs-market cap still filters); flat 1 unit at 3 points of edge or more; generalised Poisson pricing | Suspended in dev and tst since 3bfbb8b, to be reinstated shortly. While suspended the job runs, publishes nothing and clears the picks of the games it evaluates (rule 2). Otherwise: points, rebounds, assists and threes only; top 3 per team; player\_sk written as a string; the same picks mirrored into au and us; picks of re-evaluated games deleted (45f6f4f; rule 2) |
| NFL, MLB, WNBA and EPL game picks | app-data dev 2b6f998, generic path | {game\_sk}*{bet\_type}*{region}, without the line | NFL and WNBA: one status for the whole game; MLB: per pick; EPL: none. A push is stored as no outcome | Not published: probability only | One pick per region per game; side and line only inside bet\_line, bookmaker.position and code strings; au picks can carry US books |
| NFL and MLB player picks | same; nfl\_bet\_engine dev 3cf118b (fetched Sep 14, 2026) | {game\_sk}\|{player\_sk}\|{stat}\|{type}\|{region}, without the line | Scheduled, Final or Cancelled, in mixed case. NFL: a pick whose player drops out of his position's top N on the depth chart is cancelled, and restored to Scheduled if he climbs back, until kickoff | Not published | Line and odds written as strings; stat codes in mixed case; anytime touchdown written with line 0.5; cancelled can move back to scheduled (rule 6) |
| WNBA player picks | app-data dev 2b6f998 | the game\_sk alone | none | none | A raw copy with no document type; the BFF never reads it |
| Settlement write-back | app-data dev 2b6f998 | n/a | Stubs are empty | n/a | No producer sets settled or void through it |
| Live edge monitor | live-odds dev 30e05ce | {bet id}\|{REGION} | Watches only Scheduled picks | Expected value, t = 0 | Its ids match no pick\_id; observations do not reach the record through the Publish Engine (rule 5); when a re-run changes a pick's id, the old overlay node is never deleted |

Fields still to add, by producer: sport (all); pick\_id built by the formula under "Pick id" (all except NBA, which already uses it; the WNBA player-pick id is the game\_sk alone); pick\_kind, market, side and line as structured fields (all); edge\_basis, edge\_threshold, odds\_source\_kind and entry\_bookmaker\_id (all); pick\_date\_time, entry odds, entry\_edge and stake\_units (all except NBA, which has them; WNBA player picks lack pick\_date\_time); projection; current line and bookmaker; observed\_at; is\_closing (derived by the Publish Engine); current\_edge and edge\_status (NFL has them from the monitor only); outcome as won, lost, push, void instead of 0, 1, 2.

### Values the BFF accepts until producers write this page's statuses

| Value written today | BFF serves it as | Result |
| --- | --- | --- |
| active, scheduled, Scheduled, pending | open; awaiting\_result once the game starts | none |
| expired | awaiting\_result | none |
| cancelled, for a pick the engine withdrew | cancelled | none |
| cancelled, meaning the game was cancelled (NBA player picks) | void, reason game\_void | void |
| settled with outcome 1, 0 or push; won, lost, push | settled | won, lost, push |
| void, abandoned, outcome 2 | void | void |
| rescheduled | open | none |
| removed, withdrawn | not served, no alert | none |
| anything else | not served; the BFF alerts | none |

## Not yet decided

| Item | Provisional value on this page | What could change | Decision due |
| --- | --- | --- | --- |
| Status vocabulary | open, awaiting\_result, cancelled, settled, void, withdrawn | Names or the split between cancelled and withdrawn | Oct 21, 2026 |
| Cancelled returning to open | Not allowed: status only moves forward | Allow cancelled to return to open before the game starts, as the NFL engine does when a player climbs back up the depth chart; or the NFL engine stops reinstating | With the status vocabulary |
| Reason codes | probability\_moved, market\_moved, lineup\_change, withdrawn, game\_void | withdrawn may be dropped as a reason (it is a status); book\_pulled and competitor\_withdrawn may be added | Oct 21, 2026 |
| Stat codes | The table under "Stat codes" | Names, and codes for stats not produced yet | With the status vocabulary |
| When the engine cancels | When it stops backing a pick before the game; never for a line move alone | Which re-evaluations cancel, and with which reasons | Oct 30, 2026 |
| Engine persistence | Rule 2 | How the NBA engine keeps earlier picks while rebuilding, and how a producer pauses without removing published picks (the NBA player-pick switch clears them today) | Before the engine's next tst promotion, and before NBA player picks are reinstated |
| Periods, quarter lines | Full game only; no quarter lines | Halves or quarters would add a period field, a minor version | Not scheduled |
| Document layout and id format | Layout proposed in KDD-001; the id formula is fixed ("Pick id") | The container name per environment; tokens for markets added later; confirmation that game\_sk ranges never overlap between sports | With KDD-001 |
| App display basis | Not a producer concern; the BFF converts | Nothing on this page | Oct 23, 2026 |

## Change log

| Date | Version | Change | Signed by |
| --- | --- | --- | --- |
| Oct 19, 2026 | 4.0.0 draft | First self-contained draft. Same day: market rules for game and player picks, stat codes, each league's mapping and examples added; the schema now checks side, line and team per market. After review: schema closed, with the observation, pulled-price, source, game-pick, line and projection rules; pausing never removes picks; 5-minute observation rule; nba\_bet\_engine and live-odds observations moved to 3bfbb8b and 30e05ce. Second review: current\_line must also be positive on totals and over/under props. KDD review: sport added; pick\_id unique across regions and sports, with a restricted character set; the schema validates the record, not the stored document. Pick id formula: the NBA canonical id for every producer, with one line spelling, a re-issue suffix and reserved multi-way selections; the schema checks its shape; the EPL example id rewritten; the examples table shows each pick's id | Bet engine: pending. Data engineering: pending. BFF: pending. Edge monitor: pending |
