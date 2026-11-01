"""Pinned independent source-built probe. No global install or binary fallback."""
import hashlib
import json
import os
from pathlib import Path,PurePosixPath
import platform
import re
import shutil
import ssl
import subprocess
import tarfile
import tempfile
import urllib.request
import uuid

from .local_state import guard_control
from .security import WorkflowError,file_hash,write_json

ROOT=Path(__file__).resolve().parents[1]
VERSION='8.1.3'
SOURCE_URL='https://ffmpeg.org/releases/ffmpeg-8.1.3.tar.xz'
SOURCE_SHA='7138d28c96d9d3e3af4ee3d8cad72741f8ffb40da90c1112235dea3ecd3178a3'
LICENSE_SHA='246041b6ecf9bc32d718a62c57877c78b5eb397b6467e74ed7ae2626ab189c30'
SOURCE_LICENSE_SHA='2e1d16c72fd74e12063776371da757322f8b77589386532f4fd8634bde7de1af'
FIXTURES={'fixtures/audio-retime/synthetic-20s.wav':'3a4075165eae03a178af902902dce747dcf642caa4538bca578e0a02a84fa017',
          'fixtures/synthetic-voice-contract.mp3':'2a9bdbda14791cbcf6a0cd772fea4aad7219c5f1f6e669514ef5def1c04ce3f7',
          'fixtures/raster/neutral-shapes.png':'b10a05a310337da64a68826daaf54fe8e1f1d234271e7e0489421c63bbd1df0a'}
FLAGS=('--disable-programs','--enable-ffprobe','--disable-doc','--disable-debug','--disable-autodetect',
       '--disable-network','--disable-gpl','--disable-nonfree','--disable-version3','--disable-shared','--enable-static',
       '--disable-avdevice','--disable-avfilter','--disable-swscale','--disable-swresample','--disable-encoders',
       '--disable-muxers','--disable-hwaccels','--disable-asm','--enable-zlib')


def source_recipe(root=ROOT):
    root=Path(root)
    try:
        path=guard_control(root,'renderers/ffprobe-source.json')
        if path.stat().st_size>32768:raise ValueError()
        value=json.loads(path.read_text())
        if (not isinstance(value,dict) or value.get('version')!=VERSION or value.get('source_url')!=SOURCE_URL
                or value.get('source_sha256')!=SOURCE_SHA or value.get('license')!='LGPL-2.1-or-later'
                or value.get('license_path')!='vendor/licenses/ffmpeg-8.1.3-COPYING.LGPLv2.1'
                or value.get('license_sha256')!=LICENSE_SHA or value.get('configure_flags')!=list(FLAGS)
                or type(value.get('source_date_epoch')) is not int or value['source_date_epoch']!=1789951930
                or value.get('binary_redistributed') is not False):raise ValueError()
        if file_hash(guard_control(root,value['license_path']))!=LICENSE_SHA:raise ValueError()
        if file_hash(guard_control(root,'vendor/licenses/ffmpeg-8.1.3-LICENSE.md'))!=SOURCE_LICENSE_SHA:raise ValueError()
    except (OSError,ValueError,RecursionError,UnicodeError):raise WorkflowError('PROBE_SOURCE_RECIPE_INVALID') from None
    return value


