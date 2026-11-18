#!/usr/bin/env python3
"""hsap: the pilot's game side for LS. Runs one game through hs-run.sh (GPU gate, headless) and plays steps on it:
inputs and Link's state through HOS_CONTROL (protocol 1, including the oot subscription). Only debug commands such as
!cheat 996 and !shots still use HOS_INPUT_LIVE. Steps are appended to <live>/steps.txt; events go to <live>/out.jsonl.
Received snapshots are normalized for the local pilot and journalled in <live>/state.jsonl, not read from that file.

    hsap.py <copy> <tag> <wall seconds> --live <dir> [--save <game user folder>] [--boot newgame|continue|none]
            [--shots <presents>] [--analog] [--opponent <file>] [--reconnect-wait <s>] [--hud on|off]
            [--game-sock <control socket> --game-live <live input file> --game-log <log> --game-pid <pid>]

Events written: gameplay (the first state with Link in control), step (in = the step's line in steps.txt, src, result,
secs, moved, detail), state (why wait after each step, why report every `report` seconds), bad (a line not understood),
note, done.
Steps (one a line; # starts a note):
  watch <flag> ...            flags to subscribe to (read before the game starts); later lines are kept too
  walk|run <x> <z> [radius] [timeout]   to that ground point, steered each sample; reached / stuck / timeout /
                              held (an event holds Link 0.6 s); --analog / HSAP_ANALOG=1: exact stick angles
  press <buttons> [ms]        one timed press (A, ZL+R, LUP ...); done once the bridge says it ended
  stick <dir> <ms>            hold the left stick (up, down, left, right, up-left ...) relative to the camera; done
  push <lx> <ly> <ms>         the left stick at those values (-32767..32767, y up); done
  raw <presses> <s>           a socket sequence in hos units (e.g. 0:LUP/1200,0.6:X/100), then wait s seconds; done
  until flag <name><op><value> [timeout <s>] [press <button> every <s>]   met / timeout
  until area <name> [timeout <s>] [press ...]; until prompt=<text> ...; until control [timeout <s>]
  wait <s>                    done
  save [timeout <s>]          the game's own autosave (!cheat 996): done once progress.sav is written, else timeout
  report <s>                  a state line every s seconds (0: off)
  shot                        a picture of the next present (!shots), done
  duel ready | duel cancel    writes !duel ready / !duel cancel to the live input; done, or refused when the game's log
                              says `Ready refused` within half a second
  swing                       press Y 120 ms; done
  shield [ms]                 hold ZL (default 700, 50..5000); done
  roll <dir>                  the left stick plus A (a roll): dir is a stick direction as for `stick` (camera relative) or
                              toward | away | around-left | around-right (relative to the opponent); done
  sidestep <left|right> <ms>  the left stick pushed perpendicular to the opponent's bearing (left or right of the line
                              from Link to him, as Link faces him); done
  face [degrees]              short stick pushes toward the opponent until Link faces him within the tolerance (default
                              20 degrees, four pushes at most); done / timeout
  approach <m> [timeout <s>]  walk toward the opponent until within m metres (his place is read again at each fresh
                              sample); reached / stuck / timeout / held / cut / no-opponent
  interact [force] [timeout <s>]   A at the prompt, the text it opens advanced (A every 1.2 s; a scene waited out), then what
                              (default 14 s; chest 30 s and talk 45 s: the game's messages take 20 to 40 s at 30 frames a second)
                              changed: done / none / no-prompt (the prompt reads Empty: nothing sent; force presses anyway) /
                              timeout. chest: opened / none / no-prompt / timeout. talk: talked / open (text still open at
                              the timeout) / none / no-prompt. Every one of them puts `changes` in its step event: rupees, life,
                              map, prompt [before, after], flags (watched), hashes (the change scan's, clocks left out), text
                              (closed|open), scene
  advance [timeout <s>]       A every 1.2 s while a text box holds Link: closed / none (no text open: nothing sent) / timeout
  pickup <x> <z> [radius <r>] [timeout <s>] [press] [dive <s>]   walk onto the spot (a rupee is taken by touching it), advance a text
                              that opens, `press` also presses A at a prompt there, `dive` holds A for that long when the walk reached the spot
                              and nothing changed (a rupee on a pond's floor: the HUD says `Dive (Hold)`): picked / none / stuck / timeout / held / cut
  enter <x> <z> [through <x> <z>] [timeout <s>]   walk to a door or load zone, press A at its prompt, walk on through: entered
                              (the map changed, control is back) / opened (through, same map) / blocked / timeout
  faceat <x> <z> [degrees]    short stick pushes until Link faces the point (default 20 degrees): done / timeout
  ztarget [ms]                hold ZL (default 1200): targeted (the camera or Link turned 4 degrees or more) / none
  camera <left|right|up|down> [ms] | camera to <yaw> [tolerance]   the right stick: turned / none (the yaw before and after)
  ocarina <note> ... [hold <ms>] [gap <ms>] [ready <ms>] | ocarina out | ocarina away   D-pad Left takes the ocarina out (the game's log says
                              `oc: the note wait turned on`; first it waits until Link is free: a song's playback holds him and a D-pad Left sent
                              into it is lost); the window then warms up for `ready` ms (default 3000) from that line, since a window opened a
                              moment ago ignores its first note; the notes (L R A Y X, the game's own note buttons) go out as ONE timed sequence,
                              each held 100 ms and starting 250 ms after the one before by default (what the game took a song at);
                              then up to 4 s for the game to close its note wait itself: played (it did: a song was taken, the step waits for
                              Link to be free again) / no-song (it did not: B puts the ocarina away) / out / away / no-ocarina (no note wait in
                              3.5 s, or Link held 25 s)
  item [button] [ms]          press the item button (default ZR, 150 ms) and report what changed: used / none
  rendezvous <name> [timeout <s>]   two players meet: each writes $HSAP_RENDEZVOUS/<name>.$HSAP_SIDE, waits for another file,
                              and both go 1.5 s after the later one's time (one wall clock): met / timeout / alone (no folder)
Movement, combat and shop steps (hsap_actions.py; each one's result is proven by the state and its measurement is in `changes`; held while
an event or a load holds Link, cut if the game ends):
  jump <x> <z> [radius <r>] [y <y>] [lead <m>] [hold <ms>] [timeout <s>]   face the point (15 degrees), `lead` m straight back and
                              run up, then one raw sequence: the stick toward the point `hold` ms (default 800, 400..3000) with X
                              150 ms in; wait for y to settle: landed (within radius 1.2 m or past the point along the line from the
                              start, under max(radius, 2) m off it, `passed` in the detail; and y within 1.2 m of `y`, else not over
                              1.5 m down) / short (closer, not within) / fell (over 2.5 m down) / none; changes pos, dy, moved
  climb up|down [timeout <s>] up: the old climb (done / stuck / timeout); down: the stick down, done once over 1 m was dropped; dy
  swim <x> <z> [radius <r>] [timeout <s>]   a walk in water: swam (y at start and end in the detail) / stuck / timeout / held / cut
  dive [ms] [timeout <s>]     hold A (default 1500, 200..8000) with the stick still: dived (y fell 0.4 m below its start) / none;
                              changes dy, min_y (the game's own depth flag is a constant: no proof)
  block push|pull [m] [timeout <s>]   hold A while the stick pushes along (pull: against) his facing until m metres (default 2,
                              0.3..10) or the timeout (10 s): pushed / pulled (0.5 m along the line, facing within 25 degrees) /
                              none; changes along, facing [before, after], facing_drift
  strafe left|right [ms]      hold ZL (default 1200, 300..5000) with the stick sideways: strafed (0.5 m sideways, facing within 25
                              degrees) / circled (facing turned 25 degrees toward the centre) / none; changes perp_m, facing_change
  guard [ms]                  hold ZL (default 700, 50..5000): guarded (life did not drop to 0.6 s after) / hurt; changes life
  roll to <x> <z>             the stick toward the point, A 50 ms later: rolled (1 m in 0.8 s toward it) / none
  use [button] [at <x> <z>] [lock] [hold <ms>]   the item button (default ZR; hold 150 ms, 50..3000): `at` faces the point first,
                              `lock` holds ZL from 0.4 s before to 0.6 s after: used (a watched flag, rupees, life, prompt or a
                              change-scan hash changed, or camera/facing turned 4 degrees: changes aimed) / none
  buy [timeout <s>]           A at the prompt, the text advanced (a question left open 3 s is answered with A): bought (rupees fell,
                              changes rupees) / none / no-prompt / timeout (default 45 s)
  choose up|down [n]          the stick up or down n times (1..6, 120 ms, 0.3 s apart) then A: done
  ride <x> <z> [radius <r>] [fast <mps>] [timeout <s>]   a walk on horseback: ridden (reached, ground speed over some 1 s window at
                              least fast, default 6.5) / walked / the walk's words; changes speed_max, speed_mean
walk and run also take `mag <0..1>` (a cap on the stick's push), `noise <degrees>` and `seed <n>` (a hand on the stick: the angle
wanders by that many degrees, the push by 5 percent; the same seed the same hand; none: as before).
  end                         stop the game (an external game is left alone: only hsap ends), write done
The opponent is the place in the --opponent file ({x, y, z, map, w} the runner keeps; see pilot.py's follow targets). The
duel steps need it except swing, shield, `duel ...` and a roll with a camera-relative direction. State lines gain `duel`
(the game's own `coop: duel:` log lines, tailed: state, round, score, hearts in quarter hearts, own and opponent's, self
index, ready flags, last swing and the counts by result, a refusal and the run of refusals since the last countdown, and
the matches that ended, each counted once by its id: matches_ended, matches_won, matches_lost, match_results) once such a line
was seen, and `opponent` (distance,
bearing, rel_deg relative to Link's facing, positive to his left, where, dy, the file's age) when the file is usable.
A game that restarts itself (execve into a temporary save copy: same process, the control socket replaced at the same
path) is waited for up to --reconnect-wait seconds (default 180, 0: die as before), subscribed again, and booted to play.
Game data never leaves this machine; everything goes under the run's folders.
External game (--game-sock, --game-live, --game-log, --game-pid, all four; the duel session's two games): hsap starts no game
(no hs-run.sh, no gate): it connects to that control socket as an additional client (and again when the game replaces it), tails
that log from its start, appends `duel ready` lines to that live file (never truncated), and counts the game as alive while the
pid exists (a zombie is gone). `wall` bounds hsap's own life. `end`, the wall time, or the game's exit ends hsap (exit 0) and
never stops, signals or kills the game. --boot defaults to none; --save and --shots do not apply.

The panel (the pilot's decisions on the game's own screen). The pilot (pilot/pilot.py, --hud on|off) writes the panel's text to
<live>/hud.txt: plain ASCII, lines separated by newlines (at most 14 lines of 56 characters), the file replaced whole by a rename;
an empty or absent file means nothing to show. hsap looks at that file about every 0.1 s and sends its text with the bridge's `overlay`
command ({"cmd":"overlay","text":...,"seconds":60}) when it changed (at most four requests a second: the latest text wins and nothing
is queued), again every 25 s while it stays the same (the game drops a panel 60 s after the last request), `overlay_clear` when the
file is emptied or removed and at the end of the run (the game also clears it when this connection closes), and again after a game
restart. Replies are only read for their error codes, never waited for: no step and no decision waits on the panel. `unavailable` (no
renderer hook) or `unknown_cmd` (an older build) stops the panel for the rest of the run, noted once in out.jsonl, and nothing else
about the run changes; another refusal (bad_request, ...) is noted once, that text is not sent again and the next one is tried.
--hud off or HSAP_HUD=0 (either one) turns all of it off: nothing is sent and the game's environment is as it was. With the panel on
(the default), a game hsap starts itself is given RX_VK_SHOT_MENU=1: its periodic pictures (--shots) then carry the panel, while the
bridge's `shot` (the pilot's eyes use it) never does. An external game (--game-sock) is never started or changed by hsap: it gets the
panel over the control socket, and whether its pictures show it is up to how it was started.
"""
import argparse
import collections
import errno
import json
import math
import os
import random
import re
import select
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_root if (_root / 'hs_names.py').is_file() else _root / 'harness'))
sys.path.insert(0, str(Path(__file__).resolve().parent))   # (python3 -I implies -P: the script's own folder is not on the path, and hsap_actions lives beside it)
from hs_names import GAME_EXECUTABLES, log_path
import hsap_actions
from hsap_actions import ACTION_VERBS, ActionSteps, plays
import hsap_items
from hsap_items import ITEM_VERBS, ItemSteps

HS_RUN = '/home/tonesi/Games/.hookshot-harness/hs-run.sh'
SLOT_VARS = ('HSGATE_SLOT_DIR', 'HSGATE_INTEL_SLOT_DIR', 'HSGATE_SLOT_TEST', 'HSGATE_SLOT_NODESKTOP', 'HSGATE_IN_GATE')
PROMPT_HASH = '0x9824206c'
# The left stick's eight directions: (angle from "away from the camera", positive toward the right, degrees) -> presses
DIRS = [(0, 'LUP'), (45, 'LUP+LRIGHT'), (90, 'LRIGHT'), (135, 'LDOWN+LRIGHT'), (180, 'LDOWN'), (-135, 'LDOWN+LLEFT'),
        (-90, 'LLEFT'), (-45, 'LUP+LLEFT')]
