"""Import exact word anchors without inventing character/phoneme timestamps.

Supplied metadata is an operator provenance claim, not acoustic verification.
"""
import copy,re
from .security import WorkflowError,finite

FIELDS={'kind','schema_version','script_sha256','audio_sha256','method','source_alignment_sha256','words','limitations'}

def word_alignment(script,value,duration,audio_sha):
 from .audio_retime import script_sha
 if not isinstance(value,dict) or set(value)!=FIELDS or value['kind']!='word_timing' or type(value['schema_version']) is not int or value['schema_version']!=1:
  raise WorkflowError('Exact word_timing schema required')
 if value['script_sha256']!=script_sha(script) or not audio_sha or value['audio_sha256']!=audio_sha:
  raise WorkflowError('Word timing must bind exact script and approved audio SHA256')
 if not isinstance(value['source_alignment_sha256'],str) or not re.fullmatch('[a-f0-9]{64}',value['source_alignment_sha256']):raise WorkflowError('Source alignment SHA256 required')
 for key in ('method','limitations'):
  if not isinstance(value[key],str) or not 1<=len(value[key].strip())<=1000 or '\x00' in value[key]:raise WorkflowError('Bounded alignment method and limitations required')
 words=value['words'];tokens=script.split();last=0
 if not isinstance(words,list) or not 1<=len(words)<=10000 or len(words)!=len(tokens):raise WorkflowError('One word anchor per exact whitespace token required')
 for index,(word,text) in enumerate(zip(words,tokens)):
  if not isinstance(word,dict) or set(word)!={'index','text','start','end'} or type(word['index']) is not int or word['index']!=index or word['text']!=text:
   raise WorkflowError('Word anchors must preserve exact spelling, punctuation and order')
  start=finite(word['start'],'word start',0,duration);end=finite(word['end'],'word end',0,duration)
  if start<last or end<=start:raise WorkflowError('Word anchors overlap, are empty or escape measured audio')
  last=end
 provenance={k:value[k] for k in ('kind','method','source_alignment_sha256','limitations')}
 provenance['character_timing']='not_available; no interpolation performed'
 provenance['human_listening']='pending'
 return copy.deepcopy(words),provenance

def validate_provenance(value):
 if not isinstance(value,dict) or set(value)!={'kind','method','source_alignment_sha256','limitations','character_timing','human_listening'} or value['kind']!='word_timing' or value['character_timing']!='not_available; no interpolation performed' or value['human_listening']!='pending':
  raise WorkflowError('Invalid word alignment provenance')
 if not isinstance(value['source_alignment_sha256'],str) or not re.fullmatch('[a-f0-9]{64}',value['source_alignment_sha256']):raise WorkflowError('Invalid source alignment SHA256')
 for key in ('method','limitations'):
  if not isinstance(value[key],str) or not 1<=len(value[key].strip())<=1000 or '\x00' in value[key]:raise WorkflowError('Invalid alignment provenance text')
