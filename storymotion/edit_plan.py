from .account_packs import capability
"""Host compiled bounded edit plans; no model code, remote assets or final approval."""
import copy,hashlib,json,re
from pathlib import Path
from .security import WorkflowError,canonical,digest,file_hash,finite,within


def required_assets(root):
    root=Path(root).resolve();lock=json.loads((root/'renderers/assets-lock.json').read_text())
    result=[]
    if lock.get('schema_version')!=1 or len(lock.get('assets',[]))!=4:raise WorkflowError('Invalid local edit asset lock')
    for spec in lock['assets']:
        if set(spec)!={'path','sha256','role','rights'}:raise WorkflowError('Invalid edit asset fields')
        path=within(root,spec['path'])
        lexical=root/spec['path']
        if any((root/Path(*Path(spec['path']).parts[:i])).is_symlink() for i in range(1,len(Path(spec['path']).parts)+1)) or not path.is_file() or file_hash(path)!=spec['sha256']:
            raise WorkflowError('Required edit asset missing or changed: '+spec['role'])
        result.append(copy.deepcopy(spec))
    return result


def validate_operations(operations,length):
    for op in operations:
        if not re.fullmatch('[a-z][a-z-]{0,30}',op['target']):raise WorkflowError('Invalid host motion target')
        values=[op['values']] if op['op']=='set' else [op['before'],op['after']]
        if op['op'] not in {'set','tween'}:raise WorkflowError('Invalid host motion operator')
        if op['op']=='tween':
            delay=finite(op['offset'],'motion offset',0,length);duration=finite(op['duration'],'motion duration',.001,length)
            if delay+duration>length+1e-7 or op['ease']!='cubic-in-out':raise WorkflowError('Host motion escapes its scene')
        for group in values:
            if set(group)-{'x','y','scale','rotation','opacity','svgOrigin'}:raise WorkflowError('Unsupported motion property')
            for key,value in group.items():
                if key=='svgOrigin':
                    if not isinstance(value,str) or not re.fullmatch(r'-?\d+(?:\.\d+)? -?\d+(?:\.\d+)?',value):raise WorkflowError('Invalid fixed SVG origin')
                else:finite(value,'motion '+key,-2000,2000)


