# XO Canonical Data Model v3 — Proposal

Oct 16, 2026 · @Tze Liang

## Summary

Rebuild the model around seven sport-neutral entities, centred on **event, market, selection, pick and observation** — plus one versioned registry that holds every word, unit and rule, and generate every layer's validator from it. NBA 2026 got the hardest parts right (orthogonal bet axes, contract identity, one writer per document); this proposal keeps those and removes what still ties it to basketball and to string parsing.

What changes, in one line each:

- **One document set for all five leagues.** Eight generic document types replace the NBA 2026 set and the four Format A variants. Sport differences live in a sport profile, not in field names (`draw_probability`, `total_score`, `pitcher`, `quarterbacks`).
- **Competitors, not two team slots.** An event has N competitors (teams, players or pairs); outcomes and results reference a competitor. Two-sided sports use slots `c1`/`c2`, so tennis, F1 or golf would need a profile, not a new model.
- **A pick is a recommendation on a selection, not a price.** Entry is frozen at first publish; the market's later state is an observation. A line move no longer deletes the pick, which reconciles NBA 2026's contract identity with the Edge Picks v4 card.
- **Prices keep their native form; edge and EV come from the full outcome split.** A book's American, decimal or probability quote is stored as quoted. Each pick carries the probability of every result (`won`, `half_won`, `push`, `half_lost`, `lost`), so whole and quarter lines are priced correctly. `edge_prob` and `ev` are derived from that split and the native price by one shared library. The engines use "edge" for three different things today (R2).
- **Projections and probabilities are one structure.** Team scores, xG, totals, player stats and win/draw/BTTS probabilities become rows keyed by subject, stat and period, so a new sport adds rows, not fields.
- **No display words or encoded strings in documents.** `code`, `bet_line`, `position` and `stat_name` go; the registry supplies labels, units, plurals and decimals, and the BFF renders them.
- **User positions are a separate ledger.** Slips placed through Betfair, Kalshi, Polymarket or a sportsbook are recorded as append-only position events, settled by the venue's own rules and kept apart from XO's grading of its picks.
- **The registry is executable.** One source generates Spark schemas for the engines, JSON Schema for the Publish Engine, TypeScript for the BFF and app, and golden copy fixtures; a producer cannot publish an undeclared stat. §Validation lists which formulas were round-trip tested, and on what samples.

Migration fits the season calendar: WNBA and MLB move in their off-seasons first, NBA dual-publishes, NFL and EPL follow once the shape has run in production.

## Design principles

Every rule below follows from these eight; a proposed field that breaks one needs a written exception.

1. **Facts, not copy.** Documents carry typed values and registry keys. No display words, no strings that need parsing, no numbers as strings.
2. **Sport lives in data.** A sport differs by its profile and its registry entries, never by field names or document shapes. Adding a league is a registry change.
3. **Identity is the contract.** A selection's key says exactly what would be settled; a pick's key says who recommended it, where and when. Neither ever changes meaning.
4. **Recommendations are immutable; markets move.** What the engine recommended at publish is frozen. What the market did afterwards is a separate, time-stamped observation.
5. **One owner, one writer.** Each value is computed in one system; the Publish Engine is the only writer of every document.
6. **Explicit absence.** A field is always present; `null` means unknown, `[]` means none. No omitted keys, no sentinels.
7. **Additive by default.** New optional fields and new registry entries are minor versions; renames, removals and changes of meaning are majors, gated by consumers.
8. **Executable or it doesn't exist.** A rule that no generated validator checks is a comment, not a contract.

## What changes from NBA 2026

About half of NBA 2026 carries over unchanged; the changes remove basketball assumptions, legacy parsing fields and the conflicts with Edge Picks v4.

| NBA 2026 element | Verdict | v3 | Why |
| --- | --- | --- | --- |
| Orthogonal axes: market, selection, variant, period | Keep | Same axes, values come from the registry | Already sport-neutral and proven |
| `t1`/`t2` participant slots, `venue_role` separate | Change | `venue_role` required; slots become c1/c2 over N competitors | Neutral venues; tennis, F1, golf and outright markets have more than two sides |
| Contract identity in the id (line, variant, period) | Keep | Moves to `selection_key`; `pick_id` = selection + region | Fixes every legacy failure mode in the Bet Types spec §5 |
| "A line move mints a new id; the old one disappears" | Change | Old pick stays, entry frozen; the move is an observation; a new pick is optional | Edge Picks v4 needs the original card with Market Movement |
| Split picks vs predictions documents, one writer (PE) | Keep | Seven generic document types | Removes lock contention; same writers |
| `edge` in percentage points | Change | Two fractions from the outcome split: edge\_prob = A/B − 1/d and ev = d × A − B (p − 1/d and p × d − 1 when nothing can push) | "Edge" means three things across engines (NBA p − 1/d, NFL EV, EPL both); v4's card formula is p × d − 1; none of them handles a push in the shared contract |
| `predicted[].value` as a 2 dp string | Change | Number; decimals are presentation | Numbers are numbers |
| `threshold_k` beside `line` | Change | One `line`; outcome `at_least` with an integer line | One field to validate and settle |
| Flat `type` token (`spread_t1`) | Drop | Derive in code if wanted | A second source of truth for market + outcome |
| `code`, `bookmaker.bet_line`, `bookmaker.position` | Drop | PE emits them only to legacy readers during migration | Exist for BFF string parsing |
| `stat_name` in documents | Drop | Registry supplies every label | Root cause of XPRB-45 and the four "threes" labels |
| Team and player names in fact documents | Drop | Ids only; names from reference data | One owner per value; renames never touch picks |
| `game_prediction` fields (`point_spread` unsigned, `draw_probability`, `total_points`) | Change | Market probabilities + projection rows | No draw, BTTS or xG field per sport |
| Player tree `players[]` ranked by projected points | Change | Players with role, group and order from the profile | Fits pitchers/batters, NFL groups, EPL formations |
| `injuries` team document (NBA-only) | Change | `injuries` per competitor (NBA's 1 RU team read, generalised); lineups and withdrawals move to a per-event `availability` document | Injuries belong to a competitor, lineups to an event; one shape each for all sports |
| Region map in picks documents | Change | Flat `picks[]` with a `region` field | One pick struct; no team-slot nesting |
| `pick_status` list incl. `scheduled`, `pending` | Change | One vocabulary shared with the app contract (§Lifecycle) | Ends the D5 mapping table |
| `bet_outcome` 1/0/2 | Change | `result`: won, lost, push, void, half\_won, half\_lost | Explicit; supports quarter lines |
| `taxonomy_version` stamp | Keep | Registry semver + schema semver per document | Already in place |
| player\_sk type | Settle | Number everywhere; ids embed the digits | The Schema Specification says BIGINT; the Bet Types Specification says a decimal string, in both its rules and its JSON Schema |
| model\_win\_prediction on game picks | Drop | Derived from game\_projections outcome probabilities | Bet Types lists it as an optional pick field; the local spec copy calls it aggregate-only. It is a projection fact, not a pick fact |
| outcome result.match\[\] / result.player\[\] and the settlement write-back | Keep | event\_result.gradings\[\] keyed by selection\_key; PE writes status and result back into the picks documents | Keeps one writer per document; grading per selection instead of per region id |
| Containers, partition keys, point reads | Keep | Same containers and partition key paths (§Documents) | About 10–15 RU per match view; a partition key path cannot change on an existing container |
| Region = audience, US prices mirrored into AU | Keep | region names the audience; entry.source names the venue that priced it | NBA 2026 launches with US-only odds; the venue must be explicit so AU cards can say whose price it is |

## Core model

Seven entities cover every league; a sport never adds an entity, only registry entries.

&#91;embedded content: core model · 7 entities, 1 registry\]

The chain reads left to right: an **event** has **markets**, a market offers **selections**, and a **pick** recommends exactly one selection in one region. The pick cites the **projection** it was based on and freezes its entry; **observations** record what the market did afterwards; **settlement** is per selection, so every pick and every saved My Picks slip on that selection settles identically.

Two separations do most of the work:

- **Selection vs pick.** The selection is the financial contract ("Celtics −4.5, full game"); the pick is XO's recommendation of it at a time and price. NBA 2026 merged them, so a line move had to delete the pick. Here a line move leaves the pick in place, its observation shows the new line, and the engine may recommend the new selection as a second pick.
- **Projection vs probability vs pick.** A projection estimates a quantity (Tatum 27.8 points; Arsenal 1.6 goals). A market probability prices an outcome (Arsenal win 0.52, draw 0.26). A pick applies a threshold to a probability and a price. Each has one owner.
- **XO's grade vs a user's position.** Settlement grades XO's pick on the selection's rules at the entry price, for the track record. A user's slip on Betfair, Kalshi or a sportsbook is a separate position, settled by that venue's rules and fills (§Positions). The two can differ legitimately.

Competitors are the event's participants, two or N: teams in NBA, MLB, NFL and EPL, players in tennis, drivers in F1, a field in golf. Two-sided sports address them as slots `c1` and `c2` (aliases of NBA 2026's `t1`/`t2`); `venue_role` (home, away, neutral) is a separate attribute used only for display. The Publish Engine takes it from the schedule (`dim_all_games`, where `team_1` is home); a sport with no home side (tennis, golf, F1) gives `neutral`. Whether the schedule flags neutral sites, such as NFL international games, is not yet checked.

