"""Real supported CLI + authenticated Handler; fake keys, no native/provider."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import types
import unittest

from storymotion.engine import Engine
from storymotion.family_receipts import read_receipt
from storymotion.providers import SecretBroker
from storymotion.security import WorkflowError, canonical, digest, write_json
from storymotion.template_families import make_brief
import test_template_credential_intake as credentials
import test_family_history_http as history
from test_template_intake import SOURCE, covering_claims

ROOT = Path(__file__).resolve().parents[1]


class FamilyIntakeReceiptTests(unittest.TestCase):
    def setUp(self):
        self.case = credentials.TemplateCredentialHttpTests('test_invalid_intake_without_credentials_does_not_write')
        self.case.setUp();self.addCleanup(self.case.doCleanups)
        self.d = self.case.d;self.root = self.case.root
        self.get = types.MethodType(history.FamilyHistoryHttpTests.get, self.case)
        code,state,_ = self.case.request('/api/writing-context/save-sources',{'account':'neutral','expected_revision':None,'sources':SOURCE,'rights_confirmed':True})
        self.assertEqual(code,200);self.revision=state['sources']['revision']

    def data(self, family='kinetic-grid', engine='hyperframes'):
        data=self.case.payload(family,engine)
        data.update(claims=covering_claims(data['spec']),source_revision=self.revision)
        return data

    def post_prepare(self, data):
        code,result,raw=self.case.request('/api/template-families/prepare',data)
        self.assertEqual(code,200,result)
        return result

    def cli(self, data):
        binding=self.d.llm.contexts.bind('neutral',self.revision,None)
        brief=make_brief('neutral',data['spec'],claims=data['claims'],production_context=binding)
        folder=self.root/'family-inputs';folder.mkdir(mode=0o700,exist_ok=True)
        path=folder/(digest(brief)+'.json');write_json(path,brief)
        workspace=self.root/'family-renders';workspace.mkdir(mode=0o700,exist_ok=True)
        env={k:os.environ[k] for k in ('PATH','LANG','LC_ALL','TMPDIR') if k in os.environ}
        env.update(DO_NOT_TRACK='1',HYPERFRAMES_TELEMETRY_DISABLED='1')
        prefix=[sys.executable,'-B','-m','storymotion','--workspace',str(workspace)]
        create=subprocess.run(prefix+['create',str(path),'--engine',data['engine']],cwd=ROOT,env=env,capture_output=True,text=True,timeout=45)
        self.assertEqual(create.returncode,0,create.stderr)
        job=json.loads(create.stdout)['job']
        prepare=subprocess.run(prefix+['run',job,'--until','prepare'],cwd=ROOT,env=env,capture_output=True,text=True,timeout=45)
        self.assertEqual(prepare.returncode,0,prepare.stderr)
        with sqlite3.connect(workspace/'jobs.sqlite3') as db:
            payload=json.loads(db.execute('SELECT payload FROM jobs WHERE id=?',(job,)).fetchone()[0])
            manifest=json.loads(db.execute("SELECT manifest FROM stages WHERE job=? AND name='prepare'",(job,)).fetchone()[0])
        self.assertEqual(payload['execution']['fingerprint'],self.d.runtime_execution,'CLI must carry the same current source fingerprint')
        token=digest({'kind':'family_artifact','account':'neutral','job':job,'manifest':digest(manifest),'name':'caption.txt'})
        return job,'/family-files/neutral/'+job+'/'+token

    def reject(self, job, url, key):
        before=self.case.snapshot()
        for path in ('/api/family-jobs/neutral/'+job,url):
            code,value,raw=self.get(path)
            self.assertEqual(code,400,value);self.assertNotIn(key.encode(),raw)
        code,listing,raw=self.get('/api/family-jobs/neutral')
        self.assertEqual(code,200);self.assertNotIn(job,[row['job'] for row in listing['jobs']]);self.assertNotIn(key.encode(),raw)
        self.assertEqual(self.case.snapshot(),before,'History lookup mutated an un-attested CLI record')
        self.assertFalse((self.root/'family-receipts'/(job+'.json')).exists())

    def test_cli_both_families_engines_and_brokers_never_gain_intake_attestation(self):
        good=self.post_prepare(self.data())
        for family in ('kinetic-grid','contour-trace'):
            for engine in ('hyperframes','remotion'):
                for provider,broker in (('openai',self.d.llm.broker),('elevenlabs',self.d.eleven.broker)):
                    with self.subTest(family=family,engine=engine,broker=provider):
                        key='FAKE_L_OPAQUE' if provider=='openai' else 'FAKE_V_OPAQUE'
                        broker.put(provider,'synthetic-job','synthetic-request',key,synthetic=True)
                        data=self.data(family,engine);data['spec']['parameters']['title']=key;data['claims']=covering_claims(data['spec'])
                        job,url=self.cli(data)
                        self.assertIn(key,(self.root/'family-renders'/job/'BRIEF.md').read_text())
                        self.assertIn(key,(self.root/'family-renders'/job/'caption.txt').read_text())
                        self.reject(job,url,key)
                        broker.clear()
                        self.reject(job,url,key)
        value=self.get(good['detail_url'])[1]
        self.assertEqual(value['artifacts_status'],'verified')

    def test_natural_five_second_broker_timer_expiry_still_cannot_publish_cli_caption(self):
        old=self.d.llm.broker;old.clear()
        broker=SecretBroker(ttl_seconds=5);self.d.llm.broker=broker;self.addCleanup(broker.clear)
        key='FAKE_CLI_TIMER_OPAQUE'
        ref=broker.put('openai','synthetic-job','synthetic-request',key,synthetic=True)
        timer=broker._timers[ref]
        data=self.data();data['spec']['parameters']['title']=key;data['claims']=covering_claims(data['spec'])
        job,url=self.cli(data)
        self.assertIn(key,(self.root/'family-renders'/job/'caption.txt').read_text())
        self.assertTrue(broker.contains_secret(key.encode()),'CLI fixture exceeded the real five-second active window')
        self.reject(job,url,key)
        timer.join(6)
        self.assertFalse(timer.is_alive());self.assertFalse(broker.contains_secret(key.encode()))
        self.assertNotIn(ref,broker._slots,'Real broker timer must have wiped the RAM slot')
        self.reject(job,url,key)

    def test_protected_route_binds_receipt_and_reuses_identical_job_without_rewriting_receipt(self):
        for family in ('kinetic-grid','contour-trace'):
            for engine in ('hyperframes','remotion'):
                data=self.data(family,engine);result=self.post_prepare(data);job=result['job']
                receipt=read_receipt(self.root,job);path=self.root/'family-receipts'/(job+'.json')
                self.assertEqual(receipt['intake'],'dashboard_clean_raw_and_normalized_v1')
                self.assertEqual(receipt['account'],'neutral');self.assertEqual(receipt['family'],family);self.assertEqual(receipt['engine'],engine)
                self.assertEqual(path.stat().st_mode&0o777,0o600);self.assertEqual(path.parent.stat().st_mode&0o777,0o700)
                before=(path.read_bytes(),path.stat().st_mtime_ns)
                self.assertEqual(self.post_prepare(data)['job'],job)
                self.assertEqual((path.read_bytes(),path.stat().st_mtime_ns),before)
                detail=self.get(result['detail_url'])[1];self.assertEqual(detail['artifacts_status'],'verified')
                self.assertEqual(receipt['manifest_sha256'],detail['manifest_sha256'])

    def test_missing_tampered_linked_or_public_receipts_never_expose_files(self):
        result=self.post_prepare(self.data());job=result['job'];detail=self.get(result['detail_url'])[1];url=detail['files'][0]['download_url']
        path=self.root/'family-receipts'/(job+'.json');original=path.read_bytes();value=json.loads(original)
        for field in ('job','account','family','engine','payload_sha256','brief_sha256','input_sha256','manifest_sha256','intake','execution_fingerprint'):
            changed=dict(value);changed[field]='altered';write_json(path,changed)
            code,result_value,_=self.get(result['detail_url'])
            self.assertTrue(code==400 or result_value.get('artifacts_status')=='unavailable')
            self.assertEqual(self.get(url)[0],400)
        path.unlink();self.assertEqual(self.get(result['detail_url'])[0],400)
        for raw in (b'[]',b'{"schema_version":1,"schema_version":1}',b'{'):
            path.write_bytes(raw);path.chmod(0o600);self.assertEqual(self.get(result['detail_url'])[0],400);path.unlink()
        outside=self.root/'receipt-copy';outside.write_bytes(original);outside.chmod(0o600)
        for linked in ('symlink','hardlink'):
            if linked=='symlink':path.symlink_to(outside)
            else:os.link(outside,path)
            self.assertEqual(self.get(url)[0],400);path.unlink()
        path.write_bytes(original);path.chmod(0o644)
        self.assertEqual(self.get(url)[0],400)

    def test_caller_attestation_flag_cannot_mint_a_receipt(self):
        data=self.data();data['intake_receipt']={'intake':'dashboard_clean_raw_and_normalized_v1'}
        before=self.case.snapshot();code,_,_=self.case.request('/api/template-families/prepare',data)
        self.assertEqual(code,400);self.assertEqual(self.case.snapshot(),before)

    def test_non_object_selection_envelope_is_controlled_even_with_matching_stage_hash(self):
        result=self.post_prepare(self.data());job=result['job'];path=self.root/'family-renders'/job/'template-selection.json'
        write_json(path,[])
        with sqlite3.connect(self.root/'family-renders/jobs.sqlite3') as db:
            stage=dict(zip(('status','manifest'),db.execute("SELECT status,manifest FROM stages WHERE job=? AND name='prepare'",(job,)).fetchone()))
            manifest=json.loads(stage['manifest']);manifest['template-selection.json']=hashlib.sha256(path.read_bytes()).hexdigest();stage['manifest']=canonical(manifest)
            db.execute("UPDATE stages SET manifest=? WHERE job=? AND name='prepare'",(stage['manifest'],job))
            payload=json.loads(db.execute('SELECT payload FROM jobs WHERE id=?',(job,)).fetchone()[0])
        with self.assertRaises(WorkflowError):self.d.template_studio.history.verified(self.root/'family-renders',job,payload,stage)
        code,value,_=self.get(result['detail_url']);self.assertEqual(code,200);self.assertEqual(value['files'],[])
