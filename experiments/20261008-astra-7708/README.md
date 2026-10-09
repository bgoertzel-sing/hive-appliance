# Astra 7708 evidence index

Reviewed pin: `8945bdcb06415a11a5647fbb0e4decc59e021784`. Sole reviewer: verified `openai/gpt-6-astra`. [Report](../../docs/ASTRA_REVIEW_7708.md). Verdict: **NOT APPROVED**; two prior Medium startup findings closed, two Low recovery-documentation findings open.

## Execution and provenance

- [RUN.md](RUN.md): final ledger and failure accounting.
- [commands.sh](commands.sh), [runner.py](runner.py): commands, exclusive started/exit records, stdout/stderr, offline environment.
- [environment.json](environment.json), [offline-verification.json](offline-verification.json), [model-verification.json](model-verification.json).
- [pytest.stdout](pytest.stdout), [pytest-exit.json](pytest-exit.json): full suite exactly once, 808 passed.
- [author-test-provenance.json](author-test-provenance.json): exact-pin author suite execution unverified.
- [copy-provenance.json](copy-provenance.json), [adaptation-7708.diff](adaptation-7708.diff), [retry-adaptation-7708.diff](retry-adaptation-7708.diff), [startup-adaptation-7708.diff](startup-adaptation-7708.diff): retained scripts and explicit protocol/diagnostic/event-stream adaptations. Older diffs are provenance, not edits to older evidence.

## Safety and regression evidence

- [review7694.json](review7694.json): 16 retained groups; 1,440 supersession and 144 hold/rebind schedules. Detailed schedules: `policy-schedules.json`, retained group traces.
- [followup7694.json](followup7694.json): 7/8 initial groups, native faults, refused/uncertain results and historical journal cases. [legacy-retry7708.json](legacy-retry7708.json): remaining diagnostic-adapted group passes.
- [focused7701.json](focused7701.json): adapted five-group identity/runtime/restore/prefix/legacy checks.
- [marker7701.json](marker7701.json): eight startup marker variants with unchanged bytes through restarts.
- [startup7708.json](startup7708.json): corrected same-stream 48 creation injections. [startup-recovery7708.json](startup-recovery7708.json): all 24 fenced states explicitly recoverable.
- [startup7701.json](startup7701.json): initial inherited matrix with regenerated event timestamps; not same-stream replay evidence. Initial supplemental `startup-recovery7708-exit.json` preserves failure. Corrected final validation: `startup-recovery-final7708-exit.json`.
- [clearance7701.json](clearance7701.json): 80 clearance fault/crash injections, including marker renames.
- [recovery7708.json](recovery7708.json): ineffective restore instructions reproduced, `.tmp`/`.cleared-*` cases, permission/EIO and legacy versions.
- [semantic-summary.json](semantic-summary.json): current/prior 3,072 sweeps, legacy 384, retained obsolete three stale-progress failures. Other retained runner outputs preserve 7173/7195, receipt, boundary, mechanism and lifecycle controls.

## Integrity and publication

- `source/production.diff` and changed files: exact target source snapshot, not production edits.
- [source-verification-before.json](source-verification-before.json), [source-verification.json](source-verification.json): all 153 tracked non-experiment files match pin; detached checkout clean.
- [prior-evidence-verification.json](prior-evidence-verification.json): manifests for 7669/7678/7694/7701 verified.
- [publication-checks.json](publication-checks.json), [staging-checks.json](staging-checks.json): fast-forward pin check, scope and staged-byte secret scan.
- [SHA256SUMS](SHA256SUMS), [verify_evidence.py](verify_evidence.py): complete report/artifact manifest. Run `python3 experiments/20261008-astra-7708/verify_evidence.py` from delivered repository.

Raw forensic fixtures and initial failure outputs are intentionally retained. Some copied dependency scripts contain unused old tests or obsolete descriptive strings; only execution records establish what ran. Defect-asserting probes are not safety approvals. Excluded: pytest/tmp/cache directories and wheel binaries (hashes/recipe retained). No paid/remote compute or deployment; the Python socket guard is not an OS-wide network sandbox.
