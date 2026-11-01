"""Explicit official-source GPL FFmpeg provider; never ffmpeg-static's payload."""
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import ssl
import subprocess
import tarfile
import urllib.request
import uuid

from . import development_policy as dev
from .family_jobs import read_owned
from .local_state import guard_control, private_directory, write_private
from .probe_runtime import _publish, toolchain
from .security import WorkflowError, canonical, file_hash
from .development_setup import run_process, command_log, filtered_env

SOURCES = {
    'ffmpeg':{'url':'https://ffmpeg.org/releases/ffmpeg-8.1.3.tar.xz','sha256':'7138d28c96d9d3e3af4ee3d8cad72741f8ffb40da90c1112235dea3ecd3178a3','prefix':'ffmpeg-8.1.3','maximum_archive_bytes':33554432,'maximum_expanded_bytes':629145600,'format':'r:xz'},
    'x264':{'url':'https://code.videolan.org/videolan/x264/-/archive/b35605ace3ddf7c1a5d67a2eb553f034aef41d55/x264-b35605ace3ddf7c1a5d67a2eb553f034aef41d55.tar.gz','sha256':'cd71a7515b0e9a012e1ac9b1f8415bebcaf6fc97d4db32286642ac4c0fbe24f9','prefix':'x264-b35605ace3ddf7c1a5d67a2eb553f034aef41d55','maximum_archive_bytes':2097152,'maximum_expanded_bytes':104857600,'format':'r:gz'}
}


def fail(code):
    raise WorkflowError('SOURCE_FFMPEG_' + code)


def checked_source(source):
    if type(source) is not dict or source not in SOURCES.values():fail('SOURCE_SPEC_REFUSED')


def tools_state():
    tools = toolchain()
    pkg = shutil.which('pkg-config')
    if not pkg:fail('PKG_CONFIG_REQUIRED')
    tools['pkg_config'] = str(Path(pkg).resolve())
    if not re.fullmatch(r'(?:/usr/bin/pkg-config|/(?:opt/homebrew|usr/local)/(?:bin/pkg-config|Cellar/pkgconf/[0-9A-Za-z._-]+/bin/pkgconf))',tools['pkg_config']):fail('PKG_CONFIG_PATH_UNREVIEWED')
    settings = Path(tools['sdk'])/'SDKSettings.json'
    if not settings.is_file():settings = Path(tools['sdk'])/'SDKSettings.plist'
    if not settings.is_file():fail('SDK_IDENTITY_REQUIRED')
    return {**tools,'cc_sha256':file_hash(tools['cc']),'make_sha256':file_hash(tools['make']),
            'pkg_config_sha256':file_hash(tools['pkg_config']),'sdk_settings_sha256':file_hash(settings)}


def source_path(root, relative, source):
    expected = '.runtime/development/sources/'+source['sha256']+('.tar.xz' if source['format']=='r:xz' else '.tar.gz')
    if relative!=expected and not (source['prefix']=='ffmpeg-8.1.3' and re.fullmatch(r'\.runtime/probe/stages/[a-f0-9]{32}/source\.tar\.xz',relative)):
        fail('ARCHIVE_PATH_REFUSED')
    path = guard_control(root,relative)
    if path.stat().st_size>source['maximum_archive_bytes'] or file_hash(path)!=source['sha256']:fail('SOURCE_HASH_MISMATCH')
    return path


def cached_source(root, source, approval):
    """One exact owned cache entry shared by the two private source providers."""
    checked_source(source);dev.disk_preflight(root,approval,'setup')
    cache = guard_control(root,'.runtime/development/sources','dir');private_directory(cache)
    relative = '.runtime/development/sources/'+source['sha256']+('.tar.xz' if source['format']=='r:xz' else '.tar.gz')
    target = guard_control(root,relative);downloaded = False
    if not target.exists():
        part = cache/(uuid.uuid4().hex+'.part')
        download(source,part);dev.require_approval(root,approval,'setup');guard_control(root,relative)
        if target.exists():fail('CACHE_CHANGED')
        os.replace(part,target);downloaded = True
    source_path(root,relative,source)
    return relative,target,downloaded


