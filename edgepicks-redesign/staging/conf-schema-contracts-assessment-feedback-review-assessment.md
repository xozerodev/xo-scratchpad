# Assessment of the feedback on the second-pass review

**Feedback under assessment:** the critical response to `conf-schema-contracts-assessment-feedback-review.md` (pasted by the user, 2026-10-21).
**Subject:** whether that response's five objections and six-point fix-up are correct, and what should happen to `conf-schema-contracts-assessment.md`.
**Method:** re-read the response against the committed files (`e01ef6a` assessment, `801e573` review), re-verified every arithmetic claim with exact fractions, re-read the embedded design mocks, checked the contract's wording for `b`, and examined the git history for the allegedly lost edits.

**Overall:** the response is **substantially correct and improves the work**. Four of its five substantive criticisms land; the fifth (the mock re-check) is half right — its factual catch is better than mine, but the "Wait" observation is confirmed, not speculation. Its proposed fix-up should be adopted with two changes: restore the lost edits from the session that holds them (they cannot be recovered from this clone), and add item 17 with the "stop calling `b` break-even" wording plus propagation to the consumer contracts. My review's −125 argument is withdrawn; the structural findings stand.

---

## 1. Where the response is right (verified)

### 1.1 The −125 argument was circular — withdraw it

Correct. My derivation fixed `p` from the mock's "+9% at −115" and then chose `t ≈ 5%` so that `b` landed on −125; a single free parameter fitted to a single data point proves nothing. The arithmetic behind the response's counter-examples checks out:

| Reading | `p` | Zero-edge `1/p` | `b` at −125 needs `t` |
| --- | --- | --- | --- |
| "+9%" as EV edge | 0.5830 | 1.7152 → **−140** | 4.94% (EV basis) |
| "+9%" as prob-basis edge | 0.6249 | 1.6003 → **−167** | 6.93% (prob basis) |
| mock's displayed 54% | 0.54 | 1.8519 → **−117** | EV edge at −125 = **−2.8%** |

So the example is internally inconsistent and cannot adjudicate the boundary at all; and my own §6 rule ("mocks are non-normative, prose is authoritative") forbids using it to settle the question. The correct conclusion is the one already in the review's practical recommendation — product must define the boundary — now with the response's better framing.

### 1.2 The confusion is the contract mislabelling `b` — a better finding than mine

Verified. The contract calls `b` the "**break-even decimal price**" at L124 (intro), L136 (the `b` table row), L154 (rule 4) and L155 (rule 5), and option-B repeats "**Break-even price b**" at `option-b-plan.md:181`. `b` is the price where edge equals the producer's threshold `t`, i.e. break-even only when `t = 0`. Renaming it to **"threshold price"** and leaving the consumer field `edge_holds_above` as-is is the right fix — better than anything in my review. It also generalises: the snapshot contract uses "break-even" in its edge-state table (L191–193), its `edge_holds_above` field description (L104), and the option-B mock generator (L464, L494). The rename should propagate to those docs, not only the producer contract.

### 1.3 "Wait" is not in the requirement's action vocabulary — a good catch I missed

Confirmed from the embedded mock (`ep_expanded_c2.png`, re-checked from the page attachments): the line-move card (LeBron 23.5 → 25.5 PTS, −125) shows Edge **"+3%"** and Rec. Action **"Wait"**; the +9% entry card shows **"Play"**; the EPL +0% card shows **"Pass"**. The requirement says "Rec. Action (Play, Watch, Pass)" (PB/726237185 v6 L266). So the mock's **Wait** is a second mock-vs-prose mismatch (alongside the "+2% Play" figure), directly relevant to D4 and the action vocabulary. The response is right that my review should have caught it rather than only noting the figure difference.

### 1.4 The missing edits were lost before the commit — cause accepted

The local git evidence supports the response's account: `e01ef6a` arrived as a **`pull: Fast-forward`** from `origin/main` (reflog), authored elsewhere as `Tze <tze@definitely.work>`; there are **no dangling blobs, stashes or other local copies** carrying §3.5 items 13–16, the §3.6 addition, the §6 tweak or the Appendix A probe note. So those edits never existed in this clone — they were lost in the copy that produced the commit, not invented and not recoverable here. The response's explanation (session copy vs committed copy, possibly concurrent writers) is the most plausible one. I withdraw "removed the pointer to the supporting analyses": it was absent from the base copy used for that commit, so the author did not deliberately remove it.

### 1.5 Item numbering and duplication — accept

The response is right that my proposed items 14–16 duplicated already-made edits (re-issue §3.3, AU X7, mock caveat §6) and that reusing their numbers 13–16 would clash. Withdraw those three; keep only the edge-boundary point as item 17. On the four lost items themselves:

