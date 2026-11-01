from pack_fixture_case import PackFixtureCase
import concurrent.futures
import json
import tempfile
import unittest
from pathlib import Path
from storymotion.automation import compile_generated_story,provider_result_to_job
from storymotion.dashboard import Dashboard
from storymotion.engine import Engine,ROOT
from storymotion.provider_runtime import ProviderRuntime
from storymotion.providers import ADAPTERS,MockTransport,Response,SecretBroker
from storymotion.security import WorkflowError
from storymotion.worker import LocalWorker


class WorkerTests(PackFixtureCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.d=Dashboard(self.root/'work')
    def tearDown(self):self.d.clear_keys();self.tmp.cleanup()
    def enqueue(self,title='Worker fixture'):
        return self.d.enqueue({'account':'sample-flow','format':'video-script','title':title,'brief':'Local worker brief','content':'A manually written queued fixture.','caption':'Local fixture.','provider':'local','model':'manual','task':'text','template_revision':0})
    def test_worker_claims_and_prepares_once_without_provider(self):
        j=self.enqueue();result=LocalWorker(self.d).run_once();self.assertEqual(result['status'],'prepared');self.assertEqual(result['provider_calls'],0)
        self.assertEqual(self.d.job(j['id'])['attempts'],1);self.assertEqual(LocalWorker(self.d).run_once()['status'],'idle')
    def test_simultaneous_claim_does_not_duplicate_job(self):
        j=self.enqueue();d2=Dashboard(self.root/'work')
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            results=list(pool.map(lambda d:LocalWorker(d).run_once(),[self.d,d2]))
        self.assertEqual(sorted(r['status'] for r in results),['idle','prepared']);self.assertEqual(self.d.job(j['id'])['attempts'],1)
    def test_two_workers_process_two_jobs_without_file_race(self):
        jobs=[self.enqueue('First fixture'),self.enqueue('Second fixture')];d2=Dashboard(self.root/'work')
        with concurrent.futures.ThreadPoolExecutor(2) as pool:results=list(pool.map(lambda d:LocalWorker(d).run_once(),[self.d,d2]))
        self.assertEqual([r['status'] for r in results],['prepared','prepared']);self.assertEqual(len({r['job'] for r in results}),2)
    def test_manual_prepare_rejected_while_worker_owns_job(self):
        j=self.enqueue();claim=self.d.claim('fixture_worker')
        with self.assertRaisesRegex(WorkflowError,'worker'):self.d.prepare(j['id'])
        self.d.prepare(j['id'],lease_token=claim['token']);self.d.finish_claim(claim)
    def test_expired_claim_recoverable_new_token_old_owner_cannot_finish(self):
        j=self.enqueue();old=self.d.claim('old_worker')
        with self.d.connection() as db:db.execute('UPDATE dashboard_jobs SET lease_until=0 WHERE id=?',(j['id'],))
        fresh=self.d.claim('new_worker');self.assertNotEqual(old['token'],fresh['token'])
        with self.assertRaises(WorkflowError):self.d.finish_claim(old)
        self.assertNotIn('lease_token',self.d.job(j['id']))
    def test_heartbeat_renews_owned_lease_only(self):
        self.enqueue();claim=self.d.claim('worker_fixture');self.assertTrue(self.d.renew_claim(claim));wrong=dict(claim,token='wrong');self.assertFalse(self.d.renew_claim(wrong))


class NewBriefTests(PackFixtureCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.brief=json.loads((ROOT/'tests/fixtures/examples/new-brief-flow.json').read_text())
    def tearDown(self):self.tmp.cleanup()
    def test_new_brief_is_not_box_fixture_replay(self):
        path=self.root/'new.json';path.write_text(json.dumps(self.brief));e=Engine(self.root/'work');j=e.create(path)['job'];e.run(j,'prepare')
        markup=(e.directory(j)/'index.html').read_text();self.assertIn('Bir iş sıraya giriyor.',markup);self.assertIn('Yeni iş',markup);self.assertIn('s0-token',markup);self.assertNotIn('s0-lid',markup);self.assertNotIn('s0-lock',markup)
    def test_node_data_changes_generated_geometry_and_labels(self):
        self.brief['scenes'][0].update(nodes=['Giriş','Çıkış'],from_node=0,to_node=1)
        path=self.root/'new.json';path.write_text(json.dumps(self.brief));e=Engine(self.root/'work');j=e.create(path)['job'];e.run(j,'prepare')
        markup=(e.directory(j)/'index.html').read_text();self.assertIn('Giriş',markup);self.assertIn('Çıkış',markup);self.assertIn('x:884.0',markup)
    def test_generated_json_not_executable_html_or_local_audio(self):
        with self.assertRaises(WorkflowError):compile_generated_story('<script>bad</script>','sample-mechanism')
        self.brief['audio']={'file':'../private.wav'}
        with self.assertRaises(WorkflowError):compile_generated_story(json.dumps(self.brief),'sample-mechanism')
    def test_generated_brand_and_unknown_primitive_refused(self):
        with self.assertRaises(WorkflowError):compile_generated_story(json.dumps(self.brief),'sample-series')
        self.brief['scenes'][0]['action']='execute_code'
        with self.assertRaises(WorkflowError):compile_generated_story(json.dumps(self.brief),'sample-mechanism')
    def test_mock_provider_draft_compiles_to_new_project_not_fixture(self):
        e=Engine(self.root/'work');scope=e.create(ROOT/'tests/fixtures/examples/sample-mechanism.json')['job'];plan=ADAPTERS['openai'].build('synthetic-openai-model','Create a story JSON for a new queue brief.',2000)
        response={'id':'resp_story_fixture','status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(self.brief)}]}]}
        broker=SecretBroker();transport=MockTransport(Response(200,'application/json',json.dumps(response).encode()));runtime=ProviderRuntime(self.root/'work',broker,transport)
        try:
            ref=runtime.prepare(scope,plan,'.01','Synthetic test estimate')['request'];runtime.approve(ref,'.02','Synthetic approval only')
            slot=broker.put('openai',scope,plan.fingerprint,'FAKE_NEW_BRIEF_TEST_KEY_12345',synthetic=True);runtime.run(ref,slot)
            result=provider_result_to_job(runtime,ref,'sample-mechanism');self.assertNotEqual(result['job'],scope);self.assertTrue(result['synthetic_provider_result'])
            markup=(e.directory(result['job'])/'index.html').read_text();self.assertIn('Yeni iş',markup);self.assertNotIn('s0-lid',markup);self.assertEqual(len(transport.calls),1)
        finally:broker.clear()


if __name__=='__main__':unittest.main()
