"""charkit.preview: the QA tally against the previous preview, the close-ups' projection (the eye line and the scale),
the previous preview's choice and the post-merge hook (venv: run this file, or pytest)."""
import json, os, subprocess, sys, tempfile, time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import preview


def _qa(**c):
    return {'checks': {k: {'value': v, 'status': s} for k, (v, s) in c.items()}}


def test_tally_lists_the_status_changes():
    prev = _qa(a=(1, 'FAIL'), b=(2, 'PASS'), c=(3, 'WARN'), d=(4, 'PASS'), e=(5, 'INFO'), f=(6, 'FAIL'), g=(0.5, 'WARN'))
    cur = _qa(a=(1.1, 'PASS'), b=(2.2, 'FAIL'), c=(3, 'WARN'), e=(5, 'INFO'), f=(6.1, 'WARN'), g=(0.4, 'FAIL'), h=(1, 'PASS'))
    T = preview.tally(cur, prev, {'g': 'remeasured', 'c': 'remeasured'})
    assert T['changes'] == {'FAIL -> PASS': ['a'], 'PASS -> FAIL': ['b'], 'FAIL -> WARN': ['f'], 'WARN -> FAIL': ['g']}
    assert T['improved'] == ['a', 'f'] and T['regressed'] == ['b', 'g'] and T['new'] == ['h'] and T['gone'] == ['d']
    assert T['fails'] == ['b', 'g'] and T['counts']['PASS'] == 2 and T['prev_counts']['FAIL'] == 2
    assert T['remeasured'] == ['g']                          # c's step changed nothing between the two
    assert 'changes' not in preview.tally(cur)               # the first preview: counts only


def test_head_crop_keeps_the_eye_line_and_the_scale():
    """a picture at 400 px per L with a mark on the eye line and one 0.5 L under it comes out at PPL_OUT px per L with
    the eye line WIN['up'] L from the top: our board and the design are cut the same way."""
    ppl, H, W = 400.0, 960, 960
    img = np.full((H, W, 3), 0.9)
    eye = H / 2
    img[int(eye) - 2:int(eye) + 2, 380:580] = 0.1            # the eye line
    img[int(eye + 0.5 * ppl) - 2:int(eye + 0.5 * ppl) + 2, 380:580] = 0.1
    img[int(eye - 1.0 * ppl):int(eye + 0.3 * ppl), 430:530] = 0.3   # the head's columns
    out = preview.head_crop(img, eye, ppl)
    P = preview.PPL_OUT
    assert out.shape[:2] == (round((preview.WIN['up'] + preview.WIN['down']) * P), round(2 * preview.WIN['half'] * P))
    dark = np.nonzero((out[:, :, 0] < 0.2).any(1))[0]
    rows = [dark[0], dark[-1]]
    assert abs(rows[0] - preview.WIN['up'] * P) <= 2 and abs(rows[1] - (preview.WIN['up'] + 0.5) * P) <= 2, rows
    cols = np.nonzero((out[:, :, 0] < 0.5).any(0))[0]
    assert abs((cols[0] + cols[-1]) / 2 - out.shape[1] / 2) <= 2          # centred on the head


def test_figure_crop_matches_heights():
    a = np.full((1000, 600, 3), 0.9); a[100:900, 250:350] = 0.2
    b = np.full((500, 400, 3), 0.9); b[50:250, 100:200] = 0.2
    assert preview.figure_crop(a).shape[0] == preview.figure_crop(b).shape[0] == preview.BODY_H


def _repo():
    d = tempfile.mkdtemp()
    g = lambda *a: subprocess.run(['git', *a], cwd=d, capture_output=True, text=True, check=True).stdout.strip()
    g('init', '-q', '-b', 'main'); g('config', 'user.email', 't@t'); g('config', 'user.name', 't')
    g('config', 'extensions.worktreeConfig', 'true')
    for i in range(3):
        open(os.path.join(d, 'f%d' % i), 'w').write(str(i)); g('add', '.'); g('commit', '-qm', 'c%d' % i)
    return d, g


def test_previous_is_the_newest_ancestor_preview():
    d, g = _repo()
    shas = g('rev-list', '--reverse', 'HEAD').split()
    g('checkout', '-qb', 'side', shas[0]); open(os.path.join(d, 's'), 'w').write('s'); g('add', '.'); g('commit', '-qm', 's')
    side = g('rev-parse', 'HEAD')
    out = os.path.join(d, 'previews')
    old_out, old_root = preview.OUT, preview.ROOT
    try:
        preview.OUT, preview.ROOT = out, d
        for i, s in enumerate([shas[0], side, shas[1]]):
            os.makedirs(os.path.join(out, s[:7], 'qa')); json.dump(_qa(), open(os.path.join(out, s[:7], 'qa', 'qa.json'), 'w'))
            preview._record(dict(sha=s, short=s[:7], t='2026-09-30T0%d:00:00' % i))
        assert preview.previous(shas[2])['sha'] == shas[1]          # not the side branch's, though it's as new
        assert preview.previous(shas[1])['sha'] == shas[0]
        assert preview.previous(shas[0])['sha'] == shas[1]          # no ancestor: the newest other
    finally:
        preview.OUT, preview.ROOT = old_out, old_root


