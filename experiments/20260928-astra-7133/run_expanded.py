import os,sys
from run_review import E,R,run
env=os.environ.copy();env.update(HIVE_SRC=str(R),PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=str(E/'guard'))
sys.exit(run('expanded',[sys.executable,str(E/'expanded_probes.py')],E,env)['exit_code'])
