#!/bin/sh
cd "$(dirname "$0")"
export PYTHONDONTWRITEBYTECODE=1
export HIVE_SRC=/tmp/hive-astra-7734-source
python3 run_primary.py
python3 run_journals.py
python3 -c 'import sys; from runner import E,run; [run(n,[sys.executable,str(E/(p+".py"))]) for n,p in [("reset7718","reset7718"),("exact_restore_final7718","exact_restore_final7718"),("intent-final7727","intent_final7727"),("extra-io7727","extra_io7727")]]'
python3 -c 'import sys; from runner import E,run; run("intent7734",[sys.executable,str(E/"intent7734.py")])'
python3 -c 'import sys; from runner import E,run; run("source-and-prior-verification",[sys.executable,str(E/"verify_sources7734.py")])'
python3 -c 'import sys; from runner import E,run; [run(n+"-final",[sys.executable,str(E/(n+"-final.py"))]) for n in ["probes","older-regressions","independent"]]'
python3 -c 'import sys; from runner import E,run; run("metadata7734",[sys.executable,str(E/"metadata7734.py")])'
python3 -c 'import sys; from runner import E,run; run("static7734",[sys.executable,str(E/"static7734.py")])'
# Run after report, index, ledger and verifier are finalized:
python3 -c 'import sys; from runner import E,run; run("secret-scan",[sys.executable,str(E/"secret_scan.py")])'
# Generate SHA256SUMS over all regular evidence files and report, excluding itself.
# Then: python3 verify_evidence.py (read-only; output is recorded by the requester).
