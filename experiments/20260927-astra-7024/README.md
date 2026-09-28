# Astra review 7024 evidence (reviewed commit e6afe16)

Copied from the reviewer's evidence directory for reproducibility. Excluded: `source/` (tracked-source export, identical to e6afe16), `pytest-tmp/`, `tmp/`, `guard/` (sandbox scratch). `SHA256SUMS` and `source-sha256.json` refer to the original directory, so hashes for excluded paths will not verify here.

Scripts are run from the repo root against the checked-out source, e.g. `python3 experiments/20260927-astra-7024/new_cases.py`. `adversarial.py` is the 7003 script (it asserts the old buggy behaviour); `adversarial-inverted.py` asserts the corrected behaviour.
