"""Read-only install plans from real source metadata; no inferred lock entries."""
import hashlib
import hmac
import json
import os
import re
from pathlib import Path

from .security import WorkflowError

ROOT=Path(__file__).resolve().parents[1]
ENGINES=('hyperframes','remotion','all')
CORE_PACKAGES=('hyperframes','ffmpeg-static')
REMOTION_PACKAGES=('remotion','@remotion/cli','@remotion/bundler','@remotion/renderer','react','react-dom')
GRAPH_PATHS={'core':'.','remotion':'optional/remotion'}
REMOTION_NOTICE='Remotion selection requires review of its fixed-version LICENSE.md and current licensing terms: https://www.remotion.dev/docs/license/faq . This notice does not accept an agreement or establish commercial rights.'


def selected_engines(engine):
    if engine not in ENGINES:raise WorkflowError('INSTALL_ENGINE_INVALID')
    return ('hyperframes','remotion') if engine=='all' else (engine,)


def required_packages(engine):
    selected=selected_engines(engine)
    return CORE_PACKAGES+REMOTION_PACKAGES if 'remotion' in selected else CORE_PACKAGES


def selected_graphs(engine):
    return ('core','remotion') if 'remotion' in selected_engines(engine) else ('core',)


def graph_packages(graph):
    if graph not in GRAPH_PATHS:raise WorkflowError('INSTALL_GRAPH_INVALID')
    return CORE_PACKAGES if graph=='core' else REMOTION_PACKAGES


def graph_receipt(graph,lock_sha256,manifest_sha256):
    return {'schema_version':3,'graph':graph,'package_lock_sha256':lock_sha256,
            'package_json_sha256':manifest_sha256,'npm_ci':'complete','required_packages':list(graph_packages(graph))}


def npm_receipt(engine,lock_sha256):
    # Historical receipts never authorize a separated graph installation.
    return {'schema_version':2,'package_lock_sha256':lock_sha256,'npm_ci':'complete',
            'selected_engines':list(selected_engines(engine)),'required_packages':list(required_packages(engine))}


def _pairs(rows):
    value={}
    for key,item in rows:
        if key in value:raise ValueError('Duplicate JSON key')
        value[key]=item
    return value


def _invalid_constant(_):raise ValueError('Invalid JSON constant')


def _json(path):
    try:
        if path.stat().st_size>4*1024*1024:raise ValueError()
        return json.loads(path.read_text(),object_pairs_hook=_pairs,parse_constant=_invalid_constant)
    except (OSError,ValueError,RecursionError,UnicodeError):
        raise WorkflowError('INSTALL_METADATA_INVALID') from None


def graph_plan(graph,*,root=ROOT):
    from .local_state import guard_control
    required=graph_packages(graph);root=Path(root);folder=Path(GRAPH_PATHS[graph])
    package_path=guard_control(root,folder/'package.json');lock_path=guard_control(root,folder/'package-lock.json')
    package=_json(package_path);lock=_json(lock_path)
    if not isinstance(package,dict) or not isinstance(lock,dict):raise WorkflowError('INSTALL_METADATA_INVALID')
    dependencies=package.get('dependencies');packages=lock.get('packages')
    if not isinstance(dependencies,dict) or not isinstance(packages,dict) or not isinstance(packages.get(''),dict):
        raise WorkflowError('INSTALL_METADATA_INVALID')
    matching=packages[''].get('dependencies')==dependencies
    for name,version in dependencies.items():
        entry=packages.get('node_modules/'+name,{})
        if not isinstance(entry,dict):raise WorkflowError('INSTALL_METADATA_INVALID')
        matching=matching and isinstance(version,str) and entry.get('version')==version and isinstance(entry.get('integrity'),str)
    blockers=[]
    if not matching:blockers.append('PACKAGE_LOCK_MISMATCH')
    if set(dependencies)!=set(required):
        blockers.append('REQUIRED_ENGINE_PACKAGES_MISSING')
    remotion=sorted(name for name in packages if name and (name.rsplit('node_modules/',1)[-1].startswith('@remotion/')
                    or name.rsplit('node_modules/',1)[-1] in {'remotion','react','react-dom'}))
    if graph=='core' and remotion:blockers.append('CORE_LOCK_REQUIRES_REMOTION')
    return {'graph':graph,'directory':GRAPH_PATHS[graph],'required_packages':list(required),
            'package_lock_sha256':hashlib.sha256(lock_path.read_bytes()).hexdigest(),
            'package_json_sha256':hashlib.sha256(package_path.read_bytes()).hexdigest(),
            'dependency_graph_ready':not blockers,'blockers':blockers,'remotion_entries':remotion}


