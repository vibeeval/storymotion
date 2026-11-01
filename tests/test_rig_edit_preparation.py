"""Real local queue/HTTP source preparation; synthetic silence, no media calls."""
import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from audio_fixture import imported, no_media, source_job
from test_catalog_integration import MemoryConnection, authenticated_handler
import test_rig_revision as rig_fixture
from storymotion.dashboard import Dashboard
from storymotion.engine import Engine
from storymotion.security import WorkflowError, digest, file_hash, write_json
from storymotion.worker import LocalWorker


class RigEditPreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='rig-edit-prepare-')
        self.addCleanup(self.temp.cleanup)
        self.d=Dashboard(Path(self.temp.name).resolve()/'work')
        self.addCleanup(self.close)
        media=no_media();media.__enter__();self.addCleanup(media.__exit__,None,None,None)
        processes=patch('subprocess.Popen',side_effect=AssertionError('No native/provider subprocess allowed'))
        processes.start();self.addCleanup(processes.stop)

    def close(self):
        self.d.clear_keys();self.d.eleven.broker.clear();self.d.llm.close()
        self.d.renders.close();self.d.reviews.close();self.d.close_local_log()

    def http(self,path,body=None,origin='http://127.0.0.1:43333',auth=True):
        server=SimpleNamespace(server_address=('127.0.0.1',43333),dashboard=self.d)
        raw=json.dumps(body).encode() if body is not None else b''
        request=('POST' if body is not None else 'GET')+' '+path+' HTTP/1.0\r\nHost: 127.0.0.1:43333\r\nOrigin: '+origin+'\r\nX-Storymotion-Local: 1\r\nContent-Type: application/json\r\nContent-Length: '+str(len(raw))+'\r\n\r\n'
        connection=MemoryConnection(request.encode()+raw)
        if auth:authenticated_handler(connection,('127.0.0.1',1),server)
        else:
            from storymotion.dashboard import Handler
            Handler(connection,('127.0.0.1',1),server)
        head,data=bytes(connection.output).split(b'\r\n\r\n',1)
        return int(head.split()[1]),data

    def source(self,prepare_ancestors=False):
        root=source_job(self.d,'neutral')
        if prepare_ancestors:self.assertEqual(self.d.prepare(root)['status'],'prepared')
        audio=imported(self.d,root)['child_job']
        if prepare_ancestors:self.assertEqual(self.d.prepare(audio)['status'],'prepared')
        body=rig_fixture.RigRevisionTests.body(SimpleNamespace(d=self.d),audio)
        rig=self.d.rigs.create(audio,body)['child_job']
        if prepare_ancestors:self.assertEqual(self.d.prepare(rig)['status'],'prepared')
        return root,audio,rig,body

    def edit(self,parent,prop='heading'):
        plan=self.d.renders.edit_plan(parent,'hyperframes')['edit_plan'];scene=plan['scenes'][0]
        value='Aynı nesnenin yeni sahne başlığı.' if prop=='heading' else ('push-in' if scene['camera']=='locked' else 'locked')
        body={'engine':'hyperframes','expected_plan_sha256':plan['plan_sha256'],'scene_id':scene['id'],'property':prop,'value':value}
        return self.d.edits.create(parent,body)['child_job']

    def assert_prepared(self,child,rig):
        row=self.d.job(child);video=self.d.audio.guard(child)
        self.assertEqual(row['status'],'prepared');self.assertIsNone(row['error'])
        self.assertEqual(row['payload']['rig_revision'],self.d.job(rig)['payload']['rig_revision'])
        self.assertNotIn('rig-binding.json',row['manifest'])
        self.assertFalse((self.d.output(child)/'rig-binding.json').exists())
        for relative,expected in row['manifest'].items():self.assertEqual(file_hash(self.d.output(child)/relative),expected)
        for relative,value in [('rig.json',video['rig']),('revision.json',row['payload']['edit_revision']),('audio-timing.json',video['audio_timing'])]:
            self.assertIn(relative,row['manifest'])
            self.assertEqual(json.loads((self.d.output(child)/relative).read_text()),value)
            # Internal proof documents remain outside the existing download list.
            self.assertEqual(self.http('/files/'+child+'/'+relative)[0],400)
        code,raw=self.http('/files/'+child+'/caption.txt');self.assertEqual(code,200,raw)
        self.assertEqual(raw,(self.d.output(child)/'caption.txt').read_bytes())
        self.assertEqual(self.http('/files/'+child+'/rig-binding.json')[0],400)
        self.assertEqual(self.d.reviews.state(child,'hyperframes')['status'],'not_started')
        self.assertIsNone(self.d.renders.row(child,'hyperframes'))
        return video

    def test_actual_http_heading_then_camera_chain_and_both_engine_source_prepares(self):
        _,_,rig,_=self.source();origin=self.d.rigs.guard(rig)
        self.assertEqual(self.d.prepare(rig)['status'],'prepared')
        self.assertIn('rig-binding.json',self.d.job(rig)['manifest'])
        parent=rig
        for prop in ('heading','camera'):
            child=self.edit(parent,prop);before=self.d.job(child)
            path='/api/jobs/'+child+'/prepare'
            self.assertEqual(self.http(path,{},auth=False)[0],401)
            self.assertEqual(self.http(path,{},origin='https://attacker.test')[0],403)
            self.assertEqual(self.d.job(child),before)
            code,raw=self.http(path,{});self.assertEqual(code,200,raw)
            video=self.assert_prepared(child,rig)
            self.assertEqual(video['audio'],origin['audio']);self.assertEqual(video['cues'],origin['cues'])
            self.assertEqual(video['rig']['mouthCues'],origin['rig']['mouthCues'])
            self.assertEqual(video['rig']['source_timing_sha256'],digest(video['audio_timing']))
            snapshot=copy.deepcopy(self.d.job(child))
            code,raw=self.http(path,{});self.assertEqual(code,200,raw);self.assertEqual(self.d.job(child),snapshot)
            parent=child
        # These are source preparations only, not native or perceptual acceptance.
        for engine in ('hyperframes','remotion'):
            path=self.d.output(child)/('unit-'+engine+'.json');write_json(path,video)
            with Engine(self.d.workspace/('unit-engine-'+engine)) as runtime:
                ident=runtime.create(path,render_engine=engine)['job'];runtime.run(ident,'prepare')
                out=runtime.directory(ident)
                self.assertEqual(json.loads((out/'rig.json').read_text()),video['rig'])
                self.assertEqual(json.loads((out/'revision.json').read_text()),video['revision_context'])
                self.assertEqual(file_hash(out/'assets/narration.wav'),origin['audio']['sha256'])
                self.assertEqual(runtime.store.stage(ident,'render')['status'],'pending')

    def test_real_worker_claims_camera_child_and_retry_does_not_duplicate(self):
        _,_,rig,_=self.source(prepare_ancestors=True);child=self.edit(rig,'camera')
        result=LocalWorker(self.d).run_once()
        self.assertEqual(result['status'],'prepared',result);self.assertEqual(result['job'],child)
        self.assertEqual(result['provider_calls'],0);self.assertEqual(self.d.job(child)['attempts'],1)
        self.assert_prepared(child,rig)
        self.assertEqual(LocalWorker(self.d).run_once()['status'],'idle')
        before=copy.deepcopy(self.d.job(child));self.assertEqual(self.http('/api/jobs/'+child+'/prepare',{})[0],200)
        self.assertEqual(self.d.job(child),before)

    def test_missing_or_changed_ancestor_proof_and_child_proof_still_fail_before_reuse(self):
        _,_,rig,body=self.source();child=self.edit(rig)
        self.assertEqual(self.d.prepare(child)['status'],'prepared')
        for target in (self.d.output(rig)/'rig-binding.json',self.d.output(child)/'revision.json',self.d.output(child)/'rig.json'):
            raw=target.read_bytes();before=copy.deepcopy(self.d.job(child));target.write_bytes(b'{}')
            code,response=self.http('/api/jobs/'+child+'/prepare',{});self.assertEqual(code,400,response)
            self.assertEqual(self.http('/files/'+child+'/caption.txt')[0],400)
            self.assertEqual(self.d.job(child),before)
            target.write_bytes(raw);self.d.audio.guard(child)
        binding=self.d.output(rig)/'rig-binding.json';raw=binding.read_bytes();binding.unlink()
        self.assertEqual(self.http('/api/jobs/'+child+'/prepare',{})[0],400)
        write_json(binding,json.loads(raw));self.d.audio.guard(child)
        changed=copy.deepcopy(body);changed['spec']['mouthCues'][0]['value']='X'
        self.d.rigs.create(self.d.job(rig)['payload']['rig_revision']['parent_job'],changed)
        with self.assertRaises(WorkflowError):self.d.audio.guard(child)
        self.assertEqual(self.http('/api/jobs/'+child+'/prepare',{})[0],400)
        self.assertEqual(self.http('/files/'+child+'/caption.txt')[0],400)
