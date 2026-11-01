from pack_fixture_case import PackFixtureCase
import json
import tempfile
import unittest
from pathlib import Path
from storymotion.llm_service import LLMService,DemoScriptTransport
from storymotion.providers import Response,ProviderError
from storymotion.dashboard import Dashboard
from storymotion.security import canonical

KEY='FAKE_QUOTED_"_BACKSLASH_\\_123456'


class OpaqueCredentialRegression(PackFixtureCase):
    def test_second_json_decode_after_broker_clear_cannot_persist_quoted_key(self):
        class EscapedProposal(DemoScriptTransport):
            def exchange(self,plan,key,permit,job):
                response=super().exchange(plan,key,permit,job)
                body=json.loads(response.body);proposal=json.loads(body['output'][0]['content'][0]['text'])
                proposal['title']='Sentetik '+KEY
                body['output'][0]['content'][0]['text']=canonical(proposal)
                service.broker.clear()
                return Response(200,'application/json',canonical(body).encode())
        with tempfile.TemporaryDirectory() as td:
            transport=EscapedProposal();service=LLMService(td,mode='demo',transport=transport)
            try:
                c=service.connect('openai',KEY)
                p=service.preview(c['connection'],{'account':'sample-flow','title':'Yerel test','brief':'Quote guard','caption':''},2000,model=c['metadata']['models'][0]['id'])
                service.approve(c['connection'],p['request'],2000,True,True)
                r=service.execute(c['connection'],p['request'],False)
                self.assertEqual(r['status'],'uncertain');self.assertEqual(r['error_code'],'CREDENTIAL_ECHO_BLOCKED')
                self.assertEqual(len(transport.calls),1);self.assertIsNone(r['artifact'])
                for f in Path(td).rglob('*'):
                    if f.is_file():
                        for token in [KEY.encode(),canonical(KEY).encode(),canonical(canonical(KEY)).encode()]:
                            self.assertNotIn(token,f.read_bytes())
            finally:service.close()

    def test_quoted_credential_cannot_enter_customer_brand_field(self):
        with tempfile.TemporaryDirectory() as td:
            d=Dashboard(td,llm_mode='demo')
            try:
                d.llm.connect('openai',KEY)
                with self.assertRaises(ProviderError):d.enqueue({'account':'sample-flow','format':'video-script','title':'Yerel test',
                    'brief':'Örnek','content':'Örnek metin','caption':'Yerel caption','provider':'local','model':'manual','task':'text',
                    'template_revision':0,'brand_identity':{'name':KEY}})
                self.assertEqual(d.jobs(),[])
            finally:d.clear_keys()
