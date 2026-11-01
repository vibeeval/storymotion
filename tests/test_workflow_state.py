from test_catalog_integration import authenticated_handler
from pack_fixture_case import PackFixtureCase
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from test_catalog_integration import MemoryConnection
from storymotion.dashboard import Dashboard,Handler
from storymotion.workflow_state import ROOT,workflow_status,validate_matrix
from storymotion.security import WorkflowError


class WorkflowStateTests(PackFixtureCase):
    def data(self):return json.loads((ROOT/'tests/fixtures/examples/workflow-matrix.json').read_text())
    def test_four_profiles_have_source_code_test_and_open_acceptance_per_stage(self):
        result=workflow_status();self.assertEqual(len(result['profiles']),4)
        for profile in result['profiles']:
            self.assertEqual(len(profile['stages']),12);self.assertEqual(sum(profile['counts'].values()),12)
            self.assertFalse(profile['publication_ready']);self.assertEqual(profile['product_acceptance'],'incomplete')
        self.assertEqual(result['current_native_acceptance'],'unverified');self.assertFalse(result['publication_ready'])
    def test_matching_old_fingerprint_never_promotes_inventory_to_new_native_approval(self):
        data=self.data()
        with patch('storymotion.workflow_state.execution_provenance',return_value={'fingerprint':data['baseline']['execution_fingerprint']}):
            result=workflow_status();self.assertTrue(result['baseline_execution_matches'])
            self.assertEqual(result['current_native_acceptance'],'unverified');self.assertFalse(result['publication_ready'])
    def test_missing_stale_or_optimistic_projection_is_rejected(self):
        for mutation in ('pack','stage','status','path','approval','source','raw'):
            data=self.data();row=data['profiles'][0]['stages'][0]
            if mutation=='pack':data['profiles'][0]['pack_version']='unreviewed'
            elif mutation=='stage':data['profiles'][0]['stages'].pop()
            elif mutation=='status':row['status']='fully_ready'
            elif mutation=='path':row['code']=['../unrelated-private-file']
            elif mutation=='approval':data['ready_for_publication']=True
            elif mutation=='source':row['sources']=['unknown-source']
            elif mutation=='raw':data['sources'][0]['raw_distributed']=True
            with self.subTest(mutation=mutation),self.assertRaises(WorkflowError):validate_matrix(data)
    def test_unknown_account_does_not_select_paths_or_other_products(self):
        for account in ('../secret','youtube-studio','miniature-asmr',''):
            with self.subTest(account=account),self.assertRaises(WorkflowError):workflow_status(account)
    def test_cli_projection_does_not_create_a_workspace_or_dispatch(self):
        from storymotion.__main__ import main
        with tempfile.TemporaryDirectory() as temp:
            target=Path(temp)/'must-stay-absent';output=io.StringIO()
            with patch('sys.argv',['storymotion','--workspace',str(target),'workflow-status','--account','sample-reflection']),patch('sys.stdout',output):self.assertEqual(main(),0)
            self.assertFalse(target.exists());self.assertEqual(json.loads(output.getvalue())['profiles'][0]['account'],'sample-reflection')
    def test_real_get_handler_is_read_only_host_guarded_and_source_bound(self):
        with tempfile.TemporaryDirectory() as temp:
            d=Dashboard(temp);server=SimpleNamespace(server_address=('127.0.0.1',43333),dashboard=d)
            def call(host='127.0.0.1:43333'):
                conn=MemoryConnection(('GET /api/workflows HTTP/1.0\r\nHost: '+host+'\r\n\r\n').encode());authenticated_handler(conn,('127.0.0.1',1),server)
                headers,body=bytes(conn.output).split(b'\r\n\r\n',1);return int(headers.split()[1]),json.loads(body)
            try:
                with patch.object(d.eleven.client,'request',side_effect=AssertionError('Workflow GET must not call a voice provider')) as voice,patch.object(d.llm.transport,'exchange',side_effect=AssertionError('Workflow GET must not call an LLM')) as text:
                    status,data=call();self.assertEqual(status,200);self.assertEqual(len(data['profiles']),4);self.assertFalse(d.jobs())
                    self.assertEqual(call('attacker.test')[0],403);d.runtime_execution='stale-source';self.assertEqual(call()[0],400)
                    voice.assert_not_called();text.assert_not_called()
            finally:d.clear_keys()


if __name__=='__main__':unittest.main()
