import numpy as np
from regions import R
from render import load, visible
def frame(name):
    g,_=load(name); ids=[d['id'] for d in g['drawables']]; base=g['configs']['base']['pos']
    fv=np.array(base[ids.index(R[name]['face'])]).reshape(-1,2); x0,y0=fv.min(0); x1,y1=fv.max(0)
    return dict(W=x1-x0,H=y1-y0,cx=(x0+x1)/2,chin=y0)
def select(name):
    """returns {region: list of (drawable_index, vertex_index_array)}"""
    g,_=load(name); F=frame(name); base=g['configs']['base']['pos']; out={}
    for reg,clauses in R[name]['regions'].items():
        sel=[]
        for c in clauses:
            for d,dr in enumerate(g['drawables']):
                if not visible(dr): continue
                ok=('ids' in c and dr['id'] in c['ids']) or ('parts' in c and dr['part'] in c['parts']) or ('pre' in c and any(dr['part'].startswith(p) for p in c['pre']))
                if not ok: continue
                v=np.array(base[d]).reshape(-1,2); u=(v[:,0]-F['cx'])/F['W']; w=(v[:,1]-F['chin'])/F['H']
                m=np.ones(len(v),bool)
                if 'box' in c: b=c['box']; m&=(u>=b[0])&(u<=b[1])&(w>=b[2])&(w<=b[3])
                if 'absu' in c: a=c['absu']; m&=(np.abs(u)>=a[0])&(np.abs(u)<=a[1])
                if m.any(): sel.append((d,np.where(m)[0]))
        out[reg]=sel
    return out
