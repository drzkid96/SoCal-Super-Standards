#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
python3 pipeline/prepare_reference.py
