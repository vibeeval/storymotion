"""Host-only measured-audio revisions. No provider, renderer or forced speaking rate.

Model proposals remain silent-only. Explicit word anchors, measured duration and
exact spelling create a new immutable job; old timing/QA never becomes its consent.
"""
from .local_state import private_directory, guard_private, copy_private
import copy
import json
import math
import re
import shutil
import zipfile
from pathlib import Path
from .security import WorkflowError,canonical,digest,file_hash,finite,within,write_json
from .store import now


def script_sha(text):
    import hashlib
    return hashlib.sha256(text.encode()).hexdigest()


def measured_words(script,alignment,duration,audio_sha=None):
    from .elevenlabs import validate_alignment
    finite(duration,'measured audio duration',1,90)
    if isinstance(alignment,dict) and alignment.get('kind')=='word_timing':
        from .word_alignment import word_alignment
        return word_alignment(script,alignment,duration,audio_sha)[0]
    a=validate_alignment(alignment,duration)
    if not a or any(len(c)!=1 for c in a['characters']) or ''.join(a['characters'])!=script:raise WorkflowError('Exact one-codepoint script alignment required; phonetic spelling needs reviewed manual mapping')
    words=[];last=0
    for index,match in enumerate(re.finditer(r'\S+',script)):
        # Enclose every validated character, including punctuation. Never hide
        # an interior end by sampling only the last character of the word.
        start=min(a['character_start_times_seconds'][match.start():match.end()]);end=max(a['character_end_times_seconds'][match.start():match.end()])
        if start<last or end<=start or end>duration:raise WorkflowError('Word timestamps overlap, are empty or escape measured audio')
        words.append({'index':index,'text':match.group(),'start':start,'end':end});last=end
    if not words:raise WorkflowError('Audio alignment contains no words')
    return words


def scene_spans(brief,supplied=None):
    """Use ordinal word ranges, never fuzzy text or old seconds as audio anchors."""
    if supplied is None:
        if len(brief['scenes'])!=len(brief['cues']):raise WorkflowError('Explicit scene_word_spans required; cue-to-scene mapping is ambiguous')
        supplied=[];index=0
        for scene,cue in zip(brief['scenes'],brief['cues']):
            if not scene['start']<=cue['start']<cue['end']<=scene['end']+.001:
                raise WorkflowError('Explicit scene_word_spans required; source cues cross scenes')
            count=len(cue['text'].split());supplied.append({'scene_id':scene['id'],'start_word':index,'end_word':index+count});index+=count
    if not isinstance(supplied,list) or len(supplied)!=len(brief['scenes']):raise WorkflowError('One exact word span per scene required')
    end=0;size=len(brief['script'].split())
    for scene,span in zip(brief['scenes'],supplied):
        if (not isinstance(span,dict) or set(span)!={'scene_id','start_word','end_word'} or span['scene_id']!=scene['id'] or
            type(span['start_word']) is not int or type(span['end_word']) is not int or span['start_word']!=end or not end<span['end_word']<=size):
            raise WorkflowError('Scene word spans must exactly partition the script in scene order')
        end=span['end_word']
    if end!=size:raise WorkflowError('Scene word spans do not cover the full script')
    return copy.deepcopy(supplied)


def cue_spans(words):
    spans=[];start=0
    for i,word in enumerate(words):
        if len(word['text'])>95:raise WorkflowError('Single word exceeds bounded subtitle capacity')
        if i>start and len(' '.join(w['text'] for w in words[start:i+1]))>42:
            spans.append((start,i));start=i
        if word['text'][-1:] in '.!?':spans.append((start,i+1));start=i+1
    if start<len(words):spans.append((start,len(words)))
    return [{'start_word':a,'end_word':b} for a,b in spans]


