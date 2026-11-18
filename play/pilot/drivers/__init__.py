"""The pilot's drivers: who chooses the next step, behind one interface (base.py), each falling back to the next (chain.py).

A scenario (segment TOML) or the command line names the driver it WANTS and the fallbacks it ACCEPTS:

    [driver]                        # a table of its own, before the first [[goal]] (after it, TOML would make it part of that goal)
    want = "decisions"              # decisions | openrouter | chat | mcp | playback | scripted | default
    fallbacks = ["openrouter", "scripted"]   # optional; [] means none
    recording = "walk.jsonl"        # playback: an ls-input-recording/1 file (relative to the segment)
    setup = {save = "...", boot = "continue", steps = ["wait 1"]}   # playback: where it starts (the recording's header otherwise)
    script = [{name = "open", goal = "door", lines = ["press A 200"]}]   # scripted: fixed input scripts
    tolerance_m = 3.0               # playback: how far from the recorded place counts as diverged
    playback_mode = "raw"           # playback: raw (frame-scheduled sequences, default) or push (one hsap step per recorded input)
    openrouter_model = "..."        # also chat_base, chat_model, chat_mode, mcp_dir, mcp_wait_s

    pilot.py run seg.toml --driver decisions,openrouter,scripted        (want first, then the fallbacks; `--driver playback` alone has none)
    pilot.py run seg.toml --driver decisions --fallbacks none

Without fallbacks named, a driver that is asked for gets the rest of the DEFAULT chain from itself on: decisions -> openrouter -> chat
(only when a base URL is configured) -> scripted. A scenario that wants `playback` or `scripted` gets no fallback at all, so it never
falls back to a model unless it says so; `mcp` falls back to `scripted` (no model either). `default` is the whole default chain.
Nothing is chosen for a run that names no driver: it plays on the rules as it always did (set PILOT_DRIVER to change that for a shell).

Importing this package pulls in nothing heavy (the MCP server uses mcp_session alone); the drivers are imported when a chain is built.
"""
import os
from pathlib import Path

NAMES = ('decisions', 'openrouter', 'chat', 'mcp', 'playback', 'scripted')
DEFAULT_CHAIN = ('decisions', 'openrouter', 'chat', 'scripted')
TABLE_KEYS = {'want', 'fallbacks', 'recording', 'setup', 'script', 'tolerance_m', 'playback_mode', 'openrouter_model', 'chat_base',
              'chat_model', 'chat_mode', 'mcp_dir', 'mcp_wait_s', 'mcp_agent', 'mcp_agent_model'}


def parse_spec(text):
    """`want[,fallback...]` (or `default`) -> (want, [fallbacks] or None); names are checked."""
    names = [x.strip() for x in str(text).split(',') if x.strip()]
    if not names:
        raise ValueError('--driver needs a name')
    for n in names:
        if n != 'default' and n not in NAMES:
            raise ValueError(f'no driver {n!r} (drivers: {", ".join(NAMES)}, default)')
    return names[0], (names[1:] or None)


def parse_table(table, base_dir=None):
    """A scenario's `driver` table, checked and normalised (paths made absolute against the segment's folder); None without one."""
    if table is None:
        return None
    if not isinstance(table, dict):
        raise ValueError('`driver` must be a table: driver = {want = "...", fallbacks = [...]}')
    extra = set(table) - TABLE_KEYS
    if extra:
        raise ValueError(f'driver: unknown keys {sorted(extra)} (keys: {", ".join(sorted(TABLE_KEYS))})')
    want = table.get('want', 'default')
    if want != 'default' and want not in NAMES:
        raise ValueError(f'driver.want {want!r} is not one of {", ".join(NAMES)}, default')
    fb = table.get('fallbacks')
    if fb is not None:
        if not isinstance(fb, list) or any(x not in NAMES for x in fb):
            raise ValueError(f'driver.fallbacks must be a list of {", ".join(NAMES)}')
        if want in fb:
            raise ValueError('driver.fallbacks names the wanted driver itself')
        if len(set(fb)) != len(fb):
            raise ValueError('driver.fallbacks names a driver twice')
    out = dict(table, want=want)
    base = Path(base_dir) if base_dir else None
    if out.get('recording') and base and not Path(out['recording']).is_absolute():
        out['recording'] = str(base / out['recording'])
    scripts = []
    for s in out.get('script') or []:
        if not isinstance(s, dict) or not s.get('name') or not (s.get('lines') or s.get('file')):
            raise ValueError('driver.script entries need a name and `lines` or `file`')
        s = dict(s)
        if s.get('file'):
            p = Path(s['file'])
            p = p if p.is_absolute() or base is None else base / p
            try:
                s['lines'] = [ln.strip() for ln in p.read_text().splitlines() if ln.strip() and not ln.strip().startswith('#')]
            except OSError as e:
                raise ValueError(f'driver.script {s["name"]}: {e}') from None
        if not s.get('lines') or not all(isinstance(x, str) for x in s['lines']):
            raise ValueError(f'driver.script {s["name"]}: no steps')
        scripts.append({k: s[k] for k in ('name', 'goal', 'lines') if k in s})
    out['script'] = scripts
    return out   # (a playback with no recording is refused when the chain is built: the command line's --recording may supply it)


