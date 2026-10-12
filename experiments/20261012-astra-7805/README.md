# Astra 7805 evidence

**APPROVED WITH CONDITIONS** on `a875414ec0281db0a5d5a66b0d12412733f4cbd7`. See [report](../../docs/ASTRA_REVIEW_7805.md) and [execution ledger](RUN.md).

- [Model](model-verification.json), [environment](environment.json), [pinned source hashes](source.json), [source diff](target.patch), [copy provenance](copy-provenance.json), [adaptations](adaptation.diff).
- [Full suite](pytest.stdout): 867 passed, once, no thread limit override or thread exhaustion.
- [Qualified independent cases](independent7805-qualified.json): 16 hard-timeout subprocesses including real public-path FIFO append, startup/intent FIFO races, all required append errno classes.
- [Source/open/test audit](audit7805.json): three raw opens, four helper callers, correct check order, legitimate changed 7638 test.
- [Retained 7750](retained7750.json): namespace, reader, runtime, parent symlink and archive controls.
- [Supersession](schedules7805.json), [1,440 traces](policy-schedules.json), [current journal/144 hold schedules](review7694.json), [eight followup groups](followup7694.json).
- [Reset](reset7727.json), [intent/clearance](intent-final7727.json), [extra I/O](extra-io7727.json), [412 intent cases](intent7734.json), [7741 closures](focused7741.json), [exact restore](exact-restore-final7718.json).
- [Secret scan](secret-scan.json), [fixture inventory](special-fixtures.json), [manifest](SHA256SUMS), [read-only verifier](verify_evidence.py).

Every actual run has stdout, stderr, started/exit JSON. Initial incorrect fixture and obsolete legacy-entrypoint failures are preserved and explained in the report; only the qualified witness and current-format regressions support the verdict. Copied historical scripts without execution ledgers are dependencies/references, not freshly verified assertions.

Verify from any directory:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 experiments/20261012-astra-7805/verify_evidence.py
```

The manifest includes the report and all files, hashes symlinks by literal target bytes, and never follows them. The verifier also compares source blobs at the pinned commit to the repository's working files and checks that the pin is an ancestor of HEAD. Intentional malformed journal fixture files are not deployment inputs. FIFOs cannot be stored in Git: their observations survive in results and their metadata in the fixture inventory.
