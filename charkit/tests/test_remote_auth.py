"""The box calls' gcloud config (docs/workstreams/infra-auth.md): the env file's `export CLOUDSDK_CONFIG=...` reaches
remote.py's own gcloud calls, and the pre-flight turns a dead credential into one line on what to run."""
import os, stat, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import remote, bucketsync  # noqa: E402


def _envfile(d, extra):
    p = os.path.join(d, 'build.env')
    open(p, 'w').write('PROJECT=p\nZONE=z\nVM=box-1\nBUCKET=gs://b   # the bucket\n' + extra)
    return p


def _fake_gcloud(d, script):
    b = os.path.join(d, 'bin')
    os.makedirs(b, exist_ok=True)
    g = os.path.join(b, 'gcloud')
    open(g, 'w').write('#!/bin/sh\n' + script)
    os.chmod(g, os.stat(g).st_mode | stat.S_IEXEC)
    return b


def test_env_export_and_home():
    with tempfile.TemporaryDirectory() as d:
        old, oenv = remote.BOX['env'], dict(os.environ)
        try:
            remote.BOX['env'] = _envfile(d, 'export CLOUDSDK_CONFIG=$HOME/.config/x/gcloud\n')
            os.environ.pop('CLOUDSDK_CONFIG', None)
            assert remote._env('BUCKET') == 'gs://b'
            want = os.path.expanduser('~/.config/x/gcloud')
            assert remote._env('CLOUDSDK_CONFIG') == want
            assert remote._gcloud() == want and os.environ['CLOUDSDK_CONFIG'] == want
            # bucketsync on its own finds it the same way (CHARKIT_BOX_ENV names the env file)
            os.environ.pop('CLOUDSDK_CONFIG')
            os.environ['CHARKIT_BOX_ENV'] = remote.BOX['env']
            assert bucketsync.gcloud_config() == want
        finally:
            remote.BOX['env'] = old
            os.environ.clear(); os.environ.update(oenv)


def test_preflight_one_line():
    with tempfile.TemporaryDirectory() as d:
        old, oenv = remote.BOX['env'], dict(os.environ)
        try:
            remote.BOX['env'] = _envfile(d, 'export CLOUDSDK_CONFIG=%s/sa\n' % d)
            os.environ.pop('CHARKIT_NO_PREFLIGHT', None)
            os.environ['PATH'] = _fake_gcloud(d, 'echo "ERROR: (gcloud.auth.print-access-token) Reauthentication '
                                                 'failed. cannot prompt during non-interactive execution." >&2\n'
                                                 'exit 1\n') + os.pathsep + os.environ['PATH']
            remote.CHECKED.clear()
            try:
                remote.preflight()
                assert False, 'the pre-flight passed a dead credential'
            except SystemExit as e:
                msg = str(e)
            assert '\n' not in msg and 'Reauthentication failed' in msg and '%s/sa' % d in msg, msg
            # a working one passes, once per config
            os.environ['PATH'] = _fake_gcloud(d, 'echo tok\n') + os.pathsep + oenv['PATH']
            remote.preflight()
            assert '%s/sa' % d in remote.CHECKED
        finally:
            remote.BOX['env'] = old
            remote.CHECKED.clear()
            os.environ.clear(); os.environ.update(oenv)


def test_jobs_lists_every_box_once():
    """`remote jobs` with no --box asks every infra/gcp/*.env with a VM (render2 too), build and render first, and a VM
    twice (gpu.env is the render box's) once."""
    with tempfile.TemporaryDirectory() as d:
        g = os.path.join(d, 'infra', 'gcp')
        os.makedirs(g)
        for name, vm in (('build', 'b-1'), ('gpu', 'g-1'), ('render', 'g-1'), ('render2', 'g-2')):
            open(os.path.join(g, name + '.env'), 'w').write('VM=%s\nBUCKET=gs://x\n' % vm)
        open(os.path.join(g, 'build.env.example'), 'w').write('VM=example\n')
        old_root, old_env = remote.ROOT, remote.BOX['env']
        try:
            remote.ROOT = d
            assert [os.path.basename(p) for p in remote._boxes()] == ['build.env', 'render.env', 'render2.env']
        finally:
            remote.ROOT, remote.BOX['env'] = old_root, old_env