def retime(brief,alignment,duration,audio_sha,spans=None,viseme_required=False):
    if brief.get('rig'):raise WorkflowError('RIG_FRESH_DATA_REQUIRED: Yeni ses için kaynak işinden retime ve yeni ağız girdisi gerekir')
    if viseme_required is not False:raise WorkflowError('Fresh viseme generation is unavailable; articulated mouth must not reuse old visemes')
    value=copy.deepcopy(brief);words=measured_words(value['script'],alignment,duration,audio_sha);spans=scene_spans(value,spans)
    timeline_duration=math.ceil(duration*30-1e-8)/30
    boundaries=[0]+[words[span['start_word']]['start'] for span in spans[1:]]+[timeline_duration]
    changes=[]
    for i,scene in enumerate(value['scenes']):
        start,end=boundaries[i:i+2]
        if end-start<1.6:raise WorkflowError('Measured speech leaves a scene under 1.6s; revise the scene plan, never speed up or stretch audio')
        changes.append({'scene_id':scene['id'],'before':[scene['start'],scene['end']],'after':[start,end],
                        'downstream_shift_seconds':start-scene['start']})
        scene.update(start=start,end=end)
    cue_map=cue_spans(words)
    value['cues']=[{'start':words[s['start_word']]['start'],'end':words[s['end_word']-1]['end'],
                    'text':' '.join(w['text'] for w in words[s['start_word']:s['end_word']])} for s in cue_map]
    value.update(duration=timeline_duration,alignment='imported_timing')
    value['audio_timing']={'schema_version':1,'source_script_sha256':script_sha(value['script']),'source_audio_sha256':audio_sha,
        'audio_duration_seconds':duration,'timeline_duration_seconds':timeline_duration,'tail_padding_seconds':timeline_duration-duration,
        'alignment_sha256':digest(alignment),'words':words,'scene_word_spans':spans,'cue_word_spans':cue_map,
        'scene_sha256':digest(value['scenes']),'cues_sha256':digest(value['cues']),'retime_report':changes,
        'viseme':{'status':'not_applicable','reason':'Pinned bounded vectors have no articulated speaking mouth; no old viseme reused'},
        'human_listening':'pending','subtitle_semantics':'pending','visual_acceptance':'pending','publication_ready':False}
    if isinstance(alignment,dict) and alignment.get('kind')=='word_timing':
        from .word_alignment import word_alignment
        value['audio_timing']['alignment_provenance']=word_alignment(value['script'],alignment,duration,audio_sha)[1]
    return value


def validate_timed_brief(brief):
    """Validate host audio against the same strict creative contract as silent JSON."""
    from .creative import validate_proposal
    if not isinstance(brief.get('audio'),dict) or not isinstance(brief.get('audio_timing'),dict):raise WorkflowError('Host audio timing manifest required')
    t=brief['audio_timing'];spec=brief['audio']
    fields={'schema_version','source_script_sha256','source_audio_sha256','audio_duration_seconds','timeline_duration_seconds','tail_padding_seconds',
            'alignment_sha256','words','scene_word_spans','cue_word_spans','scene_sha256','cues_sha256','retime_report','viseme','human_listening','subtitle_semantics','visual_acceptance','publication_ready'}
    if set(t)-{'alignment_provenance'}!=fields or t['schema_version']!=1 or brief['alignment']!='imported_timing':raise WorkflowError('Invalid host timing manifest fields')
    if 'alignment_provenance' in t:
        from .word_alignment import validate_provenance
        validate_provenance(t['alignment_provenance'])
    duration=finite(t['audio_duration_seconds'],'measured audio duration',1,90)
    if (t['source_script_sha256']!=script_sha(brief['script']) or t['source_audio_sha256']!=spec.get('sha256') or
        t['scene_sha256']!=digest(brief['scenes']) or t['cues_sha256']!=digest(brief['cues']) or
        t['timeline_duration_seconds']!=brief['duration'] or abs(brief['duration']-math.ceil(duration*30-1e-8)/30)>1e-7 or
        abs(t['tail_padding_seconds']-(brief['duration']-duration))>1e-7):raise WorkflowError('Audio/script/scene/cue duration binding changed')
    words=t['words'];last=0
    if not isinstance(words,list) or not 1<=len(words)<=10000:raise WorkflowError('Bounded measured words required')
    for i,word in enumerate(words):
        if not isinstance(word,dict) or set(word)!={'index','text','start','end'} or word['index']!=i or not isinstance(word['text'],str):raise WorkflowError('Invalid word timing fields')
        start=finite(word['start'],'word start',0,duration);end=finite(word['end'],'word end',0,duration)
        if start<last or end<=start:raise WorkflowError('Invalid measured word order')
        last=end
    if [w['text'] for w in words]!=brief['script'].split():raise WorkflowError('Measured words changed exact script spelling/order')
    spans=scene_spans(brief,t['scene_word_spans']);boundaries=[0]+[words[s['start_word']]['start'] for s in spans[1:]]+[brief['duration']]
    if any([s['start'],s['end']]!=boundaries[i:i+2] for i,s in enumerate(brief['scenes'])):raise WorkflowError('Scene times no longer follow measured words')
    if t['cue_word_spans']!=cue_spans(words):raise WorkflowError('Subtitle word grouping changed')
    expected=[{'start':words[s['start_word']]['start'],'end':words[s['end_word']-1]['end'],'text':' '.join(w['text'] for w in words[s['start_word']:s['end_word']])} for s in t['cue_word_spans']]
    if expected!=brief['cues']:raise WorkflowError('Subtitle timing no longer follows measured words')
    from .rig_revision import RIG_TIMING_MARKER
    if t['viseme'] not in [{'status':'not_applicable','reason':'Pinned bounded vectors have no articulated speaking mouth; no old viseme reused'},RIG_TIMING_MARKER]:raise WorkflowError('Unknown viseme timing status')
    if t['publication_ready'] is not False or any(t[x]!='pending' for x in ['human_listening','subtitle_semantics','visual_acceptance']):raise WorkflowError('Timing metadata cannot supply human acceptance')
    silent=copy.deepcopy(brief);silent.pop('audio_timing');silent.update(audio=None,alignment='provisional_silent')
    from .writing_context import bound_brief
    return bound_brief(brief['brand'],silent)


