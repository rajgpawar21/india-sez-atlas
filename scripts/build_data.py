import json,re,sys
from shapely.geometry import shape, Point
from shapely.ops import unary_union
sys.path.insert(0,'.')
from coords import C, AREA
rows=json.load(open('rows.json'))

# ---------- classification (from the PDF's own "Type of SEZ" text) ----------
CATS=["IT / ITES & software","Multi-product, multi-sector & port","Pharma, biotech & chemicals",
"Engineering, aerospace & auto","Electronics & semiconductors","Textile, apparel & footwear",
"Energy, metals & minerals","Gems, food & other niche"]
OVR={172:4,173:4}
def cat(r):
    sl=r['sl']; t=r['typ'].lower()
    if sl in OVR: return OVR[sl]
    if re.search(r'semi-?conductor',t): return 4
    if 'multi' in t or 'ftwz' in t or 'port based' in t: return 1
    if re.search(r'pharma|biotech|bio-tech|chemical',t): return 2
    if re.search(r'textile|apparel|footwear|leather',t): return 5
    if re.search(r'gems|handicraft|food|agro',t): return 7
    if re.search(r'solar|non-conventional|power|alumin|mineral|granite',t): return 6
    if re.search(r'\bit\b|ites|software|animation',t): return 0
    if 'electronic' in t: return 4
    if re.search(r'engineer|aerospace|automobile|building|transport|heavy|precision|hi-tech|aviation',t): return 3
    raise Exception(('unclassified',sl,t))
for r in rows: r['cat']=cat(r)
from collections import Counter
print(sorted(Counter(r['cat'] for r in rows).items()))

# ---------- check 1: every serial has coordinates ----------
missing=[r['sl'] for r in rows if r['sl'] not in C]
extra=[k for k in C if k not in {r['sl'] for r in rows}]
print('missing coords',missing,'extra',extra,len(C))

# ---------- check 2: each point lies inside its own state ----------
d=json.load(open('geo/india-maps-data/geojson/india.geojson'))
by={}
for f in d['features']: by.setdefault(f['properties']['st_nm'],[]).append(shape(f['geometry']).buffer(0))
U={k:unary_union(v) for k,v in by.items()}
nm={'ANDHRA PRADESH':'Andhra Pradesh','CHANDIGARH':'Chandigarh','CHHATTISGARH':'Chhattisgarh','GUJARAT':'Gujarat','HARYANA':'Haryana',
'JHARKHAND':'Jharkhand','KERALA':'Kerala','KARNATAKA':'Karnataka','MAHARASHTRA':'Maharashtra','MADHYA PRADESH':'Madhya Pradesh',
'ODISHA':'Odisha','PUNJAB':'Punjab','RAJASTHAN':'Rajasthan','TAMIL NADU':'Tamil Nadu','TELANGANA':'Telangana',
'UTTAR PRADESH':'Uttar Pradesh','WEST BENGAL':'West Bengal'}
bad=[]
for r in rows:
    lat,lon=C[r['sl']]; p=Point(lon,lat); g=U[nm[r['state']]]
    if not g.contains(p):
        dist=g.distance(p)
        bad.append((r['sl'],r['state'],r['dev'][:30],round(dist,3)))
print('outside own state polygon:',len(bad)); [print(b) for b in bad]

# ---------- check 3: independent text extraction (pdftotext -layout) ----------
txt=open('out.txt').read().splitlines()
found={}
for ln in txt:
    m=re.match(r'^\s*(\d{1,3})\s+(\d{1,2})\s+(\S.*?)(?:\s{2,}|$)',ln)
    if m and 1<=int(m.group(1))<=277: found[int(m.group(1))]=(int(m.group(2)),m.group(3))
print('layout-extract serials found:',len(found))
mis=[]
norm=lambda s:re.sub(r'[^a-z0-9]','',s.lower())
for r in rows:
    f=found.get(r['sl'])
    if not f or f[0]!=r['ssl'] or not norm(r['dev']).startswith(norm(f[1])[:12]): mis.append((r['sl'],f,r['dev'][:30]))
print('mismatches vs second extraction:',len(mis)); [print(m) for m in mis[:20]]
json.dump({'bad':bad,'mis':mis},open('checks.json','w'))
out=[[r['sl'],r['ssl'],r['state'].title(),r['dev'],r['loc'],r['typ'],r['cat'],C[r['sl']][0],C[r['sl']][1],1 if r['sl'] in AREA else 0] for r in rows]
json.dump({'cats':CATS,'rows':out},open('data.json','w'),ensure_ascii=False,separators=(',',':'))
