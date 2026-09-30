"""Each box's load, summarised: the numbers for the build-box capacity call (more slots, a bigger machine, or a second
box) that the integrator brings to Michael. The samples are charkit/boxjob.py's, taken once a minute on the box and
published to the bucket (load-<VM>) whenever a job ends; slot waits are charkit.procs's (slots/waits.jsonl, one line per
slot taken, from builds running code that has it).

    python -m charkit remote load [--hours N] [--box NAME] [--fresh] [--json]
        --hours N   the last N hours (default 24)
        --fresh     have a running box publish its samples now (one ssh) rather than read what the last job published
        --json      the summary as JSON

Per box: minutes sampled; CPU busy (mean, median, p90, the share of minutes at 90% or more); 1-minute load (mean, p90,
peak, when); memory used and the least available; slot occupancy (mean held, the share of minutes with every slot held,
slot-minutes held over offered); the queue (minutes with a build waiting for a slot, the longest queue); slot waits
(builds that waited, how long: median, p90, longest, total); Blender processes; GPU use; and a reading of what binds.
"""
import json, os, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'charkit', 'out', 'remote', 'load')


def pct(xs, q):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    k = (len(xs) - 1) * q
    a = int(k)
    b = min(a + 1, len(xs) - 1)
    return xs[a] + (xs[b] - xs[a]) * (k - a)


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def read(d, since):
    """samples and waits from a pulled load directory, from epoch `since` on."""
    samples, waits = [], []
    for f in sorted(os.listdir(d)) if os.path.isdir(d) else ():
        if f.startswith('load-') and f.endswith('.jsonl'):
            for line in open(os.path.join(d, f)):
                try:
                    s = json.loads(line)
                except ValueError:
                    continue
                if s.get('ts', 0) >= since:
                    samples.append(s)
    w = os.path.join(d, 'waits.jsonl')
    if os.path.exists(w):
        for line in open(w):
            try:
                x = json.loads(line)
            except ValueError:
                continue
            if x.get('at', 0) >= since:
                waits.append(x)
    samples.sort(key=lambda s: s['ts'])
    return samples, waits


def summarise(samples, waits):
    """the numbers (see the module's docstring) -> dict."""
    if not samples:
        return dict(minutes=0)
    ncpu = samples[-1].get('ncpu') or 1
    busy = [s['cpu']['busy'] for s in samples if s.get('cpu')]
    iow = [s['cpu']['iowait'] for s in samples if s.get('cpu')]
    steal = [s['cpu'].get('steal', 0) for s in samples if s.get('cpu')]
    l1 = [s['load'][0] for s in samples]
    peak = max(samples, key=lambda s: s['load'][0])
    used = [s['mem']['used'] for s in samples]
    avail = [s['mem']['avail'] for s in samples]
    count = [s['slots']['count'] for s in samples]
    held = [s['slots']['held'] for s in samples]
    full = [s['slots']['held'] >= s['slots']['count'] for s in samples]
    waiting = [s['slots'].get('waiting', 0) for s in samples]
    qpeak = max(samples, key=lambda s: s['slots'].get('waiting', 0))
    jobs = [len(s.get('jobs', ())) for s in samples]
    blender = [s.get('blender', 0) for s in samples]
    gpu = [s['gpu']['util'] for s in samples if s.get('gpu')]
    builds = [sum(v for k, v in s.get('procs', {}).items() if k in ('charkit build', 'charkit tune')) for s in samples
              if 'procs' in s]
    by = [s['cpu']['by'] for s in samples if s.get('cpu') and s['cpu'].get('by')]
    classes = sorted({k for b in by for k in b})
    bpeak = max((s for s in samples if 'procs' in s), default=None,
                key=lambda s: sum(v for k, v in s['procs'].items() if k in ('charkit build', 'charkit tune')))
    # minutes the box was up: consecutive samples less than 3 min apart count their gap
    up = 1.0 + sum(min(b['ts'] - a['ts'], 180) / 60 for a, b in zip(samples, samples[1:]) if b['ts'] - a['ts'] < 180)
    out = dict(
        minutes=len(samples), up_minutes=round(up), first=samples[0]['t'], last=samples[-1]['t'], ncpu=ncpu,
        mem_total=samples[-1]['mem']['total'],
        cpu=dict(mean=mean(busy), p50=pct(busy, .5), p90=pct(busy, .9), max=max(busy) if busy else None,
                 share_ge90=sum(b >= .9 for b in busy) / len(busy) if busy else None, iowait=mean(iow), steal=mean(steal)),
        load=dict(mean=mean(l1), p90=pct(l1, .9), peak=peak['load'][0], peak_at=peak['t'],
                  share_over_ncpu=sum(x > ncpu for x in l1) / len(l1)),
        mem=dict(mean=mean(used), p90=pct(used, .9), max=max(used), min_avail=min(avail)),
        slots=dict(count=count[-1], counts=sorted(set(count)), held_mean=mean(held), held_max=max(held),
                   share_full=sum(full) / len(full),
                   occupancy=sum(held) / sum(count) if sum(count) else None),
        queue=dict(share_waiting=sum(w > 0 for w in waiting) / len(waiting), mean=mean(waiting), max=max(waiting),
                   max_at=qpeak['t'] if max(waiting) else None),
        jobs=dict(max=max(jobs), mean=mean(jobs)), blender=dict(mean=mean(blender), max=max(blender)),
        builds=dict(mean=mean(builds), p90=pct(builds, .9), max=max(builds), max_at=bpeak['t']) if builds else None,
        cpu_by={c: mean([b.get(c, 0.0) for b in by]) for c in classes} if by else None,
        gpu=dict(mean=mean(gpu), p90=pct(gpu, .9), max=max(gpu)) if gpu else None)
    took = [w['waited'] for w in waits]
    waited = [w for w in took if w > 1]
    out['waits'] = dict(taken=len(took), waited=len(waited), share=len(waited) / len(took) if took else None,
                        p50=pct(waited, .5), p90=pct(waited, .9), max=max(waited) if waited else None,
                        total_h=sum(waited) / 3600,
                        why={k: sum(1 for w in waits if w.get('why') == k and w['waited'] > 1) for k in ('slots', 'memory')})
    out['reading'] = reading(out)
    return out


