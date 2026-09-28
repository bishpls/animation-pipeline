"""A choreography language for the Melee director: write a fight on the film's clock, compile it to the director's tables.

    from dsl import Film
    f = Film(len_s=34.0)                                   # script frame s = film time s / 60 from the plate's first frame
    f.setup(players=[('fox', dict(x=-30, face=1)), ('falco', dict(x=30, face=-1))], seed=7)
    fox, falco = f.port(0), f.port(1)
    fox.move(6.0, 'usmash')                                # the move's first active frame lands at 6.0 s
    falco.hold(8.0, 0.5, stick=(-40, 0))                   # walk left for half a second
    f.cam(0.0, eye=(0, 20, 180), at=(0, 10, 0), fov=30)    # camera keys; ease shapes the move to the next key
    f.emit('build/script.c')

Pads are built as a per-frame timeline per port (later calls override earlier ones inside their span), then compressed to
state changes. Moves carry their first active hitbox frame (MOVES), so `move(t, name)` schedules the input so the hit lands
on t; a measured calibration (calib.json, from the director's HIT log) overrides the table per character and move.
Units: sticks and C-stick are raw -80..80 (the game normalises by 80), the analog trigger is 0..140, world units are Melee's
(Final Destination's ledges sit at x = +-85.6, the floor at y = 0).
"""
import json, math, os

FPS = 60
BTN = {'A': 0x100, 'B': 0x200, 'X': 0x400, 'Y': 0x800, 'Z': 0x10, 'R': 0x20, 'L': 0x40,
       'DL': 0x1, 'DR': 0x2, 'DD': 0x4, 'DU': 0x8}
CKIND = {'falcon': 0x00, 'dk': 0x01, 'fox': 0x02, 'gnw': 0x03, 'kirby': 0x04, 'bowser': 0x05, 'link': 0x06, 'luigi': 0x07,
         'mario': 0x08, 'marth': 0x09, 'mewtwo': 0x0A, 'ness': 0x0B, 'peach': 0x0C, 'pikachu': 0x0D, 'ics': 0x0E, 'puff': 0x0F,
         'samus': 0x10, 'yoshi': 0x11, 'zelda': 0x12, 'sheik': 0x13, 'falco': 0x14, 'ylink': 0x15, 'doc': 0x16, 'roy': 0x17,
         'pichu': 0x18, 'ganon': 0x19, 'geno': 0x22}
STAGE = {'final_destination': 0x20, 'battlefield': 0x1F}
EASE = {'cut': 0, 'linear': 1, 'inout': 2, 'in': 3, 'out': 4}
CUE = {'freeze': 1, 'stage': 2, 'bgcolor': 3, 'setpos': 4, 'face': 5, 'motion': 6, 'percent': 7, 'mark': 8, 'end': 9, 'reset': 10, 'approach': 11, 'auto': 12, 'trace': 13, 'status': 14, 'shield': 15, 'glass': 40, 'gamecam': 41}
TRACK = {None: 0, 'world': 0, 'mid': 1, 'p0': 2, 'p1': 3}

