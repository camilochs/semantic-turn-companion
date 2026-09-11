# The C++ side

Most metaheuristic code is written in C++, and a reader who works there should not
have to read Python to lift the loop. So `semantic_turn.hpp` is the same algorithm:
the same four functions in the spec (`render`, `parse`, `feasible`,
`repair_prompt`), the same separation between the incumbent the search walks and the
best artifact seen. Header-only, C++17, no third-party libraries.

```bash
make && ./bin/tsp_transient     # the traced iteration
make jit && ./bin/bpp_ahd_jit   # the operator emits C++, and the loop compiles it
```

## The port is also a test

`./bin/tsp_transient` and `uv run tsp_transient.py` read the same completions from
`fixtures/tsp_pool.txt` and are compared against the same file,
`expected/tsp_transient.txt`. If they ever disagree, Algorithm 1 as written in the
paper leaves something open, and `reproduce.py` says which line.

Two places where they nearly disagreed, both written out here instead of left to
whatever each language's library happens to do:

**Tie-breaking.** Python's `max(range(n), key=...)` returns the first maximum and so
does `std::max_element`. They agree by coincidence of library behaviour, so the
tie-break in `bpp_ahd_jit.cpp` is spelled out in a loop where you can see it.

**Iteration order.** The coordinates are a `std::vector`. Reach for a hash map here
and the two languages quietly stop matching.

## The compiler flags are part of the claim

`-std=c++17 -O2` and nothing else. `-ffast-math`, `-Ofast` and `-march=native` let
the compiler contract floating-point operations, and then the tour length printed
here stops matching the one Python prints. I checked the output under `g++` and
`clang++`: identical bytes. Comparison is always on formatted text, never on raw
doubles.

## When the validator is a compiler

In `bpp_ahd_jit.cpp` the model writes C++ and the loop builds it. A candidate that
does not compile is refused with the compiler's own words, and those words are what
the repair prompt hands back. That is the middle layer of Algorithm 2, in the form a
C++ practitioner actually meets it.

The trace prints only that the build failed. A diagnostic is worded differently by
each compiler, and a file that claims to reproduce should not contain anything that
changes with the toolchain. Pass `--show-diagnostics` to see the real text.

The candidate is compiled to its own executable and invoked, rather than loaded into
this process, so a generated program that crashes or hangs takes only itself down.
That process boundary is thin. Do not point a live model at this demo outside a
container or a virtual machine.

## What is deliberately missing

There is no C++ port of `bpp_amortized.py`. That demo emits Python source and runs
it, and doing the same in C++ would mean embedding an interpreter. The honest
counterpart is the emitted-C++ demo above, which lands on the same trace anyway:
first fit at 22 bins, best fit at 19.

There is no real model adapter here either. The C++ side exists to show the loop,
and an HTTP client plus a JSON library would double the dependencies of the
repository to demonstrate nothing about the operator.

No CMake, no test framework, one template parameter. Someone who last wrote C++11
should get through this in one sitting.
