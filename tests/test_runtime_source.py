from pack_fixture_case import PackFixtureCase
"""No disk edits: emulate changed source hashes in an already running dashboard."""
import tempfile
import unittest
from unittest.mock import patch
from storymotion.dashboard import Dashboard
from storymotion.security import WorkflowError


class RuntimeSourceTests(PackFixtureCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.d=Dashboard(self.temp.name,llm_mode='demo',elevenlabs_mode='demo')
    def tearDown(self):self.d.clear_keys();self.temp.cleanup()
    def stale(self):return patch('storymotion.dashboard.execution_provenance',return_value={'fingerprint':'f'*64})
    def data(self):
        v=self.d.template('sample-mechanism','account-video')['template']['video']
        return dict(account='sample-mechanism',format='account-video',title=v['title'],brief=v['brief'],content=v['script'],
            caption=v['caption'],provider='local',model='manual',task='text',template_revision=0)
    def test_stale_runtime_cannot_mint_new_jobs_or_save_templates(self):
        data=self.data();template=self.d.template('sample-mechanism','account-video')
        with self.stale():
            with self.assertRaisesRegex(WorkflowError,'yeniden başlat'):self.d.enqueue(data)
            with self.assertRaisesRegex(WorkflowError,'yeniden başlat'):
                self.d.save_template(dict(account='sample-mechanism',format='account-video',**template))
        self.assertEqual(self.d.jobs(),[]);self.assertEqual(self.d.template('sample-mechanism','account-video')['revision'],0)
    def test_stale_runtime_cannot_dispatch_preapproved_llm_but_disconnect_and_cancel_work(self):
        c=self.d.llm_action('connect',{'provider':'openai','value':'FAKE_SOURCE_GUARD_ONLY'})
        p=self.d.llm_action('preview',{'connection':c['connection'],'context':{'account':'sample-mechanism','title':'Local','brief':'Local','caption':''},
            'model':c['metadata']['models'][0]['id'],'max_output_tokens':2000})
        self.d.llm_action('approve',{'connection':c['connection'],'request':p['request'],'maximum_output_tokens':2000,'ack_unknown_cost':True,'rights_confirmed':True,'budget':None})
        with self.stale():
            for action,data in [('execute',{'connection':c['connection'],'request':p['request']}),('accept',{'request':p['request'],'brand_identity':{}}),
                ('connect',{'provider':'gemini','value':'FAKE_SOURCE_GUARD_OTHER'})]:
                with self.subTest(action=action),self.assertRaisesRegex(WorkflowError,'yeniden başlat'):self.d.llm_action(action,data)
            self.assertEqual(self.d.llm_action('state',{'request':p['request']})['dispatch_count'],0)
            self.d.llm_action('cancel',{'request':p['request']});self.d.llm_action('disconnect',{'connection':c['connection']})
        self.assertFalse(self.d.llm.transport.calls);self.assertFalse(self.d.llm.connections);self.assertEqual(self.d.jobs(),[])
    def test_stale_runtime_blocks_voice_connect_but_existing_session_can_be_cleared(self):
        c=self.d.voice_action('connect',{'value':'FAKE_VOICE_SOURCE_GUARD_ONLY'})
        with self.stale():
            with self.assertRaisesRegex(WorkflowError,'yeniden başlat'):self.d.voice_action('connect',{'value':'FAKE_VOICE_SOURCE_OTHER'})
            self.d.voice_action('disconnect',{'connection':c['connection']})
        self.assertFalse(self.d.eleven.connections)
