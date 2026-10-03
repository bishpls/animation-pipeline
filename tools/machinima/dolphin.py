"""Dolphin as a plate renderer: boot a GameCube game in an isolated user folder, dump every emulated frame (and the DSP audio) at
a chosen internal resolution, stop after N frames or when the game logs a line, and collect numbered plates for the engine.
  .venv/bin/python tools/machinima/dolphin.py run GAME OUT [--frames 600] [--until 'DIRECTOR END'] [--res 3] [--timeout 900]
  .venv/bin/python tools/machinima/dolphin.py run GAME OUT --logonly --until 'DIRECTOR END'   # no dumps, unthrottled
  .venv/bin/python tools/machinima/dolphin.py log OUT            # the game's OSReport lines from the last run
GAME is a disc image, or an extracted disc's sys/main.dol (Dolphin boots the folder around it as the disc, so a rebuilt DOL
needs no ISO repack). OUT gets f00001.png..., dsp.wav when the mixer dumped, osreport.log (the game's OSReport text, which
Dolphin logs from the IPL UART) and run.json. Plates are renders of game data: keep OUT outside the repo or under a gitignored
path, never commit them.
The emulator is pinned for determinism: single-core CPU, DSP HLE, no cheats, no IPL, no memory cards, custom RTC, and the
emulated CPU overclocked 2x so the game never lags (a lag frame drops an image from the dump; FRAME PERFECT lost one in a
busy pillar until this). Every frame
the game presents is dumped regardless of emulation speed, so a slow machine gives the same plates, only later.
"""
import argparse, fcntl, json, os, re, shutil, signal, subprocess, sys, time

DOLPHIN = os.environ.get('DOLPHIN_BIN', '/Applications/Dolphin.app/Contents/MacOS/Dolphin')
USER = os.path.expanduser(os.environ.get('DOLPHIN_USER', '~/games/dolphin-user'))
OSR = re.compile(r'\[OSREPORT(?:_HLE)?\]:\s?(.*)$')


def ini(sections):
    return ''.join(f'[{s}]\n' + ''.join(f'{k} = {v}\n' for k, v in kv.items()) for s, kv in sections.items())


def configure(user, res, widescreen, png_level, logonly=False, audioonly=False, cpu=2.0):
    """logonly: no frame or audio dumps, and emulation unthrottled (EmulationSpeed 0): for labs read from the game's
    log alone (a kill sweep), which then run as fast as the machine can, with nothing written but the log."""
    cfg = os.path.join(user, 'Config'); os.makedirs(cfg, exist_ok=True)
    open(os.path.join(cfg, 'Dolphin.ini'), 'w').write(ini({
        'Analytics': {'PermissionAsked': 'True', 'Enabled': 'False'},
        'AutoUpdate': {'UpdateTrack': ''},
        'Interface': {'ConfirmStop': 'False', 'UsePanicHandlers': 'False', 'OnScreenDisplayMessages': 'False'},
        # slot A: no memory card (255), unless DOLPHIN_SLOTA says otherwise (8: a GCI folder, USER/GC/USA/Card A, for the
        # labs that check what the game writes to a card)
        'Core': {'SkipIPL': 'True', 'CPUThread': 'False', 'DSPHLE': 'True', 'EnableCheats': 'False',
                 'SlotA': os.environ.get('DOLPHIN_SLOTA', '255'), 'SlotB': '255',
                 'SerialPort1': '255', 'EnableCustomRTC': 'True', 'CustomRTCValue': '0x386d4380', 'SIDevice0': '6',
                 'SIDevice1': '6', 'SIDevice2': '0', 'SIDevice3': '0',
                 # the emulated CPU at 2x: a heavy frame that would lag (two logic frames, one image) renders every frame, so
                 # the dump stays one image per game frame; game logic is unchanged either way
                 'OverclockEnable': str(cpu != 1.0), 'Overclock': str(cpu), **({'EmulationSpeed': '0.0'} if logonly else {})},
        'DSP': {'Backend': 'No Audio Output', 'DumpAudio': str(not logonly), 'DumpAudioSilent': 'True', 'Volume': '0'},
        # audioonly: the game's audio dump without frames (long captures: a stage's music loop), at normal speed
        'Movie': {'DumpFrames': str(not logonly and not audioonly), 'DumpFramesSilent': 'True'},
    }))
    open(os.path.join(cfg, 'GFX.ini'), 'w').write(ini({
        'Settings': {'InternalResolution': str(res), 'DumpFramesAsImages': 'True', 'PNGCompressionLevel': str(png_level),
                     'ShowFPS': 'False', 'wideScreenHack': str(bool(widescreen)), 'AspectRatio': '1' if widescreen else '0'},
        'Enhancements': {'MaxAnisotropy': '4'},
        # present each XFB copy as it is made (SO BACK). On VI timing, two copies could land inside one VI, the first was never
        # shown, and duplicate-present skipping hid the repeat: a deterministic lost image (script frame 7 after the slate)
        'Hacks': {'ImmediateXFBEnable': 'True'},
    }))
    open(os.path.join(cfg, 'Logger.ini'), 'w').write(ini({
        'Options': {'WriteToFile': 'True', 'WriteToConsole': 'False', 'Verbosity': '3'},
        # MASTER carries panic alerts (e.g. "Invalid read from 0x00000000"), which a batch run otherwise swallows: a
        # windowed Dolphin stops on them (Geno's missing costume table read address 0 unseen in every lab)
        'Logs': {'OSREPORT': 'True', 'OSREPORT_HLE': 'True', 'MASTER': 'True', 'MI': 'True', 'POWERPC': 'True', 'VIDEO': 'True'},
    }))


