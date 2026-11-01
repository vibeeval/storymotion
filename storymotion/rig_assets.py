"""Pinned original neutral rig assets, staged and packaged without new trust.

Only the two fixed local renderer files are accepted. Staged/ZIP bytes are
compared to the source hashes already pinned by the host edit plan, never to a
new hash accepted from a changed staging directory. No renderer or media runs.
"""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import uuid
import zipfile

from .security import WorkflowError, canonical, digest

ROOT = Path(__file__).resolve().parents[1]
ASSETS = (
    {'path': 'renderers/neutral-rig.json', 'staged_file': 'assets/rig/definition.json',
     'role': 'neutral_rig_definition', 'rights': 'original_project_vectors'},
    {'path': 'renderers/rig-motion.mjs', 'staged_file': 'assets/rig/rig-motion.mjs',
     'role': 'neutral_rig_motion', 'rights': 'original_project_code'},
)
MAX_DEFINITION = 65_536
MAX_MOTION = 262_144
MAX_METADATA = 4 * 1024 * 1024
MAX_ARCHIVE = 512 * 1024 * 1024
_IO_ERRORS = (OSError, ValueError, TypeError, KeyError, UnicodeError,
              OverflowError, RecursionError, RuntimeError, zipfile.BadZipFile,
              zipfile.LargeZipFile)


def _fail(message='Pinned neutral rig asset binding is missing or changed'):
    raise WorkflowError(message)


def _relative(value):
    if (not isinstance(value, str) or not value or '\\' in value or '\x00' in value or
            PurePosixPath(value).is_absolute() or
            any(p in {'', '.', '..'} for p in value.split('/'))):
        _fail('Neutral rig paths must be fixed relative ordinary file paths')
    return value.split('/')


@contextmanager
def _directory(root, parts=(), create=False):
    """Walk each directory using O_NOFOLLOW, including ancestors of root.

    No project-root alias is silently resolved. A caller may supply its already
    canonical workspace root, as Engine/Store normally do. New directories are
    confined to the explicit relative staging subtree.
    """
    selected = Path(root)
    if '..' in selected.parts:
        _fail('Neutral rig asset root cannot traverse parent directories')
    base = Path(os.path.abspath(selected))
    flags = os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0) | getattr(os, 'O_NOFOLLOW', 0)
    flags |= getattr(os, 'O_CLOEXEC', 0) | getattr(os, 'O_NONBLOCK', 0)
    fd = os.open(base.anchor, flags)
    try:
        for name in base.parts[1:]:
            next_fd = os.open(name, flags, dir_fd=fd)
            os.close(fd)
            fd = next_fd
            if not stat.S_ISDIR(os.fstat(fd).st_mode):
                _fail('Neutral rig asset ancestor must be an ordinary directory')
        for name in parts:
            if create:
                try:
                    os.mkdir(name, mode=0o700, dir_fd=fd)
                except FileExistsError:
                    pass
            next_fd = os.open(name, flags, dir_fd=fd)
            os.close(fd)
            fd = next_fd
            if not stat.S_ISDIR(os.fstat(fd).st_mode):
                _fail('Neutral rig staging ancestor must be an ordinary directory')
        yield fd
    finally:
        os.close(fd)


def _identity(value):
    return (value.st_dev, value.st_ino, value.st_mode, value.st_nlink,
            value.st_size, value.st_mtime_ns, value.st_ctime_ns)


@contextmanager
def _regular(root, relative, maximum):
    if os.name=='nt':
        from .windows_native import regular
        with regular(root,relative,maximum) as stream:yield stream
        return
    parts = _relative(relative)
    with _directory(root, parts[:-1]) as parent:
        fd = os.open(parts[-1], os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) |
                     getattr(os, 'O_NONBLOCK', 0) | getattr(os, 'O_CLOEXEC', 0), dir_fd=parent)
        with os.fdopen(fd, 'rb') as stream:
            before = os.fstat(stream.fileno())
            if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or
                    not 0 < before.st_size <= maximum):
                _fail('Neutral rig asset must be one bounded ordinary file')
            yield stream
            after = os.fstat(stream.fileno())
            current = os.stat(parts[-1], dir_fd=parent, follow_symlinks=False)
            if _identity(before) != _identity(after) or _identity(after) != _identity(current):
                _fail('Neutral rig asset changed during inspection')


def _read(root, relative, maximum):
    with _regular(root, relative, maximum) as stream:
        raw = stream.read(maximum + 1)
        if not raw or len(raw) > maximum:
            _fail('Neutral rig file exceeds its bounded byte limit')
        return raw


