#!/bin/bash
# FRAME PERFECT's mix: the song, and under it the game's own sound (hits, shines, footsteps), sample-locked to the plates by
# tools/machinima/plates.py (game.wav, cut between the director's slate clicks). Mastered like the other films: gain into a
# limiter, about -14 LUFS, -1 dBTP.   bash projects/frame-perfect/mix.sh [game_db]
set -euo pipefail
P=$(cd "$(dirname "$0")" && pwd)
GAME_DB=${1:--4}
ffmpeg -loglevel error -y -i "$P/assets/song.wav" -i "$P/assets/plates/game.wav" -filter_complex \
  "[0:a]aresample=48000,pan=stereo|c0=c0|c1=c1[s];[1:a]aresample=48000,pan=stereo|c0=c0|c1=c1,volume=${GAME_DB}dB[g];[s][g]amix=inputs=2:normalize=0:duration=first[m]" \
  -map "[m]" -c:a pcm_s24le "$P/assets/mix_raw.wav"
I=$(ffmpeg -hide_banner -i "$P/assets/mix_raw.wav" -af ebur128 -f null - 2>&1 | awk '/I:/{v=$2} END{print v}')
G=$(python3 -c "print(round(-14.0 - float('$I') + 0.3, 2))")
ffmpeg -loglevel error -y -i "$P/assets/mix_raw.wav" -af "volume=${G}dB,alimiter=limit=0.89:level=false" -c:a pcm_s24le "$P/assets/mix.wav"
ffmpeg -hide_banner -i "$P/assets/mix.wav" -af ebur128=peak=true -f null - 2>&1 | grep -E '^\s+(I|Peak):' | tr -s ' '
