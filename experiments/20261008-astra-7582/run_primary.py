import os,sys
from runner import E,S,run
os.environ['PIP_FIND_LINKS']=str(E/'build-prerequisites')
run('pytest',[sys.executable,'-m','pytest','tests/','-v','-p','no:cacheprovider','--basetemp='+str(E/'pytest-tmp')],S)
for n in ['review7195','review7173','boundary_and_disk','mechanism_probes','probes','older-regressions','independent','new_cases','semantic_7133']:
 run(n.replace('_','-'),[sys.executable,str(E/(n+'.py'))],E)
