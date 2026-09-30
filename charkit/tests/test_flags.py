"""charkit.flags (review flags) and charkit.preview's crop maps: a mark on a board lands where the crop's map says; a flag
on a crop is anchored on its board and shows on the board's other pictures; edits and deletes keep flags.jsonl to the
live flags (flags.log.jsonl keeps all); the part is null, with the reason, where no ID pass exists; the HTTP API round
trips (venv: run this file)."""
import json, os, shutil, sys, tempfile, threading, urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import numpy as np
from charkit import flags, preview


def _board(path, W=600, H=1000):
    """a synthetic body board: a flat background, a figure (a rectangle) and a red mark at (400, 300)."""
    from PIL import Image
    a = np.full((H, W, 3), 0.94)
    a[100:950, 200:420] = (0.8, 0.45, 0.3)
    a[298:303, 398:403] = (1.0, 0.0, 0.0)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Image.fromarray((a * 255).astype(np.uint8)).save(path)
    return a


def _setup():
    flags.OUT = tempfile.mkdtemp()
    flags._maps.clear()
    flags._ids.clear()
    d = os.path.join(flags.OUT, 'abc1234')
    rgb = _board(os.path.join(d, 'boards', 'body_000.png'))
    json.dump(dict(sha='abc1234' + '0' * 33), open(os.path.join(d, 'preview.json'), 'w'))
    crop, mp = preview.figure_crop(rgb, want_map=True)
    os.makedirs(os.path.join(d, 'page'))
    preview._save(crop, os.path.join(d, 'page', 'body_000.png'))
    json.dump(dict(got={}, maps={'body_000': dict(mp, src='boards/body_000.png')}),
              open(os.path.join(d, 'page', 'crops.json'), 'w'))
    return d, crop, mp


def test_crop_map_puts_a_board_mark_where_it_is():
    d, crop, mp = _setup()
    red = (crop[..., 0] > 0.8) & (crop[..., 1] < 0.3)
    ys, xs = np.nonzero(red)
    cx, cy = xs.mean() + 0.5, ys.mean() + 0.5                     # the mark's centre in the crop (pixel centres)
    bx, by = flags.to_board(mp, [cx, cy])[0]
    assert abs(bx - 400.5) < 1.5 and abs(by - 300.5) < 1.5, (bx, by)
    back = flags.from_board(mp, [bx, by])[0]
    assert abs(back[0] - cx) < 0.2 and abs(back[1] - cy) < 0.2
    # head_crop's map the same way: a mark 0.3 L right of centre on the eye line of a design-board-like picture
    a = np.full((960, 960, 3), 0.8)
    a[478:483, 598:603] = (1.0, 0.0, 0.0)
    hc, hm = preview.head_crop(a, 480, 400, want_map=True)
    ys, xs = np.nonzero((hc[..., 0] > 0.9) & (hc[..., 1] < 0.4))
    bx, by = flags.to_board(hm, [xs.mean() + 0.5, ys.mean() + 0.5])[0]
    assert abs(bx - 600.5) < 1.5 and abs(by - 480.5) < 1.5, (bx, by)


def test_add_edit_delete_and_view():
    d, crop, mp = _setup()
    f = flags.add(dict(image='abc1234/page/body_000.png', px=[50, 60], severity=3, note='  the hem  '))
    assert f['board'] == 'body_000' and f['view'] == 'front' and f['az'] == 0 and f['note'] == 'the hem'
    assert f['board_px'] == [round(mp['x0'] + 50 * mp['sx'], 1), round(mp['y0'] + 60 * mp['sy'], 1)]
    assert f['part'] is None and 'pruned' in f['part_source']          # no bundle here
    g = flags.add(dict(image='abc1234/boards/body_000.png', box=[420, 500, 380, 450], severity=0, note='good'))
    assert g['box'] == [380, 450, 420, 500] and g['board_box'] == [380, 450, 420, 500]
    h = flags.add(dict(image='abc1234/boards/face_000.png', px=[1, 2], severity=1))
    assert h['part'] is None and 'perspective' in h['part_source']
    for bad in (dict(image='abc1234/boards/body_000.png', severity=2), dict(image='abc1234/boards/body_000.png', px=[1, 2],
                                                                            severity=5)):
        try:
            flags.add(bad)
            assert False, bad
        except ValueError:
            pass
    v = flags.view(['abc1234/boards/body_000.png', 'abc1234/page/body_000.png'])
    on_board = {x['id']: x['at'] for x in v['abc1234/boards/body_000.png']['flags']}
    on_crop = {x['id']: x['at'] for x in v['abc1234/page/body_000.png']['flags']}
    assert set(on_board) == set(on_crop) == {f['id'], g['id']}
    assert on_crop[f['id']]['px'] == [50.0, 60.0] and on_board[f['id']]['px'] == f['board_px']
    assert abs(on_crop[g['id']]['box'][0] - (380 - mp['x0']) / mp['sx']) < 0.1
    e = flags.edit(f['id'], dict(severity=1, note='the hem, minor'))
    assert e['severity'] == 1 and e['severity_name'] == 'minor' and e.get('edited')
    flags.delete(g['id'])
    live = flags.load()
    assert [x['id'] for x in live] == [f['id'], h['id']] and live[0]['note'] == 'the hem, minor'
    log = [json.loads(l)['op'] for l in open(os.path.join(flags.OUT, 'flags.log.jsonl'))]
    assert log == ['add', 'add', 'add', 'edit', 'delete']
    try:
        flags.delete('nope')
        assert False
    except KeyError:
        pass


def test_http_api():
    d, crop, mp = _setup()
    srv = flags.ThreadingHTTPServer(('127.0.0.1', 0), flags.Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    U = 'http://127.0.0.1:%d' % srv.server_address[1]

    def call(method, path, body=None):
        req = urllib.request.Request(U + path, method=method, data=None if body is None else json.dumps(body).encode(),
                                     headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()
    try:
        s, b = call('POST', '/api/flags', dict(image='abc1234/page/body_000.png', px=[10, 20], severity=2, note='x'))
        assert s == 201 and json.loads(b)['board'] == 'body_000'
        fid = json.loads(b)['id']
        s, b = call('POST', '/api/flags/' + fid, dict(note='y'))
        assert s == 200 and json.loads(b)['note'] == 'y'
        s, b = call('POST', '/api/flags', dict(image='abc1234/page/body_000.png', px=[1, 1], severity=9))
        assert s == 400
        # a page gets the flag tools whether or not it names them; the page itself is unchanged otherwise
        open(os.path.join(d, 'review.html'), 'w').write('<!doctype html><p>hi</p>')
        s, b = call('GET', '/abc1234/review.html')
        assert s == 200 and b.startswith(b'<!doctype html><p>hi</p>') and b'/flags.js' in b
        s, b = call('GET', '/flags.js')
        assert s == 200 and b'charkit review flags' in b
        s, b = call('GET', '/abc1234/boards/body_000.png')
        assert s == 200 and b[:4] == b'\x89PNG'
        s, b = call('DELETE', '/api/flags/' + fid)
        assert s == 200 and flags.load() == []
        s, b = call('GET', '/../../etc/passwd')
        assert s == 404 or b'root:' not in b
    finally:
        srv.shutdown()


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
