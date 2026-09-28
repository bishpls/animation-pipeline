"""Screen SO BACK's song takes against its locked skeleton with tools/songscreen.py: 150 BPM, a downbeat alignable to 0.05,
the drop on bar 9 (12.85 once seated), a key the vocals can be re-tuned to (C minor), and the cold open's harshness (take c4
was "very harsh"; take f3 was chosen by ear).
    .venv/bin/python projects/so-back/song/screen.py c4 f3 ..."""
import os, subprocess, sys
T = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'tools', 'songscreen.py')
takes = [f'projects/so-back/assets/takes/{t}.mp3' for t in sys.argv[1:]]
subprocess.run([sys.executable, T, *takes, '--bpm', '150', '--phase', 'open:0-3.1,drop:12.9-19.2,drop2:19.2-25.5',
                '--drop-window', '11.5-15', '--keys', 'open:0-3.1,over:3.3-9.5,drop:12.9-25.5', '--harsh', '0-3'], check=True)
