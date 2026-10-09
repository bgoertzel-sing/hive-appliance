import os,sys,json,subprocess,socket,hashlib
from pathlib import Path
E=Path(__file__).resolve().parent;R=E.parent.parent
subprocess.run(['git','fetch','origin'],cwd=R,check=True)
read=lambda *a:subprocess.check_output(['git',*a],cwd=R).decode().strip()
pin=json.loads((E/'environment.json').read_text())['pin'];head=read('rev-parse','HEAD');origin=read('rev-parse','origin/main');assert pin==head==origin
blocked=False
try:socket.socket().connect(('203.0.113.1',9))
except OSError:blocked=True
assert blocked
wheels=Path('/tmp/hive-astra-7718/20261008-astra-7718/build-prerequisites');expected=json.loads((E/'environment.json').read_text())['offline_wheels'];assert all(hashlib.sha256((wheels/n).read_bytes()).hexdigest()==h for n,h in expected.items())
result=dict(pin=pin,head=head,origin_main=origin,extra_code=False,git_status=read('status','--short'),external_python_socket_blocked=blocked,offline_wheels_verified=True,pip_no_index=os.environ.get('PIP_NO_INDEX'),suite_runs=len(list(E.glob('pytest-started.json'))),dependency_downloads=False)
assert result['suite_runs']==1
(E/'offline-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
