import sys
sys.path.insert(0,__import__('os').path.dirname(__file__))
from render import *
from PIL import ImageDraw
name,face,out=sys.argv[1:4]
g,_=load(name); ids=[d['id'] for d in g['drawables']]; base=g['configs']['base']['pos']
fv=np.array(base[ids.index(face)]).reshape(-1,2); fx0,fy0=fv.min(0); fx1,fy1=fv.max(0); W=fx1-fx0; H=fy1-fy0; cx=(fx0+fx1)/2
box=(cx-2.0*W, fy0-3.0*H, cx+2.0*W, fy0+1.3*H); px=900
im=render(name,box=box,px=px); d=ImageDraw.Draw(im); s=px/(box[2]-box[0])
for v in np.arange(-3,1.31,0.25):
    Y=(box[3]-(fy0+v*H))*s; d.line((0,Y,px,Y),fill=(255,0,0) if v==int(v) else (255,160,160),width=1); d.text((2,Y-11),f"{v:+.2f}",fill=(200,0,0))
for u in np.arange(-2,2.01,0.25):
    X=(cx+u*W-box[0])*s; d.line((X,0,X,im.height),fill=(0,0,255) if u==int(u) else (160,160,255),width=1); d.text((X+2,2),f"{u:+.2f}",fill=(0,0,200))
im.save(out); print(out)
