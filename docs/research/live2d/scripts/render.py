import json, sys, os, numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont
H=os.path.dirname(os.path.abspath(__file__)); R=H+'/../cws/Samples/Resources/'
_cache={}
def load(name):
    if name in _cache: return _cache[name]
    g=json.load(open(f'{H}/{name}.geo.json'))
    mj=json.load(open(f'{R}{name}/{name}.model3.json'))
    texs=[cv2.imread(R+name+'/'+t, cv2.IMREAD_UNCHANGED) for t in mj['FileReferences']['Textures']]
    texs=[cv2.cvtColor(t,cv2.COLOR_BGRA2RGBA).astype(np.float32)/255 for t in texs]
    _cache[name]=(g,texs); return g,texs
SKIP=('光','煙','爆発光','ハート','オーラ','インク','うさぎ','エフェクト','乗算色','波動','魔法陣','炎','クレジット','HitArea','コア','CORE','コアパーツ')
ALT=('腕 B','右腕 B','左腕 B','左腕B','右腕B','左腕C','左腕D','右腕E','懐中時計_B')
def visible(dr):
    top=dr['part'].split('>')[0]
    return dr['opacity']>0.01 and not any(s in dr['part'] for s in SKIP) and top not in ALT
def render(name, cfg='base', box=None, px=900, only=None, tint=None, fade=None, draw_ids=None):
    """box=(x0,y0,x1,y1) model units, y up. only: set of drawable idx to draw; fade: set drawn at 25%"""
    g,texs=load(name); pos=g['configs'][cfg]['pos']
    x0,y0,x1,y1=box; s=px/(x1-x0); W=px; Hh=int((y1-y0)*s)
    img=np.ones((Hh,W,3),np.float32)*0.93
    order=sorted(range(len(g['drawables'])), key=lambda d:g['drawables'][d]['order'])
    for d in order:
        dr=g['drawables'][d]
        if not visible(dr): continue
        if only is not None and d not in only and (fade is None or d not in fade): continue
        a_mul=0.25 if (fade is not None and d in fade and (only is None or d not in only)) else 1.0
        tex=texs[dr['tex']]; th,tw=tex.shape[:2]
        v=np.array(pos[d]).reshape(-1,2); uv=np.array(dr['uv']).reshape(-1,2)
        sp=np.stack([(v[:,0]-x0)*s,(y1-v[:,1])*s],1); tp=np.stack([uv[:,0]*tw,(1-uv[:,1])*th],1)
        idx=np.array(dr['idx']).reshape(-1,3)
        for t in idx:
            dst=sp[t].astype(np.float32); src=tp[t].astype(np.float32)
            bx0,by0=np.floor(dst.min(0)).astype(int); bx1,by1=np.ceil(dst.max(0)).astype(int)+1
            bx0=max(bx0,0);by0=max(by0,0);bx1=min(bx1,W);by1=min(by1,Hh)
            if bx1<=bx0 or by1<=by0: continue
            M=cv2.getAffineTransform(src,dst-np.array([bx0,by0],np.float32))
            patch=cv2.warpAffine(tex,M,(bx1-bx0,by1-by0),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT,borderValue=(0,0,0,0))
            mask=np.zeros((by1-by0,bx1-bx0),np.float32)
            cv2.fillConvexPoly(mask,np.round((dst-np.array([bx0,by0]))*4).astype(np.int32),1.0,lineType=cv2.LINE_AA,shift=2)
            a=patch[...,3]*mask*a_mul
            col=patch[...,:3]
            if tint is not None and d in tint: col=col*0.5+np.array(tint[d])*0.5
            reg=img[by0:by1,bx0:bx1]; img[by0:by1,bx0:bx1]=reg*(1-a[...,None])+col*a[...,None]
    im=Image.fromarray((np.clip(img,0,1)*255).astype(np.uint8))
    if draw_ids:
        dd=ImageDraw.Draw(im)
        for d,lab in draw_ids.items():
            v=np.array(pos[d]).reshape(-1,2); c=v.mean(0)
            X=(c[0]-x0)*s; Y=(y1-c[1])*s; dd.text((X,Y),lab,fill=(255,0,0))
    return im
