import json, gzip, re, sys, math, collections
import numpy as np
from shapely.geometry import shape, Point
from shapely.ops import unary_union
from shapely import prepared
sys.path.insert(0, '.')
from coords import C as SEZ
from curated import curated

TOL = float(__import__('os').environ.get('TOL','4'))
def norm(s):
    return re.sub(r'[^a-z0-9]', '', s.lower())

# ---------- state / district geometry ----------
d = json.load(open('geo/india-maps-data/geojson/india.geojson'))
by_state, by_dist = {}, {}
for f in d['features']:
    g = shape(f['geometry']).buffer(0)
    by_state.setdefault(f['properties']['st_nm'], []).append(g)
    by_dist.setdefault(norm(f['properties'].get('district') or ''), []).append(g)
STATE = {k: unary_union(v).buffer(0.01) for k, v in by_state.items()}
STATE_P = {k: prepared.prep(v) for k, v in STATE.items()}
DIST = {k: prepared.prep(unary_union(v).buffer(0.04)) for k, v in by_dist.items()}
INDIA_P = prepared.prep(unary_union(list(STATE.values())))
ALIAS = {'orissa': 'odisha', 'uttaranchal': 'uttarakhand', 'dadraandnagarhaveli': 'dadraandnagarhavelianddamananddiu', 'damananddiu': 'dadraandnagarhavelianddamananddiu',
         'andamannicobarislands': 'andamanandnicobarislands', 'jammukashmir': 'jammuandkashmir', 'jammuandkashmir': 'jammuandkashmir', 'pondicherry': 'puducherry'}
SNORM = {norm(k): k for k in STATE}
def state_key(s):
    n = norm(s); n = ALIAS.get(n, n)
    return SNORM.get(n)

# ---------- SEZ positions (km grid) ----------
sez = np.array([SEZ[k] for k in sorted(SEZ)])
def km_to_sez(lat, lon):
    dl = (sez[:, 0] - lat) * 111.0
    dn = (sez[:, 1] - lon) * 111.0 * math.cos(math.radians(lat))
    return np.sqrt(dl * dl + dn * dn).min()

def hav(a, b, c, d_):
    p = math.pi / 180
    x = (d_ - b) * p * math.cos((a + c) * p / 2); y = (c - a) * p
    return 6371 * math.sqrt(x * x + y * y)

# ---------- GeoNames ----------
gn = json.load(open('geonames_in.json'))
def gn_k(pop):
    if pop >= 3e6: return 1.0
    if pop >= 1e6: return 1.5
    if pop >= 4e5: return 2.3
    if pop >= 1.5e5: return 3.6
    if pop >= 5e4: return 6.0
    if pop >= 2e4: return 9.0
    return 12.0
places = []   # [name, lat, lon, minK, kind, pop]
gn_by_name = collections.defaultdict(list)
for n, la, lo, pop, adm in gn:
    if not (6 < la < 38 and 67 < lo < 98): continue
    places.append([n, la, lo, gn_k(pop or 0), 'g', pop or 0])
    gn_by_name[norm(n)].append((la, lo))
print('geonames', len(places))

# ---------- India Post offices (filtered) ----------
rows = json.load(gzip.open('places/node_modules/india-pincode/data/pincodes.json.gz'))
def clean(name):
    s = re.sub(r'\s+', ' ', name).strip()
    s = re.sub(r'\b(S\.?\s?O|B\.?\s?O|H\.?\s?O|P\.?\s?O|G\.?\s?P\.?\s?O)\.?\s*$', '', s, flags=re.I).strip(' .,-')
    s = re.sub(r'\s*\(.*?\)\s*$', lambda m: m.group(0) if len(m.group(0)) < 22 else '', s).strip()
    if s.isupper() and len(s) > 3: s = s.title()
    return s
BAD = re.compile(r'\b(ndc|ie|foreign|camp|rms|tso|mdg|bpc|ho|hpo|gpo|collectorate|cantt?|pmg|dak|sorting|parcel|mail|ordinary|rural|extension counter|bazar po|court|secretariat)\b|\d{3,}', re.I)
valid = []
for r in rows:
    a, n = r.get('a'), r.get('n')
    if not isinstance(a, (int, float)) or not isinstance(n, (int, float)): continue
    if not (6 < a < 38 and 67 < n < 98): continue
    nm = clean(r['o'])
    if len(nm) < 3 or BAD.search(nm): continue
    valid.append((r, nm, a, n))
print('valid coords + names', len(valid))

# pincode median consistency
grp = collections.defaultdict(list)
for r, nm, a, n in valid: grp[r['p']].append((a, n))
med = {p: (float(np.median([x[0] for x in v])), float(np.median([x[1] for x in v])), len(v)) for p, v in grp.items()}

