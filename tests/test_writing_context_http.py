from test_catalog_integration import authenticated_handler
from pack_fixture_case import PackFixtureCase
"""Official HTTP handler over memory streams; no socket/provider transport."""
import json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from storymotion.dashboard import Dashboard,Handler
from storymotion.llm_service import LLMService
from storymotion.security import canonical,digest
from test_catalog_integration import MemoryConnection
from test_writing_context import SOURCE,SourceTransport,accepted_reference,KEY


class ContextHttpTests(PackFixtureCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        llm=LLMService(self.root/'writing',mode='demo',transport=SourceTransport());self.d=Dashboard(self.root,llm_mode='demo',llm_service=llm);self.server=SimpleNamespace(server_address=('127.0.0.1',43333),dashboard=self.d)
    def tearDown(self):self.d.clear_keys();self.tmp.cleanup()
    def call(self,path,body=None,expected=200,origin='http://127.0.0.1:43333',host='127.0.0.1:43333'):
        raw=canonical(body).encode() if body is not None else b'';headers=[('POST' if body is not None else 'GET')+' '+path+' HTTP/1.0','Host: '+host]
        if body is not None:headers+=['Origin: '+origin,'X-Storymotion-Local: 1','Content-Type: application/json','Content-Length: '+str(len(raw))]
        connection=MemoryConnection(('\r\n'.join(headers)+'\r\n\r\n').encode()+raw);authenticated_handler(connection,('127.0.0.1',1),self.server);response=bytes(connection.output);self.assertNotIn(KEY.encode(),response)
        head,payload=response.split(b'\r\n\r\n',1);self.assertEqual(int(head.split()[1]),expected,payload);return json.loads(payload)
    def source(self,account='sample-mechanism'):
        return self.call('/api/writing-context/save-sources',{'account':account,'expected_revision':None,'sources':SOURCE,'rights_confirmed':True})
    def test_host_origin_schema_rights_and_stale_source_guards_precede_persistence(self):
        body={'account':'sample-mechanism','expected_revision':None,'sources':SOURCE,'rights_confirmed':True}
        self.call('/api/writing-context/save-sources',body,403,origin='https://attacker.test')
        self.call('/api/writing-contexts/sample-mechanism',expected=403,host='attacker.test')
        self.call('/api/writing-context/save-sources',{**body,'rights_confirmed':False},400)
        self.call('/api/writing-context/save-sources',{**body,'extra':True},400)
        self.assertIsNone(self.call('/api/writing-contexts/sample-mechanism')['sources'])
        self.d.runtime_execution='old-code';self.call('/api/writing-context/save-sources',body,400);self.assertFalse(self.d.llm.transport.calls)
    def test_model_source_reference_reaches_actual_accepted_child_and_engine_prepare(self):
        from storymotion.engine import Engine
        from storymotion.security import write_json
        a=self.source();connection=self.call('/api/llm/connect',{'provider':'anthropic','value':KEY});ref=connection['connection']
        context={'account':'sample-mechanism','title':'Sentetik kaynak hattı','brief':'Özgün sentetik mandal çizimi.','caption':'','source_revision':a['sources']['revision']}
        preview=self.call('/api/llm/preview',{'connection':ref,'context':context,'model':connection['metadata']['models'][0]['id'],'max_output_tokens':2000});r=preview['request']
        self.call('/api/llm/approve',{'connection':ref,'request':r,'maximum_output_tokens':2000,'ack_unknown_cost':True,'rights_confirmed':True,'budget':None});self.call('/api/llm/execute',{'connection':ref,'request':r})
        with self.d.llm.lock:worker=self.d.llm.threads.get(r)
        if worker:worker.join(2)
        result=self.call('/api/llm/state',{'request':r});self.assertEqual(result['status'],'completed')
        accepted=self.call('/api/llm/accept',{'request':r,'brand_identity':{'name':'','handle':''}});child=self.d.job(accepted['accepted_job']);video=self.d.renders.video_input(child)
        self.assertEqual(video['production_context']['sources']['data'],SOURCE);self.assertEqual(child['payload']['generation']['writing_context_sha256'],video['production_context']['binding_sha256'])
        self.d.prepare(child['id']);p=self.root/'test-brief.json';write_json(p,video);engine=Engine(self.root/'engine');job=engine.create(p)['job']
        try:engine.run(job,'prepare');self.assertEqual(json.loads((engine.directory(job)/'writing-context.json').read_text())['binding'],video['production_context'])
        finally:engine.store.db.close()
    def test_canon_import_is_explicit_local_attestation_and_not_proposal_promotion(self):
        body={'account':'sample-series','expected_revision':None,'reference':accepted_reference(),'accepted_final_confirmed':False,'rights_confirmed':True}
        self.call('/api/writing-context/accept-reference',body,400);v=self.call('/api/writing-context/accept-reference',{**body,'accepted_final_confirmed':True})
        self.assertEqual(v['canon']['data']['origin'],'synthetic_reference_test');self.assertEqual(v['canon_authority'],'host_attested_reference_not_independent_final_QA')
        self.assertFalse(self.d.jobs());self.assertFalse(self.d.llm.transport.calls)


if __name__=='__main__':unittest.main()
