"""Independent per-receipt expectations, not final-state or agreement oracles."""
import copy
import importlib.util
import itertools
import json
import logging
import os
from pathlib import Path
import sys
import traceback
from unittest.mock import patch

E = Path(__file__).resolve().parent
sys.path.insert(0, os.environ['HIVE_SRC'])
from controller.reducer import Reducer, EFFECT_KINDS
from recovery.checkpoint import CheckpointManager
from schemas.types import Event, EventKind

def load(c):
    spec = importlib.util.spec_from_file_location('old_' + c, E / ('legacy-reducer-' + c + '.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.Reducer

Legacy, Previous = load('e6afe16'), load('ef18db3')
def I(i='i', p=''):
    return Event(kind=EventKind.INCIDENT, payload=dict(id=i, component='svc', symptom='down', severity='critical', plan_id=p))
def P(p='p', i='i', n=2):
    return Event(kind=EventKind.PLAN, payload=dict(id=p, incident_id=i, steps=[{} for _ in range(n)]))
def R(r, k=0, ok=True, p='p', i=''):
    return Event(kind=EventKind.RECEIPT, payload=dict(id=r, step_index=k, verified=ok, plan_id=p, incident_id=i))
def rt(r):
    new = Reducer()
    new.restore_snapshot(json.loads(json.dumps(r.snapshot())))
    return new
def disk(r, name):
    m = CheckpointManager(E / 'focused-checkpoints' / name)
    c = m.create(r.snapshot(), label=name)
    return m.load(c.id).appliance_state
def lost(n=2, ambiguous=False):
    old = Legacy()
    for ev in [P(n=n), I(p='p' if ambiguous else ''), I('other', 'p' if ambiguous else '')]:
        old.reduce(ev)
    r = Reducer()
    r.restore_snapshot(json.loads(json.dumps(old.snapshot())))
    assert r._owner_unproven == {'p'}
    return r
def ids(pv):
    return {k: [r['id'] for r in pv['effects'][k]] for k in EFFECT_KINDS}
def expected_empty():
    return {k: [] for k in EFFECT_KINDS}

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

def check(r, expected, row):
    before = copy.deepcopy(vars(r))
    with patch('controller.reducer.logger.warning') as warning, patch('controller.reducer.logger.info') as info:
        pv = r.preview_rebind('p', 'i', allow_non_candidate=True)
    row.update(expected=expected, actual=ids(pv), preview=pv, pure=vars(r) == before,
               warning_calls=warning.call_count, info_calls=info.call_count)
    assert vars(r) == before and warning.call_count == info.call_count == 0
    assert ids(pv) == expected
    assert r.rebind_plan_owner('p', 'i', actor='review7195', reason='explicit fixture authority', allow_non_candidate=True)
    audit = copy.deepcopy(r.migration_diagnostics['owner_rebinds'][-1])
    row['audit'] = audit
    assert audit['pending_before'] == sum(map(len, expected.values()))
    assert audit['effect_counts'] == {k: len(v) for k, v in expected.items()}
    assert audit['effect_ids'] == {k: v[:32] for k, v in expected.items()}
    assert set(r._pending_receipts) == set(expected['still_held'])
    assert pv['would_close'] == audit['closed']
    stable = r.snapshot()
    for _ in range(20):
        r = rt(r)
    assert r.snapshot() == stable
    return r

def per_receipt(row):
    rows = []
    # Independent specification: accepted fresh evidence changes the latest
    # truth of its own step; repeating the same truth has no progress effect.
    for truth in itertools.product([False, True], repeat=4):
        for indices in [(0, 1, 0, 1), (0, 0, 0, 0)]:
            for restore in [False, True]:
                r = lost()
                expected, latest = expected_empty(), {}
                for k, (idx, ok) in enumerate(zip(indices, truth)):
                    rid = 'r' + str(k)
                    outcome = 'consumed_no_effect' if latest.get(idx) is ok else 'credited' if ok else 'failure_recorded'
                    expected[outcome].append(rid)
                    latest[idx] = ok
                    r.reduce(R(rid, idx, ok))
                if restore:
                    r = rt(rt(r))
                result = dict(truth=truth, indices=indices, restored=restore)
                r = check(r, expected, result)
                assert r._plan_verified['p'] == {i for i, v in latest.items() if v}
                assert r._plan_failed_steps['p'] == {i for i, v in latest.items() if not v}
                assert bool(r.open_incidents()[0].id == 'i') if len(r.open_incidents()) == 2 else latest == {0: True, 1: True}
                rows.append(result)
    row['cases'] = rows
    row['total'] = len(rows)

case('n9_per_receipt_overwritten_and_unchanged', per_receipt)

def mixed(row):
    r = lost(ambiguous=True)
    stream = [R('s0'), R('f0', ok=False), R('same_failure', ok=False), R('retry0'), R('same_success'),
              R('wrong_owner', 1, i='other'), R('other_link', 0, False, '', 'other'),
              R('negative', -1), R('too_large', 2), R('bool_index', True),
              R('float_index', 0.0), R('str_index', '0'), R('none_index', None),
              R('nested_index', {'bad': [0]}), R('unproven_other_plan', 0, True, 'q'),
              R('unknown_incident', 0, False, '', 'absent'),
              R('s0', 1, False)]
    for ev in stream:
        r.reduce(ev)
    expected = expected_empty()
    expected.update(credited=['s0', 'retry0'], failure_recorded=['f0'],
        consumed_no_effect=['same_failure', 'same_success', 'wrong_owner', 'other_link',
            'negative', 'too_large', 'bool_index', 'float_index', 'str_index', 'none_index', 'nested_index'],
        still_held=['unproven_other_plan', 'unknown_incident'])
    r = check(r, expected, row)
    assert r._plan_verified['p'] == {0} and not r._plan_failed_steps['p']
    assert sorted(i.id for i in r.open_incidents()) == ['i', 'other']
    after = copy.deepcopy(vars(r))
    for ev in stream:
        r.reduce(ev)
    assert vars(r) == after
    row['duplicate_payload_first_wins_and_replay_no_effect'] = True

case('n9_invalid_identity_indices_duplicates_and_held', mixed)

def unrelated(row):
    r = lost()
    # z is unknown, so this is held. Rebinding p creates i->p, making z/i
    # contradictory even though the receipt does not directly name p.
    r.reduce(R('unrelated_z', p='z', i='i'))
    r.reduce(R('still_q', p='q'))
    expected = expected_empty()
    expected['consumed_no_effect'] = ['unrelated_z']
    expected['still_held'] = ['still_q']
    r = check(r, expected, row)
    assert not r._plan_verified['p'] and 'unrelated_z' in r._seen_receipt_ids

case('n9_unrelated_drained_receipt', unrelated)

def caps(row):
    r = lost(n=80)
    expected = expected_empty()
    for k in range(40):
        for kind, ev in [('credited', R('s' + str(k), k)),
                         ('failure_recorded', R('f' + str(k), 40 + k, False)),
                         ('consumed_no_effect', R('bad' + str(k), 99)),
                         ('still_held', R('held' + str(k), p='q'))]:
            expected[kind].append(ev.payload['id'])
            r.reduce(ev)
    r = check(r, expected, row)
    assert r._plan_verified['p'] == set(range(40))
    assert r._plan_failed_steps['p'] == set(range(40, 80))
    assert row['audit']['pending_before'] == 160
    assert all(len(v) == 32 for v in row['audit']['effect_ids'].values())

case('n9_each_effect_id_cap32_with_exact_totals', caps)

def purity(row):
    r = lost()
    r.reduce(R('bad', {'x': [1, {'y': []}]}, {'v': [False]}))
    r.reduce(R('valid_index_bad_truth', 1, {'truth': [True]}))
    r.reduce(R('held_nested', {'x': []}, {'v': []}, 'q'))
    r.reduce(P())
    before = copy.deepcopy(vars(r))
    calls = []
    class Capture(logging.Handler):
        def emit(self, record):
            calls.append(record.getMessage())
    handler = Capture()
    root = logging.getLogger()
    root.addHandler(handler)
    try:
        pv = r.preview_rebind('p', 'i')
        denied = r.preview_rebind('p', 'other')
    finally:
        root.removeHandler(handler)
    row.update(preview=copy.deepcopy(pv), denied=denied, logs=calls)
    assert not calls and vars(r) == before and not denied['allowed']
    def mutate(value):
        if isinstance(value, list):
            for item in list(value):
                mutate(item)
            value.append('changed')
        elif isinstance(value, dict):
            for item in list(value.values()):
                mutate(item)
            value['changed'] = True
    mutate(pv)
    mutate(denied)
    assert vars(r) == before
    row['detached_after_recursive_output_mutation'] = True
    assert row['preview']['effect_counts'] == dict(credited=0, failure_recorded=1, consumed_no_effect=1, still_held=1)

case('n9_nested_fields_detached_and_preview_no_logging', purity)

def n10_authentic(row):
    old = Legacy()
    for k in range(300):
        old.reduce(P('p' + str(k), 'i' + str(k), 1))
        old.reduce(I('i' + str(k)))
    s = disk(old, 'authentic-e6afe16')
    prev = Previous()
    prev.restore_snapshot(s)
    for k in range(300):
        prev.reduce(P('p' + str(k), 'i' + str(k), 1))
    candidate = disk(prev, 'authentic-ef18db3-candidates')
    r = Reducer()
    r.restore_snapshot(candidate)
    d = r.migration_diagnostics
    assert len(d['legacy_ownerless_plans']) == len(d['owner_candidates']) == 256
    assert d['legacy_ownerless_total'] == 300 and d['owner_candidates_dropped'] == 44
    assert len(r._owner_unproven) == 300
    stable = r.snapshot()
    for _ in range(20):
        r = rt(r)
    assert r.snapshot() == stable
    dropped = sorted(set(r._owner_unproven) - set(d['owner_candidates']))
    target = dropped[0]
    before = copy.deepcopy(vars(r))
    assert not r.preview_rebind(target, 'i' + target[1:])['allowed']
    assert not r.rebind_plan_owner(target, 'i' + target[1:], actor='op', reason='candidate was pruned')
    assert vars(r) == before
    row['candidates'] = dict(total=300, kept=256, dropped=dropped, quarantine=300,
                             idempotent=True, pruned_candidate_default_refused=True)
    for k in range(300):
        assert prev.rebind_plan_owner('p' + str(k), 'i' + str(k))
    audit = disk(prev, 'authentic-ef18db3-audit')
    r = Reducer()
    r.restore_snapshot(audit)
    d = r.migration_diagnostics
    assert len(d['owner_rebinds']) == 256 and d['owner_rebinds_total'] == 300
    assert d['owner_rebinds'][0]['plan_id'] == 'p44' and d['owner_rebinds'][-1]['plan_id'] == 'p299'
    assert d['legacy_ownerless_total'] == 300 and len(d['legacy_ownerless_plans']) == 256
    assert not r._owner_unproven and len(r.open_incidents()) == 300
    stable = r.snapshot()
    for _ in range(20):
        r = rt(r)
    assert r.snapshot() == stable
    row['audit'] = dict(kept=256, total=300, first='p44', last='p299', idempotent=True)

case('n10_authentic_pretrim_totals_and_candidate_safety', n10_authentic)

def n10_priority(row):
    r = lost()
    snap = r.snapshot()
    snap['migration_diagnostics']['owner_candidates'] = {
        **{'a' + str(k): ['other'] * 12 for k in range(300)},
        'p': ['i', 'other'] + ['candidate' + str(k) for k in range(10)]}
    r.restore_snapshot(snap)
    d = r.migration_diagnostics
    assert len(d['owner_candidates']) == 256 and 'p' in d['owner_candidates']
    assert d['owner_candidates_dropped'] == 45
    assert all(len(v) <= 8 for v in d['owner_candidates'].values())
    assert r._owner_unproven == {'p'} and not r._plan_owner
    assert r.preview_rebind('p', 'i')['allowed']
    assert not r.preview_rebind('p', 'absent')['allowed']
    stable = r.snapshot()
    for _ in range(20):
        r = rt(r)
    assert r.snapshot() == stable
    assert r.rebind_plan_owner('p', 'i', actor='op', reason='trusted recorded candidate')
    assert r.migration_diagnostics['owner_rebinds_total'] == 1
    assert len(r.open_incidents()) == 2
    row.update(candidate_keys=256, dropped=45, max_values=8, held_plan_retained=True,
               no_automatic_authority=True, idempotent=True)

case('n10_quarantine_first_candidate_values_and_no_auto_authority', n10_priority)

with (E / 'review7195.json').open('x') as f:
    json.dump(OUT, f, indent=2)
summary = dict(groups=len(OUT), passed=sum(v['passed'] for v in OUT.values()),
               failed=[k for k, v in OUT.items() if not v['passed']])
with (E / 'review7195-summary.json').open('x') as f:
    json.dump(summary, f, indent=2)
print(json.dumps(summary))
sys.exit(bool(summary['failed']))
