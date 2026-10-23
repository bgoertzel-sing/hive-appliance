# hive-appliance: consolidated summary

Snapshot of `bgoertzel-sing/hive-appliance` at **`main` = `68cf39c3`** (2026-10-12).
Every statement below comes from a file in the repo at that commit, and each section names its sources.
Where the repo says nothing on a point, or where two files disagree, this summary says so and does not try to settle it.
Reading time is about 15 minutes.

---

## 1. Purpose

*Sources: `README.md` (Overview, Milestones), `docs/design-hive-level-appliance.md` §1, `docs/design-conversation-store.md` §2.*

hive-appliance implements the **Omega Hive Appliance specification (v1.0, 11 Sep 2026)**. It is a managed appliance for OpenClaw/OmegaClaw agent environments. It keeps a model of its own operational state: it **observes** hosts and services, **diagnoses** incidents, and **repairs** them. Repairs are controlled: plans are limited to a small set of verbs, and every repair is verified independently.

The repo contains three layers:

- **Per-agent appliance (M0–M4).** Each agent observes, diagnoses and repairs its own services.
- **Hive-level appliance (M5).** An orchestration layer that spans agents and correlates incidents across them.
- **Hive Conversation Store.** A separate subsystem that collects Telegram, Slack and transcript messages into one store that agents can query, and handles their attachments. The design doc keeps it separate from the appliance on purpose: the appliance handles *infrastructure health*, and the store handles *conversation memory*.

The specification itself is **not in the repo**. Only the README's references to it are, so this summary can't check the code against the spec.

---

## 2. Architecture by component

*Sources: README "Structure", the module docstrings of every package below, and `schemas/types.py`.*

Data flow: **collectors → event store → controller reducer → incidents → reasoning (planner) → executor → verifier → receipts**. Recovery wraps this loop with checkpoints and upgrades. The hive layer combines many per-agent appliances.

| Component | Files | What it does |
|---|---|---|
| **collectors** | `collectors/base.py`, `host_collector.py`, `service_collector.py`, `file_collector.py` | Collect observations as events: OS, kernel, CPU, memory, disk and processes; systemd services and their status; existence and checksums of critical files. |
| **schemas** (shared) | `schemas/types.py`, `schemas/event_store.py` | Typed Event, Plan, Receipt and IncidentReport records, plus the event store. Defines `ALLOWED_VERBS = {touch, verify, inspect, restart, noop}`. |
| **controller** | `controller/appliance.py` (418 lines), `controller/reducer.py` (899) | `appliance.py` runs the collectors, reducer and event store together. `reducer.py` turns events into state updates and incidents. |
| **reasoning** | `reasoning/planner.py` (141) | Builds repair plans from incidents. Every plan step is checked against `ALLOWED_VERBS` (invariant F1). The README says this layer has "runbooks, optional LLM/PLN projections", but **no LLM, PLN or runbook code exists in `reasoning/`** at this commit. |
| **executor** | `executor/base.py`, `shell_executor.py`, `noop_executor.py`; NixOS: `adapters/nixos/executor.py` | Runs plan steps. `shell_executor` runs them as subprocesses. `noop_executor` is the dry-run/simulation mode. |
| **verifier** | `verifier/base.py`, `exit_code_verifier.py`, `file_verifier.py` | Checks repair outcomes from exit codes and file existence. Invariant F6: *simulated receipts are never verified*. The README says "authenticated receipts", but what the code actually has are unkeyed hashes (Astra 7805 records this as an accepted limitation; see §6–7). |
| **recovery** | `recovery/checkpoint.py` (C09), `recovery/upgrade.py` (C10) | Checkpoints and restores appliance state. Runs upgrades with pre-flight checks, a checkpoint first, and rollback. |
| **adapters** | `adapters/local_adapter.py`, `adapters/nixos/*` (adapter, config_generator, nix_builder, service_module, vm_manager, executor) | Backends. `local_adapter` manages the local host. The NixOS VM backend (M4) generates NixOS configs, maps services to NixOS modules, wraps nix build/eval and manages VM lifecycle. |
| **profiles** | `profiles/manager.py` | Discovers the hive profile (`hive-appliance profile`). |
| **hive** (M5) | `hive/adapter.py`, `event_bus.py`, `reducer.py` (2021 lines, the largest module), `planner.py`, `shared_store.py`, `dashboard.py`, `appliance.py`, `types.py` | `AgentApplianceAdapter` gives every per-agent appliance the same interface. `HiveEventBus` merges their event streams. `HiveReducer` derives hive state: health rollup, cross-agent incident correlation, plan ownership and supersession. `HivePlanner` proposes hive-level actions. `HiveAppliance` is the top-level orchestrator and owns the **rebind journal** (§6). |
| **conversation** | `conversation/store.py`, `threading.py`, `semantic.py`, `client.py`, `attachments.py`, `downloaders.py`, `bootstrap.py`, `types.py`, venue collectors (`base.py`, `telegram.py`, `transcript_file.py`) | The Conversation Store (§5). |

