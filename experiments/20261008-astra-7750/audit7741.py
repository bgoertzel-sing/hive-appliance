"""Read-only source audit: AST avoids counting comments/docstrings as calls."""
import ast,json,re
from pathlib import Path
from runner import E,S
rows=[];suppressed=[]
for p in sorted((S/'hive').glob('*.py')):
 t=ast.parse(p.read_text())
 for n in ast.walk(t):
  if isinstance(n,ast.Call):
   name=ast.unparse(n.func)
   if re.search(r'(lexists|isfile|islink|exists|is_file|is_dir|access)$',name):rows.append(dict(file=str(p.relative_to(S)),line=n.lineno,call=name))
  if isinstance(n,ast.ExceptHandler):
   typ=ast.unparse(n.type) if n.type else 'bare'
   if any(x in typ for x in ['OSError','FileNotFoundError','Exception']):suppressed.append(dict(file=str(p.relative_to(S)),line=n.lineno,type=typ,body=ast.unparse(n)))
assert not rows
result=dict(unsafe_predicate_calls=rows,exception_handlers=suppressed,notes={
 'cleanup':'reducer 439/442 and 550/553 swallow only cleanup unlink errors then re-raise original failure; no absent decision.',
 'presence':'454 returns missing only on FileNotFoundError (native ENOENT); 462 preserves unknown/error.',
 'startup':'644 treats intent metadata error present, sets discard; 673 blocks unwritable.',
 'anchor_gap':'533 maps open ENOENT to absent without lstat: dangling .id entry is overwritten on cold startup. Witness focused7741.dangling_anchor.',
 'clear_reset_reads':'962 and 1123 map open ENOENT to missing journal/anchor content; other errors propagate. These are explicit destructive recovery operations, unlike startup.',
 'runtime':'817/848/853/871 fence or raise; 881/885 rollback errors propagate; 892 only logs close errors after successful fsync, does not infer absence.',
 'other_modules':'Broad Exception guards log polling, planning, adapter/store and appliance errors; no filesystem existence decisions.',
 'audit_gap':'reset failure audit 1218-1223 omits presence_error; fence includes it at 1215-1216.',
 'portability':'getattr(O_NOFOLLOW,0) is safe for tested Linux flag; when unavailable, same-inode symlink replacement can be followed; concurrent hostile namespace mutation excluded.'})
(E/'audit7741.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
