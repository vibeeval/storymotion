from pack_fixture_case import PackFixtureCase
"""Registry + genuine HTTP handler code over memory streams, with no OS sockets.

Actual bind/connect acceptance is BLOCKED by the reported environment denial.
This suite never binds or connects a socket and never calls a real vendor.
"""
import copy
import http.client
import io
import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from storymotion.dashboard import Dashboard,Handler
from storymotion.llm_service import LLMService
from storymotion.provider_catalog import (CapabilityRegistry,AdapterRegistration,Endpoint,
    build_registry,load_catalog,public_capabilities,LOCAL_PROOF)
from storymotion.providers import ADAPTERS,ProviderError
from storymotion.security import WorkflowError,canonical

PROVIDERS=('openai','anthropic','gemini','openrouter')
ACCOUNTS=('sample-flow','sample-reflection','sample-mechanism','sample-series')
KEY_A='FAKE_CATALOG_SESSION_A_123456'
KEY_B='FAKE_CATALOG_SESSION_B_987654'


class MemoryConnection:
    def __init__(self,request):self.input=io.BytesIO(request);self.output=bytearray()
    def makefile(self,*_):return self.input
    def sendall(self,data):self.output.extend(data)


def issued_cookie(server):
    """Issue a real test session, preserving the production auth checks."""
    if not hasattr(server.dashboard,'session_auth'):
        from storymotion.local_session import LocalSession
        with patch('storymotion.local_session.secrets.token_urlsafe',side_effect=['FAKE_'+'B'*38,'FAKE_'+'S'*38]):
            server.dashboard.session_auth=LocalSession()
    session=server.dashboard.session_auth
    if not session._issued:
        cookie=session.bootstrap(session._bootstrap_token,server.server_address[1])
        if cookie is None:raise AssertionError('Test session bootstrap failed')
    return session.cookie_name(server.server_address[1])+'='+session._session_token


def session_headers(server,write=False):
    headers=http.client.HTTPMessage();expected='127.0.0.1:'+str(server.server_address[1])
    headers['Host']=expected;headers['Cookie']=issued_cookie(server)
    if write:
        headers['Origin']='http://'+expected;headers['X-Storymotion-Local']='1'
    return headers


def authenticated_handler(connection,address,server):
    """Old API contracts now run inside a genuine issued test session cookie."""
    request=connection.input.getvalue()
    head,body=request.split(b'\r\n\r\n',1)
    head+=b'\r\nCookie: '+issued_cookie(server).encode()
    connection.input=io.BytesIO(head+b'\r\n\r\n'+body)
    return Handler(connection,address,server)


