"""Preserve review inputs and execute each original harness and pytest once."""
import hashlib
import importlib.metadata as md
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time

E = Path(__file__).resolve().parent
R = E.parent.parent / "repos/hive-astra-7075"
S = E / "source"
OLD = E.parent / "20260927-astra-7024"

def save(name, value):
    (E / name).write_text(json.dumps(value, indent=2) + "\n")

def git(*args):
    return subprocess.check_output(["git", *args], cwd=R, text=True)

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def run(name, command, cwd, env, timeout=600):
    assert not (E / (name + "-exit.json")).exists(), "Refuse evidence overwrite"
    start = time.time()
    timed_out = False
    with (E / (name + ".stdout")).open("w") as out, (E / (name + ".stderr")).open("w") as err:
        process = subprocess.Popen(command, cwd=cwd, env=env, stdout=out, stderr=err, start_new_session=True)
        try:
            rc = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            import signal
            timed_out = True
            os.killpg(process.pid, signal.SIGKILL)
            rc = process.wait()
    result = dict(command=command, cwd=str(cwd), exit_code=rc,
                  timed_out=timed_out, wall_seconds=time.time() - start)
    save(name + "-exit.json", result)
    print(name, json.dumps(result), flush=True)
    return result

if __name__ == "__main__":
    assert git("rev-parse", "HEAD").strip() == "5de0d533a9070585c8c87129ba4c2598e3b7ac8b"
    assert not S.exists(), "Refuse rerun of single-suite launcher"
    S.mkdir()
    manifest = {}
    for name in filter(None, git("ls-files", "-z").split("\0")):
        src = R / name
        dst = S / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        manifest[name] = digest(src)
    save("source-sha256.json", manifest)
    versions = {}
    for name in ("pytest", "build", "setuptools", "wheel", "chromadb", "onnxruntime"):
        try:
            versions[name] = md.version(name)
        except md.PackageNotFoundError:
            versions[name] = None
    save("environment.json", dict(head=git("rev-parse", "HEAD").strip(),
         initial_git_status=git("status", "--porcelain"), python=sys.version,
         executable=sys.executable, platform=platform.platform(), versions=versions,
         model_provenance="User/parent reports selected gpt-6-astra and parent session_status openai/gpt-6-astra"))
    (E / "commit.diff").write_text(git("diff", "e6afe16..5de0d53", "--", "controller/reducer.py"))
    (E / "modified-tests.diff").write_text(git("diff", "e6afe16..5de0d53", "--", "tests"))
    (E / "tmp").mkdir(exist_ok=True)
    (E / "guard").mkdir(exist_ok=True)
    shutil.copy2(OLD / "guard/sitecustomize.py", E / "guard/sitecustomize.py")
    names = ["adversarial", "adversarial-inverted", "new_cases", "supplementary", "probes", "older-regressions", "independent"]
    provenance = {}
    for name in names:
        src = R / "experiments/20260927-astra-7024" / (name + ".py")
        shutil.copy2(src, E / src.name)
        provenance[src.name] = dict(source=str(src), sha256=digest(src),
                                    original_workspace_sha256=digest(OLD / src.name))
    save("copy-provenance.json", provenance)
    env = os.environ.copy()
    env.update(PYTHONDONTWRITEBYTECODE="1", PIP_NO_INDEX="1", HF_HUB_OFFLINE="1",
               TRANSFORMERS_OFFLINE="1", ANONYMIZED_TELEMETRY="False",
               TMPDIR=str(E / "tmp"), PYTHONPATH=str(E / "guard"),
               PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", HIVE_SRC=str(R))
    save("review-env-overrides.json", {k: env[k] for k in (
        "PYTHONDONTWRITEBYTECODE", "PIP_NO_INDEX", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE",
        "ANONYMIZED_TELEMETRY", "TMPDIR", "PYTHONPATH", "PYTEST_DISABLE_PLUGIN_AUTOLOAD", "HIVE_SRC")})
    for name in names:
        run(name.replace("_", "-"), [sys.executable, str(E / (name + ".py"))], E, env)
    run("pytest", [sys.executable, "-m", "pytest", "tests/", "-v", "-p", "no:cacheprovider",
                   "--basetemp=" + str(E / "pytest-tmp")], S, env)
    save("original-reruns-verification.json", dict(
        final_git_status=git("status", "--porcelain"),
        source_unchanged=all(digest(R / name) == value for name, value in manifest.items()),
        original_harnesses_unchanged=all(digest(OLD / name) == data["original_workspace_sha256"]
                                       for name, data in provenance.items())))
