"""Finish metadata and generate scoped publication/verification helpers."""
import pathlib,json,shutil,shlex
E=pathlib.Path(__file__).resolve().parent
R=pathlib.Path('/home/openclaw/research-agent/projects/hive-appliance/repos/hive-appliance');P=R/'experiments/20261008-astra-7694'
shutil.copy2('/tmp/setup7701.py',E/'setup7701.py')
m=json.loads((E/'model-verification.json').read_text())
m['final_check']=dict(session_key=m['own_session_key'],model='gpt-6-astra',provider='openai',api='openai-responses',sessions_list_verified=True,sessions_history_verified=True,history_message_ids=['005c0eda-85a0-4d6d-af6f-8ad619411a2f'],no_fallback=True,no_delegation=True)
(E/'model-verification.json').write_text(json.dumps(m,indent=2)+'\n')
for name in ['verify_evidence.py','scan_staged.py']:
 (E/name).write_text((P/name).read_text().replace('7694','7701'))
records=sorted((json.loads(p.read_text()) for p in E.glob('*-started.json')),key=lambda x:x['started'])
lines=['#!/bin/sh','set -eu','export HIVE_SRC=/tmp/hive-astra-7701-source','export PYTHONDONTWRITEBYTECODE=1','export PIP_NO_INDEX=1','export PIP_FIND_LINKS=/tmp/hive-astra-7701/20261008-astra-7701/build-prerequisites','export PYTHONPATH=/tmp/hive-astra-7701/20261008-astra-7701/guard','export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1','# Exact underlying argv/cwds, originally executed through runner with exclusive logs.','# Reproduction uses a NEW disposable directory; never run against published evidence.']
for r in records:lines+=['cd '+shlex.quote(r['cwd']),shlex.join(r['command'])]
(E/'commands.sh').write_text('\n'.join(lines)+'\n')
print('publication metadata prepared')
