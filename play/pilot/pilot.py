#!/usr/bin/env python3
"""The playthrough pilot: plays one segment of the game by deciding, at every point where the game side has no step
left, which concrete step comes next, until the segment's goal flags are set, a budget ends, or it gives up. The steps
go to the game side through its live channel (a folder: steps.txt in, out.jsonl back); a solved segment is written out
as a route file. (the harness, 2026-11-10: the game side is ../hsap.py, which runs a game copy through
hs-run.sh with live input and the state tap, in place of the earlier test autopilot; the rest is as it was.)

  pilot.py run <segment.toml> [--decider rules|replay|openai-decisions] [--replay <transcript>] [--planner]
               [--driver <want>[,<fallback>...]] [--fallbacks <a,b>|none] [--recording <file>] [--playback-mode raw|push]
               [--openrouter-model <m>]
               [--chat-base <url>] [--chat-model <m>] [--chat-mode tool|json_schema|json] [--mcp-dir <dir>] [--mcp-wait <s>]
               [--mcp-agent loop|omp] [--mcp-agent-model <m>]
               [--max-decisions <n>] [--api-base <url>] [--follow NAME=<file>] [--end-hold <s>] [--shots <presents>]
               [--matches <n>] [--humanize 0..3] [--humanize-seed <n>] [--no-recover] [--bad-points <dir>] [--no-bad-points]
               [--tactics ranked|fixed|explore|off] [--tactics-dir <dir>] [--tactics-source <name>] [--tactics-readonly] [--lessons on|off]
               [--vision off|on] [--vision-every <s>] [--vision-model <m>] [--vision-backend decisions|responses]
               [--vision-sock <path>] [--hud on|off]
  pilot.py check-route <route.txt> --segment <segment.toml> [--runs 3] [--copy <game copy>] [--tag <prefix>]
  pilot.py ledger [--run <id>] [--since YYYY-MM-DDTHH:MM] [--standin]

The game copy a run uses is --copy, else $PILOT_COPY, else the folder `.hookshot-h-play` beside the harness folder.

A segment (segments/*.toml): name, what, area, save (a library entry of the harness's saves folder, a game user
folder, or kept:<tag> for the user folder a run of this copy kept), boot (newgame, continue, none;
default continue with a save, newgame without), wall, budget_seconds, max_decisions, prefix (a route file sent before
the live steps), save_after, humanize (0..3: this segment's default level), watch
(more flags), a [place] table (to = a destination the game lists, age, hour: Link is put there through hsdebug before the first
decision, placement.py), and [[goal]] tables in order: name, what, flag (<name><op><value>, as the autopilot's until takes it),
kind (reach, door, talk, chest, wait, crawl, climb, item, fight), targets: [{name, actor = "<Name>#<n>" of the area's
placement, or at = [x, z], or follow = "<name>" (another player: a --follow file); kind, radius, y}]. Game-derived: segments,
transcripts and routes stay in this folder. A fight target (PlayExplore17) holds a place and fights what comes (strike,
swing-x3, guard, wait-a-moment, go-near, back-off, side-left/right, next-target); the goal needs some flag the segment can
name, since none tells that a fight is won; its `rules` policy goes to the place and strikes and waits for eight rounds.
The interaction goal kinds (interact.py: open_chest, collect, talk_to, enter, play_song, fight without a flag, ...) have
their own conditions and candidates; actions.py adds cross (a gap, a ledge, an ivy), dive, push_block, buy, use_item, strafe, warp_song, ride, read_sign.
A chapter (sections.py: a TOML file with an `aim`, progress markers and budgets instead of goals) is played with the same command:
`pilot.py run chapters/x.toml`: a planner model makes objectives from the aim, the world model and the pictures, each objective is a segment goal.

Never stuck, never a wasted question (recover.py): after every move the pilot watches the position and the distance to the
target. A move that ended stuck is a block; so are a few moves in a row that gain no ground. A block is answered without a
question by a ladder, one rung per decision: sidestep, back up and come at it from an angle, roll, a hop (X, no sword), the
next route point, and last a local re-plan (the planner is asked again, the point is marked bad, the target is left). Where
a rung got Link past, or the ladder failed, the place goes into a per-map file under pilot/cache (or $PILOT_CACHE), and later
routes bend round it. In front of the decider a guard offers no move that already ended stuck from here, takes the one valid
candidate without a question, does not ask again about a state that did not change, and turns a long run of identical answers
into recovery. A reach target that the planned way left short of its radius is closed in on. --no-recover gives the pilot as it
was. The state a decider sees carries nothing of this; each decision row of the transcript has `recover` (stuck, why,
stalled_obs, stalled_s, rung, streak), a `recover` row is written for a block, a recovery and a bad point, and summary.json has
`recover` (blocks, how long each lasted in game seconds, the rungs used) and `rates` (model calls and cost per minute).

Learning (tactics.py, tactics_seed.py, lessons.py; a self-play hold feeds them by night, selfplay.py): the ladder's rungs are a library of tactics keyed by
the cause of the block (a wall, a ledge from below, a drop that is not taken, a door's wrong side, a crowd, a person in the way, a text that holds Link, the
water's edge, another floor), and --tactics ranked (the default; or $PILOT_TACTICS) tries them best first: the order is the success rate of each tactic for
that cause across every map and run recorded (a prior from the static order, the same place and map and age weighing more), at most five and then the
re-plan. Every attempt, with its map, age, cause, place and the geometry round it, and every block as one episode row, goes back into the library (`tactics/`
beside the route library, or --tactics-dir, $PILOT_TACTICS_DIR; --tactics-readonly: read, never written, for a scoreboard's cells); the decision row of a rung has `recover_cause` and `recover_order`, summary.json's `recover` has `causes` and
`tactics` (tried, worked). `fixed` is the old order with the recording still on (an A/B's control arm learns too), `explore` the order the nightly self-play
uses (an optimism bonus for what has been tried little), `off` the old ladder with nothing read or written ($PILOT_LEARN=off turns tactics and lessons off).
--lessons on (the default; or $PILOT_LESSONS) adds the few most similar past failures and what finally worked, in a small token budget, to every planner call;
`off` leaves the planner's request as it was.

Moves like a person (humanize.py, --humanize 0..3, default 2 for an exploration run, 0 for a duel; seeded, so a run can be
played again): a reaction delay before a move, a little noise on the stick, small curves in long legs, looks with the camera
stick, pauses, a leg walked instead of run, at level 3 a roll along the way. Level 0 sends every line exactly as made.

A follow target waits for its file; a follower that starts on another map has its own state read again every two seconds and
goes on when the maps agree (or, after a while, with only waiting offered while they do not).

A duel goal (kind = "duel", no flag; segments/duel.toml, duel-child.toml, duel-series.toml): a sword duel against the other
player. It is met when the game's own log says `state Match ended` for `matches` different matches (matches = N in the goal,
default 1: a series; hsap tails the `coop: duel:` lines into the state line's `duel` block, whose tracker remembers each ended
match by its id), ends when it says Interrupted, or when a budget ends. Its target is a follow target for the opponent: the
pilot hands the --follow file to hsap (--opponent), reads it before each decision for the `opponent` block (distance and
bearing relative to Link's own facing), and waits for it before the first decision (a runner writes it when its own checks have
passed); its game-time budget counts from then. After a match that ended with matches remaining, Ready is offered again (a
fresh match, no second practice swing). --matches N sets N for every duel goal and scales budget_seconds and max_decisions by
N over the segment's own N. Candidates: practice-swing, ready, approach, face, swing, shield, sidestep-left/right, roll-away/
left/right, wait (duel_candidates); `rules` have a fixed policy (deciders.Rules.pick_duel); openai-decisions gets its own prompt
and is asked at most once in 1.5 s of game time (the pilot waits out the rest of the gap), never for a single candidate.

Drivers (drivers/; PilotDrivers, 2026-11-16): who chooses the next step, behind one interface, each falling back to the next.
A driver is given the observation (the state line, the goal and target, what was tried) and the allowed actions (the candidates) and
returns one step, or a short plan, with its provenance (driver, model, cost, latency): decisions (OpenAI's Decisions API, as it was),
openrouter (OpenRouter's chat completions, a forced tool call checked against the allowed labels, default model openai/gpt-6-luna, the decisions model's own),
chat (any OpenAI-compatible base URL, a local llama.cpp or Ollama server needs no key; $PILOT_CHAT_BASE / --chat-base), mcp (an outside
agent through MCP tools: `mcp_server.py --session <dir>` over stdio, with `run --driver mcp --mcp-dir <dir>`), playback (an
ls-input-recording/1 file replayed through the same input path, with the map and place checked at the recording's marks: a replay that
left the road stops and says where) and scripted (the rules policy and fixed input scripts: no model, the same inputs give the same
steps). A scenario names the driver it wants and the fallbacks it accepts, in its TOML: `[driver] want = "decisions"`,
`fallbacks = ["openrouter", "scripted"]` (also recording, setup, script, tolerance_m and the models); the command line says the same:
`--driver decisions,openrouter,scripted`, `--fallbacks none`. With none named the wanted driver gets the rest of the default chain from
itself on: decisions -> openrouter -> chat (only when a base URL is configured) -> scripted; a scenario that wants playback or scripted
never falls back to a model unless it says so. A run that names no driver (and no $PILOT_DRIVER) plays on the rules as it always did, and
--decider (rules, replay, openai-decisions) is unchanged. A driver that cannot be asked (no key, no endpoint, a cap reached) is benched
before any request; one that fails (timeout, refused, bad answer, over budget, diverged) falls back to the next: every fallback is a
`driver-fallback` row of the transcript (driver, failure kind, reason, next driver, cost), every decision row says which driver made it
(`decider`, `driver`, `fallbacks`), and summary.json `drivers` has the chain, who was benched and why, the decisions and the cost by
driver and the run-length account of who decided what. Every paid request, whichever driver, goes through the same caps (caps.json) and
the same ledger. Every run writes recording.jsonl (hsap's input journal and a mark after each step; `pilot.py record <run>` makes one
afterwards) that `--driver playback --recording <file>` replays. `pilot.py drivers [--ask NAME]` says which drivers can be asked now and
why not, and with --ask makes one tiny request through a paid one.

What leaves the machine: only with --decider openai-decisions or a driver that is a model (decisions, openrouter, and chat when its base
URL is not on this machine) (and --planner): the request bodies in each run's transcript.jsonl (the state line as JSON, the goal and
target names, what was tried, the candidate steps), sent to api.openai.com, openrouter.ai or the chat endpoint named. With the mcp driver
the same observation goes to the agent that is connected, and its screenshot tool sends the game's picture to that agent. With --vision on
(vision.py; default off) the game's own frame, downscaled, goes too, with one fixed instruction text and fixed questions and no path,
log line, flag or coordinate; the pictures sent are kept in the run's vision/ folder. With lessons on (--lessons,
lessons.py) a planner request also carries up to three short sentences about past blocks (a map name, rounded x and z, a target name, what stopped Link and
what finally got him past), under 350 tokens. The keys (OpenAI: openai_api.py; OpenRouter:
$PILOT_OPENROUTER_KEY_FILE, default ~/.config/ls-pilot/openrouter.key, mode 600; a chat endpoint: $PILOT_CHAT_KEY_FILE or
$PILOT_CHAT_API_KEY, optional) are never printed or stored.

The panel (hud_text.py, --hud on|off, default on; HSAP_HUD=0 in the environment turns it off): the pilot's decisions on the game's own
screen. After each decision and each step result the pilot writes the panel text to <live>/hud.txt (GOAL and its target, the decision
and its game time, the candidates with the chosen one and the model's percentages, STEP, LAST, MODEL, COST so far, STATE, VISION; at
most 14 lines of 56 ASCII characters; no path, key, request body or position) and hsap, told --hud on, sends it to the game with the
control bridge's `overlay` command (hsap.py: at most four a second, again every 25 s, cleared at the end; a game that cannot, or an
older one, is noted once and the run goes on exactly as without). With --hud off nothing is written and hsap is told --hud off; either
way the decisions, steps, timing and pictures are the same. The panel is in the game's periodic pictures (--shots) only when the
game was started with RX_VK_SHOT_MENU=1, which hsap does for a game it starts with the panel on; the pictures the pilot's eyes
(--vision) look at come from the bridge's `shot` and never carry it. check-route and probe.py run with the panel off. The panel
is cleared (an empty file) before the pilot's `end` step; a panel that cannot be written is noted once in the transcript (kind `hud`).
"""
import argparse
import copy
import datetime
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import deciders  # noqa: E402
import drivers  # noqa: E402
import hud_text  # noqa: E402
import humanize  # noqa: E402
import interact  # noqa: E402
import openai_api  # noqa: E402
import recover  # noqa: E402
import tactics as tactics_lib  # noqa: E402  (a Pilot's own `tactics` argument is the library's settings; the module is tactics_lib here)

H = HERE.parent.parent
sys.path.insert(0, str(H if (H / 'hs_names.py').is_file() else H / 'harness'))
from hs_names import log_path
PLAYTHROUGH = HERE.parent
sys.path.insert(0, str(PLAYTHROUGH))
import hsap  # noqa: E402  (the game side's duel log parser and opponent geometry: one copy of both)
COPY = Path(os.environ.get('PILOT_COPY') or H.parent / '.hookshot-h-play')   # the game copy a run uses unless --copy says
HSAP = PLAYTHROUGH / 'hsap.py'
SAVE_TOOL = H / 'tools' / 'hs_make_save.py'   # SaveLib's (the library's own tool): placements, saves
LIBRARY = H / 'saves'
CACHE = HERE / 'cache'
FRAGMENTS = HERE / 'fragments.jsonl'
PLANNER_LOG = HERE / 'planner.jsonl'
SLOT_VARS = ('HSGATE_SLOT_DIR', 'HSGATE_INTEL_SLOT_DIR', 'HSGATE_SLOT_TEST', 'HSGATE_SLOT_NODESKTOP', 'HSGATE_IN_GATE')
MOVES = ('walk', 'run')
REACHED = ('reached', 'done', 'met', 'opened', 'talked', 'picked', 'entered', 'closed', 'played', 'used', 'turned', 'targeted',
           'landed', 'climbed', 'swam', 'dived', 'pushed', 'pulled', 'strafed', 'circled', 'guarded', 'rolled', 'bought', 'ridden')   # a result that is an arrival or an act done


def murmur(s):
    data = s.encode()
    n, h = len(data), 0
    for i in range(0, n - n % 4, 4):
        k = (int.from_bytes(data[i:i + 4], 'little') * 0xcc9e2d51) & 0xffffffff
        k = (((k << 15) | (k >> 17)) & 0xffffffff) * 0x1b873593 & 0xffffffff
        h ^= k
        h = (((h << 13) | (h >> 19)) & 0xffffffff) * 5 + 0xe6546b64 & 0xffffffff
    if n % 4:
        k = (int.from_bytes(data[n - n % 4:], 'little') * 0xcc9e2d51) & 0xffffffff
        k = (((k << 15) | (k >> 17)) & 0xffffffff) * 0x1b873593 & 0xffffffff
        h ^= k
    h ^= n
    h ^= h >> 16
    h = h * 0x85ebca6b & 0xffffffff
    h ^= h >> 13
    h = h * 0xc2b2ae35 & 0xffffffff
    return h ^ (h >> 16)


# ---- segments

