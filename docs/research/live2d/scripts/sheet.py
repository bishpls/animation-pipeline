import sys, numpy as np, json
sys.path.insert(0,__import__('os').path.dirname(__file__))
from render import *
from PIL import Image, ImageDraw
name=sys.argv[1]; parts=sys.argv[2].split(','); box=tuple(map(float,sys.argv[3].split(','))); out=sys.argv[4]
g,_=load(name)
cand=[d for d,dr in enumerate(g['drawables']) if visible(dr) and any(dr['part'].split('>')[-1]==p or dr['part'].startswith(p) for p in parts)]
allv={d for d,dr in enumerate(g['drawables']) if visible(dr)}
tw=260; ims=[]
full=render(name,box=box,px=tw*2)
for d in cand:
    im=render(name,box=box,px=tw,only={d},fade=allv)
    ImageDraw.Draw(im).text((4,4),f"{d} {g['drawables'][d]['id']} {g['drawables'][d]['part'][-8:]}",fill=(200,0,0))
    ims.append(im)
cols=6; h=ims[0].height; rows=(len(ims)+cols-1)//cols
sheet=Image.new('RGB',(cols*tw+full.width, max(rows*h, full.height)),'white')
sheet.paste(full,(cols*tw,0))
for i,im in enumerate(ims): sheet.paste(im,((i%cols)*tw,(i//cols)*h))
sheet.save(out); print(len(cand),'meshes ->',out)
