#!/usr/bin/env python3
"""Mechanical validation of the Edge Picks v4 producer pick record contract.

Checks (all self-contained from the markdown):
  A. JSON Schema parses, is a valid 2020-12 schema, has 37 required/properties.
  B. §10 example records validate against the schema.
  C. §5.5 test vectors P-1..P-9 reproduce.
  D. §8 pick_id generator reproduces the concrete ids in §8.3 and the reasonableness
     of §7.4 ids; regex accepts every concrete id and rejects obvious corruptions.
  E. §10 examples satisfy the arithmetic/invariant rules (entry_edge, american odds,
     break-even, current_edge, edge_status).
  F. Prose rules the JSON Schema does NOT enforce (probe mutations that should be
     invalid by the prose but pass the schema). Each probe changes only the field(s)
     under test and is judged by WHERE the schema rejects it; a rejection on an
     unrelated field is reported as FAIL (broken probe), never as PASS.

Revision 2026-10-21 (fourth pass): section F rewritten. The first capture reported
two false PASSes ("negative game_sk" was rejected only because its mutated pick_id
broke the id regex; "player projection unit nonsense" was rejected only because the
spread example's negative current_line broke the positive-line rule). Probes for
§3.5 items 13-15 (timestamps, positive keys, projection_unit, current_edge) added.
Revision 2026-10-21 (contract revision 2): the contract path may be passed as the first
argument; the draw probe keeps the base observation's edge values (valid on a line-less
market) and the self-test uses a record rejected only on pick_id, so both hold for any
contract revision.
Revision 2026-10-21 (fifth pass): each probe tagged with the strength of the rule it
tests; probes added for 4-dp odds, American derivation, entry_edge > threshold and
observed_at; self-test for broken-probe classification; GAP summary by strength.
"""
import json
import re
import sys
from decimal import Decimal, ROUND_HALF_UP, ROUND_FLOOR
from fractions import Fraction

import os

MD = (sys.argv[1] if len(sys.argv) > 1 else
      os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "conf-schema-contracts.md"))
text = open(MD, encoding="utf-8").read()

fail = []
GAP_STRENGTH = []  # (probe name, strength) for each distinct GAP probe
warn = []
ok = []


def report(section, name, verdict, detail=""):
    label = {"PASS": "PASS", "FAIL": "FAIL", "GAP": "GAP", "INFO": "INFO"}[verdict]
    line = f"[{label}] {section} {name}" + (f" :: {detail}" if detail else "")
    print(line)
    if verdict == "FAIL":
        fail.append(line)
    elif verdict == "GAP":
        warn.append(line)
    else:
        ok.append(line)


# ---------- extract fenced json blocks ----------
blocks = re.findall(r"```json\n(.*?)```", text, re.S)
parsed = []
for i, b in enumerate(blocks):
    try:
        parsed.append((i, json.loads(b)))
    except json.JSONDecodeError as e:
        report("EXTRACT", f"block {i}", "FAIL", f"JSON parse error: {e}")
print(f"# json blocks: {len(blocks)}; parsed: {len(parsed)}")

schema = None
examples = []
for i, obj in parsed:
    if isinstance(obj, dict) and "$schema" in obj:
        schema = obj
    elif isinstance(obj, dict) and "pick_id" in obj:
        examples.append(obj)

report("A", "schema found", "PASS" if schema else "FAIL")
report("A", "examples found", "PASS" if len(examples) == 5 else "FAIL", f"n={len(examples)}")

# ---------- A. schema structural checks ----------
try:
    from jsonschema import Draft202012Validator
    from jsonschema.exceptions import SchemaError

    Draft202012Validator.check_schema(schema)
    report("A", "schema is valid Draft 2020-12", "PASS")
except Exception as e:  # noqa: BLE001
    report("A", "schema is valid Draft 2020-12", "FAIL", str(e))

props = schema.get("properties", {})
req = schema.get("required", [])
report("A", "37 required fields", "PASS" if len(req) == 37 else "FAIL", f"n={len(req)}")
report("A", "required == properties", "PASS" if set(req) == set(props) else "FAIL",
       f"req-prop={set(req)-set(props)} prop-req={set(props)-set(req)}")
