"""Production numbers for a film in this repo, reproducibly (no guesses): Claude token usage from the Claude Code session
transcripts, paid API calls from tools/ledger.jsonl, git activity, and asset counts. Reads numbers only: no transcript text,
keys or personal data are copied into the output.

    .venv/bin/python tools/production_stats.py [--film tsuzuku] [--out projects/tsuzuku/docs/making-of/stats.json]

Transcripts: ~/.claude/projects/-Users-michaelbishop-animation-pipeline/*.jsonl (one per main session) and <session>/subagents/*.jsonl.
Each assistant API response is counted once (streamed responses repeat the same message id and usage on several lines; the
largest output count per id is kept). A session that also made earlier films is split at the film's kickoff time (--since).
"""
import json, os, re, subprocess, sys, collections, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
a = sys.argv[1:]
opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
FILM = opt('--film', 'tsuzuku')
OUT = opt('--out', os.path.join(ROOT, 'projects', FILM, 'docs', 'making-of', 'stats.json'))
TDIR = os.path.expanduser(opt('--transcripts', '~/.claude/projects/-Users-michaelbishop-animation-pipeline'))
# TSUZUKU's kickoff: the first message proposing Op. 2 in the main session (UTC); everything before it made the earlier films
SINCE = opt('--since', '2026-09-25T06:32:00Z')
SESSIONS = {'7c22d831-c4d1-4516-b6ae-de77518b85b5': "Producer session (the song, Clawd's world, the final chorus, the film)",
            '9b0cfd68-3520-4e70-9e53-30505cd70d97': "Fable's paper world (paper theatre, puppets, bridge, outro)"}
TOK = ('input_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens', 'output_tokens')


def transcripts():
    """{message id: {session, agent, model, ts, usage}}, across every transcript file"""
    msgs = {}
    files = [(p, os.path.basename(p)[:-6], None) for p in glob.glob(os.path.join(TDIR, '*.jsonl'))]
    for sdir in glob.glob(os.path.join(TDIR, '*', 'subagents')):
        sess = os.path.basename(os.path.dirname(sdir))
        files += [(p, sess, os.path.basename(p)[:-6]) for p in glob.glob(os.path.join(sdir, '*.jsonl'))]
    for path, sess, agent in files:
        with open(path, errors='replace') as f:
            for line in f:
                if '"usage"' not in line or '"assistant"' not in line: continue
                try: d = json.loads(line)
                except ValueError: continue
                m = d.get('message')
                if not isinstance(m, dict) or m.get('role') != 'assistant' or 'usage' not in m or not m.get('id'): continue
                u = {k: int(m['usage'].get(k) or 0) for k in TOK}
                prev = msgs.get(m['id'])
                if prev is None or u['output_tokens'] >= prev['usage']['output_tokens']:
                    msgs[m['id']] = {'session': sess, 'agent': agent if prev is None else (prev['agent'] or agent),
                                     'model': m.get('model') or 'unknown', 'ts': d.get('timestamp') or (prev or {}).get('ts', ''), 'usage': u}
    return msgs


def token_table(msgs, since):
    agg = collections.defaultdict(lambda: collections.Counter())
    for m in msgs.values():
        if m['session'] not in SESSIONS or (m['ts'] and m['ts'] < since) or m['model'].startswith('<'): continue
        who = ('main' if m['agent'] is None else 'subagents')
        for key in [('total', m['model']), (m['session'], m['model']), (m['session'] + '/' + who, m['model'])]:
            c = agg[key]; c['turns'] += 1
            for k in TOK: c[k] += m['usage'][k]
    out = {}
    for (scope, model), c in sorted(agg.items()):
        out.setdefault(scope, {})[model] = dict(c)
    for scope, byModel in out.items():
        tot = collections.Counter()
        for c in byModel.values(): tot.update(c)
        byModel['_all'] = dict(tot)
    agents = {m['agent'] for m in msgs.values() if m['agent'] and m['session'] in SESSIONS and (not m['ts'] or m['ts'] >= since)}
    out['_subagent_count'] = len(agents)
    return out


