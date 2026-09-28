"""Sparse checkouts: what a worktree actually needs from the repo. The repo tracks about 1.8 GB, mostly other films'
rig art and audio (projects/tsuzuku's 2D rigs alone are 1.4 GB), and every full worktree duplicates it; a charkit
worktree reads a few hundred MB of it. Standard library only (tools/worktree.sh and the gate both use it).

    profiles:  core     engine, tools, docs, infra (and the repo's top-level files)
               charkit  core + charkit, projects/charkit-look, projects/clawd3d, and what the character's reference
                        manifest names (its rig, its model sheet)
               full     everything (no sparse checkout)

    python3 -m charkit.sparse charkit [--spec charkit/spec/clawd.json] [EXTRA ...]    # print the cone's directories
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORE = ['engine', 'tools', 'docs', 'infra']
CHARKIT = CORE + ['charkit', 'projects/charkit-look', 'projects/clawd3d']


def manifest_dirs(spec, root=ROOT):
    """the tracked paths a character's reference manifest names (directories as they are, files' folders)."""
    out = []
    try:
        s = json.load(open(os.path.join(root, spec)))
        ref = s.get('ref') or {}
        if ref.get('manifest'):
            for r in json.load(open(os.path.join(root, ref['manifest'])))['references'].values():
                p = r['path']
                if r.get('tracked', True) and not os.path.isabs(p):
                    out.append(p if os.path.isdir(os.path.join(root, p)) else os.path.dirname(p))
        if ref.get('rig'):
            out.append(ref['rig'])
    except (OSError, ValueError, KeyError):
        pass
    return out


def dirs(profile='charkit', spec='charkit/spec/clawd.json', extra=(), root=ROOT):
    """the cone for a profile -> sorted directory list, or None for 'full'."""
    if profile == 'full':
        return None
    base = list(CORE if profile == 'core' else CHARKIT)
    if profile == 'charkit':
        base += manifest_dirs(spec, root)
    return sorted(set(d.rstrip('/') for d in base + list(extra) if d))


if __name__ == '__main__':
    prof, spec, extra, a = 'charkit', 'charkit/spec/clawd.json', [], sys.argv[1:]
    while a:
        x = a.pop(0)
        if x == '--spec':
            spec = a.pop(0)
        elif x in ('core', 'charkit', 'full'):
            prof = x
        else:
            extra.append(x)
    d = dirs(prof, spec, extra)
    print('FULL' if d is None else '\n'.join(d))
