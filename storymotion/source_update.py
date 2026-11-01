"""Stage or verify a selected source archive, never overwrite an installation."""
import hashlib
import io
import json
import os
import re
import zipfile
import zlib
from pathlib import Path

from .archive_safety import _members, safe_extract_zip
from .local_state import guard_control
from .platform_support import require_platform
from .install_policy import source_distribution
from .security import WorkflowError

ROOT=Path(__file__).resolve().parents[1]
MAX_ZIP_BYTES=136*1024*1024
MUTABLE={'.git','.runtime','node_modules','work','.env','.local-tools.json'}
CODE_FOLDERS={'storymotion','dashboard','catalog','fixtures','renderers','knowledge','vendor','accountpacks','tools','docs'}
OPTIONAL_SOURCE_FILES={'optional/remotion/package.json','optional/remotion/package-lock.json'}


def _fail(code='UPDATE_SOURCE_INVALID'):raise WorkflowError(code)


def _pairs(rows):
    value={}
    for key,item in rows:
        if key in value:raise ValueError('Duplicate JSON key')
        value[key]=item
    return value


def _invalid_constant(_):raise ValueError('Invalid JSON constant')


def _relative(name):
    if (not isinstance(name,str) or len(name)>512 or '\\' in name or ':' in name
            or re.search(r'[\x00-\x1f\x7f]',name) or any(p in ('','.','..') for p in name.split('/'))):_fail()
    parts=name.split('/')
    folded=[p.casefold() for p in parts]
    if (any(p in MUTABLE for p in folded) or (len(parts)>1 and parts[0] not in CODE_FOLDERS and name not in OPTIONAL_SOURCE_FILES)
            or any(re.search(r'\.(?:key|pem|sqlite3|db)(?:-(?:wal|shm|journal))?$',p) for p in folded)
            or any(p.startswith('.env.') and p!='.env.example' for p in folded)):_fail()
    return name


def _source(archive,expected_sha256):
    if not isinstance(expected_sha256,str) or not re.fullmatch('[a-fA-F0-9]{64}',expected_sha256):_fail('UPDATE_SHA256_REQUIRED')
    with Path(archive).open('rb') as stream:raw=stream.read(MAX_ZIP_BYTES+1)
    if len(raw)>MAX_ZIP_BYTES:_fail('UPDATE_ARCHIVE_TOO_LARGE')
    if hashlib.sha256(raw).hexdigest()!=expected_sha256.lower():_fail('UPDATE_ARCHIVE_SHA_MISMATCH')
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as opened:rows=_members(opened)
        files={'/'.join(parts):data for parts,directory,data,_ in rows if not directory}
        manifests=[name for name in files if name.endswith('/SOURCE-MANIFEST.json') and name.count('/')==1]
        if len(manifests)!=1:_fail()
        manifest_name=manifests[0];prefix=manifest_name.split('/')[0]
        if not re.fullmatch(r'storymotion-\d+\.\d+\.\d+',prefix):_fail()
        if len(files[manifest_name])>512*1024:_fail()
        manifest=json.loads(files[manifest_name],object_pairs_hook=_pairs,parse_constant=_invalid_constant);version=prefix[len('storymotion-'):]
        if (not isinstance(manifest,dict) or manifest.get('version')!=version
                or not (source_distribution(manifest) or (manifest.get('customer_release_ready') is True
                        and manifest.get('rights_pending') is False))):_fail('UPDATE_RELEASE_BLOCKED')
        hashes=manifest.get('files')
        if not isinstance(hashes,dict) or not 1<=len(hashes)<=5000:_fail()
        expected={manifest_name}
        for name,digest in hashes.items():
            _relative(name)
            if name=='SOURCE-MANIFEST.json' or not isinstance(digest,str) or not re.fullmatch('[a-f0-9]{64}',digest):_fail()
            full=prefix+'/'+name;expected.add(full)
            if full not in files or hashlib.sha256(files[full]).hexdigest()!=digest:_fail('UPDATE_SOURCE_HASH_MISMATCH')
        if set(files)!=expected or any(parts[0]!=prefix for parts,_,_,_ in rows):_fail()
        directories={prefix}
        for name in expected:
            parts=name.split('/');directories.update('/'.join(parts[:i]) for i in range(1,len(parts)))
        if any(directory and '/'.join(parts) not in directories for parts,directory,_,_ in rows):_fail()
        for required in ('LICENSE','THIRD-PARTY-NOTICES.md','package.json','package-lock.json'):
            if required not in hashes:_fail()
        license_text=files[prefix+'/LICENSE'].decode('utf-8')
        if not license_text.strip() or re.search(r'(?i)\bTODO\b|placeholder|no commercial license grant',license_text):_fail('OWNER_EULA_PENDING')
        package=json.loads(files[prefix+'/package.json'],object_pairs_hook=_pairs,parse_constant=_invalid_constant)
        if not isinstance(package,dict) or package.get('name')!='storymotion' or package.get('version')!=version:_fail()
    except (zipfile.BadZipFile,zipfile.LargeZipFile,RuntimeError,ValueError,RecursionError,UnicodeError,EOFError,zlib.error,NotImplementedError):
        _fail()
    return raw,prefix,files


