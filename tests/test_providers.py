from pack_fixture_case import PackFixtureCase
import dataclasses
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from storymotion.engine import Engine,ROOT
from storymotion.provider_runtime import ProviderRuntime
from storymotion.providers import ADAPTERS,HTTPSTransport,MockTransport,NoRedirect,Permit,Plan,ProviderError,Response,SecretBroker,execute,opaque_key,safe_public_json,validate_plan,credential_echo,Result


def reply(provider='openai',text='Original synthetic output.'):
    value={'id':'resp_fixture','status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':text}]}],'usage':{'input_tokens':20,'output_tokens':8,'total_tokens':28}}
    if provider=='openrouter':value={'id':'chat_fixture','choices':[{'finish_reason':'stop','message':{'role':'assistant','content':text}}],'usage':{'prompt_tokens':20,'completion_tokens':8,'total_tokens':28}}
    return Response(200,'application/json',json.dumps(value).encode())


class ProviderTests(PackFixtureCase):
    def setUp(self):
        self.broker=SecretBroker();self.job='job_fixture';self.plan=ADAPTERS['openai'].build('synthetic-openai-model','A new brief for this job.',200)
        self.permit=Permit(self.plan.fingerprint,self.job,20000,10000,time.time()+60,'Synthetic approval only')
        self.value='FAKE_OPENAI_CONTRACT_TEST_12345'
        self.slot=self.broker.put('openai',self.job,self.plan.fingerprint,self.value,synthetic=True)
    def tearDown(self):self.broker.clear()
    def test_openai_uses_responses_contract(self):
        self.assertEqual(self.plan.url,'https://api.openai.com/v1/responses');self.assertEqual(self.plan.body['input'],'A new brief for this job.');self.assertFalse(self.plan.body['store']);self.assertEqual(self.plan.body['max_output_tokens'],200)
    def test_openrouter_uses_chat_contract(self):
        p=ADAPTERS['openrouter'].build('vendor/model','A new brief.',200)
        self.assertEqual(p.url,'https://openrouter.ai/api/v1/chat/completions');self.assertIn('max_tokens',p.body);self.assertNotIn('max_output_tokens',p.body);self.assertFalse(p.body['stream'])
    def test_elevenlabs_uses_voice_and_xi_contract(self):
        p=ADAPTERS['elevenlabs'].build('eleven_v4','Synthetic narration text.','voice_fixture')
        self.assertIn('/text-to-speech/voice_fixture?',p.url);self.assertEqual(p.body,{'text':'Synthetic narration text.','model_id':'eleven_v4'});self.assertEqual(p.public()['auth_header'],'xi-api-key')
    def test_mock_execution_parses_original_generated_text(self):
        transport=MockTransport(reply(text='This was generated for a different new brief.'))
        result=execute(self.plan,self.broker,self.slot,self.permit,transport,self.job)
        self.assertEqual(result.data.decode(),'This was generated for a different new brief.');self.assertEqual(len(transport.calls),1)
        self.assertNotIn(self.value,json.dumps(transport.calls));self.assertNotIn(self.value,repr(result))
    def test_live_disabled_before_credential_resolution(self):
        with patch.object(self.broker,'lease',side_effect=AssertionError('must not access key')):
            with self.assertRaisesRegex(ProviderError,'LIVE_TRANSPORT_DISABLED'):execute(self.plan,self.broker,self.slot,self.permit,HTTPSTransport(),self.job)
    def test_live_disabled_no_network(self):
        with patch('urllib.request.build_opener',side_effect=AssertionError('network forbidden')):
            with self.assertRaises(ProviderError):HTTPSTransport().exchange(self.plan,b'fake',self.permit,self.job)
    def test_synthetic_key_cannot_go_live(self):
        with self.assertRaisesRegex(ProviderError,'SYNTHETIC'):execute(self.plan,self.broker,self.slot,self.permit,HTTPSTransport(allow_live=True),self.job)
    def test_actual_https_request_assembly_with_mock_opener_only(self):
        captured={};response=reply()
        class StubResponse:
            status=200;headers={'Content-Type':'application/json'}
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,limit):return response.body
        class StubOpener:
            def open(self,request,timeout):captured.update(url=request.full_url,method=request.method,body=json.loads(request.data),headers=request.headers,timeout=timeout);return StubResponse()
        opaque=b'EXAMPLE_NOT_A_REAL_CREDENTIAL_12345'
        with patch('urllib.request.build_opener',return_value=StubOpener()) as build:
            result=HTTPSTransport(allow_live=True).exchange(self.plan,opaque,self.permit,self.job)
        self.assertEqual(result.status,200);self.assertEqual(captured['method'],'POST');self.assertEqual(captured['url'],self.plan.url)
        self.assertEqual(captured['headers']['Authorization'],'Bearer '+opaque.decode());self.assertEqual(captured['body'],self.plan.body)
        self.assertTrue(any(isinstance(x,NoRedirect) for x in build.call_args.args))
    def test_scope_does_not_cross_provider_job_or_request(self):
        for provider,job,request in [('openrouter',self.job,self.plan.fingerprint),('openai','other_job',self.plan.fingerprint),('openai',self.job,'other_request')]:
            with self.subTest(provider=provider,job=job,request=request),self.assertRaisesRegex(ProviderError,'SCOPE'):
                with self.broker.lease(self.slot,provider,job,request,True):pass
    def test_real_intake_defaults_off(self):
        with self.assertRaisesRegex(ProviderError,'REAL_KEY_INTAKE_DISABLED'):self.broker.put('openai',self.job,self.plan.fingerprint,'EXAMPLE_NOT_A_REAL_CREDENTIAL_12345')
    def test_opaque_malformed_keys_never_echo(self):
        for key in ['', 'a'*513, 'x'*30+'\r\nHeader:bad', ' x', 'x ', 'x y', 'x\t', 'x\x00', 'x\x1f', 'x\x7f', 'x☃', None, {'value':'a'*30}]:
            with self.subTest(key_type=type(key).__name__),self.assertRaisesRegex(ProviderError,'MALFORMED_CREDENTIAL'):opaque_key(key)
    def test_opaque_short_and_punctuation_values_are_preserved_without_network(self):
        with patch('urllib.request.build_opener',side_effect=AssertionError('validation cannot initiate network')):
            for key in ['x','short','a'*19,'a'*512,'x+/.=:{}!~','https://example.invalid/opaque?value=+/:=']:
                with self.subTest(length=len(key)):self.assertEqual(opaque_key(key),key.encode('ascii'))
    def test_quoted_backslash_credential_is_found_in_decoded_values_and_dict_keys(self):
        key=b'FAKE_OPAQUE_"\\TOKEN';text=key.decode('ascii')
        for value in [text,key,{'nested':[{'ordinary':text}]},{text:'ordinary'},(text,)]:
            self.assertTrue(credential_echo(value,key))
        self.assertFalse(credential_echo({'ordinary':'safe'},key))
    def test_quoted_backslash_credential_cannot_escape_active_broker_export(self):
        key='FAKE_OPAQUE_"\\TOKEN';broker=SecretBroker()
        try:
            broker.put('openai',self.job,self.plan.fingerprint,key,synthetic=True)
            for value in [{'ordinary':[key]},{key:'ordinary'}]:
                self.assertNotIn(key.encode(),json.dumps(value).encode())
                with self.assertRaisesRegex(ProviderError,'SECRET_EXPORT_BLOCKED'):safe_public_json(value,broker)
        finally:broker.clear()
    def test_quoted_backslash_metadata_after_broker_clear_never_reaches_commit(self):
        key='FAKE_OPAQUE_"\\TOKEN';broker=SecretBroker();consumed=[]
        slot=broker.put('openai',self.job,self.plan.fingerprint,key,synthetic=True)
        class Clear(MockTransport):
            def exchange(self,*args):broker.clear();return reply()
        parsed=Result('openai',key,'text/plain',b'Safe generated text.',{'reported':False})
        try:
            with patch.object(ADAPTERS['openai'],'parse',return_value=parsed):
                with self.assertRaisesRegex(ProviderError,'CREDENTIAL_ECHO_BLOCKED'):
                    execute(self.plan,broker,slot,self.permit,Clear(),self.job,consume=lambda result,raw:consumed.append(result))
            self.assertFalse(consumed)
        finally:broker.clear()
    def test_active_broker_expiry_without_poll(self):
        b=SecretBroker(ttl_seconds=.04);ref=b.put('openai',self.job,self.plan.fingerprint,self.value,synthetic=True);slot=b._slots[ref];threading.Event().wait(.15)
        self.assertNotIn(ref,b._slots);self.assertFalse(any(slot['raw']));b.clear()
    def test_clear_drops_all_slots_and_timers(self):
        raw=self.broker._slots[self.slot]['raw'];self.broker.clear();self.assertFalse(self.broker._slots);self.assertFalse(self.broker._timers);self.assertFalse(any(raw))
    def test_request_tampering_and_custom_endpoint_refused(self):
        for p in [dataclasses.replace(self.plan,url='https://attacker.invalid/'),dataclasses.replace(self.plan,model='other'),dataclasses.replace(self.plan,capability='voice'),dataclasses.replace(self.plan,body={'api_key':'FAKE_TEST_VALUE'})]:
            with self.subTest(url=p.url),self.assertRaises(ProviderError):validate_plan(p)
    def test_voice_id_does_not_inject_path_or_query(self):
        for voice in ['../private','voice?token=bad','voice/other','http://evil','x\r\ny']:
            with self.subTest(voice=voice),self.assertRaises(ProviderError):ADAPTERS['elevenlabs'].build('eleven_v4','Synthetic narration.',voice)
    def test_limits_and_unknown_options_refused(self):
        for limit in [False,0,-1,16001,float('nan'),1.2]:
            with self.subTest(limit=limit),self.assertRaises(ProviderError):ADAPTERS['openai'].build('synthetic-openai-model','Prompt',limit)
    def test_expired_wrong_request_and_small_budget_refused(self):
        for permit in [dataclasses.replace(self.permit,expires_at=0),dataclasses.replace(self.permit,request_hash='different'),dataclasses.replace(self.permit,maximum_microusd=1)]:
            with self.subTest(permit=repr(permit)),self.assertRaises(ProviderError):execute(self.plan,self.broker,self.slot,permit,MockTransport(reply()),self.job)
    def test_auth_rate_limit_errors_do_not_echo_provider_body(self):
        for status in [401,403,429,500]:
            with self.subTest(status=status),self.assertRaises(ProviderError) as error:ADAPTERS['openai'].parse(Response(status,'application/json',self.value.encode()),self.broker)
            self.assertNotIn(self.value,str(error.exception))
    def test_credential_echo_blocked_even_when_slot_expires_in_transport(self):
        owner=self
        class ExpiringMock(MockTransport):
            def exchange(self,*args):
                owner.broker.clear();return reply(text=owner.value)
        with self.assertRaisesRegex(ProviderError,'CREDENTIAL_ECHO_BLOCKED'):execute(self.plan,self.broker,self.slot,self.permit,ExpiringMock(),self.job)
    def test_malformed_and_incomplete_response_not_success(self):
        bodies=[b'not json',b'[]',b'{"status":"incomplete"}',b'{"status":"completed","id":"x","output":["bad"]}']
        for body in bodies:
            with self.subTest(body=body[:20]),self.assertRaises(ProviderError):ADAPTERS['openai'].parse(Response(200,'application/json',body))
    def test_usage_negative_or_noninteger_refused(self):
        value=json.loads(reply().body);value['usage']['input_tokens']=-1
        with self.assertRaises(ProviderError):ADAPTERS['openai'].parse(Response(200,'application/json',json.dumps(value).encode()))
    def test_openrouter_incomplete_not_success(self):
        v=json.loads(reply('openrouter').body);v['choices'][0]['finish_reason']='length'
        with self.assertRaisesRegex(ProviderError,'INCOMPLETE'):ADAPTERS['openrouter'].parse(Response(200,'application/json',json.dumps(v).encode()))
    def test_audio_binary_signature_and_type(self):
        p=ADAPTERS['elevenlabs'];result=p.parse(Response(200,'audio/mpeg',b'ID3SYNTHETIC_TEST_NOT_PLAYABLE'))
        self.assertEqual(result.usage['technical_decode'],'required_before_use')
        for r in [Response(200,'text/html',b'ID3fake'),Response(200,'audio/mpeg',b'error text')]:
            with self.assertRaises(ProviderError):p.parse(r)
    def test_export_blocks_opaque_value_and_sensitive_fields(self):
        for value in [{'notes':self.value},{'Authorization':'opaque value'},{'nested':[{'api_key':'FAKE_TEST'}]}]:
            with self.assertRaises(ProviderError):safe_public_json(value,self.broker)
        self.assertNotIn(self.value,safe_public_json(self.plan.public(),self.broker).decode())
    def test_redirect_is_always_blocked(self):
        with self.assertRaisesRegex(ProviderError,'REDIRECT_BLOCKED'):NoRedirect().redirect_request(None,None,None,None,None,None)


