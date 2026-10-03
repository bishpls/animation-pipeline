#!/bin/sh
# A private Melee sandbox, so several agents or sessions can build and run the game at once without trampling each other.
# Every in-game lab rewrites the decomp (director hooks, script.c, build.ninja) and the disc (main.dol, fighter files), so each
# gets its own: a decomp worktree on branch NAME (from BASE, default ext) with the configured build cloned in, the disc, a
# Dolphin profile, and a work folder (rig and movedata copied, everything else linked to the shared one, read-only by
# convention). APFS clones (cp -c) make the copies nearly free until written. Prints the exports; source them.
#   tools/machinima/melee/sandbox.sh NAME [BASE]       # -> ~/games/melee/sandbox/NAME
#   eval "$(tools/machinima/melee/sandbox.sh NAME)"    # then build.py, dolphin.py, remeasure.sh use the sandbox
# Keep a long-lived sandbox current: when the main decomp's ext gains engine changes (e.g. Geno's visibility-group default,
# without which new model parts render hidden), `git -C ~/games/melee/sandbox/NAME/decomp merge ext`, as well as merging the
# repo branch. Cap Dolphins across sandboxes with DOLPHIN_SLOTS=N (dolphin.py waits for a free slot). Merge the decomp branch back with
# `git -C ~/games/melee/decomp merge NAME`; remove with `git -C ~/games/melee/decomp worktree remove --force .../decomp`.
set -e
NAME=${1:?usage: sandbox.sh NAME [BASE]}; BASE=${2:-ext}
G=${MELEE_HOME:-$HOME/games/melee}; S=$G/sandbox/$NAME
mkdir -p "$S"
if [ ! -d "$S/decomp" ]; then
    git -C "$G/decomp" worktree add -q -b "$NAME" "$S/decomp" "$BASE" >&2
    for f in build orig; do mkdir -p "$S/decomp/$f"; cp -c -R -p "$G/decomp/$f/" "$S/decomp/$f/"; done
fi
[ -d "$S/disc" ] || cp -c -R -p "$G/disc" "$S/disc"
[ -d "$S/dolphin-user" ] || cp -c -R -p "$HOME/games/dolphin-user" "$S/dolphin-user"
if [ ! -d "$S/work" ]; then
    mkdir -p "$S/work"
    for d in "$G"/work/*; do
        b=$(basename "$d")
        case $b in rig|movedata) cp -c -R -p "$d" "$S/work/$b" ;; *) ln -s "$d" "$S/work/$b" ;; esac
    done
fi
echo "export MELEE_DECOMP=$S/decomp MELEE_DISC=$S/disc MELEE_WORK=$S/work DOLPHIN_USER=$S/dolphin-user"
