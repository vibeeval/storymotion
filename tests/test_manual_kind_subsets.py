"""AccountPack subsets through real Dashboard/Handler and actual UI validator."""
import copy
import itertools
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from storymotion import account_packs
from storymotion.account_pack_schema import validate_pack
from storymotion.dashboard import Dashboard
from storymotion.scene_plan import validate_scene_plan
from storymotion.security import WorkflowError, digest
from storymotion.writing_context import snapshot
from test_catalog_integration import MemoryConnection, authenticated_handler
from test_manual_scene_revision import authored_fixture
import test_manual_scene_ui as manual_ui

ROOT=Path(__file__).resolve().parents[1]


class ManualKindSubsetTests(unittest.TestCase):
    def prototypes(self):
        paths=[ROOT/'accountpacks/neutral/neutral.json',*sorted((ROOT/'tests/fixtures/pack-registry/accountpacks/neutral').glob('*.json'))]
        return {json.loads(p.read_text())['id']:json.loads(p.read_text()) for p in paths}

    def http(self,d,job,body=None):
        server=SimpleNamespace(server_address=('127.0.0.1',43333),dashboard=d)
        route='scene-plan-template' if body is None else 'scene-plan';raw=json.dumps(body or {}).encode()
        request=('POST /api/jobs/'+job+'/'+route+' HTTP/1.0\r\nHost: 127.0.0.1:43333\r\nOrigin: http://127.0.0.1:43333\r\nX-Storymotion-Local: 1\r\nContent-Type: application/json\r\nContent-Length: '+str(len(raw))+'\r\n\r\n').encode()+raw
        connection=MemoryConnection(request);authenticated_handler(connection,('127.0.0.1',1),server)
        head,result=bytes(connection.output).split(b'\r\n\r\n',1)
        return int(head.split()[1]),json.loads(result)

    def exercise(self,account,kinds,serial=True,accepted=True,ui=False,rename=None):
        packs=self.prototypes();pack=copy.deepcopy(packs[account]);pack['capabilities']['manual_scene_kinds']=kinds
        if account=='sample-series' and not serial:
            pack['series_rules']={'enabled':False,'fictional':False};pack['profile']['continuity_required']=False;pack['capabilities']['rig_mode']=None
            pack['fixture']['continuity']=None;pack['fixture']['creative']['canon_status']='standalone'
            with self.assertRaisesRegex(WorkflowError,'manual|clue-inspect/canon-board'):
                validate_pack(pack,account)
            return 'schema_rejected'
        if rename:
            pack['id']=rename;pack['profile']['id']=rename;pack['fixture']['brand']=rename
            if pack.get('legacy_fixture'):pack['legacy_fixture']['brand']=rename
            packs.pop(account);account=rename
        validate_pack(pack,account);packs[account]=pack
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();folder=root/'accountpacks/neutral';folder.mkdir(parents=True)
            for key,value in packs.items():(folder/(key+'.json')).write_text(json.dumps(value))
            with patch.object(account_packs,'ROOT',root):
                d=Dashboard(root/'workspace')
                try:
                    template=d.template(account,'account-video')
                    video=authored_fixture('sample-flow' if account in {'neutral',rename} else account,accepted)
                    if video['brand']!=account:
                        video['brand']=account;binding=video['production_context'];binding['account']=account
                        binding['sources']=snapshot('sources',account,binding['sources']['data'],None)
                        binding['binding_sha256']=digest({k:v for k,v in binding.items() if k!='binding_sha256'})
                    template['template']['video']=video
                    template=d.save_template({'account':account,'format':'account-video','revision':0,'template':template['template']})
                    job=d.enqueue({'account':account,'format':'account-video','title':video['title'],'brief':video['brief'],'content':video['script'],'caption':video['caption'],'provider':'local','model':'manual','task':'text','template_revision':template['revision']})['id']
                    before=[r['id'] for r in d.jobs()]
                    if not kinds or account=='sample-series' and not accepted:
                        with self.assertRaises(WorkflowError):d.plans.template(job)
                        code,value=self.http(d,job);self.assertEqual(code,400);self.assertIn('error',value)
                        self.assertEqual([r['id'] for r in d.jobs()],before)
                        self.assertFalse(d.output(job).exists())
                        return 'explicit_rejection'
                    code,data=self.http(d,job);self.assertEqual(code,200,data)
                    self.assertEqual(set(data['supported_kinds']),set(kinds))
                    self.assertEqual(data['plan']['account'],account)
                    chosen={'possibility-branches':0,'process-route':1,'object-transform':2,'observation':3,'clue-inspect':4,'canon-board':5}
                    expected=min(kinds,key=chosen.get)
                    self.assertEqual({r['kind'] for r in data['plan']['scenes']},{expected})
                    self.assertFalse(data['publication_ready'] if 'publication_ready' in data else False)
                    self.assertEqual(data['review_status'],'incomplete')
                    if ui:
                        livejob={'id':job,'payload':{'account':{'id':account},'format':{'adapter':'account-pack'},'template':{'template':{'video':video}}}}
                        body='context.actual='+json.dumps(data)+';context.liveJob='+json.dumps(livejob)+';'+"run('state.job=liveJob;state.account=state.catalog.accounts.find(a=>a.id===liveJob.payload.account.id);state.jobEpoch++;manualSceneJobChanged(state.job);manualSceneTemplate(actual)');"
                        manual_ui.ManualSceneUI().dom(body)
                    plan=copy.deepcopy(data['plan'])
                    if not pack['series_rules']['enabled']:
                        for row in plan['scenes']:row['claim_indexes']=[0]
                    validate_scene_plan(plan,video)
                    code,result=self.http(d,job,{'plan':plan,'expected_video_sha256':data['expected_video_sha256'],'approved_by':'Synthetic manual reviewer','review_pending':True})
                    self.assertEqual(code,200,result);self.assertNotEqual(result['child_job'],job)
                    self.assertEqual(d.plans.guard(result['child_job'])['scene_plan'],plan)
                    self.assertFalse(result['publication_ready']);self.assertFalse(result['render_started'])
                    return expected
                finally:
                    d.clear_keys();d.eleven.broker.clear();d.llm.close();d.renders.close();d.reviews.close();d.close_local_log()

    def test_reported_fifteen_variant_schema_http_and_save_matrix(self):
        count=0
        for account,kinds in [('neutral',['process-route','object-transform']),('sample-reflection',['possibility-branches','observation']),('sample-series',['clue-inspect','canon-board'])]:
            for size in range(3):
                for subset in itertools.combinations(kinds,size):
                    with self.subTest(account=account,kinds=subset):self.exercise(account,list(subset));count+=1
        self.exercise('sample-series',['clue-inspect','canon-board'],accepted=False);count+=1
        self.exercise('sample-series',['clue-inspect'],serial=False,accepted=False);count+=1
        self.exercise('sample-series',['canon-board'],serial=False,accepted=False);count+=1
        self.assertEqual(count,15)

    def test_actual_http_singleton_starters_pass_the_existing_ui_validator(self):
        for account,kinds in [('neutral',['process-route','object-transform']),('sample-reflection',['possibility-branches','observation']),('sample-series',['clue-inspect','canon-board'])]:
            for kind in kinds:
                with self.subTest(account=account,kind=kind):self.exercise(account,[kind],ui=True)

    def test_new_pack_identifier_needs_no_brand_branch(self):
        self.assertEqual(self.exercise('neutral',['object-transform'],rename='custom-manual'),'object-transform')
