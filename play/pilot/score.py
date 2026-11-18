#!/usr/bin/env python3
"""The bug hunter's feedback loop: a scorecard per round, triage that becomes rules, passive coverage of other lanes' runs, the next round's plan.

    hunt.py score ROUND_FOLDER... --ledger L.jsonl --registry known.json [--name N] [--passive FOLDER...] [--places P.json] [--md OUT.md]

* Scorecard (`score_round`): per detector kind the findings raised, how many a person confirmed real, how many are known issues, how many are
  explained or artefacts (the registry's verdicts and the detectors' own `explained` marks), how many nobody has looked at; the false-alarm rate
  (explained + artefact) / raised; minutes of play, the maps covered, the cost. One JSON line per round is appended to the ledger; `trend_table`
  prints the rounds side by side.
* Triage feeds back (`apply_feedback`, called by the hold before a finding is entered): the registry's verdict for a key is a rule the next run
  applies. artefact -> `info` with the reason shown; known-issue -> `info`, labelled known; real -> kept, labelled; fixed -> a finding of that key
  is a REGRESSION (error). Nothing is dropped: the finding stays in the list with its reason.
* Regression (`regression_checks`): every entry that has a replay packet is re-run each round; a real or known issue must still reproduce, a fixed one
  must have stopped reproducing; the verdicts are read from `<packet>/replay/replay.json` (written by `hunt.py verdict`).
* Passive coverage (`passive_scan`): the detectors, read-only and after the fact, over run folders other lanes already made; findings go through the
  same rules; a key the registry has never seen is flagged NEW.
* Next plan (`plan_hints`): places with no coverage get placed roams; detectors with a high false-alarm rate get their thresholds reviewed.
Made-up names in the tests; this file names no map, flag or coordinate.
"""
import collections
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bughunt  # noqa: E402

CONFIRMED = ('real', 'fixed')
HIGH_RATE = 0.5          # a detector whose raised findings were this share explained or artefact, with MIN_RAISED of them, is reviewed
MIN_RAISED = 3
THRESHOLD_KEYS = {'stall': 'stall_warn_ms / stall_error_ms / pressure_*', 'log': 'the baseline of reference logs (known-log.json)', 'visual': 'flicker_diff / burst_diff / vision_p',
                  'coop': 'net_over_factor / peer_gone_s / snap_after_stall_s', 'body': 'snap_after_stall_s', 'net': 'net_over_factor', 'softlock': 'softlock_s',
                  'hang': 'hang_s', 'oob': 'oob_*_m', 'audio': 'the audio rule', 'give': 'give_settle_s / give_lookback_s', 'desync': 'desync_grace_s'}


# ---- the registry's verdicts as rules

def verdict_of(entry):
    """open / real / known-issue / artefact / fixed of a registry entry (None: not in the registry)."""
    return None if entry is None else (entry.get('status') or 'open')


def apply_feedback(findings, entries):
    """Apply the registry's verdicts to findings in place; returns {'explained': n, 'known': n, 'real': n, 'regression': n, 'new': n} (the
    findings that were not `info` already). `entries` is Registry.entries()."""
    out = collections.Counter()
    for f in findings:
        if f.severity == 'info':
            continue
        e = entries.get(f.key)
        v = verdict_of(e)
        note = ((e or {}).get('note') or '').strip()
        if v == 'artefact':
            bughunt.explain(f, f'triaged as an artefact{": " + note if note else ""}')
            out['explained'] += 1
        elif v == 'known-issue':
            f.severity = 'info'
            f.text += f' (known issue{": " + note if note else ""})'
            f.evidence = dict(f.evidence or {}, known=note or True)
            out['known'] += 1
        elif v == 'real':
            f.text += ' (triaged: real)'
            f.evidence = dict(f.evidence or {}, triaged='real')
            out['real'] += 1
        elif v == 'fixed':
            f.severity = 'error'
            f.text += ' (REGRESSION: this key was marked fixed)'
            f.evidence = dict(f.evidence or {}, regression=True)
            out['regression'] += 1
        else:
            out['new'] += 1
    return dict(out)


