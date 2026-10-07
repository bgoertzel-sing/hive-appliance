"""
HiveAppliance — top-level orchestrator for the M5 Hive-Level Appliance.

Ties together: AgentApplianceAdapters, HiveEventBus, HiveReducer,
HivePlanner, SharedStoreAdapter, and HealthDashboard into a single
coherent control loop.

Usage:
    hive = HiveAppliance()
    hive.register_agent("proto2", adapter)
    hive.tick()   # one iteration of the control loop
    hive.run()    # continuous loop in background thread
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
from hive.types import HiveActionResult, HiveEvent, HiveIncident

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
    ):
        self.bus = HiveEventBus()
        self.reducer = HiveReducer(correlation_threshold=correlation_threshold)
        self.planner = HivePlanner()
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
        self._action_results: list[HiveActionResult] = []
        self._max_action_results: int = 500

    # ── Agent registration ───────────────────────────────

    def register_agent(self, agent_id: str | AgentApplianceAdapter,
                       adapter: AgentApplianceAdapter | None = None) -> None:
        """Register an agent adapter with all hive components."""
        if adapter is None:
            adapter = agent_id  # type: ignore[assignment]
            agent_id = adapter.identity.agent_id
        self._adapters[agent_id] = adapter
        self.bus.register_adapter(agent_id, adapter)
        self.reducer.register_agent(agent_id)
        self.shared_store.register_adapter(agent_id, adapter)
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
            "events": 0,
            "events_polled": 0,
            "incidents": [],
            "actions": [],
            "proposed_actions": [],
            "executed_results": [],
            "errors": [],
        }

        # 1. Poll events
        try:
            events = self.bus.poll_all()
            result["events"] = len(events)
            result["events_polled"] = len(events)
            self._total_events += len(events)
        except Exception:
            logger.exception("Error during event polling")
            result["errors"].append("event_poll_failed")
            events = []

        # 2. Reduce events into state
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

        # 3. Periodic health polling
        now = time.time()
        if now - self._last_health_poll >= self._health_poll_interval:
            self._poll_health(result)
            self._last_health_poll = now

        # 4. Plan actions
        try:
            actions = self.planner.plan(self.reducer.state)
            result["actions"] = [a.id for a in actions]
            result["proposed_actions"] = [a.to_dict() for a in actions]
        except Exception:
            logger.exception("Error during action planning")
            result["errors"].append("planning_failed")
            actions = []

        # 5. Execute actions
        if self._auto_execute:
            for action in actions:
                action_result = self.execute_action(action)
                result["executed_results"].append(action_result.to_dict())

        # 6. Store hive events
        for hevt in events:
            self.shared_store.ingest(hevt)

        # 7. Update dashboard
        self.dashboard.update_state(self.reducer.state)

        return result

    def _poll_health(self, result: dict[str, Any]) -> None:
        """Poll health from all adapters and update reducer."""
        for agent_id, adapter in self._adapters.items():
            try:
                summary = adapter.health_summary()
                self.reducer.update_agent_health(agent_id, summary)
            except Exception:
                logger.exception("Error polling health from agent %s", agent_id)
                result.setdefault("errors", []).append(
                    f"health_poll_failed:{agent_id}"
                )

    def execute_action(self, action: Any) -> HiveActionResult:
        """Execute an action on all targets and aggregate their receipts."""
        agent_results: dict[str, dict[str, Any]] = {}
        for target in action.target_agents:
            adapter = self._adapters.get(target)
            if adapter is None:
                agent_results[target] = {"success": False, "error": "not registered"}
                continue
            try:
                receipt = adapter.execute(action)
                detail = receipt.agent_results.get(target, {
                    "success": receipt.success, "output": receipt.output,
                    "error": receipt.error,
                })
                agent_results[target] = detail
            except Exception as exc:
                logger.exception("Error executing action %s on %s", action.id, target)
                agent_results[target] = {"success": False, "error": str(exc)}
        success = bool(agent_results) and all(r.get("success") for r in agent_results.values())
        result = HiveActionResult(action_id=action.id, success=success,
                                  agent_results=agent_results)
        self._action_results.append(result)
        self._action_results = self._action_results[-self._max_action_results:]
        self.planner.record_result(result)
        return result

    # ── Background run ───────────────────────────────────

    def run(self) -> None:
        """Start the hive control loop in a background thread."""
        if self._running:
            logger.warning("HiveAppliance already running")
            return
        if self._thread is not None and self._thread.is_alive():
            # L1: previous stop() timed out; never run two control loops.
            raise RuntimeError("previous hive control loop has not exited; refusing restart")
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop, name="hive-appliance", daemon=True,
        )
        self._thread.start()
        logger.info("HiveAppliance started (poll_interval=%.1fs)", self._poll_interval)

    def stop(self, timeout: float = 10.0) -> bool:
        """Stop the background control loop gracefully.

        L1: returns False (and keeps the thread reference so run() refuses
        a concurrent restart) if the loop does not exit within timeout.
        """
        self._running = False
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():
                logger.warning("HiveAppliance thread did not stop within %.1fs", timeout)
                return False
            self._thread = None
        logger.info("HiveAppliance stopped")
        return True

    def _run_loop(self) -> None:
        """Internal loop for the background thread."""
        logger.info("Hive control loop started")
        while self._running:
            try:
                self.tick()
            except Exception:
                logger.exception("Unexpected error in hive tick")
            # Use stop_event.wait for interruptible sleep
            if self._stop_event.wait(timeout=self._poll_interval):
                break
        logger.info("Hive control loop exited")

    # ── Status / introspection ───────────────────────────

    @property
    def is_running(self) -> bool:
        """Return is running."""
        return self._running

    def status(self) -> dict[str, Any]:
        """Return current hive appliance status."""
        return {
            "running": self._running,
            "tick_count": self._tick_count,
            "total_events": self._total_events,
            "total_incidents": self._total_incidents,
            "agents": list(self._adapters.keys()),
            "dashboard": self.dashboard.summary(),
        }

    @property
    def registered_agents(self) -> list[str]:
        return list(self._adapters)

    @property
    def state(self):
        return self.reducer.state

    @property
    def tick_count(self) -> int:
        return self._tick_count

    @property
    def action_history(self) -> list[HiveActionResult]:
        return list(self._action_results)

    def report(self) -> str:
        return self.dashboard.text_report()

    def summary(self) -> dict[str, Any]:
        return self.dashboard.summary()

    def update_agent_resources(self, agent_id: str, **resources: Any) -> list[str]:
        return self.reducer.update_resources(agent_id, **resources)

    def resolve_incident(self, incident_id: str) -> bool:
        return self.reducer.resolve_hive_incident(incident_id)
