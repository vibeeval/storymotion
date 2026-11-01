from test_catalog_integration import authenticated_handler
from pack_fixture_case import PackFixtureCase
"""Synthetic HTTP bytes; full hash/source verifier is never bypassed."""
import threading,unittest
from types import SimpleNamespace
from unittest.mock import Mock
from storymotion.http_media import media_slice
from storymotion.dashboard import Handler
from storymotion.security import WorkflowError
from test_catalog_integration import MemoryConnection

RAW=bytes(range(256))*8
class SingleRangeTests(PackFixtureCase):
 def test_full_closed_open_suffix_clamped_and_all_bytes(self):
  cases=[(None,200,0,2048,None),('bytes=10-19',206,10,20,'bytes 10-19/2048'),('bytes=2040-',206,2040,2048,'bytes 2040-2047/2048'),('bytes=-10',206,2038,2048,'bytes 2038-2047/2048'),('bytes=2000-9999',206,2000,2048,'bytes 2000-2047/2048'),('bytes=-9999',206,0,2048,'bytes 0-2047/2048'),('BYTES=0-0',206,0,1,'bytes 0-0/2048')]
  for value,*expected in cases:
   with self.subTest(value=value):self.assertEqual(media_slice(RAW,value),tuple(expected))
 def test_invalid_multiple_unbounded_control_unsatisfiable_empty(self):
  for value in ['','bytes=-','bytes=-0','bytes=20-19','bytes=2048-','bytes=0-1,4-5','bytes=+1-2','bytes= 0-1','bytes=1e2-','bytes=0-1\r\nBad: yes','bytes='+('1'*200)+'-','items=0-1',12]:
   with self.subTest(value=value):self.assertEqual(media_slice(RAW,value),(416,0,0,'bytes */2048'))
  self.assertEqual(media_slice(b'','bytes=0-1'),(416,0,0,'bytes */0'))
class MediaHandlerTests(PackFixtureCase):
 def call(self,headers=(),name='render-mobile.mp4',error=None,host='127.0.0.1:43333'):
  download=Mock(return_value=RAW,side_effect=error);d=SimpleNamespace(renders=SimpleNamespace(download=download),revision_lock=threading.RLock())
  server=SimpleNamespace(server_address=('127.0.0.1',43333),dashboard=d)
  lines=['GET /render-files/'+'a'*24+'/remotion/'+name+' HTTP/1.0','Host: '+host]+[k+': '+v for k,v in headers]
  c=MemoryConnection(('\r\n'.join(lines)+'\r\n\r\n').encode());authenticated_handler(c,('127.0.0.1',1),server)
  head,body=bytes(c.output).split(b'\r\n\r\n',1);parts=head.decode().split('\r\n');fields=dict(line.split(': ',1) for line in parts[1:])
  return int(parts[0].split()[1]),fields,body,download
 def test_range_full_and_slice_match_original_verified_bytes(self):
  for headers,status,start,stop in [([],200,0,2048),([('Range','bytes=17-99')],206,17,100),([('Range','bytes=-7')],206,2041,2048)]:
   code,h,b,download=self.call(headers);self.assertEqual(code,status);self.assertEqual(b,RAW[start:stop]);self.assertEqual(int(h['Content-Length']),len(b));self.assertEqual(h['Accept-Ranges'],'bytes');self.assertEqual(h['Content-Type'],'video/mp4');self.assertEqual(h['Cache-Control'],'no-store');download.assert_called_once_with('a'*24,'remotion','render-mobile.mp4')
 def test_bad_duplicate_or_unsatisfiable_range_returns_no_media_bytes(self):
  for value in [[('Range','bytes=9999-')],[('Range','bytes=2-1')],[('Range','bytes=0-1'),('Range','bytes=2-3')]]:
   status,h,b,download=self.call(value);self.assertEqual(status,416);self.assertEqual(h['Content-Range'],'bytes */2048');self.assertEqual(b,b'');download.assert_called_once()
 def test_hash_revision_failure_precedes_any_range_success(self):
  status,h,b,download=self.call([('Range','bytes=0-0')],error=WorkflowError('Stale immutable job or hash'))
  self.assertEqual(status,400);self.assertEqual(h['Content-Type'],'application/json; charset=utf-8');self.assertNotIn('Content-Range',h);self.assertNotIn(RAW[:20],b);download.assert_called_once()
 def test_host_guard_does_not_read_and_nonmedia_range_does_not_slice(self):
  status,h,b,download=self.call([('Range','bytes=0-0')],host='attacker.invalid');self.assertEqual(status,403);download.assert_not_called()
  status,h,b,download=self.call([('Range','bytes=0-0')],name='delivery.zip');self.assertEqual(status,200);self.assertEqual(b,RAW);self.assertNotIn('Accept-Ranges',h);self.assertEqual(h['Content-Disposition'],'attachment')
 def test_if_range_without_emitted_validator_returns_full_current_representation(self):
  status,h,b,_=self.call([('Range','bytes=0-0'),('If-Range','"old-entity"')]);self.assertEqual(status,200);self.assertEqual(b,RAW);self.assertNotIn('Content-Range',h)
