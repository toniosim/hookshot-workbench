#!/usr/bin/env python3
"""test_entry: the scripts a hold starts as subprocesses really start.

A hold runs `python3 -I -B pilot.py run ...`, and pilot.py starts `python3 -I hsap.py ...`. `-I` implies `-P`: the script's own folder is NOT on
`sys.path`, so a sibling module a script imports at the top (hsap.py's `import hsap_actions`) is found only if the script puts its folder there itself.
The unit tests import the modules with their own `sys.path` set up and never see the difference; the first hold that ran the new hsap.py under -I
(PilotSections' second) lost its whole admission to a `ModuleNotFoundError` after 0.2 s.

Each case starts the real script in a fresh interpreter with the flags the callers use, in a clean environment, up to a point that needs no game:
`--help` (argparse exits before anything starts) or `check` of a chapter file. A traceback or a nonzero exit is a failure.

    python3 -I -B test_entry.py
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
FAILED = []


def check(ok, what):
    print(('ok: ' if ok else 'FAIL: ') + what, flush=True)
    if not ok:
        FAILED.append(what)


def start(script, *args, cwd=None):
    """The script under `python3 -I -B`, a clean environment, a throw-away home: (exit code, stdout, stderr)."""
    with tempfile.TemporaryDirectory(prefix='entry-home-') as home:
        env = {'HOME': home, 'PATH': os.environ.get('PATH', '/usr/bin:/bin'), 'LANG': 'C.UTF-8'}
        r = subprocess.run([sys.executable, '-I', '-B', str(script), *args], capture_output=True, text=True, timeout=60, env=env,
                           cwd=str(cwd or home))
    return r.returncode, r.stdout, r.stderr


def case(label, script, *args):
    code, out, err = start(script, *args)
    check(code == 0 and 'Traceback' not in err and 'Traceback' not in out,
          f'{label}: exit {code}' + ('' if code == 0 else f'; {err.strip().splitlines()[-1] if err.strip() else out.strip()[-200:]}'))
    return out


def main():
    out = case('hsap.py --help (what pilot.py and probe.py start under -I)', HERE / 'hsap.py', '--help')
    check('copy' in out and '--live' in out, 'hsap.py --help prints its usage')
    case('hsap_file.py --help', HERE / 'hsap_file.py', '--help')
    if (HERE / 'probe.py').is_file():
        case('probe.py --help', HERE / 'probe.py', '--help')
    else:
        print('note: no probe.py here (a publishable tree): its check is skipped')
    case('pilot/pilot.py --help', HERE / 'pilot' / 'pilot.py', '--help')
    case('pilot/pilot.py run --help', HERE / 'pilot' / 'pilot.py', 'run', '--help')
    chapters = sorted((HERE / 'pilot' / 'chapters').glob('*.toml'))
    if not chapters:
        print('note: no private chapter files here (a publishable tree): the chapter checks are skipped')
    if (HERE / 'playbench' / 'playbench.py').is_file():   # the scoreboard (the nightly timer and the waiter start it under -I; its folder is not on sys.path then)
        out = case('playbench/playbench.py --help', HERE / 'playbench' / 'playbench.py', '--help')
        check('queue' in out and 'hold' in out, 'playbench.py --help lists its commands')
        case('playbench/playbench.py hold --help', HERE / 'playbench' / 'playbench.py', 'hold', '--help')
    for ch in chapters:
        out = case(f'sections.py check {ch.name}', HERE / 'pilot' / 'sections.py', 'check', str(ch))
        check('marker' in out, f'{ch.name}: check lists its markers')
    print('test_entry: %s' % ('all passed' if not FAILED else '%d FAILED' % len(FAILED)))
    return 1 if FAILED else 0


if __name__ == '__main__':
    sys.exit(main())
