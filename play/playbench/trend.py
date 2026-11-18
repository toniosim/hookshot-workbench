"""The trend: tables (markdown) and a chart (SVG, and a PNG when ImageMagick can draw it) from the results store.

  night table     one row per cell, one column per arm: `ok 34 s` (met, game seconds to the proof), `fail 40%` (not met; how much of the way to the proof's place the
                  best sample closed, when the proof is a place), `? why` (invalid: kept, not counted), `-` (not run)
  trend table     one row per night: the pilot commit and the game build it played with, and per arm: cells solved of the cells that counted, the median time to
                  goal of those solved, stuck seconds, decisions and USD over the cells that counted
  blocked         a failed run of a cell with a known cause outside the pilot (a game input that does nothing): shown as `blocked`, left out of solved/valid
  changes         between two nights: the cells that flipped, only over cells whose fingerprint (frozen segment, save, proof, budget) and arm hash are the same
  chart           (1) cells solved per night and arm, with the nights the pilot commit or the game build changed marked; (2) the grid cell x night per arm (green met,
                  orange-to-pink fail by progress, yellow invalid, grey not run); (3) stuck seconds and cost per night

Every number is a stored result (store.py); nothing is computed from the game here. A night's numbers say what the pilot at that commit did on that build.
"""
import statistics
import subprocess
from pathlib import Path
from xml.sax.saxutils import escape

PALETTE = ('#1f6fb4', '#d1472b', '#2e9e4f', '#8e5bb5', '#c78a1b', '#2a9d9d', '#7a7a7a', '#b5446e')


def fmt(v, nd=1, none='-'):
    return none if v is None else (f'{v:.{nd}f}' if isinstance(v, float) else str(v))


def label(row):
    """The short text of one stored result (a dict) in a table cell."""
    if row is None:
        return '-'
    if not row['valid']:
        return '? invalid'
    if row.get('blocker') and not row['success']:
        return 'blocked'
    if row['success']:
        return f"ok {row['time_to_goal_s']:.0f} s" if row['time_to_goal_s'] is not None else 'ok'
    return f"fail {row['progress'] * 100:.0f}%" if row['progress'] is not None else 'fail'


def aggregates(counted, arm, cells):
    """One arm's numbers for one night over the cells that counted ({(cell, arm): row})."""
    rows = [counted[(c, arm)] for c in cells if (c, arm) in counted]
    blocked = [r for r in rows if r['valid'] and not r['success'] and r.get('blocker')]
    valid = [r for r in rows if r['valid'] and r not in blocked]   # (a known cause outside the pilot: neither a pass nor a failure of the player)
    solved = [r for r in valid if r['success']]
    ttg = [r['time_to_goal_s'] for r in solved if r['time_to_goal_s'] is not None]

    def total(key):
        xs = [r[key] for r in valid if r[key] is not None]
        return round(sum(xs), 1) if xs else None
    return {'run': len(rows), 'valid': len(valid), 'blocked': len(blocked), 'invalid': len(rows) - len(valid) - len(blocked), 'solved': len(solved), 'median_ttg': round(statistics.median(ttg), 1) if ttg else None,
            'stuck_s': total('stuck_s'), 'decisions': total('decisions'), 'cost_usd': round(sum(r['cost_usd'] or 0 for r in rows), 4) if rows else None}


def arms_in(history, order):
    seen = {a for _, counted in history for (_, a) in counted}
    return [a for a in order if a in seen] + sorted(seen - set(order))


def night_md(night, counted, cells, arms):
    """Markdown: the night's one table (cell x arm), then each arm's details."""
    head = f"### Night {night['night']} - pilot `{night['pilot_commit'] or '?'}`, build `{night['build'] or '?'}`, status {night['status']}"
    out = [head, '', '| cell | ' + ' | '.join(arms) + ' |', '|---|' + '---|' * len(arms)]
    for c in cells:
        out.append(f'| {c} | ' + ' | '.join(label(counted.get((c, a))) for a in arms) + ' |')
    out += ['', '| cell | arm | result | time to goal s | stuck s | decisions | USD | progress | why |', '|---|---|---|---|---|---|---|---|---|']
    for c in cells:
        for a in arms:
            r = counted.get((c, a))
            if r is None:
                continue
            out.append(f"| {c} | {a} | {label(r)} | {fmt(r['time_to_goal_s'])} | {fmt(r['stuck_s'])} | {fmt(r['decisions'])} | {fmt(r['cost_usd'], 4)} | "
                       f"{fmt(None if r['progress'] is None else round(r['progress'] * 100))} | {((('blocked: ' + r['blocker'] + '; ') if r.get('blocker') and not r['success'] else '') + (r['why'] or ''))[:110].replace('|', '/')} |")
    return '\n'.join(out) + '\n'


