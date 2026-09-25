import sys
sys.path.insert(0,__import__('os').path.dirname(__file__))
from render import *
from PIL import Image, ImageDraw
name=sys.argv[1]; box=tuple(map(float,sys.argv[3].split(','))); out=sys.argv[4]; tw=int(sys.argv[5]) if len(sys.argv)>5 else 300
g,_=load(name); ids=[d['id'] for d in g['drawables']]
cand=[ids.index(x) if not x.isdigit() else int(x) for x in sys.argv[2].split(',')]
allv={d for d,dr in enumerate(g['drawables']) if visible(dr)}
ims=[]
for d in cand:
    im=render(name,box=box,px=tw,only={d},fade=allv,tint={d:(1,0,0)})
    ImageDraw.Draw(im).rectangle((0,0,tw,14),fill=(255,255,255)); ImageDraw.Draw(im).text((3,2),f"{d} {ids[d]}",fill=(0,0,0))
    ims.append(im)
cols=min(6,len(ims)); h=ims[0].height; rows=(len(ims)+cols-1)//cols
sheet=Image.new('RGB',(cols*tw, rows*h),'white')
for i,im in enumerate(ims): sheet.paste(im,((i%cols)*tw,(i//cols)*h))
sheet.save(out); print(len(ims),'->',out)
