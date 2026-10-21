# Review of the fifth pass — probe strength, coverage and self-test

**Reviewed:** commit `a6febaa` *"assessment: classify probes by rule strength, add coverage probes and self-test"* (parent `05ac852`), plus the rebased `dd12005` (my fourth-pass review; blob-identical to the original `2f26c92` — verified, no edits).
**Files:** `conf-schema-contracts-assessment.md` (+38/−…), `evidence/validate_contract.py` (+136), `evidence/validate_contract-output.txt`, `evidence/README.md`.
**Method:** read the full diff; re-ran the fifth-pass validator with and without `rfc3339-validator`; diffed the committed output against a fresh run; counted the probe/probe-run/GAP sets by hand; checked each new probe's rule and strength against the contract; re-checked the provenance and postscript text that the previous review flagged.

---

## 0. Verdict

**This pass closes five of the six corrections from my fourth-pass review, and the classification is a real improvement.** Verified: the new counts, the strength breakdown, the added probes, the self-test, the `rfc3339-validator` alternative totals, the corrected `item 6`/`item 14` and the reworded §3.6 rationale.

**But the sixth correction — the provenance claim — is untouched, and it is still the one factually false statement in the document.** Two counting ambiguities were also introduced: "19" refers to two different sets, and "22" to two different sets, in adjacent paragraphs; and §3.6 still tells the reader to add `minimum: 1` to `player_sk` while `item 14` says positivity is stated nowhere and must be decided first.

---

## 1. Verified improvements

