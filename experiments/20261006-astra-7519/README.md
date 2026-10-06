# Astra 7519 evidence

Pin: `9194f52d72a0e853427fd725d2683cc39db39339`, equal to fetched origin/main at start. Reviewer runtime metadata: gpt-6-astra; see `model-verification.json`. Report: [ASTRA_REVIEW_7519.md](../../docs/ASTRA_REVIEW_7519.md).

## Primary commands

Run from `/home/openclaw/research-agent`:

```sh
python3 projects/hive-appliance/experiments/20261006-astra-7519/prepare.py
python3 projects/hive-appliance/experiments/20261006-astra-7519/run_review.py --only pytest
python3 projects/hive-appliance/experiments/20261006-astra-7519/execute_probes.py
PYTHONDONTWRITEBYTECODE=1 python3 projects/hive-appliance/experiments/20261006-astra-7519/extend_regressions.py
```

`prepare.py` records the clean pin and exports tracked source excluding old experiments. It is a workspace-specific preparation record, not needed to replay the supplied source. `extend_regressions.py` copies two retained helpers and changes precisely one obsolete supersession expectation (see `adaptation.diff`). Its first preparation attempt stopped on an overly broad match-count assertion before invoking any child; matching was narrowed to the named case, then the two children ran once. No failed test result was overwritten.

All 11 primary children have `*-started.json`, `*-exit.json`, `.stdout`, and `.stderr`. Full pytest ran **once**: 708 passed / 1 wheel-build provisioning failure / 709 collected. The retained semantic helper exits 1 for three known obsolete automatic legacy rebind expectations; its scoped safety schedule families pass. The five new independent probe groups exit 0, including explicit witnesses of two findings; a successful witness assertion is not a claim that the corresponding product requirement passes.

Key files:

- `review7519.py`, `review7519.json`: independent quarantine, policy, health mutations, ownerless and already-resolved witnesses.
- `policy-schedules.json`: 1,440 schedules, 15,840 per-event checks; local snapshots and hive prefix replay distinguished.
- `authentic-300-before.json`: actual ef18db3 migration output produced from actual e6afe16 state.
- `review7173*.json`, `review7195*.json`, `semantic-summary.json`, `new-cases-summary.json`: retained independent regression families, without modification to prior evidence.
- `source/`, `source-sha256.json`: reviewed tracked non-experiment files. Source is not the current main checkout.
- `copy-provenance.json`, `adaptation.diff`, `final-integrity.json`, `SHA256SUMS`: provenance and integrity.

## Reproduction

Use a fresh output directory; never overwrite this evidence. The portable replay helper copies the necessary inputs and writes new logs there:

```sh
python3 replay.py /absolute/path/to/fresh-output
# Optional, separate reproduction of the full suite (not run during this review):
python3 replay.py /absolute/path/to/another-fresh-output --include-pytest
```

Install/provision requirements independently if necessary; this review did not install anything. Python and package versions are in `environment.json`. The runner explicitly sets `PYTHONDONTWRITEBYTECODE=1`, `PIP_NO_INDEX=1`, `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, `ANONYMIZED_TELEMETRY=False`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, `TMPDIR=<output>/tmp`, `PYTHONPATH=<output>/guard`, and `HIVE_SRC=<output>/source`. Its socket guard blocks external Python connections. Some retained harnesses exercise bounded local shell/filesystem controls; no production repair is performed.

The copied `run_review.py` still contains unused 7195 preparation/selection branches. Use only the commands above or `replay.py`; its inherited `--prepare`, `--only prior/new/audit` are not 7519 entry points.

Publication is a byte-identical curated copy of this run's evidence excluding disposable `tmp/`, `pytest-tmp/`, Python caches, and untracked build products within source. All manifest-listed source bytes, primary logs, witnesses and retained checkpoint JSON are included. Full manifests exclude themselves. `final-integrity.json` includes the report hash; verify with `python3 verify_evidence.py` from any directory. Replay was supplied, not independently rerun in this review.
