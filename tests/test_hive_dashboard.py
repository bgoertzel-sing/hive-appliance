"""Tests for hive.dashboard — HealthDashboard."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import time
from hive.dashboard import HealthDashboard
from hive.types import (
    HiveState, AgentHealthSummary, AgentHealth,
    HiveIncident, HiveResourceState,
)
from schemas.types import Severity


def _state_healthy():
    state = HiveState()
    state.agents["a1"] = AgentHealthSummary(
        agent_id="a1", health=AgentHealth.HEALTHY,
    )
    state.agents["a2"] = AgentHealthSummary(
        agent_id="a2", health=AgentHealth.HEALTHY,
    )
    return state


def _state_mixed():
    state = HiveState()
    state.agents["a1"] = AgentHealthSummary(
        agent_id="a1", health=AgentHealth.HEALTHY,
    )
    state.agents["a2"] = AgentHealthSummary(
        agent_id="a2", health=AgentHealth.DEGRADED, open_incidents=1,
    )
    state.agents["a3"] = AgentHealthSummary(
        agent_id="a3", health=AgentHealth.FAILED, open_incidents=3,
    )
    return state


# ── Summary ──────────────────────────────────────────────

def test_summary_healthy():
    dash = HealthDashboard(state=_state_healthy())
    s = dash.summary()
    assert s["hive_health"] == "healthy"
    assert s["agent_count"] == 2
    assert s["healthy_count"] == 2
    assert s["degraded_count"] == 0
    assert s["failed_count"] == 0


def test_summary_mixed():
    dash = HealthDashboard(state=_state_mixed())
    s = dash.summary()
    assert s["hive_health"] == "failed"  # any failed → overall failed
    assert s["healthy_count"] == 1
    assert s["degraded_count"] == 1
    assert s["failed_count"] == 1


def test_summary_empty():
    dash = HealthDashboard()
    s = dash.summary()
    assert s["hive_health"] == "unknown"
    assert s["agent_count"] == 0


def test_summary_with_incidents():
    state = _state_mixed()
    inc = HiveIncident(
        symptom="disk_full", severity=Severity.ERROR,
        affected_agents=["a2", "a3"], resolved=False,
    )
    state.incidents.append(inc)
    dash = HealthDashboard(state=state)
    s = dash.summary()
    assert s["open_incident_count"] == 1
    assert s["resolved_incident_count"] == 0


def test_summary_with_resources():
    state = _state_healthy()
    state.resources = HiveResourceState(
        total_disk_bytes=1000, used_disk_bytes=960,
    )
    dash = HealthDashboard(state=state)
    s = dash.summary()
    assert s["resources"]["disk_usage"] > 0.9


# ── Text report ──────────────────────────────────────────

def test_text_report_healthy():
    dash = HealthDashboard(state=_state_healthy())
    report = dash.text_report()
    assert "HIVE HEALTH DASHBOARD" in report
    assert "HEALTHY" in report


def test_text_report_with_incidents():
    state = _state_mixed()
    inc = HiveIncident(
        symptom="disk_full", severity=Severity.ERROR,
        affected_agents=["a2", "a3"],
    )
    state.incidents.append(inc)
    dash = HealthDashboard(state=state)
    report = dash.text_report()
    assert "disk_full" in report
    assert "OPEN HIVE INCIDENTS" in report


def test_text_report_with_services():
    state = _state_healthy()
    state.agents["a1"].services = {"nginx": "active", "postgres": "active"}
    dash = HealthDashboard(state=state)
    report = dash.text_report()
    assert "nginx" in report


def test_text_report_with_resource_alerts():
    state = _state_healthy()
    state.resources = HiveResourceState(
        total_disk_bytes=100, used_disk_bytes=96,
    )
    dash = HealthDashboard(state=state)
    report = dash.text_report()
    assert "CRITICAL" in report or "RESOURCES" in report


# ── Update state ─────────────────────────────────────────

def test_update_state():
    dash = HealthDashboard()
    assert dash.summary()["agent_count"] == 0
    dash.update_state(_state_healthy())
    assert dash.summary()["agent_count"] == 2


# ── Snapshots ────────────────────────────────────────────

def test_take_snapshot():
    dash = HealthDashboard(state=_state_healthy())
    snap = dash.take_snapshot()
    assert "snapshot_ts" in snap
    assert snap["agent_count"] == 2
    assert len(dash.snapshots) == 1


def test_snapshot_limit():
    dash = HealthDashboard(state=_state_healthy())
    dash._max_snapshots = 3
    for _ in range(5):
        dash.take_snapshot()
    assert len(dash.snapshots) == 3


# ── Trend ────────────────────────────────────────────────

def test_trend():
    dash = HealthDashboard(state=_state_healthy())
    for _ in range(5):
        dash.take_snapshot()
    trend = dash.trend("healthy_count", last_n=3)
    assert len(trend) == 3
    assert all(v == 2 for v in trend)


def test_trend_empty():
    dash = HealthDashboard()
    trend = dash.trend("healthy_count")
    assert trend == []
