#!/bin/bash
# round 4: the default's build CPU, cold against cold on one box (the gate compared a warm baseline with a cold candidate)
cd "$(dirname "$0")/../.."
export CLOUDSDK_CONFIG=$HOME/.config/charkit/gcloud CHARKIT_PY=$HOME/animation-pipeline/.venv/bin/python
PY=$HOME/animation-pipeline/.venv/bin/python
mkdir -p charkit/out/hairshell3/r7
$PY -m charkit remote --box build build tools/hairshell3/r7_hull.json --no-cache --boards '' --out charkit/out/r7_hull_cold > charkit/out/hairshell3/r7/hull.log 2>&1
$PY -m charkit remote --box build build charkit/spec/clawd.json --no-cache --boards '' --out charkit/out/r7_shells_cold > charkit/out/hairshell3/r7/shells.log 2>&1
for b in r7_hull_cold r7_shells_cold; do echo $b $(cat charkit/out/$b/build_cpu.json); grep "CHARKIT_PHASE" charkit/out/hairshell3/r7/${b#r7_}.log 2>/dev/null | tr '\n' ' '; echo; done
