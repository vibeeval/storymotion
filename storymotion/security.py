import hashlib
import json
import math
import os
import tempfile
import re
from pathlib import Path


class WorkflowError(Exception):
    pass


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def within(root, relative):
    p = (Path(root) / relative).resolve()
    if not p.is_relative_to(Path(root).resolve()):
        raise WorkflowError('Path escapes project boundary')
    return p


def write_json(path, value):
    p = Path(path)
    raw = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')
    if os.name=='nt':
        from .windows_native import write
        return write(p,raw)
    p.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix='.' + p.name + '.', suffix='.tmp', dir=p.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, p)
        directory = os.open(p.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:os.fsync(directory)
        finally:os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


PATTERNS = [
    ('google-api-key', re.compile(r'AIza[0-9A-Za-z_-]{35}')),
    ('private-key', re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')),
    ('provider-key', re.compile(r'\b(?:sk-[A-Za-z0-9_-]{20,}|sk_[A-Za-z0-9_-]{24,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16})\b')),
    ('bearer', re.compile(r'(?i)Bearer\s+[A-Za-z0-9._-]{18,}')),
    ('assigned-secret', re.compile(r'''(?i)(?:api[_-]?key|access[_-]?token|secret|password)["']?\s*[:=]\s*["']?([^\s"',;]{10,})''')),
    ('signed-url', re.compile(r'(?i)(?:X-Amz-Signature|X-Goog-Signature|[?&]token=)[A-Za-z0-9%=._-]{8,}')),
]


def scan_bytes(data):
    text = data.decode('utf-8', errors='ignore')
    results = []
    for kind, pattern in PATTERNS:
        for m in pattern.finditer(text):
            if kind == 'assigned-secret' and m.group(1).startswith(('FAKE_', 'EXAMPLE_', 'PLACEHOLDER_')):
                continue
            results.append({'kind': kind, 'line': text.count('\n', 0, m.start()) + 1})
    return results


def scan_tree(root):
    findings = []
    for p in sorted(Path(root).rglob('*')):
        if p.is_symlink():
            findings.append({'file': str(p.relative_to(root)), 'kind': 'symlink'})
        elif p.is_file() and not any(x in {'.git', 'node_modules', '__pycache__', '.hyperframes'} for x in p.parts):
            if p.name == '.env' or p.suffix in {'.pem', '.key'}:
                findings.append({'file': str(p.relative_to(root)), 'kind': 'sensitive-file'})
            if p.suffix not in {'.woff2', '.mp4', '.png', '.jpg', '.wav', '.mp3', '.zip', '.sqlite3'}:
                findings.extend(dict(file=str(p.relative_to(root)), **x) for x in scan_bytes(p.read_bytes()))
    return findings


def finite(value, name, low, high):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not low <= value <= high:
        raise WorkflowError(f'{name} outside allowed range')
    return value
