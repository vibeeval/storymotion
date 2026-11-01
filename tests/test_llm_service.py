from pack_fixture_case import PackFixtureCase
"""Synthetic session contracts; no actual credentials, HTTP or paid dispatch."""
import concurrent.futures
import copy
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from storymotion.llm_service import LLMService,DemoScriptTransport,golden_fixture,writing_budget
from storymotion.llm_api import LLMMetadataDemo,SYNTHETIC_MODEL_IDS
from storymotion.providers import ProviderError,Response
from storymotion.security import canonical,digest,write_json

LLM_PROVIDERS=('openai','anthropic','gemini','openrouter')
KEY='FAKE_OPAQUE_LLM_CONTRACT_123456789'
KEY_B='FAKE_OPAQUE_OTHER_SESSION_987654321'
CONTEXT={'account':'sample-mechanism','title':'Sentetik yazım provası','brief':'Aynı mandalın hareket sırasını açıkla.','caption':''}


class ChangedTransport(DemoScriptTransport):
    def __init__(self,change=None,error=None,after=None):
        super().__init__(error=error);self.change=change;self.after=after
    def exchange(self,plan,key,permit,job):
        response=super().exchange(plan,key,permit,job)
        if self.change:response=self.change(response,plan,key)
        if self.after:self.after()
        return response


class HeldTransport(DemoScriptTransport):
    def __init__(self):
        super().__init__();self.started=threading.Event();self.release=threading.Event();self.key_was_expected=False
    def exchange(self,plan,key,permit,job):
        response=super().exchange(plan,key,permit,job)
        self.key_was_expected=key==KEY.encode();self.started.set()
        if not self.release.wait(3):raise ProviderError('TRANSPORT_OUTCOME_UNCERTAIN')
        return response


class ChangedMetadata(LLMMetadataDemo):
    def __init__(self,change=None,error=None):self.change=change;self.error=error;self.calls=0
    def list_models(self,provider,key):
        self.calls+=1
        if self.error:raise ProviderError(self.error)
        value=super().list_models(provider,key)
        return self.change(value,key) if self.change else value


def response_with_text(response,provider,text):
    value=json.loads(response.body)
    if provider=='openai':value['output'][0]['content'][0]['text']=text
    elif provider=='anthropic':value['content'][0]['text']=text
    elif provider=='gemini':value['candidates'][0]['content']['parts'][0]['text']=text
    elif provider=='openrouter':value['choices'][0]['message']['content']=text
    else:raise AssertionError('Unsupported synthetic response protocol')
    return Response(200,'application/json',canonical(value).encode())


