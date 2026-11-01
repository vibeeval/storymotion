"""Install/check project-local tools. No provider, key, global npm, or hidden npx fallback."""
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from .security import WorkflowError, within
from .platform_support import platform_status, require_platform
from .install_policy import dependency_plan,graph_packages,graph_receipt,required_packages,selected_engines

ROOT = Path(__file__).resolve().parents[1]
ENGINES = ('hyperframes', 'remotion')


def media_binary(name,engine='all'):
    """Engine readiness uses pinned local files; standalone tools retain command names."""
    selected_engines(engine)
    from . import development_policy as dev
    if dev.development_mode(ROOT) and name in ('ffmpeg','ffprobe'):
        dev.assert_process_scope(ROOT)
        if engine!='hyperframes':raise WorkflowError('DEVELOPMENT_SCOPE_REFUSED')
        from .ffmpeg_runtime import status as source_status
        from .development_probe import status as probe_status
        status=source_status(ROOT) if name=='ffmpeg' else probe_status(ROOT)
        if not status['ready']:raise WorkflowError('DEVELOPMENT_MEDIA_NOT_READY')
        return str(ROOT/status['path']) if name=='ffmpeg' else status['binary']
    if os.name=='nt' and name in {'ffmpeg','ffprobe'}:
        from .windows_media import status
        state=status(ROOT)
        return state['ffmpeg' if name=='ffmpeg' else 'binary'] if state['ready'] else name
    if name=='ffmpeg':
        path=ROOT/'node_modules/ffmpeg-static/ffmpeg'
        return str(path) if path.is_file() and os.access(path,os.X_OK) else name
    if name=='ffprobe':
        from .probe_runtime import probe_status
        status=probe_status(ROOT)
        return status['binary'] if status['ready'] else name
    return name


def process_env(engine='all'):
    selected_engines(engine)
    from . import development_policy as dev
    if dev.development_mode(ROOT):
        dev.assert_process_scope(ROOT)
        from .development_setup import status as development_status,filtered_env
        state=development_status(ROOT,'hyperframes')
        if state['ok'] is not True or engine!='hyperframes':raise WorkflowError('DEVELOPMENT_RUNTIME_NOT_READY')
        env=filtered_env(ROOT,create=True);browser=str(ROOT/state['browser']['path'])
        env.update(HYPERFRAMES_BROWSER_PATH=browser,PRODUCER_HEADLESS_SHELL_PATH=browser,STORYMOTION_BROWSER=browser,
                   HYPERFRAMES_FFMPEG_PATH=media_binary('ffmpeg','hyperframes'),HYPERFRAMES_FFPROBE_PATH=media_binary('ffprobe','hyperframes'))
        return env
    allowed={'PATH','HOME','USER','LOGNAME','TMPDIR','TMP','TEMP','LANG','LC_ALL','SHELL','SYSTEMROOT','SystemRoot','USERPROFILE','LOCALAPPDATA','APPDATA','PATHEXT','COMSPEC','ComSpec','PYTHONUTF8'}
    env={k:v for k,v in os.environ.items() if k in allowed}
    env.update(HYPERFRAMES_TELEMETRY_DISABLED='1',DO_NOT_TRACK='1')
    if os.name=='nt':env.update(STORYMOTION_PYTHON=sys.executable,PYTHONUTF8='1')
    # These paths are controlled project files, never a credential/config search.
    manifest = ROOT/'.runtime/runtime.json'
    if manifest.is_file():
        try:
            p = within(ROOT, json.loads(manifest.read_text())['browser'])
            if p.is_file():
                env['HYPERFRAMES_BROWSER_PATH'] = str(p)
                env['PRODUCER_HEADLESS_SHELL_PATH'] = str(p)
                env['STORYMOTION_BROWSER'] = str(p)
        except (ValueError, KeyError, OSError, WorkflowError):
            pass  # Doctor provides the actionable error before render.
    for name in ['ffmpeg', 'ffprobe']:
        binary = media_binary(name,engine)
        if binary != name:
            env['HYPERFRAMES_'+name.upper()+'_PATH'] = binary
    return env


