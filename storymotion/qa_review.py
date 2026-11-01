from .local_state import open_control
"""Bounded, local MP4 review artifacts. No network, upstream QA or automatic fix."""
from .local_state import private_directory, private_database, write_private
import contextlib
from . import file_lock as fcntl
import hashlib
import json
import math
import os
import re
import sqlite3
import struct
import tempfile
import threading
import zlib
from pathlib import Path
from .engine import ROOT,checked_process
from .qa_contract import build_sampling_plan,report_template,validate_report,REQUIRED_CHECKS,_hash,_id,_path
from .runtime import media_binary
from .security import WorkflowError,canonical,digest,file_hash,scan_bytes,within,write_json
from .local_state import guard_workspace,guard_control,validate_open_control

MAX_SAMPLES=160
GLYPHS={
 '0':['111','101','101','101','111'],'1':['010','110','010','010','111'],'2':['111','001','111','100','111'],
 '3':['111','001','111','001','111'],'4':['101','101','111','001','001'],'5':['111','100','111','001','111'],
 '6':['111','100','111','101','111'],'7':['111','001','010','010','010'],'8':['111','101','111','101','111'],
 '9':['111','101','111','001','111'],'f':['111','100','110','100','100'],'s':['111','100','111','001','111'],
 '.':['000','000','000','000','010'],' ':['000']*5}


def _label_png(path,text):
    # Tiny owned bitmap timestamp font, not OCR, a downloaded font or browser.
    width,height,scale=270,32,3;rows=[bytearray([241,238,229]*width) for _ in range(height)]
    for i,char in enumerate(text):
        for y,line in enumerate(GLYPHS[char]):
            for x,bit in enumerate(line):
                if bit=='1':
                    for yy in range(scale):
                        for xx in range(scale):
                            px=8+i*12+x*scale+xx;py=8+y*scale+yy
                            if px<width:rows[py][px*3:px*3+3]=b'\x10\x10\x10'
    def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    data=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b''.join(b'\x00'+r for r in rows)))+chunk(b'IEND',b'')
    path.write_bytes(data)


