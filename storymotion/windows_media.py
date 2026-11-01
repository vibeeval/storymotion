"""Pinned Windows x64 media download, separate from the macOS source recipe."""
import hashlib
import json
import os
from pathlib import Path
import ssl
import stat
import subprocess
import urllib.request
import uuid
import zipfile

from .security import WorkflowError, file_hash, write_json
from .windows_native import component, inspect, mkdir, open_fd, write, launch, close_job

VERSION='9.0.2'
URL='https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-9.0.2-essentials_build.zip'
SHA='60f467265b1e312373dbcd92200c2618a74850f98d3d078e94296bb3fa2047ba'
BASE='.runtime/windows-media'
MAX_DOWNLOAD=160*1024*1024


def recipe(root):
    path=Path(root)/'renderers/windows-media.json';inspect(path,missing=False)
    value=json.loads(path.read_text(encoding='utf-8'))
    if (value.get('schema_version')!=1 or value.get('version')!=VERSION or value.get('archive_url')!=URL
            or value.get('archive_sha256')!=SHA or value.get('platform')!='win32' or value.get('architecture')!='x64'
            or value.get('license')!='GPL-3.0-or-later' or value.get('binary_redistributed') is not False):
        raise WorkflowError('WINDOWS_MEDIA_RECIPE_INVALID')
    return value


def status(root):
    root=Path(root);recipe(root)
    try:
        receipt=root/BASE/'receipt.json';inspect(receipt,private=True,missing=False)
        value=json.loads(receipt.read_text(encoding='utf-8'))
        if (value.get('schema_version')!=1 or value.get('platform')!='win32' or value.get('architecture')!='x64'
                or value.get('version')!=VERSION or value.get('archive_sha256')!=SHA
                or value.get('recipe_sha256')!=file_hash(root/'renderers/windows-media.json')):raise ValueError()
        archive=root/BASE/'source.zip';inspect(archive,private=True,missing=False)
        expected=archive_hashes(archive)
        binaries=value.get('binaries')
        if not isinstance(binaries,dict) or set(binaries)!={'ffmpeg','ffprobe'}:raise ValueError()
        for name,digest in binaries.items():
            target=root/BASE/(name+'.exe');inspect(target,private=True,missing=False)
            if digest!=expected[name] or file_hash(target)!=expected[name]:raise ValueError()
        license_path=root/BASE/'LICENSE.txt';inspect(license_path,private=True,missing=False)
        if value.get('license_sha256')!=expected['license'] or file_hash(license_path)!=expected['license']:raise ValueError()
        return {'ready':True,'binary':str(root/BASE/'ffprobe.exe'),'ffmpeg':str(root/BASE/'ffmpeg.exe'),
                'path':BASE+'/ffprobe.exe','version':VERSION,'native_acceptance':'unverified'}
    except (OSError,ValueError,TypeError,KeyError,WorkflowError,zipfile.BadZipFile):
        return {'ready':False,'reason':'WINDOWS_MEDIA_NOT_READY','version':VERSION}


class NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise WorkflowError('WINDOWS_MEDIA_REDIRECT_REFUSED')


def payload(archive):
    archive=Path(archive)
    if os.name=='nt':
        from .windows_native import regular
        opened=regular(archive.parent,archive.name,MAX_DOWNLOAD,private=True)
    else:opened=archive.open('rb')
    with opened as stream:
        before=os.fstat(stream.fileno())
        if before.st_size>MAX_DOWNLOAD:raise WorkflowError('WINDOWS_MEDIA_DOWNLOAD_BOUND')
        digest=hashlib.sha256()
        for chunk in iter(lambda:stream.read(512*1024),b''):digest.update(chunk)
        if digest.hexdigest()!=SHA:raise WorkflowError('WINDOWS_MEDIA_HASH_MISMATCH')
        stream.seek(0)
        with zipfile.ZipFile(stream) as z:
            selected=_selected_payload(z)
        after=os.fstat(stream.fileno())
        if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns):
            raise WorkflowError('WINDOWS_MEDIA_ARCHIVE_CHANGED')
        return selected