keep = []; drop = collections.Counter()
for r, nm, a, n in valid:
    t = r['t']
    # BO (village branch offices) only near SEZs
    if t == 'BO' and km_to_sez(a, n) > 30: drop['bo-far'] += 1; continue
    sk = state_key(r['s'] or '')
    if sk:
        if not STATE_P[sk].contains(Point(n, a)): drop['wrong-state'] += 1; continue
    elif not INDIA_P.contains(Point(n, a)): drop['outside'] += 1; continue
    dn = norm(r['i'] or '')
    if dn in DIST and not DIST[dn].contains(Point(n, a)): drop['wrong-district'] += 1; continue
    ma, mo, cnt = med[r['p']]
    if cnt >= 2 and hav(a, n, ma, mo) > TOL: drop['pincode-outlier'] += 1; continue
    # GeoNames already has this name nearby (accurate coordinates win)
    g = gn_by_name.get(norm(nm))
    if g and any(hav(a, n, x, y) < 60 for x, y in g): drop['in-geonames'] += 1; continue
    keep.append((r, nm, a, n))
print('dropped', dict(drop), 'kept', len(keep))

# ---------- curated (accurate) ----------
cur = curated()
cur_idx = collections.defaultdict(list)
for nm, la, lo, minor in cur: cur_idx[norm(nm)].append((la, lo))

# measure India Post accuracy against curated positions (same name within 25 km)
errs = []
for r, nm, a, n in keep:
    for la, lo in cur_idx.get(norm(nm), []):
        dd = hav(a, n, la, lo)
        if dd < 25: errs.append((dd, nm, r['t']))
errs.sort()
if errs:
    ds = [e[0] for e in errs]
    print('largest disagreements:',[(round(e[0],1),e[1],e[2]) for e in errs[-10:]])
    print('India Post vs curated, n=%d  median %.1f km  p90 %.1f km  max %.1f km' % (len(ds), np.median(ds), np.percentile(ds, 90), max(ds)))

seen = collections.defaultdict(list)
def near_seen(nm, a, n, km):
    return any(hav(a, n, x, y) < km for x, y in seen[norm(nm)])
for nm, la, lo, minor in cur:
    places.append([nm, la, lo, 18.0 if minor else 11.0, 'c', 0]); seen[norm(nm)].append((la, lo))
cg_seen = collections.defaultdict(list)
for g in list(places):
    if g[4] in ('g', 'c'): cg_seen[norm(g[0])].append((g[1], g[2]))
for g in list(places):
    if g[4] == 'g': seen[norm(g[0])].append((g[1], g[2]))
ncur = 0
for r, nm, a, n in sorted(keep, key=lambda x: {'HO': 0, 'PO': 1, 'SO': 1}.get(x[0]['t'], 2)):
    if near_seen(nm, a, n, 6): continue
    if any(hav(a, n, x, y) < 40 for x, y in cg_seen.get(norm(nm), [])): continue
    t = r['t']
    k = 8.0 if t == 'HO' else 15.0 if t == 'PO' else 26.0
    places.append([nm, a, n, k, t.lower(), 0]); seen[norm(nm)].append((a, n))
    ncur += 1
print('india-post places added', ncur, 'total places', len(places))
print(collections.Counter(p[4] for p in places))

# district and state names (area labels at mid zoom)
dist_pts = {}
for f in d['features']:
    nm = f['properties'].get('district')
    if not nm: continue
    g = shape(f['geometry']).buffer(0)
    dist_pts.setdefault((nm, f['properties']['st_nm']), []).append(g)
extra = []
for (nm, st), gs in dist_pts.items():
    pt = unary_union(gs).representative_point()
    extra.append([nm.title() if nm.isupper() else nm, pt.y, pt.x, 4.5, 'd', 0, 16.0])
for st, gs in by_state.items():
    u = unary_union(gs)
    big = max(u.geoms, key=lambda x: x.area) if u.geom_type == 'MultiPolygon' else u
    pt = big.representative_point()
    extra.append([st, pt.y, pt.x, 1.0, 's', 0, 4.6])
print('area labels', len(extra))
places += extra
# sort by priority (low minK first, bigger population first)
places.sort(key=lambda p: (p[3], -p[5]))
out = [[p[0], round(p[2], 4), round(p[1], 4), p[3], p[4]] + ([p[6]] if len(p) > 6 else []) for p in places]
s = json.dumps(out, ensure_ascii=False, separators=(',', ':'))
open('site/data/places.json', 'w').write(s)
print('places.json %.0f KB' % (len(s) / 1024))

# coverage of SEZ clusters: SEZs with a named place within 5 km
cov = 0
pl = np.array([[p[1], p[2]] for p in places])
for sl in sorted(SEZ):
    la, lo = SEZ[sl]
    dl = (pl[:, 0] - la) * 111.0; dn = (pl[:, 1] - lo) * 111.0 * math.cos(math.radians(la))
    if np.sqrt(dl * dl + dn * dn).min() <= 5: cov += 1
print('SEZs with a named place within 5 km:', cov, 'of', len(SEZ))
