"""
HiveAppliance — top-level orchestrator for the M5 Hive-Level Appliance.

Ties together: AgentApplianceAdapters, HiveEventBus, HiveReducer,
HivePlanner, SharedStoreAdapter, and HealthDashboard into a single
coherent control loop.

Usage:
    hive = HiveAppliance()
    hive.register_agent(adapter)
    new_incidents = hive.tick()   # poll → reduce → plan
    report = hive.dashboard.text_report()
"""
from __future__ import annotations

import time
import threading
from typing import Any, Optional

from hive.types import (
    HiveState, HiveAction, HiveActionResult, HiveIncident,
)
from hive.event_bus import HiveEventBus
from hive.reducer import HiveReducer
from hive.planner import HivePlanner
from hive.shared_store import SharedStoreAdapter
from hive.dashboard import HealthDashboard


class HiveAppliance:
    """Top-level M5 Hive Appliance orchestrator.

    Lifecycle:
    1. Register agent adapters via register_agent()
    2. Call tick() periodically (or run_loop() for continuous)
    3. Each tick: polls events → reduces state → plans actions
    4. Optionally execute proposed actions
    5. Query dashboard for reports
    """

    def __init__(
        self,
        correlation_window: float = 300.0,
        correlation_threshold: int = 2,
        auto_execute: bool = False,
    ):
        self._bus = HiveEventBus()
        self._reducer = HiveReducer(
            correlation_window=correlation_window,
            correlation_threshold=correlation_threshold,
        )
        self._planner = HivePlanner()
        self._store = SharedStoreAdapter()
        self._dashboard = HealthDashboard()
        self._adapters: dict[str, Any] = {}
        self._auto_execute = auto_execute
        self._tick_count: int = 0
        self._running = False
        self._lock = threading.Lock()
        self._action_history: list[dict[str, Any]] = []

        # Wire bus subscriber to reducer + shared store
        self._bus.add_subscriber(self._on_hive_event)

    # ── Properties ───────────────────────────────────────

    @property
    def bus(self) -> HiveEventBus:
        return self._bus

    @property
    def reducer(self) -> HiveReducer:
        return self._reducer

    @property
    def planner(self) -> HivePlanner:
        return self._planner

    @property
    def shared_store(self) -> SharedStoreAdapter:
        return self._store

    @property
    def dashboard(self) -> HealthDashboard:
        return self._dashboard

    @property
    def state(self) -> HiveState:
        return self._reducer.state

    @property
    def tick_count(self) -> int:
        return self._tick_count

    @property
    def registered_agents(self) -> list[str]:
        return list(self._adapters.keys())

    # ── Registration ─────────────────────────────────────

    def register_agent(self, adapter: Any) -> None:
        """Register an agent adapter with all subsystems."""
        agent_id = adapter.identity.agent_id
        with self._lock:
            self._adapters[agent_id] = adapter
            self._bus.register_adapter(adapter)
            self._store.register_adapter(adapter)
            self._reducer.register_agent(agent_id)

    def unregister_agent(self, agent_id: str) -> None:
        """Remove an agent from all subsystems."""
        with self._lock:
            self._adapters.pop(agent_id, None)
            self._bus.unregister_adapter(agent_id)
            self._store.unregister_adapter(agent_id)
            self._reducer.unregister_agent(agent_id)

    # ── Core loop ────────────────────────────────────────

    def tick(self) -> dict[str, Any]:
        """Execute one hive control cycle.

        Returns a summary dict:
        {
            "tick": int,
            "events_polled": int,
            "new_incidents": [...],
            "proposed_actions": [...],
            "executed_results": [...],
        }
        """
        self._tick_count += 1
        result: dict[str, Any] = {
            "tick": self._tick_count,
            "events_polled": 0,
            "new_incidents": [],
            "proposed_actions": [],
            "executed_results": [],
        }

        # 1. Poll events from all agents
        events = self._bus.poll_all()
        result["events_polled"] = len(events)

        # 2. Update agent health summaries
        self._poll_health()

        # 3. Collect new incidents (already processed via subscriber)
        # The reducer processes events via _on_hive_event callback.
        # Gather the open incidents that are new this tick.
        result["new_incidents"] = [
            inc.to_dict() for inc in self._reducer.state.open_incidents
        ]

        # 4. Plan actions
        proposed = self._planner.plan(self._reducer.state)
        result["proposed_actions"] = [a.to_dict() for a in proposed]

        # 5. Optionally execute
        if self._auto_execute and proposed:
            for action in proposed:
                exec_result = self.execute_action(action)
                result["executed_results"].append(exec_result.to_dict())

        # 6. Update dashboard
        self._dashboard.update_state(self._reducer.state)

        return result

    def _poll_health(self) -> None:
        """Poll health summaries from all adapters."""
        for agent_id, adapter in list(self._adapters.items()):
            try:
                summary = adapter.health_summary()
                self._reducer.update_agent_health(agent_id, summary)
            except Exception:
                pass  # Don't let one broken adapter stop health polling

    def _on_hive_event(self, hive_event) -> None:
        """Subscriber callback: feed events to reducer and shared store."""
        self._store.ingest(hive_event)
        new_incidents = self._reducer.reduce(hive_event)
        # Incidents are added to state inside reducer.reduce()

    # ── Action execution ─────────────────────────────────

    def execute_action(self, action: HiveAction) -> HiveActionResult:
        """Execute a proposed HiveAction by delegating to target agents."""
        results: dict[str, dict[str, Any]] = {}
        overall_success = True

        for agent_id in action.target_agents:
            adapter = self._adapters.get(agent_id)
            if adapter is None:
                results[agent_id] = {"error": "agent not registered"}
                overall_success = False
                continue
            try:
                agent_result = adapter.execute(action)
                results[agent_id] = agent_result.to_dict()
                if not agent_result.success:
                    overall_success = False
            except Exception as e:
                results[agent_id] = {"error": str(e)}
                overall_success = False

        result = HiveActionResult(
            action_id=action.id,
            success=overall_success,
            agent_results=results,
        )
        action.status = "executed"
        self._action_history.append({
            "action": action.to_dict(),
            "result": result.to_dict(),
            "ts": time.time(),
        })
        return result

    # ── Convenience ──────────────────────────────────────

    def report(self) -> str:
        """Generate a text health report."""
        self._dashboard.update_state(self._reducer.state)
        return self._dashboard.text_report()

    def summary(self) -> dict[str, Any]:
        """Return structured dashboard summary."""
        self._dashboard.update_state(self._reducer.state)
        return self._dashboard.summary()

    def resolve_incident(self, incident_id: str) -> bool:
        """Resolve a hive-level incident."""
        return self._reducer.resolve_hive_incident(incident_id)

    def update_agent_resources(
        self, agent_id: str,
        disk_total: int = 0, disk_used: int = 0,
        memory_total: int = 0, memory_used: int = 0,
        cpu_percent: float = 0.0,
    ) -> list[str]:
        """Update resource metrics for an agent. Returns alerts."""
        return self._reducer.update_resources(
            agent_id, disk_total, disk_used,
            memory_total, memory_used, cpu_percent,
        )

    @property
    def action_history(self) -> list[dict[str, Any]]:
        return list(self._action_history)
