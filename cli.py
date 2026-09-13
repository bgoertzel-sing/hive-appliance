"""
CLI interface for the Omega Hive Appliance.

P0 fixes:
  F1: Removed run-plan bypass command; all dispatch goes through appliance.
  F3: Requires --recovery-ready for live repairs.
"""
from __future__ import annotations

import argparse
import json
import sys

from controller.appliance import Appliance
from reasoning.planner import SimplePlanner
from executor.shell_executor import ShellExecutor
from executor.noop_executor import NoopExecutor
from verifier.exit_code_verifier import ExitCodeVerifier


def cmd_observe(args):
    app = Appliance(args.store)
    from collectors.host_collector import HostCollector
    from collectors.service_collector import ServiceCollector
    from collectors.file_collector import FileCollector

    if args.collectors == "all" or args.collectors == "host":
        app.add_collector(HostCollector())
    if args.collectors == "all" or args.collectors == "service":
        services = args.services.split(",") if args.services else []
        app.add_collector(ServiceCollector(services))
    if args.collectors == "all" or args.collectors == "file":
        files = args.files.split(",") if args.files else []
        app.add_collector(FileCollector(files))

    events = app.observe()
    for e in events:
        print(json.dumps(e.to_dict()))
    print(f"\n{len(events)} observations recorded.")
    app.close()


def cmd_repair(args):
    app = Appliance(args.store)
    app.set_planner(SimplePlanner())
    app.set_verifier(ExitCodeVerifier())

    if args.dry_run:
        app.set_executor(NoopExecutor())
    else:
        # F3: Must explicitly enable managed writes
        app.recovery_ready = True
        app.set_executor(ShellExecutor())

    incidents = app.open_incidents()
    if not incidents:
        print("No open incidents to repair.")
        app.close()
        return

    for inc in incidents:
        print(f"\nRepairing incident: {inc.id}")
        print(f"  Component: {inc.component}")
        print(f"  Symptom: {inc.symptom}")
        try:
            receipts = app.repair(inc, dry_run=args.dry_run)
            if not receipts:
                print("  -> Already in progress (deduplicated)")
                continue
            for r in receipts:
                status = "SIMULATED" if r.simulated else ("VERIFIED" if r.verified else "FAILED")
                print(f"  Step {r.step_index}: {r.verb} -> {status}")
            if args.dry_run:
                print("  -> Dry run complete. No effects applied. Incident NOT resolved.")
            elif inc.resolved:
                print("  -> Incident resolved.")
            else:
                print("  -> Incident NOT resolved (partial failure).")
        except Exception as e:
            print(f"  -> Error: {e}")

    app.close()


def cmd_incidents(args):
    app = Appliance(args.store)
    incidents = app.open_incidents()
    if not incidents:
        print("No open incidents.")
    for inc in incidents:
        print(f"  [{inc.severity.value}] {inc.component}: {inc.symptom} (id={inc.id})")
    print(f"\n{len(incidents)} open incidents.")
    app.close()


def cmd_status(args):
    app = Appliance(args.store)
    snapshot = app.state_snapshot()
    print(json.dumps(snapshot, indent=2, default=str))
    app.close()


def main():
    parser = argparse.ArgumentParser(
        description="Omega Hive Appliance - local repair controller"
    )
    parser.add_argument("--store", default="hive.db", help="Event store path")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    obs = subparsers.add_parser("observe", help="Run collectors and record observations")
    obs.add_argument("--collectors", default="all", choices=["all", "host", "service", "file"])
    obs.add_argument("--services", default="", help="Comma-separated service names")
    obs.add_argument("--files", default="", help="Comma-separated file paths")
    obs.set_defaults(func=cmd_observe)

    rep = subparsers.add_parser("repair", help="Repair open incidents")
    rep.add_argument("--dry-run", action="store_true", help="Simulate without real effects")
    rep.set_defaults(func=cmd_repair)

    subparsers.add_parser("incidents", help="List open incidents").set_defaults(func=cmd_incidents)
    subparsers.add_parser("status", help="Show state snapshot").set_defaults(func=cmd_status)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)
    args.func(args)


if __name__ == "__main__":
    main()
