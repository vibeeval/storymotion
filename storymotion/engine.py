from .local_state import private_directory, write_private, copy_private
from .account_packs import capability, render_profile, validate_render_profile
import datetime
import decimal
import json
import os
import re
import signal
import shutil
import subprocess
import zipfile
import contextlib
import threading
import time
from pathlib import Path
from . import __version__
from .compose import build
from .security import WorkflowError, canonical, digest, file_hash, finite, scan_bytes, within, write_json
from .store import Store, now

ROOT = Path(__file__).resolve().parents[1]
STAGES = ['prepare', 'check', 'render', 'mobile', 'cover', 'qa', 'delivery']
PROCESS_CONTEXT=threading.local()


@contextlib.contextmanager
def process_cancellation(event):
    old=getattr(PROCESS_CONTEXT,'cancel',None);PROCESS_CONTEXT.cancel=event
    try:yield
    finally:PROCESS_CONTEXT.cancel=old


def stop_owned_group(process):
    if os.name=='nt':
        from .windows_native import close_job
        close_job(process,terminate=True)
        process.communicate(timeout=5)
        return
    # The PGID is the pid returned by our start_new_session Popen. Children can
    # outlive the leader while keeping its pipes open; poll() is not a guard.
    try:os.killpg(process.pid,signal.SIGTERM)
    except ProcessLookupError:pass
    try:process.communicate(timeout=2)
    except subprocess.TimeoutExpired:
        try:os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        process.communicate(timeout=5)