## Taxonomy registry

The registry is one versioned repository of YAML that defines every key a document may carry and everything needed to validate, settle and display it. Documents hold keys; the registry holds meaning.

| File | Holds | Owner |
| --- | --- | --- |
| `sports/<sport>.yaml` | The sport profile: competitor kind, periods, enabled markets, settlement basis, roster groups, features, formatting | Sport owner (ML lead per sport) |
| `leagues.yaml` | League → sport, regions, release gate, season shape, colour and crest keys | Product |
| `markets.yaml` | Market types, their outcomes, required fields and line rules | Platform |
| `stats/<sport>.yaml` | Every stat: key, subject, eligible roles, value type, unit, components, feed and engine aliases | Sport owner |
| `units.yaml` | Units with singular, plural and short forms | Product |
| `venues.yaml` | Every place a price comes from or a user can bet: sportsbooks, exchanges, prediction markets; native price format, fee model, settlement rules, jurisdictions, deep-link template | Data engineering, legal |
| `messages/<locale>.yaml` | Every display string, as ICU MessageFormat with plurals | Product |

### Key rules

- **Keys name concepts and are sport-qualified:** `basketball.threes_made`, `baseball.pitcher_hits_allowed`, `football.anytime_touchdown`. A key never changes meaning; a new meaning is a new key.
- **Key charset is `[a-z0-9_.]`.** No `:` or `|`, because both delimit the identity keys; registry CI rejects anything else. Venue instrument ids (a Kalshi ticker, a Betfair market id) are values, never keys.
- **Roles disambiguate, not codes.** MLB's `H` is two stats (`batter_hits`, `pitcher_hits_allowed`); NFL's `TDs` is two (`passing_touchdowns`, `anytime_touchdown`). Each alias declares the context it resolves in.
- **Every stat says where it can be bet.** `eligible_markets` lists the markets a pick on it may use; `[]` means projection only. Milestone stats list their allowed `thresholds`. Fantasy stats must name their `scoring` system, or they cannot be settled. Gate 1 rejects a pick that breaks any of these.
- **Aliases are declared drift with an expiry.** Every engine, feed and legacy code is an alias with a `source` and a `remove_after` date; validators reject an alias past its date.
- **Display is never in the stat entry itself.** A stat points at message ids; translations and plurals live in `messages/`, so the client can localise without a new document field.
- **Combos are stats.** `basketball.pts_reb_ast` lists its components; settlement sums them. No combo market types.
- **Outcomes reference competitors.** A two-sided market's outcomes are the slots `c1`/`c2`; an N-way market's outcome is one competitor's key. `t1`/`t2` stay as aliases until NBA 2026 retires.

### Examples

```yaml
# stats/baseball.yaml
- key: baseball.pitcher_hits_allowed
  subject: player
  roles: [pitcher]
  value: count
  unit: hits
  eligible_markets: [player_line]
  settle_from: fact_player_stats.pitching_hits
  aliases:
    - { value: H, source: legacy_doc, when: { role: pitcher }, remove_after: 2027-06-30 }
    - { value: HA, source: mlb_bet_engine }
    - { value: predicted_pitching_hits, source: mlb_pof }
    - { value: Pitching Hits, source: odds_feed }
  display: { short: stat.baseball.hits_allowed.short, long: stat.baseball.hits_allowed.long }

- key: baseball.batter_fantasy_points
  subject: player
  roles: [batter]
  value: continuous
  unit: fantasy_points
  scoring: tbc                 # required: the named scoring system the model targets
  eligible_markets: []         # projection only: gate 1 rejects any pick on it
  aliases: [{ value: FP, source: legacy_doc, when: { role: batter } }]

# stats/basketball.yaml
- key: basketball.threes_made
  subject: player
  value: count
  unit: three_pointers
  eligible_markets: [player_line, player_threshold]
  thresholds: [1, 2, 3, 4, 5]   # milestone rungs the engine may publish
  settle_from: fact_player_stats.fg3m
  aliases:
    - { value: threes, source: nba_2026_doc, remove_after: 2027-10-01 }
    - { value: three_pointers, source: nba_pof }
    - { value: player_threes, source: odds_feed }

- key: basketball.steals
  subject: player
  value: count
  unit: steals
  eligible_markets: [player_line, player_threshold]
  thresholds: [1, 2, 3]         # ladder depth is product's call (Bet Types §9); any subset is valid
  aliases: [{ value: stl, source: nba_2026_doc, remove_after: 2027-10-01 }]

- key: basketball.pts_reb_ast
  subject: player
  value: count
  unit: points_rebounds_assists
  components: [basketball.points, basketball.rebounds, basketball.assists]
  eligible_markets: [player_line, player_threshold]
  aliases: [{ value: pra, source: nba_2026_doc, remove_after: 2027-10-01 }]
```

```yaml
# markets.yaml
# outcome kinds: slot (c1, c2), draw, over, under, yes, no, at_least, at_most, competitor
- key: h2h
  subject: none
  outcomes: { two_way: [c1, c2], three_way: [c1, draw, c2] }   # the sport profile picks one
  line: forbidden
- key: spread
  subject: none
  outcomes: [c1, c2]
  line: { required: true, signed: backed_side, step: 0.25 }
- key: total
  subject: none
  outcomes: [over, under]
  line: { required: true, signed: false }
- key: btts
  subject: none
  outcomes: [yes, no]
  line: forbidden
- key: player_line
  subject: player
  stat: required
  outcomes: [over, under]
  line: { required: true, signed: false }
- key: player_threshold
  subject: player
  stat: required
  outcomes: [at_least]
  line: { required: true, integer: true }   # 3 means 3+; never pushes
- key: player_event
  subject: player
  stat: required        # e.g. football.anytime_touchdown
  outcomes: [yes, no]
  line: forbidden
# reserved for multi-competitor sports; valid in the schema, enabled by no live profile
- key: winner
  subject: none
  outcomes: [competitor]              # one row per competitor in the field
  line: forbidden
  settlement: { dead_heat: fraction }
- key: finish_position
  subject: competitor
  outcomes: [at_most]                 # top 3, top 10
  line: { required: true, integer: true }
  settlement: { dead_heat: fraction }
- key: matchup
  subject: none
  competitors: required               # a named subset of the field, e.g. two drivers
  outcomes: [competitor, draw]
  line: forbidden
```

```yaml
# messages/en.yaml (ICU MessageFormat)
unit.runs: "{n, plural, one {# Run} other {# Runs}}"
unit.goals_xg: "{n} Goals (xG)"
pick.total: "Total {unit_plural} {outcome} {line}"
pick.spread: "{team} {signed_line}"
pick.player_line: "{player} {outcome} {line} {stat_short}"
pick.player_threshold: "{player} {line}+ {stat_short}"
projection.margin: "{team} by {unit_value}"
market.h2h.label: "{region, select, au {Win} other {Moneyline}}"
```

### Stat coverage for the five live leagues

The first registry release must declare at least these; anything an engine publishes outside this list fails its build.

