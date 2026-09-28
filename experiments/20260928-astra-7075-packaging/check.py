"""Isolated wheel build/install smoke for review 7075."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent.parent / "repos/hive-astra-7075"
results = []

def run(label, command, cwd):
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=180)
    (ROOT / (label + ".out")).write_text(result.stdout + result.stderr)
    results.append({"label": label, "command": command, "cwd": str(cwd), "exit": result.returncode})
    (ROOT / "results.json").write_text(json.dumps(results, indent=2))
    print(label, result.returncode, flush=True)
    return result.returncode == 0

if not run("build", [sys.executable, "-m", "build", "--wheel", "--outdir", str(ROOT / "wheels")], SOURCE):
    sys.exit(1)
with tempfile.TemporaryDirectory(prefix="hive-7075-wheel-") as folder:
    target = Path(folder)
    if not run("venv", [sys.executable, "-m", "venv", str(target / "venv")], target):
        sys.exit(1)
    python = str(target / "venv/bin/python")
    wheel = str(next((ROOT / "wheels").glob("*.whl")))
    if not run("install", [python, "-m", "pip", "install", "--no-index", "--no-deps", wheel], target):
        sys.exit(1)
    if not run("imports", [python, "-I", "-c", "import cli, controller.appliance, hive, conversation.client, recovery; print('installed imports OK')"], target):
        sys.exit(1)
    if not run("cli", [str(target / "venv/bin/hive-appliance"), "--help"], target):
        sys.exit(1)
