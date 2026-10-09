"""Read-only source, caller, documentation and historical evidence checks."""
import hashlib,json,os,subprocess
from pathlib import Path
E=Path(__file__).resolve().parent;S=Path(os.environ['HIVE_SRC'])
def git(*a):return subprocess.check_output(['git',*a],cwd=S,text=True)
commands=[['git','grep','-n','-E','HiveAppliance\\(|rebind_journal|HIVE_REBIND_JOURNAL|volatile_rebinds','HEAD','--',':!experiments',':!docs/ASTRA*'],['git','grep','-n','-i','-E','journal|rebind|snapshot|restore','HEAD','--','README.md','docs/POLICY_MULTI_PLAN_SUPERSESSION.md','hive/event_bus.py','hive/shared_store.py']]
results=[]
for argv in commands:
 p=subprocess.run(argv,cwd=S,text=True,capture_output=True);results.append(dict(argv=argv,exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr))
(E/'production-wiring-search.json').write_text(json.dumps(results,indent=2)+'\n')
before=json.loads((E/'source-verification-before.json').read_text());after={p:hashlib.sha256((S/p).read_bytes()).hexdigest() for p in before}
assert before==after and git('status','--porcelain')==''
r=dict(pin=git('rev-parse','HEAD').strip(),tracked_non_experiment_files=len(after),byte_identical_to_before=True,tracked_status=git('status','--short'),hashes=after)
(E/'source-verification.json').write_text(json.dumps(r,indent=2)+'\n')
p=subprocess.run(['python3','experiments/20261008-astra-7638/verify_evidence.py'],cwd=S,text=True,capture_output=True);assert p.returncode==0
(E/'prior-evidence-verification.json').write_text(json.dumps(dict(argv=p.args,exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr),indent=2)+'\n')
# Structured findings from full read, not inferred from search alone.
notes=dict(changed_files=git('diff','--name-only','ff692b9..647fac6').splitlines(),complete_changed_files_read=True,full_diff_read=True,docs=dict(appliance_usage='Updated journal argument/env/explicit volatile opt-out',README='No rebind-journal configuration or upgrade guidance',policy='Still describes hive owner_candidates/owner_rebinds as in-memory; no v1 migration/full-stream replay, journal defaults/caps/fence procedure',legacy='Only code log/test explains v1 rejection and reissue; no operator migration/runbook',callers='Other HiveAppliance instantiations are tests; no production instantiation site outside class usage. Existing tests exercise ordinary operations, not old implicit volatile rebind.',event_identity='schemas/types.py Event docstring calls events immutable; mutable dataclass/from_dict does not verify content hash',snapshot='No HiveReducer.snapshot/restore_snapshot. Local Reducer snapshots do not contain hive global accepted-event position/hash. Event bus log bounded/in-memory; this patch provides no durable globally ordered event archive.'),scope='No product/docs fixes: review/evidence only')
(E/'static-review.json').write_text(json.dumps(notes,indent=2)+'\n');print(json.dumps(dict(source_files=len(after),source_clean=True,prior_evidence=p.stdout.strip(),notes=notes),indent=2))
