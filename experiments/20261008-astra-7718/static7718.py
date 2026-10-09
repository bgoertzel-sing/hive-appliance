import pathlib,subprocess,json,hashlib,os,socket
R=pathlib.Path('/home/openclaw/research-agent/projects/hive-appliance/repos/hive-appliance');E=pathlib.Path(__file__).resolve().parent;S=pathlib.Path(os.environ['HIVE_SRC'])
def git(*a):return subprocess.check_output(['git',*a],cwd=S).decode()
before=json.loads((E/'source-verification-before.json').read_text())
verified={p:hashlib.sha256((S/p).read_bytes()).hexdigest() for p in before}
assert before==verified
for p,d in verified.items():assert hashlib.sha256(subprocess.check_output(['git','show','HEAD:'+p],cwd=S)).hexdigest()==d,p
assert not git('status','--porcelain')
(E/'source-verification.json').write_text(json.dumps(dict(pin=git('rev-parse','HEAD').strip(),files=len(verified),all_match_pinned_git_blobs=True,all_match_initial_hashes=True,source_clean=True,status=git('status','--porcelain')),indent=2))
counts={}
for tag in ['7669','7678','7694','7701','7708']:
 p=S/('experiments/20261008-astra-'+tag);n=0
 for line in (p/'SHA256SUMS').read_text().splitlines():
  d,f=line.split('  ',1);assert hashlib.sha256((p/f).read_bytes()).hexdigest()==d,(tag,f);n+=1
 counts[tag]=n
(E/'prior-evidence-verification.json').write_text(json.dumps(counts,indent=2))
files=git('ls-files','docs','experiments').splitlines();matches=[]
import re
for f in files:
 if not f.endswith(('.md','.json','.stdout','.txt','.log')):continue
 for n,line in enumerate((S/f).read_text(errors='replace').splitlines(),1):
  if '0ec1a2d' in line or re.search(r'\b813 passed\b',line):
   matches.append(dict(file=f,line=n,text=line[:500]))
(E/'author-test-provenance.json').write_text(json.dumps(dict(commit=git('show','-s','--format=fuller','HEAD'),scope='Tracked docs/experiments textual report/log/JSON files at exact pin; no author artifact tying claimed 813-passed full suite to target SHA located; remote CI not queried',matches=matches,author_exact_sha_full_suite='UNVERIFIED',independent_full_suite='813 passed; pytest-started/exit.json and source verification tie run to pin'),indent=2))
denied=False
try:socket.create_connection(('192.0.2.1',443),timeout=.2)
except OSError as ex:denied='External network disabled' in str(ex)
assert denied
(E/'offline-verification.json').write_text(json.dumps(dict(external_python_socket_denied=denied,PIP_NO_INDEX=os.environ.get('PIP_NO_INDEX'),wheel_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (E/'build-prerequisites').iterdir()},scope='Python socket guard, not OS network sandbox. Git fetch/push authorized publication only.'),indent=2))
print('source files',len(verified),'prior manifest counts',counts,'author matches',len(matches))