# the reference videos Gemini reviewed for this film (Live2D dance and production references: PICTURE.md, docs/research)
FILM_REFS = {'tsuzuku': {'-07ECr-E24M', 'V29auInv1FQ', 'HzIKNmTjVko', '6DG_J1YJvhY'}}


def ledger():
    rows = []
    with open(os.path.join(ROOT, 'tools', 'ledger.jsonl')) as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try: rows.append(json.loads(line))
            except ValueError: pass
    mine = [r for r in rows if f'projects/{FILM}/' in str(r.get('out') or '') + str(r.get('in') or '') or str(r.get('out')) in FILM_REFS.get(FILM, set())]
    g = collections.defaultdict(lambda: collections.Counter())
    detail = collections.defaultdict(lambda: collections.Counter())
    for r in mine:
        key = f"{r.get('service')}:{r.get('op')}"; c = g[key]; c['calls'] += 1
        if r.get('ok') is False: c['failed'] += 1
        for k in ('seconds', 'chars', 'n'):
            if isinstance(r.get(k), (int, float)): c[k] += r[k]
        u = r.get('usage') or {}
        for k in ('input_tokens', 'output_tokens'):
            if isinstance(u.get(k), int): c['usage_' + k] += u[k]
        if r.get('model'): detail[key]['model ' + str(r['model'])] += 1
        if r.get('size'): detail[key][f"size {r['size']} {r.get('quality', '')}".strip()] += 1
    return {k: {**dict(v), 'detail': dict(detail[k])} for k, v in sorted(g.items())}, len(mine), len(rows)


def git():
    """commits touching the film, classified by which session's files they touch (HANDOFF.md's list is the paper world's)"""
    paper = re.compile(r'projects/%s/(src/(paper|page|fable(?!seat|stage)\w*|clawdpaper|origami|verse|exchange|bridge|prologue|outro|ink|stage|scenery|audience|mother)\.js'
                       r'|rig/(fable|fable_ink|kuroko|clawd_paper|audience|butai|scenery)/|sound/|voice/|song/|FABLE\.md|HANDOFF\.md)|engine/(puppet|warp)\.js' % FILM)
    log = subprocess.run(['git', '-C', ROOT, 'log', '--numstat', '--format=@@%h %aI', '--', f'projects/{FILM}', 'engine', 'tools'],
                         capture_output=True, text=True).stdout
    commits, cur = [], None
    for line in log.splitlines():
        if line.startswith('@@'):
            h, ts = line[2:].split(' ', 1); cur = {'hash': h, 'ts': ts, 'files': [], 'add': 0, 'del': 0}; commits.append(cur)
        elif line.strip() and cur is not None:
            p = line.split('\t')
            if len(p) == 3:
                cur['files'].append(p[2])
                if p[0].isdigit(): cur['add'] += int(p[0]); cur['del'] += int(p[1])
    film = [c for c in commits if any(f.startswith(f'projects/{FILM}/') for f in c['files'])]
    cls = collections.Counter()
    for c in film:
        fp = [f for f in c['files'] if f.startswith(f'projects/{FILM}/') or f.startswith('engine/')]
        n_paper = sum(bool(paper.search(f)) for f in fp)
        cls['paper world' if n_paper == len(fp) and fp else "Clawd's world / producer" if n_paper == 0 else 'both'] += 1
    return {'commits': len(film), 'first': min(c['ts'] for c in film), 'last': max(c['ts'] for c in film),
            'lines_added': sum(c['add'] for c in film), 'lines_deleted': sum(c['del'] for c in film), 'by_session': dict(cls)}


