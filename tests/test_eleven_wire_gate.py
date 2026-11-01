from pack_fixture_case import PackFixtureCase
"""Deterministic queued-worker regressions. Inert credentials; no network/media.

The approval is valid when execute claims it, then invalid before the actual
transport write. A rejected gate must leave zero POSTs and require new consent.
"""
import contextlib
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from storymotion.dashboard import Dashboard
from storymotion.elevenlabs import ElevenService,ElevenDemo,ElevenHTTP
from storymotion.providers import ProviderError
from storymotion.security import canonical

KEY='FAKE_QUEUED_WIRE_CONTRACT_ONLY'
SCRIPT='Kilit açılır. Kapak kalkar.'
PATH='/v1/text-to-speech/demo-voice/with-timestamps?output_format=mp3_44100_128'


class QueuedVoiceGateTests(PackFixtureCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.s=ElevenService(self.root,mode='demo');self.ref=self.s.connect(KEY)['connection']
    def tearDown(self):self.s.disconnect();self.tmp.cleanup()
    def approved(self):
        request=self.s.preview(self.ref,'wire-job',SCRIPT,SCRIPT,'demo-voice','demo-model')['request']
        self.s.approve(self.ref,request,SCRIPT,len(SCRIPT),True,True)
        return request
    def queued(self,request,mutate,transport_wait=False):
        entered=threading.Event();release=threading.Event()
        target=self.s.client if transport_wait else self.s
        name='request' if transport_wait else '_work';base=getattr(target,name)
        def held(*args,**kwargs):
            entered.set()
            if not release.wait(3):raise AssertionError('test barrier timeout')
            return base(*args,**kwargs)
        with patch.object(target,name,held):
            self.s.execute(self.ref,request,SCRIPT)
            worker=self.s.threads.get(request)
            try:
                self.assertTrue(entered.wait(2));mutate()
            finally:
                release.set()
                if worker:worker.join(3)
            self.assertFalse(worker and worker.is_alive())
        return self.s.get(request)
    def no_send(self,result):
        self.assertEqual(result['status'],'invalidated')
        self.assertEqual(result['dispatch_count'],0);self.assertIsNone(result['artifact'])
        self.assertIsNone(result['approval']);self.assertIsNone(result['approved_until'])
        self.assertFalse(any(c['method']=='POST' for c in self.s.client.calls))
        self.assertFalse(list(self.root.rglob('narration*')))
        with self.assertRaises(ProviderError):self.s.execute(self.ref,result['request'],SCRIPT,False)
    def expire_approval(self,request):
        with self.s.db() as db:db.execute('UPDATE voice_requests SET approved_until=? WHERE id=?',(time.time()-1,request))
    def test_queued_approval_expiry_is_invalidated_with_zero_post(self):
        r=self.approved();self.no_send(self.queued(r,lambda:self.expire_approval(r)))
    def test_approval_expiry_during_transport_preparation_still_has_zero_post(self):
        r=self.approved();self.no_send(self.queued(r,lambda:self.expire_approval(r),True))
    def test_queued_execution_source_change_is_invalidated_with_zero_post(self):
        r=self.approved();source={'fingerprint':self.s.runtime_execution}
        with patch('storymotion.elevenlabs.current_execution',side_effect=lambda:source['fingerprint']):
            self.no_send(self.queued(r,lambda:source.update(fingerprint='f'*64)))
    def test_queued_claim_text_voice_model_and_budget_cannot_change(self):
        for field in ['tts_text','voice_id','model_id','budget']:
            with self.subTest(field=field):
                r=self.approved()
                def mutate():
                    with self.s.db() as db:
                        row=db.execute('SELECT payload,approval FROM voice_requests WHERE id=?',(r,)).fetchone()
                        p=json.loads(row['payload']);a=json.loads(row['approval'])
                        if field=='budget':a['budget']['maximum_microusd']=999999
                        else:p[field]='changed-after-claim'
                        db.execute('UPDATE voice_requests SET payload=?,approval=? WHERE id=?',(canonical(p),canonical(a),r))
                self.no_send(self.queued(r,mutate))
                # Each case uses a new request, retaining the tampered DB for inspection.
                self.s.disconnect()
                self.s=ElevenService(self.root/field,mode='demo');self.ref=self.s.connect(KEY)['connection']
    def test_queued_connection_scope_change_has_zero_post(self):
        r=self.approved()
        def mutate():
            with self.s.db() as db:db.execute('UPDATE voice_requests SET binding_scope=? WHERE id=?',('other-session',r))
        self.no_send(self.queued(r,mutate))
    def test_metadata_expiry_at_wire_invalidates_without_db_lock_deadlock(self):
        r=self.approved()
        self.no_send(self.queued(r,lambda:self.s.connections[self.ref].update(metadata_until=0),True))
    def test_cancel_before_wire_has_zero_post(self):
        r=self.approved();result=self.queued(r,lambda:self.s.cancel(r),True)
        self.assertEqual(result['status'],'cancelled');self.assertEqual(result['dispatch_count'],0)
        self.assertFalse(any(c['method']=='POST' for c in self.s.client.calls))
    def test_unspent_expired_dispatch_lease_is_invalidated_not_uncertain(self):
        r=self.approved()
        with self.s.db() as db:db.execute("UPDATE voice_requests SET status='dispatching',deadline=0 WHERE id=?",(r,))
        self.no_send(self.s.get(r))
    def test_fresh_preview_and_consent_can_recover_unspent_invalidation_once(self):
        r=self.approved();self.no_send(self.queued(r,lambda:self.expire_approval(r)))
        self.assertEqual(self.approved(),r)
        with patch('storymotion.engine.probe',return_value={'duration':4,'streams':[{'codec_type':'audio'}]}),patch('storymotion.engine.checked_process',return_value=b''):
            result=self.s.execute(self.ref,r,SCRIPT,False)
        self.assertEqual(result['status'],'completed');self.assertEqual(result['dispatch_count'],1)
        self.assertEqual(len([c for c in self.s.client.calls if c['method']=='POST']),1)


class DashboardQueuedVoiceTests(PackFixtureCase):
    def test_dashboard_source_changes_after_claim_but_before_worker(self):
        with tempfile.TemporaryDirectory() as root:
            d=Dashboard(root,elevenlabs_mode='demo');s=d.eleven
            entered=threading.Event();release=threading.Event();base=s._work
            try:
                job=d.enqueue(dict(account='sample-flow',format='video-script',title='Wire contract',brief='Local',content=SCRIPT,
                    caption='Local contract',provider='local',model='manual',task='text',template_revision=0))['id']
                ref=s.connect(KEY)['connection'];r=s.preview(ref,job,SCRIPT,SCRIPT,'demo-voice','demo-model')['request']
                s.approve(ref,r,SCRIPT,len(SCRIPT),True,True)
                def held(*args):
                    entered.set();release.wait(3);return base(*args)
                with patch.object(s,'_work',held):
                    s.execute(ref,r,SCRIPT);worker=s.threads[r];self.assertTrue(entered.wait(2))
                    with patch('storymotion.dashboard.execution_provenance',return_value={'fingerprint':'f'*64}):
                        release.set();worker.join(3)
                self.assertFalse(worker.is_alive());result=s.get(r)
                self.assertEqual(result['status'],'invalidated');self.assertEqual(result['error_code'],'VOICE_SOURCE_INVALIDATED')
                self.assertEqual(result['dispatch_count'],0);self.assertIsNone(result['approval'])
                self.assertFalse(any(c['method']=='POST' for c in s.client.calls))
            finally:release.set();d.clear_keys()


class TransportFinalGateTests(PackFixtureCase):
    def test_http_post_gate_runs_after_preparation_before_any_wire_write(self):
        events=[];valid={'value':True}
        class Connection:
            def __init__(self,*args,**kwargs):events.append('prepared');valid['value']=False
            def request(self,*args,**kwargs):events.append('POST')
            def close(self):events.append('closed')
        @contextlib.contextmanager
        def gate(*args):
            events.append('gate')
            if not valid['value']:raise ProviderError('APPROVAL_INVALIDATED')
            yield
        client=ElevenHTTP(enabled=True)
        with patch('storymotion.elevenlabs.http.client.HTTPSConnection',Connection):
            with self.assertRaisesRegex(ProviderError,'INVALIDATED'):
                client.request('POST',PATH,b'inert_contract_credential_only',{'text':SCRIPT,'model_id':'demo-model'},send_gate=gate)
        self.assertEqual(events,['prepared','gate','closed']);self.assertFalse(client.pending)
    def test_default_http_post_requires_explicit_final_gate(self):
        events=[]
        class Connection:
            def __init__(self,*args,**kwargs):pass
            def request(self,*args,**kwargs):events.append('POST')
            def close(self):pass
        with patch('storymotion.elevenlabs.http.client.HTTPSConnection',Connection):
            with self.assertRaisesRegex(ProviderError,'GATE_REQUIRED'):
                ElevenHTTP(enabled=True).request('POST',PATH,b'inert_contract_credential_only',{'text':SCRIPT,'model_id':'demo-model'})
        self.assertEqual(events,[])
