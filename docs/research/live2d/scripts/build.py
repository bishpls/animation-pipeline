import json, numpy as np, sys, os
sys.path.insert(0,os.path.dirname(__file__))
from regions import R as RSPEC
H=os.path.dirname(__file__); raw=json.load(open(H+'/raw.json')); mot=json.load(open(H+'/motion_summary.json'))
M=list(raw.keys())
def med(vals):
    v=[x for x in vals if x is not None and not (isinstance(x,float) and np.isnan(x))]
    return None if not v else round(float(np.median(v)),4)
def medrec(recs):
    recs=[r for r in recs if r]; 
    if not recs: return None
    keys=[k for k in recs[0] if isinstance(recs[0][k],(int,float))]
    return {k:med([r.get(k) for r in recs]) for k in keys}
def ratio(a,b,minb=1e-3):
    return None if (a is None or b is None or abs(b)<minb) else round(a/b,3)
REG=['face','eyes','brows','mouth','nose','front_hair','side_hair','back_hair','hair_tails','ears','hat','glasses','neck','collar','neckwear','shoulders','upper_arms','chest','waist','skirt_hem','legs']
out={'meta':{
 'source':'Live2D CubismWebSamples (github.com/Live2D/CubismWebSamples, Samples/Resources, commit b1de66b, 2026-04-02); .moc3 evaluated with Live2D Cubism Core 5.1.0 (JS) in Node; no physics, no pose/fade, no expressions; all other params at defaults',
 'models':M,'models_excluded':{'Ren':'moc3 v6 needs Core 6.x (not available); motions still used','Rice':'chibi 3/4 view, no AngleY/Breath; motions reported separately','Mark':'mascot proportions, no neck'},
 'units':'dx = displacement / face-outline-mesh width (W); dy = displacement / face-outline-mesh height (H); positions u=(x-face_centre_x)/W, v=(y-chin_y)/H; canvas y UP (Cubism model space), x = screen right',
 'rot':'best-fit rigid (Procrustes) rotation of the region vertex set, degrees, positive = counter-clockwise on screen (y up). Negative = top of the region moves to screen right',
 'sx':'ratio of horizontal spread (std of x) after/before; <1 = horizontal compression',
 'warp':'RMS residual after best rigid fit, /W (non-rigid part of the motion)',
 'sign_conventions':'AngleX+ and BodyAngleX+ move the face/chest to screen right (character turns to their own left). AngleY+/BodyAngleY+ move up. AngleZ+/BodyAngleZ+ rotate clockwise on screen (head top toward screen right). EyeBallX+ moves irises screen right.',
 'neck_bands':'neck mesh vertices split into equal thirds (or fifths) of the mesh vertical extent; v_from/v_to give the band edges relative to the chin (v=0). The top band is mostly hidden behind the jaw; the bottom is hidden under the collar',
 'median':'median across the 4 measured models of per-model values (None when unavailable)'},
 'frames':{m:raw[m]['frame'] for m in M},
 'region_definitions':{m:{'face_mesh':RSPEC[m]['face'],'regions':RSPEC[m]['regions']} for m in M}}
# 1. single-parameter tables
cfgs=list(raw[M[0]]['single'].keys())
T={}
for cfg in cfgs:
    T[cfg]={}
    for reg in REG:
        per={m:raw[m]['single'][cfg].get(reg) for m in M}
        if not any(per.values()): continue
        T[cfg][reg]={'per_model':per,'median':medrec(list(per.values()))}
    for bi,b in enumerate(['neck_top','neck_mid','neck_bottom']):
        per={m:raw[m]['neck_bands'][cfg][bi] for m in M}; T[cfg][b]={'per_model':per,'median':medrec(list(per.values()))}
out['single_param']=T
out['neck_profile_5band']={cfg:{m:raw[m]['neck_profile5'][cfg] for m in M} for cfg in cfgs}
# 2. derived ratios
D={}
def rr(cfg,key,ref,regs,src='single'):
    res={}
    for reg in regs:
        per={}
        for m in M:
            if reg.startswith('neck_'):
                idx={'neck_top':0,'neck_mid':1,'neck_bottom':2}[reg]; a=raw[m]['neck_bands'][cfg][idx][key]
            else:
                s=raw[m]['single'][cfg].get(reg); a=s[key] if s else None
            b=raw[m]['single'][cfg][ref][key]
            per[m]=ratio(a,b,0.3 if key=='rot' else 1e-3)
        res[reg]={'per_model':per,'median':med(list(per.values()))}
    return res
