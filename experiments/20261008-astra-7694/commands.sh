#!/bin/sh
set -eu
export HIVE_SRC=/tmp/hive-astra-7694-source
export PYTHONDONTWRITEBYTECODE=1
cd /tmp/hive-astra-7694/20261008-astra-7694
python3 run_primary.py
python3 -c 'from runner import run,E; import sys; run("review7694",[sys.executable,str(E/"review7694.py")],timeout=1200)'
python3 -c 'from runner import run,E; import sys; run("followup7694",[sys.executable,str(E/"followup7694.py")],timeout=1200)'
python3 -c 'from runner import run,E; import sys; run("clearance7694",[sys.executable,str(E/"clearance7694.py")],timeout=1800)'
# First static attempt recorded an incomplete source archive; fixed without source edits.
python3 -c 'from runner import run,E; import sys; run("static7694",[sys.executable,str(E/"static7694.py")],timeout=1800)'
python3 archive_sources7694.py
python3 -c 'from runner import run,E; import sys; run("static7694-final",[sys.executable,str(E/"static7694.py")],timeout=1800)'
