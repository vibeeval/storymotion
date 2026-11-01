"""Versioned account contracts for bounded, original-vector production.

Schema/state/repetition checks are executable. Source truth, semantic originality,
natural voice and creative acceptance remain explicit human review gates.
"""
import copy
import json
import re
import unicodedata
from pathlib import Path
from .security import WorkflowError,canonical,digest,finite,scan_bytes

ROOT=Path(__file__).resolve().parents[1]
from .account_packs import ACCOUNTS, load_pack, capability, is_serial
LEGACY_ACTIONS={'unlock','open','reveal','flow'}


def _object(properties):return {'type':'object','properties':properties,'required':list(properties),'additionalProperties':False}
def _string(maximum=1000):return {'type':'string','minLength':1,'maxLength':maximum}
def _array(items,minimum=0,maximum=12):return {'type':'array','items':items,'minItems':minimum,'maxItems':maximum}


def output_schema(account):
    return _schema_for_pack(load_pack(account))


def _schema_for_pack(pack):
    account=pack['id'];serial=pack['series_rules']['enabled']
    character=_object({'id':_string(40),'wardrobe':{'type':'string','enum':[pack['wardrobe']] if pack['wardrobe'] else ['not-used']},
                       'asset_license':{'type':'string','enum':['original_project_vectors']}})
    continuity=_object({'object_id':_string(40),'previous':_string(500),'next':_string(500)}) if serial else {'type':'null'}
    scene=_object({'id':_string(40),'start':{'type':'number','minimum':0,'maximum':90},'end':{'type':'number','minimum':0,'maximum':90},
        'heading':_string(50),'action':{'type':'string','enum':pack['scene_actions']},'information':_string(1200),
        'object_before':_string(500),'object_after':_string(500),'object_id':_string(40),
        'state_before':{'type':'string','enum':list(dict.fromkeys(s['state_before'] for s in pack['scene_contract'].values()))},
        'state_after':{'type':'string','enum':list(dict.fromkeys(s['state_after'] for s in pack['scene_contract'].values()))},
        'character_id':{'type':'string','minLength':1,'maxLength':40} if pack['wardrobe'] else {'type':'null'},
        'camera':{'type':'string','enum':['locked','push-in','follow-object']},
        'rule_ids':_array({'type':'string','enum':pack['rule_ids']},1,8)})
    return _object({'schema_version':{'type':'integer','enum':[1]},'brand':{'type':'string','enum':[account]},
        'title':_string(65),'brief':_string(5000),'demo':{'type':'boolean'},'language':{'type':'string','enum':['tr']},
        'script':_string(10000),'caption':_string(3000),'duration':{'type':'number','minimum':1,'maximum':90},
        'alignment':{'type':'string','enum':['provisional_silent']},'audio':{'type':'null'},
        'claims':_array(_object({'text':_string(2000),'source':_string(100),'scope':_string(1000)}),0,30),
        'continuity':continuity,'scenes':_array(scene,1,12),
        'cues':_array(_object({'start':{'type':'number','minimum':0,'maximum':90},'end':{'type':'number','minimum':0,'maximum':90},'text':_string(95)}),1,100),
        'creative':_object({'pack_version':{'type':'string','enum':[pack['version']]},'topic_id':_string(100),'visual_motif':_string(140),
            'canon_status':{'type':'string','enum':['noncanonical_fixture'] if serial else ['standalone']},
            'characters':_array(character,1 if pack['wardrobe'] else 0,1 if pack['wardrobe'] else 0),
            'asset_policy':{'type':'string','enum':['original_vectors_only']}})})