def assets():
    P = os.path.join(ROOT, 'projects', FILM)
    cnt = lambda pat: len(glob.glob(os.path.join(P, pat), recursive=True))
    code = {}
    for label, pats in {'film JS (src/)': ['src/**/*.js'], 'engine JS (engine/)': [os.path.join(ROOT, 'engine', '*.js'), os.path.join(ROOT, 'engine', '*.mjs')],
                        'Python tools (tools/)': [os.path.join(ROOT, 'tools', '*.py')], 'rig and sound build scripts (film)': ['rig/**/*.py', 'sound/*.py', 'song/*.py', 'voice/*.py']}.items():
        n = 0
        for pat in pats:
            for f in glob.glob(pat if os.path.isabs(pat) else os.path.join(P, pat), recursive=True):
                if 'vendor' in f or '.min.' in f: continue
                with open(f, errors='replace') as fh: n += sum(1 for _ in fh)
        code[label] = n
    clawd_layers = [f for f in glob.glob(os.path.join(P, 'rig/clawd/build/*.png')) if '@' not in f and not f.endswith('.inv.png')]
    return {'clawd_rig_layers': len(clawd_layers), 'clawd_drawn_variants': cnt('rig/clawd/build/*@*.png'),
            'clawd_view_drawings': cnt('rig/clawd/views/*_aligned.png'),
            'fable_seated_pose_drawings': cnt('rig/fable_seated/figure_*.png'),
            'mocap_clips': cnt('refs/mocap/*_v1.mp4'), 'sound_library_files': len({os.path.splitext(f)[0] for f in glob.glob(os.path.join(P, 'sound/lib/*'))}),
            'lines_of_code': code, 'film_length_s': 209.65, 'frames_at_24fps': round(209.65 * 24)}


def fmt(n): return f'{n:,}'


if __name__ == '__main__':
    msgs = transcripts()
    stats = {'film': FILM, 'since_utc': SINCE, 'sessions': SESSIONS, 'claude_tokens': token_table(msgs, SINCE)}
    stats['paid_calls'], stats['paid_calls_film'], stats['paid_calls_all'] = ledger()
    stats['git'] = git(); stats['assets'] = assets()
    stats['not_measured'] = ['Claude dollar cost: the transcripts record tokens, not prices',
                             'Higgsfield dollars: the account was topped up by $15 on 2026-09-26; the earlier balance is not recorded; '
                             'failed (out-of-credit) Seedance attempts are not in the ledger',
                             'ElevenLabs credits: music is logged in seconds and TTS in characters; SFX calls have no size']
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(stats, open(OUT, 'w'), indent=1)
    # a markdown summary
    t = stats['claude_tokens']; L = ['| Scope | Model | API turns | Input | Cache write | Cache read | Output |', '|---|---|---:|---:|---:|---:|---:|']
    for scope in ['total'] + [s + suf for s in SESSIONS for suf in ('/main', '/subagents')]:
        for model, c in (t.get(scope) or {}).items():
            if model == '_all' and len(t[scope]) == 2: continue
            name = 'all sessions' if scope == 'total' else SESSIONS[scope.split('/')[0]].split(' (')[0] + ' / ' + scope.split('/')[1]
            L.append(f"| {name} | {model} | {fmt(c['turns'])} | {fmt(c['input_tokens'])} | {fmt(c['cache_creation_input_tokens'])} | {fmt(c['cache_read_input_tokens'])} | {fmt(c['output_tokens'])} |")
    L += ['', '| Paid call | Calls | Detail |', '|---|---:|---|']
    for k, v in stats['paid_calls'].items():
        extra = ', '.join(f'{kk} {vv:,.0f}' for kk, vv in v.items() if kk not in ('calls', 'detail') and isinstance(vv, (int, float)))
        det = '; '.join(f'{kk} ×{vv}' for kk, vv in v['detail'].items())
        L.append(f"| {k} | {v['calls']} | {extra}{'; ' if extra and det else ''}{det} |")
    open(OUT.replace('.json', '.md'), 'w').write('\n'.join(L) + '\n')
    print('\n'.join(L)); print(json.dumps(stats['git'])); print(json.dumps(stats['assets']))