def chain_names(want, fallbacks, chat_configured):
    """(names of the chain in order, notes). want may be `default`; fallbacks None means the want's own default tail."""
    notes = []
    if want in (None, 'default'):
        want = DEFAULT_CHAIN[0]
    if fallbacks is not None:
        names = [want] + list(fallbacks)
        if len(set(names)) != len(names):
            raise ValueError(f'a driver twice in the chain ({", ".join(names)})')
    elif want in DEFAULT_CHAIN:
        names = list(DEFAULT_CHAIN[DEFAULT_CHAIN.index(want):])
        if 'chat' in names and not chat_configured and want != 'chat':
            names.remove('chat')
            notes.append('chat: not configured (PILOT_CHAT_BASE / --chat-base), left out of the default chain')
    elif want == 'mcp':
        names = ['mcp', 'scripted']
    else:   # playback: no fallback unless the scenario says so
        names = [want]
    return names, notes


def resolve(args, segment=None, env=None):
    """The wanted driver and fallbacks of a run, and the scenario's driver table: the command line over the scenario over the
    environment. (None, None, table) when nothing names a driver."""
    env = os.environ if env is None else env
    table = getattr(segment, 'driver', None) or {}
    cli = getattr(args, 'driver', None)
    cli_fb = getattr(args, 'fallbacks', None)
    fallbacks = None
    if cli_fb is not None:
        fallbacks = [] if cli_fb.strip().lower() in ('none', '') else [x.strip() for x in cli_fb.split(',') if x.strip()]
        bad = [x for x in fallbacks if x not in NAMES]
        if bad:
            raise ValueError(f'--fallbacks: no driver {bad[0]!r} (drivers: {", ".join(NAMES)}, or none)')
    if cli:
        want, fb = parse_spec(cli)
        return want, (fallbacks if fallbacks is not None else fb), table
    if table:
        return table['want'], (fallbacks if fallbacks is not None else table.get('fallbacks')), table
    if env.get('PILOT_DRIVER'):
        want, fb = parse_spec(env['PILOT_DRIVER'])
        return want, (fallbacks if fallbacks is not None else fb), table
    return None, None, table


def option(args, table, key, env_name=None, default=None, env=None):
    """One setting: the command line (args.<key>), else the scenario's table, else the environment, else the default."""
    env = os.environ if env is None else env
    v = getattr(args, key, None)
    if v is None:
        v = table.get(key)
    if v is None and env_name:
        v = env.get(env_name)
    return default if v is None else v