The CLI is `cli.py`, with entry point `hive-appliance`. Its subcommands are `observe`, `profile`, `incidents`, `state`, `events`, `repair`, `run-plan`, `checkpoint`, `restore` and `upgrade`.

The README's Structure block also lists `reports/` and describes `docs/` as holding "scope, threat model, operator runbooks". **None of those exist at this commit.** `docs/` contains design docs, one ADR, one policy doc and the Astra reviews.

---

## 3. Milestones M0–M4 and their status

*Sources: `README.md` "Milestones" and "Status", `docs/adr-m4-nixos-vm-backend.md`, and git history.*

The README marks **all five milestones ✅ Complete**. The C-numbers are the specification's component IDs.

| Milestone | Scope (per README) | First commit |
|---|---|---|
| **M0** Observe one existing hive (C00–C03) | collectors, event store, reducer, profiles | `0e76cbbe` 2026-09-12 |
| **M1** Execute controlled repairs (C04–C07) | planner, executor, verifier, repair loop, dry-run mode | `9c044723` 2026-09-12 |
| **M2** Reproducible packaging (C08) | `pyproject.toml`, `Dockerfile`, `Makefile`, wheel build, entry point | `703e7028` 2026-09-17 (M2 and M3 together) |
| **M3** State recovery and controlled upgrades (C09–C10) | checkpoint/restore, upgrade controller with pre-flight and rollback, CLI commands | `703e7028` 2026-09-17 |
| **M4** NixOS VM backend (C12) | config generator, VM manager, Nix builder, service mapper, adapter, executor | `85ee0666` 2026-09-18; ADR status **Accepted** (2026-09-18) |

What "complete" rests on here:

- The code for each listed piece exists, as described in §2.
- The test suite passes: **867 passed** at `68cf39c3` (I ran it while writing this summary; see §8).

What the repo does **not** contain:

- A spec-conformance checklist mapping C00–C12 to tests.
- Any record of M4 being run against a real NixOS VM. The tests call into the NixOS adapter, but the repo doesn't say whether they used a real `nix` or VM.
- A milestone C11. It is skipped between M3 (C09–C10) and M4 (C12), and the repo doesn't say why.

---

## 4. M5 — Hive-level appliance (design marked DRAFT)

*Sources: `docs/design-hive-level-appliance.md` (2026-09-17, **"Status: DRAFT — awaiting feedback"**), the `hive/` package, and commit `6efb35ba` "M5: Hive-Level Appliance — full implementation" (2026-09-18).*

**The repo disagrees with itself about M5's status:**

- The design doc is still marked DRAFT.
- `hive/` contains a full implementation, merged one day after the doc was written.
- `docs/design-conversation-store.md` calls M5 "complete".
- The README does not list M5 at all.

This summary treats the **design** as a draft, as the task asked, and describes what the code does separately below.

**Design (draft).** The hive layer is *layered, not monolithic*. Per-agent appliances stay unchanged, and a hive appliance federates their event streams:

- `AgentApplianceAdapter`: one uniform interface for each agent's appliance.
- `HiveEventBus`: merges every agent's event stream into one.
- `HiveReducer`: rolls up agent health, correlates incidents across agents (for example, several agents reporting ENOSPC within 60 s become one HiveIncident), and tracks plan ownership.
- `HivePlanner`: hive-level actions.

