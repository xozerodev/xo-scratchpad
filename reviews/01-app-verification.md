# App verification — mobile-app evidence behind the SDUI proposal

Reviewer: `app-verifier` (task-1) · 17 Oct 2026 · scope: `/mnt/devel/xosports/github/mobile-app` only, read-only.
Source under test: `xo-scratchpad/SDUI/sdui-proposal.md` (app sections: "Screen by screen", "Where display
decisions live today", "App (mobile-app)", app rows of "Risks and open questions", "Building blocks for SDUI",
"Test case").

## Branch and commit used

**Primary commit inspected: `main` @ `ca9cf8f0` (`ca9cf8f0808ea654d91a2d310798a348776e3fc7`, 14 Oct 2026, "Merge
pull request #514 from XOSports-ai/merge_all_changes_to_main") — the commit the proposal cites.** It is an
ancestor of `origin/main` only (20 commits behind main's tip `137f2f61`), **not** of `origin/develop`.

Because the sandbox makes `github/mobile-app` read-only, `git fetch origin` there fails
(`cannot open '.git/FETCH_HEAD': Read-only file system`). Method actually used:

| Evidence source | How obtained | What it settles |
| --- | --- | --- |
| Local objects at the cited commit | Bare repo in the scratchpad fetched with `git fetch origin refs/heads/main refs/heads/develop`, `objects/info/alternates` → the existing clone's object store; all `git show`/`git grep`/`git ls-tree` below ran against **that** store | every `file:line` in the claim and defect tables, at `ca9cf8f0` |
| Remote heads (no writes) | `git ls-remote --heads` | `main = 137f2f61`, `develop = 0e4f686d` (16 Oct 2026) — matches the proposal's date |
| GitHub REST (read-only PAT) | `/repos/XOSports-ai/mobile-app`, `/branches/{main,develop}`, `/tags`, `/releases`, `/deployments`, `/actions/workflows` | default branch, protection, tags/releases |
| Drift check | Extracted `main` tip and `develop` tip trees and diffed against `ca9cf8f0` | branch robustness of each finding |

### Which branch ships? (needed before trusting the citations)

- The repo contains **no release automation that binds a store build to a branch**: the only workflow is
  `.github/workflows/pull-request.yml` (runs `yarn test:coverage` on PRs to `main` and `develop`); there is no
  fastlane directory, no `Gemfile`, no `eas.json` `channel`, and the production EAS profile is empty
  (`eas.json` "production": {}). Builds are run by hand from the README's `yarn build:*:prod` scripts, from
  whatever branch the operator has checked out.
- Both branches are **protected**, both receive the same feature merges, and both carry release tags for the
  same iOS version: `main/1.1.66` and `develop/1.1.66` (both created 10 Sep 2026, "Released version IOS:
  1.1.66"); the only GitHub *Release* object targets `develop` (`develop/1.1.68-before-mvm`, 14 Oct 2026).
  iOS `MARKETING_VERSION` is `1.1.68` on **both** branches; Android diverges — `versionName 1.1.94 /
  versionCode 124` on `main`, `1.1.114 / 144` on `develop` (`android/app/build.gradle`).
- `develop` is the GitHub **default branch** (`/repos` → `default_branch: develop`); `origin/HEAD` →
  `refs/heads/develop`.

**Conclusion: "main is the shipping branch" is not established by the repo — it is one of two release-tagged
lines, and the default branch (`develop`) carries a higher Android version code.** The proposal's citations are
therefore valid *at the cited commit*, but not uniquely "the shipping branch". This does **not** sink the
findings: the seven defect files and the two central hardcodings (`AppConfigContext.tsx`,
`constants/leagueConfig.ts`) are **byte-identical** at `ca9cf8f0`, at `main` tip `137f2f61`, and at `develop`
tip `0e4f686d` (verified by `diff` of the nine load-bearing files listed in the method notes). Where a claim is
only true on one line, the table says so.

## Claim table

Verdicts: **Confirmed** / **Partly** / **Refuted** / **Unverifiable**. All `file:line` are repo-relative at
`ca9cf8f0` unless the row says otherwise.

### Structure, stack, plumbing

| Claim (proposal §) | Verdict | Evidence | Note |
| --- | --- | --- | --- |
| Expo 57, React Native 0.86, React Query 5 (§App) | Confirmed | `package.json`: `expo ^57.0.23`, `react-native 0.86.3`, `@tanstack/react-query ^5.90.12` | Also `apisauce 3.1.1` |
| Four tabs (Home, Edge Picks, All Games, My Picks) inside a drawer, behind auth, email verification and onboarding stacks | Confirmed | `app/navigators/TabsNavigator.tsx:230-241` (4 `Tab.Screen`; ROI commented out at :242); `app/navigators/AppNavigator.tsx:146-148` (`Drawer.Screen TabsNavigation`), `:97-105` (Login/SignUp/…), `:223` VerifyEmail, `:243` Onboarding | Tab labels "Home"/"Edge Picks"/"All Games"/"My Picks" |
| Data fetching is React Query over **one** apisauce client with a Firebase ID token | Confirmed | `app/services/api/index.ts:83-90` (single `apiSauce` instance), imported by every content service; `Bearer ${authToken}` per request e.g. `app/services/games/games.service.ts:30`; auth from `@react-native-firebase/auth` | Token passed per call, not an interceptor |
| `/config` is cached for 10 minutes | Confirmed | `app/hooks/useAppConfig.ts:48` (`APP_CONFIG_STALE_TIME_MS = 10*60*1000`), `:87-90` (`refetchOnMount:false`, `refetchOnWindowFocus:false`, `refetchOnReconnect:true`); `app/context/AppConfigContext.tsx:28-38` (AppState re-invalidate after stale window) | Default query staleTime is 60 s (`app/app.tsx:258-266`) |
| "438 source files under `app/`" (§Sources) | **Partly** | `git ls-tree -r ca9cf8f0 -- app` = **513** files: 511 `.ts/.tsx`, 2 `.md`; 437 non-test `.ts/.tsx` (206 tsx, 231 ts) | Method: `git ls-tree -r` + extension/test-path filters. 438 matches no natural definition; it is ±1 of "non-test source files" (439 incl. non-code, 437 code-only) — order of magnitude right, exact figure unsupported |
| App is typed loosely against the BFF (`[key: string]: any`) | Confirmed | 18 `[key: string]: any` index signatures in 12 non-test files — incl. `app/services/games/type.ts`, `app/services/my-picks-v2/type.ts:18-29`, `app/services/topPredictions/type.ts`, `app/types/game.type.ts`; 61 other `: any`; mappings spread upstream objects unchanged, e.g. `app/services/topPredictions/transformer.ts:31` (`...apiData`) | No runtime response validation library in `package.json` (no zod/yup/ajv/io-ts) |
| Player table already renders columns from `predicted[]` and sections from the v4 section map; `metadata.playerstatkeys` present | Confirmed | `app/screens/GameScreen/useGamePlayerTableLayout.ts:72-80` (headers from `list[0].predicted[]`); `app/screens/GameScreen/_components/shared/playerSections.ts:67-78` (v4 keyed section map) and `:80-105` (v3 flat array); `app/screens/GameScreen/gameDetailsBlur.ts:23-26,40` (`metadata.playerstatkeys`/`extraPlayerstatkeys` size the blur placeholder rows) | Reusable as-is |
| Lock rendering already driven by `locked`, `locks` and `counts` | Confirmed | `app/services/contentLocks/resolveLocks.ts:40-56` (master gate `locked === true`, fail-closed defaults), `app/screens/GameScreen/gameDetailsBlur.ts:19-21` (`resolveBlurCount(apiCount ?? fallback)`), `:62-70` (`resolveSectionPicks`) | |
| i18n uses typed keys with US and AU overlays | Confirmed | `app/i18n/index.ts:16-24` (`resources = {ar, en, ko, es, fr, hi, ja, us, au}`, region files fall back to `en`), `Translations` type exported from `app/i18n/en.ts` and used as `TxKeyPath` | 9 locales |
| "There is no component registry" | Confirmed (absence) | No registry/module map anywhere; screens import concrete components (`app/screens/GameScreen/GameCard.tsx:44-47` lazily requires `GameTeamsDisplay`) | Stated as a negative result of a repo-wide search, not a positive finding |
| "The full `EdgePick` v4 type exists but nothing imports it" (§Building blocks; §Edge Picks redesign fit) | **Refuted** | `git grep EdgePick ca9cf8f0` finds only `EdgePicksTypeFilter` (`app/constants/constants.ts:47`), `blurEdgePicks` and i18n strings. There is **no `EdgePick` type, no `EdgePickSport`, no `edge_threshold`/`overlay_key`/`field_groups` text anywhere in the repo** — also absent at `main` tip and `develop` tip | The v4 contract has no client type at all, so "exists but unused" overstates readiness; the pilot's first app task is writing the type, not importing it |
| No `@react-native-firebase/database`, no Remote Config package (§Realtime) | Confirmed | `package.json` firebase set = `app, auth, analytics, crashlytics, messaging` only | Neither live scores nor edge overlays can reach the app without a client change |

### Server values ignored or overridden

| Claim | Verdict | Evidence | Note |
| --- | --- | --- | --- |
| `api_version` from `/config` ignored; hardcoded `v6` | Confirmed | `app/context/AppConfigContext.tsx:44` `const apiVersion = DEFAULT_API_VERSION` (value `"v6"`, `app/hooks/useAppConfig.ts:42`), consumed by services via `useAppConfigContext()` (`app/services/games/games.hook.ts:23`, `game.hook.ts:25`, `topPredictions.hook.ts:36`) | `resolveApiVersion()` exists (`useAppConfig.ts:50-55`) but is called **nowhere** — the plumbing is there, the provider discards the server value |
| `enabled_leagues` ignored; hardcoded league filter list | Confirmed | `app/context/AppConfigContext.tsx:49` `[...LEAGUE_FILTER_LEAGUES]`; the list is `All, NBA, WNBA, MLB, EPL, NFL` (`app/constants/leagueConfig.ts:11-19`); consumed at `app/screens/GameScreen/GamesScreen.tsx:43,193` and `app/screens/TopPicksScreen/useTopPicksScreen.ts:19,131` | `enabled_leagues` appears only as an optional type field (`useAppConfig.ts:39`) — never read |
| Every content screen reads `/v3…?api_version=v6`; My Picks is pinned to `v3` | Confirmed | `APIs.gamesV3 = /v3/matches/:date` (`app/services/api/index.ts:99`) used at `games.service.ts:24-27`; `gameV3` (`:101`) at `game.service.ts:21-27`; `topPredictionsV3` (`:97`) at `toppicks.service.ts:39-45`; `app/services/myPicks/myPicks.service.ts:25` `?offset=…&api_version=v3` | v1 routes still exist alongside (`api/index.ts:96-101`) |
| `locks.upgrade.cta` ignored (CTA copy hardcoded) | Confirmed | `app/services/contentLocks/resolveLocks.ts:55` resolves `upgradeCta` but **nothing consumes it** (repo-wide grep: only the type at `:19` and the definition); the UI copy comes from i18n literals (`app/i18n/en.ts:654-658`) | The server *can* already send it; the client drops it |
| `subscription_features` and `freeTrialDays` ignored | Confirmed | Declared only at `app/hooks/useAppConfig.ts:29,31`; zero other references. Paywall features come from the bundled list `app/constants/subscriptionFeatures.ts:2-8` (`unlimitedHighEdgePicks, playerProjections, …`) | |
| Pick descriptions rebuilt from an NBA-only stat map | Confirmed | `app/utils/playerPropLabel.ts:1-11` (`pts/reb/ast/threes/stl/blk/pra/pr/pa`), `:105-123` (`formatPlayerPropPickLabel` returns `null` for any stat not in that map); callers `app/services/topPredictions/transformer.ts:40`, `app/screens/GameScreen/_components/GamePick.tsx:130`, `_components/PickDetails.tsx:15` | Generic fallbacks exist for *projection titles* (`:83-103`) but not for player-prop labels |
| `group.combinedProbability` recomputed | Confirmed | Server field on the API type (`my-picks-v2/type.ts:27`) and on the view type (`:78`); `app/screens/MyPicksScreen/components/PickGroupCard.tsx:64-67` recomputes it from `pick.probability`; totals via `getPickGroupAmounts` (`components/pickGroupAmounts.ts:11-21`, which does prefer saved `totalOdds`/`returnAmount`) | |
| Stake slip computes combined probability, total odds and return in the app | Confirmed | `app/context/PickSelectionContext.tsx:147-159` (product of `probability` and `decimal_odds`); `app/components/StakeModal/StakeSummary.tsx:16-18` (`(p*100).toFixed(2)`, `formatDecimalOddsByRegion`, `$ (totalOdds*stake).toFixed(2)`) | |
| Edge Picks: wager = stake × bet size; projection re-titled | Confirmed | `app/screens/TopPicksScreen/_components/TopPickCard.tsx:98-103` (`betStake * betSize`); `:251` `formatProjectionTitle(pick?.projection)` → `playerPropLabel.ts:83-103` | |
| Edge Picks: "edge and bookmaker never shown" | Confirmed | No edge/EV/bookmaker-name field is rendered in `app/screens/TopPicksScreen/**` (grep finds only the type-filter testID and `resolveBookmaker` used for prices) | |
| Odds formatted by region (`+150` / `$2.50`) | Confirmed | `app/utils/odds.ts:32-46`: `AMERICAN_ODDS_REGIONS = ["US"]`, `formatAmericanOdds` → `+150`, decimal path → `$2.50`; used at `TeamDisplay.tsx:68-71`, `StakeSummary.tsx:17`, `MyPicksItem.tsx:53` | |
| "Top Pick:" prefix added in the app | Confirmed | `app/screens/GameScreen/_components/shared/TopPickHighlightBanner.tsx:44` — literal `` `Top Pick: ${description}` `` | |
| Logos come from bundled images by `imageCode`; `team_2` drawn on the left | Confirmed | `app/components/TeamLogo.tsx:41-55` (`getTeamImage(imageCode)`, `awayImage ← teamTwoImageCode`, `homeImage ← teamOneImageCode`) + styles `:92-107` (away `left:0, zIndex:1`; home `left:14, top:12, zIndex:2`); list card ordering `app/screens/GameScreen/_components/shared/GameTeamsDisplay.tsx:76-106` renders `team2` first, `team1` second, and `FinalScoreBoard scoreLeft=team2.score` (`:115-120`) | Naming is inverted vs the share text (see defect D7): `TeamLogo` calls *team_1* "home" while `GameCard` calls team_1 "away" |
| Status defaults to Completed when missing | Confirmed | `app/screens/GameScreen/GameCard.tsx:68` default parameter `status = "Completed"` | Defect D5 |
| Details read `game_status`, the list reads `status` | Confirmed | Details: `app/services/game/game-type.ts:22`, `app/screens/GameScreen/useGameDetailsBodyModel.ts:33`; list: `GameListCard.status` (`app/types/game.type.ts:85`, alongside `game_status` at `:78`) passed through untouched (`games.service.ts:38` returns `data.matches`) | |
| NBA columns fixed to PTS REB AST STL BLK | Confirmed | `app/screens/GameScreen/useGamePlayerTableLayout.ts:24` (`NBA_TABLE_STATS = ["pts","reb","ast","stl","blk"]`), `:68-70` (headers), `:84-91` (row values looked up by stat key); also `app/services/games/transformer.ts:52,71` hard-look-up `stat === "PTS"` | |
| MLB and NFL section order set in the app; EPL pitch layout | Confirmed | `playerSections.ts:29-40` (MLB pitcher→batter, NFL QB→RB→WR→TE priorities), `:75-76,87-96`; EPL lineup `app/screens/GameScreen/_components/epl/StartingLineUp.tsx` | |
| Injury date format by region | Confirmed | `app/screens/GameScreen/_components/PlayerTable.tsx:29,45` (`getDateFormatForRegion(region)`) | |
| Man vs Machine card fully bundled, including machine score 110–118 | Confirmed | `app/constants/manVsMachine.ts:24-27` `MACHINE_PREDICTION = {away:"110", home:"118"}`; used at `app/context/ManVsMachineContext.tsx:242-243,310-311`; card `app/components/ManVsMachine/ManVsMachineCard.tsx`, mounted on Home (`app/screens/HomeScreen/HomeScreen.tsx:14`) | |
| Savings % computed in the app | Confirmed | `app/utils/paywallPricingPlans.ts:73-84` (`getSavingsPercent`, `getAnnualSavingsPercent`), `:247-282` (`savePercent` i18n string) | |
| Not shown anywhere: `/summary` (screens unmounted), `/v4/edge-picks`, Firebase overlays | Confirmed | ROI tab commented out (`TabsNavigator.tsx:27,242`); `useSummary` exists (`app/services/summary/summary.hook.ts:7`) but its only consumers `HowWereTracking.tsx` and `XOSportsSummary.tsx` are **imported by nothing** (repo-wide grep) so the query never runs; no `/v4` path in `app/services/api/index.ts`; no RTDB package | |
| "Game details: `edgePicks[]` (a copy of `picks`)" | Unverifiable (app side) | App type `app/services/game/game-type.ts:29` (`edgePicks?: MatchResponsePick[]`), consumed at `useGameDetailsBodyModel.ts:78` | Whether the BFF sends a copy of `picks` is a mobile-server fact; not checkable in this repo |

### Counts and league coupling

| Claim | Verdict | Evidence / how counted | Note |
| --- | --- | --- | --- |
| "about 37 decision points (NBA 15, EPL 11, MLB 5, NFL 5, WNBA 1)" | **Partly** | My count, method below, gives **66 league-conditional sites** (24 `PlayerTableStatColumn.tsx`, 10 `PlayerTableNameColumn.tsx`, 9 `useGamePlayerTableLayout.ts`, 5 `playerSections.ts`, 3 each `GameScoreDisplay.tsx`/`GamePlayerTable.tsx`/`gameInsightsTitles.ts`, 2 each `GameTeamsDisplay.tsx`/`PredictionOutcomeIndicator.tsx`, 1 each `ScoreBoard.tsx`/`gameInsightsLineup.ts`/`GamesScreen.tsx`/`AndroidGlassCard.tsx`, plus the NBA default fallbacks), or **≈45** excluding conditionals that only pick a style | Method: enumerate non-test `app/**` lines that contain a league guard (`isEpl`, `isNba`, `isNfl`, `isMlb`, `isWnba`, `LEAGUES.X`, `toLeagueCode(LEAGUES.X)`) *and* drive a branch (ternary/`&&`/`if`/`===`/`??`) or a league-keyed lookup, excluding static map entries, prop declarations, memo dep arrays and prop threading. Direction confirmed (branching is real, concentrated in player-table + EPL specials); the stated total **understates** it and the per-league split is not reproducible — by guard token it is EPL-heavy (EPL 39 flag occurrences, NBA 13, NFL 4, MLB 3), the opposite of the proposal's NBA-first split |
| "10 maps, from `LEAGUES` to `TEAM_IMAGES`" | Confirmed (ballpark) | I enumerate **11** league/team-keyed tables: `LEAGUES` (`constants/leagues.ts:1-9`); `SPORTS`/`SPORTS_ORDER_BY_REGION`/`SPORTS_BY_ID` (`constants/sports.ts:38-41,43-89`); `LEAGUE_CONFIGS` (`constants/leagueConfig.ts:21-46`); `GAME_BG_BY_LEAGUE` (`:56-62`); league colours (`theme/colors.ts:102-108`); `GLASS_CARD_COLOR_BY_LEAGUE` (`:113-124`); `GLASS_CARD_GLOW_BY_LEAGUE` (`:127-133`); `TEAM_IMAGES` (`utils/teamImages.ts:3`); `TEAM_TO_ABBREVIATION` (`utils/teamAbbreviation.ts:1`); `PLAYER_PROP_STAT_LABELS`/`PROJECTION_CODE_LABELS` (`utils/playerPropLabel.ts:1-31`); `MLB_SECTION_PRIORITY`/`NFL_SECTION_PRIORITY` (`playerSections.ts:29-40`) | Membership is method-dependent (10–12); "10" is defensible |
| "127 bundled logos" | Confirmed | `TEAM_IMAGES` has exactly **127** entries and **127 unique** `require()` paths (NBA 30, MLB 30, NFL 32, WNBA 15, EPL 20). Method: count map-entry lines and unique `require("@assets/…")` strings in `app/utils/teamImages.ts` | Assets are binary-bundled (no CDN) |
| "128-entry abbreviation map" | Confirmed | `TEAM_TO_ABBREVIATION` has exactly **128** quoted keys (128 unique; 86 distinct abbreviations → alias rows such as `nba_los angeles clippers`/`nba_la clippers` → `LAC`). Method: count lines matching `^\s*"<key>":` in `app/utils/teamAbbreviation.ts` | |
| Unknown leagues silently fall back to NBA styling | Confirmed | `leagueConfig.ts:50-52` (`getLeagueConfig` → `LEAGUE_CONFIGS[DEFAULT_LEAGUE]`, NBA), `:64-66` (bg → `basketball-player.png`), `theme/colors.ts:135` (`DEFAULT_GLASS_CARD_GLOW` = NBA), `components/Containers/AndroidGlassCard.tsx:15` (`DEFAULT_GLOW` = NBA) | |
| "Adding a league touches `leagues.ts`, `leagueConfig.ts`, two colour and glow maps (one duplicated), logo and abbreviation maps, the onboarding sports list, the `EdgePickSport` union, native and image assets, player-table/section/label code" | **Partly** | All items confirmed — `constants/leagues.ts:1-15`, `constants/leagueConfig.ts`, `theme/colors.ts` colour map **duplicated** in `components/Containers/AndroidGlassCard.tsx:7-13` vs `colors.ts:127-133`, `utils/teamImages.ts`, `utils/teamAbbreviation.ts`, onboarding list `constants/sports.ts:43-87` (used by `screens/OnboardingScreen/components/InterestsStep.tsx`), bundled SVG league icons (`sports.ts:3-9`), player-table/section/label code above — **except `EdgePickSport`, which does not exist** | The closed-union claim holds via `LEAGUES`/`SportKey` (`leagues.ts:11-12`, `sports.ts:11`), not `EdgePickSport` |
| Test case: "a league is a TypeScript union (`EdgePickSport`, `LEAGUES`)" | **Partly / Refuted as written** | `LEAGUES` and `SportKey` are closed unions (`constants/leagues.ts:1-12`, `constants/sports.ts:11`); `EdgePickSport` is absent at `ca9cf8f0`, `main` tip and `develop` tip | The architectural argument (new league = app change by construction) survives on `LEAGUES`/`SportKey` alone |
| Test case: "today the app splits names at the first space" | Confirmed | `app/screens/GameScreen/_components/shared/TeamDisplay.tsx:57-59` — `name.split(" ")`, first word on line 1, remainder joined on line 2; same pattern for the greeting `app/screens/HomeScreen/HomeScreen.tsx:56-57` | |

## Defect table (app rows of "Risks and open questions", plus what I found next to them)

| # | Proposal's defect | Verdict | Exact evidence at `ca9cf8f0` | Real-world effect / note |
| --- | --- | --- | --- | --- |
| D1 | Entitlement-invalidate key ships in the app bundle (`EXPO_PUBLIC_`) and calls an internal route | **Confirmed** | `app/services/entitlement/entitlement.service.ts:68` reads `process.env.EXPO_PUBLIC_ENTITLEMENT_INVALIDATE_KEY`; sent as `x-entitlement-invalidate-key` to `APIs.entitlement.invalidate = /internal/entitlement/invalidate` (`app/services/api/index.ts:140`); triggered from `app/screens/ProfileScreen/ManageSubscriptionScreen.tsx:64,97` | `EXPO_PUBLIC_*` is inlined at build time (README: "EXPO_PUBLIC_* variables are inlined at Metro / EAS build time"), so the shared secret is extractable from the store binary. **Blast radius is server-side** (anyone can invalidate any `userId` via `/internal/…`), which is why it is rated High; also `.env.example:10` |
| D2 | Game calendar ends 31 Dec 2026 | **Confirmed** | `app/components/SwipeableWeekCalendar/SwipeableWeekCalendar.tsx:30-31` (`MIN = new Date(2025,10,1)`, `MAX = new Date(2026,11,31)`), weeks built once at module scope `:32-52`, index clamped `:56-57` | User-visible from 1 Jan 2027: no week beyond 31 Dec 2026. Symptom appears ~2.5 months after the proposal date — cheap fix now, high cost later |
| D3 | My Picks shows a void result (2) as a win and a missing one as a loss | **Confirmed (app side)** | `app/components/MyPicks/MyPicksItem.tsx:98-105`, ternary at `:101-103` `icon={pick.outcome ? "tick" : "close_red"}`; `pick: MyPickV2Item` with `outcome: number \| null` (`app/services/my-picks-v2/type.ts:18`) and no normalisation anywhere (`app/services/my-picks-v2/example.ts` shows 0/1/null) | Any truthy outcome — including the `2 = void` encoding the app's own mapper documents (`app/utils/predictionOutcome.ts:3-6`, `BET_OUTCOME_VOID = 2`) — renders a green tick; `null` renders red. Same class of bug in the group header: `PickGroupCard.tsx:55-60` treats "any falsy outcome" as not-won, so a group containing a void item shows as won |
| D4 | The game's outcome overrides each top pick's own result on details | **Confirmed** | `app/screens/GameScreen/_components/shared/GamePicksList.tsx:65` `mapPickOutcome(gameOutComeStatus ?? pick.pickOutcome)` | A game-level status wins over the per-pick outcome, so individual picks inherit the game result on the details screen. Contrast: the Edge Picks list uses the pick's own outcome (`TopPickCard.tsx:185`) |
| D5 | A missing status renders as Completed | **Confirmed** | `app/screens/GameScreen/GameCard.tsx:68` default parameter `status = "Completed"` | Missing/renamed status field silently shows a completed game instead of failing visibly |
| D6 | Edge-pick blur reads `locks.topPicks`, not `locks.edgePicks` | **Confirmed** | `app/services/contentLocks/resolveLocks.ts:53` `blurEdgePicks: blur(locks?.topPicks)`; consumed at `app/screens/GameScreen/_components/details/GameDetailsPicksSection.tsx:57` (`locked={blurEdgePicks}`) via `useGameDetailsBodyModel.ts:75` | Server can lock Top Picks and Edge Picks independently; the client applies the Top Picks policy to both. Also note the resolved `upgradeCta`/`upgradeReason` (`:55-56`) are dead — nothing reads them |
| D7 | Share text pairs team_2's code with team_1's actual (not predicted) score | **Confirmed** | `app/screens/GameScreen/GameCard.tsx:158-166`: `awayTeam = team_1.code`, `homeTeam = team_2.code`, but `aiHomeScore = team_1.score`, `aiAwayScore = team_2.score`; template `app/constants/constants.ts:79` renders `{{homeTeam}} {{aiHomeScore}}–{{awayTeam}} {{aiAwayScore}}` | Renders "team_2 [team_1's score] – team_1 [team_2's score]": the score is attached to the wrong team. (Also names scores `ai*` although both come from the actual score field, not the prediction) |

Additional client-side observations found while checking (not in the proposal's table): `TeamLogo.tsx:41-55`
labels team_1 "home" while `GameCard.tsx:161-162` labels team_1 "away" — two components disagree about which
side team_1 is; `PickGroupCard.tsx:57` (void ⇒ group shows won, above); the app has no response validation
library, so D5-style drift is silent by design.

## What this means for the assessment

1. **The proposal's load-bearing app claims survive, including on the branch it did not read.** Every hardcoding
   in "Server values it ignores or overrides" is real: `AppConfigContext.tsx:44,49` throw away the
   `api_version` and `enabled_leagues` that `/config` already returns, and `resolveApiVersion()` is dead code.
   Both are byte-identical at `main` tip and `develop` tip, so the branch question does not change the finding.
2. **The direction of "the app is a thick client" is confirmed, but the number is understated.** My count is
   66 league-conditional sites (≈45 excluding style-only conditionals) against the proposal's 37, concentrated
   in `PlayerTableStatColumn/NameColumn`, `useGamePlayerTableLayout` and EPL specials — so the cost of the
   status quo is, if anything, larger than presented; the per-league split (NBA-first) is what I could not
   reproduce.
3. **Two app claims are wrong and both flatter the plan.** There is no `EdgePick` v4 type and no `EdgePickSport`
   union anywhere at the cited commit or on either branch tip; the "the type exists, it just needs wiring" and
   "league is a union (`EdgePickSport`)" statements are false. The pilot's first app task is writing the v4
   types from the spec, and the closed union is `LEAGUES`/`SportKey` (`leagues.ts:1-12`).
4. **The two precise counts that matter for Gate C are exactly right.** 127 bundled logos (127 unique
   `require()` paths) and 128 abbreviation keys. Combined with 5 `require()`d glow PNGs
   (`colors.ts:127-133`), 5 duplicated in `AndroidGlassCard.tsx:7-13`, and require()d league SVG icons
   (`sports.ts:3-9`), the "new league needs no store release" property is genuinely blocked today — nothing in
   the app fetches art from a CDN or by key.
5. **Store-release coupling is a build-time property, not just a review process.** Because assets and league
   ids are compiled in, SDUI principle 4 ("assets by key") is a client change *before* it is a server one; the
   proposal's own migration table lists "Assets by key" as a principle but the Phase-2 test case assumes the
   fallback set already exists — it does, and it is the binary.
6. **Payload/offline is under-priced in the opposite direction from intuition.** Today a card renders labels
   from its own bundle and art from the binary, so the network payload is data-only; an SDUI payload carries
   display strings (smaller than art, larger than a field) and becomes the critical path for *every* screen.
   There is **no query persistence** (no `persistQueryClient`/MMKV persister; MMKV is used only for small local
   state, `app/utils/storage/index.ts:5`) and the API timeout is 10 s (`app/services/api/index.ts:19-22`), so a
   cold, offline start renders nothing regardless of architecture — but SDUI makes the empty state the *only*
   state, versus today's bundled skeleton/labels.
7. **React Query caching needs an explicit design the proposal does not give.** Default `staleTime` is 60 s with
   `refetchOnWindowFocus: true` (`app/app.tsx:258-266`), so a composed screen would re-fetch on every focus;
   `/config`'s 10-minute policy plus AppState invalidation (`AppConfigContext.tsx:28-38`) is the only staleness
   discipline in the app; query keys already embed `apiVersion` (`app/services/queryKeys.ts:2-8`), so a
   contract/section version must either join the key or be handled by in-payload versioning.
8. **The force-update gate is real but weaker than the risk section implies.** `ForceUpdateGate.tsx:12-57` reads
   `minimum_app_version_required` and `store_links` from `/config` and compares them with
   `Application.nativeApplicationVersion` (`config/forceUpdate.ts:65-73`); the hardcoded fallback is iOS
   `1.1.46` / Android `1.1.30` (`:10-14`). It blocks only *older* builds — so SDUI cannot assume a
   component-aware client unless the minimum is raised, and raising it is a store-visible act (iOS phased
   release, user-update friction) that belongs in the phase gates.
9. **Analytics is the invisible client cost.** 72 exported `log*` helpers plus Mixpanel
   (`app/lib/mixPanel/index.ts:1`, `app/services/appEvents/events.ts`) are called from *inside* the components
   being replaced — e.g. `GameCard.tsx:26-31` (`logMatchMoreTapped`, `logShareSheetOpened`,
   `logMyPicksPredictionAdded/Removed`). Server-driven sections must keep emitting the same taxonomy, which
   turns analytics into a payload/server-naming contract rather than a free consequence of rendering.
10. **Accessibility and test hooks become payload obligations.** The app carries 41 `accessibility*` props/usages
    and 247 `testID` props; the Maestro flows (`.maestro/flows/Login.yaml`, `FavoritePodcast.yaml`) and 74 Jest
    files under `app/` depend on stable ids. A `component@1` catalogue must define required `testID`/a11y keys,
    or both E2E and screen-reader behaviour regress while the UI still "works".
11. **The client has no contract safety net today.** There is no zod/yup/ajv (or any runtime validator) in
    `package.json`, 18 `[key: string]: any` index signatures and 61 other `: any`, and transformers spread
    upstream objects (`topPredictions/transformer.ts:31`). "One contract, generated" (principle 6) is therefore
    net-new client work with no existing harness — and it is the precondition for the BFF being allowed to
    rename or restructure fields.
12. **Three of the seven app defects are user-visible and cheap to fix before any SDUI work**: D3 (void shown as
    a win) and D7 (share text attaches the wrong score) today, D2 (calendar) from 1 Jan 2027. D1 is the security
    one (shared secret in the bundle, calling `/internal/entitlement/invalidate`); D4/D5/D6 are correctness
    drift that a contract would catch mechanically. Phase 0's "removes the defects" claim is well founded.
13. **The reuse list is accurate — the catalogue is a re-packaging, not new UI.** Generic cards
    (`GameCard`+`GameTeamsDisplay`), the tab/drawer shell, `LeagueFilterBar`, status badge
    (`PredictionOutcomeIndicator`), lock/blur primitives (`resolveLocks`, `UnlockPickCard`,
    `gameDetailsBlur`), and a player table already driven by `predicted[]`/`sections`/`metadata.playerstatkeys`
    all exist and are already payload-shaped. That supports the "about 15 components" estimate, with the caveat
    that the same components contain the 66 league branches that must be evacuated first.
14. **The Gate C claim ("both leagues ship with no app release") is not verifiable from the app repo alone, and
    the app side is the weaker half.** College football/basketball would still be blocked by closed unions
    (`LEAGUES`/`SportKey` — `leagues.ts:1-12`, `sports.ts:11`), and by three bundled lists the test case itself
    names: onboarding tiles (`sports.ts:43-87`), league filter (`leagueConfig.ts:12-19`) and league icons
    (`sports.ts:3-9`). NCAAB/NCAAF do already exist as *inactive* onboarding tiles (`sports.ts:107-115`), which
    makes the first half of the test case plausible but not free.
15. **Nothing in this review depends on which of `main`/`develop` ships**: no release automation exists in the
    repo, both lines carry release tags for the same iOS version, `develop` is the default branch and leads on
    Android versionCode, and the nine load-bearing files are identical at `ca9cf8f0`, `main` tip and `develop`
    tip. The one thing that *is* branch-dependent is the app's future state, not the proposal's evidence — so
    the assessment should state the cited commit and treat "the shipping branch" as unresolved rather than
    assume `main`.

## Verdict tally

| Verdict | Count |
| --- | --- |
| Confirmed | 36 |
| Partly | 4 |
| Refuted | 1 |
| Unverifiable | 1 |
| **Total claims checked** | **42** |

Defect rows: 7/7 **Confirmed** (D3 with the caveat that `2 = void` is a BFF encoding; the app-side defect holds
regardless of the value because every truthy outcome is a win).

## Method notes (reproduction)

```bash
# read-only; no writes in github/mobile-app
git -C /mnt/devel/xosports/github/mobile-app ls-remote --heads origin main develop
# persistent temp object store (the sandbox only allows writes in xo-scratchpad)
V=/mnt/devel/xosports/xo-scratchpad/.verify/mobile-app.git
git init --bare "$V" && echo /mnt/devel/xosports/github/mobile-app/.git/objects > "$V/objects/info/alternates"
git --git-dir="$V" remote add origin git@github.com:XOSports-ai/mobile-app.git
git --git-dir="$V" fetch origin refs/heads/main:refs/remotes/origin/main refs/heads/develop:refs/remotes/origin/develop
git --git-dir="$V" grep <pattern> ca9cf8f0 ; git --git-dir="$V" show ca9cf8f0:<path>
```

Counts were produced with `git ls-tree -r` (file counts), `grep -c` of map entries and unique `require()`
paths (`teamImages.ts`), `grep -c` of quoted keys (`teamAbbreviation.ts`), and the league-conditional-site
enumeration described in that row. `drift` was checked with `diff` of extracted trees at `ca9cf8f0`,
`refs/remotes/origin/main` (`137f2f61`) and `refs/remotes/origin/develop` (`0e4f686d`). Temporary verification
artefacts live under `xo-scratchpad/.verify/` and are not part of this deliverable; no tracked file in
`mobile-app` was modified and nothing was pushed.
