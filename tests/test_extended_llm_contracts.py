from pack_fixture_case import PackFixtureCase
"""Four-provider native contracts. All upstream responses are local synthetic mocks."""
import copy
import dataclasses
import io
import json
import time
import unittest
from unittest.mock import patch
from storymotion.providers import (ADAPTERS,AUTH_HEADERS,HTTPSTransport,MockTransport,Permit,
    ProviderError,Response,SecretBroker,execute,model_identifier,request_headers,validate_plan)
from storymotion.llm_api import LLMMetadataHTTP,LLMMetadataDemo,SYNTHETIC_MODEL_IDS


def response(provider,text='{"original":"fixture"}',**changes):
    if provider=='gemini':
        value={'responseId':'synthetic-response','candidates':[{'content':{'role':'model','parts':[{'text':text}]},'finishReason':'STOP'}],
            'usageMetadata':{'promptTokenCount':20,'candidatesTokenCount':10,'totalTokenCount':35,'thoughtsTokenCount':5}}
    else:
        value={'id':'synthetic-response','choices':[{'finish_reason':'stop','message':{'role':'assistant','content':text}}],
            'usage':{'prompt_tokens':20,'completion_tokens':10,'total_tokens':30,'cost':0.0}}
    value.update(changes);return Response(200,'application/json',json.dumps(value).encode())


