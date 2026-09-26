#!/usr/bin/env python3
"""
CLI entry point for the Omega Hive Appliance.

Usage:
    python cli.py observe              Run all collectors and store events
    python cli.py profile              Discover and save hive profile
    python cli.py incidents            List open incidents
    python cli.py state                Show current state snapshot
    python cli.py events               List recent events
    python cli.py repair               Repair all open incidents
    python cli.py repair --dry-run     Preview repair plans without executing
    python cli.py run-plan FILE        Execute a plan from JSON file

P0 fixes:
  F1: All dispatch goes through appliance repair() with verb validation.
  F3: Requires --recovery-ready for live repairs.
  F5: --dry-run enforced at dispatch boundary.
"""
from __future__ import annotations

import argparse
import json
import sys

from collectors.file_collector import FileCollector
from collectors.host_collector import HostCollector
from collectors.service_collector import ServiceCollector
from controller.appliance import Appliance
from profiles.manager import ProfileManager
from recovery.upgrade import UpgradeManifest, UpgradeStep


def _build_appliance(store_path: str, dry_run: bool = False) -> Appliance:
    """Build a fully wired appliance with all M1 components."""
    from executor.noop_executor import NoopExecutor
    from executor.shell_executor import ShellExecutor
    from reasoning.planner import SimplePlanner
    from verifier.exit_code_verifier import ExitCodeVerifier

    app = Appliance(store_path)
    app.add_collector(HostCollector())
    app.add_collector(ServiceCollector())
    app.add_collector(FileCollector())
    app.set_planner(SimplePlanner())
    app.set_executor(NoopExecutor() if dry_run else ShellExecutor())
    app.set_verifier(ExitCodeVerifier())
    return app


def manifest_from_json(data: dict) -> UpgradeManifest:
    """Build an UpgradeManifest from CLI JSON.

    Accepts the canonical UpgradeManifest.to_dict() shape and the legacy CLI
    shape (manifest "name"/"version", step "name"/"verify_command").
    Unknown step keys are rejected rather than silently dropped.
    """
    if not isinstance(data, dict):
        raise ValueError("manifest must be a JSON object")
    raw_steps = data.get("steps", [])
    if not isinstance(raw_steps, list) or not raw_steps:
        raise ValueError("manifest must contain a non-empty 'steps' list")
    allowed = {"verb", "name", "command", "rollback_command", "timeout_s",
               "metadata", "verify_command"}
    steps = []
    for i, st in enumerate(raw_steps):
        if not isinstance(st, dict):
            raise ValueError(f"step {i} must be an object")
        unknown = set(st) - allowed
        if unknown:
            raise ValueError(f"step {i} has unknown keys: {sorted(unknown)}")
        verb = st.get("verb") or st.get("name") or ""
        command = st.get("command", "")
        if not verb or not command:
            raise ValueError(f"step {i} requires 'verb' (or 'name') and 'command'")
        metadata = dict(st.get("metadata", {}) or {})
        if st.get("verify_command"):
            metadata["verify_command"] = st["verify_command"]
        steps.append(UpgradeStep(
            verb=verb,
            command=command,
            rollback_command=st.get("rollback_command", ""),
            timeout_s=float(st.get("timeout_s", 60.0)),
            metadata=metadata,
        ))
    name = data.get("id") or data.get("name") or ""
    version = data.get("version", "")
    description = data.get("description") or (
        f"{name} {version}".strip() if name else "")
    kwargs = dict(
        id=name,
        description=description,
        pre_flight=data.get("pre_flight", []),
        steps=steps,
        schema_version=str(data.get("schema_version", "1")),
    )
    if "ts" in data:
        kwargs["ts"] = float(data["ts"])
    return UpgradeManifest(**kwargs)


def cmd_observe(args):
    """Execute cmd observe operation."""
    app = _build_appliance(args.store)
    events = app.observe()
    print(f"Collected {len(events)} events")
    for e in events[-5:]:
        print(f"  [{e.kind.value}] {e.source} -> {e.subject} ({e.severity.value})")
    incidents = app.open_incidents()
    if incidents:
        print(f"\nOpen incidents: {len(incidents)}")
        for inc in incidents:
            print(f"  {inc.severity.value}: {inc.component} - {inc.symptom}")
    app.close()