class Cond:
    """flag <name><op><value> as the autopilot's until and expect take it, judged on a state line's watched flags."""
    OPS = ('<=', '>=', '!=', '=', '<', '>')

    def __init__(self, text):
        self.text = text
        for op in self.OPS:
            i = text.find(op)
            if i > 0:
                self.name, self.op, self.value = text[:i], op, text[i + len(op):]
                break
        else:
            raise ValueError(f'no comparison in {text!r}')

    def met(self, flags):
        v = flags.get(self.name)
        if v is None:
            return False
        want = self.value
        if isinstance(v, str) and v.startswith('#'):   # an Enum's value as the hash of its name
            same = v == f'#{murmur(want):08x}'
            return same if self.op == '=' else (not same) if self.op == '!=' else False
        if isinstance(v, str):
            return (v == want) if self.op == '=' else (v != want) if self.op == '!=' else False
        try:
            w = float({'true': 1, 'false': 0}.get(want, want))
        except ValueError:
            return False
        return {'=': v == w, '!=': v != w, '<': v < w, '>': v > w, '<=': v <= w, '>=': v >= w}[self.op]


class DuelCond(Cond):
    """A duel goal has no flag: it is met when the game's own log has said Match ended for `matches` different matches, judged on
    the state line's `duel` block (Pilot.update_goals), never on flags. The text is what a decider reads as the goal's
    condition."""

    def __init__(self, matches=1):
        self.matches = matches
        self.text = 'the game\'s log says: state Match ended' + (f' for {matches} different matches' if matches > 1 else '')
        self.name, self.op, self.value = None, '=', 'Match ended'

    def met(self, flags):
        return False


@dataclass
class Target:
    name: str
    x: float
    z: float
    y: float = None
    kind: str = 'reach'
    radius: float = 1.0
    status: str = 'open'   # open, done, failed, dropped
    exit: tuple = None     # a crawl hole's other end (x, z): crawl-forward goes on past it
    approach: float = None  # the yaw (degrees, 0 along +z, 90 along +x) Link must walk in to open or enter it
    front: tuple = None     # where to stand before a door (x, z), when 2 m before its placed point is not free
    follow: str = None      # a moving target: the name of a --follow file the runner keeps with another player's place


@dataclass
class Goal:
    name: str
    cond: Cond
    kind: str
    targets: list
    what: str = ''
    status: str = 'open'   # open, met, failed
    order: str = 'given'   # given, or nearest: the open targets visited nearest first from where Link is
    sorted: bool = False
    matches: int = 1       # a duel goal: how many different matches must end (a series)


def actors(area):
    """{'<Name>#<n>': (x, y, z)} of an area's placement, from make_test_save.py --list-actors (cached)."""
    CACHE.mkdir(exist_ok=True)
    f = CACHE / f'actors-{area}.txt'
    if not f.exists():
        out = subprocess.run([sys.executable, str(SAVE_TOOL), '--list-actors', area], cwd=H,
                             capture_output=True, text=True, check=True).stdout
        f.write_text(out)
    got = {}
    for line in f.read_text().splitlines():
        if '@' in line and ':' in line:
            name, _, xyz = line.partition('@')[2].rpartition(':')
            try:
                got[name] = tuple(float(v) for v in xyz.split(','))
            except ValueError:
                pass
    return got


class Segment:
    def __init__(self, path, spec=None):
        d = spec if spec is not None else tomllib.loads(Path(path).read_text())   # (spec: the same tables as a dict: sections.py's objectives)
        self.path = Path(path)
        self.name, self.what, self.area = d['name'], d.get('what', ''), d['area']
        self.save, self.prefix = d.get('save'), d.get('prefix')
        self.place = None
        if 'place' in d:   # Link put at a place, an age and an hour before the first decision (placement.py, through hsdebug)
            import placement
            self.place = placement.check_spec(d['place'])
        self.boot = d.get('boot')
        self.driver = drivers.parse_table(d.get('driver'), self.path.parent)   # who decides: {want, fallbacks, ...} (drivers/)
        self.humanize = d.get('humanize')   # this segment's own level (0..3) unless --humanize says; none: the run's default
        self.wall, self.budget = int(d.get('wall', 600)), float(d.get('budget_seconds', 400))
        self.max_decisions, self.save_after = int(d.get('max_decisions', 80)), bool(d.get('save_after', False))
        self.straight = bool(d.get('straight', False))   # no offline planner: the way to a target is the straight run (the self-play's visits walk into the block earlier straight runs met)
        placed = None
        self.goals = []
        self.scripted = bool(d.get('scripted'))   # a scripted segment (scenario.py): the prefix is the whole play, no goals, no decider
        if not d.get('goal') and not self.scripted:
            raise ValueError('a segment has goals (or is scripted = true with a prefix)')
        if self.scripted and not self.prefix:
            raise ValueError('a scripted segment has a prefix: the steps to play')
        for g in d.get('goal', []):
            ts = []
            for t in g['targets']:
                if 'actor' in t:
                    placed = placed or actors(self.area)
                    x, y, z = placed[t['actor']]
                elif 'follow' in t:   # another player's place: x and z come from the --follow file, read at each decision
                    (x, z), y = t.get('at', (0.0, 0.0)), t.get('y')
                else:
                    (x, z), y = t['at'], t.get('y')
                ex = t.get('exit')
                if isinstance(ex, str):
                    placed = placed or actors(self.area)
                    ex = (placed[ex][0], placed[ex][2])
                ts.append(Target(t['name'], x, z, t.get('y', y), t.get('kind', g.get('kind', 'reach')),
                                 float(t.get('radius', 1.0)), exit=tuple(ex) if ex else None,
                                 approach=t.get('approach'), front=tuple(t['front']) if t.get('front') else None,
                                 follow=t.get('follow')))
            kind = g.get('kind', 'reach')
            matches = g.get('matches', 1)
            if 'matches' in g and kind != 'duel':
                raise ValueError(f"goal {g['name']}: `matches` belongs to a duel goal")
            if not isinstance(matches, int) or isinstance(matches, bool) or matches < 1:
                raise ValueError(f"goal {g['name']}: matches must be a whole number, 1 or more")
            if kind == 'duel':
                cond = DuelCond(matches)
            elif interaction_goal(kind, g):   # an interaction goal: the condition is its own (interact.py)
                cond = interact.make_cond(g, ts, Cond)
            else:
                cond = Cond(g['flag'])
            self.goals.append(Goal(g['name'], cond, kind, ts, g.get('what', ''), order=g.get('order', 'given'), matches=matches))
        self.watch = sorted({g.cond.name for g in self.goals if g.cond.name} | {w for g in self.goals for w in getattr(g.cond, 'watch', ())}
                            | set(d.get('watch', [])))

    def set_matches(self, n):
        """--matches N: every duel goal asks for N different matches (a series), and the segment's budget_seconds and
        max_decisions, which were written for its own `matches`, scale by N over that."""
        duels = [g for g in self.goals if g.kind == 'duel']
        if not duels:
            raise ValueError('--matches needs a duel goal')
        if n < 1:
            raise ValueError('--matches must be 1 or more')
        base = duels[0].matches
        self.budget, self.max_decisions = self.budget * n / base, math.ceil(self.max_decisions * n / base)
        for g in duels:
            g.matches, g.cond = n, DuelCond(n)


def save_dir(spec, copy):
    """The game user folder (holds save/<user id>/) a segment starts from: kept:<tag> the one run <tag> of this copy
    kept (hs-run.sh keeps runs/<tag>/user/save), a library entry by name, or a path."""
    if not spec:
        return None
    if spec.startswith('kept:'):
        return copy / 'runs' / spec[5:] / 'user'
    p = Path(spec)
    return p if p.is_absolute() else LIBRARY / spec


# ---- the live channel

class Channel:
    def __init__(self, live):
        self.live = Path(live)
        self.live.mkdir(parents=True, exist_ok=True)
        self.steps, self.out = self.live / 'steps.txt', self.live / 'out.jsonl'
        self.steps.touch()
        self.lines = len(self.steps.read_text().splitlines())
        self.off, self.buf, self.events, self.unread = 0, b'', [], []

    def send(self, lines):
        with open(self.steps, 'a') as f:
            for line in lines:
                f.write(line + '\n')
            f.flush()
        first = self.lines + 1
        self.lines += len(lines)
        return list(range(first, self.lines + 1))

    def poll(self):
        if not self.out.exists():
            return []
        with open(self.out, 'rb') as f:
            f.seek(self.off)
            data = f.read()
        self.off += len(data)
        self.buf += data
        *whole, self.buf = self.buf.split(b'\n')
        new = []
        for line in whole:
            try:
                new.append(json.loads(line.decode('utf-8', 'replace')))
            except ValueError:
                new.append({'ev': 'unreadable', 'text': line[:200].decode('utf-8', 'replace')})
        self.events += new
        return new

    def wait(self, pred, timeout, alive=lambda: True):
        """The next event, in order, that pred accepts; the events before it are passed over, those after it stay
        unread for the next wait. None at the timeout or when the game has ended without one."""
        end = time.time() + timeout
        while True:
            self.unread += self.poll()
            while self.unread:
                e = self.unread.pop(0)
                if pred(e):
                    return e
            if not alive() or time.time() >= end:
                self.unread += self.poll()
                while self.unread:
                    e = self.unread.pop(0)
                    if pred(e):
                        return e
                return None
            time.sleep(0.05)


# ---- candidates

@dataclass
class Candidate:
    label: str
    lines: list
    text: str


def unit(dx, dz):
    d = math.hypot(dx, dz)
    return (dx / d, dz / d) if d > 1e-3 else (0.0, 1.0)


def nearest_first(targets, pos):
    """Open targets in a greedy nearest-next order from pos (the others keep their place at the end)."""
    todo = [t for t in targets if t.status == 'open']
    out, x, z = [], pos[0], pos[2]
    while todo:
        t = min(todo, key=lambda t: math.hypot(t.x - x, t.z - z))
        todo.remove(t)
        out.append(t)
        x, z = t.x, t.z
    return out + [t for t in targets if t.status != 'open']


def edge_kind(r):
    """The kind of the planner's blocking edge (climb-up, climb-down, ledge-up, jump, crawl, ...), '' when not given."""
    e = r.get('edge')
    return (e.get('kind') or '') if isinstance(e, dict) else (e or '')


def world_plan():
    """The world model's planner (worldmodel/plan.py, over the data folder $PILOT_WORLD or world/): plan(area, from_xz, to_xz, from_y=, to_y=, radius=, doors=). With $ROUTELIB_DIR set it is wrapped by the
    route library (routelib.planner): the known way first, the world model's plan beyond the farthest known point."""
    try:
        sys.path.insert(0, str(PLAYTHROUGH))
        from worldmodel.plan import plan
    except Exception:   # noqa: BLE001  without it the pilot goes in straight lines
        return None
    if os.environ.get('ROUTELIB_DIR'):
        try:
            import routelib
            return routelib.planner(routelib.RouteLib(os.environ['ROUTELIB_DIR']), plan)
        except Exception:   # noqa: BLE001  (no readable library: the world model alone, as before)
            pass
    return plan


def fragments_for(area, target, pos):
    if not FRAGMENTS.exists() or not pos:
        return []
    best = []
    for line in FRAGMENTS.read_text().splitlines():
        f = json.loads(line)
        s = f['start']
        if f['area'] == area and f['target'] == target.name and math.hypot(s[0] - pos[0], s[2] - pos[2]) < 2.5:
            best.append(f)
    return best[-1:]


def yaw_to(dx, dz):
    return math.degrees(math.atan2(dx, dz))


def wrap(d):
    return (d + 180) % 360 - 180


HELD_SIGNALS = ('scene', 'pan', 'placed')


def held_signal(hist, step='', ran=0.0, prior=None, signals=HELD_SIGNALS):
    """Does an event (a scene, a talk, a message) hold Link, rather than a wall? From the pilot's own state lines only
    (with report 0.5 on: one every half second): hist the recent state lines, the last is now; step the running step's
    text ('' at a decision point); ran how long it has run; prior this function's last answer. Signals:
      scene    the music is a scene's own (Dm_*)
      pan      the camera turned more than 4 degrees between two state lines while Link stood (under 0.05 m) and no
               look or camera step ran: an event's camera; the follow camera turns only when Link moves or the right
               stick does (hold-2: still in the talks and the tutorial scene, flat while he waited with control)
      placed   Link's place jumped more than 3 m between two state lines half a second apart, no area loading: an
               event put him somewhere (a scene parks the Player at a fixed point, not where Link is drawn)
      persist  the prior answer was held and Link has not moved 0.5 m since
    A wall gives none of them: Link stands, the camera stays. Measured against the game's own flags by
    tools/holdeval.py (reports/PilotLoop2.md, "An event holds Link")."""
    now = hist[-1] if hist else {}
    pos = now.get('pos')
    if 'scene' in signals and (now.get('music') or '').startswith('Dm_'):
        return {'held': True, 'why': 'scene', 'at': pos}
    w = step.split()
    turning = bool(w) and w[0] in ('look', 'camera')
    for a, b in zip(hist[-7:-1], hist[-6:]):   # the last three seconds, pair by pair
        pa, pb = a.get('pos'), b.get('pos')
        if not (pa and pb) or (b.get('t') or 0) - (a.get('t') or 0) > 0.8:
            continue
        d = math.hypot(pb[0] - pa[0], pb[2] - pa[2])
        if 'placed' in signals and d > 3 and not a.get('loading') and not b.get('loading') and \
                a.get('area') == b.get('area'):
            return {'held': True, 'why': 'placed', 'at': pos}
        if 'pan' in signals and not turning and d < 0.05 and a.get('camera') is not None and b.get('camera') is not None \
                and abs(wrap(b['camera'] - a['camera'])) > 4:
            return {'held': True, 'why': 'pan', 'at': pos}
    if prior and prior.get('held') and prior.get('at') and pos and \
            math.hypot(prior['at'][0] - pos[0], prior['at'][2] - pos[2]) < 0.5:
        return {'held': True, 'why': 'persist', 'at': prior['at']}
    return {'held': False, 'why': None}


def duel_over(st, matches=1):
    """'met' once the game's log has said Match ended for `matches` different matches (the duel block's matches_ended: the
    tracker counts each match id once, whatever replays its line), 'interrupted' while the duel's state is Interrupted
    before that, else None."""
    d = st.get('duel') or {}
    if (d.get('matches_ended') or 0) >= matches:
        return 'met'
    return 'interrupted' if d.get('state') == 'Interrupted' else None


def duel_practice_due(d, mem):
    """The practice swing is due before the first Ready, and again when a Ready was refused because the game has read no
    sword power (a refusal that says to swing) and no practice swing was made since that refusal."""
    if d.get('state') in (None, 'Read terms') and not mem.get('practiced'):
        return True
    return 'swing your sword' in (d.get('refused') or '') and (d.get('refusals') or 0) != mem.get('practiced_at_refusals')


