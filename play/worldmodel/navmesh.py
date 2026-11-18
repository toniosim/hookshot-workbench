"""The game's nav meshes as plain data: vertices, polygons, polygon neighbours, per-polygon data words.

Sources (game 1.1.1 romfs):
- Phive/NavMesh/<banc>.Nin_Ounce_NVN2.bphnm.zs: one hkaiNavMesh per area, in the area's own coordinates (metres,
  y up).
- Phive/StitchedNavMesh/<scene>/X<i>_Z<j>.Nin_Ounce_NVN2.bphnm.zs: a square grid of tiles of TILE metres whose
  vertices are local to the tile's centre in x and z (y is absolute) and whose border edges are not linked (their
  oppositeSectionId is -1): `stitched()` moves them into place and links border edges that coincide.

Cache format (`nav/<banc>.json.gz`): {"verts": [x, y, z, ...], "faces": [[v0, v1, ...], ...] (polygon vertex
indices, counter-clockwise seen from above as Havok stores them), "adj": [[opposite face or -1 per edge], ...],
"fdata": [[word0, word1], ...], "erosion": radius, "source": [romfs paths]}.
"""
import gzip
import json
import math
import re
import struct

from . import havok

TILE = 250.0
NAV = 'Phive/NavMesh/{}.Nin_Ounce_NVN2.bphnm.zs'
STITCHED = 'Phive/StitchedNavMesh/{}/'


def _arr(t, a, fmt, size):
    _, idx, cnt = a
    if not idx:
        return []
    _t, raw, c = t.item_raw(idx)
    return [struct.unpack_from(fmt, raw, size * i) for i in range(c)]


def read_bphnm(raw):
    """(verts [(x, y, z)], faces [[v...]], adj [[f...]], fdata [[w0, w1]], erosion) of one .bphnm (after zstd)."""
    t = havok.Tagfile(raw)
    root = t.item(1)[0]
    nv = t.item(root['namedVariants'][1])
    idx = [v['variant'][1] for v in nv if v['className'] == 'hkaiNavMesh']
    if not idx:
        raise ValueError('no hkaiNavMesh in file')
    nm = t.item(idx[0])[0]
    verts = [(v[0], v[1], v[2]) for v in _arr(t, nm['vertices'], '<4f', 16)]
    faces_raw = _arr(t, nm['faces'], '<iihh', 12)
    edges = _arr(t, nm['edges'], '<iiiiiBBH', 24)
    stride = nm['faceDataStriding']
    fd = [x[0] for x in _arr(t, nm['faceData'], '<i', 4)]
    faces, adj, fdata = [], [], []
    for i, (s, _su, n, _nu) in enumerate(faces_raw):
        faces.append([edges[s + k][0] for k in range(n)])
        adj.append([edges[s + k][4] for k in range(n)])
        fdata.append(fd[i * stride:(i + 1) * stride] if stride else [])
    return verts, faces, adj, fdata, nm['erosionRadius']


def single(load, banc, name=None):
    p = NAV.format(name or banc)
    v, f, a, d, er = read_bphnm(load(p))
    return {'verts': [c for xyz in v for c in xyz], 'faces': f, 'adj': a, 'fdata': d, 'erosion': er, 'portals': [],
            'source': [p]}


