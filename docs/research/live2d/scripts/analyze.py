import sys, json, numpy as np
sys.path.insert(0,__import__('os').path.dirname(__file__))
from render import load; from sel import select, frame; from regions import R, HEAD, BODY
MODELS=['Hiyori','Haru','Mao','Natori']
SINGLE=['AX+30','AX-30','AY+30','AY-30','AZ+30','AZ-30','BX+10','BX-10','BY+10','BY-10','BZ+10','BZ-10','Br=1']
PAIRS=[('AX+30&AZ+30','AX+30','AZ+30'),('AX+30&AY+30','AX+30','AY+30'),('AZ+30&BZ+10','AZ+30','BZ+10'),('AX+30&BX+10','AX+30','BX+10'),
       ('AX-30&AZ+30','AX-30','AZ+30'),('AY+30&AZ+30','AY+30','AZ+30'),('AX+30&BZ+10','AX+30','BZ+10'),('BX+10&BZ+10','BX+10','BZ+10'),('AZ+30&BX+10','AZ+30','BX+10')]
def rigid(A,B):
    """best rigid fit B ~ R A + t (model units). returns angle deg (CCW+, y up), pivot (fixed point) or None, rms residual"""
    ca=A.mean(0); cb=B.mean(0); a=A-ca; b=B-cb
    th=np.arctan2((a[:,0]*b[:,1]-a[:,1]*b[:,0]).sum(), (a*b).sum())
    c,s=np.cos(th),np.sin(th); Rm=np.array([[c,-s],[s,c]]); t=cb-Rm@ca
    res=np.sqrt(((B-(A@Rm.T+t))**2).sum(1).mean())
    piv=None
    if abs(th)>np.radians(0.3): piv=np.linalg.solve(np.eye(2)-Rm,t)
    return np.degrees(th),piv,res
def affine(A,B):
    X=np.c_[A,np.ones(len(A))]; M,_,_,_=np.linalg.lstsq(X,B,rcond=None); return M[:2].T, M[2]
class Model:
    def __init__(s,name):
        s.name=name; s.g,_=load(name); s.F=frame(name); s.S=select(name)
    def V(s,cfg,reg=None,sel=None):
        pos=s.g['configs'][cfg]['pos']; sel=sel if sel is not None else s.S[reg]
        return np.concatenate([np.array(pos[d]).reshape(-1,2)[vi] for d,vi in sel]) if sel else np.zeros((0,2))
    def n(s,P):  # to normalised (u,v)
        return np.c_[(P[:,0]-s.F['cx'])/s.F['W'],(P[:,1]-s.F['chin'])/s.F['H']]
    def nd(s,D): return np.c_[D[:,0]/s.F['W'],D[:,1]/s.F['H']]
    def stats(s,cfg,reg=None,sel=None):
        A=s.V('base',reg,sel); B=s.V(cfg,reg,sel)
        if len(A)<3: return None
        d=s.nd(B-A).mean(0); th,piv,res=rigid(A,B)
        sx=(B[:,0].std()/A[:,0].std()) if A[:,0].std()>0 else 1
        o=dict(dx=round(d[0],4),dy=round(d[1],4),rot=round(th,2),sx=round(sx,3),warp=round(res/s.F['W'],4),n=int(len(A)))
        return o
    def neck_bands(s,cfg,nb=3):
        sel=s.S['neck']; A=s.V('base',sel=sel); B=s.V(cfg,sel=sel); v=s.n(A)[:,1]
        lo,hi=v.min(),v.max(); edges=np.linspace(hi,lo,nb+1); out=[]
        for i in range(nb):
            m=(v<=edges[i]+1e-9)&(v>=edges[i+1]-1e-9)
            d=s.nd(B[m]-A[m]).mean(0); th,_,_=rigid(A[m],B[m]) if m.sum()>=3 else (np.nan,None,0)
            out.append(dict(v_from=round(edges[i],3),v_to=round(edges[i+1],3),dx=round(d[0],4),dy=round(d[1],4),rot=round(th,2),n=int(m.sum())))
        return out
