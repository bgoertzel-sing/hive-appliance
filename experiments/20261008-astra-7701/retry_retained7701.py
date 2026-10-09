"""Retry only groups blocked by old bool equality/diagnostic expectations; no suite rerun."""
import pathlib,difflib,json,traceback,os
E=pathlib.Path(__file__).resolve().parent;P=pathlib.Path(os.environ['HIVE_SRC'])/'experiments/20261008-astra-7694'
p=E/'review7582.py';s=(P/'review7582.py').read_text()
s=s.replace("def rebind(l,h,i='i',override=False):","def business(h):\n return {k:v for k,v in vars(h).items() if k not in ['last_rebind_result','_rebind_op_id']}\n\ndef rebind(l,h,i='i',override=False):")
s=s.replace("h.rebind_plan_owner('a1','p',i,actor='Astra-7582',reason='fixture authority',allow_non_candidate=override)]","bool(h.rebind_plan_owner('a1','p',i,actor='Astra-7582',reason='fixture authority',allow_non_candidate=override))]")
s=s.replace('vars(h)','business(h)').replace('for k,v in business(h).items()','for k,v in vars(h).items()')
p.write_text(s)
p=E/'review7656.py';s=p.read_text().replace("assert ok==(mode!='default')","assert bool(ok)==(mode!='default')").replace('return_value=ok','return_value=ok.as_dict()');p.write_text(s)
diff=[]
for name in ['review7694.py','followup7694.py','review7582.py','review7656.py']:
 diff.extend(difflib.unified_diff((P/name).read_text().splitlines(True),(E/name).read_text().splitlines(True),fromfile='7694/'+name,tofile='7701/'+name))
(E/'adaptation-7701.diff').write_text(''.join(diff))
ns={'__file__':str(E/'review7694.py'),'__name__':'defs'};src=(E/'review7694.py').read_text();exec(compile(src[:src.index('\nout={}\n')],str(E/'review7694.py'),'exec'),ns)
g=ns['q']['g'];out={}
for name,fn in [('retained_foreign',g['foreign']),('retained_incidentless',g['incidentless']),('retained_hold',g['hold']),('retained_plan_only_witness',g['a']['witness']),('retained_hold_144_schedules',g['a']['schedules']),('retained_refusals_pending',g['a']['refusals_and_pending'])]:
 r={}
 try:fn(r);r['passed']=True
 except Exception as ex:r.update(passed=False,error=repr(ex),traceback=traceback.format_exc())
 out[name]=r;print(name,r['passed'])
ns={'__file__':str(E/'followup7694.py'),'__name__':'defs'};src=(E/'followup7694.py').read_text();exec(compile(src[:src.index('\nout={}\n')],str(E/'followup7694.py'),'exec'),ns)
ns['T']=E/'legacy-retry7701';ns['T'].mkdir()
r={}
try:ns['legacy_default'](r);r['passed']=True
except Exception as ex:r.update(passed=False,error=repr(ex),traceback=traceback.format_exc())
out['legacy_default']=r
(E/'retained-retry7701.json').write_text(json.dumps(out,indent=2,default=str)+'\n')
assert all(x['passed'] for x in out.values()),[(k,x.get('error')) for k,x in out.items() if not x['passed']]
