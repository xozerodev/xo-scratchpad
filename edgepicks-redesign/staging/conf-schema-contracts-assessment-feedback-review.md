# Review of the 2026-10-21 second-pass feedback on the producer-contract assessment

**Reviewed:** commit `e01ef6a` *"updated schema feedback"* against `14f07cb` *"add schema review/assessment"* in `xo-scratchpad` — 7 changed lines in `edgepicks-redesign/staging/conf-schema-contracts-assessment.md`.
**Review date:** 2026-10-21 · **Method:** read the commit diff, re-read the changed rows against the contract and Confluence v6, re-inspected the redesign page's embedded mock screenshots (the images are available as page attachments; they were fetched and read directly), and re-computed the threshold/edge arithmetic with exact fractions.

**Overall:** the second pass is directionally right and improves the requirements analysis — 4 of the 7 edits should be kept as-is, 2 need refinement, and 1 (the revision note) claims edits that are not in the commit. **No overall conclusion changes**: the record still carries the card's data, and still cannot deliver the redesign unchanged (moved-line edge, Recommended Action, historical scope, vocabulary gaps).

---

## 1. Verdict on each change

| # | Changed item | Verdict | Note |
| --- | --- | --- | --- |
| 1 | §0 bullet: "Six contract decisions" → "Six of the twelve contract decisions in §4.7" | **Accept** | §4.7 does contain exactly 12 numbered decisions (verified); the qualifier is more accurate. |
| 2 | §2.1 *Updated Edge* row: adds a note that specs D2 says "+2% Play" vs the mock's "+3% Edge", and that images can't be re-checked via markdown export | **Partially accept** | The figure difference is real, but the instruction is inaccurate: the mocks are embedded image attachments and **were re-checked**. The mock shows **"+3% Edge" with Rec. Action "Wait"**, not Play — so "…'+3% Edge' and Play" (kept from the first pass) is wrong. |
| 3 | §2.1 *Positive Edge odds threshold* row: verdict **Partial → Supported (derivable)**, with the zero-edge vs threshold-t distinction | **Accept with reframing** | The math is correct (see §2.1). But the design's own "-125" example is evidence **for** the contract's `b` (threshold price), not against it — see §2.2. Keep the upgraded verdict; reword the "trap" as a product/display decision, not a contract defect. |
| 4 | §2.1 *Edge availability* row: replaces "collapses to closed" with "closed fires at `d <= b`, i.e. edge falls to t, not zero (P-5 example)" | **Accept with reframing** | Arithmetic verified (P-5: `b = 1.9230`; zero-edge `1/p = 1.8182`). But "two mismatches with requirement 9" presumes requirement 9 means zero-edge; the requirement's own −125 example matches `b` at `t ≈ 5%` (p ≈ 0.583) and is nowhere near `1/p` (−140). Treat it as an **unresolved product definition**, not a proven mismatch. The line-move half of the finding stands unchanged. |
| 5 | §3.3 *Re-issue* bullet: "unimplementable as specified" → "needs state the contract does not assign"; checking can read `n` from the id suffix | **Accept** | Correct correction: a producer test can recover `n` from `\|r{n}` and rebuild, so §9.1 invariant 1 only needs to say so; the real gap is **minting** `n`, which needs the store. |
| 6 | §3.4 X7: adds AU truthfulness — the record can state an honest AU source, but option-B's v7 block labels every AU pick `{market_average, "Avg. Odds"}` regardless of the record | **Accept** | Verified: block table says "AU always `market_average`, 'Avg. Odds'"; producer-record appendix confirms "AU ⇒ market average"; the engine clones a US book into AU. The AU price/source/edge/b is a producer + product decision, not only display masking. |
| 7 | Revision note (replaces the "Supporting analyses" line): says corrections were folded into "§3.5 items 13–16, §6 and Appendix A" | **Reject / fix** | The commit contains **no** §3.5, §6 or Appendix A changes (only §0, §2.1 rows, §3.3, §3.4 X7). §3.5 still ends at item 12. Either the intended edits are missing or the note must be corrected. Also: the supporting-analyses pointer was removed, and `.tmp/` is now gitignored, so the evidence trail behind the assessment is no longer discoverable from the repo. |

Also note: the revision note says "No verdict changed direction", but item 3 **did** change one row's verdict (Partial → Supported). The overall assessment direction is unchanged; the sentence should say so more precisely.

