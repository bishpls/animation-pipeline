"""Bulk data between the laptop and the boxes through their bucket, not the IAP tunnel (1-3 MB/s, and ssh drops under
load). A content-addressed store in the boxes' existing bucket: every file is a blob named by its sha256
(<bucket>/cas/<aa>/<sha>), a manifest (itself a blob, cas/m/<sha>) lists a tree's paths, blobs, modes and mtimes, and each
side moves only the blobs the other lacks. Control (ssh commands, starting builds) stays on IAP; one ssh per transfer
tells the box which manifest to apply. Standard library only, Python 3.9+: the box runs this file with its system
python3, sent over the ssh's stdin (a worktree's first sync has no copy on the box to run it from).

Run by infra/gcp/build.sh (which sources the box's env file: BUCKET, VM, and the ssh config over IAP):

    python3 charkit/bucketsync.py sync WORKTREE DEST        the worktree's code and inputs to DEST on the box (/srv/work/<name>)
    python3 charkit/bucketsync.py fetch REMOTE LOCAL        a box directory (a build's outputs) into LOCAL: only what differs
    python3 charkit/bucketsync.py push LOCAL REMOTE [--link]  a file or directory onto the box (no deletes, like rsync)
    python3 charkit/bucketsync.py pull NAME LOCAL           a tree the box published under NAME (the gate's report)
    python3 charkit/bucketsync.py verify WORKTREE DEST      check the box's copy against the worktree, file by file

The same file on the box (python3 - CMD ... with this file on stdin):

    materialize MANIFEST DEST [--copy] [--no-delete]        apply a manifest: fetch missing blobs into the box's blob
                                                            cache, link or copy them into place, delete what left
    publish PATH [--name NAME]                              hash PATH's files, upload the missing blobs, print the manifest
    check MANIFEST DEST                                     a copy against a manifest (missing, content, mode, extra)

Inputs are hard-linked from the box's blob cache (/srv/work/.cas/blobs, read-only files: a write through a link fails
loudly instead of reaching every copy that shares it); outputs are never linked (charkit's cache.unshare lesson): a
publish only reads them, and the laptop writes each fetched file as a new file (temp + rename). Credentials: the
laptop user's (gcloud auth print-access-token, cached until it expires) and the box's service account (the metadata
server); the bucket's name comes from the env file, never from here.
"""
import concurrent.futures as cf
import hashlib, http.client, json, os, random, shlex, shutil, stat, subprocess, sys, tempfile, threading, time
import urllib.parse, urllib.request

HOST = 'storage.googleapis.com'
PREFIX = 'cas'                                       # blobs: cas/<aa>/<sha>; manifests: cas/m/<sha>; names: cas/n/<name>
SKIP = {'.git', '__pycache__', '.cache'}             # never synced, never deleted (build.sh's rsync excludes)
WORK = os.environ.get('BS_WORK', '/srv/work')        # the box's copies (tests point it elsewhere)
BOXCAS = os.path.join(WORK, '.cas')                  # the box's blob cache (same filesystem as the copies: hard links)
CHUNK = 1 << 20
SLICE = 8 << 20                                      # a bigger blob downloads in ranged slices of ~4 MB (a lone big
                                                     # file was a fetch's tail: 18 -> 22.6 MB/s on a 62 MB board)
THREADS = int(os.environ.get('BS_THREADS', 0)) or (32 if os.environ.get('BS_ROLE') == 'box' else 16)
HEAD_MAX = 256                                       # more unknown blobs than this: list the store instead of asking each
ADOPT_OVER = 4 << 20                                 # a sync lacking more than this asks the box's copies first
CACHE_HOME = os.path.join(os.environ.get('XDG_CACHE_HOME') or os.path.expanduser('~/.cache'), 'charkit', 'bucketsync')


def log(*a):
    print(*a, file=sys.stderr, flush=True)


class Missing(Exception):
    """blobs a manifest names that the bucket doesn't have (the laptop's record of what's there was stale)."""
    def __init__(self, shas):
        super().__init__('%d blobs missing from the bucket' % len(shas))
        self.shas = shas


# ------------------------------------------------------------------------------------------------------------ the bucket
class Token:
    """an access token: the box's service account (metadata server) or the laptop user's (gcloud), kept until it
    expires (on disk on the laptop, mode 600: gcloud itself costs ~1 s a call)."""
    def __init__(self):
        self.box = os.environ.get('BS_ROLE') == 'box'
        self.lock = threading.Lock()
        self.tok, self.exp = None, 0
        self.path = os.path.join(CACHE_HOME, 'token.json')    # (the laptop's: one per gcloud config, _laptop)

    def get(self, refresh=False):
        with self.lock:
            if refresh or not self.tok or time.time() > self.exp - 120:
                self.tok, self.exp = self._box() if self.box else self._laptop(refresh)
            return self.tok

    def _box(self):
        req = urllib.request.Request('http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/'
                                     'default/token', headers={'Metadata-Flavor': 'Google'})
        d = json.load(urllib.request.urlopen(req, timeout=10))
        return d['access_token'], time.time() + int(d['expires_in'])

    def _laptop(self, refresh):
        cfg = gcloud_config()
        if cfg:                                          # the box-control service account's: its own token
            self.path = os.path.join(CACHE_HOME, 'token-%s.json' % hashlib.sha256(cfg.encode()).hexdigest()[:12])
        if not refresh:
            try:
                d = json.load(open(self.path))
                if d['exp'] > time.time() + 300:
                    return d['token'], d['exp']
            except (OSError, ValueError, KeyError):
                pass
        r = subprocess.run(['gcloud', 'auth', 'print-access-token'], capture_output=True, text=True)
        if r.returncode != 0 or not r.stdout.strip():
            raise SystemExit('bucketsync: gcloud has no valid login (%s): %s' % (
                (r.stderr.strip().splitlines() or ['no token'])[-1], 'the service account config %s: see '
                'docs/workstreams/infra-auth.md' % cfg if cfg else 'run `gcloud auth login`'))
        tok = r.stdout.strip()
        exp = time.time() + 300                          # gcloud may hand back a cached token near its end
        try:
            info = json.load(urllib.request.urlopen('https://oauth2.googleapis.com/tokeninfo?access_token=' + tok,
                                                    timeout=10))
            exp = time.time() + int(info.get('expires_in', 300))
        except (OSError, ValueError):
            pass
        os.makedirs(CACHE_HOME, exist_ok=True)
        fd = os.open(self.path + '.tmp', os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w') as f:
            json.dump(dict(token=tok, exp=exp), f)
        os.replace(self.path + '.tmp', self.path)
        return tok, exp


def gcloud_config():
    """the laptop's gcloud config for the box: CLOUDSDK_CONFIG (build.sh exports its env file's), else the env file's
    own (CHARKIT_BOX_ENV, else infra/gcp/build.env beside this file's repo) put in the environment -> it, or None
    (gcloud's default login)."""
    if os.environ.get('CLOUDSDK_CONFIG'):
        return os.environ['CLOUDSDK_CONFIG']
    env = os.environ.get('CHARKIT_BOX_ENV') or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(
        __file__))), 'infra', 'gcp', 'build.env')
    try:
        for line in open(env):
            line = line[len('export '):] if line.startswith('export ') else line
            if line.startswith('CLOUDSDK_CONFIG='):
                v = os.path.expanduser(os.path.expandvars(line.split('=', 1)[1].split('#')[0].strip()))
                if v:
                    os.environ['CLOUDSDK_CONFIG'] = v
                    return v
    except OSError:
        pass
    return None