def regression_checks(entries, now=None):
    """[{key, status, packet, expect, verdict, result}] for every entry with a packet: expect `reproduce` for a real, known or open entry and `stop`
    for a fixed one; result `ok`, `REGRESSION` (a fixed one reproduces), `STOPPED` (a real one no longer reproduces: look, then mark it fixed)
    or `not-run` (no replay verdict yet)."""
    rows = []
    for key, e in sorted(entries.items()):
        pk = e.get('packet')
        if not pk:
            continue
        st = verdict_of(e)
        if st == 'artefact':
            continue
        expect = 'stop' if st == 'fixed' else 'reproduce'
        verdict, result = None, 'not-run'
        try:
            verdict = json.loads((Path(pk) / 'replay' / 'replay.json').read_text()).get('verdict')
        except (OSError, ValueError):
            pass
        if verdict:
            reproduced = verdict == 'reproduced'
            result = 'ok' if reproduced == (expect == 'reproduce') else ('REGRESSION' if expect == 'stop' else 'STOPPED')
        rows.append({'key': key, 'status': st, 'packet': pk, 'expect': expect, 'verdict': verdict, 'result': result})
    return rows


# ---- the scorecard

def load_round(folder):
    """(rows, findings) of a hunt folder (result.json) or an analysis folder (table.json)."""
    folder = Path(folder)
    for n in ('result.json', 'table.json'):
        p = folder / n
        if p.is_file():
            d = json.loads(p.read_text())
            fs = d.get('findings') or []
            if fs and isinstance(fs[0], (list, tuple)):   # table.json rows: [session, finding dict, status, packet]
                fs = [dict(x[1], session=x[0], status=x[2], packet=x[3]) for x in fs]
            return d.get('sessions') or d.get('rows') or [], fs, d
    return [], [], {}


def maps_of(folder, rows):
    """The maps a round's sessions were in (the state journals' `map`): the places covered."""
    maps = collections.Counter()
    for r in rows:
        d = Path(folder) / r.get('name', '')
        if not d.is_dir():
            continue
        try:
            sides = bughunt.find_sides(d)
        except OSError:
            continue
        for side in sides.values():
            seen = set()
            for s in side.states:
                m = s.get('map') or s.get('area')
                if m:
                    seen.add(m)
            maps.update(seen)
    return dict(maps)