NAMED_DIRS = {'up': 'LUP', 'down': 'LDOWN', 'left': 'LLEFT', 'right': 'LRIGHT', 'up-left': 'LUP+LLEFT',
              'up-right': 'LUP+LRIGHT', 'down-left': 'LDOWN+LLEFT', 'down-right': 'LDOWN+LRIGHT'}

EMPTY_PROMPTS = (None, '', 'Empty')   # what the sample's `prompt` says when the A button does nothing here (the game's own word)
BUTTON_NAMES = ('A', 'B', 'X', 'Y', 'L', 'R', 'ZL', 'ZR', 'PLUS', 'MINUS', 'LS', 'RS', 'LEFT', 'UP', 'RIGHT', 'DOWN')
NOTE_BUTTONS = ('L', 'R', 'A', 'Y', 'X')   # the ocarina's five note buttons (while it waits for a note); D-pad Left takes it out
INTERACT_VERBS = ('interact', 'chest', 'talk', 'advance', 'pickup', 'enter', 'ztarget', 'camera', 'faceat', 'ocarina', 'item',
                  'rendezvous') + ACTION_VERBS + ITEM_VERBS   # (`climb` and `roll`: only the forms plays() names; the old forms are handled before)
CAMERA_KEYS = {'left': 'RLEFT', 'right': 'RRIGHT', 'up': 'RUP', 'down': 'RDOWN'}
HUD_CMDS = ('overlay', 'overlay_clear')   # the control bridge's panel commands


def hud_wanted(arg=None, environ=None):
    """Whether the panel is on: yes, unless --hud off or HSAP_HUD=0 (either one turns it off)."""
    environ = os.environ if environ is None else environ
    return arg != 'off' and environ.get('HSAP_HUD') != '0'


def prompt_empty(prompt):
    return prompt in EMPTY_PROMPTS


def scene_music(st):
    """A cutscene plays its own music (named Dm_...): it needs no input."""
    return (st.get('music') or '').startswith('Dm_')


def text_open(st):
    """An event holds Link and it is no cutscene: a text box (a talk, a sign, a chest's message)."""
    return st.get('event') == 1 and not scene_music(st)


def split_opts(words, flags=(), keys=()):
    """(positional words, {key: value}, {flags}) of a step's words: `key value` pairs and bare flag words are taken out."""
    pos, kv, fl, i = [], {}, set(), 0
    while i < len(words):
        w = words[i]
        if w in flags:
            fl.add(w)
            i += 1
        elif w in keys:
            if i + 1 >= len(words):
                raise ValueError(f'{w} needs a value')
            kv[w] = words[i + 1]
            i += 2
        else:
            pos.append(w)
            i += 1
    return pos, kv, fl


def seconds_of(kv, default, key='timeout'):
    value = float(kv.get(key, default))
    if not 0 < value <= 3600:
        raise ValueError(f'{key} must be above 0 and at most 3600 seconds')
    return value


def describe_changes(ch):
    """What a step changed, in words (the structured form is the step event's `changes`)."""
    parts = [f'{k} {ch[k][0]} -> {ch[k][1]}' for k in ('rupees', 'life', 'max_life', 'map', 'prompt', 'camera', 'facing') if k in ch]
    parts += [f'flag {n} {a} -> {b}' for n, (a, b) in (ch.get('flags') or {}).items()]
    if ch.get('hashes'):
        parts.append(f"{len(ch['hashes'])} changed flag hash(es): " +
                     ' '.join(f'{k}={v}' for k, v in list(ch['hashes'].items())[:6]))
    if 'text' in ch:
        parts.append('text ' + ch['text'])
    if ch.get('scene'):
        parts.append('a scene played')
    return '; '.join(parts) or 'nothing changed'


class HandNoise:
    """A hand on the stick: an angle error (degrees, sigma) that wanders, a new value every 0.25 to 0.5 s with a linear blend
    between them, and a push that varies within 5 percent. From random.Random(seed): the same seed is the same hand."""
    def __init__(self, sigma, seed=0):
        self.sigma, self.rng = float(sigma), random.Random(seed)
        self.t0 = self.t1 = None
        self.a0 = self.a1 = 0.0
        self.m0 = self.m1 = 1.0

    def knot(self):
        return self.rng.gauss(0.0, self.sigma), 1.0 + self.rng.uniform(-0.05, 0.05)

    def at(self, now):
        """(angle error in degrees, push factor) at `now` seconds (only ever increasing)."""
        if self.t0 is None:
            self.t0, (self.a0, self.m0) = now, self.knot()
            self.t1, (self.a1, self.m1) = now + self.rng.uniform(0.25, 0.5), self.knot()
        while now >= self.t1:
            self.t0, self.a0, self.m0 = self.t1, self.a1, self.m1
            self.t1, (self.a1, self.m1) = self.t0 + self.rng.uniform(0.25, 0.5), self.knot()
        f = (now - self.t0) / (self.t1 - self.t0)
        return self.a0 + (self.a1 - self.a0) * f, self.m0 + (self.m1 - self.m0) * f


def wrap(d):
    return (d + 180.0) % 360.0 - 180.0


def yaw_of(dx, dz):
    return math.degrees(math.atan2(dx, dz))


def valid_flag(name):
    return bool(re.fullmatch(r'[A-Za-z0-9_.]{1,47}', name) and
                (not name.startswith('0x') or re.fullmatch(r'0x[0-9a-fA-F]{8}', name)))


class ControlError(RuntimeError):
    pass


# ---- the duel: the game's own log lines and the opponent's place (docs/coop.md; reports/PvpNative.md 2.4)

DUEL_PREFIX = 'coop: duel: '
_NUM = r'-?\d+(?:\.\d+)?'
_DUEL_STATE = re.compile(
    r'coop: duel: state (?P<state>.+?) match (?P<match>\S+) round (?P<round>\d+) score (?P<s0>\d+)-(?P<s1>\d+) '
    r'hearts (?P<q0>-?\d+)/(?P<q1>-?\d+) self (?P<self>[01]) ready (?P<ready>\d\d)(?: reason ?(?P<reason>.*))?$')
_DUEL_SWING = re.compile(
    r'coop: duel: swing member (?P<member>\d+) id (?P<id>\d+) node (?P<node>\S+) frame (?P<frame>' + _NUM + r') '
    r'dist (?P<dist>' + _NUM + r') bearing (?P<bearing>' + _NUM + r') dy (?P<dy>' + _NUM + r') '
    r'result (?P<result>[a-z]+) native (?P<native>-?\d+) amount (?P<amount>-?\d+) self_hearts (?P<self_hearts>-?\d+)')
_DUEL_REFUSED = re.compile(r'coop: duel: (?P<text>Ready refused.*)$')


def parse_duel_line(line):
    """One `coop: duel:` line of the game's log as a dict, or None for any other line. kind state (state, match, round,
    score [s0, s1], hearts [q0, q1] in quarter hearts, self 0|1, ready [r0, r1], reason), swing (member, id, node, frame,
    dist, bearing, dy, result, native, amount, self_hearts), refused (text: the diagnostic `Ready refused: ...`) or note
    (any other duel line, text kept)."""
    i = line.find(DUEL_PREFIX)
    if i < 0:
        return None
    body = line[i:].rstrip()
    m = _DUEL_STATE.search(body)
    if m:
        g = m.groupdict()
        return {'kind': 'state', 'state': g['state'], 'match': g['match'], 'round': int(g['round']),
                'score': [int(g['s0']), int(g['s1'])], 'hearts': [int(g['q0']), int(g['q1'])], 'self': int(g['self']),
                'ready': [int(g['ready'][0]), int(g['ready'][1])], 'reason': (g['reason'] or '').strip()}
    m = _DUEL_SWING.search(body)
    if m:
        g = m.groupdict()
        return {'kind': 'swing', 'member': int(g['member']), 'id': int(g['id']), 'node': g['node'],
                'frame': float(g['frame']), 'dist': float(g['dist']), 'bearing': float(g['bearing']),
                'dy': float(g['dy']), 'result': g['result'], 'native': int(g['native']), 'amount': int(g['amount']),
                'self_hearts': int(g['self_hearts'])}
    m = _DUEL_REFUSED.search(body)
    if m:
        return {'kind': 'refused', 'text': m.group('text').strip()}
    return {'kind': 'note', 'text': body[len(DUEL_PREFIX):]}


class DuelTracker:
    """The duel as this game's own log tells it. feed() takes log lines (with the game's time t when they were read),
    snapshot() the dict the pilot's state line carries, None until a duel line was seen. It remembers every match that
    ended (by its id: a repeated `state Match ended` line of the same match counts once) so that a series of matches can be
    counted."""
    SWING_KEYS = ('member', 'id', 'node', 'frame', 'dist', 'bearing', 'dy', 'result', 'native', 'amount', 'self_hearts')

    def __init__(self):
        self.seq = 0
        self.st, self.state_since = None, None
        self.last_swing = None
        self.counts = {}          # swing result -> how many
        self.refused, self.refusals = None, 0
        self.refusal_run = 0      # Ready refusals since the last Countdown or Duel state (consecutive failures to start)
        self.ended = {}           # match id -> {id, own_score, opp_score, won, t} of each `Match ended`, in order

    def feed(self, line, t=None):
        item = parse_duel_line(line)
        if item is None:
            return None
        self.seq += 1
        item['t'] = t
        if item['kind'] == 'state':
            if self.st is None or self.st['state'] != item['state']:
                self.state_since = t
            self.st = item
            if item['state'] in ('Countdown', 'Duel'):
                self.refused, self.refusal_run = None, 0
            if item['state'] == 'Match ended' and item['match'] not in self.ended:
                me, score = item['self'], item['score']
                own, opp = score[me], score[1 - me]
                self.ended[item['match']] = {'id': item['match'], 'own_score': own, 'opp_score': opp,
                                             'won': own > opp if own != opp else None, 't': t}
        elif item['kind'] == 'swing':
            self.last_swing = item
            self.counts[item['result']] = self.counts.get(item['result'], 0) + 1
        elif item['kind'] == 'refused':
            self.refused, self.refusals, self.refusal_run = item['text'], self.refusals + 1, self.refusal_run + 1
        return item

    def snapshot(self, now=None):
        if not self.seq:
            return None
        s = self.st or {}
        me = s.get('self')
        mine = (lambda a: a[me] if a and me in (0, 1) else None)
        theirs = (lambda a: a[1 - me] if a and me in (0, 1) else None)
        swing = None
        if self.last_swing:
            swing = {k: self.last_swing[k] for k in self.SWING_KEYS}
            t = self.last_swing.get('t')
            swing['age_s'] = round(now - t, 2) if now is not None and t is not None else None
        since = s.get('state') and self.state_since is not None and now is not None
        return {'state': s.get('state'), 'match': s.get('match'), 'round': s.get('round'), 'score': s.get('score'),
                'hearts': s.get('hearts'), 'self': me, 'ready': s.get('ready'), 'reason': s.get('reason'),
                'own_hearts': mine(s.get('hearts')), 'opp_hearts': theirs(s.get('hearts')),
                'own_score': mine(s.get('score')), 'opp_score': theirs(s.get('score')),
                'own_ready': mine(s.get('ready')), 'opp_ready': theirs(s.get('ready')),
                'in_state_s': round(now - self.state_since, 2) if since else None,
                'last_swing': swing, 'swings': dict(self.counts), 'refused': self.refused,
                'refusals': self.refusals, 'refusal_run': self.refusal_run, 'seq': self.seq,
                'matches_ended': len(self.ended), 'matches_won': sum(m['won'] is True for m in self.ended.values()),
                'matches_lost': sum(m['won'] is False for m in self.ended.values()),
                'match_results': [{k: m[k] for k in ('id', 'own_score', 'opp_score', 'won')} for m in self.ended.values()]}


def where(rel):
    """A word for a relative bearing (degrees, positive to Link's left): ahead, ahead-left, left, behind-left, behind ..."""
    if rel is None:
        return None
    a, side = abs(rel), 'left' if rel > 0 else 'right'
    if a <= 22.5:
        return 'ahead'
    if a <= 67.5:
        return 'ahead-' + side
    if a <= 112.5:
        return side
    if a <= 157.5:
        return 'behind-' + side
    return 'behind'


def opponent_block(pos, facing, f, now=None, link_map=None):
    """The other player as the pilot's state line shows him: from Link's place pos (x, y, z) and facing (degrees, 0 along
    +z, 90 along +x) and the runner's file contents f ({x, z, y?, map?, w?}): distance_m on the ground, bearing_deg
    (the world yaw from Link to him), rel_deg = bearing - facing wrapped to -180..180 (positive: he is on Link's left),
    where, dy_m, age_s (now - w). None when f has no usable place or is on another map than Link's."""
    if not (isinstance(f, dict) and all(isinstance(f.get(k), (int, float)) for k in ('x', 'z'))):
        return None
    if link_map is not None and f.get('map') is not None and f['map'] != link_map:
        return None
    dx, dz = f['x'] - pos[0], f['z'] - pos[2]
    dist = math.hypot(dx, dz)
    bearing = yaw_of(dx, dz) if dist > 1e-6 else (facing if isinstance(facing, (int, float)) else 0.0)
    rel = wrap(bearing - facing) if isinstance(facing, (int, float)) else None
    b = {'x': round(f['x'], 2), 'z': round(f['z'], 2), 'distance_m': round(dist, 2),
         'bearing_deg': round(bearing, 1), 'rel_deg': None if rel is None else round(rel, 1), 'where': where(rel)}
    if isinstance(f.get('y'), (int, float)):
        b['y'], b['dy_m'] = round(f['y'], 2), round(f['y'] - pos[1], 2)
    if now is not None and isinstance(f.get('w'), (int, float)):
        b['age_s'] = round(now - f['w'], 2)
    return b


