"""Explicit same-origin bounded file upload, never a server path or URL import."""
import base64,binascii,hashlib,re,tempfile
from pathlib import Path
from .security import WorkflowError

MAX_AUDIO=12*1024*1024
MAX_IMPORT_BODY=17*1024*1024
FIELDS={'audio_base64','container','expected_audio_sha256','alignment','approved_by','rights_note','rights_confirmed','scene_word_spans','viseme_required'}

def import_local(d,job,data):
 if not isinstance(data,dict) or set(data)!=FIELDS:raise WorkflowError('Exact local audio upload fields required; server paths/URLs are not accepted')
 d.assert_runtime_current();row,brief=d.audio.base(job)
 metadata={k:v for k,v in data.items() if k!='audio_base64'}
 try:d.clean(metadata)
 except (ValueError,TypeError):raise WorkflowError('Local audio metadata must be finite bounded JSON') from None
 if data['rights_confirmed'] is not True or data['viseme_required'] is not False:raise WorkflowError('Explicit local audio rights required; fresh viseme unavailable')
 for key,maximum in [('approved_by',200),('rights_note',1000)]:
  if not isinstance(data[key],str) or not 1<=len(data[key].strip())<=maximum:raise WorkflowError('Local audio approval notes required')
 if data['container'] not in ('mp3','wav','m4a') or not isinstance(data['expected_audio_sha256'],str) or not re.fullmatch('[a-f0-9]{64}',data['expected_audio_sha256']):raise WorkflowError('Bounded audio container and exact SHA256 required')
 encoded=data['audio_base64']
 if not isinstance(encoded,str) or not 4<=len(encoded)<=4*((MAX_AUDIO+2)//3):raise WorkflowError('Local audio upload exceeds12MiB or is empty')
 try:audio=base64.b64decode(encoded,validate=True)
 except (ValueError,binascii.Error):raise WorkflowError('Local audio upload is not strict base64') from None
 if not 100<=len(audio)<=MAX_AUDIO or hashlib.sha256(audio).hexdigest()!=data['expected_audio_sha256']:raise WorkflowError('Uploaded audio differs from selected file SHA256')
 # Bytes are private workspace temporary input; always removed, including all failures.
 # import_approved creates an immutable child only after container/decode/timing validation.
 with tempfile.TemporaryDirectory(prefix='local-audio-',dir=d.workspace) as temporary:
  source=Path(temporary)/('selected.'+data['container']);source.write_bytes(audio)
  return d.audio.import_approved(job,source,data['alignment'],expected_audio_sha256=data['expected_audio_sha256'],
   approved_by=data['approved_by'],rights_note=data['rights_note'],rights_confirmed=True,
   scene_word_spans=data['scene_word_spans'],viseme_required=False)
