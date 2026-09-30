#!/usr/bin/env bash
# The GPU box as a render box (root, idempotent; run by gpu-startup.sh on boot, or by hand): Blender headless at the
# laptop's version with its GL/EGL client libraries (EEVEE renders on the L4 through the NVIDIA driver's EGL, no display),
# a Python venv with charkit's packages (/opt/anim-build/venv, as the build box has), a shared work dir (/srv/work: one
# directory per synced worktree), and /opt/anim-build/env for a build: BLENDER and the venv, boards rendered.
set -uo pipefail
BV=${BLENDER_VERSION:-5.2.2}
PV=${PYTHON_VERSION:-3.14}
mkdir -p /opt/anim-build /srv/work && chmod 1777 /srv/work
if [ ! -f /opt/anim-build/.render-base ]; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -y
  apt-get install -y git rsync xz-utils curl libgl1 libegl1 libglib2.0-0 libxi6 libxkbcommon0 libxrender1 libsm6 \
    libxxf86vm1 libxfixes3 libxext6 libx11-6 libxcursor1 libxinerama1 libxrandr2 libvulkan1
  command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh
  touch /opt/anim-build/.render-base
fi
if [ ! -x /opt/blender/blender ] || ! /opt/blender/blender --version 2>/dev/null | grep -q "Blender $BV"; then
  MM=$(echo "$BV" | cut -d. -f1,2)
  curl -fL "https://download.blender.org/release/Blender$MM/blender-$BV-linux-x64.tar.xz" -o /tmp/blender.tar.xz \
    && rm -rf /opt/blender && mkdir -p /opt/blender \
    && tar -xJf /tmp/blender.tar.xz -C /opt/blender --strip-components=1 && rm -f /tmp/blender.tar.xz
fi
export UV_PYTHON_INSTALL_DIR=/opt/anim-build/python
if [ ! -x /opt/anim-build/venv/bin/python ] || ! readlink -f /opt/anim-build/venv/bin/python | grep -q '^/opt/'; then
  rm -rf /opt/anim-build/venv
  uv venv --python "$PV" /opt/anim-build/venv
  VIRTUAL_ENV=/opt/anim-build/venv uv pip install numpy scipy scikit-image numba pillow manifold3d matplotlib \
    opencv-python-headless pytest
fi
# charkit.render (the toon renderer, docs/workstreams/toonrender.md): wgpu, on the T4 through Vulkan (lavapipe on the CPU); also into an existing venv
VIRTUAL_ENV=/opt/anim-build/venv uv pip install -q 'wgpu>=0.32' || echo "wgpu install failed"
# boards render here (no CHARKIT_NO_RENDER): EEVEE on the GPU through EGL
printf '%s\n' 'export BLENDER=/opt/blender/blender' 'export VIRTUAL_ENV=/opt/anim-build/venv' \
  'export PATH=/opt/anim-build/venv/bin:$PATH' > /opt/anim-build/env
chmod 644 /opt/anim-build/env
/opt/blender/blender --version | head -1 || echo "Blender missing"
/opt/anim-build/venv/bin/python -c "import numpy, scipy, numba, skimage; print('venv ok')" || echo "venv broken"
touch /opt/anim-build/READY
