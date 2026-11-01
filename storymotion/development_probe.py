"""Private LGPL probe bootstrap. Only generated silent PCM is validated here."""
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import uuid

from . import development_policy as dev
from . import ffmpeg_runtime as source
from .development_setup import command_log, mode, run_process
from .family_jobs import read_owned
from .local_state import guard_control, private_directory, write_private
from .probe_runtime import _publish, source_recipe, toolchain
from .security import WorkflowError, canonical, file_hash

PROVIDER = 'source-ffprobe-8.1.3-lgpl-private-silent-v1'
PROFILE = 'private-generated-silence-v1'
BASE = '.runtime/development/probe'
BINARY = BASE+'/ffprobe'
RECEIPT = BASE+'/receipt.json'
RECIPE_SHA = '2354151b834791ba3b00d29301c15b0d03236ca0b4f6a4b1bcc65fce42eaccbd'
WAV_SHA = '643f8a8dc8bd9c19225afffad2becfec5426180b3749cb208abdf1a6c8354efc'
VALIDATION = {'profile':PROFILE,'codec':'pcm_s16le','sample_rate':16000,'channels':1,
              'bits_per_sample':16,'duration_microseconds':1000000,'format':'wav','stream_count':1}


def fail(code):
    raise WorkflowError('DEVELOPMENT_PROBE_'+code)


def recipe(root):
    if file_hash(guard_control(root,'renderers/ffprobe-source.json'))!=RECIPE_SHA:fail('RECIPE_CHANGED')
    return source_recipe(root)  # Unchanged LGPL flags/license checks; never its installer.


def tools_state():
    tools = toolchain();settings = Path(tools['sdk'])/'SDKSettings.json'
    if not settings.is_file():settings = Path(tools['sdk'])/'SDKSettings.plist'
    if not settings.is_file():fail('SDK_IDENTITY_REQUIRED')
    return {**tools,'cc_sha256':file_hash(tools['cc']),'make_sha256':file_hash(tools['make']),
            'sdk_settings_sha256':file_hash(settings)}


def silent_wav():
    return (b'RIFF'+struct.pack('<I',32036)+b'WAVEfmt '+struct.pack('<IHHIIHH',16,1,1,16000,32000,2,16)
            +b'data'+struct.pack('<I',32000)+bytes(32000))


def fixture(root, relative):
    raw = read_owned(root,relative,32044)
    if len(raw)!=32044 or hashlib.sha256(raw).hexdigest()!=WAV_SHA:fail('FIXTURE_CHANGED')


def check_configuration(build):
    raw = read_owned(build,'config.h',1024*1024).decode()+read_owned(build,'config_components.h',1024*1024).decode()
    for flag,number in [('GPL',0),('NONFREE',0),('VERSION3',0),('NETWORK',0),('ZLIB',1),('PNG_DECODER',1)]:
        if not re.search(r'^#define CONFIG_'+flag+' '+str(number)+r'$',raw,re.M):fail('CONFIGURATION_REFUSED')


def metadata(raw):
    if len(raw)>32768:fail('METADATA_INVALID')
    def pairs(rows):
        result = {}
        for key,value in rows:
            if key in result or key in ('__proto__','constructor','prototype'):fail('METADATA_INVALID')
            result[key] = value
        return result
    try:
        value = json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,parse_constant=lambda _:fail('METADATA_INVALID'))
        nodes = [0]
        def bounded(item,depth=0):
            nodes[0] += 1
            if depth>12 or nodes[0]>1000:fail('METADATA_INVALID')
            if type(item) is dict:
                for child in item.values():bounded(child,depth+1)
            elif type(item) is list:
                for child in item:bounded(child,depth+1)
            elif item is not None and type(item) not in (str,int,bool):fail('METADATA_INVALID')
            elif type(item) is int and abs(item)>9007199254740991:fail('METADATA_INVALID')
        bounded(value)
        if type(value) is not dict or set(value)!={'streams','format'}:fail('METADATA_INVALID')
        streams=value['streams'];fmt=value['format']
        if type(streams) is not list or len(streams)!=1 or type(streams[0]) is not dict or type(fmt) is not dict:fail('METADATA_INVALID')
        stream=streams[0]
        if (stream.get('codec_type')!='audio' or stream.get('codec_name')!='pcm_s16le' or stream.get('sample_rate')!='16000'
                or type(stream.get('channels')) is not int or stream['channels']!=1
                or type(stream.get('bits_per_sample')) is not int or stream['bits_per_sample']!=16
                or fmt.get('format_name')!='wav' or type(fmt.get('duration')) is not str
                or not re.fullmatch(r'1(?:\.0{1,9})?',fmt['duration'])):fail('METADATA_INVALID')
        return dict(VALIDATION)
    except (ValueError,UnicodeError,TypeError,RecursionError):fail('METADATA_INVALID')


