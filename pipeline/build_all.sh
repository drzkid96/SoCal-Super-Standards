#!/bin/sh
# Rebuild derived pages and indexes in dependency order (source extraction steps run separately).
set -e
python3 -I pipeline/apply_clean.py
python3 -I pipeline/build_refcards.py
python3 -I pipeline/build_details.py
python3 -I pipeline/dedupe.py
python3 -I pipeline/build_topics.py
python3 -I pipeline/build_ladot_hub.py .
python3 -I pipeline/build_linetypes.py
python3 -I pipeline/build_markings.py
python3 -I pipeline/build_linetypes.py
python3 -I pipeline/link_signs_docs.py
python3 -I pipeline/build_bulletins.py
python3 -I pipeline/build_index.py
python3 -I pipeline/build_supersede.py
python3 -I pipeline/tables_html.py /home/claude/work/camutcd-2026-all.pdf /home/claude/work/MUTCD-11E-R1-FULL.pdf
python3 -I pipeline/build_redraw_gallery.py
python3 -I pipeline/build_previews.py
