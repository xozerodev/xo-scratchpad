# Review of the fourth pass — validator false-PASS fix, counts and provenance

**Reviewed:** commit `05ac852` *"assessment: fix validator false passes, correct counts and provenance"* (parent `7f592eb`), 5 files changed.
**Files:** `conf-schema-contracts-assessment.md` (+31/−…), `evidence/validate_contract.py` (section F rewritten), `evidence/validate_contract-output.txt` (re-captured), `evidence/README.md`, and a second postscript in `conf-schema-contracts-assessment-feedback-review.md`.
**Method:** read the full diff; re-ran the old and new validator scripts with `uv run --with jsonschema` and again with `rfc3339-validator`; inspected the error attribution of each disputed probe; checked the committed output byte-for-byte; verified every cited contract/snapshot/option-B line; checked the repo's reflog and commit timestamps against the new provenance claim.

---

## 0. Verdict

**The correction is right, and it corrects an error I made.** The two "false PASSes" in my third-pass Appendix A are real: the probes never tested their rule, and the rewritten section F is a genuine methodological improvement. The new counts are reproducible and the `rfc3339-validator` account is exact.

**But two statements in the new text are wrong or unsupported**, and three need scoping before the document is accurate:

1. **Provenance (§6, and the feedback-review postscript):** the claim that "the local reflog shows `e01ef6a` as a local commit about two minutes later, not a pull" is not supported by this repository — its reflog records `e01ef6a` as `pull: Fast-forward`, no other checkout on this machine contains that commit, and the shared history's timestamps are ~11.5 minutes apart, not two. The cause narrative may be true in the authoring checkout, but as written it is unverifiable here and contradicted by the committed repo.
2. **§3.6 rationale:** moving schema-hardening to High is defensible, but the justification "strictness gaps partly covered by §9.1 already" contradicts the same document's Appendix A: only the `current_edge` case is partly covered; timestamps, key positivity and `projection_unit` are "covered nowhere".
3. **Precision:** "15 distinct prose rules" is a **lower bound that mixes hard, implied and "should" rules**, one of which (`player_sk > 0`) is not stated in the contract at all; "regression-checked by re-introducing the old `game_sk` probe" describes a manual check that is not in the script; and the method paragraph still says "10 mutated records".

The assessment's conclusions do not change; the corrected numbers strengthen, rather than weaken, the case for §9.1/producer-CI enforcement.

---

## 1. What the fourth pass gets right (verified)

| Claim | Verification |
| --- | --- |
| The first capture contained two false PASSes | Re-ran the old script (`7f592eb` version): **0 FAIL, 9 GAP, 39 PASS**, including `[PASS] F schema catches: negative game_sk` and `… player projection unit nonsense`. Validating the old mutated records directly: the game_sk probe's only error is `pick_id` ("-5\|…" fails the id regex); the projection probe's only error is `current_line` ("-4.5 is less than or equal to the minimum of 0"). Neither error is on the rule under test. **Correct diagnosis.** |
| New capture: 0 FAIL, 17 GAP, 38 PASS | Re-ran section F from the committed bundle: output is **byte-identical** to `evidence/validate_contract-output.txt`; `grep` counts are 38 PASS / 17 GAP / 0 FAIL; 15 distinct rules after the two duplicated timestamp lines. |
| `rfc3339-validator` behaviour (item 13) | With the README's `uv run --with jsonschema` setup, `FormatChecker.checkers` has **no `date-time`** entry and `conforms("yesterday", "date-time")` returns `True` silently; both timestamp probes are GAP twice. With `--with rfc3339-validator`, the run is **0 FAIL, 16 GAP, 39 PASS**: `"yesterday"` is caught, the offset form (`+11:00`, no ms, no `Z`) still validates, because RFC 3339 permits both. The item-13 text and its proposed `pattern` are exactly right. |
| New section-F methodology | The probe harness now starts from a §10 example, declares the fields under test, and reports FAIL when the only errors are elsewhere. This is the right fix for the class of error; the `projection_value`/`projection_unit` pairing is correctly identified as the one constraint probe the schema catches. |
| Item 17 references completed | Verified: contract L120 (section heading "…Break-Even…"), L122 (5.1 heading), L124, L136, L154, L155; `bff-to-app-contract.md` L104 (`edge_holds_above` description), L191–193 (edge-state table), L206 ("no break-even"); `option-b-plan.md` L181 and L494 ("above its break-even"). |
| Rec. Action addition | The mock's +3% card is "Wait" while the +9% card is "Play"; the inference that D4 needs a Play threshold above zero (not a sign test) follows, given the mock vocabulary caveat already in §6. |
| Counts propagated consistently | §3.1, Appendix A, README and the committed output all say 0/17/38 (15 distinct); no unresolved "9 GAP / 39 PASS" remains except in the correction narratives, where it is labelled as the old capture. |

