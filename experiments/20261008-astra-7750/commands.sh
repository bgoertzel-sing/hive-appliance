#!/bin/sh
cd "$(dirname "$0")"
export PYTHONDONTWRITEBYTECODE=1 HIVE_SRC=/tmp/hive-astra-7750-source
python3 run_primary.py
python3 run_journals.py
python3 - <<'PY'
import sys
from runner import E,run
for n in ['reset7718','exact_restore_final7718','intent_final7727','extra_io7727','intent7734','metadata7734','focused7741','focused7750','audit7750','recovery-final7750','namespace-scope7750','namespace-scope7750-final','audit7750-final','verify_sources7734','static7734','finalize_special_files','prepublish7750']:
 run(n,[sys.executable,str(E/(n+'.py'))])
PY
# After report and provenance finalization:
# python3 finalize_provenance.py
# python3 -c "import sys; from runner import E,run; run('secret-scan',[sys.executable,str(E/'secret_scan.py')])"
# Generate complete SHA256SUMS, then python3 verify_evidence.py (read-only).
