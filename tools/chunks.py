import json, numpy as np, shapefile
from PIL import Image, ImageDraw, ImageFont
from pyproj import Transformer
D='./source-data/'; OUT='./'
exec(open('./proj.py').read())
def ll2px(lon,lat):
    v=view_of(lon,lat); return topx(v,lon,lat)
R=np.load(OUT+'raster.npz'); land=R['land']; usa=R['usa']; river=R['river']; elev=R['elev']; lc=R['lc']
def cblock(a): return a.reshape(CH,PX,CW,PX).swapaxes(1,2).reshape(CH,CW,PX*PX)
L=cblock(land).mean(-1); U=cblock(usa).mean(-1); E=cblock(np.where(land,elev,0)).mean(-1)
LCb=cblock(lc)
def frac(*codes): return np.isin(LCb,codes).mean(-1)
forest=frac(41,42,43,90); crops=frac(82,81); shrub=frac(52,31); urban=frac(22,23,24); grass=frac(71)
T={'Field':0,'Town':1,'Edge':2,'Born':3,'Farm':5,'MilitaryBase':7,'WoodCabin':9,'Hospital':12,'SuperMarket':13,'GunShop':14,
   'GasStation':16,'Stadium':21,'TrainStation':22,'Ocean':26,'CargoAirport':28,'Lake':33,'Laboratory':8,'NuclearPlant':42,'Port':39}
