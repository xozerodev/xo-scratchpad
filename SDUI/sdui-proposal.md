# XO Mobile Data Lineage & SDUI Assessment

Oct 16, 2026 · @Tze Liang

Every screen in the app gets its data from one BFF over Cosmos, but display decisions are made in all four layers. The Publish Engine writes status words and stat labels. The BFF composes copy and holds 57 league branches. The app re-labels, recomputes and branches on league at about 37 points, plus 10 per-league maps and bundled logos. Adding a league therefore touches about 8 places in the Publish Engine, 11 areas of the BFF and 11 app files, plus a store release.

A server-driven UI (SDUI) is feasible because the BFF already writes most display strings, and the Edge Picks v4 contract (field groups, labels, explicit access) is the right template. The recommended shape is **server-driven content, native layout**: the BFF composes screens as ordered sections of about 15 known components from a league registry and the v3 canonical documents, and the app renders them.

Three facts set the order of work:

- `/v4/edge-picks` serves mock fixtures only, and the app does not call it yet.
- The live score and edge-monitor overlays in Firebase are built, but nothing in the app reads them.
- NBA alone is on the NBA 2026 canonical documents; MLB, WNBA, NFL and EPL are still on legacy Format A, so the BFF carries both paths.

## At a glance

&#91;embedded content: data lineage · feeds to screens, 10 systems\]

Everything the app shows today travels the left column: feeds, ingestion, bet engines, the Publish Engine, Cosmos and the BFF. The live-score and edge-monitor overlays on the right reach Firebase but stop there.

## Screen by screen

Every content screen reads a `/v3` BFF route with `api_version=v6`, which the app hardcodes and which ignores the server's `/config` value. My Picks is the exception, pinned to `api_version=v3`. The BFF joins schedule, prediction, player and outcome documents per game, and all of them are published by the Publish Engine from bet-engine and ML tables.

| Screen and element | BFF route | Cosmos source | Producer upstream | Computed or rewritten in the app |
| --- | --- | --- | --- | --- |
| Home: greeting, banner message | `/user/profile`, `/config` | `users` | BFF env vars | Man vs Machine card is fully bundled, including the machine score 110–118 |
| All Games card: teams, logo, time, status, predicted score, win and draw probability | `GET /v3/matches/{date}` | `c-sch`, `c-wltp` (`game_prediction`), `c-outcomes` | PE from `dim_all_games`, `wltp_top_picks_agg`, model POF tables | Logos come from bundled images by `imageCode`; team\_2 is drawn on the left; status defaults to Completed when missing |
| All Games card: moneyline odds, top-pick banner, correct or incorrect | same | `c-wltp` `game_odds`, `is_top_pick`; `c-outcomes` | Bet engine agg via PE | Odds formatted by region (+150 or $2.50); "Top Pick:" prefix added |
| Game details: header and scoreboard | `GET /v3/match/{id}` | `c-sch`, `c-wltp`, `c-outcomes` | same | Reads `game_status` here but `status` on the list |
| Game details: Top Picks and Edge Picks | same, `topPicks[]` and `edgePicks[]` (a copy of `picks`) | `c-wltp` `top_picks` or `game_edge_picks`; `c-ps` `player_top_picks` or `player_edge_picks` | Bet engine agg via PE | Player-prop labels rebuilt; game-level outcome overrides each top pick's own result |
| Game details: player tables | same, `team_N.players` (sections from v4) and `metadata.playerstatkeys` | `c-ps` `player_predictions` | PE: MLB batter/pitcher POFs, NFL player POFs, EPL lineups, WNBA pass-through | NBA columns fixed to PTS REB AST STL BLK; MLB and NFL section order set in the app |
| Game details: injuries | same, `team_N.injuries` | `c-injuries` (by player) or `c-injuries-team` (NBA canonical) | PE from `fact_player_injuries` | Date format by region |
| Edge Picks tab: pick, odds, XO projection, probability, wager | `GET /v3/matches/{date}/top-predictions` | `c-sch`, `c-wltp`, `c-ps`, `c-outcomes` | Bet engine agg via PE | Wager = stake × bet size; projection re-titled; edge and bookmaker never shown |
| Stake slip | none (local state) | none | none | Combined probability, total odds and return computed in the app |
| My Picks | `GET /my-picks-v2?api_version=v3` | `my_picks_v2`, then the four content containers | BFF snapshot taken at save | Combined probability recomputed; void (2) shows as a win |
| Paywall, Manage subscription | Qonversion SDK; `/entitlement/activate` | `user_subscriptions` | Qonversion | Savings % computed in the app |
| Profile, onboarding | `/user/profile` | `users` | none | Sports tiles and regions bundled |
| Push notifications | FCM | none | Service Bus queue → BFF copy | none |