# Input recipes: a list of (frame offset, frames held, stick, cstick, buttons, trigger) and the first active hitbox frame
# counted from the input frame (frame 1 = the frame the input is read). Directions are for facing right; `dir=-1` mirrors x.
# Frame data: the standard Melee 1.02 values for Fox and Falco (shared where their moves match). Calibrate from HIT logs.
def _r(*steps): return [dict(zip(('at', 'n', 'stick', 'c', 'btn', 'trig'), s)) for s in steps]
MOVES = {
    'jab':      (_r((0, 2, (0, 0), (0, 0), 'A', 0)), 2),
    'ftilt':    (_r((0, 3, (48, 0), (0, 0), 'A', 0)), 5),
    'utilt':    (_r((0, 3, (0, 48), (0, 0), 'A', 0)), 5),
    'dtilt':    (_r((0, 3, (0, -48), (0, 0), 'A', 0)), 7),
    'fsmash':   (_r((0, 2, (0, 0), (80, 0), '', 0)), 12),
    'usmash':   (_r((0, 2, (0, 0), (0, 80), '', 0)), 7),
    'dsmash':   (_r((0, 2, (0, 0), (0, -80), '', 0)), 6),
    'dashattack': (_r((0, 2, (80, 0), (0, 0), 'A', 0)), 4),   # from a run
    'shine':    (_r((0, 2, (0, -80), (0, 0), 'B', 0)), 1),
    'laser':    (_r((0, 2, (0, 0), (0, 0), 'B', 0)), 10),
    'sideb':    (_r((0, 2, (80, 0), (0, 0), 'B', 0)), 20),
    'nair':     (_r((0, 2, (0, 0), (0, 0), 'A', 0)), 4),     # aerials: already airborne
    'fair':     (_r((0, 2, (0, 0), (80, 0), '', 0)), 6),
    'bair':     (_r((0, 2, (0, 0), (-80, 0), '', 0)), 4),
    'uair':     (_r((0, 2, (0, 0), (0, 80), '', 0)), 8),
    'dair':     (_r((0, 2, (0, 0), (0, -80), '', 0)), 5),
    'grab':     (_r((0, 2, (0, 0), (0, 0), 'Z', 0)), 7),
    'taunt':    (_r((0, 2, (0, 0), (0, 0), 'DU', 0)), 1),
}
JUMPSQUAT = {'fox': 3, 'falco': 5}
# centre-to-centre spacing each move was calibrated at (projects/frame-perfect/director/calib.py): approach() walks to it
RANGE = {'jab': 16, 'ftilt': 18, 'utilt': 10, 'dtilt': 18, 'fsmash': 20, 'usmash': 12, 'dsmash': 16, 'shine': 9,
         'sh_nair': 22, 'sh_fair': 26, 'sh_dair': 18, 'sh_uair': 14}   # frames before a jump leaves the ground; 'sh_<aerial>' = short hop, aerial on the first air frame


