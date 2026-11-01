"""Real private SQLite/Handler history, not thousands of rendered/accepted videos."""
import base64
import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pack_fixture_case import PackFixtureCase
from test_catalog_integration import MemoryConnection, authenticated_handler
from test_writing_context import accepted_reference
from storymotion import account_packs
from storymotion.dashboard import Dashboard, Handler
from storymotion.security import WorkflowError, canonical, digest
from storymotion.writing_context import snapshot


class SeriesHistoryTests(PackFixtureCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.d=Dashboard(self.root/'work')
        self.addCleanup(self.close,self.d);self.reference=accepted_reference()

    def close(self,d):
        d.clear_keys();d.llm.close();d.renders.close();d.reviews.close();d.close_local_log()

    def seed(self,count,drafts=0,series='synthetic-series',account='sample-series',d=None):
        d=d or self.d;keys=[]
        with d.connection() as db:
            for i in range(1,count+1):
                value=copy.deepcopy(self.reference);value.update(series_id=series,episode_id='episode-'+str(i))
                record={'schema_version':1,'job':digest([account,series,i])[:24],'engine':'hyperframes','ordinal':i,
                        'previous_revision':keys[-1] if keys else None,'job_payload_sha256':digest('synthetic-history-only'),
                        'render_binding':{'synthetic_history_only':True},'sources':None,
                        'canon':snapshot('canon',account,value,None),'draft_revision':None,
                        'attestation':'operator_continuation_reference_only','human_qa':'incomplete','publication_ready':False}
                key=digest(record);keys.append(key)
                db.execute('INSERT INTO series_episodes VALUES(?,?,?,?,?,?)',(key,series,value['episode_id'],i,record['job'],canonical(record)))
            if keys:db.execute('INSERT OR REPLACE INTO series_heads VALUES(?,?)',(series,keys[-1]))
            draft_keys=[]
            for i in range(drafts):
                record={'previous_revision':keys[-1],'video':{'brand':account},'synthetic_history_only':True,'revision_index':i}
                key=digest(record);draft_keys.append(key)
                db.execute('INSERT INTO series_drafts VALUES(?,?,?,?)',(key,keys[-1],digest([account,series,'child',i])[:24],canonical(record)))
            if draft_keys:db.execute('INSERT OR REPLACE INTO series_draft_heads VALUES(?,?)',(keys[-1],draft_keys[-1]))
        return keys,draft_keys

    def records(self,d=None):
        with (d or self.d).connection() as db:
            return {name:[tuple(r) for r in db.execute('SELECT * FROM '+name+' ORDER BY 1')]
                    for name in ['series_episodes','series_heads','series_drafts','series_draft_heads']}

    def http(self,data,auth=True,origin='http://127.0.0.1:43333'):
        raw=canonical(data).encode();request=('POST /api/series/state HTTP/1.0\r\nHost: 127.0.0.1:43333\r\nOrigin: '+origin+'\r\nX-Storymotion-Local: 1\r\nContent-Type: application/json\r\nContent-Length: '+str(len(raw))+'\r\n\r\n').encode()+raw
        connection=MemoryConnection(request);server=SimpleNamespace(dashboard=self.d,server_address=('127.0.0.1',43333))
        (authenticated_handler if auth else Handler)(connection,('127.0.0.1',1),server)
        head,body=bytes(connection.output).split(b'\r\n\r\n',1)
        return int(head.split()[1]),json.loads(body)

    def pages(self,kind,query=None,d=None):
        d=d or self.d;query=dict(query or {});values=[];cursor_name='episode_cursor' if kind=='episodes' else 'draft_cursor'
        while True:
            state=d.series.state(query);values.extend(r['revision'] for r in state[kind]);page=state['history'][kind]
            self.assertLessEqual(len(state[kind]),query.get('limit',100))
            if page['next_cursor'] is None:break
            query[cursor_name]=page['next_cursor']
        return values

    def test_empty_and_one_legacy_shape_with_explicit_page_metadata(self):
        empty=self.d.series.state();self.assertEqual(empty['episodes'],[]);self.assertEqual(empty['drafts'],[])
        self.assertEqual(empty['history']['episodes']['total'],0);self.assertEqual(empty['active_episodes'],[])
        keys,_=self.seed(1,1);before=self.records();value=self.d.series.state()
        self.assertEqual(value['episodes'][0]['revision'],keys[-1]);self.assertTrue(value['episodes'][0]['current'])
        self.assertEqual(value['history']['episodes']['total'],1);self.assertIsNone(value['history']['drafts']['next_cursor'])
        self.assertEqual(self.records(),before);self.assertFalse(value['publication_ready'])

    def test_boundaries_and_larger_history_no_duplicates_or_skips_and_no_mutation(self):
        for count in (1000,1001,2407):
            with self.subTest(count=count):
                d=Dashboard(self.root/('size-'+str(count)))
                try:
                    episodes,drafts=self.seed(count,count,d=d);before=self.records(d)
                    query={'account':'sample-series','limit':200}
                    first=d.series.state(query);active=first['active_episodes'][0]
                    self.assertEqual(first['history']['episodes']['total'],count)
                    self.assertEqual(first['history']['drafts']['total'],count)
                    self.assertEqual(active['revision'],episodes[-1]);self.assertEqual(active['next_ordinal'],count+1)
                    self.assertEqual(active['draft_revision'],drafts[-1]);self.assertNotIn(episodes[-1],[e['revision'] for e in first['episodes']])
                    self.assertEqual(self.pages('episodes',query,d),episodes)
                    self.assertEqual(self.pages('drafts',query,d),drafts)
                    selected=d.series.state({**query,'selected_revision':episodes[-1]})
                    self.assertEqual(selected['selected_episode'],active);self.assertEqual(self.records(d),before)
                finally:self.close(d)

    def test_actual_handler_large_state_and_scope_auth_and_invalid_inputs(self):
        episodes,_=self.seed(1001,1001);before=self.records();query={'account':'sample-series','limit':100,'selected_revision':episodes[-1]}
        code,value=self.http(query);self.assertEqual(code,200,value);self.assertEqual(value['history']['episodes']['total'],1001)
        self.assertEqual(value['selected_episode']['next_ordinal'],1002);self.assertEqual(len(value['episodes']),100)
        self.assertEqual(self.http(query,auth=False)[0],401);self.assertEqual(self.http(query,origin='https://attacker.test')[0],403)
        invalid=[{'limit':v} for v in (0,-1,201,True,1.5,'100',None)]
        invalid += [{'account':v} for v in (None,[],{},'missing-pack','sample-reflection')]
        invalid += [{'series':v} for v in ('../escape','A bad id',None,1)]
        invalid += [{'selected_revision':'bad'},{'unknown':True},{'episode_cursor':'A'*1025},{'draft_cursor':'!'}]
        cursor=value['history']['episodes']['next_cursor']
        invalid += [{'account':'sample-series','series':'other-series','episode_cursor':cursor},{'account':'sample-series','draft_cursor':cursor}]
        for data in invalid:
            with self.subTest(data=data):self.assertEqual(self.http(data)[0],400)
        self.assertEqual(self.http({'account':'sample-series','series':'not-yet-created'})[1]['episodes'],[])
        self.assertEqual(self.records(),before)

    def test_cursor_watermark_keeps_order_during_appends_and_rejects_invalid_positions(self):
        keys,_=self.seed(11,11);query={'account':'sample-series','limit':3};first=self.d.series.state(query)
        cursor=first['history']['episodes']['next_cursor'];self.seed(1,1,series='aaa-new')
        seen=[r['revision'] for r in first['episodes']];body={**query,'episode_cursor':cursor}
        while True:
            page=self.d.series.state(body);seen.extend(r['revision'] for r in page['episodes']);meta=page['history']['episodes']
            self.assertEqual(meta['total'],11);self.assertEqual(meta['live_total'],12)
            if meta['next_cursor'] is None:break
            body['episode_cursor']=meta['next_cursor']
        self.assertEqual(seen,keys);self.assertEqual(len(set(seen)),11)
        decoded=json.loads(base64.urlsafe_b64decode(cursor+'='*(-len(cursor)%4)))
        for change in ({'watermark':999999},{'last':'0'*64},{'watermark':True},{'v':2},{'scope':{'account':None,'series':None}}):
            wrong=base64.urlsafe_b64encode(canonical({**decoded,**change}).encode()).decode().rstrip('=')
            with self.subTest(change=change),self.assertRaises(WorkflowError):self.d.series.state({**query,'episode_cursor':wrong})

    def test_valid_account_and_series_scopes_do_not_mix(self):
        root=self.root/'packs';folder=root/'accountpacks/neutral';folder.mkdir(parents=True)
        originals=Path(account_packs.ROOT)/'accountpacks/neutral'
        for p in originals.glob('*.json'):(folder/p.name).write_bytes(p.read_bytes())
        pack=json.loads((folder/'sample-series.json').read_text());pack['id']=pack['profile']['id']=pack['fixture']['brand']='custom-series'
        if pack.get('legacy_fixture'):pack['legacy_fixture']['brand']='custom-series'
        (folder/'custom-series.json').write_text(json.dumps(pack))
        with patch.object(account_packs,'ROOT',root):
            d=Dashboard(self.root/'scoped')
            try:
                a,_=self.seed(3,3,series='alpha',d=d);b,_=self.seed(4,4,series='beta',account='custom-series',d=d)
                self.assertEqual(self.pages('episodes',{'account':'sample-series','limit':2},d),a)
                self.assertEqual(self.pages('drafts',{'account':'custom-series','series':'beta','limit':2},d).__len__(),4)
                self.assertEqual(d.series.state({'account':'sample-series','series':'beta'})['episodes'],[])
                pinned=d.series.state({'account':'sample-series','series':'beta','selected_revision':a[-1]})
                self.assertEqual(pinned['episodes'],[]);self.assertEqual(pinned['selected_episode']['revision'],a[-1])
                with self.assertRaises(WorkflowError):d.series.state({'account':'sample-series','selected_revision':b[-1]})
                cursor=d.series.state({'account':'custom-series','limit':2})['history']['episodes']['next_cursor']
                with self.assertRaises(WorkflowError):d.series.state({'account':'sample-series','episode_cursor':cursor})
            finally:self.close(d)
