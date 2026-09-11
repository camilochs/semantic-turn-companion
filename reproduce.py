#!/usr/bin/env python3
"""Run everything in this repository and compare it against the frozen output.

    python3 reproduce.py                    the Python demos, the unit tests, and the C++ port
    python3 reproduce.py --with-notebooks   also execute the notebooks headless
    python3 reproduce.py --jit              also run the opt-in compile-emitted-C++ demo
    python3 reproduce.py --bless            rewrite expected/ from the current run

Standard library only, so the check itself carries no dependency. A step whose
tool is missing is reported as SKIP, never as a pass: the last line always says how
many passed, how many were skipped and how many failed, and the exit status is
non-zero if anything failed.

There is one expected file per demo, and both implementations are compared against
it. That is the point of the C++ port: if the two languages disagree, Algorithm 1
is under-specified in the paper, and this script is where that would show up.
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
EXPECTED = os.path.join(HERE, "expected")
CPP = os.path.join(HERE, "cpp")
NOTEBOOKS = os.path.join(HERE, "notebooks")

PASS, SKIP, FAIL = "PASS", "SKIP", "FAIL"
results: list[tuple[str, str, str]] = []          # (status, name, detail)


def record(status: str, name: str, detail: str = "") -> None:
    results.append((status, name, detail))
    mark = {PASS: "  ok  ", SKIP: " skip ", FAIL: " FAIL "}[status]
    print(f"[{mark}] {name}" + (f" — {detail}" if detail else ""))


def run(cmd: list[str], cwd: str = HERE) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def compare(name: str, produced: str, expected_file: str, bless: bool) -> None:
    path = os.path.join(EXPECTED, expected_file)
    if bless:
        os.makedirs(EXPECTED, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(produced)
        record(PASS, name, f"blessed {expected_file}")
        return
    if not os.path.exists(path):
        record(FAIL, name, f"no frozen output at expected/{expected_file} (run --bless)")
        return
    with open(path, encoding="utf-8") as fh:
        want = fh.read()
    if produced == want:
        record(PASS, name)
        return
    diff = "".join(difflib.unified_diff(
        want.splitlines(keepends=True), produced.splitlines(keepends=True),
        fromfile=f"expected/{expected_file}", tofile="produced", n=1))
    record(FAIL, name, "output differs")
    print(diff.rstrip("\n"))


# ── 1. the Python demos ──────────────────────────────────────────────────────
PY_DEMOS = [
    ("tsp_transient.py", ["python3", "tsp_transient.py"], "tsp_transient.txt"),
    ("bpp_amortized.py", ["python3", "bpp_amortized.py"], "bpp_amortized.txt"),
    ("ablation.py", ["python3", "ablation.py", "candidates.json"], "ablation.txt"),
]


def step_python(bless: bool) -> None:
    print("\n==> 1/5  Python demos")
    for name, cmd, exp in PY_DEMOS:
        rc, out = run(cmd)
        if rc != 0:
            record(FAIL, f"python {name}", f"exit {rc}")
            print(out)
            continue
        compare(f"python {name}", out, exp, bless)


# ── 2. the unit tests ────────────────────────────────────────────────────────
def step_tests() -> None:
    print("\n==> 2/5  Unit tests")
    if not os.path.isdir(os.path.join(HERE, "tests")):
        record(SKIP, "unit tests", "no tests/ directory")
        return
    rc, out = run(["python3", "-m", "unittest", "discover", "-s", "tests", "-q"])
    tail = [ln for ln in out.strip().splitlines() if ln.strip()][-1:] or [""]
    record(PASS if rc == 0 else FAIL, "unit tests", tail[0])
    if rc != 0:
        print(out)


# ── 3. the C++ port, against the same expected files ─────────────────────────
# Only the transient operator has a C++ port, and that is not an omission: its
# artifact is data (a permutation), so both languages can produce it and the
# outputs must match. The bin-packing operator emits *Python source* and executes
# it, which a C++ program cannot do without embedding an interpreter. Its C++
# counterpart is a different demo — one that emits C++ and compiles it — and it
# lives behind --jit.
CPP_DEMOS = [("tsp_transient", "tsp_transient.txt")]


def step_cpp(bless: bool) -> None:
    print("\n==> 3/5  C++ port (same expected output as Python)")
    if not os.path.isdir(CPP):
        record(SKIP, "C++ port", "no cpp/ directory")
        return
    compiler = os.environ.get("CXX") or shutil.which("g++") or shutil.which("c++")
    if not compiler:
        record(SKIP, "C++ port", "no C++ compiler on PATH")
        return
    rc, out = run(["make", "-s"], cwd=CPP)
    if rc != 0:
        record(FAIL, "cpp: make", f"exit {rc}")
        print(out)
        return
    record(PASS, "cpp: make", os.path.basename(compiler))
    for binary, exp in CPP_DEMOS:
        path = os.path.join(CPP, "bin", binary)
        if not os.path.exists(path):
            record(FAIL, f"cpp {binary}", "binary not built")
            continue
        rc, produced = run([path])
        if rc != 0:
            record(FAIL, f"cpp {binary}", f"exit {rc}")
            print(produced)
            continue
        # deliberately compared against the SAME file the Python demo is compared
        # against: the claim is that the two implementations agree line for line
        compare(f"cpp {binary} == python", produced, exp, bless=False)


# ── 4. the notebooks ─────────────────────────────────────────────────────────
def notebook_outputs(path: str) -> str:
    """Concatenate the text every cell printed in an executed notebook."""
    with open(path, encoding="utf-8") as fh:
        nb = json.load(fh)
    chunks = []
    for cell in nb.get("cells", []):
        for out in cell.get("outputs", []):
            if out.get("output_type") == "stream":
                chunks.append("".join(out.get("text", [])))
            elif out.get("output_type") in ("execute_result", "display_data"):
                chunks.append("".join(out.get("data", {}).get("text/plain", [])))
            elif out.get("output_type") == "error":
                chunks.append("\n".join(out.get("traceback", [])))
    return "\n".join(chunks)


# what each notebook must actually print; running without an exception is not reproduction
NOTEBOOK_CLAIMS = {
    "01_anatomy.ipynb": ["CANDIDATE", "accepted"],
    "02_validate_and_repair.ipynb": ["schema error", "syntax error", "feasibility"],
    "03_tsp_transient.ipynb": ["length 9.236", "best [0, 1, 2, 3, 4]  length 8.000"],
    "04_bpp_amortized.ipynb": ["first-fit start: total bins = 22", "total bins = 19  (gap 0.0%)"],
    "05_drop_channel_ablation.ipynb": ["[FULL]", "[ABLATED]", "optimal(gap=0)=3/3"],
}


def step_notebooks() -> None:
    print("\n==> 4/5  Notebooks")
    if not os.path.isdir(NOTEBOOKS):
        record(SKIP, "notebooks", "no notebooks/ directory")
        return
    if not shutil.which("uv"):
        record(SKIP, "notebooks", "uv not on PATH (needed to run Jupyter without installing it)")
        return
    with tempfile.TemporaryDirectory() as tmp:
        for name in sorted(NOTEBOOK_CLAIMS):
            src = os.path.join(NOTEBOOKS, name)
            if not os.path.exists(src):
                record(FAIL, f"notebook {name}", "missing")
                continue
            out_path = os.path.join(tmp, name)
            rc, out = run(["uv", "run", "--quiet", "--with", "jupyter",
                           "jupyter", "nbconvert", "--to", "notebook", "--execute",
                           "--output", out_path, src], cwd=NOTEBOOKS)
            if rc != 0 or not os.path.exists(out_path):
                record(FAIL, f"notebook {name}", "execution failed")
                print(out[-1500:])
                continue
            printed = notebook_outputs(out_path)
            missing = [c for c in NOTEBOOK_CLAIMS[name] if c not in printed]
            if missing:
                record(FAIL, f"notebook {name}", f"did not print: {missing}")
            else:
                record(PASS, f"notebook {name}")


# ── 5. the opt-in JIT demo ───────────────────────────────────────────────────
def step_jit(bless: bool) -> None:
    print("\n==> 5/5  Emitted-C++ demo (opt-in)")
    path = os.path.join(CPP, "bin", "bpp_ahd_jit")
    if not os.path.exists(path):
        record(SKIP, "cpp bpp_ahd_jit", "not built (run make -C cpp)")
        return
    rc, produced = run([path])
    if rc != 0:
        record(FAIL, "cpp bpp_ahd_jit", f"exit {rc}")
        print(produced)
        return
    # compared against the bin-packing golden file, the same one the Python demo
    # is compared against: the search is the same search whether the artifact it
    # emits is Python source or C++ source, and the trace says so
    compare("cpp bpp_ahd_jit == python bpp", produced, "bpp_amortized.txt", bless=False)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--with-notebooks", action="store_true", help="execute the notebooks headless")
    ap.add_argument("--jit", action="store_true", help="run the emitted-C++ demo")
    ap.add_argument("--bless", action="store_true", help="rewrite expected/ from this run")
    args = ap.parse_args()

    step_python(args.bless)
    step_tests()
    step_cpp(args.bless)
    if args.with_notebooks:
        step_notebooks()
    else:
        print("\n==> 4/5  Notebooks — not requested (pass --with-notebooks)")
    if args.jit:
        step_jit(args.bless)
    else:
        print("\n==> 5/5  Emitted-C++ demo — not requested (pass --jit)")

    npass = sum(1 for s, _, _ in results if s == PASS)
    nskip = sum(1 for s, _, _ in results if s == SKIP)
    nfail = sum(1 for s, _, _ in results if s == FAIL)
    print(f"\n{npass} passed, {nskip} skipped, {nfail} failed")
    return 1 if nfail else 0


if __name__ == "__main__":
    sys.exit(main())
