"""Build a film's Melee: compile its choreography, hook the director into the decomp, rebuild the DOL, install it in the disc.
    .venv/bin/python tools/machinima/melee/build.py P [NAME]     # P/director/NAME.py (default script) -> build/NAME.c -> main.dol
    .venv/bin/python tools/machinima/melee/build.py --matching   # restore and verify the byte-matching build (hooks stay in place)
Needs (see tools/machinima/README.md): the decomp at $MELEE_DECOMP (~/games/melee/decomp) configured once with your own disc's
main.dol, and the disc extracted to $MELEE_DISC (~/games/melee/disc). The hooks are wrapped in #ifndef MUST_MATCH, so the
matching build of the same tree still reproduces the original DOL byte for byte.
"""
import os, re, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
# An agent's worktree (animation-pipeline-<name>) builds only into its own sandbox: without MELEE_DECOMP and MELEE_DISC set,
# a build from there would overwrite the shared decomp and the main disc (2026-09-30: a lab DOL replaced Michael's playtest
# build that way). Integration builds run from the main geno checkout.
if re.search(r'animation-pipeline-[^/]+$', ROOT) and os.path.basename(ROOT) != 'animation-pipeline-geno' and not (
        os.environ.get('MELEE_DECOMP') and os.environ.get('MELEE_DISC')):
    sys.exit(f'build.py: {ROOT} is an agent worktree; eval "$(sh tools/machinima/melee/sandbox.sh NAME)" first, '
             'so the build goes to its sandbox and not the shared decomp or main disc')
DECOMP = os.path.expanduser(os.environ.get('MELEE_DECOMP', '~/games/melee/decomp'))
DISC = os.path.expanduser(os.environ.get('MELEE_DISC', '~/games/melee/disc'))
WIBO = os.path.expanduser(os.environ.get('MELEE_WRAPPER', '~/games/melee/bin/wibo-macos'))
MARK = '/* director */'

# (file, anchor text, replacement): each hook is inserted once, next to an exact line of the decomp
HOOKS = [
    ('src/melee/gm/gm_1A3F.c',
     '        state_machine.routing.curr_mode = GM_BOOT;\n',
     '#ifndef MUST_MATCH ' + MARK + '\n        state_machine.routing.curr_mode = director_boot();\n#else\n'
     '        state_machine.routing.curr_mode = GM_BOOT;\n#endif\n'),
    ('src/melee/gm/gm_1A3F.c',
     '#include <sysdolphin/baselib/video.h>\n',
     '#include <sysdolphin/baselib/video.h>\n#ifndef MUST_MATCH ' + MARK + '\n#include <melee/director/director.h>\n#endif\n'),
    ('src/melee/gm/gmvsmode.c',
     '#include <melee/mn/types.h>\n',
     '#include <melee/mn/types.h>\n#ifndef MUST_MATCH ' + MARK + '\n#include <melee/director/director.h>\n#endif\n'),
    ('src/melee/gm/gmvsmode.c',
     '    start->players[3].rumble_enabled = false;\n\n    gm_LoadAnnouncer();\n',
     '    start->players[3].rumble_enabled = false;\n\n#ifndef MUST_MATCH ' + MARK + '\n    director_setup_match(start);\n#endif\n'
     '    gm_LoadAnnouncer();\n'),
    ('src/melee/ft/ftcoll.c',
     '#include "types.h"\n',
     '#include "types.h"\n#ifndef MUST_MATCH ' + MARK + '\n#include <melee/director/director.h>\n#endif\n'),
    ('src/melee/ft/ftcoll.c',
     '    fp1 = GET_FIGHTER(arg1);\n    pl_8003EB30(arg2, fp0->player_idx, fp0->is_sub_fighter, fp1->player_idx,\n',
     '    fp1 = GET_FIGHTER(arg1);\n#ifndef MUST_MATCH ' + MARK + '\n    director_on_hit(arg0, arg1, arg2);\n#endif\n'
     '    pl_8003EB30(arg2, fp0->player_idx, fp0->is_sub_fighter, fp1->player_idx,\n'),
]
HOOKS.append(('src/melee/ft/ftcoll.c',
     '    plStale_UpdateStaleMovesFromItem(arg0, arg1);\n',
     '    plStale_UpdateStaleMovesFromItem(arg0, arg1);\n#ifndef MUST_MATCH ' + MARK + '\n    director_on_item_hit(arg0, arg1, arg2);\n#endif\n'))
HOOKS.append(('src/melee/it/kinds/itfoxlaser.c', '#include "itfoxlaser.h"\n',
              '#include "itfoxlaser.h"\n#ifndef MUST_MATCH ' + MARK + '\n#include <melee/director/director.h>\n#endif\n'))
