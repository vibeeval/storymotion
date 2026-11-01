from unittest.mock import patch
import test_local_audio_http
from storymotion.raster_revision import MAX_RASTER_BODY
class RasterHttp(test_local_audio_http.LocalAudioHttp):
 def test_only_exact_raster_route_accepts_large_body(self):
  with patch.object(self.d.raster,'import_local',return_value={'synthetic':True}) as importer:
   self.assertEqual(self.call('/api/jobs/'+'c'*24+'/raster-import',130000)[0],200)
   self.assertEqual(self.call('/api/jobs/'+'c'*24+'/raster-import/extra',130000)[0],400)
   self.assertEqual(self.call('/api/jobs/'+'c'*24+'/raster-import',MAX_RASTER_BODY)[0],400)
   self.assertEqual(self.call('/api/jobs/'+'c'*24+'/raster-import',100,origin='https://attacker.invalid')[0],403)
   self.assertEqual(importer.call_count,1)
