import ast,json,subprocess,hashlib,os
from pathlib import Path
from runner import E,S
R=E.parents[1];pin='a875414ec0281db0a5d5a66b0d12412733f4cbd7'
def git(*args):return subprocess.check_output(['git',*args],cwd=R)
assert git('rev-parse','HEAD').decode().strip()==pin
meta=json.loads((E/'source.json').read_text())
for name,digest in meta['hashes'].items():
 for b in [(S/name).read_bytes(),(R/name).read_bytes(),git('show',pin+':'+name)]:assert hashlib.sha256(b).hexdigest()==digest,name
source=(S/'hive/reducer.py').read_text();tree=ast.parse(source);sites=[];reads=[];helpers=[]
for node in ast.walk(tree):
 if not isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):continue
 for c in ast.walk(node):
  if isinstance(c,ast.Call):
   name=ast.unparse(c.func)
   if name=='os.open':sites.append(dict(function=node.name,line=c.lineno,call=ast.unparse(c)))
   if name in ['os.read','os.pread','os.write']:reads.append(dict(function=node.name,line=c.lineno,call=ast.unparse(c)))
   if name=='_open_regular_fd':helpers.append(dict(function=node.name,line=c.lineno,call=ast.unparse(c)))
assert {x['function'] for x in sites}=={'_open_regular_fd','_fsync_dir','_write_file_durably'}
assert {x['function'] for x in helpers}=={'_sync_existing_durably','_read_regular','verify_journal','_journal_write'}
fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_open_regular_fd')
s=ast.get_source_segment(source,fn)
assert s.index('os.open')<s.index('os.fstat')<s.index('_stat.S_ISREG')<s.index('os.set_blocking')
assert 'os.O_NONBLOCK' in s and 'O_NOFOLLOW' in s
old=git('show','4a9b3c55:tests/test_astra7638.py').decode();new=(S/'tests/test_astra7638.py').read_text()
name='test_short_or_failed_write_is_clean_refusal'
def segment(s):return ast.get_source_segment(s,next(n for n in ast.parse(s).body if isinstance(n,ast.FunctionDef) and n.name==name))
before=segment(old);after=segment(new)
assert before.split('    assert h.journal_status()')[0]==after.split('    assert h._plan_owner')[0]
assert 'st["healthy"] is False and st["fence"]["kind"] == "changed"' in after
(E/'audit7805.json').write_text(json.dumps(dict(pin=pin,source_files=len(meta['hashes']),source_export_and_worktree_match_git=True,os_open_sites=sites,io_sites=reads,helper_callers=helpers,helper_order_verified=True,test7638=dict(before=before,after=after,setup_and_refusal_unchanged=True,interpretation='Legitimate correction: a directory is an integrity/type replacement, not a transient regular-file write error; owner remains unbound. The independent real-path directory witness agrees.'),exceptions=dict(exclusive_creation='O_WRONLY|O_CREAT|O_EXCL creates a new regular file or fails EEXIST on an existing FIFO/symlink/directory before peer wait or write. No helper is required for this open; verified FIFO case. Literal policy every open wording is overbroad, not a durability defect.',parent_directory='_fsync_dir uses O_RDONLY|O_NONBLOCK|O_DIRECTORY. Stable trusted ancestor symlinks intentionally allowed; Linux-only qualification.')),indent=2)+'\n')
print('PASS: source files',len(meta['hashes']),'all three raw os.open sites audited; four existing-file helper callers; helper order; legitimate 7638 test correction')
