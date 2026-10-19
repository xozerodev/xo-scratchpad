# Edge Picks v4: Producer Pick Record Schema & Contract Specification

Every Edge Pick is published as one strongly typed record per pick per region, using identical field names, units, and semantics across all sports and across both game picks and player prop picks. Downstream services (the BFF, the live edge monitor, and settlement) consume these records as the single source of truth; no consumer parses free-text descriptions or sport-specific structures to determine what a pick backs, how it is priced, or how it settled.

---

## 1. Document Control & Scope

| Attribute | Value |
| --- | --- |
| **Contract Version** | `4.0.0` |
| **Status** | Draft Specification |
| **Producers** | Sport bet engines (`nba`, `nfl`, `mlb`, `wnba`, `epl`) and the Publish Engine |
| **Consumers** | BFF (builds the app's Edge Picks API responses), Live Edge Monitor (tracks live market prices and edge states for open picks), and Settlement |
| **Contract Owner** | App / Platform Architecture (with sign-off from Bet Engine, Data Engineering, BFF, and Live Edge Monitor teams) |
| **Schema ID** | `https://contracts.xosports.ai/edge-picks/v4/producer-pick.schema.json` |

### 1.1 What a Producer Pick Record Represents
A **producer pick record** represents a single betting recommendation on a specific market selection in a specific region (`"au"` or `"us"`) for a specific game (`game_sk`). It combines:
1. **Frozen entry state:** The exact selection, model probability, optional model projection, entry odds, entry edge, edge basis/threshold, and recommended stake at the moment the pick was first published.
2. **Live market observation state:** The most recent pre-game market price, line, bookmaker source, recalculated edge, and edge status observed after initial publication, culminating in the closing observation (`is_closing = true`) immediately before the game starts.
3. **Lifecycle and grading state:** The pick's current lifecycle state (`pick_status`), optional cancellation/void reason (`status_reason`), and final settlement grade (`outcome`) evaluated against the frozen entry selection and line.

---

## 2. Data & Formatting Conventions

1. **Closed, fixed-key shape:** Every record contains all **37 fields** defined in this specification. No field is ever omitted; `"no value"` or `"not applicable"` is always represented as `null`. Producers must not emit undeclared fields (`"additionalProperties": false`), and consumers must ignore any unknown fields added in future minor (`4.x`) versions.
2. **Naming & casing:** All field names use `snake_case`. All enum values, `sport` codes, `region` codes, `stat_code` values, and bookmaker identifiers (`entry_bookmaker_id`, `current_bookmaker_id`) are lowercase strings.
3. **Numbers:** All numeric values are encoded as JSON numbers, never strings.
   - **Decimal odds** (`entry_decimal_odds`, `current_decimal_odds`) are strictly greater than `1.0` and carry **at most 4 decimal places** (e.g., `1.9091`, `2.0`, `3.6`).
   - **American odds** (`entry_american_odds`, `current_american_odds`) are integers (e.g., `-115`, `100`, `260`).
   - **Probabilities and edges** (`probability`, `entry_edge`, `edge_threshold`, `current_edge`) are expressed as **unitless fractions** (`0.05` for 5%), never percentage points (`5`) or strings (`"5%"`).
4. **Timestamps:** All timestamps (`pick_date_time`, `observed_at`) are UTC ISO 8601 strings with millisecond precision and a trailing `Z` (e.g., `"2026-10-22T18:05:12.341Z"`).
5. **Opaque identifiers:** Consumers treat `pick_id` as an opaque string identifier and never parse it. Producers construct `pick_id` deterministically using the formula in [Section 8](#8-deterministic-pick_id-specification).
6. **Semantic versioning:**
   - **Minor version (`4.x.0`):** Adding a new optional/nullable field or adding a new enum value is a minor version bump. Producers may emit new `4.x` values only after all consumers have deployed support for them.
   - **Major version (`5.0.0`):** Renaming or removing a field, changing a field's type or nullability, or changing a field's semantic meaning requires a major version bump.

---

## 3. Core Producer Rules

Every producer must uphold the following six invariants:

1. **Rule 1 — Deterministic, Region-Scoped Identity (`pick_id`):**
   `pick_id` is constructed using the canonical formula in [Section 8](#8-deterministic-pick_id-specification), making it globally unique across all sports and regions. Recommendations for the same selection in `"au"` and `"us"` are separate records with distinct `pick_id` values (`...|au` vs. `...|us`).
   - `pick_id` **never changes** when the market price or live line moves after publication.
   - If the engine recommends a different entry line (e.g., `-5.5` instead of `-4.5`), that is a separate pick with its own `pick_id`.
   - If the engine re-recommends the exact same selection and entry line in the same region after an earlier pick was `cancelled` or `withdrawn`, the new record receives a re-issue suffix (`|r2`, `|r3`, etc.).
   - `pick_id` is at most 255 characters long and uses only characters from `A–Z`, `a–z`, `0–9`, and `_ . ~ | -`.
2. **Rule 2 — Persistence (No Silent Drops):**
   Once a pick record is published, it must remain present in every subsequent publish until it reaches a terminal state (`settled`, `void`, `cancelled`, or `withdrawn`).
   - If the model or engine stops backing an `open` pick before the game starts, the producer must transition that record to `pick_status = "cancelled"` (with a `status_reason`), **never** delete or omit it.
   - If a pick was published due to a system or data error, the producer transitions it to `pick_status = "withdrawn"`.
   - Re-running a model or pausing/disabling a producer stops new picks from being minted, but must never delete or overwrite already-published picks.
3. **Rule 3 — Frozen Entry State:**
   All identity, selection, model, and entry fields (`pick_id`, `region`, `sport`, `game_sk`, `pick_kind`, `market`, `side`, `line`, `team_sk`, `player_sk`, `stat_code`, `probability`, `projection_value`, `projection_unit`, `pick_date_time`, `entry_decimal_odds`, `entry_american_odds`, `entry_edge`, `edge_basis`, `edge_threshold`, `stake_units`, `odds_source_kind`, and `entry_bookmaker_id`) are **frozen at first publish** and must never change on subsequent updates. Subsequent writes may update only `schema_version`, `current_*` fields, `observed_at`, `is_closing`, `edge_status`, `rec_action`, `pick_status`, `status_reason`, and `outcome`.
4. **Rule 4 — Market Observation Timestamp (`observed_at`):**
   Whenever a record carries a live market observation, `observed_at` records the timestamp when the price (or pulled-price state) was observed at the sportsbook/feed—not the timestamp when the database write occurred.
5. **Rule 5 — Single Coherent Record Stream & Closing Flag:**
   Entry publication, pre-game market observations (delivered within 5 minutes of observation), status transitions, and post-game settlement all update the same logical record without clobbering frozen fields. `is_closing` is `false` while the game has not started and becomes `true` on the final pre-game market observation when the game starts.
6. **Rule 6 — Forward-Only Lifecycle:**
   `pick_status` transitions strictly forward along the lifecycle defined in [Section 4](#4-pick-lifecycle-statuses--grading) (`open` $\to$ `awaiting_result` $\to$ `settled` or `void`; or pre-game `open` $\to$ `cancelled`, `void`, or `withdrawn`). A pick never moves backward to an earlier status. *(Whether a pre-game `cancelled` pick may reopen to `open` is tracked in [Section 11](#11-open-decisions--sign-off)).*

---

## 4. Pick Lifecycle, Statuses & Grading

### 4.1 Lifecycle State Diagram

```mermaid
stateDiagram-v2
    [*] --> open : Pick published (pre-game)
    open --> awaiting_result : Game starts (is_closing = true)
    open --> cancelled : Engine stops backing pick (pre-game)
    open --> void : Game postponed/cancelled or market voided (pre-game)
    open --> withdrawn : Published in error (retracted)
    awaiting_result --> settled : Graded on entry selection & line (won / lost / push)
    awaiting_result --> void : Game abandoned/cancelled or prop voided (e.g., DNP)
    cancelled --> [*]
    withdrawn --> [*]
    settled --> [*]
    void --> [*]
```

### 4.2 `pick_status` and `outcome` Specification

| `pick_status` | Phase | Meaning | Allowed `outcome` | Allowed `status_reason` | Consumer Behaviour |
| --- | --- | --- | --- | --- | --- |
| `"open"` | Pre-game | Active recommendation; the game has not started. | `null` | `null` | BFF serves the pick as open; live edge monitor tracks live odds. |
| `"awaiting_result"` | In-play / Post-game ungraded | The game has started and the pick has not yet been graded. | `null` | `null` | BFF serves the pick with its closing market observation; live edge monitor stops watching. |
| `"cancelled"` | Pre-game (Terminal) | The bet engine stopped backing the pick before the game started. | `null` | Should be set (`"probability_moved"`, `"market_moved"`, `"lineup_change"`) | BFF serves the pick as cancelled with its reason; live edge monitor stops watching and removes any live overlay. Never counts in settled win/loss records. |
| `"settled"` | Post-game (Terminal) | The game and market completed and the pick was graded against its frozen entry `line` and `side`. | `"won"`, `"lost"`, or `"push"` | `null` | BFF serves the final result (`won`, `lost`, or `push`). |
| `"void"` | Pre-game or Post-game (Terminal) | The game was postponed, cancelled, or abandoned, or the specific market/prop was voided under house rules. | `"void"` | Set when known (typically `"game_void"`), or `null` | BFF serves the pick as void; excluded from win/loss settlement totals. |
| `"withdrawn"` | Pre-game (Terminal) | The pick was published in error (data/pipeline defect) and retracted. | `null` | Optional (`"withdrawn"` or `null`) | BFF hides the pick and never serves it to clients; live edge monitor stops watching. |

> **Distinguishing `"push"` (`pick_status = "settled"`) from `"void"` (`pick_status = "void"`):**
> - Use **`pick_status = "settled"` with `outcome = "push"`** when the game and prop were validly played to completion and the final result landed **exactly on a whole-number entry `line`** (for example, a team backed at `-3.0` wins by exactly 3 points, or a total of `220.0` finishes with 220 total points).
> - Use **`pick_status = "void"` with `outcome = "void"`** when the wager itself is cancelled/voided without a valid contest—for example, when a game is postponed or cancelled (`status_reason = "game_void"`), or when a player prop is voided because the player did not play (DNP).

### 4.3 `status_reason` Codes (Provisional)

`status_reason` must be `null` whenever `pick_status` is `"open"`, `"awaiting_result"`, or `"settled"`. When `pick_status` is `"cancelled"`, `"void"`, or `"withdrawn"`, `status_reason` carries one of the following lowercase codes (or `null` if unknown):

| `status_reason` | Applicable `pick_status` | Meaning |
| --- | --- | --- |
| `"probability_moved"` | `"cancelled"` | A pre-game model re-evaluation lowered `probability` enough that the engine no longer backs the pick. |
| `"market_moved"` | `"cancelled"` | Pre-game price movement caused the bet engine to explicitly cancel its recommendation. |
| `"lineup_change"` | `"cancelled"` | A pre-game injury, scratch, or depth-chart change caused the bet engine to cancel the pick. |
| `"game_void"` | `"void"` | The game was postponed, cancelled, or abandoned, or the market was voided. |
| `"withdrawn"` | `"withdrawn"` | The pick was published in error and retracted. |

> **Important — Market movement vs. Cancellation:**
> - **A line move alone never cancels a pick.** If the entry line was `-4.5` and the market moves to `-5.5`, the pick remains `pick_status = "open"` on its frozen entry line (`line = -4.5`), `current_line` updates to `-5.5`, `current_edge` becomes `null`, and `edge_status` becomes `"closed"`.
> - **`edge_status` never automatically changes `pick_status`.** Even if `edge_status` becomes `"closed"` or `"suspended"`, `pick_status` remains `"open"` unless the bet engine explicitly transitions `pick_status` to `"cancelled"`.

---

## 5. Edge Basis, Threshold, Break-Even & Live Edge Status

### 5.1 Edge Basis & Break-Even Formulas

A pick is published because its entry edge clears the producer's minimum threshold (`entry_edge > edge_threshold`) on the producer's chosen `edge_basis` (`"ev"` for Expected Value or `"prob"` for Probability Edge). Both `edge_basis` and `edge_threshold` are stored on the record so downstream services can deterministically compute the break-even decimal price $b$, the narrowing midpoint price $m$, and live edge states.

Let:
- $p$ = `probability` ($0 < p < 1$)
- $d_{\text{entry}}$ = `entry_decimal_odds` ($d_{\text{entry}} > 1$, rounded to at most 4 decimal places)
- $d_{\text{curr}}$ = `current_decimal_odds` ($d_{\text{curr}} > 1$, rounded to at most 4 decimal places)
- $t$ = `edge_threshold` ($t \ge 0$, expressed as a fraction)

| Metric | Expected-Value Basis (`edge_basis = "ev"`) | Probability Basis (`edge_basis = "prob"`) | Rounding & Constraints |
| --- | --- | --- | --- |
| **`entry_edge`** | $p \times d_{\text{entry}} - 1$ | $p - \dfrac{1}{d_{\text{entry}}}$ | Computed from `probability` and `entry_decimal_odds` **as written on the record** (never from unrounded internal floats). Must satisfy `entry_edge > edge_threshold` (and therefore `entry_edge > 0`). |
| **`current_edge`** | $p \times d_{\text{curr}} - 1$ | $p - \dfrac{1}{d_{\text{curr}}}$ | Computed only when `current_decimal_odds != null` **and** `current_line == line` (including when both `line` and `current_line` are `null`). If `current_decimal_odds == null` or `current_line != line`, `current_edge` **must be `null`**. |
| **Break-even decimal price ($b$)** | $b = \dfrac{1 + t}{p}$ | $b = \dfrac{1}{p - t}$ *(undefined if $p \le t$)* | Computed from unrounded $p$ and $t$, then **rounded down (floor)** to 4 decimal places. |
| **Narrowing midpoint price ($m$)** | $m = \dfrac{d_{\text{entry}} + b}{2}$ | $m = \dfrac{d_{\text{entry}} + b}{2}$ | Computed from unrounded inputs, then rounded to 4 decimal places **half away from zero**. |

### 5.2 Decimal-to-American Odds Conversion

American odds (`entry_american_odds`, `current_american_odds`) are derived from the corresponding decimal price $d$, rounded to the nearest integer **half away from zero**:
- When $d \ge 2.0$: $\text{American} = +\text{round}\big((d - 1) \times 100\big)$
- When $1.0 < d < 2.0$: $\text{American} = -\text{round}\!\left(\dfrac{100}{d - 1}\right)$

### 5.3 `edge_status` Decision Table (First Match Wins)

Whenever a record is written, `edge_status` is determined by evaluating the following rules in strict priority order (**first match wins**):

| Priority | Condition | `edge_status` | `current_edge` | Meaning |
| --- | --- | --- | --- | --- |
| **1** | `observed_at == null` | `null` | `null` | No live market observation has been recorded yet. |
| **2** | `observed_at != null` and `current_decimal_odds == null` | `"suspended"` | `null` | The bookmaker pulled the market or price at the latest observation (`current_american_odds` and `current_line` are also `null`). |
| **3** | `current_line != line` | `"closed"` | `null` | The market line has moved off the pick's frozen entry `line`. |
| **4** | `current_decimal_odds <= b` | `"closed"` | Number ($\le t$) | The price on the entry line has moved to or below the break-even price $b$. |
| **5** | `entry_decimal_odds > b` and `current_decimal_odds <= m` | `"narrowing"` | Number ($> t$) | The price on the entry line has decayed past the midpoint $m$ toward break-even $b$, though positive edge remains. |
| **6** | Otherwise (`current_decimal_odds > m`) | `"live"` | Number ($> t$) | The pick's edge remains healthy above the midpoint $m$. |

### 5.4 Additional Producer Calculation Rules
- **Blended model probabilities:** `probability` is the exact probability value on which the pick was selected. If an engine blends its raw model probability toward the no-vig market probability before selection, it writes the blended value to `probability`.
- **Additional selection filters:** Any secondary selection filters (such as maximum model-vs-market disagreement caps or stake-tier bands) govern whether a pick is emitted and what `stake_units` it receives; they do not alter $b$, $m$, or `edge_status`.
- **Display conversion:** Producers never convert edges to the mobile app's display basis; the BFF performs display conversion from `probability` and the decimal price.

### 5.5 Normative Calculation Test Vectors

| Vector | Input Parameters | Expected Output |
| --- | --- | --- |
| **P-1** | `edge_basis = "ev"`, `probability = 0.58`, `entry_decimal_odds = 1.9091` | `entry_edge = 0.1073` |
| **P-2** | `edge_basis = "prob"`, `probability = 0.58`, `entry_decimal_odds = 1.9091` | `entry_edge = 0.0562` |
| **P-3** | Engine computes `5.0` percentage points on `"prob"` basis | `entry_edge = 0.05` |
| **P-4** | `edge_basis = "ev"`, `probability = 0.55`, `edge_threshold = 0` | $b = 1.8181$ (`-122` American) |
| **P-5** | `edge_basis = "prob"`, `probability = 0.55`, `edge_threshold = 0.03` | $b = 1.9230$ |
| **P-6** | `edge_basis = "prob"`, `probability = 0.40`, `edge_threshold = 0.03`, `entry_decimal_odds = 3.0000` | `entry_edge = 0.0667`, $b = 2.7027$ (`+170`), $m = 2.8514$ |
| **P-7** | `edge_basis = "ev"`, `probability = 0.55`, `edge_threshold = 0`, `entry_decimal_odds = 2.0000`, `line = 24.5`; observed `current_decimal_odds = 1.9500`, `current_line = 24.5` | `current_edge = 0.0725`, `edge_status = "live"` ($b = 1.8181$, $m = 1.9091$) |
| **P-8** | Same as **P-7**, except observed `current_line = 25.5` | `current_edge = null`, `edge_status = "closed"` |
| **P-9** | Decimal odds `1.8696` | American odds `-115` |

---

## 6. Field Reference (All 37 Fields)

Every producer pick record contains all 37 fields listed below. **Frozen** fields keep their first-publish value for the life of the record; **Live** fields are updated as market observations arrive or when the pick changes status / settles.

### 6.1 Identity & Context Fields

| # | Field | JSON Type | Allowed Values / Format | Null When | Mutability | Definition |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `schema_version` | `string` | SemVer matching `^4\.\d+\.\d+$` (e.g., `"4.0.0"`) | Never | Per write | Version of this contract the record conforms to. |
| 2 | `pick_id` | `string` | Canonical ID (max 255 chars; see [Section 8](#8-deterministic-pick_id-specification)) | Never | Frozen | Globally unique identifier for this pick in this region. |
| 3 | `region` | `string` | `"au"`, `"us"` | Never | Frozen | Target region for which the pick and its sportsbook pricing were published. |
| 4 | `sport` | `string` | `"nba"`, `"nfl"`, `"mlb"`, `"wnba"`, `"epl"` | Never | Frozen | League of the game. |
| 5 | `game_sk` | `integer` | Positive integer | Never | Frozen | Surrogate key of the game in the schedule. Must not collide across sports. |
| 6 | `pick_kind` | `string` | `"game"`, `"player"` | Never | Frozen | Whether this is a game-level pick (`"game"`) or a player prop (`"player"`). Explicitly stated, never inferred. |

### 6.2 Selection Fields (Frozen)

| # | Field | JSON Type | Allowed Values / Format | Null When | Mutability | Definition |
| --- | --- | --- | --- | --- | --- | --- |
| 7 | `market` | `string` | `"moneyline"`, `"spread"`, `"total"`, `"draw"`, `"btts"`, `"player_prop"` | Never | Frozen | Betting market. Must be `"player_prop"` iff `pick_kind == "player"`. |
| 8 | `side` | `string` | `"home"`, `"away"`, `"over"`, `"under"`, `"yes"`, `"no"`, `"draw"` | Never | Frozen | Backed side of the market (see [Section 7.1](#71-market--selection-matrix)). |
| 9 | `line` | `number \| null` | Signed number for `"spread"`; positive number (`> 0`) for `"total"` and `"over"`/`"under"` `"player_prop"` | `market` is `"moneyline"`, `"draw"`, `"btts"`, or a `"yes"`/`"no"` `"player_prop"` | Frozen | Entry line or threshold. For `"spread"`, expressed from the backed team's perspective (negative when giving points, positive when receiving points). |
| 10 | `team_sk` | `integer \| null` | Integer surrogate key of the backed team | `market` is `"total"`, `"draw"`, `"btts"`, or `"player_prop"` | Frozen | Surrogate key of the backed team (`"moneyline"` and `"spread"` only). |
| 11 | `player_sk` | `integer \| null` | Integer surrogate key of the player | `pick_kind == "game"` | Frozen | Surrogate key of the subject player (`"player_prop"` only). |
| 12 | `stat_code` | `string \| null` | Lowercase identifier matching `^[a-z][a-z0-9_]*$` (see [Section 7.3](#73-supported-markets--stat_code-vocabulary-by-sport)) | `pick_kind == "game"` | Frozen | Stat category being wagered on (`"player_prop"` only, e.g., `"pts"`, `"rec_yds"`). |

### 6.3 Model & Entry Pricing Fields (Frozen)

| # | Field | JSON Type | Allowed Values / Format | Null When | Mutability | Definition |
| --- | --- | --- | --- | --- | --- | --- |
| 13 | `probability` | `number` | `0 < probability < 1` | Never | Frozen | Model win probability (as a fraction) on which the pick was selected. |
| 14 | `projection_value` | `number \| null` | Finite JSON number (e.g., `28.3`) | The model produces no numeric projection for this market | Frozen | Model's projected stat or score value at the entry line. Must be `null` iff `projection_unit` is `null`. |
| 15 | `projection_unit` | `string \| null` | Non-empty string (e.g., `"points"`, `"yards"`, `"runs"`) | `projection_value == null` | Frozen | Unit label accompanying `projection_value`. |
| 16 | `pick_date_time` | `string` | ISO 8601 UTC timestamp (`YYYY-MM-DDTHH:mm:ss.sssZ`) | Never | Frozen | Timestamp when the pick was first published. |
| 17 | `entry_decimal_odds` | `number` | `> 1.0` (at most 4 decimal places) | Never | Frozen | Decimal price at first publish. |
| 18 | `entry_american_odds` | `integer` | Integer (derived from `entry_decimal_odds` per [Section 5.2](#52-decimal-to-american-odds-conversion)) | Never | Frozen | American price at first publish. |
| 19 | `entry_edge` | `number` | `> 0` (fraction; must exceed `edge_threshold`) | Never | Frozen | Edge at first publish computed on `edge_basis` from `probability` and `entry_decimal_odds`. |
| 20 | `edge_basis` | `string` | `"ev"`, `"prob"` | Never | Frozen | Formula basis (`"ev"` or `"prob"`) used to select the pick and evaluate `entry_edge` and `current_edge`. |
| 21 | `edge_threshold` | `number` | `>= 0` (fraction, e.g., `0`, `0.03`) | Never | Frozen | Minimum edge threshold $t$ on `edge_basis` that `entry_edge` cleared at selection time. |
| 22 | `stake_units` | `number` | `>= 0` (e.g., `0.5`, `1`, `2`) | Never | Frozen | Recommended stake size in units. |
| 23 | `odds_source_kind` | `string` | `"bookmaker"`, `"market_average"` | Never | Frozen | Whether the entry price came from a specific bookmaker or a market average. |
| 24 | `entry_bookmaker_id` | `string \| null` | Lowercase slug matching `^[a-z0-9_]+$` (e.g., `"fanduel"`, `"draftkings"`, `"sportsbet"`) | `odds_source_kind == "market_average"` | Frozen | Identifier of the sportsbook supplying the entry price. Must be a string when `odds_source_kind == "bookmaker"`. |

### 6.4 Live Market Observation Fields (Live)

| # | Field | JSON Type | Allowed Values / Format | Null When | Mutability | Definition |
| --- | --- | --- | --- | --- | --- | --- |
| 25 | `current_decimal_odds` | `number \| null` | `> 1.0` (at most 4 decimal places) | `observed_at == null`, or the bookmaker pulled the price (`edge_status == "suspended"`) | Live | Latest observed decimal price for the pick's market. |
| 26 | `current_american_odds` | `integer \| null` | Integer (derived from `current_decimal_odds`) | `current_decimal_odds == null` | Live | Latest observed American price. |
| 27 | `current_line` | `number \| null` | Signed number for `"spread"`; `> 0` for `"total"` and `"over"`/`"under"` `"player_prop"` | `observed_at == null`, `line == null` (market has no line), or `current_decimal_odds == null` (price pulled) | Live | Latest observed line. Must be non-null whenever `current_decimal_odds != null` and `line != null`. |
| 28 | `current_odds_source_kind` | `string \| null` | `"bookmaker"`, `"market_average"` | `observed_at == null` | Live | Source kind of the latest market observation (remains non-null even when the price is pulled at that source). |
| 29 | `current_bookmaker_id` | `string \| null` | Lowercase slug matching `^[a-z0-9_]+$` | `observed_at == null` or `current_odds_source_kind == "market_average"` | Live | Sportsbook where the latest market observation was taken. |
| 30 | `observed_at` | `string \| null` | ISO 8601 UTC timestamp (`YYYY-MM-DDTHH:mm:ss.sssZ`) | No market observation has occurred yet | Live | Timestamp when the latest price (or pulled-price state) was observed at the sportsbook. |
| 31 | `is_closing` | `boolean` | `true`, `false` | Never (`false` when `observed_at == null`) | Live | `true` only on the final pre-game market observation before the game starts; `false` otherwise. |
| 32 | `current_edge` | `number \| null` | Number (fraction; may be negative if price deteriorated) | `current_decimal_odds == null` or `current_line != line` | Live | Edge on `edge_basis` at `current_decimal_odds`, computed only while `current_line == line`. |
| 33 | `edge_status` | `string \| null` | `"live"`, `"narrowing"`, `"closed"`, `"suspended"` | `observed_at == null` | Live | Classification of the pick's live edge at the latest observation (see [Section 5.3](#53-edge_status-decision-table-first-match-wins)). |
| 34 | `rec_action` | `null` | Always `null` in `4.0.x` (reserved for `"play"`, `"watch"`, `"pass"`) | Always in `4.0.x` | Live | Reserved field for future live bettor guidance; must be `null` in `4.0.x`. |

### 6.5 Lifecycle & Settlement Fields (Live)

| # | Field | JSON Type | Allowed Values / Format | Null When | Mutability | Definition |
| --- | --- | --- | --- | --- | --- | --- |
| 35 | `pick_status` | `string` | `"open"`, `"awaiting_result"`, `"cancelled"`, `"settled"`, `"void"`, `"withdrawn"` | Never | Live | Current lifecycle state of the pick (see [Section 4.2](#42-pick_status-and-outcome-specification)). |
| 36 | `status_reason` | `string \| null` | `"probability_moved"`, `"market_moved"`, `"lineup_change"`, `"withdrawn"`, `"game_void"` | `pick_status` is `"open"`, `"awaiting_result"`, or `"settled"`, or no reason is known | Live | Machine-readable reason why a pick was `cancelled`, `void`, or `withdrawn` (see [Section 4.3](#43-status_reason-codes-provisional)). |
| 37 | `outcome` | `string \| null` | `"won"`, `"lost"`, `"push"`, `"void"` | `pick_status` is `"open"`, `"awaiting_result"`, `"cancelled"`, or `"withdrawn"` | Live | Final settlement grade evaluated on the frozen entry selection and line (`"won" \| "lost" \| "push"` when `pick_status == "settled"`; `"void"` when `pick_status == "void"`). |

---

## 7. Game Picks, Player Picks & Market Rules

A single record structure carries both game picks (`pick_kind = "game"`) and player prop picks (`pick_kind = "player"`). The combination of `pick_kind`, `market`, `side`, `line`, `team_sk`, `player_sk`, and `stat_code` completely defines the selection.

### 7.1 Market & Selection Matrix

| `market` | `pick_kind` | Allowed `side` | `line` | `team_sk` | `player_sk` & `stat_code` |
| --- | --- | --- | --- | --- | --- |
| `"moneyline"` | `"game"` | `"home"` or `"away"` | `null` | Integer (`> 0`, backed team) | `null` |
| `"spread"` | `"game"` | `"home"` or `"away"` | Number (signed from backed team's view; negative when giving points) | Integer (`> 0`, backed team) | `null` |
| `"total"` | `"game"` | `"over"` or `"under"` | Number (`> 0`, total points/runs/goals threshold) | `null` | `null` |
| `"draw"` | `"game"` | `"draw"` | `null` | `null` | `null` |
| `"btts"` | `"game"` | `"yes"` or `"no"` | `null` | `null` | `null` |
| `"player_prop"` *(threshold)* | `"player"` | `"over"` or `"under"` | Number (`> 0`, stat threshold; `current_line` must also be `> 0` when present) | `null` | Integer `player_sk` and non-empty string `stat_code` |
| `"player_prop"` *(binary)* | `"player"` | `"yes"` or `"no"` | `null` (`current_line` must also be `null`) | `null` | Integer `player_sk` and non-empty string `stat_code` |

### 7.2 Domain Rules for Selections & Lines

1. **`side = "home" | "away"` comes from the game venue, not schedule slot order:**
   A producer that internally labels teams as `team_1`/`team_2` or `favourite`/`underdog` must resolve whether the backed team is the home team or the away team for `side`, and write that team's surrogate key to `team_sk`.
2. **Three-way moneyline in soccer (`sport = "epl"`):**
   In sports with regulation draws (`"epl"`), `"moneyline"` (`"home"` or `"away"`) is a 3-way regulation market that loses if the match finishes in a draw; backing the draw itself uses `market = "draw"` with `side = "draw"`.
3. **Milestone player props (`"25+ points"`):**
   Milestone props for $k+$ units are normalized to `market = "player_prop"`, `side = "over"`, and `line = k - 0.5` (for example, `"25+ points"` is written as `side = "over"`, `line = 24.5`).
4. **Binary (`"yes"` / `"no"`) player props:**
   Yes/no props (such as NFL `"anytime_td"`) use `market = "player_prop"`, `side = "yes"` or `"no"`, and `line = null` (never `line = 0.5`).
5. **Full-game regulation/standard settlement, one line per pick:**
   Version `4.0` covers full-game markets only (no halves, quarters, or periods). Alternate lines are represented simply by their `line` value with no separate flag. Quarter lines (Asian handicap `0.25` / `0.75` steps that split stakes) are not permitted.
6. **Edge consistency with written odds:**
   `entry_edge` must be computed from `probability` and `entry_decimal_odds` **as rounded and written in the record** (up to 4 decimal places), ensuring any consumer recomputing `entry_edge` reproduces the exact same value.

### 7.3 Supported Markets & `stat_code` Vocabulary by Sport (Provisional)

| `sport` | Supported Game Markets (`pick_kind = "game"`) | Supported Player Prop `stat_code` Values (`pick_kind = "player"`, `market = "player_prop"`) | Prop `side` & `line` Type |
| --- | --- | --- | --- |
| **`"nba"`** | `"moneyline"`, `"spread"`, `"total"` | `"pts"` (points), `"reb"` (rebounds), `"ast"` (assists), `"threes"` (three-pointers made) | `"over"` / `"under"` with `line > 0` |
| **`"nfl"`** | `"moneyline"`, `"spread"`, `"total"` | `"pass_yds"` (passing yards), `"pass_tds"` (passing touchdowns), `"rush_yds"` (rushing yards), `"rec_yds"` (receiving yards), `"receptions"` (receptions) | `"over"` / `"under"` with `line > 0` |
| **`"nfl"`** *(binary)* | — | `"anytime_td"` (anytime touchdown scorer) | `"yes"` / `"no"` with `line = null` |
| **`"mlb"`** *(batters)* | `"moneyline"`, `"total"` *(plus `"spread"` run-line when enabled)* | `"hits"` (batter hits), `"runs"` (runs scored), `"home_runs"` (home runs), `"rbi"` (runs batted in) | `"over"` / `"under"` with `line > 0` |
| **`"mlb"`** *(pitchers)* | — | `"strikeouts"` (pitcher strikeouts), `"hits_allowed"` (hits allowed), `"earned_runs"` (earned runs allowed) | `"over"` / `"under"` with `line > 0` |
| **`"wnba"`** | `"moneyline"`, `"total"` *(plus `"spread"` when enabled)* | None in `4.0.0` | — |
| **`"epl"`** | `"moneyline"` (3-way), `"draw"`, `"btts"`, `"total"`, `"spread"` | None in `4.0.0` | — |

### 7.4 Selection & `pick_id` Examples Across Sports

*(In the examples below, the home team is the schedule's `team_1` (`t1`) and the away team is `team_2` (`t2`); see [Section 8](#8-deterministic-pick_id-specification) for how `t1`/`t2` is used in `pick_id`.)*

| # | Scenario | `pick_kind` | `market` | `side` | `line` | `team_sk` | `player_sk` | `stat_code` | Canonical `pick_id` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **G1** | NBA: Celtics `-4.5` (home, `team_1`) | `"game"` | `"spread"` | `"home"` | `-4.5` | `40000002` | `null` | `null` | `{game_sk}\|spread_t1\|t1\|-4.5\|main\|full\|{region}` |
| **G2** | NBA: Over `224.5` total points | `"game"` | `"total"` | `"over"` | `224.5` | `null` | `null` | `null` | `{game_sk}\|total_over\|over\|224.5\|main\|full\|{region}` |
| **G3** | NBA: Knicks moneyline (away, `team_2`) | `"game"` | `"moneyline"` | `"away"` | `null` | `40000018` | `null` | `null` | `{game_sk}\|h2h_t2\|t2\|null\|main\|full\|{region}` |
| **G4** | EPL: Match draw | `"game"` | `"draw"` | `"draw"` | `null` | `null` | `null` | `null` | `{game_sk}\|draw_draw\|draw\|null\|main\|full\|{region}` |
| **G5** | EPL: Both teams to score — No | `"game"` | `"btts"` | `"no"` | `null` | `null` | `null` | `null` | `{game_sk}\|btts_no\|no\|null\|main\|full\|{region}` |
| **G6** | EPL: Home team 3-way moneyline (`team_1`) | `"game"` | `"moneyline"` | `"home"` | `null` | `50000001` | `null` | `null` | `{game_sk}\|h2h_t1\|t1\|null\|main\|full\|{region}` |
| **G7** | NFL: Away underdog `+6.5` (`team_2`) | `"game"` | `"spread"` | `"away"` | `6.5` | `30000014` | `null` | `null` | `{game_sk}\|spread_t2\|t2\|6.5\|main\|full\|{region}` |
| **G8** | MLB: Under `8.5` total runs | `"game"` | `"total"` | `"under"` | `8.5` | `null` | `null` | `null` | `{game_sk}\|total_under\|under\|8.5\|main\|full\|{region}` |
| **P1** | NBA: Jayson Tatum Over `24.5` points | `"player"` | `"player_prop"` | `"over"` | `24.5` | `null` | `400000000434` | `"pts"` | `{game_sk}\|{player_sk}\|pts\|player_over\|24.5\|main\|full\|{region}` |
| **P2** | NBA: Player Under `9.5` rebounds | `"player"` | `"player_prop"` | `"under"` | `9.5` | `null` | `400000000434` | `"reb"` | `{game_sk}\|{player_sk}\|reb\|player_under\|9.5\|main\|full\|{region}` |
| **P3** | NFL: Player Over `14.5` receiving yards | `"player"` | `"player_prop"` | `"over"` | `14.5` | `null` | `300123456` | `"rec_yds"` | `{game_sk}\|{player_sk}\|rec_yds\|player_over\|14.5\|main\|full\|{region}` |
| **P4** | NFL: Player Anytime Touchdown — Yes | `"player"` | `"player_prop"` | `"yes"` | `null` | `null` | `300123456` | `"anytime_td"` | `{game_sk}\|{player_sk}\|anytime_td\|player_yes\|null\|main\|full\|{region}` |
| **P5** | MLB: Aaron Judge Over `0.5` home runs | `"player"` | `"player_prop"` | `"over"` | `0.5` | `null` | `20009911` | `"home_runs"` | `{game_sk}\|{player_sk}\|home_runs\|player_over\|0.5\|main\|full\|{region}` |
| **P6** | NBA: Player `25+` points milestone | `"player"` | `"player_prop"` | `"over"` | `24.5` | `null` | `400000000434` | `"pts"` | `{game_sk}\|{player_sk}\|pts\|player_over\|24.5\|main\|full\|{region}` |

---

## 8. Deterministic `pick_id` Specification

Every producer builds `pick_id` using one canonical pipe-delimited (`|`) formula. While consumers treat `pick_id` as an opaque identifier and never parse it, the deterministic formula guarantees that every producer mints the exact same ID for the same pick and prevents collisions across games, markets, lines, and regions.

### 8.1 Canonical Templates

| Pick Category | Canonical `pick_id` Template |
| --- | --- |
| **Game pick (`pick_kind = "game"`)** | `{game_sk}\|{market_token}_{selection}\|{selection}\|{line_token}\|main\|full\|{region}` |
| **Player prop (`pick_kind = "player"`)** | `{game_sk}\|{player_sk}\|{stat_code}\|player_{side}\|{line_token}\|main\|full\|{region}` |
| **Re-issued pick (either kind)** | Same template above, followed by `\|r{n}` (where `n >= 2`, starting at `r2`) |

### 8.2 Segment Definitions

| Segment | Specification |
| --- | --- |
| `game_sk`, `player_sk`, `stat_code`, `region` | Exact string representation of the record's own `game_sk`, `player_sk`, `stat_code`, and `region` fields. |
| `market_token` *(game picks)* | `"h2h"` when `market == "moneyline"`; otherwise the record's `market` value (`"spread"`, `"total"`, `"draw"`, `"btts"`). Any future market token added in `4.x` must consist of lowercase ASCII letters and digits only (`[a-z0-9]+`), with no `_` or `\|`. |
| `selection` *(game picks)* | When `team_sk != null` (`"moneyline"` and `"spread"`), `"t1"` or `"t2"`—the backed team's slot (`team_1` or `team_2`) on the game schedule, matched by `team_sk`. When `team_sk == null` (`"total"`, `"draw"`, `"btts"`), the record's `side` (`"over"`, `"under"`, `"draw"`, `"yes"`, `"no"`). |
| `selection` *(reserved multi-way)* | Reserved for future `4.x` multi-way markets: `k{competitor_sk}` for a team/competitor among a field (e.g., tournament winner) and `p{player_sk}` for a player among all players in a game (e.g., first touchdown scorer). Not emitted in `4.0.0`. |
| `side` *(player props)* | The record's `side` (`"over"`, `"under"`, `"yes"`, `"no"`), prefixed with `player_` (`player_over`, `player_under`, `player_yes`, `player_no`). Because milestone props are represented as `side = "over"` with `line = k - 0.5`, they always use `player_over`. |
| `line_token` | `"null"` when `line == null`. Otherwise, the shortest decimal string that parses back to the exact same floating-point number, always including at least one digit after the decimal point: `"24.5"`, `"-4.5"`, `"3.0"`, `"220.0"`. Zero is `"0.0"`, never `"-0.0"`. |
| `main`, `full` | Literal constants `"main"` and `"full"` in `4.x` (representing main/alternate unified line treatment and full-game regulation period). |
| `r{n}` *(re-issue suffix)* | Omitted on first publication of a selection in a region. If that pick is `cancelled` or `withdrawn` and a later pre-game run recommends the exact same selection and entry line in the same region, the new pick appends `\|r2` (then `\|r3`, etc.). |

> **Why `side` uses `"home" | "away"` while `pick_id` uses `"t1" | "t2"`:**
> On the record itself, `side` (`"home"` or `"away"`) gives consumers the semantic venue side without needing to cross-reference the schedule. In `pick_id`, `"t1"` / `"t2"` binds identity to the game schedule's `team_1_sk` / `team_2_sk` slots and preserves backward compatibility with existing pick identifiers.

### 8.3 Concrete `pick_id` Examples

| Pick Description | `pick_id` |
| --- | --- |
| NBA spread on `team_1` (`-4.5`, US) | `40021717862\|spread_t1\|t1\|-4.5\|main\|full\|us` |
| NBA moneyline on `team_1` (AU) | `40021717862\|h2h_t1\|t1\|null\|main\|full\|au` |
| NBA player prop (`pts` Over `24.5`, US) | `40021717862\|400000000434\|pts\|player_over\|24.5\|main\|full\|us` |
| NFL spread on `team_2` on a whole-number line (`+3.0`, US) | `300019484\|spread_t2\|t2\|3.0\|main\|full\|us` |
| EPL match draw (AU) | `500000123\|draw_draw\|draw\|null\|main\|full\|au` |
| EPL both teams to score — No (AU) | `500000123\|btts_no\|no\|null\|main\|full\|au` |
| NFL anytime touchdown — Yes (US) | `300019484\|300123456\|anytime_td\|player_yes\|null\|main\|full\|us` |
| NBA total Over `224.5` re-issued after a cancellation (US) | `40021717862\|total_over\|over\|224.5\|main\|full\|us\|r2` |
| Reserved (`4.x`): Tournament winner (`competitor_sk = 3301`) | `7001234\|winner_k3301\|k3301\|null\|main\|full\|us` |
| Reserved (`4.x`): First touchdown scorer (`player_sk = 300123456`) | `300019484\|firsttd_p300123456\|p300123456\|null\|main\|full\|us` |

### 8.4 Reference `pick_id` Generator (Python)

Producers written in any language must produce output identical to this reference function:

```python
MARKET_TOKEN = {
    "moneyline": "h2h",
    "spread": "spread",
    "total": "total",
    "draw": "draw",
    "btts": "btts",
}


def line_token(line):
    if line is None:
        return "null"
    x = float(line)
    return repr(0.0 if x == 0 else x)  # e.g. "24.5", "-4.5", "3.0", "220.0"


def build_pick_id(record, team_slot=None, reissue=1):
    """
    team_slot: "t1" or "t2" (the backed team's slot on the game schedule);
               required whenever record["team_sk"] is not None.
    reissue:   1 for first issue; 2, 3, ... for re-issues after cancelled/withdrawn.
    """
    r = record
    if r["pick_kind"] == "player":
        parts = [
            r["game_sk"],
            r["player_sk"],
            r["stat_code"],
            "player_" + r["side"],
        ]
    else:
        selection = team_slot if r["team_sk"] is not None else r["side"]
        parts = [
            r["game_sk"],
            MARKET_TOKEN[r["market"]] + "_" + selection,
            selection,
        ]
    parts += [line_token(r["line"]), "main", "full", r["region"]]
    if reissue > 1:
        parts.append(f"r{reissue}")
    return "|".join(str(p) for p in parts)
```

---

## 9. Normative JSON Schema (Draft 2020-12)

The JSON Schema below is self-contained and is the normative machine-verifiable specification for a single producer pick record. It enforces:
- All 37 required fields and `"additionalProperties": false`
- Field types, numeric bounds, regex patterns, and enum vocabularies
- Co-nullability and conditional rules for market observations, pulled prices (`edge_status = "suspended"`), bookmaker vs. market-average sources, game vs. player picks, market-to-side/line/team mappings, positive lines on totals and over/under props, and `projection_value`/`projection_unit` pairing

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://contracts.xosports.ai/edge-picks/v4/producer-pick.schema.json",
  "title": "Edge Picks producer pick record 4.0.0",
  "type": "object",
  "required": [
    "schema_version",
    "pick_id",
    "region",
    "sport",
    "game_sk",
    "pick_kind",
    "market",
    "side",
    "line",
    "team_sk",
    "player_sk",
    "stat_code",
    "probability",
    "projection_value",
    "projection_unit",
    "pick_date_time",
    "entry_decimal_odds",
    "entry_american_odds",
    "entry_edge",
    "edge_basis",
    "edge_threshold",
    "stake_units",
    "odds_source_kind",
    "entry_bookmaker_id",
    "current_decimal_odds",
    "current_american_odds",
    "current_line",
    "current_odds_source_kind",
    "current_bookmaker_id",
    "observed_at",
    "is_closing",
    "current_edge",
    "edge_status",
    "rec_action",
    "pick_status",
    "status_reason",
    "outcome"
  ],
  "properties": {
    "schema_version": {"type": "string", "pattern": "^4\\.\\d+\\.\\d+$"},
    "pick_id": {
      "type": "string",
      "maxLength": 255,
      "pattern": "^(\\d+\\|[a-z0-9]+_(t1|t2|over|under|yes|no|draw|k\\d+|p\\d+)\\|(t1|t2|over|under|yes|no|draw|k\\d+|p\\d+)\\|(null|0\\.0|-?[1-9]\\d*\\.(0|\\d*[1-9])|-?0\\.\\d*[1-9])\\|main\\|full\\|(au|us)(\\|r([2-9]|[1-9]\\d+))?|\\d+\\|\\d+\\|[a-z0-9_]+\\|player_(over|under|yes|no)\\|(null|0\\.0|-?[1-9]\\d*\\.(0|\\d*[1-9])|-?0\\.\\d*[1-9])\\|main\\|full\\|(au|us)(\\|r([2-9]|[1-9]\\d+))?)$"
    },
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
    "entry_edge": {"type": "number", "exclusiveMinimum": 0},
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
      "if": {"properties": {"current_decimal_odds": {"type": "number"}, "line": {"type": "number"}}},
      "then": {"properties": {"current_line": {"type": "number"}}}
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

### 9.1 Cross-Record & Arithmetic Invariants (Checked Alongside JSON Schema)

Because JSON Schema validates one JSON object at a time, producer test suites also enforce these six contract invariants that span fields or consecutive publishes:
1. **`pick_id` reconstruction:** Rebuilding `pick_id` from the record's fields and the game schedule using `build_pick_id()` ([Section 8.4](#84-reference-pick_id-generator-python)) yields the exact `pick_id` on the record.
2. **Decimal places:** `entry_decimal_odds` and `current_decimal_odds` have at most 4 decimal places.
3. **Arithmetic consistency:** `entry_edge > edge_threshold`, and `entry_edge`, `current_edge`, `edge_status`, `entry_american_odds`, and `current_american_odds` match the formulas in [Section 5](#5-edge-basis-threshold-break-even--live-edge-status).
4. **No silent drops (Rule 2):** Every `pick_id` present in a prior publish remains present in subsequent publishes.
5. **Frozen-field immutability (Rule 3):** For any existing `pick_id`, all 23 frozen fields are byte-for-byte identical to their first-publish values.
6. **Forward-only status transitions (Rule 6):** `pick_status` transitions only along valid edges in [Section 4.1](#41-lifecycle-state-diagram).

---

## 10. Complete Example Records

All five records below validate against the normative JSON Schema in [Section 9](#9-normative-json-schema-draft-2020-12) and satisfy all arithmetic and `pick_id` invariants.

### 10.1 Example 1 — Newly Published Open Player Prop (`nba`, `"prob"` basis, no observation yet)
Jayson Tatum Over `24.5` points in the `"us"` region on the probability basis (`probability = 0.6565`, `entry_decimal_odds = 1.87`, `edge_threshold = 0.03`, giving `entry_edge = 0.6565 - 1/1.87 = 0.1217`), before the live edge monitor has recorded its first observation:

```json
{
  "schema_version": "4.0.0",
  "pick_id": "40021717862|400000000434|pts|player_over|24.5|main|full|us",
  "region": "us",
  "sport": "nba",
  "game_sk": 40021717862,
  "pick_kind": "player",
  "market": "player_prop",
  "side": "over",
  "line": 24.5,
  "team_sk": null,
  "player_sk": 400000000434,
  "stat_code": "pts",
  "probability": 0.6565,
  "projection_value": null,
  "projection_unit": null,
  "pick_date_time": "2026-10-22T03:00:00.000Z",
  "entry_decimal_odds": 1.87,
  "entry_american_odds": -115,
  "entry_edge": 0.1217,
  "edge_basis": "prob",
  "edge_threshold": 0.03,
  "stake_units": 1,
  "odds_source_kind": "bookmaker",
  "entry_bookmaker_id": "fanduel",
  "current_decimal_odds": null,
  "current_american_odds": null,
  "current_line": null,
  "current_odds_source_kind": null,
  "current_bookmaker_id": null,
  "observed_at": null,
  "is_closing": false,
  "current_edge": null,
  "edge_status": null,
  "rec_action": null,
  "pick_status": "open",
  "status_reason": null,
  "outcome": null
}
```

### 10.2 Example 2 — Newly Published Open Game Pick (`epl`, `"draw"`, `"ev"` basis, `"au"` region)
An EPL match draw in the `"au"` region on the expected-value basis (`probability = 0.30`, `entry_decimal_odds = 3.60`, `edge_threshold = 0`, giving `entry_edge = 0.30 * 3.60 - 1 = 0.08`):

```json
{
  "schema_version": "4.0.0",
  "pick_id": "500000123|draw_draw|draw|null|main|full|au",
  "region": "au",
  "sport": "epl",
  "game_sk": 500000123,
  "pick_kind": "game",
  "market": "draw",
  "side": "draw",
  "line": null,
  "team_sk": null,
  "player_sk": null,
  "stat_code": null,
  "probability": 0.3,
  "projection_value": null,
  "projection_unit": null,
  "pick_date_time": "2026-10-22T06:00:00.000Z",
  "entry_decimal_odds": 3.6,
  "entry_american_odds": 260,
  "entry_edge": 0.08,
  "edge_basis": "ev",
  "edge_threshold": 0,
  "stake_units": 0.5,
  "odds_source_kind": "bookmaker",
  "entry_bookmaker_id": "sportsbet",
  "current_decimal_odds": null,
  "current_american_odds": null,
  "current_line": null,
  "current_odds_source_kind": null,
  "current_bookmaker_id": null,
  "observed_at": null,
  "is_closing": false,
  "current_edge": null,
  "edge_status": null,
  "rec_action": null,
  "pick_status": "open",
  "status_reason": null,
  "outcome": null
}
```

### 10.3 Example 3 — Open Game Pick with Live Market Observation (`nba`, `"spread"`, `edge_status = "live"`)
An NBA home spread pick (`line = -4.5`) on the expected-value basis (`probability = 0.55`, `edge_threshold = 0`, $b = 1.8181$, $m = 1.9091$). Entry price `2.0000` gives `entry_edge = 0.1000`. The latest observation sees `current_decimal_odds = 1.9500` on the same `-4.5` line, giving `current_edge = 0.0725` and `edge_status = "live"` (since `1.9500 > 1.9091`):

```json
{
  "schema_version": "4.0.0",
  "pick_id": "40021717862|spread_t1|t1|-4.5|main|full|us",
  "region": "us",
  "sport": "nba",
  "game_sk": 40021717862,
  "pick_kind": "game",
  "market": "spread",
  "side": "home",
  "line": -4.5,
  "team_sk": 40000002,
  "player_sk": null,
  "stat_code": null,
  "probability": 0.55,
  "projection_value": null,
  "projection_unit": null,
  "pick_date_time": "2026-10-22T18:05:12.341Z",
  "entry_decimal_odds": 2.0,
  "entry_american_odds": 100,
  "entry_edge": 0.1,
  "edge_basis": "ev",
  "edge_threshold": 0,
  "stake_units": 2,
  "odds_source_kind": "bookmaker",
  "entry_bookmaker_id": "draftkings",
  "current_decimal_odds": 1.95,
  "current_american_odds": -105,
  "current_line": -4.5,
  "current_odds_source_kind": "bookmaker",
  "current_bookmaker_id": "draftkings",
  "observed_at": "2026-10-22T18:58:40.000Z",
  "is_closing": false,
  "current_edge": 0.0725,
  "edge_status": "live",
  "rec_action": null,
  "pick_status": "open",
  "status_reason": null,
  "outcome": null
}
```

### 10.4 Example 4 — Pre-Game Cancelled Game Pick (`nba`, `"moneyline"`, `status_reason = "probability_moved"`)
An away moneyline pick (`entry_decimal_odds = 2.25`, `probability = 0.48`, `entry_edge = 0.08`, $b = 2.0833$). Before tip-off, a model re-evaluation stopped backing the pick, transitioning `pick_status` to `"cancelled"` with `status_reason = "probability_moved"`. All frozen fields (`probability`, `entry_*`) retain their first-publish values, and `current_*` retains the final market observation taken before cancellation (`2.05`, where `current_edge = -0.016` and `edge_status = "closed"`):

```json
{
  "schema_version": "4.0.0",
  "pick_id": "40021717861|h2h_t2|t2|null|main|full|us",
  "region": "us",
  "sport": "nba",
  "game_sk": 40021717861,
  "pick_kind": "game",
  "market": "moneyline",
  "side": "away",
  "line": null,
  "team_sk": 40000013,
  "player_sk": null,
  "stat_code": null,
  "probability": 0.48,
  "projection_value": null,
  "projection_unit": null,
  "pick_date_time": "2026-10-22T14:02:10.500Z",
  "entry_decimal_odds": 2.25,
  "entry_american_odds": 125,
  "entry_edge": 0.08,
  "edge_basis": "ev",
  "edge_threshold": 0,
  "stake_units": 1,
  "odds_source_kind": "bookmaker",
  "entry_bookmaker_id": "draftkings",
  "current_decimal_odds": 2.05,
  "current_american_odds": 105,
  "current_line": null,
  "current_odds_source_kind": "bookmaker",
  "current_bookmaker_id": "draftkings",
  "observed_at": "2026-10-22T18:41:00.000Z",
  "is_closing": false,
  "current_edge": -0.016,
  "edge_status": "closed",
  "rec_action": null,
  "pick_status": "cancelled",
  "status_reason": "probability_moved",
  "outcome": null
}
```

### 10.5 Example 5 — Settled Player Prop After a Pre-Game Line Move (`nba`, `"player_prop"`, `is_closing = true`, `outcome = "won"`)
Tyrese Maxey Over `26.5` points (`entry_decimal_odds = 1.8696`, `probability = 0.60`, `entry_edge = 0.1218`, `projection_value = 28.3`, `projection_unit = "points"`). By the closing observation before tip-off (`is_closing = true`), the sportsbook line had moved to `27.5` (`current_line = 27.5`), setting `current_edge = null` and `edge_status = "closed"`. Because a line move never cancels a pick, the recommendation stayed active on its entry line (`26.5`), was graded post-game against `26.5`, and settled as `"won"`:

```json
{
  "schema_version": "4.0.0",
  "pick_id": "40021717850|50001234|pts|player_over|26.5|main|full|us",
  "region": "us",
  "sport": "nba",
  "game_sk": 40021717850,
  "pick_kind": "player",
  "market": "player_prop",
  "side": "over",
  "line": 26.5,
  "team_sk": null,
  "player_sk": 50001234,
  "stat_code": "pts",
  "probability": 0.6,
  "projection_value": 28.3,
  "projection_unit": "points",
  "pick_date_time": "2026-10-22T13:10:44.002Z",
  "entry_decimal_odds": 1.8696,
  "entry_american_odds": -115,
  "entry_edge": 0.1218,
  "edge_basis": "ev",
  "edge_threshold": 0,
  "stake_units": 2,
  "odds_source_kind": "bookmaker",
  "entry_bookmaker_id": "draftkings",
  "current_decimal_odds": 1.9091,
  "current_american_odds": -110,
  "current_line": 27.5,
  "current_odds_source_kind": "bookmaker",
  "current_bookmaker_id": "draftkings",
  "observed_at": "2026-10-22T15:59:30.000Z",
  "is_closing": true,
  "current_edge": null,
  "edge_status": "closed",
  "rec_action": null,
  "pick_status": "settled",
  "status_reason": null,
  "outcome": "won"
}
```

---

## 11. Open Decisions & Sign-Off

### 11.1 Open Contract Decisions

| Topic | Provisional Rule in `4.0.0` | Open Question | Target Resolution Date |
| --- | --- | --- | --- |
| **Status vocabulary** | `open`, `awaiting_result`, `cancelled`, `settled`, `void`, `withdrawn` | Final sign-off on status names and the boundary between `cancelled` (engine no longer backs pick) and `withdrawn` (published in error). | Oct 21, 2026 |
| **Reopening a `cancelled` pick** | Disallowed (Rule 6: forward-only status transitions; re-recommendations mint `\|r2`). | Whether a pre-game `cancelled` pick may transition back to `open` under the same `pick_id` (e.g., if a player returns to the starting depth chart before kickoff). | Oct 21, 2026 |
| **`status_reason` vocabulary** | `probability_moved`, `market_moved`, `lineup_change`, `withdrawn`, `game_void` | Whether to drop `withdrawn` as a reason code (since `pick_status` is already `"withdrawn"`) and whether to add `"book_pulled"` or `"competitor_withdrawn"`. | Oct 21, 2026 |
| **`stat_code` vocabulary** | Table in [Section 7.3](#73-supported-markets--stat_code-vocabulary-by-sport) | Final sign-off on canonical stat codes and any additional prop categories planned for `4.x`. | Oct 21, 2026 |
| **Pre-game cancellation policy** | Engine cancels when it stops backing a pick before the game starts; never for a line move alone. | Which specific pre-game model re-evaluation triggers transition a pick to `cancelled` vs. leaving it `open` with `edge_status = "closed"`. | Oct 30, 2026 |

### 11.2 Change Log & Sign-Off

| Date | Version | Summary | Sign-Off Status |
| --- | --- | --- | --- |
| Oct 19, 2026 | `4.0.0` | Initial self-contained v4.0.0 specification of the Edge Picks producer pick record schema, lifecycle, edge formulas, market/stat mappings, deterministic `pick_id`, and Draft 2020-12 JSON Schema. | **Bet Engine:** Pending<br>**Data Engineering:** Pending<br>**BFF:** Pending<br>**Live Edge Monitor:** Pending |

