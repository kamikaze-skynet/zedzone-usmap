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
land=np.zeros((H,W),bool); usa=np.zeros((H,W),bool); river=np.zeros((H,W),bool)
elev=np.zeros((H,W),np.float32); lc=np.zeros((H,W),np.uint8)
NL={(71,107,160):11,(209,221,249):12,(221,201,201):21,(216,147,130):22,(237,0,0):23,(170,0,0):24,(178,173,163):31,
    (104,170,99):41,(28,99,48):42,(181,201,142):43,(204,186,124):52,(226,226,193):71,(219,216,61):81,(170,112,40):82,
    (186,216,234):90,(112,163,186):95,(165,165,165):31,(175,150,60):51,(209,209,130):72,(164,204,81):73,(130,186,157):74,(215,194,135):52,(176,151,61):51,(84,117,168):11,(35,107,61):42,(189,186,171):31,(217,232,255):12,(194,225,243):90,(194,212,156):43,(112,179,107):41,(125,171,194):95,(238,238,204):71}
for v in VIEWS:
    bx0,by0,bx1,by1=v['box']; sl=(slice(by0,by1),slice(bx0,bx1))
    def ras(path,filt=None):
        im=Image.new('L',(W,H),0); d=ImageDraw.Draw(im)
        for ring in rings(path,v,filt): d.polygon(ring,fill=255)
        return np.array(im)[sl]>0
    L=ras(D+'ne_10m_land/ne_10m_land.shp'); K=ras(D+'ne_10m_lakes/ne_10m_lakes.shp')
    S=ras(D+'ne_10m_admin_1_states_provinces_lakes/ne_10m_admin_1_states_provinces_lakes.shp',lambda r: r['adm0_a3']=='USA' and v['states'](r['name']))
    L&=~K
    if v['name']!='L48': L&=S        # insets show only the state itself
    land[sl]=L; usa[sl]=S
    rv=Image.new('L',(W,H),0); d=ImageDraw.Draw(rv)
    r=shapefile.Reader(D+'ne_10m_rivers_lake_centerlines/ne_10m_rivers_lake_centerlines.shp'); b=v['lonlat']
    for sr in r.iterShapeRecords():
        if sr.record['scalerank']>5 or sr.record['featurecla']!='River': continue
        pts=np.array(sr.shape.points)
        if pts[:,0].max()<b[0] or pts[:,0].min()>b[2] or pts[:,1].max()<b[1] or pts[:,1].min()>b[3]: continue
        parts=list(sr.shape.parts)+[len(pts)]
        for a,c in zip(parts[:-1],parts[1:]):
            px,py=topx(v,pts[a:c,0],pts[a:c,1]); d.line(list(zip(px,py)),fill=255,width=2 if sr.record['scalerank']<=3 else 1)
    river[sl]=(np.array(rv)[sl]>0)&(S if v['name']!='L48' else True)
    # elevation
    nc=netCDF4.Dataset(D+v['etopo']); lat=nc['latitude'][:]; lon=nc['longitude'][:]; z=np.array(nc['altitude'][:],dtype=np.float32)
    x0,x1,y0,y1=v['bbox']; w,h=v['full']; bw,bh=bx1-bx0,by1-by0
    gx=x0+(np.arange(bw)+.5)/w*(x1-x0); gy=y1-(np.arange(bh)+.5)/h*(y1-y0)
    GX,GY=np.meshgrid(gx,gy); LON,LAT=v['inv'].transform(GX,GY)
    fi=np.clip((LAT-lat[0])/(lat[1]-lat[0]),0,len(lat)-1.001); fj=np.clip((LON-lon[0])/(lon[1]-lon[0]),0,len(lon)-1.001)
    i0=fi.astype(int); j0=fj.astype(int); di=fi-i0; dj=fj-j0
    elev[sl]=z[i0,j0]*(1-di)*(1-dj)+z[i0+1,j0]*di*(1-dj)+z[i0,j0+1]*(1-di)*dj+z[i0+1,j0+1]*di*dj
    # land cover via MRLC WMS (public domain NLCD), in this view's projection
    url=('https://www.mrlc.gov/geoserver/mrlc_display/wms?service=WMS&version=1.1.1&request=GetMap&layers=%s&styles=&bbox=%d,%d,%d,%d&srs=EPSG:%d&width=%d&height=%d&format=image/png'
         %(v['nlcd'],x0,y0,x1,y1,v['crs'],min(bw,4096),min(bh,4096)))
    try:
        img=Image.open(io.BytesIO(urllib.request.urlopen(url,timeout=180).read())).convert('RGB').resize((bw,bh),Image.NEAREST)
        a=np.array(img).astype(np.int32); key=a[...,0]*65536+a[...,1]*256+a[...,2]; out=np.zeros((bh,bw),np.uint8)
        pal=np.array(list(NL.keys())); vals=list(NL.values())
        for k in np.unique(key):
            c=np.array([k>>16,(k>>8)&255,k&255]); dd=((pal-c)**2).sum(1); j=dd.argmin()
            if dd[j]<=900: out[key==k]=vals[j]
        lc[sl]=out; print(v['name'],'nlcd classes',np.unique(out))
    except Exception as e: print(v['name'],'nlcd failed',e)
    print(v['name'],'box',v['box'])
json.dump([dict(name=v['name'],box=v['box']) for v in VIEWS],open(OUT+'views.json','w'))
np.savez_compressed(OUT+'raster.npz',land=land,usa=usa,river=river,elev=elev,lc=lc)
print('raster done',W,H,'land%',land.mean(),'us%',usa.mean())