def packages_ready(state,engine):
    required=required_packages(engine)
    packages=state.get('packages') if isinstance(state,dict) else None
    return (isinstance(packages,dict) and all(isinstance(packages.get(name),dict)
            and packages[name].get('ok') is True for name in required))


def doctor(engine='hyperframes'):
    requested=selected_engines(engine)
    from . import development_policy as dev
    if dev.development_mode(ROOT):
        from .development_setup import status as development_status
        return development_status(ROOT,engine)
    compatibility=platform_status()
    if not compatibility['supported']:
        return {'ok':False,'error':compatibility['error'],'compatibility':compatibility,
                'engines':{name:{'ready':False} for name in ENGINES},'network_during_inspection':False}
    if not shutil.which('node'):
        return {'ok':False, 'error':'Node.js 22.23.2–22.x is required. Install Node from nodejs.org, then run setup.',
                'engines':{name:{'ready':False} for name in ENGINES}, 'network_during_inspection':False}
    try:
        result = subprocess.run(['node', str(ROOT/'tools/runtime.mjs'), 'inspect','--engine',engine], cwd=ROOT,
                                env=process_env(engine), capture_output=True, timeout=60)
        data = json.loads(result.stdout)
    except (OSError, subprocess.TimeoutExpired, ValueError):
        raise WorkflowError('Runtime inspection failed. Node 22.23.2–22.x and the extracted tools/ files are required.')
    node_major = int(data.get('node','v0').lstrip('v').split('.')[0])
    data.update(python=sys.version.split()[0], requested_engine=engine,
                ok=result.returncode==0 and node_major==22 and packages_ready(data,engine)
                   and all(data['engines'][n]['ready'] is True for n in requested),
                live_generation='disabled', compatibility=compatibility,
                supported='Windows 10/11 x64 local NTFS; macOS arm64/x64 and Linux glibc arm64/x64; native acceptance unverified')
    return data


def require_engine(engine):
    from . import development_policy as dev
    if dev.development_mode(ROOT):dev.assert_process_scope(ROOT)
    status = doctor(engine)
    if not status['ok']:
        raise WorkflowError(f'{engine} local runtime missing, stale or unsupported. Review install.sh preflight and CONFIGURATION.md; setup --engine {engine} does not bypass dependency or rights blockers.')


def graph_receipt_path(root,graph):
    from .local_state import guard_control
    graph_packages(graph)
    return guard_control(root,'.runtime/npm-'+graph+'.json')


def installed_graph_packages(root,graph):
    from .install_policy import GRAPH_PATHS
    from .local_state import guard_control
    graph_packages(graph)
    folder=Path(root)/GRAPH_PATHS[graph]
    try:
        manifest=json.loads((folder/'package.json').read_text())['dependencies']
        for name in graph_packages(graph):
            path=guard_control(root,(folder/'node_modules'/name/'package.json').relative_to(root))
            if path.stat().st_size>1024*1024 or json.loads(path.read_text()).get('version')!=manifest[name]:return False
        return True
    except (OSError,ValueError,KeyError,TypeError,RecursionError,UnicodeError):return False


def graph_npm_ready(root,graph):
    try:
        path=graph_receipt_path(root,graph['graph'])
        if path.stat().st_size>65536:return False
        value=json.loads(path.read_text())
        return (isinstance(value,dict) and type(value.get('schema_version')) is int
                and value==graph_receipt(graph['graph'],graph['package_lock_sha256'],graph['package_json_sha256'])
                and installed_graph_packages(root,graph['graph']))
    except (OSError,ValueError,RecursionError,UnicodeError):return False


