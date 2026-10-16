# Validation plan

Oct 16, 2026 · @Tze Liang

Validation checks four things against the schemas and the taxonomy: that a document has the declared shape, that every key and combination exists in the registry, that its numbers and identities recompute exactly, and that it agrees with what was published before. Each rule is written once in `xo-contracts`, has an id, and runs in Spark (engines), Python (Publish Engine) and TypeScript (BFF) against one shared set of test vectors, so all three runtimes give the same verdict. Rules start in report-only mode on today's NBA 2026 and Format A output; they block publishing family by family once their false-positive rate is known.

## Assessment of the current plan

The six gates in the main tab put checks in the right layers and stop bad rows before Cosmos. They are not yet a plan, for five reasons:

- **They list checks, not rules.** "Line rules" or "header equality" has no rule id, no exact definition and no test, so the Python, Spark and TypeScript copies will drift, as the 6 dp edge identity already did.
- **Nothing looks back in time.** Entry immutability, legal status transitions and "no new pick after the start" need the previously published version. No gate holds it.
- **Nothing checks whole sets.** Per-row checks cannot catch a missing prediction for a scheduled game, a stale `current`, a day with half the usual picks, or drifting probabilities.
- **One failure action per gate.** Every failure is a reject, so a lagging roster (a player not yet on the team) would block a valid pick. Rules need severities.
- **Settlement is not re-derived.** `result` and `settlement_fraction` are trusted as published, although the registry's `settle_from` and push and dead-heat rules are enough to recompute them.

## What gets validated

Fourteen rule families cover the model. Families 1 to 6 need only the document and the registry; 7 to 10 need other documents or the previous version; 11 and 12 look at whole sets; 13 and 14 guard the registry and the consumers. Each rule id is `{family}-{nnn}`, for example `PRC-003`.

| # | Family | Example rules | Grounded in | Runs at | Default severity |
| --- | --- | --- | --- | --- | --- |
| 1 | `SHP` Structure | Types, required fields, enums, ISO 8601 UTC times, `null` vs `[]` | JSON Schema per document | All layers | Block |
| 2 | `TAX` Taxonomy membership | Every stat, market, outcome, period and unit key exists in the document's `registry_version`; aliases resolve and are not past `remove_after` | Registry keys and aliases | Engine, PE | Block |
| 3 | `CMP` Taxonomy compatibility | Stat eligible for the market and the player's role; outcome kind allowed by the market; line required, forbidden, integer or on its step; milestone in `thresholds`; fantasy stats name a `scoring`; half results only where the profile allows quarter lines | `stats/`, `markets.yaml`, sport profile | Engine | Block |
| 4 | `IDN` Identity | `selection_key` and `pick_id` re-derive from the pick's own fields; `format(parse(k)) == k`; key charset; ids unique within a document and a day | Identity spec | Engine, PE | Block |
| 5 | `PRC` Prices | Derived `decimal`, `american`, `implied_probability` recompute from `native` at 6 dp; American never in (−100, 100); implied in (0, 1) | Pricing library | Engine, PE | Block |
| 6 | `PRB` Probabilities and edge | `outcome_probs` in \[0, 1\] and sum to 1 ± 1e-6; impossible results are 0; `edge_prob` and `ev` recompute exactly; the entry satisfies its own `selection_rule`; market outcomes sum to 1 ± 1e-4 | Pricing library, profile | Engine | Block; market sum Warn |
| 7 | `REF` References | Event exists in the schedule with the same league and season; `competitor_sk` belongs to the event; `player_sk` is on one competitor's roster; `venue_role` matches the schedule | Schedule, rosters | PE | Block; roster Warn |
| 8 | `XDC` Cross-document | Header fields equal across an event's documents; `entry.projection.run_id` exists in `game_projections`; one writer per document | Document set | PE | Block |
| 9 | `LCY` Lifecycle | `entry` unchanged after first publish; status moves only along the lifecycle graph; no new pick after the start; `result` only after `final`; `current.observed_at` never moves backwards | Lifecycle spec, previous version | PE | Block (hold the document) |
| 10 | `STL` Settlement | Re-grade from `event_result` with `settle_from`, push, half and dead-heat rules; must equal `result` and `settlement_fraction` | Registry, profile | PE, nightly | Block; nightly report |
| 11 | `CPL` Completeness and freshness | Every scheduled event has projections by its checkpoint; `current` younger than 2 h before the start; no `open` pick after `final` | Schedule, checkpoints | Monitor job | Alert |
| 12 | `DRF` Drift | Daily pick volume, edge distribution and quarantine rate against a trailing baseline; weekly calibration (Brier score) per league | History | Monitor job | Alert |
| 13 | `REG` Registry integrity | Unique keys; no alias collision in one context; every message id in every locale with valid plural syntax; every profile market and stat exists; every `asset_key` exists in storage | Registry | Registry CI | Merge blocked |
| 14 | `CON` Consumer contracts | BFF and SDUI responses match their zod schemas; RTDB overlay nodes match their schema at the writer and in `.validate` rules; the app tolerates unknown keys | Response and overlay schemas | BFF, writers, app CI | Drop and alert |

