import os,sys
from run_review import E,R,run
env=os.environ.copy();env.update(HIVE_SRC=str(R),PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=str(E/'guard'))
sys.exit(run('followup',[sys.executable,str(E/'followup_probes.py')],E,env)['exit_code'])