headregs=['eyes','mouth','nose','front_hair','side_hair','back_hair','ears','neck_top','neck_mid','neck_bottom','collar','shoulders','chest']
D['AX+30_dx_over_face_dx']=rr('AX+30','dx','face',headregs)
D['AY+30_dy_over_face_dy']=rr('AY+30','dy','face',headregs)
D['AZ+30_rot_over_face_rot']=rr('AZ+30','rot','face',headregs)
D['AZ+30_dx_over_face_dx']=rr('AZ+30','dx','face',headregs)
bodyregs=['face','neck_top','neck_mid','neck_bottom','collar','neckwear','shoulders','upper_arms','chest','waist','skirt_hem','legs']
D['BZ+10_rot_over_face_rot (Haru excluded: its BZ is a shear, face rot only -0.5 deg)']=rr('BZ+10','rot','face',bodyregs)
for k in list(D.keys()):
    if k.startswith('BZ'):
        for reg in D[k]: D[k][reg]['per_model']['Haru']=None; D[k][reg]['median']=med([v for mm,v in D[k][reg]['per_model'].items()])
D['BX+10_dx_over_chest_dx']=rr('BX+10','dx','chest',bodyregs)
D['BY+10_dy_over_chest_dy']=rr('BY+10','dy','chest',bodyregs)
D['Br=1_dy_over_face_dy']=rr('Br=1','dy','face',bodyregs)
out['ratios']=D
# 3. pivots & gains
P={}
for cfg in ['AZ+30','AZ-30','BZ+10','BZ-10']:
    P[cfg]={}
    for lab in raw[M[0]]['pivots'][cfg]:
        per={m:raw[m]['pivots'][cfg][lab] for m in M}
        use=[x for mm,x in per.items() if not (cfg.startswith('BZ') and mm=='Haru')]
        P[cfg][lab]={'per_model':per,'median':medrec([{k:v for k,v in x.items() if v is not None} for x in use])}
        if cfg.startswith('BZ'): P[cfg][lab]['median_note']='median excludes Haru (BZ is a lateral shear in Haru: near-zero rotation, pivot at infinity)'
out['pivots']=P
out['pivot_notes']={'AZ':'Face rotation about a fixed point: u~0, v=+0.04..+0.19 (just above the chin). Gain: -5.2/-10/-15/-10 deg at AngleZ=+30 (Haru/Hiyori/Mao/Natori), i.e. ~1/3 deg per unit.',
 'BZ':'Head+neck+collar rotate rigidly as one block about v=-1.17..-2.32 (below the chin, between sternum and waist); lower bands rotate less about progressively lower pivots (progressive spine bend, not one rigid pivot). Haru is an outlier: BZ is a lateral shear (head translates 0.17 W, rotates only 0.5 deg).',
 'BX':'Not a rotation: horizontal shift peaking at the chest centre line; head translates rigidly (no rotation); legs ~0. Zero crossing around the hips/thighs.',
 'BY':'Vertical shift of everything above the waist; head moves with the chest; dy->0 at hips (Hiyori v~-2.5, Natori ~-2.8, Mao legs ~-5.5); Haru translates the whole figure.'}
out['height_profiles']={cfg:{m:raw[m]['height_profile'][cfg] for m in M} for cfg in raw[M[0]]['height_profile']}
# 4. combinations
C={}
for ab in raw[M[0]]['pairs']:
    C[ab]={}
    for reg in ['face','eyes','front_hair','neck','collar','shoulders','chest']:
        per={m:raw[m]['pairs'][ab].get(reg) for m in M}
        if not any(per.values()): continue
        C[ab][reg]={'per_model':per,'median':medrec([{k:v for k,v in x.items() if isinstance(v,(int,float))} for x in per.values() if x])}