def _target(destination,active_root,protected_workspaces):
    require_platform()
    value=Path(destination)
    if '..' in value.parts:_fail('UPDATE_TARGET_INVALID')
    if not value.is_absolute():value=Path.cwd()/value
    parent=value.parent
    if not parent.is_dir() or parent.absolute()!=parent.resolve():_fail('UPDATE_TARGET_INVALID')
    target=parent/value.name;active=Path(active_root).resolve()
    if target.is_relative_to(active) or active.is_relative_to(target):_fail('UPDATE_TARGET_OVERLAPS_ACTIVE_SOURCE')
    for workspace in protected_workspaces:
        protected=Path(workspace).resolve()
        if not protected.is_dir():_fail('UPDATE_PROTECTED_WORKSPACE_INVALID')
        if target.is_relative_to(protected) or protected.is_relative_to(target):_fail('UPDATE_TARGET_OVERLAPS_WORKSPACE')
    guard_control(parent,value.name,'dir')
    return parent,target


def stage_update(archive,destination,expected_sha256,*,active_root=ROOT,protected_workspaces=()):
    parent,target=_target(destination,active_root,protected_workspaces)
    if target.exists():_fail('UPDATE_TARGET_EXISTS: inspect or verify the existing outcome; it was not changed')
    raw,prefix,files=_source(archive,expected_sha256)
    try:safe_extract_zip(io.BytesIO(raw),target,scope=parent)
    except (OSError,WorkflowError):
        raise WorkflowError('UPDATE_STAGING_INCOMPLETE: old installation/work unchanged; inspect the new target before retry; no cleanup or overwrite was attempted') from None
    return {'ok':True,'status':'staged_no_execution','source_directory':str(target/prefix),
            'archive_sha256':expected_sha256.lower(),'files_verified':len(files),
            'downloads':False,'provider_calls':0,'eula_accepted':False,'old_source_or_work_modified':False,
            'next':'Read the new source EULA, then run its preflight explicitly. Staging does not accept terms or launch a process.'}


def verify_update(archive,destination,expected_sha256,*,active_root=ROOT,protected_workspaces=()):
    _,target=_target(destination,active_root,protected_workspaces)
    _,prefix,files=_source(archive,expected_sha256)
    if not target.is_dir():_fail('UPDATE_TARGET_MISSING')
    for name,raw in files.items():
        path=guard_control(target,name)
        if not path.is_file() or path.stat().st_size!=len(raw) or path.read_bytes()!=raw:_fail('UPDATE_TARGET_INCOMPLETE_OR_CHANGED')
    expected=set(files);directories=set()
    for name in expected:
        parts=name.split('/')
        directories.update('/'.join(parts[:i]) for i in range(1,len(parts)))
    pending=[target]
    while pending:
        directory=pending.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                relative=Path(entry.path).relative_to(target).as_posix();parts=relative.split('/')
                if (len(parts)>=2 and parts[0]==prefix and parts[1].casefold() in MUTABLE
                        or parts==[prefix,'optional','remotion','node_modules']):continue
                if relative not in expected and relative not in directories:_fail('UPDATE_TARGET_EXTRA_SOURCE')
                guard_control(target,relative,'dir' if relative in directories else 'file')
                if relative in directories:pending.append(Path(entry.path))
    return {'ok':True,'status':'existing_source_verified_no_changes','source_directory':str(target/prefix),
            'archive_sha256':expected_sha256.lower(),'files_verified':len(files),'downloads':False,
            'provider_calls':0,'eula_accepted':False,'old_source_or_work_modified':False,
            'verification_scope':'manifested source only; generated work and runtime not inspected'}