class Port:
    def __init__(self, film, i):
        self.f, self.i = film, i
        self.tl = [None] * film.n        # per-frame pad state, None = neutral

    def frame(self, t):
        return int(round(t * FPS)) if isinstance(t, float) else int(t)

    def state(self, stick=(0, 0), c=(0, 0), btn='', trig=0, dir=1):
        b = 0
        for k in (btn.split('+') if btn else []):
            b |= BTN[k]
        if trig: b |= BTN['R']
        return (b, int(stick[0] * dir), int(stick[1]), int(c[0] * dir), int(c[1]), int(trig))

    def hold(self, t, dur, stick=(0, 0), c=(0, 0), btn='', trig=0, dir=1):
        """Hold a pad state from t for dur seconds (or frames if dur is an int)."""
        a = self.frame(t); n = int(round(dur * FPS)) if isinstance(dur, float) else int(dur)
        st = self.state(stick, c, btn, trig, dir)
        for k in range(max(0, a), min(self.f.n, a + n)):
            self.tl[k] = st
        return self

    def neutral(self, t, dur):
        a = self.frame(t); n = int(round(dur * FPS)) if isinstance(dur, float) else int(dur)
        for k in range(max(0, a), min(self.f.n, a + n)):
            self.tl[k] = None
        return self

    def approach(self, t0, t1, rng, stick=60):
        """Closed loop, in the game: from t0 until t1 walk toward the opponent while farther than rng, then stand."""
        self.f.cue(t0, 'approach', self.i, rng, self.frame(t1), stick)
        return self

    def move(self, t_hit, name, dir=1, char=None, drift=None, mark=None):
        """Schedule a move so its first active frame lands on t_hit. Returns the input frame.
        mark=N: approach the opponent from N frames before the input (to the move's calibrated range) so it connects."""
        char = char or self.f.chars[self.i]
        if name == 'sh_laser':                                     # hit = the laser striking a standing opponent
            js = JUMPSQUAT[char]
            steps = _r((0, 2, (0, 0), (0, 0), 'X', 0), (js + 8, 2, (0, 0), (0, 0), 'B', 0))
            hit = js + 8 + 12 + 6                                  # spawn 12 frames after B, ~6 frames to cross 36 units
        elif name.startswith('sh_'):
            js = JUMPSQUAT[char]; asteps, ahit = MOVES[name[3:]]
            dx = drift if drift is not None else 56                # drift toward the opponent through the hop
            steps = (_r((0, 2, (dx, 0), (0, 0), 'X', 0), (2, js + ahit + 10, (dx, 0), (0, 0), '', 0))
                     + [dict(s, at=s['at'] + js + 1) for s in asteps])
            hit = js + 1 + ahit
        else:
            steps, hit = MOVES[name]
        hit = self.f.calib.get(char, {}).get(name, hit)
        a = self.frame(t_hit) - (hit - 1) - self.f.fix.get(f'{self.i}:{self.frame(t_hit)}', 0)
        if mark:
            self.approach(max(0, a - mark), a - 1, RANGE.get(name, 16))
        for s in steps:
            self.hold(a + s['at'], s['n'], s['stick'], s['c'], s['btn'], s['trig'], dir)
        self.f.intents.append({'port': self.i, 'move': name, 'hit': self.frame(t_hit), 'input': a})
        return a

    def jump(self, t, full=False):
        return self.hold(t, 6 if full else 2, btn='X')

    def auto(self, t, fastfall=True, lcancel=True, lowlaser=False):
        """Closed-loop tech from t on: fast fall every aerial on its first descending frame, L-cancel every landing;
        lowlaser: in every hop, fast-fall at the apex and fire a laser once low enough to hit a standing opponent."""
        self.f.cue(t, 'auto', self.i, (1 if fastfall else 0) | (2 if lcancel else 0) | (4 if lowlaser else 0))
        return self

    def trace(self, t, until):
        """Log this fighter's position every frame from t until `until` (POS lines), to plan combos."""
        self.f.cue(t, 'trace', self.i, self.frame(until))
        return self

    def airdodge(self, t, stick):
        return self.hold(t, 2, stick=stick, trig=140)

    def wavedash(self, t, dir=1, long=True):
        """Jump, then air-dodge into the floor on the first airborne frame: a slide. long=True is a low angle, farther."""
        char = self.f.chars[self.i]; js = JUMPSQUAT[char]
        a = self.frame(t)
        self.hold(a, 2, btn='X')
        self.airdodge(a + js + 1, (76 * dir, -25) if long else (57 * dir, -57))
        return a + js + 1 + 12                                   # about when the landing ends (calibrate)

    def shine_hit(self, t_hit, dir=1):
        """A shine whose hitbox lands on t_hit; returns the input frame."""
        return self.move(t_hit, 'shine', dir=dir)

    def jc(self, t):
        """Jump-cancel (out of a shine from its 4th frame)."""
        return self.hold(t, 1, btn='X')

    def waveshine(self, t_hit, dir=1, jc_at=6, long=True, ad=0):
        """Shine on t_hit, jump out of it and wavedash toward dir: returns the frame the slide's landing ends.
        jc_at: the jump press, frames after the shine input. On a hit 6 is the first that works (the shine's hitlag eats
        earlier presses, and Melee has no input buffer); 4 on a whiff. The air-dodge goes in on jumpsquat's last frame
        (ad=0), a wavedash with no airborne frames. Hit to hit, a waveshine chain cycles in 22 frames (the tech lab)."""
        char = self.f.chars[self.i]; js = JUMPSQUAT[char]
        a = self.shine_hit(t_hit, dir)
        j = a + jc_at
        self.hold(j, 1, stick=(0, 0), btn='X')
        self.airdodge(j + js + ad, (76 * dir, -25) if long else (57 * dir, -57))    # inputs land the next frame: js + 0
        return j + js + ad + 12

    def shine_chain(self, t0, offsets, dir=1, finish='usmash', di_port=None):
        """Waveshines whose hits land at t0 + offsets (frames; >= 22 apart), then a jump-cancelled up-smash out of the last
        shine (up-smash is one of the few moves jumpsquat accepts). The victim holds down through each shine (DI) so they
        stay on the floor. Returns the frame the up-smash should connect (calibrate with report.py)."""
        a0 = self.frame(t0)
        for k, off in enumerate(offsets[:-1]):
            self.waveshine(a0 + off, dir=dir, long=(k == 0))
            if di_port is not None: self.f.ports[di_port].di(a0 + off, (0, -80))
        last = a0 + offsets[-1]
        if di_port is not None: self.f.ports[di_port].di(last, (0, -80))
        if isinstance(finish, (int, float)):
            self.waveshine(last, dir=dir, long=False)
            return self.move(a0 + int(finish), 'usmash', dir=dir)
        a = self.shine_hit(last, dir)
        if finish == 'usmash':                                     # jump out of the last shine, up-smash inside the jumpsquat
            self.hold(a + 6, 1, btn='X')                           # the earliest jump-cancel: any later and the launched
            self.hold(a + 7, 2, c=(0, 80))                         # victim drifts out of reach (the timing solve tried)
            self.f.intents.append({'port': self.i, 'move': 'jc_usmash', 'hit': a + 14, 'input': a + 7})
            return a + 14
        if isinstance(finish, (int, float)):                       # finish=frame offset: waveshine, then up-smash on that frame
            self.waveshine(last, dir=dir, long=False)
            return self.move(a0 + int(finish), 'usmash', dir=dir)
        return a

    def multishine(self, t, n, every=8, jc=5):
        """n shines in place. Jumpsquat accepts no specials, so each next shine is pressed on jumpsquat's last frame: the frame
        becomes a jump, the shine comes out in the air at height 0, touches the floor and turns into a ground shine. The cycle
        is 8 frames (the tech lab: 7 double-jumps instead); every > 8 waits in the shine before jumping."""
        a = self.frame(t); js = JUMPSQUAT[self.f.chars[self.i]]
        gaps = every if isinstance(every, (list, tuple)) else [every]
        s0 = a
        for k in range(n):
            self.hold(s0, 1, stick=(0, -80), btn='B')
            g = max(gaps[k % len(gaps)], jc + js)
            if k < n - 1:
                self.hold(s0 + g - js, 1, btn='X')
            s0 += g
        return s0

    def di(self, t_hit, stick, lead=4):
        """The victim's directional influence: hold stick through the hitlag of a hit landing on t_hit, from `lead` frames
        before it. Held down, that is a crouch before the hit (a crouch cancel: less knockback) and down DI after it, which
        keeps a waveshined fighter on the floor; the tech lab's chains only held with the crouch."""
        return self.hold(self.frame(t_hit) - lead, 10 + lead, stick=stick)

    def walk(self, t, dur, dir=1, speed=44):
        return self.hold(t, dur, stick=(speed, 0), dir=dir)

    def dash(self, t, dur, dir=1):
        return self.hold(t, dur, stick=(80, 0), dir=dir)

    def crouch(self, t, dur):
        return self.hold(t, dur, stick=(0, -80))

    def shield(self, t, dur):
        return self.hold(t, dur, trig=140)

    def taunt(self, t):
        return self.hold(t, 2, btn='DU')


