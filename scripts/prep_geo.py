import json, os, math, sys
from shapely.geometry import shape, mapping, Polygon, MultiPolygon, LineString, MultiLineString, GeometryCollection
from shapely.ops import unary_union
from shapely import prepared

OUT = 'site/data'
os.makedirs(OUT, exist_ok=True)

def q(v):  # 1e-3 degree integer
    return int(round(v * 1000))

def enc(coords):
    """delta-encode a ring/line into flat ints [x0,y0,dx,dy,...]; drop consecutive duplicates"""
    pts = []
    for x, y in coords:
        p = (q(x), q(y))
        if not pts or p != pts[-1]:
            pts.append(p)
    if len(pts) < 2:
        return None
    flat = [pts[0][0], pts[0][1]]
    for i in range(1, len(pts)):
        flat.append(pts[i][0] - pts[i - 1][0]); flat.append(pts[i][1] - pts[i - 1][1])
    return flat

def polys(g):
    if g.is_empty: return []
    if g.geom_type == 'Polygon': return [g]
    if g.geom_type in ('MultiPolygon', 'GeometryCollection'):
        out = []
        for x in g.geoms: out += polys(x)
        return out
    return []

def lines(g):
    if g.is_empty: return []
    if g.geom_type == 'LineString': return [g]
    if g.geom_type in ('MultiLineString', 'GeometryCollection'):
        out = []
        for x in g.geoms: out += lines(x)
        return out
    return []

def rings_of(g):
    out = []
    for p in polys(g):
        for r in [p.exterior] + list(p.interiors):
            e = enc(r.coords)
            if e and len(e) >= 8: out.append(e)
    return out

def dump(name, obj):
    s = json.dumps(obj, separators=(',', ':'))
    open(f'{OUT}/{name}.json', 'w').write(s)
    print(f'{name}.json {len(s)/1024:.0f} KB')

# ---------- districts -> state outlines + district lines ----------
d = json.load(open('geo/india-maps-data/geojson/india.geojson'))
by = {}
dist_geoms = []
for f in d['features']:
    g = shape(f['geometry']).buffer(0)
    by.setdefault(f['properties']['st_nm'], []).append(g)
    dist_geoms.append((f['properties']['st_nm'], f['properties'].get('district'), g))

states = []
state_geom = {}
for st, gs in by.items():
    u = unary_union([g.buffer(0.003) for g in gs]).buffer(-0.003)
    state_geom[st] = u
    s = u.simplify(0.001, preserve_topology=True)
    if s.is_empty: s = u
    ps = polys(s)
    big = [p for p in ps if p.area > 0.00015] or [max(ps, key=lambda p: p.area)]
    states.append({'n': st, 'r': rings_of(MultiPolygon(big))})
dump('states', states)

india = unary_union(list(state_geom.values())).buffer(0.01)
india_p = prepared.prep(india)

dist = []
for st, nm, g in dist_geoms:
    s = g.simplify(0.0015, preserve_topology=True)
    if s.is_empty: continue
    dist += rings_of(s)
dump('districts', dist)

# ---------- taluks ----------
t = json.load(open('geo/india/taluk/india_taluk.geojson'))
tal = []
for f in t['features']:
    try:
        g = shape(f['geometry']).buffer(0)
    except Exception:
        continue
    s = g.simplify(0.002, preserve_topology=True)
    if s.is_empty: continue
    tal += rings_of(s)
dump('taluks', tal)

# ---------- Natural Earth (clipped to India's official outline) ----------
def zoom_to_k(z):
    return round(max(1.0, 2 ** ((z or 5) - 4.9)), 2)

roads = []
r = json.load(open('ne/ne_10m_roads.geojson'))
for f in r['features']:
    b = f.get('bbox')
    if not b or not (b[2] > 67 and b[0] < 98 and b[3] > 6 and b[1] < 38): continue
    g = shape(f['geometry'])
    if not india_p.intersects(g): continue
    g = g.intersection(india)
    p = f['properties']
    kind = 1 if (p.get('type') or '').startswith('Major') else (2 if 'Secondary' in (p.get('type') or '') else 3)
    if p.get('featurecla') == 'Ferry': continue
    for ln in lines(g.simplify(0.0015)):
        e = enc(ln.coords)
        if e: roads.append([kind, zoom_to_k(p.get('min_zoom')), e])
dump('roads', roads)

rivers = []
r = json.load(open('ne/ne_10m_rivers_lake_centerlines.geojson'))
for f in r['features']:
    g = shape(f['geometry'])
    if not india_p.intersects(g): continue
    g = g.intersection(india)
    mz = f['properties'].get('min_zoom')
    for ln in lines(g.simplify(0.0015)):
        e = enc(ln.coords)
        if e: rivers.append([zoom_to_k(mz), e])
dump('rivers', rivers)

lakes = []
r = json.load(open('ne/ne_10m_lakes.geojson'))
for f in r['features']:
    g = shape(f['geometry']).buffer(0)
    if not india_p.intersects(g): continue
    g = g.intersection(india)
    mz = f['properties'].get('min_zoom')
    for rg in rings_of(g.simplify(0.0015)):
        lakes.append([zoom_to_k(mz), rg])
dump('lakes', lakes)

urban = []
r = json.load(open('ne/ne_10m_urban_areas.geojson'))
for f in r['features']:
    b = f.get('bbox')
    if not b or not (b[2] > 67 and b[0] < 98 and b[3] > 6 and b[1] < 38): continue
    g = shape(f['geometry']).buffer(0)
    if not india_p.intersects(g): continue
    g = g.intersection(india)
    mz = f['properties'].get('min_zoom')
    for rg in rings_of(g.simplify(0.0008)):
        urban.append([zoom_to_k(mz), rg])
dump('urban', urban)
print('rings: districts', len(dist), 'taluks', len(tal), 'roads', len(roads), 'rivers', len(rivers), 'lakes', len(lakes), 'urban', len(urban))
