"""From a cell's record to a result row: the referee's judgement of the state journal plus the pilot's own metrics (metrics.py of the pilot that played).

success, time to goal and progress come from the REFEREE (the game's state); stuck seconds, decisions and cost come from the pilot's metrics (its transcript
and the cost ledger). `valid` says whether the run counts as the pilot's play: a run whose save did not put Link at the start, that never showed a place, that
the hold or the player's game cut short before the proof, or that the runner could not start, is `invalid` (kept, shown, not a pass or a fail).
"""
import gzip
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import board  # noqa: E402
import config  # noqa: E402
import referee  # noqa: E402

if str(config.names_dir()) not in sys.path:
    sys.path.insert(0, str(config.names_dir()))
from hs_names import LOG_VERSION  # noqa: E402  (the game log's first line: `<project> vX-N-gSHA (source S)`)

EVIDENCE = ('transcript.jsonl', 'summary.json', 'metrics.json', 'out.jsonl', 'steps.txt', 'hs-run-summary.txt', 'runner.out')


def load_metrics(pilot_dir):
    """The pilot's metrics.py as a module (named pilot_metrics; it imports its own openai_api/interact from the pilot's folder, so the cost ledger read is
    the snapshot's)."""
    pilot_dir = Path(pilot_dir)
    if str(pilot_dir) not in sys.path:
        sys.path.insert(0, str(pilot_dir))
    spec = importlib.util.spec_from_file_location('pilot_metrics', pilot_dir / 'metrics.py')
    mod = importlib.util.module_from_spec(spec)
    sys.modules['pilot_metrics'] = mod
    spec.loader.exec_module(mod)
    return mod


def build_of(run_dir):
    """The game build a run played: the token of the first line of the game's log, as the pilot copied it (run.log); 'unknown' when it is not there."""
    try:
        with open(Path(run_dir) / 'run.log', errors='replace') as f:
            for _ in range(5):
                m = LOG_VERSION.search(f.readline())
                if m:
                    return m.group(1)
    except OSError:
        pass
    return 'unknown'


def arm_hash(arm):
    return hashlib.sha256(json.dumps(arm, sort_keys=True).encode()).hexdigest()[:12]


def score_cell(rec, cell, arm_name, arm, night, pilot_commit, metrics_mod=None, local=None):
    """The result row (a dict for store.add_cell) of one finished cell record."""
    run_dir = Path(rec['run_dir'])
    rows, _ = referee.read_rows(run_dir / 'live' / 'state.jsonl', 0)
    t_ref = referee.first_decision_t(run_dir / 'transcript.jsonl', rows)
    res = referee.judge(cell.proof, rows, cell.start, t_ref)
    why = []
    if rec.get('error'):
        why.append(f"the runner failed: {rec['error']}")
    if res['valid_samples'] == 0:
        why.append('no sample showed a place (the game never reached play)')
    if res['start_ok'] is False:
        why.append(f"the first sample was not at the cell's start ({res['start']} on {res['maps'][:1]})")
    if rec.get('cut') and not res['success']:
        why.append(f"cut short: {rec['cut']}")
    valid = res['success'] and res['start_ok'] is not False or not why
    if res.get('tainted') and not res['success'] and res['start_ok'] is not False and res['valid_samples']:
        valid = True   # (a forbidden way was taken: the failure is certain, however the run ended)
    m, merr = None, None
    if metrics_mod is not None:
        try:
            m = metrics_mod.analyse(run_dir, arm=arm_name)
        except Exception as e:   # noqa: BLE001  a missing number is None, never zero
            merr = f'{type(e).__name__}: {e}'
    try:
        summary = json.loads((run_dir / 'summary.json').read_text())
    except (OSError, ValueError):
        summary = {}
    sess = (m or {}).get('session') or {}
    cost = ((m or {}).get('cost') or {}).get('total_usd')
    game_s = round(res['last_t'] - res['first_t'], 1) if res['last_t'] is not None and res['first_t'] is not None else None
    outcome = summary.get('outcome') or ('no summary' if not summary else None)
    if res.get('tainted') and not res['success']:
        why.insert(0, 'went a way the task forbids (the proof can no longer be met)')
    if not why and not res['success']:
        why.append(f'the proof was not shown in {game_s} s of play' + (f' (the pilot said: {outcome})' if outcome else ''))
    row = {
        'night': night, 'cell': cell.id, 'arm': arm_name, 'attempt': rec['attempt'], 'hold': rec.get('hold'), 'tag': rec['tag'],
        'success': int(bool(res['success'])), 'time_to_goal_s': res['time_to_goal_s'], 'stuck_s': sess.get('stuck_s_total'), 'decisions': sess.get('decisions'),
        'cost_usd': cost, 'progress': res['progress'], 'start_ok': None if res['start_ok'] is None else int(res['start_ok']), 'valid': int(bool(valid)),
        'why': '; '.join(why), 'pilot_outcome': outcome, 'play_s': game_s, 'build': build_of(run_dir), 'pilot_commit': pilot_commit,
        'fingerprint': board.fingerprint(cell, local), 'arm_hash': arm_hash(arm), 'blocker': None if res['success'] else cell.blocker,
        'referee': res, 'metrics_error': merr,
        'extra': {'stuck_steps': sess.get('stuck_steps'), 'streak_max': sess.get('streak_max'), 'distance_m': sess.get('distance_m'),
                  'recover': (m or {}).get('recover'), 'goals': (m or {}).get('goals'), 'rc': rec.get('rc'), 'stopped_after_proof': rec.get('stopped_after_proof'),
                  'planner_calls': sess.get('planner_calls'),
                  'learning': {'tactics': summary.get('tactics'), 'lessons': summary.get('lessons'), 'recover': summary.get('recover'),
                               'planner_lessons': [c.get('lessons') for c in (summary.get('planner_calls') or []) if isinstance(c, dict) and c.get('lessons')]}},
    }
    return row