class RuntimeTests(PackFixtureCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.e=Engine(self.root/'work');self.job=self.e.create(ROOT/'tests/fixtures/examples/sample-mechanism.json')['job']
        self.broker=SecretBroker();self.transport=MockTransport(reply());self.runtime=ProviderRuntime(self.root/'work',self.broker,self.transport)
        self.plan=ADAPTERS['openai'].build('synthetic-openai-model','A new original brief.',200)
        self.ref=self.runtime.prepare(self.job,self.plan,'.01','Synthetic estimate; not a market price')['request']
        self.slot=self.broker.put('openai',self.job,self.plan.fingerprint,'FAKE_OPENAI_RUNTIME_TEST_12345',synthetic=True)
    def tearDown(self):self.broker.clear();self.tmp.cleanup()
    def approve(self):self.runtime.approve(self.ref,'.02','Synthetic approval only')
    def test_runtime_requires_job_and_request_budget(self):
        with self.assertRaisesRegex(ProviderError,'UNKNOWN_JOB'):self.runtime.prepare('unknown',self.plan,'.01','Synthetic')
        with self.assertRaisesRegex(ProviderError,'NOT_APPROVED'):self.runtime.run(self.ref,self.slot)
    def test_duplicate_dispatch_reuses_receipt_and_one_ledger_row(self):
        self.approve();first=self.runtime.run(self.ref,self.slot);second=self.runtime.run(self.ref,self.slot)
        self.assertEqual(first['status'],'complete_mock');self.assertEqual(second['status'],'reused');self.assertEqual(len(self.transport.calls),1)
        self.assertEqual(self.runtime.store.db.execute('SELECT count(*) FROM provider_receipts').fetchone()[0],1)
        self.assertEqual(first['receipt']['actual_microusd'],0)
    def test_runtime_live_defaults_off_even_with_approval(self):
        self.approve();r=ProviderRuntime(self.root/'work',self.broker)
        with patch('urllib.request.build_opener',side_effect=AssertionError('no external call')):
            with self.assertRaisesRegex(ProviderError,'LIVE_TRANSPORT_DISABLED'):r.run(self.ref,self.slot)
        self.assertEqual(r.row(self.ref)['status'],'approved')
    def test_uncertain_response_never_automatically_retries(self):
        self.approve();self.transport.error='TRANSPORT_OUTCOME_UNCERTAIN'
        with self.assertRaises(ProviderError):self.runtime.run(self.ref,self.slot)
        with self.assertRaisesRegex(ProviderError,'NO_AUTOMATIC_RETRY'):self.runtime.run(self.ref,self.slot)
        with self.assertRaises(ProviderError):self.runtime.approve(self.ref,'.02','Another test')
        self.assertEqual(len(self.transport.calls),1)
    def test_mock_receipt_reconciliation_without_second_dispatch(self):
        self.approve();self.transport.error='TRANSPORT_OUTCOME_UNCERTAIN'
        with self.assertRaises(ProviderError):self.runtime.run(self.ref,self.slot)
        self.runtime.reconcile_mock(self.ref,reply());self.assertEqual(self.runtime.run(self.ref,self.slot)['status'],'reused');self.assertEqual(len(self.transport.calls),1)
    def test_repricing_cannot_create_second_request(self):
        with self.assertRaisesRegex(ProviderError,'NO_REKEY'):self.runtime.prepare(self.job,self.plan,'.02','Different synthetic quote')
    def test_raw_credential_absent_from_events_db_and_output(self):
        self.approve();self.runtime.run(self.ref,self.slot);self.runtime.store.db.commit()
        key=b'FAKE_OPENAI_RUNTIME_TEST_12345'
        self.assertNotIn(key,(self.root/'work/jobs.sqlite3').read_bytes())
        for p in (self.root/'work/provider-output').rglob('*'):
            if p.is_file():self.assertNotIn(key,p.read_bytes())
    def test_credential_echo_never_persisted(self):
        self.approve();self.transport.response=reply(text='FAKE_OPENAI_RUNTIME_TEST_12345')
        with self.assertRaisesRegex(ProviderError,'ECHO_BLOCKED'):self.runtime.run(self.ref,self.slot)
        self.assertFalse(list((self.root/'work/provider-output').glob('**/output.txt')))
        self.assertEqual(self.runtime.row(self.ref)['status'],'uncertain')
    def test_escaped_metadata_echo_after_disconnect_is_never_persisted(self):
        self.approve();owner=self
        key='FAKE_OPENAI_RUNTIME_TEST_12345'
        value=json.loads(reply().body);value['id']=key
        body=json.dumps(value).replace(key,''.join('\\u%04x'%ord(c) for c in key)).encode()
        self.assertNotIn(key.encode(),body)
        class ClearDuringExchange(MockTransport):
            def exchange(self,*args):
                result=super().exchange(*args);owner.broker.clear();return result
        transport=ClearDuringExchange(Response(200,'application/json',body))
        runtime=ProviderRuntime(self.root/'work',self.broker,transport)
        with self.assertRaisesRegex(ProviderError,'CREDENTIAL_ECHO_BLOCKED'):runtime.run(self.ref,self.slot)
        self.assertEqual(len(transport.calls),1)
        self.assertEqual(runtime.row(self.ref)['status'],'uncertain')
        runtime.store.db.commit()
        for path in (self.root/'work').rglob('*'):
            if path.is_file():self.assertNotIn(key.encode(),path.read_bytes())
        self.assertFalse(list((self.root/'work/provider-output').glob('**/receipt.json')))


if __name__=='__main__':unittest.main()