BOOT = {'debug_vs': 0x0E, 'vs': 0x02, 'title': 0x00, 'menu': 0x01, 'training': 0x1C, 'challenger': 0x14}
NO_MENU = ['const int dir_boot_mode = 0x0E; /* GM_DEBUG_VS */', 'const int dir_nmenu_pads = 0;',
           'const DirMenuPad dir_menu_pads[] = { { 0 } };', 'const int dir_nmenu_gotos = 0;',
           'const DirMenuGoto dir_menu_gotos[] = { { 0 } };']
# character select cells (icon bounds from mncharsel.c): the centre of each icon, for Menu.goto
CSS_COLS = [(-30.0, -24.4), (-24.4, -17.4), (-17.4, -10.4), (-10.4, -3.4), (-3.4, 3.6), (3.6, 10.6), (10.6, 17.6),
            (17.6, 24.4), (24.4, 30.2)]
CSS_ROWS = [(13.0, 20.0), (6.0, 13.0), (-1.0, 6.0)]
CSS_GRID = {'doc': (0, 0), 'mario': (1, 0), 'luigi': (2, 0), 'bowser': (3, 0), 'peach': (4, 0), 'yoshi': (5, 0), 'dk': (6, 0),
            'falcon': (7, 0), 'ganon': (8, 0), 'falco': (0, 1), 'fox': (1, 1), 'ness': (2, 1), 'ics': (3, 1), 'kirby': (4, 1),
            'samus': (5, 1), 'zelda': (6, 1), 'link': (7, 1), 'ylink': (8, 1), 'pichu': (1, 2), 'pikachu': (2, 2),
            'puff': (3, 2), 'mewtwo': (4, 2), 'gnw': (5, 2), 'marth': (6, 2), 'roy': (7, 2), 'geno': (8, 2)}


