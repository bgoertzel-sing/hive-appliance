"""Independent expectations for H2, N9, N10. All cases retain actual outcomes."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
import traceback

E = Path(__file__).resolve().parent
sys.path.insert(0, os.environ['HIVE_SRC'])
from controller.reducer import Reducer, MAX_DIAG_ENTRIES
from hive.reducer import HiveReducer
from hive.types import HiveEvent
from recovery.checkpoint import CheckpointManager
from schemas.types import Event, EventKind

def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), E / (name + '.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.Reducer

Legacy = load('legacy-reducer-e6afe16')
Previous = load('legacy-reducer-ef18db3')

def I(i='i', p='', resolved=False):
    return Event(kind=EventKind.INCIDENT, payload=dict(id=i, component='svc', symptom='down',
        severity='critical', plan_id=p, resolved=resolved))

def P(p='p', i='i', n=2):
    return Event(kind=EventKind.PLAN, payload=dict(id=p, incident_id=i, steps=[{} for _ in range(n)]))

def R(r, k=0, ok=True, p='p', i=''):
    return Event(kind=EventKind.RECEIPT, payload=dict(id=r, step_index=k, verified=ok, plan_id=p, incident_id=i))

def opened(l):
    return sorted(i.id for i in l.open_incidents())

def restore(l):
    r = Reducer()
    r.restore_snapshot(json.loads(json.dumps(l.snapshot())))
    return r

def state(l):
    return dict(open=opened(l), verified={k: sorted(v) for k, v in l._plan_verified.items()},
                failed={k: sorted(v) for k, v in l._plan_failed_steps.items()},
                pending=copy.deepcopy(l._pending_receipts), owner=dict(l._plan_owner),
                quarantine=sorted(l._owner_unproven), diagnostics=copy.deepcopy(l.migration_diagnostics))

def disk(producer, label):
    m = CheckpointManager(str(E / 'new-checkpoints' / label))
    c = m.create(producer.snapshot(), label=label)
    saved = m.load(c.id).appliance_state
    return saved, str(Path(m.checkpoint_dir) if hasattr(m, 'checkpoint_dir') else E / 'new-checkpoints' / label)

counter = 0
def lost(resolved=False, foreign=False, ambiguous=False):
    global counter
    counter += 1
    old = Legacy()
    for e in [P(), I(p='p' if ambiguous else ''), I('other', 'p' if ambiguous else ('q' if foreign else ''), resolved)]:
        old.reduce(e)
    s, _ = disk(old, 'lost-' + str(counter))
    r = Reducer()
    r.restore_snapshot(s)
    assert 'p' in r._owner_unproven
    return r

OUT = {}
def case(name, fn):
    row = {}
    try:
        fn(row)
        row['passed'] = True
    except Exception as exc:
        row.update(passed=False, error=repr(exc), traceback=traceback.format_exc())
    OUT[name] = row
    print(name, row['passed'], flush=True)

def h2_matrix(row):
    sequences = {
        'complete_late': ([P(), R('a'), R('b', 1), I()], []),
        'failed_late': ([P(), R('a'), R('f', ok=False), R('b', 1), I()], ['i']),
        'ambiguous_buffer_failure': ([P(), P('q'), R('f', ok=False, p='', i='i'), R('a'), R('b', 1), I()], ['i']),
        'drain_before_completion': ([P(), P('q'), R('f', ok=False, p='', i='i'), R('a'), R('b', 1), I(p='p')], ['i']),
        'drain_fresh_retry': ([P(), P('q'), R('f', ok=False, p='', i='i'), R('a'), R('b', 1), I(p='p'), R('retry')], []),
        'ownerless_payload_link': ([P(i=''), R('a'), R('b', 1), I(p='p')], ['i']),
        'unrelated': ([P(), R('a'), R('b', 1), I(), I('other')], ['other']),
    }
    rows = []
    for name, (stream, expected) in sequences.items():
        for cut in [None] + list(range(len(stream) + 1)):
            l, h = Reducer(), HiveReducer()
            h.register_agent('a')
            trace = []
            if cut == 0:
                l = restore(restore(l))
            for j, event in enumerate(stream):
                l.reduce(event)
                h.reduce(HiveEvent(source_agent='a', original_event=event))
                if cut == j + 1:
                    l = restore(restore(l))
                hs = h.state.agents['a']
                ho = sorted(i['incident_id'] for i in h._open_agent_incidents('a'))
                lv = {k: sorted(v) for k, v in l._plan_verified.items()}
                lf = {k: sorted(v) for k, v in l._plan_failed_steps.items()}
                hv = {k[2:]: sorted(v) for k, v in h._plan_verified_steps.items()}
                hf = {k[2:]: sorted(v) for k, v in h._plan_failed.items()}
                agree = opened(l) == ho and lv == hv and lf == hf and hs.open_incidents == len(ho)
                # Before an INCIDENT appears, a newly registered agent may be UNKNOWN.
                health_ok = hs.health.value == ('failed' if ho else 'healthy') if any(e.kind == EventKind.INCIDENT for e in stream[:j+1]) else True
                trace.append(dict(event=event.to_dict(), local=state(l), hive_open=ho,
                                  hive_verified=hv, hive_failed=hf, health=hs.health.value,
                                  agreement=agree, health_ok=health_ok))
            rows.append(dict(name=name, cut=cut, expected=expected, trace=trace,
                             passed=opened(l) == expected and all(t['agreement'] and t['health_ok'] for t in trace)))
    row['schedules'] = rows
    row['total'] = len(rows)
    row['passing'] = sum(r['passed'] for r in rows)
    assert all(r['passed'] for r in rows)

case('h2_boundary_matrix', h2_matrix)

def validation(row):
    results = []
    for field in ['actor', 'reason']:
        for value in ['', ' \t\n', None, 1, False, [], {}]:
            l = lost()
            kw = dict(actor='review7173', reason='documented fixture', allow_non_candidate=True)
            kw[field] = value
            before = copy.deepcopy(vars(l))
            error = None
            try:
                l.rebind_plan_owner('p', 'i', **kw)
            except ValueError:
                error = 'ValueError'
            results.append(dict(field=field, value=value, error=error, unchanged=vars(l) == before))
    row['cases'] = results
    assert all(r['error'] == 'ValueError' and r['unchanged'] for r in results)
    l = lost()
    try:
        l.rebind_plan_owner('p', 'i')
    except TypeError:
        row['missing_keywords'] = 'TypeError'
    assert row['missing_keywords'] == 'TypeError'

case('n9_actor_reason_validation', validation)

def denials(row):
    rows = []
    for name, target in [('unknown', 'unknown'), ('resolved', 'other'), ('foreign', 'other'), ('empty', ''), ('non_candidate', 'i'), ('outside', 'i')]:
        l = lost(resolved=name == 'resolved', foreign=name == 'foreign')
        if name == 'outside':
            l = Reducer()
            for e in [I(), P()]:
                l.reduce(e)
        before = copy.deepcopy(vars(l))
        pv = l.preview_rebind('p', target, allow_non_candidate=name != 'non_candidate')
        accepted = l.rebind_plan_owner('p', target, actor='op', reason='test', allow_non_candidate=name != 'non_candidate')
        rows.append(dict(name=name, preview=pv, accepted=accepted, unchanged=vars(l) == before))
    row['cases'] = rows
    assert all(not x['preview']['allowed'] and not x['accepted'] and x['unchanged'] for x in rows)

case('n9_denials_no_state_mutation', denials)

def rebind_paths(row):
    rows = []
    for candidate in [False, True]:
        for held in ['none', 'success', 'newer_failure']:
            l = lost()
            if candidate:
                l.reduce(P())
            if held != 'none':
                l.reduce(R('a'))
                l.reduce(R('b', 1))
            if held == 'newer_failure':
                l.reduce(R('f', ok=False))
            before = copy.deepcopy(vars(l))
            pv = l.preview_rebind('p', 'i', allow_non_candidate=not candidate)
            pure = vars(l) == before
            accepted = l.rebind_plan_owner('p', 'i', actor='  op  ', reason='fixture evidence', allow_non_candidate=not candidate)
            after = state(l)
            expected_closed = ['i'] if held == 'success' else []
            rec = l.migration_diagnostics['owner_rebinds'][-1]
            duplicate = l.rebind_plan_owner('p', 'other', actor='op', reason='duplicate', allow_non_candidate=True)
            for _ in range(20):
                l = restore(l)
            rows.append(dict(candidate=candidate, held=held, preview=pv, after=after, record=rec,
                accepted=accepted, duplicate=duplicate, pure=pure, persisted=state(l) == after,
                passed=pure and accepted and not duplicate and state(l) == after and pv['would_close'] == expected_closed
                and rec['closed'] == expected_closed and rec['candidate'] == candidate
                and rec['actor'] == '  op  ' and rec['reason'] == 'fixture evidence'
                and rec['held_receipts'] == (0 if held == 'none' else 2 if held == 'success' else 3)))
    row['cases'] = rows
    assert all(r['passed'] for r in rows)

case('n9_candidate_override_preview_audit_roundtrip', rebind_paths)

def preview_alias(row):
    l = lost()
    l.reduce(R('malformed', k={'bad_index': [0]}, ok={'unverified': [False]}))
    before = copy.deepcopy(vars(l))
    pv = l.preview_rebind('p', 'i', allow_non_candidate=True)
    row['call_itself_pure'] = vars(l) == before
    pv['held_receipts'][0]['step_index']['bad_index'].append(1)
    pv['held_receipts'][0]['verified']['unverified'].append(True)
    row['before_pending'] = before['_pending_receipts']
    row['after_pending'] = copy.deepcopy(l._pending_receipts)
    row['state_changed_through_returned_value'] = vars(l) != before
    assert vars(l) == before, 'Preview returned mutable receipt-field aliases into live state'

case('n9_preview_mutable_alias_purity', preview_alias)

def preview_coverage(row):
    l = lost(ambiguous=True)
    for e in [R('valid'), R('invalid_index', k=99), R('contradictory', k=1, i='other'),
              R('other_link_failure', ok=False, p='', i='other')]:
        l.reduce(e)
    pv = l.preview_rebind('p', 'i', allow_non_candidate=True)
    before = state(l)
    l.rebind_plan_owner('p', 'i', actor='op', reason='fixture', allow_non_candidate=True)
    after = state(l)
    removed = sorted(set(before['pending']) - set(after['pending']))
    advertised = sorted(x['id'] for x in pv['held_receipts'])
    row.update(preview=pv, before=before, after=after, removed_receipts=removed, advertised=advertised,
               audit=l.migration_diagnostics['owner_rebinds'][-1])
    assert advertised == removed, 'Preview held/released list omits another linked receipt consumed by rebind'

case('n9_preview_release_coverage', preview_coverage)

def n10_fresh(row):
    n = MAX_DIAG_ENTRIES + 44
    old = Legacy()
    for k in range(n):
        old.reduce(P('p' + str(k), 'i' + str(k), 1))
        old.reduce(I('i' + str(k)))
    saved, path = disk(old, 'n10-e6afe16-300')
    l = Reducer()
    l.restore_snapshot(saved)
    for k in range(n):
        l.reduce(P('p' + str(k), 'i' + str(k), 1))
    pre = state(l)
    stable = l.snapshot()
    for _ in range(20):
        l = restore(l)
    row.update(before=pre, disk=path, stable_repeated_restore=l.snapshot() == stable)
    assert len(l._owner_unproven) == n
    assert len(l.migration_diagnostics['legacy_ownerless_plans']) == 256
    assert l.migration_diagnostics['legacy_ownerless_total'] == n
    assert len(l.migration_diagnostics['owner_candidates']) == 256
    assert l.migration_diagnostics['owner_candidates_dropped'] == 44
    assert row['stable_repeated_restore']
    for k in range(n):
        assert l.rebind_plan_owner('p' + str(k), 'i' + str(k), actor='op', reason='fixture', allow_non_candidate=True)
    row['after'] = state(l)
    assert len(l.migration_diagnostics['owner_rebinds']) == 256
    assert l.migration_diagnostics['owner_rebinds_total'] == n
    assert len(opened(l)) == n and not l._owner_unproven
    stable = l.snapshot()
    for _ in range(20):
        l = restore(l)
    assert l.snapshot() == stable

case('n10_fresh_caps_totals_full_quarantine', n10_fresh)

def n10_previous(row):
    n = 300
    old = Legacy()
    for k in range(n):
        old.reduce(P('p' + str(k), 'i' + str(k), 1))
        old.reduce(I('i' + str(k)))
    saved, _ = disk(old, 'n10-old-input-for-previous')
    prev = Previous()
    prev.restore_snapshot(saved)
    for k in range(n):
        prev.reduce(P('p' + str(k), 'i' + str(k), 1))
    candidate_saved, path = disk(prev, 'n10-ef18db3-candidates')
    l = Reducer()
    l.restore_snapshot(candidate_saved)
    first = state(l)
    for _ in range(20):
        l = restore(l)
    row['candidates'] = dict(path=path, first=first, repeated=state(l), stable=state(l) == first)
    for k in range(n):
        assert prev.rebind_plan_owner('p' + str(k), 'i' + str(k))
    audit_saved, path = disk(prev, 'n10-ef18db3-audit')
    l = Reducer()
    l.restore_snapshot(audit_saved)
    first = state(l)
    for _ in range(20):
        l = restore(l)
    row['audits'] = dict(path=path, first=first, repeated=state(l), stable=state(l) == first)
    row['sizes'] = dict(ownerless=len(row['candidates']['first']['diagnostics']['legacy_ownerless_plans']),
        candidates=len(row['candidates']['first']['diagnostics']['owner_candidates']),
        audit=len(l.migration_diagnostics['owner_rebinds']), quarantine=len(row['candidates']['first']['quarantine']))
    assert all(row['sizes'][k] <= 256 for k in ['ownerless', 'candidates', 'audit']), 'Authentic ef18db3 histories bypass all three global caps on restore'

case('n10_authentic_previous_upgrade_caps', n10_previous)

def n7_cumulative(row):
    old = Legacy()
    for e in [I(), R('old', p='', i='i')]:
        old.reduce(e)
    s, _ = disk(old, 'n7-initial-discard')
    l = Reducer()
    l.restore_snapshot(s)
    assert l.legacy_pending_discarded == 1
    for _ in range(20):
        l = restore(l)
    assert l.legacy_pending_discarded == 1
    later = l.snapshot()
    later['pending_receipts'] = {'p': {'new': R('new').payload}}
    l.restore_snapshot(later)
    row['state'] = state(l)
    assert l.legacy_pending_discarded == 2
    assert 'a PLAN re-establishes the owner' not in str(l.migration_diagnostics)

case('n7_cumulative_discard_and_warning', n7_cumulative)

def supersession(row):
    rows = []
    for late in [False, True]:
        for success_plan in ['p', 'q']:
            other = 'q' if success_plan == 'p' else 'p'
            stream = ([] if late else [I()]) + [P(), P('q'), R('fail', ok=False, p=other),
                      R('ok0', p=success_plan), R('ok1', 1, p=success_plan)] + ([I()] if late else [])
            l, h = Reducer(), HiveReducer()
            h.register_agent('a')
            for event in stream:
                l.reduce(event)
                h.reduce(HiveEvent(source_agent='a', original_event=event))
            rows.append(dict(late=late, complete_plan=success_plan, local=state(l),
                             hive_open=[i['incident_id'] for i in h._open_agent_incidents('a')]))
    row['cases'] = rows
    row['policy'] = 'Any fully verified immutable-owner plan can close; no latest-plan or designated superseding-plan check.'
    assert all(not r['local']['open'] and not r['hive_open'] for r in rows)

case('multi_plan_observed_policy', supersession)

(E / 'review7173.json').write_text(json.dumps(OUT, indent=2) + '\n')
summary = dict(total=len(OUT), passed=sum(r['passed'] for r in OUT.values()),
               failed=[k for k, r in OUT.items() if not r['passed']])
(E / 'review7173-summary.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(summary), flush=True)
sys.exit(bool(summary['failed']))
