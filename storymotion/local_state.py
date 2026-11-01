"""Fail-closed checks for owned mutable local state, before opening SQLite/locks.

Workspace aliases are intentionally canonicalized at initial selection. Pinned
roots and their control descendants must subsequently stay ordinary owned paths.
This is a local path boundary, not a defense against a hostile OS administrator
changing directory entries concurrently with SQLite's own file operations.
"""
import os
import stat
import sqlite3
import tempfile
import shutil

WINDOWS = os.name == "nt"
from pathlib import Path

from .security import WorkflowError

DATABASES = ('jobs.sqlite3', 'llm-jobs.sqlite3', 'voice-jobs.sqlite3', 'reviews.sqlite3')
SIDECARS = ('', '-journal', '-wal', '-shm')
LOCKS = ('.workflow.lock', '.dashboard-instance.lock')
CONTROL_DIRS = ('writing', 'voice', 'renders', 'reviews', 'dashboard', 'imports', '.inputs', '.locks', 'family-inputs', 'family-renders', 'family-receipts', 'family-executions')
PROJECT_SCAN_MAX_ENTRIES = 200000
PROJECT_SCAN_MAX_DEPTH = 128
_PROJECT_FD_FLAGS = os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0) | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_CLOEXEC', 0)
_PROJECT_FD_SUPPORTED = (bool(getattr(os, 'O_DIRECTORY', 0)) and bool(getattr(os, 'O_NOFOLLOW', 0))
                         and os.scandir in os.supports_fd and os.open in os.supports_dir_fd
                         and os.stat in os.supports_dir_fd and os.stat in os.supports_follow_symlinks)


def _unsafe():
    raise WorkflowError('LOCAL_STATE_UNSAFE: linked, unowned, shared or unexpected control path; no external path was followed')


def _private(info, kind, path=None):
    if WINDOWS:
        if info is not None:
            from .windows_native import inspect
            if path is None:_unsafe()
            inspect(path,kind,private=True,missing=False)
        return
    if info is not None and stat.S_IMODE(info.st_mode) != (0o700 if kind == 'dir' else 0o600):
        raise WorkflowError('LOCAL_STATE_PERMISSIONS: private directories require 0700 and state files 0600. No permissions changed. Use a new empty private workspace, or stop the app and review your existing state ownership/permissions before a manual repair. / Yeni özel workspace kullanın veya uygulama kapalıyken mevcut izinleri inceleyin.')


def guard_private(root, relative, kind='file'):
    """Private mutable state only; static source guard_control stays unchanged."""
    root = _root(root, False)
    path = guard_control(root, relative, kind)
    _private(_check(root, 'dir'), 'dir',root)
    current = root
    for index, part in enumerate(Path(relative).parts):
        current = current / part
        part_kind = kind if current == path else 'dir'
        _private(_check(current, part_kind), part_kind,current)
    return path


def private_directory(path):
    """Create only missing directories as 0700; never chmod an existing path."""
    if WINDOWS:
        from .windows_native import mkdir
        return mkdir(path)
    path = _root(path, False)
    missing = [];current = path
    while not current.exists():
        missing.append(current);current = current.parent
    for directory in reversed(missing):
        try:directory.mkdir(mode=0o700)
        except FileExistsError:pass
        _private(_check(directory, 'dir'), 'dir')
    _private(_check(path, 'dir'), 'dir')
    return path


def private_database(root, database, **options):
    """Precreate an owned 0600 inode before SQLite, without changing umask."""
    root = guard_workspace(root, database, canonical_alias=False)
    private_directory(root)
    path = guard_private(root, database)
    descriptor = None
    try:
        try:descriptor = open_control(path, os.O_CREAT | os.O_EXCL | os.O_RDWR | getattr(os,'O_NOFOLLOW',0) | getattr(os,'O_CLOEXEC',0), 0o600)
        except FileExistsError:guard_private(root, database)
        if descriptor is not None:validate_open_control(descriptor, private=True)
    finally:
        if descriptor is not None:os.close(descriptor)
    guard_workspace(root, database, canonical_alias=False)
    return sqlite3.connect(path, **options)


