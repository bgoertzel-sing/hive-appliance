import pathlib,json,hashlib,subprocess,os
E=pathlib.Path(__file__).resolve().parent;S=pathlib.Path(os.environ['HIVE_SRC']);R=pathlib.Path('/home/openclaw/research-agent/projects/hive-appliance/repos/hive-appliance')
def git(*a):return subprocess.check_output(['git',*a],cwd=S)
def save(n,o):(E/n).write_text(json.dumps(o,indent=2)+'\n')
before=json.loads((E/'source-verification-before.json').read_text());changed=[];notpin=[]
for p,h in before.items():
 if hashlib.sha256((S/p).read_bytes()).hexdigest()!=h:changed.append(p)
 if git('show','HEAD:'+p)!=(S/p).read_bytes():notpin.append(p)
status=git('status','--porcelain').decode();assert not changed and not notpin and not status
save('source-verification.json',dict(files=len(before),changed=changed,not_pin=notpin,status=status,pin=git('rev-parse','HEAD').decode().strip()))
counts={}
for name in ['7669','7678','7694','7701']:
 p=S/('experiments/20261008-astra-'+name);rows=(p/'SHA256SUMS').read_text().splitlines()
 for line in rows:
  h,n=line.split('  ',1);assert hashlib.sha256((p/n).read_bytes()).hexdigest()==h,(name,n)
 counts[name]=len(rows)
save('prior-evidence-verification.json',counts)
tracked=git('ls-files').decode().splitlines();matches=[]
for p in tracked:
 if not p.startswith(('experiments/','docs/')):continue
 try:lines=(S/p).read_text().splitlines()
 except (UnicodeError,IsADirectoryError):continue
 for i,line in enumerate(lines,1):
  if '8945bdc' in line or ('808 passed' in line):matches.append(dict(path=p,line=i,text=line[:500]))
save('author-test-provenance.json',dict(pin=git('rev-parse','HEAD').decode().strip(),commit=git('show','-s','--format=fuller','HEAD').decode(),search_scope='Tracked docs and experiments at reviewed pin; exact SHA or 808 passed',matches=matches,conclusion='No authored test log tied to exactly 8945bdc was found. Commit message says tests but does not establish full-suite execution. Author execution on exact pin is UNVERIFIED; independent 808-pass suite is direct evidence.',remote_compute=False))
save('offline-verification.json',dict(guard=(E/'guard/sitecustomize.py').read_text(),limitations='Python socket guard, not OS network namespace; git fetch/push are authorized publication network operations. No paid or remote compute.',wheels={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (E/'build-prerequisites').iterdir()}))
print(json.dumps(dict(source_files=len(before),source_clean=True,prior_manifests=counts,author_matches=len(matches))))
