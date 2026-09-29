"""Audit recorded outcomes independently of observation-harness process status."""
import json
from pathlib import Path

E = Path(__file__).resolve().parent
def read(name):
    return json.loads((E / name).read_text())

new = read('new-cases.json')
supp = read('supplementary.json')
life = read('ownership-lifecycle.json')
agreement = []
for name, cases in [('original402', list(new.values()) + list(supp.values()))]:
    states = [r for c in cases for r in c['events']]
    errors = [r for r in states if r['local_open'] != r['hive_open'] or
              r['local_verified'] != r['hive_verified'] or r['local_failed'] != r['hive_failed'] or
              r['hive_health'] != ('failed' if r['hive_open'] else 'healthy')]
    agreement.append(dict(group=name, schedules=len(cases), event_states=len(states), mismatches=len(errors)))
states = [r for c in life for r in c['trace']]
errors = [r for r in states if any(r['local'][k] != r['hive'][k] for k in ['open', 'verified', 'failed'])
          or r['hive']['displayed_open'] != len(r['hive']['open'])
          or r['hive']['health'] != ('failed' if r['hive']['open'] else 'healthy' if r['hive']['links'] else 'unknown')]
agreement.append(dict(group='lifecycle', schedules=len(life), event_states=len(states), mismatches=len(errors)))
mech = read('mechanism-probes.json')
stale = read('legacy-stale-progress.json')
boundary = read('boundary-and-disk.json')
result = dict(
    agreement=agreement,
    semantic=read('semantic-summary.json'),
    raw_7024_failures=[n for n, c in {**new, **supp}.items() if not c['passed']],
    stale_safety_passes=sum(c['after_plan']['open'] == ['i'] and c['after_fresh1']['open'] == ['i'] for c in stale),
    stale_old_automatic_recovery_passes=sum(c['passed'] for c in stale),
    explicit_disk_recovery_passes=sum(c['passed'] for c in mech['disk_recovery']),
    n8_passes=sum(c['passed'] for c in boundary['n8']),
    n8_agreement=sum(c['agreement_every_event'] for c in boundary['n8']),
    rejected_state_changes=mech['rejected_full_state']['changed'],
    new=read('review7173-summary.json'),
    exits={p.name.removesuffix('-exit.json'): read(p.name)['exit_code'] for p in sorted(E.glob('*-exit.json'))},
    record_note='Owner-map references in unchanged semantic harness intermediate traces can alias later state; final oracles remain valid. New review7173 traces deep-copy maps.'
)
assert all(r['mismatches'] == 0 for r in agreement)
assert result['stale_safety_passes'] == 3 and result['explicit_disk_recovery_passes'] == 6
assert result['n8_passes'] == result['n8_agreement'] == 14
(E / 'results-audit.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
