import os
import sys
from run_review import E, R, run

env = os.environ.copy()
env.update(HIVE_SRC=str(R), PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(E / "guard"))
result = run("legacy-information-loss", [sys.executable, str(E / "legacy_information_loss.py")], E, env)
sys.exit(result["exit_code"])
