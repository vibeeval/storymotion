"""Bounded local raster ingress. Raw customer files never become executable assets."""
import hashlib
import json
import os
import re
import stat
import struct
import zlib
from pathlib import Path

from .security import WorkflowError

MAX_BYTES = 8 * 1024 * 1024
MIN_DIMENSION = 64
MAX_DIMENSION = 4096
MAX_PIXELS = 12_000_000
PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'
ROOT = Path(__file__).resolve().parents[1]


def _fail():
    raise WorkflowError('Invalid raster: use one complete PNG/JPEG within the documented size and pixel limits')


def _bounds(width, height):
    if (type(width) is not int or type(height) is not int or
            not MIN_DIMENSION <= width <= MAX_DIMENSION or
            not MIN_DIMENSION <= height <= MAX_DIMENSION or width * height > MAX_PIXELS):
        _fail()


def _png_pixels(idat, width, height, depth, colour, interlace):
    # Header limits have already been enforced. Exact inflated byte counts also
    # reject hidden trailing deflate members/data that permissive decoders ignore.
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[colour]
    passes = [(0, 0, 1, 1)] if not interlace else [
        (0, 0, 8, 8), (4, 0, 8, 8), (0, 4, 4, 8), (2, 0, 4, 4),
        (0, 2, 2, 4), (1, 0, 2, 2), (0, 1, 1, 2)]
    rows = []
    for x, y, dx, dy in passes:
        w, h = max(0, (width - x + dx - 1) // dx), max(0, (height - y + dy - 1) // dy)
        if w and h:
            rows.extend([1 + (w * channels * depth + 7) // 8] * h)
    expected = sum(rows)
    try:
        decoder = zlib.decompressobj()
        pixels = decoder.decompress(b''.join(idat), expected + 1)
    except zlib.error:
        _fail()
    if len(pixels) != expected or not decoder.eof or decoder.unconsumed_tail or decoder.unused_data:
        _fail()
    offset = 0
    for stride in rows:
        if pixels[offset] > 4:
            _fail()
        offset += stride


def _png(data, normalized=False):
    if not data.startswith(PNG_SIGNATURE):
        _fail()
    offset, chunks, seen, idat, ended_idat = 8, 0, [], [], False
    width = height = depth = colour = interlace = None
    while offset < len(data):
        if offset + 12 > len(data) or chunks >= 4096:
            _fail()
        size = struct.unpack_from('>I', data, offset)[0]
        kind = data[offset + 4:offset + 8]
        end = offset + 12 + size
        if end > len(data) or not re.fullmatch(b'[A-Za-z]{4}', kind) or kind[2] & 32:
            _fail()
        payload = data[offset + 8:offset + 8 + size]
        crc = struct.unpack_from('>I', data, offset + 8 + size)[0]
        if zlib.crc32(kind + payload) & 0xffffffff != crc:
            _fail()
        if chunks == 0 and kind != b'IHDR':
            _fail()
        if kind in {b'acTL', b'fcTL', b'fdAT'}:
            _fail()
        if normalized and kind not in {b'IHDR', b'IDAT', b'IEND', b'pHYs'}:
            _fail()
        if not kind[0] & 32 and kind not in {b'IHDR', b'PLTE', b'IDAT', b'IEND'}:
            _fail()
        if kind == b'IHDR':
            if seen or size != 13:
                _fail()
            width, height, depth, colour, compression, filtering, interlace = struct.unpack('>IIBBBBB', payload)
            _bounds(width, height)
            legal = {0: {1, 2, 4, 8, 16}, 2: {8, 16}, 3: {1, 2, 4, 8}, 4: {8, 16}, 6: {8, 16}}
            if depth not in legal.get(colour, set()) or compression or filtering or interlace not in {0, 1}:
                _fail()
            if normalized and (depth, colour, interlace) != (8, 6, 0):
                _fail()
        elif kind == b'PLTE':
            if b'PLTE' in seen or idat or colour in {0, 4} or not size or size > 768 or size % 3:
                _fail()
            if colour == 3 and size // 3 > 2 ** depth:
                _fail()
        elif kind == b'IDAT':
            if ended_idat or (colour == 3 and b'PLTE' not in seen):
                _fail()
            idat.append(payload)
        elif kind == b'IEND':
            if size or not idat or end != len(data):
                _fail()
            _png_pixels(idat, width, height, depth, colour, interlace)
            return width, height
        else:
            if idat:
                ended_idat = True
            if kind == b'pHYs' and (size != 9 or payload[8] not in {0, 1} or b'pHYs' in seen or idat):
                _fail()
            if kind == b'tRNS' and (idat or b'tRNS' in seen or colour not in {0, 2, 3} or
                                    (colour == 0 and size != 2) or (colour == 2 and size != 6) or
                                    (colour == 3 and (b'PLTE' not in seen or not size))):
                _fail()
        seen.append(kind)
        chunks += 1
        offset = end
    _fail()


def _jpeg(data):
    if not data.startswith(b'\xff\xd8'):
        _fail()
    offset, frame, scans, entropy = 2, None, 0, False
    while offset < len(data):
        if entropy:
            # Entropy bytes may escape FF as FF00 or contain restart markers.
            while offset < len(data):
                if data[offset] != 255:
                    offset += 1
                    continue
                start = offset
                while offset < len(data) and data[offset] == 255:
                    offset += 1
                if offset == len(data):
                    _fail()
                code = data[offset]
                if code == 0 or 0xd0 <= code <= 0xd7:
                    offset += 1
                    continue
                offset, entropy = start, False
                break
        if offset + 2 > len(data) or data[offset] != 255:
            _fail()
        while offset < len(data) and data[offset] == 255:
            offset += 1
        if offset == len(data):
            _fail()
        marker = data[offset]
        offset += 1
        if marker == 0xd9:
            if offset != len(data) or frame is None or not scans:
                _fail()
            return frame
        if marker in {0, 1, 0xd8} or 0xd0 <= marker <= 0xd7:
            _fail()
        if offset + 2 > len(data):
            _fail()
        size = struct.unpack_from('>H', data, offset)[0]
        if size < 2 or offset + size > len(data):
            _fail()
        payload = data[offset + 2:offset + size]
        offset += size
        if marker in {0xc0, 0xc1, 0xc2}:
            if frame is not None or len(payload) < 6:
                _fail()
            precision, height, width, channels = struct.unpack_from('>BHHB', payload)
            _bounds(width, height)
            if precision != 8 or channels not in {1, 3, 4} or len(payload) != 6 + channels * 3:
                _fail()
            frame = (width, height)
        elif 0xc0 <= marker <= 0xcf and marker not in {0xc4, 0xc8, 0xcc}:
            _fail()
        elif marker in {0xc8, 0xcc, 0xdc, 0xde, 0xdf}:
            _fail()
        elif marker == 0xda:
            if frame is None or not payload or payload[0] not in {1, 2, 3, 4} or len(payload) != 4 + payload[0] * 2:
                _fail()
            scans += 1
            entropy = True
        elif marker == 0xe2 and payload.startswith(b'MPF\0'):
            _fail()
        elif marker not in {0xc4, 0xdb, 0xdd, 0xfe, *range(0xe0, 0xf0)}:
            _fail()
    _fail()


def _parse(data, container, normalized=False):
    if type(data) is not bytes or not data or len(data) > MAX_BYTES:
        _fail()
    if container == 'png':
        return _png(data, normalized)
    if container == 'jpeg' and not normalized:
        return _jpeg(data)
    _fail()


def _physical(path, directory=False):
    """Do not resolve aliases: reject symlinks in the supplied lexical path."""
    try:
        if '..' in Path(path).parts:
            _fail()
        p = Path(os.path.abspath(path))
        for component in [*reversed(p.parents), p]:
            if stat.S_ISLNK(component.lstat().st_mode):
                _fail()
        mode = p.lstat().st_mode
        if not (stat.S_ISDIR(mode) if directory else stat.S_ISREG(mode)):
            _fail()
    except (OSError, ValueError, TypeError):
        _fail()
    if os.name=='nt':
        from .windows_native import inspect
        inspect(p,'dir' if directory else 'file',missing=False)
    return p


def _read_regular(path):
    p = _physical(path)
    if os.name=='nt':
        from .windows_native import read
        return read(p.parent,p.name,MAX_BYTES)
    try:
        flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
        descriptor = os.open(p, flags)
        with os.fdopen(descriptor, 'rb') as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                _fail()
            data = stream.read(MAX_BYTES + 1)
    except OSError:
        _fail()
    _physical(p)
    return data


def validate_normalized(path, sha, width, height):
    """Validate immutable normalized pixels; return non-private asset metadata."""
    _bounds(width, height)
    if type(sha) is not str or not re.fullmatch('[0-9a-f]{64}', sha):
        _fail()
    data = _read_regular(path)
    if _parse(data, 'png', normalized=True) != (width, height) or hashlib.sha256(data).hexdigest() != sha:
        _fail()
    return {'sha256': sha, 'width': width, 'height': height}


def normalize_raster(data: bytes, container: str, directory: Path) -> dict:
    """Decode one selected local image into a stripped bounded RGBA PNG."""
    _parse(data, container)
    folder = _physical(directory, directory=True)
    source = folder / ('selected.png' if container == 'png' else 'selected.jpeg')
    output = folder / 'normalized.png'
    if source.exists() or source.is_symlink() or output.exists() or output.is_symlink():
        _fail()
    created_source = created_output = False
    try:
        with source.open('xb') as stream:
            created_source = True
            if os.name!='nt':os.chmod(source, 0o600)
            stream.write(data)
        # Lazy import avoids an Engine import cycle. checked_process filters the
        # child environment and owns timeout/cancellation of its process group.
        from .engine import checked_process
        result = checked_process(['node', ROOT / 'tools/raster.mjs', 'normalize', source, output], cwd=ROOT, timeout=30)
        created_output = output.exists() or output.is_symlink()
        if len(result) > 1024:
            _fail()
        meta = json.loads(result)
        if type(meta) is not dict or set(meta) != {'width', 'height', 'format'} or meta['format'] != 'png':
            _fail()
        normalized = _read_regular(output)
        sha = hashlib.sha256(normalized).hexdigest()
        validate_normalized(output, sha, meta['width'], meta['height'])
        return {'file': output, 'sha256': sha, 'source_sha256': hashlib.sha256(data).hexdigest(),
                'width': meta['width'], 'height': meta['height']}
    except (OSError, ValueError, TypeError, KeyError, WorkflowError):
        # Do not expose tool diagnostics, raw pixels, paths, or metadata.
        try:
            if created_output or output.exists() or output.is_symlink():
                output.unlink(missing_ok=True)
        except OSError:
            raise WorkflowError('Raster decode failed; temporary output cleanup failed') from None
        raise WorkflowError('Raster decode failed; choose a valid bounded PNG/JPEG and check the local raster tool') from None
    finally:
        if created_source:
            try:
                source.unlink(missing_ok=True)
            except OSError:
                raise WorkflowError('Raster temporary input cleanup failed') from None
