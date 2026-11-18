"""A nav mesh loaded for queries: point location, components, and the links between components that the mesh
itself does not hold (drops off ledges, gaps, ledges up, placed climbables and crawl spaces). Standard library only.

Coordinates are the game's (metres, y up), the same as the pilot's step lines and route steps (x z).
"""
import collections
import math

from . import navmesh, paths

CELL = 8.0


def cross2(ox, oz, ax, az, bx, bz):
    return (ax - ox) * (bz - oz) - (az - oz) * (bx - ox)


def seg_closest(px, pz, ax, az, bx, bz):
    dx, dz = bx - ax, bz - az
    L = dx * dx + dz * dz
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((px - ax) * dx + (pz - az) * dz) / L))
    cx, cz = ax + t * dx, az + t * dz
    return math.hypot(px - cx, pz - cz), cx, cz, t


class Area:
    def __init__(self, banc, nav=None, path=None):
        self.banc = banc
        if nav is None:
            path = path or paths.data_dir() / 'nav' / f'{banc}.json.gz'
            nav = navmesh.load(path)
        self.nav = nav
        vs = nav['verts']
        self.V = [(vs[i], vs[i + 1], vs[i + 2]) for i in range(0, len(vs), 3)]
        self.F = nav['faces']
        self.adj = nav['adj']
        self.erosion = nav.get('erosion', 0.4)
        self.fdata = nav.get('fdata', [])
        self.xlinks = nav.get('xlinks', [])
        # neighbours: (face, portal p1, portal p2) from shared edges and tile-seam portals
        self.nbr = [[] for _ in self.F]
        for f, poly in enumerate(self.F):
            n = len(poly)
            for k in range(n):
                o = self.adj[f][k]
                if o >= 0:
                    self.nbr[f].append((o, self.V[poly[k]], self.V[poly[(k + 1) % n]]))
        for p in nav.get('portals', []):
            a, b, p1, p2 = p[0], p[1], tuple(p[2:5]), tuple(p[5:8])
            self.nbr[a].append((b, p1, p2))
            self.nbr[b].append((a, p1, p2))
        self.cen = []
        for poly in self.F:
            n = len(poly)
            self.cen.append((sum(self.V[i][0] for i in poly) / n, sum(self.V[i][1] for i in poly) / n,
                             sum(self.V[i][2] for i in poly) / n))
        self.grid = collections.defaultdict(list)
        for f, poly in enumerate(self.F):
            xs = [self.V[i][0] for i in poly]
            zs = [self.V[i][2] for i in poly]
            for cx in range(int(math.floor(min(xs) / CELL)), int(math.floor(max(xs) / CELL)) + 1):
                for cz in range(int(math.floor(min(zs) / CELL)), int(math.floor(max(zs) / CELL)) + 1):
                    self.grid[(cx, cz)].append(f)
        self.comp, self.comp_size = self._components()

    def _components(self):
        comp = [-1] * len(self.F)
        sizes = []
        for s in range(len(self.F)):
            if comp[s] != -1:
                continue
            c = len(sizes)
            comp[s] = c
            st, n = [s], 0
            while st:
                f = st.pop()
                n += 1
                for o, _p, _q in self.nbr[f]:
                    if comp[o] == -1:
                        comp[o] = c
                        st.append(o)
            sizes.append(n)
        return comp, sizes

    # ---------------------------------------------------------------------------------------------- point queries
    def inside(self, f, x, z):
        poly = self.F[f]
        inside = False
        n = len(poly)
        for i in range(n):
            x1, _, z1 = self.V[poly[i]]
            x2, _, z2 = self.V[poly[(i + 1) % n]]
            if (z1 > z) != (z2 > z):
                if x < x1 + (z - z1) * (x2 - x1) / (z2 - z1):
                    inside = not inside
        return inside

    def height(self, f, x, z):
        """y of face f at (x, z): the polygon's best-fit plane (Newell's normal through its centroid), clamped to the
        polygon's own heights. Thin polygons make a plane through three vertices useless."""
        poly = self.F[f]
        n = len(poly)
        nx = ny = nz = 0.0
        for i in range(n):
            xi, yi, zi = self.V[poly[i]]
            xj, yj, zj = self.V[poly[(i + 1) % n]]
            nx += (yi - yj) * (zi + zj)
            ny += (zi - zj) * (xi + xj)
            nz += (xi - xj) * (yi + yj)
        cx, cy, cz = self.cen[f]
        ys = [self.V[i][1] for i in poly]
        if abs(ny) < 1e-9:
            return cy
        y = cy - (nx * (x - cx) + nz * (z - cz)) / ny
        return max(min(ys), min(max(ys), y))

    def faces_at(self, x, z):
        return [f for f in self.grid.get((int(math.floor(x / CELL)), int(math.floor(z / CELL))), ()) if self.inside(f, x, z)]

    def nearest(self, x, z, y=None, radius=3.0, dy=3.0, comp=None):
        """(distance, face, (x, y, z) on the face) of the closest mesh point within radius, or None."""
        best = None
        r = int(math.ceil(radius / CELL))
        cx, cz = int(math.floor(x / CELL)), int(math.floor(z / CELL))
        seen = set()
        for gx in range(cx - r, cx + r + 1):
            for gz in range(cz - r, cz + r + 1):
                for f in self.grid.get((gx, gz), ()):
                    if f in seen:
                        continue
                    seen.add(f)
                    if comp is not None and self.comp[f] != comp:
                        continue
                    if self.inside(f, x, z):
                        d, px, pz = 0.0, x, z
                    else:
                        poly = self.F[f]
                        n = len(poly)
                        d, px, pz = 1e9, x, z
                        for k in range(n):
                            a, b = self.V[poly[k]], self.V[poly[(k + 1) % n]]
                            dd, qx, qz, _t = seg_closest(x, z, a[0], a[2], b[0], b[2])
                            if dd < d:
                                d, px, pz = dd, qx, qz
                    if d > radius:
                        continue
                    py = self.height(f, px, pz)
                    if y is not None and abs(py - y) > dy:
                        continue
                    key = (d + (abs(py - y) * 0.25 if y is not None else 0.0))
                    if best is None or key < best[0]:
                        best = (key, f, (px, py, pz), d)
        if best is None:
            return None
        return best[3], best[1], best[2]

    def locate(self, x, z, y=None, snap=2.0, prefer_comp=None):
        """(face, point on mesh, distance) for a position, choosing the floor by y when several overlap."""
        cands = self.faces_at(x, z)
        if cands:
            def score(f):
                s = 0.0
                if y is not None:
                    s += abs(self.height(f, x, z) - y)
                    if self.height(f, x, z) - y > 1.0:      # a floor above the feet is unlikely to be the one stood on
                        s += 5.0
                if prefer_comp is not None and self.comp[f] != prefer_comp:
                    s += 1000.0
                if y is None and prefer_comp is None:
                    s -= self.comp_size[self.comp[f]] * 1e-6
                return s
            f = min(cands, key=score)
            if y is None or abs(self.height(f, x, z) - y) <= 3.0:
                return f, (x, self.height(f, x, z), z), 0.0
        n = self.nearest(x, z, y, radius=snap, comp=prefer_comp)
        if n is None and prefer_comp is not None:
            n = self.nearest(x, z, y, radius=snap)
        if n is None:
            return None
        d, f, p = n
        return f, p, d

    def candidates(self, x, z, y=None, snap=2.0, dy=3.0, limit=8, above=None):
        """Every walkable place a position may stand for: [(face, point, distance)], the face under it first when
        there is one at the right height; else the closest point of each face within snap (a body pressed against a
        wall or a door stands just off the eroded mesh, and which side it is on is unknown)."""
        out = []
        for f in self.faces_at(x, z):
            h = self.height(f, x, z)
            if y is None or (abs(h - y) <= dy and h - y <= 1.0):
                out.append((f, (x, h, z), 0.0))
        if out:
            if y is not None:
                out.sort(key=lambda c: abs(c[1][1] - y))
            return out[:limit]
        r = int(math.ceil(snap / CELL))
        cx, cz = int(math.floor(x / CELL)), int(math.floor(z / CELL))
        seen = set()
        for gx in range(cx - r, cx + r + 1):
            for gz in range(cz - r, cz + r + 1):
                for f in self.grid.get((gx, gz), ()):
                    if f in seen:
                        continue
                    seen.add(f)
                    poly = self.F[f]
                    n = len(poly)
                    d, px, pz = 1e9, x, z
                    for k in range(n):
                        a, b = self.V[poly[k]], self.V[poly[(k + 1) % n]]
                        dd, qx, qz, _t = seg_closest(x, z, a[0], a[2], b[0], b[2])
                        if dd < d:
                            d, px, pz = dd, qx, qz
                    if d > snap:
                        continue
                    py = self.height(f, px, pz)
                    if y is not None and (abs(py - y) > dy or (above is not None and py - y > above)):
                        continue
                    out.append((f, (px, py, pz), d))
        out.sort(key=lambda c: c[2] + (abs(c[1][1] - y) * 0.25 if y is not None else 0.0))
        return out[:limit]

    # ------------------------------------------------------------------------------- links the mesh does not hold
    def boundary_edges(self):
        seam = set()
        for p in self.nav.get('portals', []):
            seam.add(p[0])
            seam.add(p[1])
        for f, poly in enumerate(self.F):
            n = len(poly)
            for k in range(n):
                if self.adj[f][k] < 0:
                    yield f, self.V[poly[k]], self.V[poly[(k + 1) % n]]