---

## 2. Detail and evidence

### 2.1 The threshold arithmetic is right

For both bases the **zero-edge** price is `1/p`:
- EV: `p·d − 1 > 0 ⇔ d > 1/p`.
- Prob: `p − 1/d > 0 ⇔ d > 1/p`.

The contract's `b` (§5.1) is the price where edge equals the producer's threshold `t`: `b_ev = (1+t)/p`, `b_prob = 1/(p−t)`; both reduce to `1/p` iff `t = 0`. The P-5 vector numbers in the feedback are exact: `p = 0.55`, `t = 0.03`, prob basis → `b = 1.9230` (American −108), while `1/p = 1.8182` (−122). So the sentence "closed fires when edge falls to t, not zero" is correct.

### 2.2 But the requirement's own example points at `b`, not `1/p`

The requirement text pairs "*FanDuel −115 | +9% Edge*" with "*This edge stays positive above −125*". Solving the mock's own example:
- `+9%` at `−115` (decimal 1.8696) implies `p ≈ 0.5830`.
- Zero-edge price `1/p = 1.7152` → **−140**, not −125.
- Threshold price `b_ev` with `t ≈ 5%` = `1.05 / 0.5830 = 1.8010` → **−125** exactly.

And if `t = 0`, the example would have to read "…above −140". So the requirement's phrase "positive Edge odds threshold — stays positive above −125" most plausibly means **"clears the producer's minimum threshold" (the contract's `b`)**, even though the copy says "positive". The design's mock numbers are internally inconsistent elsewhere (`54%` probability at `−115` is +1% EV, not +9%), so they are illustrative; nevertheless the one concrete threshold figure in the requirement lands on `b`, not on `1/p`.

Consequence for the review: the second pass's *math* is worth keeping, but its "two mismatches with requirement 9" overstates. The honest finding is:

- The record supplies everything needed to derive **both** boundaries (`probability` for `1/p`; `probability` + `edge_basis` + `edge_threshold` for `b`), so the schema itself supports the requirement either way.
- The consumer contracts must agree on which boundary "Edge holds above / Positive Edge odds threshold" displays: both the snapshot and the v7 plan use `b` (`edge_holds_above = edgeHoldsAbove({probability, basis, edge_threshold})`), which matches the requirement's −125 example.
- The open item is the **wording and the product definition of t** (and, if product wants the zero-edge boundary, then the BFF must derive `1/p` instead and the "stays positive above" copy becomes correct). This belongs next to D4/D3 in the decision list, not in the schema-defect list.

### 2.3 The updated-edge mock, re-checked from the page attachments

The embedded `Edge Picks - Expanded` mocks (fetched as page attachments; not lost in a markdown export) show:
- **76ers moneyline** — FanDuel −115, Edge **+9%**, Rec. Action **Play** (no line).
- **LeBron Over 23.5 PTS** — entry FanDuel **−115**, current line **25.5 PTS**, current **−125**, Edge **"Pick +9%" / "↘ +3%"**, Rec. Action **Wait**.
- **EPL Man Utd ML** — PaddyPower +125 → −105, Edge **+8%** / **+0%**, Rec. Action **Pass**.
- **MLB Under 8.5 Runs** — FanDuel +120 → −105, Edge **+9%** / **+3%**.

