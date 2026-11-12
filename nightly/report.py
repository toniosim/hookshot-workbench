"""Plain local reports, tracker searches and unposted issue-form drafts."""
from pathlib import Path
from collections import Counter
import json
import subprocess
from common import HARN, capture, put, slug, stamp


def report(local, night, build, tests, test_diff, results, findings, status, error=None):
    counts = Counter(r['status'] for r in results)
    tc = Counter(t['status'] for t in tests.values())
    elapsed = sum(r.get('elapsed_game_s') or 0 for r in results)
    lines = [f'# Nightly playtest — {night}', '', '## State', '',
             f'{stamp()} — {status}. ' + (error or ''), '',
             '## What was tested', '',
             f"Published nightly commit: `{build['commit']}`; built from source with the full workbench build.",
             f"Build: {build['status']}; elapsed including gate: {build.get('elapsed_including_gate_s', 0):.1f} s.",
             'Build duration: ' + '; '.join(build.get('build_duration_lines', [])),
             'Compiler warnings are suppressed upstream; an empty warning list is not a warning-free build.',
             f"Binary sizes (bytes): `{json.dumps(build.get('binary_bytes', {}), sort_keys=True)}`.",
             f'{len(results)} scenario attempts; {elapsed:.1f} s of wrapper/game elapsed time (queue waits excluded).',
             f'Scenario outcomes: {dict(counts)}. Game-free suite: {dict(tc)}.', '',
             '## Regressions and first observations', '']
    if findings:
        for finding in findings:
            lines += [f"### {finding['scenario']}: {finding['kind']}", '',
                      '```json', json.dumps(finding, indent=2), '```', '']
    else:
        lines += [('No established regression. A first gameplay night only seeds its baseline; it cannot establish historical speed or image stability.'
                   if results else 'No gameplay scenarios ran. No gameplay baseline or GPU regression claim exists.'), '']
    lines += ['## Scenario evidence', '', '| Scenario | Result | Save | Time (s) | Timings judged? |', '|---|---|---|---:|---|']
    for r in results:
        lines.append(f"| {r['id']} | {r['status']} | {r.get('save') or 'fresh profile'} | {r.get('elapsed_game_s') or 0:.1f} | {'no: disturbed' if r['disturbed'] else 'yes'} |")
    for r in results:
        lines += ['', f"### {r['id']}", '', f"Checks: {'; '.join(r.get('checks', [])) or 'none completed'}.",
                  f"Error: {r.get('error', 'none')}", '```text', r.get('summary', 'No wrapper summary.'), '```',
                  'Load/evidence: `' + r.get('evidence_dir', '') + '`.',
                  'Disturbance: ' + '; '.join(r.get('disturbance', [])),
                  'Missing metrics: ' + json.dumps(r.get('missing', {})),
                  'Images are collected, not human-reviewed by this automated report. Review before citing or posting.',
                  'Image diagnostics: ' + json.dumps({k: {x: v[x] for x in ('black', 'blank')} for k, v in r.get('images', {}).items()}),
                  'Flash candidates: ' + json.dumps(r.get('flash_candidates', []))]
    lines += ['', '## Game-free changes', '', 'New failures: ' + json.dumps(test_diff.get('new_failures', [])),
              'Vanished tests: ' + json.dumps(test_diff.get('vanished', [])),
              'Failures tonight: ' + json.dumps([k for k, v in tests.items() if v['status'] in ('FAIL', 'TIMEOUT')]),
              'Slowest tests that became slower (observations only under load):',
              '```json', json.dumps(test_diff.get('slower', []), indent=2), '```', '',
              '## Improvements', '',
              'Only empirical-band comparisons are labeled improvements; first-night and disturbed timing values are not.',
              '```json', json.dumps([{'scenario': r['id'], 'metric': k, **v} for r in results
                                    for k, v in r.get('comparisons', {}).items() if v['state'] == 'improvement'], indent=2), '```', '',
              '## What could not be judged', '',
              'Ordinary queue runs do not establish frame-rate changes, even when a sampled load looks low. '
              'Timings and memory are retained but excluded from their empirical baseline while disturbed. '
              'A timing/memory regression requires one undisturbed confirming rerun. '
              'Headless renderer intervals are CPU offscreen-submit intervals, not scanout or GPU completion.',
              'Image comparison needs three accepted matching-scenario nights; it is tolerant of historical variation, '
              'not proof of correctness. Black/blank and sparse flash candidates require visual review.',
              'Long-duration growth, exhaustive menu/destination coverage, save-write cycles, intentional build load, '
              'cold-cache and two-game stress are designed extensions, not exercised by this initial suite.', '',
              '## Files and privacy', '',
              f'Raw evidence: `{local / "raw" / night}`. Database: `{local / "results.sqlite"}`. '
              f'Baseline index: `{local / "baselines" / "latest.json"}`.',
              'Save inputs and run saves remain in the private harness/game copies. Nothing is uploaded or posted.',
              'No timer is implied by this report; consult timer.json for a separately approved transient arm.']
    destination = local / 'reports' / (night + '.md')
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp = destination.with_suffix('.md.next')
    tmp.write_text('\n'.join(lines) + '\n')
    tmp.replace(destination)
    return destination