def duel_candidates(goal, target, st, mem):
    """The duel goal's moves by what the game's log says the duel is (the state line's `duel`) and where the other player
    is (`opponent`: distance and bearing relative to Link's own facing). A move takes about a second or two of game time, so
    that a decider asked once in 1.5 s keeps Link busy; at most ten candidates. A state in which there is one right move
    offers that one (the decider is not asked, and no request costs anything): the practice swing, Ready, the countdown, a
    round being closed. Ready is offered again after a round and after a match that ended with matches remaining."""
    d, opp, c = st.get('duel') or {}, st.get('opponent'), []
    state, pos, D = d.get('state'), st.get('pos'), deciders.DUEL
    add = lambda label, lines, text: c.append(Candidate(label, lines, text))   # noqa: E731
    if not pos:   # a load or a restart of the game
        add('wait', ['wait 1'], 'wait a second: the game is loading or restarting')
        return c
    ended, n = d.get('matches_ended') or 0, getattr(goal, 'matches', 1)
    if state in (None, 'Read terms', 'Round ended') or (state == 'Match ended' and ended < n):
        refused, run = d.get('refused'), d.get('refusal_run') or 0
        age = d.get('in_state_s')
        if state in ('Round ended', 'Match ended') and age is not None and age < D['ready_delay_s'] and not duel_practice_due(d, mem):
            # A Ready for the next round or match that reaches the other game before it has closed this one is dropped there (its
            # engine takes a Ready only in the round-ended or finished state, and the first game then waits in vain): let it get there.
            add('wait', ['wait 0.5'], 'wait: let the other game reach the same state before Ready')
            return c
        if duel_practice_due(d, mem):
            add('practice-swing', ['swing', 'wait 1'], 'one practice sword swing (Y), so that the game can read the sword\'s '
                'power: needed before Ready')
        elif d.get('own_ready') != 1:
            what = {'Round ended': 'the next round', 'Match ended': f'the next match (match {ended + 1} of {n})'}.get(state, 'the duel')
            add('ready', ['duel ready', 'wait 0.5'], f'say Ready for {what} (the round starts 3 s after both players are ready)')
        if d.get('own_ready') == 1 or (refused and c and c[0].label == 'ready'):
            add('wait', ['wait 1'], 'wait a second (for the other player, or for the game)')
        if run >= 3:
            add('give-up-goal', [], f"give up the duel: the game refused Ready {run} times in a row ({refused})")
        return c
    if state == 'Countdown':
        if opp:   # both players stand at their spawns now: the middle of the arena is between them
            mem['arena_mid'] = ((pos[0] + opp['x']) / 2, (pos[2] + opp['z']) / 2)
        if opp and opp.get('rel_deg') is not None and abs(opp['rel_deg']) > D['face_deg']:
            add('face', [f"face {D['face_to_deg']:g}"], f"turn toward him (he is {abs(opp['rel_deg']):.0f} degrees to Link's "
                                                          f"{'left' if opp['rel_deg'] > 0 else 'right'})")
        else:
            add('wait', ['wait 0.5'], 'wait: the countdown runs, then the fight starts')
        return c
    if state != 'Duel':   # Finishing round, Match ended (the last), Interrupted
        add('wait', ['wait 0.5'], 'wait: the round is being closed')
        return c
    if opp is None or opp.get('distance_m') is None:   # no place of him: guard and wait
        add('shield', ['shield 800', 'wait 0.1'], 'hold the shield up for 0.8 s (it blocks hits from the front only)')
        add('wait', ['wait 0.5'], 'wait: the opponent\'s place is not known')
        return c
    dist, rel, where = opp['distance_m'], opp.get('rel_deg'), opp.get('where')
    near = D['approach_m']
    if dist > D['swing_range_m']:
        add('approach', [f'approach {near:g} timeout 5'], f"walk toward him until {near:g} m from him (he is {dist:.1f} m "
                                                            f"away, {where}; his place is read again as he moves)")
    if rel is not None and abs(rel) > D['face_deg']:
        add('face', [f"face {D['face_to_deg']:g}"], f"turn toward him (he is {abs(rel):.0f} degrees to Link's "
                                                      f"{'left' if rel > 0 else 'right'})")
    if dist <= D['swing_range_m'] and (rel is None or abs(rel) <= D['swing_facing_deg']):
        add('swing', ['swing', 'wait 0.9'], f"swing the sword (Y), about a second: it hits when he is within "
            f"{D['swing_range_m']:g} m and in front (he is {dist:.1f} m away, {where})")
    add('shield', ['shield 800', 'wait 0.1'], 'hold the shield up for 0.8 s (it blocks hits from the front only)')
    mid = mem.get('arena_mid')

    def room(turn, metres):   # a move that carries Link away is offered only to a place near the arena's middle
        if mid is None:
            return False
        yaw = math.radians(opp['bearing_deg'] + turn)
        return math.hypot(pos[0] + metres * math.sin(yaw) - mid[0], pos[2] + metres * math.cos(yaw) - mid[1]) <= D['leash_m']
    step_m = D['sidestep_ms'] / 1000 * D['sidestep_m_per_s']
    if room(90.0, step_m):
        add('sidestep-left', [f"sidestep left {D['sidestep_ms']}", 'wait 0.1'], 'step sideways to Link\'s left of the line to him')
    if room(-90.0, step_m):
        add('sidestep-right', [f"sidestep right {D['sidestep_ms']}", 'wait 0.1'], 'step sideways to Link\'s right of the line to him')
    if room(180.0, D['roll_m']):
        add('roll-away', ['roll away', 'wait 0.8'], 'roll straight away from him (out of his reach)')
    if room(90.0, D['roll_m']):
        add('roll-left', ['roll around-left', 'wait 0.8'], 'roll sideways to Link\'s left of the line to him')
    if room(-90.0, D['roll_m']):
        add('roll-right', ['roll around-right', 'wait 0.8'], 'roll sideways to Link\'s right of the line to him')
    add('wait', ['wait 0.5'], 'wait half a second (idle)')
    return c


def interaction_goal(kind, g=None, cond=None):
    """Whether a goal is one of interact.py's interaction goals: its kind is one of interact.GOAL_KINDS, and a `fight` goal that
    names a `flag` is the older kind of PlayExplore17 (the state's flag says when it is met) and keeps its own candidates.
    Given the goal's condition instead of its TOML table: only a goal whose condition is interact's (it has met_state)."""
    if kind not in interact.GOAL_KINDS:
        return False
    if cond is not None:
        return hasattr(cond, 'met_state')
    return not (kind == 'fight' and g is not None and 'flag' in g)


def make_candidates(area, goal, target, st, mem, plan=None, bad=None):
    if interaction_goal(goal.kind, cond=goal.cond):
        return interact.candidates(area, goal, target, st, mem, plan)
    if goal.kind == 'duel':
        return duel_candidates(goal, target, st, mem)
    pos = st.get('pos')
    c = []
    if not pos:   # no Player read (a load): waiting is all there is
        return [Candidate('wait-goal', [f'until flag {goal.cond.text} timeout 20'], 'wait until the goal is met'),
                Candidate('wait', ['wait 2'], 'wait two seconds'), Candidate('next-target', [], 'leave this target')]
    if mem.get('cross_map') and target.follow:   # the other player is on another map: his place means nothing here
        return [Candidate('wait-friend', ['wait 3'], f'wait 3 s: {target.name} is on another map (his place means nothing on this one)'),
                Candidate('next-target', [], f'leave {target.name}'),
                Candidate('give-up-goal', [], f'give up the goal {goal.name}')]
    lx, ly, lz = pos
    tx, tz = target.x, target.z
    d = math.hypot(tx - lx, tz - lz)
    if target.exit:   # a crawl hole: the way in is the tunnel's own direction
        ux, uz = mem.setdefault('dir', unit(target.exit[0] - tx, target.exit[1] - tz))
    elif target.approach is not None:   # a door or a chest that opens only from one side, Link walking into it so
        ux, uz = math.sin(math.radians(target.approach)), math.cos(math.radians(target.approach))
    else:
        ux, uz = mem.setdefault('dir', unit(tx - lx, tz - lz))   # the way in, fixed when the target begins
    if target.kind == 'door':
        gx, gz, near_r = tx - 2.0 * ux, tz - 2.0 * uz, 0.6   # in front of the door, on Link's side
        if target.front:
            gx, gz = target.front
    elif target.front:   # where to stand before it (a chest's front side)
        (gx, gz), near_r = target.front, 0.4
    else:
        gx, gz, near_r = tx, tz, max(0.4, min(1.2, target.radius))
    run_t = lambda dist: int(max(6, dist / 3 + 5))   # noqa: E731
    dg = math.hypot(gx - lx, gz - lz)
    go = [f'run {gx:.2f} {gz:.2f} radius {target.radius:g} timeout {run_t(dg)}']
    why = f'run to {target.name} ({dg:.1f} m away, straight)'
    special = None   # a door or a ladder the planner found on the way: one candidate that deals with it
    if plan and target.kind != 'door':
        try:
            r = plan(area, (lx, lz), (gx, gz), from_y=ly, to_y=target.y, radius=target.radius,
                     doors=mem.get('doors', 'stop'))
        except Exception as e:   # noqa: BLE001  the planner's own failure must not end the run
            r = {'ok': False, 'why': f'planner error {type(e).__name__}'}
        mem['plan'] = {k: r.get(k) for k in ('ok', 'why', 'length', 'near', 'after')}
        to_near = list(r.get('steps') or [])
        if r.get('ok') and to_near:
            go, why = to_near, f"run to {target.name} along {len(to_near)} waypoints ({r.get('length', 0):.0f} m)"
        elif r.get('near'):
            nx, nz = r['near']
            if not to_near:
                to_near = [f'run {nx:.2f} {nz:.2f} radius 1 timeout {run_t(math.hypot(nx - lx, nz - lz))}']
            go, why = to_near, f"run to the reachable point nearest {target.name} (the planner: {r.get('why')})"
            if r.get('why') == 'needs-door' and r.get('after'):
                ax, az = r['after']
                special = Candidate('open-door-on-way', to_near + [
                    f'walk {ax:.2f} {az:.2f} radius 0.2 timeout 4', 'until flag 0x9824206c=Open timeout 6', 'press A',
                    'wait 1.5'], f'go to the door on the way to {target.name}, push against it and press A at its prompt')
            elif r.get('why') == 'needs-climb' and edge_kind(r) == 'climb-up':
                special = Candidate('climb-on-way', to_near + ['climb up timeout 12'],
                                    f'go to the foot of the ladder on the way to {target.name} and climb')
            elif r.get('why') in ('needs-jump', 'needs-drop') or (r.get('why') == 'needs-climb' and edge_kind(r) in ('ledge-up', 'climb-down')):
                found = interact.OBSTACLE_HOOK(area, st, r, to_near) if interact.OBSTACLE_HOOK else []   # actions.py: a jump, a ledge, a climb down, a drop
                special = Candidate(found[0].label, found[0].lines, found[0].text) if found else None
            elif r.get('why') == 'needs-crawl' and r.get('after'):
                ax, az = r['after']
                nx, nz = r['near']
                cx, cz = unit(ax - nx, az - nz)
                special = Candidate('crawl-on-way', to_near + [
                    f'walk {nx + cx:.2f} {nz + cz:.2f} radius 0.2 timeout 4', 'until flag 0x9824206c=Crawl timeout 3',
                    'press A', 'wait 1', f'walk {ax + 1.5 * cx:.2f} {az + 1.5 * cz:.2f} radius 0.7 timeout 25'],
                    f'go to the crawl hole on the way to {target.name}, into it, A at its Crawl prompt, and through '
                    f'to its far end')
    mem['detours'] = []
    if bad is not None:   # where Link got stuck before on this map: the route bends round it
        go, mem['detours'] = bad.reroute(area, (lx, lz), go)
        if mem['detours']:
            why += f" (round {len(mem['detours'])} place(s) where Link got stuck before)"
    fx, fz = unit(-ux, -uz)
    fa = st.get('facing')
    if fa is not None:   # back off against Link's facing
        fx, fz = -math.sin(math.radians(fa)), -math.cos(math.radians(fa))
    sx, sz = -uz, ux   # left of the way to the target (y up: left of +z is +x)
    beyond = lambda m: (tx + m * ux, tz + m * uz)   # noqa: E731
    walk = lambda x, z, r, t: f'walk {x:.2f} {z:.2f} radius {r:g} timeout {t}'   # noqa: E731
    add = lambda label, lines, text: c.append(Candidate(label, lines, text))   # noqa: E731
    kinds = {
        'reach': ['go', 'settle', 'press-a', 'talk-until-goal', 'press-a-through', 'wait-goal', 'back-off',
                  'side-left', 'side-right', 'next-target', 'give-up-goal'],
        'item': ['go', 'settle', 'press-a', 'talk-until-goal', 'wait-goal', 'back-off', 'side-left', 'side-right',
                 'next-target', 'give-up-goal'],
        'wait': ['wait-goal', 'press-a-through', 'talk-until-goal', 'press-a', 'go', 'back-off', 'side-left',
                 'side-right', 'next-target', 'give-up-goal'],
        'door': ['go-near', 'push-open', 'push', 'wait-prompt', 'press-a', 'push-through', 'wait-goal', 'back-off',
                 'side-left', 'side-right', 'go', 'next-target'],
        'talk': ['go-near', 'push', 'press-a', 'talk-until-goal', 'press-a-through', 'wait-goal', 'back-off',
                 'side-left', 'side-right', 'go', 'next-target', 'give-up-goal'],
        'chest': ['go-near', 'push', 'press-a', 'talk-until-goal', 'press-a-through', 'wait-goal', 'back-off',
                  'side-left', 'side-right', 'go', 'next-target', 'give-up-goal'],
        'crawl': ['go-near', 'crawl-in', 'push', 'press-a', 'crawl-forward', 'back-off', 'side-left', 'side-right',
                  'go', 'next-target'],
        'climb': ['go-near', 'climb-up', 'push', 'press-a', 'back-off', 'side-left', 'side-right', 'next-target'],
        # PlayExplore17 (2026-11-15): hold a place and fight what comes (a night field's undead, a dungeon room's plants): no goal flag
        # tells it is won, the state's life and the goal text are all the model has; every step is a hsap step that exists
        'fight': ['strike', 'swing-x3', 'guard', 'wait-a-moment', 'go-near', 'back-off', 'side-left', 'side-right', 'next-target'],
    }[target.kind]
    for k in kinds:
        if k == 'go':
            add('go', go, why)
        elif k == 'go-near':
            lead = go[:-1] if go is not None and len(go) > 1 and target.kind != 'door' else []
            add('go-near', lead + [walk(gx, gz, near_r, run_t(dg) + 4)],
                f"walk to {'the front of ' if target.kind == 'door' or target.front else ''}{target.name}, within {near_r:g} m "
                f"({dg:.1f} m away{', along the planned way' if lead else ''})")
        elif k == 'push':
            x, z = beyond(1.0)
            add('push', [walk(x, z, 0.2, 4)], f'walk into {target.name} (it ends stuck against it: pushing)')
        elif k == 'push-open':
            x, z = (gx + 3.0 * ux, gz + 3.0 * uz) if target.front else beyond(1.0)
            add('push-open', [walk(x, z, 0.2, 4), 'until flag 0x9824206c=Open timeout 3', 'press A', 'wait 1.5'],
                f'walk into {target.name}, wait up to 3 s for the A prompt to read Open, press A')
        elif k == 'push-through':
            x, z = beyond(2.5)
            add('push-through', [walk(x, z, 0.5, 8)], f'walk through {target.name} to 2.5 m beyond it')
        elif k == 'press-a':
            add('press-a', ['press A', 'wait 1'], 'press A once (act on the prompt), then wait a second')
        elif k == 'talk-until-goal':
            add('talk-until-goal', [f'until flag {goal.cond.text} timeout 20 press A every 1.5'],
                'press A every 1.5 s (talk, read, open, take) until the goal is met, at most 20 s')
        elif k == 'press-a-through':
            add('press-a-through', [f'until flag {goal.cond.text} timeout 60 press A every 2'],
                'press A every 2 s for up to 60 s: a talk or a scene that holds Link and goes on only with A (a '
                'tutorial scene took 24 presses), stopping at once if the goal is met')
        elif k == 'wait-goal':
            add('wait-goal', [f'until flag {goal.cond.text} timeout 40'],
                'wait without input until the goal is met (a scene plays), at most 40 s')
        elif k == 'settle':
            add('settle', [f'until flag {goal.cond.text} timeout 5'],
                'wait up to 5 s for the goal to be met where Link is (he may still be dropping or landing)')
        elif k == 'wait-prompt':
            add('wait-prompt', ['until flag 0x9824206c=Open timeout 6'], 'wait until the A prompt reads Open, at most 6 s')
        elif k == 'back-off':
            add('back-off', [walk(lx + 2.5 * fx, lz + 2.5 * fz, 0.5, 4)], 'step 2.5 m back, away from where Link faces')
        elif k in ('side-left', 'side-right'):
            s = 1 if k == 'side-left' else -1
            add(k, [walk(lx + 3 * s * sx, lz + 3 * s * sz, 0.5, 5)],
                f"step 3 m to the {k[5:]} of the way to {target.name}")
        elif k in ('crawl-forward', 'crawl-in'):
            # crawl-1 (2026-11-10): at the hole the A prompt reads Crawl; walking into it without A goes nowhere; after
            # A Link crawls at about 0.7 m/s, and a walk step steers him through
            x, z = (target.exit[0] + 1.5 * ux, target.exit[1] + 1.5 * uz) if target.exit else beyond(3.0)
            through = walk(x, z, 0.7, 25)
            if k == 'crawl-forward':
                add(k, [through], f'crawl on through {target.name} and out 1.5 m past its far end')
            else:
                add(k, [walk(tx - 0.3 * ux, tz - 0.3 * uz, 0.25, 5), 'until flag 0x9824206c=Crawl timeout 3', 'press A',
                        'wait 1', through], f'step into the mouth of {target.name}, wait up to 3 s for the A prompt to '
                    f'read Crawl, press A, and crawl through to 1.5 m past its far end')
        elif k == 'climb-up':
            add('climb-up', ['climb up timeout 12'], 'hold up on the stick while Link climbs')
        elif k == 'strike':
            # hold ZL (it locks on the nearest enemy and raises the shield) and slash three times while it is held
            add('strike', ['raw 0:ZL/1500,0.30:Y/100,0.75:Y/100,1.20:Y/100 1.8'],
                'lock on the nearest enemy (hold ZL for 1.5 s) and slash three times (Y); with nothing near it just raises the shield')
        elif k == 'swing-x3':
            add('swing-x3', ['swing', 'wait 0.4', 'swing', 'wait 0.4', 'swing', 'wait 0.5'],
                'slash three times (Y) in the direction Link faces, 0.4 s apart')
        elif k == 'guard':
            add('guard', ['shield 900'], 'hold the shield up (ZL) for 0.9 s')
        elif k == 'wait-a-moment':
            add('wait-a-moment', ['wait 2.5'], 'stand and wait 2.5 s (let enemies come to Link)')
        elif k == 'next-target':
            add('next-target', [], f"leave {target.name}: it is reached, or it failed{' (last target)' if mem.get('last') else ''}")
        elif k == 'give-up-goal':
            add('give-up-goal', [], f'give up the goal {goal.name}')
    if special:
        c.insert(1, special)
    if st.get('event') == 1 and not (st.get('music') or '').startswith('Dm_'):
        # the tap's event (EventMgr +104): a talk or a message holds Link; a scene with its own music is waited out
        c.insert(0, Candidate('talk-through', ['until control timeout 150 press A every 1.5'],
                              "an event holds Link (the tap's event is 1): A every 1.5 s until he is free, at most 150 s"))
    for f in ([] if target.follow else fragments_for(area, target, pos)):   # a moving target has no route to replay
        if len(c) < 12:
            add('fragment', f['lines'], f"replay the {len(f['lines'])} steps that reached {target.name} from here before")
    return c[:12]


