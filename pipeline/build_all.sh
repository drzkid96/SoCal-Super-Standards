#!/bin/sh
# Rebuild derived pages and indexes in dependency order (source extraction steps run separately).
set -e
python3 -I pipeline/build_refcards.py
python3 -I pipeline/build_details.py
python3 -I pipeline/build_topics.py
python3 -I pipeline/build_ladot_hub.py .
python3 -I pipeline/build_linetypes.py
python3 -I pipeline/build_markings.py
python3 -I pipeline/build_linetypes.py