def css_cell(name):
    c, r = CSS_GRID[name]
    return (sum(CSS_COLS[c]) / 2, sum(CSS_ROWS[r]) / 2)


class Menu:
    """A menu test: boot into one of the game's own modes and drive its menus with pads. Frames are loop frames since boot
    (60 per second); each state is held until the port's next one. No match is set up: the menus choose it.

        m = Menu(boot='vs')
        m.hold(90, 0, 40, stick=(60, 0))     # port 0 pushes right for 40 frames
        m.press(140, 0, 'A')                 # a 3-frame tap
        m.emit('build/csstest.c')
    """
    def __init__(self, boot='vs', len_s=60.0, coll=0):
        self.boot, self.n, self.st, self.gotos, self.coll = BOOT[boot], int(round(len_s * FPS)), {}, [], coll

    def hold(self, f, port, dur, stick=(0, 0), btn='', c=(0, 0), trig=0):
        b = 0
        for k in btn.split('+') if btn else []: b |= BTN.get(k, 0x1000 if k == 'START' else 0)
        tl = self.st.setdefault(port, {})
        for i in range(int(f), int(f) + int(dur)): tl[i] = (b, stick[0], stick[1], c[0], c[1], trig)
        tl.setdefault(int(f) + int(dur), None)
        return self

    def press(self, f, port, btn, dur=3): return self.hold(f, port, dur, btn=btn)

    def goto(self, f, port, dur, target):
        """Steer the port's CSS token to a character's icon (a name from CSS_GRID) or an (x, y) point, closed loop."""
        x, y = css_cell(target) if isinstance(target, str) else target
        self.gotos.append((int(f), int(f) + int(dur), port, x, y))
        return self

    def emit(self, path):
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        ev = []
        for port, tl in self.st.items():
            prev = 'start'
            for i in sorted(tl):
                v = tl[i] or (0, 0, 0, 0, 0, 0)
                if v != prev: ev.append((i, port, v)); prev = v
        ev.sort(key=lambda e: (e[0], e[1]))
        L = ['/* generated by tools/machinima/melee/dsl.py (a menu test): do not edit */', '#include "director.h"', '',
             f'const int dir_boot_mode = {self.boot};', f'const int dir_show_coll = {self.coll};',
             f'const int dir_nmenu_pads = {len(ev)};', 'const DirMenuPad dir_menu_pads[] = {']
        L += [f'    {{ {i}, {p}, {v[5]}, 0x{v[0]:X}, {v[1]}, {v[2]}, {v[3]}, {v[4]} }},' for i, p, v in ev] or ['    { 0 },']
        L += ['};', f'const int dir_nmenu_gotos = {len(self.gotos)};', 'const DirMenuGoto dir_menu_gotos[] = {']
        L += [f'    {{ {a}, {b}, {p}, {x:.3f}f, {y:.3f}f }},' for a, b, p, x, y in self.gotos] or ['    { 0 },']
        L += ['};', 'const DirSetup dir_setup = { 0 };', f'const int dir_len = {self.n};',
              'const int dir_npads = 0;', 'const DirPad dir_pads[] = { { 0 } };',
              'const int dir_ncams = 0;', 'const DirCam dir_cams[] = { { 0 } };',
              'const int dir_ncues = 0;', 'const DirCue dir_cues[] = { { 0 } };']
        open(path, 'w').write('\n'.join(L) + '\n')
        return path