class NativeTextContracts(PackFixtureCase):
    def test_gemini_native_request_normalization_key_header_and_explicit_bounds(self):
        plan=ADAPTERS['gemini'].build('models/synthetic-gemini-text','Original prompt',200)
        self.assertEqual(plan.model,'synthetic-gemini-text')
        self.assertEqual(plan.url,'https://generativelanguage.googleapis.com/v1beta/models/synthetic-gemini-text:generateContent')
        self.assertEqual(plan.body,{'contents':[{'role':'user','parts':[{'text':'Original prompt'}]}],'generationConfig':{'maxOutputTokens':200}})
        self.assertEqual(plan.fingerprint,ADAPTERS['gemini'].build(plan.model,'Original prompt',200).fingerprint)
        key=b'EXAMPLE_OPAQUE_"\\TOKEN';headers=request_headers('gemini',key)
        self.assertEqual(headers[AUTH_HEADERS['gemini']],key.decode());self.assertNotIn('Authorization',headers);self.assertNotIn(key.decode(),plan.url)
        for value in (True,0,15,8001):
            with self.assertRaises(ProviderError):ADAPTERS['gemini'].build(plan.model,'Original',value)
    def test_provider_specific_model_paths_cannot_change_host_or_route_automatically(self):
        bad=['../other','models/models/id','https://attacker.invalid/id','model?key=bad','model#bad','model:generateContent','model%2Fother','x/y']
        for model in bad:
            with self.subTest(model=model),self.assertRaises(ProviderError):ADAPTERS['gemini'].build(model,'Original')
        for model in ['vendor/model:free','synthetic/openrouter-text']:
            self.assertEqual(model_identifier('openrouter',model),model)
        for model in ['openrouter/auto','openrouter/free','vendor/model/other','vendor/model?key=x','http://attacker','vendor/../model','vendor/model::free']:
            with self.subTest(model=model),self.assertRaises(ProviderError):ADAPTERS['openrouter'].build(model,'Original')
    def test_openrouter_request_explicitly_disables_vendor_fallback_and_ignored_parameters(self):
        plan=ADAPTERS['openrouter'].build('synthetic/model:free','Original',200)
        self.assertEqual(plan.url,'https://openrouter.ai/api/v1/chat/completions')
        self.assertEqual(plan.body['provider'],{'allow_fallbacks':False,'require_parameters':True})
        self.assertEqual(plan.body['max_tokens'],200);self.assertFalse(plan.body['stream'])
        for value in (True,15,8001):
            with self.assertRaises(ProviderError):ADAPTERS['openrouter'].build(plan.model,'Original',value)
        for body in [{**plan.body,'models':['another/model']},{**plan.body,'provider':{'allow_fallbacks':True,'require_parameters':True}},
                     {**plan.body,'provider':{'allow_fallbacks':False,'require_parameters':False}}]:
            with self.assertRaises(ProviderError):validate_plan(dataclasses.replace(plan,body=body))
    def test_gemini_rebuilt_plan_rejects_extra_tools_stream_or_mutated_model(self):
        plan=ADAPTERS['gemini'].build('synthetic-gemini-text','Original',200)
        values=[dataclasses.replace(plan,model='other-model'),dataclasses.replace(plan,url=plan.url+'?key=anything'),
            dataclasses.replace(plan,body={**plan.body,'tools':[{'googleSearch':{}}]}),
            dataclasses.replace(plan,body={**plan.body,'generationConfig':{'maxOutputTokens':200,'responseModalities':['IMAGE']}})]
        for value in values:
            with self.assertRaises(ProviderError):validate_plan(value)
    def test_gemini_success_returns_only_visible_text_and_numeric_usage(self):
        value=json.loads(response('gemini').body)
        value['candidates'][0]['content']['parts']=[{'text':'private thought','thought':True,'thoughtSignature':'private-signature'},
            {'text':'{"original":'},{'text':'true}'}]
        value['usageMetadata']['private_extra']='not retained'
        result=ADAPTERS['gemini'].parse(Response(200,'application/json',json.dumps(value).encode()))
        self.assertEqual(json.loads(result.data),{'original':True});self.assertEqual(result.usage['thoughtsTokenCount'],5)
        self.assertNotIn('private',json.dumps(result.public()));self.assertNotIn('cost',result.usage)
    def test_gemini_missing_usage_and_response_id_remain_unknown(self):
        value=json.loads(response('gemini').body);value.pop('usageMetadata');value.pop('responseId')
        result=ADAPTERS['gemini'].parse(Response(200,'application/json',json.dumps(value).encode()))
        self.assertEqual(result.usage,{'reported':False});self.assertIsNone(result.provider_id)
        self.assertEqual(result.public()['actual_cost'],'unknown_until_provider_receipt')
    def test_gemini_refusal_empty_tools_and_nonfinal_responses_are_never_success(self):
        base=json.loads(response('gemini').body);values=[]
        for reason in ['MAX_TOKENS','SAFETY','CONTINUATION','UNEXPECTED_TOOL_CALL',None]:
            value=copy.deepcopy(base);value['candidates'][0]['finishReason']=reason;values.append(value)
        for parts in [[],[{'functionCall':{'name':'unsafe'}}],[{'inlineData':{'data':'fixture'}}],[{'text':''}],[{'text':'reason','thought':True}]]:
            value=copy.deepcopy(base);value['candidates'][0]['content']['parts']=parts;values.append(value)
        values += [{**base,'promptFeedback':{'blockReason':'SAFETY'}},{**base,'candidates':[]},{**base,'candidates':[base['candidates'][0]]*2}]
        value=copy.deepcopy(base);value['candidates'][0]['safetyRatings']=[{'blocked':True}];values.append(value)
        for value in values:
            with self.assertRaises(ProviderError):ADAPTERS['gemini'].parse(Response(200,'application/json',json.dumps(value).encode()))
    def test_openrouter_missing_usage_is_unknown_and_private_usage_not_saved(self):
        result=ADAPTERS['openrouter'].parse(response('openrouter',usage=None))
        self.assertEqual(result.usage,{'reported':False});self.assertIn('unknown',result.public()['actual_cost'])
        result=ADAPTERS['openrouter'].parse(response('openrouter'));self.assertNotIn('cost',result.usage)
    def test_openrouter_empty_refused_tool_malformed_and_nonfinal_are_rejected(self):
        base=json.loads(response('openrouter').body);values=[]
        for reason in ['length','error','tool_calls','content_filter',None]:
            value=copy.deepcopy(base);value['choices'][0]['finish_reason']=reason;values.append(value)
        for change in [{'content':''},{'refusal':'refused'},{'tool_calls':[{'id':'unsafe'}]},{'function_call':{'name':'unsafe'}},{'role':'tool'}]:
            value=copy.deepcopy(base);value['choices'][0]['message'].update(change);values.append(value)
        values += [{**base,'choices':[]},{**base,'choices':[base['choices'][0]]*2},{**base,'choices':[{'finish_reason':'stop','message':[]}]}]
        for value in values:
            with self.assertRaises(ProviderError):ADAPTERS['openrouter'].parse(Response(200,'application/json',json.dumps(value).encode()))
    def test_both_new_adapters_reject_noninteger_negative_usage_and_bad_json(self):
        for provider,field,name in [('gemini','usageMetadata','promptTokenCount'),('openrouter','usage','prompt_tokens')]:
            for count in [-1,True,1.5,'2',100000001]:
                with self.assertRaises(ProviderError):ADAPTERS[provider].parse(response(provider,**{field:{name:count}}))
            for body in [b'bad json',b'[]',b'{}']:
                with self.assertRaises(ProviderError):ADAPTERS[provider].parse(Response(200,'application/json',body))
    def test_key_with_quote_backslash_echo_after_broker_clear_blocks_both_consumers(self):
        for provider in ['gemini','openrouter']:
            key='FAKE_OPAQUE_"\\TOKEN';broker=SecretBroker();model=SYNTHETIC_MODEL_IDS[provider]
            plan=ADAPTERS[provider].build(model,'Original',200);slot=broker.put(provider,'job',plan.fingerprint,key,synthetic=True)
            permit=Permit(plan.fingerprint,'job',1,0,time.time()+60,'Synthetic consent');consumed=[]
            payload=response(provider,key);self.assertNotIn(key.encode(),payload.body)
            class Expire(MockTransport):
                def exchange(self,*args):broker.clear();return payload
            try:
                with self.assertRaisesRegex(ProviderError,'CREDENTIAL_ECHO_BLOCKED'):
                    execute(plan,broker,slot,permit,Expire(),'job',consume=lambda r,k:consumed.append(r))
                self.assertFalse(consumed)
            finally:broker.clear()
    def test_new_transports_never_live_with_disabled_or_demo_key(self):
        for provider in ['gemini','openrouter']:
            plan=ADAPTERS[provider].build(SYNTHETIC_MODEL_IDS[provider],'Original',200)
            permit=Permit(plan.fingerprint,'job',1,0,time.time()+60,'Synthetic consent')
            with patch('urllib.request.build_opener',side_effect=AssertionError('real network forbidden')):
                for client in [HTTPSTransport(),HTTPSTransport(True)]:
                    with self.assertRaises(ProviderError):client.exchange(plan,b'FAKE_OPAQUE_TEST',permit,'job')


