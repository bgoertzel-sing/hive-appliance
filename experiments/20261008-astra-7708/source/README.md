# Omega Hive Appliance

Implementation of the Omega Hive Appliance specification (v1.0, 11 Sep 2026).

## Overview

A managed hive appliance for OpenClaw/OmegaClaw environments with:
- Operational self-modeling (observe → diagnose → repair)
- Controlled repair via typed action contracts
- Reproducible runtimes via Nix
- Recoverable agent state

## Milestones

- **M0**: Observe one existing hive (C00–C03)
- **M1**: Execute controlled repairs (C04–C07)
- **M2**: Reproducible packaging (C08)
- **M3**: State recovery and controlled upgrades (C09–C10)
- **M4**: NixOS VM backend (C12)

## Status

- **M0** ✅ Complete — Observe one existing hive (C00–C03): collectors, event store, reducer, profiles
- **M1** ✅ Complete — Execute controlled repairs (C04–C07): planner, executor, verifier, repair loop, dry-run mode
- **M2** ✅ Complete — Reproducible packaging (C08): pyproject.toml, Dockerfile, Makefile, wheel build, entry point
- **M3** ✅ Complete — State recovery and controlled upgrades (C09–C10): checkpoint/restore, upgrade controller with pre-flight/rollback, CLI commands
- **M4** ✅ Complete — NixOS VM backend (C12): config generator, VM manager, Nix builder, service mapper, adapter, executor

## Structure

```
docs/        — ADRs, scope, threat model, operator runbooks
schemas/     — resource, event, plan, receipt, recovery
controller/  — policy, reducer, orchestration, evidence API
executor/    — narrow host verbs and resource registry
verifier/    — fixed probes and authenticated receipts
collectors/  — application and host observation adapters
adapters/    — fake, Ubuntu/OCI, NixOS VM backend
reasoning/   — runbooks, optional LLM/PLN projections
recovery/    — checkpoint manager, upgrade controller
profiles/    — versioned supported hive configurations
tests/       — unit, contract, integration, fault, fixtures, packaging
reports/     — generated acceptance evidence
```

## Quick Start

```bash
# Create venv and install (editable + dev deps)
make dev

# Run tests
make test

# Build wheel
make build

# Build Docker image
make docker

# Run CLI
make run ARGS="observe"
```

## Installation

```bash
# From source
pip install .

# With dev dependencies
pip install -e ".[dev]"

# Entry point
hive-appliance --help
```

## Docker

```bash
docker build -t hive-appliance:latest .
docker run --rm hive-appliance:latest --help
docker run --rm -v $(pwd)/state:/app/state hive-appliance:latest observe
```

## Hive rebind journal

Operator rebinds of held plans are made durable by a write-ahead journal:

```bash
export HIVE_REBIND_JOURNAL=$(pwd)/state/hive-rebinds.jsonl
```

Without a journal, `HiveAppliance` refuses rebinds unless you pass
`volatile_rebinds=True`. Each rebind is journaled as a pending record plus a
commit record, and only committed rebinds replay. Each journal starts with a
header carrying a random id, also stored in `<journal>.id`; a mismatch (an old
journal swapped back, or a journal without its `.id`) fences it; any pre-v5
artifact (old `.fence` files, v1-v4 records) fences before anything is created.
Rolling back the journal AND its `.id` together is NOT detected: never restore
backups of either file on its own (see the policy doc). `rebind_plan_owner()` returns a `RebindResult`
(`applied` / `refused` / `uncertain`; only `applied` is truthy). If any journal record cannot
be verified (torn, edited, reordered, legacy v1-v4 format), the whole journal is
fenced: `journal_status()["healthy"]` is False, nothing is replayed and rebinds
are refused until an operator inspects it and calls
`clear_journal_fence(actor=..., reason=...)`, which archives the old journal
and starts a new one; re-issue any rebind still wanted. See
`docs/POLICY_MULTI_PLAN_SUPERSESSION.md` ("Hive rebind journal").

## Development

```bash
# Full test suite
python -m pytest tests/ -v

# Unit + contract tests only
python -m pytest tests/unit tests/contract

# Packaging tests only
python -m pytest tests/test_packaging.py -v

# Recovery tests only
python -m pytest tests/test_recovery.py -v

# Fault injection tests
python -m pytest tests/fault -k controller_restart
```
