from test_catalog_integration import authenticated_handler
from pack_fixture_case import PackFixtureCase
import json,tempfile,unittest
from types import SimpleNamespace
from unittest.mock import patch
from storymotion.dashboard import Dashboard,Handler
from storymotion.security import canonical
from storymotion.local_audio import MAX_IMPORT_BODY
from test_catalog_integration import MemoryConnection

class LocalAudioHttp(PackFixtureCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.d=Dashboard(self.tmp.name);self.server=SimpleNamespace(server_address=('127.0.0.1',43333),dashboard=self.d)
 def tearDown(self):self.d.clear_keys();self.tmp.cleanup()
 def call(self,path,size,origin='http://127.0.0.1:43333'):
  body=canonical({'padding':'a'*size}).encode();head=['POST '+path+' HTTP/1.0','Host: 127.0.0.1:43333','Origin: '+origin,'X-Storymotion-Local: 1','Content-Type: application/json','Content-Length: '+str(len(body))];c=MemoryConnection(('\r\n'.join(head)+'\r\n\r\n').encode()+body);authenticated_handler(c,('127.0.0.1',1),self.server);h,p=bytes(c.output).split(b'\r\n\r\n',1);return int(h.split()[1]),json.loads(p)
 def test_only_exact_job_audio_import_route_accepts_larger_bounded_body(self):
  with patch('storymotion.local_audio.import_local',return_value={'synthetic':True}) as importer:
   status,data=self.call('/api/jobs/'+'c'*24+'/audio-import',130000);self.assertEqual(status,200);self.assertTrue(data['synthetic']);self.assertEqual(importer.call_count,1)
   status,data=self.call('/api/template',130000);self.assertEqual(status,400);self.assertEqual(importer.call_count,1)
   status,data=self.call('/api/jobs/'+'c'*24+'/audio-import/extra',130000);self.assertEqual(status,400);self.assertEqual(importer.call_count,1)
 def test_cross_origin_and_above_limit_never_reach_importer(self):
  with patch('storymotion.local_audio.import_local') as importer:
   self.assertEqual(self.call('/api/jobs/'+'c'*24+'/audio-import',10,origin='https://attacker.invalid')[0],403)
   self.assertEqual(self.call('/api/jobs/'+'c'*24+'/audio-import',MAX_IMPORT_BODY)[0],400);importer.assert_not_called()
