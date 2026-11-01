"""Read-only source/rule/code/test projection, never an approval authority."""
import copy
import json
from collections import Counter
from pathlib import Path
from .creative import ACCOUNTS,load_pack
from .provenance import execution_provenance
from .security import WorkflowError,within,scan_bytes

ROOT=Path(__file__).resolve().parents[1]
STATUSES={'bounded','partial','missing','unverified','not_applicable'}
STAGES={'sources','script','brand','scenes','continuity','voice','timing','viseme','edit','cover','qa','export'}


def _file(path):
    if not isinstance(path,str) or not path or Path(path).is_absolute() or '..' in Path(path).parts:
        raise WorkflowError('Workflow evidence path must be a project-relative file')
    resolved=within(ROOT,path)
    if not resolved.is_file() or (ROOT/path).is_symlink():raise WorkflowError('Workflow code/test reference is missing')


def validate_matrix(value):
    """Reject stale/optimistic projection data instead of showing false readiness."""
    if not isinstance(value,dict) or value.get('schema_version')!=1 or set(value.get('scope',[]))!=set(ACCOUNTS):
        raise WorkflowError('Workflow matrix scope/schema changed')
    if value.get('ready_for_publication') is not False:raise WorkflowError('Workflow inventory cannot grant publication approval')
    profiles=value.get('profiles',[]);sources=value.get('sources',[])
    if len(profiles)!=len(ACCOUNTS) or {p.get('account') for p in profiles}!=set(ACCOUNTS):raise WorkflowError('Workflow matrix must contain unique profiles')
    source_ids=[s.get('id') for s in sources]
    if not source_ids or len(source_ids)!=len(set(source_ids)) or any(s.get('raw_distributed') is not False for s in sources):
        raise WorkflowError('Workflow source metadata must exclude raw references')
    for profile in profiles:
        pack=load_pack(profile['account'])
        if profile.get('pack_version')!=pack['version'] or profile.get('source_revision')!=pack['source_revision']:
            raise WorkflowError('Workflow projection is stale for this AccountPack')
        if profile.get('publication_ready') is not False or profile.get('product_acceptance')!='incomplete':
            raise WorkflowError('Workflow inventory cannot complete human/product acceptance')
        rows=profile.get('stages',[])
        if len(rows)!=len(STAGES) or {r.get('id') for r in rows}!=STAGES:raise WorkflowError('Workflow stages missing or duplicated')
        for row in rows:
            if row.get('status') not in STATUSES or row.get('next_phase') not in range(1,7):raise WorkflowError('Unknown workflow status/phase')
            for key in ('label','implemented_scope','remaining'):
                if not isinstance(row.get(key),str) or not 1<=len(row[key])<=3000:raise WorkflowError('Workflow scope/bounds must be explicit')
            for key in ('code','tests','sources','rules','acceptance'):
                if not isinstance(row.get(key),list) or not row[key] or len(row[key])!=len(set(row[key])):
                    raise WorkflowError('Workflow traceability list must be nonempty and unique')
            if set(row['sources'])-set(source_ids) or set(row['rules'])-set(pack['rule_ids']):raise WorkflowError('Unknown workflow source/rule reference')
            for path in row['code']+row['tests']:_file(path)
            if row.get('native_evidence_scope') not in {'none','baseline_tone_fixture','synthetic_tones_only'}:
                raise WorkflowError('Workflow evidence must identify its limited historical scope')
    _file(value.get('phase_plan'))
    return value


def build_matrix():
    profiles=[]
    for account in ACCOUNTS:
        pack=load_pack(account)
        rows=[{'id':stage,'label':stage,'status':'missing','next_phase':1,
               'implemented_scope':'Neutral technical example only; a custom production procedure is not configured.',
               'remaining':'Human review and native acceptance remain incomplete.',
               'code':['storymotion/account_packs.py'],'tests':['tests/test_accountpacks.py'],
               'sources':['OWNER_METHOD_TODO'],'rules':[pack['rule_ids'][0]],
               'acceptance':['pending'],'native_evidence_scope':'none'} for stage in sorted(STAGES)]
        profiles.append({'account':account,'topic':pack['display_name'],'pack_version':pack['version'],'source_revision':pack['source_revision'],
                         'publication_ready':False,'product_acceptance':'incomplete','stages':rows})
    return {'schema_version':1,'scope':list(ACCOUNTS),'ready_for_publication':False,
            'profiles':profiles,'sources':[{'id':'OWNER_METHOD_TODO','raw_distributed':False}],
            'phase_plan':'docs/PLAN.md','matrix_version':'neutral-technical-1',
            'baseline':{'execution_fingerprint':'0'*64},
            'rule_tracking_limit':'A custom production procedure is not configured; human review remains required.'}


def workflow_status(account=None):
    if account is not None and account not in ACCOUNTS:raise WorkflowError('Choose a valid workflow profile ID')
    try:
        value=validate_matrix(build_matrix())
    except (OSError,ValueError,KeyError,TypeError):raise WorkflowError('Workflow projection unavailable; acceptance is unknown') from None
    profiles=[copy.deepcopy(p) for p in value['profiles'] if account is None or p['account']==account]
    for profile in profiles:profile['counts']=dict(Counter(r['status'] for r in profile['stages']))
    current=execution_provenance()['fingerprint']
    return {'matrix_version':value['matrix_version'],'profiles':profiles,'sources':value['sources'],
        'baseline':value['baseline'],'current_execution_fingerprint':current,
        'baseline_execution_matches':current==value['baseline']['execution_fingerprint'],
        # A status page or old fixture receipt never approves a new checkpoint.
        'current_native_acceptance':'unverified','product_acceptance':'incomplete','publication_ready':False,
        'rule_tracking_limit':value['rule_tracking_limit'],'phase_plan':value['phase_plan']}
