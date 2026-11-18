#!/usr/bin/env python3
"""Placement: Link put at a place, an age and a time of day before the pilot's first decision, through hsdebug (the game's own teleport,
age switch and clock: effects read back from the game, not assumed). A segment says where in a `[place]` table:

    [place]
    to = "<a destination the game lists: a map's name or its index>"
    age = "child" | "adult"        # optional: by default the age the destination has a map for
    hour = 22                      # optional: the world clock, 0 to 23

`pilot.py run` calls `start_placed` after the game's `gameplay` event and before the first state the pilot decides from, so a roam can start
in a dungeon, a town or the field at night without a save made there. The game is the disposable run of this hold (hsdebug refuses a game
whose save folder is not inside the run's folder). Nothing here changes a file of the game or the harness.

hsdebug.py is found beside hsap.py, or at $HSDEBUG_PATH (a path to the file). It is loaded by path, so the pilot needs no install.
"""
import importlib.util
import math
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
KEYS = {'to', 'age', 'hour', 'x', 'y', 'z', 'facing'}   # x, y, z, facing: a player's coordinates (a bug report's): Link is taken there after the teleport
HSDEBUG_PATHS = (HERE.parent / 'hsdebug.py',)


class PlacementError(Exception):
    pass


def check_spec(spec):
    """The `[place]` table of a segment, or ValueError saying what is wrong."""
    if not isinstance(spec, dict):
        raise ValueError('place is a table: to = "<destination>", age, hour')
    bad = sorted(set(spec) - KEYS)
    if bad:
        raise ValueError('place: unknown keys ' + ', '.join(bad))
    if not isinstance(spec.get('to'), (str, int)) or isinstance(spec.get('to'), bool) or spec.get('to') in ('', None):
        raise ValueError('place.to: a destination the game lists (a map name or its index)')
    if spec.get('age') not in (None, 'child', 'adult'):
        raise ValueError('place.age: child or adult')
    for k in ('x', 'y', 'z', 'facing'):
        if k in spec and (isinstance(spec[k], bool) or not isinstance(spec[k], (int, float))):
            raise ValueError(f'place.{k}: a number')
    if ('x' in spec) != ('z' in spec):
        raise ValueError('place: x and z come together (y is optional)')
    h = spec.get('hour')
    if h is not None and (isinstance(h, bool) or not isinstance(h, int) or not 0 <= h <= 23):
        raise ValueError('place.hour: a whole hour, 0 to 23')
    return spec


def load_hsdebug(path=None, env=None):
    """The hsdebug module, by path ($HSDEBUG_PATH, else the file beside hsap.py)."""
    cands = [Path(p) for p in (path, (env if env is not None else os.environ).get('HSDEBUG_PATH')) if p] + list(HSDEBUG_PATHS)
    for p in cands:
        if p.is_file():
            spec = importlib.util.spec_from_file_location('hsdebug', p)
            mod = importlib.util.module_from_spec(spec)
            sys.modules.setdefault('hsdebug', mod)
            spec.loader.exec_module(mod)
            return mod
    raise PlacementError('hsdebug.py not found (looked at ' + ', '.join(str(c) for c in cands) + ')')


