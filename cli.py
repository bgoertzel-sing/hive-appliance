#!/usr/bin/env python3
"""
CLI entry point for the Omega Hive Appliance.

Usage:
    python cli.py observe       Run all collectors and store events
    python cli.py profile       Discover and save hive profile
    python cli.py incidents      List open incidents
    python cli.py state          Show current state snapshot
    python cli.py events         List recent events
    python cli.py run-plan FILE  Execute a plan from JSON file
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


def cmd_observe(args):
    app = Appliance(args.store)
    app.add_collector(HostCollector())
    app.add_collector(ServiceCollector())
    app.add_collector(FileCollector())
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

    rp = sub.add_parser("run-plan", help="Execute a plan from JSON")
    rp.add_argument("file", help="Path to plan JSON file")

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
    elif args.cmd == "run-plan":
        cmd_run_plan(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
