from pack_fixture_case import PackFixtureCase
"""Exact inner-character repro. Synthetic silence; all media operations mocked."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from storymotion.dashboard import Dashboard
from storymotion.security import WorkflowError,file_hash
from storymotion.local_state import private_directory,copy_private
from storymotion.elevenlabs import validate_alignment
from storymotion.audio_retime import measured_words
from audio_fixture import alignment,source_job,no_media


class AlignmentImportBoundaryTests(PackFixtureCase):
    def test_hidden_inner_end_beyond_duration_rejects_without_child_or_writes(self):
        import shutil
        from storymotion.engine import ROOT
        with tempfile.TemporaryDirectory() as root:
            d=Dashboard(root)
            try:
                parent=source_job(d);script=d.job(parent)['payload']['input']['content']
                source=d.workspace/'imports/synthetic-20s.wav';private_directory(source.parent);copy_private(ROOT/'fixtures/audio-retime/synthetic-20s.wav',source)
                self.assertEqual(source.parent.stat().st_mode&0o777,0o700);self.assertEqual(source.stat().st_mode&0o777,0o600)
                a=alignment(script);a['character_end_times_seconds'][0]=20.25
                before={str(p.relative_to(root)):file_hash(p) for p in Path(root).rglob('*') if p.is_file()}
                error=None;result=None
                try:
                    with no_media():result=d.audio.import_approved(parent,source,a,expected_audio_sha256=file_hash(source),
                        approved_by='Synthetic regression operator',rights_note='Original silence only',rights_confirmed=True)
                except WorkflowError as ex:error=str(ex)
                after={str(p.relative_to(root)):file_hash(p) for p in Path(root).rglob('*') if p.is_file()}
                facts={'child_created':bool(result),'files_added':sorted(set(after)-set(before)),
                    'hidden_inner_end':20.25,'measured_duration':20,'error':error}
                if result:
                    facts['recorded_first_word_end']=result['job']['payload']['template']['template']['video']['audio_timing']['words'][0]['end']
                    d.audio.guard(result['child_job']);facts['old_guard_passed']=True
                self.assertIsNotNone(error,json.dumps(facts,ensure_ascii=False))
                self.assertNotIn('LOCAL_STATE_PERMISSIONS',error)
                self.assertIsNone(result);self.assertEqual(len(d.jobs()),1);self.assertEqual(before,after)
                with d.connection() as db:
                    self.assertEqual(db.execute('SELECT count(*) FROM dashboard_audio_revisions').fetchone()[0],0)
                    self.assertEqual(db.execute('SELECT count(*) FROM dashboard_audio_heads').fetchone()[0],0)
            finally:d.clear_keys()


class CharacterAlignmentContractTests(PackFixtureCase):
    def test_all_edges_are_finite_ordered_and_inside_exact_measured_duration(self):
        original=alignment('ab cd',20)
        for field in ['character_start_times_seconds','character_end_times_seconds']:
            for index in range(len(original['characters'])):
                for bad in [float('nan'),float('inf'),-0.001,20.25,20.000000001,True,'1']:
                    with self.subTest(field=field,index=index,bad=str(bad)):
                        a=copy.deepcopy(original);a[field][index]=bad
                        with self.assertRaises(WorkflowError):validate_alignment(a,20)
    def test_inner_end_reversal_is_rejected_even_when_starts_are_monotonic(self):
        a={'characters':list('abc'),'character_start_times_seconds':[0,.1,.2],'character_end_times_seconds':[.9,.3,1]}
        with self.assertRaises(WorkflowError):validate_alignment(a,1)
    def test_shared_overlapping_character_spans_are_not_clipped_or_reordered(self):
        a={'characters':list('İç.'),'character_start_times_seconds':[0,0,.2],'character_end_times_seconds':[.2,.3,.3]}
        before=copy.deepcopy(a);self.assertEqual(validate_alignment(a,.3),before)
        self.assertEqual(measured_words('İç.',a,1),[{'index':0,'text':'İç.','start':0,'end':.3}])
        self.assertEqual(a,before)
    def test_zero_duration_space_and_punctuation_and_exact_boundary_are_supported(self):
        a={'characters':list('İ. '),'character_start_times_seconds':[0,.2,.2],'character_end_times_seconds':[.2,.2,.2]}
        self.assertEqual(validate_alignment(a,.2),a)
        self.assertEqual(measured_words('İ. ',a,1)[0]['end'],.2)
    def test_cross_word_overlap_is_rejected_by_word_timeline_contract(self):
        a={'characters':list('a b'),'character_start_times_seconds':[0,.1,.2],'character_end_times_seconds':[.3,.3,.4]}
        self.assertEqual(validate_alignment(a,1),a)
        with self.assertRaisesRegex(WorkflowError,'overlap'):measured_words('a b',a,1)
    def test_invalid_measured_duration_is_not_an_alignment_tolerance(self):
        for duration in [0,-1,float('nan'),float('inf'),True,'20']:
            with self.subTest(duration=str(duration)),self.assertRaises(WorkflowError):validate_alignment(alignment('a'),duration)
