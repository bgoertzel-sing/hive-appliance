import sys
from runner import E,run
for n in ["reset7718","exact_restore_final7718","intent7727"]:
 run(n,[sys.executable,str(E/(n+".py"))])