def score_round(name, folders, entries, kind='hunt', with_maps=True):
    """One scorecard (a dict, the ledger's line) over hunt or analysis folders; `entries` is the registry's. Findings of the detectors' own
    `explained` marks (info with a reason) are in the detectors' per-side tables, so a detector's `explained` count is added from there."""
    per = collections.defaultdict(lambda: collections.Counter())
    scen = []
    minutes, usd, maps, sessions, placed, placed_ok = 0.0, 0.0, collections.Counter(), 0, 0, 0
    seen_keys = set()
    for folder in folders:
        rows, findings, doc = load_round(folder)
        usd += float(doc.get('usd_spent') or 0.0)
        for r in rows:
            sessions += 1
            minutes += float(r.get('seconds') or 0.0) / 60.0
            sc = r.get('scenario')
            if isinstance(sc, dict) and sc.get('verdict'):   # a scenario is scored by what it was for: a reproduction attempt's verdict is a result even when no bug shows
                scen.append({'name': sc.get('name'), 'purpose': sc.get('purpose'), 'verdict': sc['verdict'], 'hardware': sc.get('hardware')})
            pl = r.get('place')
            placed += 1 if pl else 0
            placed_ok += 1 if isinstance(pl, dict) and pl.get('ok') else 0
            for side in (r.get('detectors') or {}).values():
                for det, v in side.items():
                    per[det]['explained_by_detector'] += int(v.get('explained') or 0)
        for f in findings:
            k = f.get('kind') or str(f.get('key', '')).split(':')[0]
            key = f.get('key')
            if (f.get('session'), key, f.get('side'), f.get('t')) in seen_keys:
                continue
            seen_keys.add((f.get('session'), key, f.get('side'), f.get('t')))
            v = verdict_of(entries.get(key))
            c = per[k]
            c['raised'] += 1
            if v in CONFIRMED:
                c['real'] += 1
            elif v == 'known-issue':
                c['known'] += 1
            elif v == 'artefact' or f.get('severity') == 'info':
                c['explained'] += 1
            else:
                c['unreviewed'] += 1
        if with_maps:
            maps.update(maps_of(folder, rows))
    dets = {}
    for k, c in sorted(per.items()):
        raised = c['raised']
        cut = c['explained'] + c['known']
        dets[k] = {'raised': raised, 'real': c['real'], 'known': c['known'], 'explained': c['explained'], 'unreviewed': c['unreviewed'],
                   'explained_by_detector': c['explained_by_detector'], 'false_alarm_rate': round((c['explained'] + c['explained_by_detector']) / max(1, raised + c['explained_by_detector']), 3)}
    tot = {f: sum(d[f] for d in dets.values()) for f in ('raised', 'real', 'known', 'explained', 'unreviewed', 'explained_by_detector')}
    tot['false_alarm_rate'] = round((tot['explained'] + tot['explained_by_detector']) / max(1, tot['raised'] + tot['explained_by_detector']), 3)
    return {'format': 'ls-hunt-score/1', 'round': name, 'kind': kind, 'at': time.strftime('%F %T'), 'scenarios': scen, 'sessions': sessions, 'placed_sessions': placed, 'placed_ok': placed_ok,
            'minutes': round(minutes, 1), 'usd': round(usd, 4), 'maps': maps, 'detectors': dets, 'total': tot}


def append_ledger(path, card):
    with open(path, 'a') as f:
        f.write(json.dumps(card, sort_keys=True) + '\n')


def read_ledger(path):
    try:
        return [json.loads(x) for x in Path(path).read_text().splitlines() if x.strip()]
    except OSError:
        return []


def trend_table(cards):
    """A Markdown table of the rounds side by side, then each round's detector rows."""
    out = ['| round | kind | sessions (placed) | minutes | maps | raised | real | known | explained | unreviewed | false-alarm rate | USD |', '|---|---|---|---|---|---|---|---|---|---|---|---|']
    for c in cards:
        t = c['total']
        out.append(f'| {c["round"]} | {c["kind"]} | {c["sessions"]} ({c.get("placed_ok", 0)}/{c.get("placed_sessions", 0)} placed) | {c["minutes"]} | {len(c["maps"])} | {t["raised"]} | {t["real"]} | {t["known"]} | '
                   f'{t["explained"]} (+{t["explained_by_detector"]} by the detectors) | {t["unreviewed"]} | {t["false_alarm_rate"]:.0%} | {c["usd"]} |')
    att = [(c['round'], x) for c in cards for x in c.get('scenarios') or []]
    if att:
        out += ['', '| round | scenario | for | verdict | hardware |', '|---|---|---|---|---|'] + [f'| {r} | {x["name"]} | {x["purpose"]} | {x["verdict"]} | {x.get("hardware") or ""} |' for r, x in att]
    out += ['', '| round | detector | raised | real | known | explained | unreviewed | false-alarm rate |', '|---|---|---|---|---|---|---|---|']
    for c in cards:
        for k, d in c['detectors'].items():
            out.append(f'| {c["round"]} | {k} | {d["raised"]} | {d["real"]} | {d["known"]} | {d["explained"]} (+{d["explained_by_detector"]}) | {d["unreviewed"]} | {d["false_alarm_rate"]:.0%} |')
    return '\n'.join(out)


# ---- passive coverage

