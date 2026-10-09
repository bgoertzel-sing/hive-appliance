import sys
from runner import E,run
for n in ['review7694','followup7694','focused7701','startup7701','clearance7701','marker7701']:
 run(n,[sys.executable,str(E/(n+'.py'))])