class ExternalGame:
    """A game somebody else started and keeps running (the duel session's two games): the control socket to connect to as an
    additional client, the live-input file the game already reads (HOS_INPUT_LIVE), its log, and its process id. hsap starts
    nothing, stops nothing and never truncates that live file; it ends itself (exit 0) on `end`, on its own wall time, or
    when the process is gone."""
    def __init__(self, sock, live, log, pid):
        self.sock, self.live, self.log, self.pid = Path(sock), Path(live), Path(log), int(pid)
        if self.pid <= 0:
            raise ValueError('the game process id must be positive')


class PidRunner:
    """Stands in for the Popen of hs-run.sh when the game is somebody else's: alive while the process exists. A zombie (a
    child of somebody who has not reaped it yet) is gone."""
    def __init__(self, pid):
        self.pid = pid

    def poll(self):
        try:
            data = Path(f'/proc/{self.pid}/stat').read_bytes()
        except OSError:
            return 0
        state = data.rsplit(b')', 1)[-1].split()[:1]   # (the command name in the stat line can hold parentheses)
        return 0 if not state or state[0] in (b'Z', b'X') else None

    def wait(self, timeout=None):
        return self.poll() or 0   # (never waits: the game is not ours to wait for)


class Tail:
    """New whole lines of a growing file. A file that was replaced or truncated (a game that starts its log again) is read
    from its start."""
    def __init__(self, path):
        self.path, self.off, self.buf, self.ident = Path(path), 0, b'', None

    def lines(self):
        try:
            with open(self.path, 'rb') as f:
                st = os.fstat(f.fileno())
                if (self.ident is not None and st.st_ino != self.ident) or st.st_size < self.off:
                    self.off, self.buf = 0, b''
                self.ident = st.st_ino
                f.seek(self.off)
                data = f.read()
        except OSError:
            return []
        self.off += len(data)
        self.buf += data
        *whole, self.buf = self.buf.split(b'\n')
        return [w.decode('utf-8', 'replace') for w in whole]


class Game:
    """One hs-run.sh run: a nonblocking control socket, debug-only live input, a state journal and the log. With `external`
    (an ExternalGame) the game is somebody else's: nothing is started, the control socket, live file, log and pid are the
    ones given, `wall` bounds hsap's own life, and stop() touches nothing of the game."""
    INPUT_CMDS = ('press', 'stick', 'sequence')

    def __init__(self, copy, tag, wall, run_dir, save=None, watch=(), shots=0, extra=(), reconnect_wait=0.0, external=None, hud=False):
        watch = list(dict.fromkeys(watch))
        if len(watch) > 64 or any(not valid_flag(name) for name in watch):
            raise ValueError('watch: at most 64 flag names (1..47 characters), or 0x followed by eight hex digits')
        self.copy, self.tag, self.dir = Path(copy), tag, Path(run_dir).resolve()
        self.dir.mkdir(parents=True, exist_ok=True)
        self.external = external
        self.live_in = external.live if external else self.dir / 'live.txt'
        self.state_path = self.dir / 'state.jsonl'
        if not external:
            self.live_in.write_text('')   # (an external game's live file is the game's: never truncated)
        self.state_out = open(self.state_path, 'w')
        self.inputs_out = open(self.dir / 'inputs.jsonl', 'w')   # every input request as sent, with the present it was sent at (bughunt's replay, the input recording)
        if external:
            self.control_dir, self.control_path = None, external.sock
        else:
            # A private, short path: a pilot's nested live directory can exceed AF_UNIX's path limit.
            self.control_dir = tempfile.TemporaryDirectory(prefix='hsap-control-')
            self.control_path = Path(self.control_dir.name) / 'control.sock'
        self.sock, self.connecting = None, False
        self.next_connect = 0.0
        self.tx, self.rx = bytearray(), bytearray()
        self.next_id, self.pending = 0, {}
        self.watch, self.reconnect_wait = watch, float(reconnect_wait)
        self.hud = None   # the panel's sender (Executor makes it), which the replies to its requests go to
        self.down, self.down_since, self.restarts = False, None, 0   # control socket lost, awaited again; how often
        self.t_resync, self.t_shift, self.t_last = False, 0.0, None   # game time stays one clock across a restart
        self.duel = DuelTracker()
        self.sub = self.request('subscribe', events=['oot'], every=6, flags=watch, changes=True)
        self.request('status')
        self.wall, self.deadline = wall, (time.monotonic() + wall) if external else None
        self.log_tail = None
        if external:
            self.R = external.log.parent
            self.cmd = ['external-game', f'sock={external.sock}', f'live={external.live}', f'log={external.log}',
                        f'pid={external.pid}']
            self.runner = PidRunner(external.pid)
            self.log_tail = Tail(external.log)   # (read from its start: the whole duel history is the ledger)
        else:
            self.R = self.copy / 'runs' / tag
            env = {k: v for k, v in os.environ.items() if k not in SLOT_VARS and k != 'OPENAI_API_KEY'}
            cmd = [HS_RUN, str(self.copy), tag, str(int(wall))]
            if os.environ.get('HSAP_WINDOW') == '1':   # a windowed run (hs-run.sh --window: only while its window-ok switch exists; HS_WINDOW_GEOMETRY sizes it)
                cmd.append('--window')
            if save:
                cmd += ['--user', str(save)]
            cmd += [f'HOS_CONTROL={self.control_path}', f'HOS_INPUT_LIVE={self.live_in}',
                    f'RX_VK_SHOT_EVERY={shots or 600}']
            if hud:   # the periodic pictures carry the panel (the bridge's `shot` does not)
                cmd.append('RX_VK_SHOT_MENU=1')
            cmd += list(extra)
            self.cmd = cmd
            with open(self.dir / 'hs-run.out', 'w') as out:
                self.runner = subprocess.Popen(cmd, stdout=out, stderr=subprocess.STDOUT,
                                               stdin=subprocess.DEVNULL, env=env, start_new_session=True)
        self.st, self.n_states = None, 0
        self.log_lines, self.log_mark = [], 0   # log_mark: where the log stood when the control socket was last lost
        self.changes = {}        # hash -> last value, from the samples' "changed"
        self.presents = 0
        self.history = collections.deque(maxlen=4000)   # (n_states, sample): what a step changed is read from the newest samples
        self.oc, self.oc_lines, self.oc_since = None, [], 0.0   # the ocarina's note wait as the game's log says it (on, off), every `oc:` line, and when it turned on

    def alive(self):
        if self.deadline is not None and time.monotonic() >= self.deadline:
            return False
        return self.runner.poll() is None

    def end_reason(self):
        """Why alive() is false: the game's end, or (an external game only) hsap's own wall time."""
        if self.deadline is not None and time.monotonic() >= self.deadline:
            return f'hsap wall time ({self.wall:g} s) is over; the game was not touched'
        return 'the game ended'

    def request(self, cmd, **args):
        """Queue a request without waiting for its reply; poll matches all outstanding ids."""
        self.next_id += 1
        rid = self.next_id
        if self.down and cmd in self.INPUT_CMDS:   # the old process's pad: an input meant for it is never sent to the new one
            return rid
        if cmd in self.INPUT_CMDS:
            self.record_input({'cmd': cmd, **{k: v for k, v in args.items() if k not in ('exclusive', 'wait')}})
        self.pending[rid] = cmd
        self.tx.extend((json.dumps({'id': rid, 'cmd': cmd, **args}, separators=(',', ':')) + '\n').encode())
        self._flush()
        return rid

    def record_input(self, row):
        """One line of <live>/inputs.jsonl: the request (press, stick or sequence, or a debug `!` line as cmd live) and `present`, the newest
        present the game has reported when it was sent. Read by pilot/bughunt.py and pilot/inputlog.py; the game side never reads it."""
        row['present'] = self.presents
        row['mono'] = round(time.monotonic(), 3)
        self.inputs_out.write(json.dumps(row, separators=(',', ':')) + '\n')
        self.inputs_out.flush()

    def _connect(self):
        if self.sock is None:
            if time.monotonic() < self.next_connect:
                return False
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.setblocking(False)
            error = sock.connect_ex(str(self.control_path))
            if error in (errno.ENOENT, errno.ECONNREFUSED, errno.EAGAIN):
                sock.close()
                self.next_connect = time.monotonic() + 0.25   # the game may still be in the GPU queue
                return False
            if error not in (0, errno.EINPROGRESS, errno.EALREADY):
                sock.close()
                raise ControlError(f'control connect: {os.strerror(error)}')
            self.sock, self.connecting = sock, error != 0
        if self.connecting:
            _, ready, failed = select.select([], [self.sock], [self.sock], 0)
            if not ready and not failed:
                return False
            error = self.sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
            if error:
                raise ControlError(f'control connect: {os.strerror(error)}')
            self.connecting = False
        return True

    def _lost(self, why):
        """The control socket ended. A game that restarts itself (execve into a temporary save copy: the same process, its
        socket replaced at the same path) is waited for: with reconnect_wait > 0 and the runner alive, what belonged to
        the old connection is dropped (waited inputs are released), the oot subscription is queued again for the next
        one and the run goes on. Otherwise the run ends, as before."""
        if self.reconnect_wait <= 0 or (not self.alive() and not self.external):   # (an external game's end is the loops' end)
            raise ControlError(why)
        if self.sock is not None:
            self.sock.close()
        self.sock, self.connecting = None, False
        self.rx.clear()
        self.tx.clear()
        self.pending.clear()
        self.st, self.restarts, self.presents = None, self.restarts + 1, 0
        self.t_resync, self.log_mark = True, len(self.log_lines)
        self.duel = DuelTracker()   # a new process has a new ledger: what the old one logged is over
        self.oc = None
        self.down, self.down_since, self.next_connect = True, time.monotonic(), 0.0
        self.sub = self.request('subscribe', events=['oot'], every=6, flags=self.watch, changes=True)
        self.request('status')

    def _check_down(self):
        if not self.down:
            return
        if not self.alive():
            if self.external:
                return   # the game is gone (or hsap's wall time is over): the loops end on alive(), not an error of ours
            raise ControlError('control connection closed and the game ended')
        if time.monotonic() - self.down_since > self.reconnect_wait:
            raise ControlError(f'control connection closed and no new socket within {self.reconnect_wait:g} s')

    def _flush(self):
        if self.sock is None or self.connecting:
            return
        while self.tx:
            try:
                n = self.sock.send(self.tx)
            except BlockingIOError:
                return
            except InterruptedError:
                continue
            except OSError as e:
                if e.errno in (errno.EPIPE, errno.ECONNRESET):
                    return self._lost(f'control send: {e}')
                raise ControlError(f'control send: {e}') from e
            if n == 0:
                return self._lost('control connection closed while sending')
            del self.tx[:n]

    def _messages(self):
        if not self._connect():
            self._check_down()
            return []
        self.down, self.down_since = False, None
        self._flush()
        if self.sock is None:
            return []
        messages = []
        # Bound each pass even if the server keeps writing: receiving never monopolizes the steering loop.
        for _ in range(16):
            try:
                data = self.sock.recv(65536)
            except BlockingIOError:
                break
            except InterruptedError:
                continue
            except OSError as e:
                if e.errno in (errno.ECONNRESET, errno.EPIPE):
                    self._lost(f'control receive: {e}')
                    break
                raise ControlError(f'control receive: {e}') from e
            if not data:
                self._lost('control connection closed')
                break
            self.rx.extend(data)
            while b'\n' in self.rx:
                line, _, rest = self.rx.partition(b'\n')
                self.rx = rest
                try:
                    message = json.loads(line)
                except (ValueError, UnicodeError) as e:
                    raise ControlError('control sent invalid JSON') from e
                if not isinstance(message, dict):
                    raise ControlError('control sent a non-object reply')
                messages.append(message)
            if len(self.rx) > 65536:
                raise ControlError('control sent an oversized partial reply')
        return messages

    @staticmethod
    def frames(ms):
        if ms <= 0:
            raise BadStep('input hold must be positive')
        return max(1, math.floor(ms * 60 / 1000 + 0.5))

    def press(self, buttons, ms=200):
        return self.request('press', buttons=buttons, frames=self.frames(ms), exclusive=True, wait=True)

    def stick(self, lx, ly, ms):
        lx, ly = max(-32767, min(32767, lx)), max(-32767, min(32767, ly))
        return self.request('stick', stick='L', x=lx / 32767, y=ly / 32767,
                            frames=self.frames(ms), exclusive=True, wait=True)

    def send(self, line):
        if line.startswith('!'):
            self.record_input({'cmd': 'live', 'line': line})
            with open(self.live_in, 'a') as f:
                f.write(line + '\n')
            return None
        return self.request('sequence', script=line, units='hos', exclusive=True, wait=True)

    def poll(self):
        """Drain socket events and replies without waiting; return only fresh Link samples, not reply presents."""
        new = []
        for message in self._messages():
            is_sample = message.get('event') == 'oot' and 'ok' not in message and message.get('sub') == self.sub
            if 'ok' in message:
                rid = message.get('id')
                cmd = self.pending.pop(rid, None)
                if cmd is None:
                    continue
                if cmd in HUD_CMDS:   # the panel's replies are read for their error codes: never an error of the run
                    if self.hud is not None:
                        self.hud.reply(rid, cmd, message)
                    continue
                if not message['ok']:
                    error, detail = message.get('error'), str(message.get('message', ''))
                    if cmd == 'subscribe' and (error in ('unknown_cmd', 'unavailable') or
                            (error == 'bad_request' and ('event' in detail.lower() or 'oot' in detail.lower()))):
                        raise ControlError("this build has no oot subscription: use hsap_file.py, or a build with "
                                           "HS #2292's control-bridge commits")
                    raise ControlError(f'control {cmd} #{rid}: {error}: {detail}')
                if cmd != 'status':
                    continue
                if message.get('protocol') != 1:
                    raise ControlError(f'control protocol {message.get("protocol")}, expected 1')
            elif not is_sample:
                continue
            self.presents = max(self.presents, message.get('frame', 0))
            game = message.get('game')
            if game is None:
                continue
            s = dict(game)
            # Both status and event envelopes date delivery; game.frame dates the retained/sample snapshot.
            if not isinstance(s.get('frame'), int):
                raise ControlError('control game snapshot has no sample frame (an oot subscription build is required)')
            s['child'] = {'child': 1, 'adult': 0}.get(s.pop('age', None))
            for field in ('event', 'loading'):
                s[field] = None if s.get(field) is None else int(s[field])
            if isinstance(s.get('t'), (int, float)):   # one clock across a restart: the new process counts from its own start
                t = s['t'] + self.t_shift
                if self.t_resync and self.t_last is not None and t < self.t_last:
                    self.t_shift += self.t_last - t
                    t = self.t_last
                self.t_resync, self.t_last, s['t'] = False, t, t
            if self.st is not None and s['frame'] < self.st['frame']:
                continue
            self.changes.update(s.get('changed') or {})
            if self.st is not None and s['frame'] == self.st['frame']:
                self.st.update(s)   # a same-frame oot event can add flags missing from status.game
                continue
            self.st = s
            self.n_states += 1
            self.history.append((self.n_states, s))
            new.append(s)
            self.state_out.write(json.dumps(s) + '\n')
        if new:
            self.state_out.flush()
        if self.log_tail is None and (log := log_path(self.R)) is not None:
            self.log_tail = Tail(log)
        if self.log_tail:
            for line in self.log_tail.lines():
                self.log_lines.append(line)
                self.duel.feed(line, (self.st or {}).get('t'))
                m2 = re.search(r'\boc: (.*)$', line)
                if m2:
                    self.oc_lines.append(m2.group(1))
                    if 'note wait turned on' in m2.group(1):
                        self.oc, self.oc_since = 'on', time.time()
                    elif 'note wait turned off' in m2.group(1):
                        self.oc = 'off'
                m = re.search(r'vk: (\d+) presents, ', line)
                if m:
                    self.presents = max(self.presents, int(m.group(1)))
        return new

    def game_pids(self):
        """The game process of this run (its --user is the run's user folder)."""
        want = str(self.R / 'user')
        out = []
        for p in os.listdir('/proc'):
            if not p.isdigit():
                continue
            try:
                cmd = (Path('/proc') / p / 'cmdline').read_bytes().split(b'\0')
            except OSError:
                continue
            if cmd and os.fsdecode(cmd[0]).rsplit('/', 1)[-1] in GAME_EXECUTABLES and want.encode() in cmd:
                out.append(int(p))
        return out

    def window(self, mark):
        """The samples that came after the one numbered `mark` (n_states then)."""
        return [s for n, s in self.history if n > mark]

    def stop(self, timeout=60):
        # Waited socket inputs are released by disconnect, even when several steering replies are outstanding.
        if self.sock is not None:
            self.sock.close()
            self.sock = None
        self.state_out.close()
        if self.external:
            return   # the game is somebody else's: nothing of it is stopped, signalled or killed
        for pid in self.game_pids():
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        try:
            self.runner.wait(timeout)
        except subprocess.TimeoutExpired:
            os.killpg(self.runner.pid, signal.SIGTERM)
            self.runner.wait()
        self.control_dir.cleanup()

    def saves(self):
        """{progress.sav path: mtime} in the run's user folder (none for an external game: its saves are not ours to report)"""
        if self.external:
            return {}
        out = {}
        for p in (self.R / 'user' / 'save').glob('*/slot_*/progress.sav'):
            try:
                out[str(p)] = p.stat().st_mtime
            except OSError:
                pass
        return out