The taxonomy is what makes families 2, 3 and 10 possible: without a registry that says which stat a market may use and how it settles, a document can only be checked for shape.

## Where each check runs

&#91;embedded content: validation gates · engine to app, with quarantine and monitoring\]

Gate 1 carries most of the rules because the engine is the only place that holds every field before anything is published. The Publish Engine adds what needs other documents or history, and the BFF guards what the app receives. Gate numbers match the main tab.

## How failures are handled

A failure never silently changes what users see: either the last good version stays live, or the item is dropped and someone is alerted. Each rule carries one of four severities, set in the registry so a rule can be relaxed without a deploy.

| Severity | Effect | Example |
| --- | --- | --- |
| Block | The row or document is not published; the previous version stays live | A pick whose `selection_key` does not re-derive |
| Hold batch | The whole batch waits when its failure share passes a per-document-type threshold | Half of a day's picks fail `CMP` after an engine release |
| Warn | Published, counted and reported daily | A player missing from a roster that lags by a day |
| Alert | No document involved; a set-level check pages the owner | No projections for a game at its checkpoint |

**Quarantine.** Every blocked row lands in `{league}_validation.quarantine` with the rule id, the failing value, `run_id`, `registry_version`, validator version and the full row. The table is the triage queue and the replay source.

**Replay.** Once fixed, upstream or by relaxing a rule, a job re-runs validation on quarantined rows and publishes those that now pass, in their original order. Rows superseded by a newer version are closed, not replayed.

**Ownership.** Sport owners triage their league's quarantine; platform owns rule definitions and the validators; a new Block rule needs both to agree.

**Provenance.** Every published document records the `registry_version` and validator version it passed, so a later rule change can be traced to the documents it would have rejected.

## How the validators are tested

The main risk is not a missing check but three implementations that disagree, which is how the 6 dp identity broke. So every rule is specified once, and every runtime must pass the same vectors.

- **Rules are data plus a reference implementation.** Structural rules (`SHP`) are generated from JSON Schema. Taxonomy rules (`TAX`, `CMP`) are generated from the registry as lookup tables. Numeric and identity rules (`PRC`, `PRB`, `IDN`) live in one `xo-contracts` library with a Python reference and a TypeScript port, both using decimal arithmetic.
- **Shared vectors.** `xo-contracts/vectors/` holds, for each rule id, at least one passing and one failing case with the expected verdict. Python, Spark and TypeScript CI all run the whole set; any disagreement fails the build in every repo.
- **Property tests for round-trips.** Hypothesis (Python) and fast-check (TypeScript) generate prices, lines and keys: native → derived → native, `format(parse(k)) == k`, and ev = B × d × edge\_prob within tolerance. The 100,000-sample runs in the main tab become these tests.
- **Golden documents per league.** One full, valid document set per league and per doc type, plus mutated copies that must each fail exactly one named rule. They double as BFF and app fixtures.
- **Registry changes run the corpus.** A registry PR re-validates the golden set and a sample of recent production documents, so a change that would reject live data is caught in review.

## Mock data and the conformance workbench

The same library that validates documents should also generate them. Then a new league, bet type, stat or schema variant can be drafted on a registry branch, filled with conformant mock data, checked rule by rule and previewed as app screens, all before any engine or app code changes. Build it as a command-line tool first, so CI uses it from day one, then put a small internal web app on the same commands.

**Mock data from the registry.** The generator reads a sport profile and league entry and builds a full, consistent event set: schedule, projections, picks, observations over time and a settled result. Prices, `outcome_probs`, `edge_prob`, `ev`, `selection_key` and `pick_id` are computed by the `xo-contracts` library, so mocks are conformant by construction. A fixed seed makes every output reproducible.

