#!/bin/zsh
# encode.sh OUTDIR : post the rendered frames, cut the song under them (song time from OUTDIR/shot.json), encode an mp4.
set -e
out=$1
here=${0:A:h}
py=~/animation-pipeline/.venv/bin/python
t0=$($py -c "import json;print(json.load(open('$out/shot.json'))['song_t0'])")
n=$($py -c "import json;print(json.load(open('$out/shot.json'))['frames'])")
fps=$($py -c "import json;print(json.load(open('$out/shot.json'))['fps'])")
$py $here/../build/post.py $out/frames $out/post --aux $out/aux --feat $out/feat
dur=$($py -c "print($n/$fps)")
ffmpeg -loglevel error -y -framerate $fps -i $out/post/%04d.png -ss $t0 -t $dur -i ~/animation-pipeline/projects/tsuzuku/assets/song.wav \
  -map 0:v -map 1:a -c:v libx264 -preset slow -crf 16 -pix_fmt yuv420p -c:a aac -b:a 256k -af "afade=t=in:d=0.3,afade=t=out:st=$($py -c "print($dur-0.5)"):d=0.5" \
  -movflags +faststart $out/$(basename $out).mp4
ffprobe -v error -show_entries format=duration -of csv=p=0 $out/$(basename $out).mp4
