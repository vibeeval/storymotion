"""Protected template intake receipts, distinct from generic Engine records.

Only TemplateStudio's post-clean prepare path writes these runtime records.
There is no caller-supplied attestation flag, signing credential or CLI minting
operation. An OS owner rewriting application/receipt bytes is outside this
local trust boundary; merely using the supported Engine CLI is not.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import stat

from .local_state import guard_control, validate_open_control
from .security import WorkflowError, digest, write_json

SHA = re.compile(r'[a-f0-9]{64}')
FIELDS = {'schema_version', 'kind', 'intake', 'job', 'account', 'family', 'engine',
          'payload_sha256', 'brief_sha256', 'input_sha256', 'manifest_sha256', 'execution_fingerprint'}


def unavailable():
    raise WorkflowError('FAMILY_INTAKE_RECEIPT_REQUIRED: preparation has no matching protected intake receipt; prepare again through the authenticated template panel. Existing artifacts were not cleaned or cleared.')


def _paths(root, job):
    if not isinstance(job, str) or not re.fullmatch(r'[a-f0-9]{24}', job):unavailable()
    folder = guard_control(root, 'family-receipts', 'dir')
    path = guard_control(root, 'family-receipts/' + job + '.json')
    if os.name=='nt':
        from .windows_native import inspect
        inspect(folder,'dir',private=True);inspect(path,private=True)
        return folder,path
    if folder.exists() and stat.S_IMODE(folder.stat().st_mode) != 0o700:unavailable()
    if path.exists() and stat.S_IMODE(path.stat().st_mode) != 0o600:unavailable()
    return folder, path


def common(job, payload):
    brief = payload['brief']
    return {'schema_version': 1, 'kind': 'family_preparation', 'intake': 'dashboard_clean_raw_and_normalized_v1',
            'job': job, 'account': brief['brand'], 'family': brief['template_family']['id'],
            'engine': payload['render_engine'], 'payload_sha256': digest(payload), 'brief_sha256': digest(brief),
            'execution_fingerprint': payload['execution']['fingerprint']}


def read_receipt(root, job):
    folder, path = _paths(root, job)
    if os.name=='nt':
        from .windows_native import read
        raw=read(root,path.relative_to(root),8192,private=True)
        def pairs(rows):
            value={}
            for key,item in rows:
                if key in value:unavailable()
                value[key]=item
            return value
        try:value=json.loads(raw,object_pairs_hook=pairs)
        except (ValueError,UnicodeError,RecursionError):unavailable()
        if not isinstance(value,dict) or set(value)!=FIELDS or type(value['schema_version']) is not int:unavailable()
        return value
    directory = None;descriptor = None
    try:
        directory = os.open(folder, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        info = os.fstat(directory)
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:unavailable()
        descriptor = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        before = validate_open_control(descriptor)
        if stat.S_IMODE(before.st_mode) != 0o600 or not 0 < before.st_size <= 8192:unavailable()
        raw = b''
        while len(raw) <= 8192:
            chunk = os.read(descriptor, 8193-len(raw))
            if not chunk:break
            raw += chunk
        signature = lambda s:(s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_nlink)
        after = os.fstat(descriptor);current = os.stat(path.name, dir_fd=directory, follow_symlinks=False)
        if len(raw)>8192 or signature(before)!=signature(after) or signature(after)!=signature(current):unavailable()
        def pairs(rows):
            value = {}
            for key,item in rows:
                if key in value:unavailable()
                value[key] = item
            return value
        value = json.loads(raw, object_pairs_hook=pairs)
        if not isinstance(value,dict) or set(value)!=FIELDS or type(value['schema_version']) is not int:unavailable()
        return value
    except (OSError, ValueError, TypeError, UnicodeError, RecursionError):
        unavailable()
    finally:
        try:
            if descriptor is not None:os.close(descriptor)
        finally:
            if directory is not None:os.close(directory)


def check_receipt(root, job, payload, *, source=None, manifest=None):
    value = read_receipt(root, job)
    if any(value.get(key)!=expected for key,expected in common(job,payload).items()):unavailable()
    if any(not isinstance(value[key],str) or not SHA.fullmatch(value[key]) for key in ('input_sha256','manifest_sha256')):unavailable()
    if source is not None and value['input_sha256']!=hashlib.sha256(source).hexdigest():unavailable()
    if manifest is not None and value['manifest_sha256']!=digest(manifest):unavailable()
    return value


def record_receipt(root, job, payload, source, manifest):
    """Call only after raw/normalized clean and verified Engine prepare, locked."""
    folder,path = _paths(root,job)
    value = {**common(job,payload), 'input_sha256':hashlib.sha256(source).hexdigest(), 'manifest_sha256':digest(manifest)}
    if path.exists():
        if read_receipt(root,job)!=value:unavailable()
        return
    folder.mkdir(mode=0o700,exist_ok=True)
    _paths(root,job)
    write_json(path,value)
    if check_receipt(root,job,payload,source=source,manifest=manifest)!=value:unavailable()
