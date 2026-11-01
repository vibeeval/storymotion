"""Authenticated SQLite commits replayed through the real series UI program."""
import copy
import json
from types import SimpleNamespace
from pack_fixture_case import PackFixtureCase
import test_series as backend
import test_series_ui as frontend
from test_catalog_integration import MemoryConnection,authenticated_handler
from storymotion.security import canonical,digest
from storymotion.writing_context import snapshot


class SeriesHistorySaveRace(PackFixtureCase):
    def http(self,d,action,body):
        raw=canonical(body).encode();server=SimpleNamespace(dashboard=d,server_address=('127.0.0.1',43333))
        request=('POST /api/series/'+action+' HTTP/1.0\r\nHost: 127.0.0.1:43333\r\nOrigin: http://127.0.0.1:43333\r\nX-Storymotion-Local: 1\r\nContent-Type: application/json\r\nContent-Length: '+str(len(raw))+'\r\n\r\n').encode()+raw
        connection=MemoryConnection(request);authenticated_handler(connection,('127.0.0.1',1),server)
        head,data=bytes(connection.output).split(b'\r\n\r\n',1)
        return {'request':body,'status':int(head.split()[1]),'reply':json.loads(data)}

    def actual_exchange(self,third_head=False):
        case=backend.SerialLifecycleTests();case.setUp()
        try:
            accepted=self.http(case.d,'accept',case.accept_body());self.assertEqual(accepted['status'],200,accepted)
            previous=accepted['reply']['revision'];record=accepted['reply']['record']
            # Only archive metadata is multiplied to enable real pagination.
            # The selected reference keeps the normal mock-media integrity path.
            with case.d.connection() as db:
                for n in range(1,102):
                    value=copy.deepcopy(record);data=copy.deepcopy(value['canon']['data']);data.update(series_id='zz-archive',episode_id='archive-'+str(n))
                    value.update(ordinal=n,canon=snapshot('canon','sample-series',data,None),synthetic_archive_only=True)
                    key=digest(value);db.execute('INSERT INTO series_episodes VALUES(?,?,?,?,?,?)',(key,'zz-archive',data['episode_id'],n,value['job'],canonical(value)))
                db.execute('INSERT INTO series_heads VALUES(?,?)',('zz-archive',key))
            initial=self.http(case.d,'state',{'account':'sample-series','limit':100});self.assertEqual(initial['status'],200)
            self.assertTrue(initial['reply']['history']['episodes']['next_cursor'])
            template=self.http(case.d,'draft-template',{'previous_revision':previous});self.assertEqual(template['status'],200)
            first=self.http(case.d,'draft',case.draft_body(previous));self.assertEqual(first['status'],200,first)
            first_revision=first['reply']['draft_revision']
            if third_head:
                other=case.draft_body(previous);other['video']['title']='Ayrı oturumun sonraki taslağı.'
                third=self.http(case.d,'draft',other);self.assertEqual(third['status'],200,third)
            page=self.http(case.d,'state',{'account':'sample-series','limit':100,'selected_revision':previous,'episode_cursor':initial['reply']['history']['episodes']['next_cursor']})
            self.assertEqual(page['status'],200);observed=page['reply']['selected_episode']['draft_revision']
            self.assertEqual(observed,third['reply']['draft_revision'] if third_head else first_revision)
            second_body=case.draft_body(previous);second_body['expected_draft']=first_revision;second_body['video']['title']='İkinci kontrollü devam taslağı.'
            stale=self.http(case.d,'draft',{**second_body,'expected_draft':first['request']['expected_draft']})
            self.assertEqual(stale['status'],400);self.assertIn('SERIES_DRAFT_HEAD_CHANGED',stale['reply']['error'])
            second=self.http(case.d,'draft',second_body)
            self.assertEqual(second['status'],400 if third_head else 200,second)
            if third_head:self.assertIn('SERIES_DRAFT_HEAD_CHANGED',second['reply']['error'])
            else:self.assertNotEqual(second['reply']['draft_revision'],first_revision)
            return {'job':case.d.job(case.job),'initial':initial,'template':template,'first':first,'page':page,'second':second,'stale':stale,'third_head':third_head}
        finally:case.tearDown()

    def replay(self,order,dirty=False,third_head=False):
        h=self.actual_exchange(third_head)
        script='context.H='+json.dumps(h)+';'+r'''
        const H=context.H,calls=[];let releasePage,releasePost,states=0,posts=0;
        const copy=v=>JSON.parse(JSON.stringify(v));
        context.raceApi=async(path,b)=>{calls.push({path,body:copy(b)});
          if(path==='/api/series/state'){if(states++===0){assert.deepEqual(copy(b),H.initial.request);return copy(H.initial.reply);}assert.deepEqual(copy(b),H.page.request);return new Promise(resolve=>releasePage=()=>resolve(copy(H.page.reply)));}
          if(path==='/api/series/draft-template'){assert.deepEqual(copy(b),H.template.request);return copy(H.template.reply);}
          if(path==='/api/series/draft'){if(posts++===0){assert.deepEqual(copy(b),H.first.request);return new Promise(resolve=>releasePost=()=>resolve(copy(H.first.reply)));}assert.deepEqual(copy(b),H.second.request);if(H.second.status===400)throw Error(H.second.reply.error);return copy(H.second.reply);}
          throw Error('Unexpected route '+path);
        };
        context.actualJob=H.job;run('state.account=state.catalog.accounts.find(a=>a.id===actualJob.payload.account.id);state.job=actualJob;state.jobEpoch++;seriesJobChanged(state.job);api=raceApi;refreshJobs=async()=>{};tab("qa")');
        await $('series-state-read').listeners.click[0]();$('series-previous').value=H.template.request.previous_revision;$('series-previous').listeners.change[0]();await $('series-draft-load').listeners.click[0]();
        function fill(b){setInput('series-video',JSON.stringify(b.video));setInput('series-continuation-note',b.continuation_note);setInput('series-approved-by',b.approved_by);check('series-draft-rights');check('series-review-pending');}
        fill(H.first.request);const page=$('series-episodes-next').listeners.click[0]();await settle();assert.equal($('series-draft-save').disabled,false);const post=saveDraft();await settle();
        if(DIRTY)fill(H.second.request);const local=$('series-video').value;
        if(ORDER==='history'){releasePage();await page;assert.equal(run('seriesEpisode().draft_revision'),DIRTY?H.first.request.expected_draft:H.page.reply.selected_episode.draft_revision);releasePost();await post;}
        else{releasePost();await post;releasePage();await page;}
        assert.equal(run('seriesUI.draft.expected_draft'),H.first.reply.draft_revision);assert.equal($('series-video').value,local);assert.equal(run('state.job.id'),H.job.id);
        if(H.third_head){assert.notEqual(run('seriesUI.draft.expected_draft'),H.page.reply.selected_episode.draft_revision);assert.match($('series-status').textContent,/farklı bir taslak başı/);assert.equal(run('seriesUI.child'),null);}
        fill(H.second.request);await saveDraft();assert.equal(posts,2);assert.equal(calls.filter(c=>c.path==='/api/series/draft')[1].body.expected_draft,H.first.reply.draft_revision);
        if(H.third_head){assert.equal(run('seriesUI.draft.expected_draft'),H.first.reply.draft_revision);assert.match($('series-status').textContent,/SERIES_DRAFT_HEAD_CHANGED/);assert.equal(run('seriesUI.child'),null);}
        else{assert.equal(run('seriesUI.draft.expected_draft'),H.second.reply.draft_revision);assert.equal(run('seriesUI.child.id'),H.second.reply.child_job);}
        '''.replace('DIRTY',json.dumps(dirty)).replace('ORDER',json.dumps(order))
        frontend.SeriesUI().dom(script)

    def test_postcommit_history_and_save_ack_both_orders_then_actual_second_save(self):
        for order in ('history','save'):
            for dirty in (False,True):
                with self.subTest(order=order,dirty=dirty):self.replay(order,dirty)

    def test_newer_third_head_is_not_silently_adopted_from_history(self):
        self.replay('history',third_head=True)

    def test_critical_selected_reference_changes_still_reject_stale_ack(self):
        changes=["account='another-account'","series_id='another-series'","episode_id='another-episode'","ordinal=2","final_sha256='7'.repeat(64)","job='9'.repeat(24)","current=false","revision='8'.repeat(64)"]
        for change in changes:
            with self.subTest(change=change):
                frontend.SeriesUI().dom(r'''
                await loadDraft();draftConsent();let release;context.mockApi=()=>new Promise(resolve=>release=resolve);run('api=mockApi;refreshJobs=async()=>{}');const pending=saveDraft();await settle();run("seriesUI.listing.episodes[0].CHANGE");const raw=$('series-video').value;release(drafted());await pending;assert.equal(run('seriesUI.draft.expected_draft'),null);assert.equal(run('seriesUI.child'),null);assert.equal($('series-video').value,raw);
                '''.replace('CHANGE',change))
