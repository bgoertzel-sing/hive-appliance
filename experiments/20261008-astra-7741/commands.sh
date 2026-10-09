#!/bin/sh
cd "$(dirname "$0")"
export PYTHONDONTWRITEBYTECODE=1 HIVE_SRC=/tmp/hive-astra-7741-source
python3 run_primary.py
python3 run_journals.py
python3 - <<'PY'
import sys
from runner import E,run
for n in ['reset7718','exact_restore_final7718','intent_final7727','extra_io7727','intent7734','metadata7734','verify_sources7734','static7734']:
 run(n,[sys.executable,str(E/(n+'.py'))])
PY
python3 - <<'PY'
import sys
from runner import E,run
for n in ['focused7741','audit7741','audit7741-final']:
 run(n,[sys.executable,str(E/(n+'.py'))])
PY
# After finalizing report, README, RUN and verifier:
python3 finalize_provenance.py
python3 - <<'PY'
import sys
from runner import E,run
run('secret-scan',[sys.executable,str(E/'secret_scan.py')])
PY
# Generate SHA256SUMS over all regular evidence files plus report, excluding itself.
# PYTHONDONTWRITEBYTECODE=1 python3 verify_evidence.py (read-only)