---

## 2. What is wrong or needs scoping

### 2.1 Provenance — the reflog claim is not supported by this repository (blocking factual error)

The new §6 bullet states: *"The local reflog shows `e01ef6a` as a local `commit` about two minutes later, not a pull, so this was not copy drift between clones or concurrent writers."*

Checked in this repo:

- `git reflog` records `e01ef6a HEAD@{4} pull: Fast-forward` — it arrived by pull from origin, not as a local commit.
- No other checkout of `xo-scratchpad` was found in the searched roots (`/home`, `/mnt`, `/tmp`, `/var/tmp`, and a filesystem-wide search to depth 6), and a search of the git directories under `/home` and `/mnt` found no reflog containing `e01ef6a` — so the "local reflog" being cited is not available here.
- The shared timestamps are `14f07cb` 2026-10-21 05:03:47Z and `e01ef6a` 2026-10-21 05:15:14Z — **≈11.5 minutes**, not "about two minutes".
- The second postscript in `conf-schema-contracts-assessment-feedback-review.md` repeats the claim as fact ("were not copy drift between clones: the second-pass session wrote a snapshot …").

The *cause narrative* is plausible and the commit content is consistent with it (exactly seven edits, none of the later ones). But the document may not present an unverifiable external reflog as evidence, and "not copy drift" is itself too strong: the pointer to the supporting analyses was present in `14f07cb` but absent from `e01ef6a`, which implies the working copy used for the second pass had already diverged from the committed file — which is a copy-drift symptom, even if no concurrent writer overwrote anything.

**Fix:** scope and soften, e.g. *"In the authoring checkout the reviewer reports `e01ef6a` as a local commit taken from an interim snapshot; this repository cannot verify that sequence — it received `e01ef6a` as a fast-forward pull, and the branch history records the two commits ~11.5 minutes apart. What is verifiable here: the committed file contains exactly the seven changes and lacks items 13–16 and the §3.6/§6/Appendix edits."* Update the feedback-review postscript with the same scope.

### 2.2 §3.6 rationale contradicts Appendix A

The moved edit now reads: *"hardening … — strictness gaps partly covered by §9.1 already, so not sign-off blocking"*. Appendix A says the opposite for three of the four: *"the sport/market vocabulary, key positivity, timestamp shape, `pick_status`↔`is_closing` pairing, cancel-reason presence and token/id consistency are covered nowhere"*. Only the `current_edge` presence case is partly covered by §9.1 invariant 3.

**Fix:** keep it in High if desired, but justify it as *"cheap contract hardening that does not block engine work"* and correct the coverage claim: *"only the `current_edge` presence case is partly covered by §9.1; the timestamp, key-positivity and `projection_unit` checks are covered nowhere and belong in the schema or §9.1 before sign-off."*

### 2.3 "15 distinct prose rules" is a lower bound, mixing hard / implied / soft requirements

The 15 distinct rules include at least:

- **hard, explicit:** sport↔market matrix, `game_sk` positive, `team_sk > 0` (§7.1), non-empty `projection_unit`, timestamp ms+Z (§2.4), `current_edge` null on a moved line, `current_edge` arithmetic and `edge_basis` consistency (§9.1), `pick_id` token↔selection (§8.2/§8.4);
- **implied, not explicit:** `current_edge` present on an unchanged line (§5.1 "computed only when…" is a guard, not a duty; §6.4's Null-When list is not exhaustive), `is_closing: true` while `open`, settled with `is_closing: false` (Rule 5/§1.1 imply a closing observation, but a pick with no observation is schema-legal);
- **soft ("should"):** cancelled with null `status_reason` (§4.2 says "Should be set");
- **not stated:** `player_sk > 0` — the field table calls it an integer surrogate key and §7.1 only requires an integer; unlike `game_sk` ("Positive integer") and `team_sk` (>0 in §7.1), the contract does not state positivity for `player_sk`.

Also, the probe set is **not exhaustive**: unprobed prose rules include `entry_edge > edge_threshold`, the 4-decimal odds limit, `entry_american_odds` derivation, `observed_at`'s format (only `pick_date_time` probed), and all cross-record Rules 1–3 (some covered by §9.1). Phrase the headline as *"15 distinct rules probed (not exhaustive)"*, or classify by strength, before turning them into contract edits — adding `player_sk`/`is_closing` constraints as if they were explicit requirements would over-constrain the contract.

### 2.4 "Regression-checked by re-introducing the old `game_sk` probe" — no such check exists

The committed script contains no self-test for the false-PASS class: it has the corrected probes and comments only. The old malformed probe is not in the script. The claim should read "manually re-checked" unless an actual regression probe is added (recommended: keep the old malformed record as a fixture and assert `judge()` returns FAIL for it).

### 2.5 Stale method line and probe-isolation wording

- The Method row still says *"probed the schema with 10 mutated records"* — the new section F has 15 probes (17 runs, counting the two format-checker variants). Update the number.
- Appendix A says each probe *"changes only the field(s) under test"* — not literally true for the market/draw probe (which rewrites `market`, `side`, `team_sk`, `line`, `current_line`, `current_edge`, `edge_status` and `pick_id`) or the cancelled probe (which changes `pick_status` to reach the state). The judging logic handles this; reword to *"starts from a schema-valid example and changes the fields needed to probe the rule; an error is attributed by field path"*.
- §3.1's "17 GAP lines = 15 distinct" is environment-specific; say "in the recorded environment (`rfc3339-validator` not installed)".

---

## 3. What this means for the assessment

- The fourth pass is a **net improvement**: my third-pass evidence claim was wrong, the fix is sound, and the corrected result is reproducible from the committed bundle (`diff` is empty on re-run). The evidence bundle now meets its purpose.
- The corrected numbers **do not change the verdict**; if anything they strengthen the "schema is not fully machine-verifiable" finding and the recommendation to move the enforceable rules into a schema `pattern`/`minimum` and the rest into §9.1/producer CI.
- The remaining errors are **wording/evidence problems, not analytical ones**: fix the provenance claim, the §3.6 rationale, the regression wording, and scope the count. None of the four requirement-level findings, the seam findings, or the bet-engine conclusions move.

## 4. Recommended edits (exact)

1. **§6 provenance bullet** — replace the reflog sentence with the scoped version in §2.1; keep the process fix; add *"not verifiable from this repository"* rather than asserting the authoring sequence.
2. **feedback-review second postscript** — same scoping; drop "were not copy drift between clones" as fact.
3. **§3.6 High paragraph** — replace *"strictness gaps partly covered by §9.1 already, so not sign-off blocking"* with the corrected coverage sentence and *"cheap hardening, not engine-blocking"*.
4. **Appendix A** — *"regression-checked by re-introducing the old `game_sk` probe"* → *"manually re-checked; add the old malformed probe as a FAIL-expected self-test"*; add the strength classification and "not exhaustive"; fix the isolation wording.
5. **Method row** — "10 mutated records" → "15 probes (17 runs including the two format-checker variants)".
6. **§3.1** — add "(recorded environment: no `rfc3339-validator`)" to the 17/15 figure.

---

## 5. Limits

- The authoring checkout's reflog cannot be inspected from this machine; the review therefore judges only what the shared repository can evidence. It does not dispute that the authoring session saw a local commit — only that the sentence as committed is unsupported and contradicted by this repo's history.
- No contract or consumer files were changed by the fourth pass, so the earlier substantive verifications stand; this review re-ran only the validation and checked the cited lines.
- The semantic classification of probes (hard/implied/soft) is my reading of the contract text, not a claim about the author's intent; the fix is to label them, not to remove them.