# ---- the pilot

class Pilot:
    def __init__(self, seg, decider, ch, run_dir, run_id, alive, planner=None, max_decisions=None, follows=None,
                 follow_wait=900.0, recovery=None, human=None, bad=None, eyes=None, cross_map_wait=120.0, tactics=None, lessons=None, hud=None):
        """recovery: a recover.Config (or True) turns the stuck recovery and the decision guard on, None leaves the pilot as it
        was; human: a humanize.Human (None: level 0, every line goes out as made); bad: the recover.BadPoints memory (None: none
        is read or written); eyes: vision.make()'s object (None: no pictures); tactics: {book, sensor, mode, source} (make_tactics: the recovery ladder takes the
        library's order for the cause of a block and writes every attempt back; None: the old ladder); lessons: lessons.Lessons (None: the planner is asked as before); hud: a hud_text.Hud (None: no panel)."""
        self.seg, self.decider, self.ch, self.dir, self.run_id = seg, decider, ch, run_dir, run_id
        self.alive, self.planner = alive, planner
        self.goals = list(seg.goals)
        self.max_decisions = max_decisions or seg.max_decisions
        self.tr = open(run_dir / 'transcript.jsonl', 'a')
        self.tried, self.mem, self.ti, self.decisions = [], {}, {g.name: 0 for g in self.goals}, []
        self.met_at, self.target_start, self.frags, self.plans = {}, {}, [], []
        self.plan = None if getattr(seg, 'straight', False) else world_plan()
        self.fails = {}   # failures per goal (a target left as failed, the goal given up): the planner every third
        self.follows = dict(follows or {})   # name -> a JSON file {x, y, z, map, w} the runner keeps with another player's place
        self.follow_wait, self.cross_map_wait = follow_wait, cross_map_wait
        for g in self.goals:   # a duel has one opponent: of the follow targets a segment lists, the one this side was given
            named = [t for t in g.targets if t.follow in self.follows]
            if g.kind == 'duel' and named:
                g.targets = named
        self.last_decision_t, self.duel_seen = None, None   # (game time of the last decision; the last duel block seen)
        self.last_t = None
        self.bad = bad
        self.rec = recover.Recovery(bad, recovery if isinstance(recovery, recover.Config) else None, **(tactics or {})) if recovery else None
        self.lessons = lessons
        self.rstates = {}     # (goal, target) -> recover.RecState
        self.human, self.eyes = human or humanize.Human(0), eyes
        self.skipped = {}     # why a decision needed no question -> how many
        self.who = []         # who made each decision, in order: a driver's name, `gate` or `recover` (the summary's per-driver account)
        self.stuck_plans, self.sign_seen, self.sign_value = 0, 0, 1.0
        self.hud = hud if hud is not None else hud_text.Hud(None)   # what the pilot says on the game's own screen
        self.hud.configure(total=self.max_decisions, eyes=eyes is not None, on_error=lambda text: self.log(kind='hud', error=text))

    def read_follow(self, target):
        """The other player's place from the runner's file (replaced whole by rename, so a read is never torn), or None."""
        path = self.follows.get(target.follow)
        if path is None:
            return None
        try:
            f = json.loads(Path(path).read_text())
        except (OSError, ValueError):
            return None
        ok = isinstance(f, dict) and all(isinstance(f.get(k), (int, float)) for k in ('x', 'z'))
        return f if ok else None

    def refresh_follow(self, target, st, log=True):
        """Before a decision: a follow target takes the other player's place as it is now (only on the same map: another
        map's coordinates mean nothing here). Logged to the transcript with the file's age. True when it is on Link's map."""
        f = self.read_follow(target)
        if f is None:
            return False
        same = f.get('map') is None or st.get('area') is None or f['map'] == st['area']
        if same:
            target.x, target.z = float(f['x']), float(f['z'])
            if isinstance(f.get('y'), (int, float)):
                target.y = float(f['y'])
        if log:
            self.log(kind='follow', target=target.name, x=f['x'], z=f['z'], y=f.get('y'), map=f.get('map'), link_area=st.get('area'),
                     same_map=same, age_s=round(time.time() - f['w'], 2) if isinstance(f.get('w'), (int, float)) else None)
        return same

    def wait_follows(self, st):
        """Before the first decision: wait for every follow target's file (the runner writes it only when its own checks of
        where the other player is have passed), then take a fresh state of Link. A file that is there but names another map
        than Link's is waited for as long as `cross_map_wait`, with Link's own state read again every two seconds (a follower
        may start on another map and be brought to the friend's by the runner); after that the pilot goes on and the target
        offers only waiting until the maps agree. None when a file never came."""
        start = time.time()
        end, cross_end = start + self.follow_wait, start + min(self.cross_map_wait, self.follow_wait)
        todo = [t for g in self.goals for t in g.targets if t.follow]
        asked = 0.0
        while todo and time.time() < end and self.alive():
            elsewhere = []
            for t in list(todo):
                if self.read_follow(t) is not None:
                    if self.refresh_follow(t, st, log=False):
                        todo.remove(t)
                    else:
                        elsewhere.append(t)
            if not todo or (elsewhere and len(elsewhere) == len(todo) and time.time() >= cross_end):
                break
            if elsewhere and time.time() - asked >= 2.0:   # Link's own state again: he may have changed map meanwhile
                asked = time.time()
                st = self.sync(['wait 0.2'], 15) or st
                continue
            time.sleep(0.5)
        gone = [t for t in todo if self.read_follow(t) is None]
        if gone:
            self.log(kind='follow', status='never came', targets=[t.name for t in gone])
            return None
        if todo:
            self.log(kind='follow', status='other map', targets=[t.name for t in todo], link_area=st.get('area'))
        for g in self.goals:   # (the others of the segment keep the place they have from the file)
            for t in g.targets:
                if t.follow:
                    self.refresh_follow(t, st)
        return self.sync(['wait 0.2'], 15) or st   # (a step, so that the autopilot reports a state line after it)

    def log(self, **e):
        e['wall'] = round(time.time(), 2)
        self.tr.write(json.dumps(e) + '\n')
        self.tr.flush()

    def current(self):
        for g in self.goals:
            if g.status != 'open':
                continue
            i = self.ti[g.name]
            while i < len(g.targets) and g.targets[i].status != 'open':
                i += 1
            self.ti[g.name] = i
            if i < len(g.targets):
                return g, g.targets[i]
            g.status = 'failed'
            self.log(kind='goal', goal=g.name, status='failed', why='every target done or failed')
        return None, None

    def with_opponent(self, st, target):
        """A duel goal's state line with `opponent` made here from the follow file as it is now (distance, bearing, bearing
        relative to Link's facing), in place of the one the game side wrote at its own sample. Without a usable place
        (no file, another map) the state has no opponent."""
        f = self.read_follow(target) if target.follow else None
        block = hsap.opponent_block(st['pos'], st.get('facing'), f, time.time(), st.get('area')) if f and st.get('pos') else None
        out = {k: v for k, v in st.items() if k != 'opponent'}
        if block:
            out['opponent'] = block
        return out

    def sync(self, lines, budget=30.0):
        """Steps sent, then the state line the game side writes after them; None if the game ended or it did not come."""
        nums = self.ch.send(lines)
        got, end = 0, time.time() + budget
        while time.time() < end:
            e = self.ch.wait(lambda e: e['ev'] in ('step', 'bad', 'state', 'done'), end - time.time(), self.alive)
            if e is None or e['ev'] == 'done':
                return None
            if e['ev'] in ('step', 'bad') and e.get('in') in nums:
                got += 1
            elif e['ev'] == 'state' and e['why'] == 'wait' and got == len(nums):
                return e
        return None

    def pace_due(self, st, goal, target):
        """Whether the gap before the next request is worth waiting out: only before a decision that will ask a decider that
        costs money (it has a min_gap_s) among at least two candidates; with one candidate there is no request to space."""
        if not getattr(self.decider, 'min_gap_s', 0.0):
            return False
        mem = self.mem.setdefault((goal.name, target.name), {})
        return len(duel_candidates(goal, target, self.with_opponent(st, target), mem)) >= 2

    def pace(self, st, goal):
        """A decider that costs money (its min_gap_s) is asked at most once in that much game time: the rest of the gap
        since the last decision is waited out while the game goes on. Only for a duel goal."""
        gap = getattr(self.decider, 'min_gap_s', 0.0) if goal.kind == 'duel' else 0.0
        for _ in range(3):
            left = self.last_decision_t + gap - (st.get('t') or 0) if gap and self.last_decision_t is not None else 0
            if left <= 0.05:
                break
            fresh = self.sync([f'wait {left:.2f}'], 30 + left)
            if fresh is None:
                break
            self.log(kind='pace', waited_s=round(left, 2), t=fresh.get('t'))
            st = fresh
        return st

    def update_goals(self, st, step_index):
        flags = st.get('flags') or {}
        self.duel_seen = st.get('duel') or self.duel_seen
        for g in self.seg.goals:
            if g.status == 'met':
                continue
            cond = g.cond
            if hasattr(cond, 'observe'):
                cond.observe(st)
            if g.kind == 'duel':
                done = duel_over(st, g.matches) == 'met'
            elif hasattr(cond, 'met_state'):
                done = cond.met_state(st)
            else:
                done = cond.met(flags)
            if done:
                g.status = 'met'
                self.met_at[g.name] = step_index
                self.log(kind='goal', goal=g.name, status='met', t=st.get('t'), pos=st.get('pos'))
                print(f'  goal {g.name} met at {st.get("t")} s', flush=True)

    def handedness(self):
        """The stick's handedness the game side has learned (+1 or -1): the last `stick handedness flipped to` note."""
        events = self.ch.events
        for e in events[self.sign_seen:]:
            if e.get('ev') == 'note':
                m = re.search(r'stick handedness flipped to ([+-]\d)', e.get('text') or '')
                if m:
                    self.sign_value = float(m.group(1))
        self.sign_seen = len(events)
        return self.sign_value

    def validator(self, st):
        """For the humanized path: whether a point is reachable from the one before it, by the offline planner (None without
        one: the legs are then straight lines in any case)."""
        plan = self.plan
        if plan is None or not st.get('pos'):
            return None
        area, y = self.seg.area, st['pos'][1]

        def ok(a, b):
            chord = math.hypot(b[0] - a[0], b[1] - a[1])
            try:
                r = plan(area, a, b, from_y=y, radius=1.5)
            except Exception:   # noqa: BLE001  a planner that fails says nothing: keep the leg straight
                return False
            return bool(r.get('ok')) and (r.get('length') or chord) <= 1.35 * chord + 1.0
        return ok

    def rstate(self, key, st, target):
        """The recovery state of a target, made (and anchored at where Link stands) the first time it is looked at."""
        rs = self.rstates.get(key)
        if rs is None:
            rs = self.rstates[key] = self.rec.new_state()
            pos = st.get('pos')
            if pos:
                rs.progress.anchor(st.get('t'), (pos[0], pos[2]), math.hypot(target.x - pos[0], target.z - pos[2]))
        return rs

    @staticmethod
    def rec_dict(rs):
        v = rs.verdict
        return {'stuck': v['stuck'], 'why': v['why'], 'stalled_obs': v['stalled_obs'], 'stalled_s': v['stalled_s'],
                'rung': len(rs.tried), 'streak': rs.streak}

    def recovery_ctx(self, st, target, cands, dist):
        pos = st['pos']
        ctx = {'pos': (pos[0], pos[2]), 'camera': st.get('camera'), 'sign': self.handedness(),
               'target': {'x': target.x, 'z': target.z, 'radius': target.radius},
               'go_lines': next((c.lines for c in cands if c.label == 'go'), None),
               'hop_ok': target.kind not in ('door', 'talk', 'chest', 'duel') and st.get('event') != 1 and (dist or 0.0) > 3.0}
        if self.rec.book is not None:
            ctx.update(self.tactic_extras(st, target, cands))
        return ctx

    def tactic_extras(self, st, target, cands):
        """What the tactics need beyond the old ladder: the doors the world model knows near Link, the planner's alternative edge (the candidate that deals with a
        door, a ladder or a ledge on the way) and the planner's way from any point."""
        pos, area, plan = st['pos'], self.seg.area, self.plan
        world = getattr(self.rec.sensor, 'world', None)
        doors = []
        if world is not None:
            try:
                doors = [(d[1], d[2], d[3] if len(d) > 3 else 'door') for d in world.doors(area, pos[0], pos[2], 12.0)]
            except Exception:   # noqa: BLE001  the world model is an aid
                doors = []

        def plan_from(x, z):
            if plan is None:
                return None
            r = plan(area, (x, z), (target.x, target.z), from_y=pos[1], to_y=target.y, radius=target.radius, doors='stop')
            return list(r.get('steps') or []) if r.get('ok') else None

        climb_at = None
        if world is not None and hasattr(world, 'climbables'):
            try:
                near = world.climbables(area, pos[0], pos[2], 4.0)
                if near:
                    o = min(near, key=lambda o: math.hypot(o[1] - pos[0], o[2] - pos[2]))
                    climb_at = (o[1], o[2])
            except Exception:   # noqa: BLE001  the world model is an aid
                climb_at = None
        return {'doors': doors, 'event': st.get('event'), 'plan_from': plan_from, 'climb_at': climb_at,
                'alt_lines': next((list(c.lines) for c in cands if str(c.label).endswith('-on-way') and c.lines), None)}

    @staticmethod
    def left_of(r):
        """How far a move stopped from its own point, from its result's detail (None if it does not say)."""
        m = re.search(r'([0-9.]+) m from the point', (r or {}).get('detail') or '')
        return float(m.group(1)) if m else None

    def execute(self, lines, stepwise=False):
        """Send the lines and wait for their results and the state line after them: (results aligned with the lines sent, that
        state line or None when the game stopped answering, how many lines were sent). Stepwise (a travel candidate of several
        legs): one leg at a time, ending at the first leg that ended against something, so that the legs after it are not
        walked from the wrong place."""
        chunks = [[ln] for ln in lines] if stepwise and len(lines) > 1 else [list(lines)]
        results, sent, new = [], 0, None
        for chunk in chunks:
            nums = self.ch.send(chunk)
            budget = (20 if len(chunks) > 1 else 60) + 3 * sum(step_seconds(line) for line in chunk)
            got, new, end = {}, None, time.time() + budget
            while time.time() < end:
                e = self.ch.wait(lambda e: e['ev'] in ('step', 'bad', 'state', 'done'), end - time.time(), self.alive)
                if e is None:
                    break
                if e['ev'] in ('step', 'bad') and e.get('in') in nums:
                    got[e['in']] = e
                elif e['ev'] == 'state' and e['why'] == 'wait' and len(got) == len(nums):
                    new = e
                    break
                elif e['ev'] == 'done':
                    break
            part = [got.get(k) for k in nums]
            results += part
            sent += len(chunk)
            if new is None:
                return results, None, sent
            if len(chunks) > 1:
                r = part[0]
                if r and r['ev'] == 'step' and r['src'].split()[0] in MOVES and \
                        recover.is_blocked(r['result'], r.get('moved', 0.0), self.left_of(r)):
                    break
        return results, new, sent

    def maybe_plan(self, why, force=False):
        """The planner (optional): reorders the goals and targets. `force` (a stuck point: a local re-plan) goes past the
        four calls a run otherwise makes, up to the recovery's own limit."""
        if not self.planner:
            return
        if len(self.plans) >= 4 and not (force and self.rec and self.stuck_plans < self.rec.cfg.replans_max):
            return
        if force:
            self.stuck_plans += 1
        try:
            out, info = self.planner.plan(self.seg, self.goals, self.tried)
        except Exception as e:   # noqa: BLE001  the planner is optional: its failure is recorded, the run goes on
            self.log(kind='planner', why=why, error=f'{type(e).__name__}: {e}')
            return
        self.hud.spend(info.get('cost_usd'))
        before = [(g.name, [t.name for t in g.targets]) for g in self.goals]
        order = [n for n in out.get('order', []) if any(g.name == n and g.status != 'met' for g in self.goals)]
        rest = [g for g in self.goals if g.name not in order]
        self.goals = [next(g for g in self.goals if g.name == n) for n in order] + rest
        for spec in out.get('targets', []):
            g = next((g for g in self.goals if g.name == spec['goal']), None)
            if not g:
                continue
            named = [next(t for t in g.targets if t.name == n) for n in spec['order'] if any(t.name == n for t in g.targets)]
            g.targets = named + [t for t in g.targets if t not in named]
        for g in self.goals:
            if g.status == 'failed' and g.name in order:
                g.status = 'open'
                for t in g.targets:
                    if t.status == 'failed':
                        t.status = 'open'
                        self.mem.pop((g.name, t.name), None)
                        self.rstates.pop((g.name, t.name), None)
            for t in g.targets:
                if t.name in out.get('drop', []):
                    t.status = 'dropped'
            self.ti[g.name] = 0
        after = [(g.name, [t.name for t in g.targets]) for g in self.goals]
        entry = {'n': len(self.plans) + 1, 'why': why, 'answer': out, 'changed': before != after, 'before': before,
                 'after': after, **info}
        self.plans.append(entry)
        self.log(kind='planner', **entry)
        print(f"  planner ({why}): {'changed' if entry['changed'] else 'no change'}: {out.get('reason', '')[:120]}",
              flush=True)

    def recover_summary(self):
        """What the recovery did in this run, for summary.json: blocks (episodes) and how long each lasted in game seconds, the
        rungs used, the steps that ended stuck, the decisions that needed no question."""
        episodes = [e for rs in self.rstates.values() for e in rs.episodes]
        for e in episodes:   # a block still open when the run ended lasted until the last state
            if e.get('how') is None and self.last_t is not None and e.get('t0') is not None:
                e['s'] = round(self.last_t - e['t0'], 2)
        lengths = [e['s'] for e in episodes if e.get('s') is not None]
        out = {'on': self.rec is not None, 'blocks': len(episodes),
               'recovered': sum(e.get('how') == 'recovered' for e in episodes),
               'marked_bad': sum(e.get('how') == 'marked-bad' for e in episodes),
               'left': sum(e.get('how') == 'left' for e in episodes), 'open': sum(e.get('how') is None for e in episodes),
               'longest_s': max(lengths, default=0.0), 'over_10s': sum(s > 10.0 for s in lengths),
               'stuck_steps': sum(t['result'] == 'stuck' for t in self.tried),
               'rungs': {k: self.decisions.count(k) for k in sorted({d for d in self.decisions if d.startswith('recover:')})},
               'planner_replans': self.stuck_plans, 'no_question': dict(self.skipped), 'episodes': episodes}
        if self.rec is not None and self.rec.book is not None:   # the tactics library: what the blocks were and what each tactic did (the A/B's numbers)
            out['mode'] = self.rec.mode
            out['causes'] = {c: sum(e.get('cause') == c for e in episodes) for c in sorted({e.get('cause') for e in episodes if e.get('cause')})}
            tac = {}
            for a in self.rec.history:
                t = tac.setdefault(a['tactic'], {'tried': 0, 'worked': 0})
                t['tried'] += 1
                t['worked'] += a['outcome'] == 'worked'
            out['tactics'] = tac
        return out

    def counterfactual(self, n, st, goal, target, cands, mem, choice):
        """What the picture changed: after a decision that was made with a fresh look and a real question, the decider is asked
        once more about the same moment without the picture (the state without `vision`, the candidates without the eyes' own).
        Its answer is not used; the transcript row says what it would have chosen and what that request cost."""
        plain = [c for c in cands if not c.label.startswith('vision-')]
        without = {k: v for k, v in st.items() if k != 'vision'}
        try:
            other = self.decider.choose(deciders.Context(without, goal, target, plain, copy.deepcopy(mem), list(self.tried), self.seg))
        except Exception as e:   # noqa: BLE001  a measurement, never a reason to stop
            self.log(kind='counterfactual', n=n, with_vision=choice.label, error=f'{type(e).__name__}: {e}')
            return
        self.hud.spend(other.info.get('cost_usd'))
        self.log(kind='counterfactual', n=n, with_vision=choice.label, without_vision=other.label,
                 cost_usd=other.info.get('cost_usd'), asked='request' in other.info)

    def forced_choice(self, forced, rs, st, goal, target, cands, mem):
        """The decision a guard made without a question: (choice, candidate, who). A recovery action is a candidate of its own
        (label recover:<rung>), recorded like any other decision."""
        kind = forced[0]
        if kind == 'choice':
            cand = next(c for c in cands if c.label == forced[1])
            self.skipped[forced[2]] = self.skipped.get(forced[2], 0) + 1
            if forced[2] == 'identical answers':   # left because nothing came of the same answer again and again: not a success
                mem['left_failed'] = True
            return deciders.Choice(cand.label, info={'no_request': forced[2]}), cand, 'gate'
        pos = st['pos']
        dist = math.hypot(target.x - pos[0], target.z - pos[2])
        ctx = self.recovery_ctx(st, target, cands, dist)
        if kind == 'close-in':
            act = self.rec.close_in(ctx)
        else:
            if rs.blocked is None:   # the guard saw a stuck state the monitor had not (an unchanged state, identical answers)
                ev = self.rec.start_block(rs, self.seg.area, (pos[0], pos[2]), st.get('t'), rs.last_label or '',
                                          (rs.last_go or {}).get('lines') or [], [], target.name, forced[1], st=st, target=target)
                self.log(kind='recover', n=len(self.decisions) + 1, target=target.name, **ev)
            seen = next((c for c in cands if c.label in recover.VISION_RUNGS), None)
            if seen is not None and not rs.vision_used:   # what the eyes make of the place goes before the blind rungs, once a block
                rs.vision_used = True
                rs.tried.append('vision')
                self.skipped['recover'] = self.skipped.get('recover', 0) + 1
                return (deciders.Choice(seen.label, info={'no_request': 'recover', 'recover_rung': 'vision', 'recover_why': forced[1]}),
                        seen, 'recover')
            act = self.rec.action(rs, ctx)
        self.skipped['recover'] = self.skipped.get('recover', 0) + 1
        info = {'no_request': 'recover', 'recover_rung': act.rung, 'recover_why': forced[1]}
        if getattr(act, 'info', None):   # the tactics library: the cause of the block and the order this rung was taken from
            info.update(recover_cause=act.info['cause'], recover_order=act.info['order'])
        return deciders.Choice(act.label, info=info), act, 'recover'

    def run(self, first_state):
        st, outcome = first_state, None
        step_index = 0
        if any(t.follow for g in self.goals for t in g.targets):
            st = self.wait_follows(st)
            if st is None:
                return 'no place of the other player: the follow file never came'
        # a duel's game-time budget counts from the first decision (the runner's gate, which can take minutes of room, save
        # copy and kit, opens it), as in every other segment it counts from the first state
        self.budget_from = (st.get('t') or 0) if any(g.kind == 'duel' for g in self.goals) else 0.0
        self.update_goals(st, 0)
        if self.rec and self.bad is not None:   # checkpoints inside a bad point's circle move to its edge
            nudged = recover.nudge_segment(self.seg, self.bad)
            if nudged:
                self.log(kind='bad-points', nudged=nudged)
        if self.planner:
            self.maybe_plan('start')
        while True:
            self.last_t = st.get('t')
            if all(g.status == 'met' for g in self.seg.goals):
                outcome = 'solved'
                break
            for g in self.goals:   # a goal visited nearest first: its open targets ordered once, when it comes up
                if g.status == 'open' and g.order == 'nearest' and not g.sorted and st.get('pos'):
                    g.targets = nearest_first(g.targets, st['pos'])
                    g.sorted = True
                    self.ti[g.name] = 0
                    break
                if g.status == 'open':
                    break
            goal, target = self.current()
            if not goal:
                outcome = 'gave up: every open goal failed'
                break
            if len(self.decisions) >= self.max_decisions:
                outcome = f'budget: {self.max_decisions} decisions'
                break
            if (st.get('t') or 0) - self.budget_from > self.seg.budget:
                outcome = f'budget: {self.seg.budget:g} s of game time'
                break
            if goal.kind == 'duel':
                if self.pace_due(st, goal, target):
                    st = self.pace(st, goal)
                self.update_goals(st, step_index)   # the match may have ended while the pilot waited
                over = duel_over(st, goal.matches)
                if over == 'met':
                    continue   # (the top of the loop ends the run: solved)
                if over == 'interrupted':
                    reason = (st.get('duel') or {}).get('reason') or 'no reason given'
                    goal.status = 'failed'
                    self.log(kind='goal', goal=goal.name, status='failed', why=f'duel interrupted: {reason}')
                    outcome = f'duel interrupted: {reason}'
                    break
                st = self.with_opponent(st, target)
            key = (goal.name, target.name)
            mem = self.mem.setdefault(key, {})
            if key not in self.target_start:
                self.target_start[key] = (len(self.tried), st.get('pos'))
            mem['last'] = target is goal.targets[-1]
            if any(g.kind == 'door' and g.status == 'met' for g in self.seg.goals):
                mem.setdefault('doors', 'through')   # the segment's own door is open: plan through it
            if self.plan is None and not getattr(self.seg, 'straight', False):   # the planner's module may be mid-rewrite by its owner: tried again each time
                self.plan = world_plan()
            if target.follow:
                mem['cross_map'] = not self.refresh_follow(target, st)
            rs = None
            if self.rec and goal.kind != 'duel':
                rs = self.rstate(key, st, target)
                mem['recover'] = self.rec_dict(rs)
            look = None
            if self.eyes is not None and goal.kind != 'duel':   # a look at the screen, where the eyes find a reason to
                look = self.eyes.before_decision(st, goal=goal, target=target, mem=mem, tried=self.tried,
                                                 n=len(self.decisions) + 1)
                if look is not None:
                    st = dict(st, vision=look.hint)
                    if getattr(look, 'fresh', False) and getattr(look, 'row', None):
                        self.hud.look(look.row)   # (a look reused from before costs nothing again)
            if interaction_goal(goal.kind, cond=goal.cond):   # what is near Link, from the offline world model
                st = interact.with_near(self.seg.area, st)
            cands = make_candidates(self.seg.area, goal, target, st, mem, self.plan, bad=self.bad if rs is not None else None)
            if look is not None:
                cands += [Candidate(*e) for e in (getattr(look, 'extra', None) or [])]
            forced = None
            if rs is not None and st.get('pos'):
                pos = st['pos']
                cands, forced = self.rec.gate(rs, cands, target, st, mem, math.hypot(target.x - pos[0], target.z - pos[2]))
            ctx = deciders.Context(st, goal, target, cands, mem, self.tried, self.seg)
            asked, who = False, self.decider.name
            t0 = time.perf_counter()
            self.hud.deciding(len(self.decisions) + 1, goal, target, st.get('t'), self.decider.name, [c.label for c in cands],
                              model=getattr(self.decider, 'model', None) if forced is None else None, recover=mem.get('recover'))
            if forced is None:
                choice = self.decider.choose(ctx)
                for ev in getattr(self.decider, 'drain_events', lambda: [])():   # a driver that failed and the chain went on
                    self.log(n=len(self.decisions) + 1, **ev)
                    print(f"  {len(self.decisions) + 1:3d} driver {ev['driver']} {ev['failure']}: {ev['reason'][:100]}"
                          f"{' -> ' + ev['to'] if ev.get('to') else ' (no driver left)'}", flush=True)
                who = getattr(choice, 'driver', None) or who
                if getattr(self.decider, 'stop_reason', None):   # the model was stopped (cost, refusals, a cap): no more
                    self.log(kind='stop', why=self.decider.stop_reason, **choice.info)
                    outcome = f'stopped: {self.decider.stop_reason}'
                    print(f'  STOP: {self.decider.stop_reason}', flush=True)
                    break
                cand = next((c for c in cands if c.label == choice.label), None)
                if cand is None and getattr(choice, 'candidate', None):   # a step the driver brought: a script, a recorded chunk, an agent's own
                    cand = Candidate(*choice.candidate)
                    cands = cands + [cand]
                if cand is None:   # a label not offered: rules, and their first offered step if theirs is not either
                    choice = deciders.Rules().choose(ctx)
                    cand = next((c for c in cands if c.label == choice.label), cands[0])
                    choice.label = cand.label
                asked = 'request' in choice.info
            else:
                choice, cand, who = self.forced_choice(forced, rs, st, goal, target, cands, mem)
                cands = [cand] if who == 'recover' else cands
            ms = (time.perf_counter() - t0) * 1000
            n = len(self.decisions) + 1
            self.decisions.append(choice.label)
            self.who.append(who)
            if rs is not None:
                self.rec.note_answer(rs, cand.label, cand.lines, st, cands, asked)
                mem['recover'] = self.rec_dict(rs)
            if goal.kind == 'duel' and 'request' in choice.info:   # (a decision that made no request costs nothing)
                self.last_decision_t = st.get('t')
            self.log(kind='decision', n=n, state=st, goal=goal.name, target=target.name, decider=who,
                     candidates=[c.__dict__ for c in cands], choice=choice.label, predicates=choice.predicates,
                     plan=mem.get('plan') if self.plan else 'no planner',
                     decide_ms=round(ms, 1), **({'recover': mem['recover']} if rs is not None else {}), **choice.info)
            self.hud.decided(cand.label, who, [c.label for c in cands], choice.info, recover=mem.get('recover'))
            if look is not None and getattr(look, 'fresh', False) and asked and goal.kind != 'duel':
                self.counterfactual(n, st, goal, target, cands, mem, choice)
            if cand.label in ('next-target', 'give-up-goal'):
                h = mem.get('history', [])
                ok = bool(h) and h[-1][0] not in deciders.RECOVERY and h[-1][1] in REACHED and not mem.get('left_failed')
                if cand.label == 'give-up-goal':
                    goal.status = 'failed'
                else:
                    target.status = 'done' if ok else 'failed'
                    if ok:
                        self.keep_fragment(goal, target, mem)
                h.append((cand.label, 'done', 0.0, None))
                print(f'  {n:3d} {goal.name}/{target.name}: {cand.label} ({target.status})', flush=True)
                self.hud.result('failed' if goal.status == 'failed' else target.status, goal, st.get('t'), mem.get('recover'))
                if rs is not None and rs.blocked is not None:   # left while blocked: the block ends here
                    self.rec.close_episode(rs, st.get('t'), 'left', area=self.seg.area, run=self.run_id)
                    rs.blocked = None
                if target.status == 'failed' or goal.status == 'failed':   # the planner at every third failure
                    self.fails[goal.name] = self.fails.get(goal.name, 0) + 1
                    if self.fails[goal.name] % 3 == 0 or goal.status == 'failed':
                        self.maybe_plan(f'goal {goal.name} failed {self.fails[goal.name]} times')
                continue
            if getattr(cand, 'kind', 'lines') == 'replan':   # the ladder is spent: the point is marked bad, the target left
                ev = self.rec.marked_bad(rs, self.seg.area, st, self.run_id, target.name,
                                         dist=math.hypot(target.x - st['pos'][0], target.z - st['pos'][2]))
                self.log(kind='recover', n=n, target=target.name, **ev)
                self.tried.append({'step': 'recover:replan', 'goal': goal.name, 'target': target.name, 'result': 'marked-bad',
                                   'moved_m': 0.0, 'at': ev['at']})
                mem.setdefault('history', []).append(('recover:replan', 'done', 0.0, None))
                target.status = 'failed'
                self.fails[goal.name] = self.fails.get(goal.name, 0) + 1
                print(f'  {n:3d} {goal.name}/{target.name}: recover:replan (marked bad at {ev["at"]}, target left)', flush=True)
                self.hud.result('marked-bad', goal, st.get('t'), mem.get('recover'))
                self.maybe_plan(f'stuck at {ev["at"]} on {target.name}', force=True)
                continue
            lines, notes = list(cand.lines), {}
            if self.human.on and goal.kind != 'duel' and who != 'recover':   # moves like a person: delays, curves, looks
                shaped = self.human.shape(cand.label, cand.lines, st, target, n, sign=self.handedness(), validate=self.validator(st),
                                          curves_ok=not (mem.get('blocked_lines') or mem.get('detours')) and not (rs and rs.blocked))
                lines, notes = shaped.lines, shaped.notes
            mem.setdefault('lines', []).extend(cand.lines)
            if cand.label == 'practice-swing':
                mem['practiced'] = True
                mem['practiced_at_refusals'] = (st.get('duel') or {}).get('refusals') or 0
            if cand.label == 'open-door-on-way':
                mem['doors'] = 'through'   # the planner plans past that door from now on
            results, new, sent = self.execute(lines, stepwise=self.rec is not None and recover.is_travel(cand.label))
            step_index += sent
            if new is None:
                self.log(kind='result', n=n, lines=lines[:sent], steps=results, lost=True)
                outcome = 'the game stopped answering' if self.alive() else 'the game ended'
                break
            last = history_step(results)
            result = last['result'] if last else 'bad'
            moved = round(sum(r.get('moved', 0) for r in results if r and r['ev'] == 'step'), 2)
            left = self.left_of(last)   # how far a move stopped from its point
            mem.setdefault('history', []).append((cand.label, result, moved, left))
            self.tried.append({'step': cand.label, 'goal': goal.name, 'target': target.name, 'result': result,
                               'moved_m': moved})
            inter = interact.interaction_of(cand.label, results, before=st, after=new)   # what the step changed in the world
            if inter:
                mem.setdefault('interactions', []).append(inter)
            if hasattr(goal.cond, 'note'):
                goal.cond.note(inter, new)
            self.log(kind='result', n=n, lines=lines[:sent], steps=results, result=result, moved=moved, interaction=inter,
                     **({'humanized': notes} if notes else {}))
            print(f"  {n:3d} {goal.name}/{target.name}: {cand.label} -> {result}, moved {moved} m; "
                  f"{choice.info.get('latency_ms', '')}{' ms' if 'latency_ms' in choice.info else ''}"
                  f"{' FALLBACK ' + choice.info['fallback'] if 'fallback' in choice.info else ''}", flush=True)
            st = new
            self.update_goals(st, step_index)
            if rs is not None:
                for ev in self.rec.observe(rs, self.seg.area, target, cand.label, cand.lines, results, result, moved, left, st,
                                           run=self.run_id):
                    self.log(kind='recover', n=n, target=target.name, **ev)
                    if ev['status'] == 'blocked' and cand.label in recover.NO_REPEAT:
                        mem.setdefault('blocked_lines', []).append((tuple(ev['at']), list(cand.lines)))
                mem['recover'] = self.rec_dict(rs)
            self.hud.result(result, goal, st.get('t'), mem.get('recover'))
        self.hud.finish(outcome)
        return outcome

    def keep_fragment(self, goal, target, mem):
        """The steps sent for a target that was reached, from where it began: a fragment later runs may replay."""
        _, start = self.target_start.get((goal.name, target.name), (None, None))
        if start and mem.get('lines') and not target.follow:
            self.frags.append({'area': self.seg.area, 'segment': self.seg.name, 'goal': goal.name,
                               'target': target.name, 'start': start, 'lines': list(mem['lines']), 'run': self.run_id})


