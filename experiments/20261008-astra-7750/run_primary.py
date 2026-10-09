import os,sys
from runner import E,S,run
os.environ["PIP_FIND_LINKS"]="/tmp/hive-astra-7718/20261008-astra-7718/build-prerequisites"
run("pytest",[sys.executable,"-m","pytest","tests/","-v","-p","no:cacheprovider","--basetemp="+"/tmp/hive-astra-7750-pytest"],S)
for n in ["review7195","review7173","boundary_and_disk","mechanism_probes","probes-final","older-regressions-final","independent-final","new_cases","semantic_7133"]:
 run(n.replace("_","-"),[sys.executable,str(E/(n+".py"))],E)