def compute_xlinks(area, climbables=(), crawls=(), anchor=None, max_drop=30.0, per_pair=4, spread=6.0):
    """Links between different components: 'drop' (down a ledge, height), 'jump' (a gap at about the same level),
    'ledge' (up 0.5 to 3 m: a climb onto a ledge), 'climb' (up or down a placed climbable object), 'crawl' (between
    two markers of the class named `anchor` that stand at both ends of a crawl space; `crawls` are the placed
    objects of that kind). Returns a list of dicts with from/to faces and points."""
    cands = collections.defaultdict(list)
    for f, a, b in area.boundary_edges():
        ex, ez = b[0] - a[0], b[2] - a[2]
        L = math.hypot(ex, ez)
        if L < 0.2:
            continue
        nx, nz = ez / L, -ex / L
        cx, _, cz = area.cen[f]
        mx, mz = (a[0] + b[0]) / 2, (a[2] + b[2]) / 2
        if (mx - cx) * nx + (mz - cz) * nz < 0:
            nx, nz = -nx, -nz
        samples = max(1, int(L / 2.0))
        for s in range(samples):
            t = (s + 0.5) / samples
            px, pz = a[0] + ex * t, a[2] + ez * t
            py = a[1] + (b[1] - a[1]) * t
            for d in (0.6, 1.2, 2, 3):           # probe distances in metres across the edge
                qx, qz = px + nx * d, pz + nz * d
                for g in area.faces_at(qx, qz):
                    if area.comp[g] == area.comp[f]:
                        continue
                    qy = area.height(g, qx, qz)
                    dy = qy - py
                    if -max_drop <= dy < -0.5 and d <= 2.0:
                        kind, cost = 'drop', -dy
                    elif abs(dy) <= 0.5 and d >= 1.2:
                        kind, cost = 'jump', d
                    elif 0.5 < dy <= 3.0 and d <= 1.2:
                        kind, cost = 'ledge-up', dy
                    else:
                        continue
                    cands[(area.comp[f], area.comp[g], kind)].append(
                        (cost, f, g, (round(px, 2), round(py, 2), round(pz, 2)), (round(qx, 2), round(qy, 2), round(qz, 2))))
                    break
                else:
                    continue
                break
    out = []
    for (ca, cb, kind), lst in cands.items():
        lst.sort()
        chosen = []
        for c in lst:
            if all(math.hypot(c[3][0] - o[3][0], c[3][2] - o[3][2]) >= spread for o in chosen):
                chosen.append(c)
            if len(chosen) >= per_pair:
                break
        for cost, f, g, pa, pb in chosen:
            out.append({'kind': kind, 'a': f, 'b': g, 'pa': list(pa), 'pb': list(pb),
                        'height': round(pb[1] - pa[1], 2), 'gap': round(math.hypot(pb[0] - pa[0], pb[2] - pa[2]), 2)})
    # placed climbables: link the lowest component near the object to each higher one
    for obj in climbables:
        x, y, z = obj['pos']
        near = {}
        for gx in range(int(math.floor((x - 3) / CELL)), int(math.floor((x + 3) / CELL)) + 1):
            for gz in range(int(math.floor((z - 3) / CELL)), int(math.floor((z + 3) / CELL)) + 1):
                for f in area.grid.get((gx, gz), ()):
                    r = area.nearest(x, z, None, radius=3.0, comp=area.comp[f])
                    if r is None:
                        continue
                    d, g, p = r
                    if not (y - 4.0 <= p[1] <= y + 15.0):
                        continue
                    c = area.comp[g]
                    if c not in near or d < near[c][0]:
                        near[c] = (d, g, p)
        if len(near) < 2:
            continue
        low_c = min(near, key=lambda c: near[c][2][1])
        lo = near[low_c]
        for c, hi in near.items():
            if c == low_c or hi[2][1] - lo[2][1] < 1.5:
                continue
            base = {'actor': obj['gyaml'], 'actor_hash': obj['hash'], 'actor_pos': [round(v, 2) for v in obj['pos']]}
            out.append(dict(base, kind='climb-up', a=lo[1], b=hi[1], pa=[round(v, 2) for v in lo[2]],
                            pb=[round(v, 2) for v in hi[2]], height=round(hi[2][1] - lo[2][1], 2), gap=0.0))
            out.append(dict(base, kind='climb-down', a=hi[1], b=lo[1], pa=[round(v, 2) for v in hi[2]],
                            pb=[round(v, 2) for v in lo[2]], height=round(lo[2][1] - hi[2][1], 2), gap=0.0))
    # crawl spaces: markers stand at both ends; join the walkable pieces at two markers that face each other within
    # 12 m
    if crawls and not anchor:
        raise ValueError('compute_xlinks: crawl objects given without the class name of the crawl markers')
    anchors = [o for o in crawls if o['gyaml'] == anchor]
    for i, a in enumerate(anchors):
        for b in anchors[i + 1:]:
            if math.dist(a['pos'], b['pos']) > 12.0:
                continue
            ra = area.nearest(a['pos'][0], a['pos'][2], a['pos'][1], radius=3.0, dy=2.0)
            rb = area.nearest(b['pos'][0], b['pos'][2], b['pos'][1], radius=3.0, dy=2.0)
            if not ra or not rb or area.comp[ra[1]] == area.comp[rb[1]]:
                continue
            base = {'actor': anchor, 'actor_hash': a['hash'], 'actor_pos': [round(v, 2) for v in a['pos']],
                    'other_hash': b['hash'], 'other_pos': [round(v, 2) for v in b['pos']]}
            for (r1, r2) in ((ra, rb), (rb, ra)):
                out.append(dict(base, kind='crawl', a=r1[1], b=r2[1], pa=[round(v, 2) for v in r1[2]],
                                pb=[round(v, 2) for v in r2[2]], height=round(r2[2][1] - r1[2][1], 2),
                                gap=round(math.dist((r1[2][0], r1[2][2]), (r2[2][0], r2[2][2])), 2)))
    return out