Not shown anywhere today: `/summary` (ROI and record, screens are unmounted), `/v4/edge-picks`, and the Firebase live-score and edge overlays.

## Where display decisions live today

The same decision is often made twice: the BFF writes a pick description and the app rebuilds it, and the BFF converts odds by region while the app converts them again. For SDUI, each row below has to end up in exactly one place.

| Decision | Publish Engine | BFF | App |
| --- | --- | --- | --- |
| Status words | Writes `Final`, `Completed`, `Canceled`, `confirmed` | Computes `InProgress` from start time | Matches literal `InProgress`/`Completed`; defaults to Completed |
| Stat names | Writes `passing yards`, `RBI/runs_batted_in`, 2 dp strings | `STAT_NAME_BY_ID`, `NFL_STAT_MAP` | NBA label map; fixed NBA columns; re-cases server text |
| Pick wording | Passes through bet-engine `code` and `bet_line` strings | Parses `code` into "{team} {line}", "Anytime TD", milestones | Rebuilds player-prop labels; adds "Top Pick:" |
| Odds format | none | American for US, decimal otherwise; rounds to 2 dp | Formats again by region; recomputes slip totals |
| Decimals and units | Pre-formats values | `LEAGUE_DISPLAY`, decimal-place switches per league | `toFixed(2)`, xG `toFixed(1)` |
| Teams | Team names from dims | `TEAM_DETAILS` (128 rows: colour, code) | 127 bundled logos, 128-entry abbreviation map |
| Sections and positions | NFL top-N per position; EPL position groups | Roster section titles | Section order for MLB and NFL; EPL pitch layout |
| League visibility | none | `api_version` majors (v4 EPL, v5 NFL, v6 staged seasons) | Hardcoded league filter list; ignores `enabled_leagues` |
| Locks | none | Freemium registry, key-name strippers, `locks`, `counts` | Blur rules; reads `locks.topPicks` for edge picks |

| Layer | League-conditional code | Per-league tables |
| --- | --- | --- |
| Publish Engine | about 26 branches plus 65 column-presence checks | team and sport maps, 13 start-version overrides |
| BFF | 57 branches across 10 files | `LEAGUE_DISPLAY`, `TEAM_DETAILS`, `LEAGUE_PARSER_RULES`, `LEAGUE_TO_SPORT_KEY`, `SPORT_KEYS`, `INJ_TEAM_LEAGUES` |
| App | about 37 decision points (NBA 15, EPL 11, MLB 5, NFL 5, WNBA 1) | 10 maps, from `LEAGUES` to `TEAM_IMAGES` |

## Publish Engine (app-data)

The Publish Engine is a generic CDF-to-Cosmos pipeline wrapped around one 2,900-line library of hand-written, per-league transforms. It has no schema checks, no tests, and it swallows write errors. Evidence is from `dev` at `e1980822` (last pulled 8 Sep, before the NBA 2026 work landed); the findings below describe the legacy paths.

**How it runs.** Three router jobs fire on Delta table updates (MLB; WNBA; NFL and EPL) with a 60 s debounce. Each router reads a JSON-literal map from table to (transform, container, partition key) and fans out to a worker that runs the pipeline notebook once per container. Blue and green slots have separate containers; switching the BFF between them is manual.

