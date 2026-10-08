#!/bin/sh
set -eu
export HIVE_SRC=/tmp/hive-astra-7678-source
export PYTHONDONTWRITEBYTECODE=1
cd /tmp/hive-astra-7678/20261008-astra-7678
python3 run_primary.py
python3 -c 'from runner import run,E; import sys; run("review7678",[sys.executable,str(E/"review7678.py")],timeout=1200)'
python3 -c 'from runner import run,E; import sys; run("followup7678",[sys.executable,str(E/"followup7678.py")])'
python3 -c 'from runner import run,E; import sys; run("static7678",[sys.executable,str(E/"static7678.py")])'