def compile_edit_plan(profile,brief,root):
    """Input must already have passed the strict host creative/timed contract."""
    from .creative import load_pack
    from .compose import creative_objects
    from .writing_context import audit_bound_claims
    pack=load_pack(profile['id']);assets=required_assets(root);scenes=[]
    rig=brief.get('rig');rig_assets=[]
    if rig:
        from .viseme import validate_rig
        from .rig_assets import required_rig_assets
        validate_rig(rig,brief,root);rig_assets=required_rig_assets(root)
    manual=brief.get('scene_plan')
    if manual:
        from .scene_plan import validate_scene_plan
        manual=validate_scene_plan(manual,brief)
    raster=brief.get('raster')
    if raster:
        from .raster_view import validate_raster
        raster=validate_raster(raster,brief)
    claim_trace=audit_bound_claims(brief)
    for i,scene in enumerate(brief['scenes']):
        if manual:
            from .scene_plan import compile_scene
            vector,ops=compile_scene(scene,manual['scenes'][i],profile,'s'+str(i),brief)
        elif raster:
            from .raster_view import compile_view
            vector,ops=compile_view(scene,raster['views'][i],raster['asset'],profile,'s'+str(i))
        else:vector,_,ops=creative_objects(profile,'s'+str(i),scene,with_plan=True)
        if rig and capability(profile['id'], 'rig_mode')=='serial-courier':
            # Replace exactly the host-owned courier slot, never guess at a new
            # customer character or silently layer a second person over it.
            token='<g data-character-id="'+__import__('html').escape(scene['character_id'],quote=True)+'">'
            if vector.count(token)!=1:raise WorkflowError('RIG_SCENE_SLOT_UNSUPPORTED: Bu sahnede doğrulanmış nötr karakter yuvası yok')
            first=vector.index(token);last=vector.find('</g>',first)
            if last<0 or '<g ' in vector[first+len(token):last]:raise WorkflowError('RIG_SCENE_SLOT_CHANGED')
            vector=vector[:first]+vector[last+4:]
        validate_operations(ops,scene['end']-scene['start'])
        if any('id="s'+str(i)+'-'+op['target']+'"' not in vector for op in ops):raise WorkflowError('Host motion target absent from owned vector')
        # Keep explicit claim references, including nonverbatim/global claims.
        # Exact-copy matches aid review; they do not infer semantic support.
        links=[]
        for n,claim in enumerate(brief['claims']):
            surfaces=[scene['heading'],scene['information']]+[c['text'] for c in brief['cues'] if c['start']<scene['end'] and c['end']>scene['start']]
            if any(claim['text'] in text for text in surfaces):links.append(n)
        scenes.append({'id':scene['id'],'start':scene['start'],'end':scene['end'],'action':('manual-scene' if manual else 'raster-annotation' if raster else scene['action']),
            **({'scene_type':manual['scenes'][i]['kind'],'manual_claim_indexes':manual['scenes'][i]['claim_indexes']} if manual else {}),'heading':scene['heading'],'camera':scene['camera'],
            'object_id':scene['object_id'],'character_id':scene['character_id'],
            'state_before':scene['state_before'],'state_after':scene['state_after'],
            'object_before':scene['object_before'],'object_after':scene['object_after'],
            'information':scene['information'],'rule_ids':scene['rule_ids'],
            'cue_indexes':[n for n,c in enumerate(brief['cues']) if c['start']<scene['end'] and c['end']>scene['start']],
            'exact_copy_claim_indexes':links,'semantic_claim_mapping':'pending_human_review',
            'object_motion':[op for op in ops if op['target']!='camera'],'camera_motion':[op for op in ops if op['target']=='camera'],
            'vector':vector,'vector_sha256':hashlib.sha256(vector.encode()).hexdigest()})
    value={'schema_version':1,'compiler':'bounded-account-edit-1','account':profile['id'],'pack_version':pack['version'],
        'actual_visual_family':('manual-account-scene-plan' if manual else 'customer-raster-annotation' if raster else pack['visual_family']),'requested_motif_text':brief['creative']['visual_motif'],
        'scope':('explicit supported manual scene types; source/visual meaning and any new canon acceptance pending human review' if manual else 'selected customer raster with explicit crop/highlight/camera; source script is not automatically rewritten to match image' if raster else 'existing owned bounded vector family; motif/topic text does not create new geometry or a real new-topic video'),
        **({'raster_asset':{**raster['asset'],'staged_file':'assets/customer-image.png'},'raster_sha256':digest(raster)} if raster else {}),
        **({'scene_plan_sha256':digest(manual)} if manual else {}),
        **({'rig_sha256':digest(rig),'rig_assets':rig_assets,'rig_mode':'serial-courier' if capability(profile['id'], 'rig_mode')=='serial-courier' else 'inset'} if rig else {}),
        'brief_sha256':digest(brief),'profile_sha256':digest(profile),'source_binding_sha256':brief.get('production_context',{}).get('binding_sha256'),
        'audio_timing_sha256':digest(brief['audio_timing']) if brief.get('audio_timing') else None,
        'fps':30,'width':1080,'height':1920,'duration':brief['duration'],'assets':assets,
        'claim_traceability':claim_trace,'claims_without_exact_scene_copy':[n for n in range(len(brief['claims'])) if not any(n in s['exact_copy_claim_indexes'] for s in scenes)],
        'scenes':scenes,'rights':'owned geometry code; private rig/voice/PDF excluded; customer/commercial transfer not assumed',
        'acceptance':{'status':'incomplete','visual_information_match':'pending_human_review','source_truth':'pending_human_review','publication_ready':False}}
    return {**value,'plan_sha256':digest(value)}


def verify_edit_plan(payload,root):
    expected=compile_edit_plan(payload['profile'],payload['brief'],root)
    if payload.get('edit_plan')!=expected:raise WorkflowError('Pinned edit plan/input/assets changed; create a new revision')
    return expected


