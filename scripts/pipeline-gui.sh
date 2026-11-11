#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/environment.sh
python3 scripts/pipeline-gui.py
