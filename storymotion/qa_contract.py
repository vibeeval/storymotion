"""Pure QA data contract and deterministic frame plan; no capture or tool runner.

The caller must build the plan and artifact manifest from trusted local work.
Validating JSON cannot establish that a human watched, OCR ran or pixels match a
statement. Those execution bridges deliberately remain outside this module.
"""
import math
import re
import unicodedata
from decimal import Decimal,ROUND_HALF_UP
from pathlib import PurePosixPath
from .security import WorkflowError,canonical,digest,finite,scan_bytes

CONTRACT_VERSION='qa-review-1'
UPSTREAM_COMMIT='549f745959d29e0452b238ac23d98b1cc2cdcfb3'
REQUIRED_CHECKS=('technical_decode','delivery_spec','animation_keyframes','source_claims',
    'subtitle_alignment','turkish_ocr','visual_review','human_listening','human_final_watch')
ORDERS=('forward','reverse','permuted')
# Data-only future import capabilities. No upstream CLI command is authorized.
OPTIONAL_IMPORT_ALLOWLIST=('version_metadata','saved_local_measurements')


def _hash(value):return isinstance(value,str) and re.fullmatch(r'[0-9a-f]{64}',value) is not None
def _id(value):return isinstance(value,str) and re.fullmatch(r'[a-z][a-z0-9-]{0,79}',value) is not None
def _path(value):
    if not isinstance(value,str) or not 1<=len(value)<=240 or not re.fullmatch(r'[A-Za-z0-9_./-]+',value):return False
    p=PurePosixPath(value)
    return not p.is_absolute() and '..' not in p.parts and '.' not in p.parts and p.suffix in {'.png','.json','.txt'}
def _assets(value):
    if not isinstance(value,dict) or not 1<=len(value)<=1000:raise WorkflowError('QA requires a bounded caller-owned asset hash map')
    if any(not isinstance(k,str) or not re.fullmatch(r'[A-Za-z0-9_./-]{1,240}',k) or PurePosixPath(k).is_absolute() or '..' in PurePosixPath(k).parts or not _hash(v) for k,v in value.items()):
        raise WorkflowError('Invalid QA asset hash map')
    return dict(sorted(value.items()))
