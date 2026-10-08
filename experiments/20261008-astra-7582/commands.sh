#!/bin/sh
# Exact commands executed by run_primary.py; HIVE_SRC selects pinned clean clone.
HIVE_SRC=/home/openclaw/research-agent/projects/hive-appliance/repos/hive-astra-7582 python3 /home/openclaw/research-agent/projects/hive-appliance/experiments/20261008-astra-7582/run_primary.py
# Subsequent scoped executions (runner records exact argv/cwd/env policy):
# HIVE_SRC=<pinned clone> python3 -c 'from runner import run,E; import sys; run("review7582",[sys.executable,str(E/"review7582.py")],E)'
# HIVE_SRC=<pinned clone> python3 -c 'from runner import run,E; import sys; run("followup7582",[sys.executable,str(E/"followup7582.py")],E)'
# Read *-started.json and *-exit.json for actual absolute argv/cwd and wall time.