class Film:
    def __init__(self, len_s, calib=None, fix=None):
        self.n = int(round(len_s * FPS))
        self.ports, self.cams, self.cues, self.intents, self.chars, self.labels = [], [], [], [], [], []
        self.calib = json.load(open(calib)) if calib and os.path.exists(calib) else {}
        # the timing solve: per-hit input shifts measured by report.py --fix ('port:hitframe' -> frames late)
        self.fix = json.load(open(fix)) if fix and os.path.exists(fix) else {}
        self.cfg = dict(stage='final_destination', entry=False, seed=1, aspect=0.0, coll=0, stocks=0)
        self.menu = []                   # (loop frame since boot, port, dur, buttons): pads held after the match (menu_hold)

    def setup(self, players, stage='final_destination', seed=1, entry=False, aspect=0.0, coll=0, stocks=0):
        """coll: the developer display, 1 the model with hitboxes and hurtboxes, 2 the capsules only. stocks: a stock match."""
        self.cfg.update(stage=stage, seed=seed, entry=entry, aspect=aspect, coll=coll, stocks=stocks)
        self.players = players
        self.chars = [p[0] for p in players]
        self.ports = [Port(self, i) for i in range(len(players))]
        return self

    def port(self, i):
        return self.ports[i]

    def frame(self, t):
        return int(round(t * FPS)) if isinstance(t, float) else int(t)

    def cam(self, t, eye, at, fov=30.0, roll=0.0, ease='inout', track=None):
        """A camera key. With track ('mid', 'p0', 'p1') eye and at are offsets from that smoothed tracking point."""
        self.cams.append((self.frame(t), EASE[ease], eye, at, fov, roll, TRACK[track]))
        return self

    def orbit(self, t, at, dist, yaw=0.0, pitch=0.0, fov=30.0, roll=0.0, ease='inout', track=None):
        """A camera key by orbit: yaw 0 looks straight at the stage from the front, positive yaw swings to the right."""
        y, p = math.radians(yaw), math.radians(pitch)
        eye = (at[0] + dist * math.sin(y) * math.cos(p), at[1] + dist * math.sin(p), at[2] + dist * math.cos(y) * math.cos(p))
        return self.cam(t, eye, at, fov, roll, ease, track)

    def cue(self, t, kind, port=0, a=0.0, b=0.0, c=0.0):
        self.cues.append((self.frame(t), CUE[kind], port, float(a), float(b), float(c)))
        return self

    def menu_hold(self, boot_frame, port, dur, btn):
        """Hold buttons on a port's MASTER pad from a loop frame since boot (not a script frame) for dur frames: after a
        stock match ends the director's match pads stop, and the game's own scenes read these (e.g. the victory screen
        picks the winner's pose from the button held as it sets up: B, Y or X; gm_1798.c). Start after the match."""
        b = 0
        for k in btn.split('+') if btn else []: b |= BTN.get(k, 0x1000 if k == 'START' else 0)
        self.menu.append((int(boot_frame), port, int(dur), b))
        return self

    def freeze(self, t, on=True): return self.cue(t, 'freeze', a=1 if on else 0)
    def mark(self, t, i, label=None):
        if label: self.labels.append((self.frame(t), label))
        return self.cue(t, 'mark', a=i)
    def percent(self, t, port, pct): return self.cue(t, 'percent', port, pct)
    def setpos(self, t, port, x, y=0.0): return self.cue(t, 'setpos', port, x, y)
    def face(self, t, port, d): return self.cue(t, 'face', port, d)
    def reset(self, t, port, x, face, fresh=False): return self.cue(t, 'reset', port, x, face, 1.0 if fresh else 0.0)  # fresh: clear the stale-move table (labs)
    def status(self, t, port): return self.cue(t, 'status', port)
    def shield(self, t, port): return self.cue(t, 'shield', port)

    # ---- compile
    def pads(self):
        out = []
        for p in self.ports:
            prev = 'start'
            for s, st in enumerate(p.tl):
                if st != prev:
                    out.append((s, p.i, st or (0, 0, 0, 0, 0, 0))); prev = st
        return sorted(out, key=lambda e: (e[0], e[1]))

    def emit(self, path):
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        cams = sorted(self.cams, key=lambda c: c[0]) or [(0, 0, (0, 30, 250), (0, 20, 0), 30.0, 0.0, 0)]
        cues = sorted(self.cues, key=lambda c: c[0])
        pads = self.pads()
        f4 = lambda v: f'{float(v):.4f}f'
        L = ['/* generated by tools/machinima/melee/dsl.py: do not edit */', '#include "director.h"', '']
        ck = [CKIND[c] for c in self.chars] + [0] * (4 - len(self.chars))
        col = [pl[1].get('color', 0) for pl in self.players] + [0] * (4 - len(self.players))
        xs = [pl[1].get('x', 0.0) for pl in self.players] + [0.0] * (4 - len(self.players))
        fc = [pl[1].get('face', 1) for pl in self.players] + [1] * (4 - len(self.players))
        cpu = [pl[1].get('cpu', 0) for pl in self.players] + [0] * (4 - len(self.players))   # 1-9: a CPU at that level
        L.append(f"const DirSetup dir_setup = {{ {STAGE[self.cfg['stage']]}, {len(self.players)}, {int(self.cfg['entry'])}, "
                 f"{{ {', '.join(map(str, ck))} }}, {{ {', '.join(map(str, col))} }}, {{ {', '.join(map(f4, xs))} }}, "
                 f"{{ {', '.join(map(str, fc))} }}, {self.cfg['seed']}u, {f4(self.cfg['aspect'])}, {{ {', '.join(map(str, cpu))} }}, {self.cfg['stocks']} }};")
        if self.menu:                    # menu pads held after the match (menu_hold); a film without them emits NO_MENU unchanged
            ev = sorted([(f0, p, b) for f0, p, d, b in self.menu] + [(f0 + d, p, 0) for f0, p, d, b in self.menu])
            L += ['const int dir_boot_mode = 0x0E; /* GM_DEBUG_VS */', f'const int dir_nmenu_pads = {len(ev)};',
                  'const DirMenuPad dir_menu_pads[] = {'] + [f'    {{ {f0}, {p}, 0, 0x{b:X}, 0, 0, 0, 0 }},' for f0, p, b in ev] + \
                 ['};', 'const int dir_nmenu_gotos = 0;', 'const DirMenuGoto dir_menu_gotos[] = { { 0 } };']
        else:
            L += NO_MENU
        L += [f"const int dir_show_coll = {self.cfg['coll']};"]
        L.append(f'const int dir_len = {self.n};')
        L.append(f'const int dir_npads = {len(pads)};')
        L.append('const DirPad dir_pads[] = {')
        L += [f'    {{ {s}, {p}, {st[5]}, 0x{st[0]:X}u, {st[1]}, {st[2]}, {st[3]}, {st[4]} }},' for s, p, st in pads] or ['    { 0 },']
        L.append('};')
        L.append(f'const int dir_ncams = {len(cams)};')
        L.append('const DirCam dir_cams[] = {')
        for s, e, eye, at, fov, roll, tr in cams:
            L.append(f'    {{ {s}, {e}, {tr}, {{ {", ".join(map(f4, eye))} }}, {{ {", ".join(map(f4, at))} }}, {f4(fov)}, {f4(roll)} }},')
        L.append('};')
        L.append(f'const int dir_ncues = {len(cues)};')
        L.append('const DirCue dir_cues[] = {')
        L += [f'    {{ {s}, {k}, {p}, {f4(a)}, {f4(b)}, {f4(c)} }},' for s, k, p, a, b, c in cues] or ['    { 0 },']
        L.append('};')
        open(path, 'w').write('\n'.join(L) + '\n')
        json.dump({'len': self.n, 'fps': FPS, 'intents': self.intents, 'npads': len(pads), 'ncams': len(cams),
                   'ncues': len(cues), 'chars': self.chars, 'labels': self.labels,
                   'cuts': [cams[i + 1][0] for i in range(len(cams) - 1) if cams[i][1] == 0 and cams[i + 1][0] > cams[i][0]]}, open(os.path.splitext(path)[0] + '.json', 'w'), indent=1)
        return path