class HudSender:
    """The panel on the game's own screen: what the pilot wrote to <live>/hud.txt (see the module docstring), sent with the control
    bridge's `overlay` command. tick() runs in every wait loop of the Executor and never waits: a request is made without waiting for its
    reply (Game.poll hands the reply to reply()), at most one in MIN_GAP_S, only while the socket is up and has nothing queued, and the
    newest text is all there is to send (no backlog). The game drops the panel LIFE_S after its last request, so an unchanged text is sent
    again every KEEPALIVE_S; it also drops it when this connection closes, so a restarted game gets the text again at once."""
    LIFE_S = 60           # `seconds` of every overlay request
    KEEPALIVE_S = 25.0    # the same text again after this long without a request
    MIN_GAP_S = 0.26      # between two requests: no second holds five (the game is told four a second at most)
    LOOK_S = 0.1          # how often the file is looked at
    MAX_BYTES = 8192      # read at most this much of it (the game takes 2048 and refuses more)

    def __init__(self, game, path, note):
        self.g, self.path, self.note = game, Path(path), note
        game.hud = self
        self.sig, self.want = None, ''   # the file as last read ((inode, mtime, size) or None) and the text it asks for
        self.sent, self.sent_at, self.last_req = None, 0.0, None   # the text the game shows as far as we know; when; the last request
        self.refused, self.off, self.closed = None, None, False    # a text the game refused; why sending stopped for good; ended
        self.asked, self.noted = {}, set()   # request id -> text of the overlay requests not yet answered; the notes made
        self.next_look, self.restarts = 0.0, game.restarts

    def look(self):
        """The file's text, when its inode, time or size changed: trailing blank lines left out, '' for an empty or absent file."""
        try:
            st = os.stat(self.path)
            sig = (st.st_ino, st.st_mtime_ns, st.st_size)
        except OSError:
            sig = None
        if sig == self.sig:
            return
        self.sig = sig
        if sig is None:
            self.want = ''
            return
        try:
            with open(self.path, 'rb') as f:
                raw = f.read(self.MAX_BYTES)
        except OSError:
            return   # (gone again: the next look finds out)
        self.want = raw.decode('utf-8', 'replace').replace('\r\n', '\n').rstrip().lstrip('\n')

    def tick(self):
        if self.off or self.closed:
            return
        now, g = time.monotonic(), self.g
        if now >= self.next_look:
            self.next_look = now + self.LOOK_S
            self.look()
        if g.restarts != self.restarts:   # a new process: the old one's panel went with its connection
            self.restarts, self.sent, self.asked = g.restarts, None, {}
        if g.sock is None or g.connecting or g.down or g.tx:
            return
        if self.last_req is not None and now - self.last_req < self.MIN_GAP_S:
            return
        if self.want:
            if self.want != self.refused and (self.want != self.sent or now - self.sent_at >= self.KEEPALIVE_S):
                self.send(now, self.want)
        elif self.sent is not None:
            self.send(now, None)

    def send(self, now, text):
        """The text as the panel, or (None) the panel cleared. Not waited for."""
        if text is None:
            self.g.request('overlay_clear')
            self.sent = None
        else:
            rid = self.g.request('overlay', text=text, seconds=self.LIFE_S)
            self.asked[rid] = text
            while len(self.asked) > 16:
                del self.asked[next(iter(self.asked))]
            self.sent, self.sent_at = text, now
            self.refused = None   # (a text the game refused is only ever skipped while it is still the newest)
        self.last_req = now

    def reply(self, rid, cmd, message):
        """The game's answer to a panel request: only an error matters. `unavailable` and `unknown_cmd` end the panel for the run;
        any other refusal is noted once per code and the refused text is not sent again."""
        text = self.asked.pop(rid, None)
        if message.get('ok'):
            return
        error, detail = str(message.get('error')), ' '.join(str(message.get('message', '')).split())[:120]
        if error in ('unavailable', 'unknown_cmd'):
            self.off = error
            self.note_once('off', f'overlay: the game answers {error} ({detail}); no panel is sent for the rest of the run, nothing else changes')
            return
        if cmd == 'overlay' and text is not None:
            self.refused = text
        self.note_once(error, f'overlay: the game refused a panel text ({error}: {detail}); that text is not sent again')

    def note_once(self, key, text):
        if key not in self.noted:
            self.noted.add(key)
            self.note(ev='note', text=text)

    def close(self):
        """The run ends: the panel is cleared while the connection still takes it (the game clears it itself when it closes). Once."""
        if self.closed:
            return
        self.closed, g = True, self.g
        if self.off or self.sent is None or g.sock is None or g.connecting or g.down:
            return
        wait = self.MIN_GAP_S - (time.monotonic() - self.last_req) if self.last_req is not None else 0.0
        try:
            if wait > 0:
                time.sleep(wait)   # (four a second at most, the clear included: the only wait the panel ever makes)
            g.request('overlay_clear')
        except (ControlError, OSError):
            pass   # (the connection is gone: the game has cleared it)
        self.sent = None


hsap_actions.bind(globals())   # (the helpers above: the steps of ActionSteps share them; hsap_actions cannot import this module back)
hsap_items.bind(globals())     # (and the item steps' too)


