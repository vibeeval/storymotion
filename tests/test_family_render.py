"""Real protected preparation/HTTP/SQLite; deterministic synthetic workers only."""
import copy
import contextlib
import hashlib
import json
import os
import threading
import unittest
from unittest.mock import patch

from storymotion import family_render as render
from storymotion.local_state import private_directory, write_private
from storymotion.security import WorkflowError, canonical
import test_family_history_http as history_fixture
import test_template_credential_intake as credentials


class FamilyRenderTests(unittest.TestCase):
    def setUp(self):
        self.f=history_fixture.FamilyHistoryHttpTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.d=self.f.d;self.s=self.d.family_renders;self.addCleanup(self.s.close)
        self.data,self.prepared=self.f.prepare();self.job=self.prepared['job']
        for target in ('storymotion.family_render.require_engine','storymotion.family_render.Engine','storymotion.family_render.probe'):
            mock=patch(target,side_effect=AssertionError('Real native boundary forbidden')) if not target.endswith('require_engine') else patch(target,return_value=None)
            mock.start();self.addCleanup(mock.stop)
        worker=patch.object(self.s,'execute',side_effect=self.fake);self.execute=worker.start();self.addCleanup(worker.stop)
        # Join owned workers before undoing native-boundary mocks, even on failure.
        self.addCleanup(self.s.close)

    def fake(self,attempt,snapshot,cancel):
        directory=self.d.workspace/'family-executions'/attempt
        output=directory/'work'/self.job;private_directory(output)
        manifest={}
        for name in render.MEDIA:
            raw=('TEST_ONLY_SYNTHETIC_NOT_MP4_'+name).encode();write_private(output/name,raw);manifest[name]=hashlib.sha256(raw).hexdigest()
        write_private(directory/'completion.json',canonical({'attempt':attempt,'preparation':snapshot['proof'],'attempt_binding':snapshot['attempt_binding'],'files':manifest,'output_profile':render.PROFILE}))
        return manifest

    def state(self,attempt=None):
        return self.s.state('neutral',self.job,attempt)

    def payload(self,action='start',previous=None):
        state=self.state();value={k:state[k] for k in ('engine','preparation_revision','execution_binding')}
        value.update(request_key=os.urandom(16).hex(),expected_generation=0 if action=='start' else previous['generation'],ack_local_render=True)
        if action=='retry':value['previous_attempt']=previous['attempt']
        return value

    def start(self,data=None,action='start'):
        return self.s.action('neutral',self.job,action,data or self.payload())

    def settle(self,attempt):
        with self.s.lock:owned=self.s.active.get(attempt)
        if owned:owned[1].join(5);self.assertFalse(owned[1].is_alive())
        return self.state(attempt)

    def hold(self):
        entered=threading.Event();release=threading.Event()
        def worker(*args):
            entered.set()
            if not release.wait(5):raise AssertionError('Test worker barrier expired')
            return self.fake(*args)
        self.execute.side_effect=worker;self.addCleanup(release.set)
        return entered,release

    def post(self,action,data,**kw):
        return credentials.TemplateCredentialHttpTests.request(self.f,'/api/family-renders/neutral/'+self.job+'/'+action,data,**kw)

    def test_snapshot_and_state_are_read_only_and_do_not_create_execution_root(self):
        before=self.f.snapshot();snap=self.s.snapshot('neutral',self.job)
        self.assertEqual(snap['proof']['prepare_job'],self.job);self.assertEqual(self.state()['status'],'not_started')
        self.assertEqual(self.f.snapshot(),before);self.assertFalse((self.d.workspace/'family-executions').exists())

    def test_authenticated_routes_and_closing_scope(self):
        path='/api/family-renders/neutral/'+self.job
        self.assertEqual(self.f.get(path,cookie=False)[0],401)
        self.assertEqual(self.f.get(path,headers=('Origin: http://evil.local',))[0],403)
        data=self.payload()
        for kw,status in [({'cookie':False},401),({'origin':'http://evil.local'},403),({'marker':'0'},403)]:self.assertEqual(self.post('start',data,**kw)[0],status)
        self.f.server._closing=True
        self.assertEqual(self.f.get(path)[0],403);self.assertEqual(self.post('start',data)[0],403)
        self.f.server._closing=False

    def test_start_status_download_and_same_request_replay(self):
        data=self.payload();code,row,_=self.post('start',data);self.assertEqual(code,200,row)
        row=self.settle(row['attempt']);self.assertEqual(row['status'],'complete');self.assertEqual(self.execute.call_count,1)
        code,replay,_=self.post('start',data);self.assertEqual(code,200,replay);self.assertEqual(replay['attempt'],row['attempt']);self.assertEqual(self.execute.call_count,1)
        before=self.f.snapshot()
        for item in row['files']:
            code,raw,headers=self.f.get(item['download_url'],headers=('Range: bytes=0-3',))
            self.assertEqual(code,206);self.assertEqual(raw,b'TEST');self.assertIn(b'video/mp4',headers)
        self.assertEqual(self.f.snapshot(),before)
        self.assertFalse(row['publication_ready']);self.assertEqual(row['provider_calls'],0)

    def test_double_click_busy_and_request_key_rebinding_never_duplicate(self):
        entered,release=self.hold();data=self.payload();first=self.start(data);self.assertTrue(entered.wait(3))
        second=self.start(data);self.assertEqual(first['attempt'],second['attempt'])
        with self.assertRaisesRegex(WorkflowError,'WORKER_BUSY'):self.start(self.payload())
        changed=dict(data,expected_generation=1)
        with self.assertRaisesRegex(WorkflowError,'REQUEST_KEY_REBOUND'):self.start(changed)
        self.assertEqual(self.execute.call_count,1);release.set();self.settle(first['attempt'])

    def test_cancel_wins_completion_and_repeat_cancel_is_idempotent(self):
        entered,release=self.hold();row=self.start();self.assertTrue(entered.wait(3))
        cancel={'engine':row['engine'],'attempt':row['attempt'],'generation':row['generation']}
        self.assertEqual(self.s.action('neutral',self.job,'cancel',cancel)['status'],'cancel_requested')
        self.assertEqual(self.s.action('neutral',self.job,'cancel',cancel)['status'],'cancel_requested')
        release.set();done=self.settle(row['attempt']);self.assertEqual(done['status'],'cancelled');self.assertEqual(done['files'],[])
        self.assertEqual(self.s.action('neutral',self.job,'cancel',cancel)['status'],'cancelled')

    def test_complete_wins_late_cancel_and_cannot_retry_complete(self):
        row=self.start();row=self.settle(row['attempt'])
        cancel={'engine':row['engine'],'attempt':row['attempt'],'generation':row['generation']}
        self.assertEqual(self.s.action('neutral',self.job,'cancel',cancel)['status'],'complete')
        with self.assertRaisesRegex(WorkflowError,'NOT_RETRYABLE'):self.start(self.payload('retry',row),'retry')

    def test_retry_is_new_generation_fresh_directory_and_stale_cancel_cannot_touch_it(self):
        self.execute.side_effect=WorkflowError('TEST_ONLY_FAILURE');first=self.start();first=self.settle(first['attempt'])
        self.assertEqual(first['status'],'failed');old=self.s.directory(first['attempt'])/'input.json';before=old.read_bytes(),old.stat().st_mtime_ns
        entered,release=self.hold();data=self.payload('retry',first);new=self.start(data,'retry');self.assertTrue(entered.wait(3))
        self.assertEqual(new['generation'],2);self.assertNotEqual(new['attempt'],first['attempt'])
        with self.assertRaisesRegex(WorkflowError,'STALE_ATTEMPT'):
            self.s.action('neutral',self.job,'cancel',{'engine':first['engine'],'attempt':first['attempt'],'generation':first['generation']})
        self.assertFalse(self.s.active[new['attempt']][0].is_set());self.assertEqual(self.start(data,'retry')['attempt'],new['attempt'])
        self.assertEqual((old.read_bytes(),old.stat().st_mtime_ns),before)
        release.set();self.settle(new['attempt'])
        with self.assertRaisesRegex(WorkflowError,'STALE_ATTEMPT'):self.start(self.payload('retry',first),'retry')

    def test_restart_is_unconfirmed_no_worker_or_read_mutation_then_explicit_fresh_retry(self):
        self.execute.side_effect=WorkflowError('TEST_ONLY_FAILURE');row=self.start();row=self.settle(row['attempt'])
        with self.d.connection() as db:db.execute("UPDATE family_render_attempts SET status='running',error=NULL WHERE id=?",(row['attempt'],))
        old=self.s;new=render.FamilyRender(self.d);self.d.family_renders=new;self.s=new;self.addCleanup(new.close)
        with patch.object(new,'execute',side_effect=self.fake) as execute:
            before=self.f.snapshot();state=self.state();self.assertEqual(state['status'],'interrupted_unconfirmed');self.assertEqual(execute.call_count,0);self.assertEqual(self.f.snapshot(),before)
            result=self.start(self.payload('retry',state),'retry');self.settle(result['attempt']);self.assertEqual(execute.call_count,1)
            self.assertFalse(old.finish('neutral',self.job,row['attempt'],row['generation'],'complete',manifest={}))

    def test_runtime_block_is_not_a_render_and_never_creates_attempt_files(self):
        with patch.object(render,'require_engine',side_effect=WorkflowError('TEST_ONLY_MISSING_RUNTIME')):
            row=self.start();row=self.settle(row['attempt'])
        self.assertEqual(row['status'],'blocked_runtime');self.assertFalse(row['actual_render']);self.assertEqual(self.execute.call_count,0)
        self.assertFalse((self.d.workspace/'family-executions').exists())

    def test_cross_account_engine_namespace_and_closed_fields_reject_without_writes(self):
        data=self.payload();before=self.f.snapshot()
        for value in [dict(data,engine='remotion'),dict(data,engine='all'),dict(data,ack_local_render=1),dict(data,expected_generation=True),dict(data,command='node'),dict(data,preparation_revision='0'*64),dict(data,execution_binding='0'*64)]:
            with self.assertRaises(WorkflowError):self.start(value)
        with self.assertRaises(WorkflowError):self.s.action('second',self.job,'start',data)
        with self.assertRaises(WorkflowError):self.s.state('neutral','../jobs.sqlite3')
        self.assertEqual(self.f.snapshot(),before);self.assertEqual(self.execute.call_count,0)

    def test_current_source_and_planning_rechecked_before_dispatch(self):
        data=self.payload();self.d.runtime_execution='TEST_ONLY_CHANGED'
        before=self.f.snapshot()
        with self.assertRaises(WorkflowError):self.start(data)
        self.assertEqual(self.f.snapshot(),before)

    def test_missing_protected_intake_and_tampered_prepare_never_dispatch(self):
        data=self.payload();receipts=list((self.d.workspace/'family-receipts').rglob('*.json'));self.assertTrue(receipts)
        receipts[0].unlink();before=self.f.snapshot()
        with self.assertRaises(WorkflowError):self.start(data)
        self.assertEqual(self.f.snapshot(),before);self.assertEqual(self.execute.call_count,0)

    def test_current_broker_secrets_cannot_be_used_as_render_request_data(self):
        data=self.payload();self.d.llm.broker.put('openai','test','test',credentials.LLM_OPAQUE,synthetic=True)
        for value in (credentials.LLM_OPAQUE,credentials.patterned()):
            before=self.f.snapshot();code,result,raw=self.post('start',dict(data,secret_note=value))
            self.assertEqual(code,400);self.f.assert_no_secret(raw);self.assertEqual(self.f.snapshot(),before)

    def test_shared_slot_blocks_normal_and_family_and_wrong_release_cannot_steal(self):
        entered,release=self.hold();row=self.start();self.assertTrue(entered.wait(3))
        self.assertEqual(self.d.renders.start('a'*24,'hyperframes')['status'],'local_render_already_running')
        token=self.d.render_slot.current;self.d.render_slot.release('0'*32);self.assertEqual(self.d.render_slot.current,token)
        release.set();self.settle(row['attempt']);self.assertIsNone(self.d.render_slot.current)
        held=self.d.render_slot.claim(('normal','test','hyperframes'))
        try:
            with self.assertRaisesRegex(WorkflowError,'WORKER_BUSY'):self.start(self.payload('retry',dict(row,status='failed')),'retry')
        finally:self.d.render_slot.release(held)

    def test_normal_failure_releases_shared_slot(self):
        with patch.object(self.d.renders,'_start_locked',side_effect=WorkflowError('TEST_ONLY_NORMAL_FAILURE')):
            with self.assertRaises(WorkflowError):self.d.renders.start('a'*24,'hyperframes')
        self.assertIsNone(self.d.render_slot.current)

    def test_output_input_and_completion_tamper_revokes_download_and_state_is_read_only(self):
        row=self.start();row=self.settle(row['attempt']);url=row['files'][0]['download_url']
        path=self.s.directory(row['attempt'])/'work'/self.job/render.MEDIA[0];path.write_bytes(b'TEST_ONLY_CHANGED')
        before=self.f.snapshot();state=self.state();self.assertEqual(state['status'],'invalidated');self.assertEqual(state['files'],[])
        self.assertEqual(self.f.get(url)[0],400);self.assertEqual(self.f.snapshot(),before)

    def test_output_symlink_is_rejected_without_following(self):
        row=self.start();row=self.settle(row['attempt']);url=row['files'][0]['download_url']
        path=self.s.directory(row['attempt'])/'work'/self.job/render.MEDIA[0];outside=self.d.workspace/'TEST_ONLY_OUTSIDE';write_private(outside,b'KEEP')
        path.unlink();path.symlink_to(outside);self.assertEqual(self.f.get(url)[0],400);self.assertEqual(outside.read_bytes(),b'KEEP')

    def test_thread_start_failure_does_not_leak_slot_and_requires_explicit_retry(self):
        data=self.payload()
        with patch.object(threading.Thread,'start',side_effect=RuntimeError('TEST_ONLY_THREAD_FAILURE')):
            with self.assertRaises(RuntimeError):self.start(data)
        self.assertIsNone(self.d.render_slot.current);self.assertFalse(self.s.active)
        row=self.state();self.assertEqual(row['status'],'failed_before_start')
        self.assertEqual(self.start(data)['attempt'],row['attempt'])

    def test_close_requests_owned_cancel_and_rejects_new_starts(self):
        entered,release=self.hold();row=self.start();self.assertTrue(entered.wait(3));release.set();self.s.close()
        self.assertFalse(self.s.active)
        with self.assertRaisesRegex(WorkflowError,'CLOSING'):self.start(self.payload())

    def queued(self):
        entered=threading.Event();release=threading.Event();self.addCleanup(release.set)
        def runtime(engine):
            entered.set()
            if not release.wait(5):raise AssertionError('Test runtime barrier expired')
        scope=patch.object(render,'require_engine',side_effect=runtime);scope.start();self.addCleanup(scope.stop)
        row=self.start();self.assertTrue(entered.wait(3));return row,release

    def test_cancel_before_dispatch_never_creates_files_and_retry_waits_for_exit(self):
        row,release=self.queued()
        cancel={'engine':row['engine'],'attempt':row['attempt'],'generation':row['generation']}
        self.assertEqual(self.s.action('neutral',self.job,'cancel',cancel)['status'],'cancel_requested')
        with self.assertRaisesRegex(WorkflowError,'WORKER_BUSY'):self.start(self.payload('retry',row),'retry')
        release.set();self.assertEqual(self.settle(row['attempt'])['status'],'cancelled')
        self.assertEqual(self.execute.call_count,0);self.assertFalse((self.d.workspace/'family-executions').exists())

    def test_saved_sources_changed_while_queued_fail_before_attempt_files(self):
        row,release=self.queued()
        sources=copy.deepcopy(history_fixture.SOURCE);next(iter(sources.values()))['title']='TEST_ONLY_CHANGED_SOURCE'
        self.d.llm.contexts.save('sources','neutral',sources,self.f.source_revision,True)
        release.set();self.assertEqual(self.settle(row['attempt'])['status'],'failed')
        self.assertEqual(self.execute.call_count,0);self.assertFalse((self.d.workspace/'family-executions').exists())

    def test_planning_changed_while_queued_fail_before_attempt_files(self):
        state=self.d.taxonomy.state('neutral');topic=state['topics'][0]
        selected=self.d.taxonomy.action('select',{'account':'neutral','niche':topic['niche'],'topic':topic['id'],'expected_revision':state['revision']})
        data=copy.deepcopy(self.data);data['planning']={'revision':selected['revision'],**selected['selection']}
        code,prepared,_=self.f.post('/api/template-families/prepare',data);self.assertEqual(code,200,prepared);self.job=prepared['job']
        row,release=self.queued()
        self.d.taxonomy.action('select',{'account':'neutral','niche':None,'topic':None,'expected_revision':selected['revision']})
        release.set();self.assertEqual(self.settle(row['attempt'])['status'],'failed')
        self.assertEqual(self.execute.call_count,0);self.assertFalse((self.d.workspace/'family-executions').exists())

    def test_invalidated_outputs_allow_only_explicit_new_attempt(self):
        row=self.settle(self.start()['attempt']);directory=self.s.directory(row['attempt'])
        old=directory/'input.json';before=old.read_bytes(),old.stat().st_mtime_ns
        (directory/'completion.json').write_text('{}')
        self.assertEqual(self.state()['status'],'invalidated')
        with self.assertRaisesRegex(WorkflowError,'EXPLICIT_RETRY_REQUIRED'):self.start()
        new=self.start(self.payload('retry',row),'retry');new=self.settle(new['attempt'])
        self.assertEqual((new['status'],new['generation']),('complete',2));self.assertNotEqual(new['attempt'],row['attempt'])
        self.assertEqual((old.read_bytes(),old.stat().st_mtime_ns),before)

    def test_attempt_binding_tamper_blocks_retry_and_download_without_new_worker(self):
        row=self.settle(self.start()['attempt']);url=row['files'][0]['download_url'];data=self.payload('retry',row)
        with self.d.connection() as db:db.execute("UPDATE family_render_attempts SET binding='{}' WHERE id=?",(row['attempt'],))
        before=self.f.snapshot()
        with self.assertRaisesRegex(WorkflowError,'BINDING_CHANGED'):self.start(data,'retry')
        self.assertEqual(self.f.get(url)[0],400);self.assertEqual(self.execute.call_count,1);self.assertEqual(self.f.snapshot(),before)

    def test_input_and_completion_hash_tamper_are_detected_by_read_only_gets(self):
        row=self.settle(self.start()['attempt']);directory=self.s.directory(row['attempt']);url=row['files'][0]['download_url']
        for name,raw in [('input.json',b'{}'),('completion.json',b'{}')]:
            path=directory/name;original=path.read_bytes();path.write_bytes(raw);before=self.f.snapshot()
            self.assertEqual(self.state()['status'],'invalidated');self.assertEqual(self.f.get(url)[0],400)
            self.assertEqual(self.f.snapshot(),before);path.write_bytes(original)
        self.assertEqual(self.state()['status'],'complete')

    def test_attempt_root_link_is_rejected_without_touching_target(self):
        row,release=self.queued();outside=self.d.workspace/'TEST_ONLY_UNRELATED';private_directory(outside)
        parent=self.d.workspace/'family-executions';private_directory(parent);(parent/row['attempt']).symlink_to(outside,target_is_directory=True)
        release.set();self.assertEqual(self.settle(row['attempt'])['status'],'failed')
        self.assertEqual(list(outside.iterdir()),[]);self.assertEqual(self.execute.call_count,0)

    def test_download_auth_origin_host_tokens_account_and_attempt_are_bound(self):
        row=self.settle(self.start()['attempt']);url=row['files'][0]['download_url']
        self.assertEqual(self.f.get(url,cookie=False)[0],401)
        for headers in [('Origin: http://evil.local',),('Host: evil.local',),('Origin: http://127.0.0.1:43333','Origin: http://127.0.0.1:43333')]:
            self.assertEqual(self.f.get(url,headers=headers)[0],403)
        for changed in [url.replace('/neutral/','/second/'),url.replace(row['attempt'],'0'*32),url.rsplit('/',1)[0]+'/'+('0'*64),url.replace('/family-render-files/','/family-render-files/../')]:
            self.assertIn(self.f.get(changed)[0],(400,403,404))

    def test_remotion_remains_explicitly_bound_without_engine_fallback(self):
        _,prepared=self.f.prepare(engine='remotion');self.job=prepared['job']
        data=self.payload();self.assertEqual(data['engine'],'remotion')
        with self.assertRaisesRegex(WorkflowError,'ENGINE_BINDING_CHANGED'):self.start(dict(data,engine='hyperframes'))
        row=self.settle(self.start(data)['attempt']);self.assertEqual(row['engine'],'remotion')

    def test_store_with_wal_header_is_rejected_without_sqlite_side_effects(self):
        path=self.d.workspace/'jobs.sqlite3';raw=path.read_bytes();changed=bytearray(raw);changed[18:20]=b'\x02\x02';path.write_bytes(changed)
        before={p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in self.d.workspace.glob('jobs.sqlite3*')}
        try:
            with self.assertRaisesRegex(WorkflowError,'STORE_UNAVAILABLE'):self.state()
            self.assertEqual({p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in self.d.workspace.glob('jobs.sqlite3*')},before)
        finally:path.write_bytes(raw)

    def contract_engine(self,attempt,snapshot,*,receipt_change=None,manifest_change=None,payload_change=None,job_change=None,stage_status='complete'):
        owner=self;calls=[]
        class FakeEngine:
            def __init__(self,work,hf):
                calls.append(('init',work,hf));self.root=work;private_directory(work);self.store=self;self.manifests={}
            def __enter__(self):return self
            def __exit__(self,*exc):calls.append(('close',))
            def create(self,source,render_engine):
                owner.assertEqual(source.read_bytes(),snapshot['raw']);owner.assertEqual(render_engine,snapshot['proof']['engine'])
                calls.append(('create',render_engine));return {'job':job_change or owner.job}
            def directory(self,job):return self.root/job
            def run(self,job,until,cancel_event):
                calls.append(('run',until,cancel_event));output=self.directory(job);private_directory(output)
                raw=b'TEST_ONLY_NOT_VIDEO';sha=hashlib.sha256(raw).hexdigest()
                receipt={'engine':snapshot['proof']['engine'],'execution_fingerprint':snapshot['proof']['execution_fingerprint'],'render_sha256':sha,'paid_provider_calls':0}
                if receipt_change:receipt.update(receipt_change)
                for name in render.MEDIA:write_private(output/name,raw)
                receipt_raw=canonical(receipt).encode();write_private(output/'render-engine.json',receipt_raw)
                self.manifests={'render':{render.MEDIA[0]:sha,'render-engine.json':hashlib.sha256(receipt_raw).hexdigest()},'mobile':{render.MEDIA[1]:sha}}
                if manifest_change:manifest_change(self.manifests,output)
            def lock(self):return contextlib.nullcontext()
            def stage(self,job,stage):return {'status':stage_status,'manifest':canonical(self.manifests[stage])}
            def payload(self,job):return payload_change or snapshot['payload']
        return FakeEngine,calls

    def contract_setup(self):
        self.execute.side_effect=WorkflowError('TEST_ONLY_PREPARE_ATTEMPT_WITHOUT_EXECUTION')
        row=self.settle(self.start()['attempt']);self.assertEqual(row['status'],'failed')
        snapshot=self.s.snapshot('neutral',self.job);snapshot['attempt_binding']=self.s.attempt_binding(self.s.row('neutral',self.job,row['attempt']))
        return row['attempt'],snapshot

    def valid_probe(self,snapshot,path):
        width,height=(1080,1920) if path.name==render.MEDIA[0] else (540,960)
        return {'duration':snapshot['payload']['brief']['duration'],'streams':[{'codec_type':'video','codec_name':'h264','width':width,'height':height,'r_frame_rate':'30/1','sample_aspect_ratio':'1:1'}]}

    def test_production_bridge_uses_only_bound_engine_mobile_target_and_closes(self):
        attempt,snapshot=self.contract_setup();fake,calls=self.contract_engine(attempt,snapshot);cancel=threading.Event()
        with patch.object(render,'Engine',fake),patch.object(render,'probe',side_effect=lambda path:self.valid_probe(snapshot,path)):
            manifest=render.FamilyRender.execute(self.s,attempt,snapshot,cancel)
        self.assertEqual(set(manifest),set(render.MEDIA));self.assertEqual(calls[-1],('close',))
        self.assertEqual(calls[-2],('run','mobile',cancel));self.assertTrue((self.s.directory(attempt)/'completion.json').is_file())

    def test_production_bridge_rejects_wrong_media_shape_codec_rate_sar_duration_or_audio(self):
        attempt,snapshot=self.contract_setup()
        variants=[('width',1),('height',1),('codec_name','vp9'),('r_frame_rate','60/1'),('sample_aspect_ratio','2:1'),('duration',float('nan')),('duration',float('inf')),('duration',0),('audio',True),('video',True)]
        for key,value in variants:
            with self.subTest(key=key,value=value):
                fake,calls=self.contract_engine(attempt,snapshot)
                def invalid_probe(path):
                    report=self.valid_probe(snapshot,path)
                    if key=='duration':report['duration']=value
                    elif key in ('audio','video'):report['streams'].append({'codec_type':key})
                    else:report['streams'][0][key]=value
                    return report
                with patch.object(render,'Engine',fake),patch.object(render,'probe',side_effect=invalid_probe):
                    with self.assertRaisesRegex(WorkflowError,'MEDIA_INVALID'):render.FamilyRender.execute(self.s,attempt,snapshot,threading.Event())
                self.assertEqual(calls[-1],('close',));self.assertFalse((self.s.directory(attempt)/'completion.json').exists())

    def test_production_bridge_rejects_receipt_stage_payload_job_and_hash_mismatch(self):
        attempt,snapshot=self.contract_setup()
        variants=[{'receipt_change':{'engine':'other'}},{'receipt_change':{'execution_fingerprint':'0'*64}},{'receipt_change':{'render_sha256':'0'*64}},{'receipt_change':{'paid_provider_calls':1}},{'receipt_change':{'paid_provider_calls':False}},{'stage_status':'running'},{'payload_change':{'TEST_ONLY_UNBOUND':True}},{'job_change':'0'*24},
                  {'manifest_change':lambda manifests,output:manifests['render'].update({render.MEDIA[0]:'0'*64})},
                  {'manifest_change':lambda manifests,output:manifests['mobile'].update({'TEST_ONLY_EXTRA':'0'*64})}]
        for variant in variants:
            with self.subTest(variant=variant):
                fake,calls=self.contract_engine(attempt,snapshot,**variant)
                with patch.object(render,'Engine',fake),patch.object(render,'probe',side_effect=lambda path:self.valid_probe(snapshot,path)):
                    with self.assertRaises(WorkflowError):render.FamilyRender.execute(self.s,attempt,snapshot,threading.Event())
                self.assertEqual(calls[-1],('close',));self.assertFalse((self.s.directory(attempt)/'completion.json').exists())

    def test_production_bridge_checks_input_before_engine_instantiation(self):
        attempt,snapshot=self.contract_setup();(self.s.directory(attempt)/'input.json').write_text('{}')
        with patch.object(render,'Engine') as engine:
            with self.assertRaisesRegex(WorkflowError,'INPUT_CHANGED'):render.FamilyRender.execute(self.s,attempt,snapshot,threading.Event())
            engine.assert_not_called()

    def test_real_engine_intake_keeps_original_job_payload_in_fresh_attempt_roots(self):
        from storymotion.engine import Engine as PlanningEngine
        for family in ('kinetic-grid','contour-trace'):
            for engine in ('hyperframes','remotion'):
                with self.subTest(family=family,engine=engine):
                    _,prepared=self.f.prepare(family,engine);self.job=prepared['job'];attempt,snapshot=self.contract_setup()
                    fake,calls=self.contract_engine(attempt,snapshot)
                    class PlanOnlyEngine(fake):
                        def __init__(self,work,hf):super().__init__(work,hf);self.planner=PlanningEngine(work,hf)
                        def create(self,source,render_engine):return self.planner.create(source,render_engine=render_engine)
                        def payload(self,job):return self.planner.payload(job)
                        def __exit__(self,*exc):self.planner.close();super().__exit__(*exc)
                    with patch.object(render,'Engine',PlanOnlyEngine),patch.object(render,'probe',side_effect=lambda path:self.valid_probe(snapshot,path)):
                        self.assertEqual(set(render.FamilyRender.execute(self.s,attempt,snapshot,threading.Event())),set(render.MEDIA))
                    directory=self.s.directory(attempt)
                    for path,mode in [(directory,0o700),(directory/'work',0o700),(directory/'input.json',0o600),(directory/'completion.json',0o600)]:
                        self.assertEqual(path.stat().st_mode&0o777,mode)

    def test_snapshot_refuses_tampered_original_source_and_prepared_artifact_before_queue(self):
        data=self.payload();snapshot=self.s.snapshot('neutral',self.job)
        source=self.d.workspace/'family-inputs'/(render.digest(snapshot['payload']['brief'])+'.json')
        artifact=self.d.workspace/'family-renders'/self.job/'index.html'
        for path in (source,artifact):
            original=path.read_bytes();path.write_bytes(original+b'\nTEST_ONLY_CHANGED')
            before=self.f.snapshot()
            with self.assertRaises(WorkflowError):self.start(data)
            self.assertEqual(self.f.snapshot(),before);self.assertEqual(self.execute.call_count,0);path.write_bytes(original)

    def test_output_hardlink_fifo_and_oversize_are_never_read_as_downloads(self):
        row=self.settle(self.start()['attempt']);url=row['files'][0]['download_url'];directory=self.s.directory(row['attempt'])
        path=directory/'work'/self.job/render.MEDIA[0];raw=path.read_bytes()
        outside=self.d.workspace/'TEST_ONLY_OUTSIDE';write_private(outside,b'KEEP')
        for kind in ('hardlink','fifo','oversize'):
            path.unlink()
            if kind=='hardlink':os.link(outside,path)
            elif kind=='fifo':os.mkfifo(path,0o600)
            else:write_private(path,raw)
            before=outside.read_bytes(),outside.stat().st_mtime_ns
            with patch.object(render,'MAX_MEDIA',1) if kind=='oversize' else contextlib.nullcontext():
                self.assertEqual(self.state()['status'],'invalidated');self.assertEqual(self.f.get(url)[0],400)
            self.assertEqual((outside.read_bytes(),outside.stat().st_mtime_ns),before)

    def test_close_cancellation_wins_worker_that_returns_after_cancel(self):
        entered,release=self.hold();row=self.start();self.assertTrue(entered.wait(3))
        event=self.s.active[row['attempt']][0];observed=threading.Event();original=event.set
        def cancel():original();observed.set()
        closer=threading.Thread(target=self.s.close)
        with patch.object(event,'set',side_effect=cancel):
            closer.start()
            try:self.assertTrue(observed.wait(2));release.set();closer.join(5);self.assertFalse(closer.is_alive())
            finally:release.set();closer.join(5)
        self.assertEqual(self.state()['status'],'cancelled');self.assertIsNone(self.d.render_slot.current)

    def test_same_process_lost_worker_is_unconfirmed_and_never_automatically_adopted(self):
        self.execute.side_effect=WorkflowError('TEST_ONLY_FAILURE');row=self.settle(self.start()['attempt'])
        with self.d.connection() as db:db.execute("UPDATE family_render_attempts SET status='running',error=NULL WHERE id=?",(row['attempt'],))
        before=self.f.snapshot();self.assertEqual(self.state()['status'],'interrupted_unconfirmed');self.assertEqual(self.f.snapshot(),before)
        self.execute.side_effect=self.fake;new=self.settle(self.start(self.payload('retry',row),'retry')['attempt'])
        self.assertEqual((new['status'],new['generation']),('complete',2))

    def test_normal_worker_completion_or_failure_releases_shared_slot(self):
        from types import SimpleNamespace
        for error in (None,WorkflowError('TEST_ONLY_NORMAL_FAILURE')):
            with patch.object(self.d.renders,'_start_locked',return_value={'status':'started'}):
                self.d.renders.start('a'*24,'hyperframes')
            self.assertIsNotNone(self.d.render_slot.current)
            worker=SimpleNamespace(run=lambda *a,**kw:None,close=lambda:None)
            if error:
                def run(*a,**kw):raise error
                worker.run=run
            with patch('storymotion.dashboard_render.Engine',return_value=worker):
                self.d.renders.work('a'*24,'hyperframes','b'*24,threading.Event())
            self.assertIsNone(self.d.render_slot.current);self.assertFalse(self.d.renders.slot_tokens)

    def test_server_close_retains_instance_guard_for_unsettled_family_worker(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from test_instance_guard import mocked_transport
        from storymotion.dashboard import make_server
        from storymotion.instance_guard import WorkspaceInstance
        root=self.d.workspace/'TEST_ONLY_SERVER'
        with mocked_transport():
            server=make_server(root,43334);family=server.dashboard.family_renders
            thread=SimpleNamespace(is_alive=lambda:True,join=Mock());event=threading.Event()
            family.active['a'*32]=(event,thread,1,'b'*32)
            try:
                with self.assertRaisesRegex(WorkflowError,'BACKGROUND_WORK_ACTIVE'):server.server_close()
                self.assertTrue(event.is_set())
                with self.assertRaisesRegex(WorkflowError,'WORKSPACE_IN_USE'):WorkspaceInstance(root).acquire()
            finally:family.active.clear();server.server_close()
            with WorkspaceInstance(root):pass

    def test_completion_binds_generation_request_key_and_previous_attempt(self):
        row=self.settle(self.start()['attempt']);url=row['files'][0]['download_url']
        for key,value in [('generation',2),('request_key','0'*32),('previous_attempt','0'*32)]:
            original=self.s.row('neutral',self.job,row['attempt'])[key]
            with self.d.connection() as db:db.execute('UPDATE family_render_attempts SET '+key+'=? WHERE id=?',(value,row['attempt']))
            before=self.f.snapshot();self.assertEqual(self.state()['status'],'invalidated');self.assertEqual(self.f.get(url)[0],400);self.assertEqual(self.f.snapshot(),before)
            with self.d.connection() as db:db.execute('UPDATE family_render_attempts SET '+key+'=? WHERE id=?',(original,row['attempt']))
        self.assertEqual(self.state()['status'],'complete')

    def test_queued_attempt_metadata_tamper_fails_before_worker_dispatch(self):
        row,release=self.queued()
        with self.d.connection() as db:db.execute("UPDATE family_render_attempts SET request_key=? WHERE id=?",('0'*32,row['attempt']))
        release.set();self.assertEqual(self.settle(row['attempt'])['status'],'failed');self.assertEqual(self.execute.call_count,0)
        self.assertFalse((self.d.workspace/'family-executions').exists())

    def test_worker_waits_for_bounded_history_read_without_duplicate_or_failed_dispatch(self):
        row,release=self.queued();entered=threading.Event();original=self.s.snapshot
        def snapshot(*args,**kw):entered.set();return original(*args,**kw)
        with patch.object(self.s,'snapshot',side_effect=snapshot):
            with self.d.template_studio.lock:
                release.set();self.assertTrue(entered.wait(3));self.assertEqual(self.execute.call_count,0)
            self.assertEqual(self.settle(row['attempt'])['status'],'complete')
        self.assertEqual(self.execute.call_count,1)
