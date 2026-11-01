"""Actual authenticated Handler and private SQLite; no socket/provider/native."""
import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from storymotion import account_packs
from storymotion.dashboard import Dashboard, Handler
from storymotion.engine import Engine
from storymotion.security import canonical
from storymotion.taxonomy import item_id, MAX_CUSTOM_ITEMS
from test_catalog_integration import MemoryConnection, issued_cookie

ROOT=Path(__file__).resolve().parents[1]


class TaxonomyHttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name).resolve();registry=root/'registry'
        folder=registry/'accountpacks/neutral';folder.mkdir(parents=True)
        original=json.loads((ROOT/'accountpacks/neutral/neutral.json').read_text())
        for key in ('neutral','studio-b'):
            value=copy.deepcopy(original);value['id']=key;value['profile']['id']=key;value['fixture']['brand']=key
            if 'legacy_fixture' in value:value['legacy_fixture']['brand']=key
            (folder/(key+'.json')).write_text(json.dumps(value))
        patched=patch.object(account_packs,'ROOT',registry);patched.start();self.addCleanup(patched.stop)
        self.d=Dashboard(root/'workspace')
        for close in (self.d.close_local_log,self.d.reviews.close,self.d.renders.close,self.d.clear_keys,self.d.llm.close,self.d.eleven.broker.clear):self.addCleanup(close)
        self.d.local_log
        self.server=SimpleNamespace(server_address=('127.0.0.1',43333),dashboard=self.d)
        self.cookie=issued_cookie(self.server)
        for target in ('socket.socket.connect','socket.socket.bind','urllib.request.urlopen','storymotion.engine.checked_process'):
            blocker=patch(target,side_effect=AssertionError('External/native operation forbidden'));blocker.start();self.addCleanup(blocker.stop)

    def request(self,action,data,*,account='neutral',cookie=True,host='127.0.0.1:43333',origin='http://127.0.0.1:43333',marker='1',path=None,raw=None):
        body=json.dumps(data).encode() if raw is None else raw
        headers=['POST '+(path or '/api/taxonomy/'+action)+' HTTP/1.0','Host: '+host,'Origin: '+origin,
                 'X-Storymotion-Local: '+marker,'Content-Type: application/json','Content-Length: '+str(len(body))]
        if cookie:headers.append('Cookie: '+self.cookie)
        connection=MemoryConnection(('\r\n'.join(headers)+'\r\n\r\n').encode()+body)
        Handler(connection,('127.0.0.1',1),self.server)
        response=bytes(connection.output);head,raw=response.split(b'\r\n\r\n',1)
        return int(head.split()[1]),json.loads(raw),response

    def state(self,account='neutral'):
        code,value,_=self.request('state',{'account':account});self.assertEqual(code,200,value);return value

    def snapshot(self):
        with self.d.connection() as db:return tuple(db.iterdump())

    def create(self,name,kind='niche',account='neutral',niche=None):
        data={'account':account,'kind':kind,'name':name,'expected_revision':self.state(account)['revision']}
        if kind=='topic':data['niche']=niche
        code,value,_=self.request('create',data);self.assertEqual(code,200,value);return value

    def selected(self):
        state=self.state();topic=state['topics'][0]
        data={'account':'neutral','niche':topic['niche'],'topic':topic['id'],'expected_revision':state['revision']}
        code,value,_=self.request('select',data);self.assertEqual(code,200,value);return value

    def test_editorial_hierarchy_exact_families_and_honest_context(self):
        state=self.state();self.assertEqual(len(state['niches']),74);self.assertEqual(len(state['topics']),182)
        self.assertEqual(len({f for row in state['niches'] for f in row['family_ids']}),91)
        self.assertEqual(len({row['id'] for row in state['topics']}),182)
        self.assertTrue(all(row['niche'] in {n['id'] for n in state['niches']} for row in state['topics']))
        self.assertIsNone(state['selection']);self.assertIsNone(state['planning_context'])
        selected=self.selected();ctx=selected['planning_context']
        self.assertFalse(ctx['sources_verified']);self.assertFalse(ctx['style_applied_by_taxonomy'])
        self.assertFalse(ctx['capability']['render_verified']);self.assertEqual(ctx['human_review'],'pending')
        self.assertEqual(ctx['catalog_revision'],selected['revision']);self.assertEqual(ctx['source_items'],[])
        self.assertEqual(self.d.workspace.stat().st_mode&0o777,0o700)
        self.assertEqual((self.d.workspace/'jobs.sqlite3').stat().st_mode&0o777,0o600)

    def test_custom_records_reopen_and_same_label_is_idempotent(self):
        first=self.create('  Field  Notes  ');self.assertTrue(first['created']);item=first['item']
        second=self.create('field notes');self.assertFalse(second['created']);self.assertEqual(second['item']['id'],item['id'])
        topic=self.create('An original process','topic',niche=item['id'])['item']
        code,state,_=self.request('select',{'account':'neutral','niche':item['id'],'topic':topic['id'],'expected_revision':self.state()['revision']})
        self.assertEqual(code,200,state)
        from storymotion.taxonomy import Taxonomy
        reopened=Taxonomy(self.d).state('neutral');self.assertEqual(reopened,state)
        self.assertEqual(state['custom_count'],2);self.assertEqual(state['planning_context']['production_profile'],'neutral')

    def test_stale_revisions_do_not_mutate_or_hide_edits(self):
        stale=self.state()['revision'];self.create('New section');before=self.snapshot()
        for action,data in [('create',{'account':'neutral','kind':'niche','name':'Second section','expected_revision':stale}),
                            ('select',{'account':'neutral','niche':None,'topic':None,'expected_revision':stale})]:
            code,value,_=self.request(action,data);self.assertEqual(code,400);self.assertIn('REVISION_CHANGED',value['error']);self.assertEqual(self.snapshot(),before)

    def test_select_clear_select_never_reuses_an_old_revision(self):
        initial=self.state();selected=self.selected()
        code,cleared,_=self.request('select',{'account':'neutral','niche':None,'topic':None,'expected_revision':selected['revision']})
        self.assertEqual(code,200);self.assertIsNone(cleared['selection'])
        self.assertNotEqual(initial['revision'],cleared['revision'])
        code,again,_=self.request('select',{'account':'neutral',**selected['selection'],'expected_revision':cleared['revision']})
        self.assertEqual(code,200);self.assertNotEqual(selected['revision'],again['revision'])
        before=self.snapshot();code,value,_=self.request('select',{'account':'neutral','niche':None,'topic':None,'expected_revision':selected['revision']})
        self.assertEqual(code,400);self.assertEqual(self.snapshot(),before)

    def test_cross_account_records_and_topic_parent_are_refused(self):
        a=self.create('Private section')['item'];topic=self.create('Private topic','topic',niche=a['id'])['item']
        b=self.state('studio-b');self.assertNotIn(a['id'],{r['id'] for r in b['niches']})
        self.assertNotIn(topic['id'],{r['id'] for r in b['topics']})
        cases=[('select',{'account':'studio-b','niche':a['id'],'topic':topic['id'],'expected_revision':b['revision']}),
               ('create',{'account':'studio-b','kind':'topic','name':'Foreign parent','niche':a['id'],'expected_revision':b['revision']}),
               ('select',{'account':'neutral','niche':self.state()['niches'][0]['id'],'topic':topic['id'],'expected_revision':self.state()['revision']})]
        before=self.snapshot()
        for action,data in cases:
            self.assertEqual(self.request(action,data)[0],400);self.assertEqual(self.snapshot(),before)

    def test_auth_host_origin_marker_guard_every_action_before_dispatch(self):
        for action in ('state','create','select'):
            with patch.object(self.d.taxonomy,'action',side_effect=AssertionError('Must not reach service')):
                self.assertEqual(self.request(action,{'account':'neutral'},cookie=False)[0],401)
                self.assertEqual(self.request(action,{'account':'neutral'},host='other.invalid')[0],403)
                self.assertEqual(self.request(action,{'account':'neutral'},origin='https://other.invalid')[0],403)
                self.assertEqual(self.request(action,{'account':'neutral'},marker='0')[0],403)

    def test_malformed_unsafe_and_forged_identifiers_never_mutate(self):
        revision=self.state()['revision'];base={'account':'neutral','kind':'niche','name':'Safe name','expected_revision':revision}
        cases=[('state',{}),('state',{'account':'unknown'}),('state',{'account':'../neutral'}),('state',{'account':True}),
               ('create',{**base,'id':'caller-id'}),('create',{**base,'__proto__':{}}),('create',{**base,'constructor':{}}),
               ('create',{**base,'name':'<script>marker</script>'}),('create',{**base,'name':'\u0000hidden'}),
               ('create',{**base,'name':'x'*101}),('create',{**base,'name':{}}),('create',{**base,'name':True}),
               ('select',{'account':'neutral','niche':None,'topic':'topic-x','expected_revision':revision}),
               ('select',{'account':'neutral','niche':[],'topic':{},'expected_revision':revision}),('unknown',{})]
        before=self.snapshot()
        for action,data in cases:
            with self.subTest(action=action,data=data):
                self.assertEqual(self.request(action,data)[0],400);self.assertEqual(self.snapshot(),before)
        for raw in (b'[]',b'{',b'{"account":'+b'9'*5000+b'}'):
            self.assertEqual(self.request('state',{},raw=raw)[0],400);self.assertEqual(self.snapshot(),before)

    def test_fake_patterned_and_both_active_opaque_credentials_are_never_saved(self):
        keys=[('sk-'+'A'*24,None),('FAKE_OPAQUE_TAXONOMY_A',self.d.llm.broker),('FAKE_OPAQUE_TAXONOMY_B',self.d.eleven.broker)]
        for secret,broker in keys:
            if broker:broker.put('openai','synthetic-job','synthetic-request',secret,synthetic=True)
            before=self.snapshot();code,value,response=self.request('create',{'account':'neutral','kind':'niche','name':secret,'expected_revision':self.state()['revision']})
            self.assertEqual(code,400);self.assertNotIn(secret.encode(),response);self.assertEqual(self.snapshot(),before)
            self.assertFalse(any(secret.encode() in p.read_bytes() for p in self.d.workspace.rglob('*') if p.is_file()))

    def test_explicit_selection_binds_prepare_and_stale_or_foreign_token_never_persists(self):
        state=self.selected();token={**state['selection'],'revision':state['revision']}
        spec=json.loads((ROOT/'fixtures/template-families.json').read_text())['families']['kinetic-grid'][0]['spec']
        data={'account':'neutral','engine':'hyperframes','spec':spec,'planning':token}
        code,value,_=self.request('',data,path='/api/template-families/prepare');self.assertEqual(code,200,value)
        with Engine(self.d.workspace/'family-renders') as engine:
            subject=engine.payload(value['job'])['brief']['template_subject']
            self.assertEqual(subject,state['planning_context'])
        changed=self.create('New metadata')['state'];before=self.snapshot()
        for bad in (data,{**data,'account':'studio-b'},{**data,'planning':{**token,'revision':changed['revision'],'niche':'caller-id'}}):
            code,value,_=self.request('',bad,path='/api/template-families/prepare');self.assertEqual(code,400,value);self.assertEqual(self.snapshot(),before)
        self.assertEqual(changed['selection'],state['selection'])

    def test_clear_is_explicit_and_foreign_account_selection_is_untouched(self):
        state=self.selected();other=self.state('studio-b')
        code,value,_=self.request('select',{'account':'neutral','niche':None,'topic':None,'expected_revision':state['revision']})
        self.assertEqual(code,200,value);self.assertIsNone(value['planning_context']);self.assertIsNone(value['selection'])
        self.assertEqual(self.state('studio-b'),other)

    def test_removed_pack_is_not_kept_active_by_cached_account_metadata(self):
        self.state('studio-b');(account_packs.ROOT/'accountpacks/neutral/studio-b.json').unlink()
        before=self.snapshot();code,value,_=self.request('state',{'account':'studio-b'})
        self.assertEqual(code,400,value);self.assertEqual(self.snapshot(),before)

    def test_capacity_error_retains_existing_records_and_current_selection(self):
        state=self.selected()
        with self.d.connection() as db:
            for index in range(MAX_CUSTOM_ITEMS):
                name='Synthetic item '+str(index);ident=item_id('niche','neutral',name)
                value={'id':ident,'name':name,'account':'neutral','origin':'customer_local'}
                db.execute('INSERT INTO taxonomy_items VALUES(?,?,?,?)',('neutral',ident,'niche',canonical(value)))
        full=self.state();before=self.snapshot()
        code,value,_=self.request('create',{'account':'neutral','kind':'niche','name':'Overflow item','expected_revision':full['revision']})
        self.assertEqual(code,400,value);self.assertIn('CAPACITY',value['error']);self.assertEqual(self.snapshot(),before)
        self.assertEqual(full['selection'],state['selection']);self.assertEqual(full['custom_count'],MAX_CUSTOM_ITEMS)

    def test_malformed_owned_record_is_controlled_without_automatic_repair(self):
        with self.d.connection() as db:db.execute('INSERT INTO taxonomy_items VALUES(?,?,?,?)',('neutral','local-niche-bad','niche','[]'))
        before=self.snapshot();code,value,_=self.request('state',{'account':'neutral'})
        self.assertEqual(code,400,value);self.assertIn('STATE_INVALID',value['error']);self.assertEqual(self.snapshot(),before)
