from runner import run,E
import sys
# review7519.py is preserved as provenance, not executed: its last group asserts old defects.
for n in ['review7195','review7173','boundary_and_disk','mechanism_probes','probes','older-regressions','independent','new_cases','semantic_7133']:
 run(n.replace('_','-'),[sys.executable,str(E/(n+'.py'))])
