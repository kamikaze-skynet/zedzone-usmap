import json, numpy as np
from PIL import Image, ImageDraw, ImageFont
OUT='./'; R=np.load(OUT+'raster.npz'); M=json.load(open(OUT+'usmap.json'))
land=R['land']; usa=R['usa']; river=R['river']; elev=R['elev']; lc=R['lc']; H,W=land.shape; PX=24
COL={11:(70,110,160),12:(230,235,245),21:(200,185,170),22:(190,150,130),23:(180,90,80),24:(150,60,60),31:(190,180,160),
     41:(110,160,90),51:(170,150,90),72:(190,190,130),73:(160,190,100),74:(140,180,150),42:(50,100,60),43:(120,160,100),52:(200,180,130),71:(215,210,160),81:(200,200,110),82:(180,150,90),90:(120,160,140),95:(110,150,160),0:(170,170,150)}
rgb=np.zeros((H,W,3),np.float32)
for k,c in COL.items(): rgb[lc==k]=c
rgb[(lc==0)&land]=(160,165,140)
# hillshade
e=elev.astype(np.float32); gy,gx=np.gradient(e); px_m=4800000/W
sl=np.arctan(np.hypot(gx,gy)/px_m*8); asp=np.arctan2(-gx,gy)
az=np.radians(315); alt=np.radians(45)
hs=np.sin(alt)*np.cos(sl)+np.cos(alt)*np.sin(sl)*np.cos(az-asp); hs=np.clip(hs,0,1)
rgb*= (0.55+0.6*hs)[...,None]
fg=land&~usa; g=rgb[fg].mean(-1,keepdims=True); rgb[fg]=rgb[fg]*0.35+g*0.65*0.9
water=~land|river
rgb[water]=(40,80,135); rgb[river&land]=(60,110,170)
img=Image.fromarray(np.clip(rgb,0,255).astype(np.uint8)); d=ImageDraw.Draw(img,'RGBA')
for (a,b) in M['edges']:
    d.line([(a[0]*PX+PX/2,a[1]*PX+PX/2),(b[0]*PX+PX/2,b[1]*PX+PX/2)],fill=(225,60,40,230),width=4)
T=np.array(M['types'])
for y in range(M['ch']):
    for x in range(M['cw']):
        t=T[y,x]
        if t==1: d.rectangle([x*PX+2,y*PX+2,x*PX+PX-3,y*PX+PX-3],fill=(255,240,200,150),outline=(60,50,40,255),width=2)
cmap={'MilitaryBase':(60,90,40),'NuclearPlant':(240,220,0),'CargoAirport':(120,120,255),'Port':(0,200,220),'Laboratory':(200,0,200),'Stadium':(255,140,0),'Hospital':(255,255,255)}
for p in M['pois']:
    x,y=p['cx']*PX+PX/2,p['cy']*PX+PX/2; d.ellipse([x-9,y-9,x+9,y+9],fill=cmap[p['kind']]+(255,),outline=(0,0,0,255),width=2)
bx,by=M['born']; d.polygon([(bx*PX+12,by*PX-6),(bx*PX+30,by*PX+30),(bx*PX-6,by*PX+30)],fill=(255,255,0,255),outline=(0,0,0,255))
try: f=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',26); fs=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',40)
except: f=fs=ImageFont.load_default()
for c in M['towns'][:40]+[t for t in M['towns'] if t['name'] in ('Anchorage','Honolulu','Fairbanks','Juneau','Hilo')]:
    d.text((c['px']+14,c['py']-14),c['name'].replace(',  D.C.',' DC'),font=f,fill=(255,255,255,255),stroke_width=3,stroke_fill=(0,0,0,255))
for vw in json.load(open(OUT+'views.json'))[1:]:
    b=vw['box']; d.rectangle([b[0],b[1],b[2],b[3]],outline=(255,255,255,200),width=3); d.text((b[0]+12,b[1]+8),{'AK':'Alaska (40% scale)','HI':'Hawaii'}[vw['name']],font=f,fill=(255,255,255,255),stroke_width=3,stroke_fill=(0,0,0,255))
# chunk grid
for x in range(0,W,PX*8): d.line([(x,0),(x,H)],fill=(255,255,255,40),width=1)
for y in range(0,H,PX*8): d.line([(0,y),(W,y)],fill=(255,255,255,40),width=1)
d.rectangle([1500,20,2730,150],fill=(0,0,0,170))
d.text((1520,30),'ZED ZONE - United States, lower 48 states (preview)',font=fs,fill=(255,255,255,255))
d.text((1520,85),'128 x 80 chunks  |  red = interstates  |  boxes = towns  |  dots = bases, plants, airports, ports, labs  |  yellow = spawn',font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',24) if f else f,fill=(230,230,230,255))
img.save(OUT+'preview_full.png'); img.resize((1920,1200),Image.LANCZOS).save(OUT+'preview.png')
# zoom crop: northeast
img.crop((int(W*0.74),int(H*0.18),int(W*0.74)+960,int(H*0.18)+600)).save(OUT+'preview_northeast.png')
print('ok')
