#!/bin/bash
# round 4's real builds against the 52-lock truth (charkit hairlocks score), on the box each lives on
cd "$(dirname "$0")/../.."
export CLOUDSDK_CONFIG=$HOME/.config/charkit/gcloud CHARKIT_PY=$HOME/animation-pipeline/.venv/bin/python
PY=$HOME/animation-pipeline/.venv/bin/python
box=$1; shift
B=(); [ "$box" != build ] && B=(--box "$box")
for b in "$@"; do
  $PY -m charkit remote "${B[@]}" run --fetch charkit/out/hairshell3/r5/locks_$b hairlocks score charkit/out/$b --json charkit/out/hairshell3/r5/locks_$b/score.json > charkit/out/hairshell3/r5/locks_$b.log 2>&1
done
