from pack_fixture_case import PackFixtureCase
"""Pure container/command tests. No decoder, network or external files executed."""
import json
import shutil
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from storymotion.audio_input import approved_audio_options
from storymotion.engine import ROOT,probe
from storymotion.security import WorkflowError,file_hash
from storymotion.local_state import private_directory,copy_private
from storymotion.dashboard import Dashboard
from audio_fixture import source_job,alignment,no_media


def box(kind,data):return struct.pack('>I',len(data)+8)+kind+data
def m4a(reference=b'\0\0\0\1',kind=b'url '):
    dref=box(b'dref',b'\0'*4+struct.pack('>I',1)+box(kind,reference))
    return box(b'ftyp',b'M4A '+b'\0'*4+b'isom')+box(b'moov',box(b'trak',box(b'mdia',box(b'minf',box(b'dinf',dref)))))+box(b'mdat',b'\0'*64)


class LocalAudioInputTests(PackFixtureCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def local(self,name,data):p=self.root/name;p.write_bytes(data);return p
    def test_original_wav_and_mp3_get_fixed_file_only_demuxers(self):
        for source,demuxer in [(ROOT/'fixtures/audio-retime/synthetic-20s.wav','wav'),(ROOT/'fixtures/synthetic-voice-contract.mp3','mp3')]:
            p=self.root/source.name;shutil.copyfile(source,p)
            self.assertEqual(approved_audio_options(p),['-protocol_whitelist','file','-f',demuxer])
    def test_playlist_disguised_as_each_extension_is_rejected_before_dispatch(self):
        for suffix in ['mp3','wav','m4a']:
            for data in [b'#EXTM3U\nhttps://not-called.invalid/audio.mp3\n',b'ffconcat version 1.0\nfile /not/opened\n']:
                p=self.local('disguised.'+suffix,data.ljust(150,b' '))
                with patch('storymotion.engine.checked_process') as dispatch:
                    with self.assertRaises(WorkflowError):probe(p,restricted_audio=True)
                    dispatch.assert_not_called()
    def test_id3_wrapped_fake_reaches_only_explicit_restricted_mp3_probe(self):
        data=(b'ID3'+b'\0'*16+b'#EXTM3U\nhttps://not-called.invalid/audio.mp3\n').ljust(150,b' ')
        p=self.local('id3-wrapped.mp3',data)
        self.assertEqual(approved_audio_options(p),['-protocol_whitelist','file','-f','mp3'])
        with patch('storymotion.engine.checked_process',side_effect=WorkflowError('MOCK_RESTRICTED_MP3_REJECTED')) as dispatch:
            with self.assertRaisesRegex(WorkflowError,'MOCK_RESTRICTED'):probe(p,restricted_audio=True)
        cmd=dispatch.call_args.args[0]
        self.assertEqual(cmd[cmd.index('-protocol_whitelist')+1],'file');self.assertEqual(cmd[cmd.index('-f')+1],'mp3')
        self.assertNotIn('https://not-called.invalid/audio.mp3',cmd)
    def test_self_contained_mov_disables_external_tracks_and_absolute_paths(self):
        p=self.local('local.m4a',m4a());self.assertEqual(approved_audio_options(p),['-protocol_whitelist','file','-f','mov','-enable_drefs','0','-use_absolute_path','0'])
    def test_remote_local_urn_and_reference_movie_are_rejected_statically(self):
        for kind,value in [(b'url ',b'\0'*4+b'https://not-called.invalid/a\0'),(b'url ',b'\0'*4+b'/not/opened\0'),(b'urn ',b'\0\0\0\1'),(b'url ',b'\0\0\0\1https://not-called.invalid/a\0')]:
            p=self.local('reference.m4a',m4a(value,kind))
            with self.subTest(kind=kind),patch('storymotion.engine.checked_process') as dispatch:
                with self.assertRaises(WorkflowError):probe(p,restricted_audio=True)
                dispatch.assert_not_called()
        p=self.local('reference.m4a',m4a()+box(b'rdrf',b'\0'*32))
        with self.assertRaises(WorkflowError):approved_audio_options(p)
    def test_truncated_container_sizes_are_not_guessed(self):
        wav=(ROOT/'fixtures/audio-retime/synthetic-20s.wav').read_bytes()
        for name,data in [('bad.wav',wav[:-1]),('bad.m4a',m4a()[:-1]),('bad.wav',b'RIFF'+b'\xff'*4+b'WAVE'+b'\0'*100)]:
            with self.subTest(name=name),self.assertRaises(WorkflowError):approved_audio_options(self.local(name,data))
    def test_probe_command_has_only_file_protocol_and_exact_demuxer(self):
        p=self.local('local.m4a',m4a());response={'format':{'duration':'20'},'streams':[{'codec_type':'audio'}]}
        with patch('storymotion.engine.checked_process',return_value=json.dumps(response).encode()) as run:
            self.assertEqual(probe(p,restricted_audio=True)['duration'],20)
            cmd=run.call_args.args[0];self.assertEqual(cmd[cmd.index('-protocol_whitelist')+1],'file');self.assertEqual(cmd[cmd.index('-f')+1],'mov')
            self.assertEqual(cmd[cmd.index('-enable_drefs')+1],'0');self.assertEqual(cmd[cmd.index('-use_absolute_path')+1],'0')
    def test_import_decode_command_is_fixed_without_running_decoder(self):
        d=Dashboard(self.root/'workspace');parent=source_job(d);source=d.workspace/'imports/fixture.wav';private_directory(source.parent);copy_private(ROOT/'fixtures/audio-retime/synthetic-20s.wav',source)
        self.assertEqual(source.parent.stat().st_mode&0o777,0o700);self.assertEqual(source.stat().st_mode&0o777,0o600)
        script=d.job(parent)['payload']['input']['content']
        try:
            with patch('storymotion.engine.probe',return_value={'duration':20,'streams':[{'codec_type':'audio'}]}),patch('storymotion.engine.checked_process',return_value=b'') as run:
                d.audio.import_approved(parent,source,alignment(script),expected_audio_sha256=file_hash(source),approved_by='Synthetic test',rights_note='Original silence',rights_confirmed=True)
                cmd=run.call_args.args[0];self.assertEqual(cmd[cmd.index('-protocol_whitelist')+1],'file');self.assertEqual(cmd[cmd.index('-f')+1],'wav')
                self.assertLess(cmd.index('-protocol_whitelist'),cmd.index('-i'));self.assertEqual(cmd[cmd.index('-map')+1],'0:a:0')
        finally:d.clear_keys()
