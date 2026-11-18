"""Short private game-control sockets; run evidence stays in its registered build."""
import json
import os
from pathlib import Path
import stat
import time
import uuid
from src.errors import WorkbenchError, fail
from src.models import ProcessIdentity
from src.registry.process import identity

TMP_ROOT = Path('/tmp')
MAX_SOCKET_BYTES = 107  # sockaddr_un.sun_path includes one terminating NUL.


def _directory(path, *, create=False):
    if create:
        try:
            path.mkdir(mode=0o700)
        except FileExistsError:
            pass
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise fail('refused_by_policy', 'session_runtime_directory')


def runtime_root(config):
    value = os.environ.get('XDG_RUNTIME_DIR')
    root = Path(value) / 'lswb' if value else TMP_ROOT / ('lswb-' + str(os.getuid()))
    if not root.is_absolute():
        raise fail('invalid_argument', 'session_runtime_directory')
    canonical = root.resolve()
    if any(root.is_relative_to(p.resolve()) or canonical.is_relative_to(p.resolve()) for p in config.protected_roots):
        raise fail('refused_by_policy', 'session_runtime_directory')
    if value:
        _directory(Path(value))
    if root.exists() or root.is_symlink():
        _directory(root)
    return root


def check_length(path):
    size = len(os.fsencode(path))
    if size > MAX_SOCKET_BYTES:
        shown = str(path)
        if len(shown) > 512:
            shown = shown[:512] + '… [path truncated]'
        raise WorkbenchError('unavailable', 'session_socket_path', operator_action=
            f'Unix socket path {shown!r} is {size} bytes; maximum is {MAX_SOCKET_BYTES} bytes plus the NUL terminator. Configure a shorter XDG_RUNTIME_DIR.')


def _read_marker(directory):
    _directory(directory)
    fd = os.open(directory / 'owner.json', os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
            raise fail('refused_by_policy', 'session_runtime_owner')
        raw = stream.read(4097)
    if len(raw) > 4096:
        raise fail('refused_by_policy', 'session_runtime_owner')
    marker = json.loads(raw)
    if not isinstance(marker, dict):
        raise fail('refused_by_policy', 'session_runtime_owner')
    return marker


def _write_marker(directory, marker, *, replace=False):
    path = directory / ('owner.new' if replace else 'owner.json')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(marker, stream)
        stream.flush()
        os.fsync(stream.fileno())
    if replace:
        os.replace(path, directory / 'owner.json')


def allocate(deps, run_id):
    root = runtime_root(deps.config)
    directory = root / uuid.uuid4().hex[:12]
    path = directory / 'c.sock'
    check_length(path)  # Before creating directories or starting any child.
    _directory(root, create=True)
    directory.mkdir(mode=0o700)
    owner = identity(os.getpid())
    if owner is None:
        directory.rmdir()
        raise fail('unavailable', 'session_runtime_owner')
    _write_marker(directory, {'state_root': str(deps.config.state_root.resolve()), 'run_id': run_id,
        'owner': owner.model_dump(), 'process_job': None, 'created': time.time()})
    return path


def validate(deps, path, run_id):
    root = runtime_root(deps.config)
    if path.name != 'c.sock' or path.parent.parent != root:
        raise fail('refused_by_policy', 'session_runtime_socket')
    _directory(root)
    marker = _read_marker(path.parent)
    if marker.get('state_root') != str(deps.config.state_root.resolve()) or marker.get('run_id') != run_id:
        raise fail('refused_by_policy', 'session_runtime_owner')
    if path.is_symlink():
        raise fail('refused_by_policy', 'session_runtime_socket')
    return marker


def bind_job(deps, path, run_id, job_id):
    marker = validate(deps, path, run_id)
    marker['process_job'] = job_id
    _write_marker(path.parent, marker, replace=True)


def cleanup(deps, path, run_id):
    if not path.parent.exists():
        return
    validate(deps, path, run_id)
    if any(item.name not in {'c.sock', 'owner.json'} for item in path.parent.iterdir()):
        raise fail('refused_by_policy', 'session_runtime_contents')
    try:
        info = path.lstat()
    except FileNotFoundError:
        pass
    else:
        if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid():
            raise fail('refused_by_policy', 'session_runtime_socket')
        path.unlink()
    (path.parent / 'owner.json').unlink()
    path.parent.rmdir()  # Never recursively remove unexpected contents.


def _dead(birth):
    current = identity(birth.pid)
    return current != birth if current is not None else not Path('/proc', str(birth.pid)).exists()


def cleanup_stale(deps):
    root = runtime_root(deps.config)
    if not root.exists():
        return
    _directory(root)
    for index, directory in enumerate(root.iterdir()):
        if index >= 1000:
            break
        if len(directory.name) != 12 or any(c not in '0123456789abcdef' for c in directory.name):
            continue
        try:
            marker = _read_marker(directory)
            if marker.get('state_root') != str(deps.config.state_root.resolve()):
                continue
            if not _dead(ProcessIdentity.model_validate(marker['owner'])):
                continue
            job_id = marker.get('process_job')
            if job_id:
                birth, _ = deps.registry.process(job_id)
                receipt = deps.registry.receipt(job_id)
                if birth is not None and not _dead(birth):
                    continue
                if birth is None and not (receipt and receipt.process_exited):
                    continue  # An unbound launch is uncertain, never assumed dead.
            cleanup(deps, directory / 'c.sock', marker['run_id'])
        except (OSError, ValueError, KeyError, WorkbenchError):
            continue  # Unknown/foreign state is retained, not adopted or removed.
