"""
HiveAppliance — top-level orchestrator for the M5 Hive-Level Appliance.

Ties together: AgentApplianceAdapters, HiveEventBus, HiveReducer,
HivePlanner, SharedStoreAdapter, and HealthDashboard into a single
coherent control loop.

Usage:
    hive = HiveAppliance()
    hive.register_agent(adapter)
    hive.tick()   # one iteration of the control loop
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Optional

from hive.adapter import AgentApplianceAdapter
from hive.dashboard import HealthDashboard
from hive.event_bus import HiveEventBus
from hive.planner import HivePlanner
from hive.reducer import HiveReducer
from hive.shared_store import SharedStoreAdapter
from hive.types import (
    HiveAction,
    HiveActionResult,
    HiveEvent,
    HiveIncident,
    HiveState,
)

logger = logging.getLogger(__name__)


class HiveAppliance:
    """Top-level M5 Hive-Level Appliance.

    Orchestrates:
    1. Event polling from all agent adapters (via HiveEventBus)
    2. State reduction (via HiveReducer)
    3. Action planning (via HivePlanner)
    4. Action execution (delegated back to adapters)
    5. Health dashboard updates
    """

    def __init__(
        self,
        poll_interval: float = 5.0,
        health_poll_interval: float = 30.0,
        correlation_threshold: int = 2,
        auto_execute: bool = False,
        disk_critical: float | None = None,
    ):
        self.bus = HiveEventBus()
        self.reducer = HiveReducer()
        self.planner = HivePlanner(
            correlation_threshold=correlation_threshold,
            disk_critical=disk_critical,
        )
        self.shared_store = SharedStoreAdapter()
        self.dashboard = HealthDashboard()

        self._adapters: dict[str, AgentApplianceAdapter] = {}
        self._poll_interval = poll_interval
        self._health_poll_interval = health_poll_interval
        self._last_health_poll: float = 0.0
        self._auto_execute = auto_execute

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Tick metrics
        self._tick_count: int = 0
        self._total_events: int = 0
        self._total_incidents: int = 0
        self._action_history: list[HiveActionResult] = []
        self._max_action_history: int = 500
        self._seen_event_ids: set[str] = set()

    # ── Properties ───────────────────────────────────────

    @property
    def registered_agents(self) -> set[str]:
        """Return set of registered agent IDs."""
        return set(self._adapters.keys())

    @property
    def state(self) -> HiveState:
        """Return the current HiveState from the reducer."""
        return self.reducer.state

    @property
    def tick_count(self) -> int:
        """Return number of ticks executed."""
        return self._tick_count

    @property
    def action_history(self) -> list[HiveActionResult]:
        """Return list of past action results."""
        return list(self._action_history)

    # ── Agent registration ───────────────────────────────

    def register_agent(self, adapter: AgentApplianceAdapter) -> None:
        """Register an agent adapter with all hive components."""
        agent_id = adapter.identity.agent_id
        self._adapters[agent_id] = adapter
        self.bus.register_adapter(adapter)
        self.reducer.register_agent(agent_id)
        self.shared_store.register_adapter(adapter)
        # Initialize health in state
        try:
            health = adapter.health_summary()
            self.reducer.state.agents[agent_id] = health
        except Exception:
            pass
        logger.info("Registered agent %s in HiveAppliance", agent_id)

    def unregister_agent(self, agent_id: str) -> None:
        """Unregister an agent from all hive components."""
        self._adapters.pop(agent_id, None)
        self.bus.unregister_adapter(agent_id)
        self.reducer.unregister_agent(agent_id)
        self.shared_store.unregister_adapter(agent_id)
        logger.info("Unregistered agent %s from HiveAppliance", agent_id)

    # ── Control loop ─────────────────────────────────────

    def tick(self) -> dict[str, Any]:
        """One iteration of the hive control loop.

        Returns a summary dict of what happened.
        """
        self._tick_count += 1
        result: dict[str, Any] = {
            "tick": self._tick_count,
            "events_polled": 0,
            "incidents": [],
            "proposed_actions": [],
            "executed_results": [],
            "errors": [],
        }

        # 1. Poll events (dedup via seen set)
        try:
            raw_events = self.bus.poll_all()
            events = [e for e in raw_events if e.id not in self._seen_event_ids]
            for e in events:
                self._seen_event_ids.add(e.id)
            if len(self._seen_event_ids) > 10000:
                self._seen_event_ids = set(list(self._seen_event_ids)[-5000:])
            result["events_polled"] = len(events)
            self._total_events += len(events)
        except Exception:
            logger.exception("Error during event polling")
            result["errors"].append("event_poll_failed")
            events = []

        # 2. Ingest into shared store
        for hevt in events:
            self.shared_store.ingest(hevt)

        # 3. Reduce events into state
        new_incidents: list[HiveIncident] = []
        for hevt in events:
            try:
                incidents = self.reducer.reduce(hevt)
                new_incidents.extend(incidents)
            except Exception:
                logger.exception("Error reducing event %s", hevt.id)
                result["errors"].append(f"reduce_failed:{hevt.id}")

        result["incidents"] = [i.id for i in new_incidents]
        self._total_incidents += len(new_incidents)

        # 4. Poll health from adapters
        self._poll_health()

        # 5. Plan actions
        try:
            actions = self.planner.plan(self.state)
            result["proposed_actions"] = [
                {"kind": a.kind.value, "target_agents": a.target_agents,
                 "parameters": a.parameters, "id": a.id}
                for a in actions
            ]
        except Exception:
            logger.exception("Error during planning")
            result["errors"].append("planning_failed")
            actions = []

        # 6. Auto-execute if enabled
        if self._auto_execute and actions:
            for action in actions:
                try:
                    action_result = self.execute_action(action)
                    result["executed_results"].append(action_result)
                except Exception:
                    logger.exception("Error executing action %s", action.id)

        # 7. Update dashboard
        try:
            self.dashboard.update_state(self.state)
        except Exception:
            logger.exception("Error updating dashboard")

        return result

    def _poll_health(self) -> None:
        """Poll health from all registered adapters and update state."""
        for agent_id, adapter in self._adapters.items():
            try:
                health = adapter.health_summary()
                self.reducer.state.agents[agent_id] = health
            except Exception:
                logger.exception("Error polling health from %s", agent_id)

    # ── Action execution ─────────────────────────────────

    def execute_action(self, action: HiveAction) -> HiveActionResult:
        """Execute a HiveAction by delegating to target agent adapters.

        If target_agents is empty, attempts to execute on all.
        Returns aggregated HiveActionResult.
        """
        targets = action.target_agents or list(self._adapters.keys())
        agent_results: dict[str, dict[str, Any]] = {}
        overall_success = True

        for agent_id in targets:
            adapter = self._adapters.get(agent_id)
            if adapter is None:
                agent_results[agent_id] = {"error": "unregistered"}
                overall_success = False
                continue
            try:
                r = adapter.execute(action)
                agent_results[agent_id] = {
                    "success": r.success,
                    "action_id": r.action_id,
                }
                if not r.success:
                    overall_success = False
            except Exception as exc:
                agent_results[agent_id] = {"error": str(exc)}
                overall_success = False

        result = HiveActionResult(
            action_id=action.id,
            success=overall_success,
            agent_results=agent_results,
        )
        self._action_history.append(result)
        if len(self._action_history) > self._max_action_history:
            self._action_history = self._action_history[-self._max_action_history:]
        return result

    # ── Resource updates ─────────────────────────────────

    def update_agent_resources(
        self,
        agent_id: str,
        disk_used: int = 0,
        disk_total: int = 0,
        mem_used: int = 0,
        mem_total: int = 0,
        cpu_pct: float = 0.0,
    ) -> list[str]:
        """Update resource metrics for a specific agent. Returns alerts."""
        rs = self.state.resources
        rs.used_disk_bytes += disk_used
        rs.total_disk_bytes += disk_total
        rs.used_memory_bytes += mem_used
        rs.total_memory_bytes += mem_total
        rs.total_cpu_percent += cpu_pct
        return rs.alerts()

    # ── Incident resolution ──────────────────────────────

    def resolve_incident(self, incident_id: str) -> bool:
        """Mark an incident as resolved."""
        for inc in self.state.incidents:
            if inc.id == incident_id:
                inc.resolved = True
                inc.resolved_at = time.time()
                return True
        return False

    # ── Reporting ────────────────────────────────────────

    def report(self) -> str:
        """Generate a text health report."""
        self.dashboard.update_state(self.state)
        return self.dashboard.text_report()

    def summary(self) -> dict[str, Any]:
        """Generate a summary dict."""
        self.dashboard.update_state(self.state)
        return self.dashboard.summary()

    # ── Background run ───────────────────────────────────

    def run(self, blocking: bool = False) -> None:
        """Start the continuous tick loop."""
        if self._running:
            return
        self._running = True
        self._stop_event.clear()

        def _loop():
            while not self._stop_event.is_set():
                try:
                    self.tick()
                except Exception:
                    logger.exception("Tick error")
                self._stop_event.wait(timeout=self._poll_interval)
            self._running = False

        if blocking:
            _loop()
        else:
            self._thread = threading.Thread(target=_loop, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        """Stop the background tick loop."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)
            self._thread = None
        self._running = False
