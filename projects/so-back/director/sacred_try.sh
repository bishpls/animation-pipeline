#!/bin/zsh
# iterate on sacred.py at --res 1 with a params JSON; prints the key events
cd $HOME/animation-pipeline
.venv/bin/python projects/so-back/director/run.py sacred --env SOBACK_LAB=1 "SOBACK_P=$1" 2>&1 | grep -v '^{' | tail -1
L=~/games/melee/work/soback/labs/sacred/osreport.log
grep -E "^MARK|^HIT|RESET" $L | tr '\n' ';'; echo