The design lists four planned hive operations:

- rolling upgrades: checkpoint all agents, then upgrade one at a time with a health check and rollback;
- cross-agent incident correlation;
- coordinated checkpoints, aborting if any agent's checkpoint fails;
- a health dashboard.

Shared stores, such as the Conversation Store, plug in as `SharedStoreAdapter`s so their health can be monitored. The planned phases are M5a adapter → M5b bus and reducer → M5c planner → M5d dashboard.

**Open questions the doc leaves open** (the repo records no answers):

1. Where the hive appliance runs: a dedicated container, a plugin inside one agent, or on the host.
2. Agent discovery: static config or dynamic scanning.
3. Remote agents: whether to add an RPC layer.
4. Authority: whether the hive appliance can force-restart an agent or only request it. The doc recommends *request only*.

**What the code has** (`hive/`):

- `HiveAppliance` with `register_agent`, `tick`, `execute_action`, `run`/`stop` and `status`/`report`.
- `HivePlanner` with five rules: restart failed agents, delegate repairs, rebalance resources, `CHECKPOINT_ALL` after a failed checkpoint, and handle stale agents.
- `HealthDashboard`, which returns a summary, a text report and trends.
- `SharedStoreAdapter`.

**Rolling upgrades are not implemented as behaviour.** `hive/types.py` defines a `ROLLING_UPGRADE` action kind, but no planner rule emits it, and nothing in `hive/` or `tests/` uses it.

`hive/reducer.py` (2021 lines) is where almost all the Astra-reviewed work happened: plan ownership, multi-plan supersession and operator rebinds. See §6–7, and `docs/POLICY_MULTI_PLAN_SUPERSESSION.md` (decided by Ben Goertzel, 2026-10-06). Its rule is that an incident may own several repair plans, and when any one of them completes, the others are superseded.

---

## 5. Conversation Store and attachment service

*Sources: `docs/design-conversation-store.md` (2026-09-18, **"Status: DRAFT — awaiting feedback"**), `docs/attachment-service.md`, the `conversation/` package, and git history of `conversation/`.*

**Where it lives is another point the repo disagrees on.** Design-hive-level-appliance §6 says the Conversation Store is "**not** part of the Appliance codebase", a separate project. In fact it is implemented inside this repo, as `conversation/`. The design doc also ends with "Implementation awaits feedback", yet all six planned phases have code.

**Purpose.** Pull messages from every venue (Telegram groups, Slack, Iter `transcript.txt` files) into one store that every agent can query. The design treats it as a *peer service* to the appliance: the appliance may monitor its health through a `SharedStoreAdapter`, but agents use the store directly.

| Phase (design §9) | Code | What it is |
|---|---|---|
| P1 Core store | `conversation/store.py` (477), `types.py` | `MessageStore`: append-only SQLite, WAL mode, FTS5 full-text search, dedup on message ID, thread-local connections. |
| P2 Semantic search | `conversation/semantic.py` (195) | `SemanticIndex`: embedding search backed by ChromaDB. |
| P3 Collectors | `conversation/collectors/telegram.py`, `transcript_file.py`, `base.py` | The Telegram collector is a *pure adapter* for Bot API message dicts: no credentials, no polling. The transcript collector parses `[YYYY-MM-DD HH:MM:SS] sender: text` lines, including continuation lines. |
| P4 Threading | `conversation/threading.py` (375) | `ThreadAssembler` groups messages by reply chains, then by time proximity, then by a speaker-change heuristic. |
| P5 Integration | `conversation/client.py` (544), `hive/shared_store.py` | `ConversationStoreClient` combines store, index and threads into one query API. The hive side observes the store through `SharedStoreAdapter`. |
| P6 Bootstrap | `conversation/bootstrap.py` (334) | Finds agent transcript files across the hive and bulk-ingests them into the store and the index. |