**What it publishes.** Format A documents only: `schedule`, `game_prediction`, `player_predictions`, `player_top_picks`, `outcome` and `injuries` for MLB, WNBA, NFL and EPL. NBA publishes the NBA 2026 canonical documents in production; that code is newer than the checkout reviewed here, so it is not assessed below. The EPL 1.40 split and `game_edge_picks` are spec only.

**Gaps that block canonical documents and SDUI:**

- **No validation.** Documents are built from whichever columns exist (65 presence checks); the WNBA player document is a `select("*")` of its source table.
- **Silent loss.** A failed Cosmos write only increments a counter, and the checkpoint still advances.
- **Deletes ignored.** CDF deletes are discarded for every transform except `player_top_picks`, so a cancelled game stays in Cosmos; `delete_stale_epl_wltp_docs.py` patches this by hand.
- **No ordering.** Several CDF versions in one batch resolve last-write-wins; MLB patches and upserts the same document from two tables.
- **Display data in documents.** Status words, stat labels, 2 dp strings, NFL top-N per position and position buckets are written by the PE.
- **Not the only writer.** live-scores, seeders and a laptop injector also write to the same Cosmos account.
- **Contracts are prose.** Container specs disagree with the code on versions, doc types, ids and partition keys; there is no PE-to-BFF contract.

**Adding a league today** means editing the league detection and maps in the pipeline notebook, every relevant branch in the library, the JSON map, a router YAML, and the container fan-out in four places if a container is new. The first test is a dev deploy.

## BFF (mobile-server)

The BFF is already where most screen content is composed, which makes it the natural SDUI producer. But it has no response contracts outside v4 edge picks, and it carries three generations of mappers. Evidence is from `develop` at `95733012`.

**Routes the app uses.** `/v3/matches/{date}`, `/v3/match/{id}`, `/v3/matches/{date}/top-predictions`, `/my-picks-v2` (read, create, update, delete), `/config`, `/user/profile`, `/target/follow`, `/user/devices`, `/feedback`, `/man-vs-machine` and `/entitlement/activate`. The v1 and non-v3 routes remain and duplicate the v3 loaders almost line for line.

**Versioning is overloaded.** The `api_version` query major controls three things at once: which leagues are visible (v4 adds EPL, v5 adds NFL), response shape (v4 sectioned rosters, v5 split locks) and staged-season release (v6). An approved league registry with `minApiVersion` per league is documented but not built.

**Canonical NBA 2026 support has no single switch.** Documents are chosen by shape (`doc_type`, `schema_version`, id pattern, or `league === "nba"`), then `normaliseWltp` lifts nested canonical fields back onto legacy flat names. Legacy naming therefore becomes the long-term internal model, which is the opposite of the v3 data model's direction.

**Freemium is a strong base but enforced by key names.** Field groups per screen and a `show_*` policy are reusable for SDUI. Enforcement, though, is a denylist of key names plus hand-written mutations per endpoint, and new leagues are always locked for free users because `LEAGUE_TO_SPORT_KEY` is hardcoded. v4 edge picks shows the better pattern: named field groups, path-based redaction and `access.hidden` in the payload.

**Contracts.** Mappers return `any` and pass whole upstream objects through (`outcome`, `game`, `...pick`), so new Cosmos fields reach the app unreviewed. Only `/v4/edge-picks` has a zod schema, runtime validation and an exported JSON Schema.

**Edge Picks v4.** The route exists, but `EDGE_PICKS_SOURCE=live` always returns 503 because `loadLiveEdgePicks` throws; only mock scenarios work. Its schema also differs from the current v4 spec text: `edge_threshold` instead of `edge_holds_above`, and no `overlay_key`.

**Adding a league today** touches parser rules, `LEAGUE_DISPLAY` and two decimal switches, `TEAM_DETAILS`, stat and section maps, version gating in three files, five freemium places, the v4 sport enums, `enabled_leagues`, canonical markers, soccer `isEpl` branches, and seeds.

