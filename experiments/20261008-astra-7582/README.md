# Astra 7582 reproducible review evidence

Reviewed `bgoertzel-sing/hive-appliance` at `4d5fdff7902963b2d07329e959f938451a109107`, equal to origin/main at clone and pre-publication fetch. Sole reviewer: openai/gpt-6-astra (runtime metadata confirmed).

Report: `../../docs/ASTRA_REVIEW_7582.md` in the published repository.

## Results

- Full suite run exactly once: 738 passed, no failures/skips.
- Exact candidate/preview/audited rebind witness passes; 144 hold/rebind schedules, retained 180 ownerless schedules and 1,440 owned supersession schedules pass.
- High: receipt explicitly naming j before owner proof closes i after rebind; four independent cases plus owned-first rejection controls.
- Medium: formerly held plan escapes the audited path after last linked incident resolves; hive replay cannot restore operator rebind/audit.
- Retention fixed: 600/600 open holds survive. Audit/candidate caps preserve current holds.
- Low: misleading INFO closure from hive preview; stale local restore guidance; aggregate resource bounds remain absent.
- One unchanged historical helper exits 1 for three obsolete legacy-auto-recovery expectations; actual states remain fail-closed. See report for exclusions and explicit-rebind controls.

## Artifact map

- `review7582.py/json/stdout/stderr`: new witnesses, full-object purity, serialized replay, caps, namespace controls, retained regression extraction and F7 mutants.
- `followup7582.py/json`: foreign-receipt rejection controls, 60-receipt audit clipping, preview log side effect, stale recovery text.
- `pytest.*`, `pytest-started.json`, `pytest-exit.json`: sole full-suite record.
- `run_primary.py`, `runner.py`, `commands.sh`: commands and exclusive-output runner.
- Other retained helpers/results: N1–N10, H2, disk/migration/rebind, replay, health and prior safety regressions. `review7519.py` and `review7542.py` supply definitions only; their superseded whole-script expectations are not invoked. Copied helpers are byte-identical to 7562; see `copy-provenance.json`.
- `source/`, `source-sha256.json`, `source-verification.json`, `production.diff`: pinned product/test sources, complete changed-file diff and integrity checks. Historical review reports/experiments excluded from source copy.
- `environment.json`, `build-prerequisites.json`, `model-verification.json`, `DECISIONS-input.md`: run/model/decision provenance.
- `publication-checks.json`, `SHA256SUMS`, `final-integrity.json`, `verify_evidence.py`: publication scan and integrity manifest.

## Reproduction

First run `python3 verify_evidence.py` in this published directory. Do not rerun helpers in prior evidence: output names are fixed and the runner intentionally refuses to overwrite its logs.

Create a fresh scratch directory; copy the root `*.py` helpers, `source/` and `guard/` there, but no existing result/log/manifest files. Set `HIVE_SRC` to the copied source and `PIP_FIND_LINKS` to a separate directory containing wheels whose versions/hashes match `build-prerequisites.json`. Python/pytest/build environment versions are in `environment.json`. From the fresh directory run:

```sh
python3 run_primary.py
python3 review7582.py
python3 followup7582.py
```

For identical network/plugin isolation and per-command metadata, invoke the two independent scripts through `runner.run` as recorded in `commands.sh`. The runner disables external Python socket connects, plugin autoload and pip network access; localhost fixtures remain available. No production credentials or live integrations are required. There is no RNG seed: schedule enumerations and expectations are deterministic; generated event IDs/timestamps and scratch filenames vary and are serialized in outputs.

Third-party build wheels and disposable build/pytest caches are not committed; wheel hashes are supplied. No source code modifications were used for mutants: methods are replaced temporarily in-process, then restored. A witness “passed” may mean a documented defect was reproduced; consult its expected versus actual state, not just its exit status.
