#!/bin/sh
set -eu
export HIVE_SRC=/tmp/hive-astra-7669-source
export PYTHONDONTWRITEBYTECODE=1
cd /tmp/hive-astra-7669/20261008-astra-7669
python3 run_primary.py
python3 -c 'from runner import run,E; import sys; run("review7669",[sys.executable,str(E/"review7669.py")],timeout=1200)'
python3 -c 'from runner import run,E; import sys; run("followup7669",[sys.executable,str(E/"followup7669.py")])'
python3 -c 'from runner import run,E; import sys; run("static7669",[sys.executable,str(E/"static7669.py")])'