class Executor(ActionSteps, ItemSteps):
    def __init__(self, game, live_dir, boot, opponent_path=None, hud=False):
        self.g, self.live = game, Path(live_dir)
        self.steps_tail = Tail(self.live / 'steps.txt')
        self.out = open(self.live / 'out.jsonl', 'a')
        self.n_line, self.queue = 0, []
        self.report, self.report_next = 0.0, 0.0
        self.t0 = None
        self.last = {}
        self.boot = boot
        self.watch = []
        self.flag_values = {}
        self.sign = 1.0          # +1: the stick's right is the camera's yaw - 90 (a right-handed world, y up)
        self.mirror, self.checked = 0, 0.0
        self.ended = False
        # Exact stick angles use the bridge's analog axes; no input-script-analog build is needed.
        self.analog = os.environ.get('HSAP_ANALOG') == '1'
        self.opponent_path, self.restarts_seen = opponent_path, 0   # the runner's file with the other player's place
        self.counters, self.key_hits = set(), {}   # change-scan keys that move all the time (clocks): learned, left out of results
        self.extra = {}                            # the structured part of the running step's result (its changes)
        self.cam_sign, self.cam_rate = 1.0, 120.0  # the right stick: +1 when RRIGHT raises the camera's yaw; degrees a second
        self.hud = HudSender(game, self.live / 'hud.txt', self.emit) if hud else None   # the pilot's panel on the game's screen

    def emit(self, **e):
        self.out.write(json.dumps(e) + '\n')
        self.out.flush()

    def t(self):
        st = self.g.st or {}
        now = st.get('t') if st.get('t') is not None else self.g.t_last   # (between a restart and its first sample: the last)
        return round((now or 0) - (self.t0 or 0), 2)

    def state_event(self, why):
        st = self.g.st or {}
        music = st.get('music') or ''
        flags = dict(st.get('flags') or {})
        e = {'ev': 'state', 'why': why, 'n': self.g.n_states, 't': self.t(), 'frame': st.get('frame'),
             'pos': st.get('pos'), 'facing': st.get('facing'), 'camera': st.get('camera'), 'area': st.get('map'),
             'prompt': st.get('prompt'), 'music': st.get('music'), 'scene': music.startswith('Dm_'),
             'event': st.get('event'), 'loading': st.get('loading'), 'child': st.get('child'), 'life': st.get('life'),
             'max_life': st.get('max_life'), 'rupees': st.get('rupees'), 'last': self.last, 'flags': flags,
             'changed': sorted(self.g.changes)}
        self.g.changes = {}
        duel = self.g.duel.snapshot(st.get('t'))   # only once the game's log said something about a duel
        if duel:
            e['duel'] = duel
        if text_open(st):
            e['text'] = True   # a text box holds Link (an event with no scene music)
        if self.g.oc is not None:
            e['ocarina'] = self.g.oc   # the game's log: the ocarina's note wait is on or off
        opponent = self.opponent()
        if opponent:
            e['opponent'] = opponent
        self.emit(**e)

    def read_steps(self):
        for line in self.steps_tail.lines():
            self.n_line += 1
            s = line.split('#', 1)[0].strip()
            if s:
                self.queue.append((self.n_line, s))

    def tick(self, seconds=0.05):
        time.sleep(seconds)
        new = self.g.poll()
        self.note_changes(new)
        if self.hud is not None:
            self.hud.tick()
        if new and self.report and self.t() >= self.report_next:
            self.state_event('report')
            self.report_next = self.t() + self.report
        return new

    # ---- boot: to the first state with Link in control
    def to_control(self, limit=900, log_from=0):
        """limit counts from the game's start (its log appears), not from ours: the GPU gate's queue may hold the run for
        most of an hour first (newgame-1, 2026-11-10: hsap's limit ran out in the queue and the game never started)"""
        end = None
        calm, next_a, title_at = 0, 0.0, None
        while (end is None or time.time() < end) and self.g.alive():
            new = self.tick(0.1)
            if end is None:
                if self.g.log_tail is None:
                    continue
                end = time.time() + limit
                self.emit(ev='note', text='the game started (its log appeared)', wall=round(time.time(), 1))
            if title_at is None and any('a frame:' in l and re.search(r'a frame: (\d+) draws', l) and
                                        int(re.search(r'a frame: (\d+) draws', l).group(1)) >= 15
                                        for l in self.g.log_lines[max(log_from, len(self.g.log_lines) - 20):]):
                title_at = time.time()
                self.emit(ev='note', text='title (15 draws a frame)', wall=round(time.time(), 1))
            for s in new:
                calm = calm + 1 if s.get('map') and s.get('event') == 0 and s.get('loading') == 0 else 0
            if calm >= 30:   # three seconds at the subscription's six-present cadence
                return True
            if self.boot != 'none' and title_at and time.time() >= next_a:
                self.g.press('A', 100)
                next_a = time.time() + (0.75 if self.boot == 'newgame' else 2.0)
        return False

    # ---- steps
    def run(self):
        if not self.to_control():
            self.emit(ev='note', text='no control: ' + (self.g.end_reason() if not self.g.alive() else 'boot timeout'))
            return
        self.restarts_seen = self.g.restarts   # (a restart during this first boot is part of it)
        self.t0 = (self.g.st or {}).get('t') or 0
        self.emit(ev='gameplay', t=0.0, frame=(self.g.st or {}).get('frame'), area=(self.g.st or {}).get('map'))
        self.state_event('wait')
        while self.g.alive() and not self.ended:
            if self.g.restarts != self.restarts_seen:
                self.reboot()
                continue
            self.read_steps()
            if not self.queue:
                self.tick(0.05)
                continue
            n, src = self.queue.pop(0)
            t_start, p_start = time.time(), (self.g.st or {}).get('pos')
            self.extra = {}
            try:
                result, detail = self.step(src)
            except BadStep as e:
                self.emit(ev='bad', **{'in': n}, src=src, why=str(e))
                continue
            p_end = (self.g.st or {}).get('pos')
            moved = round(math.dist(p_start[::2], p_end[::2]), 2) if p_start and p_end else 0.0
            secs = round(time.time() - t_start, 2)
            extra, self.extra = self.extra, {}
            self.last = {'src': src, 'result': result, 'secs': secs, 'moved': moved, 'detail': detail, **extra}
            self.emit(ev='step', **{'in': n}, src=src, result=result, secs=secs, moved=moved, detail=detail,
                      pos=p_end, t=self.t(), **extra)
            self.read_steps()
            if not self.queue:
                self.state_event('wait')
        if self.hud is not None:
            self.hud.close()
        if self.g.external and not self.ended:
            self.emit(ev='note', text=self.g.end_reason())
        self.emit(ev='done', t=self.t())

    def reboot(self):
        """The game restarted itself (execve into a temporary save copy: the same process, a new control socket): its title
        again, then Link in control, before any further step."""
        self.restarts_seen = self.g.restarts
        self.emit(ev='note', text=f'the game restarted itself (the control socket was replaced, restart {self.restarts_seen}): '
                                  f'boot again', wall=round(time.time(), 1))
        if not self.to_control(log_from=self.g.log_mark):
            self.emit(ev='note', text='no control after the restart: ' +
                      (self.g.end_reason() if not self.g.alive() else 'boot timeout'))
            return
        self.restarts_seen = self.g.restarts
        self.emit(ev='gameplay', t=self.t(), frame=(self.g.st or {}).get('frame'), area=(self.g.st or {}).get('map'),
                  restart=self.restarts_seen)
        self.state_event('wait')

    def step(self, src):
        w = src.split()
        k = w[0]
        if k == 'watch':
            self.watch += w[1:]
            return 'done', 'watch lines are read before the game starts; later ones are reported only if already watched'
        if k in ('walk', 'run'):
            if len(w) < 3:
                raise BadStep('walk <x> <z> [radius <r>] [timeout <s>]')
            kw = dict(zip(w[3::2], w[4::2])) if len(w) > 3 and not w[3][0].isdigit() else {}
            radius = float(kw.get('radius', w[3] if len(w) > 3 and not kw else 1.0))
            timeout = float(kw.get('timeout', w[4] if len(w) > 4 and not kw else 30.0))
            try:
                mag = float(kw['mag']) if 'mag' in kw else None
                noise, seed = float(kw.get('noise', 0.0)), int(kw.get('seed', 0))
            except ValueError:
                raise BadStep('walk <x> <z> ... mag <0..1> noise <degrees> seed <n>: numbers') from None
            if (mag is not None and not 0.0 < mag <= 1.0) or noise < 0.0:
                raise BadStep('walk ...: mag in (0, 1], noise 0 degrees or more')
            return self.walk(float(w[1]), float(w[2]), radius, timeout, mag=mag, noise=noise, seed=seed)
        if k == 'press':
            if len(w) < 2:
                raise BadStep('press <buttons> [ms]')
            ms = int(w[2]) if len(w) > 2 else 200
            self.wait_input(self.g.press(w[1], ms))
            return 'done', ''
        if k == 'stick':
            if len(w) < 3 or w[1] not in NAMED_DIRS:
                raise BadStep('stick <up|down|left|right|up-left|...> <ms>')
            ms = int(w[2])
            names = NAMED_DIRS[w[1]].split('+')
            lx = 32767 * (('LRIGHT' in names) - ('LLEFT' in names))
            ly = 32767 * (('LUP' in names) - ('LDOWN' in names))
            self.wait_input(self.g.stick(lx, ly, ms))
            return 'done', ''
        if k == 'push':
            if len(w) < 4:
                raise BadStep('push <lx> <ly> <ms>')
            lx, ly, ms = int(w[1]), int(w[2]), int(w[3])
            self.wait_input(self.g.stick(lx, ly, ms))
            return 'done', f'stick {lx} {ly} for {ms} ms'
        if k == 'raw':    # a sequence of timed inputs; its explicit wait remains wall seconds
            if len(w) < 3:
                raise BadStep('raw <presses> <wait s>')
            self.g.send(w[1])
            self.wait(float(w[2]))
            return 'done', w[1]
        if k == 'cheat':  # cheat <n>: the debug tools' action n (!cheat: 3000+ items, 1000+ teleports, 996 save ...)
            if len(w) < 2 or not w[1].isdigit():
                raise BadStep('cheat <number>')
            mark = len(self.g.log_lines)
            self.g.send(f'!cheat {w[1]}')
            self.wait(1.5)
            said = [ln.split('cheats:', 1)[1].strip() for ln in self.g.log_lines[mark:] if 'cheats:' in ln]
            return 'done', '; '.join(said)[:300] or 'no cheats: line in the log'
        if k == 'until':
            return self.until(w[1:])
        if k == 'wait':
            self.wait(float(w[1]) if len(w) > 1 else 1.0)
            return 'done', ''
        if k == 'climb' and not plays(w):
            return self.climb(float(w[w.index('timeout') + 1]) if 'timeout' in w else 12.0)
        if k == 'save':
            return self.save(float(w[2]) if len(w) > 2 and w[1] == 'timeout' else 60.0)
        if k == 'report':
            self.report = float(w[1]) if len(w) > 1 else 0.5
            self.report_next = self.t()
            return 'done', ''
        if k == 'shot':
            self.g.send('!shots 1')
            self.wait(0.5)
            return 'done', ''
        if k == 'end':
            self.ended = True
            return 'done', ''
        if k in ('duel', 'swing', 'shield', 'roll', 'sidestep', 'face', 'approach') and not plays(w):
            try:
                return self.duel_steps(k, w)
            except ValueError as e:
                raise BadStep(f'{k}: {e}') from None
        if k in INTERACT_VERBS:
            try:
                return getattr(self, 'step_' + k.replace('-', '_'))(w[1:])
            except ValueError as e:
                raise BadStep(f'{k}: {e}') from None
        raise BadStep(f'unknown step {k}')

    def wait(self, seconds):
        end = time.time() + seconds
        while time.time() < end and self.g.alive():
            self.tick(0.05)

    def wait_input(self, rid):
        # The input's own completion is in game frames, not wall time. Events and other replies still get drained.
        while rid in self.g.pending and self.g.alive():
            self.tick(0.05)

    # ---- the duel's steps (the opponent's place comes from the --opponent file)
    ROLL_TURNS = {'toward': 0.0, 'away': 180.0, 'around-left': 90.0, 'around-right': -90.0}   # from the bearing to him

    def opponent(self):
        """The other player now, as opponent_block() makes him from the --opponent file; None without a usable place."""
        st = self.g.st or {}
        pos = st.get('pos')
        if not self.opponent_path or not pos:
            return None
        try:
            f = json.loads(Path(self.opponent_path).read_text())
        except (OSError, ValueError):
            return None
        return opponent_block(pos, st.get('facing'), f, time.time(), st.get('map'))

    def aim(self):
        """(opponent, '') for a step that needs him and the camera, else (None, why)."""
        st = self.g.st or {}
        if not st.get('pos') or st.get('camera') is None:
            return None, 'no sample of Link yet'
        opp = self.opponent()
        if opp is None:
            return None, 'no opponent: the --opponent file has no usable place (missing, unreadable or on another map)'
        return opp, ''

    def stick_at(self, yaw, mag=1.0):
        """The left stick (lx, ly) that moves Link toward the world yaw, as walk() steers: the stick's angle is the
        camera's yaw minus the wanted yaw, right positive."""
        want = wrap((self.g.st or {})['camera'] - yaw) * self.sign
        return round(mag * 32767 * math.sin(math.radians(want))), round(mag * 32767 * math.cos(math.radians(want)))

    def duel_detail(self):
        d = self.g.duel.snapshot((self.g.st or {}).get('t'))
        return f"duel {d['state']} round {d['round']} hearts {d['own_hearts']}/{d['opp_hearts']}" if d else ''

    def duel_steps(self, k, w):
        if k == 'duel':
            if len(w) != 2 or w[1] not in ('ready', 'cancel'):
                raise BadStep('duel ready | duel cancel')
            refusals = self.g.duel.refusals
            self.g.send(f'!duel {w[1]}')
            self.wait(0.5)   # (the game answers in its log within a few frames)
            if self.g.duel.refusals > refusals:
                return 'refused', self.g.duel.refused
            return 'done', self.duel_detail() or 'no duel line in the log yet'
        if k == 'swing':
            if len(w) != 1:
                raise BadStep('swing')
            self.wait_input(self.g.press('Y', 120))
            return 'done', self.duel_detail()
        if k == 'shield':
            if len(w) > 2:
                raise BadStep('shield [ms]')
            ms = int(w[1]) if len(w) == 2 else 700
            if not 50 <= ms <= 5000:
                raise BadStep('shield [ms]: 50 to 5000')
            self.wait_input(self.g.press('ZL', ms))
            return 'done', f'ZL held {ms} ms'
        if k == 'roll':
            if len(w) != 2 or (w[1] not in NAMED_DIRS and w[1] not in self.ROLL_TURNS):
                raise BadStep('roll <up|down|left|right|up-left|...|toward|away|around-left|around-right>')
            if w[1] in NAMED_DIRS:
                names = NAMED_DIRS[w[1]].split('+')
                lx, ly = 32767 * (('LRIGHT' in names) - ('LLEFT' in names)), 32767 * (('LUP' in names) - ('LDOWN' in names))
                text = f'roll {w[1]} (camera relative)'
            else:
                opp, why = self.aim()
                if opp is None:
                    return 'no-opponent', why
                lx, ly = self.stick_at(opp['bearing_deg'] + self.ROLL_TURNS[w[1]])
                text = f"roll {w[1]} the opponent at {opp['distance_m']} m"
            self.wait_input(self.g.send(f'0:LX={lx}+LY={ly}/240,0.05:A/100'))   # the stick, then A a moment later
            return 'done', text
        if k == 'sidestep':
            if len(w) != 3 or w[1] not in ('left', 'right'):
                raise BadStep('sidestep <left|right> <ms>')
            ms = int(w[2])
            if not 50 <= ms <= 3000:
                raise BadStep('sidestep <left|right> <ms>: 50 to 3000')
            opp, why = self.aim()
            if opp is None:
                return 'no-opponent', why
            lx, ly = self.stick_at(opp['bearing_deg'] + (90.0 if w[1] == 'left' else -90.0))
            self.wait_input(self.g.stick(lx, ly, ms))
            return 'done', f"{w[1]} of the line to the opponent at {opp['distance_m']} m, {ms} ms"
        if k == 'face':
            if len(w) > 2:
                raise BadStep('face [degrees]')
            return self.face(float(w[1]) if len(w) == 2 else 20.0)
        if k == 'approach':
            if len(w) not in (2, 4) or (len(w) == 4 and w[2] != 'timeout'):
                raise BadStep('approach <m> [timeout <s>]')
            radius, timeout = float(w[1]), float(w[3]) if len(w) == 4 else 20.0
            if radius <= 0:
                raise BadStep('approach <m>: m above 0')
            return self.approach(radius, timeout)
        raise BadStep(f'unknown step {k}')

    def face(self, tolerance, pushes=4):
        """Short stick pushes toward the opponent (a low push turns Link toward him) until he is within the tolerance."""
        rel = None
        for i in range(pushes + 1):
            opp, why = self.aim()
            if opp is None:
                return 'no-opponent', why
            rel = opp['rel_deg']
            if rel is None:
                return 'no-sample', 'Link has no facing in the sample'
            if abs(rel) <= tolerance:
                return 'done', f"facing the opponent within {abs(rel):.0f} degrees ({opp['distance_m']} m), {i} pushes"
            if i < pushes:
                lx, ly = self.stick_at(opp['bearing_deg'], 0.4)
                self.wait_input(self.g.stick(lx, ly, 100))
                self.wait(0.15)   # (a fresh sample to judge by)
        return 'timeout', f'still {abs(rel):.0f} degrees off the opponent after {pushes} pushes'

    def approach(self, radius, timeout):
        """walk() toward the opponent, his place read again at each fresh sample, until within radius metres."""
        seen = {'frame': None, 'at': None}

        def aim():
            frame = (self.g.st or {}).get('frame')
            if frame != seen['frame']:
                opp = self.opponent()
                seen.update(frame=frame, at=None if opp is None else (opp['x'], opp['z']))
            return seen['at']
        return self.walk(0.0, 0.0, radius, timeout, aim=aim)

    def climb(self, timeout):
        """Hold up on the stick while Link climbs (a ladder, ivy): done once he has risen over 1 m and stopped rising
        for a second, stuck if he never rose, timeout otherwise"""
        start, st = time.time(), self.g.st or {}
        y0 = top = (st.get('pos') or [0, 0, 0])[1]
        top_at = start
        while time.time() - start < timeout and self.g.alive():
            self.g.stick(0, 32767, 250)
            self.wait(0.2)
            y = ((self.g.st or {}).get('pos') or [0, y0, 0])[1]
            if y > top + 0.05:
                top, top_at = y, time.time()
            if top - y0 > 1.0 and time.time() - top_at > 1.0:
                return 'done', f'rose {top - y0:.1f} m'
            if top - y0 < 0.2 and time.time() - start > 3.0:
                return 'stuck', f'rose {top - y0:.2f} m in 3 s'
        return 'timeout', f'rose {top - y0:.1f} m in {timeout:g} s'

    # ---- interactions: A at a prompt, text, pickups, doors, the camera, the ocarina, items. Each step ends with a result
    # word and what changed (self.extra['changes'], and in words in the detail); none sends an input it was not asked for.
    def note_changes(self, new):
        """Learn which change-scan keys are clocks: a key that rose in four samples running is one (the play time moves in
        every sample); a step's result leaves those out."""
        for s in new:
            for k, v in (s.get('changed') or {}).items():
                hits, last, rising = self.key_hits.get(k, (0, None, True))
                rising = rising and isinstance(v, (int, float)) and (last is None or v > last)
                self.key_hits[k] = (hits + 1, v, rising)
                if hits + 1 >= 4 and rising:
                    self.counters.add(k)

    def fresh(self, wait=0.4):
        """The newest sample, waiting up to `wait` s for one that arrives after this call."""
        n = self.g.n_states
        end = time.time() + wait
        while self.g.n_states == n and time.time() < end and self.g.alive():
            self.tick(0.03)
        return self.g.st or {}

    def snap(self):
        st = self.g.st or {}
        out = {k: st.get(k) for k in ('map', 'pos', 'facing', 'camera', 'event', 'loading', 'life', 'max_life', 'rupees',
                                      'prompt', 'music')}
        out['flags'] = dict(st.get('flags') or {})
        return out

    def changes(self, before, after, mark):
        """What happened between two snapshots, over the samples after `mark`: the state's own values, the watched flags, the
        change scan's hashes (not the clocks), and how text and a scene went (`text` closed or open at the end)."""
        out = {k: [before.get(k), after.get(k)] for k in ('rupees', 'life', 'max_life', 'map', 'prompt')
               if before.get(k) != after.get(k)}
        flags = {n: [before['flags'].get(n), after['flags'].get(n)] for n in sorted(set(before['flags']) | set(after['flags']))
                 if before['flags'].get(n) != after['flags'].get(n)}
        if flags:
            out['flags'] = flags
        window = self.g.window(mark)
        hashes = {}
        for s in window:
            for k, v in (s.get('changed') or {}).items():
                if k not in self.counters:
                    hashes[k] = v
        if hashes:
            out['hashes'] = hashes
        texts = [text_open(s) for s in window]
        if any(texts) or text_open(before):
            out['text'] = 'open' if (texts[-1] if texts else text_open(before)) else 'closed'
        if any(scene_music(s) and s.get('event') == 1 for s in window):
            out['scene'] = True
        return out

    def outcome(self, result, ch, said=''):
        """The step's (result, detail), its changes kept for the step event."""
        if ch:
            self.extra['changes'] = ch
        return result, '; '.join(x for x in (said, describe_changes(ch)) if x)

    def advance_text(self, deadline):
        """A every 1.2 s while a text box holds Link; a scene (its own music) is waited out without input, except that one
        which has held Link over 8 s gets an A every 3 s (a message inside a scene waits for A too). (closed, presses):
        closed once Link has been free for 0.6 s, False at the deadline."""
        presses, calm, next_press, scene_since = 0, None, time.time() + 0.8, None
        while self.g.alive():
            if self.g.oc == 'on':   # a note wait is no text: A there is a note
                return False, presses
            st, now = self.g.st or {}, time.time()
            if now >= deadline:
                return False, presses
            if text_open(st):
                calm, scene_since = None, None
                if now >= next_press:
                    self.wait_input(self.g.press('A', 100))
                    presses += 1
                    next_press = time.time() + 1.2
            elif st.get('event') == 1 or st.get('loading') == 1:   # a scene, a load
                calm = None
                if st.get('event') == 1:
                    scene_since = scene_since or now
                    if now - scene_since > 8.0 and now >= next_press:
                        self.wait_input(self.g.press('A', 100))
                        presses += 1
                        next_press = time.time() + 3.0
            else:
                calm, scene_since = calm or now, None
                if now - calm >= 0.6:
                    return True, presses
            self.tick(0.05)
        return False, presses

    EVIDENCE = ('rupees', 'life', 'max_life', 'map', 'flags', 'hashes', 'text', 'scene')

    def act(self, timeout, force):
        """A at the prompt, then the text it opens advanced until Link is free: (changes, closed, prompt), changes None when
        nothing was sent (no prompt, no force). A text already open is only advanced."""
        st = self.fresh()
        before, mark = self.snap(), self.g.n_states
        if not text_open(st) and not (scene_music(st) and st.get('event') == 1):
            if prompt_empty(st.get('prompt')) and not force:
                return None, False, st.get('prompt')
            self.wait_input(self.g.press('A', 100))
            react = time.time() + 2.5
            while time.time() < react and self.g.alive() and not (self.g.st or {}).get('event'):
                self.tick(0.05)
        closed, _ = self.advance_text(time.time() + timeout)
        self.wait(0.6)   # (the counters and flags settle)
        if not closed:   # (the deadline can fall inside the 0.6 s Link must be free before the text counts as closed: the settle is that time)
            now = self.g.st or {}
            closed = not text_open(now) and now.get('event') != 1 and now.get('loading') != 1
        return self.changes(before, self.snap(), mark), closed, st.get('prompt')

    def no_prompt(self, prompt):
        return 'no-prompt', f'the A prompt reads {prompt!r}: nothing was sent (force sends A anyway)'

    def step_interact(self, args):
        pos, kv, fl = split_opts(args, flags=('force',), keys=('timeout',))
        if pos:
            raise ValueError('interact [force] [timeout <s>]')
        ch, closed, prompt = self.act(seconds_of(kv, 14.0), 'force' in fl)
        if ch is None:
            return self.no_prompt(prompt)
        done = any(k in ch for k in self.EVIDENCE + ('prompt',))
        return self.outcome('timeout' if not closed else 'done' if done else 'none', ch)

    def step_chest(self, args):
        pos, kv, fl = split_opts(args, flags=('force',), keys=('timeout',))
        if pos:
            raise ValueError('chest [force] [timeout <s>]')
        ch, closed, prompt = self.act(seconds_of(kv, 30.0), 'force' in fl)
        if ch is None:
            return self.no_prompt(prompt)
        done = any(k in ch for k in self.EVIDENCE + ('prompt',))
        return self.outcome('none' if not done else 'opened' if closed else 'timeout', ch)

    def step_talk(self, args):
        pos, kv, fl = split_opts(args, flags=('force',), keys=('timeout',))
        if pos:
            raise ValueError('talk [force] [timeout <s>]')
        ch, closed, prompt = self.act(seconds_of(kv, 45.0), 'force' in fl)
        if ch is None:
            return self.no_prompt(prompt)
        done = any(k in ch for k in self.EVIDENCE)
        return self.outcome('none' if not done else 'talked' if closed else 'open', ch)

    def step_advance(self, args):
        pos, kv, _ = split_opts(args, keys=('timeout',))
        if pos:
            raise ValueError('advance [timeout <s>]')
        st = self.fresh()
        if self.g.oc == 'on':   # the note wait holds Link like a text box, but A is a note there: nothing is sent (`ocarina away` puts it back)
            return 'none', 'the ocarina waits for a note: A would play one, nothing was sent (ocarina away puts it back)'
        before, mark = self.snap(), self.g.n_states
        opened = text_open(st) or st.get('event') == 1
        closed, presses = self.advance_text(time.time() + seconds_of(kv, 20.0))
        ch = self.changes(before, self.snap(), mark)
        if not opened and not any(k in ch for k in ('text', 'scene')):
            return 'none', 'no text was open: nothing was sent'
        return self.outcome('closed' if closed else 'timeout', ch, f'{presses} A presses')

    def step_pickup(self, args):
        pos, kv, fl = split_opts(args, flags=('press',), keys=('radius', 'timeout', 'dive'))
        if len(pos) != 2:
            raise ValueError('pickup <x> <z> [radius <r>] [timeout <s>] [press] [dive <s>]')
        x, z, radius = float(pos[0]), float(pos[1]), float(kv.get('radius', 0.35))
        if radius <= 0:
            raise ValueError('radius must be above 0')
        timeout = seconds_of(kv, 20.0)
        dive = None
        if 'dive' in kv:   # the item lies on a pond's floor (the HUD says `Dive (Hold)` on A): hold A over it
            dive = float(kv['dive'])
            if not 0.5 <= dive <= 8.0:
                raise ValueError('dive <s>: 0.5 to 8 seconds')
        self.fresh()
        before, mark = self.snap(), self.g.n_states
        result, detail = self.walk(x, z, radius, timeout)
        if result in ('reached', 'held', 'stuck', 'timeout'):
            self.wait(0.8)   # (the counter runs up; a first-time pickup opens its text)
            if 'press' in fl and result == 'reached' and not prompt_empty((self.g.st or {}).get('prompt')) \
                    and not text_open(self.g.st or {}):
                self.wait_input(self.g.press('A', 100))
                self.wait(0.8)
            if dive is not None and result == 'reached' and not any(k in self.changes(before, self.snap(), mark) for k in ('rupees', 'life', 'flags', 'text')):
                self.wait_input(self.g.press('A', int(dive * 1000)))
                self.wait(1.0)
            self.advance_text(time.time() + 15.0)
            self.wait(0.4)
        ch = self.changes(before, self.snap(), mark)
        # (the change scan's hashes also move for a camera cut or a prompt: they count only for a walk that reached the spot)
        keys = ('rupees', 'life', 'max_life', 'flags', 'text', 'scene') + (('hashes',) if result == 'reached' else ())
        if any(k in ch for k in keys):
            return self.outcome('picked', ch, f'walk {result}: {detail}')
        return (result if result != 'reached' else 'none'), f'{detail}; nothing changed'

    def step_enter(self, args):
        words, through = list(args), None
        if 'through' in words:
            i = words.index('through')
            if len(words) < i + 3:
                raise ValueError('enter <x> <z> [through <x> <z>] [timeout <s>]')
            through = (float(words[i + 1]), float(words[i + 2]))
            del words[i:i + 3]
        pos, kv, _ = split_opts(words, keys=('timeout',))
        if len(pos) != 2:
            raise ValueError('enter <x> <z> [through <x> <z>] [timeout <s>]')
        x, z, timeout = float(pos[0]), float(pos[1]), seconds_of(kv, 40.0)
        st = self.fresh()
        before, mark = self.snap(), self.g.n_states
        if not before['pos']:
            return 'none', 'no sample of Link yet'
        map0, p0 = before['map'], before['pos']
        if through is None:   # on along the line from where Link stands, 3 m past the door
            dx, dz = x - p0[0], z - p0[2]
            n = math.hypot(dx, dz) or 1.0
            through = (x + 3.0 * dx / n, z + 3.0 * dz / n)
        deadline, pressed, last, said = time.time() + timeout, 0, None, []
        stop = lambda s: s.get('map') != map0 or s.get('loading') == 1   # noqa: E731  (a walk across a load zone ends there: the point is in the old map)
        # the way to the door stops where the A prompt reads Open (a door's prompt can show on one side only, a step away from the point the
        # walk aims at: pi-solo-2a); a text open does not count
        at_open = lambda s: stop(s) or (str(s.get('prompt') or '').strip().lower().startswith('open') and not text_open(s))   # noqa: E731
        result, detail = self.walk(x, z, 0.4, min(timeout, 25.0), stop=at_open)
        for _ in range(4):
            st = self.g.st or {}
            if st.get('map') != map0 or st.get('loading') == 1:
                break
            if time.time() >= deadline:
                last = 'timeout'
                break
            if result == 'stuck' and prompt_empty(st.get('prompt')):   # (a door's prompt can lag Link's stop: give it a moment)
                end_wait = time.time() + 2.0
                while prompt_empty((self.g.st or {}).get('prompt')) and time.time() < end_wait and self.g.alive():
                    self.tick(0.05)
                st = self.g.st or {}
            if not prompt_empty(st.get('prompt')) and not text_open(st):
                self.wait_input(self.g.press('A', 100))
                pressed += 1
                self.wait(1.2)
                self.advance_text(time.time() + 10.0)
            elif result == 'stuck':
                last = 'blocked'
                break
            result, detail = self.walk(through[0], through[1], 0.6, min(8.0, max(1.0, deadline - time.time())), stop=stop)
            if (self.g.st or {}).get('map') != map0 or result == 'reached':
                break
            if result == 'stuck' and prompt_empty((self.g.st or {}).get('prompt')):
                last = 'blocked'
                break
        entered = (self.g.st or {}).get('map') != map0 or (self.g.st or {}).get('loading') == 1
        if entered:   # the new map: wait until control is back
            end = time.time() + 25.0
            free = None
            while time.time() < end and self.g.alive():
                s = self.g.st or {}
                free = (free or time.time()) if s.get('event') == 0 and s.get('loading') == 0 and s.get('map') else None
                if free and time.time() - free >= 1.0:
                    break
                self.tick(0.05)
        ch = self.changes(before, self.snap(), mark)
        if entered or ch.get('map'):
            return self.outcome('entered', ch, f'{map0} -> {(self.g.st or {}).get("map")}')
        if last == 'blocked':
            return self.outcome('blocked', ch, f'the way is shut: {detail}; the A prompt reads {(self.g.st or {}).get("prompt")!r}')
        if last == 'timeout':
            return self.outcome('timeout', ch, f'{timeout:g} s used; {detail}')
        if result == 'reached' or pressed:
            return self.outcome('opened', ch, f'through the door ({pressed} A presses): {detail}')
        return self.outcome('blocked', ch, detail)

    def step_ztarget(self, args):
        if len(args) > 1:
            raise ValueError('ztarget [ms]')
        ms = int(args[0]) if args else 1200
        if not 50 <= ms <= 5000:
            raise ValueError('ztarget [ms]: 50 to 5000')
        self.fresh()
        before, mark = self.snap(), self.g.n_states
        self.wait_input(self.g.press('ZL', ms))
        self.wait(0.3)
        after = self.snap()
        ch = self.changes(before, after, mark)
        turned = {k: [before.get(k), after.get(k)] for k in ('camera', 'facing')
                  if None not in (before.get(k), after.get(k)) and abs(wrap(after[k] - before[k])) >= 4.0}
        ch.update(turned)
        if 'music' in before and before.get('music') != after.get('music'):
            ch['music'] = [before.get('music'), after.get('music')]
        return self.outcome('targeted' if turned else 'none', ch, f'ZL held {ms} ms')

    def camera_push(self, name, ms):
        """The right stick for ms: the camera's yaw before and after (the rate and handedness learned from it)."""
        c0 = (self.fresh().get('camera'))
        self.wait_input(self.g.send(f'0:{name}/{ms}'))
        self.wait(0.25)
        c1 = (self.g.st or {}).get('camera')
        if c0 is not None and c1 is not None and abs(wrap(c1 - c0)) >= 1.0:
            self.cam_sign = 1.0 if (name == 'RRIGHT') == (wrap(c1 - c0) > 0) else -1.0
            self.cam_rate = max(10.0, abs(wrap(c1 - c0)) / ms * 1000.0)
        return c0, c1

    def step_camera(self, args):
        usage = 'camera <left|right|up|down> [ms] | camera to <yaw> [tolerance]'
        if not args:
            raise ValueError(usage)
        if args[0] == 'to':
            if len(args) not in (2, 3):
                raise ValueError(usage)
            yaw, tol = float(args[1]), float(args[2]) if len(args) == 3 else 8.0
            if tol <= 0:
                raise ValueError('tolerance above 0 degrees')
            c0 = self.fresh().get('camera')
            if c0 is None:
                return 'none', 'no camera yaw in the sample'
            for _ in range(8):
                cam = (self.g.st or {}).get('camera')
                err = wrap(yaw - cam)
                if abs(err) <= tol:
                    break
                name = 'RRIGHT' if err * self.cam_sign > 0 else 'RLEFT'
                self.camera_push(name, int(max(80, min(1500, abs(err) / self.cam_rate * 800))))
            c1 = (self.g.st or {}).get('camera')
            if abs(wrap(c1 - c0)) < 1.0:
                return 'none', f'the camera already looks {c1:.1f} (within {tol:g} degrees of {yaw:g})'
            return self.outcome('turned', {'camera': [c0, c1]}, f'to {c1:.1f} (asked {yaw:g}, tolerance {tol:g})')
        if args[0] not in CAMERA_KEYS or len(args) > 2:
            raise ValueError(usage)
        ms = int(args[1]) if len(args) == 2 else 400
        if not 50 <= ms <= 3000:
            raise ValueError('camera ' + args[0] + ' <ms>: 50 to 3000')
        c0, c1 = self.camera_push(CAMERA_KEYS[args[0]], ms)
        if c0 is None or c1 is None or abs(wrap(c1 - c0)) < 2.0:
            return 'none', f'the camera did not turn ({c0} -> {c1})'
        return self.outcome('turned', {'camera': [c0, c1]}, f'{wrap(c1 - c0):+.1f} degrees')

    def face_point(self, x, z, tolerance, pushes=4):
        """Short stick pushes until Link faces the ground point (x, z) within the tolerance: done / timeout."""
        for i in range(pushes + 1):
            st = self.g.st or {}
            pos, facing = st.get('pos'), st.get('facing')
            if not pos or facing is None or st.get('camera') is None:
                return 'no-sample', 'Link has no place or facing in the sample'
            bearing = yaw_of(x - pos[0], z - pos[2])
            rel = wrap(bearing - facing)
            if abs(rel) <= tolerance:
                return 'done', f'facing the point within {abs(rel):.0f} degrees ({math.hypot(x - pos[0], z - pos[2]):.1f} m), {i} pushes'
            if i < pushes:
                lx, ly = self.stick_at(bearing, 0.4)
                self.wait_input(self.g.stick(lx, ly, 100))
                self.wait(0.15)   # (a fresh sample to judge by)
        return 'timeout', f'still {abs(rel):.0f} degrees off the point after {pushes} pushes'

    def step_faceat(self, args):
        if len(args) not in (2, 3):
            raise ValueError('faceat <x> <z> [degrees]')
        return self.face_point(float(args[0]), float(args[1]), float(args[2]) if len(args) == 3 else 20.0)

    OC_TAKES_S, OC_FREE_S, OC_READY_MS = 4.0, 25.0, 3000   # (how long after the last note the game may take to close its note wait; how long a song's playback may hold Link; how long a fresh window ignores notes)

    def wait_control(self, seconds):
        """True once Link is free (no event, no load) in two samples that arrive after this call (the last sample may be older than the
        song the game just took) within `seconds`; the note wait itself holds him, so ask only with the ocarina away"""
        end, seen, free = time.time() + seconds, self.g.n_states, 0
        while time.time() < end and self.g.alive():
            if self.g.n_states != seen:
                seen = self.g.n_states
                st = self.g.st or {}
                free = free + 1 if not st.get('event') and not st.get('loading') else 0
                if free >= 2:
                    return True
            self.tick(0.05)
        return False

    def step_ocarina(self, args):
        usage = 'ocarina <note> ... [hold <ms>] [gap <ms>] [ready <ms>] (notes: ' + ' '.join(NOTE_BUTTONS) + ') | ocarina out | ocarina away'
        if not args:
            raise ValueError(usage)
        notes, opts, i = [], {}, 0
        while i < len(args):   # (hold: how long each note button is held, default 100 ms; gap: the pause after each note, default 150 ms)
            if args[i] in ('hold', 'gap', 'ready'):
                if i + 1 >= len(args) or not args[i + 1].isdigit() or args[i] in opts:
                    raise ValueError(usage)
                opts[args[i]] = int(args[i + 1])
                i += 2
            else:
                notes.append(args[i])
                i += 1
        hold, gap, ready = opts.get('hold', 100), opts.get('gap', 150), opts.get('ready', self.OC_READY_MS)
        if not notes or not 50 <= hold <= 3000 or not 0 <= gap <= 5000 or not 0 <= ready <= 10000:
            raise ValueError(usage)
        args = notes
        mode = args[0] if args[0] in ('out', 'away') and len(args) == 1 and not opts else None
        if mode is None and (any(a not in NOTE_BUTTONS for a in args) or len(args) > 40):
            raise ValueError(usage)
        mark_oc = len(self.g.oc_lines)
        before, mark = self.snap(), self.g.n_states

        def lines():
            return '; '.join('oc: ' + t for t in self.g.oc_lines[mark_oc:][:6])

        def away():
            if self.g.oc != 'on':
                return
            self.wait_input(self.g.press('B', 120))
            end = time.time() + 3.0
            while self.g.oc == 'on' and time.time() < end and self.g.alive():
                self.tick(0.05)
        if mode == 'away':
            was = self.g.oc
            away()
            return 'away', 'the ocarina was ' + ('put away; ' + lines() if was == 'on' else 'not out: nothing was sent')
        if self.g.oc != 'on':
            # a song the game took plays back and holds Link: a D-pad Left sent into that is lost (hold pi2-h1: the next notes then went to Link as
            # plain buttons, L opened the item wheel), so wait until he is free
            if not self.wait_control(self.OC_FREE_S):
                return 'no-ocarina', f'Link was still held {self.OC_FREE_S:g} s after the step began (a scene, a text or a song playing): nothing was sent'
            self.wait_input(self.g.press('LEFT', 120))   # the D-pad's Left takes the ocarina out
            end = time.time() + 3.5
            while self.g.oc != 'on' and time.time() < end and self.g.alive():
                self.tick(0.05)
            if self.g.oc != 'on':
                return 'no-ocarina', f'no `oc: the note wait turned on` line in 3.5 s after D-pad Left ({lines() or "no oc line at all"})'
        if mode == 'out':
            return 'out', 'the ocarina waits for a note; ' + lines()
        # all the notes as ONE timed sequence (the game's frames, not this program's wall clock between requests): 100 ms notes starting 250 ms
        # apart took a song in every run of hold pi2-h1; one request a note, 150/450 ms or 400/450 ms, never did
        every = (hold + gap) / 1000.0
        # a window opened a moment ago ignores its first note (holds pi2-h1..h3: 21 of 22 tries in a fresh window gave no song, 6 of 6 in one open 3 s or more did):
        # the window warms up first, `ready` ms from the game's `turned on` line
        warm = ready / 1000.0 - (time.time() - self.g.oc_since)
        if warm > 0:
            self.wait(warm)
        self.wait_input(self.g.send(','.join(f'{k * every:g}:{note}/{hold}' for k, note in enumerate(args))))
        # a song the game takes closes its note wait itself a moment after the last note; one it does not take leaves the wait open
        end = time.time() + self.OC_TAKES_S
        while self.g.oc == 'on' and time.time() < end and self.g.alive():
            self.tick(0.05)
        taken = self.g.oc != 'on'
        if taken:
            self.wait_control(self.OC_FREE_S)   # (it plays the song back and acts on it: weather, a warp, a door)
        else:
            away()
        self.advance_text(time.time() + 12.0)
        ch = self.changes(before, self.snap(), mark)
        return self.outcome('played' if taken else 'no-song', ch, f"{len(args)} notes {' '.join(args)}; {lines()}")

    def step_item(self, args):
        if len(args) > 2:
            raise ValueError('item [button] [ms]')
        button, ms = 'ZR', 150
        for a in args:
            if a.isdigit():
                ms = int(a)
            elif a in BUTTON_NAMES:
                button = a
            else:
                raise ValueError('item [button] [ms]: ' + ' '.join(BUTTON_NAMES))
        if not 50 <= ms <= 5000:
            raise ValueError('item [button] [ms]: 50 to 5000')
        self.fresh()
        before, mark = self.snap(), self.g.n_states
        self.wait_input(self.g.press(button, ms))
        self.wait(1.0)
        if text_open(self.g.st or {}):
            self.advance_text(time.time() + 10.0)
        ch = self.changes(before, self.snap(), mark)
        return self.outcome('used' if any(k in ch for k in self.EVIDENCE) else 'none', ch, f'{button} held {ms} ms')

    def step_rendezvous(self, args):
        pos, kv, _ = split_opts(args, keys=('timeout',))
        if len(pos) != 1 or not re.fullmatch(r'[A-Za-z0-9_-]{1,40}', pos[0]):
            raise ValueError('rendezvous <name> [timeout <s>]')
        timeout, name = seconds_of(kv, 120.0), pos[0]
        folder = os.environ.get('HSAP_RENDEZVOUS')
        if not folder:
            return 'alone', 'HSAP_RENDEZVOUS is not set: nobody to meet'
        mine = Path(folder) / f"{name}.{os.environ.get('HSAP_SIDE') or os.getpid()}"
        start = time.time()
        mine.write_text(json.dumps({'t': start, 'pid': os.getpid()}))   # (both players run on this PC: one wall clock)
        times = None
        while time.time() - start < timeout and self.g.alive():
            seen = {}
            for f in Path(folder).glob(name + '.*'):
                try:
                    seen[f.name] = float(json.loads(f.read_text())['t'])
                except (OSError, ValueError, KeyError, TypeError):
                    pass
            if len(seen) >= 2 and mine.name in seen:
                times = seen
                break
            self.tick(0.05)
        if times is None:
            return 'timeout', f'nobody else wrote {name}.* in {timeout:g} s'
        go = max(times.values()) + 1.5   # (a moment after the later of them: both are waiting by then)
        while time.time() < go and self.g.alive():
            self.tick(0.005)
        return 'met', f'{len(times)} players; released {time.time() - go:+.3f} s from the agreed instant, after {go - 1.5 - start:+.2f} s of waiting'

    def cond(self, words):
        """(test(state) -> bool, text) for flag <name><op><value> | area <name> | prompt=<text> | control"""
        if not words:
            raise BadStep('until <condition>')
        if words[0] == 'control':
            return (lambda s: bool(s.get('map')) and s.get('event') == 0 and s.get('loading') == 0), 'control', 1
        if words[0] == 'area' and len(words) > 1:
            name = words[1]
            return (lambda s: s.get('map') == name), f'area {name}', 2
        if words[0].startswith('prompt='):
            want = words[0][7:]
            return (lambda s: s.get('prompt') == want), f'prompt {want}', 1
        if words[0] == 'flag' and len(words) > 1:
            m = re.match(r'([A-Za-z0-9_.]+)(==|!=|<=|>=|=|<|>)(.+)$', words[1])
            if not m:
                raise BadStep('flag <name><op><value>')
            name, op, val = m.groups()
            if name in ('prompt', PROMPT_HASH):
                return (lambda s: s.get('prompt') == val), f'prompt {val}', 2

            def test(s, name=name, op=op, val=val):
                v = (s.get('flags') or {}).get(name)
                if v is None:
                    return False
                try:
                    a, b = float(v), float(val)
                except (TypeError, ValueError):
                    a, b = str(v), val
                return {'=': a == b, '==': a != b, '!=': a != b, '<': a < b, '>': a > b, '<=': a <= b, '>=': a >= b}[op]
            return test, f'flag {name}{op}{val}', 2
        raise BadStep('until flag|area|prompt=|control ...')

    def until(self, words):
        test, text, used = self.cond(words)
        rest = words[used:]
        timeout, press, every = 30.0, None, None
        i = 0
        while i < len(rest):
            if rest[i] == 'timeout' and i + 1 < len(rest):
                timeout = float(rest[i + 1])
                i += 2
            elif rest[i] == 'press' and i + 3 < len(rest) and rest[i + 2] == 'every':
                press, every = rest[i + 1], float(rest[i + 3])
                i += 4
            else:
                raise BadStep(f'until ...: {rest[i]} not understood')
        start, next_press = time.time(), time.time()
        while time.time() - start < timeout and self.g.alive():
            if self.g.st and test(self.g.st):
                return 'met', f'{text}: met after {time.time() - start:.1f} s'
            if press and time.time() >= next_press:
                self.g.press(press, 100)
                next_press = time.time() + every
            self.tick(0.05)
        return 'timeout', f'{text}: not met in {timeout:g} s'

    def walk(self, x, z, radius, timeout, aim=None, mag=None, noise=0.0, seed=0, stop=None):
        """Steer Link to (x, z): each fresh sample, the stick direction nearest the needed one relative to the camera,
        with the error carried to the next tick (eight directions), or the exact angle with analog on. Ends 'held' when an
        event (a talk, a scene) has held Link for 0.6 s: pushing on into a talk does nothing. `stop(state)` true ends it
        'stopped' (the enter step: the map changed, the point is no longer in this one)"""
        hand = HandNoise(noise, seed) if noise else None   # a hand on the stick (PilotRecover's humanize levels)
        cap = round(mag * 32767) if mag else None          # a cap on the push (below the walk's own full push)
        restarts = self.g.restarts
        start = stuck_from = time.time()
        carry, hist = 0.0, []
        sent_frame = None
        held_since = None
        while self.g.alive():
            self.tick(0.03)
            if self.g.restarts != restarts:
                return 'cut', 'the game restarted itself during the step'
            st = self.g.st or {}
            if stop is not None and stop(st):
                return 'stopped', 'the stop test passed (the map changed or a load began)'
            pos, cam = st.get('pos'), st.get('camera')
            if not pos:
                continue
            if aim is not None:   # a moving target (the opponent): where he is at this sample
                got = aim()
                if got is None:
                    return 'no-opponent', 'no usable place of the opponent (the file is missing or unreadable, or he is on another map)'
                x, z = got
            d = math.hypot(x - pos[0], z - pos[2])
            if d <= radius:
                return 'reached', f'{d:.2f} m from the point'
            if st.get('event') == 1:
                held_since = held_since or time.time()
                if time.time() - held_since >= 0.6:
                    return 'held', f'{d:.2f} m from the point; an event holds Link at {pos[0]:.1f} {pos[1]:.1f} {pos[2]:.1f}'
            else:
                held_since = None
            now = time.time()
            hist.append((now, pos[0], pos[2]))
            # (the stick's handedness, checked as he moves: off the wanted heading by over 100 degrees three times running
            # while the wanted way is to the camera's side)
            old = [h for h in hist if now - h[0] >= 0.6]
            if old and cam is not None and now - self.checked > 0.5:
                self.checked = now
                mx, mz = pos[0] - old[-1][1], pos[2] - old[-1][2]
                if math.hypot(mx, mz) > 0.5:
                    err = abs(wrap(yaw_of(mx, mz) - yaw_of(x - pos[0], z - pos[2])))
                    lateral = abs(abs(wrap(cam - yaw_of(x - pos[0], z - pos[2]))) - 90) < 60
                    self.mirror = self.mirror + 1 if err > 100 and lateral else 0
                    if self.mirror >= 3:
                        self.sign, self.mirror = -self.sign, 0
                        self.emit(ev='note', text=f'stick handedness flipped to {self.sign:+.0f} (heading off by {err:.0f} degrees)')
                        hist, self.checked, stuck_from = [], now + 0.5, now   # (judge the new way on its own)
            hist = [h for h in hist if now - h[0] <= 2.5]
            if now - stuck_from > 2.5 and hist and math.hypot(pos[0] - hist[0][1], pos[2] - hist[0][2]) < 0.3:
                return 'stuck', f'{d:.2f} m from the point; moved under 0.3 m in 2.5 s at {pos[0]:.1f} {pos[1]:.1f} {pos[2]:.1f}'
            if now - start > timeout:
                return 'timeout', f'{d:.2f} m from the point after {timeout:g} s'
            if cam is None or st.get('frame') == sent_frame or st.get('event') != 0 or st.get('loading') != 0:
                continue
            want = wrap(cam - yaw_of(x - pos[0], z - pos[2])) * self.sign + carry   # the stick's angle, right positive
            mfac = 1.0
            if hand is not None:
                err, mfac = hand.at(time.time())   # the angle wanders a few degrees, the push varies by 5 percent
                want += err
            if self.analog:   # the exact angle; within 1.2 m of the point at half push (Link walks), not full
                mag_now = 32767 if d > 1.2 else 16384
                mag_now = min(32767, round(min(mag_now, cap if cap is not None else mag_now) * mfac))
                lx, ly = round(mag_now * math.sin(math.radians(want))), round(mag_now * math.cos(math.radians(want)))
                carry = 0.0
                self.g.stick(lx, ly, 140)
            else:
                a, press = min(DIRS, key=lambda dp: abs(wrap(dp[0] - want)))
                carry = max(-40.0, min(40.0, wrap(want - a)))
                self.g.press(press, 140)
            sent_frame = st['frame']
        return 'cut', 'the game ended'

    def save(self, timeout):
        before = self.g.saves()
        mark = len(self.g.log_lines)
        self.g.send('!cheat 996')
        start = time.time()
        said = ''
        while time.time() - start < timeout and self.g.alive():
            self.tick(0.1)
            for line in self.g.log_lines[mark:]:
                if 'cheats: save:' in line:
                    said = line.split('cheats: save:', 1)[1].strip()
            mark = len(self.g.log_lines)
            now = self.g.saves()
            changed = [p for p, t in now.items() if before.get(p) != t]
            if changed:
                self.wait(2.0)   # (the game writes progress.sav and caption.sav: let it finish)
                return 'done', f'saved {", ".join(Path(p).parent.name for p in changed)} ({said})'
            if said and 'not taken' in said and time.time() - start > 3:
                return 'refused', said
        return 'timeout', said or 'no answer to !cheat 996'


