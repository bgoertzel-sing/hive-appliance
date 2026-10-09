"""Read-only complete artifact/report manifest and semantic ledger verification."""
import hashlib,json
from pathlib import Path
E=Path(__file__).resolve().parent;report=(E.parent.parent/'docs/ASTRA_REVIEW_7741.md').resolve();seen=set()
for line in (E/'SHA256SUMS').read_text().splitlines():
 expected,name=line.split('  ',1);p=(E/name).resolve()
 assert p.is_relative_to(E) or p==report,name
 assert p not in seen,name
 assert hashlib.sha256(p.read_bytes()).hexdigest()==expected,name
 seen.add(p)
actual={p.resolve() for p in E.rglob('*') if p.is_file() and not p.is_symlink() and p.name!='SHA256SUMS'}|{report}
assert seen==actual,dict(unmanifested=list(actual-seen),missing=list(seen-actual))
load=lambda n:json.loads((E/n).read_text())
m=load('model-verification.json');assert m['runtime_model']=='openai/gpt-6-astra' and m['provider']=='openai' and m['model_match']
s=load('source-verification.json');assert s['pin']=='2c7e337202cbfa19569b344992326a1603d867cd' and s['files']==161 and s['all_match_pinned_git_blobs']
exits=list(E.glob('*-exit.json'));assert len(exits)==30,len(exits)
for p in exits:
 d=load(p.name);assert d['exit_code']==(1 if p.name=='semantic-7133-exit.json' else 0),p.name
 assert not d['timed_out'];stem=p.name.removesuffix('-exit.json')
 for suffix in ['-started.json','.stdout','.stderr']:assert (E/(stem+suffix)).is_file(),stem+suffix
assert len(list(E.glob('pytest-started.json')))==1
assert '840 passed in 50.37s' in (E/'pytest.stdout').read_text()
for name in ['reset7727.json','intent-final7727.json','extra-io7727.json','intent7734.json','review7694.json','followup7694.json','focused7701.json','focused7741.json']:
 assert all(r['passed'] for r in load(name).values()),name
r=load('reset7727.json')['interruptions'];assert r['injections']==208 and r['error_verify_clear_cases']==104 and r['live_replay_after_error']==0
r=load('intent-final7727.json');assert r['intent_controls']['count']==42 and r['intent_clearance_matrix']['count']==72
r=load('intent7734.json');assert r['intent_matrix']['count']==388 and r['compound_failures']['count']==4 and not r['classification_errors']['defect_reproduced']
assert not any(x['file_fsync_missing_but_durable'] for x in r['classification_errors']['cases'])
assert r['mode000']['not_deleted'] and r['mode000']['uid']!=0
r=load('metadata7734.json');assert len(r['presence_error_cases'])==2 and all(not x['false_old_pair_claim'] and not x['false_unlinked_claim'] for x in r['presence_error_cases'])
r=load('focused7741.json');assert r['classification']['count']==12 and r['races']['count']==7 and r['strict_checks']['count']==45 and r['metadata_boundaries']['count']==6
assert sum(x['applicable'] for x in r['strict_checks']['cases'])==42
assert all(not x['audit_has_presence_error'] for x in r['metadata_boundaries']['cases'])
assert r['dangling_anchor']['anchor_replaced'] and r['dangling_anchor']['journal_created'] and r['dangling_anchor']['state']['status']['healthy']
assert not load('audit7741-final.json')['unsafe_predicate_calls']
assert len(load('policy-schedules.json'))==1440 and load('review7694.json')['retained_hold_144_schedules']['schedules']==144
assert len(load('prior-evidence-verification.json'))==8 and all(r['all_match'] for r in load('prior-evidence-verification.json'))
assert load('secret-scan.json')['matches']==[] and load('secret-scan.json')['passed']
assert '## Verdict: NOT APPROVED' in report.read_text()
for row in load('copy-provenance.json'):
 assert hashlib.sha256((E/row['destination']).read_bytes()).hexdigest()==row['adapted_sha256'],row['destination']
 assert hashlib.sha256((E.parent.parent/row['source']).read_bytes()).hexdigest()==row['source_sha256'],row['source']
print('verified',len(seen),'artifact/report hashes; complete manifest coverage; 30 execution ledgers; suite, retained matrices, closed durability witnesses and reproduced residual findings')