HOOKS.append(('src/melee/it/kinds/itfoxlaser.c',
              '        item->xDD4_itemVar.foxlaser.pos = spawn.pos;\n',
              '        item->xDD4_itemVar.foxlaser.pos = spawn.pos;\n#ifndef MUST_MATCH ' + MARK + '\n'
              '        director_on_laser(parent, &spawn.pos, kind, angle, speed);\n#endif\n'))
# one game frame per rendered image: the loop runs a logic frame per queued pad sample, so a slow render (two samples waiting)
# would run two logic frames and dump one image. A director build never catches up; the extra samples are dropped (the
# director writes the pads every frame anyway). FRAME PERFECT's first full capture lost a frame to this in a busy pillar.
# The same test is the lag measure: a loop frame that found more than one sample queued ran longer than a video frame (the
# console would slow down), and the director logs it (LAGFRAME) before the flush. One block, one hook: a second hook that
# edited this block made the first one's text vanish, so the next build inserted a plain block ahead of it, which zeroed
# the count before the lag call (the 07:49 incident, 2026-09-30); GMSCENE_UPGRADES and the check in hook() keep it single.
PAD_ANCHOR = '        while ((pad_queue_count = lb_80019894()) == 0) {\n            lb_800195D0();\n        }\n        lb_800195D0();\n'
PAD_PLAIN = ('#ifndef MUST_MATCH ' + MARK + '\n        if (pad_queue_count > 1) {\n'
             '            HSD_PadFlushQueue(HSD_PAD_FLUSH_QUEUE_LEAVE1);\n            pad_queue_count = 1;\n        }\n#endif\n')
PAD_LAG = ('#ifndef MUST_MATCH ' + MARK + '\n        if (pad_queue_count > 1) {\n            director_on_lag(pad_queue_count);\n'
           '            HSD_PadFlushQueue(HSD_PAD_FLUSH_QUEUE_LEAVE1);\n            pad_queue_count = 1;\n        }\n#endif\n')
HOOKS.append(('src/melee/gm/gmscene.c', PAD_ANCHOR, PAD_ANCHOR + PAD_LAG))
# older builds' flush blocks, upgraded in place before the hooks run: a doubled pair (plain, then the lag block) collapses
# to the lag block, and a lone plain block (the older hook's, or a decomp commit of it) gains the lag call
GMSCENE_UPGRADES = [(PAD_ANCHOR + PAD_PLAIN + PAD_LAG, PAD_ANCHOR + PAD_LAG), (PAD_ANCHOR + PAD_PLAIN, PAD_ANCHOR + PAD_LAG)]
HOOKS.append(('src/melee/gm/gmscene.c', '#include <sysdolphin/baselib/sobjlib.h>\n',
              '#include <sysdolphin/baselib/sobjlib.h>\n#ifndef MUST_MATCH ' + MARK + '\n#include <melee/director/director.h>\n#endif\n'))
# menu tests drive the game's own menus: pads go into the master status each loop frame, before menus and matches read it
HOOKS.append(('src/melee/gm/gmscene.c',
              '            HSD_PerfSetStartTime();\n            lb_800198E0();\n',
              '            HSD_PerfSetStartTime();\n            lb_800198E0();\n#ifndef MUST_MATCH ' + MARK + '\n'
              '            director_boot_frame();\n#endif\n'))
# the director's menu tests steer a port's character-select token closed loop: they read the hand and token positions
# (main's hook for a stock decomp; Geno's decomp (ext, 28d4d6d) already carries this exact text, so there the hook is a no-op)
HOOKS.append(('src/melee/mn/mncharsel.c', '}* mnCharSel_804A0BD0[4];\n\n',
              '}* mnCharSel_804A0BD0[4];\n\n' + "#ifndef MUST_MATCH\n/* for the director's menu tests (tools/machinima/melee): a port's hand and token positions on the character select\n * screen, in icon-bound units. Only meaningful while the screen is running. */\nbool mnCharSel_DebugPositions(int port, float* hand, float* token)\n{\n    if (port < 0 || port > 3 || mnCharSel_804A0BC0[port] == NULL ||\n        mnCharSel_804A0BD0[port] == NULL)\n    {\n        return false;\n    }\n    hand[0] = mnCharSel_804A0BC0[port]->xC;\n    hand[1] = mnCharSel_804A0BC0[port]->x10;\n    token[0] = mnCharSel_804A0BD0[port]->x8;\n    token[1] = mnCharSel_804A0BD0[port]->xC;\n    return true;\n}\n#endif\n\n"))
