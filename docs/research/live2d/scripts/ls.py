import sys,json,numpy as np
sys.path.insert(0,__import__('os').path.dirname(__file__))
from render import load, visible
name=sys.argv[1]; face=sys.argv[2]; filt=sys.argv[3] if len(sys.argv)>3 else ''
g,_=load(name); ids=[d['id'] for d in g['drawables']]; base=g['configs']['base']['pos']
fv=np.array(base[ids.index(face)]).reshape(-1,2); fx0,fy0=fv.min(0); fx1,fy1=fv.max(0); W=fx1-fx0; H=fy1-fy0; cx=(fx0+fx1)/2
print(f'{name} face {face} W={W:.4f} H={H:.4f} chin_y={fy0:.4f} cx={cx:.4f}')
for d,dr in enumerate(g['drawables']):
    if not visible(dr) or (filt and not any(f in dr['part'] for f in filt.split(','))): continue
    v=np.array(base[d]).reshape(-1,2); u=(v[:,0]-cx)/W; w=(v[:,1]-fy0)/H
    print(f"{d:4d} {dr['id']:12s} {dr['part'][:22]:22s} nv={len(v):4d} u[{u.min():6.2f},{u.max():6.2f}] v[{w.min():6.2f},{w.max():6.2f}] ord={dr['order']}")