def passive_scan(folders, cfg, bounds, baseline, entries, only_kinds=None):
    """Read-only detectors over run folders other lanes made. Returns (rows, findings): a row per folder {name, sides, findings, flagged_new}; the
    findings go through `apply_feedback`; those whose key the registry has never seen carry `evidence['passive_new']`."""
    rows, allf = [], []
    for folder in folders:
        try:
            sides = bughunt.find_sides(folder)
            if not any(s.state_path or s.present or s.log or s.counters for s in sides.values()):
                rows.append({'name': Path(folder).name, 'sides': 0, 'findings': 0, 'flagged_new': 0, 'skipped': 'no state journal or present trace'})
                continue
            rep = bughunt.analyze(folder, cfg, bounds, baseline, None, None, sides)
        except Exception as e:   # noqa: BLE001  a folder that cannot be read is a row, not a stop
            rows.append({'name': Path(folder).name, 'sides': 0, 'findings': 0, 'flagged_new': 0, 'skipped': f'{type(e).__name__}: {str(e)[:100]}'})
            continue
        fs = [f for f in rep['findings'] if not only_kinds or f.kind in only_kinds]
        apply_feedback(fs, entries)
        new = 0
        for f in fs:
            if f.key not in entries and f.severity != 'info':
                f.evidence = dict(f.evidence or {}, passive_new=True)
                new += 1
        maps = sorted({m for sd in sides.values() for m in (x.get('map') or x.get('area') for x in sd.states) if m})
        rows.append({'name': Path(folder).name, 'sides': len(sides), 'findings': sum(1 for f in fs if f.severity != 'info'), 'explained': sum(1 for f in fs if f.severity == 'info'), 'flagged_new': new,
                     'maps': maps, 'read': [k for k, v in (('state', any(sd.state_path for sd in sides.values())), ('present', any(sd.present for sd in sides.values())), ('log', any(sd.log for sd in sides.values()))) if v]})
        for f in fs:
            allf.append((Path(folder).name, f))
    return rows, allf


def passive_card(name, rows, allf, entries):
    """The ledger line of a passive pass: the same shape as a round's, built from `passive_scan`'s output."""
    per = collections.defaultdict(collections.Counter)
    for _, f in allf:
        c = per[f.kind]
        v = verdict_of(entries.get(f.key))
        c['raised'] += 1
        if v in CONFIRMED:
            c['real'] += 1
        elif v == 'known-issue':
            c['known'] += 1
        elif f.severity == 'info' or v == 'artefact':
            c['explained'] += 1
        else:
            c['unreviewed'] += 1
    dets = {k: {'raised': c['raised'], 'real': c['real'], 'known': c['known'], 'explained': c['explained'], 'unreviewed': c['unreviewed'], 'explained_by_detector': 0,
                'false_alarm_rate': round(c['explained'] / max(1, c['raised']), 3)} for k, c in sorted(per.items())}
    tot = {f: sum(d[f] for d in dets.values()) for f in ('raised', 'real', 'known', 'explained', 'unreviewed', 'explained_by_detector')}
    tot['false_alarm_rate'] = round(tot['explained'] / max(1, tot['raised']), 3)
    return {'format': 'ls-hunt-score/1', 'round': name, 'kind': 'passive', 'at': time.strftime('%F %T'), 'sessions': sum(1 for r in rows if not r.get('skipped')), 'placed_sessions': 0,
            'minutes': 0.0, 'usd': 0.0, 'maps': dict(collections.Counter(m for r in rows for m in r.get('maps', []))), 'detectors': dets, 'total': tot,
            'flagged_new': sum(r['flagged_new'] for r in rows), 'folders': len(rows)}


# ---- the next round

