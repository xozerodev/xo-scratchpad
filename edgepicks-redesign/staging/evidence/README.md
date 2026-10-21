# Evidence bundle — Edge Picks v4 producer-contract assessment

Raw working material behind `../conf-schema-contracts-assessment.md` (contract `4.0.0` draft; requirement page Confluence PB/726237185 v6). Captured 2026-10-21. Everything here is read-only investigation output; the assessment is the normative summary, these files are the audit trail.

| File | What it is | How it was produced |
| --- | --- | --- |
| `validate_contract.py` | Mechanical validation of `../conf-schema-contracts.md`: extracts the Draft 2020-12 JSON Schema and the five §10 example records, validates them, recomputes vectors P-1…P-9, rebuilds every documented `pick_id` and probes prose rules the schema does not enforce. | Python 3 + `jsonschema` 4.26.0, run 2026-10-21. Run: `uv run --with jsonschema python validate_contract.py` (expects the contract at `../conf-schema-contracts.md`; adjust `MD` if run from a different directory). |
| `validate_contract-output.txt` | Captured output: **0 FAIL, 9 GAP, 39 PASS**, with the per-check lines. | Same run as above, redirected to file. |
| `req-mapping.md` | Requirement-by-requirement mapping of PB/726237185 v6 (plus baseline PB/769687553 v5) onto the 37-field record, with contract line references. | Confluence API reads (`body-format=storage`), page v6 2026-10-19T04:30:29Z; v5/v6 body diff; embedded screenshots inspected. |
| `nba-engine-gaps.md` | NBA bet engine (`nba_bet_engine@dev d36b2d1`) → v4 record gap analysis: field mapping, Rules 1–6, observation ownership, domain gaps, prioritised work. | Repo code read; live `dev_nba.nba_gold_bets` via read-only Databricks profile `dev` (2026-10-21); Publish Engine (`app-data@tst-blue a1c16f4`, `feat/nba-2026@54214ec`) and Confluence PB/720142351/717914114. |
| `ecosystem-coherence.md` | Writer/ownership and cross-contract review: single-writer premise, merge semantics, field seams, versioning/coexistence, diff against the earlier `producers-to-bff.md` edition, and 12 probed internal contradictions. | Contract/sibling docs, `mobile-server@develop fffcc9e`, `app-data`, `live-odds@dev e2c04ca`, KDD-001/002/003, option-B plan. |

Notes:
- These are working analyses, not normative documents; where they disagree with the assessment, the assessment (revised) governs.
- The live-data snapshots are as of 2026-10-21 and the engine at `d36b2d1`; jobs were paused and the PS tables were empty, so PS shapes are code-derived, not data-derived.
- No external system was written to; the only writes are files under the agent workspace.