def apply(spec, game_run, hsdebug=None, env=None):
    """hsdebug's `setup` against the game of this run folder: {ok, seconds, steps: [brief], state, map, error}. Never raises."""
    t0 = time.monotonic()
    out = {'ok': False, 'to': spec.get('to'), 'age': spec.get('age'), 'hour': spec.get('hour'), **({'x': spec['x'], 'z': spec['z']} if 'x' in spec else {})}
    try:
        env = os.environ if env is None else env   # (the session's own env when the hold places Link: HSDEBUG_INFO, HSDEBUG_PATH)
        mod = hsdebug or load_hsdebug(env=env)
        info = env.get('HSDEBUG_INFO')   # the game-info file (hsdebug.py game-info): the hour needs it; a private path, set in the session's env
        d = mod.attach(run=str(game_run), info=info if info and Path(info).is_file() else None)
        try:
            res = d.setup(to=spec.get('to'), age=spec.get('age'), hour=spec.get('hour'))
            warp = None
            fn = next((getattr(d, n) for n in ('warp', 'warp_to') if callable(getattr(d, n, None))), None)
            if fn is not None and 'x' in spec and 'y' in spec and (res.get('ok') or any(s_.get('action') == 'time' for s_ in (res.get('steps') or []) if isinstance(s_, dict) and not s_.get('ok', True))):
                # the debug tools' coordinate warp (warp(x, y, z, facing=None) -> {ok, effect, after: {pos}}): Link is moved there and the position read back
                try:   # (a warp needs the height: without y the run walks to the point instead; the game needs the host's `!place` live-input command, else the warp is `not_applied` and the run walks; the facing is not set)
                    try:
                        w = fn(float(spec['x']), float(spec['y']), float(spec['z']), facing=spec.get('facing'))
                    except TypeError:
                        w = fn(float(spec['x']), float(spec['y']), float(spec['z']))
                    pos = ((w.get('after') or w.get('state') or {}).get('pos')) or None
                    dist = round(math.hypot(pos[0] - float(spec['x']), pos[2] - float(spec['z'])), 2) if pos else None
                    warp = {'ok': bool(w.get('ok')) and w.get('effect') in (None, 'verified'), 'effect': w.get('effect'), 'pos': pos, 'distance_m': dist}
                except Exception as e:   # noqa: BLE001  a warp that fails (the position field not found, no memory access) is not a failed placement: the run walks to the point
                    warp = {'ok': False, 'error': f'{type(e).__name__}: {str(e)[:200]}'}
        finally:
            d.close()
        raw = [s for s in res.get('steps') or [] if isinstance(s, dict)]
        if warp is not None:
            out['warp'] = warp
        out.update(ok=bool(res.get('ok')), effect=res.get('effect'), steps=[[s.get('action'), s.get('effect') or s.get('error')] for s in raw],
                   state={k: (res.get('state') or {}).get(k) for k in ('map', 'age', 'pos', 'life', 'rupees')}, map=((res.get('state') or {}).get('map')))
        if not out['ok']:
            bad = [s for s in raw if not s.get('ok', True)]
            first = bad[0] if bad else {}
            out['error'] = str(first.get('message') or first.get('error') or res.get('effect') or 'not applied')[:300]
            if bad and all(s.get('action') == 'time' for s in bad) and out['map']:   # placed and aged, only the clock could not be set: the roam goes on, and the result says so
                out.update(ok=True, partial=['time'], note='placed, but the hour was not set: ' + out.pop('error'))
    except Exception as e:   # noqa: BLE001  a placement that cannot be made is a result the hunt records, never a crash of the pilot
        out['error'] = f'{type(e).__name__}: {str(e)[:300]}'
    out['seconds'] = round(time.monotonic() - t0, 1)
    return out


def start_placed(spec, ch, game_run, alive, apply_fn=None, fresh_s=30.0):
    """After `gameplay`: place Link, then the first state event the pilot should decide from (one that came after the placement, the
    steps' own `wait` forcing it). Returns (state event or None, the placement's result). None for the state: the placement failed or no
    fresh state came (the result says which)."""
    placed = (apply_fn or apply)(spec, game_run)
    if not placed.get('ok'):
        return None, placed
    n = ch.send(['wait 0.5'])[0]
    ch.wait(lambda e: e.get('ev') == 'step' and e.get('in') == n, fresh_s, alive)
    st = ch.wait(lambda e: e.get('ev') == 'state' and e.get('why') == 'wait', fresh_s, alive)
    if st is None:
        placed['ok'], placed['error'] = False, 'no state line after the placement'
    else:
        placed['area_after'] = st.get('area')
        want = (placed.get('map') or '').lower()
        if want and (st.get('area') or '').lower() != want:
            placed['note'] = f'the first state after it says area {st.get("area")}, the placement says {placed.get("map")}'
    return st, placed