def _json(raw):
    def unique(pairs):
        value = {}
        for name, item in pairs:
            if name in value:
                _fail('Duplicate neutral rig metadata property')
            value[name] = item
        return value
    value = json.loads(raw, object_pairs_hook=unique,
                       parse_constant=lambda _: _fail('Neutral rig metadata must be finite JSON'))
    canonical(value)
    return value


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _exists(root, relative):
    if os.name=='nt':
        from .windows_native import inspect
        return inspect(Path(root)/relative) is not None
    parts = _relative(relative)
    with _directory(root, parts[:-1]) as parent:
        try:
            os.stat(parts[-1], dir_fd=parent, follow_symlinks=False)
            return True
        except FileNotFoundError:
            return False


def _validate_specs(specs, expected):
    if not isinstance(specs, list) or len(specs) != 2:
        _fail('Exactly two pinned neutral rig assets are required')
    for spec in specs:
        if (not isinstance(spec, dict) or set(spec) != {'path', 'staged_file', 'sha256', 'role', 'rights'} or
                not isinstance(spec['sha256'], str) or not re.fullmatch('[a-f0-9]{64}', spec['sha256'])):
            _fail('Invalid pinned neutral rig asset fields')
    if canonical(specs) != canonical(expected):
        _fail('Pinned neutral rig source asset paths, rights or hashes changed')


def required_rig_assets(root=None):
    """Return detached fixed path/role/rights/bytehash specs for the edit plan."""
    try:
        from .viseme import rig_descriptor
        base = ROOT if root is None else root
        descriptor = rig_descriptor(base)
        result = []
        for spec, maximum in zip(ASSETS, (MAX_DEFINITION, MAX_MOTION)):
            raw = _read(base, spec['path'], maximum)
            sha = _sha(raw)
            if spec['role'] == 'neutral_rig_definition' and sha != descriptor['sha256']:
                _fail('Neutral rig definition changed while pinning its byte hash')
            result.append({**spec, 'sha256': sha})
        return result
    except _IO_ERRORS:
        raise WorkflowError('Pinned local neutral rig source assets missing or invalid') from None


def _preflight_target(root, relative):
    if os.name=='nt':
        from .windows_native import inspect
        inspect(Path(root)/relative)
        return
    parts = _relative(relative)
    # This also rejects an existing linked ancestor before any target write.
    with _directory(root) as root_fd:
        fd = os.dup(root_fd)
        try:
            flags = os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0) | getattr(os, 'O_NOFOLLOW', 0)
            for name in parts[:-1]:
                try:
                    next_fd = os.open(name, flags, dir_fd=fd)
                except FileNotFoundError:
                    return
                os.close(fd)
                fd = next_fd
            try:
                value = os.stat(parts[-1], dir_fd=fd, follow_symlinks=False)
            except FileNotFoundError:
                return
            if not stat.S_ISREG(value.st_mode) or value.st_nlink != 1:
                _fail('Neutral rig staging target must be an ordinary unlinked file')
        finally:
            os.close(fd)


