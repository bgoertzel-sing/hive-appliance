"""Reconstruction of Astra 7024 experiment harness (originals under
experiments/20260927-astra-7024/ were never pushed).  Rebuilt by ProtoMegaBot2
from docs/ASTRA_REVIEW_7024.md sections 1, 2, 4 and the P1 qualification item.

Sections:
  inverted     - the three 7003 adversarial checks with corrected expectations
  named        - 14 named identical-stream schedules (+ snapshot variants)
  systematic   - 384 mixed-address orderings (24 orders x 16 addressings)
  supplementary- 4 lifecycle/prelink schedules incl. the N4 residual
  public_repair- real Appliance.repair() success/failure through
                 LocalAgentAdapter + HiveAppliance ticks (in-memory executor)
Failures are recorded and the stream continues.  Exit 0 iff all pass.
"""
from __future__ import annotations
import itertools, json, sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from controller.reducer import Reducer
from hive.reducer import HiveReducer
from hive.types import HiveEvent
from schemas.types import Event, EventKind, IncidentReport


def ev(kind, payload):
    return Event(kind=kind, source="t", subject="svc", payload=payload)

def INC(iid):
    return ev(EventKind.INCIDENT, IncidentReport(id=iid, component="svc", symptom="down").to_dict())

def PLAN(pid, iid, n):
    return ev(EventKind.PLAN, {"id": pid, "incident_id": iid, "steps": [{"verb": "v"}] * n})

def RC(rid, plan_id="", idx=0, ok=True, incident_id=""):
    p = {"id": rid, "step_index": idx, "verified": ok}
    if plan_id: p["plan_id"] = plan_id
    if incident_id: p["incident_id"] = incident_id
    return ev(EventKind.RECEIPT, p)

SNAP = "SNAPSHOT"


def run(name, stream, plans=("p",), expect=None, snapshot_before_first_plan=False):
    """expect: dict {event_index: sorted open ids} (negative index ok)."""
    loc, hive = Reducer(), HiveReducer(); hive.register_agent("a1")
    if snapshot_before_first_plan:
        k = next(i for i, e in enumerate(stream) if e is not SNAP and e.kind == EventKind.PLAN)
        stream = stream[:k] + [SNAP] + stream[k:]
    errs, trace, n = [], [], 0
    for e in stream:
        if e is SNAP:
            r2 = Reducer(); r2.restore_snapshot(json.loads(json.dumps(loc.snapshot()))); loc = r2
            continue
        loc.reduce(e); hive.reduce(HiveEvent(source_agent="a1", original_event=e))
        lo = sorted(i.id for i in loc.open_incidents())
        hi = sorted(i["incident_id"] for i in hive._open_agent_incidents("a1"))
        hc = hive.state.agents["a1"].open_incidents
        if lo != hi: errs.append(f"ev{n}: open local={lo} hive={hi}")
        if hc != len(hi): errs.append(f"ev{n}: hive displayed count {hc} != {len(hi)}")
        for pid in plans:
            ls = (sorted(loc._plan_verified.get(pid, ())), sorted(loc._plan_failed_steps.get(pid, ())))
            hs = (sorted(hive._plan_verified_steps.get("a1:" + pid, ())), sorted(hive._plan_failed.get("a1:" + pid, ())))
            if ls != hs: errs.append(f"ev{n}: steps[{pid}] local={ls} hive={hs}")
        trace.append({"local": lo, "hive": hi, "hive_count": hc})
        n += 1
    for k, want in (expect or {}).items():
        got = trace[k]["local"]
        if got != want: errs.append(f"expect ev{k}: want {want} got local={got} hive={trace[k]['hive']}")
    return {"name": name, "pass": not errs, "errors": errs, "trace": trace}


def inverted():
    out = []
    s = [INC("i"), RC("r0", "p", 0), RC("r1", "p", 1), RC("rf", "p", 0, ok=False), PLAN("p", "i", 2)]
    r = run("buffered_successes_failure_plan (old 1/0 -> want 1/1)", s, expect={-1: ["i"]}); out.append(r)
    r = run("same_then_fresh_retry (want 0/0)", s + [RC("r0b", "p", 0)], expect={-2: ["i"], -1: []}); out.append(r)
    r = run("contradiction_both_plans_registered (old 1/2 -> want 2/2)",
            [INC("i"), INC("o"), PLAN("p", "i", 2), PLAN("q", "o", 1), RC("a", "p", 0), RC("x", "p", 1, incident_id="o")],
            plans=("p", "q"), expect={-1: ["i", "o"]}); out.append(r)
    return out


