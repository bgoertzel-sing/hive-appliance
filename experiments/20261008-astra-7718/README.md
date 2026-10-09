# Astra 7718 evidence index

Pin: `0ec1a2dc9b56b8011903180f07f94cd1f3f3d39f`. Sole reviewer: verified `openai/gpt-6-astra`. [Report](../../docs/ASTRA_REVIEW_7718.md). **NOT APPROVED**: two prior Low documentation findings closed in their stated scopes; two new Medium reset interruption/live-error findings open.

## Execution and provenance

- [RUN.md](RUN.md), [commands.sh](commands.sh), [runner.py](runner.py): execution ledger, commands, exclusive started/exit JSON and logs.
- [model-verification.json](model-verification.json), [environment.json](environment.json), [offline-verification.json](offline-verification.json).
- [pytest.stdout](pytest.stdout), [pytest-exit.json](pytest-exit.json): full suite exactly once, **813 passed**.
- [author-test-provenance.json](author-test-provenance.json): no tracked author full-suite artifact tied to exact pin found.
- [copy-provenance.json](copy-provenance.json), [adaptation-7718.diff](adaptation-7718.diff): retained script hashes and current diagnostic/scan adaptations. Older copied diffs preserve provenance; older evidence was not edited.

## Reset and storage review

- [reset7718.py](reset7718.py), [reset7718.json](reset7718.json): six successful reset states, seven validation refusals, **176 interruptions**, and two live-error witnesses. An assertion proving a defect is not a safety approval.
- [exact-restore-final7718.json](exact-restore-final7718.json): immutable exact 7708 restore timeline; two held restarts before reissue and two authorized restarts after reissue; byte archives and operator audit/log.
- [exact-restore-adaptation.diff](exact-restore-adaptation.diff): initial supplemental logger-threshold failure preserved; targeted corrected run captured separately. Initial reset matrix second-restart serialization occurs after reissue; final timeline removes that display ambiguity.
- [review7694.json](review7694.json): 16 retained groups; 144 hold/rebind schedules. [review7195.json](review7195.json), [policy-schedules.json](policy-schedules.json): 1,440 supersession schedules.
- [followup7694.json](followup7694.json): 8 retained journal groups, 24 fault modes, eight abrupt rebind boundaries.
- [focused7701.json](focused7701.json), [marker7701.json](marker7701.json): five identity/runtime/prefix/legacy groups and eight active-marker startup cases.
- [startup7708.json](startup7708.json), [startup-recovery7708.json](startup-recovery7708.json): 48 same-stream initial creation injections; 24 fenced states cleared/reissued/restarted.
- [clearance7701.json](clearance7701.json): 80 clearance fault/crash boundaries including both marker renames.
- [recovery7708.json](recovery7708.json): temporary artifacts, unreadable files, legacy version/op combinations. Its old clearance-only restore witness is a historical control, not a rejection of successful new reset.
- [semantic-summary.json](semantic-summary.json): historical three obsolete stale-progress failures remain explicit; current/prior/legacy sweeps pass. Other retained logs cover 7173, boundary, mechanism, probes, older, independent and new cases.

## Integrity and publication

- [source-verification-before.json](source-verification-before.json), [source-verification.json](source-verification.json): 155 non-experiment source files unchanged and equal to pinned blobs; detached source clean.
- [prior-evidence-verification.json](prior-evidence-verification.json): prior 7669–7708 manifests preserved.
- `source/`: exact target patch and changed files, not modifications to production.
- [publication-checks.json](publication-checks.json), [staging-checks.json](staging-checks.json): publication scope and staged-byte secret scan.
- [SHA256SUMS](SHA256SUMS), [verify_evidence.py](verify_evidence.py): read-only full artifact/report validation.

Reproduction requires a new evidence directory to avoid mixing forensic fixtures and runner logs. Use the recorded source pin and environment, copy retained scripts according to provenance, apply only the retained adaptation diff, and execute the recorded commands. Do not execute every copied dependency script indiscriminately: some contain historical unexecuted tests. Temporary caches, pytest workdirs and third-party wheel binaries are excluded; wheel hashes/recipe are retained. No paid/remote compute or deployment.
