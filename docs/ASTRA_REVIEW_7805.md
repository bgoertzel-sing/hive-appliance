# Astra review 7805 — storage durability and recovery

## Verdict: APPROVED WITH CONDITIONS

Reviewed **`a875414ec0281db0a5d5a66b0d12412733f4cbd7`** (`origin/main`), against the preceding review commit `4a9b3c55`. **Both 7750 findings are closed. No open Medium-or-higher finding remains; no further source change is a condition of this approval.** Conditions below are the existing deployment/recovery boundary, not a demand for another hardening round. Narrow, documented fail-closed namespace cases are accepted proportionately.

Sole reviewer self-identity: **“You are Codex, an agent based on GPT-6.”** The supplied routing attestation identifies catalog **`openai/gpt-6-astra`**, provider **`openai`**, API **`openai-responses`**, `resolvedModel=openai/gpt-6-astra`, `resolvedProvider=openai`, `modelApplied=true`. GPT-6 is the permitted family identity for this routing. [Model confirmation](../experiments/20261012-astra-7805/model-verification.json) records the attestation and UTC timestamp; the model name is routing metadata, not inferred from test results. No delegated reviewer or substitute model.

Reference full suite: **867 passed, 0 failed, 35.04 seconds**, exit 0, run **exactly once** on a Git-blob export of a875414. No thread exhaustion occurred; no thread-limited rerun or thread-limit override was needed. All six requested thread environment variables were unset. Runner wall time: 35.4048 seconds.

## Findings and disposition

Locations refer to a875414 unless noted.

| Finding | Status / severity | Location and evidence |
|---|---|---|
| F-regular-check-after-blocking-open (7750) | **CLOSED — Medium** | `hive/reducer.py:117`, `:514`, `:577`, `:948`, `:972`. Four existing-file callers use `_open_regular_fd`; NONBLOCK + NOFOLLOW precede fstat and regular-file rejection, and blocking is restored only afterward. Independent real FIFO startup, lstat/open races, verify, **public rebind → real append open**, and reset-intent open race all terminate under a hard five-second per-process timeout. |
| F-runtime-directory-swap-health (7750) | **CLOSED — Low** | `hive/reducer.py:975`, `:982`, `:1513`. Real directory/FIFO/symlink replacements refuse the public rebind and set `changed`, unhealthy; no owner is applied. Independent append-open injections of EISDIR/ENXIO/ELOOP/ENOTDIR also fence. |
| Changed 7638 directory test | **CLOSED — Low audit scope** | `tests/test_astra7638.py:192`. Identical setup and refusal assertion; now additionally asserts no owner and correctly expects `changed`/unhealthy. A directory is a namespace/type replacement, not a transient regular-file write failure. Independent real-directory append agrees; this is not weakening a durability assertion. |
| F-startup-dangling-anchor-overwrite (7741) | **CLOSED — Medium, retained** | `hive/reducer.py:563`, `:719`. Original witness plus 32 nonregular startup/clear/reset configurations preserve entries; 40 strict-reader errors and eight namespace swaps fence without adoption. |
| F-reset-error-metadata-status | **CLOSED — Low, retained** | `hive/reducer.py:490`, `:1338`. Original metadata cases and six after-return boundaries retain accurate progress and audit/fence `presence_error`; all 45 strict-check cases apply. |
| Reset interruption / live pending / intent durability | **CLOSED — Medium, retained established-intent scope** | `hive/reducer.py:497`, `:1151`. 208 interruption injections, 104 caught-error recoveries, 412 intent-boundary cases, four compound failures, 52 extra I/O boundaries and four anchor-read cases pass. |
| Intent startup, clearance and retry recovery | **CLOSED — Medium, retained** | `hive/reducer.py:719`, `:1054`, `:1151`. 42 marker controls, 72 intent-bearing clearance interruptions, 96 retry/live-error cases pass, including actual non-root mode-000 permission repair. |
| Refused/uncertain rebind, identity, order/content, abort-tail and rollback regressions | **CLOSED — retained High/Medium/Low scopes** | `hive/reducer.py:719`, `:908`, `:962`, `:1366`, `:1434`. Sixteen current primary journal groups and eight followup groups pass; startup/clearance/marker controls and exact restored-pair reset/reissue pass. Full suite includes 7638–7750 tests. |
| Literal “every open” documentation wording | **ACCEPTED LIMITATION — Low documentation precision** | `docs/POLICY_MULTI_PLAN_SUPERSESSION.md:179`, `hive/reducer.py:461`. New exclusive creation is deliberately `O_WRONLY|O_CREAT|O_EXCL`, not the existing-file helper. Existing FIFO/symlink/directory entries fail EEXIST before a peer wait or write; a newly created inode is regular. Independent FIFO exclusive-create control passes. Parent-directory fsync is a separate NONBLOCK/O_DIRECTORY open (`:426`). The literal wording is broader than the code, but not an unclosed availability or durability defect. |
| Namespace concurrency / platform scope | **ACCEPTED LIMITATION — bounded deployment scope** | `hive/reducer.py:124`, `:426`, `:617`, `:1054`. Stable parent symlinks work; final-component checks do not pin ancestors or close lstat→rename windows. Not an adversarial namespace-writer guarantee. |

