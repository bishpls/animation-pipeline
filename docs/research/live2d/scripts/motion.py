import json,glob,numpy as np
R=__import__('os').path.dirname(__file__)+'/../cws/Samples/Resources/'
MAIN=['Hiyori','Haru','Mao','Natori','Ren']; EXTRA=['Rice','Mark']
FS=60.0
def parse(seg):
    """returns list of pieces: (kind,t0,v0,t1,v1,ctrl) """
    out=[]; t0,v0=seg[0],seg[1]; i=2; keys=[(t0,v0)]
    while i<len(seg):
        k=int(seg[i])
        if k==1:
            c=(seg[i+1],seg[i+2],seg[i+3],seg[i+4]); t1,v1=seg[i+5],seg[i+6]; out.append(('bez',t0,v0,t1,v1,c)); i+=7
        else:
            t1,v1=seg[i+1],seg[i+2]; out.append(({0:'lin',2:'step',3:'istep'}[k],t0,v0,t1,v1,None)); i+=3
        t0,v0=t1,v1; keys.append((t0,v0))
    return out,keys
def evaluate(pieces,ts,restricted):
    y=np.empty_like(ts); 
    for j,t in enumerate(ts):
        p=pieces[-1]
        for q in pieces:
            if t<=q[3]: p=q; break
        kind,t0,v0,t1,v1,c=p
        if t>=t1: y[j]=v1; continue
        if t<=t0: y[j]=v0; continue
        if kind=='lin': y[j]=v0+(v1-v0)*(t-t0)/(t1-t0)
        elif kind=='step': y[j]=v0
        elif kind=='istep': y[j]=v1
        else:
            if restricted: s=(t-t0)/(t1-t0)
            else:
                lo,hi=0.0,1.0
                for _ in range(40):
                    s=(lo+hi)/2; x=(1-s)**3*t0+3*(1-s)**2*s*c[0]+3*(1-s)*s*s*c[2]+s**3*t1
                    if x<t: lo=s
                    else: hi=s
            y[j]=(1-s)**3*v0+3*(1-s)**2*s*c[1]+3*(1-s)*s*s*c[3]+s**3*v1
    return y
def load_motion(f):
    d=json.load(open(f)); M=d['Meta']; ts=np.arange(0,M['Duration']+1e-9,1/FS); cur={}; keys={}
    for cv in d['Curves']:
        if cv['Target']!='Parameter': continue
        pcs,ks=parse(cv['Segments'])
        cur[cv['Id']]=evaluate(pcs,ts,M.get('AreBeziersRestricted',False)) if pcs else np.full_like(ts,ks[0][1]); keys[cv['Id']]=ks
    return ts,cur,keys,M
PAIRS=[('ParamAngleX','ParamBodyAngleX',3,1),('ParamAngleY','ParamBodyAngleY',3,1),('ParamAngleZ','ParamBodyAngleZ',3,1),
       ('ParamEyeBallX','ParamAngleX',0.2,3),('ParamEyeBallY','ParamAngleY',0.2,3),('ParamAngleX','ParamBodyAngleZ',3,1),('ParamAngleZ','ParamBodyAngleX',3,1),('ParamAngleZ','ParamAngleX',3,3)]
def xlag(a,b,maxlag=1.0,sign=1):
    """lag (s) maximising sign*corr(a(t), b(t+lag)); positive => b later than a"""
    da=np.gradient(a); db=np.gradient(b); n=len(a); L=int(maxlag*FS); best=(-2,0)
    for k in range(-L,L+1):
        if k>=0: x,y=da[:n-k],db[k:]
        else: x,y=da[-k:],db[:n+k]
        if len(x)<10 or x.std()==0 or y.std()==0: continue
        c=sign*np.corrcoef(x,y)[0,1]
        if c>best[0]: best=(c,k/FS)
    return best[1],best[0]
def extrema(ks):
    out=[]
    for i in range(1,len(ks)-1):
        a,b,c=ks[i-1][1],ks[i][1],ks[i+1][1]
        if (b-a)*(c-b)<0 or (b!=a and c==b) : out.append((ks[i][0],1 if b>a else -1))
    return out
def keylag(kh,kb,sign):
    eh=extrema(kh); eb=extrema(kb); d=[]
    for tb,pb in eb:
        cand=[th for th,ph in eh if ph==pb*sign and abs(th-tb)<=1.0]
        if cand: th=min(cand,key=lambda x:abs(x-tb)); d.append(tb-th)
    return d