def probe_status(root=ROOT):
    if os.name=='nt':
        from .windows_media import status
        return status(root)
    root=Path(root);source_recipe(root)
    if platform.system()!='Darwin' or platform.machine()!='arm64':
        return {'ready':False,'reason':'PROBE_PLATFORM_UNVERIFIED','version':VERSION}
    binary=guard_control(root,'.runtime/probe/ffprobe');receipt=guard_control(root,'.runtime/probe/receipt.json')
    try:
        if receipt.stat().st_size>65536:raise ValueError()
        value=json.loads(receipt.read_text())
        if (not isinstance(value,dict) or type(value.get('schema_version')) is not int or value['schema_version']!=1
                or value.get('version')!=VERSION or value.get('source_sha256')!=SOURCE_SHA
                or value.get('recipe_sha256')!=file_hash(root/'renderers/ffprobe-source.json')
                or value.get('platform')!=platform.system() or value.get('architecture')!=platform.machine()
                or value.get('binary')!='.runtime/probe/ffprobe' or not binary.is_file() or not os.access(binary,os.X_OK)
                or value.get('binary_sha256')!=file_hash(binary)):raise ValueError()
        archive=value.get('source_archive')
        if not isinstance(archive,str) or not re.fullmatch(r'\.runtime/probe/stages/[a-f0-9]{32}/source\.tar\.xz',archive):raise ValueError()
        if file_hash(guard_control(root,archive))!=SOURCE_SHA:raise ValueError()
        if file_hash(guard_control(root,'.runtime/probe/COPYING.LGPLv2.1'))!=LICENSE_SHA:raise ValueError()
        if file_hash(guard_control(root,'.runtime/probe/LICENSE.md'))!=SOURCE_LICENSE_SHA:raise ValueError()
        return {'ready':True,'binary':str(binary),'version':VERSION,'binary_sha256':value['binary_sha256'],'native_acceptance':'standalone source-built probe only'}
    except (OSError,ValueError,RecursionError,UnicodeError):return {'ready':False,'reason':'INDEPENDENT_PROBE_NOT_READY','version':VERSION}


def toolchain():
    # Only this platform/toolchain has independent native evidence. Other targets
    # stay explicit pending checks instead of being presented as ready.
    if platform.system()!='Darwin' or platform.machine()!='arm64':raise WorkflowError('PROBE_PLATFORM_UNVERIFIED: source build currently verified only on macOS arm64')
    cc=Path('/Library/Developer/CommandLineTools/usr/bin/clang');make=Path('/usr/bin/make')
    sdks=Path('/Library/Developer/CommandLineTools/SDKs')
    for name in ('MacOSX15.4.sdk','MacOSX.sdk'):
        sdk=sdks/name
        if (sdk.is_dir() and sdk.resolve().parent==sdks and (sdk/'usr/lib/libSystem.tbd').is_file()
                and (sdk/'usr/include/zlib.h').is_file() and (sdk/'usr/include/ctype.h').is_file()
                and cc.is_file() and make.is_file()):return {'cc':str(cc),'make':str(make),'sdk':str(sdk)}
    raise WorkflowError('PROBE_TOOLCHAIN_REQUIRED: an installed compiler, make and macOS SDK with zlib headers are required; no OS changes were attempted')


class _NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise WorkflowError('PROBE_SOURCE_REDIRECT_REFUSED')


def download_source(target):
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),_NoRedirects(),urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    try:
        with opener.open(urllib.request.Request(SOURCE_URL,headers={'User-Agent':'StoryMotion-Source-Probe/1'}),timeout=40) as response,target.open('xb') as output:
            total=0
            while True:
                data=response.read(512*1024)
                if not data:break
                total+=len(data)
                if total>32*1024*1024:raise WorkflowError('PROBE_SOURCE_BOUND_EXCEEDED')
                output.write(data)
            output.flush();os.fsync(output.fileno())
    except (OSError,ValueError):raise WorkflowError('PROBE_SOURCE_DOWNLOAD_FAILED') from None
    if file_hash(target)!=SOURCE_SHA:raise WorkflowError('PROBE_SOURCE_HASH_MISMATCH')


