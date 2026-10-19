# Edge Picks v4 — Schema Contracts

Oct 19, 2026 · @Tze Liang

Edge Picks data crosses three team boundaries, and each has one contract page: the snapshot API (BFF to app), the realtime overlays (live services to app) and the producer pick record (bet engine and Publish Engine to BFF). Each page is self-contained: its fields, enum values, rules, formulas, test vectors and complete JSON Schema are on the page, so a team builds against it without opening another document. Rules that two pages share are repeated in full on both, generated from one source so they stay identical.

**The contracts** (each is its own tab of this doc):

- Snapshot API (BFF to app): GET /v4/edge-picks, every field, the rules for producing and handling the values, the JSON Schema and examples
- Realtime overlays (live services to app): the edge overlay and the live game card in Firebase, key derivation, merge rules, schemas
- Producer pick record (engine to BFF): the record the bet engine and Publish Engine write, the producer rules, the schema, and today's gaps by sport

## Readiness

Yes: publish the three pages as drafts now. Their shapes are settled; the open decisions change values, not structure, and each page marks the affected values Provisional.

| Contract | Publish now as | Still open (values, not shape) | Signs |
| --- | --- | --- | --- |
| Snapshot API (BFF to app) | 4.0.0 draft; build against it | Display basis for edges, reason codes, cancel triggers, overlay key format | App team, BFF |
| Realtime overlays (live services to app) | 4.0.0 draft | Overlay key format and read rules | App team, edge monitor, live scores |
| Producer pick record (engine to BFF) | 4.0.0 draft target, with today's gaps | Status vocabulary, reason codes, cancel triggers, engine persistence, document layout and ids | Bet engine, data engineering, BFF, edge monitor |

Three things gate agreement, not publication: the engine team's answer on persistence and cancel triggers before the next tst promotion, a recorded decision on document layout and pick ids, and a run of every page's examples and vectors against the BFF mock and one producer.

## What the current schema page gets wrong