| Change | Verification |
| --- | --- |
| New totals: 0 FAIL, 22 GAP, 39 PASS | Re-ran from the committed bundle without `rfc3339-validator`: byte-identical to `validate_contract-output.txt`; 22 GAP lines, 39 PASS, 0 FAIL. |
| Alternative environment: 0 FAIL, 20 GAP, 41 PASS with `rfc3339-validator` | Re-ran with `--with rfc3339-validator`: exactly 20/41; the two `"yesterday"` probes move to PASS under `FormatChecker`, the offset form does not. |
| Strength breakdown: 19 = explicit 14, implied 2, provisional 1, not-stated 1, permitted 1 | Matches the printed `=== GAP probes …` line and the 22 GAP lines (19 primary + 3 FormatChecker re-runs). Spot-checked classifications against the contract: `game_sk` (#5 "Positive integer") explicit; `team_sk` explicit only via §7.1 (field #10 says "Integer") — correctly noted; `player_sk` not-stated (field #11/§7.1 say only "Integer") — correct; `cancelled` with null reason permitted (§4.2 "Should be set", §4.3 "or null if unknown") — correct; sport↔market provisional (§7.3 marked Provisional) — correct; `is_closing`/settled pairings implied — correct. |
| New coverage probes: 4-dp odds, American derivation, `entry_edge > edge_threshold`, `observed_at` format | All four are present, start from schema-valid §10 records, and are GAP as expected; each is labelled with the right contract reference and §9.1 coverage. |
| Self-test replaces the "regression-checked" claim | The script now feeds the old false-PASS record to `classify()` and requires `FAIL`; output line: `[PASS] F self-test: probe rejected only on an unrelated field is classified broken :: classified FAIL, errors on ['pick_id']`. The Appendix now describes it as a self-test rather than a manual check. |
| Method row and environment note updated | "19 single-rule mutated records (22 validator runs; the three timestamp probes are also run with a format checker)" replaces "10 mutated records"; §3.1 and Appendix A state jsonschema 4.26.0 / no `rfc3339-validator`. |
| §3.5 item 6 and item 14 corrected | Item 6 now says a cancelled pick with no reason is *permitted*, not a violation, and recommends deciding the card behaviour. Item 14 now attributes `game_sk` positivity to field #5, `team_sk` to §7.1 only, and states that `player_sk` positivity is not stated — exactly the overreach the previous review identified. |
| §3.6 rationale corrected | "cheap, mechanical hardening … which is why it is High rather than blocking; of these only the `current_edge` case is partly covered today (by §9.1 invariant 3), while timestamps, key positivity and `projection_unit` are covered nowhere" — this is now consistent with Appendix A. |
| README updated | History, counts, strength breakdown and the `rfc3339-validator` alternative all match the script and output. |

Also confirmed: `dd12005` (the rebased review commit) contains exactly my fourth-pass review file, blob-identical to `2f26c92`; the rebase did not alter it.

---

## 2. Remaining errors and ambiguities

### 2.1 The provenance claim is still wrong as committed (the one unaddressed correction)

The fifth pass did not touch §6 or the feedback-review postscript. The text still says:

> "The local reflog shows `e01ef6a` as a local `commit` about two minutes later, not a pull, so this was not copy drift between clones or concurrent writers."

Against the repository this is still contradicted: `git reflog` records `e01ef6a` as `pull: Fast-forward`; no other `xo-scratchpad` checkout was found in the searched roots and no reflog under `/home` or `/mnt` contains it; and the two commits are 05:03:47Z → 05:15:14Z (≈11.5 minutes), not two. The feedback-review "Second postscript" repeats the same assertion. The fifth-pass revision note also still says the fourth pass made "the §6 provenance note … state the actual cause" — so the document currently asserts a provenance claim it cannot evidence.

The fix remains the same as in the previous review: scope the statement to the authoring checkout and present it as the reviewer's account, not as repository evidence; or simply say the sequence cannot be verified from this clone, state the verifiable facts (seven edits present, later edits absent, commit parent/time), and keep the process fix. Update the postscript in the same edit.

### 2.2 Two different "19"s and two different "22"s

The numbers coincide by accident and the text conflates the sets:

- **F probe records = 19** (18 GAP + 1 constraint-pass `projection_value`/`projection_unit`). This is the "19 single-rule mutated records" in the Method row, and 19 × 1 + 3 timestamp FormatChecker re-runs = **22 validator runs**.
- **GAP items = 19** (18 F GAP + the section-D `pick_id` regex check) — the strength breakdown and the printed `=== GAP probes` line.
- **GAP lines printed = 22** (18 F GAP + 3 FormatChecker duplicate lines + 1 section-D line), which §3.1 calls "22 GAP lines = 19 probe records the schema accepts".

So §3.1's "22 … = 19" and the Method row's "19 … (22 …)" use the same numerals for different sets. Worse, the section-D item is a **regex check on an id string**, not a record the schema accepts; counting it as a "probe record the schema accepts" is inaccurate. Since the last two rounds were specifically about accounting accuracy, this needs one reconciliation sentence (and ideally either move the id mismatch into section F as a record-level probe, or label it separately).

### 2.3 `§3.6` still overreaches on `player_sk`

The reworded High line says "`minimum: 1` on `game_sk`/`team_sk`/`player_sk`", while item 14 now says `player_sk` positivity "is **not stated anywhere** … decide whether surrogate keys are positive by convention, state it, then add `minimum: 1`". Keep the two consistent: either name `game_sk`/`team_sk` only in the immediate schema edit and add "and `player_sk` once its positivity is stated", or reference item 14.

### 2.4 Minor wording

- The Method row still says "19 **single-rule** mutated records"; the Appendix and script now correctly say probes change the target field(s) plus premise fields (draw, cancelled, settled, moved-line). Align the Method wording.
- §3.1 says "the three timestamp probes are reported twice" — true, but it doesn't say the 22 GAP lines include the section-D line; the reconciliation in §2.2 covers this.
- The "permitted" and "not-stated" probes are not contract defects; the strength table says so, but the §3.1 sentence "19 probe records the schema accepts" could be read as 19 violations. Add "of which 2 are not requirement gaps (1 not-stated, 1 permitted)".

---

## 3. What does not change

The fifth pass does not move any substantive conclusion: the four requirement-level findings, the contract-seam defects and the bet-engine assessment stand. The classification strengthens the document's central quality claim — the JSON Schema is field-level sound, but 14 explicit prose rules (plus implied/provisional/not-stated entries) are unenforced and belong in `pattern`/`minimum`/§9.1/CI — while correctly de-escalating the two probes that are not violations.

## 4. Recommended edits (exact, small)

1. **§6 provenance bullet** — replace the reflog sentence with the scoped version recommended in the fourth-pass review: state the authoring-session account as reported, state that this repo received `e01ef6a` as a fast-forward pull (so the repo reflog and the ~11.5-minute timestamps do not evidence it), and keep the process fix.
2. **`conf-schema-contracts-assessment-feedback-review.md` second postscript** — same scoping; drop "were not copy drift between clones" as fact.
3. **§3.1 / Method reconciliation** — one sentence: "The 19 F-probe records (18 GAP + 1 constraint probe) account for 22 validator runs; the 19 GAP items are those 18 plus the section-D id-regex check, printed as 22 GAP lines including the 3 FormatChecker re-runs." Or relabel the numbers.
4. **§3.6** — `minimum: 1` for `game_sk`/`team_sk` now, `player_sk` only after item 14's decision.
5. **§3.1** — add "2 of the 19 are not requirement gaps (1 not-stated, 1 permitted)".
6. **Method row** — drop "single-rule" or say "one rule per probe"; Appendix A already explains the premise-field changes.

---

## 5. Limits

- I cannot inspect the authoring checkout's reflog; the review judges only what the shared repository can evidence and does not dispute that the authoring session may have seen a local commit. The problem is the sentence as committed, not the author's account.
- No contract or consumer file changed in this pass, so the earlier substantive verifications stand; this review re-ran the validator and re-checked the changed assessment text and probe definitions only.
- The strength classifications are my reading of the contract's may/should/must language; the pass's classification matches them except where noted.