class ReviewService:
    """Server-only API: the server maps a validated Engine job to render_path.

    media_root is fixed by the host, never a request parameter. Client payloads
    must not reach create's path/brief/source/asset arguments directly.
    """
    def __init__(self,qa_root,*,media_root):
        self.root=guard_workspace(qa_root,database='reviews.sqlite3');private_directory(self.root)
        guard_workspace(self.root,database='reviews.sqlite3',canonical_alias=False)
        self._media_root_input=Path(media_root).absolute();self.media_root=Path(media_root).resolve();self.lock=threading.RLock()
        self.db=private_database(self.root,'reviews.sqlite3',check_same_thread=False)
        self._closed=False
        try:
            self.db.execute('CREATE TABLE IF NOT EXISTS reviews(id TEXT PRIMARY KEY, state TEXT, payload TEXT)')
            self.db.execute('CREATE TABLE IF NOT EXISTS defects(review_id TEXT,id TEXT,payload TEXT,PRIMARY KEY(review_id,id))');self.db.commit()
        except BaseException:
            self.close()
            raise

    def close(self):
        with self.lock:
            if not self._closed:
                self.db.close()
                self._closed=True

    def __enter__(self):return self
    def __exit__(self,*args):self.close()

    def _run(self,args,timeout=120):
        name=args[0]
        if name not in {'ffmpeg','ffprobe'} or media_binary(name)==name:raise WorkflowError('Pinned project-local FFmpeg/ffprobe missing; run project doctor/setup separately')
        return checked_process(args,timeout=timeout)

    def _media(self,path):
        candidate=Path(path)
        if not candidate.is_absolute():candidate=self.media_root/candidate
        if candidate.name!='render-1080.mp4' or not candidate.resolve().is_relative_to(self.media_root):raise WorkflowError('QA accepts only the server-mapped Engine render-1080.mp4 inside media_root')
        base=next((p for p in [self.media_root,self._media_root_input] if candidate.is_relative_to(p)),None)
        if base is None:raise WorkflowError('QA media path is outside the host media root')
        relative=candidate.relative_to(base)
        if '..' in relative.parts:raise WorkflowError('QA media traversal is not allowed')
        part=base
        for segment in relative.parts:
            part=part/segment
            if part.is_symlink():raise WorkflowError('QA media symlinks are not allowed')
        if not candidate.is_file():raise WorkflowError('Finished Engine render is missing')
        return candidate.resolve()

    def _row(self,ident):
        if not re.fullmatch(r'[0-9a-f]{24}',str(ident)):raise WorkflowError('Unknown QA review')
        row=self.db.execute('SELECT state,payload FROM reviews WHERE id=?',(ident,)).fetchone()
        if not row:raise WorkflowError('Unknown QA review')
        return row[0],json.loads(row[1])

    def _directory(self,ident):self._row(ident);return within(self.root,ident)
    def _save(self,ident,state,payload):
        guard_workspace(self.root,database='reviews.sqlite3',canonical_alias=False)
        self.db.execute('UPDATE reviews SET state=?,payload=? WHERE id=?',(state,canonical(payload),ident));self.db.commit()

    @contextlib.contextmanager
    def _operation_lock(self,ident):
        # Separate open file descriptions serialize threads, service instances
        # and processes. A crashed process releases this lock automatically.
        if not re.fullmatch(r'[0-9a-f]{24}',str(ident)):raise WorkflowError('Unknown QA review')
        guard_workspace(self.root,database='reviews.sqlite3',canonical_alias=False)
        directory=guard_control(self.root,'.locks','dir')
        private_directory(directory)
        path=guard_control(self.root,'.locks/'+ident+'.lock')
        try:descriptor=open_control(path,os.O_CREAT|os.O_RDWR|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0)|getattr(os,'O_CLOEXEC',0),0o600)
        except OSError:raise WorkflowError('LOCAL_STATE_UNSAFE: QA operation lock unavailable; no external path was followed') from None
        acquired=False
        try:
            validate_open_control(descriptor,private=True)
            try:fcntl.flock(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB);acquired=True
            except BlockingIOError:pass
            yield acquired
        finally:
            if acquired:fcntl.flock(descriptor,fcntl.LOCK_UN)
            os.close(descriptor)

    def _assert_bound(self,payload,media):
        expected=payload.get('expected_render_sha256',payload['render_sha256'])
        if not _hash(expected) or expected!=payload['render_sha256'] or file_hash(media)!=expected:
            raise WorkflowError('Final render differs from the immutable host receipt/hash binding')
        if self._assets(media,dict(payload['asset_hashes']))!=payload['asset_hashes']:
            raise WorkflowError('QA assets changed since the host binding')

    def _capture_attempt(self,ident,payload=None,media=None,*,force=False):
        # One build attempt per explicit request; never an automatic retry loop.
        with self._operation_lock(ident) as acquired:
            if not acquired:
                with self.lock:
                    exists=self.db.execute('SELECT id FROM reviews WHERE id=?',(ident,)).fetchone()
                    if exists:return self.status(ident)
                return {'review_id':ident,'state':'capturing','status':'incomplete','render_sha256':payload['render_sha256']}
            with self.lock:
                row=self.db.execute('SELECT state,payload FROM reviews WHERE id=?',(ident,)).fetchone()
                if row:
                    state,stored=row[0],json.loads(row[1])
                    if state=='invalidated':return self.status(ident)
                    if state=='ready':
                        if not force:return self.status(ident)
                        stored,media,_,_,_,_=self._loaded(ident)
                    elif state not in {'failed','capturing'}:raise WorkflowError('QA capture state is unsupported')
                    # Failed/crash-stale rows need no plan/report/manifest files.
                    payload=stored;media=self._media(payload['media'])
                elif payload is None:raise WorkflowError('Unknown QA review')
                self._assert_bound(payload,media)
                payload=json.loads(canonical(payload))
                attempts=payload.get('capture_attempts',0)
                payload['capture_attempts']=attempts+1 if type(attempts) is int and 0<=attempts<2147483646 else 1
                if row:self._save(ident,'capturing',payload)
                else:
                    self.db.execute('INSERT INTO reviews VALUES(?,?,?)',(ident,'capturing',canonical(payload)));self.db.commit()
            try:
                self._build(ident,payload,media)
                self._assert_bound(payload,media)
            except Exception:
                with self.lock:self._save(ident,'failed',payload)
                raise
        return self.status(ident)

    def _probe(self,path):
        data=json.loads(self._run(['ffprobe','-v','error','-protocol_whitelist','file,pipe','-show_streams','-show_format','-of','json',str(path)]))
        video=next((s for s in data['streams'] if s['codec_type']=='video'),None)
        if not video:raise WorkflowError('QA input has no video stream')
        return {'width':video['width'],'height':video['height'],'fps':video.get('r_frame_rate'),
            'sar':video.get('sample_aspect_ratio','unknown'),'codec':video.get('codec_name'),
            'duration':float(data['format']['duration']),'has_audio':any(s['codec_type']=='audio' for s in data['streams'])}

    def _image_meta(self,path):
        data=path.read_bytes()
        if data[:8]!=b'\x89PNG\r\n\x1a\n':raise WorkflowError('QA image is not a PNG')
        width,height=struct.unpack('>II',data[16:24])
        raw=self._run(['ffmpeg','-nostdin','-v','error','-protocol_whitelist','file,pipe','-i',str(path),'-frames:v','1','-c:v','rawvideo','-pix_fmt','rgba','-f','rawvideo','-'])
        if len(raw)!=width*height*4:raise WorkflowError('QA image full pixel decode failed')
        return {'sha256':file_hash(path),'pixel_sha256':hashlib.sha256(raw).hexdigest(),'width':width,'height':height}

    def _capture(self,media,out,frame,fps,name):
        path=within(out,name);path.parent.mkdir(parents=True,exist_ok=True)
        self._run(['ffmpeg','-nostdin','-v','error','-y','-protocol_whitelist','file,pipe','-ss',f'{frame/fps:.9f}','-i',str(media),
            '-vf','setsar=1','-frames:v','1','-c:v','png','-threads','1','-update','1',str(path)])
        return path

    def _assets(self,media,provided):
        base=media.parent
        if provided is None:
            candidates=[media]+[p for p in (base/'assets').rglob('*') if p.is_file()]
            candidates += [base/n for n in ['index.html','profile.json','remotion-entry.jsx','remotion-props.json'] if (base/n).is_file()]
            if len(candidates)>1000:raise WorkflowError('Too many local QA assets')
            provided={p.relative_to(base).as_posix():None for p in candidates}
        if not isinstance(provided,dict) or not provided:raise WorkflowError('QA assets must be a host-owned file hash map')
        for rel,sha in provided.items():
            path=within(base,rel);raw=base/rel
            if any(p.is_symlink() for p in [raw,*raw.parents] if p!=base and p.is_relative_to(base)) or not path.is_file():raise WorkflowError('QA asset symlink/missing file refused')
            actual=file_hash(path)
            if sha is not None and actual!=sha:raise WorkflowError('QA asset changed or is missing')
            provided[rel]=actual
        return dict(sorted(provided.items()))

    def create(self,render_path,brief,*,source_fingerprint=None,asset_hashes=None,scene_keyframes=None,seed=0,
               expected_render_sha256=None,render_binding=None):
        media=self._media(render_path)
        try:raw=canonical(brief).encode()
        except (TypeError,ValueError,RecursionError):raise WorkflowError('QA canonical brief must be bounded JSON') from None
        if len(raw)>100000 or scan_bytes(raw):raise WorkflowError('QA brief oversized or possible secret')
        source=file_hash(media)
        if expected_render_sha256 is not None and (not _hash(expected_render_sha256) or source!=expected_render_sha256):raise WorkflowError('Final render does not match the host receipt SHA-256')
        if render_binding is not None:
            try:binding_raw=canonical(render_binding)
            except (TypeError,ValueError,RecursionError):raise WorkflowError('Render receipt binding must be bounded host JSON') from None
            if not isinstance(render_binding,dict) or not render_binding or len(binding_raw)>4000 or scan_bytes(binding_raw.encode()):raise WorkflowError('Render receipt binding must be bounded nonsecret host metadata')
            render_binding=json.loads(binding_raw)
        assets=self._assets(media,dict(asset_hashes) if isinstance(asset_hashes,dict) else asset_hashes)
        # Own runtime/contract changes also invalidate capture reuse.
        code={p.name:file_hash(p) for p in [Path(__file__),Path(__file__).with_name('qa_contract.py')]}
        payload={'media':media.relative_to(self.media_root).as_posix(),'render_sha256':source,'brief':json.loads(raw),'asset_hashes':assets,
            'expected_render_sha256':expected_render_sha256 or source,'render_binding':render_binding,
            'source_fingerprint':source_fingerprint,'scene_keyframes':scene_keyframes,'seed':seed,'qa_code':code}
        ident=digest(payload)[:24]
        return self._capture_attempt(ident,payload,media)

    def _build(self,ident,payload,media):
        self._assert_bound(payload,media)
        out=self._directory(ident);private_directory(out);info=self._probe(media)
        if info['fps']!='30/1':raise WorkflowError('QA milestone requires the Engine FPS30 output')
        issues=[json.loads(r[0]) for r in self.db.execute('SELECT payload FROM defects WHERE review_id=? ORDER BY id',(ident,))]
        plan=build_sampling_plan(payload['brief'],payload['render_sha256'],payload['asset_hashes'],fps=30,seed=payload['seed'],width=info['width'],height=info['height'],
            source_fingerprint=payload['source_fingerprint'],scene_keyframes=payload['scene_keyframes'],issue_frames=[i['frame'] for i in issues])
        if len(plan['samples'])>MAX_SAMPLES:raise WorkflowError('QA milestone supports at most 160 planned frames; no silent coverage truncation')
        report=report_template(plan);manifest={};covered={};cells={}
        def add(ident,kind,path,frame=None,bounds=None,parent=None):
            rel=path.relative_to(out).as_posix();meta=self._image_meta(path) if path.suffix=='.png' else {'sha256':file_hash(path),'pixel_sha256':None,'width':None,'height':None}
            manifest[rel]=meta;report['evidence'].append({'id':ident,'kind':kind,'path':rel,'sha256':meta['sha256'],'pixel_sha256':meta['pixel_sha256'],
                'render_sha256':payload['render_sha256'],'frame':frame,'bounds':bounds,'parent_id':parent});return ident
        for sample in plan['samples']:
            path=self._capture(media,out,sample['frame'],30,'frames/'+sample['id']+'.png');evid=add(sample['id'],'frame',path,sample['frame']);covered[sample['id']]=evid
            report['coverage']['samples'].append({'sample_id':sample['id'],'evidence_id':evid})
            label=out/'labels'/f'{sample["id"]}.png';label.parent.mkdir(exist_ok=True);_label_png(label,f'f{sample["frame"]:06d} {sample["frame"]/30:.3f}s')
            cell=out/'cells'/f'{sample["id"]}.png';cell.parent.mkdir(exist_ok=True)
            self._run(['ffmpeg','-nostdin','-v','error','-y','-i',str(path),'-i',str(label),'-filter_complex',
                '[0:v]scale=270:480:flags=lanczos,setsar=1[t];[t][1:v]vstack=inputs=2','-frames:v','1','-c:v','png','-threads','1','-update','1',str(cell)])
            cells[sample['id']]=cell
        def board(path,ids,width,height):
            args=['ffmpeg','-nostdin','-v','error','-y']
            for sid in ids:args+=['-i',str(cells[sid])]
            if len(ids)==1:filters=f'[0:v]pad={width}:{height}:0:0:color=0xF1EEE5'
            else:filters=f'xstack=inputs={len(ids)}:layout='+ '|'.join(f'{i%3*270}_{i//3*512}' for i in range(len(ids)))+f':fill=0xF1EEE5,pad={width}:{height}:0:0:color=0xF1EEE5'
            path.parent.mkdir(exist_ok=True)
            self._run(args+['-filter_complex',filters,'-frames:v','1','-c:v','png','-threads','1','-update','1',str(path)])
        for page in plan['boards']:
            path=out/'boards'/f'page-{page["page"]:03d}.png';board(path,[s['sample_id'] for s in page['slots']],page['width'],page['height'])
            evid=add(f'board-{page["page"]}','board',path)
            report['coverage']['board_pages'].append({'page':page['page'],'evidence_id':evid,'slots':[dict(s,frame_evidence_id=covered[s['sample_id']]) for s in page['slots']]})
        transitions={}
        for sample in plan['samples']:
            for role in sample['roles']:
                if role.startswith('transition:'):
                    _,transition,phase=role.split(':');transitions.setdefault(transition,{})[phase]=sample['id']
        for i,(transition,phases) in enumerate(sorted(transitions.items())):
            path=out/'transitions'/f'transition-{i+1:03d}.png';board(path,[phases[p] for p in ['before','mid','after']],810,512);add(f'transition-{i+1}','board',path)
        decode='pass'
        try:self._run(['ffmpeg','-nostdin','-v','error','-xerror','-protocol_whitelist','file,pipe','-i',str(media),'-c:v','rawvideo','-c:a','pcm_s16le','-f','null','-'],180)
        except WorkflowError:decode='fail'
        dimensions=info['width']==1080 and info['height']==1920 and info['sar']=='1:1' and info['codec']=='h264' and abs(info['duration']-payload['brief']['duration'])<=.15
        measurement=out/'measurements.json';write_json(measurement,{'media':info,'full_decode':decode,'provider_calls':0,'capture':'one FFmpeg decode per unique planned frame','source_renderer_seek':'not_run'})
        evid=add('measurements','measurement',measurement)
        try:
            from .writing_context import audit_bound_claims
            claim_guard=audit_bound_claims(payload['brief'])
        except WorkflowError:
            claim_guard={'status':'fail','reason':'Unregistered source claim or unsourced number/price; production acceptance blocked'}
        claim_path=out/'claim-guard.json';write_json(claim_path,claim_guard);claim_evidence=add('claim-guard','measurement',claim_path)
        report['checks']=[{'id':check,'status':decode if check=='technical_decode' else ('pass' if dimensions else 'fail') if check=='delivery_spec' else 'pending',
            'render_sha256':payload['render_sha256'],'evidence_ids':[evid] if check in {'technical_decode','delivery_spec'} else [],
            'note':'Measured local MP4' if check in {'technical_decode','delivery_spec'} else 'Not executed by local frame/contact-board capture'} for check in REQUIRED_CHECKS]
        for check in report['checks']:
            if check['id']=='source_claims':check.update(status='fail' if claim_guard['status']=='fail' else 'pending',evidence_ids=[claim_evidence],note='Numeric/price registry boundary checked; semantic source truth remains pending')
        report['issues']=[]
        # Existing defects are never auto-resolved; regenerate their current proof.
        for issue in issues:
            issue=dict(issue,recheck=None);self._crop_issue(out,media,plan,report,manifest,issue);report['issues'].append(issue)
        self._assert_bound(payload,media)
        self._persist(ident,payload,plan,report,manifest)

    def _write_review_transaction(self,ident,payload,defect):
        # Caller owns BEGIN/COMMIT. A defect never commits ahead of its report.
        if defect is not None:
            self.db.execute('INSERT OR REPLACE INTO defects VALUES(?,?,?)',(ident,defect['id'],canonical(defect)))
        self.db.execute('UPDATE reviews SET state=?,payload=? WHERE id=?',('ready',canonical(payload),ident))

    def _persist(self,ident,payload,plan,report,manifest,*,defect=None,staged_files=None):
        out=self._directory(ident);media=self._media(payload['media']);self._assert_bound(payload,media)
        result=validate_report(report,expected_plan=plan,current_render_sha256=file_hash(media),artifact_manifest=manifest)
        values={'plan.json':plan,'report.json':report,'artifact-manifest.json':manifest,'result.json':result}
        # Prepare all JSON before touching published bytes or starting a DB write.
        with tempfile.TemporaryDirectory(prefix='.qa-publish-',dir=self.root) as temporary:
            temporary=Path(temporary);publish=dict(staged_files or {});backup=temporary/'backup';backup.mkdir()
            for name,value in values.items():
                stage=temporary/name;write_json(stage,value);publish[name]=stage
            for rel,stage in publish.items():
                if not _path(rel) or not Path(stage).is_file() or Path(stage).is_symlink():raise WorkflowError('Invalid staged QA artifact')
                within(out,rel)
                if rel in manifest and file_hash(stage)!=manifest[rel]['sha256']:raise WorkflowError('Staged QA evidence changed before publication')
            updated=json.loads(canonical(payload))
            updated['review_artifact_hashes']={name:file_hash(publish[name]) for name in values}
            moved=[];created_dirs=[]
            with self.lock:
                self.db.execute('BEGIN IMMEDIATE')
                try:
                    for index,(rel,stage) in enumerate(publish.items()):
                        target=within(out,rel)
                        absent=[];parent=target.parent
                        while parent!=out and not parent.exists():absent.append(parent);parent=parent.parent
                        for directory in reversed(absent):directory.mkdir();created_dirs.append(directory)
                        old=backup/str(index) if target.exists() else None
                        if target.is_symlink() or target.exists() and not target.is_file():raise WorkflowError('QA artifact target is not a regular file')
                        if old is not None:os.replace(target,old)
                        moved.append((target,old))
                        os.replace(stage,target)
                    self._assert_bound(updated,media)
                    self._write_review_transaction(ident,updated,defect)
                    self.db.commit()
                except BaseException:
                    self.db.rollback()
                    for target,old in reversed(moved):
                        if target.exists():target.unlink()
                        if old is not None:os.replace(old,target)
                    for directory in reversed(created_dirs):
                        if directory.exists():directory.rmdir()
                    raise
            payload.clear();payload.update(updated)

    def _loaded(self,ident):
        state,payload=self._row(ident)
        if state!='ready':raise WorkflowError('QA artifacts are not ready')
        media=self._media(payload['media'])
        if file_hash(media)!=payload['render_sha256']:
            self._save(ident,'invalidated',payload);raise WorkflowError('Final MP4 changed; old review approval invalid. Create a new hash-bound review.')
        self._assert_bound(payload,media)
        out=self._directory(ident)
        pins=payload.get('review_artifact_hashes',{})
        if set(pins)!={'plan.json','report.json','artifact-manifest.json','result.json'} or any(not (out/n).is_file() or (out/n).is_symlink() or file_hash(out/n)!=sha for n,sha in pins.items()):raise WorkflowError('QA report/manifest changed outside review service')
        return payload,media,out,*[json.loads((out/n).read_text()) for n in ['plan.json','report.json','artifact-manifest.json']]

    def status(self,ident):
        with self.lock:
            state,payload=self._row(ident)
            if state!='ready':return {'review_id':ident,'state':state,'status':'fail' if state in {'failed','invalidated'} else 'incomplete','render_sha256':payload['render_sha256']}
            try:payload,media,out,plan,report,manifest=self._loaded(ident)
            except WorkflowError:return {'review_id':ident,'state':'invalidated','status':'fail','render_sha256':payload['render_sha256'],'reason':'Final render/assets changed or input unavailable; prior approval invalid'}
            # A stored manifest is never accepted as current byte verification.
            current={}
            for rel,meta in manifest.items():
                path=within(out,rel)
                if path.is_file() and not path.is_symlink():current[rel]=dict(meta,sha256=file_hash(path))
            result=validate_report(report,expected_plan=plan,current_render_sha256=payload['render_sha256'],artifact_manifest=current)
            return {'review_id':ident,'state':state,**result,'coverage':{'planned':len(plan['samples']),'captured':len(report['coverage']['samples']),'pages':len(report['coverage']['board_pages'])},'issues':report['issues'],'files':self.files(ident)}

    def files(self,ident):
        state,_=self._row(ident)
        if state!='ready':return []
        _,_,out,_,_,manifest=self._loaded(ident)
        return [{'path':rel,'sha256':meta['sha256']} for rel,meta in sorted(manifest.items())]+[{'path':n,'sha256':file_hash(out/n)} for n in ['plan.json','report.json','artifact-manifest.json','result.json']]

    def file(self,ident,relative):
        if not _path(relative):raise WorkflowError('QA download requires a safe registered evidence path')
        self._loaded(ident);files={r['path']:r['sha256'] for r in self.files(ident)}
        if relative not in files:raise WorkflowError('QA file is not registered')
        path=within(self._directory(ident),relative)
        if path.is_symlink() or not path.is_file() or file_hash(path)!=files[relative]:raise WorkflowError('QA evidence changed; download refused')
        return path

    def _crop_issue(self,out,media,plan,report,manifest,issue):
        frame=issue['frame'];frame_id=f'issue-frame-{issue["id"]}';crop_id=f'crop-{issue["id"]}'
        source=self._capture(media,out,frame,plan['fps'],'frames/'+frame_id+'.png')
        b=issue.pop('_bounds',None) or {'x':0,'y':0,'width':plan['viewport']['width'],'height':plan['viewport']['height']}
        target=out/'crops'/f'{crop_id}.png';target.parent.mkdir(exist_ok=True)
        self._run(['ffmpeg','-nostdin','-v','error','-y','-i',str(source),'-vf',f'crop={b["width"]}:{b["height"]}:{b["x"]}:{b["y"]}',
            '-frames:v','1','-c:v','png','-threads','1','-update','1',str(target)])
        for ident,kind,path,bounds,parent in [(frame_id,'frame',source,None,None),(crop_id,'crop',target,b,frame_id)]:
            meta=self._image_meta(path);rel=path.relative_to(out).as_posix();manifest[rel]=meta
            report['evidence']=[e for e in report['evidence'] if e['id']!=ident]
            report['evidence'].append({'id':ident,'kind':kind,'path':rel,'sha256':meta['sha256'],'pixel_sha256':meta['pixel_sha256'],
                'render_sha256':plan['render_sha256'],'frame':frame,'bounds':bounds,'parent_id':parent})
        issue['crop_evidence_id']=crop_id

    def record_issue(self,ident,value):
        with self._operation_lock(ident) as acquired:
            if not acquired:raise WorkflowError('A QA operation is already running; retry after it completes')
            return self._record_issue(ident,value)

    def _record_issue(self,ident,value):
        with self.lock:
            payload,media,out,plan,report,manifest=self._loaded(ident)
            fields={'frame','scene_id','severity','description','local_fix','affected_scene_ids','affected_check_ids','bounds'}
            if not isinstance(value,dict) or set(value)!=fields:raise WorkflowError('Issue needs exact local QA fields')
            try:raw=canonical(value)
            except (TypeError,ValueError,RecursionError):raise WorkflowError('Issue must be bounded JSON') from None
            if len(raw)>10000 or scan_bytes(raw.encode()):raise WorkflowError('Issue oversized or possible secret')
            ranges={s['id']:s for s in plan['scene_ranges']};scene=ranges.get(value['scene_id'])
            if type(value['frame']) is not int or not scene or not scene['start_frame']<=value['frame']<scene['end_frame_exclusive']:raise WorkflowError('Issue frame must lie in the selected scene')
            if value['severity'] not in {'critical','major','minor','info'} or not isinstance(value['description'],str) or not value['description'].strip() or not isinstance(value['local_fix'],str):raise WorkflowError('Invalid issue severity or text')
            scenes=value['affected_scene_ids'];checks=value['affected_check_ids']
            if not isinstance(scenes,list) or not 1<=len(scenes)<=12 or not all(isinstance(s,str) for s in scenes) or len(set(scenes))!=len(scenes) or value['scene_id'] not in scenes or set(scenes)-set(ranges):raise WorkflowError('Invalid affected scene IDs')
            if not isinstance(checks,list) or not 1<=len(checks)<=20 or not all(isinstance(s,str) for s in checks) or len(set(checks))!=len(checks) or set(checks)-set(REQUIRED_CHECKS):raise WorkflowError('Invalid affected QA checks')
            b=value['bounds'];v=plan['viewport']
            if not isinstance(b,dict) or set(b)!={'x','y','width','height'} or any(type(n) is not int or n<0 for n in b.values()) or b['width']<1 or b['height']<1 or b['x']+b['width']>v['width'] or b['y']+b['height']>v['height']:raise WorkflowError('Issue proof crop lies outside final frame')
            issue={k:value[k] for k in fields-{'bounds'}};issue.update(id='issue-'+digest(value)[:12],status='open',crop_evidence_id='',recheck=None,_bounds=dict(b))
            stored=json.loads(canonical(issue));candidate={k:v for k,v in issue.items() if k!='_bounds'};candidate['crop_evidence_id']='crop-'+issue['id']
            report['issues']=[i for i in report['issues'] if i['id']!=issue['id']]+[candidate]
            # Run the complete schema first: malformed fields cannot even start
            # a crop or poison defects. Missing new crop evidence is expected here.
            validate_report(report,expected_plan=plan,current_render_sha256=file_hash(media),artifact_manifest=manifest)
            with tempfile.TemporaryDirectory(prefix='.qa-issue-',dir=self.root) as temporary:
                temporary=Path(temporary);self._crop_issue(temporary,media,plan,report,manifest,issue)
                report['issues']=[i for i in report['issues'] if i['id']!=issue['id']]+[issue]
                staged={p.relative_to(temporary).as_posix():p for p in temporary.rglob('*') if p.is_file()}
                self._persist(ident,payload,plan,report,manifest,defect=stored,staged_files=staged)
            return self.status(ident)

    def resolve_issue(self,ident,issue_id,local_fix):
        with self._operation_lock(ident) as acquired:
            if not acquired:raise WorkflowError('A QA operation is already running; retry after it completes')
            return self._resolve_issue(ident,issue_id,local_fix)

    def _resolve_issue(self,ident,issue_id,local_fix):
        with self.lock:
            payload,_,_,plan,report,manifest=self._loaded(ident)
            if not _id(issue_id) or not isinstance(local_fix,str) or not 1<=len(local_fix.strip())<=2000 or scan_bytes(local_fix.encode()):raise WorkflowError('A bounded local fix note is required')
            row=self.db.execute('SELECT payload FROM defects WHERE review_id=? AND id=?',(ident,issue_id)).fetchone()
            if not row:raise WorkflowError('Unknown QA defect')
            stored=json.loads(row[0]);stored.update(status='fixed',local_fix=local_fix,recheck=None)
            for issue in report['issues']:
                if issue['id']==issue_id:issue.update(status='fixed',local_fix=local_fix,recheck=None)
            self._persist(ident,payload,plan,report,manifest,defect=stored);return self.status(ident)

    def recheck(self,ident):
        return self._capture_attempt(ident,force=True)
