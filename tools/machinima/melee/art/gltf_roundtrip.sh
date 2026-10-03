#!/bin/sh
# gltf_roundtrip.sh RIG.json OUTDIR [HIGH.gltf] [LOW.gltf]: import a glTF costume the way fighter-build does (datkit
# gltf-model), export the result back to glTF, and compare the two numerically (gltf_compare.py) and for GPU alignment
# (gxalign.py). Without HIGH/LOW, rig.json's "model" names them. Outputs (derived data) go to OUTDIR. CMPARGS passes
# options to gltf_compare.py (e.g. --wmap NewJoint=J29 for a joint the rig doesn't have yet).
#   tools/machinima/melee/art/gltf_roundtrip.sh ~/games/melee/work/rig/rig.json ~/games/melee/work/art/import/geno geno.gltf geno_low.gltf
set -e
ROOT=$(cd "$(dirname "$0")/../../../.." && pwd)
PY=${PY:-$ROOT/.venv/bin/python}; [ -x "$PY" ] || PY=$HOME/animation-pipeline/.venv/bin/python
DK="$ROOT/tools/machinima/melee/datkit.sh"
RIG=$1; OUT=$2; HIGH=$3; LOW=$4
mkdir -p "$OUT/back"
ARGS=""; [ -n "$HIGH" ] && ARGS="--high $HIGH --eyes"; [ -n "$LOW" ] && ARGS="$ARGS --low $LOW"
$DK gltf-model "$RIG" "$OUT/PlXxNr.dat" $ARGS > "$OUT/import.txt"
grep -vE '^  (d[0-9]|[^ ].*: [0-9]+x[0-9]+ )' "$OUT/import.txt" || true
if [ -z "$HIGH" ]; then
  HIGH=$($PY -c "import json,os,sys; r=json.load(open(sys.argv[1])); print(os.path.expanduser(r['model']['high']))" "$RIG")
  LOW=$($PY -c "import json,os,sys; r=json.load(open(sys.argv[1])); print(os.path.expanduser(r['model'].get('low') or ''))" "$RIG")
fi
python3 "$ROOT/projects/geno/menus/gxalign.py" "$OUT/PlXxNr.dat"
# the file has no fighter data: the lookups printed by gltf-model say which DObjs are high and low
LU=$(grep '^lookups:' "$OUT/import.txt")
HI=$($PY -c "import json,sys; s=sys.argv[1]; h=json.loads(s.split(' high ')[1].split(' low ')[0]); print(','.join(str(i) for g in h for o in g for i in o))" "$LU")
$DK export "$OUT/PlXxNr.dat" "$OUT/back/high.gltf" --dobjs "$HI" | tail -1
$PY "$ROOT/tools/machinima/melee/art/gltf_compare.py" "$HIGH" "$OUT/back/high.gltf" --rig "$RIG" --json "$OUT/compare_high.json" $CMPARGS | tail -1
if [ -n "$LOW" ]; then
  LO=$($PY -c "import json,sys; s=sys.argv[1]; h=json.loads(s.split(' low ')[1].split(' eyes ')[0]); print(','.join(str(i) for g in h for o in g for i in o))" "$LU")
  $DK export "$OUT/PlXxNr.dat" "$OUT/back/low.gltf" --dobjs "$LO" | tail -1
  $PY "$ROOT/tools/machinima/melee/art/gltf_compare.py" "$LOW" "$OUT/back/low.gltf" --rig "$RIG" --json "$OUT/compare_low.json" $CMPARGS | tail -1
fi