| Generator | What it produces | Used by |
| --- | --- | --- |
| Valid sets | A league-day of documents for any profile, including a draft one | Golden fixtures, local Cosmos seeds, BFF mock mode, app previews |
| Named scenarios | Line move, push on a whole total, half-lost quarter line, dead heat in a top 10, postponed game, late scoring correction, stale overlay | Lifecycle and settlement tests; the v4 Edge Picks mock scenarios |
| Rule mutators | For each rule id, a copy of a valid document that breaks exactly that rule | The failing half of the shared vectors, generated rather than hand-written |
| Property strategies | Hypothesis and fast-check generators for prices, lines, keys and outcome splits | Fuzzing the round-trips in CI |
| Consumer shapes | Delta rows, Cosmos documents, SDUI payloads, RTDB overlay nodes | Engine, Publish Engine, BFF and app tests |

This replaces three hand-made sets that already drift: the BFF's `script/db-seeds`, its Edge Picks `mock/fixtures.ts`, and the Publish Engine's seeders.

**The command-line tool** (`xo-contracts`) has five commands, and the workbench calls the same ones:

| Command | What it does |
| --- | --- |
| `generate` | Mock documents for a league, date range and scenario list |
| `validate` | Rule-by-rule verdicts for a document, a folder or a Delta table sample |
| `diff` | Compares two schema or registry versions: lists changes, classifies each as minor or major, and runs the old version's validators over the new version's mocks (the readers-first check) |
| `preview` | Runs documents through the BFF screen composer and writes the SDUI payloads |
| `promote` | Saves a scenario as golden fixtures and vectors, ready for a pull request |

**The web workbench** is an internal tool for product, sport owners and engineers:

1. Edit a draft profile, league, stat or market on a registry branch, with autocomplete and registry checks as you type.
2. Generate a mock league-day or a named scenario for it.
3. Validate generated or pasted documents, or fetch one from dev Cosmos by id, and see each rule's verdict with its id and an explanation.
4. Compare a schema variant with the current version and see whether it is a minor or major change, and which consumers it would break.
5. Preview the resulting cards and screens in the SDUI component catalogue, with copy from `messages/`.
6. Promote the scenario to golden fixtures through a pull request.

**Architecture.** A thin React front end calls a validation API that wraps the Python reference library, hosted internally (for example on Azure Container Apps behind Entra ID) with access to dev and tst data only. A browser-only version, with TypeScript validators or Python through Pyodide, would avoid running a service but would put a second implementation in front of users and could not read Cosmos. Previews render the component catalogue's web build: Expo can target the web, but whether every catalogue component works there is unverified.

**What it changes in this plan.** The workbench calls the Python reference, so CEL's in-browser appeal disappears, and CUE's Go-only toolchain becomes a further cost. It also gives Gate C (a new league with no app release) a concrete rehearsal: draft college basketball in the workbench, generate, validate and preview, before any producer emits a document.

## Rule language: CEL, CUE and alternatives

No single rule language fits all fourteen families, and most rules need none. Taxonomy membership and compatibility (`TAX`, `CMP`) are set lookups generated from the registry. Prices and probabilities (`PRC`, `PRB`) need decimal arithmetic and rounding, which CEL does not have. That leaves the cross-field and lifecycle rules (`XDC`, `LCY`, some `CMP`), a small set where CEL is the best candidate once its Python and TypeScript ports mature. CUE is an authoring and CI tool, not a runtime for this stack.