def status(root=dev.ROOT):
    recipe = dev.recipe(root)
    result = {'ready':False,'provider':dev.PROVIDER,'path':recipe['binary'],'reason':'SOURCE_FFMPEG_NOT_READY'}
    try:
        value, _ = dev.strict_json(root,recipe['receipt'],65536)
        expected = {'schema_version','provider','policy_sha256','source_binding','recipe_sha256','platform','architecture',
                    'binary','binary_sha256','sources','toolchain','configuration_files','license_files','capabilities','capabilities_sha256'}
        if (type(value) is not dict or set(value)!=expected or type(value['schema_version']) is not int
                or value['schema_version']!=1 or value['provider']!=dev.PROVIDER or value['policy_sha256']!=dev.POLICY_SHA
                or value['source_binding']!=dev.binding(root,dev.policy(root)) or value['recipe_sha256']!=dev.RECIPE_SHA
                or value['platform']!='Darwin' or value['architecture']!='arm64' or value['binary']!=recipe['binary']
                or value['toolchain']!=tools_state()):return result
        binary = guard_control(root,recipe['binary'])
        if not os.access(binary,os.X_OK) or file_hash(binary)!=value['binary_sha256']:return result
        if set(value['sources'])!=set(recipe['sources']):return result
        for name, relative in value['sources'].items():source_path(root,relative,recipe['sources'][name])
        configs = value['configuration_files']
        if type(configs) is not dict or len(configs)!=3:return result
        stages = {p.split('/')[3] for p in configs if re.fullmatch(r'\.runtime/ffmpeg/stages/[a-f0-9]{32}/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',p)}
        if len(stages)!=1:return result
        stage = '.runtime/ffmpeg/stages/'+next(iter(stages))
        if set(configs)!={stage+'/ffmpeg-source/config.h',stage+'/ffmpeg-source/config_components.h',stage+'/x264-source/config.mak'}:return result
        if set(value['license_files'])!={'.runtime/ffmpeg/COPYING.GPLv2','.runtime/ffmpeg/x264-COPYING.GPLv2','.runtime/ffmpeg/LICENSE.md'}:return result
        if (value['license_files']['.runtime/ffmpeg/x264-COPYING.GPLv2']!=recipe['license_files']['vendor/licenses/x264-b35605a-COPYING.GPLv2']
                or value['license_files']['.runtime/ffmpeg/LICENSE.md']!=recipe['license_files']['vendor/licenses/ffmpeg-8.1.3-LICENSE.md']
                or value['license_files']['.runtime/ffmpeg/COPYING.GPLv2']!=file_hash(guard_control(root,stage+'/ffmpeg-source/COPYING.GPLv2'))):return result
        for group in ('configuration_files','license_files'):
            if type(value[group]) is not dict or not value[group]:return result
            for relative, expected_sha in value[group].items():
                if not re.fullmatch(r'\.runtime/ffmpeg/(?:stages/[a-f0-9]{32}/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+|[A-Za-z0-9_.-]+)',relative):return result
                if file_hash(guard_control(root,relative))!=expected_sha:return result
        capabilities, sha = dev.strict_json(root,'.runtime/ffmpeg/capabilities.json',32768)
        required = {name:recipe[name] for name in ('required_filters','required_encoders','required_decoders','required_muxers','required_bitstream_filters')}
        if (type(capabilities) is not dict or set(capabilities)!={'validated','required','buildconf_sha256'}
                or not isinstance(capabilities['buildconf_sha256'],str) or not re.fullmatch('[a-f0-9]{64}',capabilities['buildconf_sha256'])
                or sha!=value['capabilities_sha256'] or capabilities!=value['capabilities']
                or capabilities.get('required')!=required or capabilities.get('validated') is not True):return result
        return {**result,'ready':True,'reason':None,'binary_sha256':value['binary_sha256']}
    except (WorkflowError,OSError,ValueError,KeyError,TypeError,RecursionError):return result


class NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kw):fail('REDIRECT_REFUSED')


