"""The standard review page (charkit/reviewpage.py) on a synthetic build (venv: run this file): the summary box first,
before any picture (Recommended, Asked of Michael, Key numbers), the design beside every build per view, a close-up
region at one scale, the numbers from each build's qa.json with flag checks marked, a sweep's table; the build folder
is only read."""
import json, os, sys, tempfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import preview as P, reviewpage


def fake_build(d, tone):
    """a build folder with a preview's page crops (heads at PPL_OUT px per L, full figures) and a qa.json."""
    os.makedirs(os.path.join(d, 'page'), exist_ok=True)
    os.makedirs(os.path.join(d, 'qa'), exist_ok=True)
    got = {}
    for v in ('front', 'three_quarter', 'profile', 'back'):
        h = int((P.WIN['up'] + P.WIN['down']) * P.PPL_OUT)
        img = np.full((h, int(2 * P.WIN['half'] * P.PPL_OUT), 3), tone)
        P._save(img, os.path.join(d, 'page', 'head_%s.png' % v))
        got['head_' + v] = 'page/head_%s.png' % v
    for az in P.BODY_AZ:
        P._save(np.full((P.BODY_H, 200, 3), tone), os.path.join(d, 'page', 'body_%03d.png' % az))
        got['body_%03d' % az] = 'page/body_%03d.png' % az
    json.dump(dict(got=got), open(os.path.join(d, 'page', 'crops.json'), 'w'))
    json.dump({'checks': {'x_flag': {'value': tone, 'status': 'PASS', 'flag': 'a flag'},
                          'y_plain': {'value': 2 * tone, 'status': 'WARN'}}}, open(os.path.join(d, 'qa', 'qa.json'), 'w'))
    return d


def test_page():
    with tempfile.TemporaryDirectory() as d:
        a, b = fake_build(os.path.join(d, 'a'), 0.3), fake_build(os.path.join(d, 'b'), 0.7)
        before = sorted(os.listdir(os.path.join(a, 'page')))
        sw = os.path.join(d, 'sw')
        os.makedirs(os.path.join(sw, 'control'))
        json.dump(dict(decl=dict(base=a, stage='qa', checks=['x_*']), commit='c', rows=[
            dict(name='control', control=True, set={}, checks={'x_flag': {'value': 0.3, 'status': 'PASS'}}),
            dict(name='v1', set={'k': 1}, checks={'x_flag': {'value': 0.5, 'status': 'WARN'}})], guard=[]),
            open(os.path.join(sw, 'sweep.json'), 'w'))
        spec = dict(title='T', summary=dict(recommended='take B', asked=['A or B?']),
                    builds=[dict(label='before', path=a), dict(label='after', path=b)], views=['front', 'profile'],
                    regions=['face'], checks=['x_*', 'y_*'], sweep=os.path.join(sw, 'sweep.json'))
        path = reviewpage.make(spec, os.path.join(d, 'page'), log=lambda *x: None)
        H = open(path).read()
        i_sum, i_img = H.index('class="box summary"'), H.index('<img')
        assert i_sum < i_img and 'take B' in H and 'A or B?' in H and 'Key numbers' in H
        assert H.index('Recommended') < H.index('Asked of Michael') < H.index('Key numbers')
        assert 'design (body_turnaround)' in H and H.count('>before<') >= 2 and '<h3>front</h3>' in H
        assert '<h3>back</h3>' not in H                                    # (views: front, profile only)
        assert 'cu_face_front_0.png' in H and 'cu_face_front_1.png' in H and 'cu_face_front_design.png' in H
        assert '<code>x_flag</code> <span class="k">[F]</span>' in H and '(+0.2)' in H
        assert sorted(os.listdir(os.path.join(a, 'page'))) == before       # (the build folder only read)
        # the close-ups share one scale: the design's and each build's crops of a region are the same size
        from PIL import Image
        sizes = {Image.open(os.path.join(d, 'page', 'img', f)).size for f in os.listdir(os.path.join(d, 'page', 'img'))
                 if f.startswith('cu_face_front_')}
        assert len(sizes) == 1, sizes


def test_table_section():
    from charkit import reviewpage
    h = reviewpage.table_section({'title': 'T <x>', 'columns': ['pose', 'value'],
                                  'rows': [['rest', ['0.5', 'FAIL']], ['a', 'b']]})
    assert '<h2>T &lt;x&gt;</h2>' in h and '<td class="FAIL">0.5</td>' in h and '<td>b</td>' in h


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)


def test_the_pages_design_is_the_builds_own_character():
    """the design's pictures were always Clawd's (preview.design_refs read her manifest): the page takes PAGE.json's
    'manifest', else its first build's (its resolved NAME.spec.json's ref.manifest)."""
    import json, tempfile
    from charkit import reviewpage
    d = tempfile.mkdtemp(prefix='charkit-rp-')
    json.dump({'name': 'x', 'ref': {'manifest': 'somewhere/manifest.json'}}, open(os.path.join(d, 'x.spec.json'), 'w'))
    assert reviewpage.manifest_of(d) == 'somewhere/manifest.json'
    assert reviewpage.manifest_of(tempfile.mkdtemp(prefix='charkit-rp-')) is None
