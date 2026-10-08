#!/bin/sh
set -eu
export HIVE_SRC=/tmp/hive-astra-7656-source
export PYTHONDONTWRITEBYTECODE=1
cd /tmp/hive-astra-7656/20261008-astra-7656
python3 run_primary.py
python3 -c 'from runner import run,E; import sys; run("review7656",[sys.executable,str(E/"review7656.py")])'
python3 -c 'from runner import run,E; import sys; run("followup7656",[sys.executable,str(E/"followup7656.py")])'
python3 -c 'from runner import run,E; import sys; run("static7656",[sys.executable,str(E/"static7656.py")])'
