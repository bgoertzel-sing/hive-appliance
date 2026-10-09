from pathlib import Path
import subprocess,shutil
E=Path(__file__).resolve().parent;S=Path('/tmp/hive-astra-7694-source')
for path in subprocess.check_output(['git','diff','--name-only','d1239f9','cf6a060'],cwd=S,text=True).splitlines():
 if (S/path).is_file():
  target=E/'source'/path;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(S/path,target)
print('Complete changed-source archive populated; no source tree changed.')
