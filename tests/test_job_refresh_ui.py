from pack_fixture_case import PackFixtureCase
"""Real app event/hook regressions for status refreshes; all HTTP is mocked."""
import shutil
import unittest

import test_manual_scene_ui as manual


REAL_SETUP = r'''
const aId=jobId,bId='e'.repeat(24),calls=[];
function actualJob(id=aId){const job=manualJob('sample-reflection',id);job.status='prepared';job.files=[];job.payload.input={title:'Sentetik iş '+id[0],content:'Yalnız sentetik metin.'};job.payload.format={adapter:'account-pack',name:'Yerel sahne',state:'bounded'};return job;}
const actualJobs=new Map([[aId,actualJob(aId)],[bId,actualJob(bId)]]);
let deferred=null;
context.actualApi=async(path,data)=>{
 calls.push({path,data});
 if(deferred&&deferred.path===path)return new Promise(resolve=>deferred.release=resolve);
 if(path==='/api/jobs')return {jobs:[...actualJobs.values()].map(j=>JSON.parse(JSON.stringify(j)))};
 if(path==='/api/elevenlabs/state')return {requests:[]};
 const match=path.match(/^\/api\/jobs\/([a-f0-9]{24})(?:\/(.+))?$/);if(!match)throw Error('Unexpected API '+path);
 if(!match[2])return JSON.parse(JSON.stringify(actualJobs.get(match[1])));
 if(match[2]==='render-state')return {status:'not_started',files:{}};
 if(match[2]==='scene-plan-template')return manualTemplate();
 if(match[2]==='check'||match[2]==='prepare')return {status:'checked'};
 if(match[2]==='scene-plan')return {parent_job:match[1],child_job:childId,publication_ready:false};
 throw Error('Unexpected action '+match[2]);
};
run('api=actualApi');
async function realLoad(id=aId){await run(`selectJob('${id}')`);await $('manual-load').listeners.click[0]();}
async function realReady(){await realLoad();await run('refreshJobs()');}
function dirty(value){input('manual-content',value);assert.equal(run('manualSceneUI.dirty'),true);}
function clickOperation(kind){return kind==='check'?$('check-job').listeners.click[0]():$('jobs').children[0].children[3].children[0].listeners.click[0]();}
'''