**Attachment service** (`conversation/attachments.py`, 930 lines; `conversation/downloaders.py`). Attachment metadata is kept in SQLite, in the same database as `MessageStore`, with files filed by venue and date and a download queue. Downloaders are registered per `(venue, account_id)`, and `AttachmentDownloadManager.start()`/`stop()` control the workers. The contract in `docs/attachment-service.md` lists these invariants:

- A message is identified by `(venue, venue_id, venue_message_id)`, and reply resolution is scoped to all three.
- Messages, attachment membership and indexing intent survive a reopen.
- Attachment metadata must point at an existing parent with matching coordinates.
- Generated paths stay under the configured root. External paths supplied by callers are rejected.
- Work is claimed with a durable attempt ID and lease. Only the owning attempt may publish its result, and expired attempts can be recovered.
- Downloads go to attempt-specific temporary files, and completion requires a real file within the size limit followed by an atomic rename. Downloaders should accept `max_bytes` and stop the transfer at that bound. Legacy two-argument downloaders are only checked after the transfer, so they are **not qualified for untrusted remote content**.
- Missing files, expired work and orphaned partial downloads are reconciled.

**Deliberately excluded** (per the contract):

- thumbnails and content-based MIME inspection;
- automatic retention, so deletion is explicit through `AttachmentStore.delete`.

The *integrating service* must also supply credentials, Telegram polling, audience authorization, disk quotas and backup policy before production use.

**Review history.** Astra findings fixed in this area:

- AF01–AF13, PF01 and GF01: `251662bc`, 2026-09-22.
- R2 NEW-1 to NEW-5: `b3e2ea74`.
- 6882 A1, A2, P1-symlink, P2-store, L1 and S1: `855ad1ac` and `4f5220da`, 2026-09-26.

**Open questions in the design** (the repo records no answers): storage location, the embedding model, real-time vs polling, message retention, and whether DMs are included.

---

## 6. Rebind journal: durability guarantees

*Sources: `docs/POLICY_MULTI_PLAN_SUPERSESSION.md` section "Hive rebind journal: recovery, fencing and migration" (Astra 7638–7750), `README.md` "Hive rebind journal", `hive/appliance.py`, `hive/reducer.py` (journal code from about line 150 onward).*

**What it protects.** An operator can *rebind* a held repair plan to a new owner with `rebind_plan_owner()`. The journal is a write-ahead JSONL file that makes those rebinds survive a restart.

**Configuration.** Use `HiveAppliance(rebind_journal=PATH)` or set `HIVE_REBIND_JOURNAL` (the explicit argument wins). If neither is set, `HiveAppliance` **refuses** rebinds unless you pass `volatile_rebinds=True`. A bare `HiveReducer()` still allows volatile rebinds.

**How it is written.**

- The journal starts with a `journal_header` that carries a random `journal_id`. The same id is stored, fsync'd, in an identity anchor file `<journal>.id`. The anchor is created **before** the journal.
- Each rebind is written as a `rebind_pending` record, then a `rebind_commit` record that names it. Every append is fsync'd, and so is the directory.
- Each record carries `prev` and `rec_hash` (SHA-256), which form a hash chain.
- Each record also stores the event-stream position (`seq`) and a hash chain over the content of every reduced event. **On restart, the full event stream must be replayed from the beginning.** An entry is re-applied only at exactly that position, and only if the replayed stream hashes the same.

**Guarantees, by failure:**