def download(source, target):
    checked_source(source)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirects(),
        urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    try:
        with opener.open(urllib.request.Request(source['url'],headers={'User-Agent':'StoryMotion-Source-FFmpeg/1'}),timeout=40) as response:
            fd = os.open(target,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
            with os.fdopen(fd,'wb') as stream:
                total = 0
                while True:
                    data = response.read(512*1024)
                    if not data:break
                    total += len(data)
                    if total>source['maximum_archive_bytes']:fail('DOWNLOAD_BOUND_EXCEEDED')
                    stream.write(data)
                stream.flush();os.fsync(stream.fileno())
    except (OSError,ValueError):fail('DOWNLOAD_FAILED')
    if file_hash(target)!=source['sha256']:fail('SOURCE_HASH_MISMATCH')


def extract(archive_path, destination, source):
    checked_source(source)
    if file_hash(archive_path)!=source['sha256']:fail('SOURCE_HASH_MISMATCH')
    with tarfile.open(archive_path,source['format']) as archive:
        members = list(archive);seen = {};total = 0
        for member in members:
            parts = member.name.rstrip('/').split('/');total += member.size
            if (not parts or parts[0]!=source['prefix'] or len(member.name)>512
                    or re.search(r'[\\:\x00-\x1f\x7f]',member.name) or any(p in ('','.','..') for p in parts)
                    or not (member.isdir() or member.isfile()) or len(members)>32000
                    or member.size<0 or member.size>64*1024*1024 or total>source['maximum_expanded_bytes']
                    or member.name.rstrip('/').casefold() in seen or len(parts)==1 and not member.isdir()):fail('ARCHIVE_REFUSED')
            seen[member.name.rstrip('/').casefold()] = member.isdir()
        for name in seen:
            if any(seen.get(str(p)) is False for p in PurePosixPath(name).parents):fail('ARCHIVE_REFUSED')
        destination.mkdir(mode=0o700)
        for member in members:
            parts = PurePosixPath(member.name).parts[1:]
            if not parts:continue
            target = destination.joinpath(*parts)
            private_directory(target.parent)
            if member.isdir():private_directory(target)
            else:
                fd = os.open(target,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o700 if member.mode&0o111 else 0o600)
                with os.fdopen(fd,'wb') as stream:shutil.copyfileobj(archive.extractfile(member),stream)


def environment(tools, recipe, root):
    env = filtered_env(root,create=True)
    env.update(DO_NOT_TRACK='1',HYPERFRAMES_TELEMETRY_DISABLED='1',SOURCE_DATE_EPOCH=str(recipe['source_date_epoch']),
               SDKROOT=tools['sdk'],CC=tools['cc'])
    return env


def run(argv, cwd, env, timeout, log):
    try:result = run_process(argv,cwd=cwd,env=env,timeout=timeout)
    except (OSError,subprocess.TimeoutExpired):fail('BUILD_OR_VALIDATION_FAILED')
    raw = result.stdout+result.stderr
    command_log(log,raw)
    if result.returncode:fail('BUILD_OR_VALIDATION_FAILED')
    return raw.decode('utf-8',errors='replace')


def check_configuration(build):
    configuration = read_owned(build,'config.h',1024*1024).decode()+read_owned(build,'config_components.h',1024*1024).decode()
    for flag, number in [('GPL',1),('LIBX264',1),('AVFILTER',1),('SWSCALE',1),('NONFREE',0),('VERSION3',0),('NETWORK',0)]:
        if not re.search(r'^#define CONFIG_'+flag+' '+str(number)+r'$',configuration,re.M):fail('CONFIGURATION_REFUSED')


def install(root, approval):
    dev.require_approval(root,approval,'setup')
    from .store import Store
    folder = guard_control(root,'.runtime/ffmpeg','dir');private_directory(folder)
    with Store(folder/'build-state') as store,store.lock():
        return _install(root,approval)


def _install(root, approval):
    root = Path(root)
    dev.require_approval(root,approval,'setup');recipe = dev.recipe(root);current = status(root)
    if current['ready']:return {**current,'action':'reused','network':False}
    disk = dev.disk_preflight(root,approval,'setup');tools = tools_state()
    private_directory(guard_control(root,'.runtime/ffmpeg/stages','dir'))
    stage = guard_control(root,'.runtime/ffmpeg/stages/'+uuid.uuid4().hex,'dir');stage.mkdir(mode=0o700)
    inventory = {'provider_root':'.runtime/ffmpeg','stage':str(stage.relative_to(root)),'generated':[],'disk_before':disk,'deletion_authorized':False}
    write_private(stage/'inventory.json',canonical(inventory))
    archives = {}
    for name, source in recipe['sources'].items():
        relative,target,_ = cached_source(root,source,approval);archives[name] = relative
        extract(target,stage/(name+'-source'),source)
    if file_hash(stage/'x264-source/COPYING')!=recipe['license_files']['vendor/licenses/x264-b35605a-COPYING.GPLv2']:fail('LICENSE_CHANGED')
    if file_hash(stage/'ffmpeg-source/LICENSE.md')!=recipe['license_files']['vendor/licenses/ffmpeg-8.1.3-LICENSE.md']:fail('LICENSE_CHANGED')
    gpl = read_owned(stage,'ffmpeg-source/COPYING.GPLv2',65536)
    if b'GNU GENERAL PUBLIC LICENSE' not in gpl or b'Version 2' not in gpl:fail('LICENSE_CHANGED')
    prefix = stage/'x264-prefix';xb = stage/'x264-source';fb = stage/'ffmpeg-source'
    # Configure in the freshly extracted owned source trees: upstream only
    # creates its retained src directory link for out-of-tree builds.
    # No control-path symlink exception is needed or permitted.
    env = environment(tools,recipe,root)
    env.update(PKG_CONFIG_LIBDIR=str(prefix/'lib/pkgconfig'),PKG_CONFIG_PATH='')
    common = '-arch arm64 -isysroot '+tools['sdk']
    commands = [
        ([str(stage/'x264-source/configure'),*recipe['x264_flags'],'--prefix='+str(prefix),'--extra-cflags='+common,'--extra-ldflags='+common],xb,300),
        ([tools['make'],'-j2','install'],xb,900),
        ([str(stage/'ffmpeg-source/configure'),*recipe['ffmpeg_flags'],'--cc='+tools['cc'],'--sysroot='+tools['sdk'],
          '--pkg-config='+tools['pkg_config'],'--pkg-config-flags=--static','--extra-cflags='+common+' -I'+str(prefix/'include'),
          '--extra-ldflags='+common+' -L'+str(prefix/'lib')],fb,300),
        ([tools['make'],'-j2','ffmpeg'],fb,900)]
    for index,(argv,cwd,timeout) in enumerate(commands):
        dev.disk_preflight(root,approval,'setup');run(argv,cwd,env,timeout,stage/(str(index)+'.log'))
        if index==2:check_configuration(fb)  # Before compiling an unintended configuration.
    check_configuration(fb)
    binary = guard_control(fb,'ffmpeg')
    if not binary.is_file() or binary.stat().st_size>64*1024*1024:fail('BINARY_REFUSED')
    checks = {}
    for argument in ('-version','-L','-buildconf','-filters','-encoders','-decoders','-muxers','-bsfs'):
        checks[argument] = run([str(binary),argument],fb,env,20,stage/(argument[1:]+'.log'))
    if not re.search(r'^ffmpeg version 8\.1\.3\b',checks['-version']) or 'GNU General Public License' not in checks['-L']:fail('BINARY_REFUSED')
    if any(flag not in checks['-buildconf'] for flag in recipe['ffmpeg_flags']):fail('CONFIGURATION_REFUSED')
    required = {}
    for key,arg in [('required_filters','-filters'),('required_encoders','-encoders'),('required_decoders','-decoders'),('required_muxers','-muxers'),('required_bitstream_filters','-bsfs')]:
        for name in recipe[key]:
            if not re.search(r'(?m)(?:^|[\s,])'+re.escape(name)+r'(?:[\s,]|$)',checks[arg]):fail('CAPABILITY_MISSING')
        required[key] = recipe[key]
    capabilities = {'validated':True,'required':required,'buildconf_sha256':hashlib.sha256(checks['-buildconf'].encode()).hexdigest()}
    dev.require_approval(root,approval,'setup')
    _publish(root,recipe['binary'],binary.read_bytes(),0o700)
    _publish(root,'.runtime/ffmpeg/COPYING.GPLv2',gpl)
    _publish(root,'.runtime/ffmpeg/x264-COPYING.GPLv2',(stage/'x264-source/COPYING').read_bytes())
    _publish(root,'.runtime/ffmpeg/LICENSE.md',(stage/'ffmpeg-source/LICENSE.md').read_bytes())
    write_private(root/'.runtime/ffmpeg/capabilities.json',canonical(capabilities))
    configs = {str(path.relative_to(root)):file_hash(path) for path in [fb/'config.h',fb/'config_components.h',xb/'config.mak']}
    licenses = {'.runtime/ffmpeg/'+name:file_hash(root/'.runtime/ffmpeg'/name) for name in ('COPYING.GPLv2','x264-COPYING.GPLv2','LICENSE.md')}
    receipt = {'schema_version':1,'provider':dev.PROVIDER,'policy_sha256':dev.POLICY_SHA,
        'source_binding':dev.binding(root,dev.policy(root)),'recipe_sha256':dev.RECIPE_SHA,'platform':'Darwin','architecture':'arm64',
        'binary':recipe['binary'],'binary_sha256':file_hash(root/recipe['binary']),'sources':archives,'toolchain':tools,
        'configuration_files':configs,'license_files':licenses,'capabilities':capabilities,
        'capabilities_sha256':file_hash(root/'.runtime/ffmpeg/capabilities.json')}
    write_private(root/recipe['receipt'],canonical(receipt))
    inventory['generated'] = [str(p.relative_to(root)) for p in sorted(stage.rglob('*'))]
    inventory['source_archives'] = archives;write_private(stage/'inventory.json',canonical(inventory))
    result = status(root)
    if not result['ready']:fail('ACTIVATION_FAILED')
    return {**result,'action':'source_built','network':True}
