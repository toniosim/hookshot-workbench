import os
from pathlib import Path
import pytest
from src.errors import WorkbenchError
from src.effects import session_runtime as runtime


@pytest.fixture
def private_runtime(tmp_path, monkeypatch):
    monkeypatch.delenv('XDG_RUNTIME_DIR', raising=False)
    monkeypatch.setattr(runtime, 'TMP_ROOT', tmp_path)
    return tmp_path / ('lswb-' + str(os.getuid()))


def test_unset_runtime_fallback_is_private_and_removed(deps, private_runtime):
    path = runtime.allocate(deps, 'run_' + '1' * 32)
    assert path.parent.parent == private_runtime
    assert private_runtime.stat().st_mode & 0o777 == 0o700
    assert path.parent.stat().st_mode & 0o777 == 0o700
    assert (path.parent / 'owner.json').stat().st_mode & 0o777 == 0o600
    runtime.cleanup(deps, path, 'run_' + '1' * 32)
    assert not path.parent.exists()


def test_xdg_runtime_directory(deps, tmp_path, monkeypatch):
    xdg = tmp_path / 'xdg'
    xdg.mkdir(mode=0o700)
    monkeypatch.setenv('XDG_RUNTIME_DIR', str(xdg))
    path = runtime.allocate(deps, 'run_' + '2' * 32)
    assert path.parent.parent == xdg / 'lswb'
    runtime.cleanup(deps, path, 'run_' + '2' * 32)


@pytest.mark.parametrize('mode', [0o755, 0o777])
def test_existing_fallback_with_wrong_mode_refuses(deps, private_runtime, mode):
    private_runtime.mkdir(mode=mode)
    private_runtime.chmod(mode)
    with pytest.raises(WorkbenchError) as error:
        runtime.allocate(deps, 'run_' + '3' * 32)
    assert error.value.envelope.code == 'refused_by_policy'
    assert private_runtime.stat().st_mode & 0o777 == mode


def test_existing_fallback_with_wrong_owner_refuses(deps, tmp_path, monkeypatch, private_runtime):
    wrong_uid = os.getuid() + 1
    wrong_root = tmp_path / ('lswb-' + str(wrong_uid))
    wrong_root.mkdir(mode=0o700)
    monkeypatch.setattr(runtime.os, 'getuid', lambda: wrong_uid)
    with pytest.raises(WorkbenchError):
        runtime.allocate(deps, 'run_' + '4' * 32)
    assert not list(wrong_root.iterdir())


def test_fallback_symlink_refuses(deps, tmp_path, private_runtime):
    other = tmp_path / 'other'
    other.mkdir(mode=0o700)
    private_runtime.symlink_to(other, target_is_directory=True)
    with pytest.raises(WorkbenchError):
        runtime.allocate(deps, 'run_' + '5' * 32)
    assert not list(other.iterdir())


def test_socket_length_counts_encoded_bytes():
    runtime.check_length(Path('/' + 'a' * 106))
    for path in (Path('/' + 'a' * 107), Path('/tmp') / ('é' * 52)):
        with pytest.raises(WorkbenchError) as error:
            runtime.check_length(path)
        assert error.value.envelope.operation == 'session_socket_path'
        assert str(path) in error.value.envelope.operator_action
        assert str(len(os.fsencode(path))) in error.value.envelope.operator_action
        assert '107' in error.value.envelope.operator_action


async def test_stale_cleanup_keeps_live_and_uncertain_owners(deps, private_runtime):
    await deps.open()
    try:
        stale = runtime.allocate(deps, 'run_' + '6' * 32)
        live = runtime.allocate(deps, 'run_' + '7' * 32)
        uncertain = runtime.allocate(deps, 'run_' + '8' * 32)
        job = deps.registry.create_job('session_process')
        runtime.bind_job(deps, uncertain, 'run_' + '8' * 32, job.job_id)
        for path in (stale, uncertain):
            marker = runtime._read_marker(path.parent)
            marker['owner']['pid'] = 999999999
            runtime._write_marker(path.parent, marker, replace=True)
        runtime.cleanup_stale(deps)
        assert not stale.parent.exists()
        assert live.parent.exists() and uncertain.parent.exists()
        runtime.cleanup(deps, live, 'run_' + '7' * 32)
        runtime.cleanup(deps, uncertain, 'run_' + '8' * 32)
    finally:
        await deps.close()
