"""Opt-in private fixture setup. No customer installer, scripts or binary fallback."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import uuid

from . import development_policy as dev
from .family_jobs import read_owned
from .local_state import guard_control, guard_project_scope, private_directory, write_private
from .security import WorkflowError, canonical, digest, file_hash, scan_bytes

CHROME_VERSION = '152.0.7977.30'
CHROME_LICENSE_SHA = '92b1cf9cde6cc452b041c55f97154e32500a535c4a13b3e4676d689789c7d89b'
PROCESS_BASE = '.runtime/development/process'
PROCESS_PATHS = {'HOME':'home','CFFIXED_USER_HOME':'home','TMPDIR':'tmp','TMP':'tmp','TEMP':'tmp',
                 'XDG_CACHE_HOME':'home/.cache','XDG_CONFIG_HOME':'home/.config',
                 'XDG_STATE_HOME':'home/.local/state','XDG_DATA_HOME':'home/.local/share','XDG_RUNTIME_DIR':'run',
                 'NODE_COMPILE_CACHE':'compile-cache','HYPERFRAMES_EXTRACT_CACHE_DIR':'extract',
                 'HYPERFRAMES_FONT_CACHE_DIR':'home/.cache/hyperframes/fonts','HYPERFRAMES_MEDIA_HOME':'media',
                 'PUPPETEER_CACHE_DIR':'home/.cache/puppeteer','CLANG_MODULE_CACHE_PATH':'clang-cache'}
PROCESS_DIRS = sorted(set(PROCESS_PATHS.values())|{'home/.cache/hyperframes/history','home/.hyperframes/running'})
PROCESS_CONTROLS = {'DO_NOT_TRACK':'1','HYPERFRAMES_TELEMETRY_DISABLED':'1','HYPERFRAMES_NO_TELEMETRY':'1',
                    'HYPERFRAMES_NO_UPDATE_CHECK':'1','HYPERFRAMES_NO_AUTO_INSTALL':'1',
                    'HYPERFRAMES_MEDIA_HOME_REQUIRED':'1','PYTHONDONTWRITEBYTECODE':'1'}


def fail(code):
    raise WorkflowError('DEVELOPMENT_' + code)


def process_paths(root, *, create=False):
    root = Path(root).absolute()
    if root!=root.resolve():fail('PROCESS_ROOT_INVALID')
    paths = [guard_control(root,PROCESS_BASE,'dir'),*[guard_control(root,PROCESS_BASE+'/'+name,'dir') for name in PROCESS_DIRS]]
    for path in paths:
        if path.exists() and stat.S_IMODE(path.stat().st_mode)!=0o700:fail('PROCESS_DIRECTORY_NOT_PRIVATE')
    base = guard_control(root,PROCESS_BASE,'dir')
    if base.exists():
        for folder, dirs, files in os.walk(base,followlinks=False):
            for name in dirs:guard_control(root,(Path(folder)/name).relative_to(root),'dir')
            for name in files:guard_control(root,(Path(folder)/name).relative_to(root))
    if create:
        for path in paths:private_directory(path)
    return {name:str(root/PROCESS_BASE/path) for name,path in PROCESS_PATHS.items()}


def filtered_env(root, *, create=False):
    allowed = ('PATH','USER','LOGNAME','LANG','LC_ALL','SHELL')
    env = {name:os.environ[name] for name in allowed if name in os.environ}
    env.update(process_paths(root,create=create),**PROCESS_CONTROLS)
    return env


def command_log(path, raw):
    # Scan the full output before truncation, persistence or caller inspection.
    # A blocked command exposes only this fixed diagnostic, never its payload.
    if scan_bytes(raw):
        write_private(path, 'Command output withheld: credential scanner match.\n')
        fail('CREDENTIAL_ECHO_BLOCKED')
    write_private(path, raw[-65536:])


def run_process(argv, *, cwd, env, timeout):
    from .engine import stop_owned_group
    process = subprocess.Popen(argv,cwd=cwd,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
    try:stdout,stderr = process.communicate(timeout=timeout)
    except BaseException:
        stop_owned_group(process)  # Only the group created immediately above.
        raise
    return subprocess.CompletedProcess(argv,process.returncode,stdout,stderr)


def mode(root):
    value, _ = dev.strict_json(root,dev.MODE,32768)
    expected = {'schema_version','mode_id','policy_sha256','source_binding','root_sha256','provider','fixture_sha256','node'}
    if (type(value) is not dict or set(value)!=expected or type(value['schema_version']) is not int
            or value['schema_version']!=1 or not re.fullmatch('[a-f0-9]{32}',value['mode_id'])
            or value['policy_sha256']!=dev.POLICY_SHA or value['source_binding']!=dev.binding(root,dev.policy(root))
            or value['root_sha256']!=hashlib.sha256(str(Path(root).resolve()).encode()).hexdigest()
            or value['provider']!=dev.PROVIDER or value['fixture_sha256']!=dev.FIXTURE_SHA):fail('MODE_INVALID')
    node = value['node'];current = shutil.which('node')
    if (type(node) is not dict or set(node)!={'binary','sha256','version'} or current is None
            or str(Path(current).resolve())!=node['binary'] or file_hash(Path(current).resolve())!=node['sha256']
            or type(node['version']) is not str or not re.fullmatch(r'v22\.[0-9]+\.[0-9]+',node['version'])
            or tuple(map(int,node['version'][1:].split('.')))<(22,23,2)):fail('NODE_CHANGED')
    return value


def installed_packages(root):
    expected = dev.installation_artifacts(root);actual = set()
    def visit(folder):
        if not folder.exists():return
        guard_control(root,folder.relative_to(root),'dir')
        for child in sorted(folder.iterdir()):
            if child.name in ('.bin','.package-lock.json'):continue
            if child.name.startswith('@'):
                guard_control(root,child.relative_to(root),'dir')
                candidates = sorted(child.iterdir())
            else:candidates = [child]
            for candidate in candidates:
                path = candidate.relative_to(root).as_posix()
                guard_control(root,path,'dir')
                if path not in expected:fail('UNEXPECTED_INSTALLED_ARTIFACT')
                value, _ = dev.strict_json(root,path+'/package.json',1024*1024)
                if type(value) is not dict or value.get('name')!=expected[path]['name'] or value.get('version')!=expected[path]['version']:fail('INSTALLED_ARTIFACT_CHANGED')
                actual.add(path);visit(candidate/'node_modules')
    visit(Path(root)/'node_modules')
    if actual!=set(expected):fail('INSTALLED_ARTIFACT_MISSING')
    forbidden = Path(root)/'node_modules/ffmpeg-static/ffmpeg'
    if forbidden.exists() or forbidden.is_symlink():fail('STATIC_BINARY_EXCLUDED')
    return sorted(actual)


def installed_tree(root):
    root = Path(root);base = guard_control(root,'node_modules','dir');result = {};total = 0
    for folder, dirs, files in os.walk(base,followlinks=False):
        for name in sorted(dirs+files):
            path = Path(folder)/name;info = path.lstat();relative = path.relative_to(root).as_posix()
            if info.st_uid!=os.getuid():fail('INSTALLED_PATH_REFUSED')
            if stat.S_ISLNK(info.st_mode):
                resolved = path.resolve()
                if not resolved.is_relative_to(base) or not resolved.is_file():fail('INSTALLED_PATH_REFUSED')
                actual = resolved.stat()
                if actual.st_uid!=os.getuid() or actual.st_nlink!=1 or actual.st_size>128*1024*1024:fail('INSTALLED_PATH_REFUSED')
                result[relative] = {'target':resolved.relative_to(root).as_posix(),'sha256':file_hash(resolved)}
                total += actual.st_size
            elif stat.S_ISREG(info.st_mode):
                if info.st_nlink!=1 or info.st_size>128*1024*1024:fail('INSTALLED_PATH_REFUSED')
                result[relative] = {'sha256':hashlib.sha256(read_owned(root,relative,128*1024*1024)).hexdigest()}
                total += info.st_size
            elif not stat.S_ISDIR(info.st_mode):fail('INSTALLED_PATH_REFUSED')
            if len(result)>50000 or total>512*1024*1024:fail('INSTALLED_BOUND_EXCEEDED')
    return digest(result)


def npm_receipt(root, mode_value, tree_sha, packages):
    return {'schema_version':4,'graph':'core','npm_ci':'complete_ignored_scripts','npm_mode':'ignore_scripts',
            'lifecycle_allowlist':[],'provider':dev.PROVIDER,'policy_sha256':dev.POLICY_SHA,
            'source_binding':mode_value['source_binding'],'mode_id':mode_value['mode_id'],
            'node':mode_value['node'],
            'package_lock_sha256':file_hash(guard_control(root,'package-lock.json')),
            'package_json_sha256':file_hash(guard_control(root,'package.json')),
            'installed_tree_sha256':tree_sha,'installed_packages':packages}


def npm_ready(root):
    try:
        value = mode(root);receipt, _ = dev.strict_json(root,'.runtime/npm-core.json',32768)
        return receipt==npm_receipt(root,value,installed_tree(root),installed_packages(root)) and type(receipt['schema_version']) is int
    except (WorkflowError,OSError,ValueError,KeyError,TypeError,RecursionError):return False


def status(root=dev.ROOT, engine='hyperframes', *, require_completion=True):
    base = {'ok':False,'requested_engine':engine,'engines':{'hyperframes':{'ready':False},'remotion':{'ready':False}},
            'packages':{'hyperframes':{'ok':False},'ffmpeg-static':{'ok':False}},'network_during_inspection':False,
            'runtime_scope':'fixed private silent fixture only','provider_calls':0,**{name:False for name in dev.FLAGS}}
    try:
        dev.policy(root,engine);m = mode(root)
        from .ffmpeg_runtime import status as ffmpeg_status
        from .development_probe import status as probe_status
        ffmpeg = ffmpeg_status(root);probe = probe_status(root);npm = npm_ready(root)
        browser, _ = dev.strict_json(root,'.runtime/development/browser.json',32768)
        expected = {'schema_version','policy_sha256','source_binding','mode_id','browser','browser_version','browser_sha256','license_sha256','browser_drawing_smoke','platform','architecture'}
        if type(browser) is not dict:return base
        path = browser.get('browser')
        if (set(browser)!=expected or type(browser['schema_version']) is not int
                or browser['schema_version']!=4 or browser['policy_sha256']!=dev.POLICY_SHA
                or browser['source_binding']!=m['source_binding'] or browser['mode_id']!=m['mode_id']
                or browser['browser_version']!=CHROME_VERSION or browser['license_sha256']!=CHROME_LICENSE_SHA
                or browser['browser_drawing_smoke']!='pass' or browser['platform']!='Darwin' or browser['architecture']!='arm64'
                or not isinstance(path,str) or not path.startswith('.runtime/chrome/') or not path.endswith('/chrome-headless-shell')):return base
        binary = guard_control(root,path);license_path = str(Path(path).parent/'LICENSE.headless_shell')
        browser_ok = (os.access(binary,os.X_OK) and file_hash(binary)==browser['browser_sha256']
                      and file_hash(guard_control(root,license_path))==CHROME_LICENSE_SHA)
        ready = npm and ffmpeg['ready'] and probe['ready'] and browser_ok
        if require_completion:
            complete, _ = dev.strict_json(root,'.runtime/development/setup.json',32768)
            expected_completion = setup_receipt(root,m,'complete')
            ready = ready and type(complete) is dict and complete==expected_completion and type(complete.get('schema_version')) is int
        return {**base,'ok':ready,'policy_sha256':dev.POLICY_SHA,'source_binding':m['source_binding'],
                'packages':{'hyperframes':{'ok':npm},'ffmpeg-static':{'ok':npm,'inert_wrapper_only':True}},
                'engines':{'hyperframes':{'ready':ready},'remotion':{'ready':False}},
                'browser':{'path':path,'version':CHROME_VERSION,'ok':browser_ok},'ffmpeg':ffmpeg,'probe':probe,
                'npm_receipt_matches_scope':npm}
    except (WorkflowError,OSError,ValueError,KeyError,TypeError,RecursionError):return base


def install_npm(root, approval):
    root = Path(root);dev.require_approval(root,approval,'npm');disk = dev.disk_preflight(root,approval,'npm')
    guard_project_scope(root)
    fresh = not dev.development_mode(root)
    if fresh and ((root/'node_modules').exists() or (root/'.runtime/npm-core.json').exists()):fail('FRESH_ISOLATED_RUNTIME_REQUIRED')
    node = shutil.which('node')
    if not node:fail('NODE_REQUIRED')
    node = Path(node).resolve()
    try:version = run_process([str(node),'--version'],cwd=root,env=filtered_env(root),timeout=10)
    except (OSError,subprocess.TimeoutExpired):fail('NODE_REQUIRED')
    try:node_version = version.stdout.decode('ascii').strip()
    except UnicodeError:fail('NODE_REQUIRED')
    if version.returncode or not re.fullmatch(r'v22\.[0-9]+\.[0-9]+',node_version) or tuple(map(int,node_version[1:].split('.')))<(22,23,2):fail('NODE_REQUIRED')
    node_identity = {'binary':str(node),'sha256':file_hash(node),'version':node_version}
    from .store import Store
    runtime = guard_control(root,'.runtime','dir');private_directory(runtime)
    with Store(runtime/'setup-state') as store,store.lock():
        if fresh:
            if (root/'node_modules').exists() or (root/'.runtime/npm-core.json').exists() or (root/dev.MODE).exists():fail('FRESH_ISOLATED_RUNTIME_REQUIRED')
            private_directory(root/'.runtime/development')
            value = {'schema_version':1,'mode_id':uuid.uuid4().hex,'policy_sha256':dev.POLICY_SHA,
                     'source_binding':approval.source_binding,'root_sha256':hashlib.sha256(str(root.resolve()).encode()).hexdigest(),
                     'provider':dev.PROVIDER,'fixture_sha256':dev.FIXTURE_SHA,'node':node_identity}
            write_private(root/dev.MODE,canonical(value))
        value = mode(root)
        if npm_ready(root):return {**dev.gate(root),'npm_ci':'reused_ignored_scripts','network':False}
        receipt = guard_control(root,'.runtime/npm-core.json')
        if receipt.exists():receipt.unlink()  # Only this bound private receipt, never a normal one.
        for name in ('empty-user.npmrc','empty-global.npmrc'):write_private(root/'.runtime'/name,'')
        argv = ['npm','ci','--ignore-scripts','--include=optional','--no-audit','--no-fund','--registry=https://registry.npmjs.org',
                '--cache='+str(runtime/'npm-cache'),'--userconfig='+str(runtime/'empty-user.npmrc'),
                '--globalconfig='+str(runtime/'empty-global.npmrc'),'--fetch-timeout=30000','--fetch-retries=0']
        try:result = run_process(argv,cwd=root,env=filtered_env(root,create=True),timeout=900)
        except (OSError,subprocess.TimeoutExpired):fail('NPM_FAILED')
        command_log(root/'.runtime/development/npm.log',result.stdout+result.stderr)
        if result.returncode:fail('NPM_FAILED')
        dev.require_approval(root,approval,'npm')
        packages = installed_packages(root);tree = installed_tree(root)
        write_private(receipt,canonical(npm_receipt(root,value,tree,packages)))
        write_private(root/'.runtime/development/npm-inventory.json',canonical({'generated':['node_modules','.runtime/npm-cache',dev.MODE,'.runtime/npm-core.json',PROCESS_BASE],
                      'disk_before':disk,'lifecycle_scripts_executed':[],'deletion_authorized':False}))
        return {**dev.gate(root),'npm_ci':'complete_ignored_scripts','network':True,'lifecycle_scripts_executed':[]}


def setup_receipt(root, value, state):
    receipts = {name:file_hash(guard_control(root,name)) for name in ('.runtime/npm-core.json','.runtime/ffmpeg/receipt.json','.runtime/development/browser.json','.runtime/development/probe/receipt.json')} if state=='complete' else {}
    return {'schema_version':1,'state':state,'policy_sha256':dev.POLICY_SHA,'source_binding':value['source_binding'],'mode_id':value['mode_id'],'receipts':receipts}


def setup(root, approval):
    root = Path(root);dev.require_approval(root,approval,'setup');dev.disk_preflight(root,approval,'setup')
    if not npm_ready(root):fail('PRIVATE_NPM_RECEIPT_REQUIRED')
    from .development_probe import install as install_private_probe
    from .store import Store
    from .ffmpeg_runtime import install
    with Store(root/'.runtime/setup-state') as store,store.lock():
        value = mode(root);receipt = guard_control(root,'.runtime/development/setup.json')
        write_private(receipt,canonical(setup_receipt(root,value,'in_progress')))
        browser_receipt = guard_control(root,'.runtime/development/browser.json')
        if browser_receipt.exists():browser_receipt.unlink()
        try:
            install_private_probe(root,approval)
            dev.disk_preflight(root,approval,'setup')
            install(root,approval)
            dev.disk_preflight(root,approval,'setup')
            argv = [value['node']['binary'],str(root/'tools/runtime.mjs'),'development-setup','--policy-sha256',dev.POLICY_SHA,'--allow-private-test-execution']
            result = run_process(argv,cwd=root,env=filtered_env(root,create=True),timeout=900)
            command_log(root/'.runtime/development/browser-setup.log',result.stdout+result.stderr)
            if result.returncode or status(root,require_completion=False)['ok'] is not True:fail('BROWSER_SETUP_FAILED')
            dev.require_approval(root,approval,'setup')
            write_private(receipt,canonical(setup_receipt(root,value,'complete')))
        except (Exception,KeyboardInterrupt):
            write_private(receipt,canonical(setup_receipt(root,value,'failed')))
            raise
    result = status(root)
    if result['ok'] is not True:fail('RUNTIME_NOT_READY')
    return result
