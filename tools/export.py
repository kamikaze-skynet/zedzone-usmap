# Writes usmap.bin for the mod: chunk grid + smooth water/ocean fields + elevation.
import json, struct, gzip, numpy as np
from PIL import Image, ImageFilter
OUT='./'; R=np.load(OUT+'raster.npz'); M=json.load(open(OUT+'usmap.json'))
land=R['land']; river=R['river']; elev=R['elev']; H,W=land.shape
CW,CH=M['cw'],M['ch']
# ocean = water connected to the map border (everything else is lake/river)
from collections import deque
water=(~land)|river
ocean=np.zeros_like(water); q=deque()
for x in range(W):
    for y in (0,H-1):
        if water[y,x] and not ocean[y,x]: ocean[y,x]=True; q.append((y,x))
for y in range(H):
    for x in (0,W-1):
        if water[y,x] and not ocean[y,x]: ocean[y,x]=True; q.append((y,x))
while q:
    y,x=q.popleft()
    for dy,dx in ((1,0),(-1,0),(0,1),(0,-1)):
        Y,X=y+dy,x+dx
        if 0<=Y<H and 0<=X<W and water[Y,X] and not ocean[Y,X] and not river[Y,X]: ocean[Y,X]=True; q.append((Y,X))
def smooth(mask,r=1.2):
    im=Image.fromarray((mask*255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r)); return np.array(im)
wf=smooth(water); of=smooth(ocean)
el=np.array(Image.fromarray(np.where(land,elev,0).astype(np.float32)).resize((W//2,H//2),Image.BILINEAR))
el=np.clip(el,-500,6000).astype(np.int16)
types=np.array(M['types'],np.uint8); veg=(np.array(M['veg'])*255).astype(np.uint8)
edges=M['edges']; born=M['born']
b=bytearray()
b+=b'USMP'+struct.pack('<iiiiii',1,CW,CH,W,H,len(edges))
b+=struct.pack('<ii',born[0],born[1])
b+=types.tobytes()+veg.tobytes()
for (a,c) in edges: b+=struct.pack('<hhhh',a[0],a[1],c[0],c[1])
b+=wf.astype(np.uint8).tobytes()+of.astype(np.uint8).tobytes()
b+=struct.pack('<ii',W//2,H//2)+el.tobytes()
open(OUT+'usmap.bin','wb').write(gzip.compress(bytes(b),9))
print('bytes',len(b),'gz',len(gzip.compress(bytes(b),9)),'ocean%',ocean.mean(),'water%',water.mean())
