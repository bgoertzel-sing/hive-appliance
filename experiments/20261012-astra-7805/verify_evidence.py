"""Read-only complete manifest/source/outcome verification; no fixture replay."""
import hashlib,json,os,subprocess
from pathlib import Path
E=Path(__file__).resolve().parent;R=E.parents[1];report=R/'docs/ASTRA_REVIEW_7805.md'
PIN='a875414ec0281db0a5d5a66b0d12412733f4cbd7'
def digest(p):return hashlib.sha256(os.fsencode(os.readlink(p)) if p.is_symlink() else p.read_bytes()).hexdigest()
def load(n):return json.loads((E/n).read_text())
def git(*a):return subprocess.check_output(['git',*a],cwd=R)
seen=set()
for line in (E/'SHA256SUMS').read_text().splitlines():
 expected,name=line.split('  ',1);p=Path(os.path.abspath(E/name))
 assert p.is_relative_to(E) or p==report,name
 assert p not in seen and digest(p)==expected,name
 seen.add(p)
actual={p.absolute() for p in E.rglob('*') if (p.is_symlink() or p.is_file()) and p.name!='SHA256SUMS'}|{report}
assert seen==actual,dict(unmanifested=[str(x) for x in actual-seen],missing=[str(x) for x in seen-actual])
m=load('model-verification.json');assert m['matched'] and m['requested_model']=='openai/gpt-6-astra' and m['routing_model']=='gpt-6-astra' and m['routing_provider']=='openai' and m['routing_api']=='openai-responses'
assert m['self_reported_identity']=='You are Codex, an agent based on GPT-6.'
s=load('source.json');assert s['pin']==PIN and len(s['hashes'])==165
assert git('rev-parse',PIN).decode().strip()==PIN
subprocess.run(['git','merge-base','--is-ancestor',PIN,'HEAD'],cwd=R,check=True)
for name,h in s['hashes'].items():
 assert hashlib.sha256(git('show',PIN+':'+name)).hexdigest()==h,name
 assert digest(R/name)==h,('working-source-differs',name)
changes=git('diff','--name-only',PIN,'--',':!experiments').decode().splitlines()
assert all(x=='docs/ASTRA_REVIEW_7805.md' for x in changes),changes
for row in load('copy-provenance.json'):
 assert digest(R/row['source'])==row['original_sha256']
 assert digest(E/row['destination'])==row['adapted_sha256']
exits=list(E.glob('*-exit.json'));assert len(exits)==26,len(exits)
for p in exits:
 d=load(p.name);stem=p.name.removesuffix('-exit.json')
 assert d['exit_code']==(1 if stem in ['independent7805','policy7638'] else 0),(stem,d)
 assert not d['timed_out'],stem
 assert load(stem+'-started.json')['command']==d['command']
 for suf in ['.stdout','.stderr']:assert (E/(stem+suf)).is_file()
assert '867 passed in 35.04s' in (E/'pytest.stdout').read_text()
assert len(list(E.glob('pytest*-exit.json')))==1
assert all(v is None for v in load('environment.json')['thread_environment'].values())
rows=load('independent7805-qualified.json');assert len(rows)==16 and all(x['exit_code']==0 and not x['timed_out'] for x in rows)
q=json.loads(next(x for x in rows if x['case']=='append-fifo')['stdout']);assert q['real_append_open'] and q['changed'] and q['restart_held']
assert 'changed while it was being confirmed' in next(x for x in rows if x['case']=='intent-race-marker')['stderr']
for n in ['review7694.json','followup7694.json','focused7701.json','focused7741.json','retained7750.json','reset7727.json','intent-final7727.json','extra-io7727.json','intent7734.json','recovery-final7750.json']:
 assert all(x['passed'] for x in load(n).values()),n
assert load('metadata7734.json')['passed'] and load('exact-restore-final7718.json')['passed']
r=load('reset7727.json')['interruptions'];assert r['injections']==208 and r['error_verify_clear_cases']==104 and r['live_replay_after_error']==0
r=load('intent-final7727.json');assert r['intent_controls']['count']==42 and r['intent_clearance_matrix']['count']==72 and r['reset_retries_and_live_errors']['count']==96
assert load('extra-io7727.json')['extra_boundaries']['additional_injections']==52
r=load('intent7734.json');assert r['intent_matrix']['count']==412 and r['compound_failures']['count']==4
r=load('retained7750.json');assert r['nonregular_variants']['count']==32 and r['reader_errors']['count']==40 and r['reader_swaps']['count']==8 and r['runtime']['count']==16 and r['archive_trace']['archive_read_count']==0
assert not r['runtime']['directory_append_defect_reproduced']
assert len(load('policy-schedules.json'))==1440 and load('schedules7805.json')['per_event_checks']==15840
assert load('review7694.json')['retained_hold_144_schedules']['schedules']==144
assert load('audit7805.json')['source_export_and_worktree_match_git'] and load('audit7805.json')['helper_order_verified']
f=load('special-fixtures.json');assert len(f['serialized_special_entries'])==12 and len(f['retained_symlinks'])==37
assert {x['path']:x['target'] for x in f['retained_symlinks']}=={str(p.relative_to(E)):os.readlink(p) for p in E.rglob('*') if p.is_symlink()}
assert load('secret-scan.json')['passed'] and load('secret-scan.json')['matches']==[]
assert '## Verdict: APPROVED WITH CONDITIONS' in report.read_text()
print(f'PASS: {len(seen)} artifact/report hashes; complete manifest; source {PIN} matches 165 repository files; 26 execution ledgers; 867 tests; 16 independent timeout cases; 1440/144 schedules; reset/intent matrices; both 7750 findings CLOSED; zero secret-scan matches.')
