# Astra 7694 evidence

Independent review of **cf6a0601ddc03dcd87daab7f982cb97361ac7ee8**, parent **d1239f9**, by sole **openai/gpt-6-astra**. Production ownerless hold/rebind gate **NOT APPROVED**; see [report](../../docs/ASTRA_REVIEW_7694.md).

**785 passed in 47.86s, full suite exactly once.** Primary 16/16; focused 12/12 including explicit defect assertions. Final static verification passes. One static setup retry completed missing source archives; no product/test or suite rerun.

The same reviewer continued from session agent:main:subagent:ce379868-8734-49fc-b8b2-9b17659d49ef in agent:main:subagent:58d4840d-3ff6-4ae5-afbe-193491620461 after a provider content-refusal on a large embedded script. No fallback or reviewer delegation. Model checks are in model-verification.json.

## Index

| Artifact | Purpose |
|---|---|
| RUN.md, environment.json, commands.sh, *-started.json, *-exit.json | Status, provenance, exact commands, timings/exits |
| model-verification.json | Both session identities and final own-model/provider check |
| pytest.stdout / stderr / exit JSON | Sole complete suite, 785 passed |
| review7694.py / .json / -summary.json | 16 primary groups, exact retained semantic witnesses |
| followup7694.py / .json / -summary.json | Archived 7678 bytes and native v4 faults/crashes/rollback/duplicate/prefix/migration witnesses |
| clearance7694.py, clearance7694.* logs | Additional seven pre-rename faults, post-rename directory-fsync fault, successful applied-only re-journaling |
| static7694.py / static7694-final.* | Final source, docs, prior manifests, wiring and offline checks |
| static7694.* logs, archive_sources7694.py | Preserved initial archive-inventory failure and repair procedure |
| deleted-test-coverage.json | Eight deleted tests mapped, genuine selective-availability coverage loss distinguished |
| static-review.json, production-wiring-search.json | Documentation/production integration findings |
| source-verification-before.json / source-verification.json | 149 unchanged pinned tracked files |
| prior-evidence-verification.json | 7669: 315; 7678: 351 complete hashes verified |
| source/production.diff, source/ | Complete nine-file change, changed source, deleted test, setup inputs |
| journal-followup7694/, journal-7694/, other checkpoint/journal fixtures | Raw witness bytes and retained state |
| semantic-summary.json, current-format-sweep.json, prior-ordered-format-sweep.json, legacy-fail-closed-sweep.json | Retained semantic results |
| retained-extraction.json, copy-provenance.json, witness-adaptation.diff | Exact helper provenance and adaptations |
| guard/sitecustomize.py, offline-verification.json, build-prerequisites.json | Socket guard and wheel hashes (wheels excluded) |
| scan_staged.py, staging-checks.json, publication-checks.json, prepublication-git.json | Publication scope, credential-pattern scan and exact prepublication Git state |
| SHA256SUMS, verify_evidence.py | Complete published artifact/report manifest and read-only verification |

## Reproduction

First verify the immutable delivered artifacts:

```sh
python3 experiments/20261008-astra-7694/verify_evidence.py
```

Execution is **not** the same operation as manifest verification. Use a new disposable copy of this evidence directory and a clean detached checkout of cf6a060; do not run generators in this published tree. Runner uses exclusive log creation, deliberately preventing accidental rerun/overwrite. Python 3.10.12, pytest 9.1.1 and build 1.5.0 were used. Supply offline build wheels matching build-prerequisites.json if reproducing static wheel verification; no paid/remote services are needed.

Set HIVE_SRC to the detached checkout and PYTHONDONTWRITEBYTECODE=1. Exact original commands/cwds are in commands.sh and *-started.json; absolute paths reflect the recorded machine. In a fresh run directory, run_primary.py executes the full suite once plus retained harnesses. review7694.py is a separate primary witness invocation. Run followup7694.py through runner, then clearance7694.py through runner to add its group to followup7694.json, and static7694.py through runner after completing source/ inventory. Read scripts before recreating paths; static verification expects the archived initial source hashes and matching wheel cache.

The retained older review scripts are **definition/input dependencies, not additional suites to execute**. The unchanged semantic_7133 legacy expectations intentionally still exit 1 in three cases; semantic-summary and current/prior/legacy fail-closed sweeps show the accepted interpretation. Defect-reproducing assertions are passes of a witness, not production approvals.

## Scope and exclusions

No production/test changes, paid/remote compute or deployment. Scratch and previous evidence are unchanged. Python socket guard rejects external connections and pip uses offline mode; not an OS-wide network sandbox. Disposable tmp/, pytest-tmp/, bytecode/caches and third-party wheel files are excluded; wheel hashes, fixture generation and raw result evidence are retained. Some retained source/patch fixtures contain intentional whitespace preserved verbatim.

Post-push verification is saved separately at /tmp/hive-astra-7694/postpush-verification.json rather than modifying a committed manifest to mention its own commit.
