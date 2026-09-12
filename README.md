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
- **M2** 🔲 Reproducible packaging (C08)
- **M3** 🔲 State recovery and controlled upgrades (C09–C10)
- **M4** 🔲 NixOS VM backend (C12)

## Structure

```
docs/        — ADRs, scope, threat model, operator runbooks
schemas/     — resource, event, plan, receipt, recovery
controller/  — policy, reducer, orchestration, evidence API
executor/    — narrow host verbs and resource registry
verifier/    — fixed probes and authenticated receipts
collectors/  — application and host observation adapters
adapters/    — fake, Ubuntu/OCI, later NixOS
reasoning/   — runbooks, optional LLM/PLN projections
profiles/    — versioned supported hive configurations
tests/       — unit, contract, integration, fault, fixtures
reports/     — generated acceptance evidence
```

## Development

```bash
python -m pytest tests/unit tests/contract
python -m pytest tests/fault -k controller_restart
```

## Status

**M0 in progress** — profile discovery, typed records, event store, collectors, incident reports.
