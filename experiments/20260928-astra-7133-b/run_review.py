"""Copy pinned inputs, preserve each child result, run full pytest only once."""
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
R = Path(os.environ.get("HIVE_SRC", E.parent.parent / "repos/hive-astra-7133")).resolve()
OLD = E.parent / "20260928-astra-7075"
S = E / "source"
PIN = "623c92be3e2ab96fd76024881066628b6c73abb5"
NAMES = ["adversarial", "adversarial-inverted", "new_cases", "supplementary", "probes", "older-regressions", "independent"]

def save(name, value):
    (E / name).write_text(json.dumps(value, indent=2) + "\n")

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def git(*args):
    return subprocess.check_output(["git", *args], cwd=R, text=True)

def environment():
    env = os.environ.copy()
    env.update(PYTHONDONTWRITEBYTECODE="1", PIP_NO_INDEX="1", HF_HUB_OFFLINE="1",
               TRANSFORMERS_OFFLINE="1", ANONYMIZED_TELEMETRY="False",
               TMPDIR=str(E / "tmp"), PYTHONPATH=str(E / "guard"),
               PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", HIVE_SRC=str(R))
    return env

def run(name, command, cwd=None, timeout=600):
    marker = E / (name + "-started.json")
    with marker.open("x") as f:
        json.dump(dict(command=command, started=time.time()), f)
    start = time.time()
    timed_out = False
    with (E / (name + ".stdout")).open("x") as out, (E / (name + ".stderr")).open("x") as err:
        p = subprocess.Popen(command, cwd=cwd or E, env=environment(), stdout=out,
                             stderr=err, start_new_session=True)
        try:
            rc = p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            import signal
            timed_out = True
            os.killpg(p.pid, signal.SIGKILL)
            rc = p.wait()
    result = dict(command=command, cwd=str(cwd or E), exit_code=rc,
                  timed_out=timed_out, wall_seconds=time.time()-start)
    save(name + "-exit.json", result)
    print(name, json.dumps(result), flush=True)
    return result

if __name__ == "__main__":
    assert git("rev-parse", "HEAD").strip() == PIN
    S.mkdir()
    manifest = {}
    for name in filter(None, git("ls-files", "-z").split("\0")):
        src, dst = R / name, S / name
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
    save("environment.json", dict(head=PIN, initial_git_status=git("status", "--porcelain"),
         python=sys.version, executable=sys.executable, platform=platform.platform(),
         versions=versions, model_provenance="Selected gpt-6-astra per requesting parent"))
    (E / "commit.diff").write_text(git("diff", "5de0d53..623c92b", "--", "controller/reducer.py", "hive/reducer.py"))
    (E / "modified-tests.diff").write_text(git("diff", "5de0d53..623c92b", "--", "tests"))
    (E / "tmp").mkdir(exist_ok=True)
    (E / "guard").mkdir(exist_ok=True)
    shutil.copy2(OLD / "guard/sitecustomize.py", E / "guard/sitecustomize.py")
    provenance = {}
    for name in NAMES + ["semantic_probes", "legacy_information_loss"]:
        src = OLD / (name + ".py")
        dst = E / (src.name if name in NAMES else "prior-" + src.name)
        shutil.copy2(src, dst)
        provenance[dst.name] = dict(source=str(src), sha256=digest(src))
    for ref in ("e6afe16", "5de0d53"):
        (E / ("legacy-reducer-" + ref + ".py")).write_bytes(subprocess.check_output(
            ["git", "show", ref + ":controller/reducer.py"], cwd=R))
    save("copy-provenance.json", provenance)
    keys = ("PYTHONDONTWRITEBYTECODE", "PIP_NO_INDEX", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE",
            "ANONYMIZED_TELEMETRY", "TMPDIR", "PYTHONPATH", "PYTEST_DISABLE_PLUGIN_AUTOLOAD", "HIVE_SRC")
    save("review-env-overrides.json", {k: environment()[k] for k in keys})
    for name in NAMES:
        run(name.replace("_", "-"), [sys.executable, str(E / (name + ".py"))])
    run("pytest", [sys.executable, "-m", "pytest", "tests/", "-v", "-p", "no:cacheprovider",
                   "--basetemp=" + str(E / "pytest-tmp")], S)
    save("original-reruns-verification.json", dict(final_git_status=git("status", "--porcelain"),
        source_unchanged=all(digest(R / n) == h for n, h in manifest.items()),
        originals_unchanged=all(digest(Path(v["source"])) == v["sha256"] for v in provenance.values())))
