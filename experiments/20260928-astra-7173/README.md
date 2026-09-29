# Astra review 7173 evidence

Pin: `cfb03f2aa71e494ed3dd782d6179ed5f1621889b`.
Base: `ef18db3ab415d0eabd4e92a96d4f0d7c53d91ad5`.
Report: `../../docs/ASTRA_REVIEW_7173.md`. No source, old evidence, live gate or publication changes.

## Inputs and provenance

`source/` is a complete tracked export of the pin. `source-sha256.json` maps every tracked input to its digest. Prior helpers come only from the pinned repository's tracked `experiments/20260928-astra-7160/`; `copy-provenance.json` identifies them. No unpublished 7133 worktree or collision-prone external evidence file is imported. The name `semantic_7133.py` is historical, not an external dependency.

The actual e6afe16/5de0d53 reducers are included, and ef18db3 is exported directly from Git for the authentic diagnostics-upgrade test. `baseline-provenance.json` and final integrity checks pin those bytes. All checkpoint fixtures were produced in this run and passed through real `CheckpointManager.create/load`, with distinct fixture directories. `new-checkpoints/`, `legacy-checkpoint/`, `mechanism-checkpoints/` and `linked-stale-checkpoints/` retain them.

`adaptation.diff` preserves only the copied mechanism helper's rebind API updates: actor/reason and explicit override where its old scenario lacks a candidate. Old expectations were not rewritten. Ordinary PLAN recovery fails intentionally under the new quarantine policy. Resolved targets are now refused. Non-candidate targets are accepted only with the deliberate override in that compatibility harness.

## Execution

The initial `run_review.py` preparation failed before any child test because an old guard was not tracked. `preparation-failure.json` records the true exit and resolution. The new `guard/sitecustomize.py` is self-contained. Preparation was resumed; pytest was invoked exactly once.

Initial commands, from the research workspace:

```sh
python3 projects/hive-appliance/experiments/20260928-astra-7173/run_review.py
python3 projects/hive-appliance/experiments/20260928-astra-7173/run_review.py --extra
```

`*-started.json`, `*-exit.json`, stdout and stderr retain actual child commands, cwd, elapsed time, timeout flag and OS exit. Launcher exit zero is not a passing test result. Full suite: 693 collected, 692 passed, 1 failed, exit 1. Only isolated packaging dependency provisioning failed. The review sets `PIP_NO_INDEX=1`, offline model flags and a Python socket guard; environment overrides and package versions are recorded. No dependency installation/retry was performed. The socket guard is not an OS sandbox.

## Portable Replay

Do not rerun scripts inside this evidence directory: several intentionally use exclusive-create output. Use a NEW destination. The replay helper needs no Git checkout or prior project directory and preserves the same offline settings:

```sh
python3 replay.py /tmp/astra7173-probe-replay --only probes
python3 replay.py /tmp/astra7173-full-replay --only all
```

The second command is provided for a later independent reproduction; it was not used to repeat pytest in this review. `replay.py` copies source and harness inputs and sets `HIVE_SRC` to the relocated `source/`. The runner creates the required writable `tmp/` and isolated pytest basetemp. Python 3.10+ and the dependencies recorded in `environment.json` are needed for full-suite parity. No installer is invoked by the launcher, although the authored wheel test itself attempts isolated build provisioning.

A narrower manual run also works from a fresh copy of input scripts and old reducer modules:

```sh
mkdir -p tmp
export HIVE_SRC=/absolute/path/to/pinned/source
export TMPDIR="$PWD/tmp"
PYTHONDONTWRITEBYTECODE=1 python3 review7173.py
```

`review7173.py` exits 1 at this pin for its three preserved defect assertions, not a harness crash. The original expected-bug harness, two historical-policy harnesses, and unadapted stale automatic-recovery oracle also have documented nonzero exits. `results-audit.json` separates safety expectations, obsolete expectations, agreement and actual exits. `verify_evidence.py` checks pin/export/helper provenance and writes final hashes. `SHA256SUMS` covers deliverable evidence (excluding source, temporary artifacts, relocation smoke inputs, caches and the checksum file itself); the source has its separate full manifest.

The probe-only relocated replay was executed successfully as a reproduction check: every child exit and semantic summary matches the primary run. Its outer exit is 1 because expected defect/policy assertions remain nonzero, not because portability failed. All child logs are in `relocation-smoke/`; no second pytest invocation occurred.

The initial results audit mistakenly required HEALTHY before any INCIDENT arrived; 11 pre-incident lifecycle states are correctly UNKNOWN. `audit_results-initial.py` and `results-audit.stderr` preserve that failed audit. `audit_results.py` uses the incident-presence-aware expectation; `results-audit-corrected-exit.json` records exit 0. No probe or product test was rerun to correct the audit.
