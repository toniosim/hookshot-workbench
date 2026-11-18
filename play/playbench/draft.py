"""The weekly draft for issue 1198 (the test player's tracker): a section written from the trend, in the form of the earlier drafts (a bold headline, plain
paragraphs, a table, `PICTURE:` lines naming the chart). It posts nothing and names no place, coordinate or flag: the cells are described by what they ask.

It says what the stored results say and no more: how many cells each arm solved on the last night and a week before, which cells flipped (only cells whose
frozen definition and arm are unchanged), which pilot commits and game builds played, what the model arms cost, and what did not count (invalid runs, partial
nights, cells that are new this week and have no earlier night to compare with).
"""
import datetime
import statistics

import board  # noqa: F401  (the cell titles)
import trend



def _parse(night):
    return datetime.datetime.strptime(night, '%Y%m%d').date()


def week_window(history, days=7):
    """(old, new): the nights of the last `days` days up to the newest night, and the newest night of the week before (or None)."""
    if not history:
        return [], None
    last = _parse(history[-1][0]['night'])
    week = [(n, c) for n, c in history if (last - _parse(n['night'])).days < days]
    earlier = [(n, c) for n, c in history if (last - _parse(n['night'])).days >= days]
    return week, (earlier[-1] if earlier else None)


def weekly(history, cells, arms, titles, chart_name='pilot-1198-scoreboard.png', days=7, issue_url='the test player tracker issue'):
    """The draft text. history: [(night row, counted)], oldest first; cells: ids in order; titles: {cell id: text}."""
    week, before = week_window(history, days)
    if not week:
        return 'No night has been scored yet.\n'
    first, last = week[0][0]['night'], week[-1][0]['night']
    n_last, c_last = week[-1]
    out = [f'**The test player scoreboard: {len(cells)} fixed tasks played every night ({first[4:6]}-{first[6:]} to {last[4:6]}-{last[6:]}, {len(week)} night(s))**', '',
           f'Update for {issue_url}. Each night the test player plays the same {len(cells)} small tasks from fixed starting saves: open a door (from its front and from the wrong side), '
           'climb a ledge, take a drop, climb a ladder, cross a crowd, open a chest, pick up items (one lies under water), play a warp song, use an item and one short chapter. '
           'A task counts as solved only when the game\'s own state shows it (a flag, a count, the map, or Link standing at the place at its height), never because the player '
           'said so. Nothing here is a frame-rate claim; every run is windowless, one game copy per lane.', '']
    head = []
    for a in arms:
        ag = trend.aggregates(c_last, a, cells)
        if not ag['run']:
            continue
        s = f"**{a}** solved {ag['solved']} of {ag['valid']} on {n_last['night'][4:6]}-{n_last['night'][6:]}"
        if before:
            bg = trend.aggregates(before[1], a, cells)
            if bg['run']:
                s += f" (a week before: {bg['solved']} of {bg['valid']})"
        head.append(s)
    out += ['; '.join(head) + '.', '']
    out += ['| task | ' + ' | '.join(arms) + ' |', '|---|' + '---|' * len(arms)]
    for c in cells:
        out.append(f'| {titles.get(c, c)} | ' + ' | '.join(trend.label(c_last.get((c, a))) for a in arms) + ' |')
    out += ['', '"ok 34 s" is solved after 34 game seconds; "fail 40%" is not solved and the best moment closed 40% of the way to the place that proves it (position tasks only); '
            '"? invalid" is a run that does not count (the save did not put Link at the start, or the hold ended it); "blocked" is a failure with a known cause outside the player (named below), left out of the count.', '']
    blocks = sorted({(c, r['blocker']) for c in cells for a in arms for r in [c_last.get((c, a))] if r and r.get('blocker') and not r['success']})
    if blocks:
        out += ['**Blocked by a known cause:** ' + '; '.join(f'{titles.get(c, c)}: {b}' for c, b in blocks) + '.', '']
    flips = []
    if before:
        for c, a, t in trend.changes(before[1], c_last, cells, arms):
            flips.append(f'{titles.get(c, c)} ({a}): {t}')
    if flips:
        out += ['**What changed since ' + before[0]['night'][4:6] + '-' + before[0]['night'][6:] + '** (same tasks, same arm): ' + '; '.join(flips) + '.', '']
    elif before:
        out += [f"**What changed since {before[0]['night'][4:6]}-{before[0]['night'][6:]}:** no solved task flipped in either direction.", '']
    else:
        out += ['**Trend:** there is no night a week older yet, so this is the first week: the numbers above are the baseline, not a trend.', '']
    ids = []
    for n, _ in week:
        ids.append((n['pilot_commit'] or '?', n['build'] or '?'))
    commits = sorted({i[0] for i in ids})
    builds = sorted({i[1] for i in ids})
    out += [f"**What played:** pilot commits {', '.join(f'`{c}`' for c in commits)}; game build {', '.join(f'`{b}`' for b in builds)}. "
            + ('The pilot changed during the week, so a change in the table can be the pilot or the game build; the chart marks the nights where either moved.'
               if len(commits) > 1 or len(builds) > 1 else 'Pilot and game build did not change during the week.'), '']
    cost = {}
    for n, c in week:
        for a in arms:
            ag = trend.aggregates(c, a, cells)
            if ag['cost_usd']:
                cost[a] = cost.get(a, 0.0) + ag['cost_usd']
    if cost:
        out += ['**Cost** over the week: ' + ', '.join(f'{a} {v:.2f} USD' for a, v in cost.items()) + ' (the pilot\'s own caps are 3 USD a run and 50 USD a night; the scoreboard keeps its own allowance below them).', '']
    notes = []
    inv = sum(1 for n, c in week for r in c.values() if not r['valid'])
    if inv:
        notes.append(f'{inv} run(s) did not count (invalid), they are kept in the results and not shown as passes or fails')
    part = [n['night'] for n, _ in week if not str(n['status']).startswith('complete')]
    if part:
        notes.append('night(s) not complete: ' + ', '.join(part))
    if notes:
        out += ['**Not counted:** ' + '; '.join(notes) + '.', '']
    out += [f'PICTURE: {chart_name} - left to right the nights; top: tasks solved per arm; middle: every task and night, green solved (game seconds to the goal in it), pink to orange not solved (how far it got), yellow does not count; bottom: stuck seconds and cost', '']
    return '\n'.join(out)
