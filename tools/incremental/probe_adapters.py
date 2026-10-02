"""which wgpu adapters this machine has, and a tiny draw timed on each (incremental round 1, task 2)."""
import json, os, subprocess, sys, time
sys.path.insert(0, os.getcwd())
from charkit.render import gpu
print(json.dumps(gpu.adapters(), indent=1))
for pref in ('gpu', 'cpu', 'auto'):
    try:
        t = time.time(); d, info = gpu.device(pref); print(pref, '->', info, '%.2f s' % (time.time() - t))
    except Exception as e:
        print(pref, 'FAILED', type(e).__name__, e)
try:
    print(subprocess.run(['nvidia-smi', '--query-gpu=name,memory.used,memory.total,utilization.gpu', '--format=csv'],
                         capture_output=True, text=True).stdout)
except Exception as e:
    print('nvidia-smi', e)
print('nproc', os.cpu_count(), 'load', os.getloadavg())
for p in ('/usr/share/vulkan/icd.d', '/etc/vulkan/icd.d'):
    print(p, os.listdir(p) if os.path.isdir(p) else None)