The [NBA 2026 Schema Specification](https://xosports.atlassian.net/wiki/spaces/PB/pages/717914114) (v6, 23 Sep) is a good design narrative but a weak contract: it mixes how data is built with what consumers may rely on, and parts of it no longer match the code on dev. Each gap below has a fix that every page in this set follows.

| # | Gap in the NBA page | What it costs | Standard in these pages |
| --- | --- | --- | --- |
| 1 | Contract and implementation are mixed: Databricks source tables and transforms sit beside the Cosmos fields | Consumers cannot tell what they may rely on from what may change without notice | The contract states only what crosses a boundary. Sources and transforms live on the producer's own pages |
| 2 | It describes behaviour the code does not have: the settlement write-back loop, `pick_status` on game picks, a region map as the engine's output | Teams build on mechanisms that do not exist | Every statement about today is an **observation** with the commit it was checked at; everything else is a requirement |
| 3 | No machine-readable schema: tables plus one example each | No validation, no generated types, drift between docs and code | Each contract has a JSON Schema (draft 2020-12) that is the source of truth; the tables are generated from it or checked against it |
| 4 | Required, nullable and absent are not distinguished; some tables list nullability, others do not | Readers guess whether a field can be missing | Every field states required, nullable and what null means |
| 5 | Units are implicit: `edge` in percentage points, probability as a fraction, projections as 2-decimal strings | Factor-of-100 and string-parsing bugs | Units in every field description; numbers are numbers; one unit per concept across all contracts |
| 6 | Three version formats (`1.10`, `2.0.0`, `1.00`) and no compatibility rule | Nobody knows which change breaks whom | Semantic versions with a written rule for minor and major changes, and a change log per page |
| 7 | Mixed casing and meanings in enums: `schedule.status` lowercase, `outcome.game_status` capitalised, `pick_status` mixing lifecycle with result | Mapping tables in every consumer | Every enum listed with its meaning and fallback on the page that uses it; lowercase; lifecycle and result kept separate |
| 8 | Identity rules that cannot hold together: line-aware ids, and "a line move means the old pick is absent" | Picks vanish; saved slips break; the track record is biased | Identity, persistence and lifecycle stated as testable rules on the producer pick record page |
| 9 | No owner per field, no consumers listed, no guarantees (freshness, ordering, idempotency) | Nobody knows who to ask or what breaks downstream | Each page has owner, consumers and guarantees in its header block |
| 10 | Examples contradict the stated rules: the AU block names SportsBet while the code mirrors US picks; `environment: prd`, which does not exist | Examples get copied into code and fixtures | Examples are validated against the JSON Schema and reflect real behaviour, or say they are illustrative |
| 11 | No acceptance criteria or test vectors | No way to check an implementation | Each page carries the test vectors that check it |
| 12 | Status "Request for Comment" since 16 Sep with no sign-off record | Draft and agreed are indistinguishable | Status per page: draft, agreed, deprecated, with who agreed and when |

## Contract map and Confluence page tree

Three contracts sit between four producers and two consumers; the realtime overlays contract covers two feeds.

&#91;embedded content: contract map · 4 producers, 5 contracts, 2 consumers\]

The edge monitor's latest observation reaches the pick record only through the Publish Engine. The app merges both realtime feeds onto the snapshot and never reads the pick record.

Proposed Confluence tree, one page per tab of this doc:

- Edge Picks Contracts (this overview)
  - Snapshot API (BFF to app)
  - Realtime overlays (live services to app)
  - Producer pick record (engine to BFF)

## Open decisions and publishing plan

Each contract page lists the decisions that can still change it; this table gathers them with owners and dates.

| Decision | Pages it changes | Owner | Due |
| --- | --- | --- | --- |
| Status vocabulary | Producer pick record | Bet engine, data engineering, monitor owner | Oct 21, 2026 |
| Cancelled returning to open before the start (the NFL engine reinstates depth-chart cancellations today) | Producer pick record, snapshot API | Bet engine, product | With the status vocabulary |
| Reason codes | Snapshot API, producer pick record | Spec owner | Oct 21, 2026 |
| Display basis for edges | Snapshot API | Bet engine, product | Oct 23, 2026 |
| When the engine cancels | Snapshot API, producer pick record | Bet engine, product | Oct 30, 2026 |
| Overlay key format and read rules | Snapshot API, realtime overlays | Monitor owner, app team | Nov 2, 2026 |
| Engine persistence, including pausing without removing published picks | Producer pick record | Bet engine, NBA schema owners | Before the engine's next tst promotion, and before NBA player picks are reinstated |
| Document layout and pick id format | Producer pick record | Bet engine, data engineering | Not scheduled |

### How to publish

1. Keep each JSON Schema and vector table in one repository as the source of truth. The pages render them, and rules repeated across pages are generated from one source so they cannot drift.
2. Create "Edge Picks Contracts" in the PB space with this overview and one child page per contract.
3. Mark the superseded parts of the NBA 2026 Schema Specification (its pick status list, the line-move rule in §5.2, the settlement write-back) and link each to the page that replaces it, rather than editing the RFC in place.
4. Ask each owner to sign their page's change log; a page moves to agreed only when all its owners have.
5. Run each page's examples and vectors against the BFF mock and one producer before the first page is agreed.

The NBA page remains the producer's design narrative (sources, transforms, container layout). These pages take over the part other teams build against.

### Working in dev

Tst serves real users, so building to these contracts happens in dev, which is also used for testing. Any parallel setup (separate bet engine output tables, a second Publish Engine instance, a second BFF instance) keeps to these rules:

1. Content goes to a separate Cosmos database, so a misconfigured target fails instead of overwriting dev data.
2. It sends no events to the dev notification queue, and a second BFF does not consume that queue.
3. Caches are not shared with the dev BFF, or use a separate key prefix.
4. My Picks data written against new pick ids goes to separate containers; user accounts and subscriptions stay shared.
5. Any live edge monitor feeding it reads and writes dev data only.
6. It has an end date: once the pages are agreed and their examples and vectors pass, dev moves to the new shape and the parallel setup is removed.

Engine switches in dev and tst, such as the NBA player-pick switch, follow the persistence rule: they stop new picks and never remove published ones.