NAMED = {
  "failure_then_success_in_buffer": ([INC("i"), RC("f", "p", 0, False), RC("s", "p", 0), RC("r1", "p", 1), PLAN("p", "i", 2)], ("p",), {-1: []}),
  "multiple_failed_indices": ([INC("i"), RC("f0", "p", 0, False), RC("f1", "p", 1, False), PLAN("p", "i", 2), RC("s0", "p", 0), RC("s1", "p", 1)], ("p",), {-3: ["i"], -2: ["i"], -1: []}),
  "retry_before_plan": ([INC("i"), RC("r1", "p", 1), RC("f0", "p", 0, False), RC("s0", "p", 0), PLAN("p", "i", 2)], ("p",), {-1: []}),
  "retry_after_plan": ([INC("i"), RC("f0", "p", 0, False), RC("r1", "p", 1), PLAN("p", "i", 2), RC("s0", "p", 0)], ("p",), {-2: ["i"], -1: []}),
  "duplicate_retries": ([INC("i"), RC("f0", "p", 0, False), PLAN("p", "i", 2), RC("s0", "p", 0), RC("s0", "p", 0), RC("r1", "p", 1)], ("p",), {-2: ["i"], -1: []}),
  "duplicate_old_failure_replayed": ([INC("i"), RC("f0", "p", 0, False), PLAN("p", "i", 2), RC("s0", "p", 0), RC("r1", "p", 1), RC("f0", "p", 0, False)], ("p",), {-2: [], -1: []}),
  "plan_replay": ([INC("i"), RC("r0", "p", 0), PLAN("p", "i", 2), PLAN("p", "i", 2), RC("r1", "p", 1)], ("p",), {-2: ["i"], -1: []}),
  "two_plans_one_incident": ([INC("i"), RC("q0", "q", 0), RC("f0", "p", 0, False), PLAN("p", "i", 2), PLAN("q", "i", 1), RC("s0", "p", 0), RC("s1", "p", 1)], ("p", "q"), {-3: ["i"], -2: ["i"], -1: []}),
  "untargeted_receipts_resolve_nothing": ([INC("i"), PLAN("p", "i", 2), RC("u0", idx=0), RC("u1", idx=1)], ("p",), {-1: ["i"]}),
  "incident_only_held_across_other_plan": ([INC("i"), INC("o"), RC("a", idx=0, incident_id="i"), PLAN("q", "o", 1), PLAN("p", "i", 1)], ("p", "q"), {-2: ["i", "o"], -1: ["o"]}),
  "contradiction_while_buffered_other_open": ([INC("i"), INC("o"), RC("bad", "p", 0, incident_id="o"), RC("good", "p", 1), PLAN("q", "o", 1), PLAN("p", "i", 2)], ("p", "q"), {-1: ["i", "o"]}),
  "mixed_early_incident_success_late_plan_failure": ([INC("i"), RC("is", idx=0, incident_id="i"), RC("pf", "p", 0, False), RC("r1", "p", 1), PLAN("p", "i", 2), RC("r0b", "p", 0)], ("p",), {-2: ["i"], -1: []}),
  "mixed_early_incident_failure_late_plan_success": ([INC("i"), RC("if", idx=0, ok=False, incident_id="i"), RC("ps", "p", 0), RC("r1", "p", 1), PLAN("p", "i", 2)], ("p",), {-1: []}),
  "mixed_early_plan_success_late_incident_failure": ([INC("i"), RC("ps", "p", 0), RC("if", idx=0, ok=False, incident_id="i"), RC("r1", "p", 1), PLAN("p", "i", 2), RC("is", idx=0, incident_id="i")], ("p",), {-2: ["i"], -1: []}),
}


def systematic():
    base = [(0, True), (0, False), (1, True), (1, False)]
    out = []
    for order in itertools.permutations(range(4)):
        for addr in itertools.product((0, 1), repeat=4):
            s, latest = [INC("i")], {}
            for j in order:
                idx, ok = base[j]
                s.append(RC(f"r{j}", idx=idx, ok=ok, incident_id="i") if addr[j] else RC(f"r{j}", "p", idx, ok))
                latest[idx] = ok
            s.append(PLAN("p", "i", 2))
            out.append(run(f"sys order={order} addr={addr}", s, expect={-1: [] if all(latest.values()) else ["i"]}))
    return out


def _n4():
    return [INC("i"), INC("o"), RC("bad", "p", 0, incident_id="o"), RC("good", "p", 1),
            PLAN("q", "o", 1), RC("q0", "q", 0)]