def test_the_hook_runs_in_the_background_on_its_branch_only():
    d, g = _repo()
    log = os.path.join(d, 'charkit', 'out', 'previews', 'hook.log')
    p = preview.hook('install', 'main', cwd=d, py='/bin/echo')
    assert os.access(p, os.X_OK) and g('config', '--worktree', '--get', 'core.hooksPath') == os.path.dirname(p)
    assert preview.hook('status', cwd=d) == p
    g('checkout', '-qb', 'topic'); open(os.path.join(d, 't'), 'w').write('t'); g('add', 't'); g('commit', '-qm', 't')
    g('checkout', '-q', 'main')
    t = time.time()
    g('merge', '-q', '--no-ff', '-m', 'merge topic', 'topic')        # the hook: backgrounded, the merge doesn't wait
    assert time.time() - t < 5
    for _ in range(50):
        if os.path.exists(log) and open(log).read().strip():
            break
        time.sleep(0.1)
    assert open(log).read().split() == ['-m', 'charkit', 'preview', '--tip', 'main']
    os.remove(log)
    g('checkout', '-q', 'topic'); g('merge', '-q', '--no-ff', '-m', 'back', 'main')      # another branch: nothing
    time.sleep(0.3)
    assert not os.path.exists(log)
    preview.hook('remove', cwd=d)
    assert preview.hook('status', cwd=d) is None


def test_the_hooks_preview_never_touches_the_hooked_worktree():
    """git exports GIT_DIR, GIT_INDEX_FILE and more to a hook's processes; a git command run with them acts on the
    hooked repository whatever its cwd. The preview's checkout in its own worktree once detached pipeline-3d's HEAD
    (2026-09-30). The hook unsets them, and preview._git drops them itself."""
    d, g = _repo()
    other = tempfile.mkdtemp() + '/wt'
    g('worktree', 'add', '-q', '--detach', other, 'main')
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    done = os.path.join(d, 'stub.done')
    stub = os.path.join(d, 'stub.sh')
    # the hook's "python": records the git variables it was given, then does what build_worktree does (a forced
    # detached checkout in another worktree) through preview._git with GIT_DIR pointing at the hooked repository
    open(stub, 'w').write('#!/bin/sh\nenv | grep "^GIT_" > %s.env\n'
                          'GIT_DIR=%s/.git GIT_INDEX_FILE=%s/.git/index %s -c "import sys; sys.path.insert(0, %r); '
                          'from charkit import preview; preview._git(\'checkout\', \'-q\', \'-f\', \'--detach\', '
                          '\'topic\', cwd=%r)"\ntouch %s\n' % (done, d, d, sys.executable, root, other, done))
    os.chmod(stub, 0o755)
    preview.hook('install', 'main', cwd=d, py=stub)
    g('checkout', '-qb', 'topic'); open(os.path.join(d, 't'), 'w').write('t'); g('add', 't'); g('commit', '-qm', 't')
    g('checkout', '-q', 'main')
    g('merge', '-q', '--no-ff', '-m', 'merge topic', 'topic')
    head = g('rev-parse', 'HEAD')
    for _ in range(100):
        if os.path.exists(done):
            break
        time.sleep(0.1)
    assert os.path.exists(done), open(os.path.join(d, 'charkit', 'out', 'previews', 'hook.log')).read()
    seen = open(done + '.env').read().split()
    assert not [v for v in seen if v.split('=')[0] in preview.GIT_HOOK_ENV], seen
    # the hooked worktree: still on main at the merge; the other worktree: detached at topic
    assert g('rev-parse', '--abbrev-ref', 'HEAD') == 'main' and g('rev-parse', 'HEAD') == head
    assert g('status', '--porcelain', '--untracked-files=no') == ''
    og = lambda *a: subprocess.run(['git', *a], cwd=other, capture_output=True, text=True).stdout.strip()
    assert og('rev-parse', '--abbrev-ref', 'HEAD') == 'HEAD' and og('rev-parse', 'HEAD') == g('rev-parse', 'topic')
    preview.hook('remove', cwd=d)


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
