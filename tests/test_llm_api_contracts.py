from pack_fixture_case import PackFixtureCase
import dataclasses
import http.client
import io
import json
import time
import unittest
import urllib.error
from unittest.mock import patch
from storymotion.providers import (ADAPTERS,ANTHROPIC_VERSION,AUTH_HEADERS,HTTPSTransport,
    MockTransport,Permit,ProviderError,Response,SecretBroker,execute,request_headers,
    validate_credential_provider,validate_plan)
from storymotion.llm_api import LLMMetadataHTTP,LLMMetadataDemo,SYNTHETIC_MODEL_IDS,MAX_BODY

KEY='FAKE_ANTHROPIC_CONTRACT_CREDENTIAL'


def anthropic_reply(text='{"original":"fixture"}',**changes):
    value={'id':'msg_synthetic','type':'message','role':'assistant','model':'synthetic-anthropic-text',
        'content':[{'type':'text','text':text}],'stop_reason':'end_turn','stop_sequence':None,
        'usage':{'input_tokens':20,'output_tokens':10,'cache_creation_input_tokens':0,'cache_read_input_tokens':0}}
    value.update(changes)
    return Response(200,'application/json',json.dumps(value).encode())


class AnthropicContractTests(PackFixtureCase):
    def setUp(self):
        self.plan=ADAPTERS['anthropic'].build('synthetic-anthropic-text','New original prompt.',200)
        self.b=SecretBroker();self.slot=self.b.put('anthropic','job',self.plan.fingerprint,KEY,synthetic=True)
        self.permit=Permit(self.plan.fingerprint,'job',20000,10000,time.time()+60,'Synthetic consent')
    def tearDown(self):self.b.clear()
    def test_exact_messages_body_and_headers(self):
        self.assertEqual(self.plan.url,'https://api.anthropic.com/v1/messages')
        self.assertEqual(self.plan.body,{'model':'synthetic-anthropic-text','messages':[{'role':'user','content':'New original prompt.'}],'max_tokens':200,'stream':False})
        h=request_headers('anthropic',KEY.encode());self.assertEqual(h[AUTH_HEADERS['anthropic']],KEY)
        self.assertEqual(h['anthropic-version'],ANTHROPIC_VERSION);self.assertNotIn('Authorization',h)
    def test_prefix_never_overrides_explicit_provider_or_fixed_endpoint(self):
        cases=[('openai',b'sk-'+b'ant-'+b'x'*30),('anthropic',b'sk-'+b'proj-'+b'x'*30),('anthropic',b'sk-'+b'or-'+b'x'*30)]
        for provider,key in cases:
            captured=[]
            class RejectingOpener:
                def open(self,request,timeout):
                    captured.append(request)
                    raise urllib.error.HTTPError(request.full_url,401,'synthetic upstream rejection',{},None)
            plan=ADAPTERS[provider].build('synthetic-'+provider+'-text','Synthetic test.',200)
            permit=Permit(plan.fingerprint,'job',20000,10000,time.time()+60,'Synthetic consent')
            self.assertEqual(validate_credential_provider(provider,key),key)
            with patch('urllib.request.build_opener',return_value=RejectingOpener()):
                with self.assertRaisesRegex(ProviderError,'HTTP_401'):HTTPSTransport(True).exchange(plan,key,permit,'job')
            self.assertEqual(len(captured),1);self.assertEqual(captured[0].full_url,plan.url)
            headers={k.lower():v for k,v in captured[0].header_items()}
            expected=key.decode() if provider=='anthropic' else 'Bearer '+key.decode()
            self.assertEqual(headers[AUTH_HEADERS[provider].lower()],expected)
        self.assertEqual(validate_credential_provider('anthropic',b'FAKE_OPENAI_CONTRACT_CREDENTIAL'),b'FAKE_OPENAI_CONTRACT_CREDENTIAL')
    def test_header_validation_accepts_short_opaque_symbols_and_rejects_controls(self):
        with patch('urllib.request.build_opener',side_effect=AssertionError('header assembly is not connect')):
            for provider in ('openai','anthropic','elevenlabs'):
                for key in (b'x',b'x+/.=:{}!~'):
                    h=request_headers(provider,key);auth=h[AUTH_HEADERS[provider]]
                    self.assertEqual(auth,('Bearer ' if provider=='openai' else '')+key.decode('ascii'))
                for key in (b'',b'x '*5,b'x\r\nHeader:bad',b'x\t',b'x\x00',b'x\x7f','x☃'.encode(),b'x'*513):
                    with self.assertRaisesRegex(ProviderError,'MALFORMED_CREDENTIAL'):request_headers(provider,key)
    def test_mock_parses_only_text_and_numeric_usage(self):
        r=execute(self.plan,self.b,self.slot,self.permit,MockTransport(anthropic_reply()),'job')
        self.assertEqual(json.loads(r.data),{'original':'fixture'});self.assertEqual(r.usage['output_tokens'],10)
        self.assertEqual(r.provider,'anthropic');self.assertNotIn(KEY,json.dumps(r.public()))
    def test_incomplete_refusal_and_tool_results_fail_closed(self):
        for reason in ['max_tokens','tool_use','pause_turn','refusal','stop_sequence',None]:
            with self.subTest(reason=reason),self.assertRaisesRegex(ProviderError,'INCOMPLETE'):
                ADAPTERS['anthropic'].parse(anthropic_reply(stop_reason=reason))
        with self.assertRaisesRegex(ProviderError,'REFUSAL'):
            ADAPTERS['anthropic'].parse(anthropic_reply(stop_details={'type':'refusal'}))
        with self.assertRaisesRegex(ProviderError,'UNSUPPORTED'):
            ADAPTERS['anthropic'].parse(anthropic_reply(content=[{'type':'tool_use','id':'call','name':'unsafe','input':{}}]))
    def test_reasoning_is_not_returned_or_stored_as_script(self):
        r=ADAPTERS['anthropic'].parse(anthropic_reply(content=[{'type':'thinking','thinking':'private reasoning'},
            {'type':'text','text':'{"safe":true}'}]))
        self.assertEqual(r.data,b'{"safe":true}');self.assertNotIn('private reasoning',json.dumps(r.public()))
    def test_malformed_json_type_and_usage_are_refused(self):
        for body in [b'invalid',b'[]',b'{}']:
            with self.assertRaises(ProviderError):ADAPTERS['anthropic'].parse(Response(200,'application/json',body))
        for value in [-1,True,1.5,'5']:
            with self.subTest(value=value),self.assertRaises(ProviderError):
                ADAPTERS['anthropic'].parse(anthropic_reply(usage={'input_tokens':value}))
    def test_mutated_url_body_and_tools_are_refused(self):
        plans=[dataclasses.replace(self.plan,url='https://other.invalid/v1/messages'),
            dataclasses.replace(self.plan,body={**self.plan.body,'tools':[{'name':'unsafe'}]}),
            dataclasses.replace(self.plan,body={**self.plan.body,'stream':True})]
        for plan in plans:
            with self.assertRaises(ProviderError):validate_plan(plan)
    def test_decoded_metadata_echo_after_clear_never_reaches_consumer(self):
        base=json.loads(anthropic_reply().body);base['id']=KEY
        body=json.dumps(base).replace(KEY,'\\u0046'+KEY[1:]).encode();self.assertNotIn(KEY.encode(),body)
        owner=self
        class Expire(MockTransport):
            def exchange(self,*args):
                super().exchange(*args);owner.b.clear();return Response(200,'application/json',body)
        consumed=[]
        with self.assertRaisesRegex(ProviderError,'ECHO_BLOCKED'):
            execute(self.plan,self.b,self.slot,self.permit,Expire(anthropic_reply()),'job',consume=lambda r,k:consumed.append(r))
        self.assertFalse(consumed)
    def test_output_echo_after_clear_never_reaches_consumer(self):
        body=anthropic_reply(KEY).body.replace(KEY.encode(),('\\u0046'+KEY[1:]).encode());owner=self
        class Expire(MockTransport):
            def exchange(self,*args):owner.b.clear();return Response(200,'application/json',body)
        with self.assertRaisesRegex(ProviderError,'ECHO_BLOCKED'):
            execute(self.plan,self.b,self.slot,self.permit,Expire(),'job')
    def test_numeric_usage_cannot_carry_encoded_key(self):
        response=anthropic_reply(usage={'input_tokens':KEY});self.assertRaises(ProviderError,ADAPTERS['anthropic'].parse,response)
    def test_active_lease_survives_until_commit_guard(self):
        seen=[]
        result=execute(self.plan,self.b,self.slot,self.permit,MockTransport(anthropic_reply()),'job',
            consume=lambda r,key:seen.append((r.provider,key)) or 'committed')
        self.assertEqual(result,'committed');self.assertEqual(seen,[('anthropic',KEY.encode())])
    def test_live_is_disabled_and_fake_cannot_go_live(self):
        with patch('urllib.request.build_opener',side_effect=AssertionError('network forbidden')):
            with self.assertRaisesRegex(ProviderError,'DISABLED'):HTTPSTransport().exchange(self.plan,KEY.encode(),self.permit,'job')
            with self.assertRaisesRegex(ProviderError,'SYNTHETIC'):HTTPSTransport(True).exchange(self.plan,KEY.encode(),self.permit,'job')
    def test_auth_and_version_assembly_has_no_fallback_or_extra_headers(self):
        captured=[];payload=anthropic_reply()
        class Reply:
            status=200;headers={'Content-Type':'application/json'}
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,n):return payload.body
        class Opener:
            def open(self,req,timeout):captured.append(req);return Reply()
        with patch('urllib.request.build_opener',return_value=Opener()):
            HTTPSTransport(True).exchange(self.plan,b'EXAMPLE_SYNTHETIC_WIRE_CONTRACT_ONLY',self.permit,'job')
        self.assertEqual(len(captured),1);req=captured[0];headers={k.lower():v for k,v in req.header_items()}
        self.assertEqual(req.full_url,'https://api.anthropic.com/v1/messages');self.assertEqual(headers['anthropic-version'],'2023-06-01')
        self.assertIn('x-api-key',headers);self.assertNotIn('authorization',headers);self.assertNotIn('anthropic-workspace-id',headers)