def cmd_profile(args):
    """Execute cmd profile operation."""
    pm = ProfileManager(args.store_dir)
    profile = pm.discover()
    path = pm.save(profile)
    print(f"Profile saved: {path}")
    print(f"  Hostname: {profile.hostname}")
    print(f"  OS: {profile.os}")
    print(f"  Tier: {profile.tier.value}")
    print(f"  Resources: {len(profile.resources)}")


def cmd_incidents(args):
    """Execute cmd incidents operation."""
    app = Appliance(args.store)
    incidents = app.open_incidents()
    if not incidents:
        print("No open incidents")
    for inc in incidents:
        print(f"  {inc.id} [{inc.severity.value}] {inc.component}: {inc.symptom}")
    app.close()


def cmd_state(args):
    """Execute cmd state operation."""
    app = Appliance(args.store)
    snap = app.state_snapshot()
    print(json.dumps(snap, indent=2, default=str))
    app.close()


def cmd_events(args):
    """Execute cmd events operation."""
    app = Appliance(args.store)
    events = app.store.query(limit=args.limit)
    for e in events:
        print(f"  [{e.kind.value}] {e.ts:.1f} {e.source} -> {e.subject} ({e.severity.value})")
    app.close()


def cmd_repair(args):
    # F3: Recovery-ready gate for live repairs
    """Execute cmd repair operation."""
    if not args.dry_run and not args.recovery_ready:
        print("ERROR: Live repair requires --recovery-ready flag (F3).")
        print("Use --dry-run to preview, or add --recovery-ready to confirm.")
        sys.exit(1)

    app = _build_appliance(args.store, dry_run=args.dry_run)
    # Observe first to detect incidents
    app.observe()
    incidents = app.open_incidents()
    if not incidents:
        print("No open incidents to repair.")
        app.close()
        return

    mode = "DRY-RUN" if args.dry_run else "LIVE"
    print(f"Repairing {len(incidents)} incident(s) [{mode}]")
    print()

    results = app.repair_all(dry_run=args.dry_run)
    for inc_id, receipts in results.items():
        inc = next((i for i in incidents if i.id == inc_id), None)
        if inc:
            print(f"Incident {inc_id}: [{inc.severity.value}] {inc.component} - {inc.symptom}")
        else:
            print(f"Incident {inc_id}:")
        for r in receipts:
            status = "VERIFIED" if r.verified else ("SIMULATED" if r.simulated else "FAILED")
            print(f"  Step {r.step_index}: {r.verb} -> exit={r.exit_code} [{status}]")
            if r.stdout:
                print(f"    stdout: {r.stdout[:200]}")
            if r.stderr:
                print(f"    stderr: {r.stderr[:200]}")
        print()

    # Summary
    total = sum(len(v) for v in results.values())
    verified = sum(1 for v in results.values() for r in v if r.verified)
    simulated = sum(1 for v in results.values() for r in v if r.simulated)
    print(f"Total steps: {total}, Verified: {verified}, Simulated: {simulated}, Failed: {total - verified - simulated}")
    remaining = app.open_incidents()
    print(f"Remaining open incidents: {len(remaining)}")
    app.close()


def cmd_run_plan(args):
    """F3: Execute a plan from JSON file with recovery-ready gate."""
    if not args.recovery_ready:
        print("ERROR: run-plan requires --recovery-ready flag (F3).")
        sys.exit(1)

    from schemas.types import Plan

    with open(args.file) as f:
        plan_data = json.load(f)

    # F2: Strict plan schema validation
    plan = Plan.from_dict(plan_data)
    errors = plan.validate()
    if errors:
        print(f"Plan validation errors: {errors}")
        sys.exit(1)

    app = _build_appliance(args.store, dry_run=False)
    from schemas.types import IncidentReport
    incident = IncidentReport(
        id=plan.incident_id,
        component="manual",
        symptom="plan_execution",
    )
    incident.plan_id = plan.id
    app.record_plan(plan)

    for i, step in enumerate(plan.steps):
        receipt = app.executor.execute_step(step, plan, i)
        expected = step.get("expected", {"exit_code": 0})
        app.verifier.verify(receipt, expected)
        app.record_receipt(receipt)
        status = "VERIFIED" if receipt.verified else "FAILED"
        print(f"Step {i}: {step.get('verb', '?')} -> exit={receipt.exit_code} [{status}]")
        if receipt.stdout:
            print(f"  stdout: {receipt.stdout[:200]}")
        if receipt.stderr:
            print(f"  stderr: {receipt.stderr[:200]}")
    app.close()


