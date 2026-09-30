"""Switch a stopped VM's machine type and attached GPU in one instance update (gpu-start.sh). They must change
together: a G2 must keep its L4, and an L4 can't go on an N1, so a machine type change and a GPU change made
separately are each refused. The disks' interface changes with them: G2 takes only NVMe, N1 only SCSI (the guest
mounts by UUID, so it boots either way).

    python3 reshape.py PROJECT ZONE VM MACHINE_TYPE [GPU]      (no GPU: none attached)
"""
import glob, json, os, subprocess, sys, urllib.error, urllib.request

project, zone, vm, mt = sys.argv[1:5]
gpu = sys.argv[5] if len(sys.argv) > 5 else ''
# the gcloud config: CLOUDSDK_CONFIG (gpu-start.sh's env file exports it), else the one set by this VM's env file
# beside this script (the box-control service account's: docs/workstreams/infra-auth.md), else the default login
if not os.environ.get('CLOUDSDK_CONFIG'):
    for env in sorted(glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), '*.env'))):
        kv = {}
        for line in open(env):
            line = line[len('export '):] if line.startswith('export ') else line
            if '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                kv[k.strip()] = os.path.expanduser(os.path.expandvars(v.split('#')[0].strip()))
        if kv.get('VM') == vm and kv.get('CLOUDSDK_CONFIG'):
            os.environ['CLOUDSDK_CONFIG'] = kv['CLOUDSDK_CONFIG']
            break
r = subprocess.run(['gcloud', 'auth', 'print-access-token'], capture_output=True, text=True, stdin=subprocess.DEVNULL)
if r.returncode or not r.stdout.strip():
    sys.exit('reshape: gcloud (config %s) has no token: %s' % (os.environ.get('CLOUDSDK_CONFIG', 'default'),
                                                               (r.stderr.strip().splitlines() or ['?'])[-1]))
tok = r.stdout.strip()
base = 'https://compute.googleapis.com/compute/v1/projects/%s/zones/%s' % (project, zone)


def call(method, url, body=None):
    req = urllib.request.Request(url, method=method, data=None if body is None else json.dumps(body).encode(),
                                 headers={'Authorization': 'Bearer ' + tok, 'Content-Type': 'application/json'})
    try:
        return json.load(urllib.request.urlopen(req, timeout=300))
    except urllib.error.HTTPError as e:
        sys.exit('%s %s: %s %s' % (method, url.rsplit('/', 1)[-1], e.code, e.read().decode()[:400]))


inst = call('GET', '%s/instances/%s' % (base, vm))
if inst['status'] != 'TERMINATED':
    sys.exit('%s is %s: reshape only a stopped VM' % (vm, inst['status']))
inst['machineType'] = 'zones/%s/machineTypes/%s' % (zone, mt)
inst['guestAccelerators'] = ([{'acceleratorType': 'zones/%s/acceleratorTypes/%s' % (zone, gpu), 'acceleratorCount': 1}]
                             if gpu else [])
iface = 'SCSI' if mt.startswith('n1-') else 'NVME'
for d in inst.get('disks', []):
    d['interface'] = iface
op = call('PUT', '%s/instances/%s' % (base, vm), inst)
while op.get('status') != 'DONE':
    op = call('POST', '%s/operations/%s/wait' % (base, op['name']))
if op.get('error'):
    sys.exit('; '.join(e['message'] for e in op['error']['errors']))
