"""Read-only full evidence/report manifest and semantic ledger verification."""
import hashlib,json
from pathlib import Path
E=Path(__file__).resolve().parent
report=(E.parent.parent/'docs/ASTRA_REVIEW_7727.md').resolve()
seen=set()
for line in (E/'SHA256SUMS').read_text().splitlines():
 expected,name=line.split('  ',1);p=(E/name).resolve()
 assert p.is_relative_to(E) or p==report,name
 assert p not in seen,name
 assert hashlib.sha256(p.read_bytes()).hexdigest()==expected,name
 seen.add(p)
actual={p.resolve() for p in E.rglob('*') if p.is_file() and p.name!='SHA256SUMS'}|{report}
assert seen==actual,dict(unmanifested=list(actual-seen),missing=list(seen-actual))
load=lambda n:json.loads((E/n).read_text())
assert load('model-verification.json')['runtime_model']=='openai/gpt-6-astra'
assert load('source-verification.json')['pin']=='7ce5cd5c2c3289ee1ce9f50c2683854e038df0d0'
assert load('source-verification.json')['files']==157
expected_nonzero={'semantic-7133-exit.json','intent7727-exit.json'}
exits=list(E.glob('*-exit.json'));assert len(exits)==24
for p in exits:
 d=load(p.name);assert d['exit_code']==(1 if p.name in expected_nonzero else 0),p.name
 assert not d['timed_out'];stem=p.name.removesuffix('-exit.json')
 for suffix in ['-started.json','.stdout','.stderr']:assert (E/(stem+suffix)).is_file(),stem+suffix
assert '817 passed in 51.57s' in (E/'pytest.stdout').read_text()
for name in ['reset7727.json','intent-final7727.json','extra-io7727.json']:
 assert all(r['passed'] for r in load(name).values()),name
r=load('reset7727.json')['interruptions'];assert r['injections']==208 and r['error_verify_clear_cases']==104 and r['live_replay_after_error']==0
assert len(load('policy-schedules.json'))==1440
assert load('review7694.json')['retained_hold_144_schedules']['schedules']==144
assert '## Verdict: NOT APPROVED' in report.read_text()
print('verified',len(seen),'artifact/report hashes; complete manifest coverage; 24 execution ledgers; suite and review invariants')
