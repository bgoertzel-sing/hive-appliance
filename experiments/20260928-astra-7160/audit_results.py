import json
from pathlib import Path
E=Path(__file__).resolve().parent
out={}
def audit(rows,eventkey,localkey=None):
 total=0;fail=[];health=[]
 for name,r in rows:
  for j,t in enumerate(r[eventkey]):
   total+=1
   if localkey:
    l,h=t['local'],t['hive'];same=all(l[k]==h[k] for k in ['open','verified','failed'])
    countok=len(l['open'])==h['displayed_open'];healthyok=not(l['open'] and h['health']=='healthy')
   else:
    same=all(t['local_'+k]==t['hive_'+k] for k in ['open','verified','failed']);countok=True;healthyok=not(t['local_open'] and t['hive_health']=='healthy')
   if not same:fail.append([name,j])
   if not countok or not healthyok:health.append([name,j])
 return dict(schedules=len(rows),events=total,agreement_failures=fail,health_failures=health)
rows=[]
for n in ['new-cases.json','supplementary.json']:rows+=list(json.loads((E/n).read_text()).items())
out['original_402']=audit(rows,'events')
x=json.loads((E/'ownership-lifecycle.json').read_text());out['lifecycle_48']=audit([(r['name'],r) for r in x],'trace',True)
for n in ['current-format-sweep','prior-ordered-format-sweep','legacy-fail-closed-sweep']:
 x=json.loads((E/(n+'.json')).read_text());out[n]=dict(total=len(x),passed=sum(r['passed'] for r in x))
x=json.loads((E/'review-a/expanded-results.json').read_text())['lifecycle'];out['lifecycle_18']=dict(total=len(x),passed=sum(r['passed'] for r in x.values()),failures=[k for k,v in x.items() if not v['passed']],current_total=sum('baseline' not in k for k in x),current_agreement=sum(v['agreement_every_event'] for k,v in x.items() if 'baseline' not in k))
(E/'agreement-audit.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
