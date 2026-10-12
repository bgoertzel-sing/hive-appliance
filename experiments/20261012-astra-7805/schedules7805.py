import json
from runner import E
ns={'__file__':str(E/'review7519.py'),'__name__':'defs'}
s=(E/'review7519.py').read_text();exec(compile(s[:s.index('\nout={}')],str(E/'review7519.py'),'exec'),ns)
r={};ns['schedules'](r);assert r['schedules']==1440 and r['per_event_checks']==15840
(E/'schedules7805.json').write_text(json.dumps(r,indent=2)+'\n');print(r)