def write_private(path, data):
    """Atomic private user-content write. No mode repair of pre-existing files."""
    if WINDOWS:
        from .windows_native import write
        return write(path,data.encode('utf-8') if isinstance(data,str) else data)
    path = Path(path);private_directory(path.parent)
    guard_private(path.parent, path.name)
    raw = data.encode('utf-8') if isinstance(data, str) else data
    descriptor, temporary = tempfile.mkstemp(prefix='.'+path.name+'.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(raw);stream.flush();os.fsync(stream.fileno())
        guard_private(path.parent, path.name)
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:os.fsync(directory)
        finally:os.close(directory)
    finally:
        Path(temporary).unlink(missing_ok=True)


def copy_private(source, destination):
    """Copy into a new 0600 inode; never chmod or replace another output."""
    if WINDOWS:
        from .windows_native import write
        return write(destination,Path(source).read_bytes(),exclusive=True)
    destination = Path(destination);private_directory(destination.parent)
    guard_private(destination.parent, destination.name)
    try:descriptor = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        raise WorkflowError('LOCAL_STATE_COPY_TARGET_EXISTS: existing output was not changed; inspect it before an explicit retry') from None
    try:info = validate_open_control(descriptor, private=True)
    finally:os.close(descriptor)
    try:
        shutil.copyfile(source, destination)
        current = guard_private(destination.parent, destination.name).stat()
        if (current.st_dev, current.st_ino) != (info.st_dev, info.st_ino):_unsafe()
        descriptor = os.open(destination, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            current = validate_open_control(descriptor, private=True)
            if (current.st_dev,current.st_ino)!=(info.st_dev,info.st_ino):_unsafe()
            os.fsync(descriptor)
        finally:os.close(descriptor)
    except BaseException:
        try:
            current = destination.lstat()
            if stat.S_ISREG(current.st_mode) and (current.st_dev,current.st_ino)==(info.st_dev,info.st_ino):destination.unlink()
        except OSError:pass
        raise


def _check(path, kind):
    if WINDOWS:
        from .windows_native import inspect
        return inspect(path,kind)
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    except OSError:
        _unsafe()
    return _owned_info(info, kind)


def _owned_info(info, kind):
    if (stat.S_ISLNK(info.st_mode) or info.st_uid != os.getuid() or
            (kind == 'dir' and not stat.S_ISDIR(info.st_mode)) or
            (kind == 'file' and (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1))):
        _unsafe()
    return info


def _root(workspace, canonical_alias):
    try:
        lexical = Path(os.path.abspath(workspace))
        root = lexical.resolve()
        if not canonical_alias and lexical != root:
            _unsafe()
        _check(root, 'dir')
        return root
    except (OSError, ValueError, TypeError):
        _unsafe()


def guard_control(root, relative, kind='file'):
    """Check an exact descendant and every internal ancestor without creating it."""
    root = _root(root, False)
    try:
        rel = Path(relative)
        if kind not in {'file', 'dir'} or rel.is_absolute() or not rel.parts or '..' in rel.parts:
            _unsafe()
        current = root
        for index, part in enumerate(rel.parts):
            current = current / part
            _check(current, kind if index == len(rel.parts) - 1 else 'dir')
            if current.resolve() != current:
                _unsafe()
        return current
    except (OSError, ValueError, TypeError):
        _unsafe()


def guard_workspace(workspace, database='jobs.sqlite3', *, canonical_alias=True, skip=()):
    """Read-only preflight for the workspace's known mutable control paths.

    Includes nested dashboard services before any root DB/lock is written. The
    caller rechecks pinned roots on every open; initial explicit aliases retain
    the historical single canonical workspace identity.
    """
    if database not in DATABASES:
        _unsafe()
    root = _root(workspace, canonical_alias)
    _private(_check(root, 'dir'), 'dir',root)
    for name in CONTROL_DIRS:
        guard_private(root, name, 'dir')
    for prefix in ('', 'writing/', 'voice/', 'renders/', 'reviews/', 'family-renders/'):
        for name in DATABASES:
            for suffix in SIDECARS:
                relative = prefix + name + suffix
                if relative not in skip:
                    guard_private(root, relative)
        for name in LOCKS:
            relative = prefix + name
            if relative not in skip:
                guard_private(root, relative)
        # Review lock IDs are dynamic, but their flat directory is host-owned.
        lock_directory=guard_private(root,prefix+'.locks','dir')
        if lock_directory.is_dir():
            try:
                with os.scandir(lock_directory) as entries:
                    for entry in entries:
                        guard_private(root,Path(prefix+'.locks')/entry.name)
            except OSError:
                _unsafe()
    for name in ('family-inputs', 'family-receipts'):
        directory = guard_private(root, name, 'dir')
        if directory.is_dir():
            with os.scandir(directory) as entries:
                for entry in entries:guard_private(root, Path(name)/entry.name)
    return root


def validate_open_control(fd, *, private=False):
    """Check the actual lock inode after O_NOFOLLOW open, before flock/use."""
    if WINDOWS:
        from .windows_native import validate_fd
        return validate_fd(fd,private)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid():
            _unsafe()
        if private:_private(info, 'file')
        return info
    except OSError:
        _unsafe()


def guard_project_scope(project):
    """Only first-run's own mutable subtrees; do not traverse installed vendors.

    Chrome bundles/node_modules legitimately contain vendor-owned symlinks.
    Their top-level roots are checked, but their installed contents are not
    recursively treated as StoryMotion DB/control state.
    """
    if WINDOWS:
        from .windows_native import scan_project
        return scan_project(project)
    try:
        if Path(project).is_symlink():
            _unsafe()
        root = _root(project, True)
        for name in ('node_modules', 'work', '.runtime'):
            guard_control(root, name, 'dir')
        guard_control(root,'optional/remotion/node_modules','dir')
        for name in ('.runtime/chrome', '.runtime/npm-cache', '.runtime/setup-state'):
            guard_control(root, name, 'dir')
        original = _check(root, 'dir')
        if original is None:return root
        if not _PROJECT_FD_SUPPORTED:_unsafe()
        descriptor = os.open(root, _PROJECT_FD_FLAGS)
        try:
            if _project_entry_state(_owned_info(os.fstat(descriptor), 'dir')) != _project_entry_state(original):_unsafe()
            budget = [0]
            for name in ('work', '.runtime'):
                try:info = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
                except FileNotFoundError:continue
                _owned_info(info, 'dir')
                _scan_project_directory(descriptor, name, (name,), info, budget)
                if _project_entry_state(os.stat(name, dir_fd=descriptor, follow_symlinks=False)) != _project_entry_state(info):_unsafe()
            # An anchored descriptor must still name the selected canonical root.
            if (root.resolve() != root or _project_entry_state(_check(root, 'dir')) != _project_entry_state(original)
                    or _project_entry_state(os.fstat(descriptor)) != _project_entry_state(original)):_unsafe()
        finally:os.close(descriptor)
        return root
    except (OSError, ValueError, TypeError):
        _unsafe()


def _project_entry_state(info):
    if info is None:_unsafe()
    # Per-walk identity observations, never a reusable/cache verdict. Atime is
    # excluded because merely reading a directory may update it.
    return (info.st_dev, info.st_ino, info.st_uid, info.st_mode, info.st_nlink,
            info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _scan_project_directory(parent, name, relative, expected, budget):
    if len(relative) > PROJECT_SCAN_MAX_DEPTH:
        raise WorkflowError(f'LOCAL_STATE_SCAN_LIMIT: local mutable state exceeds {PROJECT_SCAN_MAX_DEPTH} relative path components')
    descriptor = os.open(name, _PROJECT_FD_FLAGS, dir_fd=parent)
    try:
        initial = _owned_info(os.fstat(descriptor), 'dir')
        if _project_entry_state(initial) != _project_entry_state(expected):_unsafe()
        rows = [];names = set()
        # Enumerate each directory once. All descendants remain anchored to
        # checked parents, rather than resolving every absolute ancestor again.
        with os.scandir(descriptor) as entries:
            for entry in entries:
                child = entry.name
                if (not isinstance(child, str) or child in ('', '.', '..') or '/' in child or '\0' in child or child in names):_unsafe()
                names.add(child);budget[0] += 1
                if budget[0] > PROJECT_SCAN_MAX_ENTRIES:
                    raise WorkflowError(f'LOCAL_STATE_SCAN_LIMIT: local mutable state exceeds {PROJECT_SCAN_MAX_ENTRIES} entries')
                if len(relative) + 1 > PROJECT_SCAN_MAX_DEPTH:
                    raise WorkflowError(f'LOCAL_STATE_SCAN_LIMIT: local mutable state exceeds {PROJECT_SCAN_MAX_DEPTH} relative path components')
                info = os.stat(child, dir_fd=descriptor, follow_symlinks=False)
                kind = 'dir' if stat.S_ISDIR(info.st_mode) else 'file'
                _owned_info(info, kind)
                rows.append((child, kind, info))
        for child, kind, info in rows:
            path = relative + (child,)
            # Exact existing vendor exclusions only; no new build-tree bypass.
            if kind == 'dir' and path not in (('.runtime', 'chrome'), ('.runtime', 'probe', 'stages')):
                _scan_project_directory(descriptor, child, path, info, budget)
        for child, kind, info in rows:
            current = _owned_info(os.stat(child, dir_fd=descriptor, follow_symlinks=False), kind)
            if _project_entry_state(current) != _project_entry_state(info):_unsafe()
        if _project_entry_state(os.fstat(descriptor)) != _project_entry_state(initial):_unsafe()
    finally:os.close(descriptor)


def open_control(path,flags,mode=0o600):
    if WINDOWS:
        from .windows_native import open_fd
        return open_fd(path,flags,mode)
    return os.open(path,flags,mode)