class BadStep(Exception):
    pass


def env_pair(text):
    """--env's NAME=VALUE: the game's switches are upper case words (HOS_..., RX_...); a value has no white space (the command line of
    hs-run.sh carries it as one word)"""
    if not re.fullmatch(r'[A-Z][A-Z0-9_]*=\S*', text):
        raise argparse.ArgumentTypeError(f'{text!r} is not NAME=VALUE (an upper case name, a value without white space)')
    return text


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('copy')
    ap.add_argument('tag')
    ap.add_argument('wall', type=int)
    ap.add_argument('--live', required=True)
    ap.add_argument('--save')
    ap.add_argument('--boot', choices=('newgame', 'continue', 'none'), default=None)
    ap.add_argument('--shots', type=int, default=0)
    ap.add_argument('--env', action='append', type=env_pair, default=[], metavar='NAME=VALUE',
                    help='one more switch for the game of this run, as hs-run.sh takes them after its own (repeatable: '
                         'HOS_CONTROL_MEM=ro lets a second client read the guest memory)')
    ap.add_argument('--keep-going', action='store_true', help='after the steps are done, keep the game until end')
    ap.add_argument('--analog', action='store_true', help='steer with exact stick values through the control socket')
    ap.add_argument('--opponent', help='a JSON file {x, y, z, map, w} a runner keeps with the other player\'s place: the duel '
                                       'steps aim at it and the state lines carry his distance and bearing')
    ap.add_argument('--reconnect-wait', type=float, default=180.0, metavar='SECONDS',
                    help='a game that restarts itself replaces its control socket: wait this long for the new one and '
                         'subscribe again (0: end the run as before)')
    ap.add_argument('--hud', choices=('on', 'off'), default=None,
                    help='the pilot\'s decisions on the game\'s own screen (the control bridge\'s `overlay` command; the panel text is '
                         '<live>/hud.txt); default on unless HSAP_HUD=0; off sends nothing and leaves the game\'s environment alone')
    ap.add_argument('--game-sock', metavar='PATH', help='external game: the control socket of a game somebody else runs (hsap '
                    'connects, and reconnects, as an additional client); starts no game')
    ap.add_argument('--game-live', metavar='FILE', help='external game: the HOS_INPUT_LIVE file the game already reads (the '
                    '`duel ready` lines are appended there; never truncated)')
    ap.add_argument('--game-log', metavar='FILE', help='external game: its log, tailed for the `coop: duel:` lines')
    ap.add_argument('--game-pid', type=int, metavar='PID', help='external game: its process id (alive while it exists)')
    a = ap.parse_args()
    given = [a.game_sock, a.game_live, a.game_log, a.game_pid]
    external = None
    if any(x is not None for x in given):
        if any(x is None for x in given):
            ap.error('an external game needs --game-sock, --game-live, --game-log and --game-pid together')
        if a.save or a.shots or a.env:
            ap.error('--save, --shots and --env belong to a game hsap starts: not with --game-sock')
        if a.wall <= 0:
            ap.error('the wall time of an external game (the life of hsap itself) must be positive')
        try:
            external = ExternalGame(a.game_sock, a.game_live, a.game_log, a.game_pid)
        except ValueError as e:
            ap.error(str(e))
    live = Path(a.live)
    live.mkdir(parents=True, exist_ok=True)
    (live / 'steps.txt').touch()
    time.sleep(1.0)   # (the pilot writes its watch lines first)
    watch = []
    for line in (live / 'steps.txt').read_text().splitlines():
        w = line.split('#', 1)[0].split()
        if w and w[0] == 'watch':
            watch += [x for x in w[1:] if valid_flag(x)]
    boot = a.boot or ('none' if external else 'continue' if a.save else 'newgame')
    hud = hud_wanted(a.hud)
    g = Game(a.copy, a.tag, a.wall, live, save=a.save, watch=sorted(set(watch))[:64], shots=a.shots, extra=a.env,
             reconnect_wait=a.reconnect_wait, external=external, hud=hud)
    ex = Executor(g, live, boot, opponent_path=a.opponent, hud=hud)
    ex.analog = ex.analog or a.analog
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(1))   # (a stop from the pilot still stops the game: finally below)
    ex.emit(ev='note', text=('external game (hsap starts and stops nothing): ' if external else 'hs-run: ') + ' '.join(g.cmd),
            boot=boot, analog=ex.analog, hud=hud)
    result = 0
    try:
        ex.run()
    except ControlError as e:
        ex.emit(ev='note', text=str(e))
        result = 1
    finally:
        if ex.hud is not None:
            ex.hud.close()   # (a run that ended in an error: the normal end did it already, once)
        g.stop()
        ex.emit(ev='note', text=(f'hsap ended; the game (pid {external.pid}) was left running' if external else
                                 f'game stopped; run folder {g.R}'), saves={Path(p).parent.name: t for p, t in g.saves().items()})
    return result


if __name__ == '__main__':
    sys.exit(main())