class FakeResponse:
    def __init__(self,value,status=200,content_type='application/json'):
        self.status=status;self.mime=content_type;self.stream=io.BytesIO(value if isinstance(value,bytes) else json.dumps(value).encode())
    def getheader(self,name,default=None):return self.mime if name=='Content-Type' else default
    def read1(self,limit):return self.stream.read(limit)


class MetadataTests(PackFixtureCase):
    def fake(self,values):
        calls=[];replies=list(values)
        class Connection:
            def __init__(self,host,timeout):calls.append({'host':host,'timeout':timeout})
            def request(self,method,path,headers):calls[-1].update(method=method,path=path,headers=headers)
            def getresponse(self):
                value=replies.pop(0)
                if isinstance(value,Exception):raise value
                return value
            def close(self):calls[-1]['closed']=True
        return calls,patch('storymotion.llm_api.http.client.HTTPSConnection',Connection)
    def test_disabled_and_fake_keys_do_not_reach_network(self):
        with patch('storymotion.llm_api.http.client.HTTPSConnection') as wire:
            for client,provider,key in [(LLMMetadataHTTP(),'openai',b'x'*30),
                (LLMMetadataHTTP(True),'openai',b'FAKE_OPENAI_TEST_CREDENTIAL')]:
                with self.assertRaises(ProviderError):client.list_models(provider,key)
            wire.assert_not_called()
    def test_opaque_prefix_and_symbols_use_selected_metadata_host_until_upstream_rejects(self):
        for provider,key in [('openai',b'sk-'+b'ant-'+b'x'*30),('anthropic',b'x+/.=:{}!~')]:
            calls,stub=self.fake([FakeResponse(b'unread upstream body',status=401)])
            with stub,self.assertRaisesRegex(ProviderError,'HTTP_401'):LLMMetadataHTTP(True).list_models(provider,key)
            self.assertEqual(len(calls),1);self.assertEqual(calls[0]['host'],'api.'+provider+'.com')
            self.assertNotIn(key.decode(),calls[0]['path']);self.assertTrue(calls[0]['closed'])
    def test_demo_ids_are_explicitly_synthetic_and_price_unknown(self):
        demo=LLMMetadataDemo()
        for provider in ['openai','anthropic']:
            result=demo.list_models(provider,b'FAKE_GENERIC_CONTRACT_CREDENTIAL')
            self.assertTrue(result['synthetic']);self.assertEqual(result['models'][0]['id'],SYNTHETIC_MODEL_IDS[provider])
            self.assertIsNone(result['usd_estimate']);self.assertFalse(result['verified_usd_rate'])
        with self.assertRaises(ProviderError):demo.list_models('openai',b'EXAMPLE_WIRE_CONTRACT_CREDENTIAL')
    def test_openai_is_one_fixed_get_sanitized_without_invented_limits_or_rates(self):
        values=[FakeResponse({'data':[{'id':'fixture-text','owned_by':'private_org','secret_extra':'not retained'}]})]
        calls,stub=self.fake(values)
        with stub:r=LLMMetadataHTTP(True).list_models('openai',b'EXAMPLE_WIRE_CONTRACT_CREDENTIAL')
        self.assertEqual(len(calls),1);self.assertEqual(calls[0]['host'],'api.openai.com');self.assertEqual(calls[0]['path'],'/v1/models')
        self.assertTrue(calls[0]['closed']);self.assertTrue(calls[0]['headers']['Authorization'].startswith('Bearer '))
        self.assertIsNone(r['models'][0]['max_output_tokens']);self.assertNotIn('private_org',json.dumps(r));self.assertIsNone(r['usd_estimate'])
    def test_anthropic_pagination_limits_and_header(self):
        calls,stub=self.fake([FakeResponse({'data':[{'id':'fixture-a','display_name':'Fixture A','max_tokens':123,'max_input_tokens':456}],
            'has_more':True,'last_id':'fixture-a'}),FakeResponse({'data':[{'id':'fixture-b','display_name':'Fixture B'}],'has_more':False,'last_id':'fixture-b'})])
        with stub:r=LLMMetadataHTTP(True).list_models('anthropic',b'EXAMPLE_WIRE_CONTRACT_CREDENTIAL')
        self.assertEqual([m['id'] for m in r['models']],['fixture-a','fixture-b']);self.assertFalse(r['truncated'])
        self.assertEqual(r['models'][0]['max_output_tokens'],123);self.assertEqual(r['models'][0]['max_input_tokens'],456)
        self.assertEqual(calls[1]['path'],'/v1/models?limit=100&after_id=fixture-a');self.assertEqual(calls[0]['headers']['anthropic-version'],'2023-06-01')
    def test_repeating_cursor_fails_closed_no_retry(self):
        page={'data':[],'has_more':True,'last_id':'fixture-cursor'};calls,stub=self.fake([FakeResponse(page),FakeResponse(page)])
        with stub,self.assertRaisesRegex(ProviderError,'PAGINATION'):LLMMetadataHTTP(True).list_models('anthropic',b'EXAMPLE_WIRE_CONTRACT_CREDENTIAL')
        self.assertEqual(len(calls),2)
    def test_page_budget_marks_truncated(self):
        calls,stub=self.fake([FakeResponse({'data':[{'id':'fixture-a'}],'has_more':True,'last_id':'fixture-a'})])
        with stub:r=LLMMetadataHTTP(True,max_pages=1).list_models('anthropic',b'EXAMPLE_WIRE_CONTRACT_CREDENTIAL')
        self.assertTrue(r['truncated']);self.assertEqual(len(calls),1)
    def test_model_count_budget_and_unsupported_id_filter(self):
        calls,stub=self.fake([FakeResponse({'data':[{'id':'ft:unsupported'},{'id':'fixture-a'},{'id':'fixture-b'}]})])
        with stub:r=LLMMetadataHTTP(True,max_models=1).list_models('openai',b'EXAMPLE_WIRE_CONTRACT_CREDENTIAL')
        self.assertEqual(r['filtered_models'],1);self.assertTrue(r['truncated']);self.assertEqual(len(r['models']),1)
    def test_auth_rate_and_redirect_never_retry_or_echo(self):
        for status in [401,403,429,302]:
            calls,stub=self.fake([FakeResponse(b'secret response is not read',status=status)])
            with stub,self.assertRaisesRegex(ProviderError,'HTTP_'+str(status)):
                LLMMetadataHTTP(True).list_models('openai',b'EXAMPLE_WIRE_CONTRACT_CREDENTIAL')
            self.assertEqual(len(calls),1);self.assertTrue(calls[0]['closed'])
    def test_timeout_closes_single_owned_connection(self):
        calls,stub=self.fake([TimeoutError('do not log raw exception')])
        with stub,self.assertRaisesRegex(ProviderError,'TIMEOUT'):LLMMetadataHTTP(True).list_models('openai',b'EXAMPLE_WIRE_CONTRACT_CREDENTIAL')
        self.assertEqual(len(calls),1);self.assertTrue(calls[0]['closed'])
    def test_json_escape_secret_is_blocked_before_any_metadata_is_returned(self):
        key=b'EXAMPLE_WIRE_CONTRACT_CREDENTIAL'
        raw=json.dumps({'data':[{'id':key.decode()}]}).replace(key.decode(),'\\u0045'+key.decode()[1:]).encode()
        self.assertNotIn(key,raw);calls,stub=self.fake([FakeResponse(raw)])
        with stub,self.assertRaisesRegex(ProviderError,'ECHO_BLOCKED'):LLMMetadataHTTP(True).list_models('openai',key)
        self.assertTrue(calls[0]['closed'])
    def test_json_escaped_quoted_backslash_key_is_checked_in_decoded_metadata(self):
        key=b'EXAMPLE_OPAQUE_"\\TOKEN'
        for value in [{'data':[{'id':'fixture-model','display_name':key.decode()}],'has_more':False},
                      {'data':[],key.decode():'ordinary','has_more':False}]:
            raw=json.dumps(value).encode();self.assertNotIn(key,raw)
            calls,stub=self.fake([FakeResponse(raw)])
            with stub,self.assertRaisesRegex(ProviderError,'ECHO_BLOCKED'):LLMMetadataHTTP(True).list_models('anthropic',key)
            self.assertTrue(calls[0]['closed'])
    def test_invalid_json_list_and_content_type_fail(self):
        for response in [FakeResponse(b'bad json'),FakeResponse([]),FakeResponse({'data':'bad'}),FakeResponse({},content_type='text/html')]:
            calls,stub=self.fake([response])
            with stub,self.assertRaises(ProviderError):LLMMetadataHTTP(True).list_models('openai',b'EXAMPLE_WIRE_CONTRACT_CREDENTIAL')
            self.assertEqual(len(calls),1)
    def test_oversized_response_fails_without_returning_partial_model_list(self):
        calls,stub=self.fake([FakeResponse(b' '*(MAX_BODY+1))])
        with stub,self.assertRaisesRegex(ProviderError,'TOO_LARGE'):LLMMetadataHTTP(True).list_models('openai',b'EXAMPLE_WIRE_CONTRACT_CREDENTIAL')
    def test_total_deadline_stops_after_slow_response_chunk(self):
        calls,stub=self.fake([FakeResponse({'data':[]})])
        with stub,patch('storymotion.llm_api.time.monotonic',side_effect=[0,0,0,21]):
            with self.assertRaisesRegex(ProviderError,'TIMEOUT'):LLMMetadataHTTP(True).list_models('openai',b'EXAMPLE_WIRE_CONTRACT_CREDENTIAL')
        self.assertTrue(calls[0]['closed'])


if __name__=='__main__':unittest.main()