| Failure | What happens |
|---|---|
| Process stops between pending and commit | No commit record exists, so the rebind never replays. It is listed in `journal_status()["unapplied"]`. |
| Pending write fails, rollback (truncate + fsync) works | Clean refusal; the journal stays healthy. |
| Pending write fails, rollback fails | Refused and fenced. A torn tail fences the journal at the next start. |
| Commit write fails, rollback works | Clean refusal; the pending record never replays. |
| Commit write fails, rollback fails | Returns `status == "uncertain"` (falsy) and fences `commit_uncertain`. After a restart the rebind is replayed, held again or fenced, and **a refused rebind never comes back**. |
| Any record that doesn't verify at startup (bad hash, broken chain, torn last line, duplicate, legacy or unknown format) | **Nothing replays**, the journal is unhealthy, and new rebinds are refused. It is never auto-repaired, so it fences on every restart until an operator calls `clear_journal_fence()`. |
| Header doesn't match the anchor, or the anchor is missing or unreadable (an old journal put back in place) | The whole journal is fenced (`identity`). |
| Symlink, FIFO or directory swapped in for a journal file | Fenced, never followed. Every open uses `O_NONBLOCK\|O_NOFOLLOW` plus an `fstat` regular-file check, so the service cannot hang. |
| Pre-v5 artifacts | Fenced (`legacy`) until `clear_journal_fence()`, which archives them. |
| Edit between writes | Caught by the running process at its next write or `verify_journal()` (size plus a SHA-256 of the whole file). |
| Interrupted `reset_journal()` | A durable `<journal>.reset-intent` marker fences every start until the reset is retried or cleared. Discarded rebinds stay discarded. |

**What is explicitly *not* guaranteed** (stated in the policy doc):

- **Truncation at a record boundary** is not detected at restart. It can only *drop* rebinds; it can't bring back a refused one.
- **Rolling back the journal and its `.id` together** (for example, from the same backup) is accepted as healthy, so a discarded authorization could come back. Never restore either file while the hive is in service. If a restore can't be avoided: stop the service, restore both, call `reset_journal()` before any event is reduced, replay the stream, and re-issue the wanted rebinds.
- **The hashes are not a keyed MAC.** Someone with write access who recomputes them is not detected, so the journal relies on file permissions.
- **Snapshot or suffix restore** of the event stream is not supported.
- **Results.** `rebind_plan_owner()` returns a `RebindResult`. Only `"applied"` is truthy, and only it means the commit is durable.

---

## 7. Astra review history and open conditions

*Sources: `docs/ASTRA_REVIEW_*.md` (29 files, 6949 to 7805), `docs/ASTRA_7133_RECONCILIATION.md`, `docs/POLICY_MULTI_PLAN_SUPERSESSION.md`, and git history.*

Reviews are numbered by their Telegram message ID. The history falls into these phases:

| Dates | Reviews | Focus and outcome |
|---|---|---|
| 2026-09-22 to 09-26 | (no review files) AF01–AF13/PF01/GF01, R2 NEW-1 to NEW-5, 6882 | Attachment and conversation findings. **These are known only from commit messages** (`251662bc`, `b3e2ea74`, `855ad1ac`, `4f5220da`). The repo has no review document for them. |
| 2026-09-26 to 09-27 | 6949, 6979, 6986, 7003, 7024 | Structural fixes: receipt resolution, plan-to-incident links. **6979 is an Opus 5.5 review**, filed in the same series for continuity, as the file itself says. 7003 and 7024 record the model as self-reported "GPT-6 (Codex)". |
| 2026-09-28 | 7075, 7133 (two files plus `ASTRA_7133_RECONCILIATION.md`), 7146, 7160, 7173, 7195 | Gating of live repair and replay. **7146**: keep it gated. **7160**: would lift the current-format live-repair gate at that pin, on a bounded scope. 7173 and 7195 raised multi-plan supersession, which Ben decided on 2026-10-06 (policy doc). |
| 2026-10-06 to 10-08 | 7519, 7542, 7562, 7582 | Conformance with the supersession policy, held plans and operator rebinds. 7582 was requested by Protomega2 and approved by glicerico. |
| 2026-10-08 | 7638, 7656, 7669, 7678, 7694, 7701, 7708, 7718, 7727, 7734, 7741, 7750 | Eleven rounds on rebind-journal durability, reset and recovery. Each fix is folded into the policy doc (§6). |
| 2026-10-12 | **7805** | Reviewed `a875414` (then `origin/main`). **Verdict: APPROVED WITH CONDITIONS.** Both 7750 findings are closed, no Medium-or-higher finding is open, and **no code-fix conditions remain**. |

**Approval on `main`.** The current `main` (`68cf39c3`, 2026-10-12, Benjamin Goertzel) is the only commit after `a875414`, the commit 7805 reviewed. Its message is "docs: approve Astra 7805 durability review with scoped conditions and FIFO append …", and it adds the 7805 report and its evidence. The repo doesn't record a separate written sign-off beyond that commit.

