import hashlib, importlib.metadata as md, json, os, pathlib, platform, shutil, subprocess, sys, time
E=pathlib.Path(__file__).resolve().parent
R=pathlib.Path(__import__('os').environ.get('HIVE_SRC', str(E.parent.parent)))
S=E/'source'
S.mkdir(exist_ok=True)
files=subprocess.check_output(['git','ls-files','-z'],cwd=R).decode().split('\0')
manifest={}
for name in filter(None,files):
    src=R/name; dst=S/name; dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst)
    manifest[name]=hashlib.sha256(src.read_bytes()).hexdigest()
(E/'source-sha256.json').write_text(json.dumps(manifest,indent=2))
versions={}
for name in ['pytest','build','setuptools','wheel','chromadb','onnxruntime','tomli']:
    try: versions[name]=md.version(name)
    except md.PackageNotFoundError: versions[name]='not found'
env_info={'python':sys.version,'executable':sys.executable,'platform':platform.platform(),'sqlite':__import__('sqlite3').sqlite_version,'versions':versions,'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),'status':subprocess.check_output(['git','status','--porcelain'],cwd=R,text=True),'model':'GPT-6 (Codex), self-reported; gateway verified separately by parent'}
(E/'environment.json').write_text(json.dumps(env_info,indent=2))
(E/'tmp').mkdir(exist_ok=True)
env=os.environ.copy(); env.update({'PYTHONDONTWRITEBYTECODE':'1','PIP_NO_INDEX':'1','HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','ANONYMIZED_TELEMETRY':'False','TMPDIR':str(E/'tmp'),'PYTHONPATH':str(E/'guard'),'PYTEST_DISABLE_PLUGIN_AUTOLOAD':'1'})
cmd=[sys.executable,'-m','pytest','tests/','-v','-p','no:cacheprovider','--basetemp='+str(E/'pytest-tmp')]
start=time.time(); timed_out=False
with (E/'pytest.stdout').open('w') as out,(E/'pytest.stderr').open('w') as err:
    p=subprocess.Popen(cmd,cwd=S,env=env,stdout=out,stderr=err,start_new_session=True)
    try: rc=p.wait(timeout=600)
    except subprocess.TimeoutExpired:
        import signal
        timed_out=True; os.killpg(p.pid,signal.SIGKILL); rc=p.wait()
result={'command':cmd,'cwd':str(S),'exit_code':rc,'timed_out':timed_out,'timeout_seconds':600,'wall_seconds':time.time()-start}
(E/'pytest-result.json').write_text(json.dumps(result,indent=2)); print(json.dumps(result,indent=2))
