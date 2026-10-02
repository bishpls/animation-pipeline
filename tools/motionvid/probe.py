"""what the render box offers the video: ffmpeg and its H.264 encoders, fonts, Pillow, the GPU, the load."""
import os, shutil, subprocess, sys
print('python', sys.version.split()[0])
import PIL
print('Pillow', PIL.__version__)
ff = shutil.which('ffmpeg')
print('ffmpeg', ff)
if ff:
    out = subprocess.run([ff, '-hide_banner', '-encoders'], capture_output=True, text=True).stdout
    print('\n'.join(l for l in out.splitlines() if '264' in l))
try:
    import imageio_ffmpeg
    print('imageio_ffmpeg', imageio_ffmpeg.get_ffmpeg_exe())
except Exception as e:
    print('imageio_ffmpeg: no', e)
try:
    import av
    print('av', av.__version__, [c for c in av.codecs_available if '264' in c])
except Exception as e:
    print('av: no', e)
for d in ('/usr/share/fonts/truetype', '/usr/share/fonts'):
    if os.path.isdir(d):
        print(d, os.listdir(d)[:20])
from PIL import ImageFont
try:
    f = ImageFont.load_default(size=24)
    print('load_default(size)', type(f).__name__)
except Exception as e:
    print('load_default(size): no', e)
print(subprocess.run(['nvidia-smi', '--query-gpu=name,memory.used,utilization.gpu', '--format=csv'],
                     capture_output=True, text=True).stdout)
print(open('/proc/loadavg').read(), os.cpu_count())
print(os.getcwd(), os.listdir('charkit/out')[:40])
