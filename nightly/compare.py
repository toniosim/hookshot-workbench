"""Empirical comparisons. No game, network, or machine-specific data required."""
import math
import re
import statistics


def signature(line):
    """Keep words/error identity; strip volatile timestamps, addresses, counters and paths."""
    line = re.sub(r'\x1b\[[0-9;]*[A-Za-z]', '', line)
    line = re.sub(r'\b(?:0x[0-9a-f]+|[0-9a-f]{8,})\b', '<addr>', line, flags=re.I)
    line = re.sub(r'(?<![\w])[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?', '<n>', line)
    return re.sub(r'\s+', ' ', line).strip()


def band(values):
    """At least three independent nights, at most the most recent seven; no fixed % allowance.

    Half width is the larger of the observed maximum deviation and three robust sigma
    (sigma = 1.4826*MAD). Zero-spread data has a zero-width band; confirmation still applies.
    """
    values = list(values)[-7:]
    if len(values) < 3:
        return None
    if not all(math.isfinite(x) for x in values):
        raise ValueError('Non-finite baseline metric')
    mid = statistics.median(values)
    mad = statistics.median(abs(x - mid) for x in values)
    width = max(3 * 1.4826 * mad, max(abs(x - mid) for x in values))
    return {'n': len(values), 'median': mid, 'mad': mad, 'low': mid - width, 'high': mid + width}


def compare_metric(value, history, *, kind='timing', direction='higher', disturbed=False,
                   rerun=None, rerun_disturbed=False):
    eligible = [h['value'] for h in history if h.get('good', True) and
                not (kind in ('timing', 'memory') and h.get('disturbed', False))]
    limits = band(eligible)
    if kind in ('timing', 'memory') and disturbed:
        return {'state': 'not-judged', 'why': 'disturbed run', 'band': limits}
    if limits is None:
        return {'state': 'baseline-only', 'samples': len(eligible[-7:])}
    worse = (lambda x: x > limits['high']) if direction == 'higher' else (lambda x: x < limits['low'])
    better = (lambda x: x < limits['low']) if direction == 'higher' else (lambda x: x > limits['high'])
    if worse(value):
        if kind in ('timing', 'memory'):
            if rerun is None:
                state = 'needs-rerun'
            elif rerun_disturbed:
                state = 'not-judged'
            elif worse(rerun):
                state = 'regression'
            else:
                state = 'unconfirmed'
        else:
            state = 'regression'
    elif better(value):
        state = 'improvement'
    else:
        state = 'within-band'
    return {'state': state, 'value': value, 'band': limits, 'rerun': rerun}


def compare_signatures(current, histories):
    if not histories:
        return []
    findings = []
    known = set().union(*(h.keys() for h in histories[-7:]))
    for sig, count in sorted(current.items()):
        if sig not in known:
            findings.append({'signature': sig, 'state': 'new-signature', 'count': count})
        else:
            limits = band([h.get(sig, 0) for h in histories[-7:]])
            if limits and count > limits['high']:
                findings.append({'signature': sig, 'state': 'count-jump', 'count': count, 'band': limits})
    return findings


def compare_tests(now, before):
    if not before:
        return {'new_failures': [], 'vanished': [], 'slower': [], 'first_run': True}
    failures = sorted(k for k, v in now.items() if v['status'] in ('FAIL', 'TIMEOUT')
                      and before.get(k, {}).get('status') not in ('FAIL', 'TIMEOUT'))
    slower = [{'name': k, 'before_s': before[k]['seconds'], 'now_s': v['seconds'],
               'delta_s': v['seconds'] - before[k]['seconds']}
              for k, v in now.items() if k in before and v['status'] == before[k]['status'] == 'pass'
              and v['seconds'] > before[k]['seconds']]
    return {'new_failures': failures, 'vanished': sorted(set(before) - set(now)),
            'slower': sorted(slower, key=lambda v: -v['delta_s'])[:10], 'first_run': False}


def image_distance(a, b):
    if len(a) != len(b) or not a:
        raise ValueError('Image features differ in size or are empty')
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)) / len(a)) / 255


def compare_image(current, history):
    """Distance to the last good image, tolerance learned from pairwise good-night distances."""
    history = list(history)[-7:]
    if len(history) < 3:
        return {'state': 'baseline-only', 'samples': len(history)}
    distances = [image_distance(history[i], history[j]) for i in range(len(history)) for j in range(i)]
    # Unlike per-night metrics all pairwise distances belong to these same 3–7 nights.
    mid = statistics.median(distances)
    mad = statistics.median(abs(x - mid) for x in distances)
    tolerance = max(max(distances), mid + 3 * 1.4826 * mad)
    distance = image_distance(current, history[-1])
    return {'state': 'regression' if distance > tolerance else 'within-band',
            'distance': distance, 'tolerance': tolerance, 'nights': len(history)}