## App (mobile-app)

The app is a thick client: it trusts the BFF for data but not for presentation, so it re-labels, re-formats and recomputes much of what it receives. It is typed loosely against the BFF (`[key: string]: any`), so drift goes unnoticed. Evidence is from `main` at `ca9cf8f0` (Expo 57, React Native 0.86, React Query 5).

**Structure.** Four tabs (Home, Edge Picks, All Games, My Picks) inside a drawer, behind auth, email verification and onboarding stacks. Data fetching is React Query over one `apisauce` client with a Firebase ID token; `/config` is cached for 10 minutes.

**Server values it ignores or overrides:**

- `api_version` and `enabled_leagues` from `/config` (hardcoded `v6` and a fixed league list).
- `locks.upgrade.cta` (CTA copy is hardcoded), `subscription_features`, `freeTrialDays`.
- Pick descriptions (rebuilt from an NBA-only stat map) and `group.combinedProbability` (recomputed).

**Per-league code.** About 37 decision points, mostly NBA defaults and EPL specials, plus 10 maps every new league must extend. Logos are 127 bundled images and league icons are native assets, so a new league needs a store release. Unknown leagues silently fall back to NBA styling.

**Building blocks for SDUI.** Generic cards, tabs, filter bar, status badges, lock and blur primitives, and a player table that already renders columns from `predicted[]` and sections from the v4 section map. Lock rendering is already driven by `locked`, `locks` and `counts`. i18n uses typed keys with US and AU overlays. There is no component registry, and the full `EdgePick` v4 type exists but nothing imports it.

**Realtime.** The app has no Firebase Realtime Database or Remote Config package, so neither live scores nor edge overlays can reach it without a client change.

**Adding a league today** touches `leagues.ts`, `leagueConfig.ts`, two colour and glow maps (one duplicated), logo and abbreviation maps, the onboarding sports list, the `EdgePickSport` union, native and image assets, and usually player-table, section and label code.

## SDUI target

The BFF should decide **what** a screen shows (which sections, in what order, with which words and locks), and the app should decide **how** it looks. That keeps a new league, market or stat to a registry and BFF change, while the app stays a fast native renderer instead of a layout interpreter.

**Principles:**

1. **Content first, layout only where it earns it.** The payload names components and their order; the app owns spacing, typography, theme and animation. Where a layout choice changes the experience, the server picks from a small fixed set per component (for example `pick_list` as `list` or `carousel`). There is no generic layout DSL.
2. **Every domain value arrives as `{value, display}`.** The app never formats odds, probabilities, lines or stats. Live overlay values come with a format key (`odds_american`, `percent_1dp`) handled by a small, versioned formatter set in the app.
3. **Capability negotiation replaces league gating.** The app sends the component versions it supports; the BFF omits or downgrades unsupported sections. This retires the `api_version` majors that today gate EPL, NFL and staged seasons.
4. **Assets by key.** Logos, league icons and backgrounds are fetched by `asset_key` from Azure Storage behind Front Door, curated by the product owner, with the bundled set as fallback. A new league then needs no store release.
5. **Access per section and field group,** applied after composition, as v4 edge picks already does.
6. **One contract, generated.** zod in the BFF, exported JSON Schema, generated TypeScript in the app, contract tests in both CIs.

**Contract sketch** for game details (abridged):