def build_chain(want, fallbacks, *, args, table, client, run_id, segment, run_dir, copy=None, env=None):
    """The chain a run asked for. `client` is the run's openai_api.Client (the decisions driver's). Raises ValueError for a setting
    that cannot be (a playback with no recording)."""
    from . import chat as chat_mod
    from .chain import Chain
    from .decisions import DecisionsDriver
    from .scripted import ScriptedDriver
    env = os.environ if env is None else env
    chat_base = option(args, table, 'chat_base', 'PILOT_CHAT_BASE', env=env)
    names, notes = chain_names(want, fallbacks, bool(chat_base))
    kw = {}
    if option(args, table, 'chat_mode', 'PILOT_CHAT_MODE', env=env):
        kw['mode'] = option(args, table, 'chat_mode', 'PILOT_CHAT_MODE', env=env)
    if env.get('PILOT_CHAT_TIMEOUT'):
        kw['timeout'] = float(env['PILOT_CHAT_TIMEOUT'])
    if env.get('PILOT_CHAT_MAX_COST'):
        kw['max_cost'] = float(env['PILOT_CHAT_MAX_COST'])
    built = []
    for n in names:
        if n == 'decisions':
            built.append(DecisionsDriver(client))
        elif n == 'openrouter':
            built.append(chat_mod.make_openrouter(
                run_id, segment, base=env.get('PILOT_OPENROUTER_BASE'),
                model=option(args, table, 'openrouter_model', 'PILOT_OPENROUTER_MODEL', env=env), **kw))
        elif n == 'chat':
            built.append(chat_mod.make_chat(run_id, segment, base=chat_base,
                                            model=option(args, table, 'chat_model', 'PILOT_CHAT_MODEL', env=env), **kw))
        elif n == 'scripted':
            built.append(ScriptedDriver(table.get('script') or ()))
        elif n == 'playback':
            from .playback import PlaybackDriver
            rec = option(args, table, 'recording')
            if not rec:
                raise ValueError('the playback driver needs a recording: --recording FILE or driver.recording in the scenario')
            built.append(PlaybackDriver(rec, tolerance_m=option(args, table, 'tolerance_m'), setup=table.get('setup'),
                                        mode=option(args, table, 'playback_mode', 'PILOT_PLAYBACK_MODE', default='raw', env=env)))
        elif n == 'mcp':
            from .mcp_queue import McpDriver
            d = McpDriver(option(args, table, 'mcp_dir', 'PILOT_MCP_DIR', default=str(Path(run_dir) / 'mcp'), env=env),
                          wait_s=float(option(args, table, 'mcp_wait_s', 'PILOT_MCP_WAIT_S', default=180.0, env=env)),
                          first_wait_s=float(env.get('PILOT_MCP_FIRST_WAIT_S') or 600.0))
            kind = option(args, table, 'mcp_agent', 'PILOT_MCP_AGENT', env=env)
            if kind:
                from .agents import launcher
                d.on_first = launcher(kind, session_dir=d.session.dir, run_dir=run_dir, run_id=run_id, segment=segment,
                                      model=option(args, table, 'mcp_agent_model', 'PILOT_MCP_AGENT_MODEL', env=env))
            built.append(d)
    chain = Chain(built, want=want or 'default', notes=notes)
    return chain


def start(chain, *, run_id, segment, copy=None, briefing=''):
    """Once the chain is built and the run is known: the mcp driver opens its session (the folder an agent's server watches); the
    control socket for screenshots is looked up when it is asked (the game has not started yet). Returns the lines to tell the
    person who started the run (how to attach an agent)."""
    notes = []
    for d in chain.drivers:
        if hasattr(d, 'begin'):
            sock = None
            if copy:
                def sock(copy=copy, run_id=run_id):
                    import vision
                    return vision.control_socket(copy, run_id)
            d.begin(run=run_id, segment=segment, briefing=briefing, control_sock=sock)
            server = Path(__file__).resolve().parent.parent / 'mcp_server.py'
            notes.append(f'mcp: waiting for an agent at each decision (first {d.first_wait_s:g} s, then {d.wait_s:g} s). Attach one: an MCP client '
                         f'whose server command is  python3 -I -B {server} --session {d.session.dir}')
    return notes


def setup_of(chain):
    """The start setup a driver brings (playback's save, boot and steps), or {}."""
    for d in chain.drivers:
        if hasattr(d, 'setup'):
            return d.setup()
    return {}


def run_settings(chain, humanize_given=False):
    """What the head of the chain needs of the run loop: {'recovery': bool, 'humanize': 0 or None (the run's default)}. A replay
    must meet exactly the questions it recorded and an agent decides for itself (no guard in front of either); a scripted run must give
    the same result every time (no seeded delays unless --humanize says)."""
    head = chain.drivers[0].name
    return {'recovery': head not in ('playback', 'mcp'), 'humanize': 0 if head in ('playback', 'mcp', 'scripted') else None}
