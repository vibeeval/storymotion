"""Prevalidate a source ZIP completely, then create a new confined extraction."""
import os
import re
import stat
import unicodedata
import zipfile
import zlib
import errno
from pathlib import Path

from .security import WorkflowError

MAX_MEMBERS = 5000
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 128 * 1024 * 1024


def _fail():
    raise WorkflowError('UNSAFE_SOURCE_ARCHIVE')


def _members(archive):
    infos = archive.infolist()
    if len(infos) > MAX_MEMBERS:
        _fail()
    seen, files, rows, total = set(), set(), [], 0
    prefixes = {}
    for info in infos:
        name = info.orig_filename
        if (name != info.filename or not name or '\x00' in name or '\\' in name or name.startswith('/')
                or re.search(r'[\x00-\x1f\x7f:]', name) or info.flag_bits & 1):
            _fail()
        directory = info.is_dir()
        parts = (name[:-1] if directory else name).split('/')
        if os.name=='nt':
            from .windows_native import component
            for part in parts:component(part)
        if any(part in ('', '.', '..') for part in parts):
            _fail()
        for length in range(1,len(parts)+1):
            canonical='/'.join(unicodedata.normalize('NFC', part).casefold() for part in parts[:length])
            spelling='/'.join(parts[:length])
            if canonical in prefixes and prefixes[canonical]!=spelling:_fail()
            prefixes[canonical]=spelling
        key = '/'.join(unicodedata.normalize('NFC', part).casefold() for part in parts)
        if key in seen:
            _fail()
        seen.add(key)
        mode = info.external_attr >> 16
        kind = stat.S_IFMT(mode)
        if kind not in (0, stat.S_IFDIR if directory else stat.S_IFREG):
            _fail()
        if info.file_size > MAX_FILE_BYTES or info.file_size < 0:
            _fail()
        total += info.file_size
        if total > MAX_TOTAL_BYTES:
            _fail()
        if not directory:files.add(key)
        rows.append((info, parts, directory, key))
    for _, parts, _, key in rows:
        if any('/'.join(key.split('/')[:n]) in files for n in range(1, len(parts))):
            _fail()
    # Verify decompression and CRC before any destination directory is created.
    result = []
    for info, parts, directory, _ in rows:
        raw = b'' if directory else archive.read(info)
        if len(raw) != info.file_size:
            _fail()
        result.append((parts, directory, raw, (info.external_attr >> 16) & 0o100))
    return result


def _open_directories(root, parts):
    descriptor = os.dup(root)
    try:
        for part in parts:
            try:os.mkdir(part, 0o700, dir_fd=descriptor)
            except FileExistsError:pass
            try:child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            except OSError as error:
                if error.errno in (errno.ELOOP,errno.ENOTDIR):raise WorkflowError('ZIP_TARGET_SYMLINK') from None
                raise
            os.close(descriptor); descriptor = child
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def safe_extract_zip(archive_path, destination, *, scope):
    scope = Path(scope).resolve()
    destination = Path(destination)
    if not destination.is_absolute():destination = scope / destination
    if '..' in destination.parts:
        _fail()
    try:relative = destination.relative_to(scope).parts
    except ValueError:_fail()
    if not relative:
        _fail()
    # No write, including parent mkdir, happens before full member validation.
    try:
        with zipfile.ZipFile(archive_path) as archive:rows = _members(archive)
    except (zipfile.BadZipFile, zipfile.LargeZipFile, RuntimeError, UnicodeError, ValueError, EOFError, zlib.error, NotImplementedError):
        _fail()
    if os.name=='nt':
        from .windows_native import extract
        return extract(rows,destination,scope)
    root = os.open(scope, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    parent = None
    target = None
    try:
        parent = _open_directories(root, relative[:-1])
        # Exclusive mkdir preserves existing user work, including empty targets.
        try:os.mkdir(relative[-1], 0o700, dir_fd=parent)
        except FileExistsError:raise WorkflowError('CLEAN_INSTALL_TARGET_EXISTS') from None
        target = os.open(relative[-1], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
        for parts, directory, raw, executable in rows:
            container = _open_directories(target, parts if directory else parts[:-1])
            try:
                if not directory:
                    fd = os.open(parts[-1], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600 | executable, dir_fd=container)
                    with os.fdopen(fd, 'wb') as stream:
                        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
                os.fsync(container)
            finally:os.close(container)
        os.fsync(target)
    finally:
        if target is not None:os.close(target)
        if parent is not None:os.close(parent)
        os.close(root)
    return destination
