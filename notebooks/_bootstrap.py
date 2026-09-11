"""Put the repository root on sys.path so a notebook can import the modules.

The notebooks import the code; they never restate it. A cell that copies a
function already defined in a module creates a second version of it that stops
matching the first one the day either is corrected, and here there would be three
versions to keep in step: the paper, the Python and the C++.

Three lines instead of making the repository an installable package, because the
published way to run everything is `uv run tsp_transient.py` from the root, and
that must keep working.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)  # fixtures/ and candidates.json are resolved from the root
