"""Cross-view links as data: the labelling task's proposals (the agent's) or Michael's answers (the held-out truth) ->
{"links": {item: {"family", "home", "views": {view: [region ids] ([] not visible)}, "unsure": [views]}}}.

    python tools/hairident/links.py TASK.json OUT.json [--answers ANSWERS.json]
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)


def family(rid, info=None):
    if rid.startswith('T:'):
        return rid[2:].split('/', 1)[0]
    return 'side_locks' if not info or '(lower_back)' not in info else 'lower_back'


def make(task, answers=None):
    out = {}
    for it in task['items']:
        hv = it['home']['view']
        info = (task['regions'][hv].get('info') or {}) if isinstance(task['regions'][hv], dict) else {}
        q = dict(family=family(it['home']['regions'][0], info.get(it['home']['regions'][0])), home=hv,
                 views={hv: list(it['home']['regions'])}, unsure=[], number=it['number'], title=it.get('title'))
        rec = (answers or {}).get('items', {}).get(it['id'], {}) if answers else None
        for vn, p in (it.get('proposals') or {}).items():
            if answers is None:
                q['views'][vn] = list(p.get('regions') or [])
                continue
            a = (rec or {}).get('views', {}).get(vn)
            if a is None or a['verdict'] == 'unsure':
                q['unsure' if a else 'unanswered'] = q.get('unsure' if a else 'unanswered', []) + [vn]
                continue
            q['views'][vn] = [] if a['verdict'] == 'hidden' else list(a['regions'])
        out[it['id']] = q
    return dict(source='answers' if answers else 'proposals', links=out)


if __name__ == '__main__':
    a = sys.argv[1:]
    task = json.load(open(a[0]))
    ans = json.load(open(a[a.index('--answers') + 1])) if '--answers' in a else None
    json.dump(make(task, ans), open(a[1], 'w'), indent=1)
    print('wrote', a[1])
