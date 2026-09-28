import os
import sys
from run_review import E, R, run

env = os.environ.copy()
env.update(HIVE_SRC=str(R), PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(E / "guard"))
result = run("semantic", [sys.executable, str(E / "semantic_probes.py")], E, env)
sys.exit(result["exit_code"])