**Open conditions from 7805.** These are the operational boundary the approval depends on:

1. **Linux-qualified storage.** It needs working `O_NOFOLLOW`/`O_NONBLOCK`/`O_DIRECTORY` semantics, a single writer, and protected, stable file and parent namespaces. A stable, trusted symlink for the journal's parent directory is accepted; retargeting it concurrently is not. Other platforms are not qualified.
2. **Keep and replay the full original ordered event stream.** Snapshots, suffixes and partial streams are not allowed. Reset and restore recovery happen on a fresh reducer **before replay or serving**.
3. **After a joint restore of the journal and its `.id`,** run an explicit reset before replay if earlier decisions must stay discarded, then re-issue the wanted authorizations. A healthy status is not proof that no rollback happened.
4. **On `intent_durable: false`,** keep the service stopped, fix the cause, and retry the reset before replay. If the marker is an unreadable regular file, fix its permissions rather than deleting it.

**Limitations 7805 accepts and carries forward:**

- The hashes are unkeyed.
- A joint rollback is not detected without a reset.
- Clean truncation at a record boundary can drop rebinds.
- Snapshot restore is unsupported.
- Non-regular entries need an operator to clear or reset them.
- The `O_NOFOLLOW` qualification covers Linux only and protects only the final path component.
- Races between `lstat` and `rename` remain (hostile concurrent writers are out of scope).
- Verification time grows linearly with journal size.
- **No physical power-cut or firmware persistence testing** has been done, and no broad performance qualification.

Evidence for 7805 is in `experiments/20261012-astra-7805/` (`SHA256SUMS`, `verify_evidence.py`, and the full-suite stdout).

The repo records **no review of the M5 hive layer as a whole** apart from the reducer and journal work, and no Astra review of M0–M4 as milestones.

---

## 8. How to run and test

*Sources: `README.md` ("Development" and its usage blocks), `Makefile`, `pyproject.toml`, `Dockerfile`, `cli.py`.*

**Requirements.** Python ≥ 3.9 and no runtime dependencies (`dependencies = []`). There are two optional extras:

- `semantic` (`chromadb>=1.0`) for the Conversation Store's `SemanticIndex`;
- `dev` (`pytest`, `chromadb`, `build`).

**Setup with the Makefile:**

```bash
make dev        # create .venv and install -e ".[dev]"
make test       # .venv/bin/pytest -v tests/
make build      # sdist + wheel into dist/
make docker     # docker build -t hive-appliance:latest .
make run ARGS="observe"   # run the CLI from the venv
```

**CLI** (`hive-appliance`, entry point `cli:main`): `observe`, `profile`, `incidents`, `state`, `events`, `repair`, `run-plan`, `checkpoint`, `restore`, `upgrade`.

**Rebind journal.** Before running the hive layer in service, set this, or rebinds are refused (see §6):

```bash
export HIVE_REBIND_JOURNAL=$(pwd)/state/hive-rebinds.jsonl
```

**Tests.** They live in `tests/unit`, `tests/contract`, `tests/integration`, `tests/fault` and `tests/fixtures`, plus top-level files such as `test_packaging.py` and `test_recovery.py`. Subsets from the README:

```bash
python -m pytest tests/unit tests/contract
python -m pytest tests/test_packaging.py -v
python -m pytest tests/test_recovery.py -v
python -m pytest tests/fault -k controller_restart
```

**Result at `68cf39c3`, run here on 2026-10-23:** `.venv/bin/python -m pytest tests/ -q` gave **867 passed in 87.7 s**, with no failures or skips reported. This used the system's Linux host. The system `python3` has no pytest, so use the venv.

**Not covered by this run:** a real NixOS VM, real Telegram traffic, and power-cut persistence (see §7). The Astra review evidence under `experiments/` has its own reproduction scripts, and this summary doesn't re-run them.

---

*Written by ProtoMegaBot2 for hive task `t-2026-10-23-repo-summary`. It is docs-only; no source was changed.*