def verify_staged_assets(payload,out,delivery=False):
    """Compare copied AND packaged bytes to the pinned required asset hashes."""
    if not payload['brief'].get('creative'):return
    import hashlib,zipfile,stat
    out=Path(out);plan=payload['edit_plan']
    from .rig_assets import verify_rig_assets
    verify_rig_assets(payload,out,delivery=delivery)
    manual=payload['brief'].get('scene_plan')
    if manual:
        from .manual_scene_revision import validate_stored_plan
        validate_stored_plan(payload['brief'],out)
        if plan.get('scene_plan_sha256')!=digest(manual):raise WorkflowError('Staged manual scene plan binding changed')
    raster=payload['brief'].get('raster')
    if raster:
        from .raster_io import validate_normalized
        from .raster_revision import pinned_path
        if plan.get('raster_asset')!={**raster['asset'],'staged_file':'assets/customer-image.png'} or plan.get('raster_sha256')!=digest(raster):raise WorkflowError('Pinned raster plan binding changed')
        a=raster['asset'];path=pinned_path(out,'assets/customer-image.png');validate_normalized(path,a['sha256'],a['width'],a['height'])
        if json.loads(pinned_path(out,'raster.json').read_text())!=raster:raise WorkflowError('Staged raster manifest changed')
    for spec in plan['assets']:
        rel='assets/'+Path(spec['path']).relative_to('vendor').as_posix();path=within(out,rel)
        if any((out/Path(*Path(rel).parts[:i])).is_symlink() for i in range(1,len(Path(rel).parts)+1)) or not path.is_file() or file_hash(path)!=spec['sha256']:
            raise WorkflowError('Staged required edit asset missing or changed: '+spec['role'])
    if delivery:
        try:
            manifest=json.loads((out/'delivery.json').read_text())
            if manifest.get('edit_plan_sha256')!=plan['plan_sha256'] or json.loads((out/'edit-plan.json').read_text())!=plan:raise WorkflowError('Delivery edit plan binding changed')
            with zipfile.ZipFile(out/'delivery.zip') as archive:
                if manual:
                    receipt=json.loads((out/'render-engine.json').read_text())
                    if receipt.get('scene_plan_sha256')!=digest(manual) or json.loads(archive.read('render-engine.json'))!=receipt:raise WorkflowError('Render receipt manual scene plan binding changed')
                    infos=[i for i in archive.infolist() if i.filename=='manual-plan.json']
                    sha=file_hash(out/'manual-plan.json')
                    if len(infos)!=1 or infos[0].is_dir() or stat.S_IFMT(infos[0].external_attr>>16) not in {0,stat.S_IFREG} or manifest.get('files',{}).get('manual-plan.json')!=sha or hashlib.sha256(archive.read('manual-plan.json')).hexdigest()!=sha or manifest.get('scene_plan_sha256')!=digest(manual):raise WorkflowError('Packaged manual scene plan missing, linked, duplicate or changed')
                if raster:
                    for rel,sha in [('assets/customer-image.png',raster['asset']['sha256']),('raster.json',file_hash(out/'raster.json'))]:
                        infos=[i for i in archive.infolist() if i.filename==rel]
                        if len(infos)!=1 or infos[0].is_dir() or stat.S_IFMT(infos[0].external_attr>>16) not in {0,stat.S_IFREG} or manifest.get('files',{}).get(rel)!=sha or hashlib.sha256(archive.read(rel)).hexdigest()!=sha:raise WorkflowError('Packaged customer raster missing, linked, duplicate or changed')
                    if manifest.get('raster_sha256')!=digest(raster) or json.loads(archive.read('raster.json'))!=raster:raise WorkflowError('Packaged raster binding changed')
                revision=payload['brief'].get('revision_context')
                if revision and (json.loads((out/'revision.json').read_text())!=revision or json.loads(archive.read('revision.json'))!=revision or manifest.get('revision_sha256')!=revision['binding_sha256']):raise WorkflowError('Packaged visual revision binding changed')
                for spec in plan['assets']:
                    rel='assets/'+Path(spec['path']).relative_to('vendor').as_posix()
                    infos=[i for i in archive.infolist() if i.filename==rel]
                    if len(infos)!=1 or infos[0].is_dir() or stat.S_IFMT(infos[0].external_attr>>16) not in {0,stat.S_IFREG}:raise WorkflowError('Packaged required edit asset must be one regular file')
                    if manifest.get('files',{}).get(rel)!=spec['sha256'] or hashlib.sha256(archive.read(rel)).hexdigest()!=spec['sha256']:
                        raise WorkflowError('Packaged required edit asset hash differs from pinned plan')
        except (OSError,ValueError,KeyError,zipfile.BadZipFile):raise WorkflowError('Packaged required edit assets missing or malformed') from None