```json
{
  "screen": "game_details", "contract_version": "1.0.0",
  "context": { "league": "nba", "region": "us", "event_id": "nba:40021717862" },
  "sections": [
    { "id": "scoreboard", "component": "scoreboard@1",
      "props": { "state": "scheduled", "starts_at": "2026-10-22T23:30:00.000Z",
        "competitors": [{ "slot": "c1", "name": "Boston Celtics", "asset_key": "team/nba/bos",
          "predicted": { "value": 118, "display": "118" },
          "win_probability": { "value": 0.62, "display": "62%" } }] } },
    { "id": "edge_picks", "component": "pick_list@1", "title": "Edge Picks",
      "props": { "items": [{ "pick_id": "nba:40021717862:spread:full:-:-:c1:-4.5|us|1",
        "label": "Celtics −4.5", "price": { "value": 1.909091, "display": "−110", "format": "odds_american" },
        "overlay_key": "ek_7f3a…" }] },
      "access": { "locked": true, "hidden": ["price", "edge"],
        "upgrade": { "label": "Unlock Edge Picks", "action": "open_paywall" } } },
    { "id": "players_c1", "component": "stat_table@1", "title": "Celtics",
      "props": { "columns": [{ "key": "basketball.points", "label": "PTS", "tooltip": "Points" }], "rows": [] } }
  ],
  "actions": { "open_paywall": { "type": "native", "route": "Paywall" } }
}
```

**Component catalogue** (about 15 covers every screen today):

| Component | Used on | Replaces in the app |
| --- | --- | --- |
| `match_card` | All Games, Home | GameCard, top-pick gold design, EPL draw and xG branches |
| `scoreboard` | Game details | GameTeamsDisplay, ScoreBoard, team\_2-left ordering |
| `probability_bar` | cards, details | ProbabilityScoreBoard and its leader colouring |
| `pick_card` | Edge Picks, details | TopPickCard, GamePick, player-prop label builder |
| `pick_list` | Edge Picks, details | GamePicksList, Top vs Edge variants |
| `stat_table` | details | GamePlayerTable, NBA fixed columns, MLB and NFL section order |
| `lineup_pitch` | details (soccer) | `epl/StartingLineUp` |
| `injury_table` | details | PlayerTable injuries |
| `filter_bar` | All Games, Edge Picks | LeagueFilterBar with its hardcoded list |
| `section_header`, `empty_state`, `disclaimer` | all | i18n literals per screen |
| `promo_banner`, `locked_placeholder` | all | PromoBanner, UnlockPickCard, blur counts |
| `metric_tile` | Home, track record | the unmounted summary and ROI cards |

**Who owns what:**

| Layer | Owns | Must not own |
| --- | --- | --- |
| Bet engines and Publish Engine | Typed data in v3 canonical documents; ids; lifecycle | Labels, status words, formatted strings, product grouping rules |
| Registry (`xo-contracts`) | Leagues, sport profiles, stats, markets, messages, units, asset keys, component versions; owned by platform | Per-user state |
| BFF | Screen composition, wording from the registry, locale and region formatting, access, actions, validation | Raw document pass-through |
| App | Rendering, layout, theme, navigation shell, purchase, slip editing, overlay merge, analytics dispatch | Domain formatting, league branches, recomputed values |

Stays native: auth and onboarding forms, the paywall and Qonversion purchase, stake-slip and My Picks editing, the realtime overlay merge, and the tab shell (server-driven tabs can come later).

### Test case: college football and college basketball

Yes for the everyday product. With the target design in place, both leagues' game cards, game details, Edge Picks, My Picks and live overlays could ship with no app release. Two things still need one: brackets for March Madness and the College Football Playoff, and any new kind of screen the catalogue does not foresee. College basketball (NCAAB) is the easier first test, because it reuses the basketball sport profile and stat keys. It is the natural candidate for Gate C.

That holds only if Phase 2 builds six things the current app lacks:

1. **Open keys in the client contract.** League, sport, stat and market keys are strings the app passes through, never closed enums. Today a league is a TypeScript union (`EdgePickSport`, `LEAGUES`), so a new value is an app change by construction.
2. **Server-supplied navigation data.** The league filter, its icons, the onboarding sports tiles and push topics all come from `/config` or a screen payload, not from bundled lists.
3. **Annotation slots on components.** `match_card` and `scoreboard` carry optional `annotations` (rank, seed, record, conference) and display lines for names, so "#5 Ohio State" and long school names need no new component. Today the app splits names at the first space.
4. **Paging and grouping inside sections.** A busy Saturday has dozens of FBS games and well over 100 college basketball games, so sections need cursors and server-chosen grouping (Top 25, by conference).
5. **Period and clock from the sport profile.** College basketball plays two halves; live text such as "2nd Half 12:40" must arrive composed, with format keys for overlay values.
6. **Colour and art by registry.** Card glow and backgrounds become registry colours and `asset_key` images, replacing the per-league PNGs, otherwise new leagues fall back to NBA styling.

