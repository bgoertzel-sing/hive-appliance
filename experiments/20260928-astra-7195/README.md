# Astra review 7195 evidence

Pin: `f1736e578993d96816114ab4b0dc2023a1534f9f`.
Base: `cfb03f2aa71e494ed3dd782d6179ed5f1621889b`.
Report: [ASTRA_REVIEW_7195.md](../../docs/ASTRA_REVIEW_7195.md).
Single user-selected gpt-6-astra reviewer; no delegation, production edits,
prior-evidence overwrite, commits, pushes, deployment or gate/publication changes.

## Results

N9 and N10 CLOSED for reviewed implementation defects; H2/N5-N8 retained.
Inherited recovery-text, health-helper and supersession follow-ups remain.
Full pytest exactly once: 699 collected, 698 passed, 1 wheel-provisioning failure,
actual exit 1, no timeout. All six new authored tests passed within it.
Retained adapted review 10/10 groups; new review 7/7 groups including 64
independent per-receipt schedules. Detailed historical-policy failures are
preserved and explained in the report, not hidden behind launcher exit zero.

## Inputs

`source/` is the complete tracked pin export; `source.tar.gz` is its portable
compressed counterpart. `source-sha256.json` hashes every tracked file.
`copy-provenance.json` identifies the pinned 7173 helpers. `adaptation.diff`
records exactly two copied-helper API changes; original bytes remain under
`source/experiments/20260928-astra-7173/`. No earlier evidence was modified.
Four historical reducer modules are included and checked against Git bytes
in `baseline-provenance.json`. Runtime probes need no Git or prior checkout.

Actual e6afe16, 5de0d53 and ef18db3 producers are used where named, not current
snapshots with fields removed. Disk fixtures are under `focused-checkpoints/`,
`new-checkpoints/`, `legacy-checkpoint/`, `mechanism-checkpoints/` and
`linked-stale-checkpoints/`. Logs, full snapshots and per-ID expectations are
retained. Synthetic candidate-priority controls are explicitly separate.

## Commands Used

From `/home/openclaw/research-agent`:

```sh
python3 projects/hive-appliance/experiments/20260928-astra-7195/run_review.py --prepare projects/hive-appliance/repos/hive-astra-7195 --only pytest
python3 projects/hive-appliance/experiments/20260928-astra-7195/run_review.py --only prior
python3 projects/hive-appliance/experiments/20260928-astra-7195/run_review.py --only new
python3 projects/hive-appliance/experiments/20260928-astra-7195/run_review.py --only audit
python3 projects/hive-appliance/experiments/20260928-astra-7195/replay.py projects/hive-appliance/experiments/20260928-astra-7195/relocation-smoke --only probes
python3 projects/hive-appliance/experiments/20260928-astra-7195/verify_evidence.py
```

The copied `review7173.py` was adapted before its primary execution.
Every child invocation has `*-started.json`, `*-exit.json`, stdout and stderr,
including actual return code, command, cwd, elapsed seconds and timeout flag.
Prior-run launcher completion is not a claim that every historical oracle passes.
Full pytest and independent probes ran in separate processes; no source writes.

## Portable Replay

Do not rerun in this evidence directory. Use a NEW destination:

```sh
python3 replay.py /tmp/astra7195-independent-probes --only probes
python3 replay.py /tmp/astra7195-independent-full --only all
```

The second command is for future reproduction; this review executed only the
first mode. `replay.py` copies source, guard, scripts and baselines, sets
`HIVE_SRC` to the new source path and creates writable `tmp/`. Full tests need
the versions in `environment.json`. No installer is invoked by the runner;
the authored packaging test itself attempts isolated build provisioning.
If transporting the compressed source, extract `source.tar.gz` alongside the
runner first. Commands then require no original machine paths or Git checkout.

For a narrow run from a fresh copy of harness inputs:

```sh
mkdir -p tmp
export HIVE_SRC=/absolute/path/to/pinned/source
export TMPDIR="$PWD/tmp"
PYTHONDONTWRITEBYTECODE=1 python3 review7195.py
```

Use the launcher for the recorded offline environment and Python socket guard.
The guard only denies external Python socket connections; it is not an OS sandbox.
`environment-overrides.json` contains only explicitly selected nonsecret settings,
not an environment dump. Temporary fixtures are not live host repair targets.

## Integrity

`verify_evidence.py` verifies clean HEAD, all tracked source/export hashes,
historical reducer bytes, unchanged prior helpers except documented adaptation,
actual test totals and relocated probe parity. `final-integrity.json` contains
the report and source-archive hashes. `SHA256SUMS` covers deliverable evidence
and `source.tar.gz`, excluding source duplication, temporary/cache files,
relocation duplication and the checksum file itself. Source has its own full
manifest. Parent owns publication and project-record integration.