- **13 unenforced timestamps — real.** `pick_date_time`/`observed_at` use `"format": "date-time"`, which in Draft 2020-12 is annotation-only by default; it neither requires millisecond precision nor a trailing `Z`, and none of the §9.1 invariants cover timestamp format.
- **14 missing positive minimums / min length — real, with specifics.** `game_sk`, `team_sk` and `player_sk` have no `minimum: 1` (the field reference says positive integers); `projection_unit` has no `minLength: 1` although the prose says non-empty. (`pick_id` already gets non-emptiness from its pattern; `minLength` there would be redundant — worth saying which field is meant.)
- **15 `current_edge` allowed null on an unchanged line — real strictness gap.** The schema has no conditional requiring `current_edge` when `observed_at`/`current_decimal_odds` are present and the line matches; only the §9.1 invariant 3 implies it, at test level.
- **16 cancelled picks keeping the old probability — needs a definition before it becomes an item.** `probability` is frozen by Rule 3, so a cancelled pick keeping the entry probability is by design. If the concern is that the re-evaluated probability which triggered `probability_moved` is not recorded anywhere, that is a real explainability gap — but it is an open modelling decision (a new field or a reason payload), not a demonstrated schema defect. State the consumer harm (audit? display?) and decide; otherwise it will read as a contradiction of Rule 3.

---

## 2. Where the response is wrong or overstated

### 2.1 "The review's main argument doesn't hold up" — only the −125 sub-argument does not

The review's two structural findings are factual: (a) the committed file lacks the sections its own revision note cites (true, now explained as copy loss), and (b) the mock action/figure differs from the prose and my reading of it was wrong in one respect (now corrected). The −125 argument was a supporting argument for a **non-blocking** reframing, not the main argument. Withdraw the −125 claim; the review's conclusion — the requirement's boundary is undefined, prose says "positive", contract should stop calling `b` break-even — is what the response itself recommends.

### 2.2 The mock re-check was not speculation

The response says it "can't confirm 'Wait'"; that is an access limitation, not evidence against. The mock is an embedded page attachment and does show **Wait**; the crop is at `.tmp/ep_expanded_c2.png` and re-fetchable from PB/726237185. The other half of the response's point stands: **Wait is not one of Play/Watch/Pass**, and my claim that D2's "+2% Play" is "a different design state" was an unverified guess. Correct wording: "the action shown varies across the design sources (Play / Wait / Pass); 'Wait' is not in the requirement's vocabulary; D2's +2% Play cannot be attributed to the same mock state."

### 2.3 The cause correction does not change the review's file-level finding

The review said "either the intended edits are missing or the note must be corrected" and did not assert fabrication. The response supplies the cause (lost before commit). Both are true: the file is incomplete relative to its note, and the cause is copy drift. The useful addition is procedural, not analytical: single-writer discipline for this file.

---

## 3. Assessment of the six-point fix-up

| # | Proposed action | Verdict |
| --- | --- | --- |
| 1 | Restore items 13–16 and the §3.6/§6/Appendix A edits | **Yes — but only the session that holds the text can supply it.** This clone and `origin/main` hold `e01ef6a` as-is; nothing is recoverable here. Restore from that copy, then diff against the committed file to confirm nothing else moved. |
| 2 | Add the edge-boundary point as item 17, worded as product decision + stop calling `b` break-even | **Yes**, with one addition: propagate the rename to the snapshot contract's edge-state table/`edge_holds_above` description and to option-B's block/`edgeHoldsAbove` docs. `edge_holds_above` itself keeps its name. |
| 3 | Reword the Updated Edge row (Play/Wait vary; drop "could not be re-checked") | **Yes.** Say the mock shows +3% with **Wait**; the +9% card shows Play; D2's +2% Play is unverified; all sources require a positive edge after a move. |
| 4 | Add the Rec. Action ↔ current-edge link to the Rec. Action row | **Yes — strong.** The mocks derive action from the current edge (+9% Play, +3% Wait, +0% Pass), so Rec. Action is blocked twice: `rec_action` is null and the current edge it needs is nulled after a line move. State both in the row. |
| 5 | Change the verdict sentence to "one row upgraded; overall conclusions unchanged" | **Yes.** |
| 6 | Decide the `.tmp` evidence question | **Recommendation:** commit a compact evidence bundle — `validate_contract.py` + `validate_out.txt` at minimum, ideally the three supporting analyses — under a new `staging/evidence/` directory, and point the assessment's method section at it. They are the audit trail behind the SQL, engine-commit and screenshot claims. If the raw analyses are not wanted in the repo, commit the validation artefacts and add a one-line note saying where the rest lives. Do not leave the claims with no discoverable evidence. |

**Before applying:** pull first (the review commit `801e573` is already on `origin/main`), then check the on-disk file hash against `e01ef6a` before editing; assign one writer and commit immediately after; the suspected cause of this incident is a second copy overwriting the first.

---

## 4. What does not change

Nothing in the assessment's conclusions moves: the record carries the card's data model but not the redesign (moved-line edge; Recommended Action — now doubly blocked because its input is also nulled; historical scope; market vocabulary), the seam defects remain (single writer, observation path, merge semantics, store/id scope, status crosswalk), and the NBA conclusion stands (state/persistence/lifecycle and a single-writer PE — not field conversion — are the engine's real work). The edge-boundary confusion is a contract-wording and product-definition item; it is not a schema-support failure, and the record can derive either boundary once the consumer decision is made.

---

*Not applied to the assessment; recommendations above are for the file's owner to execute, since the missing edits exist only in their session copy.*