out['combinations']=C
out['combination_notes']={
 'fields':'err_additive = mean |P_AB - (P0 + D_A + D_B)| / W; err_B_outer = mean |P_AB - (P_B + L_B*D_A)| / W where L_B is the 2x2 linear part of the best affine fit of B alone on that region (B applied after/outside A); err_A_outer likewise. rel_additive = err_additive / mean|D_AB|. rot_* = rigid-fit rotations.',
 'AX+30&AZ+30':'Not additive (face rel err 6-15%). Exactly reproduced (err <1e-4 W) by rotating the AngleX warp result with the AngleZ rotation: Z is applied AFTER (outside) the XY warp. Same for AX-30&AZ+30 and AY+30&AZ+30.',
 'AX+30&AY+30':'Same deformer (2-D keyform grid). Centroid ~additive, but per-vertex shape differs from the sum by 1.5% (Hiyori) to 9-16% (Haru, Mao, Natori): the (30,30) corner is a separately drawn keyform, blended bilinearly. No nesting order explains it.',
 'AZ+30&BZ+10':'Head angles add exactly (-10 + -4.7 = -14.7 deg for Hiyori). Exactly reproduced by applying the BodyZ rotation AFTER the head: body Z is the parent.',
 'AX+30&BX+10':'Additive to <1e-4 W: BodyX only translates the head, so order is immaterial (consistent with BodyX warp being the parent).',
 'BX+10&BZ+10':'BZ applied after BX fits better (err 0.06-2.4e-3 W) than additive (2-16e-3 W): body Z rotation is outermost.',
 'inferred_chain_outer_to_inner':['BodyAngleZ rotation (pivot sternum-waist, progressive by height)','BodyAngleX/BodyAngleY/Breath warps (head carried by translation only)','neck mesh (own warp keyed on Angle X/Y/Z: top follows head partially, bottom pinned)','AngleZ rotation (pivot at chin, ~1/3 deg per unit)','AngleX/AngleY face warp (2-D keyform grid, per-layer parallax)','face parts (eyes, mouth, hair...)']}
# 5. linearity/symmetry
out['linearity']={m:raw[m]['linearity'] for m in M}
out['linearity_note']='All params have keys at min/0/max (Breath 0/1). Half-value displacement = 0.50 of full within 1% for every region: piecewise-linear between keyforms.'
sym={}
for m in M:
    S=raw[m]['single']
    sym[m]={'AX face dx (-30,+30)':[S['AX-30']['face']['dx'],S['AX+30']['face']['dx']],'AY face dy (-30,+30)':[S['AY-30']['face']['dy'],S['AY+30']['face']['dy']],
            'AZ face rot (-30,+30)':[S['AZ-30']['face']['rot'],S['AZ+30']['face']['rot']],'BZ face rot (-10,+10)':[S['BZ-10']['face']['rot'],S['BZ+10']['face']['rot']],
            'BX chest dx (-10,+10)':[S['BX-10']['chest']['dx'],S['BX+10']['chest']['dx']],'BY face dy (-10,+10)':[S['BY-10']['face']['dy'],S['BY+10']['face']['dy']]}
out['symmetry']=sym
out['symmetry_note']='Looking/bending DOWN is larger than up: AY-30 face dy is 1.0-1.9x AY+30; BY-10 is 1.0-2.1x BY+10. X and Z are near-symmetric (Haru AZ 6.0 vs 5.2 deg; Hiyori BZ 3.8 vs 4.7 deg).'
# 6. motions
out['motions']=mot
out['motion_notes']={'lag':'vel_lag_s: lag maximising the correlation of the two parameter VELOCITIES (60 Hz resampled curves), searched within +-1 s; positive = second parameter (body, or head for eye|head pairs) moves LATER than the first. key_lag: time of each extremum key of the second curve minus the nearest same-polarity extremum key of the first within 1 s.',
 'ratio':'ptp_ratio = peak-to-peak(head param) / peak-to-peak(body param) in parameter units, over motions where both move (head >=3 units, body >=1 unit, eyeball >=0.2).',
 'counter':'frac_counter = share of active motions whose zero-lag correlation < -0.2 (opposite directions); frac_same: > +0.2.',
 'motion_sets':'main = Hiyori(10), Haru(27), Mao(8), Natori(8), Ren(3) = 56 motion3.json files; extra = Rice(4), Mark(6).'}
json.dump(out,open(H+'/../coupling.json','w'),ensure_ascii=False,indent=1,default=float)
print('written', os.path.getsize(H+'/../coupling.json'))
# quick print of key medians
for k,v in D.items():
    print(k); print('   ',{reg:x['median'] for reg,x in v.items()})