class Bucket:
    """the GCS JSON API over kept-alive HTTPS connections (a pool the threads share)."""
    def __init__(self, url):
        self.name = url[5:].strip('/') if url.startswith('gs://') else url.strip('/')
        self.token = Token()
        self.pool = []                                # idle kept-alive connections (thread pools come and go)
        self.lock = threading.Lock()
        self.stale = False

    def _conn(self):
        with self.lock:
            if self.pool:
                return self.pool.pop()
        return http.client.HTTPSConnection(HOST, timeout=300, blocksize=CHUNK)

    def _release(self, c):
        with self.lock:
            self.pool.append(c)

    def _o(self, name):
        return '/storage/v1/b/%s/o/%s' % (self.name, urllib.parse.quote(name, safe=''))

    def request(self, method, path, body=None, headers=None, ok=(200,), sink=None, tries=6):
        """one call, retried on a dropped connection, 429/5xx or an expired token. body: bytes or a callable
        returning a fresh file object; sink(response) reads a streamed body (it's rerun from the start on a retry)."""
        for i in range(tries):
            c = self._conn()
            h = {'Authorization': 'Bearer ' + self.token.get(refresh=self.stale)}
            self.stale = False
            h.update(headers or {})
            b = None
            try:
                b = body() if callable(body) else body
                c.request(method, path, body=b, headers=h)
                r = c.getresponse()
                if r.status in ok:
                    out = sink(r) if sink else (r.status, r.read())
                    self._release(c)
                    return out
                data = r.read()
                self._release(c)
                if r.status == 401:
                    self.stale = True
                    continue
                if r.status in (408, 429) or r.status >= 500:
                    if i == tries - 1:
                        return r.status, data
                    time.sleep(min(30, 0.5 * 2 ** i) * (0.5 + random.random()))
                    continue
                return r.status, data
            except (OSError, http.client.HTTPException):
                c.close()                             # a dropped or half-read connection isn't reused
                if i == tries - 1:
                    raise
                time.sleep(min(30, 0.5 * 2 ** i) * (0.5 + random.random()))
            finally:
                if hasattr(b, 'close'):
                    b.close()
        raise ConnectionError('gave up after %d tries' % tries)

    def exists(self, name):
        s, _ = self.request('GET', self._o(name) + '?fields=size', ok=(200, 404))
        return s == 200

    def list(self, prefix):
        out, tok = [], None
        while True:
            q = dict(prefix=prefix, fields='items(name),nextPageToken', maxResults=1000)
            if tok:
                q['pageToken'] = tok
            s, data = self.request('GET', '/storage/v1/b/%s/o?%s' % (self.name, urllib.parse.urlencode(q)))
            d = json.loads(data)
            out += [i['name'] for i in d.get('items', ())]
            tok = d.get('nextPageToken')
            if not tok:
                return out

    def upload(self, name, path=None, data=None, overwrite=False):
        """a file or bytes as object NAME. Content-addressed names never overwrite (ifGenerationMatch=0: a blob
        someone else just wrote is the same bytes)."""
        q = dict(uploadType='media', name=name)
        if not overwrite:
            q['ifGenerationMatch'] = 0
        size = os.path.getsize(path) if path else len(data)
        s, body = self.request('POST', '/upload/storage/v1/b/%s/o?%s' % (self.name, urllib.parse.urlencode(q)),
                               body=(lambda: open(path, 'rb')) if path else data, ok=(200, 412),
                               headers={'Content-Type': 'application/octet-stream', 'Content-Length': str(size)})
        if s not in (200, 412):
            raise OSError('upload %s: HTTP %d %s' % (name, s, body[:300]))
        return size

    def get(self, name):
        s, data = self.request('GET', self._o(name) + '?alt=media', ok=(200, 404))
        if s == 404:
            return None
        return data

    def download(self, name, dest, size=None, sha=None):
        """object NAME into file DEST (written in place: DEST is a temp path of the caller's), checked against sha.
        A big blob comes in ranged slices in parallel (inside GCP one stream is the limit, not the network)."""
        if size and size > SLICE and THREADS >= 8:
            n = min(16, -(-size // (4 << 20)))
            with open(dest, 'wb') as f:
                f.truncate(size)
            def part(k):
                a, b = k * size // n, (k + 1) * size // n - 1
                fd = os.open(dest, os.O_WRONLY)
                try:
                    def sink(r, fd=fd, a=a):
                        off = a
                        while True:
                            buf = r.read(CHUNK)
                            if not buf:
                                return off - a
                            os.pwrite(fd, buf, off)
                            off += len(buf)
                    got = self.request('GET', self._o(name) + '?alt=media', headers={'Range': 'bytes=%d-%d' % (a, b)},
                                       ok=(206,), sink=sink)
                    if not isinstance(got, int):
                        if got[0] == 404:
                            raise FileNotFoundError(name)
                        raise OSError('download %s: HTTP %s' % (name, got[0]))
                    if got != b - a + 1:
                        raise OSError('download %s: short slice' % name)
                finally:
                    os.close(fd)
            with cf.ThreadPoolExecutor(n) as ex:
                list(ex.map(part, range(n)))
            if sha and file_sha(dest) != sha:
                raise OSError('download %s: sha256 mismatch' % name)
            return size

        def sink(r):
            h = hashlib.sha256()
            n = 0
            with open(dest, 'wb') as f:
                while True:
                    buf = r.read(CHUNK)
                    if not buf:
                        break
                    h.update(buf)
                    f.write(buf)
                    n += len(buf)
            return h.hexdigest(), n
        got = self.request('GET', self._o(name) + '?alt=media', ok=(200,), sink=sink)
        if not isinstance(got[0], str):
            if got[0] == 404:
                raise FileNotFoundError(name)
            raise OSError('download %s: HTTP %s %s' % (name, got[0], got[1][:300]))
        if sha and got[0] != sha:
            raise OSError('download %s: sha256 mismatch' % name)
        return got[1]


def blob(sha):
    return '%s/%s/%s' % (PREFIX, sha[:2], sha)


def mblob(sha):
    return '%s/m/%s' % (PREFIX, sha)


def file_sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while True:
            b = f.read(CHUNK)
            if not b:
                return h.hexdigest()
            h.update(b)


class Known:
    """the blobs this side knows the bucket has (it uploaded or checked them): a text file of shas, appended. A stale
    entry heals itself: the box reports a blob it can't fetch, and it's uploaded again."""
    def __init__(self, path):
        self.path = path
        self.lock = threading.Lock()
        try:
            self.s = set(open(path).read().split())
        except OSError:
            self.s = set()

    def add(self, shas):
        new = [s for s in shas if s not in self.s]
        if not new:
            return
        with self.lock:
            self.s.update(new)
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, 'a') as f:
                f.write(''.join(s + '\n' for s in new))

    def drop(self, shas):
        with self.lock:
            self.s.difference_update(shas)
            tmp = '%s.%d' % (self.path, os.getpid())
            with open(tmp, 'w') as f:
                f.write(''.join(s + '\n' for s in sorted(self.s)))
            os.replace(tmp, self.path)


def present(bk, shas):
    """which of shas the bucket has: one metadata call each for a few, else a listing of the store's prefixes."""
    shas = set(shas)
    if not shas:
        return set()
    with cf.ThreadPoolExecutor(THREADS) as ex:
        if len(shas) <= HEAD_MAX:
            s = sorted(shas)
            return {x for x, ok in zip(s, ex.map(lambda x: bk.exists(blob(x)), s)) if ok}
        pre = sorted({x[:2] for x in shas})
        names = [n for ns in ex.map(lambda p: bk.list('%s/%s/' % (PREFIX, p)), pre) for n in ns]
    return shas & {n.rsplit('/', 1)[1] for n in names}


def lacking(bk, need, known):
    """the blobs in need the bucket lacks (those this side doesn't already know it has are checked)."""
    unknown = set(need) - known.s
    have = present(bk, unknown)
    known.add(have)
    return unknown - have


def upload_blobs(bk, need, known, path_of, miss=None):
    """the blobs in need the bucket lacks, uploaded in parallel (biggest first) -> (count, bytes)."""
    miss = sorted(lacking(bk, need, known) if miss is None else miss, key=lambda s: -os.path.getsize(path_of[s]))
    if not miss:
        return 0, 0
    def up(s):
        n = bk.upload(blob(s), path=path_of[s])
        known.add([s])
        return n
    with cf.ThreadPoolExecutor(min(THREADS, len(miss))) as ex:
        sizes = list(ex.map(up, miss))
    return len(miss), sum(sizes)


def put_manifest(bk, m, known, name=None):
    data = json.dumps(m, separators=(',', ':'), sort_keys=True).encode()
    sha = hashlib.sha256(data).hexdigest()
    if sha not in known.s:
        bk.upload(mblob(sha), data=data)
        known.add([sha])
    if name:
        bk.upload('%s/n/%s' % (PREFIX, name), data=sha.encode(), overwrite=True)
    return sha


def get_manifest(bk, sha):
    data = bk.get(mblob(sha))
    if data is None or hashlib.sha256(data).hexdigest() != sha:
        raise SystemExit('bucketsync: manifest %s missing or corrupt in the bucket' % sha)
    return json.loads(data)


# --------------------------------------------------------------------------------------------------- the laptop's trees
def git_paths(wt, *args):
    r = subprocess.run(['git', '-C', wt, 'ls-files', '-z'] + list(args), capture_output=True, check=True)
    return [os.fsdecode(p) for p in r.stdout.split(b'\0') if p]


def skipped(rel):
    return any(c in SKIP for c in rel.split('/'))


def sync_paths(wt):
    """build.sh sync's set: tracked and untracked-not-ignored files on disk (a sparse checkout's absent ones aren't),
    plus charkit/out/remote/*.json (portable specs); nothing else under charkit/out (charkit/out/i3d, TRELLIS's output,
    is no longer sent: no build reads it since the sheet-only outfit masks, decision 8), nothing under .git, __pycache__
    or .cache. -> (paths, the ignored paths the box must keep)."""
    out = []
    for rel in git_paths(wt, '--cached', '--others', '--exclude-standard'):
        if not rel.startswith('charkit/out/') and not skipped(rel):
            out.append(rel)
    rem = os.path.join(wt, 'charkit', 'out', 'remote')
    if os.path.isdir(rem):
        out += ['charkit/out/remote/' + f for f in os.listdir(rem) if f.endswith('.json')]
    keep = [p for p in git_paths(wt, '--others', '--ignored', '--exclude-standard', '--directory')
            if not p.startswith('charkit/out')]
    return sorted(set(out)), keep


def walk_paths(root):
    """every file and symlink under root (a directory), relative, SKIP left out."""
    out = []
    for d, ds, fs in os.walk(root):
        ds[:] = [x for x in ds if x not in SKIP]
        for x in ds:
            if os.path.islink(os.path.join(d, x)):
                out.append(os.path.relpath(os.path.join(d, x), root))
        out += [os.path.relpath(os.path.join(d, f), root) for f in fs]
    return sorted(out)


class StatCache:
    """sha256 by path, reused while (size, mtime, inode) hold and the hash was taken after the file settled."""
    def __init__(self, path):
        self.path = path
        try:
            self.d = json.load(open(path))
        except (OSError, ValueError):
            self.d = {}
        self.dirty = False

    def sha(self, full, st):
        key = [st.st_size, st.st_mtime_ns, st.st_ino]
        m = self.d.get(full)
        if m and m[:3] == key and m[4] - st.st_mtime_ns / 1e9 > 2:
            return m[3]
        h = file_sha(full)
        self.d[full] = key + [h, time.time()]
        self.dirty = True
        return h

    def save(self):
        if self.dirty:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            tmp = '%s.%d' % (self.path, os.getpid())
            json.dump(self.d, open(tmp, 'w'))
            os.replace(tmp, self.path)


def scan(root, rels, cache=None):
    """a manifest's entries for root/rel: files [rel, sha, size, exec, mtime_ns] and links [rel, target], hashed in
    parallel (hashlib releases the GIL) -> (files, links, {sha: a path holding it})."""
    files, links, where = [], [], {}
    todo = []
    for rel in rels:
        full = os.path.join(root, rel)
        try:
            st = os.lstat(full)
        except OSError:
            continue
        if stat.S_ISLNK(st.st_mode):
            links.append([rel, os.readlink(full)])
        elif stat.S_ISREG(st.st_mode):
            todo.append((rel, full, st))
    def h(t):
        rel, full, st = t
        return cache.sha(full, st) if cache else file_sha(full)
    with cf.ThreadPoolExecutor(min(THREADS, 12)) as ex:
        shas = list(ex.map(h, todo))
    for (rel, full, st), sha in zip(todo, shas):
        files.append([rel, sha, st.st_size, 1 if st.st_mode & 0o100 else 0, st.st_mtime_ns])
        where.setdefault(sha, full)
    return files, links, where


def known_set():
    return Known(os.path.join(CACHE_HOME, hashlib.sha256(os.environ['BUCKET'].encode()).hexdigest()[:16], 'known'))


# -------------------------------------------------------------------------------------------------------- ssh to the box
def box_run(args, capture=True):
    """this file run on the box (python3 - ARGS, the file on stdin) over build.sh's ssh config (IAP)."""
    cfg, vm = os.environ['BS_SSHCFG'], os.environ['VM']
    env = 'BS_ROLE=box BUCKET=%s' % shlex.quote(os.environ['BUCKET'])
    cmd = '%s python3 - %s' % (env, ' '.join(shlex.quote(a) for a in args))
    src = open(os.path.abspath(__file__), 'rb').read()
    r = subprocess.run(['ssh', '-F', cfg, vm, cmd], input=src, stdout=subprocess.PIPE if capture else None)
    return r.returncode, (r.stdout.decode(errors='replace') if capture else '')


def box_install(bucket):
    """for an ssh session of someone else's (a gate's, a remote build's): a shell group that saves this file, sent on
    the session's stdin, on the box under its content's name (stdin is always drained, so nothing after reads it), and
    the command that runs it there -> (group, runner, the file's bytes). The session publishes its outputs itself, so
    they come back without a second connection through the tunnel."""
    src = open(os.path.abspath(__file__), 'rb').read()
    f = '%s/bin/bucketsync-%s.py' % (BOXCAS, hashlib.sha256(src).hexdigest()[:12])
    prefix = ('{ mkdir -p %s/bin && cat > %s.$$ && { [ -s %s ] || mv %s.$$ %s; }; rm -f %s.$$; }'
              % (BOXCAS, f, f, f, f, f))
    runner = 'BS_ROLE=box BUCKET=%s python3 %s' % (shlex.quote(bucket), f)
    return prefix, runner, src


def box_apply(bk, known, msha, dest, where, extra=(), sent=None):
    """materialize a manifest on the box. Blobs neither the bucket nor the box's copies have (it reports them) are
    uploaded from here and it's rerun; blobs the box found in its copies it uploaded itself (reported, learned here).
    sent: [count, bytes] uploaded from here, added to."""
    for attempt in range(2):
        rc, out = box_run(['materialize', msha, dest] + list(extra))
        miss = [l.split()[1] for l in out.splitlines() if l.startswith('BUCKETSYNC-MISSING ')]
        known.add([l.split()[1] for l in out.splitlines() if l.startswith('BUCKETSYNC-ADOPTED ')])
        for l in out.splitlines():
            if l.startswith('BUCKETSYNC ') or not l.startswith('BUCKETSYNC'):
                print(l)
        if rc == 3 and miss and attempt == 0:
            known.drop(miss)
            n, nb = upload_blobs(bk, miss, known, where, miss=miss)
            log('bucketsync: %d blobs (%.1f MB) the bucket and the box lacked, sent from here' % (n, nb / 1e6))
            if sent is not None:
                sent[0] += n
                sent[1] += nb
            continue
        return rc
    return rc


class Clock:
    def __init__(self):
        self.t0 = self.t = time.time()
        self.laps = {}

    def lap(self, k):
        t = time.time()
        self.laps[k] = round(t - self.t, 2)
        self.t = t

    def total(self):
        return round(time.time() - self.t0, 2)


def record(kind, **kw):
    """one line per transfer in ~/.cache/charkit/bucketsync/log.jsonl: the numbers behind the timing table."""
    try:
        os.makedirs(CACHE_HOME, exist_ok=True)
        with open(os.path.join(CACHE_HOME, 'log.jsonl'), 'a') as f:
            f.write(json.dumps(dict(kind=kind, at=time.strftime('%Y-%m-%dT%H:%M:%S'), **kw)) + '\n')
    except OSError:
        pass


def cmd_sync(wt, dest):
    wt = os.path.abspath(wt)
    ck = Clock()
    bk, known = Bucket(os.environ['BUCKET']), known_set()
    rels, keep = sync_paths(wt)
    ck.lap('list')
    sc = StatCache(os.path.join(CACHE_HOME, 'stat', hashlib.sha256(wt.encode()).hexdigest()[:16] + '.json'))
    files, links, where = scan(wt, rels, sc)
    sc.save()
    ck.lap('hash')
    # the laptop's uplink is the slow link (~1.3-1.9 MB/s, the same through IAP or to the bucket): a small gap is sent
    # first; a big one is offered to the box, which looks for those blobs in its own copies before asking for them
    miss = lacking(bk, {f[1] for f in files}, known)
    size_of = {f[1]: f[2] for f in files}
    sent = [0, 0]
    if sum(size_of[x] for x in miss) <= ADOPT_OVER:
        sent = list(upload_blobs(bk, miss, known, where, miss=miss))
    m = dict(v=1, kind='sync', files=files, links=links, keep=keep)
    msha = put_manifest(bk, m, known)
    ck.lap('upload')
    rc = box_apply(bk, known, msha, dest, where, sent=sent)
    ck.lap('box')
    n, nb = sent
    size = sum(f[2] for f in files)
    print('bucketsync sync: %d files, %.0f MB; uploaded %d blobs, %.1f MB; %.1f s (%s); exit %d'
          % (len(files), size / 1e6, n, nb / 1e6, ck.total(), ' '.join('%s %.1f' % kv for kv in ck.laps.items()), rc))
    record('sync', wt=os.path.basename(wt), files=len(files), bytes=size, up_blobs=n, up_bytes=nb, seconds=ck.total(),
           laps=ck.laps, rc=rc)
    return rc


def cmd_push(local, remote, link=False):
    """build.sh push: rsync's semantics (a directory with a trailing slash sends its contents; no deletes)."""
    ck = Clock()
    bk, known = Bucket(os.environ['BUCKET']), known_set()
    local_abs = os.path.abspath(local)
    if os.path.isdir(local_abs):
        root = local_abs
        rels = walk_paths(root)
        if not local.endswith('/'):
            remote = remote.rstrip('/') + '/' + os.path.basename(local_abs)
        dest, prefix = remote.rstrip('/') or '/', ''
    else:
        root = os.path.dirname(local_abs)
        rels = [os.path.basename(local_abs)]
        if remote.endswith('/'):
            dest, prefix = remote.rstrip('/'), ''
        else:                                        # a file to a path: the box decides whether it's a directory
            dest, prefix = remote, None
    files, links, where = scan(root, rels)
    n, nb = upload_blobs(bk, {f[1] for f in files}, known, where)
    m = dict(v=1, kind='push', files=files, links=links)
    if prefix is None:
        m['as_file'] = True
    msha = put_manifest(bk, m, known)
    ck.lap('upload')
    rc = box_apply(bk, known, msha, dest, where, ['--no-delete'] + ([] if link else ['--copy']))
    print('bucketsync push: %d files, %.1f MB; uploaded %.1f MB; %.1f s; exit %d'
          % (len(files), sum(f[2] for f in files) / 1e6, nb / 1e6, ck.total(), rc))
    record('push', files=len(files), bytes=sum(f[2] for f in files), up_bytes=nb, seconds=ck.total(), rc=rc)
    return rc


def pull(bk, msha, local):
    """a manifest's files into local: what's already there (same size and mtime, or same sha) stays; the rest is
    downloaded to a temp file beside it and renamed over (never written through: a fetched output may share an inode
    with another copy). No deletes (rsync fetch had none). -> (files, bytes, downloaded files, downloaded bytes)."""
    m = get_manifest(bk, msha)
    os.makedirs(local, exist_ok=True)
    sc = StatCache(os.path.join(CACHE_HOME, 'stat', 'fetch.json'))
    todo = {}
    for rel, sha, size, x, mt in m['files']:
        p = os.path.join(local, rel)
        try:
            st = os.lstat(p)
        except OSError:
            st = None
        if st and stat.S_ISREG(st.st_mode) and st.st_size == size:
            if st.st_mtime_ns == mt or sc.sha(p, st) == sha:
                if st.st_mtime_ns != mt:
                    os.utime(p, ns=(mt, mt))
                continue
        todo.setdefault(sha, []).append((p, size, x, mt))
    for rel, target in m.get('links', ()):
        p = os.path.join(local, rel)
        if os.path.islink(p) and os.readlink(p) == target:
            continue
        os.makedirs(os.path.dirname(p), exist_ok=True)
        tmp = p + '.bs-%d' % os.getpid()
        os.symlink(target, tmp)
        os.replace(tmp, p)
    def get(item):
        sha, dests = item
        p, size, x, mt = dests[0]
        os.makedirs(os.path.dirname(p), exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix='.bs-', dir=os.path.dirname(p))
        os.close(fd)
        try:
            bk.download(blob(sha), tmp, size=size, sha=sha)
            os.chmod(tmp, 0o755 if x else 0o644)
            os.utime(tmp, ns=(mt, mt))
            for q, _, x2, mt2 in dests[1:]:
                os.makedirs(os.path.dirname(q), exist_ok=True)
                t2 = q + '.bs-%d' % os.getpid()
                shutil.copy2(tmp, t2)
                os.chmod(t2, 0o755 if x2 else 0o644)
                os.utime(t2, ns=(mt2, mt2))
                os.replace(t2, q)
            os.replace(tmp, p)
        except BaseException:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise
        return size
    items = sorted(todo.items(), key=lambda kv: -kv[1][0][1])
    got = 0
    if items:
        with cf.ThreadPoolExecutor(min(THREADS, len(items))) as ex:
            got = sum(ex.map(get, items))
    sc.save()
    return len(m['files']), sum(f[2] for f in m['files']), sum(len(v) for v in todo.values()), got


def cmd_fetch(remote, local):
    """a box directory into local: the box publishes it (one ssh), this side downloads what it lacks."""
    ck = Clock()
    bk = Bucket(os.environ['BUCKET'])
    rc, out = box_run(['publish', remote])
    lines = [l for l in out.splitlines() if l.startswith('BUCKETSYNC-MANIFEST ')]
    if rc != 0 or not lines:
        log(out)
        log('bucketsync fetch: the box could not publish %s (exit %d)' % (remote, rc))
        return rc or 1
    msha = lines[-1].split()[1]
    ck.lap('box')
    boxside = lines[-1].split(';', 1)[-1].strip()
    nf, nbytes, got_f, got_b = pull(bk, msha, local)
    ck.lap('download')
    print('bucketsync fetch: %d files, %.1f MB; downloaded %d, %.1f MB; %.1f s (%s; box: %s)'
          % (nf, nbytes / 1e6, got_f, got_b / 1e6, ck.total(), ' '.join('%s %.1f' % kv for kv in ck.laps.items()),
             boxside))
    record('fetch', path=remote, manifest=msha, files=nf, bytes=nbytes, got_files=got_f, got_bytes=got_b,
           seconds=ck.total(), laps=ck.laps, box=boxside)
    return 0


def cmd_verify(wt, dest):
    """the box's copy of a worktree checked against the worktree as it is now (no sync): the sync's correctness,
    measured."""
    wt = os.path.abspath(wt)
    bk, known = Bucket(os.environ['BUCKET']), known_set()
    rels, keep = sync_paths(wt)
    files, links, where = scan(wt, rels, StatCache(os.path.join(CACHE_HOME, 'stat', hashlib.sha256(wt.encode())
                                                                .hexdigest()[:16] + '.json')))
    msha = put_manifest(bk, dict(v=1, kind='sync', files=files, links=links, keep=keep), known)
    rc, out = box_run(['check', msha, dest])
    print(out.rstrip())
    return rc


def cmd_pull(name, local):
    """a tree the box published under a name (publish --name: the gate's report, published in the gate's own ssh)."""
    ck = Clock()
    bk = Bucket(os.environ['BUCKET'])
    ref = bk.get('%s/n/%s' % (PREFIX, name))
    if ref is None:
        log('bucketsync pull: nothing published as %s' % name)
        return 1
    nf, nbytes, got_f, got_b = pull(bk, ref.decode().strip(), local)
    print('bucketsync pull: %d files, %.2f MB; downloaded %d; %.1f s' % (nf, nbytes / 1e6, got_f, ck.total()))
    record('pull', name=name, files=nf, bytes=nbytes, got_files=got_f, seconds=ck.total())
    return 0


# ----------------------------------------------------------------------------------------------------------- on the box
def managed(rel, keep_files, keep_dirs):
    """whether the sync owns rel on the box (else it's left alone: build.sh's rsync --delete excludes): not under a
    SKIP directory, not under charkit/out except remote/*.json, not an ignored path the laptop has. (A copy's
    charkit/out/i3d, which the sync used to send, is left alone like the rest of charkit/out.)"""
    parts = rel.split('/')
    if any(c in SKIP for c in parts):
        return False
    if rel.startswith('charkit/out/') or rel == 'charkit/out':
        if len(parts) < 3:
            return True                               # charkit/out itself: a directory, kept
        if parts[2] == 'remote':
            return len(parts) == 3 or (len(parts) == 4 and parts[3].endswith('.json'))
        return False
    if rel in keep_files:
        return False
    return not any('/'.join(parts[:i]) in keep_dirs for i in range(1, len(parts) + 1))


def adopt(bk, sha, size, candidates, tmp):
    """a blob the bucket lacks, found in one of the box's copies (a file at the same path, same size and sha256): copied
    into tmp (never linked: the copy's file is rsync's, writable) and uploaded from here, inside GCP."""
    for c in candidates:
        try:
            if os.path.getsize(c) != size or os.path.islink(c):
                continue
            h = hashlib.sha256()
            with open(c, 'rb') as f, open(tmp, 'wb') as g:
                while True:
                    b = f.read(CHUNK)
                    if not b:
                        break
                    h.update(b)
                    g.write(b)
        except OSError:
            continue
        if h.hexdigest() == sha:
            bk.upload(blob(sha), path=tmp)
            print('BUCKETSYNC-ADOPTED %s' % sha)
            return True
    return False


def cache_blob(bk, sha, size, x, mt, missing, candidates=()):
    """the blob in the box's cache (read-only; <sha>.x with the exec bit, since links share the mode)."""
    d = os.path.join(BOXCAS, 'blobs', sha[:2])
    base = os.path.join(d, sha)
    p = base + ('.x' if x else '')
    try:
        if os.stat(p).st_mode & 0o222:                # an rsync -a into a linked copy chmods in place: read-only again
            os.chmod(p, 0o555 if x else 0o444)
        return p
    except FileNotFoundError:
        pass
    os.makedirs(d, exist_ok=True)
    tmp = '%s.%d.%d' % (base, os.getpid(), threading.get_ident())
    try:
        if os.path.exists(base):                      # the other mode's variant: a copy of it
            shutil.copyfile(base, tmp)
        else:
            try:
                bk.download(blob(sha), tmp, size=size, sha=sha)
            except FileNotFoundError:
                if not adopt(bk, sha, size, candidates, tmp):
                    missing.append(sha)
                    return None
        os.chmod(tmp, 0o555 if x else 0o444)
        os.utime(tmp, ns=(mt, mt))
        os.replace(tmp, p)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    return p


def place(src, dest, copy):
    """src (a cache blob) at dest: a hard link, or a copy for trees that aren't inputs; by rename, so an existing file
    at dest (maybe a link another copy shares) is replaced, never written through."""
    parent = os.path.dirname(dest)
    try:
        os.makedirs(parent, exist_ok=True)
    except (FileExistsError, NotADirectoryError):
        _clear_parents(parent)
        os.makedirs(parent, exist_ok=True)
    if os.path.isdir(dest) and not os.path.islink(dest):
        shutil.rmtree(dest)
    tmp = '%s.bs-%d' % (dest, os.getpid())
    if copy:
        shutil.copyfile(src, tmp)
        os.chmod(tmp, 0o755 if os.stat(src).st_mode & 0o100 else 0o644)
        st = os.stat(src)
        os.utime(tmp, ns=(st.st_mtime_ns, st.st_mtime_ns))
    else:
        os.link(src, tmp)
    os.replace(tmp, dest)
    if dest.endswith('.py'):                          # its bytecode was keyed on the old file's (mtime, size)
        pc = os.path.join(parent, '__pycache__')
        stem = os.path.basename(dest)[:-3] + '.'
        if os.path.isdir(pc):
            for f in os.listdir(pc):
                if f.startswith(stem) and f.endswith('.pyc'):
                    os.remove(os.path.join(pc, f))


def _clear_parents(path):
    """a file standing where a directory must go (the laptop turned a file into a directory)."""
    p = path
    while p and p != '/':
        if os.path.lexists(p) and not os.path.isdir(p):
            os.remove(p)
            return
        p = os.path.dirname(p)


def box_materialize(msha, dest, copy=False, delete=True):
    ck = Clock()
    bk = Bucket(os.environ['BUCKET'])
    if not dest.startswith(WORK + '/') or dest.rstrip('/') in (WORK, BOXCAS) or '/..' in dest:
        raise SystemExit('bucketsync: refusing to materialize into %s' % dest)
    m = get_manifest(bk, msha)
    if m.get('as_file'):                              # push of one file to a path (a directory's, if it is one)
        if os.path.isdir(dest):
            m['files'][0][0] = os.path.basename(m['files'][0][0])
        else:
            m['files'][0][0] = os.path.basename(dest)
            dest = os.path.dirname(dest)
    os.makedirs(dest, exist_ok=True)
    if copy:
        return box_copy(bk, m, dest, ck)
    want = {}                                          # sha -> (size, exec, mtime) of each variant needed
    for rel, sha, size, x, mt in m['files']:
        want.setdefault((sha, x), (size, mt))
    missing = []
    cands = candidates(m, dest) if m.get('kind') == 'sync' else lambda sha: ()
    with cf.ThreadPoolExecutor(THREADS) as ex:
        paths = dict(zip(want, ex.map(lambda k: cache_blob(bk, k[0], want[k][0], k[1], want[k][1], missing,
                                                           cands(k[0])), want)))
    ck.lap('blobs')
    if missing:
        for s in sorted(set(missing)):
            print('BUCKETSYNC-MISSING %s' % s)
        print('BUCKETSYNC materialize: %d blobs neither the bucket nor the box has (%.1f s)'
              % (len(set(missing)), ck.laps['blobs']))
        return 3
    placed = 0
    for rel, sha, size, x, mt in m['files']:
        p = os.path.join(dest, rel)
        src = paths[(sha, x)]
        try:
            st = os.lstat(p)
        except OSError:
            st = None
        if st and not copy and stat.S_ISREG(st.st_mode) and st.st_ino == os.stat(src).st_ino:
            continue
        if st and copy and stat.S_ISREG(st.st_mode) and st.st_size == size and st.st_mtime_ns == mt:
            continue
        place(src, p, copy)
        placed += 1
    for rel, target in m.get('links', ()):
        p = os.path.join(dest, rel)
        if os.path.islink(p) and os.readlink(p) == target:
            continue
        os.makedirs(os.path.dirname(p), exist_ok=True)
        tmp = p + '.bs-%d' % os.getpid()
        os.symlink(target, tmp)
        if os.path.isdir(p) and not os.path.islink(p):
            shutil.rmtree(p)
        os.replace(tmp, p)
        placed += 1
    ck.lap('place')
    removed = 0
    if delete and m.get('kind') == 'sync':
        removed = prune(dest, m)
    ck.lap('delete')
    gc_cache()
    print('BUCKETSYNC materialize: %d files, %d placed, %d removed, blobs %.1f s, place %.1f s, delete %.1f s'
          % (len(m['files']), placed, removed, ck.laps['blobs'], ck.laps['place'], ck.laps['delete']))
    return 0


def candidates(m, dest):
    """where the box's copies might hold a blob: the same paths in this copy (an rsync-era copy of this worktree),
    then in the other copies, most recently changed first -> sha -> [paths]."""
    rels = {}
    for rel, sha, size, x, mt in m['files']:
        rels.setdefault(sha, []).append(rel)
    copies = []
    for c in os.listdir(WORK):
        d = os.path.join(WORK, c)
        if d != dest.rstrip('/') and os.path.isdir(os.path.join(d, 'charkit')):
            copies.append((os.path.getmtime(d), d))
    copies = [dest.rstrip('/')] + [d for _, d in sorted(copies, reverse=True)][:40]
    return lambda sha: (os.path.join(d, r) for d in copies for r in rels.get(sha, ())[:3])


def box_copy(bk, m, dest, ck):
    """a push that isn't an input (a git bundle, a tarball: read once, then deleted): each file written at dest,
    copied from the blob cache when it's there, else downloaded straight into place (not kept in the cache)."""
    todo = {}
    for rel, sha, size, x, mt in m['files']:
        p = os.path.join(dest, rel)
        try:
            st = os.lstat(p)
            if stat.S_ISREG(st.st_mode) and st.st_size == size and st.st_mtime_ns == mt:
                continue
        except OSError:
            pass
        todo.setdefault(sha, []).append((p, size, x, mt))
    missing = []
    def one(item):
        sha, dests = item
        src = next((c for c in (os.path.join(BOXCAS, 'blobs', sha[:2], sha + v) for v in ('', '.x'))
                    if os.path.exists(c)), None)
        n = 0
        for p, size, x, mt in dests:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            tmp = '%s.bs-%d' % (p, os.getpid())
            try:
                if src:
                    shutil.copyfile(src, tmp)
                else:
                    bk.download(blob(sha), tmp, size=size, sha=sha)
                os.chmod(tmp, 0o755 if x else 0o644)
                os.utime(tmp, ns=(mt, mt))
                os.replace(tmp, p)
            except FileNotFoundError:
                missing.append(sha)
                return n
            finally:
                if os.path.exists(tmp):
                    os.remove(tmp)
            src = src or p                            # the rest of this blob's paths copy the first
            n += 1
        return n
    with cf.ThreadPoolExecutor(max(1, min(THREADS, len(todo)))) as ex:
        placed = sum(ex.map(one, todo.items()))
    ck.lap('copy')
    if missing:
        for s in sorted(set(missing)):
            print('BUCKETSYNC-MISSING %s' % s)
        return 3
    print('BUCKETSYNC materialize: %d files, %d copied, %.1f s' % (len(m['files']), placed, ck.laps['copy']))
    return 0


def prune(dest, m):
    """delete what the manifest no longer names, where the sync owns the path (rsync --delete with its excludes);
    directories left empty go too."""
    have = {f[0] for f in m['files']} | {l[0] for l in m.get('links', ())}
    dirs_needed = set()
    for rel in have:
        parts = rel.split('/')
        for i in range(1, len(parts)):
            dirs_needed.add('/'.join(parts[:i]))
    keep = m.get('keep', ())
    keep_files = {k for k in keep if not k.endswith('/')}
    keep_dirs = {k.rstrip('/') for k in keep if k.endswith('/')}
    removed, empty = 0, []
    for d, ds, fs in os.walk(dest, topdown=True):
        rd = os.path.relpath(d, dest)
        rd = '' if rd == '.' else rd + '/'
        if rd and rd[:-1] not in dirs_needed:
            empty.append(d)
        kept = []
        for x in ds:
            rel = rd + x
            full = os.path.join(d, x)
            if os.path.islink(full):
                fs.append(x)
            elif managed(rel, keep_files, keep_dirs):
                kept.append(x)
        ds[:] = kept
        for f in fs:
            rel = rd + f
            if rel in have or not managed(rel, keep_files, keep_dirs):
                continue
            os.remove(os.path.join(d, f))
            removed += 1
    for d in sorted(empty, key=len, reverse=True):     # deepest first; one holding what the sync leaves alone stays
        try:
            os.rmdir(d)
        except OSError:
            pass
    return removed


def gc_cache(days=3):
    """cache blobs no copy links to any more (link count 1), untouched for days, are dropped."""
    root = os.path.join(BOXCAS, 'blobs')
    cut = time.time() - days * 86400
    for d, ds, fs in os.walk(root):
        for f in fs:
            p = os.path.join(d, f)
            try:
                st = os.lstat(p)
                if st.st_nlink == 1 and st.st_ctime < cut:
                    os.remove(p)
            except OSError:
                pass


def box_check(msha, dest):
    """a copy against a manifest, file by file: missing, wrong content (sha256), wrong exec bit, symlinks, and managed
    files the manifest doesn't name (what a sync should have deleted). Prints counts and the first few of each."""
    bk = Bucket(os.environ['BUCKET'])
    m = get_manifest(bk, msha)
    bad = {'missing': [], 'content': [], 'mode': [], 'link': [], 'extra': []}
    have = set()
    for rel, sha, size, x, mt in m['files']:
        have.add(rel)
        p = os.path.join(dest, rel)
        if not os.path.isfile(p) or os.path.islink(p):
            bad['missing'].append(rel)
        elif os.path.getsize(p) != size or file_sha(p) != sha:
            bad['content'].append(rel)
        elif bool(os.stat(p).st_mode & 0o100) != bool(x):
            bad['mode'].append(rel)
    for rel, target in m.get('links', ()):
        have.add(rel)
        p = os.path.join(dest, rel)
        if not os.path.islink(p) or os.readlink(p) != target:
            bad['link'].append(rel)
    if m.get('kind') == 'sync':
        keep = m.get('keep', ())
        kf = {k for k in keep if not k.endswith('/')}
        kd = {k.rstrip('/') for k in keep if k.endswith('/')}
        for d, ds, fs in os.walk(dest):
            rd = os.path.relpath(d, dest)
            rd = '' if rd == '.' else rd + '/'
            ds[:] = [x for x in ds if managed(rd + x, kf, kd)]
            bad['extra'] += [rd + f for f in fs if rd + f not in have and managed(rd + f, kf, kd)]
    print('BUCKETSYNC check: %d files, %d links; %s' % (len(m['files']), len(m.get('links', ())),
                                                        ', '.join('%s %d' % (k, len(v)) for k, v in bad.items())))
    for k, v in bad.items():
        for rel in v[:5]:
            print('  %s %s' % (k, rel))
    return 1 if any(bad.values()) else 0


def box_publish(path, name=None):
    """path's files (a build's outputs, a gate's report) into the bucket: hashed here, the blobs the bucket lacks
    uploaded, the manifest printed (and stored under name if given). Outputs are read, never linked into the cache."""
    ck = Clock()
    bk = Bucket(os.environ['BUCKET'])
    known = Known(os.path.join(BOXCAS, 'known'))
    path = os.path.abspath(path)
    if not os.path.isdir(path):
        print('bucketsync publish: no directory %s' % path)
        return 2
    rels = walk_paths(path)
    files, links, where = scan(path, rels)
    ck.lap('hash')
    n, nb = upload_blobs(bk, {f[1] for f in files}, known, where)
    msha = put_manifest(bk, dict(v=1, kind='publish', files=files, links=links), known, name=name)
    ck.lap('upload')
    print('BUCKETSYNC-MANIFEST %s %d files %d bytes; uploaded %d blobs %d bytes; hash %.1f s upload %.1f s'
          % (msha, len(files), sum(f[2] for f in files), n, nb, ck.laps['hash'], ck.laps['upload']))
    return 0


# ------------------------------------------------------------------------------------------------------------------ cli
def main(argv):
    if not argv or argv[0] in ('-h', '--help'):
        print(__doc__)
        return 0
    cmd, a = argv[0], argv[1:]
    flags = {x for x in a if x.startswith('--')}
    pos = [x for x in a if not x.startswith('--')]
    if cmd == 'materialize':
        return box_materialize(pos[0], pos[1], copy='--copy' in flags, delete='--no-delete' not in flags)
    if cmd == 'check':
        return box_check(pos[0], pos[1])
    if cmd == 'publish':
        name = a[a.index('--name') + 1] if '--name' in a else None
        pos = [x for x in pos if x != name]
        return box_publish(pos[0], name)
    if not os.environ.get('BUCKET'):
        raise SystemExit('bucketsync: no BUCKET (infra/gcp/*.env): run through infra/gcp/build.sh')
    if cmd == 'sync':
        return cmd_sync(pos[0], pos[1])
    if cmd == 'fetch':
        return cmd_fetch(pos[0], pos[1])
    if cmd == 'push':
        return cmd_push(pos[0], pos[1], link='--link' in flags)
    if cmd == 'pull':
        return cmd_pull(pos[0], pos[1])
    if cmd == 'verify':
        return cmd_verify(pos[0], pos[1])
    print(__doc__)
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
