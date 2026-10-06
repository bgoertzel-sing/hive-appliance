from run_review import run,E
import sys
for n in ['review7519','review7195','review7173','boundary_and_disk','mechanism_probes','probes','older-regressions','independent']:
 run(n.replace('_','-'),[sys.executable,str(E/(n+'.py'))])