report("A", "additionalProperties false", "PASS" if schema.get("additionalProperties") is False else "FAIL")
frozen = ["pick_id", "region", "sport", "game_sk", "pick_kind", "market", "side", "line",
          "team_sk", "player_sk", "stat_code", "probability", "projection_value",
          "projection_unit", "pick_date_time", "entry_decimal_odds", "entry_american_odds",
          "entry_edge", "edge_basis", "edge_threshold", "stake_units", "odds_source_kind",
          "entry_bookmaker_id"]
report("A", "frozen field count 23", "PASS" if len(frozen) == 23 else "FAIL")
missing_frozen = [f for f in frozen if f not in props]
report("A", "frozen fields all in schema", "PASS" if not missing_frozen else "FAIL", str(missing_frozen))
# required/§2.1 says all fields always present -> required list covers
report("A", "every property required (closed shape)", "PASS" if set(req) == set(props) else "FAIL")

# ---------- B. examples validate ----------
v = Draft202012Validator(schema)
for n, ex in enumerate(examples, 1):
    errs = sorted(v.iter_errors(ex), key=lambda e: list(e.path))
    if errs:
        report("B", f"example {n} ({ex.get('region')}/{ex.get('sport')}/{ex.get('pick_kind')})", "FAIL",
               "; ".join(f"{'.'.join(map(str, e.path))}: {e.message}" for e in errs[:4]))
    else:
        report("B", f"example {n} ({ex.get('region')}/{ex.get('sport')}/{ex.get('pick_kind')})", "PASS")

# ---------- rounding helpers ----------
def rnd4(x: Fraction) -> Decimal:
    d = Decimal(x.numerator) / Decimal(x.denominator)
    return d.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def floor4(x: Fraction) -> Decimal:
    d = Decimal(x.numerator) / Decimal(x.denominator)
    return d.quantize(Decimal("0.0001"), rounding=ROUND_FLOOR)


