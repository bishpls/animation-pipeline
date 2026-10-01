#!/bin/bash
# round 4's real candidate builds (merged head), each followed by its six placements on the same box
cd "$(dirname "$0")/../.."
export CLOUDSDK_CONFIG=$HOME/.config/charkit/gcloud CHARKIT_PY=$HOME/animation-pipeline/.venv/bin/python
PY=$HOME/animation-pipeline/.venv/bin/python
name=$1; spec=$2; box=$3; boards=$4
mkdir -p charkit/out/hairshell3/r5
B=(); [ "$box" != build ] && B=(--box "$box")
$PY -m charkit remote "${B[@]}" build "$spec" --boards "$boards" --out charkit/out/$name > charkit/out/hairshell3/r5/$name.log 2>&1 || exit 1
$PY -m charkit remote "${B[@]}" run --fetch charkit/out/hairshell3/r5/t6_$name script tools/hairshell3/term6p.py charkit/out/$name $name=- --json charkit/out/hairshell3/r5/t6_$name/t6.json > charkit/out/hairshell3/r5/t6_$name.log 2>&1
