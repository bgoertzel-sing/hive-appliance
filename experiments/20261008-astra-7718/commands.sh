#!/bin/sh
# Recorded commands; run only in a fresh evidence directory with the same retained scripts and offline wheel prerequisites.
export HIVE_SRC=/tmp/hive-astra-7718-source
python3 run_primary.py
python3 -c 'import sys; from runner import E,run; names=["review7694","followup7694","focused7701","startup7708","startup_recovery_final7708","clearance7701","marker7701","recovery7708"]; [run(n,[sys.executable,str(E/(n+".py"))]) for n in names]'
python3 -c 'import sys; from runner import E,run; run("reset7718",[sys.executable,str(E/"reset7718.py")])'
python3 -c 'import sys; from runner import E,run; run("static7718",[sys.executable,str(E/"static7718.py")])'
python3 -c 'import sys; from runner import E,run; run("exact-restore7718",[sys.executable,str(E/"exact_restore7718.py")])'
python3 -c 'import sys; from runner import E,run; run("exact-restore-final7718",[sys.executable,str(E/"exact_restore_final7718.py")])'