rows=[]
for m in MAIN+EXTRA:
    for f in sorted(glob.glob(f'{R}{m}/motions/*.motion3.json')):
        ts,cur,keys,M=load_motion(f)
        for h,b,th,tb in PAIRS:
            if h not in cur or b not in cur: continue
            a=cur[h]; c=cur[b]
            if np.ptp(a)<th or np.ptp(c)<tb: 
                rows.append(dict(model=m,motion=f.split('/')[-1],pair=h+'|'+b,active=False,ptp_head=float(np.ptp(a)),ptp_body=float(np.ptp(c)))); continue
            r0=np.corrcoef(a,c)[0,1]; sign=1 if r0>=0 else -1
            lag,cl=xlag(a,c,1.0,sign)
            va=np.gradient(a)*FS; vc=np.gradient(c)*FS; mv=(np.abs(va)>0.1*np.abs(va).max())&(np.abs(vc)>0.1*np.abs(vc).max())
            opp=float((np.sign(va[mv])!=np.sign(vc[mv])).mean()) if mv.sum()>5 else None
            kl=keylag(keys[h],keys[b],sign)
            rows.append(dict(model=m,motion=f.split('/')[-1],pair=h+'|'+b,active=True,dur=M['Duration'],ptp_head=round(float(np.ptp(a)),2),ptp_body=round(float(np.ptp(c)),2),
                std_ratio=round(float(a.std()/c.std()),2),ptp_ratio=round(float(np.ptp(a)/np.ptp(c)),2),corr0=round(float(r0),2),vel_lag_s=round(lag,3),vel_corr=round(float(cl),2),
                opp_vel_frac=None if opp is None else round(opp,2),key_lags=[round(x,3) for x in kl]))
json.dump(rows,open(__import__('os').path.dirname(__file__)+'/motion_rows.json','w'),indent=0)
def summ(models):
    out={}
    for h,b,_,_ in PAIRS:
        rr=[r for r in rows if r['pair']==h+'|'+b and r['model'] in models]; act=[r for r in rr if r['active']]
        if not act: continue
        kl=sum([r['key_lags'] for r in act],[])
        out[h+'|'+b]=dict(n_motions=len(rr),n_active=len(act),
            frac_counter=round(np.mean([r['corr0']<-0.2 for r in act]),2),frac_same=round(np.mean([r['corr0']>0.2 for r in act]),2),
            median_corr0=round(float(np.median([r['corr0'] for r in act])),2),
            median_ptp_ratio=round(float(np.median([r['ptp_ratio'] for r in act])),2),iqr_ptp_ratio=[round(float(np.percentile([r['ptp_ratio'] for r in act],q)),2) for q in (25,75)],
            median_vel_lag_s=round(float(np.median([r['vel_lag_s'] for r in act])),3),iqr_vel_lag_s=[round(float(np.percentile([r['vel_lag_s'] for r in act],q)),3) for q in (25,75)],
            frac_body_lags=round(np.mean([r['vel_lag_s']>0.017 for r in act]),2),frac_body_leads=round(np.mean([r['vel_lag_s']<-0.017 for r in act]),2),
            n_key_pairs=len(kl),median_key_lag_s=None if not kl else round(float(np.median(kl)),3),iqr_key_lag_s=None if not kl else [round(float(np.percentile(kl,q)),3) for q in (25,75)],
            frac_key_zero=None if not kl else round(float(np.mean(np.abs(np.array(kl))<0.02)),2),
            median_opp_vel_frac=round(float(np.median([r['opp_vel_frac'] for r in act if r['opp_vel_frac'] is not None])),2))
    return out
S={'main_5_models':summ(MAIN),'per_model':{m:summ([m]) for m in MAIN},'extra_Rice_Mark':summ(EXTRA)}
json.dump(S,open(__import__('os').path.dirname(__file__)+'/motion_summary.json','w'),indent=1)
for k,v in S['main_5_models'].items(): print(k,v)
print()
for m in MAIN:
    for k in ['ParamAngleX|ParamBodyAngleX','ParamAngleZ|ParamBodyAngleZ','ParamAngleY|ParamBodyAngleY','ParamEyeBallX|ParamAngleX']:
        v=S['per_model'][m].get(k); 
        if v: print(m,k,'act',v['n_active'],'/',v['n_motions'],'ratio',v['median_ptp_ratio'],'corr',v['median_corr0'],'counter',v['frac_counter'],'vlag',v['median_vel_lag_s'],'klag',v['median_key_lag_s'],'kzero',v['frac_key_zero'])