def supplementary():
    return [
        run("buffer_contradiction_then_other_resolved", _n4() + [PLAN("p", "i", 2), RC("p0", "p", 0)], ("p", "q"), {-2: ["i"], -1: []}),
        run("buffer_contradiction_then_other_resolved_snapshot", _n4() + [SNAP, PLAN("p", "i", 2), RC("p0", "p", 0)], ("p", "q"), {-2: ["i"], -1: []}),
        run("control_contradiction_arrives_after_plan_q", [INC("i"), INC("o"), PLAN("q", "o", 1), RC("bad", "p", 0, incident_id="o"), RC("good", "p", 1), RC("q0", "q", 0), PLAN("p", "i", 2)], ("p", "q"), {-1: ["i"]}),
        run("prelink_other_resolved_before_receipt_arrives", [INC("i"), INC("o"), PLAN("q", "o", 1), RC("q0", "q", 0), RC("bad", "p", 0, incident_id="o"), RC("good", "p", 1), PLAN("p", "i", 2)], ("p", "q"), None),
    ]


def public_repair():
    from controller.appliance import Appliance
    from hive.adapter import LocalAgentAdapter
    from hive.appliance import HiveAppliance
    from reasoning.planner import SimplePlanner
    from schemas.types import Receipt, Severity
    from verifier.exit_code_verifier import ExitCodeVerifier

    class MemExecutor:
        is_simulation = False; name = "mem"
        def __init__(self, fail_idx=None): self.fail_idx, self.ran = fail_idx, []
        def execute_step(self, step, plan, i):
            self.ran.append(i)
            return Receipt(plan_id=plan.id, step_index=i, verb=step.get("verb", ""), target="x",
                           exit_code=1 if i == self.fail_idx else 0, attempt_id=getattr(plan, "attempt_id", ""))
    out = []
    for label, fail_idx, want_local, want_health in (("success", None, 0, "healthy"), ("failure_step1", 1, 1, "failed")):
        errs = []
        app = Appliance(":memory:")
        app.set_planner(SimplePlanner()); ex = MemExecutor(fail_idx); app.set_executor(ex); app.set_verifier(ExitCodeVerifier())
        inc = IncidentReport(component="/nonexistent/hive-qual", symptom="file_missing", severity=Severity.ERROR)
        app.record_incident(inc)
        rs = app.repair(inc)
        hive = HiveAppliance(); hive.register_agent("a1", LocalAgentAdapter("a1", app))
        hive.tick(); hive.tick()
        lo = len(app.reducer.open_incidents())
        hi = len(hive.reducer._open_agent_incidents("a1"))
        ag = hive.reducer.state.agents["a1"]
        health = getattr(ag.health, "value", str(ag.health))
        outcome = str(app.repair_outcomes.get(inc.id))
        if lo != want_local: errs.append(f"local open {lo} != {want_local}")
        if hi != want_local or ag.open_incidents != want_local: errs.append(f"hive open {hi}/{ag.open_incidents} != {want_local}")
        if health != want_health: errs.append(f"hive health {health} != {want_health}")
        out.append({"name": f"public_repair_{label}", "pass": not errs, "errors": errs,
                    "executed": ex.ran, "verified": [r.verified for r in rs], "outcome": outcome,
                    "local_open": lo, "hive_open": hi, "hive_health": health})
        app.close()
    return out


def main():
    res = {"inverted": inverted(),
           "named": [run(k, s, pl, ex) for k, (s, pl, ex) in NAMED.items()],
           "named_snapshot": [run(k + "_snap", s, pl, ex, snapshot_before_first_plan=True) for k, (s, pl, ex) in NAMED.items()],
           "systematic": systematic(), "supplementary": supplementary(), "public_repair": public_repair()}
    summ = {k: {"total": len(v), "pass": sum(r["pass"] for r in v), "fail": sum(not r["pass"] for r in v)} for k, v in res.items()}
    out = pathlib.Path(__file__).with_name("results.json")
    for k in ("systematic",):  # keep file small: traces only for failures
        for r in res[k]:
            if r["pass"]: r.pop("trace")
    out.write_text(json.dumps({"summary": summ, "results": res}, indent=1, default=str))
    print(json.dumps(summ, indent=1))
    for k, v in res.items():
        for r in v:
            if not r["pass"]: print("FAIL", k, r["name"], r["errors"][:3])
    for r in res["public_repair"]:
        print("REPAIR", {x: r[x] for x in r if x != "errors"})
    sys.exit(0 if all(s["fail"] == 0 for s in summ.values()) else 1)

if __name__ == "__main__":
    main()
