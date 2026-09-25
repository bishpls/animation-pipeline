cd ~/animation-pipeline; V=projects/tsuzuku/voice/spoken; mkdir -p $V/conv
for f in $V/f_*.mp3; do n=$(basename $f .mp3); [ -f $V/conv/$n.wav ] || .venv/bin/python tools/revoice.py $f projects/tsuzuku/voice/REF_fable.wav $V/conv/$n.wav --steps 30; done
for f in $V/c_*.mp3; do n=$(basename $f .mp3); [ -f $V/conv/$n.wav ] || .venv/bin/python tools/revoice.py $f projects/tsuzuku/voice/REF_clawd.wav $V/conv/$n.wav --steps 30; done
ls $V/conv
