"""Pose tracking for motion reference (a dancer on a plain set, e.g. a Seedance clip made with the user's sign-off): MediaPipe's
pose landmarker, every frame, in video mode (temporally smoothed). Writes <out>.json: fps, size, and per frame the 33 landmarks
in image coords (x, y normalised; z relative depth; visibility) and in world coords (metres, hip-centred), plus <out>_overlay.mp4
with the skeleton drawn, to check the tracking by eye.
    .venv-pose/bin/python tools/posetrack.py IN.mp4 OUT_BASE
"""
import json, os, sys, subprocess
import cv2, numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mpt
from mediapipe.tasks.python import vision

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EDGES = [(11, 12), (11, 13), (13, 15), (12, 14), (14, 16), (11, 23), (12, 24), (23, 24), (23, 25), (25, 27), (24, 26), (26, 28),
         (27, 31), (28, 32), (27, 29), (28, 30), (15, 19), (16, 20), (0, 7), (0, 8)]


def main(src, base):
    opts = vision.PoseLandmarkerOptions(base_options=mpt.BaseOptions(model_asset_path=os.path.join(ROOT, 'tools/models/pose_landmarker_heavy.task'), delegate=mpt.BaseOptions.Delegate.CPU),
                                        running_mode=vision.RunningMode.VIDEO, num_poses=1, min_pose_detection_confidence=.5, min_tracking_confidence=.5)
    det = vision.PoseLandmarker.create_from_options(opts)
    cap = cv2.VideoCapture(src); fps = cap.get(cv2.CAP_PROP_FPS) or 24; W = int(cap.get(3)); H = int(cap.get(4))
    frames, k = [], 0
    tmp = base + '_overlay_raw.mp4'; vw = cv2.VideoWriter(tmp, cv2.VideoWriter_fourcc(*'mp4v'), fps, (W, H))
    while True:
        ok, img = cap.read()
        if not ok: break
        res = det.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(img, cv2.COLOR_BGR2RGB)), int(k * 1000 / fps))
        if res.pose_landmarks:
            L, Wd = res.pose_landmarks[0], res.pose_world_landmarks[0]
            frames.append({'i': k, 'img': [[round(p.x, 5), round(p.y, 5), round(p.z, 5), round(p.visibility, 3)] for p in L],
                           'world': [[round(p.x, 5), round(p.y, 5), round(p.z, 5)] for p in Wd]})
            for a, b in EDGES:
                pa, pb = L[a], L[b]; cv2.line(img, (int(pa.x * W), int(pa.y * H)), (int(pb.x * W), int(pb.y * H)), (60, 220, 255), 3)
            for p in L: cv2.circle(img, (int(p.x * W), int(p.y * H)), 4, (255, 90, 170), -1)
        else: frames.append({'i': k, 'img': None, 'world': None})
        cv2.putText(img, f'{k}', (12, 32), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 3); vw.write(img); k += 1
    vw.release()
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', tmp, '-c:v', 'libx264', '-pix_fmt', 'yuv420p', base + '_overlay.mp4'], check=True); os.remove(tmp)
    json.dump({'fps': fps, 'size': [W, H], 'frames': frames}, open(base + '.json', 'w'))
    print(f'{k} frames, tracked {sum(1 for f in frames if f["img"])}, fps {fps:.2f}, {W}x{H}')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