| Option | Python and Spark | TypeScript (BFF) | Decimal maths | Cross-field and history rules | Maturity in our runtimes | Best use here |
| --- | --- | --- | --- | --- | --- | --- |
| Code plus shared vectors | Native; Spark through pandas UDFs | Native | Yes | Yes | Mature | `PRC`, `PRB`, `IDN`, `STL`; everything at first |
| CEL (Common Expression Language) | cel-expr-python (Google, March 2026, wraps the C++ engine; read-only repo at launch) or the community cel-python; row by row in Spark | `@bufbuild/cel` (beta) or community cel-js | No: int, uint and double only | Yes: pass `prev` and registry slices as variables; no side effects, bounded cost | Go, C++ and Java mature; Python and TypeScript new | `XDC`, `LCY` and leftover `CMP` rules, later |
| CUE | Go toolchain; Python and JavaScript only through experimental bindings or an old WASM build | Same | Yes (arbitrary-precision numbers) | Constraints inside one value; no history | Go mature only | Authoring the registry and schemas; `cue vet` and JSON Schema export in registry CI |
| JSON Schema 2020-12 | Mature validators | ajv | No | Limited (`if`/`then`, dependencies) | Mature | `SHP`, as already planned |
| Spark SQL, optionally Databricks Labs DQX | Native and fast; DQX adds YAML checks, warn or error criticality and a valid/invalid split | None | Yes (`DECIMAL`) | Set-level well; per-document cross-field awkwardly | DQX is a Labs project | `CPL`, `DRF` and quarantine plumbing |
| OPA Rego | WASM or a sidecar | WASM SDK | No | Yes | Mature in Go | Poor fit: built for authorisation, unfamiliar to the team |
| JSON Logic | Small libraries | Small libraries | No | Weak, untyped | Implementations disagree | Poor fit |
| LinkML | Generators for JSON Schema, Pydantic and TypeScript | Generated types | Not applicable | Limited rule support | Established in data modelling | Alternative to a hand-built registry code generator; worth a spike |

**Recommendation:**

1. **Now.** JSON Schema for shape; generated lookup tables for `TAX` and `CMP`; code plus shared vectors for `PRC`, `PRB`, `IDN`, `XDC`, `LCY` and `STL`; Spark SQL for `CPL` and `DRF`, with DQX if its quarantine split saves work.
2. **Keep rules as registry entries.** Each rule's id, severity, scope and description live in the registry, with an optional `expr` field. A rule can later move from code to CEL without changing its id or its vectors.
3. **Adopt CEL for cross-field rules when** both cel-expr-python and `@bufbuild/cel` pass the cel-spec conformance cases we rely on and are out of beta, and either the number of such rules grows or rules need to change without a deploy. The shared vectors stay the parity guarantee either way.
4. **CUE only for authoring, if YAML proves error-prone.** It would run in registry CI and export JSON Schema; no engine, Publish Engine or BFF would depend on it.

Illustrative registry entry with a CEL expression:

```yaml
- id: LCY-002
  family: lifecycle
  severity: block
  applies_to: pick
  description: entry never changes after first publish
  expr: "prev == null || pick.entry == prev.entry"
```

Sources: [cel-expr-python announcement](https://opensource.googleblog.com/2026/03/announcing-cel-expr-python-the-common-expression-language-in-python-now-open-source.html), [cel-es / `@bufbuild/cel`](https://github.com/hudlow/cel-es), [cuelang-js](https://www.npmjs.com/package/cuelang-js), [DQX overview](https://www.waitingforcode.com/databricks/data-quality-databricks-dqx/read).

## Rollout

Validation reaches today's data before it blocks anything, so the first weeks measure how much existing output would fail.

1. **Report-only on current output.** Run all families over NBA 2026 documents and over Format A documents mapped to v3 by an adapter. Nothing is blocked; results go to the quarantine table with a `mode: report` flag.
2. **Backfill.** Run the same validators over the season's Delta history and Cosmos, to find bad data already live, such as stale schedule copies of rescheduled games.
3. **Enforce in order of confidence.** `SHP`, `IDN` and `PRC` first, since they have no judgement in them; then `TAX` and `CMP`; then the stateful `LCY` and `STL`. A family moves to Block when its report-only failures are all explained.
4. **Per league.** Enforcement switches on per league, so a new league (college basketball, say) starts enforced from its first document.

## Limits and open decisions

Schemas and the taxonomy prove a document is well formed, consistent and settled by the rules. They cannot prove it is right:

- **Model quality.** A valid probability can be a bad one; only calibration and results over time (`DRF`) show it.
- **Venue truth.** A price can be valid and still wrong if the feed is wrong; comparing observations against a second source is a Warn rule, not a proof.
- **Source results.** Settlement is only as good as `event_result`; a scoring correction arrives as a new version, under the profile's `correction_policy`.

Open decisions:

- Where the stateful checks read the previous version: a point read from Cosmos, or a Delta snapshot of the last published version (cheaper, and replayable).
- When cross-field rules move from code to CEL; the triggers are in the rule-language section.
- The hold-batch threshold for each document type.
- Whether `REF` roster checks Block for player picks once roster feeds are reliable.