def inventory(stage, archive, disk):
    return {'schema_version':1,'provider':PROVIDER,'stage':stage,'source_archive':archive,
            'generated_roots':[stage+'/ffmpeg-source',stage+'/silent.wav',stage+'/logs'],
            'disk_before':disk,'retained':True,'deletion_authorized':False}


def expected_receipt(root, stage, archive, tools, m):
    r=recipe(root)
    configs={stage+'/ffmpeg-source/'+name:file_hash(guard_control(root,stage+'/ffmpeg-source/'+name)) for name in ('config.h','config_components.h')}
    licenses={BASE+'/COPYING.LGPLv2.1':r['license_sha256'],BASE+'/LICENSE.md':'2e1d16c72fd74e12063776371da757322f8b77589386532f4fd8634bde7de1af'}
    return {'schema_version':1,'provider':PROVIDER,'profile':PROFILE,'policy_sha256':dev.POLICY_SHA,
            'source_binding':m['source_binding'],'mode_id':m['mode_id'],'recipe_sha256':RECIPE_SHA,
            'version':'8.1.3','platform':'Darwin','architecture':'arm64','binary':BINARY,
            'binary_sha256':file_hash(guard_control(root,BINARY)),
            'source_url':source.SOURCES['ffmpeg']['url'],'source_sha256':source.SOURCES['ffmpeg']['sha256'],
            'source_archive':archive,'toolchain':tools,'stage':stage,
            'fixture':{'path':stage+'/silent.wav','sha256':WAV_SHA,'bytes':32044},'validation':VALIDATION,
            'configuration_files':configs,'license_files':licenses,'inventory_sha256':file_hash(guard_control(root,stage+'/inventory.json'))}


def status(root=dev.ROOT):
    base={'ready':False,'provider':PROVIDER,'profile':PROFILE,'path':BINARY,'version':'8.1.3','reason':'DEVELOPMENT_PROBE_NOT_READY'}
    try:
        root=Path(root);dev.policy(root);m=mode(root);r=recipe(root)
        v,_=dev.strict_json(root,RECEIPT,32768)
        if type(v) is not dict or type(v.get('stage')) is not str or not re.fullmatch(re.escape(BASE)+r'/stages/[a-f0-9]{32}',v['stage']):return base
        stage=v['stage'];archive='.runtime/development/sources/'+source.SOURCES['ffmpeg']['sha256']+'.tar.xz'
        if canonical(v)!=canonical(expected_receipt(root,stage,archive,tools_state(),m)) or type(v.get('schema_version')) is not int:return base
        binary=guard_control(root,BINARY)
        if not os.access(binary,os.X_OK) or binary.stat().st_size>64*1024*1024:return base
        source.source_path(root,archive,source.SOURCES['ffmpeg']);fixture(root,stage+'/silent.wav')
        check_configuration(guard_control(root,stage+'/ffmpeg-source','dir'))
        for path,sha in v['license_files'].items():
            if file_hash(guard_control(root,path))!=sha:return base
        inv,_=dev.strict_json(root,stage+'/inventory.json',4096)
        disk=inv.get('disk_before') if type(inv) is dict else None
        if (type(disk) is not dict or set(disk)!={'free_bytes','minimum_free_bytes','upper_bound_guaranteed'}
                or type(disk['free_bytes']) is not int or disk['free_bytes']<6442450944
                or type(disk['minimum_free_bytes']) is not int or disk['minimum_free_bytes']!=6442450944
                or disk['upper_bound_guaranteed'] is not False or canonical(inv)!=canonical(inventory(stage,archive,disk))):return base
        return {**base,'ready':True,'reason':None,'binary':str(binary),'binary_sha256':v['binary_sha256'],'validation':dict(VALIDATION)}
    except (WorkflowError,OSError,ValueError,KeyError,TypeError,UnicodeError,RecursionError):return base


