"""Read-only complete manifest, symlink inventory, semantic and execution verification."""
import hashlib,json,os
from pathlib import Path
E=Path(__file__).resolve().parent;R=E.parent.parent;report=R/'docs/ASTRA_REVIEW_7750.md';seen=set()
def digest(p):
 return hashlib.sha256(os.fsencode(os.readlink(p)) if p.is_symlink() else p.read_bytes()).hexdigest()
for line in (E/'SHA256SUMS').read_text().splitlines():
 expected,name=line.split('  ',1);p=Path(os.path.abspath(E/name))
 assert p.is_relative_to(E) or p==report,name
 assert p not in seen,name
 assert digest(p)==expected,name
 seen.add(p)
actual={p.absolute() for p in E.rglob('*') if (p.is_symlink() or p.is_file()) and p.name!='SHA256SUMS'}|{report}
assert seen==actual,dict(unmanifested=[str(x) for x in actual-seen],missing=[str(x) for x in seen-actual])
load=lambda n:json.loads((E/n).read_text())
m=load('model-verification.json');assert m['runtime_model']=='openai/gpt-6-astra' and m['provider']=='openai' and m['model_match']
s=load('source-verification.json');assert s['pin']=='6b750ca53a695d70ba4fd44dd2961389f1690df9' and s['files']==163 and s['all_match_pinned_git_blobs']
s=load('source-verification-precommit.json');assert s['pin']==s['head']==s['origin_main'] and not s['extra_code'] and s['repository_source_unchanged']
exits=list(E.glob('*-exit.json'));assert len(exits)==36,len(exits)
nonzero={'semantic-7133','recovery7708','namespace-scope7750'}
for p in exits:
 d=load(p.name);stem=p.name.removesuffix('-exit.json');assert d['exit_code']==(1 if stem in nonzero else 0),(stem,d['exit_code'])
 assert not d['timed_out']
 for suffix in ['-started.json','.stdout','.stderr']:assert (E/(stem+suffix)).is_file(),stem+suffix
 assert load(stem+'-started.json')['command']==d['command']
assert len(list(E.glob('pytest-started.json')))==1 and '855 passed in 49.93s' in (E/'pytest.stdout').read_text()
for name in ['reset7727.json','intent-final7727.json','extra-io7727.json','intent7734.json','review7694.json','followup7694.json','focused7701.json','focused7741.json','focused7750.json','recovery-final7750.json']:
 assert all(r['passed'] for r in load(name).values()),name
r=load('reset7727.json')['interruptions'];assert r['injections']==208 and r['error_verify_clear_cases']==104 and r['live_replay_after_error']==0
r=load('intent-final7727.json');assert r['intent_controls']['count']==42 and r['intent_clearance_matrix']['count']==72 and r['reset_retries_and_live_errors']['count']==96
r=load('extra-io7727.json');assert r['extra_boundaries']['additional_injections']==52 and len(r['anchor_reads']['cases'])==4
r=load('intent7734.json');assert r['intent_matrix']['count']==412 and r['compound_failures']['count']==4 and not r['classification_errors']['defect_reproduced']
assert r['mode000']['not_deleted'] and r['mode000']['uid']!=0
r=load('focused7741.json');assert r['classification']['count']==12 and r['races']['count']==7 and r['strict_checks']['count']==45 and all(x['applicable'] for x in r['strict_checks']['cases'])
assert r['metadata_boundaries']['count']==6 and all(x['audit_has_presence_error'] for x in r['metadata_boundaries']['cases'])
assert not r['dangling_anchor']['anchor_replaced'] and not r['dangling_anchor']['journal_created'] and r['dangling_anchor']['state']['status']['fence']['kind']=='identity'
r=load('focused7750.json');assert r['nonregular_variants']['count']==32 and r['reader_errors']['count']==40 and r['reader_swaps']['count']==8 and r['runtime']['count']==15
assert r['runtime']['directory_append_defect_reproduced'] and sum(x['missing_changed_fence'] for x in r['runtime']['cases'])==1
assert r['fifo_blocking']['count']==3 and all(x['blocked_without_fifo_writer'] and x['returned_after_writer_open'] for x in r['fifo_blocking']['cases'])
assert r['directory_symlinks']['count']==5 and r['archive_trace']['archive_read_count']==0
r=load('namespace-scope7750-final.json');assert r['passed'] and r['count']==3
r=load('audit7750-final.json');assert not r['builtin_open_calls'] and not r['unsafe_predicate_calls'] and '_replay_journal' in r['reachable_methods']
assert r['test_adaptation']['same_function_AST_after_builtin_to_os_normalization']
assert len(load('policy-schedules.json'))==1440 and load('review7694.json')['retained_hold_144_schedules']['schedules']==144
p=load('prior-evidence-verification.json');assert len(p)==9 and all(x['all_match'] for x in p) and p[-1]['round']=='7741' and p[-1]['artifacts']==6131
assert load('secret-scan.json')['matches']==[] and load('secret-scan.json')['passed']
assert '## Verdict: NOT APPROVED' in report.read_text()
for row in load('copy-provenance.json'):
 assert digest(E/row['destination'])==row['adapted_sha256'],row['destination']
 assert digest(R/row['source'])==row['source_sha256'],row['source']
f=load('special-fixtures.json');assert len(f['serialized_special_entries'])==14 and len(f['retained_symlinks'])==39
assert {x['path']:x['target'] for x in f['retained_symlinks']}=={str(p.relative_to(E)):os.readlink(p) for p in E.rglob('*') if p.is_symlink()}
print('verified',len(seen),'artifact/report hashes including symlink payloads; complete coverage; 36 execution ledgers; 855 tests; retained schedules/reset matrices; both 7741 closures; two reproduced OPEN runtime findings')
