#!/bin/sh
# measure.sh [OUT]: datkit meshstats for every fighter's costume-0 model, plus attrs.csv (ModelScale), then castspec.py.
# OUT defaults to ~/games/melee/work/art/spec (game-derived data: never commit it).
set -e
H="$(cd "$(dirname "$0")" && pwd)"; DK="$H/../datkit/dk"; D="${DISC:-$HOME/games/melee/disc/files}"; O="${1:-$HOME/games/melee/work/art/spec}"
mkdir -p "$O/stats" "$O/tex"
for kv in Mr:0 Fx:1 Ca:2 Dk:3 Kb:4 Kp:5 Lk:6 Sk:7 Ns:8 Pe:9 Pp:10 Nn:11 Pk:12 Ss:13 Ys:14 Pr:15 Mt:16 Lg:17 Ms:18 Zd:19 Cl:20 Dr:21 Fc:22 Pc:23 Gw:24 Gn:25 Fe:26; do
  c=${kv%%:*}; k=${kv##*:}; mkdir -p "$O/tex/$c"
  "$DK" meshstats "$D/Pl${c}Nr.dat" --ft "$D/Pl$c.dat" --co "$D/PlCo.dat" --kind $k --texdir "$O/tex/$c" > "$O/stats/$c.json"
done
if [ -f "$D/PlGeNr.dat" ]; then mkdir -p "$O/tex/Ge"; "$DK" meshstats "$D/PlGeNr.dat" --ft "$D/PlGe.dat" --rig "${MELEE_WORK:-$HOME/games/melee/work}/rig/rig.json" --texdir "$O/tex/Ge" > "$O/stats/Ge.json"; fi
"$DK" attrs $(for c in Mr Fx Ca Dk Kb Kp Lk Sk Ns Pe Pp Nn Pk Ss Ys Pr Mt Lg Ms Zd Cl Dr Fc Pc Gw Gn Fe; do echo "$D/Pl$c.dat"; done) $( [ -f "$D/PlGe.dat" ] && echo "$D/PlGe.dat") > "$O/stats/attrs.csv"
"${PY:-$HOME/animation-pipeline/.venv/bin/python}" "$H/castspec.py" "$O/stats" --out "$O/summary.json"