def frames_in(d):
    try:
        return sorted((f for f in os.listdir(d) if f.startswith('framedump_') and f.endswith('.png')),
                      key=lambda f: int(f[10:-4]))
    except FileNotFoundError:
        return []


def osreport(logfile):
    try:
        return [m.group(1) for m in map(OSR.search, open(logfile, errors='replace')) if m]
    except FileNotFoundError:
        return []


def take_slot():
    """DOLPHIN_SLOTS=N (opt-in) waits for one of N machine-wide slots before booting, so parallel agents can't pile up more
    Dolphins than memory allows. The lock is a file lock, released when this process exits (however it exits)."""
    n = int(os.environ.get('DOLPHIN_SLOTS') or 0)
    if not n: return None
    d = os.path.expanduser('~/games/.dolphin-slots'); os.makedirs(d, exist_ok=True)
    t0 = time.time()
    while True:
        for i in range(n):
            f = open(os.path.join(d, f'slot{i}'), 'w')
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                if time.time() - t0 > 1: print(f'dolphin slot {i} after {time.time() - t0:.0f}s', file=sys.stderr)
                return f
            except OSError:
                f.close()
        time.sleep(2)


def run(a):
    user = os.path.abspath(a.user); game = os.path.abspath(a.game)
    slot = take_slot()
    for sub in ('Dump/Frames', 'Dump/Audio', 'Logs'):
        shutil.rmtree(os.path.join(user, sub), ignore_errors=True)
    configure(user, a.res, a.widescreen, a.png, a.logonly, a.audioonly, 1.0 if a.nooverclock else a.cpu)
    dump, logf = os.path.join(user, 'Dump', 'Frames'), os.path.join(user, 'Logs', 'dolphin.log')
    t0 = time.time()
    p = subprocess.Popen([DOLPHIN, '-u', user, '-b', '-e', game], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    why, n = 'exited', 0
    try:
        while p.poll() is None:
            time.sleep(.5)
            n = len(frames_in(dump))
            if a.frames and n >= a.frames: why = 'frames'; break
            if a.until and any(a.until in line for line in osreport(logf)): why = 'until'; break
            if time.time() - t0 > a.timeout: why = 'timeout'; break
            if not a.quiet: print(f'\r{n} frames  {time.time() - t0:5.0f}s', end='', flush=True)
    finally:
        if p.poll() is None:
            p.send_signal(signal.SIGINT)                  # first signal: Dolphin stops emulation cleanly and closes the dumps
            try: p.wait(8)
            except subprocess.TimeoutExpired: p.kill(); p.wait()
    if not a.quiet: print()
    collect(user, a.out, a.frames, why, time.time() - t0, game, a)


def collect(user, out, want, why, secs, game, a):
    os.makedirs(out, exist_ok=True)
    for f in os.listdir(out):
        if re.fullmatch(r'f\d{5}\.png|dsp\.wav|dtk\.wav', f): os.remove(os.path.join(out, f))
    fs = frames_in(os.path.join(user, 'Dump', 'Frames'))
    if want: fs = fs[:want]
    for i, f in enumerate(fs):
        os.replace(os.path.join(user, 'Dump', 'Frames', f), os.path.join(out, f'f{i + 1:05d}.png'))
    audio = []
    for f in sorted(os.listdir(os.path.join(user, 'Dump', 'Audio')) if os.path.isdir(os.path.join(user, 'Dump', 'Audio')) else []):
        if f.endswith('.wav') and os.path.getsize(os.path.join(user, 'Dump', 'Audio', f)) > 44:
            name = 'dtk.wav' if f.endswith('dtkdump.wav') else 'dsp.wav'   # dsp: voices and SFX; dtk: streamed disc audio
            shutil.copy(os.path.join(user, 'Dump', 'Audio', f), os.path.join(out, name)); audio.append(name)
    lines = osreport(os.path.join(user, 'Logs', 'dolphin.log'))
    open(os.path.join(out, 'osreport.log'), 'w').write('\n'.join(lines) + '\n')
    meta = {'game': game, 'frames': len(fs), 'stop': why, 'seconds': round(secs, 1), 'res': a.res, 'widescreen': a.widescreen,
            'audio': audio, 'osreport_lines': len(lines), 'dolphin': subprocess.run([DOLPHIN, '--version'], capture_output=True,
                                                                                    text=True).stdout.strip()}
    json.dump(meta, open(os.path.join(out, 'run.json'), 'w'), indent=1)
    print(json.dumps(meta))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    r = sp.add_parser('run'); r.add_argument('game'); r.add_argument('out')
    r.add_argument('--frames', type=int, default=0); r.add_argument('--until', default='')
    r.add_argument('--res', type=int, default=3); r.add_argument('--widescreen', action='store_true')
    r.add_argument('--png', type=int, default=1, help='PNG zlib level for dumps (1 is fast; plates are re-encoded later)')
    r.add_argument('--timeout', type=float, default=900); r.add_argument('--user', default=USER); r.add_argument('--quiet', action='store_true')
    r.add_argument('--logonly', action='store_true', help='no frame or audio dumps, emulation unthrottled: stop with --until')
    r.add_argument('--nooverclock', action='store_true', help="the console's CPU speed (the labs run it at 2x so dumps never lag): for lag measurement")
    r.add_argument('--cpu', type=float, default=2.0, help='the emulated CPU clock as a multiple of the console\'s (below 1: a slower console, for '
                   'a lag measure\'s positive control and for headroom: the slowest clock a scene still runs without lag)')
    r.add_argument('--audioonly', action='store_true', help='the audio dump without frames, normal speed: stop with --until')
    lg = sp.add_parser('log'); lg.add_argument('out')
    a = ap.parse_args()
    if a.cmd == 'run': run(a)
    else: print(open(os.path.join(a.out, 'osreport.log')).read(), end='')