def trend_md(history, cells, arms):
    """Markdown: one row per night with the identity of what played, then each arm's aggregates."""
    cols = ['night', 'pilot', 'build'] + [f'{a} solved' for a in arms] + [f'{a} median s | {a} stuck s | {a} decisions | {a} USD' for a in arms]
    out = ['| ' + ' | '.join(cols) + ' |', '|' + '---|' * len(' | '.join(cols).split(' | ')), ]
    prev = None
    for n, counted in history:
        ag = {a: aggregates(counted, a, cells) for a in arms}
        mark = lambda key, v: v if prev is None or prev.get(key) == v else f'**{v}**'   # noqa: E731
        ident = [n['night'], mark('pilot_commit', n['pilot_commit'] or '?'), mark('build', n['build'] or '?')]
        solved = [f"{ag[a]['solved']}/{ag[a]['valid']}" + (f" (+{ag[a]['invalid']} invalid)" if ag[a]['invalid'] else '') + (f" (+{ag[a]['blocked']} blocked)" if ag[a]['blocked'] else '') if ag[a]['run'] else '-' for a in arms]
        rest = [f"{fmt(ag[a]['median_ttg'])} | {fmt(ag[a]['stuck_s'])} | {fmt(ag[a]['decisions'])} | {fmt(ag[a]['cost_usd'], 4)}" for a in arms]
        out.append('| ' + ' | '.join(ident + solved + rest) + ' |')
        prev = n
    return '\n'.join(out) + '\n'


def grid_md(history, cells, arm):
    """Markdown grid for one arm: a row per cell, a column per night (`+` met, `-` not met, `?` invalid, `.` not run; `*` the cell or the arm changed)."""
    cols = [n['night'][4:] for n, _ in history]
    out = [f'**{arm}**', '', '| cell | ' + ' | '.join(cols) + ' |', '|---|' + '---|' * len(cols)]
    for c in cells:
        cs, prev = [], None
        for _, counted in history:
            r = counted.get((c, arm))
            if r is None:
                cs.append('.')
            else:
                sym = '?' if not r['valid'] else '+' if r['success'] else 'b' if r.get('blocker') else '-'
                if prev is not None and (prev['fingerprint'], prev['arm_hash']) != (r['fingerprint'], r['arm_hash']):
                    sym += '*'
                cs.append(sym)
                prev = r
        out.append(f'| {c} | ' + ' | '.join(cs) + ' |')
    return '\n'.join(out) + '\n'


def changes(prev_counted, cur_counted, cells, arms):
    """Between two nights, over the cells and arms whose fingerprint and arm hash are unchanged: [(cell, arm, text)] for each that flipped or moved a lot."""
    out = []
    for c in cells:
        for a in arms:
            p, q = prev_counted.get((c, a)), cur_counted.get((c, a))
            if not p or not q or not p['valid'] or not q['valid'] or (p['fingerprint'], p['arm_hash']) != (q['fingerprint'], q['arm_hash']):
                continue
            if p['success'] != q['success']:
                out.append((c, a, 'now met' if q['success'] else 'no longer met'))
            elif p['success'] and q['success'] and p['time_to_goal_s'] and q['time_to_goal_s'] and abs(q['time_to_goal_s'] - p['time_to_goal_s']) >= 0.25 * p['time_to_goal_s']:
                out.append((c, a, f"time to goal {p['time_to_goal_s']:.0f} s -> {q['time_to_goal_s']:.0f} s"))
    return out


# ---------------------------------------------------------------------------------------------------------------------------------------------- the chart

def _cell_color(r):
    if r is None:
        return '#dcdcdc'
    if not r['valid']:
        return '#efe08a'
    if r['success']:
        return '#2e9e4f'
    if r.get('blocker'):
        return '#9fb4c9'
    p = r['progress']
    if p is None:
        return '#e4a0a0'
    # 0% -> pink, 100% (nearly there) -> orange
    a, b = (0xe8, 0xa6, 0xa6), (0xf0, 0xa8, 0x40)
    return '#%02x%02x%02x' % tuple(round(x + (y - x) * p) for x, y in zip(a, b))


