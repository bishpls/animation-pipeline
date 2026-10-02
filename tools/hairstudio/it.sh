#!/bin/bash
# one studio iteration: build the style's groom, render and measure it, refresh the page. it.sh STYLE TAG "NOTE"
set -e
T=$HOME/animation-pipeline-3d/charkit/out/groomtest
PY=$HOME/animation-pipeline/.venv/bin/python
SRC=${HAIRSTUDIO_BASE:-$HOME/animation-pipeline-3d/charkit/out/hairbase/bundle}
$PY $T/groom3.py $SRC $T/it/$2 $T/styles/$1.json > $T/it/$2.log 2>&1
cd $HOME/animation-pipeline-3d && nice -n 5 $PY $T/studio.py measure $T/it/$2 $2 "$3" 2>&1 | grep -v -i warn | tail -1