def reading(s):
    """what binds, from the numbers (a hint for the capacity call, not the call). A build takes a slot only for its
    Blender step; its Python stages (the hull, garments, QA) run outside the slots, so the CPU and the load, not the
    slots, say whether the box is full."""
    if not s.get('minutes'):
        return 'no samples'
    cpu, sl, q, w, ld = s['cpu'], s['slots'], s['queue'], s['waits'], s['load']
    notes = []
    sat = (cpu['p50'] or 0) >= 0.85 or (cpu['share_ge90'] or 0) >= 0.3
    busy = (cpu['p50'] or 0) >= 0.5 or ld['share_over_ncpu'] >= 0.2
    if sat:
        notes.append('CPU-bound: median %.0f%% busy, >=90%% in %.0f%% of minutes, load above %d in %.0f%% (peak %.1f); more '
                     'builds at once only slow each one: a bigger machine or a second box adds throughput'
                     % (100 * (cpu['p50'] or 0), 100 * (cpu['share_ge90'] or 0), s['ncpu'], 100 * ld['share_over_ncpu'],
                        ld['peak']))
    elif busy:
        notes.append('busy but not saturated: median %.0f%% busy (>=90%% in %.0f%% of minutes), load above %d in %.0f%% of '
                     'minutes (peak %.1f): runnable work queues on the cores at peaks, the cores idle between'
                     % (100 * (cpu['p50'] or 0), 100 * (cpu['share_ge90'] or 0), s['ncpu'], 100 * ld['share_over_ncpu'],
                        ld['peak']))
    else:
        notes.append('not busy: median %.0f%% CPU, load above %d in %.0f%% of minutes'
                     % (100 * (cpu['p50'] or 0), s['ncpu'], 100 * ld['share_over_ncpu']))
    if s.get('builds'):
        notes.append('%.1f builds at once on average (max %d) against %.1f slots held (all %d held in %.0f%% of minutes): '
                     'the slots bound only the Blender step' % (s['builds']['mean'], s['builds']['max'],
                                                                sl['held_mean'], sl['count'], 100 * sl['share_full']))
    if s.get('cpu_by'):
        py = sum(v for k, v in s['cpu_by'].items() if k.startswith('charkit'))
        notes.append('charkit processes use %.0f%% of the CPU, Blender %.0f%% (processes alive at a sample; short-lived '
                     'ones are missed)' % (100 * py, 100 * s['cpu_by'].get('blender', 0)))
    if w.get('taken'):
        notes.append('%d of %d slot takes waited (median %.0f s, longest %.0f s, %.1f h in all); a build waiting in %.0f%% of '
                     'minutes' % (w['waited'], w['taken'], w['p50'] or 0, w['max'] or 0, w['total_h'],
                                  100 * q['share_waiting']))
    else:
        notes.append('no slot waits recorded yet (builds record them once their code has charkit.procs\' wait log)')
    notes.append('memory: at most %.0f GB used, never under %.0f GB available' % (s['mem']['max'], s['mem']['min_avail']))
    return '; '.join(notes)


def hourly(samples):
    """per UTC hour: CPU busy mean, load peak, slots held mean, the longest queue."""
    rows = {}
    for s in samples:
        rows.setdefault(s['t'][:13], []).append(s)
    return [dict(hour=h, n=len(ss), cpu=mean([x['cpu']['busy'] for x in ss if x.get('cpu')]),
                 builds=max([sum(v for k, v in x.get('procs', {}).items() if k in ('charkit build', 'charkit tune'))
                             for x in ss] or [0]),
                 load=max(x['load'][0] for x in ss), held=mean([x['slots']['held'] for x in ss]),
                 count=ss[-1]['slots']['count'], waiting=max(x['slots'].get('waiting', 0) for x in ss))
            for h, ss in sorted(rows.items())]