def checked_process(argv, cwd=None, timeout=120):
    from .development_policy import assert_process_scope
    assert_process_scope(ROOT)
    from .runtime import process_env, media_binary
    from . import development_policy as dev
    private = dev.development_mode(ROOT)
    env = process_env('hyperframes') if private else process_env()
    if private:
        # A local HOME does not protect a CLI pointed at an external project.
        target = Path(ROOT if cwd is None else cwd).absolute()
        if target!=target.resolve():raise WorkflowError('DEVELOPMENT_PROCESS_CWD_REFUSED')
        try:relative = target.relative_to(ROOT)
        except ValueError:raise WorkflowError('DEVELOPMENT_PROCESS_CWD_REFUSED') from None
        if relative.parts:
            from .local_state import guard_control
            guard_control(ROOT,relative,'dir')
        cwd = target
    argv=list(argv)
    if str(argv[0])=='node' and dev.development_mode(ROOT):
        from .development_setup import mode
        argv[0]=mode(ROOT)['node']['binary']
    if str(argv[0]) in {'ffmpeg','ffprobe'}:argv[0]=media_binary(str(argv[0]),'hyperframes') if private else media_binary(str(argv[0]))
    # Never persist raw process output here: a tool can emit machine paths or credentials.
    try:
        if os.name=='nt':
            from .windows_native import launch
            process=launch(argv,cwd=cwd,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        else:
            process = subprocess.Popen([str(x) for x in argv], cwd=cwd, env=env,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE,start_new_session=True)
        deadline=time.monotonic()+timeout
        try:
            while True:
                cancel=getattr(PROCESS_CONTEXT,'cancel',None)
                if cancel and cancel.is_set():raise KeyboardInterrupt()
                remaining=deadline-time.monotonic()
                if remaining<=0:raise subprocess.TimeoutExpired(argv,timeout)
                try:
                    stdout,stderr=process.communicate(timeout=min(.25,remaining));break
                except subprocess.TimeoutExpired:
                    if time.monotonic()>=deadline:raise
        except (subprocess.TimeoutExpired, KeyboardInterrupt):
            # Only our newly created process group; no discovery or other-session control.
            stop_owned_group(process)
            raise WorkflowError('Local tool timed out or was cancelled; owned process group stopped. Completed stage hashes are preserved.')
        finally:
            if os.name=='nt':
                from .windows_native import close_job
                close_job(process,terminate=process.poll() is None)
    except OSError:
        raise WorkflowError('Local tool unavailable or timed out; see doctor and retry local stage')
    if process.returncode:
        # Only save a redacted tail; no secret values are echoed back.
        tail = (stdout + stderr).decode(errors='replace')[-12000:]
        if scan_bytes(tail.encode()):
            tail = '[tool output withheld by secrets filter]'
        tail = tail.replace(str(Path.home()), '$HOME')
        raise WorkflowError(f'Local tool exited {process.returncode}: {tail}')
    return stdout


def probe(path,restricted_audio=False):
    from .audio_input import approved_audio_options
    options=approved_audio_options(path) if restricted_audio else []
    data=json.loads(checked_process(['ffprobe','-v','error',*options,'-show_streams','-show_format','-of','json',path]))
    # Do not retain absolute source path or arbitrary media tags.
    return {'duration': float(data['format']['duration']), 'streams':[
        {k:s[k] for k in ['codec_type','codec_name','width','height','r_frame_rate','sample_aspect_ratio','sample_rate','channels','duration'] if k in s}
        for s in data['streams']]}


def validate(brief, profile):
    if brief.get('template_family'):
        from .template_families import validate_brief
        validate_brief(brief,profile)
        return
    from .creative import load_pack
    actions={'unlock','open','reveal','flow'}
    if brief.get('creative'):
        actions=set(load_pack(profile['id'])['scene_actions'])
    if brief.get('schema_version') != 1 or brief.get('brand') != profile['id']:
        raise WorkflowError('Unknown schema or brand profile')
    for field in ['title','brief','script','caption']:
        if not isinstance(brief.get(field), str) or not brief[field].strip():
            raise WorkflowError(f'Missing {field}')
    if len(brief['title']) > 65:
        raise WorkflowError('Title exceeds small-template capacity (65 characters)')
    duration=finite(brief.get('duration'),'duration',1,90)
    if brief.get('language','tr') not in {'tr','en','de'}:raise WorkflowError('Supported composition languages: tr, en, de')
    if brief.get('alignment') not in {'provisional_silent','imported_timing'}:
        raise WorkflowError('Alignment must be explicitly provisional_silent or imported_timing')
    if not isinstance(brief.get('demo'),bool):
        raise WorkflowError('demo flag is required')
    if not isinstance(brief.get('claims'), list):
        raise WorkflowError('claims must be a list; each factual claim requires a source')
    for claim in brief['claims']:
        if not claim.get('text') or not claim.get('source') or not claim.get('scope'):
            raise WorkflowError('Claim requires text, source and scope; human source review remains required')
    if profile.get('continuity_required') and not all(brief.get('continuity',{}).get(x) for x in ['object_id','previous','next']):
        raise WorkflowError('Serial format requires object_id, previous and next continuity')
    scenes=brief.get('scenes',[])
    if not 1 <= len(scenes) <= 12:
        raise WorkflowError('Expected 1–12 scenes')
    end=0; ids=set()
    for s in scenes:
        a=finite(s.get('start'),'scene start',0,duration); z=finite(s.get('end'),'scene end',0,duration)
        if abs(a-end) > .001 or z<=a or z-a<1.6:
            raise WorkflowError('Scenes must be contiguous, ordered, and at least 1.6s')
        if not re.fullmatch(r'[a-z][a-z0-9-]{0,39}',s.get('id','')) or s['id'] in ids:
            raise WorkflowError('Scene ids must be unique simple identifiers')
        if s.get('action') not in actions:
            raise WorkflowError('Scene action is outside the selected versioned profile')
        if s['action']=='flow':
            nodes=s.get('nodes')
            if not isinstance(nodes,list) or not 2<=len(nodes)<=4 or not all(isinstance(x,str) and 1<=len(x)<=14 for x in nodes):raise WorkflowError('Flow requires 2–4 node labels, each 1–14 characters')
            for field in ['from_node','to_node']:
                if type(s.get(field)) is not int or not 0<=s[field]<len(nodes):raise WorkflowError('Flow node index outside diagram')
            if s['from_node']==s['to_node']:raise WorkflowError('Flow must change node')
        for f in ['heading','information','object_before','object_after']:
            if not isinstance(s.get(f),str) or not s[f].strip():
                raise WorkflowError(f'Scene requires {f}')
        if len(s['heading'])>50:
            raise WorkflowError('Scene heading exceeds template capacity')
        ids.add(s['id']); end=z
    if abs(end-duration)>.001:
        raise WorkflowError('Scenes must cover duration')
    last=0
    if not brief.get('cues'):
        raise WorkflowError('At least one cue is required')
    for c in brief['cues']:
        a=finite(c.get('start'),'cue start',0,duration); z=finite(c.get('end'),'cue end',0,duration)
        if a<last or z<=a or not isinstance(c.get('text'),str) or not c['text'].strip() or len(c['text'])>95:
            raise WorkflowError('Invalid, overlapping or oversized subtitle cue')
        last=z
    if ' '.join(' '.join(c['text'].split()) for c in brief['cues']) != ' '.join(brief['script'].split()):
        raise WorkflowError('Cue text must match the full script, preserving case and punctuation')
    if scan_bytes(canonical(brief).encode()):
        raise WorkflowError('Possible secret in brief; input refused without echoing its value')


def apply_appearance(profile,appearance):
    profile=json.loads(canonical(profile))
    if appearance is None:return profile
    if not isinstance(appearance,dict) or set(appearance)!={'palette','title_size','subtitle_size'}:raise WorkflowError('Appearance supports palette, title_size and subtitle_size only')
    palette=appearance['palette']
    if not isinstance(palette,dict) or set(palette)!={'background','ink','muted','accent'} or not all(isinstance(v,str) and re.fullmatch('#[a-fA-F0-9]{6}',v) for v in palette.values()):raise WorkflowError('Appearance palette requires four hex colors')
    finite(appearance['title_size'],'title_size',48,100);finite(appearance['subtitle_size'],'subtitle_size',36,60)
    profile.update(appearance);return profile


def prepare_input(brief):
    brand=brief.get('brand','')
    from .creative import ACCOUNTS,validate_proposal
    if brand not in ACCOUNTS:
        raise WorkflowError('Choose a valid local AccountPack')
    if brief.get('template_family'):
        profile=render_profile(brand)
        from .identity import apply_identity
        profile=apply_identity(profile,brief.get('brand_identity',{'name':'','handle':''}))
        validate_render_profile(profile)
        validate(brief,profile)
        return brief,profile
    if brief.get('creative'):
        # These two bounded host controls are not part of model JSON output.
        host={key:brief.pop(key) for key in ('appearance','production_notes','brand_identity','revision_context','raster','scene_plan','rig') if key in brief}
        if brief.get('audio') or brief.get('audio_timing'):
            from .audio_retime import validate_timed_brief
            audio=brief['audio'];timing=brief['audio_timing']
            brief=validate_timed_brief(brief)
            brief.update(audio=audio,audio_timing=timing,alignment='imported_timing')
        else:
            from .writing_context import bound_brief
            brief=bound_brief(brand,brief)
        brief.update(host)
        from .rig_revision import RIG_TIMING_MARKER
        if brief.get('rig'):
            from .viseme import validate_rig
            if brief.get('audio_timing',{}).get('viseme')!=RIG_TIMING_MARKER:raise WorkflowError('RIG_FRESH_TIMING_REQUIRED: Ayrı taze ağız girdisi zamanlama manifestine bağlanmalı')
            brief['rig']=validate_rig(brief['rig'],brief)
        elif brief.get('audio_timing',{}).get('viseme')==RIG_TIMING_MARKER:
            raise WorkflowError('RIG_TRACK_MISSING: Konuşan rig için taze ağız girdisi eksik')
        if brief.get('scene_plan'):
            from .scene_plan import validate_scene_plan
            validate_scene_plan(brief['scene_plan'],brief)
        if brief.get('raster'):
            from .raster_view import validate_raster
            validate_raster(brief['raster'],brief)
    elif not capability(brand, 'legacy_fixture'):
        raise WorkflowError('This account requires a versioned creative proposal')
    profile=render_profile(brand)
    profile=apply_appearance(profile,brief.get('appearance'))
    brief.setdefault('brand_identity',{'name':'','handle':''})
    if 'brand_identity' in brief:
        from .identity import apply_identity
        profile=apply_identity(profile,brief['brand_identity'])
    validate_render_profile(profile)
    validate(brief,profile)
    return brief,profile


class Engine:
    def __init__(self, workspace='work', hf=None):
        self._workspace=workspace
        self._store=None
        # Default is always project-local. A historical npx cache is never discovered.
        self.hf=Path(hf or ROOT/'node_modules/hyperframes/dist/cli.js')

    def close(self):
        if self._store is not None:
            self._store.close()
            self._store=None

    def __enter__(self):return self
    def __exit__(self,*args):self.close()

    @property
    def store(self):
        if self._store is None:self._store=Store(self._workspace)
        return self._store

    def plan(self, brief_path, render_engine='hyperframes'):
        from .runtime import ENGINES
        if render_engine not in ENGINES:raise WorkflowError('Choose hyperframes or remotion; no automatic fallback')
        path=Path(brief_path).resolve()
        brief=json.loads(path.read_text())
        brief,profile=prepare_input(brief)
        payload={'render_engine':render_engine,'engine_version':__version__,'engine_sha256':digest({p.relative_to(ROOT).as_posix():file_hash(p) for p in sorted((ROOT/'storymotion').glob('*.py'))}),
                 'vendor_sha256':digest({p.relative_to(ROOT).as_posix():file_hash(p) for p in sorted((ROOT/'vendor').rglob('*')) if p.is_file()}),
                 'brief':brief,'profile':profile}
        from .provenance import execution_provenance
        payload['execution']=execution_provenance()
        if brief.get('creative'):
            from .edit_plan import compile_edit_plan
            payload['edit_plan']=compile_edit_plan(profile,brief,ROOT)
        if brief.get('audio'):
            spec=brief['audio']
            if brief['alignment']!='imported_timing' or not spec.get('approved_by') or not spec.get('rights_note'):
                raise WorkflowError('Audio import requires imported_timing, approved_by and rights_note')
            source=within(path.parent,spec.get('file',''))
            if source.suffix.lower() not in {'.wav','.mp3','.m4a'} or not source.is_file():
                raise WorkflowError('Missing local audio file')
            actual=file_hash(source)
            if actual!=spec.get('sha256'):
                raise WorkflowError('Audio hash differs from approved source')
            from .audio_input import approved_audio_options
            if brief.get('audio_timing'):approved_audio_options(source)
            media=probe(source,restricted_audio=bool(brief.get('audio_timing')))
            if not any(s['codec_type']=='audio' for s in media['streams']) or media['duration']>brief['duration']+.05:
                raise WorkflowError('Audio must fit naturally in timeline; no speed-up or automatic trim')
            if brief['cues'][-1]['end']>media['duration']+.5:
                raise WorkflowError('Last imported cue falls outside approved audio')
            if brief.get('audio_timing') and abs(media['duration']-brief['audio_timing']['audio_duration_seconds'])>.002:
                raise WorkflowError('Measured audio duration changed from the timing revision')
            payload.update(audio_source=str(source),audio_duration=media['duration'],audio_sha256=actual)
        elif brief['alignment']!='provisional_silent':
            raise WorkflowError('Measured alignment requires a local audio source')
        if brief.get('raster'):
            from .raster_revision import pinned_path
            from .raster_io import validate_normalized
            spec=brief['raster']['asset'];raster_path=pinned_path(path.parent,spec['file']);validate_normalized(raster_path,spec['sha256'],spec['width'],spec['height'])
            payload.update(raster_source=str(raster_path),raster_sha256=spec['sha256'])
        identity=dict(payload)
        identity.pop('raster_source',None)
        identity.pop('audio_source',None)  # content identity survives relocating the same bytes
        job=digest(identity)[:24]
        if brief.get('audio'):
            staged=Path(self._workspace).resolve()/'.inputs'/job/('approved'+source.suffix.lower())
            if staged.exists():
                if staged.is_symlink() or file_hash(staged)!=actual:raise WorkflowError('Immutable staged audio changed')
                payload['audio_source']=str(staged)
        if brief.get('raster'):
            staged=Path(self._workspace).resolve()/'.inputs'/job/'raster.png'
            if staged.exists():
                from .raster_revision import pinned_path
                from .raster_io import validate_normalized
                pinned_path(Path(self._workspace).resolve(),'.inputs/'+job+'/raster.png');validate_normalized(staged,payload['raster_sha256'],brief['raster']['asset']['width'],brief['raster']['asset']['height']);payload['raster_source']=str(staged)
        return job,payload

    def create(self, path, dry_run=False, render_engine='hyperframes'):
        job,payload=self.plan(path,render_engine)
        if dry_run:
            return {'job':job,'render_engine':render_engine,'mode':'dry_run','stages':STAGES,'paid_calls':0,'external_calls':0,
                    'audio':'import_local_approved' if payload['brief'].get('audio') else 'silent_provisional',
                    'new_generation':'blocked; no live adapter in this release'}
        with self.store.lock():
            if payload['brief'].get('audio'):
                source=Path(payload['audio_source'])
                rel='.inputs/'+job+'/approved'+source.suffix.lower()
                staged=within(self.store.root,rel);private_directory(staged.parent)
                if not staged.is_file() or file_hash(staged)!=payload['audio_sha256']:
                    tmp=staged.with_suffix(staged.suffix+'.tmp');copy_private(source,tmp)
                    if file_hash(tmp)!=payload['audio_sha256']:
                        tmp.unlink(missing_ok=True);raise WorkflowError('Audio changed while staging approved source')
                    tmp.replace(staged)
                payload['audio_source']=rel
            if payload['brief'].get('raster'):
                from .raster_revision import pinned_path
                source=Path(payload['raster_source']);rel='.inputs/'+job+'/raster.png';staged=pinned_path(self.store.root,rel);private_directory(staged.parent)
                if not staged.exists():
                    copy_private(source,staged)
                if staged.is_symlink() or file_hash(staged)!=payload['raster_sha256']:raise WorkflowError('Immutable staged raster changed')
                payload['raster_source']=rel
            self.store.db.execute('INSERT OR IGNORE INTO jobs VALUES(?,?,?)',(job,canonical(payload),now()))
            self.store.db.commit()
            self.store.event(job,'intake','created_or_reused')
        return {'job':job,'mode':'local','render_engine':render_engine}

    def payload(self,job):
        row=self.store.db.execute('SELECT payload FROM jobs WHERE id=?',(job,)).fetchone()
        if not row:
            raise WorkflowError('Unknown job')
        payload=json.loads(row[0])
        if payload.get('audio_source') and not Path(payload['audio_source']).is_absolute():
            payload['audio_source']=str(within(self.store.root,payload['audio_source']))
        if payload.get('raster_source'):
            from .raster_revision import pinned_path
            raw=Path(payload['raster_source'])
            try:rel=str(raw.relative_to(self.store.root)) if raw.is_absolute() else str(raw)
            except ValueError:raise WorkflowError('Raster source escapes the immutable workspace') from None
            payload['raster_source']=str(pinned_path(self.store.root,rel))
        return payload

    def directory(self,job):
        self.payload(job)
        if (self.store.root/job).is_symlink():raise WorkflowError('Engine output directory must not be linked')
        return within(self.store.root,job)

    def hf_call(self,args,cwd,timeout=180):
        from .runtime import require_engine
        require_engine('hyperframes')
        if not self.hf.is_file():
            raise WorkflowError('HyperFrames missing: follow docs/INSTALL.md; no auto-install')
        return checked_process(['node',self.hf,*args],cwd,timeout)

    def manifest_valid(self,job,stage):
        row=self.store.stage(job,stage)
        if not row or row['status']!='complete': return False
        manifest=json.loads(row['manifest'])
        if stage=='prepare':
            from .edit_plan import verify_staged_assets
            try:verify_staged_assets(self.payload(job),self.directory(job))
            except WorkflowError:return False
        return bool(manifest) and all(within(self.directory(job),p).is_file() and file_hash(within(self.directory(job),p))==h for p,h in manifest.items())

    def run(self,job,until='delivery',cancel_event=None):
        from .development_policy import assert_job_scope
        assert_job_scope(self,job,until)
        with process_cancellation(cancel_event),self.store.lock():
            payload=self.payload(job)
            from .provenance import execution_provenance
            if payload.get('execution',{}).get('fingerprint')!=execution_provenance()['fingerprint']:
                raise WorkflowError('Execution code/adapter/vendor changed; create a new pinned job before resuming')
            if payload['brief'].get('audio_timing') and file_hash(payload['audio_source'])!=payload['audio_sha256']:
                raise WorkflowError('Immutable audio source changed; downstream stages invalidated')
            if payload.get('raster_source'):
                from .raster_io import validate_normalized
                from .raster_revision import pinned_path
                spec=payload['brief']['raster']['asset'];pinned_path(self.store.root,str(Path(payload['raster_source']).relative_to(self.store.root)));validate_normalized(Path(payload['raster_source']),spec['sha256'],spec['width'],spec['height'])
            out=self.directory(job);private_directory(out)
            invalid=False
            for stage in STAGES[:STAGES.index(until)+1]:
                if cancel_event and cancel_event.is_set():raise WorkflowError('Local render cancelled; completed stage hashes preserved')
                if not invalid and self.manifest_valid(job,stage):
                    self.store.event(job,stage,'reused_hash_verified');continue
                invalid=True
                self.store.set_stage(job,stage,'in_progress')
                self.store.event(job,stage,'started')
                try:
                    files=self.perform(stage,payload,out)
                    manifest={f:file_hash(within(out,f)) for f in files}
                    self.store.set_stage(job,stage,'complete',manifest)
                    self.store.event(job,stage,'completed',{'files':len(files),'actual_microusd':0})
                    # Descendants are invalid immediately, including when --until stops here.
                    for later in STAGES[STAGES.index(stage)+1:]:
                        self.store.set_stage(job,later,'pending')
                except Exception as e:
                    msg=str(e).replace(str(Path.home()),'$HOME')
                    if scan_bytes(msg.encode()):msg='Error details withheld by secrets filter'
                    self.store.set_stage(job,stage,'failed',error=msg)
                    self.store.event(job,stage,'failed',{'error':msg})
                    raise WorkflowError(msg)
        return self.store.status(job)

    def perform(self,stage,payload,out):
        brief=payload['brief']
        render_engine=payload.get('render_engine','hyperframes')
        from .development_templates import FAMILIES as DEVELOPMENT_FAMILIES
        if stage!='prepare':
            if brief.get('template_family',{}).get('id') in DEVELOPMENT_FAMILIES:
                from .development_templates import verify_staged
                verify_staged(out)
            from .edit_plan import verify_staged_assets
            verify_staged_assets(payload,out)
        if stage=='prepare':
            if brief.get('creative'):
                from .edit_plan import verify_edit_plan
                verify_edit_plan(payload,ROOT)
            if brief.get('audio') and file_hash(payload['audio_source'])!=payload['audio_sha256']:
                raise WorkflowError('Imported audio changed since intake')
            files=build(payload,out,ROOT)
            if brief.get('revision_context'):
                write_json(out/'revision.json',brief['revision_context']);files.append('revision.json')
            if brief.get('creative'):
                write_json(out/'edit-plan.json',payload['edit_plan']);files.append('edit-plan.json')
            if brief.get('production_context'):
                write_json(out/'source-brief.json',brief)
                write_json(out/'writing-context.json',{'binding':brief['production_context'],'claim_traceability':brief.get('creative',{}).get('audit',{}).get('claim_traceability',brief.get('template_audit')),
                    'source_truth':'pending_human_review','canon_authority':'host_attested_reference_not_independent_final_QA'})
                files+=['source-brief.json','writing-context.json']
            if brief.get('audio_timing'):
                write_json(out/'audio-timing.json',brief['audio_timing']);files.append('audio-timing.json')
            shutil.copyfile(ROOT/'knowledge/production-playbook.md',out/'WORKFLOW.md')
            files.append('WORKFLOW.md')
            if render_engine=='remotion':
                from .compose import creative_objects
                write_json(out/'remotion-props.json',{'brief':brief,'profile':payload['profile'],
                           'vectors':{f's{i}':s['vector'] for i,s in enumerate(payload['edit_plan']['scenes'])} if brief.get('creative') else {},
                           'edit_plan':payload.get('edit_plan'),
                           'rig_definition':json.loads((out/'assets/rig/definition.json').read_text()) if brief.get('rig') else None,
                           'template_scene':json.loads((out/'template-scene.json').read_text()) if brief.get('template_family') else None,
                           'audio_file':'narration'+Path(payload['audio_source']).suffix.lower() if brief.get('audio') else None})
                entry=(ROOT/'renderers/remotion/entry.jsx').read_text().replace("from '../edit-motion.mjs'","from './edit-motion.mjs'").replace("from '../template-motion.mjs'","from './template-motion.mjs'")
                if brief.get('template_family',{}).get('id') in DEVELOPMENT_FAMILIES:
                    entry=entry.replace("from '../template-registry/registry.mjs'","from './template-registry/registry.mjs'").replace("from '../svg-tree.mjs'","from './svg-tree.mjs'")
                else:
                    entry=entry.replace("import {compileStaged} from '../template-registry/registry.mjs';","const compileStaged=()=>{throw Error('Development scene not selected');};").replace("import {parseSvg} from '../svg-tree.mjs';","const parseSvg=()=>{throw Error('Development scene not selected');};")
                if not brief.get('template_family'):
                    shutil.copyfile(ROOT/'renderers/template-motion.mjs',out/'template-motion.mjs')
                    files.append('template-motion.mjs')
                line="import {sampleRig,rigSvg} from '../rig-motion.mjs';"
                entry=entry.replace(line,"import {sampleRig,rigSvg} from './assets/rig/rig-motion.mjs';" if brief.get('rig') else "const sampleRig=()=>null,rigSvg=()=>'';")
                write_private(out/'remotion-entry.jsx',entry)
                shutil.copyfile(ROOT/'renderers/edit-motion.mjs',out/'edit-motion.mjs')
                files+=['remotion-props.json','remotion-entry.jsx','edit-motion.mjs']
            return files
        if stage=='check':
            if render_engine=='remotion':
                from .runtime import require_engine
                require_engine('remotion')
                raw=checked_process(['node',ROOT/'tools/remotion.mjs','check',out],ROOT,240)
            else:raw=self.hf_call(['check','--json','--samples','9'],out)
            result=json.loads(raw)
            if not result.get('ok') or result.get('browserSkipped'):
                raise WorkflowError(f'{render_engine} browser check did not pass')
            write_json(out/'check.json',result)
            return ['check.json']
        if stage=='render':
            if render_engine=='remotion':
                from .runtime import require_engine
                require_engine('remotion')
                checked_process(['node',ROOT/'tools/remotion.mjs','render',out],ROOT,600)
            else:self.hf_call(['render','--quality','looks','--fps','30','--workers','1','--output','render-1080.mp4'],out,600)
            # Remotion's encoded H.264 may omit SAR. Set stream/container aspect
            # metadata without changing pixels, speech timing or re-encoding.
            normalized=out/'.square-pixels.mp4'
            checked_process(['ffmpeg','-v','error','-y','-i',out/'render-1080.mp4','-map','0','-c','copy',
                '-bsf:v','h264_metadata=sample_aspect_ratio=1/1','-aspect','9:16','-movflags','+faststart',normalized])
            video=next(s for s in probe(normalized)['streams'] if s['codec_type']=='video')
            if (video.get('width'),video.get('height'),video.get('sample_aspect_ratio'))!=(1080,1920,'1:1'):
                raise WorkflowError('Rendered frame dimensions or square-pixel metadata failed; no delivery receipt')
            normalized.replace(out/'render-1080.mp4')
            versions=json.loads((ROOT/'renderers/versions.json').read_text())
            write_json(out/'render-engine.json',{'engine':render_engine,'version':versions[render_engine],
                'chrome_version':versions['chrome_headless_shell'],'render_sha256':file_hash(out/'render-1080.mp4'),
                'execution_fingerprint':payload['execution']['fingerprint'],'paid_provider_calls':0,
                **({'scene_plan_sha256':digest(brief['scene_plan'])} if brief.get('scene_plan') else {}),
                **({'rig_sha256':digest(brief['rig']),'rig_definition_sha256':brief['rig']['rig_sha256']} if brief.get('rig') else {}),
                **({'raster_sha256':digest(brief['raster']),'raster_asset_sha256':brief['raster']['asset']['sha256']} if brief.get('raster') else {}),
                **({'audio_timing_sha256':digest(brief['audio_timing']),'audio_sha256':payload['audio_sha256']} if brief.get('audio_timing') else {})})
            return ['render-1080.mp4','render-engine.json']
        if stage=='mobile':
            checked_process(['ffmpeg','-v','error','-y','-i',out/'render-1080.mp4','-vf','scale=540:960','-c:v','libx264','-preset','fast','-crf','23','-c:a','aac','-movflags','+faststart',out/'render-mobile.mp4'],timeout=180)
            return ['render-mobile.mp4']
        if stage=='cover':
            # Cover renders in the same installed Chrome, not a generated raster or paid call.
            checked_process(['node',ROOT/'tools/cover.mjs',self.hf,out],timeout=60)
            return ['cover.png','cover-360.png','browser-evidence.json']
        if stage=='qa':
            media={}
            for name,expected in [('render-1080.mp4',(1080,1920)),('render-mobile.mp4',(540,960))]:
                report=probe(out/name);v=next((x for x in report['streams'] if x['codec_type']=='video'),{})
                if (v.get('width'),v.get('height'))!=expected or v.get('codec_name')!='h264' or v.get('r_frame_rate')!='30/1' or abs(report['duration']-brief['duration'])>.15:
                    raise WorkflowError('Render dimensions, codec, frame rate or duration mismatch')
                sound=[x for x in report['streams'] if x['codec_type']=='audio']
                if bool(sound)!=bool(brief.get('audio')) or (sound and sound[0]['codec_name']!='aac'):
                    raise WorkflowError('Unexpected or missing AAC audio track')
                # The npm compositor build omits wrapped_avframe, the null muxer's
                # default encoder. Explicit raw/PCM keeps a real complete decode.
                checked_process(['ffmpeg','-v','error','-xerror','-i',out/name,'-c:v','rawvideo','-c:a','pcm_s16le','-f','null','-'],timeout=180)
                media[name]={'sha256':file_hash(out/name),'full_decode':'pass',**report}
            review=self.review_template(out,payload)
            write_json(out/'qa.json',{'technical':'pass','render_engine':render_engine,'media':media,'subtitle_timing':brief['alignment'],
                       'cue_text_match':'pass','audio_source_sha256':payload.get('audio_sha256'),
                       'playback_rate':1,'audio_processing':'no trim, rate or gain change in source; final AAC encode',
                       'human_review':review,'actual_paid_calls':0,'actual_microusd':0,
                       **({'rig_sha256':digest(brief['rig']),'rig_definition_sha256':brief['rig']['rig_sha256'],'human_phonetic':'pending','human_rig_visual':'pending'} if brief.get('rig') else {}),
                       **({'audio_timing_sha256':digest(brief['audio_timing']),'viseme':brief['audio_timing']['viseme']} if brief.get('audio_timing') else {})})
            return ['qa.json']
        if stage=='delivery':
            if brief.get('audio_timing'):
                from .audio_retime import verify_final_audio
                verify_final_audio(payload,out)
            # Technical package is allowed before human review; its label never says final.
            files=['BRIEF.md','WORKFLOW.md','index.html','hyperframes.json','index.motion.json','timeline.json','profile.json',
                   'caption.txt','subtitles.srt','cover.svg','cover.html','cover.png','cover-360.png',
                   'render-1080.mp4','render-mobile.mp4','render-engine.json','qa.json','check.json','browser-evidence.json']
            if render_engine=='remotion':files+=['remotion-props.json','remotion-entry.jsx','edit-motion.mjs']
            if brief.get('template_family'):
                files+=['template-motion.mjs','template-scene.json','template-selection.json']
                if brief['template_family']['id'] in DEVELOPMENT_FAMILIES:
                    from .development_templates import staged_files
                    files+=staged_files()
            elif render_engine=='remotion':files.append('template-motion.mjs')
            if brief.get('raster'):files.append('raster.json')
            if brief.get('scene_plan'):files.append('manual-plan.json')
            if brief.get('rig'):files.append('rig.json')
            if brief.get('audio_timing'):files.append('audio-timing.json')
            if brief.get('production_context'):files+=['source-brief.json','writing-context.json']
            if brief.get('creative'):files.append('edit-plan.json')
            if brief.get('revision_context'):files.append('revision.json')
            files += [p.relative_to(out).as_posix() for p in (out/'assets').rglob('*') if p.is_file()]
            write_json(out/'delivery.json',{'status':'technical_review_copy','final_release':'pending_human_review',
                       'demo':brief['demo'],'render_engine':render_engine,
                       **({'scene_plan_sha256':digest(brief['scene_plan'])} if brief.get('scene_plan') else {}),
                **({'raster_sha256':digest(brief['raster']),'raster_asset_sha256':brief['raster']['asset']['sha256'],'customer_asset_distribution':'private_project_only_unless_separately_licensed'} if brief.get('raster') else {}),'files':{f:file_hash(out/f) for f in files},
                       **({'writing_context_sha256':brief['production_context']['binding_sha256']} if brief.get('production_context') else {}),
                       **({'edit_plan_sha256':payload['edit_plan']['plan_sha256']} if brief.get('creative') else {}),
                       **({'rig_sha256':digest(brief['rig']),'rig_definition_sha256':brief['rig']['rig_sha256'],'human_phonetic':'pending','human_rig_visual':'pending'} if brief.get('rig') else {}),
                       **({'revision_sha256':brief['revision_context']['binding_sha256']} if brief.get('revision_context') else {}),
                       **({'audio_timing_sha256':digest(brief['audio_timing']),'audio_sha256':payload['audio_sha256'],
                           'main_render_sha256':file_hash(out/'render-1080.mp4'),'mobile_render_sha256':file_hash(out/'render-mobile.mp4'),
                           'publication_ready':False} if brief.get('audio_timing') else {})})
            files.append('delivery.json')
            with zipfile.ZipFile(out/'delivery.zip.tmp','w',zipfile.ZIP_DEFLATED) as z:
                for f in sorted(files):z.write(out/f,f)
            (out/'delivery.zip.tmp').replace(out/'delivery.zip')
            with zipfile.ZipFile(out/'delivery.zip') as z:
                if z.testzip() or len(z.namelist())!=len(files) or set(z.namelist())!=set(files): raise WorkflowError('Delivery ZIP verification failed')
            from .edit_plan import verify_staged_assets
            verify_staged_assets(payload,out,delivery=True)
            return ['delivery.json','delivery.zip']
        raise WorkflowError('Unknown stage')

    def review_template(self,out,payload):
        return {'story':'pending','visual':'pending','cover':'pending','caption':'pending',
                'audio_listening':'pending' if payload['brief'].get('audio') else 'not_applicable_silent_demo',
                'subtitle_semantics':'pending','final_watch':'pending',
                'device_preview':'simulated_360px; no physical device test',
                'render_sha256':file_hash(out/'render-1080.mp4')}

    def request(self,job,provider,model,voice,estimate_usd,quote_source):
        payload=self.payload(job)
        cost=microusd(estimate_usd)
        if not all(isinstance(x,str) and x.strip() for x in [provider,model,voice,quote_source]):raise WorkflowError('Complete request identity and quote source required')
        req={'job':job,'kind':'voice','provider':provider,'model':model,'voice':voice,
             'script_sha256':digest(payload['brief']['script']),'characters':len(payload['brief']['script']),
             'estimate_microusd':cost,'quote_source':quote_source}
        if scan_bytes(canonical(req).encode()):raise WorkflowError('Request contains possible secret')
        key=digest({k:v for k,v in req.items() if k not in {'estimate_microusd','quote_source'}})
        with self.store.lock():
            existing=self.store.db.execute('SELECT payload FROM requests WHERE id=?',(key,)).fetchone()
            if existing and existing[0]!=canonical(req):raise WorkflowError('Request identity already exists with another quote; no second dispatch or silent repricing')
            self.store.db.execute('INSERT OR IGNORE INTO requests(id,job,payload,status) VALUES(?,?,?,?)',(key,job,canonical(req),'awaiting_budget'))
            self.store.db.commit();self.store.event(job,'voice','request_prepared',{'request':key,'live_adapter':'disabled'})
        return dict(id=key,**req,live_adapter='disabled')

    def approve(self,request,cap,approver,hours=1):
        amount=microusd(cap)
        if not approver.strip():raise WorkflowError('Named approval evidence required')
        finite(hours,'approval hours',.01,24)
        if scan_bytes(approver.encode()):raise WorkflowError('Approval evidence contains possible secret')
        with self.store.lock():
            row=self.store.db.execute('SELECT * FROM requests WHERE id=?',(request,)).fetchone()
            if not row or row['status'] not in {'awaiting_budget','approved'}:raise WorkflowError('Request cannot be approved in its current state')
            req=json.loads(row['payload'])
            if amount<req['estimate_microusd']:raise WorkflowError('Budget cap below the quoted estimate')
            until=(datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(hours=hours)).isoformat()
            self.store.db.execute('UPDATE requests SET status=?,cap_microusd=?,approver=?,approved_until=? WHERE id=?',('approved',amount,approver,until,request))
            self.store.db.commit();self.store.event(row['job'],'voice','budget_recorded',{'request':request,'cap_microusd':amount,'live_adapter':'disabled'})
        return {'request':request,'status':'approved_for_mock_only','actual_microusd':0}

    def execute_voice(self,request,simulate_uncertain=False):
        with self.store.lock():
            row=self.store.db.execute('SELECT * FROM requests WHERE id=?',(request,)).fetchone()
            if not row:raise WorkflowError('Unknown request')
            req=json.loads(row['payload'])
            if req['provider']!='mock':
                self.store.event(row['job'],'voice','blocked_live_provider',{'request':request})
                raise WorkflowError('Live voice/model calls are disabled in this release, even with budget recorded')
            if row['status']=='completed':return {'status':'reused','receipt':json.loads(row['receipt'])}
            if row['status'] in {'dispatching','uncertain'}:raise WorkflowError('Outcome uncertain; reconcile evidence first. Automatic retry forbidden')
            if row['status']!='approved' or not row['approved_until'] or now()>row['approved_until'] or row['cap_microusd']<req['estimate_microusd']:
                raise WorkflowError('Fresh request-specific budget approval required')
            # Persist intent BEFORE dispatch. A process death here is conservatively uncertain.
            self.store.db.execute('UPDATE requests SET status=? WHERE id=?',('dispatching',request));self.store.db.commit()
            self.store.event(row['job'],'voice','mock_dispatched',{'request':request})
            if simulate_uncertain:
                self.store.db.execute('UPDATE requests SET status=? WHERE id=?',('uncertain',request));self.store.db.commit()
                raise WorkflowError('Simulated lost response; no retry until receipt reconciliation')
            receipt={'request':request,'provider':'mock','simulated':True,'audio_generated':False,'actual_microusd':0,'simulated_microusd':req['estimate_microusd']}
            self._settle(row,receipt)
            return {'status':'completed_mock_only','receipt':receipt}

    def _settle(self,row,receipt):
        self.store.db.execute('INSERT OR IGNORE INTO costs(request,simulated_microusd,actual_microusd,created) VALUES(?,?,0,?)',(row['id'],receipt['simulated_microusd'],now()))
        self.store.db.execute('UPDATE requests SET status=?,receipt=? WHERE id=?',('completed',canonical(receipt),row['id']))
        self.store.db.commit();self.store.event(row['job'],'voice','mock_receipt_recorded',{'request':row['id'],'actual_microusd':0})

    def reconcile(self,request,receipt):
        with self.store.lock():
            row=self.store.db.execute('SELECT * FROM requests WHERE id=?',(request,)).fetchone()
            if not row or row['status'] not in {'uncertain','dispatching'}:raise WorkflowError('Only uncertain mock requests may be reconciled')
            req=json.loads(row['payload'])
            if req['provider']!='mock' or receipt!={'request':request,'provider':'mock','simulated':True,'audio_generated':False,'actual_microusd':0,'simulated_microusd':req['estimate_microusd']}:
                raise WorkflowError('Receipt must exactly match the mock request and estimate')
            self._settle(row,receipt)
        return {'request':request,'status':'reconciled_mock'}

    def logs(self,job):
        return [dict(x) for x in self.store.db.execute('SELECT * FROM events WHERE job=? ORDER BY seq',(job,))]


def microusd(value):
    try:
        num=decimal.Decimal(str(value))
        if not num.is_finite() or num<0 or num>10000 or num*1000000!=(num*1000000).to_integral_value():raise ValueError()
        return int(num*1000000)
    except (decimal.InvalidOperation,ValueError,OverflowError):
        raise WorkflowError('USD amount must be finite, non-negative, <=10000, with <=6 decimals')
