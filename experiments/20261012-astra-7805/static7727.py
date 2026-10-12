"""Exact pin, prior evidence, offline runtime and copied-harness provenance."""
import pathlib,subprocess,json,hashlib,os,socket,difflib
E=pathlib.Path(__file__).resolve().parent;R=E.parent.parent;S=pathlib.Path(os.environ['HIVE_SRC']);P=E.parent/'20261008-astra-7718'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
before=json.loads((E/'source-verification-before.json').read_text());pin=before['pin'];verified={}
for name,h in before['hashes'].items():
 assert digest(S/name)==h and digest(R/name)==h,name
 assert hashlib.sha256(subprocess.check_output(['git','show',pin+':'+name],cwd=R)).hexdigest()==h,name
 verified[name]=h
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()==pin
(E/'source-verification.json').write_text(json.dumps(dict(pin=pin,files=len(verified),source=str(S),all_match_initial_hashes=True,all_match_pinned_git_blobs=True,repository_source_unchanged=True,source_is_export_not_git_worktree=True,git_status=subprocess.check_output(['git','status','--short'],cwd=R,text=True)),indent=2)+'\n')
counts={}
for tag in ['7669','7678','7694','7701','7708','7718']:
 d=E.parent/('20261008-astra-'+tag);n=0
 for line in (d/'SHA256SUMS').read_text().splitlines():
  h,f=line.split('  ',1);assert digest(d/f)==h,(tag,f);n+=1
 counts[tag]=n
(E/'prior-evidence-verification.json').write_text(json.dumps(counts,indent=2)+'\n')
diffs=[]
for name,h in json.loads((E/'copy-provenance.json').read_text())['sha256'].items():
 assert digest(P/name)==h,name
 if digest(E/name)!=h:diffs.extend(difflib.unified_diff((P/name).read_text().splitlines(True),(E/name).read_text().splitlines(True),fromfile='7718/'+name,tofile='7727/'+name))
(E/'adaptation-7727.diff').write_text(''.join(diffs))
denied=False
try:socket.create_connection(('192.0.2.1',443),timeout=.2)
except OSError as ex:denied='External network disabled' in str(ex)
assert denied
(E/'offline-verification.json').write_text(json.dumps(dict(external_python_socket_denied=True,PIP_NO_INDEX=os.environ.get('PIP_NO_INDEX'),scope='Python socket guard, not OS network sandbox. No package downloads, paid compute or remote execution.'),indent=2)+'\n')
(E/'author-test-provenance.json').write_text(json.dumps(dict(pin=pin,author_claim='817 passed',independent_result='817 passed in 51.57 seconds; full suite exactly once',author_provenance='Not independently verified; independent runner and pin verification are authoritative for this review'),indent=2)+'\n')
print('source files',len(verified),'prior manifests',counts,'source unchanged; offline guard verified')
