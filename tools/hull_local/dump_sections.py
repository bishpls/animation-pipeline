"""the authored head's sections (charkit.code_base.head_sections: what the hull's face carve reads) from a worktree's
code, saved for the locality lab (hull_local/locality.py), so two trees' heads can carve one hull code.
    python tools/hull_local/dump_sections.py WORKTREE OUT.npz [SPEC]"""
import contextlib, io, json, os, sys
root, out = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
spec_path = sys.argv[3] if len(sys.argv) > 3 else 'charkit/spec/clawd.json'
sys.path.insert(0, root)
os.chdir(root)
import numpy as np
from charkit import bodyeval, code_base
spec = bodyeval.resolve(spec_path)
spec.pop('head_code', None)
with contextlib.redirect_stdout(io.StringIO()):
    S, C, rep = code_base.head_sections(spec, log=lambda *a: None)
import subprocess
head = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=root, capture_output=True, text=True).stdout.strip()
np.savez(out, zs=S.zs, cy=S.cy, r=S.r, root=root, head=head)
print('%s (%s): %d sections -> %s' % (root, head, len(S.zs), out))
