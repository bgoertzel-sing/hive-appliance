"""
Main appliance controller: orchestrates collectors, reducer, and event store.
P0 fixes: F1-F10 from Astra review.
"""
from __future__ import annotations
import hashlib
import time
from typing import Any, Optional
from schemas.types import Event, EventKind, Severity, IncidentReport, Plan, Receipt, ALLOWED_VERBS
from schemas.event_store import EventStore
from controller.reducer import Reducer

class Appliance:
    def __init__(self, store_path=":memory:"):
        self.store = EventStore(store_path)
        self.reducer = Reducer()
        self.collectors = []
        self.planner = None
        self.executor = None
        self.verifier = None
        self.max_steps = 20
        self.recovery_ready = False
        self._active_attempts = {}
        self._completed_attempts = {}
        self._active_targets = {}
        self._replay_events()

    def _replay_events(self):
        for event in self.store.query(limit=100000):
            self.reducer.reduce(event)

    def add_collector(self, collector):
        self.collectors.append(collector)
    def set_planner(self, planner):
        self.planner = planner
    def set_executor(self, executor):
        self.executor = executor
    def set_verifier(self, verifier):
        self.verifier = verifier
    def set_recovery_ready(self, ready):
        self.recovery_ready = ready

    def observe(self):
        all_events = []
        for collector in self.collectors:
            try:
                events = collector.collect()
                for event in events:
                    self.store.append(event)
                    self.reducer.reduce(event)
                all_events.extend(events)
            except Exception as e:
                err = Event(kind=EventKind.OBSERVATION, source="appliance",
                    subject=getattr(collector, "name", "unknown"),
                    payload={"error": str(e)}, severity=Severity.ERROR)
                self.store.append(err)
                self.reducer.reduce(err)
                all_events.append(err)
        return all_events

    def record_incident(self, incident):
        event = Event(kind=EventKind.INCIDENT, source="reducer",
            subject=incident.component, payload=incident.to_dict(),
            severity=incident.severity)
        self.store.append(event)
        self.reducer.reduce(event)

    def record_plan(self, plan):
        event = Event(kind=EventKind.PLAN, source="planner",
            subject=plan.incident_id, payload=plan.to_dict(),
            severity=Severity.INFO)
        self.store.append(event)

    def record_receipt(self, receipt, simulated=False):
        if simulated:
            event = Event(kind=EventKind.SIMULATED,
                source=getattr(self.verifier, "name", "verifier"),
                subject=receipt.target or "system", payload=receipt.to_dict(),
                severity=Severity.INFO)
        else:
            event = Event(kind=EventKind.RECEIPT,
                source=getattr(self.verifier, "name", "verifier"),
                subject=receipt.target or "system", payload=receipt.to_dict(),
                severity=Severity.INFO if receipt.verified else Severity.ERROR)
        self.store.append(event)
        if not simulated:
            self.reducer.reduce(event)

    def repair(self, incident, dry_run=False):
        if self.planner is None: raise RuntimeError('No planner configured')
        if self.executor is None: raise RuntimeError('No executor configured')
        if self.verifier is None: raise RuntimeError('No verifier configured')
        if not dry_run and not self.recovery_ready:
            raise RuntimeError('Managed writes disabled: recovery_ready is False (F3).')
        if incident.id in self._active_attempts: return []
        if incident.id in self._completed_attempts: return []
        if incident.resolved: return []
        plan = self.planner.plan(incident)
        plan.incident_id = incident.id
        errors = plan.validate()
        if errors: raise ValueError(f'Invalid plan: {errors}')
        if len(plan.steps) > self.max_steps:
            raise ValueError(f'Plan too large: {len(plan.steps)} steps > max_steps {self.max_steps} (F7).')
        if self.max_steps == 0 and len(plan.steps) > 0:
            raise ValueError('max_steps is 0 but plan has steps. Over-budget rejected (F7).')
        plan.digest = plan.compute_digest()
        attempt_id = hashlib.sha256((plan.id + incident.id).encode()).hexdigest()[:16]
        plan.attempt_id = attempt_id
        self._active_attempts[incident.id] = attempt_id
        incident.plan_id = plan.id
        plan.status = 'executing'
        self.record_plan(plan)
        if dry_run:
            return self._simulate_plan(plan, incident)
        # F9: Check target conflicts against OTHER active plans
        plan_targets = set()
        for step in plan.steps:
            target = step.get('target', incident.component)
            owner = self._active_targets.get(target)
            if owner is not None and owner != plan.id:
                plan.status = 'rejected'
                del self._active_attempts[incident.id]
                raise RuntimeError(f'Target conflict: {target} (F9).')
            plan_targets.add(target)
        for t in plan_targets:
            self._active_targets[t] = plan.id
        receipts = []
        all_verified = True
        in_doubt = False
        for i, step in enumerate(plan.steps):
            target = step.get('target', incident.component)
            try:
                receipt = self.executor.execute_step(step, plan, i)
                receipt.plan_id = plan.id
                receipt.step_index = i
                receipt.attempt_id = attempt_id
                expected = step.get('expected', {'exit_code': 0})
                receipt.verified = self.verifier.verify(receipt, expected)
                self.record_receipt(receipt)
                receipts.append(receipt)
                self._active_targets.pop(target, None)
                if not receipt.verified:
                    all_verified = False
                    break
            except Exception as e:
                all_verified = False
                in_doubt = True
                plan.status = 'in_doubt'
                err_r = Receipt(plan_id=plan.id, step_index=i,
                    verb=step.get('verb', ''), target=target,
                    exit_code=-2, stderr=str(e), verified=False,
                    attempt_id=attempt_id)
                self.record_receipt(err_r)
                receipts.append(err_r)
                self._active_targets.pop(target, None)
                break
        else:
            if all_verified and len(receipts) == len(plan.steps) and len(plan.steps) > 0:
                plan.status = 'completed'
                incident.resolved = True
                self.reducer.resolve_incident(incident.id, plan.id)
        if not all_verified and not in_doubt:
            plan.status = 'failed'
        self._update_incident_status(incident, plan)
        # F9: Release all targets for this plan
        for t in plan_targets:
            self._active_targets.pop(t, None)
        self._active_attempts.pop(incident.id, None)
        self._completed_attempts[incident.id] = attempt_id
        return receipts

    def _simulate_plan(self, plan, incident):
        receipts = []
        for i, step in enumerate(plan.steps):
            r = Receipt(plan_id=plan.id, step_index=i,
                verb=step.get('verb', ''), target=step.get('target', ''),
                exit_code=0, stdout='[simulated]', stderr='',
                verified=False, simulated=True, attempt_id=plan.attempt_id)
            self.record_receipt(r, simulated=True)
            receipts.append(r)
        plan.status = 'simulated'
        self._active_attempts.pop(incident.id, None)
        self._completed_attempts[incident.id] = plan.attempt_id
        return receipts

    def repair_all(self, dry_run=False):
        results = {}
        for inc in self.open_incidents():
            results[inc.id] = self.repair(inc, dry_run=dry_run)
        return results

    def _update_incident_status(self, incident, plan):
        for inc in self.reducer.incidents:
            if inc.id == incident.id:
                inc.plan_id = plan.id
                inc.resolved = incident.resolved
                break

    def open_incidents(self):
        return self.reducer.open_incidents()

    def state_snapshot(self):
        return self.reducer.snapshot()

    def event_count(self):
        return self.store.count()

    def close(self):
        self.store.close()
