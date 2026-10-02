#!/bin/bash
# the back view's terminator overlays (kinkattr, one placement) of round 4's real builds, on the box each lives on
cd "$(dirname "$0")/../.."
export CLOUDSDK_CONFIG=$HOME/.config/charkit/gcloud CHARKIT_PY=$HOME/animation-pipeline/.venv/bin/python
PY=$HOME/animation-pipeline/.venv/bin/python
box=$1; shift
B=(); [ "$box" != build ] && B=(--box "$box")
for b in "$@"; do
  $PY -m charkit remote "${B[@]}" run --fetch charkit/out/hairshell3/r5/pics script tools/hairshell3/kinkattr.py charkit/out/$b --views back,front --n 1 --png charkit/out/hairshell3/r5/pics/kinks_$b.png --json charkit/out/hairshell3/r5/pics/kinks_$b.json > charkit/out/hairshell3/r5/pics_$b.log 2>&1
done