def collect(rec, dest, shots=4):
    """Copy a cell's evidence out of the snapshot before it is deleted: the pilot's files, the state journal (gzipped), the game's own summary and up to
    `shots` of its pictures, downscaled. Returns the folder."""
    run_dir, dest = Path(rec['run_dir']), Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    for name in EVIDENCE:
        if (run_dir / name).is_file():
            shutil.copy(run_dir / name, dest / name)
    j = run_dir / 'live' / 'state.jsonl'
    if j.is_file():
        with open(j, 'rb') as src, gzip.open(dest / 'state.jsonl.gz', 'wb') as out:
            shutil.copyfileobj(src, out)
    log = run_dir / 'run.log'
    if log.is_file():
        with open(log, errors='replace') as f:
            (dest / 'run.log.head').write_text(''.join(f.readlines()[:60]))
    game = Path(rec['copy']) / 'runs' / rec['tag']
    for name in ('summary.txt', 'exit.txt', 'kernel-status.json'):
        if (game / name).is_file():
            shutil.copy(game / name, dest / ('game-' + name))
    pics = sorted((game / 'shots').glob('*.png')) if (game / 'shots').is_dir() else []
    if pics and shots:
        step = max(1, len(pics) // shots)
        for p in (pics[::step][:shots - 1] + [pics[-1]])[:shots]:
            subprocess.run(['magick', str(p), '-resize', '640x', '-quality', '80', str(dest / (p.stem + '.jpg'))], check=False, timeout=60)
    return dest


def merge_ledger(snapshot_pilot, dev_pilot):
    """Append the cost-ledger rows the hold made (in the snapshot's ledger, not yet in the dev copy's) to the dev copy's ledger, so the caps see them."""
    snap, dev = Path(snapshot_pilot) / 'ledger.jsonl', Path(dev_pilot) / 'ledger.jsonl'
    if not snap.is_file():
        return 0
    have = set()
    if dev.is_file():
        for line in dev.read_text().splitlines():
            try:
                r = json.loads(line)
                have.add((r.get('ts'), r.get('run')))
            except ValueError:
                pass
    new = []
    for line in snap.read_text().splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if (r.get('ts'), r.get('run')) not in have:
            new.append(line)
    if new:
        with open(dev, 'a') as f:
            f.write('\n'.join(new) + '\n')
    return len(new)


def rejudge_row(old, cell, journal_rows, transcript, local=None, ended_by_old_proof=False):
    """The stored row `old` (a dict, as in row_json) judged again by `cell`'s CURRENT proof and start on the stored journal (rows of state.jsonl): the same sample,
    a corrected reading. `ended_by_old_proof`: the run met the earlier proof, so the runner ended it a few seconds later: if the corrected proof is not met in
    what is left, the run is invalid (too short), not a failure. Returns the new row (every field but the judgement is the old one's). Rejudgement never un-cuts a run: a cut reason in `why` stays."""
    t_ref = referee.first_decision_t(transcript, journal_rows)
    res = referee.judge(cell.proof, journal_rows, cell.start, t_ref)
    why = []
    if res['valid_samples'] == 0:
        why.append('no sample showed a place (the game never reached play)')
    if res['start_ok'] is False:
        why.append(f"the first sample was not at the cell's start ({res['start']} on {res['maps'][:1]})")
    if res.get('tainted') and not res['success']:
        why.append('went a way the task forbids (the proof can no longer be met)')   # (a failure that is already certain: how long the run lasted does not matter)
    elif ended_by_old_proof and not res['success']:   # (the runner ends a cell a few seconds after the proof was seen: a run that the OLD proof ended is too short to count as a failure of the new one)
        why.append('ended early by the earlier proof (the runner stops a cell a few seconds after a proof was seen), so too short to count as a failure of the corrected one: play it again')
    cut = re.search(r'cut short: \w+', old.get('why') or '')
    if cut and not res['success']:
        why.append(cut.group(0))
    if old.get('why', '').startswith('the runner failed'):
        why.insert(0, old['why'].split('; ')[0])
    valid = res['success'] and res['start_ok'] is not False or not why
    if res.get('tainted') and not res['success'] and res['start_ok'] is not False and res['valid_samples']:
        valid = True
    if not why and not res['success']:
        why.append(f"the proof was not shown in {old.get('play_s')} s of play" + (f" (the pilot said: {old['pilot_outcome']})" if old.get('pilot_outcome') else ''))
    new = dict(old)
    new.update({'success': int(bool(res['success'])), 'time_to_goal_s': res['time_to_goal_s'], 'progress': res['progress'],
                'start_ok': None if res['start_ok'] is None else int(res['start_ok']), 'valid': int(bool(valid)), 'why': '; '.join(why),
                'fingerprint': board.fingerprint(cell, local), 'referee': res})
    return new
