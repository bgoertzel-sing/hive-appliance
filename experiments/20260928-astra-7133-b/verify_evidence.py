"""Verify recorded claims and seal outputs; this does not execute product tests."""
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

E = Path(__file__).resolve().parent
R = Path(os.environ.get("HIVE_SRC", E.parent.parent / "repos/hive-astra-7133"))
OLD = E.parent / "20260928-astra-7075"
REPORT = E.parent.parent / "docs/ASTRA_REVIEW_7133.md"

def read(name):
    return json.loads((E / name).read_text())

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

checks = {}
checks["pin"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=R, text=True).strip() == "623c92be3e2ab96fd76024881066628b6c73abb5"
checks["worktree_clean"] = not subprocess.check_output(["git", "status", "--porcelain"], cwd=R, text=True)
manifest = read("source-sha256.json")
checks["pinned_source_unchanged"] = all(sha(R / n) == h for n, h in manifest.items())
checks["source_copy_tracked_files_unchanged"] = all(sha(E / "source" / n) == h for n, h in manifest.items())
checks["copied_original_scripts_unchanged"] = all(sha(E / n) == r["sha256"] == sha(Path(r["source"])) for n, r in read("copy-provenance.json").items())
old_entries = []
for line in (OLD / "SHA256SUMS").read_text().splitlines():
    h, name = line.split("  ", 1)
    old_entries.append(sha(OLD / name) == h)
checks["original_7075_evidence_seal_intact"] = all(old_entries)
checks["original_402"] = read("new-cases-summary.json") == dict(total=398, **{"pass":398, "fail":0, "failed_names":[]}) and len(read("supplementary.json")) == 4 and all(r["passed"] for r in read("supplementary.json").values())
checks["regression_groups"] = len(read("probes-result.json")) == 14 and len(read("older-regressions.json")) == 2 and all(r["probe"] == "PASS" for r in read("probes-result.json") + read("older-regressions.json"))
ind = read("independent.json")
checks["public_repair"] = ind["public_repair_failure_False"]["health"] == "healthy" and ind["public_repair_failure_False"]["local_open"] == 0 and ind["public_repair_failure_True"]["health"] == "failed" and ind["public_repair_failure_True"]["local_open"] == 1
expected_exits = {"adversarial":1, "adversarial-inverted":0, "new-cases":0,
    "supplementary":0, "probes":0, "older-regressions":0, "independent":0,
    "semantic":1, "focused":1, "trace-correction":0, "pytest":1}
checks["child_exits_no_timeout"] = all(read(n + "-exit.json")["exit_code"] == rc and not read(n + "-exit.json")["timed_out"] for n, rc in expected_exits.items())
checks["full_pytest_once"] = len(list(E.glob("pytest-started.json"))) == 1 and "1 failed, 664 passed" in (E / "pytest.stdout").read_text() and "collected 665 items" in (E / "pytest.stdout").read_text()
checks["all_nine_added_tests_pass"] = sum("test_astra7075.py::" in line and "PASSED" in line for line in (E / "pytest.stdout").read_text().splitlines()) == 9
expected_groups = {"current_format":(3072,3072,0), "prior_ordered_format":(3072,3072,0),
    "legacy_fail_closed":(384,384,0), "original_witnesses":(2,2,0),
    "stale_progress":(3,0,3), "ownership_lifecycle":(48,34,14),
    "authentic_old_ownership":(6,2,4), "agent_namespace":(1,1,0)}
ss = read("semantic-summary.json")
checks["semantic_counts"] = all(ss[k] == dict(zip(("total", "passed", "failed"), v)) for k, v in expected_groups.items())
focused = read("focused-witnesses.json")
checks["focused_counts"] = focused["summary"] == {"e6afe16":dict(total=6,passed=3,failed=3), "5de0d53":dict(total=6,passed=3,failed=3), "623c92b":dict(total=14,passed=2,failed=12)}
checks["real_information_loss_proofs"] = read("legacy-original-witnesses.json")["identical_snapshot_bytes"] and all(r["equal_bytes"] for r in focused["identical_old_owner_snapshots"])
correction = read("corrected-old-owner-traces.json")
checks["recorder_correction"] = len(correction) == 6 and all(r["final_matches_original"] for r in correction) and sum(r["intermediate_owner_record_corrected"] for r in correction) == 2
checks["baseline_shared_dependencies_unchanged"] = not subprocess.check_output(["git", "diff", "e6afe16..623c92b", "--", "schemas", "hive/types.py", "recovery/checkpoint.py"], cwd=R)
checks["exported_baseline_source_exact"] = all((E / (prefix + ref + ".py")).read_bytes() == subprocess.check_output(["git", "show", ref + ":" + path], cwd=R) for ref in ("e6afe16", "5de0d53") for prefix,path in (("legacy-reducer-", "controller/reducer.py"), ("legacy-hive-", "hive/reducer.py")))
links = re.findall(r"\]\(([^)]+)\)", REPORT.read_text())
checks["local_report_links_resolve"] = all((REPORT.parent / link).exists() for link in links if not link.startswith("http"))
for p in E.glob("*.py"):
    ast.parse(p.read_text(), filename=str(p))
checks["evidence_python_parses"] = True
files = [p for p in E.iterdir() if p.is_file() and p.name not in ("SHA256SUMS", "verification.json")]
files += list((E / "guard").glob("*.py")) + list((E / "legacy-checkpoint").rglob("*.json"))
secret_pattern = re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{60,}|\bAKIA[0-9A-Z]{16}\b|sk-proj-[A-Za-z0-9_-]{30,}")
suspect = [str(p.relative_to(E)) for p in files if secret_pattern.search(p.read_bytes())]
checks["bounded_secret_pattern_scan"] = not suspect
result = dict(passed=all(checks.values()), checks=checks, source_files=len(manifest),
    old_seal_entries=len(old_entries), source_git_status="", source_pin=read("environment.json")["head"],
    full_pytest_invocations_by_this_reviewer=1, report_sha256=sha(REPORT),
    secret_pattern_suspect_files=suspect,
    seal_exclusions=["source (separate source-sha256.json)", "tmp", "pytest-tmp", "__pycache__"])
with (E / "verification.json").open("x") as f:
    json.dump(result, f, indent=2)
    f.write("\n")
files.append(E / "verification.json")
with (E / "SHA256SUMS").open("x") as f:
    for p in sorted(files):
        f.write(f"{sha(p)}  {p.relative_to(E)}\n")
print(json.dumps(result, indent=2))
raise SystemExit(0 if result["passed"] else 1)