| Surface | Without an app release? | What makes it work |
| --- | --- | --- |
| All Games cards | Yes | `match_card` with annotations; server matchup text ("vs" at neutral sites); paged sections |
| League and conference filters | Yes | Filter options in the payload |
| Game details: scoreboard, picks, player tables | Yes | Basketball and football profiles, registry stat labels, `stat_table` columns from the payload |
| Injuries | Yes, if data exists | `injury_table`; college injury data may be thinner than the NFL's |
| Edge Picks and My Picks | Yes | `pick_card` labels and prices from the server; picks the user may not bet on are omitted server-side |
| Live overlays | Yes | League-neutral live node and format keys |
| Team logos | Yes, after curation | About 135 FBS and 360 Division I basketball teams by `asset_key`; the product owner curates and confirms logo licensing |
| Onboarding tile, push opt-in | Yes | Sports list and topics from `/config` |
| Brackets (March Madness, CFP) | No | A new `bracket` component |
| Conference standings | Only with a generic screen route | `stat_table` inside a server-defined screen the app can open by id |

SDUI removes the app work, not the rest of it. A college league still needs feeds, models and bet-engine output, NBA 2026 or v3 canonical documents from the Publish Engine, about 500 team entries in the registry, and a compliance review, because some US states restrict betting on college games or on college player props. That eligibility check belongs in the BFF, which can drop ineligible picks by the user's region and state claims without the app knowing why.

## Edge Picks redesign fit

Edge Picks v4 should be the SDUI pilot: it is the one contract that already composes labels server-side, declares field groups and access, and validates at runtime. The work left is wiring, not design. The data model it needs is in XO Canonical Data Model v3 — Proposal.

| Piece | State today | Needed for the pilot |
| --- | --- | --- |
| BFF `/v4/edge-picks` | Mock fixtures only; live adapter throws | Live adapter reading v3 `pick` documents (entry, current, status, result) |
| Contract | zod 4.0.0, but `edge_threshold` and no `overlay_key` versus the spec | Align with the spec, then wrap picks as `pick_card@1` items |
| App | `EdgePick` type defined, never imported; tab still reads `/v3/.../top-predictions` | Render the payload through the component catalogue |
| Edge monitor (live-odds) | NFL only, dev only; writes RTDB `/edgePicks`, `/edgePickStatus` and a Delta history | All pilot sports; `next_update_due` written; ids match `pick_id` |
| Overlay delivery | No RTDB client in the app; no RTDB security rules | RTDB client, per-pick read rules, opaque `overlay_key` |
| Current price into Cosmos | History table has no Publish Engine reader | PE maps history to `current` observations |
| Producer documents | NBA on NBA 2026 canonical documents; other leagues on Format A | v3 canonical documents for the pilot leagues |

The v3 model also removes most of the app's league code on this screen: `selection_key` and registry labels replace the client's player-prop label builder, `{value, display}` prices replace region formatting, and `edge_prob` and `ev` arrive computed, so the card never derives them.

### Live overlays: Firebase RTDB or a BFF stream

Stay on Firebase RTDB for the Edge Picks pilot. In the scenarios below it costs 3 to 9 times less than a managed Azure stream, needs no new infrastructure, and its writers (live-scores and the edge monitor) already exist. Its weak point is access control, which custom claims and split nodes fix. Revisit when overlays become per-user.