def plan_hints(cards, places=(), min_sessions=1):
    """What the next round should do, from the ledger: {'places': [...], 'review': [...], 'text': [...]}. places: the destinations (a list of names)
    no round covered; review: detectors with a false-alarm rate of HIGH_RATE or more over MIN_RAISED or more findings, in the latest hunt round."""
    covered = collections.Counter()
    for c in cards:
        for m, n in (c.get('maps') or {}).items():
            covered[m] += n
    low = [p for p in places if covered.get(p, 0) < min_sessions]
    hunts = [c for c in cards if c['kind'] == 'hunt'] or cards
    latest = hunts[-1] if hunts else None
    review = []
    if latest:
        for k, d in latest['detectors'].items():
            if d['raised'] + d['explained_by_detector'] >= MIN_RAISED and d['false_alarm_rate'] >= HIGH_RATE:
                review.append({'detector': k, 'raised': d['raised'], 'false_alarm_rate': d['false_alarm_rate'], 'review': THRESHOLD_KEYS.get(k, 'its thresholds')})
    text = [f'placed roams wanted for {len(low)} of {len(places)} destinations with no coverage: ' + ', '.join(low[:12]) + (' ...' if len(low) > 12 else '')] if low else ['every listed destination has some coverage']
    text += [f'review {r["review"]} ({r["detector"]}: {r["false_alarm_rate"]:.0%} of {r["raised"]} findings were explained or artefacts)' for r in review]
    return {'places': low, 'review': review, 'text': text}


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description='the hunt scorecard')
    ap.add_argument('folders', nargs='*')
    ap.add_argument('--name', required=True)
    ap.add_argument('--ledger', required=True)
    ap.add_argument('--registry', required=True)
    ap.add_argument('--kind', default='hunt')
    ap.add_argument('--passive', nargs='*', default=[], help='run folders of other lanes: read-only detectors, after the fact')
    ap.add_argument('--config')
    ap.add_argument('--bounds')
    ap.add_argument('--baseline')
    ap.add_argument('--places', help='a JSON list of destination names for the next plan')
    ap.add_argument('--md')
    a = ap.parse_args(argv)
    import bugpacket
    entries = bugpacket.Registry(a.registry).entries()
    out = []
    if a.folders:
        card = score_round(a.name, a.folders, entries, kind=a.kind)
        append_ledger(a.ledger, card)
        out.append(f'scored {a.name}: {card["total"]}')
    if a.passive:
        cfg = bughunt.Config.from_dict(json.loads(Path(a.config).read_text()) if a.config else None)
        bounds = bughunt.Bounds.load(a.bounds) if a.bounds else None
        rows, allf = passive_scan(a.passive, cfg, bounds, bughunt.load_baseline(a.baseline), entries)
        pc = passive_card(a.name + '-passive', rows, allf, entries)
        append_ledger(a.ledger, pc)
        out.append(f'passive {a.name}: {pc["folders"]} folders, {pc["total"]["raised"]} findings, {pc["flagged_new"]} NEW')
        for r in rows:
            out.append(f'   {r["name"]}: sides {r["sides"]}, findings {r["findings"]}, new {r["flagged_new"]}' + (f' ({r["skipped"]})' if r.get('skipped') else ''))
        for n, f in allf:
            if (f.evidence or {}).get('passive_new'):
                out.append(f'   NEW {n}: {f.kind}/{f.sub} {f.key} {f.text[:110]}')
    cards = read_ledger(a.ledger)
    table = trend_table(cards)
    reg = regression_checks(entries)
    hints = plan_hints(cards, json.loads(Path(a.places).read_text()) if a.places else [])
    md = ['# Scorecard', '', table, '', '## Regression checks (every entry with a replay packet)', '', '| key | status | expect | verdict | result |', '|---|---|---|---|---|']
    md += [f'| `{r["key"]}` | {r["status"]} | {r["expect"]} | {r["verdict"]} | {r["result"]} |' for r in reg]
    md += ['', '## Next round', ''] + [f'- {t}' for t in hints['text']]
    if a.md:
        Path(a.md).write_text('\n'.join(md) + '\n')
    print('\n'.join(out + [''] + md))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