@unittest.skipUnless(shutil.which('node'), 'Node required for offline app hooks')
class JobRefreshUI(PackFixtureCase):
    def dom(self, body):
        manual.ManualSceneUI().dom(REAL_SETUP + body)

    def test_check_response_cannot_clear_new_manual_draft_on_same_job(self):
        self.dom(r'''
        await realReady();deferred={path:'/api/jobs/'+aId+'/check'};const pending=clickOperation('check');await settle();dirty('{new A draft while checking');
        const before=run('manualSceneRaw()');deferred.release({status:'checked'});deferred=null;await pending;await settle();
        assert.equal(run('state.job.id'),aId);assert.equal(run('manualSceneRaw()'),before);assert.equal(run('manualSceneUI.dirty'),true);assert.ok(run('manualSceneUI.base'));
        ''')

    def test_check_response_cannot_roll_back_new_selection_and_manual_draft(self):
        self.dom(r'''
        await realReady();deferred={path:'/api/jobs/'+aId+'/check'};const pending=clickOperation('check');await settle();await realLoad(bId);dirty('{new B draft while A checks');
        const before=run('manualSceneRaw()');deferred.release({status:'checked'});deferred=null;await pending;await settle();
        assert.equal(run('state.job.id'),bId);assert.equal(run('manualSceneRaw()'),before);assert.equal(run('manualSceneUI.dirty'),true);assert.ok(run('manualSceneUI.base'));
        ''')

    def test_prepare_response_cannot_clear_new_manual_draft_on_same_job(self):
        self.dom(r'''
        await realReady();deferred={path:'/api/jobs/'+aId+'/prepare'};const pending=clickOperation('prepare');await settle();dirty('{new A draft while preparing');
        const before=run('manualSceneRaw()');deferred.release({status:'prepared'});deferred=null;await pending;await settle();
        assert.equal(run('state.job.id'),aId);assert.equal(run('manualSceneRaw()'),before);assert.equal(run('manualSceneUI.dirty'),true);assert.ok(run('manualSceneUI.base'));
        ''')

    def test_prepare_response_cannot_roll_back_new_selection_and_manual_draft(self):
        self.dom(r'''
        await realReady();deferred={path:'/api/jobs/'+aId+'/prepare'};const pending=clickOperation('prepare');await settle();await realLoad(bId);dirty('{new B draft while A prepares');
        const before=run('manualSceneRaw()');deferred.release({status:'prepared'});deferred=null;await pending;await settle();
        assert.equal(run('state.job.id'),bId);assert.equal(run('manualSceneRaw()'),before);assert.equal(run('manualSceneUI.dirty'),true);assert.ok(run('manualSceneUI.base'));
        ''')

    def test_same_immutable_job_status_and_files_refresh_preserves_raw_base_and_dirty(self):
        self.dom(r'''
        await realReady();dirty('{raw draft kept across explicit refresh');$('manual-approved-by').value='Unsaved reviewer';const before=run('manualSceneRaw()'),epoch=run('state.jobEpoch'),base=run('JSON.stringify(manualSceneUI.base)');
        actualJobs.get(aId).status='checked';actualJobs.get(aId).files=['qa.json'];await run(`selectJob('${aId}')`);await settle();
        assert.ok(run('state.jobEpoch')>epoch);assert.equal(run('state.job.status'),'checked');assert.deepEqual(Array.from(run('state.job.files')),['qa.json']);
        assert.equal(run('manualSceneRaw()'),before);assert.equal(run('JSON.stringify(manualSceneUI.base)'),base);assert.equal(run('manualSceneUI.dirty'),true);assert.equal($('manual-form').hidden,false);
        ''')

    def test_changed_payload_or_account_context_resets_old_manual_plan(self):
        for mutation in ["actualJobs.get(aId).payload.template.template.video.scenes[0].heading='Changed immutable payload'", "run('state.epoch++')", "run('state.account=state.catalog.accounts.find(a=>a.id===\"sample-series\")')"]:
            with self.subTest(mutation=mutation):
                self.dom(r'''
                await realReady();dirty('{old payload draft');MUTATION;await run(`selectJob('${aId}')`);await settle();
                assert.equal(run('manualSceneUI.base'),null);assert.equal(run('manualSceneUI.dirty'),false);assert.equal($('manual-content').value,'');assert.equal($('manual-form').hidden,true);
                '''.replace('MUTATION', mutation))

    def test_guard_is_rechecked_after_queue_refresh_and_pending_job_get(self):
        for phase in ['queue', 'get']:
            with self.subTest(phase=phase):
                self.dom(r'''
                await realReady();deferred={path:PHASE==='queue'?'/api/jobs':'/api/jobs/'+aId};
                const pending=clickOperation('check');await settle();dirty('{edit during refreshed '+PHASE);
                const before=run('manualSceneRaw()'),release=deferred.release;assert.equal(typeof release,'function');
                const response=PHASE==='queue'?{jobs:[...actualJobs.values()]}:actualJob(aId);deferred=null;release(response);await pending;await settle();
                assert.equal(run('manualSceneRaw()'),before);assert.equal(run('manualSceneUI.dirty'),true);assert.equal(run('state.job.id'),aId);
                '''.replace('PHASE', repr(phase)))

    def test_same_job_refresh_invalidates_pending_manual_save_and_old_open(self):
        self.dom(r'''
        await realReady();approve();deferred={path:'/api/jobs/'+aId+'/scene-plan'};const pending=submit();await settle();
        const before=run('manualSceneRaw()'),epoch=run('manualSceneUI.epoch');await run(`selectJob('${aId}')`);assert.ok(run('manualSceneUI.epoch')>epoch);assert.equal(run('manualSceneRaw()'),before);assert.ok(run('manualSceneUI.base'));
        const release=deferred.release;deferred=null;release(saved());await pending;assert.equal($('manual-open').hidden,true);assert.equal(run('manualSceneUI.child'),null);assert.equal(run('state.job.id'),aId);
        ''')

    def test_same_job_refresh_invalidates_pending_template_without_losing_existing_draft(self):
        self.dom(r'''
        await realReady();dirty('{keep original raw draft');deferred={path:'/api/jobs/'+aId+'/scene-plan-template'};const pending=$('manual-load').listeners.click[0]();await settle();
        const before=run('manualSceneRaw()');await run(`selectJob('${aId}')`);assert.equal(run('manualSceneRaw()'),before);const release=deferred.release;deferred=null;release(manualTemplate());await pending;
        assert.equal(run('manualSceneRaw()'),before);assert.equal(run('manualSceneUI.dirty'),true);assert.equal($('manual-open').hidden,true);
        ''')

    def test_unchanged_check_or_prepare_still_updates_selected_job_and_uses_readonly_followups(self):
        self.dom(r'''
        await realReady();for(const kind of ['check','prepare']){const before=run('state.jobEpoch');await clickOperation(kind);await settle();assert.equal(run('state.job.id'),aId);assert.ok(run('state.jobEpoch')>before);}
        assert.ok(calls.some(c=>c.path.endsWith('/check')));assert.ok(calls.some(c=>c.path.endsWith('/prepare')));
        assert.ok(!calls.some(c=>/\/render$|\/execute$|\/connect$|\/scene-plan$/.test(c.path)));
        ''')


if __name__ == '__main__':
    unittest.main()
