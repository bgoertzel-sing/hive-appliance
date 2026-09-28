import sys
from run_review import E, run

run("trace-correction", [sys.executable, str(E / "correct_owner_traces.py")])