def _check(value,schema,path='proposal'):
    kind=schema['type']
    match={'object':lambda:isinstance(value,dict),'array':lambda:isinstance(value,list),'string':lambda:isinstance(value,str),
           'number':lambda:type(value) in {int,float},'integer':lambda:type(value) is int,'boolean':lambda:type(value) is bool,'null':lambda:value is None}
    if not match[kind]():raise WorkflowError('Invalid creative field type: '+path)
    if 'enum' in schema and value not in schema['enum']:raise WorkflowError('Creative field outside selected pack: '+path)
    if kind=='object':
        if set(value)!=set(schema['properties']):raise WorkflowError('Creative fields missing or unsupported: '+path)
        for key,item in value.items():_check(item,schema['properties'][key],path+'.'+key)
    elif kind=='array':
        if not schema.get('minItems',0)<=len(value)<=schema.get('maxItems',100):raise WorkflowError('Creative array size outside contract: '+path)
        for item in value:_check(item,schema['items'],path+'[]')
    elif kind=='string':
        if not value.strip() or not schema.get('minLength',1)<=len(value)<=schema.get('maxLength',10000) or '\x00' in value:
            raise WorkflowError('Creative text empty or oversized: '+path)
        if re.search(r'<[^>]*>|(?:javascript|data|file)\s*:|https?://|\b(?:eval|fetch)\s*\(',value,re.I):
            raise WorkflowError('Code, markup and external asset URLs are not creative data: '+path)
    elif kind in {'number','integer'}:finite(value,path,schema.get('minimum',-1e9),schema.get('maximum',1e9))


def _normal_text(value):
    return ' '.join(re.findall(r'\w+',unicodedata.normalize('NFKC',value).casefold(),flags=re.UNICODE))


def audit_audience_copy(account,value):
    """One conservative account wording boundary across all public surfaces.

    This is neither a semantic psychology validator nor source-truth approval.
    Brief/instructions are not audience copy and may quote words to avoid.
    """
    if not capability(account, 'certainty_guard'):return
    surfaces={k:value[k] for k in ('title','script','caption')}
    for i,scene in enumerate(value['scenes']):
        for key in ('heading','information'):surfaces[f'scenes.{i}.{key}']=scene[key]
    for path,text in surfaces.items():
        normalized=' '.join(unicodedata.normalize('NFKC',text).split())
        if re.search(r'\b(?:kesin nedeni|tanısı|bozukluğun var|tedavi eder|her zaman)\b',normalized,re.I):
            raise WorkflowError('Düşünce örneği certainty/diagnosis boundary requires revision: '+path)