def text(name, s, hours_rows=None):
    f = lambda x, k=100, d=0: '-' if x is None else ('%.' + str(d) + 'f') % (x * k)
    if not s.get('minutes'):
        return '%s box: no samples in the window' % name
    L = ['%s box (%d vCPU, %.0f GB): %d samples, %s .. %s (UTC), up about %d min'
         % (name, s['ncpu'], s['mem_total'], s['minutes'], s['first'], s['last'], s['up_minutes']),
         '  CPU busy     mean %s%%  median %s%%  p90 %s%%  max %s%%;  >=90%% busy in %s%% of minutes;  iowait %s%%  steal %s%%'
         % (f(s['cpu']['mean']), f(s['cpu']['p50']), f(s['cpu']['p90']), f(s['cpu']['max']), f(s['cpu']['share_ge90']),
            f(s['cpu']['iowait'], d=1), f(s['cpu']['steal'], d=1)),
         '  load (1 min) mean %.1f  p90 %.1f  peak %.1f at %s;  above %d in %s%% of minutes'
         % (s['load']['mean'], s['load']['p90'], s['load']['peak'], s['load']['peak_at'], s['ncpu'],
            f(s['load']['share_over_ncpu'])),
         '  memory used  mean %.0f GB  p90 %.0f GB  max %.0f GB;  least available %.0f GB'
         % (s['mem']['mean'], s['mem']['p90'], s['mem']['max'], s['mem']['min_avail']),
         '  slots        %s;  held mean %.1f  max %d;  all held in %s%% of minutes;  occupancy %s%%'
         % ('/'.join(map(str, s['slots']['counts'])), s['slots']['held_mean'], s['slots']['held_max'],
            f(s['slots']['share_full']), f(s['slots']['occupancy'])),
         '  queue        a build waiting in %s%% of minutes;  mean %.2f  longest %d%s'
         % (f(s['queue']['share_waiting']), s['queue']['mean'], s['queue']['max'],
            ' at %s' % s['queue']['max_at'] if s['queue']['max_at'] else ''),
         '  slot waits   %d slots taken, %d waited%s' % (
             s['waits']['taken'], s['waits']['waited'],
             ': median %.0f s  p90 %.0f s  longest %.0f s  total %.1f h (for slots %d, for memory %d)' % (
                 s['waits']['p50'], s['waits']['p90'], s['waits']['max'], s['waits']['total_h'],
                 s['waits']['why']['slots'], s['waits']['why']['memory']) if s['waits']['waited'] else ''),
         '  jobs         detached jobs running: max %d;  Blender processes mean %.1f  max %d'
         % (s['jobs']['max'], s['jobs']['mean'], s['blender']['max'])]
    if s.get('builds'):
        L.append('  builds       charkit build/tune processes: mean %.1f  p90 %.0f  max %d at %s' % (
            s['builds']['mean'], s['builds']['p90'], s['builds']['max'], s['builds']['max_at']))
    if s.get('cpu_by'):
        L.append('  CPU by class ' + '  '.join('%s %s%%' % (k, f(v)) for k, v in sorted(s['cpu_by'].items(),
                                                                                  key=lambda kv: -kv[1])))
    if s.get('gpu'):
        L.append('  GPU          mean %.0f%%  p90 %.0f%%  max %.0f%%' % (s['gpu']['mean'], s['gpu']['p90'], s['gpu']['max']))
    L.append('  reading      ' + s['reading'])
    if hours_rows:
        L.append('  hour (UTC)      min  cpu%  load-peak  builds-max  held/slots  queue-max')
        for r in hours_rows:
            L.append('  %s  %4d  %4s  %9.1f  %10d  %5.1f/%-4d  %9d' % (
                r['hour'].replace('T', ' '), r['n'], f(r['cpu']), r['load'], r['builds'], r['held'], r['count'], r['waiting']))
    return '\n'.join(L)


def main(args, BOX):
    """`remote load`: pull each box's samples from the bucket (or have it publish now: --fresh) and summarise."""
    from charkit import remote, bucketsync
    hours = float(remote._opt(args, '--hours', '24'))
    since = time.time() - hours * 3600
    envs = [BOX['env']] if BOX.get('chosen') else remote._boxes()
    res = {}
    for env in envs:
        BOX['env'] = env
        name = os.path.basename(env)[:-4]
        vm = remote._env('VM')
        d = os.path.join(OUT, name)
        if '--fresh' in args and remote._box_status() == 'RUNNING':
            install, runner, script = bucketsync.box_install(remote._env('BUCKET'))
            remote._sh('ssh', '%s && { [ ! -f %s/bin/boxjob.py ] || python3 %s/bin/boxjob.py sample; } && %s publish '
                       '/srv/work/.load --name load-%s >/dev/null' % (install, remote.JOBS_BOX, remote.JOBS_BOX, runner, vm),
                       check=False, input=script.decode(), retry=True)
        remote._sh('pull', 'load-' + vm, d, check=False, capture=True)        # nothing published yet: no samples
        samples, waits = read(d, since)
        s = summarise(samples, waits)
        res[name] = s
        if '--json' not in args:
            print(text(name, s, hourly(samples) if hours <= 48 else None))
            print()
    if '--json' in args:
        print(json.dumps(res, indent=1))
    return 0
