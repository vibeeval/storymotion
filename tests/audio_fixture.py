"""Explicit silence and invented alignment: contract plumbing, not speech QA."""
import copy
import json
import shutil
from pathlib import Path
from unittest.mock import patch
from contextlib import contextmanager
from storymotion.engine import ROOT
from storymotion.security import file_hash
from storymotion.local_state import private_directory, copy_private

ACCOUNTS=('sample-reflection','sample-flow','sample-mechanism','sample-series')

def alignment(script,duration=20):
    step=(duration-.2)/len(script)
    return {'characters':list(script),'character_start_times_seconds':[.1+i*step for i in range(len(script))],
        'character_end_times_seconds':[.1+(i+1)*step for i in range(len(script))]}

def source_job(d,account='sample-mechanism'):
    v=d.template(account,'account-video')['template']['video']
    return d.enqueue(dict(account=account,format='account-video',title=v['title'],brief=v['brief'],content=v['script'],caption=v['caption'],
        provider='local',model='manual',task='text',template_revision=0))['id']

def imported(d,parent,**overrides):
    source=d.workspace/'imports/synthetic-20s.wav';private_directory(source.parent)
    if not source.exists():copy_private(ROOT/'fixtures/audio-retime/synthetic-20s.wav',source)
    script=d.job(parent)['payload']['input']['content']
    options=dict(expected_audio_sha256=file_hash(source),approved_by='Synthetic contract operator',
        rights_note='Original synthetic silence; not speech or human acceptance',rights_confirmed=True)
    options.update(overrides)
    return d.audio.import_approved(parent,source,alignment(script),**options)

@contextmanager
def no_media(duration=20):
    with patch('storymotion.engine.probe',return_value={'duration':duration,'streams':[{'codec_type':'audio'}]}),patch('storymotion.engine.checked_process',return_value=b''):
        yield