def dependency_plan(engine='hyperframes',*,root=ROOT):
    selected=selected_engines(engine);root=Path(root)
    graphs=[graph_plan(graph,root=root) for graph in selected_graphs(engine)]
    blockers=[reason for graph in graphs for reason in graph['blockers']]
    from .probe_runtime import source_recipe
    try:
        if os.name=='nt':
            from .windows_media import recipe
            probe=recipe(root)
        else:probe=source_recipe(root)
        probe_ready=True
    except WorkflowError:probe=None;probe_ready=False;blockers.append('INDEPENDENT_FFPROBE_SOURCE_INVALID')
    return {'requested_engine':engine,'selected_engines':list(selected),'required_packages':list(required_packages(engine)),'default_engine':'hyperframes',
            'skipped_engines':['remotion'] if selected==('hyperframes',) else [],
            'dependency_graph_ready':not blockers,'blockers':blockers,'root_remotion_dependencies':graphs[0]['remotion_entries'],
            'graphs':graphs,'independent_ffprobe':probe,'probe_source_ready':probe_ready,'package_lock_sha256':graphs[0]['package_lock_sha256'],
            'license_notice':REMOTION_NOTICE if 'remotion' in selected else None,'network':False,
            'status':'blocked' if blockers else 'separate_locked_graphs_source_build_probe'}


def source_distribution(manifest):
    """Installation contract, deliberately separate from rights/QA certification."""
    return (isinstance(manifest,dict)
            and type(manifest.get('source_distribution_schema')) is int
            and manifest['source_distribution_schema']==1
            and manifest.get('status')=='installable_source_distribution'
            and manifest.get('customer_release_ready') is False
            and manifest.get('rights_pending') is True
            and manifest.get('publication_ready') is False
            and manifest.get('native_acceptance')=='unverified'
            and manifest.get('browser_acceptance')=='unverified'
            and manifest.get('independent_review')=='pending'
            and isinstance(manifest.get('source_commit'),str)
            and re.fullmatch('[a-f0-9]{40}',manifest['source_commit']) is not None)


def verify_source_files(root,files):
    from .local_state import guard_control
    if not isinstance(files,dict) or not 1<=len(files)<=5000:
        raise WorkflowError('INSTALL_SOURCE_MANIFEST_INVALID')
    required={'LICENSE','THIRD-PARTY-NOTICES.md','assets-lock.json','package.json','package-lock.json',
              'install.sh','tools/first_run.py','storymotion/install_policy.py'}
    if not required.issubset(files):raise WorkflowError('INSTALL_SOURCE_MANIFEST_INVALID')
    for name,digest in files.items():
        if (not isinstance(name,str) or not name or len(name)>512 or name.startswith('/')
                or '\\' in name or ':' in name or re.search(r'[\x00-\x1f\x7f]',name)
                or any(part in {'','.','..'} for part in name.split('/'))
                or not isinstance(digest,str) or not re.fullmatch('[a-f0-9]{64}',digest)):
            raise WorkflowError('INSTALL_SOURCE_MANIFEST_INVALID')
        path=guard_control(root,name)
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
            raise WorkflowError('INSTALL_SOURCE_HASH_MISMATCH')


def owner_terms(root=ROOT):
    root=Path(root)
    try:
        path=root/'LICENSE'
        if path.stat().st_size>256*1024:raise ValueError()
        raw=path.read_bytes();text=raw.decode('utf-8')
    except (OSError,UnicodeError,ValueError):
        return {'ready':False,'text_ready':False,'reason':'OWNER_EULA_PENDING','acceptance_available':False}
    if not text.strip() or re.search(r'(?i)\bTODO\b|placeholder|no commercial license grant',text):
        return {'ready':False,'text_ready':False,'reason':'OWNER_EULA_PENDING','acceptance_available':False}
    digest=hashlib.sha256(raw).hexdigest()
    try:manifest=_json(root/'SOURCE-MANIFEST.json')
    except WorkflowError:manifest={}
    if not isinstance(manifest,dict):manifest={}
    files=manifest.get('files')
    source=source_distribution(manifest)
    if (not source and (manifest.get('customer_release_ready') is not True or manifest.get('rights_pending') is not False)
            or not isinstance(files,dict) or files.get('LICENSE')!=digest):
        return {'ready':False,'text_ready':True,'reason':'OWNER_RELEASE_PENDING','acceptance_available':False,'license_sha256':digest}
    if source:verify_source_files(root,files)
    return {'ready':True,'text_ready':True,'reason':None,'acceptance_available':True,'license_sha256':digest,
            'customer_release_ready':manifest.get('customer_release_ready') is True,
            'distribution':manifest.get('status'),'rights_pending':manifest.get('rights_pending')}


def require_owner_terms(root=ROOT,accepted_sha256=None):
    terms=owner_terms(root)
    if not terms['ready']:raise WorkflowError(terms['reason'])
    if (not isinstance(accepted_sha256,str) or not re.fullmatch('[a-f0-9]{64}',accepted_sha256)
            or not hmac.compare_digest(accepted_sha256,terms['license_sha256'])):
        raise WorkflowError('EULA_ACCEPTANCE_REQUIRED: provide the reviewed source LICENSE file\'s exact SHA256. This legacy error code identifies a missing or mismatched license hash; it does not require acceptance of an additional contract. Download permission and third-party terms are separate.')
    # Preserve the legacy field for callers; both fields identify the same file.
    return {'owner_eula_sha256':terms['license_sha256'],'license_sha256':terms['license_sha256'],
            'scope':'Reviewed source LICENSE hash only; no additional contract or third-party agreement accepted.'}
