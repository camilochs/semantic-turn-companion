# Companion code — *The Semantic Turn in Metaheuristics*

Runnable reference implementation for the tutorial **"The Semantic Turn in
Metaheuristics: A Tutorial on Conditioning, Building, and Choosing LLM Variation
Operators."**

Everything here runs **offline, with no API key and no network**: a deterministic
`MockLLM` returns completions from a fixed pool, so the full
build → sample → parse/validate → bounded-repair → select loop executes end to end
and reproduces exactly. An optional Claude adapter is included for real runs.

## Contents

| File | Maps to | What it is |
|------|---------|-----------|
| `search.py` | **Algorithm 1** | the reference build loop (bounded repair; keeps the incumbent `cur` separate from the best-so-far `best`, so it is correct under any acceptance rule) |
| `llm.py` | §4.2, Appendix B | pluggable LLM interface: offline `MockLLM` + optional `AnthropicLLM` |
| `tsp_transient.py` | **§4.4** | a *transient*, numeric-conditioned operator: proposes a TSP tour (a permutation) directly |
| `bpp_amortized.py` | **§4 / §5.2** | an *amortized*, code-conditioned operator (FunSearch/EoH style): emits a Python `priority(item, bins)` heuristic for online bin packing |
| `ablation.py` | **§3 / App. C** | drop-channel ablation harness: scores heuristics generated *with* vs *without* the natural-language channel by their bin-packing gap (validation of the placement rule) |

## Run

```bash
python3 tsp_transient.py             # transient solution-level operator
python3 bpp_amortized.py             # amortized code-emitting operator
python3 ablation.py candidates.json  # drop-channel ablation (Appendix C)
```

Requires only Python ≥ 3.9 (standard library). Expected output:

```
# tsp_transient.py
incumbent [0, 2, 3, 4, 1]  length 9.236
  step 0: accepted 8.0
  ...
best [0, 1, 2, 3, 4]  length 8.000

# bpp_amortized.py
lower bound (total bins) = 19
first-fit start: total bins = 22  (gap 15.8%)
  step 1: accepted 19
  ...
best heuristic: total bins = 19  (gap 0.0%)

# ablation.py candidates.json
[FULL]     n=3  valid=3   gap%: mean=0.0 ... optimal(gap=0)=3/3   implements least-slack idea: 3/3
[ABLATED]  n=3  valid=3   gap%: mean=0.0 ... optimal(gap=0)=3/3   implements least-slack idea: 0/3
```

The TSP run reproduces the traced iteration of §4.4 (invalid `[0,1,4,4,2]` →
repaired `[0,1,2,3,4]`, length 8.000). The bin-packing run starts from a first-fit
heuristic (22 bins, 15.8% above the lower bound on three fixed synthetic
instances) and discovers a best-fit heuristic (19 bins, optimal). Both numbers are
recomputed by the code, not hard-coded in the paper.

## Using a real LLM (optional)

```bash
pip install anthropic
export ANTHROPIC_API_KEY=...      # your key
```

```python
from llm import AnthropicLLM
llm = AnthropicLLM(model="claude-opus-4-8", temperature=1.0)   # pin a dated snapshot for a study
```

Swap the `MockLLM(...)` construction in either demo for `AnthropicLLM(...)`. The
heuristics emitted by a real model are executed in a restricted namespace with an
import block (see `bpp_amortized.parse`); **harden this sandbox before running
genuinely untrusted code** (Appendix B, "Validation and safety").

## Reproducibility (Appendix B)

- `MockLLM` is seeded and deterministic; the synthetic instances are fixed.
- For real-LLM runs, pin a dated model snapshot, fix and report the seed, and run
  multiple independent repetitions (a single run is not evidence).

## Validation of the placement rule (Appendix C)

- **Reproducibility.** Three independent coders applied the placement rule to the
  eleven surveyed methods from their channel descriptions and agreed on all eleven
  (Gwet's AC1 = 1.0) — the *labeling* is reproducible.
- **Load-bearing test.** `ablation.py` runs a drop-channel ablation: heuristics
  generated *with* vs *without* the natural-language idea (parent code + scores held
  fixed), scored by bin-packing gap. On the easy BPP task both conditions reach the
  optimum (mean gap 0%; 6/6 candidates optimal), so the natural-language channel is
  *not* load-bearing there — *how much* a present channel contributes is
  task-dependent. A reproducible example set ships as `candidates.json` (three FULL
  heuristics carrying the least-slack idea, three ABLATED ones without it); run it
  directly with `python3 ablation.py candidates.json`. To run your own ablation,
  regenerate the `{"FULL": [...], "ABLATED": [...]}` JSON with `AnthropicLLM` or any
  operator and pass it the same way.

## License

MIT (see `LICENSE`). If you use this code, please cite the paper and this
repository (see `CITATION.cff`).