| League | Player stats (registry keys, short) | Count | Notes |
| --- | --- | --- | --- |
| NBA | points, rebounds, assists, threes\_made, steals, blocks, pts\_reb\_ast, pts\_reb, pts\_ast | 9 | BR-05 required; BR-06 (steals, blocks, combos) optional, product to decide. Threes cannot be priced until prop odds and the ML threes output are ingested (Bet Types §8) |
| WNBA | points, rebounds, assists (+ the NBA set when modelled) | 3 | Shares `sports/basketball.yaml` |
| MLB | batter: hits, home\_runs, runs, rbis, total\_bases, fantasy\_points; pitcher: strikeouts, hits\_allowed, earned\_runs, fantasy\_points | 10 | Two fantasy-points keys, scoring differs by role; both projection-only (no eligible market, scoring system to be named) |
| NFL | passing\_yards, passing\_touchdowns, rushing\_yards, rushing\_touchdowns, receiving\_yards, receiving\_touchdowns, receptions, anytime\_touchdown | 8 | Rushing and receiving TDs (RuTDs, RecTDs) added 16 Oct. The engine's other six STAT\_TYPE\_MAP keys (FP, INT, CMP, ATT, CAR, TGT) publish to projections; FP is projection-only, as NBA 2026 keeps fantasy markets out of scope (Bet Types §7) |
| EPL | none today | 0 | Team-level projections only; lineup position is roster data, not a stat |

## Documents

Eight document types, identical for every league, replace the NBA 2026 set and all four Format A variants. Writers, containers and partition keys stay as NBA 2026 has them (Schema Specification §6); only shapes change.

| Document | One per | Holds | Writer (via PE) | Container / partition key | Replaces |
| --- | --- | --- | --- | --- | --- |
| `event` | event | Competitors (slot, kind, venue role), parent event and stage, start time, status | Silver ETL | `c-sch` / `/game_date` | `schedule` |
| `event_result` | event | Final status; per-competitor result (score, placing, status such as DNF or retired); scores by period; `gradings[]` of XO picks by `selection_key` | Settlement ETL | `c-outcomes` / `/game_sk` | `outcome`, including `result.match[]` and `result.player[]` |
| `injuries` | competitor | Current injuries for one team or individual competitor | Injury ETL | `c-injuries-team` / `/team_sk` | NBA `injuries`, EPL `player_injuries` |
| `availability` | event | Lineup status, formation, roster rows (role, group, order), withdrawals | Lineup ETL | `c-ps` / `/game_sk` | Roster blocks in player documents, EPL lineups |
| `game_projections` | event | Outcome probabilities per market and competitor/game projections | Inference | `c-wltp` / `/game_sk` | `game_prediction` (all versions) |
| `player_projections` | event | Player projection rows | Inference | `c-ps` / `/game_sk` | `player_predictions` (all shapes) |
| `game_picks` | event | Game-level picks, flat list | Bet engine | `c-wltp` / `/game_sk` | `game_edge_picks`, `top_picks` in `game_prediction` |
| `player_picks` | event | Player picks, flat list | Bet engine | `c-ps` / `/game_sk` | `player_edge_picks`, `player_top_picks` |

A Cosmos partition key path cannot change on an existing container, so v3 documents keep the partition fields NBA 2026 uses: `game_sk` (equal to `event_sk`), `game_date` and `team_sk` (equal to `competitor_sk`). Renaming them means new containers; that is only worth it if a non-team sport ships (V15). A match view stays one point read per document, about 10–15 RU, as NBA 2026 measured.

### Event and result (competitors, not team slots)

```json
{
  "...envelope": "event/3.0",
  "parent_event": null, "stage": null,
  "starts_at": "2026-10-23T23:00:00.000Z",
  "status": "scheduled",
  "competitors": [
    { "slot": "c1", "kind": "team", "competitor_sk": 40000002, "venue_role": "home" },
    { "slot": "c2", "kind": "team", "competitor_sk": 40000020, "venue_role": "away" }
  ]
}
```

```json
{
  "...envelope": "event_result/3.0",
  "status": "final",
  "results": [
    { "slot": "c1", "score": 112, "placing": 1, "status": "finished" },
    { "slot": "c2", "score": 108, "placing": 2, "status": "finished" }
  ],
  "by_period": [ { "period": "q1", "scores": { "c1": 28, "c2": 31 } } ],
  "gradings": [
    { "selection_key": "nba:40021717862:spread:full:-:-:c1:-4.5", "result": "lost", "settlement_fraction": null, "graded_at": "2026-10-24T02:45:00.000Z" }
  ]
}
```

The settlement ETL grades each selection once; the PE then writes `status`, `result` and `settled_at` into every pick on that selection, in both regions, as NBA 2026's write-back loop does today. Grades that match no published selection go to a rejections table, as `nba_settlement_rejections` does.

A golf event has 150 competitors with `kind: player` and no slots; a tennis match has two with slots and `parent_event` pointing at the tournament. The shapes do not change.

### Envelope (every document)

```json
{
  "id": "epl|game_picks|500000123",
  "doc_type": "game_picks",
  "schema": "game_picks/3.0",
  "registry_version": "1.0.0",
  "sport": "soccer", "league": "epl", "season": 2026,
  "event_sk": 500000123,
  "as_of": "2026-10-22T18:00:00.000Z",
  "produced_by": { "engine": "epl_bet_engine", "engine_version": "3.4.0", "run_id": "wltp|2026-10-22T18:00Z" },
  "published_at": "2026-10-22T18:02:11.000Z"
}
```

### Projections without sport-specific fields

Win, draw and BTTS probabilities are rows on markets; xG and integer scorelines are two estimates of the same stat. The same shape carries an NBA game with no draw row and an MLB game with runs.

```json
{
  "...envelope": "game_projections/3.0",
  "outcome_probabilities": [
    { "market": "h2h", "period": "full", "outcome": "c1", "p": 0.52 },
    { "market": "h2h", "period": "full", "outcome": "draw", "p": 0.2315 },
    { "market": "h2h", "period": "full", "outcome": "c2", "p": 0.2485 },
    { "market": "btts", "period": "full", "outcome": "yes", "p": 0.618 }
  ],
  "projections": [
    { "subject": { "kind": "competitor", "slot": "c1" }, "stat": "soccer.goals", "period": "full", "estimate": "mean", "value": 2.2 },
    { "subject": { "kind": "competitor", "slot": "c1" }, "stat": "soccer.goals", "period": "full", "estimate": "mode", "value": 2 },
    { "subject": { "kind": "game" }, "stat": "soccer.goals", "period": "full", "estimate": "mean", "value": 3.0 }
  ],
  "is_top_pick": true
}
```

Projections carry a `checkpoint` (`pre_24m`, `pre_6h`, `pre_2h`; values not yet confirmed), the field the Schema Specification plans for `game_prediction`. The document holds the latest checkpoint; every checkpoint stays in Delta, and a pick's `entry.projection` names the `run_id` and `checkpoint` it was selected on.

### Pick (both picks documents)

```json
{
  "pick_id": "nba:40021717862:spread:full:-:-:c1:-4.5|us|1",
  "selection_key": "nba:40021717862:spread:full:-:-:c1:-4.5",
  "region": "us",
  "market": "spread", "period": "full", "variant": "main",
  "player_sk": null, "stat": null,
  "outcome": "c1", "competitor_sk": 40000002, "line": -4.5,
  "issued_at": "2026-10-22T18:05:12.341Z",
  "entry": {
    "price": { "native": { "format": "american", "value": -110 },
               "decimal": 1.909091, "american": -110, "implied_probability": 0.52381 },
    "source": { "kind": "bookmaker", "venue": "draftkings" },
    "outcome_probs": { "won": 0.556, "half_won": 0, "push": 0, "half_lost": 0, "lost": 0.444 },
    "model_probability": 0.571, "probability": 0.556,
    "edge_prob": 0.03219, "ev": 0.061455, "selection_rule": { "metric": "edge_prob", "threshold": 0.03 }, "stake_units": 2.0,
    "projection": { "stat": "basketball.score_margin", "estimate": "mean", "value": 9.5,
                    "checkpoint": "pre_6h", "run_id": "ml_inference|2026-10-22T18:00:00Z" }
  },
  "current": {
    "observed_at": "2026-10-23T14:00:00.000Z",
    "price": { "native": { "format": "american", "value": -105 },
               "decimal": 1.952381, "american": -105, "implied_probability": 0.512195 },
    "line": -4.5,
    "source": { "kind": "bookmaker", "venue": "draftkings" },
    "edge_prob": 0.043805, "ev": 0.085524, "edge_state": "live", "is_closing": false
  },
  "status": "open", "status_reason": null,
  "result": null, "settlement_fraction": null, "settled_at": null,
  "action": null,
  "legacy_ids": ["40021717862|spread_t1|t1|-4.5|main|full|us"]
}
```

Every number above was computed from the native price, not typed: −110 American is 1.909091 decimal and 0.523810 implied; `edge_prob` 0.556 − 0.523810 = 0.032190; `ev` 0.556 × 1.909091 − 1 = 0.061455. Multiplying the rounded fields (1.909091 × 0.032190) gives 0.061454, one unit off in the 6th decimal, so the validator recomputes from `native` rather than checking fields against each other. `probability` is the value the pick was selected on (the NBA engine smooths it toward the market); `model_probability` is the raw model output.