def stitched(load, files, scene):
    """Merge the tiles of a stitched nav mesh into one mesh in area coordinates."""
    prefix = STITCHED.format(scene)
    tiles = []
    for p in sorted(files):
        if not p.startswith(prefix):
            continue
        m = re.match(r'X(\d+)_Z(\d+)\.', p[len(prefix):])
        if m:
            tiles.append((int(m.group(1)), int(m.group(2)), p))
    if not tiles:
        raise KeyError(prefix)
    n = int(math.isqrt(len(tiles)))
    verts, faces, adj, fdata, er, src = [], [], [], [], 0.0, []
    for i, j, p in tiles:
        v, f, a, d, er_t = read_bphnm(load(p))
        if len(f) <= 1 and all(abs(y) < 1.5 for _, y, _ in v):
            continue                      # an empty tile holds one placeholder quad at y 0
        ox, oz = (i - n / 2 + 0.5) * TILE, (j - n / 2 + 0.5) * TILE
        vb, fb = len(verts), len(faces)
        verts += [(x + ox, y, z + oz) for x, y, z in v]
        faces += [[vb + k for k in poly] for poly in f]
        adj += [[fb + o if o >= 0 else -1 for o in row] for row in a]
        fdata += d
        er = er_t
        src.append(p)
    portals = _link_borders(verts, faces, adj)
    return {'verts': [c for xyz in verts for c in xyz], 'faces': faces, 'adj': adj, 'fdata': fdata, 'erosion': er,
            'portals': portals, 'source': src}


def _link_borders(verts, faces, adj, tol=0.05):
    """Portals across tile seams: open edges of two tiles that lie on the same seam line and overlap along it.

    The two sides of a seam are split differently (T-junctions), so edges are matched by overlap, not by vertex. An
    edge may face several polygons on the other side, hence portals, not adjacency: returns [[fa, fb, x1, y1, z1,
    x2, y2, z2], ...] with the overlapping piece as the portal."""
    lines = {}
    for fi, poly in enumerate(faces):
        for k in range(len(poly)):
            if adj[fi][k] >= 0:
                continue
            xa, ya, za = verts[poly[k]]
            xb, yb, zb = verts[poly[(k + 1) % len(poly)]]
            if abs(xa - xb) < tol and abs(xa / TILE - round(xa / TILE)) < 1e-4:
                axis, c, lo, hi = 'x', round(xa / TILE), (za, ya), (zb, yb)
            elif abs(za - zb) < tol and abs(za / TILE - round(za / TILE)) < 1e-4:
                axis, c, lo, hi = 'z', round(za / TILE), (xa, ya), (xb, yb)
            else:
                continue
            if lo[0] > hi[0]:
                lo, hi = hi, lo
            # which side of the seam the polygon lies on: its centroid
            cen = sum(verts[v][0 if axis == 'x' else 2] for v in poly) / len(poly)
            side = cen > c * TILE
            lines.setdefault((axis, c), []).append((lo, hi, side, fi))
    portals = []
    for (axis, c), es in lines.items():
        a_side = sorted((e for e in es if not e[2]), key=lambda e: e[0][0])
        b_side = sorted((e for e in es if e[2]), key=lambda e: e[0][0])
        j0 = 0
        for lo, hi, _s, fa in a_side:
            while j0 < len(b_side) and b_side[j0][1][0] <= lo[0]:
                j0 += 1
            j = j0
            while j < len(b_side) and b_side[j][0][0] < hi[0]:
                blo, bhi, _sb, fb = b_side[j]
                s, e = max(lo[0], blo[0]), min(hi[0], bhi[0])
                if e - s > 0.05:
                    def y_at(p, q, t):
                        return p[1] + (q[1] - p[1]) * ((t - p[0]) / (q[0] - p[0]) if q[0] != p[0] else 0)
                    ys, ye = y_at(lo, hi, s), y_at(lo, hi, e)
                    if abs(ys - y_at(blo, bhi, s)) < 1.0 and abs(ye - y_at(blo, bhi, e)) < 1.0:
                        v = c * TILE
                        p1 = (v, ys, s) if axis == 'x' else (s, ys, v)
                        p2 = (v, ye, e) if axis == 'x' else (e, ye, v)
                        portals.append([fa, fb, *p1, *p2])
                j += 1
    return portals


def save(nav, path):
    data = dict(nav)
    data['verts'] = [round(c, 3) for c in data['verts']]
    with gzip.open(path, 'wt') as f:
        json.dump(data, f, separators=(',', ':'))


def load(path):
    with gzip.open(path, 'rt') as f:
        return json.load(f)
