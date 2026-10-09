from pathlib import Path
import subprocess,json,hashlib,platform,os,importlib.metadata as md
R=Path(__file__).resolve().parents[2];P=R/'experiments/20261008-astra-7741';E=Path(__file__).resolve().parent;S=Path('/tmp/hive-astra-7750-source');S.mkdir();Path('/tmp/hive-astra-7750-runtime').mkdir()
git=lambda *a:subprocess.check_output(['git',*a],cwd=R)
save=lambda n,o:(E/n).write_text(json.dumps(o,indent=2)+'\n')
pin=git('rev-parse','HEAD').decode().strip();assert pin=='6b750ca53a695d70ba4fd44dd2961389f1690df9'
files=[x for x in git('ls-tree','-r','--name-only',pin).decode().splitlines() if not x.startswith('experiments/')];hashes={}
for f in files:
 b=git('show',pin+':'+f);p=S/f;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b);hashes[f]=hashlib.sha256(b).hexdigest()
(S/'experiments').symlink_to(R/'experiments',target_is_directory=True)
(E/'source').mkdir()
for f in git('diff','--name-only','2c7e337',pin,'--',':!experiments').decode().splitlines():
 p=E/'source'/f;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(git('show',pin+':'+f))
(E/'source/target.patch').write_bytes(git('diff','2c7e337',pin,'--',':!experiments'))
save('source-verification-before.json',dict(pin=pin,source=str(S),files=len(files),hashes=hashes,origin_main=git('rev-parse','origin/main').decode().strip(),git_status=git('status','--short').decode(),patch_scope='2c7e337..pin excluding experiments; prior evidence verified separately'))
for p in list(P.glob('*.py'))+list((P/'guard').glob('*.py')):
 if p.name.startswith('setup'):continue
 rel=p.relative_to(P);q=E/rel;q.parent.mkdir(parents=True,exist_ok=True);new=p.read_text().replace('/tmp/hive-astra-7741','/tmp/hive-astra-7750')
 if p.name=='secret_scan.py':new=new.replace('ASTRA_REVIEW_7741','ASTRA_REVIEW_7750')
 if p.name=='verify_sources7734.py':new=new.replace("'7727','7734'","'7727','7734','7741'")
 if p.name=='finalize_provenance.py':new=new.replace('20261008-astra-7734','20261008-astra-7741').replace('adaptation-7741.diff','adaptation-7750.diff')
 if p.name=='metadata7734.py':new=new.replace('op=builtins.open','op=os.open').replace("patch.object(builtins,'open',opening)","patch.object(os,'open',opening)")
 if p.name=='focused7741.py':
  new=new.replace('op=builtins.open','op=os.open').replace("patch.object(builtins,'open',opening)","patch.object(os,'open',opening)")
  new=new.replace("applicable=not(operation=='clear' and target=='anchor')","applicable=True # clear now lstat-checks the anchor before replacement")
  new=new.replace("assert row['anchor_replaced'] and row['journal_created'] and h.journal_status()['healthy']","assert not row['anchor_replaced'] and not row['journal_created'] and h.journal_status()['fence']['kind']=='identity'")
  new=new.replace("assert f['completed_steps']==st['resets'][-1]['completed_steps']","assert f['completed_steps']==st['resets'][-1]['completed_steps']\n  assert f['presence_error']==st['resets'][-1]['presence_error']")
 q.write_text(new)
save('environment.json',dict(python=platform.python_version(),platform=platform.platform(),uid=os.getuid(),packages={k:md.version(k) for k in ['pytest','build']},pin=pin,source=str(S),cpu_count=os.cpu_count(),offline_wheels={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('/tmp/hive-astra-7718/20261008-astra-7718/build-prerequisites').glob('*.whl')}))
save('model-verification.json',dict(runtime_model='openai/gpt-6-astra',required_model='openai/gpt-6-astra',model_match=True,evidence_source=['OpenClaw sessions_list runtime metadata','OpenClaw sessions_history assistant provider/model/api metadata'],session_key='agent:main:subagent:34f672b3-afff-4f0c-8c81-77bb756083ff',session_id='fa54ff28-5c50-4367-9f0c-a3c675f00633',provider='openai',model='gpt-6-astra',api='openai-responses',note='Sole reviewer; no descendants or model substitution.'))
print(pin,len(files))
