# Companion code — *From Hand-Crafted to LLM-Based Variation Operators in Metaheuristics*

An LLM variation operator is easy to describe and fiddly to build. The model returns
text. Something has to find the answer inside that text, decide whether it is a
solution at all, and say what was wrong when it is not. That part is most of the
code, and it is the part a paper has no room for. So it is here, running.

Everything runs offline. A mock model returns completions from a fixed pool, so the
loop goes all the way through and lands on the same numbers every time, on any
machine, with no API key. There is an optional Claude adapter for real runs.

```bash
python3 reproduce.py --with-notebooks --jit
```

```
12 passed, 0 skipped, 0 failed
```

Python 3.9 and the standard library. The notebooks want Jupyter, and that command
runs them through `uv` without installing anything.

## Start with the notebooks

They print their output, so GitHub shows the traces without you running a thing.

1. [The anatomy of an operator](notebooks/01_anatomy.ipynb). Prompt, sample, verdict,
   decision. Four events, on a problem small enough to hold in your head.
2. [The validator](notebooks/02_validate_and_repair.ipynb). Three layers, each one
   refusing a different bad reply, and the reason travelling into the repair prompt.
3. [A transient operator](notebooks/03_tsp_transient.ipynb). The traced iteration of
   the tutorial, on TSP.
4. [An amortized operator](notebooks/04_bpp_amortized.ipynb). The same loop searching
   program space instead of solution space.
5. [The drop-channel ablation](notebooks/05_drop_channel_ablation.ipynb). The test the
   placement rule has to survive, and a negative result read for what it is.

## The demos

```bash
python3 tsp_transient.py
```

```
incumbent [0, 2, 3, 4, 1]  length 9.236
  step 0: accepted 8.0
  step 1: rejected 9.236
  step 2: rejected 10.893
best [0, 1, 2, 3, 4]  length 8.000
```

This is the traced iteration of the tutorial. The first completion the model returns
is `[0, 1, 4, 4, 2]`, which is not a tour: city 4 twice, city 3 missing. The validator
says so in those words, the words go back to the model, and the second attempt comes
back as `[0, 1, 2, 3, 4]`. The repair happens inside step 0, which is why the log
shows three steps and not four.

```bash
python3 bpp_amortized.py
```

```
lower bound (total bins) = 19
first-fit start: total bins = 22  (gap 15.8%)
  step 0: rejected 22
  step 1: accepted 19
  step 2: rejected 22
  step 3: rejected 19
best heuristic: total bins = 19  (gap 0.0%)
```

Same loop, different artifact. Here the model writes a `priority(item, bins)`
function and the search walks through programs. It starts from first fit at 22 bins
and finds best fit at 19, which is the lower bound. The model is paid once; the
heuristic it wrote then runs on new instances for free.

## The same loop in C++

Most metaheuristic code is written in C++, so the loop is there too, header-only,
C++17, nothing to install.

```bash
make -C cpp && ./cpp/bin/tsp_transient
```

That prints the five lines above, byte for byte. Both implementations are compared
against the same file, `expected/tsp_transient.txt`, which turns the port into the
strongest check in the repository: if the two ever disagree, Algorithm 1 as written
in the paper leaves something open, and `reproduce.py` is where it surfaces. I
checked it under `g++` and `clang++`.

There is a second one worth your time:

```bash
make -C cpp jit && ./cpp/bin/bpp_ahd_jit
```

The operator emits C++ and the loop compiles it. The middle layer of the validator
stops being a parser and becomes the compiler, and what the repair prompt hands back
is a compiler diagnostic. It reaches the same trace as the Python demo, 22 bins down
to 19. Whether the artifact is Python source or C++ source turns out to be a design
choice, and here is the evidence.

Do not point a live model at that demo outside a container. Compiling and running
whatever a model wrote is exactly as dangerous as it sounds. The candidate runs in
its own process, which is the only isolation on offer.

## What is in here

| File | Maps to | What it is |
|---|---|---|
| `search.py` | Algorithm 1 | the build loop with bounded repair. It keeps the incumbent the search walks apart from the best artifact seen, so it stays correct under an acceptance rule that may take a worsening move |
| `llm.py` | §*Developing LLM variation operators* | the model interface: offline `MockLLM`, optional `AnthropicLLM`, and the loader for the completion pools |
| `tsp_transient.py` | §*One traced iteration* | the transient, numeric-conditioned operator |
| `bpp_amortized.py` | §*A second trace: a code-emitting operator* | the amortized, code-conditioned operator |
| `ablation.py`, `candidates.json` | App. *Placing every method: a drop-channel audit* | the ablation behind the placement rule |
| `fixtures/` | | the completions the mock model returns. One file, read by Python and by C++, because two copies of a pool drift on the first edit |
| `cpp/` | Algorithm 1, again | the port and the emitted-C++ demo. See [`cpp/README.md`](cpp/README.md) |
| `expected/` | | the frozen output of each demo |
| `tests/` | Algorithms 1 and 2 | invariants the demos never reach: non-monotone acceptance, exhausted retries, each way the validator can refuse |
| `reproduce.py` | | runs all of it and says what matched |

Each artifact is mapped to the paper by section title, not by number. The numbering
moved between drafts and the titles held.

## Using a real model

```bash
pip install anthropic
export ANTHROPIC_API_KEY=...
```

```python
from llm import AnthropicLLM
llm = AnthropicLLM(model="claude-opus-4-8", temperature=1.0)
```

Swap the `MockLLM(...)` construction in either demo. What a real model writes is
executed in a restricted namespace with an import block, in `bpp_amortized.parse`.
That is a weak sandbox and I would not trust it with a live model on a machine I
cared about.

For a study rather than a demo: pin a dated model snapshot, fix and report the seed,
run several repetitions. One run is not evidence.

## Validation of the placement rule

Two checks, two different questions.

**Is the labeling reproducible?** Three LLM coders, one from each of three model
families, saw only the placement rule and the channel descriptions, and classified
the twelve methods of the evidence table. They coincide on nine. Chance-corrected
agreement is Gwet's AC1 = 0.73. The disagreements land on the rows whose channel
description leaves the representation open, which is where they should land.

**Does the channel carry weight?** `ablation.py` removes the natural-language idea
and holds the parent code and the scores fixed. On this bin-packing task both
conditions reach the optimum, so on this task the natural-language channel is not
doing the work: the operator gets to best fit with it or without it. That is a
negative result and the paper reports it as one. How much a present channel
contributes depends on the task.

To run your own, regenerate the `{"FULL": [...], "ABLATED": [...]}` JSON with
`AnthropicLLM` or any operator and pass it the same way.

## A note on the word semantic

It is used here in the structural sense: which representation conditions the next
sample. Nothing in this repository understands, reasons or believes. Each operator
samples from a distribution conditioned on a prompt, and everything the code reports
is about what came out and whether it validated.

## License

MIT, see `LICENSE`. If you use this code, cite the paper and the repository
(`CITATION.cff`).
