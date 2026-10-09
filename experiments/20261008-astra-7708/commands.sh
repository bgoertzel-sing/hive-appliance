#!/bin/sh
# Historical command ledger; exclusive runner outputs require a fresh evidence directory for replay.
set -eu
export HIVE_SRC=/tmp/hive-astra-7708-source
export PYTHONDONTWRITEBYTECODE=1
# Setup recipe: setup7708.py; then adapt7708.py (applied before journal runner).
cd /tmp/hive-astra-7708/20261008-astra-7708
python3 run_primary.py # pytest exactly once, then retained general controls
python3 run_journals.py # primary + journal + focused + original creation + clearance + markers
# Additional executions through runner.run, in order (all Python commands):
# recovery7708.py -> recovery7708
# retry_legacy7708.py -> legacy-retry7708 (only failing legacy group)
# startup_recovery7708.py -> startup-recovery7708 (preserved failure)
# fix_startup7708.py generated corrected scripts and explicit diff
# startup7708.py -> startup7708
# startup_recovery_final7708.py -> startup-recovery-final7708
# static7708.py -> static7708
# Source checkout remained clean. No production/test edits.
# Publication: publish7708.py, scan_staged.py --write, manifest, restage,
# verify_evidence.py, scan_staged.py, git commit, git push origin main,
# then fetched remote/local hash equality outside manifest.