def _write_atomic(root, relative, raw):
    if os.name=='nt':
        from .windows_native import write
        return write(Path(root)/relative,raw)
    parts = _relative(relative)
    with _directory(root, parts[:-1], create=True) as parent:
        name = '.rig-stage-' + uuid.uuid4().hex + '.tmp'
        fd = os.open(name, os.O_CREAT | os.O_EXCL | os.O_WRONLY |
                     getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_CLOEXEC', 0), 0o600, dir_fd=parent)
        published = False
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            # Revalidate immediately before replace as well as in preflight.
            try:
                current = os.stat(parts[-1], dir_fd=parent, follow_symlinks=False)
            except FileNotFoundError:
                current = None
            if current is not None and (not stat.S_ISREG(current.st_mode) or current.st_nlink != 1):
                _fail('Neutral rig staging target changed to a linked or special file')
            os.replace(name, parts[-1], src_dir_fd=parent, dst_dir_fd=parent)
            published = True
        finally:
            if not published:
                try:
                    os.unlink(name, dir_fd=parent)
                except FileNotFoundError:
                    pass


def stage_rig_assets(specs, out, root=None):
    """Copy only the two pinned source byte sequences; return staged filenames.

    Empty specs are a no-op for jobs without a rig. Existing safe regular files
    may be repaired on prepare/resume; links/special files are never overwritten.
    All source and target controls are checked before the first asset write.
    """
    if specs is None or specs == []:
        return []
    try:
        base = ROOT if root is None else root
        expected = required_rig_assets(base)
        _validate_specs(specs, expected)
        copies = []
        for spec, maximum in zip(specs, (MAX_DEFINITION, MAX_MOTION)):
            raw = _read(base, spec['path'], maximum)
            if _sha(raw) != spec['sha256']:
                _fail('Neutral rig source changed after the edit plan was pinned')
            copies.append((spec, raw, maximum))
            _preflight_target(out, spec['staged_file'])
        for spec, raw, maximum in copies:
            _write_atomic(out, spec['staged_file'], raw)
            if _sha(_read(out, spec['staged_file'], maximum)) != spec['sha256']:
                _fail('Staged neutral rig bytes differ from the pinned source hash')
        return [spec['staged_file'] for spec in specs]
    except _IO_ERRORS:
        raise WorkflowError('Neutral rig staging failed; no linked or external asset is accepted') from None


def _binding(record, rig_sha, definition_sha):
    if (not isinstance(record, dict) or record.get('rig_sha256') != rig_sha or
            record.get('rig_definition_sha256') != definition_sha):
        _fail('Neutral rig receipt, QA or delivery binding is missing or changed')


def verify_rig_assets(payload, out, delivery=False):
    """Verify rig plan, staged bytes, optional receipts and final delivery bytes.

    Receipt/QA are optional only while preparing; any existing record must bind
    this exact rig and definition. Delivery requires both and the same ordinary,
    unique ZIP members. This is integrity validation, never human acceptance.
    """
    try:
        if not isinstance(payload, dict) or not isinstance(payload.get('brief'), dict):
            _fail('Neutral rig verifier requires the current host brief')
        brief = payload['brief']
        rig = brief.get('rig')
        if rig is None:
            return
        if not isinstance(rig, dict):
            _fail('Explicit neutral rig specification is invalid')
        plan = payload['edit_plan']
        if not isinstance(plan, dict):
            _fail('Neutral rig verifier requires its current host edit plan')
        expected = required_rig_assets()
        _validate_specs(plan.get('rig_assets'), expected)
        rig_sha, definition_sha = digest(rig), expected[0]['sha256']
        if (plan.get('rig_sha256') != rig_sha or rig.get('rig_sha256') != definition_sha or
                rig.get('rig_id') != 'neutral-presenter-1'):
            _fail('Neutral rig edit plan or definition binding changed')
        raw_files = {}
        for spec, maximum in zip(expected, (MAX_DEFINITION, MAX_MOTION)):
            raw = _read(out, spec['staged_file'], maximum)
            if _sha(raw) != spec['sha256']:
                _fail('Staged neutral rig bytes differ from the pinned source hash')
            raw_files[spec['staged_file']] = raw
        raw_files['rig.json'] = _read(out, 'rig.json', 110_000)
        if digest(_json(raw_files['rig.json'])) != rig_sha:
            _fail('Staged neutral rig specification changed')
        for relative in ('render-engine.json', 'qa.json'):
            if delivery or _exists(out, relative):
                raw_files[relative] = _read(out, relative, MAX_METADATA)
                _binding(_json(raw_files[relative]), rig_sha, definition_sha)
        if delivery or _exists(out, 'edit-plan.json'):
            raw_files['edit-plan.json'] = _read(out, 'edit-plan.json', MAX_METADATA)
            if canonical(_json(raw_files['edit-plan.json'])) != canonical(plan):
                _fail('Staged neutral rig edit plan changed')
        if not delivery:
            return
        manifest_raw = _read(out, 'delivery.json', MAX_METADATA)
        manifest = _json(manifest_raw)
        _binding(manifest, rig_sha, definition_sha)
        files = manifest.get('files')
        if not isinstance(files, dict) or not 1 <= len(files) <= 500 or 'delivery.json' in files:
            _fail('Neutral rig delivery file manifest is missing or invalid')
        for relative, sha in files.items():
            _relative(relative)
            if not isinstance(sha, str) or not re.fullmatch('[a-f0-9]{64}', sha):
                _fail('Neutral rig delivery file manifest contains an invalid hash')
        for relative, raw in raw_files.items():
            if files.get(relative) != _sha(raw):
                _fail('Neutral rig delivery member hash differs from its pinned bytes')
        with _regular(out, 'delivery.zip', MAX_ARCHIVE) as stream, zipfile.ZipFile(stream) as archive:
            infos = archive.infolist()
            names = [item.filename for item in infos]
            if len(names) != len(set(names)) or set(names) != set(files) | {'delivery.json'}:
                _fail('Neutral rig delivery ZIP has missing, duplicate or unexpected members')
            for info in infos:
                _relative(info.filename)
                if info.is_dir() or stat.S_IFMT(info.external_attr >> 16) not in {0, stat.S_IFREG}:
                    _fail('Neutral rig delivery ZIP members must be ordinary files')
            for relative, raw in {**raw_files, 'delivery.json': manifest_raw}.items():
                info = archive.getinfo(relative)
                if info.file_size != len(raw) or archive.read(info) != raw:
                    _fail('Packaged neutral rig bytes differ from the pinned delivery member')
    except _IO_ERRORS:
        raise WorkflowError('Neutral rig plan/staging/receipt/QA/delivery missing or malformed') from None
