# Astra 7701 evidence

Sole independent **openai/gpt-6-astra** review of **865fd633bc53561aea140dc3f43fee72b8fd61ee**, parent **5535545**. Production ownerless hold/rebind gate **NOT APPROVED**. See [report](../../docs/ASTRA_REVIEW_7701.md).

**795 passed in 48.55 s; full suite exactly once.** All applicable retained groups completed after explicit result-API harness adaptations. Two new Medium startup findings and one Low documentation finding remain; the three OPEN 7694 findings close at their original scope. No delegation, fallback, continuation or provider interruption.

## Index

| Artifact | Purpose |
|---|---|
| RUN.md, environment.json, commands.sh, *-started.json, *-exit.json | Run provenance, exact argv/cwds, timing and exits |
| model-verification.json | Start and near-completion own-session model/provider verification |
| pytest.stdout / stderr / exit JSON | Sole full suite: 795 passed |
| review7694.py/.json/-summary.json | Primary retained groups; initial six obsolete result-shape failures preserved |
| retained-retry7701.json, retry_retained7701.py, retained-retry7701*.stderr | Completed six primary groups; loader/serialization setup errors preserved |
| followup7694.py/.json | Exact archived old witnesses; native v5 fault/tail/order/crash probes; explicit no-commit uncertainty |
| legacy_final7701.py, legacy-final7701.json | Completed default/legacy group after serializer repair |
| focused7701.py/.json | Exact old archive rollback with current anchor; joint rollback; whole-file edits; startup adoption; prefixes; v4 migration |
| marker7701.py/.json | Three legacy-marker startup bypasses and correctly fenced existing-anchor control |
| startup7701.py/.json | 12 creation operations, 48 before/after Crash/OSError injections |
| clearance7701.py/.json | 16 clearance operations, 64 fault/crash injections, applied-only success |
| performance7701.py/.json | Warm-cache verify/per-record/rebind timings through 63 MiB; fixture recipe/hashes |
| observability7701.py/.json | Structured/volatile/refused/uncertain results, appliance summary, memory-effect audit and overwritten last-result |
| semantic-summary.json, policy-schedules.json, retained semantic outputs | 1,440 supersession schedules, 144 hold schedules, current/prior/legacy sweeps |
| adaptation-7701.diff, adapt7701.py, copy-provenance.json, retained-extraction.json | Exact retained witness provenance and v5/API adaptations |
| interpretation-notes.json | Supersedes obsolete inherited verdict strings in raw retained output; does not relabel execution failures |
| static7701.py, source-verification-before.json, source-verification.json | 151 tracked source files unchanged and pinned; clean detached checkout |
| prior-evidence-verification.json | Complete 7669/7678/7694 manifests: 315/351/355 verified |
| production-wiring-search.json, author-test-provenance.json | All tracked callers/docs inventory; author's pre-doc tested tree cannot be identified |
| source/production.diff, source/ | Complete eight-file target diff and changed files |
| journal-followup7694/, journal-7694/, legacy-*/ and other fixtures | Original/restarted/corrupt/archived witness bytes and state |
| guard/sitecustomize.py, offline-verification.json, build-prerequisites.json | Python network guard, offline pip and wheel hashes |
| scan_staged.py, staging-checks.json, publication-checks.json, prepublication-git.json | Exact staged-byte scope/credential scan and publication state |
| SHA256SUMS, verify_evidence.py | Complete read-only manifest, including report |

## Verification and reproduction

Read-only verification of delivered artifacts:

```sh
python3 experiments/20261008-astra-7701/verify_evidence.py
```

Execution differs from verification. **Do not run generators in the published evidence tree.** Use a new disposable copy and clean detached checkout of the reviewed pin. Recreate offline wheel cache matching build-prerequisites.json; wheel binaries are intentionally excluded. Python 3.10.12 and pytest 9.1.1 were used.

The runner provides Python socket guard, offline pip, disabled pytest plugin autoload, no bytecode, exclusive output logs, started/exit metadata and timeout handling. Set HIVE_SRC to the detached source. Exact commands/cwds are in commands.sh and started JSON; absolute paths record the original machine.

For semantic reproduction, copy retained Python inputs from pinned 7694 evidence into the new directory (setup7701.py documents the original preparation), apply adapt7701.py, run the suite/retained baseline once through run_primary.py, then run primary/followup probes through runner. retry_retained7701.py and legacy_final7701.py contain final repaired adaptations; original failed executions are retained but need not be deliberately recreated. Run each new focused script through runner. Static verification requires the initial source hashes and offline wheel cache. Final report/index generation and publication are not test executions.

Prior helper scripts are definition/input dependencies, **not additional suites to execute**. Their old negative verdict strings are not current approvals/findings. The unchanged semantic_7133 expectation failures remain recorded; independent fail-closed sweeps pass. Defect-asserting probes are not safety approvals.

## Scope and exclusions

Only report/new evidence are published. No code/test changes, old-evidence changes, scratch changes, remote/paid compute or deployment. Disposable tmp/, pytest-tmp/, bytecode/caches and third-party wheel binaries are omitted. Large valid-header padding journals are removed after hashes/timings are recorded; their generation recipe remains. Python socket guard is not an OS-wide network sandbox. Raw fixture/patch whitespace remains unchanged.

Post-push verification lives outside this immutable manifest at /tmp/hive-astra-7701/postpush-verification.json.