def extract_source(archive_path,destination):
    if file_hash(archive_path)!=SOURCE_SHA:raise WorkflowError('PROBE_SOURCE_HASH_MISMATCH')
    with tarfile.open(archive_path,'r:xz') as archive:
        members=list(archive);seen=set();kinds={};total=0
        for member in members:
            path=PurePosixPath(member.name);parts=member.name.rstrip('/').split('/');total+=member.size
            if (path.is_absolute() or re.search(r'[\\:\x00-\x1f\x7f]',member.name) or any(p in {'','.','..'} for p in parts) or parts[0]!='ffmpeg-'+VERSION
                    or not (member.isfile() or member.isdir()) or len(members)>32000
                    or member.size<0 or member.size>64*1024*1024 or total>600*1024*1024 or member.name.rstrip('/').casefold() in seen
                    or len(parts)==1 and not member.isdir()):
                raise WorkflowError('PROBE_SOURCE_ARCHIVE_REFUSED')
            seen.add(member.name.rstrip('/').casefold())
            kinds[member.name.rstrip('/').casefold()]=member.isdir()
        for name in kinds:
            if any(kinds.get(str(parent)) is False for parent in PurePosixPath(name).parents):
                raise WorkflowError('PROBE_SOURCE_ARCHIVE_REFUSED')
        destination.mkdir(mode=0o700)
        for member in members:
            relative=PurePosixPath(member.name).parts[1:]
            if not relative:continue
            target=destination.joinpath(*relative)
            if member.isdir():target.mkdir(parents=True,exist_ok=True,mode=0o700)
            else:
                target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
                with target.open('xb') as out:shutil.copyfileobj(archive.extractfile(member),out)
                target.chmod(0o700 if member.mode&0o111 else 0o600)


