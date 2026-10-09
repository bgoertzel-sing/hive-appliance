# Astra 7741 evidence index

Review: [ASTRA_REVIEW_7741.md](../../docs/ASTRA_REVIEW_7741.md) — **NOT APPROVED** on `2c7e337202cbfa19569b344992326a1603d867cd`.

## Execution and provenance

- [RUN.md](RUN.md): scope, counts, timing, complete command-ledger index and nonzero-run accounting.
- [commands.sh](commands.sh), [runner.py](runner.py), [setup7741.py](setup7741.py): commands, exclusive recorder and pinned exporter. Use fresh namespaces; runner refuses to overwrite logs. Setup precedes commands.
- [model-verification.json](model-verification.json), [environment.json](environment.json), [offline-verification.json](offline-verification.json): verified provider/model, environment allowlist, local-wheel hashes and socket guard.
- [source-verification-before.json](source-verification-before.json), [source-verification.json](source-verification.json), [source/target.patch](source/target.patch): exact pin, hashes, immutability, changed-file snapshots and requested diff.
- [copy-provenance.json](copy-provenance.json), [adaptation-7741.diff](adaptation-7741.diff), [finalize_provenance.py](finalize_provenance.py): original/adapted hashes and complete changes for every inherited Python harness. Copied dependency scripts need not have standalone executions; the ledger is authoritative.
- [prior-evidence-verification.json](prior-evidence-verification.json): eight earlier manifests, including 7734, verified.
- Every substantive run has `<name>-started.json`, `<name>-exit.json`, `<name>.stdout`, `<name>.stderr`. `setup7741.py` only exports/copies and captures initial metadata; it does not run tests.

## Review results

- [pytest.stdout](pytest.stdout): **840 passed in 50.37 s**, one full-suite run.
- [reset7727.json](reset7727.json): 208 interruptions / 104 error recoveries.
- [intent-final7727.json](intent-final7727.json): 42 marker controls, 72 clearance interruptions, 96 retry/live-error cases and corrected original durability witnesses.
- [extra-io7727.json](extra-io7727.json): 48 supplementary boundaries plus four anchor I/O cases.
- [intent7734.json](intent7734.json): expanded 388-case matrix, four compound cases, mode-000 repair, no classification durability defect.
- [metadata7734.json](metadata7734.json): both original metadata contradictions corrected; nonregular reset markers refused.
- [focused7741.json](focused7741.json): 12 metadata-classification variants; seven race/fstat/portability cases; 45 strict-check combinations (42 applicable); six diagnostic boundaries; real dangling-anchor overwrite witness.
- [audit7741-final.json](audit7741-final.json): whole-hive AST/exception audit and reasoned scope. Original audit has one mistaken line-reference note, corrected in the final artifact; behavior/results are unchanged.
- [exact-restore-final7718.json](exact-restore-final7718.json): byte-preserving restore and explicit durable reissue.
- [review7694.json](review7694.json), [followup7694.json](followup7694.json), [focused7701.json](focused7701.json), startup/clearance/marker/recovery JSON: retained applicable journal regressions.
- [policy-schedules.json](policy-schedules.json): 1,440 supersession schedules; 144 hold/rebind schedules in review7694.json.
- [semantic-summary.json](semantic-summary.json): current/prior/legacy sweeps and three explicitly obsolete expectations responsible for the only nonzero run.

## Integrity

[secret-scan.json](secret-scan.json) covers report/evidence credential-pattern scanning. `SHA256SUMS` is also the exact inventory of all regular delivered files, including the report, except itself. `PYTHONDONTWRITEBYTECODE=1 python3 verify_evidence.py` verifies hashes, full coverage, all 30 execution ledgers, suite, matrices and findings **without writing files**. Journal/checkpoint fixtures, damaged markers, dangling links and directories are intentional evidence, not deployment files. Symlinks are not followed by scan/manifest; their observed behavior is recorded in hashed JSON.