def _frame(seconds,fps):return int((Decimal(str(seconds))*fps).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
def _text(value):return ' '.join(unicodedata.normalize('NFC',value).split())


def build_sampling_plan(brief,render_sha256,asset_hashes,*,fps=30,seed=0,width=1080,height=1920,
                        board_capacity=12,scene_keyframes=None,issue_frames=(),source_fingerprint=None):
    """Plan exact integer frames; explicit animation keyframes must come from host.

    Default scene start/mid/last + cut boundary before/at/after + cue midpoints
    are always included. Missing declared animation keyframes/source pin keeps
    the plan incomplete. No browser, MP4, OCR or provider is accessed.
    """
    if not isinstance(brief,dict) or not _hash(render_sha256):raise WorkflowError('QA plan requires a brief and final MP4 SHA-256')
    if type(fps) is not int or not 1<=fps<=120 or type(seed) is not int or not 0<=seed<=2147483647:raise WorkflowError('Invalid QA frame rate or seed')
    if any(type(v) is not int or not 1<=v<=8192 for v in (width,height)) or type(board_capacity) is not int or not 1<=board_capacity<=24:raise WorkflowError('Invalid QA viewport or board capacity')
    duration=finite(brief.get('duration'),'QA duration',1,90);total=_frame(duration,fps)
    assets=_assets(asset_hashes);reasons=[]
    if source_fingerprint is not None and not _hash(source_fingerprint):raise WorkflowError('Invalid QA source fingerprint')
    if source_fingerprint is None:reasons.append('source_fingerprint_missing')
    scenes=brief.get('scenes')
    if not isinstance(scenes,list) or not 1<=len(scenes)<=12:raise WorkflowError('QA needs 1–12 timed scenes')
    keyframes={} if scene_keyframes is None else scene_keyframes
    if not isinstance(keyframes,dict):raise WorkflowError('Declared keyframes must be a scene-to-frame map')
    ranges=[];samples={};expectations=[];last=0;ids=set()
    def add(frame,role,scene_ids):
        if type(frame) is not int or not 0<=frame<total:raise WorkflowError('QA sample outside final render frame range')
        sample=samples.setdefault(frame,{'id':f'frame-{frame:06d}','frame':frame,'roles':[],'scene_ids':[]})
        if role not in sample['roles']:sample['roles'].append(role)
        sample['scene_ids']=sorted(set(sample['scene_ids'])|set(scene_ids))
        return sample['id']
    for scene in scenes:
        if not isinstance(scene,dict) or not _id(scene.get('id')) or scene['id'] in ids:raise WorkflowError('QA scenes require unique simple IDs')
        ident=scene['id'];ids.add(ident)
        start=_frame(finite(scene.get('start'),'QA scene start',0,duration),fps)
        end=_frame(finite(scene.get('end'),'QA scene end',0,duration),fps)
        if start!=last or end<=start:raise WorkflowError('QA scene frame ranges must be contiguous and nonempty')
        last=end;ranges.append({'id':ident,'start_frame':start,'end_frame_exclusive':end})
        for frame,label in [(start,'start'),((start+end-1)//2,'mid'),(end-1,'last')]:add(frame,'scene:'+ident+':'+label,[ident])
        declared=keyframes.get(ident)
        if not isinstance(declared,list) or not declared:reasons.append('declared_keyframes_missing:'+ident)
        else:
            if len(declared)>200 or any(type(f) is not int or not start<=f<end for f in declared):raise WorkflowError('Declared animation keyframe outside its scene')
            for frame in declared:add(frame,'animation-keyframe:'+ident,[ident])
        if scene.get('heading'):
            if not isinstance(scene['heading'],str) or len(scene['heading'])>500:raise WorkflowError('Invalid QA expected heading')
            frame=(start+end-1)//2;expectations.append({'id':'heading-'+ident,'sample_id':add(frame,'ocr-heading:'+ident,[ident]),'text':unicodedata.normalize('NFC',scene['heading'])})
    if last!=total or set(keyframes)-ids:raise WorkflowError('QA scene timeline or declared keyframe IDs do not match')
    for left,right in zip(ranges,ranges[1:]):
        boundary=right['start_frame'];pair=[left['id'],right['id']]
        for frame,label in [(max(0,boundary-2),'before'),(boundary,'mid'),(min(total-1,boundary+2),'after')]:
            add(frame,'transition:'+left['id']+'-to-'+right['id']+':'+label,pair)
    cues=brief.get('cues',[])
    if not isinstance(cues,list) or len(cues)>200:raise WorkflowError('Invalid QA cue expectations')
    for i,cue in enumerate(cues):
        if not isinstance(cue,dict) or not isinstance(cue.get('text'),str) or not 1<=len(cue['text'])<=500:raise WorkflowError('Invalid QA expected subtitle')
        start=_frame(finite(cue.get('start'),'QA cue start',0,duration),fps);end=_frame(finite(cue.get('end'),'QA cue end',0,duration),fps)
        if end<=start:raise WorkflowError('Empty QA cue frame range')
        frame=(start+end-1)//2;owners=[s['id'] for s in ranges if s['start_frame']<=frame<s['end_frame_exclusive']]
        expectations.append({'id':f'cue-{i}','sample_id':add(frame,f'ocr-cue:{i}',owners),'text':unicodedata.normalize('NFC',cue['text'])})
    if not isinstance(issue_frames,(list,tuple)) or len(issue_frames)>200:raise WorkflowError('Invalid QA issue probe frames')
    for frame in issue_frames:add(frame,'issue-probe',[s['id'] for s in ranges if s['start_frame']<=frame<s['end_frame_exclusive']])
    ordered=[samples[f] for f in sorted(samples)]
    if len(ordered)<3:reasons.append('insufficient_frames_for_three_seek_orders')
    forward=[s['id'] for s in ordered];permuted=sorted(forward,key=lambda ident:digest({'seed':seed,'sample_id':ident}))
    if len(forward)>=3 and permuted in [forward,list(reversed(forward))]:permuted=forward[1:]+forward[:1]
    boards=[];columns=min(3,board_capacity)
    for i in range(0,len(ordered),board_capacity):
        group=ordered[i:i+board_capacity]
        boards.append({'page':len(boards)+1,'width':columns*270,'height':math.ceil(len(group)/columns)*512,
            'slots':[{'sample_id':s['id'],'bounds':{'x':j%columns*270,'y':j//columns*512,'width':270,'height':480}} for j,s in enumerate(group)]})
    return {'schema_version':1,'contract_version':CONTRACT_VERSION,'render_sha256':render_sha256,'source_fingerprint':source_fingerprint,
        'asset_hashes':assets,'seed':seed,'fps':fps,'frame_count':total,'viewport':{'width':width,'height':height},
        'scene_ranges':ranges,'samples':ordered,'text_expectations':expectations,'boards':boards,
        'seek_orders':{'forward':forward,'reverse':list(reversed(forward)),'permuted':permuted},
        'complete':not reasons,'incomplete_reasons':reasons,'coverage_scope':'planned timestamp samples only; not every frame'}


def _obj(props):return {'type':'object','properties':props,'required':list(props),'additionalProperties':False}
def _str(n=1000):return {'type':'string','maxLength':n}
def _arr(items,n=10000):return {'type':'array','items':items,'maxItems':n}
def _enum(*values):return {'type':'string','enum':list(values)}
def _nullable(schema):return {'anyOf':[schema,{'type':'null'}]}
def report_schema():
    sha={'type':'string','pattern':'^[0-9a-f]{64}$'};integer={'type':'integer','minimum':0,'maximum':1000000}
    assets={'type':'object','additionalProperties':sha,'maxProperties':1000}
    bounds=_obj({key:integer for key in ['x','y','width','height']})
    evidence=_obj({'id':_str(80),'kind':_enum('frame','crop','board','measurement','human'),'path':_str(240),'sha256':sha,
        'pixel_sha256':_nullable(sha),'render_sha256':sha,'frame':_nullable(integer),'bounds':_nullable(bounds),'parent_id':_nullable(_str(80))})
    capture=_obj({'sample_id':_str(80),'frame':integer,'seed':integer,'asset_hashes':assets,'evidence_id':_str(80)})
    check=_obj({'id':_enum(*REQUIRED_CHECKS),'status':_enum('pass','fail','pending','skipped'),'render_sha256':sha,'evidence_ids':_arr(_str(80),100),'note':_str(2000)})
    review=_obj({'kind':_enum('listening','final_watch'),'status':_enum('pass','fail','pending'),'reviewer':_str(100),'render_sha256':sha,'evidence_ids':_arr(_str(80),100)})
    recheck=_obj({'status':_enum('pass','fail','pending'),'render_sha256':sha,'seed':integer,'asset_hashes':assets,
        'sample_ids':_arr(_str(80),2000),'check_ids':_arr(_enum(*REQUIRED_CHECKS),20),'evidence_ids':_arr(_str(80),100)})
    issue=_obj({'id':_str(80),'frame':integer,'scene_id':_str(80),'severity':_enum('critical','major','minor','info'),
        'status':_enum('open','fixed'),'description':_str(2000),'local_fix':_str(2000),'crop_evidence_id':_str(80),
        'affected_scene_ids':_arr(_str(80),12),'affected_check_ids':_arr(_enum(*REQUIRED_CHECKS),20),'recheck':_nullable(recheck)})
    return _obj({'schema_version':{'type':'integer','enum':[1]},'plan_sha256':sha,'render_sha256':sha,'evidence':_arr(evidence),
        'coverage':_obj({'samples':_arr(_obj({'sample_id':_str(80),'evidence_id':_str(80)})),
            'board_pages':_arr(_obj({'page':integer,'evidence_id':_str(80),'slots':_arr(_obj({'sample_id':_str(80),'frame_evidence_id':_str(80),'bounds':bounds}),24)}),1000),
            'seek_runs':_arr(_obj({'id':_str(80),'renderer_instance':_str(100),'order':_enum(*ORDERS),'sample_ids':_arr(_str(80)), 'captures':_arr(capture)}),3)}),
        'checks':_arr(check,20),'ocr':_obj({'status':_enum('pass','fail','pending','skipped'),'engine_language':_enum('tur'),
            'normalization':_enum('NFC'),'unicode_verified':{'type':'boolean'},
            'observations':_arr(_obj({'expectation_id':_str(100),'evidence_id':_str(80),'observed_text':_str(2000)}),1000)}),
        'issues':_arr(issue,1000),'human_reviews':_arr(review,2),
        'upstream':_obj({'name':_enum('none','sagecut'),'mode':_enum('not_run','saved_local_measurements'),
            'commit':_nullable(_str(40)),'exit_code':_nullable({'type':'integer','minimum':-1000,'maximum':1000}),
            'score':_nullable({'type':'number','minimum':0,'maximum':100})})})


def _validate(value,schema,path='report'):
    if 'anyOf' in schema:
        for option in schema['anyOf']:
            try:_validate(value,option,path);return
            except WorkflowError:pass
        raise WorkflowError('Invalid nullable QA field: '+path)
    kind=schema['type'];types={'object':dict,'array':list,'string':str,'integer':int,'number':(int,float),'boolean':bool,'null':type(None)}
    if not isinstance(value,types[kind]) or kind in {'integer','number'} and isinstance(value,bool):raise WorkflowError('Invalid QA field type: '+path)
    if 'enum' in schema and value not in schema['enum']:raise WorkflowError('Unsupported QA field: '+path)
    if kind=='object':
        if 'properties' in schema:
            if set(value)!=set(schema['properties']):raise WorkflowError('Missing or unsupported QA fields: '+path)
            for key,item in value.items():_validate(item,schema['properties'][key],path+'.'+key)
        else:
            if len(value)>schema.get('maxProperties',1000):raise WorkflowError('Oversized QA map')
            for item in value.values():_validate(item,schema['additionalProperties'],path+'[]')
    elif kind=='array':
        if len(value)>schema['maxItems']:raise WorkflowError('Oversized QA array')
        for item in value:_validate(item,schema['items'],path+'[]')
    elif kind=='string':
        if len(value)>schema.get('maxLength',10000) or '\x00' in value or 'pattern' in schema and not re.fullmatch(schema['pattern'],value):raise WorkflowError('Invalid QA text/hash: '+path)
    elif kind in {'integer','number'}:finite(value,path,schema.get('minimum',-1e12),schema.get('maximum',1e12))


def report_template(plan):
    """An honest unexecuted report, not an approval or synthetic capture."""
    return {'schema_version':1,'plan_sha256':digest(plan),'render_sha256':plan['render_sha256'],'evidence':[],
        'coverage':{'samples':[],'board_pages':[],'seek_runs':[]},'checks':[],
        'ocr':{'status':'pending','engine_language':'tur','normalization':'NFC','unicode_verified':False,'observations':[]},
        'issues':[],'human_reviews':[],'upstream':{'name':'none','mode':'not_run','commit':None,'exit_code':None,'score':None}}


def optional_import_policy(capability):
    """Allow data planning only. This never returns a shell command or executor."""
    if capability not in OPTIONAL_IMPORT_ALLOWLIST:raise WorkflowError('Optional QA capability outside local data-import allowlist')
    return {'capability':capability,'execution_enabled':False,'network_allowed':False,'provider_allowed':False,
        'upstream_commit':UPSTREAM_COMMIT,'required_bridge':'host-verified saved files; explicit isolated runner review before any future execution'}


def validate_report(report,*,expected_plan,current_render_sha256,artifact_manifest):
    """Recompute pass/fail/incomplete against host-owned plan and verified files.

    artifact_manifest[path] must be produced outside model output, after reading
    local bytes/pixels: {sha256, pixel_sha256, width, height}. This function does
    not read, trust-download, render, OCR, listen or execute anything.
    """
    try:
        raw=canonical(report).encode()
        if len(raw)>4000000 or scan_bytes(raw):raise WorkflowError('QA data oversized or possible secret; withheld')
    except (TypeError,ValueError,RecursionError):raise WorkflowError('QA report must be bounded JSON') from None
    _validate(report,report_schema())
    if not isinstance(expected_plan,dict) or expected_plan.get('contract_version')!=CONTRACT_VERSION or not _hash(current_render_sha256):raise WorkflowError('QA requires its host-built plan and current final MP4 hash')
    failures=[];missing=[]
    def fail(code):
        if code not in failures:failures.append(code)
    def incomplete(code):
        if code not in missing:missing.append(code)
    if report['render_sha256']!=current_render_sha256 or expected_plan['render_sha256']!=current_render_sha256:fail('final_render_changed_old_approval_invalid')
    if report['plan_sha256']!=digest(expected_plan):fail('sampling_plan_hash_mismatch')
    if not expected_plan['complete']:incomplete('sampling_plan_incomplete')
    manifest=artifact_manifest if isinstance(artifact_manifest,dict) else {}
    if not manifest:incomplete('host_verified_artifact_manifest_missing')
    evidences={};paths=set();viewport=expected_plan['viewport'];samples={s['id']:s for s in expected_plan['samples']}
    for item in report['evidence']:
        ident=item['id']
        if not _id(ident) or ident in evidences or not _path(item['path']) or item['path'] in paths:raise WorkflowError('QA evidence IDs/paths must be unique bounded local references')
        evidences[ident]=item;paths.add(item['path'])
        if item['render_sha256']!=current_render_sha256:fail('evidence_render_binding_mismatch')
        actual=manifest.get(item['path'])
        if not isinstance(actual,dict):incomplete('artifact_not_verified:'+ident);continue
        if actual.get('sha256')!=item['sha256']:fail('artifact_hash_mismatch:'+ident)
        if item['kind'] in {'frame','crop','board'}:
            if not _hash(item['pixel_sha256']) or actual.get('pixel_sha256')!=item['pixel_sha256']:fail('artifact_pixel_hash_mismatch:'+ident)
            if any(type(actual.get(k)) is not int or actual[k]<=0 for k in ['width','height']):fail('artifact_image_dimensions_invalid:'+ident)
        if item['kind']=='frame':
            if item['bounds'] is not None or item['parent_id'] is not None or item['frame'] is None or not 0<=item['frame']<expected_plan['frame_count']:fail('full_frame_reference_invalid:'+ident)
            if (actual.get('width'),actual.get('height'))!=(viewport['width'],viewport['height']):fail('full_frame_dimensions_mismatch:'+ident)
        elif item['kind']!='crop' and (item['bounds'] is not None or item['parent_id'] is not None or item['frame'] is not None):fail('nonframe_evidence_reference_invalid:'+ident)
    for item in evidences.values():
        if item['kind']!='crop':continue
        parent=evidences.get(item['parent_id']);bounds=item['bounds'];actual=manifest.get(item['path'],{})
        if not parent or parent['kind']!='frame' or item['frame']!=parent['frame'] or not bounds:
            fail('crop_parent_missing_or_wrong:'+item['id']);continue
        if bounds['width']<=0 or bounds['height']<=0 or bounds['x']+bounds['width']>viewport['width'] or bounds['y']+bounds['height']>viewport['height']:
            fail('crop_bounds_outside_parent:'+item['id'])
        if (actual.get('width'),actual.get('height'))!=(bounds['width'],bounds['height']):fail('crop_dimensions_mismatch:'+item['id'])
    def evidence(ident,kind=None,frame=None):
        value=evidences.get(ident)
        if value is None:incomplete('evidence_missing:'+ident);return None
        if kind and value['kind']!=kind or frame is not None and value['frame']!=frame:fail('evidence_reference_type_or_frame_mismatch:'+ident);return None
        return value
    coverage={}
    for item in report['coverage']['samples']:
        ident=item['sample_id']
        if ident not in samples or ident in coverage:raise WorkflowError('Unknown or repeated QA sample coverage')
        coverage[ident]=item['evidence_id'];evidence(item['evidence_id'],'frame',samples[ident]['frame'])
    if set(coverage)!=set(samples):incomplete('sample_coverage_missing')
    pages={p['page']:p for p in expected_plan['boards']};seen_pages=set()
    for page in report['coverage']['board_pages']:
        if page['page'] not in pages or page['page'] in seen_pages:raise WorkflowError('Unknown or repeated QA board page')
        seen_pages.add(page['page']);expected=pages[page['page']];board=evidence(page['evidence_id'],'board')
        if board:
            actual=manifest.get(board['path'],{})
            if (actual.get('width'),actual.get('height'))!=(expected['width'],expected['height']):fail('contact_board_dimensions_mismatch')
        if [{'sample_id':s['sample_id'],'bounds':s['bounds']} for s in page['slots']]!=expected['slots']:incomplete('contact_board_slot_coverage_mismatch')
        for slot in page['slots']:
            if slot['sample_id'] not in samples:raise WorkflowError('Unknown QA board sample')
            evidence(slot['frame_evidence_id'],'frame',samples[slot['sample_id']]['frame'])
            if slot['sample_id'] in coverage and coverage[slot['sample_id']]!=slot['frame_evidence_id']:fail('contact_board_source_differs_from_covered_frame')
    if seen_pages!=set(pages):incomplete('contact_board_pagination_incomplete')
    orders=set();instances=set();run_ids=set();capture_ids=set();pixel_hashes={}
    for run in report['coverage']['seek_runs']:
        order=run['order']
        if order in orders or not _id(run['id']) or run['id'] in run_ids or not run['renderer_instance'] or run['renderer_instance'] in instances:raise WorkflowError('Seek runs need distinct IDs and independent renderer instances')
        orders.add(order);instances.add(run['renderer_instance']);run_ids.add(run['id'])
        if run['sample_ids']!=expected_plan['seek_orders'][order] or [c['sample_id'] for c in run['captures']]!=run['sample_ids']:incomplete('seek_order_or_capture_coverage_incomplete:'+order)
        for capture in run['captures']:
            ident=capture['sample_id']
            if ident not in samples:raise WorkflowError('Unknown QA seek sample')
            if capture['frame']!=samples[ident]['frame'] or capture['seed']!=expected_plan['seed'] or capture['asset_hashes']!=expected_plan['asset_hashes']:fail('seek_context_changed:'+ident)
            if capture['evidence_id'] in capture_ids:fail('seek_evidence_reused_across_captures')
            capture_ids.add(capture['evidence_id']);image=evidence(capture['evidence_id'],'frame',samples[ident]['frame'])
            if image:
                old=pixel_hashes.setdefault(ident,image['pixel_sha256'])
                if old!=image['pixel_sha256']:fail('seek_pixel_nondeterminism:'+ident)
    if orders!=set(ORDERS):incomplete('independent_seek_orders_missing')
    checks={}
    for check in report['checks']:
        if check['id'] in checks:raise WorkflowError('Repeated QA check')
        checks[check['id']]=check
        if check['render_sha256']!=current_render_sha256:fail('check_render_binding_mismatch')
        if check['status']=='fail':fail('required_check_failed:'+check['id'])
        elif check['status']!='pass':incomplete('required_check_incomplete:'+check['id'])
        if not check['evidence_ids']:incomplete('check_evidence_missing:'+check['id'])
        for ident in check['evidence_ids']:evidence(ident)
    if set(checks)!=set(REQUIRED_CHECKS):incomplete('required_checks_missing')
    ocr=report['ocr']
    if ocr['status']=='fail':fail('turkish_ocr_failed')
    elif ocr['status']!='pass' or not ocr['unicode_verified']:incomplete('turkish_unicode_ocr_incomplete')
    expectations={e['id']:e for e in expected_plan['text_expectations']};observed=set()
    for row in ocr['observations']:
        if row['expectation_id'] not in expectations or row['expectation_id'] in observed:raise WorkflowError('Unknown or repeated OCR expectation')
        observed.add(row['expectation_id']);target=expectations[row['expectation_id']]
        evidence(row['evidence_id'],'frame',samples[target['sample_id']]['frame'])
        if _text(row['observed_text'])!=_text(target['text']):fail('turkish_unicode_text_mismatch:'+row['expectation_id'])
    if observed!=set(expectations):incomplete('ocr_text_coverage_missing')
    humans=set()
    for review in report['human_reviews']:
        if review['kind'] in humans:raise WorkflowError('Repeated human QA review')
        humans.add(review['kind'])
        if review['render_sha256']!=current_render_sha256:fail('human_review_render_changed')
        if review['status']=='fail':fail('human_review_failed:'+review['kind'])
        elif review['status']!='pass' or not review['reviewer'].strip():incomplete('human_review_incomplete:'+review['kind'])
        if not review['evidence_ids']:incomplete('human_review_evidence_missing:'+review['kind'])
        for ident in review['evidence_ids']:evidence(ident,'human')
    if humans!={'listening','final_watch'}:incomplete('human_listening_or_final_watch_missing')
    issue_ids=set();ranges={s['id']:s for s in expected_plan['scene_ranges']}
    for issue in report['issues']:
        if not _id(issue['id']) or issue['id'] in issue_ids or issue['scene_id'] not in ranges:raise WorkflowError('Invalid QA issue or scene identity')
        issue_ids.add(issue['id']);span=ranges[issue['scene_id']]
        if not span['start_frame']<=issue['frame']<span['end_frame_exclusive']:fail('issue_timestamp_outside_scene')
        evidence(issue['crop_evidence_id'],'crop',issue['frame'])
        if not issue['description'].strip():incomplete('issue_description_missing')
        if not issue['affected_scene_ids'] or set(issue['affected_scene_ids'])-set(ranges) or issue['scene_id'] not in issue['affected_scene_ids'] or not issue['affected_check_ids']:raise WorkflowError('Issue needs bounded affected scenes and checks')
        if issue['status']=='open':
            if issue['severity'] in {'critical','major'}:fail('open_blocking_issue:'+issue['id'])
            else:incomplete('open_issue:'+issue['id'])
            continue
        if not issue['local_fix'].strip():incomplete('fixed_issue_local_fix_missing:'+issue['id'])
        recheck=issue['recheck']
        if recheck is None:incomplete('affected_scene_recheck_missing:'+issue['id']);continue
        if recheck['render_sha256']!=current_render_sha256 or recheck['seed']!=expected_plan['seed'] or recheck['asset_hashes']!=expected_plan['asset_hashes']:fail('recheck_context_changed:'+issue['id'])
        if recheck['status']=='fail':fail('recheck_failed:'+issue['id'])
        elif recheck['status']!='pass':incomplete('recheck_incomplete:'+issue['id'])
        expected={s['id'] for s in samples.values() if set(s['scene_ids'])&set(issue['affected_scene_ids'])}
        if set(recheck['sample_ids'])!=expected or not any(s['frame']==issue['frame'] for s in samples.values() if s['id'] in expected):incomplete('affected_scene_exact_frame_coverage_missing:'+issue['id'])
        if set(recheck['check_ids'])!=set(issue['affected_check_ids']):incomplete('affected_checks_not_rechecked:'+issue['id'])
        if not recheck['evidence_ids']:incomplete('recheck_evidence_missing:'+issue['id'])
        for ident in recheck['evidence_ids']:evidence(ident)
    upstream=report['upstream']
    if upstream['name']=='sagecut' and upstream['commit']!=UPSTREAM_COMMIT:incomplete('optional_upstream_revision_unreviewed')
    # Upstream exit/score are diagnostic fields; they never set our result.
    status='fail' if failures else 'incomplete' if missing else 'pass'
    return {'status':status,'failures':failures,'incomplete':missing,'render_sha256':current_render_sha256,
        'plan_sha256':digest(expected_plan),'approval_fingerprint':digest({'report':report,'plan':expected_plan,'artifacts':manifest}) if status=='pass' else None,
        'scope':'contract and declared evidence consistency; execution/human authenticity requires the host bridge'}
