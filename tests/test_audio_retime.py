from pack_fixture_case import PackFixtureCase
import copy
import concurrent.futures
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from storymotion.audio_retime import retime,validate_timed_brief,measured_words
from storymotion.dashboard import Dashboard
from storymotion.engine import Engine,ROOT
from storymotion.security import WorkflowError,canonical,digest,file_hash,write_json
from storymotion.local_state import private_directory,copy_private
from audio_fixture import ACCOUNTS,alignment,source_job,imported,no_media


class AudioRevisionTests(PackFixtureCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.d=Dashboard(self.root,elevenlabs_mode='demo')
    def tearDown(self):self.d.clear_keys();self.tmp.cleanup()
    def test_four_profiles_create_immutable_word_anchored_child_not_paid_or_rendered(self):
        with no_media():
            for account in ACCOUNTS:
                parent=source_job(self.d,account);before=copy.deepcopy(self.d.job(parent)['payload'])
                result=imported(self.d,parent);child=result['child_job'];row=self.d.job(child);video=self.d.renders.video_input(row)
                self.assertNotEqual(parent,child);self.assertEqual(row['status'],'queued');self.assertFalse(result['render_started'])
                self.assertEqual(self.d.job(parent)['payload'],before);self.assertEqual(video['duration'],20)
                self.assertEqual(video['audio_timing']['source_audio_sha256'],video['audio']['sha256'])
                self.assertEqual(video['audio_timing']['human_listening'],'pending');self.assertFalse(result['publication_ready'])
                words=video['audio_timing']['words'];spans=video['audio_timing']['scene_word_spans']
                self.assertEqual([s['start'] for s in video['scenes']][1:],[words[s['start_word']]['start'] for s in spans[1:]])
                self.assertNotEqual(video['cues'],before['template']['template']['video']['cues'])
                self.assertFalse(self.d.eleven.client.calls)
                for engine in ('hyperframes','remotion'):self.assertEqual(self.d.renders.state(child,engine)['status'],'not_started')
    def test_same_audio_and_approval_is_idempotent_and_original_downstream_is_blocked(self):
        parent=source_job(self.d)
        with no_media():
            child=imported(self.d,parent)['child_job'];self.assertEqual(imported(self.d,parent)['child_job'],child)
            for operation in [lambda:self.d.prepare(parent),lambda:self.d.check(parent),lambda:self.d.export(parent),lambda:self.d.renders.validate(parent,'hyperframes')]:
                with self.assertRaisesRegex(WorkflowError,'FRESH_TIMING'):operation()
            self.assertEqual(len(self.d.jobs()),2)
    def test_both_engines_prepare_same_audio_cues_and_scene_times_without_render(self):
        with no_media():
            for account in ACCOUNTS:
                parent=source_job(self.d,account);child=imported(self.d,parent)['child_job'];self.d.prepare(child)
                row=self.d.job(child);video=self.d.renders.video_input(row)
                self.assertIn('audio-timing.json',row['manifest']);self.assertIn(video['audio']['file'],row['manifest'])
                for engine in ('hyperframes','remotion'):
                    path=self.d.output(child)/('render-input-'+engine+'.json');write_json(path,video)
                    e=Engine(self.root/'renders');ident=e.create(path,render_engine=engine)['job'];e.run(ident,'prepare')
                    out=e.directory(ident);html=(out/'index.html').read_text();timeline=json.loads((out/'timeline.json').read_text())
                    self.assertIn('<audio id="narration" class="clip"',html);self.assertIn('data-duration="20"',html)
                    self.assertEqual(file_hash(out/'assets/narration.wav'),video['audio']['sha256'])
                    self.assertEqual(timeline['cues'],video['cues']);self.assertEqual(timeline['scenes'],video['scenes'])
                    self.assertEqual(e.plan(path,engine)[1],e.payload(ident))
                    if engine=='remotion':
                        props=json.loads((out/'remotion-props.json').read_text());self.assertEqual(props['audio_file'],'narration.wav');self.assertEqual(props['brief']['audio_timing'],video['audio_timing'])
                    e.store.db.close()
    def test_missing_rights_bad_hash_bad_path_and_viseme_requirement_have_no_new_job(self):
        parent=source_job(self.d)
        with no_media():
            for options in [dict(rights_confirmed=False),dict(approved_by=''),dict(rights_note=''),dict(expected_audio_sha256='f'*64),dict(viseme_required=True)]:
                with self.subTest(options=options),self.assertRaises(WorkflowError):imported(self.d,parent,**options)
                self.assertEqual(len(self.d.jobs()),1)
                with self.d.connection() as db:self.assertEqual(db.execute('SELECT count(*) FROM dashboard_audio_heads').fetchone()[0],0)
    def test_imported_audio_bytes_or_manifest_changes_block_downstream(self):
        for name in ['audio/approved.wav','audio-timing.json','audio-binding.json']:
            with self.subTest(name=name),tempfile.TemporaryDirectory() as root,no_media():
                d=Dashboard(root);parent=source_job(d);child=imported(d,parent)['child_job'];(d.output(child)/name).write_bytes(b'changed')
                with self.assertRaises(WorkflowError):d.renders.validate(child,'remotion')
                with self.assertRaises(WorkflowError):d.export(child)
                d.clear_keys()
    def test_new_timing_revision_supersedes_old_without_copying_qa_or_onays(self):
        parent=source_job(self.d)
        with no_media():
            first=imported(self.d,parent)['child_job']
            second=imported(self.d,parent,rights_note='New explicitly reviewed local use note')['child_job']
            self.assertNotEqual(first,second)
            with self.assertRaisesRegex(WorkflowError,'superseded'):self.d.audio.guard(first)
            with self.assertRaisesRegex(WorkflowError,'superseded'):imported(self.d,parent)
            self.d.audio.guard(second)
            with self.d.connection() as db:
                self.assertEqual(db.execute('SELECT count(*) FROM dashboard_reviews WHERE job=?',(second,)).fetchone()[0],0)
                self.assertEqual(db.execute('SELECT count(*) FROM dashboard_budgets WHERE job=?',(second,)).fetchone()[0],0)
    def test_word_alignment_errors_and_too_short_speech_stop_before_revision(self):
        v=json.loads((ROOT/'tests/fixtures/examples/golden/sample-reflection.json').read_text());a=alignment(v['script'])
        for mutation in ['spelling','nan','overlap','duration','short']:
            b=copy.deepcopy(a);duration=20
            if mutation=='spelling':b['characters'][0]='X'
            if mutation=='nan':b['character_start_times_seconds'][0]=float('nan')
            if mutation=='overlap':b['character_start_times_seconds'][-1]=0
            if mutation=='duration':duration=10
            if mutation=='short':duration=4;b=alignment(v['script'],4)
            with self.subTest(mutation=mutation),self.assertRaises(WorkflowError):retime(v,b,duration,'f'*64)
    def test_explicit_word_spans_required_for_ambiguous_source(self):
        v=json.loads((ROOT/'tests/fixtures/examples/golden/sample-mechanism.json').read_text());a=alignment(v['script'])
        v['cues']=[dict(start=0,end=12,text=v['script'])]
        with self.assertRaisesRegex(WorkflowError,'ambiguous'):retime(v,a,20,'f'*64)
        spans=[dict(scene_id=s['id'],start_word=x,end_word=y) for s,x,y in zip(v['scenes'],[0,5,9],[5,9,len(v['script'].split())])]
        self.assertEqual(retime(v,a,20,'f'*64,spans)['audio_timing']['scene_word_spans'],spans)
    def test_turkish_spelling_repeated_words_and_padding_are_preserved(self):
        script='İı Şş Ğğ Çç Öö Üü aynı aynı.';words=measured_words(script,alignment(script),20)
        self.assertEqual([w['text'] for w in words],script.split());self.assertNotEqual(words[-2]['start'],words[-1]['start'])
        v=json.loads((ROOT/'tests/fixtures/examples/golden/sample-mechanism.json').read_text());value=retime(v,alignment(v['script'],19.91),19.91,'f'*64)
        self.assertGreaterEqual(value['duration'],19.91);self.assertLess(value['audio_timing']['tail_padding_seconds'],1/30)
    def test_measured_duration_and_timing_tamper_cannot_plan(self):
        parent=source_job(self.d)
        with no_media():
            child=imported(self.d,parent)['child_job'];v=self.d.renders.video_input(self.d.job(child));path=self.d.output(child)/'test.json'
            bad=copy.deepcopy(v);bad['cues'][0]['start']+=.1;write_json(path,bad)
            with self.assertRaises(WorkflowError):Engine(self.root/'renders').plan(path)
            write_json(path,v)
            with patch('storymotion.engine.probe',return_value={'duration':19,'streams':[{'codec_type':'audio'}]}):
                with self.assertRaises(WorkflowError):Engine(self.root/'renders').plan(path)
    def test_source_only_export_contains_new_audio_and_timing_not_old_approval(self):
        parent=source_job(self.d)
        with no_media():
            child=imported(self.d,parent)['child_job'];self.d.prepare(child);self.d.export(child)
            with zipfile.ZipFile(self.d.output(child)/'package.zip') as z:
                self.assertIn('audio/approved.wav',z.namelist());self.assertIn('audio-timing.json',z.namelist());self.assertIn('audio-binding.json',z.namelist())
                self.assertEqual(json.loads(z.read('audio-binding.json'))['parent_job'],parent)
                self.assertFalse(any(n.endswith('approval.json') or 'voice-jobs' in n for n in z.namelist()))
    def test_external_path_and_multichar_alignment_are_rejected(self):
        parent=source_job(self.d);script=self.d.job(parent)['payload']['input']['content']
        with no_media(),self.assertRaisesRegex(WorkflowError,'boundary'):
            self.d.audio.import_approved(parent,ROOT/'fixtures/audio-retime/synthetic-20s.wav',alignment(script),
                expected_audio_sha256=file_hash(ROOT/'fixtures/audio-retime/synthetic-20s.wav'),approved_by='Test',rights_note='Original test',rights_confirmed=True)
        a=alignment('aynı aynı');a['characters']=['ay']+a['characters'][2:];a['character_start_times_seconds']=a['character_start_times_seconds'][1:];a['character_end_times_seconds']=a['character_end_times_seconds'][1:]
        with self.assertRaisesRegex(WorkflowError,'one-codepoint'):measured_words('aynı aynı',a,20)
        self.assertEqual(len(self.d.jobs()),1)
    def test_parent_change_during_validation_has_no_new_job_or_audio_head(self):
        parent=source_job(self.d)
        def changed(*args,**kwargs):
            p=self.d.job(parent)['payload'];p['input']['content']+=' Changed during validation.'
            with self.d.connection() as db:db.execute('UPDATE dashboard_jobs SET payload=? WHERE id=?',(canonical(p),parent))
            return b''
        with no_media(),patch('storymotion.engine.checked_process',side_effect=changed),self.assertRaisesRegex(WorkflowError,'changed during audio binding'):
            imported(self.d,parent)
        self.assertEqual(len(self.d.jobs()),1)
        with self.d.connection() as db:self.assertEqual(db.execute('SELECT count(*) FROM dashboard_audio_heads').fetchone()[0],0)
    def test_concurrent_same_import_creates_one_child(self):
        parent=source_job(self.d)
        import shutil
        p=self.d.workspace/'imports/synthetic-20s.wav';private_directory(p.parent);copy_private(ROOT/'fixtures/audio-retime/synthetic-20s.wav',p)
        self.assertEqual(p.parent.stat().st_mode&0o777,0o700);self.assertEqual(p.stat().st_mode&0o777,0o600)
        with no_media(),concurrent.futures.ThreadPoolExecutor(2) as pool:
            results=list(pool.map(lambda _:imported(self.d,parent)['child_job'],range(2)))
        self.assertEqual(results[0],results[1]);self.assertEqual(len(self.d.jobs()),2)
    def test_model_output_stays_silent_only_despite_host_audio_support(self):
        from storymotion.creative import validate_proposal
        parent=source_job(self.d)
        with no_media():
            child=imported(self.d,parent)['child_job'];v=self.d.renders.video_input(self.d.job(child))
            for name in ['appearance','production_notes','brand_identity']:v.pop(name,None)
            with self.assertRaises(WorkflowError):validate_proposal('sample-mechanism',v)
    def test_video_stream_in_import_is_rejected_without_media_dispatch(self):
        parent=source_job(self.d)
        with patch('storymotion.engine.probe',return_value={'duration':20,'streams':[{'codec_type':'audio'},{'codec_type':'video'}]}),patch('storymotion.engine.checked_process') as dispatch:
            with self.assertRaisesRegex(WorkflowError,'Audio-only'):imported(self.d,parent)
            dispatch.assert_not_called()
        self.assertEqual(len(self.d.jobs()),1)


if __name__=='__main__':unittest.main()