## Independent closure evidence

[Independent qualified harness](../experiments/20261012-astra-7805/independent7805-qualified.py) runs **16 child cases**, each with `subprocess.run(..., timeout=5)`; any hang or nonzero child is failure. It does **not** replace reducer methods, bypass verification, or call `_journal_write` directly. For `append-fifo`, it creates a healthy reducer with a held plan, renames the real active journal, creates a real FIFO, calls public `rebind_plan_owner`, and observes the actual `os.open` flags. The trace contains O_RDWR/O_APPEND/O_NONBLOCK/O_NOFOLLOW, proving that the FIFO reached the append open itself. Refusal is un-applied and unhealthy/changed. Explicit clearance followed by full replay stays held. Directory and symlink cases provide the same public-path check; error injections target only the append-open syscall.

Journal and `.id` cases cover steady FIFO startup and regular-to-FIFO swaps after lstat. The reset case starts with an unreplayed reducer and changes a regular existing intent marker into a FIFO at its read-open, after classification; the result is ESTALE/reset_failed with `intent_durable:false`, not a hang. The original pair stays subject to the stopped-service retry requirement. Separate exclusive-create coverage proves that the one non-helper namespace-file open refuses an existing FIFO promptly.

[Source/AST audit](../experiments/20261012-astra-7805/audit7805.json) inventories **all three raw os.open sites**, all four existing-file helper callers, helper operation order and the full before/after 7638 test. All **165 tracked non-experiment files** in the export and working tree matched their exact pinned Git blobs. The existing-file helper is the only raw non-creation file open. `_read_regular` retains device/inode checks; `_verify_on_disk` retains whole-file and anchor verification. Existing regular-file read/write starts only after regular classification. Exclusive new-file creation and directory fsync are explicitly distinguished above rather than incorrectly claiming every raw open uses the helper.

[Retained 7750 harness](../experiments/20261012-astra-7805/retained7750.json) passes **32** nonregular startup/recovery variants, **40** reader error probes, **eight** reader swaps, **16** runtime type probes (now including FIFO verify), **five** stable parent-symlink controls, and archive read tracing (**zero archive reads**). Only the old defect-expecting directory assertion is corrected, and the obsolete deliberate-blocking witness is replaced by the independent hard-timeout harness. No production file or repository test was edited.

## Regression and execution accounting

- **1,440 supersession schedules / 15,840 event-prefix checks** pass independently; **144 hold/rebind schedules** pass through the retained current-format journal harness.
- The 7638–7750 journal test files all execute in the reference full suite. Current-format `review7694`, `followup7694`, `focused7701`, startup/clearance/marker/recovery harnesses pass. The exact restore/reset test preserves archive bytes, holds through restart, and persists only a new explicit reissue.
- Reset matrices: **208** interruptions, **104** caught errors; **42** marker controls, **72** clearance interruptions, **96** retry/live-error cases; **52** additional I/O boundaries plus **four** anchor-read injections; **412** intent injections and **four** compound failures. These are syscall-boundary fault models, not physical power-cut experiments.
- **Full-suite reference is `pytest`**, not any auxiliary legacy probe: **867 passed in 35.04s**, no skips reported, exit 0. Python 3.10.12, pytest 9.1.1, installed build 1.5.0, chromadb 1.5.9, Linux, uid 1001, eight reported CPUs. This records the actual environment, not a claim that installed build equals the current development pin. Existing local wheel inputs were used; no dependency download. External Python socket connections were blocked by the retained guard, not an OS-level sandbox.
- Two auxiliary runs are nonzero and retained without hiding them. `independent7805` initially attempted reset after event replay, correctly hitting the API's lifecycle guard; the corrected final fixture passes, and the subsequent **qualified** fixture moves the injection to the actual intent read-open. `policy7638` accidentally ran the obsolete defect-reproduction entrypoint, whose six failures expect removed defects/old one-record journal format and old candidate caps. Current replacements in `review7694`/`followup7694` and the repository suite pass. The supersession subgroup already passed there and is separately rerun with its unchanged oracle in `schedules7805`. These failures are not unexplained current-product regressions.
- Each actual run has exclusive started/exit JSON and stdout/stderr. Copied historical helper scripts are dependencies or references; **only the execution ledger denotes an executed run**. Copied stale audit/verifier scripts are not current conclusions. Source hashes and harness adaptation provenance are included. Reviewer-created FIFOs were inventoried and unlinked only after testing (Git cannot store FIFOs); 37 intentional symlink fixtures are hashed by literal link payload, never by following their targets. `scratch/` was not modified.