def history_step(results):
    """The step whose result word stands for a candidate in the history: the last move, unless the candidate ends with an interaction
    step (a run to a far spot, then the pickup there), which is the step that tells what happened (pi-solo-3: the pickup ended `none`, the
    run before it `reached`, and the history said reached, so the dive that follows a pickup that found nothing was never offered). None
    when no step answered."""
    got = [r for r in results if r]
    if not got:
        return None
    move = [r for r in got if r['ev'] == 'step' and r['src'].split()[0] in MOVES + ('until', 'climb', 'approach')]
    tail = got[-1]
    if move and tail['ev'] == 'step' and tail['src'].split()[0] in interact.DECIDING:
        return tail
    return (move or got)[-1]


def step_seconds(line):
    s = interact.step_seconds(line)   # the interaction steps' own allowances
    if s is not None:
        return s
    w = line.split()
    if 'timeout' in w:
        return float(w[w.index('timeout') + 1])
    if w[0] in ('wait',):
        return float(w[1])
    if w[0] == 'shield':
        return (float(w[1]) if len(w) > 1 else 700) / 1000 + 1
    if w[0] == 'sidestep' and len(w) > 2:
        return float(w[2]) / 1000 + 1
    if w[0] == 'raw':   # raw <presses> <wait s>: the wait is the last word
        return float(w[-1]) + 2
    return {'walk': 30, 'run': 30, 'until': 30, 'climb': 20, 'save': 60, 'approach': 20, 'face': 3, 'roll': 2}.get(w[0], 2)


