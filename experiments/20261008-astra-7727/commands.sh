#!/bin/sh
export PYTHONDONTWRITEBYTECODE=1
export HIVE_SRC=/tmp/hive-astra-7727-source
python3 run_primary.py
python3 run_journals.py
python3 run_reset7727.py
python3 -c 'import sys; from runner import E,run; run("intent-final7727",[sys.executable,str(E/"intent_final7727.py")])'
python3 -c 'import sys; from runner import E,run; run("extra-io7727",[sys.executable,str(E/"extra_io7727.py")])'
python3 -c 'import sys; from runner import E,run; run("static7727",[sys.executable,str(E/"static7727.py")])'