class Svg:
    def __init__(self, w, h):
        self.w, self.h, self.parts = w, h, []

    def add(self, s):
        self.parts.append(s)

    def rect(self, x, y, w, h, fill, stroke=None, title=None, rx=0):
        t = f'<title>{escape(title)}</title>' if title else ''
        self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{fill}"' + (f' stroke="{stroke}"' if stroke else '') + (f' rx="{rx}"' if rx else '') + f'>{t}</rect>')

    def text(self, x, y, s, size=11, anchor='start', fill='#222', weight='normal', rotate=None):
        tr = f' transform="rotate({rotate} {x:.1f} {y:.1f})"' if rotate else ''
        self.add(f'<text x="{x:.1f}" y="{y:.1f}" font-family="DejaVu Sans, Arial, sans-serif" font-size="{size}" text-anchor="{anchor}" fill="{fill}" font-weight="{weight}"{tr}>{escape(str(s))}</text>')

    def line(self, x1, y1, x2, y2, stroke='#999', width=1, dash=None):
        self.add(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{stroke}" stroke-width="{width}"' + (f' stroke-dasharray="{dash}"' if dash else '') + '/>')

    def poly(self, pts, stroke, width=2):
        self.add('<polyline points="' + ' '.join(f'{x:.1f},{y:.1f}' for x, y in pts) + f'" fill="none" stroke="{stroke}" stroke-width="{width}"/>')

    def circle(self, x, y, r, fill, stroke='#fff'):
        self.add(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="1"/>')

    def render(self):
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" viewBox="0 0 {self.w} {self.h}"><rect width="{self.w}" height="{self.h}" fill="white"/>'
                + ''.join(self.parts) + '</svg>\n')


def chart_svg(history, cells, arms, title='Pilot scoreboard'):
    n = len(history)
    W = 1100
    left, right = 150, 40
    grid_rows = len(cells)
    cell_h = 17
    hA, hB, hC = 230, len(arms) * (grid_rows * cell_h + 44) + 10, 210
    H = 60 + hA + hB + hC + 60
    s = Svg(W, H)
    s.text(20, 28, title, 18, weight='bold')
    s.text(20, 46, f'{len(cells)} cells, {len(arms)} arm(s), {n} night(s); every point is a stored result: the game\'s state proved the goal', 11, fill='#555')
    colw = min(110.0, (W - left - right) / max(n, 1))
    xs = [left + colw * (i + 0.5) for i in range(n)]

    def ticks(y0):
        prev = None
        for i, (night, _) in enumerate(history):
            if n > 16 and i % 2:
                continue
            s.text(xs[i], y0 + 14, night['night'][4:6] + '-' + night['night'][6:8], 10, 'middle', '#444')
            c = (night['pilot_commit'] or '?')[:7]
            b = (night['build'] or '?')
            b = b.rsplit('-', 1)[-1] if '-g' in b else b   # (the build's commit part: the version prefix is the same for weeks)
            changed = prev is not None and (prev[0] != c or prev[1] != b)
            s.text(xs[i], y0 + 26, c, 9, 'middle', '#b0301c' if changed and prev[0] != c else '#777')
            s.text(xs[i], y0 + 37, b[:12], 8, 'middle', '#b0301c' if changed and prev[1] != b else '#999')
            prev = (c, b)

    # (1) solved per night
    y0, y1 = 70, 70 + hA - 70
    s.text(20, 66, '1. Cells solved per night (valid cells only)', 13, weight='bold')
    top = max(len(cells), 1)
    for v in range(0, top + 1, max(1, top // 4)):
        y = y1 - (y1 - y0 - 12) * v / top
        s.line(left - 6, y, W - right, y, '#e4e4e4')
        s.text(left - 10, y + 4, v, 10, 'end', '#666')
    for k, a in enumerate(arms):
        col = PALETTE[k % len(PALETTE)]
        pts = []
        for i, (_, counted) in enumerate(history):
            ag = aggregates(counted, a, cells)
            if ag['run']:
                pts.append((xs[i], y1 - (y1 - y0 - 12) * ag['solved'] / top, ag))
        if len(pts) > 1:
            s.poly([(x, y) for x, y, _ in pts], col)
        for x, y, ag in pts:
            s.circle(x, y, 5, col)
            s.text(x + 9, y + 4 + 11 * (k - (len(arms) - 1) / 2), ag['solved'], 10, fill=col, weight='bold')
        s.rect(W - right - 150, y0 + 4 + 16 * k, 10, 10, col)
        s.text(W - right - 134, y0 + 13 + 16 * k, a, 11)
    ticks(y1)
    # (2) grids
    gy = 60 + hA + 10
    s.text(20, gy, '2. Each cell, each night (green: met, number = game seconds to goal; pink to orange: not met, by progress; blue-grey: blocked by a known cause; yellow: invalid; grey: not run)', 12, weight='bold')
    gy += 12
    for k, a in enumerate(arms):
        col = PALETTE[k % len(PALETTE)]
        s.text(20, gy + 14, a, 13, fill=col, weight='bold')
        gy += 20
        for r_i, c in enumerate(cells):
            y = gy + r_i * cell_h
            s.text(left - 8, y + 12, c, 10, 'end', '#333')
            prev = None
            for i, (_, counted) in enumerate(history):
                row = counted.get((c, a))
                x = xs[i] - colw / 2 + 1
                tip = f"{c} / {a}: {label(row)}" + (f" - {row['why']}" if row and row['why'] else '')
                s.rect(x, y, colw - 2, cell_h - 2, _cell_color(row), title=tip)
                if row and row['valid'] and row['success'] and row['time_to_goal_s'] is not None and colw >= 22:
                    s.text(x + (colw - 2) / 2, y + 12, f"{row['time_to_goal_s']:.0f}", 9, 'middle', '#fff', 'bold')
                elif row and not row['valid'] and colw >= 14:
                    s.text(x + (colw - 2) / 2, y + 12, '?', 10, 'middle', '#7a6a00', 'bold')
                if row is not None and prev is not None and (prev['fingerprint'], prev['arm_hash']) != (row['fingerprint'], row['arm_hash']):
                    s.line(x, y, x, y + cell_h - 2, '#222', 2)   # a thick edge: the cell (or the arm) changed since the last night it ran
                if row is not None:
                    prev = row
        gy += grid_rows * cell_h + 24
    # (3) stuck seconds and cost
    cy = gy + 10
    s.text(20, cy, '3. Stuck seconds (lines) and cost in USD (bars) per night, over the cells that counted', 13, weight='bold')
    y0, y1 = cy + 16, cy + hC - 70
    stuck = {a: [aggregates(c_, a, cells)['stuck_s'] for _, c_ in history] for a in arms}
    cost = {a: [aggregates(c_, a, cells)['cost_usd'] for _, c_ in history] for a in arms}
    mx = max([v for vs in stuck.values() for v in vs if v is not None] + [1.0])
    mc = max([v for vs in cost.values() for v in vs if v is not None] + [0.01])
    s.line(left - 6, y1, W - right, y1, '#bbb')
    s.text(left - 10, y0 + 8, f'{mx:.0f} s', 10, 'end', '#666')
    s.text(left - 10, y1, '0', 10, 'end', '#666')
    s.text(W - right, y0 + 8, f'bars: up to {mc:.2f} USD', 10, 'end', '#666')
    bw = max(3.0, colw / (len(arms) + 2))
    for k, a in enumerate(arms):
        col = PALETTE[k % len(PALETTE)]
        pts = []
        for i in range(n):
            if cost[a][i] is not None:
                h = (y1 - y0 - 6) * cost[a][i] / mc * 0.5
                s.rect(xs[i] - colw / 2 + 3 + k * bw, y1 - h, bw - 1, h, col, title=f'{a} {cost[a][i]:.3f} USD')
            if stuck[a][i] is not None:
                pts.append((xs[i], y1 - (y1 - y0 - 6) * stuck[a][i] / mx))
        if len(pts) > 1:
            s.poly(pts, col)
        for x, y in pts:
            s.circle(x, y, 3.5, col)
    ticks(y1)
    return s.render()


def write_all(history, cells, arms, outdir, title='Pilot scoreboard', png=True):
    """Write trend.md, chart.svg and (with ImageMagick) chart.png into outdir; returns {name: path}."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    md = ['# Pilot scoreboard trend', '', trend_md(history, cells, arms)]
    for a in arms:
        md += [grid_md(history, cells, a), '']
    if history:
        n, counted = history[-1]
        md += [night_md(n, counted, cells, arms)]
        if len(history) > 1:
            ch = changes(history[-2][1], counted, cells, arms)
            md += ['', f"Changes since night {history[-2][0]['night']} (cells and arms unchanged): " + ('; '.join(f'{c}/{a} {t}' for c, a, t in ch) if ch else 'none')]
    files = {}
    (outdir / 'trend.md').write_text('\n'.join(md) + '\n')
    files['trend.md'] = outdir / 'trend.md'
    svg = chart_svg(history, cells, arms, title)
    (outdir / 'chart.svg').write_text(svg)
    files['chart.svg'] = outdir / 'chart.svg'
    if png:
        r = subprocess.run(['magick', '-density', '110', str(outdir / 'chart.svg'), str(outdir / 'chart.png')], capture_output=True, text=True, timeout=120)
        if r.returncode == 0 and (outdir / 'chart.png').is_file():
            files['chart.png'] = outdir / 'chart.png'
    return files