res={}
for name in MODELS:
    M=Model(name); r=res[name]={'frame':{k:round(float(v),5) for k,v in M.F.items()},'single':{},'neck_bands':{},'neck_profile5':{},'pivots':{},'pairs':{},'height_profile':{}}
    for cfg in SINGLE:
        r['single'][cfg]={reg:M.stats(cfg,reg) for reg in M.S if M.S[reg]}
        r['neck_bands'][cfg]=M.neck_bands(cfg,3); r['neck_profile5'][cfg]=M.neck_bands(cfg,5)
    # pivots: rigid fits
    torso=M.S['shoulders']+M.S['chest']+M.S['waist']
    body_all=torso+M.S['collar']+M.S['skirt_hem']+M.S['legs']
    for cfg in ['AZ+30','AZ-30','BZ+10','BZ-10']:
        pv={}
        for lab,sel in [('face',M.S['face']),('head_all',sum([M.S[k] for k in HEAD if k in M.S],[])),('neck',M.S['neck']),('collar',M.S['collar']),('torso',torso),('skirt_hem',M.S['skirt_hem']),('legs',M.S['legs']),('body_all',body_all)]:
            A=M.V('base',sel=sel); B=M.V(cfg,sel=sel); th,piv,rs=rigid(A,B)
            pp=M.n(piv[None])[0] if piv is not None else None
            pv[lab]=dict(rot=round(th,2),pivot_u=None if pp is None else round(pp[0],2),pivot_v=None if pp is None else round(pp[1],2),rms=round(rs/M.F['W'],4))
        r['pivots'][cfg]=pv
    # height profile for body params: dx,dy of all visible verts binned by v (body + head), and zero crossing
    g=M.g; allsel=[]
    for reg in M.S: allsel+= [x for x in M.S[reg] if reg not in ('hair_tails','hat')]
    A=M.V('base',sel=allsel); vv=M.n(A)[:,1]
    for cfg in ['BX+10','BY+10','BZ+10','Br=1','AX+30','AY+30','AZ+30']:
        B=M.V(cfg,sel=allsel); D=M.nd(B-A); prof=[]
        for top in np.arange(1.5,-6.01,-0.5):
            m=(vv<=top)&(vv>top-0.5)
            if m.sum()>=5: prof.append(dict(v=round(top-0.25,2),dx=round(D[m,0].mean(),4),dy=round(D[m,1].mean(),4),n=int(m.sum())))
        r['height_profile'][cfg]=prof
    # pairs: additivity & nesting
    for ab,a,b in PAIRS:
        pr={}
        for reg in ['face','eyes','front_hair','neck','collar','shoulders','chest']:
            sel=M.S.get(reg)
            if not sel: continue
            P0=M.V('base',sel=sel); PA=M.V(a,sel=sel); PB=M.V(b,sel=sel); PAB=M.V(ab,sel=sel)
            DA=PA-P0; DB=PB-P0; DAB=PAB-P0; scale=np.linalg.norm(DAB,axis=1).mean()+1e-12
            add=PAB-(P0+DA+DB)
            LA,tA=affine(P0,PA); LB,tB=affine(P0,PB)
            nestB_outer=PAB-(PB+DA@LB.T)   # B applied after (outside) A
            nestA_outer=PAB-(PA+DB@LA.T)   # A applied after (outside) B
            e=lambda X: round(float(np.linalg.norm(X,axis=1).mean()/M.F['W']),5)
            thA=rigid(P0,PA)[0]; thB=rigid(P0,PB)[0]; thAB=rigid(P0,PAB)[0]
            cA=M.nd(DA).mean(0); cB=M.nd(DB).mean(0); cAB=M.nd(DAB).mean(0)
            pr[reg]=dict(err_additive=e(add),err_B_outer=e(nestB_outer),err_A_outer=e(nestA_outer),mean_disp=round(float(scale/M.F['W']),5),
                         rel_additive=round(e(add)/(scale/M.F['W']),3),
                         rot_A=round(thA,2),rot_B=round(thB,2),rot_AB=round(thAB,2),
                         d_A=[round(x,4) for x in cA],d_B=[round(x,4) for x in cB],d_AB=[round(x,4) for x in cAB],d_sum=[round(x,4) for x in cA+cB])
        r['pairs'][ab]=pr
    # linearity / symmetry of face
    r['linearity']={k:{reg:M.stats(k,reg) for reg in ['face','neck','chest']} for k in ['AX+15','AY+15','AZ+15','BX+5','BY+5','BZ+5','Br=0.5']}
json.dump(res,open(__import__('os').path.dirname(__file__)+'/raw.json','w'),ensure_ascii=False,indent=0)
print('ok')
