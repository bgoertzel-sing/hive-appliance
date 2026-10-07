#!/bin/sh
# Exact recorded child invocations, in launch order; NOT an overwrite-safe replay script.
# Use replay.py for reproduction into a new directory.

(cd /home/openclaw/research-agent/projects/hive-appliance/experiments/20261006-astra-7542 && git clone https://github.com/bgoertzel-sing/hive-appliance.git /home/openclaw/research-agent/projects/hive-appliance/repos/hive-astra-7542)

(cd /home/openclaw/research-agent/projects/hive-appliance/repos/hive-astra-7542 && git checkout -b review/astra-7542)

(cd /home/openclaw/research-agent/projects/hive-appliance/experiments/20261006-astra-7542/source && /usr/bin/python3 -m pytest tests/ -v -p no:cacheprovider --basetemp=/home/openclaw/research-agent/projects/hive-appliance/experiments/20261006-astra-7542/pytest-tmp)

(cd /home/openclaw/research-agent/projects/hive-appliance/experiments/20261006-astra-7542 && /usr/bin/python3 /home/openclaw/research-agent/projects/hive-appliance/experiments/20261006-astra-7542/review7195.py)

(cd /home/openclaw/research-agent/projects/hive-appliance/experiments/20261006-astra-7542 && /usr/bin/python3 /home/openclaw/research-agent/projects/hive-appliance/experiments/20261006-astra-7542/review7173.py)

(cd /home/openclaw/research-agent/projects/hive-appliance/experiments/20261006-astra-7542 && /usr/bin/python3 /home/openclaw/research-agent/projects/hive-appliance/experiments/20261006-astra-7542/boundary_and_disk.py)

(cd /home/openclaw/research-agent/projects/hive-appliance/experiments/20261006-astra-7542 && /usr/bin/python3 /home/openclaw/research-agent/projects/hive-appliance/experiments/20261006-astra-7542/mechanism_probes.py)

(cd /home/openclaw/research-agent/projects/hive-appliance/experiments/20261006-astra-7542 && /usr/bin/python3 /home/openclaw/research-agent/projects/hive-appliance/experiments/20261006-astra-7542/probes.py)

(cd /home/openclaw/research-agent/projects/hive-appliance/experiments/20261006-astra-7542 && /usr/bin/python3 /home/openclaw/research-agent/projects/hive-appliance/experiments/20261006-astra-7542/older-regressions.py)

(cd /home/openclaw/research-agent/projects/hive-appliance/experiments/20261006-astra-7542 && /usr/bin/python3 /home/openclaw/research-agent/projects/hive-appliance/experiments/20261006-astra-7542/independent.py)

(cd /home/openclaw/research-agent/projects/hive-appliance/experiments/20261006-astra-7542 && /usr/bin/python3 /home/openclaw/research-agent/projects/hive-appliance/experiments/20261006-astra-7542/new_cases.py)

(cd /home/openclaw/research-agent/projects/hive-appliance/experiments/20261006-astra-7542 && /usr/bin/python3 /home/openclaw/research-agent/projects/hive-appliance/experiments/20261006-astra-7542/semantic_7133.py)

(cd /home/openclaw/research-agent/projects/hive-appliance/experiments/20261006-astra-7542 && /usr/bin/python3 /home/openclaw/research-agent/projects/hive-appliance/experiments/20261006-astra-7542/review7542.py)

(cd /home/openclaw/research-agent/projects/hive-appliance/experiments/20261006-astra-7542 && /usr/bin/python3 /home/openclaw/research-agent/projects/hive-appliance/experiments/20261006-astra-7542/source_audit.py)

(cd /home/openclaw/research-agent/projects/hive-appliance/repos/hive-astra-7542 && git fetch origin main)