Rules that apply to every document:

- **Types:** numbers are JSON numbers (surrogate keys included), times ISO 8601 UTC with milliseconds, enums lowercase snake\_case (injury statuses too: `day_to_day`, `out_for_season`), every field present (`null` = unknown, `[]` = none).
- **Prices:** `native` is the venue's quote exactly as given (American, decimal, fractional, or a 0–1 probability price for exchanges and prediction markets) and is the authority. `decimal`, `american` and `implied_probability` are derived from it once, decimal and probability at 6 dp, and stored so no consumer recomputes them. 4 dp is not enough: it loses American prices beyond −1000 (§Validation).
- **Edge and EV come from the outcome split, both as fractions.** `entry.outcome_probs` gives the probability of each result and sums to 1; results that cannot happen are 0. `ev` is the expected return per unit staked, and `edge_prob` is the probability edge on the stake that stays in action (formulas below). With no push or half results they reduce to p × d − 1 and p − 1/d. `probability` is A/B, which equals P(won) when the line cannot push. Which one the card labels "Edge" is v4's D3.
- **Region is the audience, not the market.** NBA 2026 launches with US-only odds mirrored into AU; each AU pick says which venue priced it in `entry.source`, so the card can show "DraftKings" or "Avg. Odds" honestly. The selection, and its grade, are the same in both regions.
- **No names:** teams, players and venues are keys; the BFF joins reference data. **No display strings, no parseable codes.**
- **`current`** is written by the Publish Engine from the edge monitor's history table, never by the monitor (Edge Picks v4 §8.3).

```latex
\begin{aligned}
A &= P_{won} + \tfrac{1}{2}P_{half\_won} \qquad B = A + \tfrac{1}{2}P_{half\_lost} + P_{lost} \\
ev &= d \cdot A - B \qquad edge\_prob = \frac{A}{B} - \frac{1}{d} \qquad d^{*}_{break\text{-}even} = \frac{B}{A}
\end{aligned}
```

B is the share of the stake in action, and ev = B × d × edge\_prob. A whole-number total shows why the split matters: over 2.0 goals at 1.80, with P(3+) = 0.47 and P(exactly 2) = 0.25, has `ev` 0.096 and `edge_prob` 0.071111 (break-even 1.595745); p × d − 1 would say −0.154. The same holds for whole-number spreads and totals in every sport (NFL −3, NBA 220).

**One library, exact recompute.** The `xo-contracts` library derives `decimal`, `implied_probability`, `edge_prob` and `ev` from `native` and `outcome_probs` in decimal arithmetic, rounding once at 6 dp. Gate 1 recomputes them and requires an exact match. The identity ev = B × d × edge\_prob is only a cross-check, within 1e-6 × (1 + d), because rounding each field separately breaks exact equality (§Validation).

## Identity

Two keys, two jobs: `selection_key` names the contract and drives settlement; `pick_id` names XO's recommendation and drives My Picks, overlays and the audit trail. Neither changes when a price or line moves.

| Key | Format | Example | Changes when |
| --- | --- | --- | --- |
| `event_sk` | Existing numeric game key | `40021717862` | Never |
| `competitor_sk` | Team, player or pair key from reference data | `40000002` | Never |
| `selection_key` | `{league}:{event_sk}:{market}:{period}:{subject}:{stat}:{outcome}:{line}`; `-` where not applicable | `nba:40021717862:spread:full:-:-:c1:-4.5` | Never; a different line is a different selection |
| `pick_id` | `{selection_key}\|{region}\|{seq}` | `…:c1:-4.5\|us\|1` | Never; `seq` increments only if the same selection is recommended again after a cancellation |
| `overlay_key` | Opaque: base32 of HMAC-SHA256(secret, `pick_id`), 26 characters | `k7q2m…` | Rotates with the secret; issued only to users entitled to the pick (Edge Picks v4 D6) |
| `position_id` | UUID minted by the BFF when a user adds a selection to a slip | `9f1c…` | Never (§Positions) |

Field encoding inside `selection_key`: two-sided outcomes are slots (`c1`, `c2`, `draw`, `over`…); an N-way outcome or subject is `k{competitor_sk}`; a player subject is `p{player_sk}`. A golf winner selection reads `pga:7001234:winner:full:-:-:k3301:-`.

**Exception to the NBA 2026 erratum on `subject_sk`.** The 16 Sep erratum renamed the pick's `subject_sk` to `player_sk`: in NBA 2026 the entity is always a player, so the generic name only forced a translation at every boundary. v3 keeps that rule in documents. A pick carries typed fields (`player_sk` for props, `competitor_sk` for sides and N-way outcomes), and a future team-subject market adds its own typed field, as the erratum allows. The generic form appears only where several entity kinds share one shape: the `selection_key` token (`p{player_sk}`, `k{competitor_sk}`), the position ledger, and projection rows, whose `subject` is a kind-tagged object rather than a bare id. A market's `subject:` in the registry is metadata, not a document field.

### Rules

- **The engine mints both keys once, from structured fields.** The PE re-derives each key from the pick's own fields and rejects a mismatch; nobody re-mints.
- **A key parses back to its fields, exactly.** `selection_key` always splits into 8 fields on `:`; `format(parse(key)) == key` and `parse(format(fields)) == fields` are CI tests in every generated library. This is why registry keys may not contain `:` or `|`.
- **Lines have one spelling.** Round half away from zero to 2 dp, drop trailing zeros and a trailing `.`, write `-0` as `0`: `24.50` → `24.5`, `220.0` → `220`, `-0.25` → `-0.25`. Language defaults are not used: Python's `Decimal.normalize()` writes `2.2E+2` and JavaScript's `String(0.1 + 0.2)` writes `0.30000000000000004`.
- **`variant` is not identity.** Main and alternate at the same line are the same contract; the line already separates them. `variant` stays an attribute for display and analysis.
- **A line move never deletes a pick.** The pick keeps its id and frozen entry; its next observation carries the new line and `edge_state: closed`. If the engine still likes the market, it issues a new pick on the new selection. Both cards exist; product decides whether the closed one is shown.
- **XO's grade is per selection, not per region.** AU and US picks on the same line share one grade; different lines are different selections. This removes the regional collision in Bet Types spec §5.2. A user's position is graded separately, by its venue (§Positions).
- **Keys are never used raw as database paths.** `:`, `|` and `.` are legal in ids; realtime nodes use `overlay_key`, URLs encode ids. Edge Picks v4's ban on `.` (AC-25) should move from `id` to `overlay_key`.
- **Migration:** each pick carries `legacy_ids[]` (the NBA 2026 id and the Format A id) until saved My Picks slips are rewritten, then the field is removed in a major version.

## Lifecycle and settlement

Producers publish the same five statuses the Edge Picks v4 card shows, so the BFF's mapping table (v4 §5.1) shrinks to a pass-through. This settles D5 by adopting the app's vocabulary at the source.

&#91;embedded content: pick lifecycle · 5 states\]

- **Statuses:** `open`, `awaiting_result`, `cancelled`, `settled`, `void`. A pick published in error becomes `withdrawn` and is never served or counted.
- **Reasons** (only on `cancelled` and `void`): `probability_moved`, `market_moved`, `line_moved`, `lineup_change`, `book_pulled`, `game_void`, `competitor_withdrawn`. Copy for each is a registry message.
- **Results:** `won`, `lost`, `push`, `void`, `half_won`, `half_lost`, plus `settlement_fraction` (0–1, null unless a dead heat applies) for multi-competitor markets: a top-10 bet tied for 10th with two others settles `won` at fraction 1/3. The half results exist only where a profile allows quarter lines; EPL filters them out today (`filter_quarter_ball`).
- **Corrections are new facts.** A result changed after `final` (a post-race penalty, a scoring correction) is a new `event_result` version; whether picks re-grade follows the profile's `correction_policy` (most books settle on the first official result).
- **Event status** (on `event` and `event_result`): `scheduled`, `live`, `delayed`, `interrupted`, `final`, `postponed`, `cancelled`, `abandoned`. Pick status and event status never share values.
- **Two gradings.** This section grades XO's picks for the track record and ROI, at entry price, on the profile's rules. Users' positions settle on their venue's rules and fills (§Positions) and are never back-filled from the pick grade.