class LLMSessionTests(PackFixtureCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='llm-contract-');self.root=Path(self.tmp.name)
        # Concurrent agents are changing sources in this development checkpoint.
        # Contract-change behavior has its own explicit test below.
        self.source=patch('storymotion.llm_service.current_execution',return_value='owned-synthetic-source-contract');self.source.start()
        self.services=[];self.transport=DemoScriptTransport();self.s=self.service('main',transport=self.transport)
        self.ref=self.s.connect('openai',KEY)['connection']
    def tearDown(self):
        for service in self.services:service.close()
        self.source.stop();self.tmp.cleanup()
    def service(self,name,**kwargs):
        result=LLMService(self.root/name,mode='demo',**kwargs);self.services.append(result);return result
    def preview(self,service=None,ref=None,context=None,provider='openai',tokens=2000):
        return (service or self.s).preview(ref or self.ref,context or CONTEXT,tokens,model=SYNTHETIC_MODEL_IDS[provider])
    def approve(self,request,service=None,ref=None):
        return (service or self.s).approve(ref or self.ref,request,2000,True,True)
    def complete(self,service=None,ref=None,context=None,provider='openai'):
        service=service or self.s;ref=ref or self.ref
        request=self.preview(service,ref,context,provider)['request'];self.approve(request,service,ref)
        return service.execute(ref,request,False)
    def assertNoKey(self,*values):
        for key in (KEY,KEY_B):
            for value in values:self.assertNotIn(key,json.dumps(value,ensure_ascii=False,default=str))
            for file in self.root.rglob('*'):
                if file.is_file():self.assertNotIn(key.encode(),file.read_bytes(),str(file))
    def wait_worker(self,service,request):
        for _ in range(80):
            with service.lock:worker=service.threads.get(request)
            if not worker:return service.get(request)
            worker.join(.05)
        self.fail('Owned mock worker exceeded its bounded test wait')
    def test_default_off_blocks_intake_and_has_no_network(self):
        off=LLMService(self.root/'off');self.services.append(off)
        with self.assertRaisesRegex(ProviderError,'DISABLED'):off.connect('openai',KEY)
        self.assertFalse(off.config()['network_enabled']);self.assertFalse(off.broker.status())
    def test_invalid_expiry_values_rejected(self):
        for value in (True,0,-1,901,float('nan'),float('inf')):
            with self.assertRaises(ProviderError):LLMService(self.root/'invalid',ttl=value)
        for value in (True,0,-1,121,float('nan'),float('inf')):
            with self.assertRaises(ProviderError):LLMService(self.root/'invalid',approval_ttl=value)
    def test_provider_allowlist_and_separate_synthetic_demo_policy(self):
        for provider,key in [('unsupported-provider',KEY),('openai','sk-'+'ant-'+'x'*25),('openai','sk-'+'proj-'+'x'*25)]:
            with self.assertRaises(ProviderError) as error:self.s.connect(provider,key)
            self.assertNotIn(key,str(error.exception))
        connection=self.s.connect('anthropic','FAKE_OPENAI_CONTRACT_CREDENTIAL')
        self.assertEqual(connection['metadata']['provider'],'anthropic')
        self.assertFalse(self.transport.calls)
    def test_explicit_provider_selection_never_infers_routing_from_key_prefix(self):
        for provider in LLM_PROVIDERS:
            result=self.s.connect(provider,'FAKE_OPENAI_CONTRACT_CREDENTIAL')
            self.assertEqual(result['provider'],provider);self.assertEqual(result['metadata']['provider'],provider)
        self.assertFalse(self.transport.calls)
    def test_connect_reads_only_metadata_and_requires_selected_model(self):
        self.assertFalse(self.transport.calls)
        with self.assertRaisesRegex(ProviderError,'MODEL_NOT'):self.s.preview(self.ref,CONTEXT)
        with self.assertRaisesRegex(ProviderError,'MODEL_NOT'):self.s.preview(self.ref,CONTEXT,model='invented-real-model')
        result=self.preview();self.assertIsNone(result['usd_estimate']);self.assertFalse(result['billing_cap_guaranteed'])
        self.assertEqual(result['maximum_dispatches'],1);self.assertIn('not arbitrary',self.s.config()['demo_behavior'])
    def test_context_only_four_accounts_bounded_no_markup_execution(self):
        for context in ({**CONTEXT,'account':'youtube'},{**CONTEXT,'title':'x'*66},{**CONTEXT,'brief':KEY},{**CONTEXT,'caption':False},{**CONTEXT,'script':'hidden'}):
            with self.assertRaises(ProviderError):self.preview(context=context)
        self.assertFalse(self.transport.calls);self.assertNoKey()
    def test_provider_output_maximum_and_token_type_are_checked(self):
        self.s.connections[self.ref]['metadata']['models'][0]['max_output_tokens']=100
        with self.assertRaisesRegex(ProviderError,'LIMIT'):self.preview()
        for tokens in (True,0,8001):
            with self.assertRaises(ProviderError):self.preview(tokens=tokens)
    def test_refreshed_metadata_revocation_or_lower_token_limit_blocks_approval_and_wire(self):
        request=self.preview()['request'];self.approve(request)
        models=copy.deepcopy(self.s.connections[self.ref]['metadata']['models'])
        self.s.connections[self.ref]['metadata']['models']=[]
        with self.assertRaisesRegex(ProviderError,'MODEL_NOT'):self.approve(request)
        with self.assertRaisesRegex(ProviderError,'MODEL_NOT'):self.s.execute(self.ref,request,False)
        self.s.connections[self.ref]['metadata']['models']=models
        self.s.connections[self.ref]['metadata']['models'][0]['max_output_tokens']=100
        with self.assertRaisesRegex(ProviderError,'LIMIT'):self.approve(request)
        with self.assertRaisesRegex(ProviderError,'LIMIT'):self.s.execute(self.ref,request,False)
        self.assertFalse(self.transport.calls)
    def test_two_explicit_consents_and_exact_token_cap_required(self):
        request=self.preview()['request']
        for maximum,ack,rights in ((1999,True,True),(True,True,True),(2000,False,True),(2000,True,False)):
            with self.assertRaises(ProviderError):self.s.approve(self.ref,request,maximum,ack,rights)
        with self.assertRaises(ProviderError):self.s.execute(self.ref,request,False)
        self.assertFalse(self.transport.calls)
    def test_unknown_live_budget_requires_finite_positive_current_quote(self):
        for budget in (None,{}, {'max_usd':1,'estimate_usd':0,'quote_source':'current user quote','verified_by_user':True},
            {'max_usd':0,'estimate_usd':0,'quote_source':'current user quote','verified_by_user':True},
            {'max_usd':1,'estimate_usd':2,'quote_source':'current user quote','verified_by_user':True},
            {'max_usd':float('nan'),'estimate_usd':1,'quote_source':'current user quote','verified_by_user':True},
            {'max_usd':float('inf'),'estimate_usd':1,'quote_source':'current user quote','verified_by_user':True},
            {'max_usd':1,'estimate_usd':1,'quote_source':'current user quote','verified_by_user':False}):
            with self.assertRaises(ProviderError):writing_budget(budget,False)
        budget=writing_budget({'max_usd':2,'estimate_usd':1,'quote_source':'User reviewed current official quote','verified_by_user':True},False)
        self.assertEqual(budget['estimate_microusd'],1000000);self.assertFalse(budget['api_verified_usd_rate'])
    def test_expired_approval_and_stale_metadata_block_wire(self):
        request=self.preview()['request'];self.approve(request)
        with self.s.db() as db:db.execute('UPDATE llm_requests SET approved_until=0 WHERE id=?',(request,))
        with self.assertRaisesRegex(ProviderError,'FRESH'):self.s.execute(self.ref,request,False)
        self.s.connections[self.ref]['metadata_until']=0
        with self.assertRaisesRegex(ProviderError,'REFRESH'):self.approve(request)
        self.assertFalse(self.transport.calls)
    def test_session_rebind_requires_own_consent_for_all_four_providers(self):
        for provider in LLM_PROVIDERS:
            for same_key in (False,True):
                with self.subTest(provider=provider,same_key=same_key):
                    transport=DemoScriptTransport();s=self.service(provider+str(same_key),transport=transport)
                    a=s.connect(provider,KEY)['connection'];context={**CONTEXT,'title':provider+str(same_key)}
                    request=self.preview(s,a,context,provider)['request'];self.approve(request,s,a)
                    b=s.connect(provider,KEY if same_key else KEY_B)['connection']
                    rebound=self.preview(s,b,context,provider)
                    self.assertEqual(rebound['request'],request);self.assertEqual(rebound['status'],'preview');self.assertIsNone(rebound['approval'])
                    s.disconnect(a)
                    with self.assertRaisesRegex(ProviderError,'FRESH'):s.execute(b,request,False)
                    self.assertEqual(s.get(request)['dispatch_count'],0);self.assertFalse(transport.calls)
                    self.approve(request,s,b);result=s.execute(b,request,False)
                    self.assertEqual(result['status'],'completed');self.assertEqual(result['dispatch_count'],1)
                    self.assertEqual(len(transport.calls),1)
        self.assertNoKey()
    def test_same_connection_preview_preserves_own_approval(self):
        request=self.preview()['request'];self.approve(request)
        again=self.preview();self.assertEqual(again['status'],'approved');self.assertIsNotNone(again['approval'])
        self.assertEqual(self.s.execute(self.ref,request,False)['status'],'completed')
    def test_new_service_owner_cannot_inherit_old_session_approval(self):
        request=self.preview()['request'];self.approve(request)
        second=LLMService(self.s.root,mode='demo');self.services.append(second)
        ref=second.connect('openai',KEY)['connection'];self.preview(second,ref)
        self.assertIsNone(second.get(request)['approval'])
        with self.assertRaises(ProviderError):second.execute(ref,request,False)
        self.s.disconnect(self.ref)
        self.approve(request,second,ref);self.assertEqual(second.execute(ref,request,False)['status'],'completed')
    def test_stale_approval_json_binding_is_checked_again(self):
        request=self.preview()['request'];self.approve(request)
        row=self.s.row(request);approval=json.loads(row['approval']);approval['connection_scope']='old-session'
        with self.s.db() as db:db.execute('UPDATE llm_requests SET approval=? WHERE id=?',(canonical(approval),request))
        with self.assertRaisesRegex(ProviderError,'SCOPE'):self.s.execute(self.ref,request,False)
        self.assertFalse(self.transport.calls)
    def test_scopes_checked_at_wire_after_claim(self):
        request=self.preview()['request'];self.approve(request)
        original=self.s._work
        def invalidate_then_work(ref,identity):
            with self.s.db() as db:db.execute("UPDATE llm_requests SET binding_scope='different' WHERE id=?",(identity,))
            original(ref,identity)
        with patch.object(self.s,'_work',side_effect=invalidate_then_work):result=self.s.execute(self.ref,request,False)
        self.assertEqual(result['dispatch_count'],0);self.assertEqual(result['status'],'blocked_before_dispatch');self.assertFalse(self.transport.calls)
    def test_concurrent_execute_dispatches_only_once(self):
        held=HeldTransport();s=self.service('concurrent',transport=held);ref=s.connect('openai',KEY)['connection']
        request=self.preview(s,ref)['request'];self.approve(request,s,ref)
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
                futures=[pool.submit(s.execute,ref,request,True) for _ in range(5)]
                results=[]
                for future in futures:
                    try:results.append(future.result())
                    except ProviderError:pass
            self.assertTrue(held.started.wait(1));self.assertEqual(len(held.calls),1);self.assertTrue(results)
        finally:held.release.set()
        self.assertEqual(self.wait_worker(s,request)['status'],'completed')
    def test_inflight_rebind_denied_and_cancel_keeps_uncertain_hold(self):
        held=HeldTransport();s=self.service('held',transport=held);ref=s.connect('openai',KEY)['connection']
        request=self.preview(s,ref)['request'];self.approve(request,s,ref);s.execute(ref,request)
        try:
            self.assertTrue(held.started.wait(1));other=s.connect('openai',KEY_B)['connection']
            with self.assertRaisesRegex(ProviderError,'LOCKED'):self.preview(s,other)
            self.assertEqual(s.cancel(request)['status'],'uncertain')
            second=self.preview(s,ref,{**CONTEXT,'title':'Jenerik başka iş'})['request'];self.approve(second,s,ref)
            with self.assertRaisesRegex(ProviderError,'HOLD'):s.execute(ref,second,False)
            self.assertEqual(len(held.calls),1)
        finally:held.release.set()
        result=self.wait_worker(s,request);self.assertEqual(result['status'],'received_after_cancel_review')
        with self.assertRaises(ProviderError):s.accept(request,lambda *_:'not-allowed')
    def test_disconnect_after_wire_retains_immutable_lease_and_no_new_charge(self):
        held=HeldTransport();s=self.service('disconnect',transport=held);ref=s.connect('openai',KEY)['connection']
        request=self.preview(s,ref)['request'];self.approve(request,s,ref);s.execute(ref,request)
        try:self.assertTrue(held.started.wait(1));s.disconnect(ref);self.assertFalse(s.broker.status())
        finally:held.release.set()
        result=self.wait_worker(s,request);self.assertEqual(result['status'],'received_after_cancel_review');self.assertEqual(len(held.calls),1)
        self.assertNoKey(result)
    def test_cancel_before_dispatch_never_calls_transport(self):
        request=self.preview()['request'];self.approve(request);self.assertEqual(self.s.cancel(request)['status'],'cancelled')
        with self.assertRaises(ProviderError):self.s.execute(self.ref,request,False)
        self.assertFalse(self.transport.calls)
    def test_uncertain_error_never_retries_and_blocks_another_request(self):
        for code in ('TRANSPORT_OUTCOME_UNCERTAIN','HTTP_503'):
            with self.subTest(code=code):
                transport=ChangedTransport(error=code);s=self.service(code,transport=transport);ref=s.connect('openai',KEY)['connection']
                result=self.complete(s,ref);self.assertEqual(result['status'],'uncertain');self.assertEqual(len(transport.calls),1)
                with self.assertRaises(ProviderError):s.execute(ref,result['request'],False)
                with self.assertRaises(ProviderError):self.preview(s,s.connect('openai',KEY_B)['connection'])
                request=self.preview(s,ref,{**CONTEXT,'title':'Niyet iki'})['request'];self.approve(request,s,ref)
                with self.assertRaisesRegex(ProviderError,'HOLD'):s.execute(ref,request,False)
    def test_known_auth_and_rate_errors_never_retry_and_auth_clears_key(self):
        for code in ('HTTP_401','HTTP_403','HTTP_429'):
            with self.subTest(code=code):
                transport=ChangedTransport(error=code);s=self.service(code,transport=transport);ref=s.connect('openai',KEY)['connection']
                result=self.complete(s,ref);self.assertEqual(result['status'],'failed_known_no_retry');self.assertEqual(len(transport.calls),1)
                with self.assertRaises(ProviderError):s.execute(ref,result['request'],False)
                if code!='HTTP_429':self.assertFalse(s.broker.status())
        self.assertNoKey()
    def test_completed_hash_reuse_survives_disconnect_and_restart(self):
        result=self.complete();request=result['request'];self.s.disconnect()
        second=LLMService(self.s.root,mode='demo');self.services.append(second)
        cached=second.execute('no-connection',request,False)
        self.assertEqual(cached['artifact'],result['artifact']);self.assertEqual(len(second.transport.calls),0)
        self.assertEqual(cached['dispatch_count'],1)
    def test_completed_corrupt_artifact_blocks_read_and_replay(self):
        result=self.complete();request=result['request'];(self.s.root/request/'proposal.json').write_text('{}')
        for operation in (lambda:self.s.get(request),lambda:self.s.download(request,'proposal.json'),lambda:self.s.execute(self.ref,request,False),lambda:self.s.accept(request,lambda *_:'should-not-create')):
            with self.assertRaisesRegex(ProviderError,'HASH'):operation()
        self.assertEqual(len(self.transport.calls),1)
    def test_restart_expired_dispatch_does_not_send_again(self):
        request=self.preview()['request'];self.approve(request)
        with self.s.db() as db:db.execute("UPDATE llm_requests SET status='dispatching',owner='old-owner',deadline=0,dispatch_count=1 WHERE id=?",(request,))
        second=LLMService(self.s.root,mode='demo');self.services.append(second)
        self.assertEqual(second.get(request)['status'],'uncertain')
        with self.assertRaises(ProviderError):second.execute(self.ref,request,False)
        self.assertFalse(second.transport.calls)
    def test_nested_escaped_key_is_blocked_after_broker_cleared_for_all_four_providers(self):
        for provider in LLM_PROVIDERS:
            with self.subTest(provider=provider):
                def change(response,plan,key):
                    proposal=golden_fixture(CONTEXT['account']);proposal['title']=key.decode()
                    text=canonical(proposal).replace(key.decode(),'\\u0046'+key.decode()[1:])
                    result=response_with_text(response,provider,text)
                    self.assertNotIn(key,result.body)
                    return result
                transport=ChangedTransport(change=change);s=self.service('nested-'+provider,transport=transport)
                transport.after=s.broker.clear;ref=s.connect(provider,KEY)['connection']
                result=self.complete(s,ref,provider=provider)
                self.assertEqual(result['status'],'uncertain');self.assertEqual(result['error_code'],'CREDENTIAL_ECHO_BLOCKED')
                self.assertIsNone(result['artifact']);self.assertFalse(list(s.root.rglob('proposal.json')))
                self.assertFalse(list(s.root.rglob('receipt.json')));self.assertEqual(len(transport.calls),1)
        self.assertNoKey()
    def test_provider_metadata_escaped_key_blocked_after_broker_clear(self):
        for provider in LLM_PROVIDERS:
            def change(response,plan,key):
                value=json.loads(response.body);value['responseId' if provider=='gemini' else 'id']=key.decode()
                raw=canonical(value).replace(key.decode(),'\\u0046'+key.decode()[1:]).encode()
                self.assertNotIn(key,raw);return Response(200,'application/json',raw)
            transport=ChangedTransport(change=change);s=self.service('metadata-'+provider,transport=transport)
            transport.after=s.broker.clear;ref=s.connect(provider,KEY)['connection']
            result=self.complete(s,ref,provider=provider)
            self.assertEqual(result['error_code'],'CREDENTIAL_ECHO_BLOCKED');self.assertIsNone(result['artifact'])
        self.assertNoKey()
    def test_error_code_cannot_persist_a_leased_key_after_clear(self):
        transport=ChangedTransport(error=KEY);s=self.service('error',transport=transport);ref=s.connect('openai',KEY)['connection']
        result=self.complete(s,ref);self.assertEqual(result['error_code'],'CREDENTIAL_ECHO_BLOCKED');self.assertNoKey(result)
    def test_metadata_errors_do_not_echo_and_auth_invalidates_connection(self):
        for code in ('HTTP_401','HTTP_403','HTTP_429','METADATA_TIMEOUT','METADATA_TIMEOUT_OR_NETWORK_ERROR'):
            client=ChangedMetadata();s=self.service('read-'+code,metadata_client=client);ref=s.connect('openai',KEY)['connection'];client.error=code
            with self.assertRaisesRegex(ProviderError,code):s.metadata(ref)
            self.assertFalse(s.transport.calls)
            if code in ('HTTP_401','HTTP_403'):self.assertFalse(s.broker.status())
        self.assertNoKey()
    def test_metadata_decoded_secret_after_broker_expiry_is_rejected(self):
        client=ChangedMetadata();s=self.service('read-echo',metadata_client=client);ref=s.connect('openai',KEY)['connection']
        def echo(value,key):s.broker.clear();value['models'][0]['name']=key.decode();return value
        client.change=echo
        with self.assertRaisesRegex(ProviderError,'CREDENTIAL_ECHO_BLOCKED'):s.metadata(ref)
        self.assertNoKey()
    def test_active_ttl_disconnects_without_poll(self):
        s=self.service('short',ttl=.04);s.connect('openai',KEY);threading.Event().wait(.14)
        self.assertFalse(s.connections);self.assertFalse(s.broker.status());self.assertFalse(s.timers)
    def test_malformed_duplicate_json_and_unsafe_proposals_are_not_accepted(self):
        variants=['not JSON','{"brand":"a","brand":"b"}','{"duration":NaN}']
        unsafe=golden_fixture(CONTEXT['account']);unsafe['scenes'][0]['information']='<script>alert(1)</script>';variants.append(canonical(unsafe))
        claims=golden_fixture(CONTEXT['account']);claims['claims']=[{'text':'Uydurulmuş iddia','source':'invented','scope':'all people'}];variants.append(canonical(claims))
        wrong=golden_fixture('sample-reflection');variants.append(canonical(wrong))
        for i,text in enumerate(variants):
            transport=ChangedTransport(change=lambda response,plan,key,text=text:response_with_text(response,'openai',text))
            s=self.service('invalid-'+str(i),transport=transport);ref=s.connect('openai',KEY)['connection'];result=self.complete(s,ref)
            self.assertEqual(result['status'],'received_invalid_review');self.assertIsNone(result['artifact']);self.assertEqual(len(transport.calls),1)
            with self.assertRaises(ProviderError):s.accept(result['request'],lambda *_:'not-created')
    def test_accept_exact_normalized_artifact_and_idempotent_history(self):
        result=self.complete();request=result['request'];calls=[]
        def create(proposal,receipt):
            calls.append((proposal,receipt));return 'llm-'+receipt['request']
        accepted=self.s.accept(request,create);again=self.s.accept(request,create)
        self.assertEqual(accepted['accepted_job'],again['accepted_job']);self.assertTrue(again['reused']);self.assertEqual(len(calls),1)
        self.assertEqual(digest(calls[0][0]),result['artifact']['proposal_sha256'])
        history=self.s.history(CONTEXT['account']);self.assertEqual(len(history),1)
        self.assertIn('script_sha256',history[0]);self.assertIn('visual_signature',history[0]);self.assertIn('proposal_sha256',history[0])
        self.assertEqual(self.preview()['request'],request);self.assertEqual(len(self.transport.calls),1)
        self.assertFalse(result['artifact']['publication_ready']);self.assertNoKey(result,accepted,history)
    def test_callback_crash_retry_reuses_deterministic_external_job(self):
        result=self.complete();created={};attempts=[]
        def crashsafe(proposal,receipt):
            identity='llm-'+receipt['request'];created.setdefault(identity,receipt['proposal_sha256']);attempts.append(identity)
            if len(attempts)==1:raise RuntimeError('simulated local commit gap')
            return identity
        with self.assertRaises(RuntimeError):self.s.accept(result['request'],crashsafe)
        self.assertFalse(self.s.get(result['request'])['accepted_job']);accepted=self.s.accept(result['request'],crashsafe)
        self.assertEqual(len(created),1);self.assertEqual(accepted['accepted_job'],attempts[0]);self.assertEqual(len(self.transport.calls),1)
    def test_changed_contract_blocks_dispatch_and_accept(self):
        request=self.preview()['request'];self.approve(request)
        with patch('storymotion.llm_service.current_execution',return_value='changed'):
            with self.assertRaisesRegex(ProviderError,'CONTRACT'):self.s.execute(self.ref,request,False)
        self.assertFalse(self.transport.calls)
        result=self.s.execute(self.ref,request,False)
        with patch('storymotion.llm_service.current_execution',return_value='changed'):
            with self.assertRaisesRegex(ProviderError,'CONTRACT'):self.s.accept(request,lambda *_:'not-created')
    def test_accepted_history_rejects_renamed_duplicate_in_new_intent(self):
        first=self.complete();self.s.accept(first['request'],lambda *_:'first-review-job')
        result=self.complete(context={**CONTEXT,'title':'Yeni başlıklı fakat aynı üretim'})
        self.assertEqual(result['status'],'received_invalid_review');self.assertEqual(len(self.transport.calls),2)
        self.assertIsNone(result['artifact']);self.assertEqual(len(self.s.history(CONTEXT['account'])),1)
    def test_accept_checks_new_history_even_for_already_completed_second_proposal(self):
        first=self.complete();second=self.complete(context={**CONTEXT,'title':'İkinci tamamlanmış taslak'})
        self.s.accept(first['request'],lambda *_:'first-job')
        with self.assertRaisesRegex(ProviderError,'HISTORY'):self.s.accept(second['request'],lambda *_:'duplicate-job')
        self.assertIsNone(self.s.get(second['request'])['accepted_job']);self.assertEqual(len(self.transport.calls),2)
    def test_pinned_prompt_is_not_replaced_by_model_or_database_change(self):
        request=self.preview()['request'];self.approve(request)
        row=self.s.row(request);payload=json.loads(row['payload']);payload['plan']['hash']='changed-hash'
        with self.s.db() as db:db.execute('UPDATE llm_requests SET payload=? WHERE id=?',(canonical(payload),request))
        with self.assertRaisesRegex(ProviderError,'SCOPE'):self.s.execute(self.ref,request,False)
        self.assertFalse(self.transport.calls)
    def test_cancelled_zero_wire_intent_requires_new_preview_and_own_approval(self):
        request=self.preview()['request'];self.approve(request);self.s.cancel(request)
        self.assertEqual(self.preview()['status'],'preview');self.assertIsNone(self.s.get(request)['approval'])
        with self.assertRaises(ProviderError):self.s.execute(self.ref,request,False)
        self.approve(request);self.assertEqual(self.s.execute(self.ref,request,False)['status'],'completed')
    def test_accept_callback_cannot_write_an_active_key_as_job_identifier(self):
        result=self.complete()
        with self.assertRaisesRegex(ProviderError,'SECRET'):self.s.accept(result['request'],lambda *_:KEY)
        self.assertIsNone(self.s.get(result['request'])['accepted_job']);self.assertNoKey()
    def test_four_native_protocols_have_the_same_canonical_proposal_hash(self):
        hashes=set()
        for provider in LLM_PROVIDERS:
            s=self.service('canonical-'+provider);ref=s.connect(provider,KEY)['connection']
            result=self.complete(s,ref,provider=provider)
            self.assertEqual(result['status'],'completed');hashes.add(result['artifact']['proposal_sha256'])
        self.assertEqual(len(hashes),1)
    def test_four_providers_preserve_unknown_limits_usage_and_prices(self):
        for provider in LLM_PROVIDERS:
            def no_usage(response,plan,key):
                value=json.loads(response.body);value.pop('usageMetadata' if provider=='gemini' else 'usage',None)
                return Response(200,'application/json',canonical(value).encode())
            transport=ChangedTransport(change=no_usage);s=self.service('unknown-'+provider,transport=transport)
            ref=s.connect(provider,KEY)['connection']
            model=s.connections[ref]['metadata']['models'][0]
            model['max_input_tokens']=None;model['max_output_tokens']=None
            preview=self.preview(s,ref,provider=provider)
            self.assertIsNone(preview['model_metadata']['max_input_tokens']);self.assertIsNone(preview['model_metadata']['max_output_tokens'])
            self.assertIsNone(preview['usd_estimate']);self.assertFalse(preview['verified_usd_rate']);self.assertFalse(preview['billing_cap_guaranteed'])
            self.approve(preview['request'],s,ref);result=s.execute(ref,preview['request'],False)
            self.assertEqual(result['status'],'completed');self.assertEqual(result['artifact']['usage'],{'reported':False})
            self.assertEqual(result['artifact']['cost_status'],'synthetic_no_charge')
    def test_four_providers_nonfinal_responses_remain_no_retry_holds(self):
        for provider in LLM_PROVIDERS:
            def nonfinal(response,plan,key):
                value=json.loads(response.body)
                if provider=='openai':value['status']='incomplete'
                elif provider=='anthropic':value['stop_reason']='max_tokens'
                elif provider=='gemini':value['candidates'][0]['finishReason']='MAX_TOKENS'
                else:value['choices'][0]['finish_reason']='length'
                return Response(200,'application/json',canonical(value).encode())
            transport=ChangedTransport(change=nonfinal);s=self.service('nonfinal-'+provider,transport=transport)
            ref=s.connect(provider,KEY)['connection'];result=self.complete(s,ref,provider=provider)
            self.assertEqual(result['status'],'uncertain');self.assertIsNone(result['artifact']);self.assertEqual(result['dispatch_count'],1)
            with self.assertRaises(ProviderError):s.execute(ref,result['request'],False)
            self.assertEqual(len(transport.calls),1)
    def test_four_providers_known_limits_and_uncertain_errors_never_resend(self):
        for provider in LLM_PROVIDERS:
            for code in ('HTTP_401','HTTP_429','HTTP_503','TRANSPORT_OUTCOME_UNCERTAIN'):
                transport=ChangedTransport(error=code);s=self.service('errors-'+provider+'-'+code,transport=transport)
                ref=s.connect(provider,KEY)['connection'];result=self.complete(s,ref,provider=provider)
                self.assertEqual(result['status'],'failed_known_no_retry' if code in ('HTTP_401','HTTP_429') else 'uncertain')
                self.assertEqual(result['dispatch_count'],1)
                with self.assertRaises(ProviderError):s.execute(ref,result['request'],False)
                self.assertEqual(len(transport.calls),1)
    def test_metadata_echo_after_clear_is_blocked_for_four_providers(self):
        for provider in LLM_PROVIDERS:
            client=ChangedMetadata();s=self.service('read-all-'+provider,metadata_client=client)
            ref=s.connect(provider,KEY)['connection']
            def echo(value,key):s.broker.clear();value['models'][0]['name']=key.decode();return value
            client.change=echo
            with self.assertRaisesRegex(ProviderError,'CREDENTIAL_ECHO_BLOCKED'):s.metadata(ref)
        self.assertNoKey()
    def test_provider_cannot_be_switched_between_scoped_preview_and_approval(self):
        for provider in LLM_PROVIDERS:
            s=self.service('switch-'+provider);ref=s.connect(provider,KEY)['connection']
            request=self.preview(s,ref,provider=provider)['request']
            other='anthropic' if provider!='anthropic' else 'openai'
            other_ref=s.connect(other,KEY)['connection']
            with self.assertRaises(ProviderError):self.approve(request,s,other_ref)
            with self.assertRaises(ProviderError):s.execute(other_ref,request,False)
            self.assertFalse(s.transport.calls)
    def test_four_providers_nested_quoted_key_after_expiry_never_persists(self):
        quoted='FAKE_LLM_SESSION_"QUOTED"_\\TOKEN'
        for provider in LLM_PROVIDERS:
            def echo(response,plan,key):
                proposal=golden_fixture(CONTEXT['account']);proposal['title']=key.decode()
                return response_with_text(response,provider,canonical(proposal))
            transport=ChangedTransport(change=echo);s=self.service('quoted-'+provider,transport=transport)
            transport.after=s.broker.clear;ref=s.connect(provider,quoted)['connection']
            result=self.complete(s,ref,provider=provider)
            self.assertEqual(result['status'],'uncertain');self.assertEqual(result['error_code'],'CREDENTIAL_ECHO_BLOCKED')
            self.assertIsNone(result['artifact']);self.assertFalse(list(s.root.rglob('proposal.json')))
            self.assertNotIn(quoted,canonical(result))
            for path in s.root.rglob('*'):
                if path.is_file():self.assertNotIn(quoted.encode(),path.read_bytes())
    def test_four_provider_concurrent_execute_keeps_one_dispatch(self):
        for provider in LLM_PROVIDERS:
            held=HeldTransport();s=self.service('concurrent-all-'+provider,transport=held)
            ref=s.connect(provider,KEY)['connection'];request=self.preview(s,ref,provider=provider)['request'];self.approve(request,s,ref)
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                    futures=[pool.submit(s.execute,ref,request,True) for _ in range(4)]
                    for future in futures:
                        try:future.result()
                        except ProviderError:pass
                self.assertTrue(held.started.wait(1));self.assertEqual(len(held.calls),1)
            finally:held.release.set()
            self.assertEqual(self.wait_worker(s,request)['status'],'completed')
    def test_gemini_missing_optional_response_id_remains_unknown(self):
        def without_id(response,plan,key):
            value=json.loads(response.body);value.pop('responseId',None)
            return Response(200,'application/json',canonical(value).encode())
        transport=ChangedTransport(change=without_id);s=self.service('gemini-no-id',transport=transport)
        ref=s.connect('gemini',KEY)['connection'];result=self.complete(s,ref,provider='gemini')
        self.assertEqual(result['status'],'completed');self.assertIsNone(result['artifact']['provider_id'])
        self.assertIsNone(json.loads(s.download(result['request'],'receipt.json'))['provider_id'])
    def test_download_allowlist_no_path_traversal(self):
        result=self.complete();self.assertTrue(json.loads(self.s.download(result['request'],'proposal.json'))['creative']['audit'])
        for name in ('../../llm-jobs.sqlite3','receipt.json/../proposal.json','unknown.json'):
            with self.assertRaises(ProviderError):self.s.download(result['request'],name)
    def test_real_golden_all_four_accounts_all_four_provider_envelopes(self):
        for account in ('sample-reflection','sample-flow','sample-mechanism','sample-series'):
            for provider in LLM_PROVIDERS:
                with self.subTest(account=account,provider=provider):
                    s=self.service(account+'-'+provider);ref=s.connect(provider,KEY)['connection']
                    result=self.complete(s,ref,{**CONTEXT,'account':account},provider)
                    self.assertEqual(result['status'],'completed');self.assertEqual(result['dispatch_count'],1)
                    proposal=json.loads(s.download(result['request'],'proposal.json'))
                    self.assertEqual(proposal['brand'],account);self.assertTrue(proposal['creative']['audit'])
                    self.assertEqual(result['artifact']['human_review']['source_truth'],'pending')
                    self.assertFalse(result['artifact']['publication_ready']);self.assertIsNone(proposal['audio'])
        self.assertNoKey()


if __name__=='__main__':unittest.main()