class CatalogIntegrationTests(PackFixtureCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='catalog-contract-');self.root=Path(self.tmp.name)
        self.d=Dashboard(self.root/'http',llm_mode='demo')
        self.server=SimpleNamespace(server_address=('127.0.0.1',4396),dashboard=self.d)
        self.services=[];self.responses=[]
    def tearDown(self):
        self.d.clear_keys()
        for service in self.services:service.close()
        self.tmp.cleanup()
    def call(self,path,body=None,expected=200,origin='http://127.0.0.1:4396',host='127.0.0.1:4396',local='1'):
        raw=b'' if body is None else canonical(body).encode()
        lines=[('GET' if body is None else 'POST')+' '+path+' HTTP/1.0','Host: '+host]
        if body is not None:lines+=['Origin: '+origin,'X-Storymotion-Local: '+local,'Content-Type: application/json','Content-Length: '+str(len(raw))]
        connection=MemoryConnection(('\r\n'.join(lines)+'\r\n\r\n').encode()+raw)
        # Execute the real parser/route/header/body code; no socket is created.
        authenticated_handler(connection,('127.0.0.1',12345),self.server)
        response=bytes(connection.output);self.responses.append(response)
        headers,payload=response.split(b'\r\n\r\n',1)
        status=int(headers.split(b'\r\n')[0].split()[1]);self.assertEqual(status,expected,response)
        self.assertIn(b'Cache-Control: no-store',headers)
        for key in (KEY_A,KEY_B):self.assertNotIn(key.encode(),response)
        return json.loads(payload)
    def context(self,account):return {'account':account,'title':'Katalog sözleşme provası','brief':'Sessiz golden sahne sözleşmesini denetle.','caption':''}
    def preview(self,provider,account='sample-mechanism',key=KEY_A):
        connection=self.call('/api/llm/connect',{'provider':provider,'value':key})
        ref=connection['connection'];model=connection['metadata']['models'][0]['id']
        proposal=self.call('/api/llm/preview',{'connection':ref,'context':self.context(account),'model':model,'max_output_tokens':2000})
        return ref,model,proposal
    def approve(self,ref,request):return self.call('/api/llm/approve',{'connection':ref,'request':request,'maximum_output_tokens':2000,'ack_unknown_cost':True,'rights_confirmed':True,'budget':None})
    def wait(self,request):
        with self.d.llm.lock:worker=self.d.llm.threads.get(request)
        if worker:worker.join(3)
        self.assertNotIn(request,self.d.llm.threads)
        return self.call('/api/llm/state',{'request':request})
    def test_catalog_exposes_actual_host_registry_config_and_runtime_fingerprint(self):
        value=self.call('/api/catalog');rows=value['capabilities']
        registered={r['provider'] for r in rows if r['capability']=='text' and r['adapter_registered'] and r['selectable']}
        self.assertEqual(registered,set(PROVIDERS));self.assertEqual(registered,set(value['llm']['providers']))
        self.assertEqual(value['runtime_execution_fingerprint'],self.d.runtime_execution);self.assertTrue(value['source_current'])
        self.assertTrue(all(r['dispatch_enabled'] is False and r['live_verified'] is False for r in rows))
        self.d.runtime_execution='previous-source';changed=self.call('/api/catalog')
        self.assertFalse(changed['source_current']);self.assertEqual(changed['runtime_execution_fingerprint'],'previous-source')
    def test_local_source_status_never_claims_doctor_or_runtime_verification(self):
        rows=self.call('/api/catalog')['capabilities']
        self.assertEqual(LOCAL_PROOF,'implemented_local_runtime_unverified')
        for row in rows:
            if row['execution']=='local':self.assertEqual(row['status'],LOCAL_PROOF);self.assertFalse(row['live_verified']);self.assertFalse(row['dispatch_enabled'])
        js=(Path(__file__).resolve().parents[1]/'dashboard/app.js').read_text()
        self.assertIn(LOCAL_PROOF,js);self.assertNotIn('implemented_local_verified',js)
    def test_planned_catalog_and_forged_fields_never_authorize_dispatch(self):
        rows=self.call('/api/catalog')['capabilities'];planned=[r for r in rows if r['status']=='planned']
        self.assertTrue(planned)
        for row in planned:
            self.assertFalse(row['adapter_registered']);self.assertFalse(row['selectable']);self.assertFalse(row['dispatch_enabled']);self.assertIsNone(row['ui_target'])
        for provider in ('runway','luma','bfl','ideogram'):
            self.call('/api/llm/connect',{'provider':provider,'value':KEY_A},400)
        self.call('/api/llm/connect',{'provider':'openai','value':KEY_A,'capability':'image_generation'},400)
        self.call('/api/llm/execute',{'connection':'f'*32,'request':'a'*32,'dispatch_enabled':True},400)
        self.assertFalse(self.d.llm.transport.calls);self.assertFalse(self.d.llm.broker.status())
    def test_all_four_accounts_and_native_providers_use_handler_contract(self):
        for provider in PROVIDERS:
            for account in ACCOUNTS:
                with self.subTest(provider=provider,account=account):
                    ref,model,preview=self.preview(provider,account);self.assertEqual(preview['provider'],provider);self.assertEqual(preview['context']['account'],account)
                    self.assertEqual(preview['dispatch_count'],0);self.assertIsNone(preview['usd_estimate'])
                    self.approve(ref,preview['request']);self.call('/api/llm/execute',{'connection':ref,'request':preview['request']})
                    result=self.wait(preview['request']);self.assertEqual(result['status'],'completed');self.assertEqual(result['dispatch_count'],1)
                    self.assertEqual(result['artifact']['account'],account);self.assertFalse(result['artifact']['publication_ready'])
                    self.call('/api/llm/disconnect',{'connection':ref})
        self.assertEqual(len(self.d.llm.transport.calls),16)
        for path in self.root.rglob('*'):
            if path.is_file():
                for key in (KEY_A,KEY_B):self.assertNotIn(key.encode(),path.read_bytes())
    def test_foreign_origin_and_host_fail_before_any_connection_or_dispatch(self):
        self.call('/api/catalog',expected=403,host='attacker.test')
        for origin,local in [('https://attacker.test','1'),('http://127.0.0.1:4396','0')]:
            self.call('/api/llm/connect',{'provider':'openai','value':KEY_A},403,origin=origin,local=local)
        self.assertFalse(self.d.llm.connections);self.assertFalse(self.d.llm.transport.calls)
    def test_four_provider_handler_rebind_cannot_reuse_another_key_approval(self):
        for provider in PROVIDERS:
            ref,model,a=self.preview(provider);request=a['request'];self.approve(ref,request)
            b,_,rebound=self.preview(provider,key=KEY_B)
            self.assertEqual(rebound['request'],request);self.assertIsNone(rebound['approval'])
            self.call('/api/llm/disconnect',{'connection':ref})
            self.call('/api/llm/execute',{'connection':b,'request':request},400)
            self.assertEqual(self.d.llm.get(request)['dispatch_count'],0)
            self.approve(b,request);self.call('/api/llm/execute',{'connection':b,'request':request})
            self.assertEqual(self.wait(request)['status'],'completed');self.call('/api/llm/disconnect',{'connection':b})
        self.assertEqual(len(self.d.llm.transport.calls),4)
    def test_registry_intersection_is_live_actual_code_not_descriptive_json(self):
        registry=build_registry({k:v for k,v in ADAPTERS.items() if k=='anthropic'},local_renderers=())
        service=LLMService(self.root/'narrow',mode='demo',registry=registry);self.services.append(service)
        self.assertEqual(service.config()['providers'],['anthropic'])
        with self.assertRaisesRegex(ProviderError,'UNSUPPORTED'):service.connect('openai',KEY_A)
        with patch.dict('storymotion.llm_service.ADAPTERS',{},clear=True):self.assertEqual(service.config()['providers'],[])
        with self.assertRaisesRegex(ProviderError,'REGISTRY'):LLMService(self.root/'json',mode='demo',registry={'providers':['openai']})
        future=SimpleNamespace(provider='future_text',capability='text',build=lambda *a:None,parse=lambda *a:None)
        registry.register(AdapterRegistration('future_text','text','future_text:text',(Endpoint('POST','https://api.future-text.example','/v1/text'),)))
        with patch.dict('storymotion.llm_service.ADAPTERS',{'future_text':future}):self.assertIn('future_text',service.config()['providers'])
        self.assertNotIn('future_text',service.config()['providers']);self.assertFalse(service.transport.calls)
    def test_exact_registry_endpoint_is_enforced_again_at_wire_boundary(self):
        ref,_,preview=self.preview('openai');request=preview['request'];self.approve(ref,request)
        original=self.d.llm._endpoint;calls=[]
        def endpoint(*args,**kwargs):
            calls.append(args)
            if len(calls)==3:raise ProviderError('REGISTERED_TEXT_ENDPOINT_REQUIRED')
            return original(*args,**kwargs)
        with patch.object(self.d.llm,'_endpoint',side_effect=endpoint):
            self.d.llm.execute(ref,request,False)
        result=self.d.llm.get(request)
        self.assertEqual(len(calls),3);self.assertEqual(result['status'],'blocked_before_dispatch')
        self.assertEqual(result['dispatch_count'],0);self.assertIsNone(result['approval']);self.assertIsNone(result['approved_until'])
        self.assertFalse(self.d.llm.transport.calls)
        with self.assertRaises(ProviderError):self.d.llm.execute(ref,request,False)
    def test_tampered_native_post_endpoint_cannot_reach_claim_or_wire(self):
        ref,_,preview=self.preview('gemini');request=preview['request'];self.approve(ref,request)
        row=self.d.llm.row(request);payload=json.loads(row['payload']);payload['plan']['url']='https://api.openai.com/v1/responses'
        with self.d.llm.db() as db:db.execute('UPDATE llm_requests SET payload=? WHERE id=?',(canonical(payload),request))
        self.call('/api/llm/execute',{'connection':ref,'request':request},400)
        self.assertEqual(self.d.llm.get(request)['dispatch_count'],0);self.assertFalse(self.d.llm.transport.calls)
    def test_provider_capability_scope_is_checked_even_with_valid_session_reference(self):
        ref=self.call('/api/llm/connect',{'provider':'openai','value':KEY_A})['connection']
        self.d.llm.connections[ref]['capability_scope']='openai:image_generation'
        self.call('/api/llm/metadata',{'connection':ref},400)
        self.assertFalse(self.d.llm.transport.calls)


if __name__=='__main__':unittest.main()