class WireResponse:
    def __init__(self,value,status=200):self.status=status;self.stream=io.BytesIO(json.dumps(value).encode())
    def getheader(self,name,default=None):return 'application/json' if name=='Content-Type' else default
    def read1(self,limit):return self.stream.read(limit)


class ExtendedDiscoveryContracts(PackFixtureCase):
    def wire(self,values):
        replies=list(values);calls=[]
        class Connection:
            def __init__(self,host,timeout):calls.append({'host':host})
            def request(self,method,path,headers):calls[-1].update(method=method,path=path,headers=headers)
            def getresponse(self):return replies.pop(0)
            def close(self):calls[-1]['closed']=True
        return calls,patch('storymotion.llm_api.http.client.HTTPSConnection',Connection)
    def model(self,provider,identity='fixture-model'):
        if provider=='gemini':return {'name':'models/'+identity,'displayName':'Fixture','supportedGenerationMethods':['generateContent'],'inputTokenLimit':1234,'outputTokenLimit':567}
        return {'id':'fixture/'+identity,'name':'Fixture','architecture':{'input_modalities':['text'],'output_modalities':['text']},
            'supported_parameters':['max_tokens'],'context_length':1234,'top_provider':{'max_completion_tokens':567},'pricing':{'prompt':'0','completion':'0'}}
    def test_four_demo_ids_remain_synthetic_unknown_cost_and_separate_from_live(self):
        for provider in ['openai','anthropic','gemini','openrouter']:
            value=LLMMetadataDemo().list_models(provider,b'FAKE_DEMO_OPAQUE')
            self.assertTrue(value['synthetic']);self.assertEqual(value['models'][0]['id'],SYNTHETIC_MODEL_IDS[provider]);self.assertIsNone(value['usd_estimate'])
            with self.assertRaises(ProviderError):LLMMetadataHTTP(True).list_models(provider,b'FAKE_DEMO_OPAQUE')
    def test_gemini_native_paging_capabilities_limits_and_no_key_in_url(self):
        model=self.model('gemini');incompatible={**model,'name':'models/embedding-fixture','supportedGenerationMethods':['embedContent']}
        token='opaque+/=:token';calls,stub=self.wire([WireResponse({'models':[model,incompatible],'nextPageToken':token}),WireResponse({'models':[self.model('gemini','second-model')]})])
        with stub:value=LLMMetadataHTTP(True).list_models('gemini',b'EXAMPLE_OPAQUE_"\\TOKEN')
        self.assertEqual([m['id'] for m in value['models']],['fixture-model','second-model']);self.assertEqual(value['filtered_models'],1)
        self.assertEqual(calls[0]['host'],'generativelanguage.googleapis.com');self.assertEqual(calls[0]['path'],'/v1beta/models?pageSize=100')
        self.assertEqual(calls[1]['path'],'/v1beta/models?pageSize=100&pageToken=opaque%2B%2F%3D%3Atoken')
        self.assertIn('x-goog-api-key',calls[0]['headers']);self.assertNotIn('key=',calls[1]['path'])
        self.assertEqual(value['models'][0]['max_input_tokens'],1234);self.assertFalse(value['verified_usd_rate'])
    def test_gemini_repeating_or_bad_cursor_is_blocked_without_third_call(self):
        for token in ['repeat','bad cursor']:
            calls,stub=self.wire([WireResponse({'models':[],'nextPageToken':token})]*2)
            with stub,self.assertRaises(ProviderError):LLMMetadataHTTP(True).list_models('gemini',b'EXAMPLE_OPAQUE_CREDENTIAL')
            self.assertLessEqual(len(calls),2)
    def test_openrouter_fixed_get_pagination_filtered_capabilities_and_no_price_claim(self):
        model=self.model('openrouter');image={**model,'id':'fixture/image','architecture':{'input_modalities':['text'],'output_modalities':['image']}}
        unsupported={**model,'id':'fixture/no-limit','supported_parameters':['temperature']}
        calls,stub=self.wire([WireResponse({'data':[model,image,unsupported],'links':{'next':'/api/v1/models?offset=100&limit=100'}}),
            WireResponse({'data':[self.model('openrouter','second-model')],'links':{'next':None}})])
        with stub:value=LLMMetadataHTTP(True).list_models('openrouter',b'EXAMPLE_OPAQUE_CREDENTIAL')
        self.assertEqual(calls[0]['host'],'openrouter.ai');self.assertEqual(calls[0]['path'],'/api/v1/models?offset=0&limit=100')
        self.assertTrue(calls[0]['headers']['Authorization'].startswith('Bearer '));self.assertEqual(value['filtered_models'],2)
        self.assertEqual(value['models'][0]['max_output_tokens'],567);self.assertIsNone(value['models'][0]['max_input_tokens'])
        self.assertEqual(value['models'][0]['context_window_tokens'],1234);self.assertIsNone(value['usd_estimate']);self.assertNotIn('pricing',value['models'][0])
    def test_openrouter_next_link_cannot_switch_host_path_limit_or_offset(self):
        links=['https://attacker.invalid/api/v1/models?offset=100&limit=100','/api/v1/keys?offset=100&limit=100',
               '/api/v1/models?offset=100&limit=999','/api/v1/models?offset=0&limit=100','/api/v1/models?offset=100&limit=100&key=anything']
        for link in links:
            calls,stub=self.wire([WireResponse({'data':[],'links':{'next':link}})])
            with stub,self.assertRaises(ProviderError):LLMMetadataHTTP(True).list_models('openrouter',b'EXAMPLE_OPAQUE_CREDENTIAL')
            self.assertEqual(len(calls),1)
    def test_five_page_budget_returns_truncated_instead_of_following_sixth_link(self):
        replies=[WireResponse({'data':[],'links':{'next':f'/api/v1/models?offset={100*(i+1)}&limit=100'}}) for i in range(5)]
        calls,stub=self.wire(replies)
        with stub:value=LLMMetadataHTTP(True).list_models('openrouter',b'EXAMPLE_OPAQUE_CREDENTIAL')
        self.assertEqual(len(calls),5);self.assertTrue(value['truncated'])
    def test_openrouter_auto_router_and_unknown_limits_are_not_faked(self):
        model=self.model('openrouter');auto={**model,'id':'openrouter/auto'}
        for value in (None,True,-1,'999'):
            item={**model,'top_provider':{'max_completion_tokens':value}}
            calls,stub=self.wire([WireResponse({'data':[auto,item]})])
            with stub:result=LLMMetadataHTTP(True).list_models('openrouter',b'EXAMPLE_OPAQUE_CREDENTIAL')
            self.assertEqual(result['filtered_models'],1);self.assertIsNone(result['models'][0]['max_output_tokens'])
    def test_both_new_metadata_auth_rate_redirect_errors_close_once_without_body_echo(self):
        for provider in ['gemini','openrouter']:
            for status in [401,429,302]:
                calls,stub=self.wire([WireResponse({'not':'retained'},status=status)])
                with stub,self.assertRaisesRegex(ProviderError,'HTTP_'+str(status)):LLMMetadataHTTP(True).list_models(provider,b'EXAMPLE_OPAQUE_CREDENTIAL')
                self.assertEqual(len(calls),1);self.assertTrue(calls[0]['closed'])
    def test_decoded_quoted_key_in_new_provider_metadata_fails_closed(self):
        key=b'EXAMPLE_OPAQUE_"\\TOKEN'
        for provider,field in [('gemini','models'),('openrouter','data')]:
            item=self.model(provider);item['displayName' if provider=='gemini' else 'name']=key.decode()
            calls,stub=self.wire([WireResponse({field:[item]})])
            with stub,self.assertRaisesRegex(ProviderError,'ECHO_BLOCKED'):LLMMetadataHTTP(True).list_models(provider,key)
            self.assertTrue(calls[0]['closed'])
    def test_no_implicit_network_from_build_header_or_disabled_discovery(self):
        with patch('storymotion.llm_api.http.client.HTTPSConnection',side_effect=AssertionError('no implicit network')):
            for provider in ['gemini','openrouter']:
                ADAPTERS[provider].build(SYNTHETIC_MODEL_IDS[provider],'Original',200);request_headers(provider,b'x+/.=:')
                with self.assertRaisesRegex(ProviderError,'DISABLED'):LLMMetadataHTTP().list_models(provider,b'x')


if __name__=='__main__':unittest.main()
