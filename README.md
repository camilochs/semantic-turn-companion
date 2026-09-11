# Companion code — *From Hand-Crafted to LLM-Based Variation Operators in Metaheuristics*

Runnable reference implementation for the tutorial. Everything here runs **offline,
with no API key and no network**: a deterministic mock model returns completions
from a fixed pool, so the whole loop — assemble the prompt, sample, parse and
validate, repair, select — executes end to end and reproduces exactly. An optional
Claude adapter is included for real runs.

The loop is here twice, in Python and in C++, and both are compared against the same
frozen output. That is the point of the port: if the two disagree, the algorithm as
written in the paper is under-specified, and `reproduce.py` is where that shows up.

```bash
python3 reproduce.py                    # everything that needs no extra tool
python3 reproduce.py --with-notebooks   # also runs the notebooks headless
```

Last line of that run:

```
11 passed, 0 skipped, 0 failed
```

## Start here

If you want to read rather than run, open the notebooks in order. Each one prints
its own output, so GitHub shows the trace without executing anything.

| Notebook | What it gives you |
|---|---|
| [`01_anatomy.ipynb`](notebooks/01_anatomy.ipynb) | the four parts of the operator running, with prompt, sample, verdict and decision as four separate events |
| [`02_validate_and_repair.ipynb`](notebooks/02_validate_and_repair.ipynb) | the three layers of the validator, each refusing a different bad reply, and the reason travelling into the repair prompt |
| [`03_tsp_transient.ipynb`](notebooks/03_tsp_transient.ipynb) | the traced iteration of the tutorial, and the same trace coming out of the C++ port |
| [`04_bpp_amortized.ipynb`](notebooks/04_bpp_amortized.ipynb) | the same loop searching program space, and what changes in the validator when the payload is code |
| [`05_drop_channel_ablation.ipynb`](notebooks/05_drop_channel_ablation.ipynb) | the drop-channel ablation, and a negative result read for what it is |

## What is in here

| File | Maps to | What it is |
|---|---|---|
| `search.py` | **Algorithm 1** | the reference build loop with bounded repair; keeps the incumbent the search walks (`cur`) apart from the best artifact seen (`best`), so it stays correct under an acceptance rule that may take a worsening move |
| `llm.py` | §*Developing LLM variation operators* | the model interface: offline `MockLLM`, optional `AnthropicLLM`, and the loader for the completion pools |
| `tsp_transient.py` | §*One traced iteration* | a **transient**, numeric-conditioned operator: it proposes a TSP tour directly |
| `bpp_amortized.py` | §*A second trace: a code-emitting operator* | an **amortized**, code-conditioned operator (FunSearch / EoH style): it emits a Python `priority(item, bins)` heuristic for online bin packing |
| `ablation.py`, `candidates.json` | App. *Placing every method: a drop-channel audit* | the drop-channel ablation: heuristics generated with and without the natural-language idea, scored by bin-packing gap |
| `fixtures/` | — | the completions the mock model returns, as text. One file, read by both languages: two copies of a pool drift on the first edit |
| `cpp/` | **Algorithm 1**, again | the loop in C++17, header-only, no third-party libraries. See [`cpp/README.md`](cpp/README.md) |
| `expected/` | — | the frozen output of every demo. One file per demo, and both implementations are compared against it |
| `tests/` | **Algorithms 1 and 2** | invariants the demos never exercise: non-monotone acceptance, exhausted retries, each reason the validator can refuse |
| `reproduce.py` | — | runs all of it and says what matched |

Artifacts are mapped to the paper by section title and appendix name, not by number:
the numbering moved between drafts and the titles did not.

## Run the pieces on their own

```bash
python3 tsp_transient.py             # transient solution-level operator
python3 bpp_amortized.py             # amortized code-emitting operator
python3 ablation.py candidates.json  # drop-channel ablation
make -C cpp && ./cpp/bin/tsp_transient   # the same trace, in C++
```

Python ≥ 3.9, standard library only. The notebooks are the one exception: they need
Jupyter, and `reproduce.py --with-notebooks` runs them through `uv` without
installing anything permanently.

Real output of `python3 tsp_transient.py`:

```
incumbent [0, 2, 3, 4, 1]  length 9.236
  step 0: accepted 8.0
  step 1: rejected 9.236
  step 2: rejected 10.893
best [0, 1, 2, 3, 4]  length 8.000
```

and of `python3 bpp_amortized.py`:

```
lower bound (total bins) = 19
first-fit start: total bins = 22  (gap 15.8%)
  step 0: rejected 22
  step 1: accepted 19
  step 2: rejected 22
  step 3: rejected 19
best heuristic: total bins = 19  (gap 0.0%)
```

The TSP run reproduces the traced iteration of the tutorial: the first sample,
`[0, 1, 4, 4, 2]`, is refused by the validator, and the repaired `[0, 1, 2, 3, 4]` is
accepted at length 8.000. The bin-packing run starts from first fit — 22 bins, 15.8%
above the lower bound on three fixed instances — and reaches best fit at 19. Every
number here is recomputed by the code.

## Using a real model (optional)

```bash
pip install anthropic
export ANTHROPIC_API_KEY=...
```

```python
from llm import AnthropicLLM
llm = AnthropicLLM(model="claude-opus-4-8", temperature=1.0)   # pin a dated snapshot
```

Swap the `MockLLM(...)` construction in either demo. Heuristics emitted by a real
model are executed in a restricted namespace with an import block
(`bpp_amortized.parse`). That is a weak sandbox: **harden it before running anything
a live model wrote**, and do not point a live model at the emitted-C++ demo outside a
container.

For a study rather than a demo, pin a dated model snapshot, fix and report the seed,
and run several independent repetitions. One run is not evidence.

## Validation of the placement rule

Two checks accompany this code, and they answer different questions.

**Is the labeling reproducible?** Three independent LLM coders — one instance each
from three model families — were shown only the placement rule and the channel
descriptions, and classified the twelve methods of the evidence table. They coincide
on nine of the twelve; chance-corrected agreement is Gwet's AC1 = 0.73. The
divergences fall on the placements whose channel description is least determinate.
The labeling is therefore largely reproducible, and it is contested exactly where the
channel description leaves the representation open.

**Does the channel carry weight?** `ablation.py` removes the natural-language idea
while holding the parent code and the scores fixed. On this bin-packing task both
conditions reach the optimum, so the natural-language channel is not load-bearing
here: the operator recovers the best-fit heuristic with it or without it. That is a
negative result and it is reported as one. How much a present channel contributes is
task-dependent.

To run your own ablation, regenerate the `{"FULL": [...], "ABLATED": [...]}` JSON with
`AnthropicLLM` or any operator and pass it the same way.

## Guard

*Semantic* is used here in its structural sense — which representation conditions the
next sample — never a mental one. No operator in this repository understands,
reasons, or holds a belief; each samples from a distribution conditioned on a prompt,
and everything the code reports is about what came out and whether it validated.

## License

MIT (see `LICENSE`). If you use this code, please cite the paper and this repository
(see `CITATION.cff`).