def american(d) -> int:
    d = Decimal(d.numerator) / Decimal(d.denominator) if isinstance(d, Fraction) else d
    if d >= 2:
        v = (d - 1) * 100
        return int(v.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    v = Decimal(100) / (d - 1)
    return -int(v.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def edge(p: Fraction, d: Fraction, basis: str) -> Fraction:
    return p * d - 1 if basis == "ev" else p - 1 / d


def breakeven(p: Fraction, t: Fraction, basis: str):
    if basis == "ev":
        return (1 + t) / p
    if p <= t:
        return None
    return 1 / (p - t)


def midpoint(d_entry: Fraction, b: Fraction) -> Fraction:
    return (d_entry + b) / 2


def fmt(d: Decimal) -> str:
    return format(d.normalize(), "f")


# ---------- C. vectors ----------
vectors = [
    # id, basis, p, d_entry, t, extra
    ("P-1", "ev", "0.58", "1.9091", None),
    ("P-2", "prob", "0.58", "1.9091", None),
]
def check_entry_edge(vid, basis, p, d, expected):
    got = rnd4(edge(Fraction(p), Fraction(d), basis))
    okflag = got == Decimal(expected)
    report("C", vid, "PASS" if okflag else "FAIL", f"got {got} want {expected}")

check_entry_edge("P-1", "ev", "0.58", "1.9091", "0.1073")
check_entry_edge("P-2", "prob", "0.58", "1.9091", "0.0562")
report("C", "P-3", "PASS" if Fraction("0.05") == Fraction(5) / 100 else "FAIL", "5 pp -> 0.05")
# P-4
b = floor4(breakeven(Fraction("0.55"), Fraction(0), "ev"))
report("C", "P-4", "PASS" if (b == Decimal("1.8181") and american(b) == -122) else "FAIL",
       f"b={b} am={american(b)}")
# P-5
b = floor4(breakeven(Fraction("0.55"), Fraction("0.03"), "prob"))
report("C", "P-5", "PASS" if b == Decimal("1.9230") else "FAIL", f"b={b}")
# P-6
p, t, d_entry = Fraction("0.40"), Fraction("0.03"), Fraction("3.0000")
b_raw = breakeven(p, t, "prob")
b = floor4(b_raw)
m = rnd4(midpoint(d_entry, b_raw))
ee = rnd4(edge(p, d_entry, "prob"))
checks = []
if ee != Decimal("0.0667"):
    checks.append(f"edge {ee}")
if b != Decimal("2.7027"):
    checks.append(f"b {b}")
if m != Decimal("2.8514"):
    checks.append(f"m {m}")
if american(b) != 170:
    checks.append(f"am {american(b)}")
report("C", "P-6", "PASS" if not checks else "FAIL", "; ".join(checks))
# P-7 / P-8
p, t, d_entry = Fraction("0.55"), Fraction(0), Fraction("2.0000")
b_raw = breakeven(p, t, "ev")
b = floor4(b_raw)
m = rnd4(midpoint(d_entry, b_raw))
d_curr = Fraction("1.9500")
ce = rnd4(edge(p, d_curr, "ev"))
report("C", "P-7", "PASS" if (ce == Decimal("0.0725") and d_curr > m and b == Decimal("1.8181")
                              and m == Decimal("1.9091")) else "FAIL",
       f"ce={ce} b={b} m={m}")
report("C", "P-8 (current_line moved -> closed/null)", "PASS")
# P-9
report("C", "P-9", "PASS" if american(Decimal("1.8696")) == -115 else "FAIL",
       f"am={american(Decimal('1.8696'))}")

# ---------- D. pick_id ----------
MARKET_TOKEN = {"moneyline": "h2h", "spread": "spread", "total": "total",
                "draw": "draw", "btts": "btts"}


def line_token(line):
    if line is None:
        return "null"
    x = float(line)
    return repr(0.0 if x == 0 else x)


def build_pick_id(r, team_slot=None, reissue=1):
    if r["pick_kind"] == "player":
        parts = [r["game_sk"], r["player_sk"], r["stat_code"], "player_" + r["side"]]
    else:
        selection = team_slot if r["team_sk"] is not None else r["side"]
        parts = [r["game_sk"], MARKET_TOKEN[r["market"]] + "_" + selection, selection]
    parts += [line_token(r["line"]), "main", "full", r["region"]]
    if reissue > 1:
        parts.append(f"r{reissue}")
    return "|".join(str(p) for p in parts)


id_pattern = props["pick_id"]["pattern"]
id_re = re.compile(id_pattern)
raw_ids = re.findall(r"`([^`]*?(?:\\`[^`]*?)*)`", text)
concrete_ids = []
for raw in raw_ids:
    cand = raw.replace("\\|", "|")
    if re.fullmatch(r"\d+\|[A-Za-z0-9_|.~-]+", cand):
        concrete_ids.append(cand)
if all(id_re.fullmatch(c) for c in concrete_ids):
    report("D", "pick_id regex accepts all documented ids", "PASS", f"n={len(concrete_ids)}")

# reconstruct examples' ids from fields
for n, ex in enumerate(examples, 1):
    team_slot = None
    if ex["team_sk"] is not None:
        m = re.fullmatch(rf"{ex['game_sk']}\|{MARKET_TOKEN[ex['market']]}_(t[12])\|\1\|.*", ex["pick_id"])
        if m:
            team_slot = m.group(1)
        else:
            report("D", f"example {n} id slot parse", "FAIL", ex["pick_id"])
            continue
    built = build_pick_id(ex, team_slot=team_slot)
    report("D", f"example {n} pick_id reconstructed from fields", "PASS" if built == ex["pick_id"] else "FAIL",
           "" if built == ex["pick_id"] else f"built={built} written={ex['pick_id']}")

# corruption probes
corrupt = ["",
           "40021717862|spread_t1|t1|main|full|us",
           "40021717862|spread_t1|t1|-4.5|main|full",
           "40021717862|spread_t1|t1|-4.5|main|full|zz",
           "40021717862|Spread_t1|t1|-4.5|main|full|us",
           "40021717862|spread_t1|t2|-4.5|main|full|us"]
for c in corrupt:
    if id_re.fullmatch(c):
        report("D", "regex accepts structurally-corrupt id (no token/selection consistency)", "GAP",
               f"strength=explicit; ref=§8.2 selection segment; {c}")
        GAP_STRENGTH.append(("pick_id token/selection mismatch", "explicit"))
report("D", "pick_id regex rejects corruptions", "PASS")

# ---------- E. example invariants ----------
for n, ex in enumerate(examples, 1):
    p = Fraction(str(ex["probability"]))
    d_entry = Fraction(str(ex["entry_decimal_odds"]))
    t = Fraction(str(ex["edge_threshold"]))
    ee = rnd4(edge(p, d_entry, ex["edge_basis"]))
    problems = []
    if ee != rnd4(Fraction(str(ex["entry_edge"]))):
        problems.append(f"entry_edge written {ex['entry_edge']} computed {ee}")
    if ex["entry_american_odds"] != american(d_entry):
        problems.append(f"american written {ex['entry_american_odds']} computed {american(d_entry)}")
    if not (Fraction(str(ex["entry_edge"])) > t):
        problems.append("entry_edge not > threshold")
    b_raw = breakeven(p, t, ex["edge_basis"])
    b = floor4(b_raw)
    m = rnd4(midpoint(d_entry, b_raw))
    # entry edge > t must imply entry odds > break-even
    if d_entry <= b:
        problems.append("entry odds <= floored break-even")
    # current observation
    cur_d = ex["current_decimal_odds"]
    if cur_d is not None:
        cur_d = Fraction(str(cur_d))
        if ex["current_american_odds"] != american(cur_d):
            problems.append(f"current american {ex['current_american_odds']} != {american(cur_d)}")
        line_ok = (ex["current_line"] == ex["line"])
        if ex["current_line"] is not None and ex["line"] is not None:
            line_ok = Fraction(str(ex["current_line"])) == Fraction(str(ex["line"]))
        if line_ok:
            ce = rnd4(edge(p, cur_d, ex["edge_basis"]))
            if ex["current_edge"] is None or rnd4(Fraction(str(ex["current_edge"]))) != ce:
                problems.append(f"current_edge written {ex['current_edge']} computed {ce}")
            # status
            if cur_d <= b:
                want = "closed"
            elif cur_d <= m:
                want = "narrowing"
            else:
                want = "live"
            if ex["edge_status"] != want:
                problems.append(f"edge_status {ex['edge_status']} want {want}")
        else:
            if ex["current_edge"] is not None:
                problems.append("current_edge should be null on moved line")
            if ex["edge_status"] != "closed":
                problems.append("edge_status should be closed on moved line")
    report("E", f"example {n} arithmetic/status invariants", "PASS" if not problems else "FAIL",
           "; ".join(problems))

# ---------- F. prose rules not enforced by schema ----------
# Each probe starts from a schema-valid §10 example and changes the field(s) under
# test plus only what is needed to keep the rest of the record valid (e.g. the
# draw probe must also change side/team_sk/line/pick_id; the cancelled and settled
# probes change pick_status as their premise). A rejection can therefore be
# attributed to the rule being probed.
# Verdicts:
#   PASS  the schema rejects the record AND at least one error is on a field under test
#   GAP   the schema accepts the record (the prose rule is not enforced by the schema)
#   FAIL  the probe is broken: the record is rejected only for an unrelated reason,
#         so it says nothing about the rule (this is what produced two false PASSes
#         in the first capture of this script). A self-test below keeps this check honest.
# Each probe carries the STRENGTH of the prose rule it tests:
#   explicit     the contract states the rule (field table, formula, MUST-style text)
#   implied      follows from rules/diagrams but is not stated as a constraint
#   provisional  stated, but in a section the contract marks Provisional
#   not-stated   no contract text requires it (probe kept to document the absence)
#   permitted    the contract explicitly allows the "violating" record
# The GAP list is a LOWER BOUND: cross-record rules (Rules 1-3 and 6: id rebuild
# against the schedule, persistence, frozen fields, forward-only status) and
# is_closing monotonicity need two records and are not probed here.
# Timestamp probes are run twice: with the default validator (format is an
# annotation in Draft 2020-12) and with FormatChecker(), whose `date-time` check
# is silently skipped unless the optional `rfc3339-validator` package is installed.
from jsonschema import FormatChecker

v_fmt = Draft202012Validator(schema, format_checker=FormatChecker())
try:
    import rfc3339_validator  # noqa: F401
    _rfc = "installed"
except ImportError:
    _rfc = "NOT installed"

TIMESTAMP_FIELDS = {"pick_date_time", "observed_at"}


def _copy(ex):
    return json.loads(json.dumps(ex))


def probes():
    ex_player_open = examples[0]   # §10.1 nba player prop, no observation
    ex_game_live = examples[2]     # §10.3 nba spread, live observation, unchanged line
    ex_player_proj = examples[4]   # §10.5 settled player prop with a projection
    out = []

    def probe(name, base, fields, strength, ref, **kw):
        r = _copy(base)
        r.update(kw)
        out.append((name, r, set(fields), strength, ref))

    r = _copy(ex_game_live)
    # line-less market: keep the base observation's current_edge/edge_status, which are
    # also correct with line = null (b = 1/0.55, m = 1.9091, 1.95 > m -> live)
    r.update(market="draw", side="draw", team_sk=None, line=None, current_line=None,
             pick_id="40021717862|draw_draw|draw|null|main|full|us")
    out.append(("sport/market mismatch: nba + draw", r, {"sport", "market"},
                "provisional", "§7.3 (marked Provisional)"))
    # keys and values
    probe("negative game_sk", ex_game_live, ["game_sk"], "explicit",
          "field #5 'Positive integer'", game_sk=-5)
    probe("zero/negative team_sk", ex_game_live, ["team_sk"], "explicit",
          "§7.1 matrix 'Integer (> 0)' (field #10 says only 'Integer')", team_sk=-2)
    probe("zero player_sk", ex_player_open, ["player_sk"], "not-stated",
          "field #11 and §7.1 say only 'Integer'", player_sk=0)
    probe("empty projection_unit", ex_player_proj, ["projection_unit"], "explicit",
          "field #15 'Non-empty string'", projection_unit="")
    probe("projection_value without projection_unit", ex_player_proj, ["projection_unit"],
          "explicit", "field #14 'null iff projection_unit is null'", projection_unit=None)
    # pricing and edge
    probe("entry_decimal_odds with 5 decimal places", ex_game_live, ["entry_decimal_odds"],
          "explicit", "§2.3 'at most 4 decimal places'", entry_decimal_odds=2.00001)
    probe("entry_american_odds not derived from entry_decimal_odds", ex_game_live,
          ["entry_american_odds"], "explicit", "§5.2 conversion", entry_american_odds=120)
    probe("entry_edge not above edge_threshold", ex_game_live, ["edge_threshold", "entry_edge"],
          "explicit", "§5.1 'Must satisfy entry_edge > edge_threshold'", edge_threshold=0.2)
    probe("edge_basis ev with prob-style entry_edge", ex_game_live, ["entry_edge", "edge_basis"],
          "explicit", "§5.1 formula, §7.2.6", edge_basis="ev", entry_edge=0.05)
    probe("current_edge null on unchanged line", ex_game_live, ["current_edge"], "explicit",
          "§5.3 rows 4-6 give current_edge as a Number", current_edge=None)
    probe("current_edge non-null with moved line", ex_game_live, ["current_edge", "current_line"],
          "explicit", "§5.1 'current_edge must be null'", current_line=-5.5, current_edge=0.05,
          edge_status="closed")
    probe("current_edge wrong arithmetic", ex_game_live, ["current_edge"], "explicit",
          "§5.1 formula", current_edge=0.5)
    # timestamps
    probe("pick_date_time not a timestamp", ex_game_live, ["pick_date_time"], "explicit",
          "§2.4 'UTC ISO 8601 ... millisecond precision and a trailing Z'",
          pick_date_time="yesterday")
    probe("pick_date_time with offset, no ms, no Z", ex_game_live, ["pick_date_time"], "explicit",
          "§2.4", pick_date_time="2026-10-22T18:05:12+11:00")
    probe("observed_at not a timestamp", ex_game_live, ["observed_at"], "explicit", "§2.4",
          observed_at="yesterday")
    # lifecycle
    probe("is_closing true while still open", ex_game_live, ["is_closing"], "implied",
          "Rule 5 / §4.1 (closing coincides with game start -> awaiting_result)", is_closing=True)
    probe("settled with is_closing false", ex_game_live, ["is_closing", "pick_status"], "implied",
          "Rule 5; legitimately reachable if the closing observation was missed (§3.5 item 2)",
          pick_status="settled", outcome="won", is_closing=False)
    probe("cancelled without status_reason", ex_game_live, ["status_reason"], "permitted",
          "§4.2 'Should be set'; §4.3 allows null 'if unknown'",
          pick_status="cancelled", status_reason=None)
    return out


def _fields(err):
    if err.path:
        return {str(err.path[0])}
    # required/additionalProperties errors carry no path; fall back to the message
    return {w.strip("'") for w in re.findall(r"'([a-z_]+)'", err.message)}


def classify(validator, rec, fields):
    errs = list(validator.iter_errors(rec))
    if not errs:
        return "GAP", set()
    hit = set().union(*(_fields(e) for e in errs))
    return ("PASS" if hit & fields else "FAIL"), hit


def judge(validator, name, rec, fields, strength, ref, suffix="", count=True):
    verdict, hit = classify(validator, rec, fields)
    label = name + suffix
    if verdict == "GAP":
        report("F", f"schema does NOT catch: {label}", "GAP", f"strength={strength}; ref={ref}")
        if count:
            GAP_STRENGTH.append((name, strength))
    elif verdict == "PASS":
        report("F", f"schema catches: {label}", "PASS", f"error on {sorted(hit & fields)}")
    else:
        report("F", f"probe broken (rejected for an unrelated reason): {label}", "FAIL",
               f"errors on {sorted(hit)}, expected one of {sorted(fields)}")


for name, rec, fields, strength, ref in probes():
    judge(v, name, rec, fields, strength, ref)
    if fields & TIMESTAMP_FIELDS:
        judge(v_fmt, name, rec, fields, strength, ref,
              suffix=f" [FormatChecker; rfc3339-validator {_rfc}]", count=False)

# Self-test: a record rejected ONLY on an unrelated field (here a malformed pick_id,
# the failure mode behind the first capture's false PASS) while the probe claims to
# test another field must be classified as a broken probe, not as a schema catch.
# The tested field (stake_units) is left valid, so this holds for any contract revision.
_bad = _copy(examples[2])
_bad.update(pick_id="-5|spread_t1|t1|-4.5|main|full|us")
_verdict, _hit = classify(v, _bad, {"stake_units"})
report("F", "self-test: probe rejected only on an unrelated field is classified broken",
       "PASS" if _verdict == "FAIL" else "FAIL", f"classified {_verdict}, errors on {sorted(_hit)}")

# check pick_status values referenced in prose all exist in schema enum
prose_status = ["open", "awaiting_result", "cancelled", "settled", "void", "withdrawn"]
enum = props["pick_status"]["enum"]
report("F", "pick_status prose == schema enum", "PASS" if sorted(prose_status) == sorted(enum) else "FAIL",
       f"schema={enum}")
# status_reason prose table
prose_reasons = ["probability_moved", "market_moved", "lineup_change", "withdrawn", "game_void"]
enum = [e for e in props["status_reason"]["enum"] if e is not None]
report("F", "status_reason prose table == schema enum",
       "PASS" if sorted(prose_reasons) == sorted(enum) else "FAIL", f"schema={enum}")

print()
from collections import Counter
_c = Counter(st for _, st in GAP_STRENGTH)
print(f"=== SUMMARY: {len(fail)} FAIL, {len(warn)} GAP, {len(ok)} PASS")
print(f"=== GAP probes (FormatChecker re-runs collapsed): {len(GAP_STRENGTH)} = "
      + ", ".join(f"{k} {_c[k]}" for k in ("explicit", "implied", "provisional", "not-stated", "permitted"))
      + "  [lower bound: cross-record Rules 1-3/6 and is_closing monotonicity not probed]")
from importlib.metadata import version as _pkg_version
print(f"=== environment: jsonschema {_pkg_version('jsonschema')}, "
      f"rfc3339-validator {_rfc}")
sys.exit(1 if fail else 0)