def install_graphs(engine='hyperframes',*,root=ROOT,skip_npm=False):
    """Caller holds the setup lock and download/rights authorization boundary."""
    from .engine import checked_process
    from .security import file_hash,write_json
    from .local_state import guard_control
    from .development_policy import development_mode
    if development_mode(root):raise WorkflowError('DEVELOPMENT_LEGACY_SETUP_REFUSED')
    root=Path(root);plan=dependency_plan(engine,root=root)
    if not plan['dependency_graph_ready']:raise WorkflowError('DEPENDENCY_PLAN_BLOCKED: '+','.join(plan['blockers']))
    if skip_npm and not all(graph_npm_ready(root,g) for g in plan['graphs']):
        raise WorkflowError('RUNTIME_NPM_RECEIPT_REQUIRED: each selected graph needs matching completed metadata and packages')
    actions=[];runtime=root/'.runtime'
    for graph in plan['graphs']:
        if graph_npm_ready(root,graph):actions.append({'graph':graph['graph'],'action':'reused'});continue
        receipt=graph_receipt_path(root,graph['graph'])
        if receipt.exists():receipt.unlink()
        for name in ('empty-user.npmrc','empty-global.npmrc'):guard_control(root,Path('.runtime')/name).write_text('')
        folder=root/graph['directory']
        checked_process(['npm','ci','--no-audit','--no-fund','--registry=https://registry.npmjs.org',
                         '--cache='+str(runtime/'npm-cache'),'--userconfig='+str(runtime/'empty-user.npmrc'),
                         '--globalconfig='+str(runtime/'empty-global.npmrc'),'--fetch-timeout=30000','--fetch-retries=0'],folder,900)
        if (file_hash(folder/'package-lock.json')!=graph['package_lock_sha256']
                or file_hash(folder/'package.json')!=graph['package_json_sha256']):raise WorkflowError('RUNTIME_LOCK_CHANGED_DURING_SETUP')
        if not installed_graph_packages(root,graph['graph']):raise WorkflowError('RUNTIME_PACKAGES_NOT_READY')
        write_json(receipt,graph_receipt(graph['graph'],graph['package_lock_sha256'],graph['package_json_sha256']))
        actions.append({'graph':graph['graph'],'action':'installed'})
    return actions


def setup(skip_npm=False, *, if_needed=False,engine='hyperframes'):
    from .development_policy import development_mode
    if development_mode(ROOT):raise WorkflowError('DEVELOPMENT_LEGACY_SETUP_REFUSED')
    selected_engines(engine);require_platform()
    if not shutil.which('node') or not shutil.which('npm'):raise WorkflowError('Install Node.js22.23.2–22.x first; no OS packages are installed')
    from .local_state import guard_project_scope,guard_control
    from .probe_runtime import install_probe,probe_status,toolchain
    guard_project_scope(ROOT)
    plan=dependency_plan(engine,root=ROOT)
    if not plan['dependency_graph_ready']:raise WorkflowError('DEPENDENCY_PLAN_BLOCKED: '+','.join(plan['blockers']))
    if os.name!='nt' and not probe_status(ROOT)['ready']:toolchain()
    version=subprocess.check_output(['node','--version'],text=True,timeout=10,env=process_env(engine)).strip()
    parts=tuple(int(v) for v in version.lstrip('v').split('.')[:3])
    if not (parts>=(22,23,2) and parts[0]==22):raise WorkflowError('Node.js22.23.2–22.x required; no global renderer fallback')
    runtime=guard_control(ROOT,'.runtime','dir')
    from .local_state import private_directory
    private_directory(runtime)
    from .store import Store
    with Store(runtime/'setup-state') as store,store.lock():
        guard_project_scope(ROOT)
        if if_needed:
            current=doctor(engine)
            if current['ok'] and all(graph_npm_ready(ROOT,g) for g in plan['graphs']):
                return dict(current,setup='reused_ready_project_local',paid_provider_calls=0)
        actions=install_graphs(engine,root=ROOT,skip_npm=skip_npm)
        probe=install_probe(ROOT,allow_downloads=True)
        from .engine import checked_process
        checked_process(['node',ROOT/'tools/runtime.mjs','setup','--engine',engine],ROOT,900)
    result=doctor(engine)
    if not result['ok']:raise WorkflowError('Selected runtime setup incomplete; no engine fallback was used')
    result.update(setup='complete_project_local',paid_provider_calls=0,graph_actions=actions,probe_action=probe['action'])
    return result
