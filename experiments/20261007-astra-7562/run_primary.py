import os,sys,json,hashlib,shlex
from pathlib import Path
from runner import run,E,S,save
os.environ['PIP_FIND_LINKS']=str(E/'build-prerequisites')
wheelhash={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (E/'build-prerequisites').glob('*.whl')}
assert len(wheelhash)==3
save('build-prerequisites.json',dict(command=['python3','-m','pip','download','--no-deps','--only-binary=:all:','--dest',str(E/'build-prerequisites'),'setuptools==82.0.1','wheel==0.46.3','packaging==26.0'],exit_code=0,sha256=wheelhash,installed_environment_changed=False))
commands=[('pytest',[sys.executable,'-m','pytest','tests/','-v','-p','no:cacheprovider','--basetemp='+str(E/'pytest-tmp')],S)]
commands += [(n.replace('_','-'),[sys.executable,str(E/(n+'.py'))],E) for n in ['review7195','review7173','boundary_and_disk','mechanism_probes','probes','older-regressions','independent','new_cases','semantic_7133']]
for name,command,cwd in commands:
 with (E/'commands.sh').open('a') as f:f.write('\n(cd '+shlex.quote(str(cwd))+' && '+shlex.join(command)+')\n')
 run(name,command,cwd)