def validate_proposal(account,proposal,history=(),source_registry=None):
    """Return a renderable normalized brief; never a publication approval.

    source_registry is a caller-owned ID registry, not model-supplied references.
    A registered ID only proves traceability, never factual correctness.
    """
    pack=load_pack(account)
    if not isinstance(proposal,dict):raise WorkflowError('Creative proposal must be one JSON object')
    try:
        if len(canonical(proposal).encode())>100000 or scan_bytes(canonical(proposal).encode()):raise WorkflowError('Creative proposal too large or contains possible secrets')
    except (TypeError,ValueError):raise WorkflowError('Creative proposal is not bounded JSON') from None
    value=copy.deepcopy(proposal)
    if isinstance(value.get('creative'),dict):value['creative'].pop('audit',None) # Always recomputed by the host.
    _check(value,output_schema(account))
    audit_audience_copy(account,value)
    if value['claims']:
        if not isinstance(source_registry,dict):raise WorkflowError('Factual claims require a caller-owned source registry; no self-declared provenance')
        if any(c['source'] not in source_registry for c in value['claims']):raise WorkflowError('Claim source was not supplied by the caller')
    from .claims import audit_claims
    claim_trace=audit_claims(value,source_registry,fictional=is_serial(account) and value['creative']['canon_status']=='noncanonical_fixture')
    characters=value['creative']['characters'];character_ids={c['id'] for c in characters}
    if any(not re.fullmatch(r'[a-z][a-z0-9-]{0,39}',c) for c in character_ids):raise WorkflowError('Character IDs must be simple, stable IDs')
    ids=set();end=0;object_states={};primary=None;mechanical=pack['initial_state']
    for scene in value['scenes']:
        for field in ['id','object_id']:
            if not re.fullmatch(r'[a-z][a-z0-9-]{0,39}',scene[field]):raise WorkflowError('Creative identifiers must be simple, stable IDs')
        if scene['id'] in ids:raise WorkflowError('Creative scene ID repeated')
        ids.add(scene['id'])
        if abs(scene['start']-end)>.001 or scene['end']-scene['start']<1.6:raise WorkflowError('Creative scenes must be contiguous and >=1.6s')
        end=scene['end']
        if scene['character_id'] is not None and scene['character_id'] not in character_ids:raise WorkflowError('Scene character is not in the pinned cast')
        if set(scene['rule_ids'])-set(pack['rule_ids']):raise WorkflowError('Untracked creative rule')
        if 'CORE-01' not in scene['rule_ids']:raise WorkflowError('Each scene must track the object/camera continuity rule')
        contract=pack['scene_contract'][scene['action']]
        if any(scene[key]!=contract[key] for key in ['state_before','state_after']) or scene['state_before']!=mechanical:
            raise WorkflowError('Scene state IDs contradict the compiled object mechanism')
        mechanical=scene['state_after']
        oid=scene['object_id']
        if oid in object_states and scene['object_before']!=object_states[oid]:raise WorkflowError('Object state continuity broken')
        object_states[oid]=scene['object_after'];primary=primary or oid
        if oid!=primary:raise WorkflowError('Bounded AccountPack preserves one primary object across all scenes')
    if abs(end-value['duration'])>.001:raise WorkflowError('Creative scenes must cover duration')
    if mechanical!=pack['final_state']:raise WorkflowError('The bounded mechanism must reach its final state')
    if value['continuity']:
        continuity=value['continuity']
        if continuity['object_id']!=primary or continuity['previous']!=value['scenes'][0]['object_before'] or continuity['next']!=value['scenes'][-1]['object_after']:
            raise WorkflowError('Pinned serial continuity does not match the same object and states')
        if any(s['object_id']!=primary for s in value['scenes']):raise WorkflowError('Serial rehearsal must preserve its primary object')
    last=0
    for cue in value['cues']:
        if cue['start']<last or cue['end']<=cue['start'] or cue['end']>value['duration']+.001:raise WorkflowError('Creative subtitle times overlap or escape the timeline')
        last=cue['end']
    if ' '.join(c['text'] for c in value['cues']).split()!=value['script'].split():raise WorkflowError('Creative cues must preserve the exact full script')
    script_sha=digest(_normal_text(value['script']))
    visual_signature=digest({'account':account,'family':pack['visual_family'],'actions':[s['action'] for s in value['scenes']],
        'camera':[s['camera'] for s in value['scenes']],'cast_count':len(characters)})
    history=list(history or ())
    if len(history)>1000:raise WorkflowError('History window exceeds bounded creative audit')
    checked=0
    for previous in history:
        if not isinstance(previous,dict):raise WorkflowError('Creative history must contain records')
        if previous.get('account',previous.get('brand',account))!=account:continue
        checked+=1
        prior_creative=previous.get('creative',{})
        if not isinstance(prior_creative,dict):raise WorkflowError('Creative history metadata must be objects')
        audit=previous.get('audit',prior_creative.get('audit',previous))
        if not isinstance(audit,dict):raise WorkflowError('Creative history metadata must be objects')
        topic=previous.get('topic_id',prior_creative.get('topic_id',''));motif=previous.get('visual_motif',prior_creative.get('visual_motif',''))
        prior_script=audit.get('script_sha256') or (digest(_normal_text(previous['script'])) if previous.get('script') else None)
        if prior_script==script_sha or audit.get('visual_signature')==visual_signature:
            raise WorkflowError('Repeated script or compiled visual sequence; rename alone is not a new concept')
        if topic and _normal_text(topic)==_normal_text(value['creative']['topic_id']) or motif and _normal_text(motif)==_normal_text(value['creative']['visual_motif']):
            raise WorkflowError('Topic or visual motif repeats supplied history; revise the concept')
    value['creative']['audit']={'script_sha256':script_sha,'visual_signature':visual_signature,'history_entries_checked':checked,
        'source_truth':'pending_human_review','semantic_originality':'pending_human_review','creative_acceptance':'pending_human_review','publication_ready':False}
    if value['claims']:value['creative']['audit']['claim_traceability']=claim_trace
    return value