So the load-bearing design fact is confirmed — a **positive edge is recomputed after a line change** (LeBron's line moves 23.5 → 25.5 and the card still shows +3%) — but the action for that card is **Wait**, not Play. "Play" is the entry +9% card. `specs.md` D2's "+2% Play" is a different data point (another design state or the Figma's later iteration); it is not the same mock. Correct the row to:

> The embedded mock shows a line move (entry 23.5 → current 25.5, current odds −125) with a recomputed **"+3% Edge"** and Rec. Action **"Wait"**; the +9% entry card shows "Play". specs D2 refers to a "+2% Play" state. The exact figure/action vary across design revisions and the mock's probability/edge numbers are internally inconsistent, so treat the screenshots qualitatively — but all of them require the edge at the current line, which the record cannot supply.

This also strengthens the Rec. Action finding (unchanged row): the design derives the action from the **current** edge, including after a line move — i.e. the one value the record is explicitly forbidden to compute. The second pass did not connect these two rows; it should.

---

## 3. Corrections to apply to the assessment

1. **Revision note** — either add the intended §3.5 items/§6/Appendix edits in a follow-up commit, or rewrite the note to match the actual delta: "§0, §2.1 (updated edge, positive-edge threshold, edge availability), §3.3, §3.4 X7. One verdict upgraded (positive-edge threshold); overall conclusions unchanged." Do not claim §3.5 items 13–16, §6 or Appendix A changes that are not in the file.
2. **Updated Edge row** — replace "…'+3% Edge' and Play" with "…'+3% Edge' and **Wait** (Play is the +9% entry card)", and drop "the Confluence markdown export drops images, so it could not be re-checked": the mocks are embedded attachments and were re-checked; note instead that the figure/action differ across design revisions and the mock arithmetic is illustrative.
3. **Positive Edge threshold row** — keep "Supported (derivable)", but replace "semantic trap" with a product-definition note: the record supports either boundary; the requirement's −125 example actually matches the contract's `b` at t ≈ 5% and is inconsistent with `1/p` (−140), so the display must choose and the requirement copy needs correcting. The snapshot and v7 block both already display `b`.
4. **Edge availability row** — keep the P-5 arithmetic and the line-move clause, but reword "two mismatches with requirement 9" to "the requirement's 'positive Edge range' is undefined: if it means zero-edge (`1/p`), `edge_status = closed` (at `b`) fires early and the BFF must not map it straight to 'edge no longer available'; if it means 'clears the producer's threshold', the contract is already correct. The −125 example favours the latter." This is a product/BFF-contract item, not a proven schema defect.
5. **Verdict sentence** — change "No verdict changed direction" to "No overall conclusion changed; one row's verdict was upgraded (positive-edge threshold became derivable)."
6. **Traceability** — the evidence files (`.tmp/req-mapping.md`, `.tmp/nba-engine-gaps.md`, `.tmp/ecosystem-coherence.md`, validation output) are now gitignored and the pointer to them was removed. Either commit them under the staging tree (as prior analyses are committed) or keep a short "evidence capture" note in the document. An assessment whose claims cite live SQL, engine commits and screenshot readings is hard to audit without them.
7. **Add to §3.5** (the four items the revision note promised but that are missing) — suggested items 13–16:
   - 13. **Edge-boundary semantics** — define whether the availability/threshold boundary is zero-edge (`1/p`) or the producer's threshold price (`b`), and make the requirement copy, `edge_status`, snapshot `edge_holds_above` and v7 block agree (product + contract).
   - 14. **Re-issue invariant wording** — §9.1 invariant 1 should say the `|r{n}` suffix is read back from the id and that minting `n` is a store responsibility.
   - 15. **AU source/price decision** — a record can name an honest AU source, but the v7 block masks every AU pick as `market_average`/"Avg. Odds"; product must decide the AU price (US mirror, computed average, or new feed) because it determines the AU record's `entry_edge`/`b`, not only the display.
   - 16. **Mock evidence caveat** — the design mocks are illustrative and arithmetically inconsistent (54% probability at −115 is not +9% edge); conclusions must rest on the prose requirements and the decisions, not on mock numbers.

---

## 4. What does not change

The first-pass conclusions stand, including the four requirement-level findings:

1. **Updated Edge after a line move** — the record structurally nulls `current_edge` when `current_line != line`; no probability-at-new-line field exists. The mocks confirm the design needs it, now with the action (Wait) also depending on it.
2. **Recommended Action** — `rec_action` is force-null in 4.0.x and typed `null`; the mocks show actions derived from current edge (+9% Play, +3% Wait, +0% Pass), so both the field and the moved-line edge are needed, plus product thresholds.
3. **Historical picks** — no record field is needed; the contract needs scope/coexistence rules and the consumer contract needs `era`. The product cut-off (publish date) vs KDD-002 (game start) disagreement is unresolved.
4. **Contract seam defects** — writer/ownership, merge ordering, storage/id scope, status crosswalk and the dropped single-writer premise remain the blocking coherence issues for implementation.

The NBA bet-engine conclusions are unaffected: field conversion is secondary; persistence/freeze/lifecycle plus a single-writer PE and observation path are the real work, and the contract decisions (including the edge-boundary definition) are on the critical path.

---

*Review only; the committed assessment was not modified. The corrections above can be applied in a follow-up edit if wanted.*

---

**Postscript (same day):** these corrections were applied to `conf-schema-contracts-assessment.md` in the follow-up commit; see its revision note.