## Conditions and accepted limitations

Approval requires the following operational boundary; **there are no outstanding code-fix conditions**:

1. **Linux-qualified storage**, with working O_NOFOLLOW/O_NONBLOCK/O_DIRECTORY semantics, one writer, protected stable file and parent namespaces. A stable trusted journal-parent symlink is accepted; concurrent parent retargeting is not. Do not assume this review qualifies fallback semantics on other platforms.
2. Retain and replay the **full original ordered event stream**, not snapshots, suffixes or synthetic partial streams. Reset/restore recovery must occur on a fresh reducer **before replay or serving**.
3. After a journal/`.id` pair is jointly restored, perform a successful explicit **reset before replay** if earlier decisions must remain discarded. Do not treat a healthy status or no-op clear as proof against rollback. Reissue any desired authorization explicitly after reset.
4. On `intent_durable:false`, **keep service stopped, repair the cause, and retry reset before replay**. Repair an unreadable regular marker's permissions rather than deleting it. Nonregular intent markers require stopped-service cleanup and reset retry. Nonregular journal/anchor entries require explicit operator clear or reset; do not silently replace them.

Accepted limitations carried forward:

- **Unkeyed hashes**, not authentication/MACs; an authorized storage writer can recompute them.
- **Joint rollback of journal and `.id` is undetected without reset** and may revive old decisions; both active files absent is indistinguishable from first use.
- **Clean truncation at a record boundary** is accepted at restart and can drop rebinds; live verification can detect a changed whole file. A pending record without commit does not replay.
- **Snapshot/partial-replay restore is unsupported** for this journal/reducer contract.
- An **intent file that cannot be made durable** follows the `intent_durable:false` procedure above; a visible partial marker is not a durable barrier and may vanish after a crash.
- **Symlink/directory/FIFO entries require operator clear/reset** for the active pair; nonregular intent markers need stopped-service cleanup/retry. These are bounded fail-closed limitations, not approval blockers.
- **O_NOFOLLOW/O_NONBLOCK qualification is Linux-only** here. “Nonblocking” prevents special-file peer handshakes, not arbitrary regular-filesystem I/O stalls or kernel/device failure.
- A **stable journal parent-directory symlink is accepted**. Ancestors are not pinned by dirfd; O_NOFOLLOW protects the final component only.
- **lstat→rename race windows** and namespace mutation after open remain. Protected single-writer/stable-ancestor operation is required; hostile concurrent namespace writers are not supported.
- Verification is linear in journal size. Physical power-cut/firmware persistence and broad performance qualification were not tested. The exclusive-creation documentation shorthand is qualified above, not escalated into a new hardening requirement.

## Evidence and publication

[Evidence index](../experiments/20261012-astra-7805/README.md), [run ledger](../experiments/20261012-astra-7805/RUN.md), [source metadata](../experiments/20261012-astra-7805/source.json), [patch](../experiments/20261012-astra-7805/target.patch), [full-suite stdout](../experiments/20261012-astra-7805/pytest.stdout), [secret scan](../experiments/20261012-astra-7805/secret-scan.json).

`SHA256SUMS` covers all delivered regular evidence files, literal symlink targets and this report, except the manifest itself. `verify_evidence.py` checks complete coverage, a875414 Git ancestry, current source against pinned Git blobs, model metadata, execution ledgers, suite and key matrices. The credential-pattern scan covers report and regular evidence files without traversing symlinks. Publication stages only this report and `experiments/20261012-astra-7805/`, commits, pushes `HEAD:main` without force, and compares local HEAD, origin/main and remote refs/heads/main. The resulting publication hash and final verification output are returned separately to avoid self-referential hashes.
