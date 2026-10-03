"""A local review page: images (and videos) with captions on one page, opened in the browser from disk. Review boards hold
game renders and reference art, which never leave the machine, so the page links local files and is never published.
    .venv/bin/python tools/machinima/melee/art/review_page.py OUT.html "Title" [--note TEXT] [--sound] [--open] FILE::caption ...
A FILE of '#Heading' starts a section. Images open full size on click; .mp4/.webm files play inline (muted; --sound keeps
their sound, for in-game captures with game audio); .wav/.mp3/.m4a files get an audio player; a .csv becomes a table
(its first row the header), with a link to the file.
"""
import csv, html, os, subprocess, sys


def table(path):
    rows = list(csv.reader(open(os.path.expanduser(path))))
    if not rows:
        return ''
    head = ''.join(f'<th>{html.escape(c)}</th>' for c in rows[0])
    body = ''.join('<tr>' + ''.join(f'<td>{html.escape(c)}</td>' for c in r) + '</tr>' for r in rows[1:])
    return f'<div class="tbl"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def page(title, items, note='', sound=False):
    out = [f'<!doctype html><meta charset="utf-8"><title>{html.escape(title)}</title><style>'
           ':root{--bg:#f4f4f6;--fg:#1b1b1f;--mute:#62626b;--card:#fff}'
           '@media(prefers-color-scheme:dark){:root{--bg:#141417;--fg:#ececf1;--mute:#9a9aa6;--card:#1f1f24}}'
           'body{margin:0;padding:24px 16px 64px;background:var(--bg);color:var(--fg);font:15px/1.45 -apple-system,system-ui,sans-serif}'
           'main{max-width:1500px;margin:0 auto}h1{font-size:22px;margin:0 0 6px}h2{font-size:17px;margin:32px 0 10px}'
           '.note{color:var(--mute);margin:0 0 18px;max-width:900px}figure{margin:0 0 22px;background:var(--card);'
           'border-radius:10px;padding:10px;box-shadow:0 1px 3px #0002}img,video{display:block;max-width:100%;height:auto;'
           'border-radius:6px}audio{display:block;width:100%;max-width:640px}figcaption{margin:8px 2px 2px;color:var(--mute)}'
           '.tbl{max-height:520px;overflow:auto;border-radius:6px}table{border-collapse:collapse;font:12px/1.35 ui-monospace,'
           'Menlo,monospace;font-variant-numeric:tabular-nums}th,td{padding:3px 9px;text-align:right;white-space:nowrap}'
           'th{position:sticky;top:0;background:var(--card);border-bottom:1px solid var(--mute)}tr:nth-child(even) td{'
           'background:color-mix(in srgb,var(--fg) 5%,transparent)}'
           '</style><main>',
           f'<h1>{html.escape(title)}</h1>']
    if note: out.append(f'<p class="note">{html.escape(note)}</p>')
    for path, cap in items:
        if path.startswith('#'):
            out.append(f'<h2>{html.escape(path[1:])}</h2>'); continue
        src = 'file://' + os.path.abspath(os.path.expanduser(path))
        if path.lower().endswith(('.mp4', '.webm')):
            media = f'<video src="{src}" controls {"" if sound else "loop muted "}playsinline></video>'
        elif path.lower().endswith('.csv'):
            media = table(path) + f'<p><a href="{src}">{html.escape(os.path.basename(path))}</a></p>'
        elif path.lower().endswith(('.wav', '.mp3', '.m4a')):
            media = f'<audio src="{src}" controls preload="metadata"></audio>'
        else:
            media = f'<a href="{src}" target="_blank"><img src="{src}" loading="lazy"></a>'
        out.append(f'<figure>{media}<figcaption>{html.escape(cap)}</figcaption></figure>')
    return '\n'.join(out) + '</main>'


if __name__ == '__main__':
    a = sys.argv[1:]
    opn = '--open' in a; sound = '--sound' in a; a = [x for x in a if x not in ('--open', '--sound')]
    note = ''
    if '--note' in a:
        i = a.index('--note'); note = a[i + 1]; del a[i:i + 2]
    out, title, rest = a[0], a[1], a[2:]
    items = [(r.split('::', 1) + [''])[:2] for r in rest]
    open(out, 'w').write(page(title, items, note, sound))
    print(out)
    if opn: subprocess.run(['open', '-a', 'Google Chrome', out])