def cmd_checkpoint(args):
    """Take a state checkpoint."""
    app = _build_appliance(args.store)
    ckpt = app.checkpoint()
    print(f"Checkpoint saved: {ckpt.id}")
    print(f"  Timestamp: {ckpt.ts}")
    app.close()


def cmd_restore(args):
    """Restore from a checkpoint."""
    app = _build_appliance(args.store)
    success = app.restore(args.checkpoint_id)
    if success:
        print(f"Restored from checkpoint {args.checkpoint_id}")
    else:
        print(f"Failed to restore from checkpoint {args.checkpoint_id}")
    app.close()


def cmd_upgrade(args):
    """Execute an upgrade manifest."""
    if not args.recovery_ready:
        print("ERROR: upgrade requires --recovery-ready flag (F3).")
        sys.exit(1)

    with open(args.manifest) as f:
        manifest_data = json.load(f)

    try:
        manifest = manifest_from_json(manifest_data)
    except (TypeError, ValueError) as exc:
        print(f"ERROR: invalid upgrade manifest: {exc}")
        sys.exit(2)

    app = _build_appliance(args.store)
    result = app.upgrade(manifest)
    label = manifest.description or manifest.id
    print(f"Upgrade '{label}': {'SUCCESS' if result.success else 'FAILED'}")
    print(f"  Steps: {result.steps_completed}/{result.steps_total}")
    if result.error:
        print(f"  Error: {result.error}")
    if result.pre_checkpoint_id:
        print(f"  Checkpoint: {result.pre_checkpoint_id}")
    if not result.success:
        if result.rolled_back:
            print("  Rolled back: state restored from pre-upgrade checkpoint")
        else:
            print(f"  Rolled back: NO ({result.rollback_error or 'not attempted'})")
    app.close()


def main():
    """Execute main operation."""
    parser = argparse.ArgumentParser(description="Omega Hive Appliance CLI")
    parser.add_argument("--store", default=":memory:", help="Event store path")
    parser.add_argument("--store-dir", default=".", dest="store_dir",
                        help="Profile store directory")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("observe", help="Run collectors")
    sub.add_parser("profile", help="Discover hive profile")
    sub.add_parser("incidents", help="List open incidents")
    sub.add_parser("state", help="Show state snapshot")

    events_parser = sub.add_parser("events", help="List recent events")
    events_parser.add_argument("--limit", type=int, default=20)

    repair_parser = sub.add_parser("repair", help="Repair open incidents")
    repair_parser.add_argument("--dry-run", action="store_true",
                               help="Preview repairs without executing")
    repair_parser.add_argument("--recovery-ready", action="store_true",
                               help="F3: Confirm recovery readiness for live repair")

    plan_parser = sub.add_parser("run-plan", help="Execute a plan from JSON")
    plan_parser.add_argument("file", help="Path to plan JSON file")
    plan_parser.add_argument("--recovery-ready", action="store_true",
                             help="F3: Confirm recovery readiness")

    sub.add_parser("checkpoint", help="Take a state checkpoint")
    sub.add_parser("restore", help="Restore from checkpoint").add_argument(
        "checkpoint_id", help="Checkpoint ID to restore")

    upgrade_parser = sub.add_parser("upgrade", help="Execute an upgrade manifest")
    upgrade_parser.add_argument("manifest", help="Path to manifest JSON")
    upgrade_parser.add_argument("--recovery-ready", action="store_true",
                                help="F3: Confirm recovery readiness")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "observe": cmd_observe,
        "profile": cmd_profile,
        "incidents": cmd_incidents,
        "state": cmd_state,
        "events": cmd_events,
        "repair": cmd_repair,
        "run-plan": cmd_run_plan,
        "checkpoint": cmd_checkpoint,
        "restore": cmd_restore,
        "upgrade": cmd_upgrade,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
