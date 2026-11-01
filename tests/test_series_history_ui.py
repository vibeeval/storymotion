"""Actual SQLite history responses in the production panel's offline DOM model."""
import json
from pack_fixture_case import PackFixtureCase
import test_series_history as database
import test_series_ui as panel


class SeriesHistoryUI(PackFixtureCase):
    def dom(self,body,count=1001,other_series=False):
        case=database.SeriesHistoryTests();case.setUp()
        try:
            keys,_=case.seed(count,count);q={'account':'sample-series','limit':100}
            if other_series:case.seed(2,2,series='another-series')
            first=case.d.series.state(q);head=next((h for h in first['active_episodes'] if h['series_id']=='synthetic-series'),None)
            selected={**q,**({'selected_revision':keys[-1]} if keys else {})}
            ep=first['history']['episodes']['next_cursor'];draft=first['history']['drafts']['next_cursor']
            values={'first':first,'head':head,'selected':case.d.series.state(selected),
                    'filtered':case.d.series.state({**selected,'series':'another-series' if other_series else 'synthetic-series'})}
            for name,extra in [('episodes',{'episode_cursor':ep}),('drafts',{'draft_cursor':draft}),('both',{'episode_cursor':ep,'draft_cursor':draft})]:
                values[name]=case.d.series.state({**selected,**extra}) if ep and draft else values['selected']
            setup='context.HISTORY='+json.dumps(values)+';'+r'''
            const H=context.HISTORY,historyCalls=[];let holdHistory=false,releaseHistory=null,failHistory=false,holdDraft=false,releaseDraft=null;
            function actualPage(b){assert.equal(b.account,'sample-series');assert.equal(b.limit,100);let value=b.series?H.filtered:b.episode_cursor&&b.draft_cursor?H.both:b.episode_cursor?H.episodes:b.draft_cursor?H.drafts:b.selected_revision?H.selected:H.first;return JSON.parse(JSON.stringify(value));}
            const historySaved=()=>({child_job:'7'.repeat(24),parent_job:H.head.job,previous_revision:H.head.revision,draft_revision:'6'.repeat(64),status:'draft_pending',publication_ready:false});
            context.historyApi=async(path,b)=>{historyCalls.push({path,body:JSON.parse(JSON.stringify(b))});
              if(path==='/api/series/state'){if(failHistory)throw Error('Synthetic history unavailable');if(holdHistory)return new Promise(resolve=>releaseHistory=()=>resolve(actualPage(b)));return actualPage(b);}
              if(path==='/api/series/draft-template')return {video:video(),expected_draft:H.head.draft_revision,previous_revision:H.head.revision,next_ordinal:H.head.next_ordinal};
              if(path==='/api/series/draft'){if(holdDraft)return new Promise(resolve=>releaseDraft=()=>resolve(historySaved()));return historySaved();}
              throw Error('Unexpected history test route '+path);
            };
            function historyStart(){selected();run('api=historyApi;refreshJobs=async()=>{}');}
            async function historyRead(){return $('series-state-read').listeners.click[0]();}
            async function historyDraft(){historyStart();await historyRead();$('series-previous').value=H.head.revision;$('series-previous').listeners.change[0]();await $('series-draft-load').listeners.click[0]();draftConsent();}
            const nextEpisode=()=>$('series-episodes-next').listeners.click[0]();
            '''
            panel.SeriesUI().dom(setup+body)
        finally:case.doCleanups()

    def test_real_empty_one_thousand_and_larger_metadata_stays_usable(self):
        for count in (0,1,1000,1001,2407):
            with self.subTest(count=count):
                self.dom(r'''
                historyStart();await historyRead();assert.equal(run('seriesUI.stateFresh'),true);assert.match($('series-state-summary').textContent,new RegExp('/'+COUNT+' '));
                assert.equal(run('seriesUI.listing.episodes.length'),Math.min(COUNT,100));assert.equal($('series-episodes-next').disabled,COUNT<=100);
                if(COUNT){$('series-previous').value=H.head.revision;$('series-previous').listeners.change[0]();assert.equal($('series-draft-load').disabled,false);await $('series-draft-load').listeners.click[0]();assert.equal(run('seriesUI.draft.next_ordinal'),COUNT+1);assert.equal(run('seriesUI.draft.expected_draft'),H.head.draft_revision);draftConsent();assert.equal($('series-draft-save').disabled,false);}
                else {assert.equal($('series-draft-load').disabled,true);assert.equal($('series-draft-save').disabled,true);}
                '''.replace('COUNT',str(count)),count)

    def test_independent_pages_keep_current_editor_cas_focus_and_back_navigation(self):
        self.dom(r'''
        await historyDraft();for(let node=$('series-video');node;node=node.parentElement)if(node.tagName==='details')node.open=true;$('series-video').focus();assert.equal(document.activeElement,$('series-video'));const focused=document.activeElement,raw=run('seriesRaw()'),epoch=run('seriesUI.epoch');
        await nextEpisode();assert.equal(run('seriesUI.epoch'),epoch);assert.equal(run('seriesRaw()'),raw);assert.equal(document.activeElement,focused);assert.equal(run('seriesEpisode().revision'),H.head.revision);assert.equal($('series-draft-save').disabled,false);assert.equal($('series-episodes-back').disabled,false);
        await $('series-drafts-next').listeners.click[0]();assert.equal(run('seriesRaw()'),raw);assert.equal(run('seriesUI.listing.history.episodes.cursor'),H.episodes.history.episodes.cursor);assert.equal($('series-draft-history').children.length,100);
        await $('series-episodes-back').listeners.click[0]();assert.equal(run('seriesUI.listing.history.episodes.cursor'),null);assert.equal(run('seriesUI.listing.history.drafts.cursor'),H.drafts.history.drafts.cursor);assert.equal(run('seriesRaw()'),raw);
        ''')

    def test_page_pending_editor_remains_enabled_and_late_response_preserves_new_edit(self):
        self.dom(r'''
        await historyDraft();holdHistory=true;const pending=nextEpisode();await settle();assert.equal($('series-draft-save').disabled,false);assert.equal(run('seriesUI.pending'),null);assert.equal($('series-episodes-next').disabled,true);
        setInput('series-video','{new local draft');const raw=$('series-video').value,listing=run('seriesUI.listing');releaseHistory();await pending;assert.equal($('series-video').value,raw);assert.equal(run('seriesUI.listing'),listing);assert.equal(run('seriesUI.stateFresh'),true);
        ''')

    def test_page_failure_and_malformed_response_preserve_editor_and_allow_retry(self):
        self.dom(r'''
        await historyDraft();const raw=run('seriesRaw()');failHistory=true;await nextEpisode();assert.match($('series-history-status').textContent,/Synthetic history unavailable/);assert.equal(run('seriesRaw()'),raw);assert.equal($('series-draft-save').disabled,false);assert.equal($('series-episodes-next').disabled,false);
        failHistory=false;const total=H.episodes.history.episodes.total;H.episodes.history.episodes.total=-1;await nextEpisode();assert.equal(run('seriesUI.listing.history.episodes.cursor'),null);assert.equal(run('seriesRaw()'),raw);H.episodes.history.episodes.total=total;await nextEpisode();assert.equal(run('seriesUI.listing.history.episodes.cursor'),H.episodes.history.episodes.cursor);
        ''')

    def test_refresh_and_context_changes_drop_late_pages_without_restoring_old_account(self):
        for mutation in ["selected('sample-reflection')", "selected('sample-series','9'.repeat(24))", "$('render-engine').value='remotion';run('seriesJobChanged(state.job)')", "setInput('series-history-filter','synthetic-series')", "$('series-previous').value=H.first.episodes[0].revision;$('series-previous').listeners.change[0]()"]:
            with self.subTest(mutation=mutation):
                self.dom(r'''
                await historyDraft();holdHistory=true;const pending=nextEpisode();await settle();MUTATION;const raw=run('seriesRaw()'),listing=run('seriesUI.listing');releaseHistory();await pending;assert.equal(run('seriesRaw()'),raw);assert.equal(run('seriesUI.listing'),listing);
                '''.replace('MUTATION',mutation))
        self.dom(r'''
        await historyDraft();holdHistory=true;const pending=historyRead();await settle();assert.equal(run('seriesUI.stateFresh'),false);setInput('series-video','{fresh local edit');releaseHistory();await pending;assert.equal(run('seriesUI.stateFresh'),false);assert.equal($('series-video').value,'{fresh local edit');
        ''')

    def test_history_response_cannot_rebase_or_hide_a_verified_concurrent_save(self):
        for response_first in (True,False):
            with self.subTest(response_first=response_first):
                self.dom(r'''
                await historyDraft();holdHistory=true;holdDraft=true;const page=nextEpisode();await settle();const saved=saveDraft();await settle();
                if(RESPONSE_FIRST){releaseHistory();await page;releaseDraft();await saved;}else{releaseDraft();await saved;releaseHistory();await page;}
                assert.equal(run('seriesUI.draft.expected_draft'),'6'.repeat(64));assert.equal(historyCalls.filter(c=>c.path==='/api/series/draft').length,1);assert.equal(run('state.job.id'),jobId);assert.equal(run('seriesUI.draft.next_ordinal'),1002);
                '''.replace('RESPONSE_FIRST',json.dumps(response_first)))

    def test_filtering_archive_to_another_series_does_not_switch_current_editor(self):
        self.dom(r'''
        await historyDraft();const raw=run('seriesRaw()'),base=run('seriesUI.draft.expected_draft');setInput('series-history-filter','another-series');await historyRead();
        assert.equal(run('seriesUI.listing.episodes.length'),2);assert.equal(run('seriesEpisode().series_id'),'synthetic-series');assert.equal(run('seriesRaw()'),raw);assert.equal(run('seriesUI.draft.expected_draft'),base);assert.equal($('series-draft-save').disabled,false);
        ''',other_series=True)
