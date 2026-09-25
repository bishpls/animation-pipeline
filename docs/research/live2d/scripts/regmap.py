import sys,colorsys
sys.path.insert(0,__import__('os').path.dirname(__file__))
from render import *; from sel import select, frame
from PIL import ImageDraw
name=sys.argv[1]; S=select(name); F=frame(name); g,_=load(name); base=g['configs']['base']['pos']
box=(F['cx']-2*F['W'],F['chin']-3.2*F['H'],F['cx']+2*F['W'],F['chin']+1.4*F['H']); px=700
im=render(name,box=box,px=px); d=ImageDraw.Draw(im); s=px/(box[2]-box[0])
regs=list(S.keys())
for i,r in enumerate(regs):
    col=tuple(int(255*c) for c in colorsys.hsv_to_rgb(i/len(regs),1,0.9))
    for dd,vi in S[r]:
        v=np.array(base[dd]).reshape(-1,2)[vi]
        for x,y in v: X=(x-box[0])*s; Y=(box[3]-y)*s; d.ellipse((X-2,Y-2,X+2,Y+2),fill=col)
    d.text((5,5+i*12),f"{r} n={sum(len(v) for _,v in S[r])}",fill=col)
im.save(f'{H}/regmap_{name}.png'); print(name,{r:sum(len(v) for _,v in S[r]) for r in regs})