A BFF stream cannot run through Front Door itself: Front Door [does not support server-sent events](https://learn.microsoft.com/en-us/azure/frontdoor/standard-premium/websocket) and caps WebSockets at 3,000 concurrent connections per profile and two hours per connection. The realistic Azure option is therefore Azure Web PubSub (or SignalR Service), fed by the BFF and the edge monitor, with the app connecting to its endpoint.

|  | Firebase RTDB | Azure Web PubSub |
| --- | --- | --- |
| Scale ceiling | 200,000 simultaneous connections per database; more by adding databases | 1,000 connections per unit; up to 100 units on Standard, 1,000 on Premium |
| Cost model | $1 per GB downloaded after 360 MB a day free, including protocol and TLS overhead (about 3.5 KB per handshake); connections are free | About $1.61 per unit a day, sized to peak connections at 80% use; 1 million 2 KB outbound messages per unit a day free, then about $1 per million; broadcasts count per recipient |
| Access control | Security rules on the Firebase ID token; tier must be a custom claim the BFF sets from entitlements, refreshed with the token (up to 1 hour) | The BFF issues each user a client token listing the groups they may join; entitlement is checked at issue time |
| Hiding premium fields | Not per field: premium fields need their own node with a tier rule | Premium fields go to a premium group |
| Built today | live-scores and the edge monitor write RTDB | Nothing; both writers would need to publish to it |
| App client | `@react-native-firebase/database` (not yet installed); reconnect and offline cache included | WebSocket client; reconnect and resume handled in the app or client SDK |
| Cloud | Google, beside Azure | Azure, with the BFF and Cosmos |

| Daily active users | Peak concurrent (10%) | RTDB per month | Web PubSub per month |
| --- | --- | --- | --- |
| 10,000 | 1,000 | about $11 | about $98 |
| 50,000 | 5,000 | about $97 | about $405 |
| 200,000 | 20,000 | about $419 | about $1,563 |

Assumptions, to replace with real analytics: each user is connected 15 minutes a day across 3 sessions, watching 20 picks that update every 5 minutes and one live game that updates every 15 seconds, with 300 to 400 byte updates. RTDB cost scales with bytes delivered; Web PubSub cost mostly with peak connections. Latency does not decide this: both deliver in under a second, and the producers' cadence (15 seconds to 3 hours) dominates.

**If RTDB is kept:**

- Add the database client behind an app-side `OverlaySource` interface, so the transport can change later without touching components.
- The BFF sets a tier custom claim on every entitlement change; premium fields live in separate nodes; listing is denied; the BFF hands out an opaque `overlay_key`.
- Listen only to picks on screen and detach on blur; this is the main cost lever.
- Set a Firebase budget alert on downloads.

Web PubSub becomes the better fit when overlays are per-user (open positions, My Picks P&L), or when running one cloud is worth the higher cost.

Prices from [Firebase pricing](https://firebase.google.com/pricing), [Realtime Database billing](https://firebase.google.com/docs/database/usage/billing) and the [Web PubSub billing model](https://learn.microsoft.com/th-th/azure/azure-web-pubsub/concept-billing-model). Microsoft's [pricing page](https://azure.microsoft.com/en-us/pricing/details/web-pubsub/) did not render dollar amounts, so the Web PubSub unit and message prices come from a [third-party summary](https://epcgroup.net/azure-web-pubsub-pricing-and-features-real-time-messaging/) and should be checked in the Azure calculator.

## Migration path

&#91;embedded content: migration roadmap · 4 phases, 3 gates\]

Each phase ships value on its own. Phase 0 removes the defects and gives every route a contract, so the later phases can move logic between layers without silent breakage. Phase 1 proves the pattern on the screen that is being redesigned anyway. Gate C is the test that matters for scale: a new league lands through registry and BFF changes alone. No dates are set; phase lengths depend on team capacity.

## Risks and open questions

Thirteen defects surfaced while reading the code; none was confirmed by running it. The first five affect users or data today and are worth fixing before any SDUI work.

| Area | Defect | Where | Severity |
| --- | --- | --- | --- |
| App | Entitlement-invalidate key ships in the app bundle (`EXPO_PUBLIC_`) and calls an internal route | `services/entitlement/entitlement.service.ts:68` | High |
| App | Game calendar ends 31 Dec 2026 | `components/SwipeableWeekCalendar.tsx:30-31` | High |
| Publish Engine | Failed Cosmos writes are counted, then the checkpoint advances, so the data is lost | `generic_cdf_to_cosmos_pipeline` cell 4 | High |
| Publish Engine | CDF deletes ignored, so cancelled games and withdrawn picks stay in Cosmos | same, cell 4 L16 | High |
| live-odds | Defaults to the `tst_nfl` catalog, which serves production, when `DATABRICKS_CATALOG` is unset | `nfl/mappers/databricks_client.py:41` | High |
| App | My Picks shows a void result (2) as a win and a missing one as a loss | `components/MyPicks/MyPicksItem.tsx:101-103` | Medium |
| App | The game's outcome overrides each top pick's own result on details | `GamePicksList.tsx:65` | Medium |
| App | A missing status renders as Completed | `GameCard.tsx:68` | Medium |
| App | Edge-pick blur reads `locks.topPicks`, not `locks.edgePicks` | `services/contentLocks/resolveLocks.ts:53` | Medium |
| BFF | Team colour lookup is not lowercased, so list cards get the default colour | `lib/match/map-match-list-detail.ts:29-30` | Medium |
| Publish Engine | A rescheduled game writes a second schedule document (partition is `/game_date`) | `transformations_library.py` `transform_game_data` | Medium |
| BFF | Placeholder push copy "We went 4/6 today, earning a profit of $X" | `functions/service-bus-push-events.ts:261` | Low |
| App | Share text pairs team\_2's code with team\_1's actual (not predicted) score | `GameCard.tsx:158-166` | Low |

**Risks to the plan:**

- **Old app versions.** SDUI only reaches users on new builds. The force-update gate (`minimum_app_version_required`) exists and should be part of each phase gate.
- **Over-reach.** A generic layout DSL would trade league code for an interpreter that is harder to test. The catalogue approach keeps components native and typed.
- **Overlay security.** No RTDB rules exist in any repo, and overlay paths are predictable. Freemium fields could leak through live nodes.

**Decided on 16 Oct:**

- Content-driven SDUI, with server-chosen layout only where it earns its place.
- Platform owns the registry.
- The product owner curates team and league assets, stored in Azure Storage and served through Front Door.
- Still open: overlay transport. The recommendation is Firebase RTDB for the pilot (see Live overlays), to be confirmed against real daily-active and session numbers.

## Sources

Code was read from local checkouts on 16 Oct 2026; line numbers refer to these commits.

| Repo | Branch and commit | Main files read |
| --- | --- | --- |
| mobile-app | `main` `ca9cf8f0` | 438 source files under `app/`: navigators, screens, services, hooks, utils, constants, theme, i18n |
| mobile-server | `develop` `95733012` | all non-test `src/` files, `script/`, `docs/nba-2026-bff-handover.md`, `docs/EPL/api-alignment-and-backward-compat.md` |
| app-data | `dev` `e1980822` | `transformations_library.py`, `generic_cdf_to_cosmos_pipeline.ipynb`, `build_transformation_map.ipynb`, router and worker jobs, `databricks.yml`, container specs |
| live-scores | `origin/dev` | `shared/`, per-league `function_app.py`, `config.py`, mappers, `docs/PROJECT_APPDEV.md` |
| live-odds | `dev` | `nfl/function_app.py`, `shared/edge_status.py`, `shared/firebase_writer.py`, mappers |
| data\_ingestion, bet\_odds\_lib, apis, infra | working trees | READMEs, endpoint configs, schedules |

Specifications: Edge Picks v4 contract (`xo-scratchpad/edgepicks-redesign/specs.md`), NBA 2026 specs (`reqs/nba/specs/`), and XO Canonical Data Model v3 — Proposal.