def enrich(config, night, build, finding, spec, good, out):
    """Read-only tracker search; never create or comment on an issue."""
    out.mkdir(parents=True, exist_ok=True)
    query = spec.get('issue_query', 'Linux')
    searches = []
    commands = [
        ['gh', 'search', 'issues', '--repo', config['repository'], '--state', 'open', '--limit', '30',
         '--json', 'number,title,url', query],
        ['gh', 'pr', 'list', '--repo', config['repository'], '--state', 'all', '--search', query,
         '--limit', '30', '--json', 'number,title,state,url'],
    ]
    for command in commands:
        p = subprocess.run(command, capture_output=True, text=True, timeout=120)
        searches.append({'argv': command, 'exit': p.returncode, 'stdout': p.stdout, 'stderr': p.stderr})
    put(out / 'tracker-search.json', {'at': stamp(), 'searches': searches})
    finding['tracker_search'] = str(out / 'tracker-search.json')
    finding['duplicate_review'] = 'Search results require human matching; no issue was opened.'
    if good:
        revision_range = good['commit'] + '..' + build['commit']
        finding['last_good_commit'] = good['commit']
        finding['commit_range'] = revision_range
        (out / 'commits.txt').write_text(capture(['git', '-C', config['repo'], 'log', '--format=%H %s', '--reverse', revision_range]))
        paths = spec.get('affected_paths', [])
        (out / 'suspects.txt').write_text(capture(['git', '-C', config['repo'], 'log', '--format=%H %s', '--reverse',
                                                revision_range, '--', *paths]))
        finding['suspected_commits'] = str(out / 'suspects.txt')
        hunt = HARN / 'regress' / 'regress.py'
        if hunt.is_file():
            p = subprocess.run([config['python'], '-I', '-B', str(hunt), 'plan', '--repo', config['repo'],
                                '--good', good['commit'], '--bad', build['commit'], '--output', str(out / 'hunt-plan')],
                               capture_output=True, text=True, timeout=180)
            (out / 'hunt-plan.log').write_text(p.stdout + p.stderr)
            finding['hunt_plan_exit'] = p.returncode
        from hunt import handoff
        finding['hunt'] = handoff(config, spec, good, build, finding, out)
    draft = Path(config['drafts']) / f'nightly-{night}-{slug(finding["scenario"])}-{slug(finding["kind"])}.md'
    draft.parent.mkdir(parents=True, exist_ok=True)
    lines = [f'# Draft — {finding["scenario"]}: {finding["kind"]}', '',
             'Draft only; inspect the evidence and duplicate search before publication.', '',
             '### Hookshot version', build['commit'], '', '### What kind of problem', 'Something else', '',
             '### What happened', '```json', json.dumps(finding, indent=2), '```', '',
             '### Where in the game', spec.get('description', spec['id']), '',
             '### How often', 'Once so far; any confirmation evidence is recorded above.', '',
             '### Graphics card and driver version', '\n'.join(finding.get('device_lines', [])) or 'Unavailable in the failed run; no device identity assumed.', '',
             '### CPU, RAM and operating system', finding.get('hardware', config.get('hardware', 'Unavailable in the recorded environment.')), '',
             '### Changes from the defaults', '```json', json.dumps(spec.get('settings', {}), indent=2), '```', '',
             '### Other software hooked into the game', 'No, nothing hooked in. Automated control and trace switches are recorded.', '',
             '### hookshot_log.txt', finding.get('log', 'See the scenario evidence directory in the night report.'), '',
             '### Screenshots or video', 'Collected locally; visual review and selection required, nothing attached automatically.', '',
             '### Before you send it', '- [ ] Confirm still present on the newest release.',
             '- [ ] Read the saved open-issue and PR search and select an existing thread when appropriate.',
             '- [x] No game files, saves, keys, binaries or shader caches are attached.', '',
             'Score is not guessed: choose severity, affected reach and confidence after evidence review.']
    if spec.get('form') == 'build':
        lines = [f'# Draft — {finding["scenario"]}: {finding["kind"]}', '',
                 '### Builder version', build['commit'], '', '### How you built',
                 'Command line (nx2/make_game.py), followed by the complete game-free suite.', '',
                 '### Game files given to it', 'romfs and exefs folders (build only; the failing suite needs no game).', '',
                 '### The error', '```json', json.dumps(finding, indent=2), '```', '',
                 '### Visual Studio or Build Tools version, and Windows SDK version',
                 'Not applicable: Linux.', '', '### Operating system and free space on the output drive',
                 finding.get('hardware', 'See the retained environment.') + '; free bytes: ' +
                 str(__import__('shutil').disk_usage(out).free), '',
                 '### Before you send it', '- [ ] Check whether the newest release has the same failure.',
                 '- [ ] Read the retained open-issue and PR search for duplicates.',
                 '- [x] No game files or anything built from them are attached.']
    draft.write_text('\n'.join(lines) + '\n')
    finding['draft'] = str(draft)


def discord(config, night, build, results, findings):
    dest = Path(config['drafts']) / ('DISCORD-nightly-' + night + '.md')
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not results:
        dest.write_text(f"Progress (mooki000's agent): built nightly {build['commit'][:12]} from source on Linux.\n"
                        "The build and named game-free suite evidence are retained in the local report.\n"
                        "No nightly GPU scenarios ran; no gameplay baseline exists. GPU time is reserved for the regression hunt.\n"
                        "The optional timer is disabled; nothing posted or attached.\n")
        return dest
    passed = sum(r['status'] == 'passed' for r in results)
    dest.write_text(f"Progress (mooki000's agent): tested nightly {build['commit'][:12]} from source on Linux.\n"
                    f"{passed}/{len(results)} scenario attempts completed; {len(findings)} findings need review.\n"
                    "Ordinary-queue timings are disturbed, not performance claims; this first record seeds the baseline.\n"
                    "Logs, pictures and the named game-free results are local; nothing posted or attached.\n")
    return dest
