from pack_fixture_case import PackFixtureCase
import base64
import concurrent.futures
import copy
import http.client
import io
import json
import tempfile
import threading
import time
import types
import unittest
from pathlib import Path
from unittest.mock import patch
from storymotion.elevenlabs import ElevenService,ElevenDemo,ElevenHTTP,fresh_cues,validate_alignment,approval_budget
from storymotion.providers import ProviderError
from storymotion.dashboard import Dashboard,Handler

KEY='FAKE_ELEVENLABS_CONTRACT_CREDENTIAL'
SCRIPT='Kilit açılıyor. Ardından kapak kalkıyor.'


class ChangedDemo(ElevenDemo):
    def __init__(self,change=None,error=None):super().__init__();self.change=change;self.error=error
    def request(self,method,path,key,body=None,operation=None,send_gate=None):
        value,request=super().request(method,path,key,body,operation,send_gate=send_gate)
        if self.error and method=='POST':raise ProviderError(self.error)
        if self.change:value=self.change(method,path,value)
        return value,request


class ElevenContractTests(PackFixtureCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.client=ElevenDemo()
        self.s=ElevenService(self.root,mode='demo',client=self.client)
        self.ref=self.s.connect(KEY)['connection']
    def tearDown(self):self.s.disconnect();self.tmp.cleanup()
    def preview(self,text=SCRIPT):return self.s.preview(self.ref,'contract-job',SCRIPT,text,'demo-voice','demo-model')
    def approve(self,request):return self.s.approve(self.ref,request,SCRIPT,len(SCRIPT),True,True)
    def complete(self):
        r=self.preview()['request'];self.approve(r);return self.s.execute(self.ref,r,SCRIPT,asynchronous=False)
    def paid(self):return [c for c in self.client.calls if c['method']=='POST']
    def test_default_off_never_accepts_or_contacts(self):
        off=ElevenService(self.root/'off')
        with self.assertRaisesRegex(ProviderError,'DISABLED'):off.connect(KEY)
        self.assertFalse(off.broker.status())
    def test_demo_rejects_real_looking_credential_without_echo(self):
        value='sk_'+'z'*30
        with self.assertRaises(ProviderError) as ex:self.s.connect(value)
        self.assertNotIn(value,str(ex.exception));self.assertEqual(len(self.s.broker.status()),1)
    def test_demo_rejects_any_non_synthetic_key_without_prefix_inference(self):
        before=len(self.client.calls)
        with self.assertRaisesRegex(ProviderError,'SYNTHETIC_KEY_REQUIRED'):self.s.connect('sk-'+'ant-'+'x'*30)
        self.assertEqual(len(self.client.calls),before)
    def test_explicit_live_connect_opaque_key_stays_on_elevenlabs_until_upstream_rejects(self):
        value='sk-'+'ant-'+('x'*30)+'+/.=:';captured=[]
        class Unauthorized:
            status=401
        class Connection:
            def __init__(self,host,timeout):captured.append({'host':host})
            def request(self,method,path,body,headers):captured[-1].update(method=method,path=path,headers=headers)
            def getresponse(self):return Unauthorized()
            def close(self):captured[-1]['closed']=True
        service=ElevenService(self.root/'live-mock',mode='live')
        try:
            with patch('storymotion.elevenlabs.http.client.HTTPSConnection',Connection):
                with self.assertRaisesRegex(ProviderError,'HTTP_401'):service.connect(value)
            self.assertEqual(len(captured),1);self.assertEqual(captured[0]['host'],'api.elevenlabs.io')
            self.assertEqual(captured[0]['method'],'GET');self.assertTrue(captured[0]['path'].startswith('/v2/voices?'))
            self.assertEqual(captured[0]['headers']['xi-api-key'],value);self.assertTrue(captured[0]['closed'])
            self.assertFalse(service.connections);self.assertFalse(service.broker.status())
        finally:service.disconnect()
    def test_connect_only_reads_metadata_no_generation(self):
        self.assertEqual(len(self.client.calls),3);self.assertFalse(self.paid())
        self.assertEqual({x['path'].split('?')[0] for x in self.client.calls},{'/v2/voices','/v1/models','/v1/user/subscription'})
    def test_vendor_5xx_keeps_uncertain_hold_and_never_retries(self):
        self.client.error='HTTP_503'
        with patch.object(self.client,'request',wraps=ChangedDemo(error='HTTP_503').request):
            r=self.preview()['request'];self.approve(r)
            result=self.s.execute(self.ref,r,SCRIPT,False)
            self.assertEqual(result['status'],'uncertain')
            self.assertEqual(result['dispatch_count'],1)
            with self.assertRaises(ProviderError):self.s.execute(self.ref,r,SCRIPT,False)
    def test_key_not_persisted_in_ledger_files_or_public_result(self):
        p=self.preview();self.approve(p['request']);r=self.s.execute(self.ref,p['request'],SCRIPT,False)
        self.assertNotIn(KEY,json.dumps(r))
        self.assertTrue(all(KEY.encode() not in f.read_bytes() for f in self.root.rglob('*') if f.is_file()))
    def test_active_expiry_removes_key_and_connection_without_poll(self):
        short=ElevenService(self.root/'short',mode='demo',ttl=.04)
        short.connect(KEY);threading.Event().wait(.12)
        self.assertFalse(short.connections);self.assertFalse(short.broker.status());self.assertFalse(short.timers)
    def test_disconnect_removes_ram_values(self):
        self.s.disconnect(self.ref);self.assertFalse(self.s.connections);self.assertFalse(self.s.broker.status())
    def test_preview_price_is_unknown_not_zero_or_fixed_dollars(self):
        p=self.preview();self.assertIsNone(p['usd_estimate']);self.assertFalse(p['billing_cap_guaranteed'])
        self.assertEqual(p['characters'],len(SCRIPT));self.assertEqual(p['maximum_dispatches'],1)
    def test_approval_and_cap_required(self):
        r=self.preview()['request']
        for cap,ack,rights in [(1,True,True),(len(SCRIPT),False,True),(len(SCRIPT),True,False),(True,True,True)]:
            with self.assertRaises(ProviderError):self.s.approve(self.ref,r,SCRIPT,cap,ack,rights)
        with self.assertRaises(ProviderError):self.s.execute(self.ref,r,SCRIPT,False)
        self.assertFalse(self.paid())
    def test_expired_approval_blocks_wire(self):
        r=self.preview()['request'];self.approve(r)
        with self.s.db() as db:db.execute('UPDATE voice_requests SET approved_until=0 WHERE id=?',(r,))
        with self.assertRaises(ProviderError):self.s.execute(self.ref,r,SCRIPT,False)
        self.assertFalse(self.paid())
    def test_changed_source_script_cannot_use_approval(self):
        r=self.preview()['request'];self.approve(r)
        with self.assertRaisesRegex(ProviderError,'SCOPE'):self.s.execute(self.ref,r,SCRIPT+' Yeni.',False)
        self.assertFalse(self.paid())
    def test_stale_metadata_blocks_new_approval(self):
        r=self.preview()['request'];self.s.connections[self.ref]['metadata_until']=0
        with self.assertRaisesRegex(ProviderError,'REFRESH'):self.approve(r)
        self.assertFalse(self.paid())
    def test_voice_model_and_current_maximum_are_bound(self):
        for voice,model in [('unknown','demo-model'),('demo-voice','unknown')]:
            with self.assertRaises(ProviderError):self.s.preview(self.ref,'contract-job',SCRIPT,SCRIPT,voice,model)
        self.s.connections[self.ref]['metadata']['models'][0]['maximum_text_length_per_request']=2
        with self.assertRaisesRegex(ProviderError,'LIMIT'):self.preview()
    def test_quota_blocks_before_generation(self):
        self.s.connections[self.ref]['metadata']['subscription']['remaining']=1
        with self.assertRaisesRegex(ProviderError,'LIMIT'):self.preview()
        self.assertFalse(self.paid())
    def test_missing_modern_limit_is_not_replaced_with_deprecated_field(self):
        self.s.connections[self.ref]['metadata']['models'][0]['maximum_text_length_per_request']=None
        with self.assertRaisesRegex(ProviderError,'MODEL_LIMIT_UNVERIFIED'):self.preview()
    def test_one_dispatch_and_hash_verified_reuse_after_disconnect(self):
        r=self.complete();self.s.disconnect(self.ref)
        again=self.s.execute(self.ref,r['request'],SCRIPT,False)
        self.assertEqual(r['artifact'],again['artifact']);self.assertEqual(len(self.paid()),1)
    def test_simultaneous_execute_only_one_wire_attempt(self):
        r=self.preview()['request'];self.approve(r)
        def run():
            try:return self.s.execute(self.ref,r,SCRIPT,False)['status']
            except ProviderError:return 'blocked'
        with concurrent.futures.ThreadPoolExecutor(2) as pool:results=list(pool.map(lambda _:run(),range(2)))
        self.assertIn('completed',results);self.assertEqual(len(self.paid()),1)
    def test_different_key_preview_cannot_inherit_approval_after_a_disconnect(self):
        request=self.preview()['request'];self.approve(request)
        approval_a=self.s.get(request)['approval']
        second_key='FAKE_ELEVENLABS_SECOND_SESSION_CREDENTIAL'
        ref_b=self.s.connect(second_key)['connection'];sent=[];base=self.client.request
        def wire(method,path,key,body=None,operation=None,send_gate=None):
            if method=='POST':sent.append(key)
            return base(method,path,key,body,operation,send_gate=send_gate)
        self.client.request=wire
        rebound=self.s.preview(ref_b,'contract-job',SCRIPT,SCRIPT,'demo-voice','demo-model')
        self.assertEqual(rebound['request'],request);self.assertEqual(rebound['status'],'preview')
        self.assertIsNone(rebound['approval']);self.assertIsNone(rebound['approved_until'])
        self.s.disconnect(self.ref)
        with self.assertRaisesRegex(ProviderError,'FRESH_APPROVAL'):self.s.execute(ref_b,request,SCRIPT,False)
        self.assertFalse(sent);self.assertFalse(self.paid())
        self.s.approve(ref_b,request,SCRIPT,len(SCRIPT),True,True)
        self.assertNotEqual(approval_a['connection_scope'],self.s.get(request)['approval']['connection_scope'])
        self.assertEqual(self.s.execute(ref_b,request,SCRIPT,False)['status'],'completed')
        self.assertEqual(sent,[second_key.encode()]);self.assertEqual(len(self.paid()),1)
    def test_new_connection_with_same_key_still_needs_own_consent(self):
        request=self.preview()['request'];self.approve(request)
        ref_b=self.s.connect(KEY)['connection']
        self.s.preview(ref_b,'contract-job',SCRIPT,SCRIPT,'demo-voice','demo-model')
        with self.assertRaisesRegex(ProviderError,'FRESH_APPROVAL'):self.s.execute(ref_b,request,SCRIPT,False)
        with self.assertRaisesRegex(ProviderError,'SCOPE'):self.s.execute(self.ref,request,SCRIPT,False)
        self.assertFalse(self.paid())
    def test_same_connection_preview_keeps_only_its_own_approval(self):
        request=self.preview()['request'];self.approve(request);approval=self.s.get(request)['approval']
        self.assertEqual(self.preview()['approval'],approval)
        self.assertEqual(self.s.execute(self.ref,request,SCRIPT,False)['status'],'completed')
        self.assertEqual(len(self.paid()),1)
    def test_stale_approved_row_cannot_authorize_rebound_connection(self):
        request=self.preview()['request'];self.approve(request);old=self.s.row(request)
        ref_b=self.s.connect('FAKE_ELEVENLABS_OTHER_ACCOUNT_CREDENTIAL')['connection']
        self.s.preview(ref_b,'contract-job',SCRIPT,SCRIPT,'demo-voice','demo-model')
        with self.s.db() as db:db.execute("UPDATE voice_requests SET status='approved',approval=?,approved_until=? WHERE id=?",(old['approval'],old['approved_until'],request))
        with self.assertRaisesRegex(ProviderError,'SCOPE'):self.s.execute(ref_b,request,SCRIPT,False)
        self.assertFalse(self.paid())
    def test_inflight_claim_cannot_be_rebound_before_wire(self):
        request=self.preview()['request'];self.approve(request);self.s._claim(self.ref,request,SCRIPT)
        ref_b=self.s.connect('FAKE_ELEVENLABS_OTHER_ACCOUNT_CREDENTIAL')['connection']
        with self.assertRaisesRegex(ProviderError,'SCOPE_LOCKED'):self.s.preview(ref_b,'contract-job',SCRIPT,SCRIPT,'demo-voice','demo-model')
        self.assertEqual(self.s.bindings[request],self.ref);self.assertFalse(self.paid())
        self.s.cancel(request)
    def test_second_service_rebind_uses_db_scope_and_old_disconnect_cannot_cancel_it(self):
        request=self.preview()['request'];self.approve(request)
        other=ElevenService(self.root,mode='demo')
        try:
            ref_b=other.connect('FAKE_ELEVENLABS_OTHER_SERVICE_CREDENTIAL')['connection']
            other.preview(ref_b,'contract-job',SCRIPT,SCRIPT,'demo-voice','demo-model')
            with self.assertRaisesRegex(ProviderError,'FRESH_APPROVAL'):other.execute(ref_b,request,SCRIPT,False)
            with self.assertRaises(ProviderError):self.s.execute(self.ref,request,SCRIPT,False)
            other.approve(ref_b,request,SCRIPT,len(SCRIPT),True,True);self.s.disconnect(self.ref)
            self.assertEqual(other.get(request)['status'],'approved')
            self.assertEqual(other.execute(ref_b,request,SCRIPT,False)['status'],'completed')
            self.assertFalse(self.paid());self.assertEqual(sum(c['method']=='POST' for c in other.client.calls),1)
        finally:other.disconnect()
    def test_legacy_unscoped_approval_is_invalidated_during_migration(self):
        import sqlite3
        from storymotion.local_state import private_directory,private_database
        folder=self.root.resolve()/'legacy';private_directory(folder);db=private_database(folder,'voice-jobs.sqlite3')
        db.execute('''CREATE TABLE voice_requests(id TEXT PRIMARY KEY,job TEXT NOT NULL,payload TEXT NOT NULL,status TEXT NOT NULL,
            approved_until REAL,deadline REAL,owner TEXT,dispatch_count INTEGER NOT NULL DEFAULT 0,
            artifact TEXT,error_code TEXT,approval TEXT,updated REAL NOT NULL)''')
        request=self.preview()['request'];row=self.s.row(request)
        db.execute('INSERT INTO voice_requests(id,job,payload,status,approved_until,approval,updated) VALUES(?,?,?,?,?,?,?)',
            (request,row['job'],row['payload'],'approved',time.time()+100,'{}',time.time()));db.commit();db.close()
        self.assertEqual(folder.stat().st_mode&0o777,0o700);self.assertEqual((folder/'voice-jobs.sqlite3').stat().st_mode&0o777,0o600)
        legacy=ElevenService(folder,mode='demo')
        try:
            self.assertEqual(legacy.get(request)['status'],'preview');self.assertIsNone(legacy.get(request)['approval'])
            self.assertFalse(legacy.client.calls)
        finally:legacy.disconnect()
    def test_timeout_uncertain_no_retry_and_holds_other_generation(self):
        self.client=ChangedDemo(error='OUTCOME_UNCERTAIN');self.s.client=self.client
        r=self.preview()['request'];self.approve(r);result=self.s.execute(self.ref,r,SCRIPT,False)
        self.assertEqual(result['status'],'uncertain')
        with self.assertRaises(ProviderError):self.s.execute(self.ref,r,SCRIPT,False)
        other=self.s.preview(self.ref,'another-job',SCRIPT,SCRIPT,'demo-voice','demo-model')['request'];self.approve(other)
        with self.assertRaisesRegex(ProviderError,'HOLD'):self.s.execute(self.ref,other,SCRIPT,False)
        self.assertEqual(len(self.paid()),1)
    def test_auth_rate_and_permission_errors_are_not_retried(self):
        for status in [401,403,429]:
            service=ElevenService(self.root/str(status),mode='demo',client=ChangedDemo(error='HTTP_'+str(status)))
            ref=service.connect(KEY)['connection'];r=service.preview(ref,'job',SCRIPT,SCRIPT,'demo-voice','demo-model')['request']
            service.approve(ref,r,SCRIPT,len(SCRIPT),True,True);result=service.execute(ref,r,SCRIPT,False)
            self.assertEqual(result['status'],'failed_known_no_retry')
            with self.assertRaises(ProviderError):service.execute(ref,r,SCRIPT,False)
            self.assertEqual(len([c for c in service.client.calls if c['method']=='POST']),1);service.disconnect()
    def test_metadata_failure_wipes_key_and_never_generates(self):
        client=ChangedDemo(change=lambda method,path,value: {'voices':'bad'} if path.startswith('/v2/voices?') else value)
        service=ElevenService(self.root/'invalid-list',mode='demo',client=client)
        with self.assertRaises(ProviderError):service.connect(KEY)
        self.assertFalse(service.connections);self.assertFalse(service.broker.status());self.assertFalse(any(c['method']=='POST' for c in client.calls))
    def test_repeating_pagination_token_fails_closed(self):
        client=ChangedDemo(change=lambda method,path,value:{'voices':[],'has_more':True,'next_page_token':'same'} if path.startswith('/v2/voices?') else value)
        service=ElevenService(self.root/'pages',mode='demo',client=client)
        with self.assertRaisesRegex(ProviderError,'PAGINATION'):service.connect(KEY)
        self.assertEqual(len(client.calls),2);self.assertFalse(service.broker.status())
    def test_cancel_before_dispatch_never_sends(self):
        r=self.preview()['request'];self.approve(r);self.assertEqual(self.s.cancel(r)['status'],'cancelled')
        with self.assertRaises(ProviderError):self.s.execute(self.ref,r,SCRIPT,False)
        self.assertFalse(self.paid())
    def test_cancel_after_dispatch_has_no_retry_or_false_refund(self):
        entered=threading.Event();release=threading.Event();base=self.client.request
        def blocked(method,path,key,body=None,operation=None,send_gate=None):
            response=base(method,path,key,body,operation,send_gate=send_gate)
            if method=='POST':entered.set();release.wait(2)
            return response
        self.client.request=blocked;r=self.preview()['request'];self.approve(r);self.s.execute(self.ref,r,SCRIPT)
        self.assertTrue(entered.wait(1));self.assertEqual(self.s.cancel(r)['status'],'uncertain');release.set()
        end=time.monotonic()+3
        while r in self.s.threads and time.monotonic()<end:threading.Event().wait(.02)
        result=self.s.get(r);self.assertEqual(result['status'],'received_after_cancel_review')
        self.assertFalse(result['artifact']['publication_ready']);self.assertEqual(len(self.paid()),1)
    def test_new_audio_has_fresh_timestamps_srt_and_invalidates_old_visemes(self):
        r=self.complete();timing=json.loads(self.s.download(r['request'],'timestamps.json'))
        self.assertTrue(timing['old_subtitles_invalid']);self.assertTrue(timing['old_visemes_invalid'])
        self.assertEqual(timing['source_audio_sha256'],r['artifact']['source_audio_sha256'])
        self.assertIsNotNone(timing['cues']);self.assertIn('Kilit açılıyor.',self.s.download(r['request'],'fresh-subtitles.srt').decode())
        with self.assertRaisesRegex(ProviderError,'FRESH_TIMING'):self.s.guard_old_timing('contract-job')
    def test_phonetic_tts_is_not_silently_written_as_screen_subtitles(self):
        r=self.s.preview(self.ref,'contract-job',SCRIPT,'TTS telaffuzu farklı.','demo-voice','demo-model')['request']
        self.s.approve(self.ref,r,SCRIPT,100,True,True);result=self.s.execute(self.ref,r,SCRIPT,False)
        timing=json.loads(self.s.download(r,'timestamps.json'));self.assertIsNone(timing['cues'])
        self.assertNotIn('fresh-subtitles.srt',result['artifact']['files'])
    def test_tampered_audio_cannot_be_downloaded_or_recharged(self):
        r=self.complete();(self.root/r['request']/'narration.mp3').write_bytes(b'tamper')
        with self.assertRaisesRegex(ProviderError,'HASH'):self.s.download(r['request'],'narration.mp3')
        with self.assertRaisesRegex(ProviderError,'HASH'):self.s.execute(self.ref,r['request'],SCRIPT,False)
        self.assertEqual(len(self.paid()),1)
    def test_key_echo_in_provider_response_is_quarantined(self):
        self.client=ChangedDemo(change=lambda m,p,v:{**v,'echo':KEY} if m=='POST' else v);self.s.client=self.client
        r=self.preview()['request'];self.approve(r);result=self.s.execute(self.ref,r,SCRIPT,False)
        self.assertEqual(result['status'],'uncertain');self.assertEqual(result['error_code'],'CREDENTIAL_ECHO_BLOCKED')
        self.assertNotIn(KEY,json.dumps(result));self.assertFalse(list(self.root.rglob('*.mp3')))
    def test_invalid_alignment_does_not_reuse_old_times_or_retry(self):
        def bad(m,p,v):
            if m=='POST':v['alignment']['character_end_times_seconds'][0]=float('inf')
            return v
        self.s.client=ChangedDemo(change=bad)
        r=self.preview()['request'];self.approve(r);result=self.s.execute(self.ref,r,SCRIPT,False)
        self.assertEqual(result['status'],'uncertain');self.assertIsNone(result['artifact'])
        with self.assertRaises(ProviderError):self.s.execute(self.ref,r,SCRIPT,False)
    def test_live_budget_needs_current_user_quote_and_finite_cap(self):
        for value in [None,{}, {'max_usd':'1','estimate_usd':'2','quote_source':'Current account quote','verified_by_user':True},
                      {'max_usd':'NaN','estimate_usd':'.01','quote_source':'Current account quote','verified_by_user':True}]:
            with self.assertRaises(ProviderError):approval_budget(value,False)
        good=approval_budget({'max_usd':'.02','estimate_usd':'.01','quote_source':'Synthetic current quote test, no market price','verified_by_user':True},False)
        self.assertEqual(good['maximum_microusd'],20000);self.assertFalse(good['api_verified_usd_rate'])
    def test_voice_list_auth_denial_clears_session(self):
        def deny(*args,**kwargs):raise ProviderError('HTTP_403')
        self.client.request=deny
        with self.assertRaisesRegex(ProviderError,'403'):self.s.metadata(self.ref)
        self.assertFalse(self.s.broker.status());self.assertFalse(self.s.connections)
    def test_restart_keeps_completed_result_without_another_dispatch(self):
        result=self.complete();self.s.disconnect()
        other=ElevenService(self.root,mode='demo');ref=other.connect(KEY)['connection']
        preview=other.preview(ref,'contract-job',SCRIPT,SCRIPT,'demo-voice','demo-model')
        self.assertEqual(preview['request'],result['request'])
        self.assertEqual(other.execute(ref,preview['request'],SCRIPT,False)['artifact'],result['artifact'])
        self.assertFalse(any(c['method']=='POST' for c in other.client.calls));other.disconnect()
    def test_expired_dispatch_lease_becomes_uncertain_without_retry(self):
        r=self.preview()['request'];self.approve(r)
        with self.s.db() as db:db.execute("UPDATE voice_requests SET status='dispatching',dispatch_count=1,deadline=0 WHERE id=?",(r,))
        result=self.s.get(r);self.assertEqual(result['status'],'uncertain')
        with self.assertRaises(ProviderError):self.s.execute(self.ref,r,SCRIPT,False)
        self.assertFalse(self.paid())


class ElevenDashboardTests(PackFixtureCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.d=Dashboard(self.root,elevenlabs_mode='demo')
        self.job=self.d.enqueue({'account':'sample-flow','format':'video-script','title':'Voice contract','brief':'Local demo','content':SCRIPT,'caption':'Local demo',
            'provider':'local','model':'manual','task':'text','template_revision':0})['id']
    def tearDown(self):self.d.clear_keys();self.tmp.cleanup()
    def test_voice_job_is_linked_and_stale_source_export_is_blocked(self):
        self.d.prepare(self.job);self.d.export(self.job)
        c=self.d.voice_action('connect',{'value':KEY})['connection']
        p=self.d.voice_action('preview',{'connection':c,'job':self.job,'tts_text':SCRIPT,'voice_id':'demo-voice','model_id':'demo-model'})
        self.d.voice_action('approve',{'connection':c,'request':p['request'],'maximum_characters':len(SCRIPT),'ack_unknown_cost':True,'rights_confirmed':True})
        self.d.eleven.execute(c,p['request'],SCRIPT,False)
        with self.assertRaisesRegex(ProviderError,'FRESH_TIMING'):self.d.export(self.job)
        with self.assertRaisesRegex(ProviderError,'FRESH_TIMING'):self.d.prepare(self.job)
        with self.assertRaisesRegex(ProviderError,'FRESH_TIMING'):self.d.renders.start(self.job,'remotion')
        self.assertEqual(self.d.voice_action('state',{'job':self.job})['requests'][0]['job'],self.job)
    def test_new_routes_still_require_origin_and_custom_header(self):
        h=Handler.__new__(Handler);h.server=types.SimpleNamespace(server_address=('127.0.0.1',4397),dashboard=self.d)
        h.headers=http.client.HTTPMessage();h.headers['Host']='127.0.0.1:4397';h.path='/api/elevenlabs/connect'
        h.rfile=io.BytesIO(b'{}');responses=[];h.send=lambda code,value:responses.append((code,value));h.do_POST()
        self.assertEqual(responses[0][0],403);self.assertFalse(self.d.eleven.connections)
    def test_static_frontend_never_persists_key(self):
        from storymotion.engine import ROOT
        js=(ROOT/'dashboard/app.js').read_text();html=(ROOT/'dashboard/index.html').read_text()
        self.assertNotIn('localStorage',js);self.assertNotIn('sessionStorage',js);self.assertNotIn('console.log',js)
        self.assertIn('id="el-key" type="password"',html);self.assertIn('ack_unknown_cost:true',js)
        self.assertNotIn(KEY,js+html)
    def test_controls_have_unique_ids_and_reachable_labels(self):
        from html.parser import HTMLParser
        from storymotion.engine import ROOT
        class Controls(HTMLParser):
            def __init__(self):super().__init__();self.ids=[];self.labels=[]
            def handle_starttag(self,tag,attrs):
                values=dict(attrs)
                if 'id' in values:self.ids.append(values['id'])
                if tag=='label' and 'for' in values:self.labels.append(values['for'])
        parser=Controls();parser.feed((ROOT/'dashboard/index.html').read_text())
        self.assertEqual(len(parser.ids),len(set(parser.ids)))
        self.assertTrue(set(parser.labels).issubset(parser.ids))
        self.assertEqual(parser.ids.count('el-key'),1)


class ElevenWireTests(PackFixtureCase):
    def test_socket_timeout_does_not_retry_and_closes_owned_connection(self):
        calls=[]
        class Fake:
            def __init__(self,*a,**kw):pass
            def request(self,*a,**kw):calls.append('request')
            def getresponse(self):raise TimeoutError('redacted')
            def close(self):calls.append('close')
        client=ElevenHTTP(enabled=True)
        with patch('storymotion.elevenlabs.http.client.HTTPSConnection',Fake):
            with self.assertRaisesRegex(ProviderError,'UNCERTAIN'):client.request('GET','/v1/models',b'contract_credential_not_real_000')
        self.assertEqual(calls.count('request'),1);self.assertIn('close',calls);self.assertFalse(client.pending)
    def test_https_host_header_and_no_redirect_or_retry(self):
        calls=[]
        class Fake:
            def __init__(self,host,timeout):calls.append(('host',host,timeout))
            def request(self,method,path,body,headers):calls.append(('request',method,path,headers.copy()))
            def getresponse(self):return self
            status=302
            def close(self):pass
        client=ElevenHTTP(enabled=True)
        value=b'contract_wire_credential_not_real'
        with patch('storymotion.elevenlabs.http.client.HTTPSConnection',Fake):
            with self.assertRaisesRegex(ProviderError,'HTTP_302'):client.request('GET','/v1/models',value)
        self.assertEqual(calls[0][1],'api.elevenlabs.io');self.assertEqual(calls[1][3]['xi-api-key'],value.decode())
        self.assertEqual(len([c for c in calls if c[0]=='request']),1);self.assertFalse(client.pending)
    def test_external_endpoint_and_fake_key_never_go_live(self):
        client=ElevenHTTP(enabled=True)
        with patch('storymotion.elevenlabs.http.client.HTTPSConnection') as network:
            with self.assertRaises(ProviderError):client.request('GET','https://other.invalid/',b'wire_contract_not_real_credential')
            with self.assertRaises(ProviderError):client.request('GET','/v1/models',KEY.encode())
            network.assert_not_called()


if __name__=='__main__':unittest.main()