Entry and observation formalise what the [Bet Engine Output Contracts — Cross-Sport Comparison](https://xosports.atlassian.net/wiki/pages/viewpage.action?pageId=725123074) (v4, 18 Sep) already proposes from the live tst tables. Its `bet_entry_price` and `bet_entry_ts` become `entry`, and its history table becomes the observation stream. Its keep-and-re-price `held` is an `open` pick whose price moved on the same line. A line move is different: the old pick's edge closes, and any new pick sits on the new selection (§Identity). Its assumption of one pick per game per region is not carried over, because that rule is under review.

### Settlement basis comes from the sport profile

| Sport | `h2h` | Settles on | `h2h` tie | Player prop, player inactive |
| --- | --- | --- | --- | --- |
| Basketball (NBA, WNBA) | Two-way | Full game incl. overtime | Not possible | Void |
| American football (NFL) | Two-way | Full game incl. overtime | Push | Void |
| Baseball (MLB) | Two-way | Full game incl. extra innings | Not possible | Void; pitcher props void if he does not start |
| Soccer (EPL) | Three-way | 90 minutes + stoppage; extra time and penalties excluded | Draw is an outcome | Void |

The settlement job reads the basis from the registry; none of these rules is coded per league. The rows are proposed defaults: each sport owner confirms them against the books XO prices from before the registry is frozen.

## Sport profiles

A profile is everything that differs by sport, declared once and read by every layer: the engines validate against it, the BFF renders from it, and the app's `isEpl`, `isNba` and `isNfl` branches become profile lookups. Four profiles cover the five live leagues; WNBA reuses basketball.

```yaml
# sports/soccer.yaml
sport: soccer
leagues: [epl]                     # laliga, seriea, bundesliga, ligue1, ucl: add here
competitors: { kind: team, count: 2 }   # slots c1, c2
periods: [full, h1, h2]
correction_policy: first_official_result
markets:
  h2h: { ways: three_way, settles_on: regulation }
  spread: { quarter_lines: false }  # true requires half_won / half_lost settlement
  total: {}
  btts: {}
score_stat: soccer.goals
roster:
  groups: [goalkeepers, defenders, midfielders, forwards, substitutes]
  order: formation_slot
  lineup: confirmed_before_kickoff
features: [draw_probability, expected_goals, lineup_tabs, formation]
format:
  team_score: { mean: { decimals: 1, label: unit.goals_xg }, mode: { decimals: 0 } }
  margin: { decimals: 1 }
  total: { decimals: 1, keep_integers: true }
  spread_label: { unit: none }      # "Everton -1.5", no unit
```

| Profile | Leagues | Roster groups | Order | Lineup | `h2h` | Features | Decimals: margin / total / player |
| --- | --- | --- | --- | --- | --- | --- | --- |
| basketball | NBA, WNBA | none (position from reference data) | projected points | none | two-way | team-name column | 0 / 0 / 2 |
| baseball | MLB | pitchers, batters | batting order | projected | two-way | extra players | 0 / 1 / 2 |
| football | NFL | quarterbacks, running backs, wide receivers, tight ends | receiving order | none | two-way, ties push | ties | 0 / 1 / 1 |
| soccer | EPL | goalkeepers, defenders, midfielders, forwards, substitutes | formation slot | confirmed | three-way | draw, xG, lineup tabs, formation | 1 / 1 / 1 |

Decimals follow today's BFF rules where they exist; the MLB total and the NFL total and player values are raw today, so 1 dp is a proposal for product to confirm.

Adding a league in an existing sport (LaLiga, UCL) is one line in `leagues` plus its teams in reference data. A new sport (ice hockey for NHL) is a new profile and its stats file; neither touches a document schema.

### Stress test: tennis, F1, golf

None of these is planned; they test whether the model is general. With competitors, the reserved markets and settlement fractions in v3, all three are profile work. Without them, all three would need new document shapes.

| Need | Tennis | F1 | Golf | Where v3 handles it |
| --- | --- | --- | --- | --- |
| Competitors are people or pairs | Players, doubles pairs | Drivers; constructors as a second kind | Players | `competitors[].kind` |
| More than two competitors | — | 20 | About 150 | `winner`, `finish_position`, `matchup` markets; outcome `k{competitor_sk}` |
| Event hierarchy | Match within a tournament draw | Season, weekend, session (practice, qualifying, sprint, race) | Tournament, round | `parent_event` + `stage`; periods are profile-defined segments (`set_1`, `round_2`, `session_qualifying`) |
| Outcome kinds | Exact set score (2–1) | Top 3/6/10, head-to-heads inside the field | Top 5/10/20, 2- and 3-balls, make or miss the cut | `at_most`, `matchup`, `player_event`; exact score is the one reserved addition (`exact_score`) |
| Settlement | Retirement: void or advance, varies by book | Post-race penalties, DNF | Dead heats split the stake; withdrawal before tee-off voids | `settlement_fraction`, `correction_policy`, `competitor_withdrawn` |
| Results | Sets and games | Finishing order and status | Position, score to par, cut | `event_result.results[]`: score, placing, status |
| Projections | Win probability, games, aces | Finish-position distribution | Finish-position distribution, round scores | `outcome_probabilities` (one row per competitor) and `projections` |

Two things v3 still lacks and would add only when such a sport is real: **each-way bets** (a win leg plus a place leg with place terms) and **in-play across days** (a golf round suspended overnight). Both are additive.

## Validation and governance

One repository (`xo-contracts`) holds the registry and the seven document schemas, and generates each layer's native validator; no team hand-writes a schema again.

| Generated artefact | Used by | Replaces |
| --- | --- | --- |
| Spark `StructType` + a row validator | Bet engines and inference, before writing Delta | Hand-written `_schemas.py` in five engines |
| JSON Schema 2020-12 per document | Publish Engine CI and runtime | NBA pick schema in the spec; nothing for Format A |
| TypeScript types + runtime validators | BFF | Hand-written parsers per league |
| App config (leagues, features, colours, crests, sections) | Mobile app build | \~14 hand-edited registries |
| Golden fixtures: documents + expected rendered copy, per league | BFF and app tests | Hand-made seeds |

### Gates

| # | Layer | Checks | On failure |
| --- | --- | --- | --- |
| 1 | Engine output | Shape; every key in the registry; stat eligible for the role and market; line rules and spelling; keys re-derive and round-trip; derived prices match `native`; `edge_prob` and `ev` match their formulas and `ev = d × edge_prob`, at 6 dp | Row to a quarantine table, never published; job alerts |
| 2 | Publish Engine | Document schema; header equality across an event's documents; `current` only from monitor history | Document held back; alert |
| 3 | BFF CI | Contract tests on golden fixtures for every league; rendered copy equals expected | Merge blocked |
| 4 | BFF runtime | Each pick validated on read | Pick dropped and alerted; never a default unit |
| 5 | App CI | Generated types and config compile; rendered-copy snapshots | Build fails |
| 6 | Registry CI | Unique keys; alias `remove_after` not passed; every message id in every locale; every profile market and stat exists | Merge blocked |

Gate 1 is the only one that prevents bad data; gates 2–5 detect it. It must be a required check in every engine repository; without it, bad data still reaches Cosmos and the other gates only report it.

It is needed today, not in theory. The NBA engine's own output schema (`nba_bet_engine/src/bet_engine/_schemas.py`, local checkout) matches neither Confluence page: player picks nest under `picks[].items[]`; `bookmaker` and `bet_odds` are arrays with no `bookmaker_id`, `bet_price` or `stake_units`; game picks store American odds as a float and mint `bet_code`, which the spec assigns to the Publish Engine; and there is no region map. The Publish Engine absorbs every difference silently. Generated schemas remove the layer where that drift lives.

### Versioning and change control

- **Schemas:** `name/major.minor` per document. A new optional field is a minor; anything else is a major, shipped readers-first.
- **Registry:** semver. A new stat, market, unit or message is a minor and is released before any producer emits it. Consumers show a neutral fallback for an unknown value (Edge Picks v4 §4.4).
- **Ownership:** platform owns schemas and generators; each sport owner owns its profile and stats; product owns `messages/` and approves every user-visible string by PR review. That review replaces the market-mapping spreadsheets of XOD-349 and XOD-477.
- **Change path:** registry PR → product and sport-owner review → CI → release → consumers upgrade → producers may emit.

### Round-trip checks (run 16 Oct, become CI tests)

The derivations below were run over the ranges shown, in Python decimal arithmetic; the failures changed the design above. Anything not listed here was not tested.

| Check | Range | Result | Consequence |
| --- | --- | --- | --- |
| Decimal → American → decimal | Every 2 dp price, 1.01–10.00 | 900 of 900 pass | Decimal-native quotes are safe |
| American → decimal (4 dp) → American | ±100 to ±10,000 | 8,100 fail, all at −1023 or shorter; 0 fail within ±1000; 0 fail at 6 dp | Store `native`; derive at 6 dp, not 4 |
| Probability price → decimal → probability | 0.01–0.99 in 0.01 ticks | 99 of 99 pass, directly and via American | Exchange and prediction-market quotes fit `native` |
| Edge Picks v4 worked examples | E1–E11, D-1–D-10 | All reproduce: b 1.8181 (−122), m 1.9091 (−110), E10 b 1.8545, payout $37.39 | v4's precision rules hold |
| `ev = decimal × edge_prob` on the rounded fields | 100,000 random binary picks: American −2,000 to −101 and +100 to +2,000, decimal 1.01–20.00, p 0.01–0.99 | Exact equality fails in 68.9% (the reviewer reports 78% on their sample); the pick example itself gives 0.061454 vs 0.061455. Within 1e-6 × (1 + d): 0 fail | Gate 1 recomputes from `native`; the identity is a tolerance check only |
| `ev = B × d × edge_prob` with push and half results | 100,000 random five-way outcome splits, American −2,000 to +10,000 | The payoff sum equals d × A − B exactly; within 1e-6 × (1 + d): 0 fail | One formula covers whole, half and quarter lines |
| Push-aware vs naive EV | Over 2.0, 2.25 and 2.5 at 1.80 with P(3+) 0.47 and P(2) 0.25; NFL −3 at −110 with P(win) 0.50, P(push) 0.09 | Over 2.0: `ev` 0.096 vs naive −0.154; over 2.25: −0.029; over 2.5: −0.154 both ways; NFL −3: 0.044545 vs naive −0.045455 | `outcome_probs` is required on every pick |
| Engine edge vs v4 edge | NBA `_ps_engine.py:275`; NFL `_wltp_engine.py:280–281, 491`; EPL `_wltp_engine.py`, `_probability.py` | NBA computes p − 1/d. NFL's `edge` is p / implied − 1, which is EV. EPL publishes both, with push-adjusted EV on totals in its newer revision (`_probability.py:428–455` per the reviewer) | Two named fields; NFL `edge` migrates to `ev`, NBA's to `edge_prob` |
| `selection_key` format ↔ parse | Spread, threshold, draw, quarter line | Pass; fails if any field contains `:` | Key charset `[a-z0-9_.]` |
| Line spelling | 11 values incl. 220, −0.0, 0.1 + 0.2 | Language defaults disagree (`2.2E+2`, `0.30000000000000004`) | One explicit algorithm (§Identity) |

Not yet checked, because no implementation exists: settlement fractions against books' dead-heat rules, and venue fee models against real Betfair and Kalshi statements. Engine line numbers here come from local dev checkouts; the EPL one is from 27 Aug 2026 and older than the revision the reviewer read, which is why its numbers differ (213–214 here, 250–251 there). Every code citation from now on pins a commit SHA.

## Positions and venue accounting

XO hands users off to Betfair, Kalshi, Polymarket or a sportsbook; it never holds funds or places bets. So the record must keep three things apart: what the user intended (XO knows), what was executed (only the venue knows) and how it settled (the venue decides).

| Entity | Holds | Owner | Store |
| --- | --- | --- | --- |
| `venue` | Kind (sportsbook, exchange, prediction market), native price format, fee model, settlement rules, jurisdictions, deep-link template, affiliate id | Data engineering, legal | Registry (`venues.yaml`) |
| `venue_listing` | `selection_key` → the venue's instrument (Betfair market + selection + handicap; Kalshi ticker + yes/no; Polymarket token), equivalence (`exact`, `equivalent`, `proxy`), the venue's rule reference, valid from/to | New mapping service, published by PE | One document per event |
| `position` | `position_id`, user, slip, `pick_id` (null if not an XO pick), `selection_key`, venue and listing, side (`back`, `lay`, `yes`, `no`), the quote the user saw (native price, `observed_at`, source), intended stake and currency, current state | BFF | User data store (successor to My Picks) |
| `position_event` | Append-only: type, time, source (`user`, `venue_api`, `on_chain`, `system`), payload (fill price and size, fee, payout), venue reference as idempotency key | BFF | Same store; never updated |

&#91;embedded content: position lifecycle · 7 states\]

Rules:

- **Append-only ledger.** A position's state is the fold of its events. Corrections (a disputed Polymarket resolution, a Betfair resettlement) are new events; nothing is edited.
- **Every execution fact carries its confirmation level:** `user_reported` < `venue_api` < `on_chain`. Only verified levels count in a user's P&L or in XO-facing analytics; a handoff alone proves nothing was placed.
- **Money is integers.** Amounts in minor units with a currency; fees and commission are their own events. Betfair commission applies to net winnings per market, so it is computed at market settlement, not per bet.
- **Exchange and prediction-market sides.** `lay` carries a liability; a prediction-market position is a quantity of contracts at a 0–1 price and may exit before resolution (`exited`). Partial fills are separate fill events.
- **The venue result is authoritative for the position.** It is never back-filled from XO's grade. A reconciliation job compares the two and flags divergence (XO graded `won`, venue voided).
- **Equivalence is shown, not hidden.** A `proxy` listing (the venue's contract resolves differently, e.g. regulation time only) is labelled for the user and excluded from XO's track record.
- **Jurisdiction and attribution at handoff.** The BFF checks the venue's jurisdictions from the registry before showing a link, and records the affiliate id on the `handed_off` event.

This is user data owned by the BFF, not something the Publish Engine writes, so it deserves its own spec; it depends on v3 only through `selection_key`, `pick_id` and `venue_listing`.

## Migration plan

Ship Phase 1A on the NBA 2026 documents unchanged except for additive fields, and move leagues to v3 in season order: off-season leagues first, in-season leagues only after a dual-publish proves the shape.

&#91;embedded content: migration roadmap · 4 phases, 3 gates\]

1. **Decide (by 23 Oct).** Agree the four contested points as one change to this proposal and to Edge Picks v4: identity (§Identity), edge as a fraction, the status vocabulary (closes D5 by 21 Oct) and entry/current. Draft registry v1.0 for the five leagues from the coverage table.
2. **Phase 1A (31 Oct).** Add `picked_at`, the `entry` block and `observed_at` to NBA 2026 picks as optional fields. No v3 dependency, so 1A is not put at risk.
3. **Phase 1B (1 Dec).** WNBA and MLB publish v3 only; both are off-season, so the shape is tested on replayed games with no live users. NBA publishes v3 beside NBA 2026; the BFF reads v3 behind a per-league flag and compares rendered output against the legacy path.
4. **Phase 2 (Dec–Jan).** NFL and EPL dual-publish, then each league cuts over through the existing release gate once its golden diffs are clean for a week. Legacy documents become read-only; the BFF reads them through adapters until then (Edge Picks v4 §8.1 allows this).

Two compatibility rules hold throughout:

- **My Picks:** slips keep resolving through `legacy_ids[]`; a one-off job rewrites saved ids to v3 `pick_id`s before the field is dropped.
- **App contract:** `/v4/edge-picks` does not change shape; only its source documents change. The app never sees v3 directly.

This puts NFL and EPL about a month after v4's 1 Dec target for "one schema for all sports". The alternative, migrating two in-season leagues and NBA in November, risks the live product for a deadline the BFF adapters already cover.

### Changes to request in Edge Picks v4

Every v4 `EdgePick` field has a v3 source; these six v4 rules need to change, along with R1–R4 and R6 in Conflict resolutions.

| v4 rule | Change | Why |
| --- | --- | --- |
| §8.2 pick id has no line | Use v3 `pick_id`; amend the 4.0.0 draft before build rather than waiting for a v5 | R1 needs line-aware ids; saved My Picks resolve through `legacy_ids[]` (R4) |
| AC-25: ids contain no `.` | Apply it to `overlay_key` only | v3 ids carry lines (`-4.5`); the opaque key is what reaches the realtime database |
| §4.2 `side` has no milestone | Add `at_least` and show the integer line ("3+ Threes") | NBA 2026 already defines milestone picks |
| §4.2 `result` | Add `half_won`, `half_lost` | Needed only if quarter lines are enabled |
| §6.1 edge = p × d − 1 | Name it `ev`; carry `edge_prob` too; both from `outcome_probs` (§Pick); D3 picks the label | Engines disagree (NBA p − 1/d, NFL EV), and p × d − 1 is wrong on any line that can push |
| §4.2 `model.probability` | Define it as the probability the pick was selected on; expose `model_probability` separately if wanted | The NBA engine smooths toward the market |

## Conflict resolutions

NBA 2026, Edge Picks v4 and this proposal disagree on 22 points; each has one proposed answer below. The rule used: v4 decides what users see, v3 decides what producers publish, and NBA 2026 changes only where it blocks either. Owners sign off in Open decisions.

### R1. A line moves before the game

NBA 2026 drops the old pick ("absent, never cancelled"); v4 keeps the card and shows Market Movement. **Resolution: the pick stays `open` with its entry frozen; its observation carries the new line and `edge_state: closed`. The engine may issue a second pick on the new selection. NBA 2026's freeze after tip-off is kept.**

| Time | Event | Pick A (−4.5) | Pick B (−1.5) |
| --- | --- | --- | --- |
| 09:00 | Engine recommends Celtics −4.5 @ 1.90 | `open`, entry −4.5 @ 1.90 | — |
| 14:00 | Line moves to −1.5 | `open`; current line −1.5, `edge_state: closed` | Engine may issue it, own entry |
| 23:00 | Tip-off; pick set frozen | `awaiting_result` | `awaiting_result` |
| Final | Celtics win by 2 | `lost` (did not cover 4.5) | `won` |

Why this beats deletion: a user who saved A sees `lost`, which is true (the Bet Types spec's failure mode 1, fixed without deleting anything). And a line usually moves because the market agrees or disagrees with the pick, so deleting superseded picks removes exactly the ones that say most about the model; the track record would be biased.

No cap on picks per game or market is assumed. The legacy one-game-pick-per-game rule is a temporary business rule under review; if any cap survives, it lives in the Bet Engine's selection config (for example `max_open_picks_per_market`, counting open picks only), never in a schema.

### R2. Which edge, and which threshold

The engines mean three things by `edge`. NBA 2026 publishes probability − implied probability in percentage points; NFL's `edge` is p / implied − 1, which is EV (`_wltp_engine.py:491`, "`edge` IS the EV in NFL"); EPL publishes both, with push-adjusted EV on totals in its newer revision. v4 defines edge as p × d − 1 with an EV threshold t. **Resolution: publish both as fractions (`edge_prob`, `ev`), derived from `outcome_probs` and the native price (§Pick), plus each engine's actual selection rule: `{ metric: edge_prob, threshold: 0.03 }` for NBA, `{ metric: ev, … }` for NFL. "Edge holds above" is computed from that rule. The card's "Edge" shows `ev`, the expected return on $1 (product confirms, D3).**

The threshold metric matters: at t = 0 both give the same break-even price, above it they do not. With p = 0.55:

| Threshold t | Break-even if t is on `ev`: (1 + t) / p | Break-even if t is on `edge_prob`: 1 / (p − t) |
| --- | --- | --- |
| 0 | 1.8181 | 1.8181 |
| 0.02 | 1.8545 | 1.8867 |
| 0.03 | 1.8727 | 1.9230 |

v4's `(1 + t) / p` would show the wrong "edge holds above" price for an engine that selects on probability edge, as NBA does today. Both forms round down to 4 dp and pass the same boundary test as v4 E8/E11 (at 1.9230, `edge_prob` = 0.02998 < 0.03; at 1.9231 it is 0.03001).

On a line that can push, the same two rules use A and B from §Pick: break-even is (B + t) / A on `ev` and 1 / (A/B − t) on `edge_prob`. Both reduce to the table's formulas when B = 1.

### R3. One status vocabulary (closes D5)

**Resolution: producers publish the five v4 statuses plus `withdrawn`; results are separate.** The mapping below is for readers of documents published before the switch, and is the only mapping any system keeps.

| Value published today | v3 `status` | v3 `result` |
| --- | --- | --- |
| `scheduled`, `active`, `rescheduled`, NFL `Scheduled` | `open`; `awaiting_result` after the start | `null` |
| `pending`, `expired` | `awaiting_result` | `null` |
| `won`, `lost`, `push` | `settled` | same value |
| `settled` with outcome 1 / 0 / 2-push | `settled` | `won` / `lost` / `push` |
| `void`, `abandoned` | `void` | `void` |
| Game postponed or cancelled (NBA 2026 marks some `cancelled`) | `void`, reason `game_void` | `void` |
| `cancelled` (engine withdrew before the start) | `cancelled` | `null` |
| `removed` | `withdrawn` (never served) | — |

The edge monitor's filter becomes a case-insensitive match on `open` in the same release (v4 X1).

### R4–R22

| # | Topic | NBA 2026 | Edge Picks v4 | Resolution | Spec to change |
| --- | --- | --- | --- | --- | --- |
| R4 | Pick id | `{game_sk}\|{type}\|{selection}\|{line}\|{variant}\|{period}\|{region}` | Legacy `{game_sk}_{bet_type}_{region}`, frozen through Phase 2 | v3 `{selection_key}\|{region}\|{seq}`. v4 is still a 4.0.0 draft, so §8.2 is amended before build, not bumped to v5. My Picks: the BFF resolves saved ids through `legacy_ids[]` (both old formats), one job rewrites stored slips, and the field is removed in the next major version | v4 §8.2; NBA Schema §4.2 |
| R5 | `.` in ids | Allowed | Banned (AC-25) | Allowed; `overlay_key` is opaque | v4 AC-25 moves to `overlay_key` |
| R6 | Market and side names | `h2h`, `t1`/`t2` | `moneyline`, `home`/`away`, draw as a market | Producers publish v3 names; the app contract keeps v4's; the BFF maps through `venue_role`, which the PE takes from the schedule (`dim_all_games`, `team_1` = home), `neutral` where there is no home side | v4 §8.3 cites v3 enums |
| R7 | Milestones | `selection: milestone` + `threshold_k` | No milestone side | Outcome `at_least` with an integer `line`; v4 adds side `at_least` | v4 §4.2 |
| R8 | Outcome encoding | `bet_outcome` 1/0/2 + `pick_status` | `result` enum | `result` + `settlement_fraction`; `bet_outcome` only in legacy documents | NBA Schema §5 |
| R9 | `player_sk` type | Number (Schema) vs string (Bet Types) | String id | Number | Bet Types §4.1, §4.4 |
| R10 | `model_win_prediction` | Optional pick field (Bet Types) | — | Dropped; derive from projections | Bet Types §4.2 |
| R11 | Meaning of `probability` | "Model win probability" (the NBA engine smooths it) | `model.probability` | `probability` = value the pick was selected on; `model_probability` = raw; v4 maps `probability` | Both |
| R12 | Price time | `market_last_update` | `observed_at` | `entry.observed_at`, `current.observed_at` | NBA Schema §3 |
| R13 | Stake | `stake_units` + alias `bet_stake` | `stake_units` | `entry.stake_units` only | NBA Schema §3 |
| R14 | Region | US prices mirrored into AU | AU shows "Avg. Odds" and "Win" | Region = audience; `source` names the venue; BFF applies v4 AC-7 | None |
| R15 | `bookmaker_options` | `[]` at launch | A book per price | Dropped; other books' prices become observations | NBA Schema §3 |
| R16 | `code`, `bet_line`, `position` | Required | Not used | Not in v3; PE writes them into legacy documents only | NBA Schema §3 |
| R17 | Event status casing | `schedule` lowercase, `outcome` capitalised | `game.state` | One lowercase list (§Lifecycle) | NBA Schema §5.1 |
| R18 | Featured game | `predictions.is_top_pick` | — | Keep the name `is_top_pick` on `game_projections` | This proposal |
| R19 | After the start | Id set frozen | Cutoff (D13) | Kept: no new picks after the start; only status and result change | None |
| R20 | Bookmaker block shape | Three shapes: Bet Types §4.3.1 object (bet\_price + bet\_odds object), §6.2 examples (flat decimal\_odds), engine output (bookmaker and bet\_odds as arrays, no bookmaker\_id or stake\_units) | entry.source + entry.price | NBA 2026: §4.3.1 is the only shape (the BFF reads bookmaker.bet\_price), §6.2 fixed, PE contract test against BFF fixtures. v3: the engine writes the v3 pick shape itself | Bet Types §4.3.1, §6.2; Schema §2.5, §2.7 |
| R21 | taxonomy\_version on each pick | Required (Bet Types §4.2) vs optional override (Schema §3) | — | Document-level only. Optional per pick in NBA 2026 and readers ignore it; dropped in v3 | Bet Types §4.2 |
| R22 | bookmaker\_options empty value | \[\] and never null (Schema §1) vs array or null (Bet Types §4.4) | A book per price | Always \[\]; dropped in v3, where other books' prices are observations per venue | Bet Types §4.2, §4.3.2, §4.4 |

## Review response

A review on 16 Oct found two blockers, the pricing identity and push-adjusted EV, and nine smaller errors. All are fixed above; the core model is unchanged.

| Finding | Verdict | Change |
| --- | --- | --- |
| `ev = d × edge_prob` fails at 6 dp | Right: 68.9% of my binary samples, and the pick example | Gate 1 recomputes from `native`; the identity is a tolerance check (§Pick, §Validation) |
| Push-adjusted EV (EPL totals) missing | Right, and it applies to every whole-number spread and total | `outcome_probs` on every pick; one formula for whole, half and quarter lines |
| NFL `edge` is EV | Right; "every engine computes p − 1/d" was false | R2 and §Validation corrected; NFL `edge` maps to `ev` |
| Generic `subject` reverses the NBA 2026 erratum | Right that it was not acknowledged | Written exception: typed fields in documents, the generic form only in keys, the ledger and projection rows (§Identity) |
| `venue_role` has no source | Right as written | Taken from the schedule, `team_1` = home (§Core model, R6) |
| v4 §8.2 is frozen and needs a v5 | Partly: v4 is a 4.0.0 draft, but §8.2 does conflict with R1 | Amend §8.2 before build; My Picks migrate through `legacy_ids[]` (R4) |
| Cross-Sport Comparison not cited | Right; it already proposes entry price, `held` and a history table | Cited; v3 builds on it (§Lifecycle) |
| NFL list omits RuTDs, RecTDs | Right | Added (§Stat coverage) |
| "Every formula round-trip tested" | Overclaim | Reworded; §Validation lists what was tested |
| Cited line numbers do not hold | My EPL checkout was 27 Aug, older than the reviewer's | Code citations will pin commit SHAs |
| Local Bet Types copy diverged from Confluence | Confirmed | V17 names Confluence as the source |

## Open decisions and risks

Seventeen decisions unblock the build; V1–V3 and V9 are on the Phase 1A critical path. V1–V4, V9, V10 and V14 now have proposed answers in Conflict resolutions, so what remains for them is sign-off.

| # | Decision | Recommendation | Owner | Needed by |
| --- | --- | --- | --- | --- |
| V1 | Producer status vocabulary | The five v4 statuses at the source (closes D5) | Bet engine, data engineering, monitor owner | Oct 21, 2026 |
| V2 | Identity model | `selection_key` + `pick_id`; a line move keeps the pick | Bet engine, BFF, app | Oct 23, 2026 |
| V3 | Edge fields | Publish `edge_prob` and `ev` as fractions, derived from `outcome_probs` and `native` by the shared library; D3 picks which the card calls "Edge" | Bet engine, product | Oct 23, 2026 |
| V4 | Show a line-moved pick to users? | Yes, with Market Movement showing the closed edge | Product | Oct 30, 2026 |
| V5 | NFL and EPL on v3 in January, not 1 Dec | Yes; BFF adapters cover the gap | Product, bet engine | Oct 30, 2026 |
| V6 | Stat key style | Sport-qualified slugs; NBA short codes become aliases | Platform, sport owners | Nov 6, 2026 |
| V7 | Schema source and repository | JSON Schema 2020-12 + YAML registry in a new `xo-contracts` repo | Platform | Nov 6, 2026 |
| V8 | Who renders localised copy | BFF renders from `messages/` per locale; app renders verbatim | App, BFF | Nov 6, 2026 |
| V9 | Price authority | Store the venue's `native` quote; derive the rest at 6 dp | Bet engine, data engineering | Oct 23, 2026 |
| V10 | N competitors in v3 now | Yes: `competitors[]`, `c1`/`c2` slots, `t1`/`t2` as aliases | Platform, bet engine | Oct 30, 2026 |
| V11 | Who builds and owns `venue_listing` | A small mapping service owned by data engineering, published by PE | Data engineering, product | Nov 13, 2026 |
| V12 | Position ledger spec and store | Its own spec, owned by the BFF; replaces My Picks storage | App, BFF | Nov 13, 2026 |
| V13 | Which venues launch, and where | Legal names the venues and jurisdictions before any deep link ships | Legal, product | Nov 13, 2026 |
| V14 | Resolve the NBA 2026 specs' contradictions | One revision of both pages covering R9, R10 and R20–R22, two corrected odds examples, and both pages marked frozen until v3. Draft: V14 Confluence edits (draft) | Bet engine, data engineering | Oct 23, 2026 |
| V15 | Rename partition fields (`game_sk` → `event_sk`) | No, until a non-team sport ships; it needs new containers | Data engineering, platform | Nov 13, 2026 |
| V16 | How the card shows a pick that can push | Show win and push separately ("Win 47% · Push 25%"); probability (A/B) drives the ring | Product, design | Oct 30, 2026 |
| V17 | Which copy of Bet Types is the source of truth | Confluence. The repo copy reqs/nba/bet\_types.md has diverged (BIGINT player\_sk, no model\_win\_prediction); regenerate it from Confluence or delete it | Bet engine, data engineering | Oct 21, 2026 |

### Risks

- **Gate 1 left optional.** If engines can publish without the generated validator, drift returns. Make it a required check before v3 goes live anywhere.
- **Book-specific settlement rules.** Books differ on void rules for props and on dead heats; profile defaults may not match every venue. Venue rules live in `venues.yaml` and are applied to positions, never the profile defaults.
- **Venue resolution risk.** Prediction-market resolutions can be disputed and reversed days later; the ledger must accept corrections after `settled`, and user-facing P&L should say when a result is provisional.
- **Unverifiable placement.** A handoff without a venue API or wallet link leaves `placed` as self-reported; any user-facing record or ROI built on it must say so.
- **Dual-publish cost.** Cosmos throughput and PE runtime roughly double per league for about a month; size it before 1B.
- **The NBA 2026 specs are not frozen and disagree.** Checked against Confluence on 16 Oct: the Schema Specification (v6, 23 Sep) is a request for comment and the Bet Types Specification (v5, 16 Sep) is for team review. They contradict each other on `player_sk` (number vs string), and Bet Types publishes `model_win_prediction` where the repo copy keeps it aggregate-only. The repo copy has diverged and is not a source (V17). V14 settles both before any engine builds to either.
- **Live data not yet checked.** Stat lists come from seeds and engine code, not live Cosmos; confirm against production before the registry is frozen.

## Sources

- [NBA 2026 — Schema Specification](https://xosports.atlassian.net/wiki/spaces/PB/pages/717914114/NBA+2026+Schema+Specification) (Confluence v6, 23 Sep 2026; read 16 Oct)
- [NBA 2026: Bet Types Specification](https://xosports.atlassian.net/wiki/spaces/PB/pages/717029379/NBA+2026+Bet+Types+Specification) (Confluence v5, 16 Sep 2026; read 16 Oct)
- [Bet Engine Output Contracts — Cross-Sport Comparison](https://xosports.atlassian.net/wiki/pages/viewpage.action?pageId=725123074) (Confluence v4, 18 Sep 2026; read 16 Oct)
- Local working copies (not authoritative; `bet_types.md` has diverged from Confluence): `reqs/nba/specs/02-schemas-and-examples.md`, `reqs/nba/bet_types.md`, `reqs/nba/nba_proposed_canonical.md`
- NBA 2026 erratum renaming `subject_sk` to `player_sk` (16 Sep): `reqs/nba/nba_schemas_refined.md`, `reqs/nba/specs/README.md`
- Edge Picks v4 contract: `xo-scratchpad/edgepicks-redesign/specs.md`
- Live vocabulary: `mobile-server/script/db-seeds/*.json`; engine configs in `mlb_bet_engine`, `nba_bet_engine`, `nfl_bet_engine`, `wnba_bet_engine`, `epl_bet_engine`
- Engine code cited: NBA `_ps_engine.py`, NFL `_wltp_engine.py`, EPL `_wltp_engine.py` and `_probability.py`, from local dev checkouts (EPL as of 27 Aug 2026); commit SHAs to be pinned
- Display rules today: `mobile-server/src/lib/top-picks/*`, `mobile-app/app/utils/*`
