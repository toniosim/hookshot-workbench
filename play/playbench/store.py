"""The results store: one SQLite file (WAL, like the nightly's results.sqlite) with a row per night and a row per (night, cell, arm, attempt).

Rules of the nightly store kept: a result is unique per night/cell/arm/attempt, a rerun is a NEW attempt with its own evidence and never replaces the first
sample, and what counts for the trend is the first VALID attempt (a run that was `invalid` - the save did not put Link at the start, the hold ended it, the
player's game appeared - is kept and shown, but is not a pass or a fail of the pilot). A night's identity (pilot commit, build, tools commit) is stored with it,
and every result carries its cell fingerprint and its arm's hash: when either changes the trend starts a new series there.
"""
import json
import sqlite3
from pathlib import Path

SCHEMA = '''
CREATE TABLE IF NOT EXISTS nights (
    night TEXT PRIMARY KEY, started TEXT, ended TEXT, status TEXT NOT NULL, pilot_commit TEXT, pilot_dirty INTEGER, tools_commit TEXT,
    build TEXT, holds INTEGER NOT NULL DEFAULT 0, plan_json TEXT);
CREATE TABLE IF NOT EXISTS cells (
    night TEXT NOT NULL, cell TEXT NOT NULL, arm TEXT NOT NULL, attempt INTEGER NOT NULL, hold INTEGER, tag TEXT,
    success INTEGER NOT NULL, time_to_goal_s REAL, stuck_s REAL, decisions INTEGER, cost_usd REAL, progress REAL,
    start_ok INTEGER, valid INTEGER NOT NULL, why TEXT, pilot_outcome TEXT, play_s REAL, build TEXT, pilot_commit TEXT,
    fingerprint TEXT, arm_hash TEXT, row_json TEXT NOT NULL, blocker TEXT, PRIMARY KEY (night, cell, arm, attempt));
CREATE TABLE IF NOT EXISTS rejudged (
    night TEXT NOT NULL, cell TEXT NOT NULL, arm TEXT NOT NULL, attempt INTEGER NOT NULL, at TEXT NOT NULL, reason TEXT NOT NULL, old_json TEXT NOT NULL);
'''
COLS = ('night', 'cell', 'arm', 'attempt', 'hold', 'tag', 'success', 'time_to_goal_s', 'stuck_s', 'decisions', 'cost_usd', 'progress', 'start_ok', 'valid',
        'why', 'pilot_outcome', 'play_s', 'build', 'pilot_commit', 'fingerprint', 'arm_hash', 'blocker')


