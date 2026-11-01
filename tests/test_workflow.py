from pack_fixture_case import PackFixtureCase
import copy
import json
import multiprocessing
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch
from storymotion.engine import Engine, ROOT, STAGES, microusd
from storymotion.security import WorkflowError, file_hash, scan_bytes, within
from storymotion.store import Store
from neutral_identity_fixture import assert_no_source_identity, source_identity_profiles


def other_lock(workspace, q):
    try:
        with Store(workspace).lock():q.put('unexpected-acquired')
    except WorkflowError:q.put('blocked')


class WorkflowTests(PackFixtureCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.fixture=json.loads((ROOT/'tests/fixtures/examples/sample-mechanism.json').read_text())
        self.path=self.root/'brief.json';self.save()
        self.e=Engine(self.root/'work')

    def tearDown(self):self.tmp.cleanup()
    def save(self):self.path.write_text(json.dumps(self.fixture,ensure_ascii=False))
    def create(self):return self.e.create(self.path)['job']
    def req(self,job=None,provider='mock',estimate='.01'):
        return self.e.request(job or self.create(),provider,'mock-v1','fake-voice',estimate,'fixture, not a current market price')['id']
    def approved(self):
        r=self.req();self.e.approve(r,'.02','Test fixture approval; mock only');return r

    def test_dry_run_has_no_workspace_side_effect(self):
        result=self.e.create(self.path,True)
        self.assertEqual(result['paid_calls'],0);self.assertFalse((self.root/'work').exists())

    def test_identical_input_reuses_job(self):
        j=self.create();self.assertEqual(j,self.create())
        self.assertEqual(self.e.store.db.execute('SELECT count(*) FROM jobs').fetchone()[0],1)

    def test_script_change_creates_new_job(self):
        j=self.create();self.fixture['script']='Yeni cümle. Ardından kapak kalkıyor.';self.fixture['cues'][0]['text']='Yeni cümle.';self.save()
        self.assertNotEqual(j,self.create())

    def test_vendor_change_changes_job(self):
        j=self.create()
        with patch('storymotion.engine.file_hash',return_value='changed'):
            self.assertNotEqual(j,self.e.plan(self.path)[0])

    def test_profile_change_changes_job(self):
        from storymotion.account_packs import render_profile
        j=self.create();changed=render_profile('sample-mechanism')
        changed['palette']['accent']='#D5692E'
        with patch('storymotion.engine.render_profile',return_value=changed):
            self.assertNotEqual(j,self.e.plan(self.path)[0])

    @source_identity_profiles()
    def test_prepare_outputs_and_case(self):
        j=self.create();self.e.run(j,'prepare');out=self.e.directory(j)
        self.assertIn('Ardından kapak kalkıyor.',(out/'subtitles.srt').read_text())
        assert_no_source_identity(self,(out/'index.html').read_text())
        self.assertNotIn('text-transform',(out/'index.html').read_text())
        self.assertNotIn('https://cdn.',(out/'index.html').read_text())

    def test_prepare_is_idempotent(self):
        j=self.create();self.e.run(j,'prepare');p=self.e.directory(j)/'index.html';t=p.stat().st_mtime_ns
        self.e.run(j,'prepare');self.assertEqual(t,p.stat().st_mtime_ns)

    def test_tampered_asset_rebuilt_and_descendants_invalidated(self):
        j=self.create();self.e.run(j,'prepare');p=self.e.directory(j)/'caption.txt';p.write_text('tamper')
        self.e.store.set_stage(j,'check','complete',{'caption.txt':file_hash(p)})
        self.e.run(j,'prepare');self.assertEqual(p.read_text().strip(),self.fixture['caption'])
        self.assertEqual(self.e.store.stage(j,'check')['status'],'pending')

    def test_missing_asset_rebuilt(self):
        j=self.create();self.e.run(j,'prepare');p=self.e.directory(j)/'index.html';p.unlink()
        self.e.run(j,'prepare');self.assertTrue(p.is_file())

    def test_failed_stage_resume_reuses_completed_stage(self):
        j=self.create();self.e.run(j,'prepare');t=(self.e.directory(j)/'index.html').stat().st_mtime_ns
        with patch.object(self.e,'hf_call',side_effect=WorkflowError('Fixture failure')):
            with self.assertRaises(WorkflowError):self.e.run(j,'check')
        self.assertEqual(self.e.store.stage(j,'check')['status'],'failed')
        with patch.object(self.e,'hf_call',return_value=b'{"ok":true,"browserSkipped":false}'):
            self.e.run(j,'check')
        self.assertEqual(self.e.store.stage(j,'check')['status'],'complete')
        self.assertEqual(t,(self.e.directory(j)/'index.html').stat().st_mtime_ns)

    def test_skipped_browser_cannot_pass(self):
        j=self.create()
        with patch.object(self.e,'hf_call',return_value=b'{"ok":true,"browserSkipped":true}'):
            with self.assertRaises(WorkflowError):self.e.run(j,'check')

    def test_lock_blocks_second_process(self):
        q=multiprocessing.Queue()
        with self.e.store.lock():
            p=multiprocessing.Process(target=other_lock,args=(str(self.root/'work'),q));p.start();p.join(10)
            self.assertEqual(q.get(timeout=2),'blocked')

    def test_budget_required(self):
        with self.assertRaises(WorkflowError):self.e.execute_voice(self.req())

    def test_small_budget_rejected(self):
        with self.assertRaises(WorkflowError):self.e.approve(self.req(),'.001','Test')

    def test_expired_budget_rejected(self):
        r=self.approved();self.e.store.db.execute('UPDATE requests SET approved_until=? WHERE id=?',('2000-01-01T00:00:00+00:00',r));self.e.store.db.commit()
        with self.assertRaises(WorkflowError):self.e.execute_voice(r)

    def test_mock_retry_cost_recorded_once(self):
        r=self.approved();a=self.e.execute_voice(r);b=self.e.execute_voice(r)
        self.assertEqual(a['status'],'completed_mock_only');self.assertEqual(b['status'],'reused')
        costs=self.e.store.db.execute('SELECT * FROM costs').fetchall()
        self.assertEqual(len(costs),1);self.assertEqual(costs[0]['actual_microusd'],0)

    def test_live_provider_hard_blocked_with_approval(self):
        r=self.req(provider='elevenlabs');self.e.approve(r,'.02','Fixture approval')
        with self.assertRaisesRegex(WorkflowError,'disabled'):self.e.execute_voice(r)
        self.assertEqual(self.e.store.db.execute('SELECT count(*) FROM costs').fetchone()[0],0)

    def test_uncertain_no_retry_or_reapproval(self):
        r=self.approved()
        with self.assertRaises(WorkflowError):self.e.execute_voice(r,True)
        with self.assertRaisesRegex(WorkflowError,'reconcile'):self.e.execute_voice(r)
        with self.assertRaises(WorkflowError):self.e.approve(r,'.02','Test')

    def test_dispatching_from_crash_no_retry(self):
        r=self.approved();self.e.store.db.execute('UPDATE requests SET status=? WHERE id=?',('dispatching',r));self.e.store.db.commit()
        with self.assertRaisesRegex(WorkflowError,'uncertain'):self.e.execute_voice(r)

    def test_uncertain_receipt_then_reuse(self):
        r=self.approved()
        with self.assertRaises(WorkflowError):self.e.execute_voice(r,True)
        receipt={'request':r,'provider':'mock','simulated':True,'audio_generated':False,'actual_microusd':0,'simulated_microusd':10000}
        self.e.reconcile(r,receipt);self.assertEqual(self.e.execute_voice(r)['status'],'reused')

    def test_wrong_receipt_rejected(self):
        r=self.approved()
        with self.assertRaises(WorkflowError):self.e.execute_voice(r,True)
        with self.assertRaises(WorkflowError):self.e.reconcile(r,{'request':'wrong'})

    def test_quote_cannot_rekey_same_request(self):
        j=self.create();self.req(j)
        with self.assertRaisesRegex(WorkflowError,'another quote'):self.req(j,estimate='.02')

    def test_budget_not_shared_between_jobs(self):
        self.approved();self.fixture['title']='Başka demo';self.save()
        with self.assertRaises(WorkflowError):self.e.execute_voice(self.req())

    def test_invalid_money(self):
        for v in ['NaN','Infinity','-1','0.0000001','10001']:
            with self.subTest(v=v),self.assertRaises(WorkflowError):microusd(v)

    def test_overlap_and_nonfinite_timing(self):
        for value in [-1,float('nan'),1]:
            self.fixture['cues'][1]['start']=value;self.save()
            with self.subTest(v=value),self.assertRaises((WorkflowError,ValueError)):self.create()

    def test_script_cue_mismatch_refused(self):
        self.fixture['cues'][1]['text']='ardından kapak kalkıyor.';self.save()
        with self.assertRaisesRegex(WorkflowError,'match'):self.create()

    def test_unknown_motion_refused(self):
        self.fixture['scenes'][0]['action']='invent-whatever';self.save()
        with self.assertRaises(WorkflowError):self.create()

    def test_serial_requires_continuity(self):
        self.fixture=json.loads((ROOT/'tests/fixtures/examples/sample-series.json').read_text());self.fixture.pop('continuity');self.save()
        with self.assertRaises(WorkflowError):self.create()

    def test_claim_requires_source(self):
        self.fixture['claims']=[{'text':'Unsupported claim'}];self.save()
        with self.assertRaises(WorkflowError):self.create()

    def test_html_escaped(self):
        self.fixture['scenes'][0]['heading']='<script>alert(1)</script>';self.save()
        j=self.create();self.e.run(j,'prepare');markup=(self.e.directory(j)/'index.html').read_text()
        self.assertIn('&lt;script&gt;',markup);self.assertNotIn('<script>alert(1)</script>',markup)

    def test_path_boundary(self):
        with self.assertRaises(WorkflowError):within(self.root,'../outside')
        (self.root/'link').symlink_to('/tmp')
        with self.assertRaises(WorkflowError):within(self.root,'link/outside')

    def test_secret_detection_never_returns_value(self):
        fake='sk-'+'z'*28
        findings=scan_bytes(''.join(['API','_KEY','=',fake]).encode());self.assertTrue(findings)
        self.assertNotIn(fake,json.dumps(findings))
        self.assertFalse(scan_bytes(b'API_KEY=FAKE_EXAMPLE_NOT_A_REAL_KEY'))

    def test_secret_input_refused_without_value(self):
        self.fixture['caption']='sk-'+'z'*28;self.save()
        with self.assertRaisesRegex(WorkflowError,'Possible secret'):self.create()

    def test_approved_local_audio_import_and_hash(self):
        audio=self.root/'tone.wav'
        with wave.open(str(audio),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000);w.writeframes(b'\0\0'*64000)
        self.fixture['audio']={'file':'tone.wav','sha256':file_hash(audio),'approved_by':'test fixture, no speech','rights_note':'Generated silence for technical import testing'}
        self.fixture['alignment']='imported_timing';self.save()
        j=self.create();self.e.run(j,'prepare');out=self.e.directory(j)
        self.assertEqual(file_hash(audio),file_hash(out/'assets/narration.wav'))
        self.assertIn('id="narration"',(out/'index.html').read_text())

    def test_changed_approved_audio_rejected(self):
        self.fixture['audio']={'file':'tone.wav','sha256':'wrong','approved_by':'test','rights_note':'test'}
        self.fixture['alignment']='imported_timing';(self.root/'tone.wav').write_bytes(b'fixture');self.save()
        with self.assertRaisesRegex(WorkflowError,'hash'):self.create()

    def test_import_cannot_escape(self):
        self.fixture['audio']={'file':'../private.wav','sha256':'wrong','approved_by':'test','rights_note':'test'}
        self.fixture['alignment']='imported_timing';self.save()
        with self.assertRaisesRegex(WorkflowError,'boundary'):self.create()

    def test_cli_invalid_input_has_clean_error(self):
        self.path.write_text('not JSON')
        proc=subprocess.run([sys.executable,'-m','storymotion','--workspace',str(self.root/'cli'),'create',str(self.path)],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(proc.returncode,2);self.assertFalse(json.loads(proc.stderr)['ok'])


if __name__=='__main__':unittest.main()