HOOKS.append(('src/melee/mn/mncharsel.h', '/* 2669F4 */ void mnCharSel_Scene_OnFrame(void);\n',
              '/* 2669F4 */ void mnCharSel_Scene_OnFrame(void);\n' + '#ifndef MUST_MATCH\n#include <Runtime/platform.h>\nbool mnCharSel_DebugPositions(int port, float* hand, float* token);\n#endif\n'))
LIB = ('    MeleeLib(\n        "director (machinima) ' + MARK + '",\n        [\n'
       '            Object(Equivalent, "melee/director/director.c"),\n'
       '            Object(Equivalent, "melee/director/script.c"),\n        ],\n    ),\n')


def hook():
    p = os.path.join(DECOMP, 'src/melee/gm/gmscene.c'); s = open(p, encoding='utf-8').read(); s0 = s
    for old, new in GMSCENE_UPGRADES:
        s = s.replace(old, new)
    if s != s0:
        open(p, 'w', encoding='utf-8').write(s); print('upgraded the flush block in src/melee/gm/gmscene.c')
    for rel, anchor, repl in HOOKS:
        p = os.path.join(DECOMP, rel); s = open(p, encoding='utf-8').read()
        if repl in s: continue
        if s.count(anchor) != 1: sys.exit(f'hook anchor not found exactly once in {rel}: {anchor!r}')
        open(p, 'w', encoding='utf-8').write(s.replace(anchor, repl))
        print('hooked', rel)
    s = open(os.path.join(DECOMP, 'src/melee/gm/gmscene.c'), encoding='utf-8').read()
    if s.count('if (pad_queue_count > 1)') != 1 or s.count('director_on_lag(pad_queue_count);') != 1:
        sys.exit('src/melee/gm/gmscene.c: expected exactly one director flush block, with the lag call (see PAD_LAG)')
    p = os.path.join(DECOMP, 'configure.py'); s = open(p).read()
    if MARK not in s:
        anchor = '\n]\n\n\nconfig.link_order_callback'
        if s.count(anchor) != 1: sys.exit('configure.py: library list end not found')
        open(p, 'w').write(s.replace(anchor, '\n' + LIB + ']\n\n\nconfig.link_order_callback'))
        print('added the director library to configure.py')


def run(cmd, **kw):
    r = subprocess.run(cmd, cwd=DECOMP, capture_output=True, text=True, **kw)
    if r.returncode:
        out = '\n'.join(l for l in (r.stdout + r.stderr).splitlines() if not re.match(r'\[\d+/\d+\] ', l))
        sys.exit(f'{" ".join(cmd)} failed:\n{out[-4000:]}')
    return r.stdout


def build(proj, name='script'):
    script = os.path.join(proj, 'director', name + '.py')
    out_c = os.path.join(proj, 'director', 'build', name + '.c')
    subprocess.run([sys.executable, script, out_c], check=True, cwd=ROOT,
                   env={**os.environ, 'PYTHONPATH': HERE + os.pathsep + os.environ.get('PYTHONPATH', '')})
    # capture lanes (several scenes captured at once) share this one decomp worktree: a build holds an exclusive lock from
    # writing script.c to installing its DOL in the lane's disc (MELEE_DISC). Dolphin reads the DOL at boot, so the next
    # lane's build can go ahead while this one captures.
    import fcntl
    with open(os.path.join(DECOMP, '.machinima-build.lock'), 'w') as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        hook()
        dst = os.path.join(DECOMP, 'src', 'melee', 'director'); os.makedirs(dst, exist_ok=True)
        for f in ('director.h', 'director.c'):
            shutil.copy(os.path.join(HERE, 'director', f), dst)
        shutil.copy(out_c, os.path.join(dst, 'script.c'))
        run([sys.executable, 'configure.py', '--non-matching', '--wrapper', WIBO])
        run(['ninja', '-j', os.environ.get('MELEE_JOBS', '6')])
        dol = os.path.join(DECOMP, 'build', 'GALE01', 'main.dol')
        shutil.copy(dol, os.path.join(DISC, 'sys', 'main.dol'))
    print(f'built {os.path.getsize(dol)} byte main.dol -> {DISC}/sys/main.dol')


def matching():
    run([sys.executable, 'configure.py', '--wrapper', WIBO])
    print(run(['ninja', '-j', os.environ.get('MELEE_JOBS', '6')]).strip().splitlines()[-1])
    shutil.copy(os.path.join(DECOMP, 'orig', 'GALE01', 'sys', 'main.dol'), os.path.join(DISC, 'sys', 'main.dol'))


if __name__ == '__main__':
    if sys.argv[1] == '--matching': matching()
    else: build(os.path.abspath(sys.argv[1]), *(sys.argv[2:3]))
