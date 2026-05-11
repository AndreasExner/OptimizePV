#!/bin/bash
# Kopiert src/ und requirements.txt ins Add-on Verzeichnis für HA Supervisor Build.
# Wird vor dem ersten Build auf HA OS ausgeführt.
#
# Verwendung:
#   cd /path/to/OptimizePV
#   bash optimizepv/prepare_build.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

echo "Kopiere src/ und requirements.txt nach optimizepv/..."
cp -r "$REPO_DIR/src" "$SCRIPT_DIR/src"
cp "$REPO_DIR/requirements.txt" "$SCRIPT_DIR/requirements.txt"
echo "Fertig. Add-on kann jetzt gebaut werden."
