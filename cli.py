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
"""
from __future__ import annotations

import sys
import json
import argparse

from controller.appliance import Appliance
from collectors.host_collector import HostCollector
from collectors.service_collector import ServiceCollector
from collectors.file_collector import FileCollector
from profiles.manager import ProfileManager
from recovery.checkpoint import CheckpointManager
from recovery.upgrade import UpgradeController, UpgradeManifest, UpgradeStep


def _build_appliance(store_path: str, dry_run: bool = False) -> Appliance:
    """Build a fully wired appliance with all M1 components."""
    from reasoning.planner import SimplePlanner
    from executor.shell_executor import ShellExecutor
    from executor.noop_executor import NoopExecutor
    from verifier.exit_code_verifier import ExitCodeVerifier

    app = Appliance(store_path)
    app.add_collector(HostCollector())
    app.add_collector(ServiceCollector())
    app.add_collector(FileCollector())
    app.set_planner(SimplePlanner())
    app.set_executor(NoopExecutor() if dry_run else ShellExecutor())
    app.set_verifier(ExitCodeVerifier())
    return app


def cmd_observe(args):
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
    pm = ProfileManager(args.store_dir)
    profile = pm.discover()
    path = pm.save(profile)
    print(f"Profile saved: {path}")
    print(f"  Hostname: {profile.hostname}")
    print(f"  OS: {profile.os}")
    print(f"  Tier: {profile.tier.value}")
    print(f"  Resources: {len(profile.resources)}")


def cmd_incidents(args):
    app = Appliance(args.store)
    incidents = app.open_incidents()
    if not incidents:
        print("No open incidents")
    for inc in incidents:
        print(f"  {inc.id} [{inc.severity.value}] {inc.component}: {inc.symptom}")
    app.close()


def cmd_state(args):
    app = Appliance(args.store)
    snap = app.state_snapshot()
    print(json.dumps(snap, indent=2, default=str))
    app.close()


def cmd_events(args):
    app = Appliance(args.store)
    events = app.store.query(limit=args.limit)
    for e in events:
        print(f"  [{e.kind.value}] {e.ts:.1f} {e.source} -> {e.subject} ({e.severity.value})")
    app.close()


def cmd_repair(args):
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
            status = "VERIFIED" if r.verified else "FAILED"
            print(f"  Step {r.step_index}: {r.verb} -> exit={r.exit_code} [{status}]")
            if r.stdout:
                print(f"    stdout: {r.stdout[:200]}")
            if r.stderr:
                print(f"    stderr: {r.stderr[:200]}")
        print()

    # Summary
    total = sum(len(v) for v in results.values())
    verified = sum(1 for v in results.values() for r in v if r.verified)
    print(f"Total steps: {total}, Verified: {verified}, Failed: {total - verified}")
    remaining = app.open_incidents()
    print(f"Remaining open incidents: {len(remaining)}")
    app.close()


def cmd_run_plan(args):
    from executor.shell_executor import ShellExecutor
    from verifier.exit_code_verifier import ExitCodeVerifier
    from schemas.types import Plan

    with open(args.file) as f:
        plan_data = json.load(f)
    plan = Plan.from_dict(plan_data)

    executor = ShellExecutor()
    verifier = ExitCodeVerifier()

    for i, step in enumerate(plan.steps):
        receipt = executor.execute_step(step, plan, i)
        expected = step.get("expected", {"exit_code": 0})
        ok = verifier.verify(receipt, expected)
        print(f"  Step {i}: {step.get('verb', '?')} -> exit={receipt.exit_code} verified={ok}")
        if receipt.stderr:
            print(f"    stderr: {receipt.stderr[:200]}")
        if not ok:
            print("  Step failed, stopping plan execution.")
            break



def cmd_checkpoint(args):
    """Create a state checkpoint."""
    app = _build_appliance(args.store)
    app.observe()  # get current state
    label = args.label or ""
    ckpt = app.checkpoint(label=label)
    print(f"Checkpoint created: {ckpt.id}")
    print(f"  Label: {ckpt.label}")
    print(f"  Time:  {ckpt.ts:.1f}")
    meta = ckpt.metadata
    print(f"  Events: {meta.get('event_count', '?')}")
    print(f"  Open incidents: {len(meta.get('open_incidents', []))}")
    app.close()


def cmd_checkpoints(args):
    """List all checkpoints."""
    app = _build_appliance(args.store)
    ckpts = app.list_checkpoints()
    if not ckpts:
        print("No checkpoints found.")
    else:
        print(f"{'ID':<30} {'Label':<30} {'Timestamp':<20}")
        print("-" * 80)
        for c in ckpts:
            import datetime
            ts_str = datetime.datetime.fromtimestamp(c.ts).strftime("%Y-%m-%d %H:%M:%S")
            print(f"{c.id:<30} {c.label:<30} {ts_str:<20}")
    app.close()


def cmd_restore(args):
    """Restore appliance state from a checkpoint."""
    app = _build_appliance(args.store)
    ckpt_id = args.checkpoint_id
    ok = app.restore(ckpt_id)
    if ok:
        print(f"Restored from checkpoint: {ckpt_id}")
    else:
        print(f"Checkpoint not found: {ckpt_id}")
        sys.exit(1)
    app.close()


def cmd_delete_checkpoint(args):
    """Delete a checkpoint."""
    app = _build_appliance(args.store)
    ok = app.delete_checkpoint(args.checkpoint_id)
    if ok:
        print(f"Deleted checkpoint: {args.checkpoint_id}")
    else:
        print(f"Checkpoint not found: {args.checkpoint_id}")
        sys.exit(1)
    app.close()


def cmd_prune_checkpoints(args):
    """Prune old checkpoints, keeping only the newest N."""
    app = _build_appliance(args.store)
    removed = app.prune_checkpoints(keep=args.keep)
    print(f"Pruned {removed} checkpoint(s), kept newest {args.keep}")
    app.close()


def cmd_upgrade(args):
    """Execute an upgrade from a JSON manifest file."""
    app = _build_appliance(args.store, dry_run=args.dry_run)
    with open(args.file) as f:
        mdata = json.load(f)
    manifest = UpgradeManifest.from_dict(mdata)
    result = app.upgrade(manifest, dry_run=args.dry_run)
    mode = "DRY-RUN" if args.dry_run else "LIVE"
    print(f"Upgrade {manifest.id} [{mode}]")
    print(f"  Success:    {result.success}")
    print(f"  Steps:      {result.steps_completed}/{result.steps_total}")
    print(f"  Rolled back: {result.rolled_back}")
    if result.error:
        print(f"  Error:      {result.error}")
    if result.pre_checkpoint_id:
        print(f"  Pre-upgrade checkpoint: {result.pre_checkpoint_id}")
    app.close()


def main():
    parser = argparse.ArgumentParser(description="Omega Hive Appliance CLI")
    parser.add_argument("--store", default=":memory:", help="Event store path")
    parser.add_argument("--store-dir", default=".", help="Profile store directory")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("observe", help="Run collectors")
    sub.add_parser("profile", help="Discover hive profile")
    sub.add_parser("incidents", help="List open incidents")
    sub.add_parser("state", help="Show state snapshot")

    ev = sub.add_parser("events", help="List recent events")
    ev.add_argument("--limit", type=int, default=20)

    rp = sub.add_parser("repair", help="Repair all open incidents")
    rp.add_argument("--dry-run", action="store_true",
                    help="Preview repair plans without executing commands")

    rp2 = sub.add_parser("run-plan", help="Execute a plan from JSON")
    rp2.add_argument("file", help="Path to plan JSON file")

    args = parser.parse_args()

    if args.cmd == "observe":
        cmd_observe(args)
    elif args.cmd == "profile":
        cmd_profile(args)
    elif args.cmd == "incidents":
        cmd_incidents(args)
    elif args.cmd == "state":
        cmd_state(args)
    elif args.cmd == "events":
        cmd_events(args)
    elif args.cmd == "repair":
        cmd_repair(args)
    elif args.cmd == "run-plan":
        cmd_run_plan(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
