# Bakes the ZED ZONE US map: the lower 48 states (no Alaska or Hawaii).
import json, math, numpy as np, shapefile, netCDF4, urllib.request, io
from PIL import Image, ImageDraw
from pyproj import Transformer
D='./source-data/'; OUT='./'
CW,CH,PX=128,80,24; W,H=CW*PX,CH*PX
# views: name, crs, crs bbox (x0,x1,y0,y1), pixel box (px0,py0,px1,py1), state filter, etopo file, nlcd layer
VIEWS=[
 dict(name='L48',crs=5070,bbox=(-2400000,2400000,200000,3200000),box=(0,0,W,H),states=lambda n:n not in('Alaska','Hawaii'),
      etopo='etopo.nc',nlcd='NLCD_2021_Land_Cover_L48',lonlat=(-135,18,-55,56)),
]
mpp=(VIEWS[0]['bbox'][1]-VIEWS[0]['bbox'][0])/W   # metres per pixel at full scale
for v in VIEWS[1:]:
    x0,x1,y0,y1=v['bbox']; w=int((x1-x0)*v['scale']/mpp); h=int((y1-y0)*v['scale']/mpp)
    px0,py0=v['at'][0]*PX,v['at'][1]*PX; v['box']=(px0,py0,min(W,px0+w),min(H,py0+h)); v['full']=(w,h)
for v in VIEWS:
    v['fwd']=Transformer.from_crs(4326,v['crs'],always_xy=True); v['inv']=Transformer.from_crs(v['crs'],4326,always_xy=True)
    if 'full' not in v: v['full']=(W,H)
def topx(v,lon,lat):
    x,y=v['fwd'].transform(np.asarray(lon),np.asarray(lat)); x0,x1,y0,y1=v['bbox']; w,h=v['full']
    return v['box'][0]+(np.asarray(x)-x0)/(x1-x0)*w, v['box'][1]+(y1-np.asarray(y))/(y1-y0)*h
def view_of(lon,lat):
    return VIEWS[0]
def rings(path, v, filt=None):
    r=shapefile.Reader(path); b=v['lonlat']
    for sr in r.iterShapeRecords():
        if filt and not filt(sr.record): continue
        s=sr.shape
        if s.bbox[2]<b[0] or s.bbox[0]>b[2] or s.bbox[3]<b[1] or s.bbox[1]>b[3]: continue
        pts=np.array(s.points); parts=list(s.parts)+[len(pts)]
        for a,c in zip(parts[:-1],parts[1:]):
            ring=pts[a:c]
            if len(ring)<3: continue
            px,py=topx(v,ring[:,0],ring[:,1]); yield list(zip(px,py))
