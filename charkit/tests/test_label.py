"""charkit.label: the labelling page's server saves every answer at once, resumes, and undoes (tool/hairident)."""
import json, os, threading, urllib.request

import numpy as np
import pytest
from PIL import Image

from charkit import label


def _task(tmp_path):
    img = np.full((40, 60, 3), 200, np.uint8)
    for v in ('front', 'side'):
        Image.fromarray(img).save(tmp_path / ('%s.png' % v))
    idx = np.zeros((40, 60), np.uint8)
    idx[5:20, 5:25] = 1
    idx[5:20, 30:55] = 2
    idx[25:35, 10:50] = 3
    Image.fromarray(idx).save(tmp_path / 'side_regions.png')
    T = dict(format=label.TASK_FORMAT, id='t', title='test', summary=dict(asked='a', minutes=1, used_for='b'),
             views=[dict(id='front', name='Front', image='front.png'), dict(id='side', name='Side', image='side.png')],
             regions=dict(front=[dict(id='A', polygon=[[5, 5], [25, 5], [25, 20], [5, 20]]),
                                 dict(id='B', polygon=[[30, 5], [55, 5], [55, 20], [30, 20]])],
                          side=dict(mask='side_regions.png', ids=['a', 'b', 'c'])),
             items=[dict(id='i1', number=1, group='g', home=dict(view='front', regions=['A']),
                         proposals=dict(side=dict(regions=['a'], confidence=0.9, reason='r'))),
                    dict(id='i2', number=2, group='g', home=dict(view='front', regions=['B']),
                         proposals=dict(side=dict(regions=[], confidence=0.8, reason='hidden')))])
    p = tmp_path / 'task.json'
    p.write_text(json.dumps(T))
    return str(p)


def test_mask_regions_traced(tmp_path):
    T = label.load_task(_task(tmp_path))
    side = {r['id']: r for r in T['regions']['side']}
    assert set(side) == {'a', 'b', 'c'}
    x0, y0, x1, y1 = side['a']['bbox']
    # pixel corners, within the outline's simplification
    assert np.allclose((x0, y0, x1, y1), (5, 5, 25, 20), atol=label.SIMPLIFY_PX)
    assert side['a']['area'] == 15 * 20
    assert 5 < side['a']['anchor'][0] < 25 and 5 < side['a']['anchor'][1] < 20


def test_bad_task_refused(tmp_path):
    p = _task(tmp_path)
    T = json.load(open(p))
    T['items'][0]['proposals']['side']['regions'] = ['zz']
    open(p, 'w').write(json.dumps(T))
    with pytest.raises(SystemExit):
        label.load_task(p)


def test_store_answers_resume_undo(tmp_path):
    p = _task(tmp_path)
    T = label.load_task(p)
    S = label.Store(T)
    assert S.resume_at() == 'i1'
    S.answer('i1', 'side', 'fixed', ['b'], seconds=3.2)
    on_disk = json.load(open(S.path))                      # saved at once
    assert on_disk['items']['i1']['views']['side'] == dict(verdict='fixed', regions=['b'],
                                                           t=on_disk['items']['i1']['views']['side']['t'])
    assert on_disk['items']['i1']['status'] == 'done'
    assert not [f for f in os.listdir(tmp_path) if f.endswith('.tmp')]     # the atomic write left nothing behind
    # a fresh store (the page reopened) resumes at the first open item
    S2 = label.Store(T)
    assert S2.resume_at() == 'i2'
    S2.accept_all('i2')
    assert S2.snapshot()['items']['i2']['views']['side']['verdict'] == 'accept'
    assert label.links(T, S2.snapshot())['i2']['side'] is None            # the accepted proposal: not visible
    A, touched = S2.undo()
    assert touched == 'i2' and A['items']['i2']['views'] == {} and A['items']['i2']['status'] == 'open'
    A, touched = S2.undo()
    assert touched == 'i1' and A['items']['i1']['views'] == {}
    assert len(json.load(open(S2.path))['undone']) == 2
    assert label.Store(T).resume_at() == 'i1'
    with pytest.raises(ValueError):
        S2.answer('i1', 'front', 'accept')                 # the home view isn't answered
    with pytest.raises(ValueError):
        S2.answer('i1', 'side', 'fixed', ['zz'])


def test_skip_and_reanswer(tmp_path):
    T = label.load_task(_task(tmp_path))
    S = label.Store(T)
    S.skip('i1')
    assert S.resume_at() == 'i2'
    S.answer('i1', 'side', 'unsure')
    rec = S.snapshot()['items']['i1']
    assert rec['status'] == 'done' and rec['views']['side']['verdict'] == 'unsure'
    assert label.progress(T, S.snapshot())['unsure'] == ['i1']


def test_server_roundtrip(tmp_path):
    p = _task(tmp_path)
    srv, store = label.make_server(p, port=0)
    assert srv.server_address[0] == '127.0.0.1'
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    base = 'http://127.0.0.1:%d' % srv.server_address[1]

    def post(path, body):
        rq = urllib.request.Request(base + path, json.dumps(body).encode(), {'Content-Type': 'application/json'})
        return json.load(urllib.request.urlopen(rq))
    try:
        page = urllib.request.urlopen(base + '/').read().decode()
        assert '<title>test</title>' in page
        t = json.load(urllib.request.urlopen(base + '/api/task'))
        assert 'path' not in t and t['views'][0]['src'] == '/img/front'
        assert urllib.request.urlopen(base + '/img/side').read()[:4] == b'\x89PNG'
        r = post('/api/answer', dict(item='i1', view='side', verdict='accept', seconds=1.0))
        assert r['answers']['items']['i1']['views']['side']['regions'] == ['a']
        assert json.load(open(store.path))['items']['i1']['status'] == 'done'
        r = post('/api/undo', {})
        assert r['touched'] == 'i1' and r['answers']['items']['i1']['views'] == {}
        try:
            post('/api/answer', dict(item='i1', view='side', verdict='nope'))
            assert False
        except urllib.error.HTTPError as e:
            assert e.code == 400
        with pytest.raises(urllib.error.HTTPError):
            urllib.request.urlopen(base + '/img/../task.json')
    finally:
        srv.shutdown()
