# Astra 7562 evidence

Reviewed product pin: **57a62987a8e46fe2fdf45d63c1a9c148d3e12fbd** (`origin/main` at clean clone and pre-publication fetch). Model/provider: **openai/gpt-6-astra**, API `openai-responses`, confirmed from own session/transcript metadata. Single reviewer, no delegation. [Review](../../docs/ASTRA_REVIEW_7562.md).

## Outcomes

- **P3-ownerless safety CLOSED**: 180 schedules / 1,224 states; six owned-positive controls. Additional visibility: 60 schedules / 408 states / 60 repairs. Local JSON restore and serialized hive replay; hive has no snapshot API.
- **O-ownerless-hold OPEN, Medium**: visible via new accessor, but no operator hold/rebind; ordinary re-send establishes owner using existing progress without operator audit. Ordinary PLAN event storage exists and is distinguished from operator authorization/effect audit.
- **Decision conformance OPEN, Medium, human decision required**: recorded (a) was previewed/audited rebind; code/document implement recorded (b) plus visibility and reverse the option labels. This review does not choose a replacement policy.
- **Newly tested inherited retention limitation, Medium**: at 600 open linked plans, hive retains/reports only 500. Local returns all 600, including after restore. No global diagnostic cap; two hive agents produce 1,000 reasons (Low resource/operability limitation, no OOM claimed).
- **F7 negative fixtures CLOSED**: both detect the identical 7542 completeness-gate mutant. Seven authored 7542 tests are legitimate behavior tests, not conformance tests.
- **Sole full suite: 725 passed / 0 failed / 0 skipped**, 47.73 seconds, runner exit 0. Build smoke passes with isolated local build dependencies.
- Retained **1,440 owned supersession schedules / 15,840 states**, N1–N10, H2, H-oracle and authentic quarantine checks pass within documented scopes.
- Retained `semantic_7133.py` exits 1 for **three known obsolete automatic legacy-recovery expectations**. Original new authority fixture also failed because it accidentally supplied reconstructable historical ownership; its result is preserved. Corrected authority-only follow-up passes. No product source was changed and the full suite was not repeated.

## Execution / provenance

`RUN.md` records scope and completion. `commands.sh` records test child commands; each of the **12 primary test children** has `*-started.json`, `*-exit.json`, stdout and stderr. These are: full pytest once, nine retained helpers, `review7562.py`, and the authority-only follow-up. `run_primary.py` is an execution driver, not evidence that every child passed: inspect child exit JSON.

`copy-provenance.json` hashes byte-identical helpers from 7542. `review7542.py` and `review7519.py` are retained as helper-definition sources; their obsolete final defect-assertion dispatchers are not run. Prefix extraction selections/hashes are recorded. `authority_followup.py` extracts only the authority function and corrects one historical INCIDENT fixture; the first failed function/source/log remains intact. Prior experiment directories were not modified.

`source/` is the tracked pin export excluding old experiment directories. `source-sha256.json` binds every exported source file. `production.diff` is the complete requested five-file delta. `DECISIONS-input.md` preserves the project decision file used by the reviewer. Tests run against `source/`, not an editable live installation. No deployed processes or real repairs are exercised.

Important outputs: `review7562.json`, `authority-followup.json`, `visibility-schedules.json`, `ownerless-witness.json`, `ownerless-schedules.json`, `policy-schedules.json`, authentic migration/checkpoint outputs, and retained per-family summary JSON. Assertion pass means the witness matched its stated expected behavior, not necessarily closure of the finding.

## Environment and build prerequisites

Python/platform and installed pytest/build/setuptools/wheel versions are in `environment.json`. Test children use the inherited review runner: `PYTHONDONTWRITEBYTECODE=1`, `PIP_NO_INDEX=1`, `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, `ANONYMIZED_TELEMETRY=False`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, `TMPDIR=<output>/tmp`, `PYTHONPATH=<output>/guard`, `HIVE_SRC=<output>/source`. `guard/sitecustomize.py` blocks external Python socket connections; it is not an OS sandbox.

Before the one full suite, `pip download` fetched setuptools 82.0.1, wheel 0.46.3 and packaging 26.0 into `build-prerequisites/`. No installed package/credential configuration changed. Primary children inherit `PIP_FIND_LINKS=<output>/build-prerequisites`; pip's isolated build environment can provision these wheels without external network. Exact download command, artifact hashes and stdout/stderr are preserved. `built-wheel.json` records the resulting package hash. The dependency wheel binaries and built wheel are **not committed**; they are reproducible third-party/build artifacts, not omitted test results.

Disposable `tmp/`, `pytest-tmp/`, Python caches and generated `source/build`, `source/dist`, egg metadata are excluded. All tracked source and all primary result/log/checkpoint evidence is retained. Copied source/raw logs/diffs retain their original formatting.

## Verification and reproduction

Inside this published directory:

```sh
python3 verify_evidence.py
```

This checks every artifact, source/helper hashes and the report hash. Reproduction never overwrites this evidence:

```sh
python3 replay.py /absolute/path/to/new-output
```

The optional full-suite reproduction first downloads the recorded build prerequisites (network required for that preparation only), then runs the suite once:

```sh
python3 replay.py /absolute/path/to/another-new-output --include-pytest
```

The replayer is supplied but was **not rerun** in this review. It requires compatible preinstalled test dependencies from `environment.json`. It preserves expected known obsolete-helper failures and the first historical-fixture error rather than presenting a falsely all-green run. Reproduction UUIDs/timestamps differ; semantic assertions/counts, not output byte identity, are expected to match.
