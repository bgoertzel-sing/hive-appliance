"""Recovery diagnostics under namespace inspection errors; no production mutations."""
import os,sys,json,errno,builtins
from pathlib import Path
from unittest.mock import patch
E=Path(__file__).resolve().parent
ns={'__file__':str(E/'reset7718.py'),'__name__':'defs'}
src=(E/'reset7718.py').read_text();exec(compile(src[:src.index('\nout={}\n')],str(E/'reset7718.py'),'exec'),ns)
ns['T']=E/'metadata7734-cases';ns['T'].mkdir(exist_ok=True)
rows=[]
for stage in ['archive old anchor','remove reset-intent marker']:
 p,s,h=ns['restored'](stage.replace(' ','-'));ip=str(p)+'.reset-intent';old=ns['pair'](p);in_failure=False;ls=os.lstat;op=builtins.open;un=os.unlink
 def stat(path,*a,**kw):
  if in_failure and str(path)==ip:raise OSError(errno.EIO,'marker lstat unavailable')
  return ls(path,*a,**kw)
 def opening(path,*a,**kw):
  global in_failure
  if stage=='archive old anchor' and str(path)==str(ns['anchor'](p)):
   in_failure=True;raise OSError(errno.EIO,'anchor read fails')
  return op(path,*a,**kw)
 def unlink(path,*a,**kw):
  global in_failure
  if stage=='remove reset-intent marker' and str(path)==ip:
   in_failure=True;raise OSError(errno.EACCES,'intent unlink fails')
  return un(path,*a,**kw)
 with patch.object(os,'lstat',stat),patch.object(builtins,'open',opening),patch.object(os,'unlink',unlink):
  try:h.reset_journal('op','metadata failure')
  except OSError:pass
 st=ns['state'](h);f=st['status']['fence'];assert os.path.lexists(ip) and f['intent_present'] is None and f['presence_error']
 assert f['intent_durable'] is False and ns['pair'](p)!=old
 assert 'old journal and .id are unchanged' not in f['error'] and 'marker was unlinked' not in f['error']
 z=ns['hnew'](p);assert z.journal_status()['fence']['kind']=='reset_incomplete';ns['held'](ns['hfeed'](z,s))
 rows.append(dict(stage=stage,failed=st,actual_intent_present=True,old_pair_unchanged=False,restart=ns['state'](z),false_old_pair_claim='old journal and .id are unchanged' in f['error'],false_unlinked_claim='marker was unlinked' in f['error']))
# Nonregular markers are treated as namespace-only barriers, despite universal
# file+directory-fsync wording. Directory case reaches removal and fails safely.
nonregular=[]
for form in ['directory','dangling_symlink']:
 p,s,h=ns['restored']('nonregular-'+form);ip=Path(str(p)+'.reset-intent')
 if form=='directory':ip.mkdir()
 else:ip.symlink_to(ip.name+'.absent')
 h=ns['hnew'](p);fs=os.fsync;syncs=[]
 def syncing(fd):syncs.append(ns['fpath'](fd));return fs(fd)
 def stop(*a,**kw):raise OSError(errno.EIO,'first mutation stopped')
 with patch.object(os,'fsync',syncing),patch.object(os,'replace',stop):
  try:h.reset_journal('op','namespace marker')
  except OSError:pass
 nonregular.append(dict(form=form,fsync_acknowledgements=syncs,failed=ns['state'](h)))
result=dict(presence_error_cases=rows,nonregular_markers=nonregular,passed=True)
(E/'metadata7734.json').write_text(json.dumps(result,indent=2)+'\n');print('2 corrected presence/error-text cases; 2 nonregular refusals recorded')
