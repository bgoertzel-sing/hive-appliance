# Astra 7750 evidence index

Review: [ASTRA_REVIEW_7750.md](../../docs/ASTRA_REVIEW_7750.md) — **NOT APPROVED** on `6b750ca53a695d70ba4fd44dd2961389f1690df9`.

## Execution and provenance

- [RUN.md](RUN.md): scope, counts, timings, complete command-ledger index and nonzero-run accounting.
- [commands.sh](commands.sh), [runner.py](runner.py), [setup7750.py](setup7750.py): equivalent command sequence, exclusive recorder and pinned exporter. Use fresh namespaces; logs are never overwritten. Setup exports/copies, not tests.
- [model-verification.json](model-verification.json), [environment.json](environment.json), [offline-verification.json](offline-verification.json): verified provider/model, environment allowlist, local-wheel hashes and socket guard.
- [source-verification-before.json](source-verification-before.json), [source-verification.json](source-verification.json), [source-verification-precommit.json](source-verification-precommit.json), [source/target.patch](source/target.patch): exact pin, hash/immutability checks, repeated fetch, changed-file snapshots and requested source diff. Prior experiments omitted from patch and verified separately.
- [copy-provenance.json](copy-provenance.json), [adaptation-7750.diff](adaptation-7750.diff), [finalize_provenance.py](finalize_provenance.py): original/adapted hashes and complete changes for inherited/corrected harnesses. Copied legacy dependencies need not have standalone executions; the ledger is authoritative.
- [prior-evidence-verification.json](prior-evidence-verification.json): nine earlier manifests, now including **7741**, verified.
- Every substantive run has `<name>-started.json`, `<name>-exit.json`, `<name>.stdout`, `<name>.stderr`. Final publication hashes are delivered separately, not recursively included in their own commit.

## Review results

- [pytest.stdout](pytest.stdout): **855 passed in 49.93 s**, one full-suite run.
- [reset7727.json](reset7727.json): 208 interruptions / 104 caught-error recoveries.
- [intent-final7727.json](intent-final7727.json): 42 marker controls, 72 clearance interruptions and 96 retry/live-error cases.
- [extra-io7727.json](extra-io7727.json): 52 extra boundaries plus four current anchor open/read cases.
- [intent7734.json](intent7734.json): expanded 412-case matrix, four compound cases, non-root mode-000 repair and corrected classification.
- [metadata7734.json](metadata7734.json), [focused7741.json](focused7741.json): original metadata cases and six after-return boundaries now carry audit `presence_error`; original dangling-anchor overwrite is closed; 45/45 strict-check cases apply.
- [focused7750.json](focused7750.json): 32 nonregular startup/clear/reset configurations, 40 reader errors, eight read swaps, 15 runtime type controls, three real FIFO-blocking process witnesses, five parent-directory symlink controls and archive read trace. Expected defect reproduction marked `passed` is **witness success, not safety approval**.
- [audit7750-final.json](audit7750-final.json): AST call graph including event replay, every open/read site, archive dataflow and exact changed-test normalization. Initial audit omitted the replay root due to a wrong method name; both versions are retained.
- [namespace-scope7750-final.json](namespace-scope7750-final.json): three deliberately concurrent namespace races, explicitly outside protected-single-writer scope. Initial retarget-before-pending probe correctly fenced; corrected commit-open timing reproduces the scoped limitation.
- [exact-restore-final7718.json](exact-restore-final7718.json): byte-preserving reset, two held starts and explicit reissue durable through two more.
- Retained review7694/followup7694/focused7701, startup/clearance/marker/recovery files: applicable earlier journal regressions. [recovery-final7750.json](recovery-final7750.json) fixes only the obsolete builtin-open injection hook in the original retained run.
- [policy-schedules.json](policy-schedules.json): 1,440 supersession schedules; 144 hold/rebind schedules in review7694.json.
- [semantic-summary.json](semantic-summary.json): current/prior/legacy sweeps and three already obsolete expectations.

## Integrity

[secret-scan.json](secret-scan.json) covers report/evidence credential-pattern scanning. `SHA256SUMS` is the complete inventory of delivered regular files and report (content bytes), plus symlinks (literal link-target bytes), excluding itself. Symlink targets are **never followed**. [special-fixtures.json](special-fixtures.json) preserves 14 FIFO fixture metadata records (FIFOs then removed because Git cannot store them) and inventories 39 retained symlinks. Existing journals, damaged markers, directories and links are intentional evidence, not deployment files.

`PYTHONDONTWRITEBYTECODE=1 python3 verify_evidence.py` verifies hashes, full coverage, all **36 execution ledgers**, suite, matrices, source and findings **without writing files**. Re-executing commands in this populated directory is intentionally refused; prepare a fresh source/runtime/evidence namespace.
