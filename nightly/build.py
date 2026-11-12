"""Full workbench build of an immutable nightly target, into an owned reflink snapshot."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import HARN, LOCAL, capture, command, env_clean, gated, put, stamp, text


def resolve(config, out):
    release = json.loads(capture(['gh', 'release', 'view', 'nightly', '--repo', config['repository'],
                                 '--json', 'tagName,publishedAt,targetCommitish,url,name']))
    fetched = capture(['git', '-C', config['repo'], 'fetch', 'origin', '+refs/tags/nightly:refs/tags/nightly'])
    (out / 'fetch.log').write_text(fetched)
    commit = capture(['git', '-C', config['repo'], 'rev-parse', 'nightly^{commit}']).strip()
    assert re.fullmatch('[0-9a-f]{40}', commit)
    put(out / 'release.json', {**release, 'commit': commit, 'resolved_at': stamp()})
    return commit


def run(config, out, commit=None):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    commit = commit or resolve(config, out)
    wt, staging = Path(config['worktree']), Path(config['build_copy'])
    dest = Path(config['copy_prefix'] + out.name)
    info = {'commit': commit, 'started': stamp(), 'warnings_suppressed_by_upstream': True,
            'copy': str(dest), 'worktree': str(wt), 'status': 'building'}
    put(out / 'build.json', info)
    from monitor import wait_for_player_idle
    wait_for_player_idle(config, out / 'player-idle.jsonl')
    if not wt.exists():
        capture(['git', '-C', config['repo'], 'worktree', 'add', '--detach', wt, commit])
    else:
        dirty = capture(['git', '-C', wt, 'status', '--porcelain', '--untracked-files=no'])
        if dirty.strip():
            raise RuntimeError('Owned nightly worktree has tracked changes; refusing to replace them')
        capture(['git', '-C', wt, 'checkout', '--detach', commit])
    assert capture(['git', '-C', wt, 'rev-parse', 'HEAD']).strip() == commit
    for diagnostic in config.get('diagnostic_commits', []):
        capture(['git', '-c', 'user.name=' + config['author_name'],
                 '-c', 'user.email=' + config['author_email'], '-C', wt, 'cherry-pick', '-x', diagnostic])
    info['source_commit'] = capture(['git', '-C', wt, 'rev-parse', 'HEAD']).strip()
    info['diagnostic_commits'] = config.get('diagnostic_commits', [])
    put(out / 'build.json', info)
    rc = command([HARN / 'tools/deps-local.sh', wt], out / 'deps.log')
    if rc:
        raise RuntimeError('Dependency setup failed; see deps.log')
    profile_env = env_clean({'TMPDIR': config['release_cache']})
    if not (wt / 'work/hookshot_pieces.prof').is_file():
        # release_parts uses gh's authenticated downloads without printing its token.
        profile_env['GH_TOKEN'] = capture(['gh', 'auth', 'token']).strip()
        rc = command([config['python'], '-I', '-B', 'scripts/release_parts.py', 'profile',
                      config['release_setup'], 'work'], out / 'profile.log', cwd=wt, env=profile_env)
        profile_env.pop('GH_TOKEN', None)
        if rc:
            raise RuntimeError('Play profile setup failed; see profile.log')
    build_env = ['RX_CPM=' + config['cpm'], 'HOOKSHOT_LIFT_JOBS=8', 'HOOKSHOT_KEEP_BUILD_FILES=1']
    if config.get('ngx_sdk'):
        if not Path(config['ngx_sdk']).is_dir():
            raise RuntimeError('Already accepted local upscaler SDK is missing; no license is accepted automatically')
        build_env.append('HOOKSHOT_NGX_SDK=' + config['ngx_sdk'])
    argv = gated(['flock', config['full_build_lock'], config['build_gate'], 'env', *build_env,
                  config['python'], '-I', '-B', '-u', 'nx2/make_game.py',
                  '--romfs', config['romfs'], '--exefs', config['exefs'], '--out', staging,
                  '--work', wt / 'work/build', '--jobs', str(config['build_jobs']),
                  '--no-prepare-shaders', '--log', out / 'make-game.log'])
    put(out / 'build-command.json', argv)
    start = time.monotonic()
    rc = command(argv, out / 'build.log', cwd=wt, guard=config)
    elapsed = time.monotonic() - start
    log = text(out / 'build.log')
    warnings = [line for line in log.splitlines() if re.search(r'\bwarning\b', line, re.I)]
    info.update(exit=rc, elapsed_including_gate_s=elapsed, ended=stamp(), warnings=warnings)
    # make_game reports its own elapsed duration; gate waiting is separate above.
    duration = re.findall(r'the build took[^\n]+', log)
    info['build_duration_lines'] = duration
    if rc or '@@done ' not in log:
        info['status'] = 'failed'
        put(out / 'build.json', info)
        raise RuntimeError('Full build failed or missing @@done; see build.log')
    if dest.exists():
        raise RuntimeError('Night snapshot already exists; refusing to overwrite it')
    capture(['cp', '-a', '--reflink=always', staging, dest])
    (dest / '.nightly-owned').write_text(out.name + '\n')
    info['binary_bytes'] = {name: (dest / name).stat().st_size for name in ('hookshot', 'hookshot_vk.so')}
    info['binary_sha256'] = {name: hashlib.file_digest((dest / name).open('rb'), 'sha256').hexdigest()
                             for name in info['binary_bytes']}
    info['non_romfs_bytes'] = sum(p.stat().st_size for p in dest.rglob('*')
                                 if p.is_file() and 'romfs' not in p.relative_to(dest).parts)
    info['status'] = 'passed'
    put(out / 'build.json', info)
    return info


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output')
    parser.add_argument('--config', type=Path, default=LOCAL / 'config.json')
    parser.add_argument('--commit', help='already fetched immutable commit; avoids a second fetch during a resumed cycle')
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    print(json.dumps(run(config, Path(args.output), args.commit), indent=2), flush=True)
