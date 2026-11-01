"""Disabled historical private fixture profile in this source distribution.

Its excluded CI policy/evidence and old license binding are not portable
approvals. Detect old private namespaces and refuse them without falling back
to the public runtime; public customer setup keeps its own gates.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import platform
import re
import shutil
import sys
import uuid

from .family_jobs import read_owned
from .local_state import guard_control, guard_project_scope
from .security import WorkflowError, canonical, digest, file_hash

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_PROFILE_AVAILABLE = False
PRIVATE_PROFILE_REASON = 'PRIVATE_PROFILE_NOT_DISTRIBUTED'
POLICY_PATH = 'ci/hf-development-policy.json'
POLICY_SHA = '5fb8ded307f2f111201a4e764c68668f839f8687db824250bfd0f3a6bf82faee'
EVIDENCE_PATH = 'ci/hf-development-evidence.json'
EVIDENCE_SHA = 'd132d5b9675daf93e006fd8a7621d5142e8f222f116b27e44f85bed44039d0ed'
RECIPE_PATH = 'renderers/ffmpeg-source.json'
RECIPE_SHA = '9a64dae21b2115e46158520fcb983705bc784970480fbec304840fb423bd67bb'
PROVIDER = 'source-ffmpeg-8.1.3-x264-b35605a'
FIXTURE = 'fixtures/turkish-font-smoke.json'
FIXTURE_SHA = '92a04ed2faad9018addf20d13150733007d3f7131b68420c79f287de7c51be46'
LICENSE_SHA = '5ecd8a56929f982bf1cfae4c7e5a7aedf3c31c13e8355bedab67ce0d70055682'
MODE = '.runtime/development/mode.json'
FLAGS = ('owner_eula_accepted','third_party_terms_accepted','customer_installation','native_acceptance',
         'customer_acceptance','creative_acceptance','publication_ready','commercial_clearance')
_RUN = ContextVar('development_fixture_run', default=None)


def require_private_profile():
    raise WorkflowError(PRIVATE_PROFILE_REASON)


def fail(code):
    raise WorkflowError('DEVELOPMENT_' + code)


def strict_json(root, relative, maximum=512*1024):
    def pairs(rows):
        value = {}
        for key, item in rows:
            if key in value or key in ('__proto__','prototype','constructor'):fail('METADATA_INVALID')
            value[key] = item
        return value
    try:
        raw = read_owned(Path(root), relative, maximum)
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=lambda _: fail('METADATA_INVALID'))
        nodes = [0]
        def visit(item, depth=0):
            nodes[0] += 1
            if depth>12 or nodes[0]>30000:fail('METADATA_INVALID')
            if isinstance(item,dict):
                for child in item.values():visit(child,depth+1)
            elif isinstance(item,list):
                for child in item:visit(child,depth+1)
            elif item is not None and type(item) not in (str,int,bool):fail('METADATA_INVALID')
            elif type(item) is int and abs(item)>9007199254740991:fail('METADATA_INVALID')
        visit(value)
        return value, hashlib.sha256(raw).hexdigest()
    except (OSError, ValueError, TypeError, RecursionError, UnicodeError):fail('METADATA_INVALID')


def development_mode(root=ROOT):
    # A missing/changed mode receipt must not turn source mode into static/PATH.
    root = Path(root)
    for name in ('.runtime/development','.runtime/ffmpeg'):
        path = root/name
        if path.exists() or path.is_symlink():return True
    return False


def recipe(root=ROOT):
    require_private_profile()
    value, sha = strict_json(root, RECIPE_PATH, 32768)
    if sha!=RECIPE_SHA or type(value) is not dict or value.get('provider')!=PROVIDER:fail('RECIPE_CHANGED')
    for name, expected in value['license_files'].items():
        if file_hash(guard_control(root,name))!=expected:fail('LICENSE_CHANGED')
    return value


def policy(root=ROOT, engine='hyperframes', fixture=FIXTURE):
    require_private_profile()
    root = Path(root).absolute()
    if root!=root.resolve():fail('ROOT_INVALID')
    guard_project_scope(root)
    if engine!='hyperframes' or fixture!=FIXTURE:fail('SCOPE_REFUSED')
    if platform.system()!='Darwin' or platform.machine()!='arm64':fail('PLATFORM_REFUSED')
    if sys.version_info<(3,9):fail('PYTHON_REQUIRED')
    value, sha = strict_json(root,POLICY_PATH)
    expected = {'schema_version','id','source_basis','research_basis','engine','platform','architecture',
                'fixture','fixture_sha256','provider','npm_mode','lifecycle_allowlist','allowed_operations',
                'minimum_free_bytes','gsap_scope','excluded_uses','probe_bootstrap','flags','reviewed_files'}
    if (type(value) is not dict or set(value)!=expected or sha!=POLICY_SHA
            or type(value['schema_version']) is not int or value['schema_version']!=1
            or value['engine']!=engine or value['platform']!='Darwin' or value['architecture']!='arm64'
            or value['fixture']!=FIXTURE or value['fixture_sha256']!=FIXTURE_SHA or value['provider']!=PROVIDER
            or value['npm_mode']!='ignore_scripts' or value['lifecycle_allowlist']!=[]
            or value['allowed_operations']!=['npm','setup','render']
            or value['probe_bootstrap']!={'provider':'source-ffprobe-8.1.3-lgpl-private-silent-v1',
                'recipe':'renderers/ffprobe-source.json','recipe_sha256':'2354151b834791ba3b00d29301c15b0d03236ca0b4f6a4b1bcc65fce42eaccbd',
                'namespace':'.runtime/development/probe','profile':'private-generated-silence-v1',
                'fixture_sha256':'643f8a8dc8bd9c19225afffad2becfec5426180b3749cb208abdf1a6c8354efc',
                'repository_media':False,'build_strategy':'in_source_no_links'}
            or type(value['minimum_free_bytes']) is not int or value['minimum_free_bytes']!=6442450944
            or type(value['flags']) is not dict or set(value['flags'])!=set(FLAGS)
            or any(v is not False for v in value['flags'].values())):fail('POLICY_CHANGED')
    from tools.check_assets import verify_assets
    from .install_policy import dependency_plan
    verify_assets(root)
    if not dependency_plan('hyperframes',root=root)['dependency_graph_ready']:fail('DEPENDENCY_PLAN_BLOCKED')
    reviewed = value['reviewed_files']
    if type(reviewed) is not dict or not reviewed:fail('SOURCE_BINDING_MISSING')
    for name, expected_sha in reviewed.items():
        if (not isinstance(name,str) or not re.fullmatch('[A-Za-z0-9_./-]+',name)
                or type(expected_sha) is not str or not re.fullmatch('[a-f0-9]{64}',expected_sha)
                or file_hash(guard_control(root,name))!=expected_sha):fail('SOURCE_CHANGED')
    if file_hash(guard_control(root,'LICENSE'))!=LICENSE_SHA:fail('OWNER_TEXT_CHANGED')
    if file_hash(guard_control(root,FIXTURE))!=FIXTURE_SHA:fail('FIXTURE_CHANGED')
    source, _ = strict_json(root,FIXTURE,32768)
    if source.get('audio') is not None or source.get('demo') is not True or source.get('alignment')!='provisional_silent' or source.get('duration')!=3:fail('FIXTURE_CHANGED')
    installation_artifacts(root)
    recipe(root)
    return value


def installation_artifacts(root):
    require_private_profile()
    # npm installs compatible optional lock entries even when their parent
    # platform wrapper is omitted. Runtime reachability is not an inventory.
    evidence, evidence_sha = strict_json(root,EVIDENCE_PATH)
    if evidence_sha!=EVIDENCE_SHA or type(evidence) is not dict:fail('EVIDENCE_CHANGED')
    lock, lock_sha = strict_json(root,'package-lock.json',4*1024*1024)
    if lock_sha!=evidence['package_lock_sha256']:fail('GRAPH_CHANGED')
    rows = evidence['artifacts']
    if type(rows) is not dict or len(rows)!=94:fail('EVIDENCE_CHANGED')
    compatible = {path for path, entry in lock['packages'].items() if path
                  and ('os' not in entry or 'darwin' in entry['os'])
                  and ('cpu' not in entry or 'arm64' in entry['cpu'])}
    if set(rows)!=compatible:fail('GRAPH_CHANGED')
    for path, row in rows.items():
        entry = lock['packages'][path]
        if (row['name']!=path.rsplit('node_modules/',1)[1]
                or (entry.get('version'),entry.get('resolved'),entry.get('integrity'))
                !=(row['version'],row['url'],row['integrity'])):fail('GRAPH_CHANGED')
        if row['evidence_class'] not in ('package_text','pinned_upstream_text','publisher_declaration'):fail('EVIDENCE_CHANGED')
    return rows


def binding(root, value):
    require_private_profile()
    # The validator/pure JS checker contain the policy digest; exclude that
    # self-reference from the policy, and bind their actual bytes in receipts.
    return digest({'policy':POLICY_SHA,'files':value['reviewed_files'],
                   'validator':file_hash(guard_control(root,'storymotion/development_policy.py')),
                   'js_validator':file_hash(guard_control(root,'tools/development-runtime.mjs'))})


def gate(root=ROOT,engine='hyperframes',fixture=FIXTURE):
    value = policy(root,engine,fixture)
    return {'ok':True,'scope':'fixed private silent HF development fixture only','policy_sha256':POLICY_SHA,
            'source_binding':binding(root,value),'provider':PROVIDER,'fixture':FIXTURE,
            'operations_authorized':False,'network':False,'provider_calls':0,'runtime_payment':0,
            **value['flags']}


@dataclass(frozen=True)
class Approval:
    root: str
    policy_sha256: str
    source_binding: str
    operation: str
    nonce: str


def authorize(root, operation, approved=False, approved_policy_sha256=None):
    require_private_profile()
    value = policy(root)
    if operation not in value['allowed_operations']:fail('OPERATION_REFUSED')
    if approved is not True or approved_policy_sha256!=POLICY_SHA:fail('OPERATION_APPROVAL_REQUIRED')
    return Approval(str(Path(root).resolve()),POLICY_SHA,binding(root,value),operation,uuid.uuid4().hex)


def require_approval(root, approval, operation):
    require_private_profile()
    if not re.fullmatch(r'/[A-Za-z0-9_./-]+',str(Path(root).absolute())):fail('BUILD_ROOT_UNREVIEWED')
    value = policy(root)
    if (type(approval) is not Approval or approval.root!=str(Path(root).resolve())
            or approval.policy_sha256!=POLICY_SHA or approval.source_binding!=binding(root,value)
            or approval.operation!=operation):fail('OPERATION_APPROVAL_REQUIRED')
    return value


def disk_preflight(root, approval, operation):
    require_private_profile()
    value = require_approval(root,approval,operation)
    free = shutil.disk_usage(root).free
    if free<value['minimum_free_bytes']:fail('DISK_HEADROOM_REQUIRED')
    return {'free_bytes':free,'minimum_free_bytes':value['minimum_free_bytes'],'upper_bound_guaranteed':False}


@contextmanager
def fixture_run(root, workspace, approval):
    require_private_profile()
    if catalog_run_active():fail('CROSS_PROFILE_REFUSED')
    require_approval(root,approval,'render')
    workspace = Path(workspace)
    relative = workspace.relative_to(Path(root))
    if not re.fullmatch(r'work/development-hf/[a-f0-9]{32}',str(relative)):fail('OUTPUT_SCOPE_REFUSED')
    guard_control(root,relative,'dir')
    token = _RUN.set((str(Path(root).resolve()),str(workspace),approval))
    try:yield
    finally:_RUN.reset(token)


def glyph_run_active():return _RUN.get() is not None


def catalog_run_active():
    try:
        from .catalog_test_policy import active
    except ModuleNotFoundError as error:
        if error.name!='storymotion.catalog_test_policy':raise
        return False  # The private-only profile is excluded from customer ZIPs.
    return active()


def assert_process_scope(root=ROOT):
    if development_mode(root):require_private_profile()
    if catalog_run_active():
        from .catalog_test_policy import assert_process_scope as catalog_scope
        catalog_scope(root);return
    if not development_mode(root):return
    run = _RUN.get()
    if run is None or run[0]!=str(Path(root).resolve()):fail('FIXTURE_RUN_APPROVAL_REQUIRED')
    require_approval(root,run[2],'render')


def assert_job_scope(engine, job, until):
    if development_mode(ROOT):require_private_profile()
    if catalog_run_active():
        from .catalog_test_policy import assert_job_scope as catalog_scope
        catalog_scope(engine,job,until);return
    if not development_mode(ROOT):return
    if until=='prepare':return
    assert_process_scope(ROOT)
    run = _RUN.get()
    if str(engine.store.root)!=run[1]:fail('OUTPUT_SCOPE_REFUSED')
    expected, payload = engine.plan(ROOT/FIXTURE,render_engine='hyperframes')
    if job!=expected or digest(engine.payload(job))!=digest(payload):fail('FIXTURE_CHANGED')