def verify_final_audio(payload,out,delivery=False):
    """Bind a technical review delivery to audio, timing and both final MP4 hashes.

    Full media decode occurs in the Engine QA stage, never inferred from a ZIP.
    This verifier preserves pending human acceptance even after technical pass.
    """
    try:
        from .edit_plan import verify_staged_assets
        verify_staged_assets(payload,out,delivery=delivery)
        brief=payload['brief'];timing=brief['audio_timing'];sha=digest(timing)
        receipt=json.loads((out/'render-engine.json').read_text());qa=json.loads((out/'qa.json').read_text())
        main=file_hash(out/'render-1080.mp4');mobile=file_hash(out/'render-mobile.mp4')
        if (receipt.get('render_sha256')!=main or receipt.get('engine')!=payload['render_engine'] or
            receipt.get('execution_fingerprint')!=payload['execution']['fingerprint'] or
            receipt.get('audio_timing_sha256')!=sha or receipt.get('audio_sha256')!=payload['audio_sha256']):
            raise WorkflowError('Final audio render receipt binding changed')
        if (qa.get('technical')!='pass' or qa.get('audio_source_sha256')!=payload['audio_sha256'] or qa.get('audio_timing_sha256')!=sha or
            any(qa.get('media',{}).get(name,{}).get('sha256')!=h or qa.get('media',{}).get(name,{}).get('full_decode')!='pass'
                for name,h in [('render-1080.mp4',main),('render-mobile.mp4',mobile)])):
            raise WorkflowError('Final audio QA/hash binding is missing or stale')
        audio=out/'assets'/('narration'+Path(payload['audio_source']).suffix.lower())
        if audio.is_symlink() or file_hash(audio)!=payload['audio_sha256'] or json.loads((out/'audio-timing.json').read_text())!=timing:
            raise WorkflowError('Final audio/timing asset changed')
        revision=brief.get('revision_context')
        if revision and json.loads((out/'revision.json').read_text())!=revision:raise WorkflowError('Final visual revision manifest changed')
        context=brief.get('production_context')
        if brief.get('creative'):
            from .edit_plan import verify_edit_plan
            from .engine import ROOT
            plan=verify_edit_plan(payload,ROOT);path=out/'edit-plan.json'
            if path.is_symlink() or json.loads(path.read_text())!=plan:raise WorkflowError('Final edit plan changed')
        if context:
            from .writing_context import validate_binding
            validate_binding(context,brief['brand'])
            source=out/'source-brief.json';record=out/'writing-context.json'
            if source.is_symlink() or record.is_symlink() or json.loads(source.read_text())!=brief or json.loads(record.read_text()).get('binding')!=context:
                raise WorkflowError('Final host source/canon context binding changed')
        if delivery:
            manifest=json.loads((out/'delivery.json').read_text());files=manifest['files']
            required={'render-1080.mp4','render-mobile.mp4','audio-timing.json','subtitles.srt','caption.txt','cover.png','index.html','qa.json','render-engine.json',audio.relative_to(out).as_posix()}
            if revision:
                required.add('revision.json')
                if manifest.get('revision_sha256')!=revision['binding_sha256']:raise WorkflowError('Final delivery revision binding changed')
            if brief.get('creative'):
                required.add('edit-plan.json')
                if manifest.get('edit_plan_sha256')!=plan['plan_sha256']:raise WorkflowError('Final delivery edit plan binding changed')
            if context:
                required|={'source-brief.json','writing-context.json'}
                if manifest.get('writing_context_sha256')!=context['binding_sha256']:raise WorkflowError('Final delivery source/canon revision changed')
            if (manifest.get('status')!='technical_review_copy' or manifest.get('publication_ready') is not False or
                manifest.get('final_release')!='pending_human_review' or manifest.get('render_engine')!=payload['render_engine'] or
                manifest.get('audio_timing_sha256')!=sha or manifest.get('audio_sha256')!=payload['audio_sha256'] or
                manifest.get('main_render_sha256')!=main or manifest.get('mobile_render_sha256')!=mobile or
                not isinstance(files,dict) or not 1<=len(files)<=500 or not required<=set(files)):raise WorkflowError('Final audio delivery manifest binding changed')
            for name,h in files.items():
                p=within(out,name)
                if p.is_symlink() or not p.is_file() or file_hash(p)!=h:raise WorkflowError('Final audio delivery file hash changed')
            with zipfile.ZipFile(out/'delivery.zip') as z:
                if set(z.namelist())!=set(files)|{'delivery.json'} or z.testzip():raise WorkflowError('Final audio delivery ZIP manifest changed')
                import hashlib
                if z.read('delivery.json')!=(out/'delivery.json').read_bytes() or any(hashlib.sha256(z.read(n)).hexdigest()!=h for n,h in files.items()):
                    raise WorkflowError('Final audio delivery ZIP bytes changed')
    except (OSError,ValueError,TypeError,KeyError,zipfile.BadZipFile):raise WorkflowError('Final audio receipt/QA/delivery missing or malformed') from None


