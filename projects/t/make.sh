#!/bin/bash
# make.sh: build *t* from scratch (run from the repo root): the cue sheet, the master, every frame, the final file.
#   bash projects/t/make.sh            everything
#   bash projects/t/make.sh video      frames + encode only (the audio already mastered)
# The film is frame(t) for t = 0 .. 30.000 (721 frames at 24 fps). The song's final hit lands 7 ms after the last frame, and
# that frame is held for 1.96 s while the hit rings out: the clock has stopped at t = 30.000.
set -euo pipefail
P=projects/t
if [ "${1:-}" != "video" ]; then
  # master: the song from 0.05 s (build_cues.py's HEAD) for 32 s. The intro (bars 1-4, a lone ticking clock at about
  # -41 LUFS short-term) is lifted 14 dB so it can be heard on a phone, easing back to unity in the 0.15 s before the drop;
  # the final hit rings out on its own (a 0.3 s fade only at the very end), and gain goes into two limiters (the second at 4x rate, for true peak),
  # to about -14 LUFS and under -1 dBTP.
  ffmpeg -v error -y -ss 0.05 -i $P/assets/song.mp3 -t 32.0 -af "volume='if(lt(t,7.85),5.012,if(lt(t,8.0),5.012-(t-7.85)/0.15*4.012,1))':eval=frame,afade=t=out:st=31.7:d=0.3,volume=-1.35dB,alimiter=limit=0.84:attack=3:release=60:level=false:asc=1,aresample=192000,alimiter=limit=0.87:attack=1:release=40:level=false,aresample=48000" -c:a pcm_s24le $P/assets/master.wav
  ffmpeg -hide_banner -i $P/assets/master.wav -af ebur128=peak=true -f null - 2>&1 | grep -E 'I:|Peak:' | tail -2
  .venv/bin/python $P/build_cues.py                  # the cue sheet, and the hills' loudness table from the master
fi
node engine/render.mjs $P --frames --workers=4 --clean --framesdir=$P/out/frames
ffmpeg -v error -y -framerate 24 -i $P/out/frames/f%05d.jpg -i $P/assets/master.wav \
  -vf "tpad=stop_mode=clone:stop_duration=1.96,scale=in_range=full:out_range=tv,format=yuv420p" -map 0:v -map 1:a \
  -c:v libx264 -preset slow -crf 17 -maxrate 14M -bufsize 28M -profile:v high -pix_fmt yuv420p -tune grain \
  -c:a aac -b:a 320k -ar 48000 -movflags +faststart -t 32.0 $P/out/t_vertical.mp4
ffprobe -v error -show_entries stream=codec_name,profile,width,height,pix_fmt,r_frame_rate,duration -of compact $P/out/t_vertical.mp4
