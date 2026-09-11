"""Drop-channel ablation for the placement rule (companion validation).

Tests whether the NATURAL-LANGUAGE 'idea' channel is load-bearing for an EoH-style
operator on online bin packing: does *removing* that channel change the distribution
of emitted heuristics? Candidate programs are generated externally by an LLM operator
under two conditions --
  FULL    = parent code + NL idea ('prefer least remaining slack') + scores
  ABLATED = parent code + scores only (NL idea removed)
-- and scored here by their bin-packing gap (objective, deterministic) and by whether
they implement the idea's structural marker (use of remaining slack b-item).

If the NL channel is load-bearing, FULL and ABLATED should differ.

Usage:  python3 ablation.py candidates.json
  candidates.json = {"FULL": ["def priority(item, bins): ...", ...], "ABLATED": [...]}
"""
import json
import sys
import statistics

from bpp_amortized import parse, evaluator, lower_bound_total
from llm import envelope

LB = lower_bound_total()


def gap(bins):
    return 100.0 * (bins - LB) / LB


def score(code):
    try:
        fn = parse(envelope(code))
    except ValueError as e:
        return None, str(e)
    return evaluator(fn), None


def uses_slack(code):
    c = code.replace(" ", "")
    return ("b-item" in c) or ("-(b-item)" in c) or ("item-b" in c)


def summarize(name, codes):
    rows = []
    for code in codes:
        bins, err = score(code)
        rows.append({"valid": err is None, "bins": bins,
                     "gap": None if bins is None else round(gap(bins), 1),
                     "slack_idea": uses_slack(code), "err": err})
    valid = [r for r in rows if r["valid"]]
    gaps = [r["gap"] for r in valid]
    print(f"\n[{name}]  n={len(codes)}  valid={len(valid)}")
    if gaps:
        print(f"  gap%: mean={statistics.mean(gaps):.1f}  min={min(gaps)}  max={max(gaps)}  "
              f"optimal(gap=0)={sum(1 for g in gaps if g == 0)}/{len(valid)}")
    print(f"  implements least-slack idea: {sum(r['slack_idea'] for r in valid)}/{len(valid)}")
    return rows


if __name__ == "__main__":
    data = json.load(open(sys.argv[1]))
    print(f"online BPP lower bound = {LB} bins; parent first-fit gap = {gap(22):.1f}%")
    for cond in ("FULL", "ABLATED"):
        summarize(cond, data.get(cond, []))