# ---- the route a solved segment becomes

def export_route(seg, run_dir, run_id, decider_name, ch_events):
    """The steps that reached the goals as an ordinary route: every step as sent, in order, except moves that ended
    stuck, timed out or cut having moved under 0.3 m; an expect after the step in which each goal was first met."""
    steps = [e for e in ch_events if e['ev'] == 'step' and e.get('in')]
    first_met = {}
    for e in ch_events:   # the step after which each goal's flag was first seen met
        if e['ev'] == 'state':
            for g in seg.goals:
                if g.name not in first_met and g.cond.met(e.get('flags') or {}):
                    first_met[g.name] = e.get('in', 0)
    out = [f'# {seg.name}: exported by pilot.py from run {run_id} (decider {decider_name}), {datetime.date.today()}',
           f'# {seg.what}', f'expect area {seg.area}']
    kept = 0
    for e in steps:
        w = e['src'].split()
        if w[0] in MOVES and e['result'] in ('stuck', 'timeout', 'cut') and e.get('moved', 0) < 0.3:
            out.append(f"# left out: {e['src']} ({e['result']}, moved {e.get('moved', 0)} m)")
            continue
        out.append(e['src'])
        kept += 1
        for g in seg.goals:
            if first_met.get(g.name) == e['in']:
                out.append(f'expect flag {g.cond.text}')
    done = set(first_met)
    for g in seg.goals:
        if g.name in done and f'expect flag {g.cond.text}' not in out:
            out.append(f'expect flag {g.cond.text}')
    route = run_dir / 'route.txt'
    route.write_text('\n'.join(out) + '\n')
    lib = HERE / 'routes' / f'{seg.name}-{run_id}.txt'
    lib.parent.mkdir(exist_ok=True)
    shutil.copy(route, lib)
    return lib, kept


# ---- commands

def make_decider(args, client):
    if args.decider == 'rules':
        return deciders.Rules(), None
    if args.decider == 'replay':
        return deciders.Replay(args.replay), None
    real = not args.api_base
    if real and openai_api.key_state() not in ('file', 'env'):
        print(f'openai-decisions: {openai_api.key_state()}; the run uses rules', flush=True)
        return deciders.Rules(), 'no key'
    try:
        return deciders.Decisions(client), None
    except openai_api.CapReached as e:   # (no caps file: a fresh tree)
        print(f'openai-decisions: {e}; the run uses rules', flush=True)
        return deciders.Rules(), 'no caps'


def private_world():
    """The world model's objects and nav meshes as the tactics' sensor asks them (routelib.PrivateWorld), or None where there is none (a publishable tree)."""
    try:
        import routelib
        return routelib.PrivateWorld(PLAYTHROUGH / 'world')
    except Exception:   # noqa: BLE001  no world model: the sensor knows only what the steps say
        return None


def make_tactics(args, world='auto'):
    """The tactics library of a run (tactics.py) as pilot.Pilot's `tactics` settings, or None for the pilot's old ladder. --tactics (else $PILOT_TACTICS, else
    ranked): `ranked` the library's order for the cause of a block, every attempt written back; `fixed` the old order, attempts still written back (the A/B's
    control arm learns too); `explore` the order with the optimism bonus (the nightly self-play); `off` the old ladder, nothing read or written.
    $PILOT_LEARN=off turns it (and the lessons) off unless the flag says otherwise. --tactics-readonly (or $PILOT_TACTICS_READONLY=1) reads the library and never writes it
    (a scoreboard's cells must not learn from their own test); the summary's numbers are still kept."""
    mode = getattr(args, 'tactics', None) or ('off' if os.environ.get('PILOT_LEARN') == 'off' else os.environ.get('PILOT_TACTICS') or 'ranked')
    if mode not in ('ranked', 'fixed', 'explore'):
        return None
    readonly = bool(getattr(args, 'tactics_readonly', False)) or os.environ.get('PILOT_TACTICS_READONLY', '').lower() in ('1', 'on', 'yes', 'true')
    return {'book': tactics_lib.Book(getattr(args, 'tactics_dir', None), readonly=readonly), 'sensor': tactics_lib.Sensor(private_world() if world == 'auto' else world), 'mode': mode,
            'source': getattr(args, 'tactics_source', None) or 'live'}


def make_lessons(args, learn=None):
    """The lessons for the planner's prompt (lessons.py): the few most similar past failures and what finally worked, or None when switched off
    (--lessons, else $PILOT_LESSONS, else on; $PILOT_LEARN=off turns it off unless the flag says otherwise)."""
    import lessons
    book = learn['book'] if learn else tactics_lib.Book(getattr(args, 'tactics_dir', None), readonly=True)
    return lessons.make(getattr(args, 'lessons', None), book)


def who_runs(who):
    """The decisions' makers in order as runs: [[first n, last n, who], ...] (n counts from 1)."""
    out = []
    for i, w in enumerate(who, 1):
        if out and out[-1][2] == w and out[-1][1] == i - 1:
            out[-1][1] = i
        else:
            out.append([i, i, w])
    return out


def make_planner(client, args):
    """The planner (a model asked for route help) when it was asked for and can be had: a key (or a stand-in) and a caps file."""
    if not args.planner or not (args.api_base or openai_api.key_state() in ('file', 'env')):
        return None
    try:
        return deciders.Planner(client)
    except openai_api.CapReached as e:
        print(f'planner: {e}; no planner', flush=True)
        return None


def watch_lines(names, width=250):
    """watch control lines for these flags, each under the autopilot's 255 characters a line (a longer line is
    refused whole: run b-rules-1 watched nothing); the autopilot adds the flags of every watch line to its list."""
    out, cur = [], 'watch'
    for n in names:
        if len(cur) + 1 + len(n) > width and cur != 'watch':
            out.append(cur)
            cur = 'watch'
        cur += ' ' + n
    return out + ([cur] if cur != 'watch' else [])


def runner_env():
    env = dict(os.environ)
    for k in SLOT_VARS:
        env.pop(k, None)
    for k in ('OPENAI_API_KEY', 'OPENROUTER_API_KEY', 'PILOT_CHAT_API_KEY'):   # the game and the sandbox never see a key
        env.pop(k, None)
    return env


def panel_note(run_dir, text):
    """One line for the live panel (live_panel.py reads <run folder>/panel-notes.txt): the placement's result and any fallback."""
    try:
        with open(run_dir / 'panel-notes.txt', 'a') as f:
            f.write(time.strftime('%H:%M:%S ') + text.replace('\n', ' ')[:300] + '\n')
    except OSError:
        pass