def install(root, approval):
    root=Path(root);dev.require_approval(root,approval,'setup');dev.disk_preflight(root,approval,'setup');m=mode(root)
    from .store import Store
    folder=guard_control(root,BASE,'dir');private_directory(folder)
    with Store(folder/'build-state') as store,store.lock():
        current=status(root)
        if current['ready']:return {**current,'action':'reused','network':False}
        r=recipe(root);tools=tools_state();disk=dev.disk_preflight(root,approval,'setup')
        stage=BASE+'/stages/'+uuid.uuid4().hex;private_directory(guard_control(root,stage,'dir'))
        archive='.runtime/development/sources/'+source.SOURCES['ffmpeg']['sha256']+'.tar.xz'
        write_private(root/stage/'inventory.json',canonical(inventory(stage,archive,disk)))
        archive,target,downloaded=source.cached_source(root,source.SOURCES['ffmpeg'],approval)
        build=root/stage/'ffmpeg-source';source.extract(target,build,source.SOURCES['ffmpeg'])
        for name,sha in [('COPYING.LGPLv2.1',r['license_sha256']),('LICENSE.md','2e1d16c72fd74e12063776371da757322f8b77589386532f4fd8634bde7de1af')]:
            if file_hash(guard_control(build,name))!=sha:fail('LICENSE_CHANGED')
        env=source.environment(tools,r,root)
        argv=[str(build/'configure'),*r['configure_flags'],'--cc='+tools['cc'],'--sysroot='+tools['sdk'],
              '--host-cflags=-isysroot '+tools['sdk'],'--host-ldflags=-isysroot '+tools['sdk']]
        for name,args,timeout in [('configure',argv,300),('make',[tools['make'],'-j2','ffprobe'],900)]:
            dev.disk_preflight(root,approval,'setup');source.run(args,build,env,timeout,root/stage/'logs'/(name+'.log'))
            check_configuration(build)
        binary=guard_control(build,'ffprobe')
        if not binary.is_file() or binary.stat().st_size>64*1024*1024 or not os.access(binary,os.X_OK):fail('BINARY_REFUSED')
        binary_sha=file_hash(binary)
        generated=root/stage/'silent.wav';raw=silent_wav()
        if len(raw)!=32044 or hashlib.sha256(raw).hexdigest()!=WAV_SHA:fail('FIXTURE_CHANGED')
        fd=os.open(generated,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
        observed=None
        for name,args in [('version',['-version']),('license',['-L']),('silence',['-v','error','-show_streams','-show_format','-of','json',str(generated)])]:
            dev.require_approval(root,approval,'setup');fixture(root,stage+'/silent.wav')
            try:result=run_process([str(binary),*args],cwd=build,env=env,timeout=20)
            except (OSError,subprocess.TimeoutExpired):fail('VALIDATION_FAILED')
            command_log(root/stage/'logs'/(name+'.log'),result.stdout+result.stderr)
            if result.returncode or len(result.stdout)>32768 or len(result.stderr)>32768:fail('VALIDATION_FAILED')
            if name=='version' and not re.search(rb'^ffprobe version 8\.1\.3\b',result.stdout):fail('VALIDATION_FAILED')
            if name=='license' and b'Lesser General Public License' not in result.stdout:fail('VALIDATION_FAILED')
            if name=='silence':
                if result.stderr:fail('VALIDATION_FAILED')
                observed=metadata(result.stdout)
            fixture(root,stage+'/silent.wav')
        if observed!=VALIDATION or tools_state()!=tools or file_hash(binary)!=binary_sha:fail('VALIDATION_FAILED')
        dev.require_approval(root,approval,'setup');check_configuration(build)
        _publish(root,BINARY,binary.read_bytes(),0o700)
        _publish(root,BASE+'/COPYING.LGPLv2.1',(build/'COPYING.LGPLv2.1').read_bytes())
        _publish(root,BASE+'/LICENSE.md',(build/'LICENSE.md').read_bytes())
        write_private(root/RECEIPT,canonical(expected_receipt(root,stage,archive,tools,m)))
        result=status(root)
        if not result['ready']:fail('ACTIVATION_FAILED')
        return {**result,'action':'source_built_private_silent_probe','network':downloaded}
