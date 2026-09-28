"""Validate recorded facts and seal the review artifacts, excluding scratch."""
import difflib
import hashlib
import json
from pathlib import Path
import subprocess

E = Path(__file__).resolve().parent
R = E.parent.parent / "repos/hive-astra-7075"
OLD = E.parent / "20260927-astra-7024"
REPORT = E.parent.parent / "docs/ASTRA_REVIEW_7075.md"

def read(name):
    return json.loads((E / name).read_text())

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

assert read("new-cases-summary.json") == dict(total=398, **{"pass": 398, "fail": 0, "failed_names": []})
assert len(read("supplementary.json")) == 4
assert all(v["passed"] for v in read("supplementary.json").values())
assert len(read("probes-result.json")) == 14
assert all(v["probe"] == "PASS" for v in read("probes-result.json"))
assert len(read("older-regressions.json")) == 2
assert all(v["probe"] == "PASS" for v in read("older-regressions.json"))
assert read("pytest-exit.json")["exit_code"] == 1
assert "1 failed, 655 passed" in (E / "pytest.stdout").read_text()
assert read("semantic-summary.json")["current_snapshots"] == dict(total=1920, passed=1920, failed=0)
assert read("semantic-summary.json")["legacy_migrations"] == dict(total=384, passed=288, failed=96)
assert read("legacy-information-loss.json")["identical_legacy_snapshot_bytes"]
assert read("semantic-exit.json")["exit_code"] == 1
assert read("legacy-information-loss-exit.json")["exit_code"] == 1

diffs = []
adaptations = {}
for name, rec in read("copy-provenance.json").items():
    assert sha(E / name) == rec["sha256"]
    assert sha(OLD / name) == rec["original_workspace_sha256"]
    old = (OLD / name).read_text().splitlines(keepends=True)
    new = (E / name).read_text().splitlines(keepends=True)
    changed = [(a, b) for a, b in zip(old, new) if a != b]
    assert len(old) == len(new)
    if name == "supplementary.py":
        assert not changed
        adaptations[name] = "byte-identical original; imports the adapted new_cases.py preamble"
    else:
        assert len(changed) == 1
        assert "hive-astra-7024" in changed[0][0] and "HIVE_SRC" in changed[0][1]
        adaptations[name] = "one import-root line changed in published copy; assertions unchanged"
    diffs.extend(difflib.unified_diff(old, new, fromfile=str(OLD / name), tofile=str(E / name)))
(E / "original-harness-path-adaptations.diff").write_text("".join(diffs))
manifest = read("source-sha256.json")
assert all(sha(R / name) == value for name, value in manifest.items())
assert not subprocess.check_output(["git", "diff", "e6afe16..5de0d53", "--", "hive", "schemas"], cwd=R)
status = subprocess.check_output(["git", "status", "--porcelain"], cwd=R, text=True)
assert not status
parent = E.parent / "20260928-astra-7075-packaging/results.json"
assert all(row["exit"] == 0 for row in json.loads(parent.read_text()))
result = dict(source_unchanged=True, source_files=len(manifest), worktree_git_status=status,
    original_harnesses_unchanged=True, original_copy_adaptations=adaptations,
    original_cases=402, all_original_cases_pass=True, full_pytest_invocations_by_this_reviewer=1,
    report_sha256=sha(REPORT), parent_packaging_results_sha256=sha(parent),
    parent_packaging_execution="parent-verified, not executed by this reviewer",
    excluded_from_seal=["source (separate source-sha256.json)", "tmp", "pytest-tmp", "__pycache__"])
(E / "verification.json").write_text(json.dumps(result, indent=2) + "\n")
paths = [p for p in E.iterdir() if p.is_file() and p.name != "SHA256SUMS"]
paths += list((E / "guard").glob("*.py"))
paths += list((E / "legacy-checkpoint").rglob("*.json"))
(E / "SHA256SUMS").write_text("".join(f"{sha(p)}  {p.relative_to(E)}\n" for p in sorted(paths)))
print(json.dumps(result, indent=2))