def humanize_level(args, seg, chain_default=None):
    """The humanize level of a run: --humanize, else the segment's own `humanize`, else the chain's own (a scripted or replayed run:
    0, so that it gives the same result every time), else 2 (exploration) and 0 for a duel (its moves are timed to the game: no
    delays, no curves)."""
    if getattr(args, 'humanize', None) is not None:
        return args.humanize
    if seg.humanize is not None:
        return int(seg.humanize)
    if chain_default is not None:
        return chain_default
    return 0 if any(g.kind == 'duel' for g in seg.goals) else 2


def cmd_run(args):
    chapter = None   # a TOML file with an `aim` is a chapter (sections.py): the pilot plays objectives a planner model makes from it
    if str(args.segment).endswith('.toml'):
        sys.modules.setdefault('pilot', sys.modules[__name__])
        import sections
        chapter = sections.load_if_chapter(args.segment)
    seg = sections.segment_for(chapter) if chapter else Segment(args.segment)
    if getattr(args, 'matches', None):
        seg.set_matches(args.matches)   # (a duel series: every duel goal asks for that many matches; budgets scale with it)
    copy = Path(args.copy or COPY)
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    if getattr(args, 'driver', None) and getattr(args, 'decider', None):
        print('--driver and --decider both say who decides: use one (--decider is the older way: rules, replay, openai-decisions)',
              file=sys.stderr)
        return 2
    try:
        want, fallbacks, table = drivers.resolve(args, seg)
    except ValueError as e:
        print(f'driver: {e}', file=sys.stderr)
        return 2
    use_chain = want is not None and not getattr(args, 'decider', None)   # (an explicit --decider is the older way and wins over a scenario)
    if not use_chain:
        args.decider = getattr(args, 'decider', None) or 'rules'
    run_id = args.tag or f'{seg.name}-{(want or "default") if use_chain else args.decider}-{stamp}'
    run_dir = HERE / 'runs' / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    allowance = (datetime.datetime.fromisoformat(args.allowance_since).timestamp(), args.allowance_usd) \
        if args.allowance_usd is not None else None
    client = openai_api.Client(run_id, seg.name, args.api_base, allowance)
    chain, settings = None, {'recovery': True, 'humanize': None}
    if use_chain:
        try:
            chain = drivers.build_chain(want, fallbacks, args=args, table=table, client=client, run_id=run_id, segment=seg.name,
                                        run_dir=run_dir, copy=copy)
        except ValueError as e:
            print(f'driver: {e}', file=sys.stderr)
            shutil.rmtree(run_dir, ignore_errors=True)
            return 2
        decider, note = chain, None
        availability = chain.probe()
        settings = drivers.run_settings(chain)
        for line in drivers.start(chain, run_id=run_id, segment=seg.name, copy=copy, briefing=deciders.DEVELOPER):
            print('  ' + line, flush=True)
        print('  driver chain: ' + ' -> '.join(n + ('' if ok else f' [{why}]') for n, (ok, why) in availability.items())
              + (f'  ({"; ".join(chain.notes)})' if chain.notes else ''), flush=True)
    else:
        decider, note = make_decider(args, client)
    planner = make_planner(client, args)
    level = humanize_level(args, seg, settings['humanize'])
    seed = getattr(args, 'humanize_seed', None)
    if seed is None:
        seed = int(hashlib.sha256(run_id.encode()).hexdigest()[:8], 16)
    human = humanize.Human(level, seed)
    recovery = bool(getattr(args, 'recover', True)) and args.decider != 'replay' and settings['recovery']   # (a replay must meet exactly the questions it recorded)
    bad = recover.BadPoints(getattr(args, 'bad_points', None)) if recovery and not getattr(args, 'no_bad_points', False) else None
    learn = make_tactics(args) if recovery else None
    less = make_lessons(args, learn)
    if planner is not None:
        planner.lessons = less   # (the goal-level planner reads them at each call; the chapter pilot gets them through `lessons=` below)
    import vision   # noqa: E402  (the pictures: pilot/vision.py; make() says why when it is off)
    eyes = vision.make(args, client=client, run_dir=run_dir, run_id=run_id, copy=Path(args.copy or COPY), segment=seg)
    live = Path(args.attach) if args.attach else run_dir / 'live'
    ch = Channel(live)
    hud_on = hsap.hud_wanted(getattr(args, 'hud', None))   # --hud on|off (default on); HSAP_HUD=0 turns it off
    hud = hud_text.Hud(live / 'hud.txt' if hud_on else None)
    if hud_on:
        (live / 'hud.txt').unlink(missing_ok=True)   # (a panel an earlier pilot left in this folder is gone)
    ch.send(watch_lines(seg.watch))
    setup = drivers.setup_of(chain) if chain else {}
    prefix_lines = [ln for ln in (seg.path.parent / seg.prefix).read_text().splitlines()
                    if ln.split('#', 1)[0].strip() and not ln.startswith('expect')] if seg.prefix else []
    prefix_lines += list(setup.get('steps') or [])   # a playback's own start (the scenario's `setup.steps`) follows the segment's route
    if prefix_lines and not seg.place:   # a route sent before the live steps (hsap plays it once Link is in control); after the placement when there is one
        ch.send(prefix_lines)
    runner = None
    follows = dict(item.split('=', 1) for item in args.follow)   # NAME=PATH: the files with the other players' places
    summary = {'run': run_id, 'segment': seg.name, 'decider': decider.name, 'decider_note': note,
               'planner': bool(planner), 'copy': str(copy), 'live': str(live), 'started': stamp,
               'load_start': open('/proc/loadavg').read().split()[:3], 'humanize': {'level': level, 'seed': seed},
               'recovery': recovery, 'vision': bool(eyes), 'tactics': {'mode': learn['mode'] if learn else 'off', 'dir': str(learn['book'].dir) if learn else None,
                                                                        'readonly': learn['book'].readonly if learn else None},
               'lessons': bool(less), 'hud': hud_on}
    print(f'{run_id}: segment {seg.name}, decider {decider.name}{" (" + note + ")" if note else ""}, '
          f'planner {"on" if planner else "off"}, live {live}', flush=True)
    try:
        if not args.attach:
            save = save_dir(args.save or seg.save or setup.get('save'), copy)
            cmd = [sys.executable, '-I', str(HSAP), str(copy), run_id, str(args.wall or seg.wall), '--live', str(live)]
            if save:
                cmd += ['--save', str(save)]
            if seg.boot or setup.get('boot'):
                cmd += ['--boot', seg.boot or setup['boot']]
            duel = next((t for g in seg.goals if g.kind == 'duel' for t in g.targets if t.follow in follows), None)
            if duel:   # the game side aims the duel steps at that file and puts his distance and bearing in the state lines
                cmd += ['--opponent', follows[duel.follow], '--analog']
            if args.shots:
                cmd += ['--shots', str(args.shots)]
            cmd += ['--hud', 'on' if hud_on else 'off']
            summary['runner'] = cmd
            runner = subprocess.Popen(cmd, stdout=open(run_dir / 'runner.out', 'w'), stderr=subprocess.STDOUT,
                                      stdin=subprocess.DEVNULL, env=runner_env(), start_new_session=True)
        alive = (lambda: runner.poll() is None) if runner else (lambda: True)
        t0 = time.time()
        # the runner may wait long for one of the machine's null-run slots; its own wall starts when the game does
        gp = ch.wait(lambda e: e['ev'] == 'gameplay', 6 * 3600 if runner else float(args.wall or seg.wall), alive)
        summary['gameplay_after_s'] = round(time.time() - t0, 1) if gp else None
        placed = None
        if gp and seg.place:   # the game's own teleport, age and clock, then the first state the pilot decides from
            import placement
            st, placed = placement.start_placed(seg.place, ch, copy / 'runs' / run_id, alive)
            summary['place'] = placed
            print(f'  placement: {"ok" if placed.get("ok") else "FAILED"} in {placed.get("seconds")} s' + (f' ({placed.get("error")})' if placed.get('error') else ''), flush=True)
            where = ', '.join(str(seg.place[k]) for k in ('to', 'age', 'hour') if seg.place.get(k) is not None)
            panel_note(run_dir, f'placement ok: {where} ({placed.get("seconds")} s)' if placed.get('ok') else
                       f'placement FAILED: {placed.get("error")} ({where})')
            fallback = os.environ.get('PILOT_PLACE_FALLBACK')
            if st is None and fallback:   # (the live watch: the save already starts near the place; play on from where the game stands)
                panel_note(run_dir, 'fallback: ' + fallback)
                summary['place_fallback'] = fallback
                n = ch.send(['wait 0.5'])[0]
                ch.wait(lambda e: e.get('ev') == 'step' and e.get('in') == n, 30, alive)
                st = ch.wait(lambda e: e.get('ev') == 'state' and e.get('why') == 'wait', 30, alive)
        else:
            st = ch.wait(lambda e: e['ev'] == 'state' and e['why'] == 'wait', 600, alive) if gp else None
        if st and prefix_lines and seg.place:   # the route after the placement (a failed placement sends nothing)
            ch.send(prefix_lines)
        if not st:
            outcome = 'no gameplay' if not gp else ('placement failed' if placed is not None else 'no first state line')
            pilot = None
        elif seg.scripted:   # no decisions: the prefix is the play; `end` queues behind it
            outcome, pilot = 'scripted', None
        else:
            print(f'  gameplay after {summary["gameplay_after_s"]} s of wall time', flush=True)
            kw = dict(follows=follows, recovery=True if recovery else None, human=human, bad=bad, eyes=eyes, tactics=learn, lessons=less, hud=hud)
            pilot = sections.make_pilot(seg, decider, ch, run_dir, run_id, alive, None, args.max_decisions, copy=copy, client=client, args=args, **kw) \
                if chapter else Pilot(seg, decider, ch, run_dir, run_id, alive, planner, args.max_decisions, **kw)
            t1 = time.time()
            outcome = pilot.run(st)
            summary['play_wall_s'] = round(time.time() - t1, 1)
            if outcome == 'solved' and seg.save_after:
                ch.send(['save timeout 60'])
                ch.wait(lambda e: e['ev'] == 'step' and e['src'].startswith('save'), 240, alive)
        if args.end_hold > 0 and runner and pilot:   # the game stays up after the last decision: a controller takes its pictures
            hold_end = time.time() + args.end_hold
            while time.time() < hold_end and alive():
                time.sleep(0.5)
            summary['end_hold_s'] = args.end_hold
        hud.clear()   # (nothing to show any more; hsap clears the panel itself when it ends, too)
        ch.send(['end'])
        done = ch.wait(lambda e: e['ev'] == 'done', float(args.wall or seg.wall) if seg.scripted else 120, alive)
        summary.update({'outcome': outcome, 'done': done})
        if chain:
            chain.finish(outcome)
        if runner:
            try:
                runner.wait(timeout=60)
            except subprocess.TimeoutExpired:
                pass
    finally:
        if runner and runner.poll() is None:
            os.killpg(runner.pid, 15)
            runner.wait()
    ch.poll()
    if ch.steps.parent != run_dir:
        shutil.copy(ch.steps, run_dir / 'steps.txt')
        if ch.out.exists():
            shutil.copy(ch.out, run_dir / 'out.jsonl')
    game_run = copy / 'runs' / run_id
    for source, target in ((log_path(game_run), 'run.log'), (game_run / 'summary.txt', 'hs-run-summary.txt')):
        if source is not None and source.exists():
            shutil.copy(source, run_dir / target)
    summary['load_end'] = open('/proc/loadavg').read().split()[:3]
    if chain:   # which driver made each decision, what failed first, what each cost
        summary['drivers'] = dict(chain.report(), spec={'want': want, 'fallbacks': fallbacks, 'chain': [d.name for d in chain.drivers]},
                                  per_decision=who_runs(pilot.who) if pilot else [])
    try:   # the run as an ls-input-recording/1 file (hsap's input journal and a mark after each step): the playback driver replays it
        from drivers import recording as recording_io
        rec = recording_io.write_run(live, run_dir / 'recording.jsonl', segment=seg.name, area=seg.area, save=args.save or seg.save,
                                     boot=seg.boot, tag=run_id, driver=decider.name)
        summary['recording'] = {'file': str(rec[0]), 'inputs': rec[1], 'marks': rec[2]} if rec else None
    except Exception as e:   # noqa: BLE001  a recording is a by-product, never a reason for the run to fail
        summary['recording'] = None
        print(f'recording: {type(e).__name__}: {e}', flush=True)
    if pilot:
        summary['decisions'] = len(pilot.decisions)
        summary['goals'] = {g.name: g.status for g in seg.goals}
        summary['labels'] = {k: pilot.decisions.count(k) for k in sorted(set(pilot.decisions))}
        summary['duel'] = pilot.duel_seen
        wanted = max((g.matches for g in seg.goals if g.kind == 'duel'), default=None)
        if wanted:   # a duel: how many matches were asked for and how many ended (by id, from the game's own log), won and lost
            d = pilot.duel_seen or {}
            summary['matches'] = {'wanted': wanted, 'ended': d.get('matches_ended') or 0, 'won': d.get('matches_won') or 0,
                                  'lost': d.get('matches_lost') or 0, 'results': d.get('match_results') or []}
        summary['planner_calls'] = [{'n': p['n'], 'why': p['why'], 'changed': p['changed'],
                                     'cost_usd': p.get('cost_usd'), 'latency_ms': p.get('latency_ms'), 'lessons': p.get('lessons')} for p in pilot.plans]
        if summary['play_wall_s'] and pilot.decisions:
            summary['decisions_per_minute'] = round(len(pilot.decisions) / summary['play_wall_s'] * 60, 2)
        summary['recover'] = pilot.recover_summary()
        if chapter:
            summary['chapter'] = {k: v for k, v in pilot.write().items() if k in ('chapter', 'outcome', 'markers', 'coverage', 'objectives', 'objectives_met',
                                                                                  'plan_cost_usd', 'cost_usd')}
        rates = {}
        if summary.get('play_wall_s'):   # what the questions and the money come to per minute of play
            minutes = summary['play_wall_s'] / 60
            led = openai_api.summary(run_id, standin=bool(args.api_base))
            calls, cost = sum(v['requests'] for v in led.values()), sum(v['cost_usd'] for v in led.values())
            rates = {'play_minutes': round(minutes, 2), 'model_calls': calls, 'model_calls_per_minute': round(calls / minutes, 2),
                     'cost_usd': round(cost, 6), 'cost_usd_per_minute': round(cost / minutes, 6),
                     'decisions_without_a_question': dict(pilot.skipped)}
        summary['rates'] = rates
        for p in pilot.plans:
            with open(PLANNER_LOG, 'a') as f:
                f.write(json.dumps({'run': run_id, 'segment': seg.name, 'n': p['n'], 'why': p['why'],
                                    'changed': p['changed'], 'after': p['after'], 'segment_solved': outcome == 'solved',
                                    'cost_usd': p.get('cost_usd'), 'lessons': p.get('lessons')}) + '\n')
        if outcome == 'solved' and not any(g.kind == 'duel' for g in seg.goals):   # (a fight is no route to replay)
            route, kept = export_route(seg, run_dir, run_id, decider.name, ch.events)
            summary['route'], summary['route_steps'] = str(route), kept
        with open(FRAGMENTS, 'a') as f:
            for fr in pilot.frags:
                f.write(json.dumps(fr) + '\n')
    summary['ledger'] = openai_api.summary(run_id, standin=bool(args.api_base))
    if eyes:
        eyes.close()   # (writes its oddity summary)
    if chain:
        chain.close()
    (run_dir / 'summary.json').write_text(json.dumps(summary, indent=1))
    if os.environ.get('ROUTELIB_DIR'):   # the run leaves its tracks, stuck points and links in the route library
        try:
            import routelib
            summary['routes'] = routelib.RouteLib(os.environ['ROUTELIB_DIR']).import_run(run_dir, label=run_id)
            (run_dir / 'summary.json').write_text(json.dumps(summary, indent=1))
        except Exception as e:   # noqa: BLE001  the library is a record, never a reason for the run to fail
            print(f'routelib: {type(e).__name__}: {e}', flush=True)
    try:
        import metrics   # noqa: E402  (pilot/metrics.py: the run's numbers from its own files)
        metrics.write_run(run_dir)
    except Exception as e:   # noqa: BLE001  the numbers are a report, never a reason for the run to fail
        print(f'metrics: {type(e).__name__}: {e}', flush=True)
    print(json.dumps({k: summary.get(k) for k in ('run', 'outcome', 'decisions', 'goals', 'decisions_per_minute',
                                                  'route', 'ledger', 'recording')}, indent=1), flush=True)
    if chain:
        d = summary['drivers']
        print(json.dumps({'decisions_by_driver': d['decisions_by_driver'], 'fallbacks': len(d['fallbacks']),
                          'cost_usd_by_driver': d['cost_usd_by_driver'], 'benched': d['benched']}), flush=True)
    return 0 if summary.get('outcome') in ('solved', 'scripted') else 1