class AudioRevisions:
    def __init__(self,dashboard):
        self.d=dashboard
        with self.d.connection() as db:db.executescript('''CREATE TABLE IF NOT EXISTS dashboard_audio_revisions(parent TEXT,child TEXT PRIMARY KEY,binding_sha256 TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS dashboard_audio_heads(parent TEXT PRIMARY KEY,child TEXT NOT NULL);''')
    def voice_snapshot(self,job):
        states=self.d.eleven.job_state(job)
        if any(s['status'] in {'dispatching','uncertain','received_after_cancel_review'} for s in states):raise WorkflowError('Voice result is pending/uncertain; reconcile before local audio binding')
        return digest(sorted([{'request':s['request'],'status':s['status'],'audio_sha256':s['artifact']['source_audio_sha256']} for s in states if s['artifact']],key=lambda s:s['request']))
    def base(self,job):
        row=self.d.job(job);self.d.assert_provenance(row)
        if row['payload'].get('edit_revision') or row['payload'].get('raster_revision') or row['payload'].get('scene_plan_revision') or row['payload'].get('rig_revision'):raise WorkflowError('Görsel/rig revizyonu sesi korur; yeni ses için kaynak işinden ilerleyin')
        if row['payload']['format']['adapter']!='account-pack' or row['payload'].get('audio_revision'):raise WorkflowError('Audio binding starts from an original four-profile AccountPack job')
        return row,self.d.renders.base_video_input(row)
    def bind_voice(self,job,data):
        fields={'request','approved_by','rights_note','rights_confirmed','scene_word_spans','viseme_required'}
        if not isinstance(data,dict) or set(data)!=fields:raise WorkflowError('Invalid audio binding fields; paths/URLs are not accepted')
        self.d.clean(data);row,brief=self.base(job);r=self.d.eleven.get(data['request'])
        if r['job']!=job or r['status']!='completed' or not r['artifact']:raise WorkflowError('A completed audio artifact for this exact job is required')
        request=json.loads(self.d.eleven.row(r['request'])['payload'])
        if request['source_script']!=brief['script'] or request['tts_text']!=brief['script']:raise WorkflowError('Phonetic TTS spelling requires reviewed manual screen-text mapping')
        timing=json.loads(self.d.eleven.download(r['request'],'timestamps.json'))
        source=within(self.d.eleven.root,r['request']+'/narration.mp3')
        return self.import_approved(job,source,timing['alignment'],expected_audio_sha256=r['artifact']['source_audio_sha256'],
            approved_by=data['approved_by'],rights_note=data['rights_note'],rights_confirmed=data['rights_confirmed'],
            scene_word_spans=data['scene_word_spans'],viseme_required=data['viseme_required'],voice_request=r['request'])
    def import_approved(self,job,audio_file,alignment,*,expected_audio_sha256,approved_by,rights_note,rights_confirmed,
                        scene_word_spans=None,viseme_required=False,voice_request=None):
        row,brief=self.base(job)
        if voice_request is not None and (not isinstance(voice_request,str) or not re.fullmatch('[a-f0-9]{32}',voice_request)):
            raise WorkflowError('Invalid source voice request reference')
        if rights_confirmed is not True or not isinstance(approved_by,str) or not 1<=len(approved_by.strip())<=200 or not isinstance(rights_note,str) or not 1<=len(rights_note.strip())<=1000:
            raise WorkflowError('Explicit audio rights confirmation, approved_by and rights_note required')
        self.d.clean({'approved_by':approved_by,'rights_note':rights_note})
        source=within(self.d.workspace,audio_file)
        if Path(audio_file).is_symlink() or not source.is_file() or source.suffix.lower() not in {'.mp3','.wav','.m4a'} or not 100<=source.stat().st_size<=12*1024*1024:
            raise WorkflowError('Bounded approved local audio inside this workspace required')
        if file_hash(source)!=expected_audio_sha256:raise WorkflowError('Imported audio differs from approved SHA256')
        snapshot=self.voice_snapshot(job)
        from .engine import probe,checked_process
        from .audio_input import approved_audio_options
        input_options=approved_audio_options(source)
        media=probe(source,restricted_audio=True)
        if not media.get('streams') or any(s.get('codec_type')!='audio' for s in media['streams']):raise WorkflowError('Audio-only media required')
        duration=finite(media.get('duration'),'measured audio duration',1,90)
        checked_process(['ffmpeg','-v','error','-xerror',*input_options,'-i',source,'-map','0:a:0','-c:a','pcm_s16le','-f','null','-'],timeout=60)
        video=retime(brief,alignment,duration,expected_audio_sha256,scene_word_spans,viseme_required)
        rel='audio/approved'+source.suffix.lower()
        video['audio']={'file':rel,'sha256':expected_audio_sha256,'approved_by':approved_by.strip(),'rights_note':rights_note.strip()}
        # Validate before filesystem writes or DB mutation.
        host={k:video.pop(k) for k in ('appearance','production_notes','brand_identity') if k in video}
        normalized=validate_timed_brief(video);video['creative']=normalized['creative'];video.update(host)
        binding={'schema_version':1,'parent_job':job,'parent_payload_sha256':digest(row['payload']),
            'source_script_sha256':script_sha(video['script']),'audio_sha256':expected_audio_sha256,'timing_sha256':digest(video['audio_timing']),
            'voice_request':voice_request,'voice_snapshot_sha256':snapshot,'approved_by':approved_by.strip(),'rights_note':rights_note.strip(),
            'rights_confirmed':True,'execution_fingerprint':self.d.runtime_execution,'publication_ready':False}
        self.d.clean(binding)
        payload=copy.deepcopy(row['payload']);payload['template']['template']['video']=video;payload['audio_revision']=binding
        child=digest(payload)[:24];out=self.d.output(child)
        with self.d.revision_lock,self.d.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            if digest(self.d.job(job)['payload'])!=binding['parent_payload_sha256'] or self.voice_snapshot(job)!=snapshot:raise WorkflowError('Source or voice changed during audio binding')
            self.d.assert_runtime_current()
            known=db.execute('SELECT child FROM dashboard_audio_revisions WHERE child=?',(child,)).fetchone()
            head=db.execute('SELECT child FROM dashboard_audio_heads WHERE parent=?',(job,)).fetchone()
            if known and head and head['child']!=child:raise WorkflowError('Previously superseded audio revision needs a new explicit revision; no silent rollback')
            private_directory(out);target=within(out,rel);private_directory(target.parent);guard_private(out,rel)
            if target.exists() and file_hash(target)!=expected_audio_sha256:raise WorkflowError('Immutable imported audio was modified')
            if not target.exists():
                temp=target.with_suffix(target.suffix+'.tmp');copy_private(source,temp)
                if file_hash(temp)!=expected_audio_sha256:temp.unlink();raise WorkflowError('Audio changed during snapshot copy')
                temp.replace(target)
            for name,value in [('audio-timing.json',video['audio_timing']),('audio-binding.json',binding)]:
                p=out/name
                if p.exists() and canonical(json.loads(p.read_text()))!=canonical(value):raise WorkflowError('Immutable audio manifest was modified')
                if not p.exists():write_json(p,value)
            db.execute('INSERT OR IGNORE INTO dashboard_jobs(id,payload,status,created) VALUES(?,?,?,?)',(child,canonical(payload),'queued',now()))
            db.execute('INSERT OR IGNORE INTO dashboard_audio_revisions VALUES(?,?,?)',(job,child,digest(binding)))
            db.execute('INSERT INTO dashboard_audio_heads VALUES(?,?) ON CONFLICT(parent) DO UPDATE SET child=excluded.child',(job,child))
            db.execute('INSERT INTO dashboard_events(job,event,created) VALUES(?,?,?)',(child,'approved_audio_bound_new_timing_review_pending',now()))
        return {'job':self.d.job(child),'parent_job':job,'child_job':child,'publication_ready':False,'provider_calls':0,'render_started':False}
    def guard(self,job):
        try:return self._guard(job)
        except (OSError,ValueError,KeyError,TypeError):raise WorkflowError('Audio revision bytes/manifest missing or changed; downstream invalidated') from None
    def _guard(self,job):
        row=self.d.job(job)
        if row['payload'].get('edit_revision'):return self.d.edits.guard(job)
        if row['payload'].get('scene_plan_revision'):return self.d.plans.guard(job)
        if row['payload'].get('raster_revision'):return self.d.raster.guard(job)
        if row['payload'].get('rig_revision'):return self.d.rigs.guard(job)
        binding=row['payload'].get('audio_revision')
        with self.d.connection() as db:
            head=db.execute('SELECT child FROM dashboard_audio_heads WHERE parent=?',(binding['parent_job'] if binding else job,)).fetchone()
        if not binding:
            if head:raise WorkflowError('NEW_AUDIO_REQUIRES_FRESH_TIMING: use the new audio revision job')
            return
        self.d.assert_provenance(row)
        if not head or head['child']!=job:raise WorkflowError('Audio revision superseded; old downstream render/QA/export invalidated')
        parent=self.d.job(binding['parent_job'])
        if digest(parent['payload'])!=binding['parent_payload_sha256'] or self.voice_snapshot(binding['parent_job'])!=binding['voice_snapshot_sha256']:
            raise WorkflowError('Audio parent/script/voice binding changed; downstream timing invalidated')
        with self.d.connection() as db:record=db.execute('SELECT binding_sha256 FROM dashboard_audio_revisions WHERE child=?',(job,)).fetchone()
        if not record or record[0]!=digest(binding) or digest(row['payload'])[:24]!=job:raise WorkflowError('Immutable audio revision payload changed')
        video=row['payload']['template']['template']['video'];out=self.d.output(job)
        if file_hash(within(out,video['audio']['file']))!=binding['audio_sha256'] or digest(video['audio_timing'])!=binding['timing_sha256']:
            raise WorkflowError('Audio/timing bytes changed; downstream invalidated')
        if canonical(json.loads((out/'audio-binding.json').read_text()))!=canonical(binding) or canonical(json.loads((out/'audio-timing.json').read_text()))!=canonical(video['audio_timing']):
            raise WorkflowError('Audio manifest changed; downstream invalidated')
    def render_input(self,row):
        self.guard(row['id']);p=row['payload'];video=copy.deepcopy(p['template']['template']['video'])
        if video['script']!=p['input']['content']:raise WorkflowError('Audio source script changed')
        return video