typ=np.zeros((CH,CW),np.int32); veg=np.clip(forest*1.2+grass*0.4+crops*0.3,0.05,1.0)
water=L<0.4
typ[water]=T['Ocean']
typ[(~water)&(crops>0.55)]=T['Farm']
# cities -> towns
p=shapefile.Reader(D+'ne_10m_populated_places/ne_10m_populated_places.shp')
cities=[]
for sr in p.iterShapeRecords():
    r=sr.record
    if r['ADM0_A3']!='USA': continue
    lon,lat=sr.shape.points[0]; v=view_of(lon,lat)
    if r['POP_MAX']<50000: continue
    if v['name']=='L48' and (lat<24 or lat>50 or lon<-126): continue
    px,py=ll2px(lon,lat); px=float(px); py=float(py); cx,cy=int(px//PX),int(py//PX)
    if not(0<=cx<CW and 0<=cy<CH): continue
    cities.append(dict(name=r['NAME'],pop=int(r['POP_MAX']),cx=cx,cy=cy,px=float(px),py=float(py)))
cities.sort(key=lambda c:-c['pop'])
towns=[]
for c in cities:
    rad=2 if c['pop']>=4e6 else 1 if c['pop']>=1e6 else 0
    cells=[(c['cx']+dx,c['cy']+dy) for dx in range(-rad,rad+1) for dy in range(-rad,rad+1) if abs(dx)+abs(dy)<=rad+ (1 if rad==2 else 0)]
    placed=0
    for (x,y) in cells:
        if 0<=x<CW and 0<=y<CH and not water[y,x] and typ[y,x]!=T['Town']:
            typ[y,x]=T['Town']; placed+=1
    if placed: towns.append(c)
# interstates
r=shapefile.Reader(D+'ne_10m_roads/ne_10m_roads.shp'); roads=[]
for sr in r.iterShapeRecords():
    rec=sr.record
    if rec['sov_a3']!='USA': continue
    pts=np.array(sr.shape.points); v=view_of(pts[0,0],pts[0,1])
    ok = rec['level']=='Interstate' or (v['name']=='AK' and rec['type']=='Major Highway') or (v['name']!='L48' and rec['level'] in ('Federal','State') and rec['type']=='Major Highway')
    if not ok: continue
    parts=list(sr.shape.parts)+[len(pts)]
    for a,b in zip(parts[:-1],parts[1:]):
        px,py=topx(v,pts[a:b,0],pts[a:b,1]); line=list(zip(px.tolist(),py.tolist()))
        if v['name']=='L48':   # keep lower-48 roads out of the inset boxes
            line=[p for p in line if not any(o['box'][0]<=p[0]<o['box'][2] and o['box'][1]<=p[1]<o['box'][3] for o in VIEWS[1:])]
        if len(line)>1: roads.append(line)
edges=set()
for line in roads:
    prev=None
    for (x0,y0),(x1,y1) in zip(line[:-1],line[1:]):
        n=max(2,int(max(abs(x1-x0),abs(y1-y0))/(PX/3)))
        for t in np.linspace(0,1,n):
            c=(int((x0+(x1-x0)*t)//PX),int((y0+(y1-y0)*t)//PX))
            if not(0<=c[0]<CW and 0<=c[1]<CH): continue
            if prev and c!=prev: edges.add(tuple(sorted((prev,c))))
            prev=c
roadcells={c for e in edges for c in e}
# gas stations along interstates every so often, a few real POIs
rng=np.random.default_rng(1776)
for c in sorted(roadcells):
    x,y=c
    if typ[y,x] in (T['Field'],T['Farm']) and rng.random()<0.08: typ[y,x]=T['GasStation']
POI=[('MilitaryBase',-79.0,35.14,'Fort Bragg'),('MilitaryBase',-97.78,31.13,'Fort Hood'),('MilitaryBase',-106.4,31.81,'Fort Bliss'),
     ('MilitaryBase',-117.35,33.3,'Camp Pendleton'),('MilitaryBase',-122.58,47.1,'Lewis-McChord'),('MilitaryBase',-87.48,36.66,'Fort Campbell'),
     ('MilitaryBase',-115.03,36.24,'Nellis'),('MilitaryBase',-76.3,36.95,'Norfolk'),('MilitaryBase',-84.0,32.36,'Fort Benning'),
     ('NuclearPlant',-112.86,33.39,'Palo Verde'),('NuclearPlant',-76.72,40.15,'Three Mile Island'),('NuclearPlant',-81.07,34.30,'V.C. Summer'),
     ('NuclearPlant',-96.05,28.80,'South Texas'),('NuclearPlant',-88.23,41.24,'Braidwood'),
     ('CargoAirport',-84.43,33.64,'ATL'),('CargoAirport',-87.9,41.98,'ORD'),('CargoAirport',-97.04,32.9,'DFW'),('CargoAirport',-104.67,39.86,'DEN'),
     ('CargoAirport',-89.98,35.04,'Memphis'),('CargoAirport',-85.74,38.17,'Louisville'),
     ('Port',-118.26,33.73,'Port of LA'),('Port',-95.0,29.73,'Port of Houston'),('Port',-74.15,40.68,'Port Newark'),('Port',-122.36,47.58,'Seattle'),
     ('Laboratory',-106.3,35.88,'Los Alamos'),('Laboratory',-84.27,35.93,'Oak Ridge'),('Laboratory',-115.8,37.24,'Area 51'),
     ('Stadium',-74.07,40.81,'MetLife'),('Stadium',-97.09,32.75,'AT&T'),('Hospital',-76.59,39.3,'Johns Hopkins'),('Hospital',-92.47,44.02,'Mayo')]
pois=[]
for kind,lon,lat,name in POI:
    px,py=ll2px(lon,lat); cx,cy=int(px//PX),int(py//PX)
    # nudge onto land
    best=None
    for dx in range(-2,3):
        for dy in range(-2,3):
            X,Y=cx+dx,cy+dy
            if 0<=X<CW and 0<=Y<CH and not water[Y,X] and typ[Y,X]!=T['Town']:
                dd=dx*dx+dy*dy
                if best is None or dd<best[0]: best=(dd,X,Y)
    if best: typ[best[2],best[1]]=T[kind]; pois.append(dict(kind=kind,name=name,cx=best[1],cy=best[2]))
# map border ring = Edge, like the game's own maps
typ[0,:]=typ[-1,:]=typ[:,0]=typ[:,-1]=T['Edge']
# spawn chunk: near St. Louis-ish? pick Kansas center (geographic center of lower 48)
px,py=ll2px(-98.58,39.83); born=(int(float(px)//PX),int(float(py)//PX)); typ[born[1],born[0]]=T['Born']
json.dump(dict(cw=CW,ch=CH,types=typ.tolist(),veg=np.round(veg,2).tolist(),elev=np.round(E).astype(int).tolist(),
               us=np.round(U,2).tolist(),land=np.round(L,2).tolist(),edges=sorted(edges),towns=towns,pois=pois,born=born),
          open(OUT+'usmap.json','w'))
from collections import Counter
inv={v:k for k,v in T.items()}; print({inv[k]:v for k,v in Counter(typ.ravel().tolist()).items()}, 'edges',len(edges),'towns',len(towns))