def _selected_payload(z):
    rows=z.infolist();seen=set();total=0;selected={}
    if not 1<=len(rows)<=1000:raise WorkflowError('WINDOWS_MEDIA_ARCHIVE_INVALID')
    for row in rows:
        parts=row.filename.rstrip('/').split('/')
        for part in parts:component(part)
        folded=row.filename.rstrip('/').casefold();total+=row.file_size
        kind=stat.S_IFMT(row.external_attr>>16)
        if (folded in seen or row.flag_bits&1 or kind not in (0,stat.S_IFDIR if row.is_dir() else stat.S_IFREG)
                or row.file_size<0 or row.file_size>256*1024*1024 or total>1024*1024*1024):
            raise WorkflowError('WINDOWS_MEDIA_ARCHIVE_INVALID')
        seen.add(folded)
        if row.is_dir():continue
        name=parts[-1].lower()
        key=name[:-4] if name in {'ffmpeg.exe','ffprobe.exe'} and len(parts)==3 and parts[1]=='bin' else 'license' if len(parts)==2 and name in {'license','license.txt'} else None
        if key:
            if key in selected:raise WorkflowError('WINDOWS_MEDIA_ARCHIVE_INVALID')
            selected[key]=z.read(row)
    if set(selected)!={'ffmpeg','ffprobe','license'}:raise WorkflowError('WINDOWS_MEDIA_ARCHIVE_INVALID')
    for name in ('ffmpeg','ffprobe'):
        raw=selected[name]
        offset=int.from_bytes(raw[60:64],'little') if len(raw)>64 else 0
        if raw[:2]!=b'MZ' or not 64<=offset<len(raw)-6 or raw[offset:offset+6]!=b'PE\0\0d\x86':
            raise WorkflowError('WINDOWS_X64_MEDIA_REQUIRED')
    return selected


def archive_hashes(archive):
    """Expected installed bytes derive only from the pinned archive, never a receipt."""
    return {name:hashlib.sha256(raw).hexdigest() for name,raw in payload(archive).items()}


def install(root,allow_downloads=False):
    root=Path(root);current=status(root)
    if current['ready']:return dict(current,action='reuse_windows_media',network=False)
    if allow_downloads is not True:raise WorkflowError('PROBE_DOWNLOAD_PERMISSION_REQUIRED')
    folder=root/BASE;mkdir(folder);archive=folder/'source.zip'
    if archive.exists():
        inspect(archive,private=True,missing=False)
        if file_hash(archive)!=SHA:raise WorkflowError('WINDOWS_MEDIA_EXISTING_ARCHIVE_INVALID')
    else:
        temporary=folder/('download-'+uuid.uuid4().hex+'.zip')
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirects(),urllib.request.HTTPSHandler(context=ssl.create_default_context()))
        with opener.open(URL,timeout=40) as response:
            fd=open_fd(temporary,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
            with os.fdopen(fd,'wb') as out:
                total=0
                while True:
                    chunk=response.read(512*1024)
                    if not chunk:break
                    total+=len(chunk)
                    if total>MAX_DOWNLOAD:raise WorkflowError('WINDOWS_MEDIA_DOWNLOAD_BOUND')
                    out.write(chunk)
                out.flush();os.fsync(out.fileno())
        if file_hash(temporary)!=SHA:raise WorkflowError('WINDOWS_MEDIA_HASH_MISMATCH')
        # Windows rename fails if destination exists; no clobber or retry.
        os.rename(temporary,archive)
    data=payload(archive)
    for name in ('ffmpeg','ffprobe'):write(folder/(name+'.exe'),data[name])
    write(folder/'LICENSE.txt',data['license'])
    from .runtime import process_env
    for name in ('ffmpeg','ffprobe'):
        proc=launch([str(folder/(name+'.exe')),'-version'],env=process_env(),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            stdout,_=proc.communicate(timeout=20)
            if proc.returncode or VERSION.encode() not in stdout[:512]:raise WorkflowError('WINDOWS_MEDIA_VERSION_MISMATCH')
        finally:close_job(proc,terminate=proc.poll() is None)
    write_json(folder/'receipt.json',{'schema_version':1,'platform':'win32','architecture':'x64','version':VERSION,
        'archive_sha256':SHA,'recipe_sha256':file_hash(root/'renderers/windows-media.json'),
        'binaries':{name:hashlib.sha256(data[name]).hexdigest() for name in ('ffmpeg','ffprobe')},
        'license_sha256':hashlib.sha256(data['license']).hexdigest()})
    return dict(status(root),action='installed_windows_media',network=True)
