"""Retry only legacy_default, adapting the now-explicit MIGRATION diagnostic."""
import pathlib,json,difflib
E=pathlib.Path(__file__).resolve().parent
src=(E/'followup7694.py').read_text();adapted=src.replace("'legacy or unknown' in h.journal_status()['fence']['error']", "h.journal_status()['fence']['kind']=='legacy' and 'MIGRATION' in h.journal_status()['fence']['error']")
(E/'retry-adaptation-7708.diff').write_text(''.join(difflib.unified_diff(src.splitlines(True),adapted.splitlines(True),fromfile='initial/followup7694.py',tofile='retry/in-memory-followup7694.py')))
ns={'__file__':str(E/'followup7694.py'),'__name__':'defs'};exec(compile(adapted[:adapted.index('\nout={}\n')],str(E/'followup7694.py'),'exec'),ns)
ns['T']=E/'legacy-retry7708';ns['T'].mkdir();r={};ns['legacy_default'](r);r['passed']=True
(E/'legacy-retry7708.json').write_text(json.dumps(r,indent=2,default=str)+'\n');print('legacy_default passed')