def _publish(root,relative,raw,mode=0o600):
    target=guard_control(root,relative);fd,name=tempfile.mkstemp(prefix='.'+target.name+'.',suffix='.tmp',dir=target.parent)
    try:
        with os.fdopen(fd,'wb') as out:out.write(raw);out.flush();os.fchmod(out.fileno(),mode);os.fsync(out.fileno())
        guard_control(root,relative);os.replace(name,target)
        directory=os.open(target.parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(directory)
        finally:os.close(directory)
    finally:Path(name).unlink(missing_ok=True)


def install_probe(root=ROOT,*,allow_downloads=False):
    if os.name=='nt':
        from .windows_media import install
        return install(root,allow_downloads)
    root=Path(root);recipe=source_recipe(root);current=probe_status(root)
    if current['ready']:return dict(current,action='reuse_source_built_probe',network=False)
    if allow_downloads is not True:raise WorkflowError('PROBE_DOWNLOAD_PERMISSION_REQUIRED')
    tools=toolchain()
    try:
        for name,digest in FIXTURES.items():
            if file_hash(guard_control(root,name))!=digest:raise ValueError()
    except (OSError,ValueError):raise WorkflowError('PROBE_FIXTURE_HASH_MISMATCH') from None
    folder=guard_control(root,'.runtime/probe','dir');folder.mkdir(parents=True,exist_ok=True,mode=0o700)
    stages=guard_control(root,'.runtime/probe/stages','dir');stages.mkdir(exist_ok=True,mode=0o700)
    stage=guard_control(root,Path('.runtime/probe/stages')/uuid.uuid4().hex,'dir');stage.mkdir(mode=0o700)
    archive=stage/'source.tar.xz';download_source(archive);extract_source(archive,stage/'source')
    build=stage/'build';build.mkdir(mode=0o700)
    env={k:v for k,v in os.environ.items() if k in {'PATH','HOME','USER','LOGNAME','TMPDIR','TMP','TEMP','LANG','LC_ALL','SHELL'}}
    env.update(DO_NOT_TRACK='1',HYPERFRAMES_TELEMETRY_DISABLED='1',SOURCE_DATE_EPOCH=str(recipe['source_date_epoch']),SDKROOT=tools['sdk'])
    flags=list(FLAGS)+['--cc='+tools['cc'],'--sysroot='+tools['sdk'],'--host-cflags=-isysroot '+tools['sdk'],'--host-ldflags=-isysroot '+tools['sdk']]
    for step,argv,timeout in [('configure',[str(stage/'source/configure'),*flags],300),('make',[tools['make'],'-j2','ffprobe'],900)]:
        try:proc=subprocess.run(argv,cwd=build,env=env,capture_output=True,timeout=timeout)
        except (OSError,subprocess.TimeoutExpired):raise WorkflowError('PROBE_'+step.upper()+'_FAILED') from None
        # Fixed signed source + filtered environment; bounded local diagnostics.
        (stage/(step+'.log')).write_bytes((proc.stdout+proc.stderr)[-65536:]);(stage/(step+'.log')).chmod(0o600)
        if proc.returncode:raise WorkflowError('PROBE_'+step.upper()+'_FAILED')
        if step=='configure':
            try:config=(build/'config.h').read_text()+'\n'+(build/'config_components.h').read_text()
            except (OSError,UnicodeError):raise WorkflowError('PROBE_BUILD_CONFIGURATION_REFUSED') from None
            if any(not re.search(r'^#define CONFIG_'+name+r' 0$',config,re.M) for name in ('GPL','NONFREE','VERSION3','NETWORK')):
                raise WorkflowError('PROBE_BUILD_CONFIGURATION_REFUSED')
            if any(not re.search(r'^#define CONFIG_'+name+r' 1$',config,re.M) for name in ('ZLIB','PNG_DECODER')):
                raise WorkflowError('PROBE_BUILD_CONFIGURATION_REFUSED')
    binary=build/'ffprobe'
    if not binary.is_file() or binary.stat().st_size>64*1024*1024:raise WorkflowError('PROBE_BINARY_REFUSED')
    def run_probe(args):
        try:return subprocess.run([str(binary),*args],env=env,capture_output=True,text=True,timeout=20)
        except (OSError,subprocess.TimeoutExpired,UnicodeError):raise WorkflowError('PROBE_BINARY_VALIDATION_FAILED') from None
    for args,needle in [(['-version'],VERSION),(['-L'],'Lesser General Public License')]:
        proc=run_probe(args)
        if proc.returncode or needle not in proc.stdout:raise WorkflowError('PROBE_BINARY_VALIDATION_FAILED')
    for name,digest in FIXTURES.items():
        if file_hash(guard_control(root,name))!=digest:raise WorkflowError('PROBE_FIXTURE_HASH_MISMATCH')
        proc=run_probe(['-v','error','-show_streams','-of','json',str(root/name)])
        try:
            streams=json.loads(proc.stdout)['streams']
            if not isinstance(streams,list) or not all(isinstance(s,dict) for s in streams):raise ValueError()
            valid=any(s.get('codec_type')=='video' and type(s.get('width')) is int and type(s.get('height')) is int
                      and s['width']>0 and s['height']>0 for s in streams) if name.endswith('.png') else any(
                      s.get('codec_type')=='audio' and re.fullmatch(r'[1-9][0-9]{0,6}',str(s.get('sample_rate',''))) for s in streams)
        except (ValueError,KeyError,TypeError,RecursionError):raise WorkflowError('PROBE_FIXTURE_VALIDATION_FAILED') from None
        if proc.returncode or not valid:raise WorkflowError('PROBE_FIXTURE_VALIDATION_FAILED')
    _publish(root,'.runtime/probe/ffprobe',binary.read_bytes(),0o700)
    _publish(root,'.runtime/probe/COPYING.LGPLv2.1',(root/recipe['license_path']).read_bytes())
    _publish(root,'.runtime/probe/LICENSE.md',(root/'vendor/licenses/ffmpeg-8.1.3-LICENSE.md').read_bytes())
    receipt=guard_control(root,'.runtime/probe/receipt.json')
    write_json(receipt,{'schema_version':1,'version':VERSION,'source_sha256':SOURCE_SHA,'recipe_sha256':file_hash(root/'renderers/ffprobe-source.json'),
        'binary_sha256':file_hash(folder/'ffprobe'),'binary':'.runtime/probe/ffprobe','platform':platform.system(),'architecture':platform.machine(),
        'source_archive':str(archive.relative_to(root))})
    return dict(probe_status(root),action='source_built_probe',network=True)
