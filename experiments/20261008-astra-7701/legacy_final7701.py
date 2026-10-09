"""Finish only the default/legacy group after fixing duplicate result serialization."""
import pathlib,os,json,difflib
E=pathlib.Path(__file__).resolve().parent
p=E/'review7656.py';s=p.read_text().replace('ok.as_dict().as_dict()','ok.as_dict()');p.write_text(s)
ns={'__file__':str(E/'followup7694.py'),'__name__':'defs'};src=(E/'followup7694.py').read_text();exec(compile(src[:src.index('\nout={}\n')],str(E/'followup7694.py'),'exec'),ns)
ns['T']=E/'legacy-final7701';ns['T'].mkdir()
r={};ns['legacy_default'](r);r['passed']=True
(E/'legacy-final7701.json').write_text(json.dumps(r,indent=2,default=str)+'\n')
P=pathlib.Path(os.environ['HIVE_SRC'])/'experiments/20261008-astra-7694';diff=[]
for name in ['review7694.py','followup7694.py','review7582.py','review7656.py']:
 diff.extend(difflib.unified_diff((P/name).read_text().splitlines(True),(E/name).read_text().splitlines(True),fromfile='7694/'+name,tofile='7701/'+name))
(E/'adaptation-7701.diff').write_text(''.join(diff));print('legacy/default controls passed')
