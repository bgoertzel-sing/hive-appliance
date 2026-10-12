"""AST/read-path audit, original-test comparison and explicit scope evidence."""
import ast,json,subprocess,os,re,hashlib
from pathlib import Path
from runner import E,S
R=E.parent.parent;source=(S/'hive/reducer.py').read_text();t=ast.parse(source);cls=next(n for n in t.body if isinstance(n,ast.ClassDef) and n.name=='HiveReducer');methods={n.name:n for n in cls.body if isinstance(n,ast.FunctionDef)}
opens=[];builtins=[];reads=[];unsafe=[]
for name,n in methods.items():
 for c in ast.walk(n):
  if not isinstance(c,ast.Call):continue
  f=ast.unparse(c.func)
  if f in ['open','builtins.open']:builtins.append(dict(method=name,line=c.lineno,call=ast.unparse(c)))
  if f=='os.open':opens.append(dict(method=name,line=c.lineno,call=ast.unparse(c)))
  if f in ['os.read','os.pread']:reads.append(dict(method=name,line=c.lineno,call=ast.unparse(c)))
  if re.search(r'(lexists|isfile|islink|exists|is_file|is_dir|access)$',f):unsafe.append(dict(method=name,line=c.lineno,call=f))
assert not builtins and not unsafe
calls={name:sorted({c.func.attr for c in ast.walk(n) if isinstance(c,ast.Call) and isinstance(c.func,ast.Attribute) and isinstance(c.func.value,ast.Name) and c.func.value.id=='self' and c.func.attr in methods}) for name,n in methods.items()}
def reachable(start):
 seen=set();stack=[start]
 while stack:
  n=stack.pop()
  if n in seen:continue
  seen.add(n);stack+=calls.get(n,[])
 return sorted(seen)
roots={n:reachable(n) for n in ['_open_journal','_replay_journal','verify_journal','_journal_write','clear_journal_fence','reset_journal'] if n in methods}
archive_exprs=[]
for n in ast.walk(t):
 if isinstance(n,ast.JoinedStr) and any(x in ast.unparse(n) for x in ['.fenced-','.reset-','.cleared-']):archive_exprs.append(dict(line=n.lineno,expression=ast.unparse(n)))
old=subprocess.check_output(['git','show','2c7e337:tests/test_astra7734.py'],cwd=R).decode();new=(S/'tests/test_astra7734.py').read_text();test='test_handler_lstat_eio_after_journal_moved_reports_unknown'
get=lambda s:next(n for n in ast.parse(s).body if isinstance(n,ast.FunctionDef) and n.name==test)
a=get(old);b=get(new)
class Normalize(ast.NodeTransformer):
 def visit_Name(self,n):
  if n.id=='builtins':n.id='os'
  return n
assert ast.dump(Normalize().visit(a),include_attributes=False)==ast.dump(b,include_attributes=False)
assert (E/'source/test_astra7734-before.py').read_text()==old
result=dict(builtin_open_calls=builtins,unsafe_predicate_calls=unsafe,os_open_calls=opens,fd_read_calls=reads,reachable_methods=roots,self_call_graph=calls,archive_expressions=archive_exprs,test_adaptation=dict(name=test,original_commit='2c7e337202cbfa19569b344992326a1603d867cd',same_function_AST_after_builtin_to_os_normalization=True,semantic_injection='First anchor read open fails EIO after old journal renamed. Subsequent marker-lstat EIO reports unknown presence and acknowledged rename, not unchanged pair. Same path guard, one-shot trigger, lstat hook and assertions; current test PASSED in full suite.'),notes={
 'strict_reads':'Only os.read call is _read_regular after lstat/O_NOFOLLOW/fstat identity+type validation. Only os.pread call is _verify_on_disk after descriptor regular check and anchor validation. No builtin open remains.',
 'archives':'Startup reads only exact configured journal and its exact .id. Legacy fence and reset-intent checks are lstat-only. No glob/listdir/archive discovery or record archived-field dereference. _open_journal treats journal_reset as an audit record; archive path strings are not opened. All constructed archive outputs flow to _write_file_durably O_WRONLY|O_CREAT|O_EXCL or os.replace. Behavior trace in focused7750 confirms no archived-file read with deliberately valid old rebinds in archive files.',
 'nonregular':'Steady entries fence identity and stay untouched. Clear moves nonregular journal to .fenced-, anchor to .cleared-; reset moves either to .reset-. Policy lists .cleared/.reset shorthand but journal clearance actually uses .fenced as documented separately at policy:264.',
 'races':'lstat->open same-device/inode/type comparison prevents tested regular, symlink and directory swaps, except FIFO open may block BEFORE fstat. O_NOFOLLOW=0 accepts a same-inode symlink. Final-component checks are not namespace locks.',
 'parent':'All paths are string-based. _fsync_dir opens dirname(abspath(path)) without O_DIRECTORY/O_NOFOLLOW or stored parent dirfd. Intermediate symlinks are followed by lstat/open/replace/unlink; stable symlink parents work. A changed ancestor can redirect operation/fsync. No hostile namespace-writer or concurrently retargeted directory guarantee.',
 'remaining_check_trust':'After absent lstat, _create_journal uses replace, not an atomic expected-absence check; a newly introduced entry can be replaced. _move_aside_if_not_regular lstat and rename are separate, and clear/reset later replace names without inode preconditions. Runtime verifies opened descriptor bytes and current anchor but does not bind its descriptor inode to the current journal pathname after opening; a namespace swap can detach it. These are outside the single-writer protected-stable-directory scope, not evidence of safe adversarial concurrency.',
 'runtime_findings':'_journal_write only maps ENOENT/ELOOP at open to _JournalChanged; EISDIR flows to generic OSError and refusal leaves healthy=True. verify opens FIFO O_RDONLY and blocks; startup reader can also block on a regular->FIFO swap. See independent runtime/fifo witnesses.',
 'limits_docs':'Unkeyed hashes policy 204-208; joint rollback 112-131; record-boundary tail 198-206; snapshot/partial replay 87-89; undurable intent 180-191; nonregular entries 169-177. Linux/no-O_NOFOLLOW scope explicitly in existing docs/ASTRA_REVIEW_7741.md sections 2, 4 and findings, not repeated in primary README/policy. This report makes ancestor scope explicit; no claim of universal symlink protection.'})
(E/'audit7750-final.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
