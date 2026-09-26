"""Rebuild the retargeted curves of every motion-capture phrase listed in a film's refs/mocap/phrases.json (tools/retarget_mocap.py
with each phrase's bars, anchors and tail).
    .venv/bin/python tools/mocap_phrases.py projects/<film> [name ...]
"""
import json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
proj = sys.argv[1]; only = sys.argv[2:]; M = os.path.join(proj, 'refs', 'mocap')
for ph in json.load(open(os.path.join(M, 'phrases.json')))['phrases']:
    if only and ph['name'] not in only: continue
    cmd = [os.path.join(ROOT, '.venv', 'bin', 'python'), os.path.join(ROOT, 'tools', 'retarget_mocap.py'), os.path.join(M, ph['name'] + '_pose.json'),
           os.path.join(M, ph['name'] + '_rig.json'), '--bar0', str(ph['bar0']), '--bars', str(ph['bars'])]
    if ph.get('anchors'): cmd += ['--anchors', ph['anchors']]
    if ph.get('tail'): cmd += ['--tail', ph['tail']]
    r = subprocess.run(cmd, capture_output=True, text=True)
    print(ph['name'], 'ok' if r.returncode == 0 else 'FAILED\n' + r.stderr[-800:])
