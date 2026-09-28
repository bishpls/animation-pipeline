#!/bin/sh
# Decode the announcer's sound banks from your own extracted disc into the layout the vocal code reads (common.py: A).
#   sh projects/so-back/vocals/decode_banks.sh ~/games/melee/disc/files/audio [~/games/melee/work/announcer]
# Game-derived audio: the output stays outside the repo.
set -e
AUDIO=${1:?path to the disc's files/audio}; A=${2:-$HOME/games/melee/work/announcer}; HERE=$(dirname "$0")
PY=${PYTHON:-.venv/bin/python}
$PY "$HERE/ssm.py" "$AUDIO/us/nr_name.ssm" "$A/names"            # the name calls and short lines (US)
cp "$HERE/INDEX.tsv" "$A/names/INDEX.tsv"                         # ids, sfx ids, character kinds and texts of the 52
for b in nr_select nr_vs nr_1p nr_title; do $PY "$HERE/ssm.py" "$AUDIO/us/$b.ssm" "$A/banks/$b"; done
$PY "$HERE/ssm.py" "$AUDIO/nr_name.ssm" "$A/banks/nr_name_jp"     # the Japanese-language set
