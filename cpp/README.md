# The C++ side

Most metaheuristic code is written in C++, so the loop of the tutorial is here as
well. `semantic_turn.hpp` is a translation of `search.py` and `llm.py`, not a
second design: same four functions in the spec (`render`, `parse`, `feasible`,
`repair_prompt`), same separation between the incumbent the search walks and the
best artifact seen.

```bash
make && ./bin/tsp_transient     # the traced iteration, same output as python3 tsp_transient.py
make jit && ./bin/bpp_ahd_jit   # opt-in: the operator emits C++, and the loop compiles it
```

## Why the port is also a test

`./bin/tsp_transient` and `python3 tsp_transient.py` are compared against the same
file, `expected/tsp_transient.txt`. They read the same completions from
`fixtures/tsp_pool.txt`. If the two disagree, the algorithm as written in the paper
is under-specified somewhere, and `reproduce.py` says so.

Two places where that nearly happens, both handled explicitly here rather than
inherited from whatever each language's library does:

- **Tie-breaking.** Python's `max(range(n), key=...)` returns the first maximum and
  so does `std::max_element`. They agree by coincidence of library behaviour, not by
  specification, so any tie-break in this code is written out instead of assumed.
- **Iteration order.** The coordinates are a `std::vector`, never a map. An
  unordered container is the usual way to lose cross-language identity quietly.

## The compiler flags are part of the claim

`-std=c++17 -O2` and nothing else. `-ffast-math`, `-Ofast` and `-march=native` let
the compiler contract floating-point operations, and then the tour length printed
here stops matching the one printed by Python. Verified with both `g++` and
`clang++`: byte-identical output.

Comparison is always on formatted text, never on raw doubles.

## What is not here, and why

- **No port of the bin-packing operator.** That demo emits Python source and runs
  it; a C++ program cannot do that without embedding an interpreter. The honest C++
  counterpart is `bpp_ahd_jit.cpp`, where the emitted artifact is C++.
- **No real model adapter.** The C++ side is mock-only. It exists to show the loop,
  not the transport; adding an HTTP client and a JSON library would double the
  dependencies of the repository to demonstrate nothing about the operator.
- **No CMake, no test framework, no templates beyond one.** A reader who last wrote
  C++11 should be able to follow this in one sitting.
