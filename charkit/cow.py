"""Copy on write for a box copy's linked inputs (standard library only).

A box's copy of a worktree (/srv/work/<worktree>) hard-links every synced file read-only from the box's blob cache
(charkit/bucketsync.py), so a write through a link fails instead of reaching every copy that shares the blob. Any
charkit command that rewrites a tracked file in place there (open(path, 'w'), json.dump into it, np.save, shutil.copyfile
onto it) therefore died with PermissionError: 22 box calibrate jobs on 2026-10-01 (charkit/calib/records/*.json, then
known_bad/*.json once the records' writer was fixed alone, 8580945f). Fixing writers one at a time leaves the next
one; this fixes the class.

In a box copy, opening a file for writing first gives that path a private, writable file when the path is a read-only
hard link under the copy: a write that truncates removes the link (the open then creates a new file), any other write
(append, r+, a write without truncation) copies it and renames the copy over the link (cache.unshare's pattern). The
shared blob, and every other copy linked to it, are untouched; the write lands in this copy only, as it would in a
worktree. Only an open that would have failed with PermissionError (a read-only file with other links) is changed.

Installed by charkit/__init__.py through a Python audit hook (the 'open' event comes before the open, for builtins.open,
io.open and os.open alike; charkit/closure.py records a gate's reads the same way), and only where the package itself
is such a link (charkit/__init__.py read-only with other links: a box copy, never a worktree or a gate's git clone).
CHARKIT_COW=0 turns it off, CHARKIT_COW=1 forces it on. Not covered: writes from other programs (a shell redirect,
Blender's C code) and os.rename/os.replace onto a link (those replace the link already, and never write through it).
"""
import os, shutil, stat, sys, threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV = 'CHARKIT_COW'
_WRITE = os.O_WRONLY | os.O_RDWR
_STATE = {}
_TLS = threading.local()


def shared_readonly(path):
    """is path a regular file that is read-only for its owner and hard-linked elsewhere (a box copy's synced input)?"""
    try:
        st = os.stat(path)
    except (OSError, ValueError, TypeError):
        return False
    return stat.S_ISREG(st.st_mode) and st.st_nlink > 1 and not st.st_mode & stat.S_IWUSR


def unshare(path, truncate=False):
    """give path (a read-only hard link) a private, owner-writable file of its own: removed when the write truncates
    (the open creates it anew), else copied and renamed over the link (an append or r+ sees the same content). The
    link's other names keep the shared file. -> True when something was done."""
    st = os.stat(path)
    if truncate and not st.st_mode & 0o111:
        os.unlink(path)
        return True
    tmp = '%s.cow-%d-%d' % (path, os.getpid(), threading.get_ident())
    try:
        shutil.copyfile(path, tmp)
        os.chmod(tmp, (stat.S_IMODE(st.st_mode) | stat.S_IWUSR))
        os.utime(tmp, ns=(st.st_atime_ns, st.st_mtime_ns))
        os.replace(tmp, path)
    finally:
        if os.path.lexists(tmp):
            os.remove(tmp)
    return True


def box_copy(root=ROOT):
    """is root a box copy (its charkit/__init__.py a read-only hard link from the blob cache)?"""
    return shared_readonly(os.path.join(root, 'charkit', '__init__.py'))


def install(root=ROOT, force=False):
    """the hook in this process (once) for writes under root -> True when installed now. Off with CHARKIT_COW=0; on
    only in a box copy (box_copy) unless CHARKIT_COW=1 or force."""
    v = os.environ.get(ENV, '')
    if _STATE.get('root') or v == '0' or not (force or v == '1' or box_copy(root)):
        return False
    pre = os.path.realpath(root) + os.sep
    _STATE.update(root=pre, done=0)

    def hook(event, args):
        if event != 'open' or getattr(_TLS, 'busy', False):
            return
        try:
            path, flags = args[0], args[2] if len(args) > 2 else None
            if isinstance(path, int) or not isinstance(flags, int) or not flags & _WRITE:
                return
            p = os.path.realpath(os.fsdecode(path))
            if not p.startswith(pre) or not shared_readonly(p):
                return
            _TLS.busy = True
            try:
                unshare(p, truncate=bool(flags & os.O_TRUNC and flags & os.O_CREAT))
                _STATE['done'] += 1
            finally:
                _TLS.busy = False
        except Exception:                       # never fails the open itself: it then fails (or not) as it would have
            pass
    sys.addaudithook(hook)
    return True


def unshared():
    """how many writes this process gave a file of its own (0 when the hook isn't installed)."""
    return _STATE.get('done', 0)