def route_steps(route):
    """A route file as hsap steps: `expect flag|area ...` becomes `until ... timeout 10` (its result tells)."""
    out = []
    for ln in Path(route).read_text().splitlines():
        s = ln.split('#', 1)[0].strip()
        if not s:
            continue
        out.append('until ' + s[len('expect '):] + ' timeout 10' if s.startswith('expect ') else s)
    return out


def cmd_check_route(args):
    """The exported route on its own (no decisions), several runs one after another (one game at a time on the card):
    are its expects met?"""
    seg = Segment(args.segment)
    copy = Path(args.copy or COPY)
    steps = route_steps(args.route)
    tag0 = args.tag or f'{seg.name}-check-{datetime.datetime.now():%H%M%S}'
    rows = []
    for i in range(1, args.runs + 1):
        tag = f'{tag0}-{i}'
        live = HERE / 'runs' / 'checks' / tag
        ch = Channel(live)
        ch.send(watch_lines(seg.watch) + steps + ['end'])
        cmd = [sys.executable, '-I', str(HSAP), str(copy), tag, str(args.wall or seg.wall), '--live', str(live), '--hud', 'off']
        save = save_dir(seg.save, copy)
        if save:
            cmd += ['--save', str(save)]
        if seg.boot:
            cmd += ['--boot', seg.boot]
        subprocess.run(cmd, stdout=open(live / 'runner.out', 'w'), stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                       env=runner_env())
        ch.poll()
        expects = [e for e in ch.events if e['ev'] == 'step' and e['src'].startswith('until ') and
                   e['src'].endswith(' timeout 10')]
        unmet = [e['src'] for e in expects if e['result'] != 'met']
        done = any(e['ev'] == 'done' for e in ch.events)
        rows.append({'tag': tag, 'done': done, 'expects': len(expects), 'unmet': unmet, 'passed': done and not unmet})
    print(json.dumps(rows, indent=1))
    print(f"{sum(r['passed'] for r in rows)} of {len(rows)} runs passed")
    return 0


def cmd_ledger(args):
    since = datetime.datetime.fromisoformat(args.since).timestamp() if args.since else None
    print(json.dumps(openai_api.summary(args.run, since, args.standin), indent=1))
    print(json.dumps({k: round(v, 6) for k, v in openai_api.spent(args.run).items()}))
    return 0


def cmd_record(args):
    """The ls-input-recording/1 file of a finished run (cmd_run writes it for every run; this is for a run that did not, or an
    attached game's live folder): hsap's inputs.jsonl from control on, a mark after each step."""
    from drivers import recording as recording_io
    run = Path(args.run)
    live = run / 'live' if (run / 'live').is_dir() else run
    try:
        info = json.loads((run / 'summary.json').read_text())
    except (OSError, ValueError):
        info = {}
    out = Path(args.out) if args.out else run / 'recording.jsonl'
    made = recording_io.write_run(live, out, segment=info.get('segment'), tag=run.name, driver=info.get('decider'))
    if made is None:
        print(f'no inputs.jsonl in {live}: that run left no input journal (hsap writes it)', file=sys.stderr)
        return 2
    print(json.dumps({'recording': str(made[0]), 'inputs': made[1], 'marks': made[2]}))
    return 0


def cmd_drivers(args):
    """Which drivers can be asked now and why not (no request is made), as JSON. `--ask NAME` also makes ONE tiny request through that
    driver with a made-up decision point (no game fact in it; about 0.0002 USD on a paid one, written to the ledger like any other)."""
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    run_id = f'drivers-smoke-{stamp}'
    client = openai_api.Client(run_id, 'smoke', args.api_base)
    try:
        chain = drivers.build_chain('decisions', ['openrouter', 'chat', 'scripted'], args=args, table={}, client=client, run_id=run_id,
                                    segment='smoke', run_dir=Path(tempfile.gettempdir()))
    except ValueError as e:
        print(f'driver: {e}', file=sys.stderr)
        return 2
    out = {'drivers': {}}
    for d in chain.drivers:
        av = d.available()
        out['drivers'][d.name] = dict(d.describe(), available=av.ok, why_not=None if av.ok else av.reason,
                                       why_not_kind=None if av.ok else av.kind)
    out['mcp'] = 'always available: it waits for an agent (pilot.py run --driver mcp, then mcp_server.py --session <dir>)'
    out['playback'] = 'needs --recording FILE (an ls-input-recording/1 file)'
    code = 0
    if args.ask:
        d = chain.by_name.get(args.ask)
        if d is None or args.ask == 'scripted':
            print(f'--ask: one of {", ".join(n for n in chain.by_name if n != "scripted")}', file=sys.stderr)
            return 2
        g = Goal('smoke', Cond('X=1'), 'reach', [Target('spot', 5, 5)])
        st = {'pos': [0, 0, 0], 'facing': 0}
        ctx = deciders.Context(st, g, g.targets[0], make_candidates('Smoke_Area', g, g.targets[0], st, {}), {}, [])
        try:
            dec = d.decide(ctx)
            out['ask'] = {'driver': d.name, 'step': dec.label, 'offered': [c.label for c in ctx.candidates], 'provenance': dec.provenance.as_dict()}
        except drivers.base.DriverFailure as f:
            out['ask'] = {'driver': d.name, 'failed': f.kind, 'reason': f.reason[:300], 'cost_usd': f.cost_usd}
            code = 1
        out['ledger'] = openai_api.summary(run_id)
    print(json.dumps(out, indent=1, default=str))
    return code


def cmd_story(args):
    """A segment TOML whose goals come from the story data (story.py); written to --out or printed. story.py and the world
    model it reads are private (game data): a tree without them says so."""
    try:
        import story
    except ImportError:
        print('story needs story.py and the private world model (world/story.json), which this tree does not have', file=sys.stderr)
        return 2
    text = story.segment_toml(args.quest, args.after, args.area, args.save, args.name)
    if args.out:
        Path(args.out).write_text(text)
    print(text)
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    r = sub.add_parser('run')
    r.add_argument('segment')
    r.add_argument('--decider', default=None, choices=['rules', 'replay', 'openai-decisions'],
                   help='the older way to say who decides (default rules when no --driver and no scenario `driver` names one)')
    r.add_argument('--driver', metavar='WANT[,FALLBACK...]',
                   help='who decides, behind one interface with fallbacks: decisions, openrouter, chat, mcp, playback, scripted, or '
                        'default (decisions, openrouter, chat if configured, scripted); a scenario\'s `driver` table says the same')
    r.add_argument('--fallbacks', metavar='A,B|none', help='the fallbacks the run accepts (default: the wanted driver\'s own tail of the '
                   'default chain; playback and scripted have none)')
    r.add_argument('--recording', metavar='FILE', help='playback: the ls-input-recording/1 file to replay')
    r.add_argument('--playback-mode', dest='playback_mode', default=None, choices=('raw', 'push'),
                   help='playback: raw (inputs scheduled in the game\'s frame clock, default) or push (one hsap step per recorded input)')
    r.add_argument('--openrouter-model', default=None, help='the OpenRouter model (default openai/gpt-6-luna, or $PILOT_OPENROUTER_MODEL)')
    r.add_argument('--chat-base', default=None, help='an OpenAI-compatible base URL for the chat driver, e.g. http://127.0.0.1:8080/v1 ($PILOT_CHAT_BASE)')
    r.add_argument('--chat-model', default=None, help='the model name the chat endpoint wants ($PILOT_CHAT_MODEL; default `local`)')
    r.add_argument('--chat-mode', default=None, choices=('tool', 'json_schema', 'json'), help='how the chat drivers ask for a structured answer')
    r.add_argument('--mcp-dir', default=None, help='the session folder an MCP agent\'s server watches ($PILOT_MCP_DIR; default <run>/mcp)')
    r.add_argument('--mcp-agent', dest='mcp_agent', default=None, choices=('loop', 'omp'),
                   help='mcp driver: start an agent when the first decision point is open: loop (our own OpenRouter tool-calling agent) or omp (the omp coding agent)')
    r.add_argument('--mcp-agent-model', dest='mcp_agent_model', default=None, help='the model of that agent (loop: an OpenRouter model; omp: omp\'s model pattern)')
    r.add_argument('--mcp-wait', dest='mcp_wait_s', type=float, default=None, help='how long to wait for the agent at each decision (default 180 s)')
    r.add_argument('--replay')
    r.add_argument('--planner', action='store_true')
    r.add_argument('--copy')
    r.add_argument('--tag')
    r.add_argument('--attach')
    r.add_argument('--save')
    r.add_argument('--wall', type=int)
    r.add_argument('--max-decisions', type=int)
    r.add_argument('--follow', action='append', default=[], metavar='NAME=PATH',
                   help='a follow target\'s file: JSON {x, y, z, map, w} a controller keeps with another player\'s place; '
                        'the pilot waits for it before its first decision and reads it before each one')
    r.add_argument('--end-hold', type=float, default=0.0, metavar='SECONDS',
                   help='keep the game running this long after the last decision, before the end step')
    r.add_argument('--shots', type=int, default=0, metavar='PRESENTS',
                   help='a picture every this many presents (hsap --shots; the game side defaults to 600)')
    r.add_argument('--hud', choices=('on', 'off'), default=None,
                   help='the pilot\'s decisions on the game\'s own screen (hud_text.py; hsap sends <live>/hud.txt with the bridge\'s `overlay` '
                        'command): default on unless HSAP_HUD=0; off writes nothing and tells hsap --hud off')
    r.add_argument('--matches', type=int, metavar='N',
                   help='a duel series: N different matches must end (sets `matches` of every duel goal; budget_seconds and '
                        'max_decisions scale by N over the segment\'s own matches)')
    r.add_argument('--humanize', type=int, choices=humanize.LEVELS, default=None, metavar='0..3',
                   help='human-like movement: 0 off (every line as made: proofs, duels), 1 delays and stick noise, 2 curves, looks, '
                        'pauses, a walked leg, 3 more of it and rolls; default: the segment\'s `humanize`, else 2 (0 for a duel)')
    r.add_argument('--humanize-seed', type=int, default=None, help='the seed of the shaping (default: from the run id)')
    r.add_argument('--no-recover', dest='recover', action='store_false',
                   help='no stuck recovery and no guard in front of the decider (the pilot as it was)')
    r.add_argument('--bad-points', metavar='DIR', help='where the per-map bad-point memory lives (default: pilot/cache or $PILOT_CACHE)')
    r.add_argument('--no-bad-points', action='store_true', help='neither read nor write the bad-point memory')
    r.add_argument('--tactics', choices=('ranked', 'fixed', 'explore', 'off'), default=None,
                   help='the recovery ladder\'s tactics library (tactics.py): ranked (default, or $PILOT_TACTICS) the library\'s order for the cause of a block, every attempt written back; '
                        'fixed the old order, attempts still written back; explore the nightly self-play\'s order; off the old ladder, nothing read or written')
    r.add_argument('--tactics-dir', metavar='DIR', help='where the library lives (default: tactics/ beside the route library in the harness, or $PILOT_TACTICS_DIR)')
    r.add_argument('--tactics-readonly', action='store_true', help='read the library, never write it (a scoreboard\'s cells must not learn from their own test; or $PILOT_TACTICS_READONLY=1)')
    r.add_argument('--tactics-source', default=None, metavar='NAME', help='what the attempts are filed under (default live; the nightly self-play: selfplay)')
    r.add_argument('--lessons', choices=('on', 'off'), default=None,
                   help='the planner\'s lessons (lessons.py): the few most similar past failures and what finally worked go into each planner call (default on, or $PILOT_LESSONS); off: the planner is asked as before')
    r.add_argument('--vision', choices=('off', 'on'), default=None, help='look at the screen (vision.py; default off, or $PILOT_VISION)')
    r.add_argument('--vision-every', type=float, default=None, metavar='SECONDS', help='a look at least this often (wall seconds)')
    r.add_argument('--vision-model', default=None)
    r.add_argument('--vision-backend', choices=('decisions', 'responses'), default=None)
    r.add_argument('--vision-sock', default=None, metavar='PATH', help='the control socket to take pictures from (with --attach)')
    r.add_argument('--chapter-model', default=None, help='a chapter (sections.py): the model that plans its objectives (default: the chapter\'s planner_model, else the planner model)')
    r.add_argument('--no-chapter-planner', action='store_true', help='a chapter: no planner model, the chapter\'s own [[objective]] outline is played')
    r.add_argument('--api-base', help='a stand-in server (standin.py); the real key is never sent there')
    r.add_argument('--allowance-usd', type=float, help="a limit below the caps for this lane's runs since --allowance-since")
    r.add_argument('--allowance-since', default=datetime.date.today().isoformat())
    c = sub.add_parser('check-route')
    c.add_argument('route')
    c.add_argument('--segment', required=True)
    c.add_argument('--runs', type=int, default=3)
    c.add_argument('--copy')
    c.add_argument('--tag')
    c.add_argument('--wall', type=int)
    rc = sub.add_parser('record', help='write the ls-input-recording/1 file of a finished run (cmd_run does it for every run)')
    rc.add_argument('run', help='a run folder (pilot/runs/<tag>) or an hsap live folder')
    rc.add_argument('--out')
    dr = sub.add_parser('drivers', help='which drivers can be asked now (no request); --ask NAME makes one tiny request through it')
    dr.add_argument('--ask', metavar='NAME', help='decisions, openrouter or chat: one tiny request with a made-up decision point')
    dr.add_argument('--openrouter-model', default=None)
    dr.add_argument('--chat-base', default=None)
    dr.add_argument('--chat-model', default=None)
    dr.add_argument('--chat-mode', default=None, choices=('tool', 'json_schema', 'json'))
    dr.add_argument('--api-base', help='a stand-in server for the Decisions API; the real key is never sent there')
    lg = sub.add_parser('ledger')
    lg.add_argument('--run')
    lg.add_argument('--since')
    lg.add_argument('--standin', action='store_true')
    s = sub.add_parser('story')
    s.add_argument('quest')
    s.add_argument('--after', required=True)
    s.add_argument('--area', required=True)
    s.add_argument('--save', required=True)
    s.add_argument('--name', required=True)
    s.add_argument('--out')
    a = ap.parse_args()
    return {'run': cmd_run, 'check-route': cmd_check_route, 'ledger': cmd_ledger, 'story': cmd_story, 'record': cmd_record,
            'drivers': cmd_drivers}[a.cmd](a)


if __name__ == '__main__':
    sys.exit(main())