class Store:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path), timeout=60)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript(SCHEMA)
        if 'blocker' not in [r[1] for r in self.db.execute('PRAGMA table_info(cells)')]:   # (a store made before blockers existed)
            self.db.execute('ALTER TABLE cells ADD COLUMN blocker TEXT')
            self.db.commit()

    def close(self):
        self.db.close()

    # ---- nights
    def begin_night(self, night, started, plan=None):
        self.db.execute('INSERT OR IGNORE INTO nights (night, started, status, plan_json) VALUES (?,?,?,?)', (night, started, 'running', json.dumps(plan or {})))
        self.db.commit()

    def night_identity(self, night, **kw):
        """Set what the night played with (pilot_commit, pilot_dirty, tools_commit, build); the first value written stays."""
        for k, v in kw.items():
            if k not in ('pilot_commit', 'pilot_dirty', 'tools_commit', 'build'):
                raise KeyError(k)
            self.db.execute(f'UPDATE nights SET {k}=? WHERE night=? AND {k} IS NULL', (v, night))
        self.db.commit()

    def end_night(self, night, status, ended, holds=None):
        self.db.execute('UPDATE nights SET status=?, ended=?, holds=COALESCE(?, holds) WHERE night=?', (status, ended, holds, night))
        self.db.commit()

    def night(self, night):
        r = self.db.execute('SELECT * FROM nights WHERE night=?', (night,)).fetchone()
        return dict(r) if r else None

    def nights(self, last=None):
        rows = [dict(r) for r in self.db.execute('SELECT * FROM nights ORDER BY night')]
        return rows[-last:] if last else rows

    # ---- results
    def add_cell(self, row):
        """Insert one result (a dict with the COLS keys, `valid` and `success` as 0/1); an attempt already stored is not replaced (ValueError)."""
        vals = [row.get(c) for c in COLS]
        try:
            self.db.execute(f'INSERT INTO cells ({",".join(COLS)}, row_json) VALUES ({",".join("?" * len(COLS))}, ?)', vals + [json.dumps(row, sort_keys=True)])
        except sqlite3.IntegrityError:
            raise ValueError(f'{row.get("night")}/{row.get("cell")}/{row.get("arm")} attempt {row.get("attempt")} is already stored') from None
        self.db.commit()

    def rejudge(self, night, cell, arm, attempt, new_row, reason, at):
        """Replace the JUDGEMENT of a stored result (its proof was wrong, not its sample): the journal is the same, the referee's reading of it changed. The row as it was
        is kept whole in `rejudged` with the reason and the time; nothing else about the run (tag, metrics, cost, evidence) changes."""
        old = self.db.execute('SELECT * FROM cells WHERE night=? AND cell=? AND arm=? AND attempt=?', (night, cell, arm, attempt)).fetchone()
        if old is None:
            raise KeyError(f'{night}/{cell}/{arm}/{attempt}')
        self.db.execute('INSERT INTO rejudged VALUES (?,?,?,?,?,?,?)', (night, cell, arm, attempt, at, reason, json.dumps(dict(old), sort_keys=True)))
        cols = ('success', 'time_to_goal_s', 'progress', 'start_ok', 'valid', 'why', 'fingerprint')
        self.db.execute(f'UPDATE cells SET {",".join(c + "=?" for c in cols)}, row_json=? WHERE night=? AND cell=? AND arm=? AND attempt=?',
                        [new_row[c] for c in cols] + [json.dumps(new_row, sort_keys=True), night, cell, arm, attempt])
        self.db.commit()

    def annotate_blocker(self, night, cell, blocker):
        """Mark the stored FAILED results of a cell on a night as blocked by a known cause (text); successes are left alone. Returns how many rows changed."""
        cur = self.db.execute('UPDATE cells SET blocker=? WHERE night=? AND cell=? AND success=0 AND valid=1', (blocker, night, cell))
        self.db.commit()
        return cur.rowcount

    def rejudgements(self, night=None):
        q, a = ('SELECT * FROM rejudged WHERE night=? ORDER BY at', (night,)) if night else ('SELECT * FROM rejudged ORDER BY at', ())
        return [dict(r) for r in self.db.execute(q, a)]

    def attempts(self, night):
        return [dict(r) for r in self.db.execute('SELECT * FROM cells WHERE night=? ORDER BY cell, arm, attempt', (night,))]

    def counted(self, night):
        """{(cell, arm): row}: the first valid attempt, else the last attempt (invalid)."""
        out = {}
        for r in self.attempts(night):
            k = (r['cell'], r['arm'])
            cur = out.get(k)
            if cur is None or (not cur['valid'] and (r['valid'] or r['attempt'] > cur['attempt'])):
                out[k] = r
        return out

    def next_attempt(self, night, cell, arm):
        r = self.db.execute('SELECT MAX(attempt) FROM cells WHERE night=? AND cell=? AND arm=?', (night, cell, arm)).fetchone()
        return (r[0] or 0) + 1

    def all_counted(self, last_nights=None):
        """[(night row, {(cell, arm): row})] for the stored nights, oldest first (the last `last_nights` of them). A PROVING run (a plan with `proof`: a few cells played
        to see that a fix works before a night) is not a night of the trend and is left out."""
        def real(n):
            try:
                return not json.loads(n['plan_json'] or '{}').get('proof')
            except ValueError:
                return True
        nights = [n for n in self.nights() if real(n)]
        if last_nights:
            nights = nights[-last_nights:]
        return [(n, self.counted(n['night'])) for n in nights]

    def export_jsonl(self, path):
        with open(path, 'w') as f:
            for n in self.nights():
                for r in self.attempts(n['night']):
                    f.write(json.dumps({**r, 'pilot_commit_night': n['pilot_commit'], 'build_night': n['build']}, sort_keys=True) + '\n')
