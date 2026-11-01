from pack_fixture_case import PackFixtureCase
"""Synthetic DOM checks for explicit episode reference/draft actions; no media IO."""
import json
import shutil
import unittest

import test_llm_ui as ui
from test_compact_ui import HTML, JS, MARKUP, ROOT

SOURCE = (ROOT / 'dashboard/series-panel.js').read_text()
SETUP = r'''
ready();run(SERIES_SOURCE);
const finalHash='f'.repeat(64),previousRevision='e'.repeat(64),draftRevision='d'.repeat(64),newRevision='a'.repeat(64),childId='d'.repeat(24);
const canon=()=>({series_id:'synthetic-series',episode_id:'episode-01',bible_version:'synthetic-1',origin:'synthetic_reference_test',final_sha256:finalHash,accepted_by:'operator',narrator:'first_person',cast:[],objects:[],open_clues:[],source_revision:null});
const video=()=>({brand:'sample-series',script:'Önceki sentetik senaryo.',scenes:[{id:'beat-1',information:'Önceki sentetik senaryo.'}],cues:[{text:'Önceki sentetik senaryo.',start:0,end:3}]});
const episode=(current=true)=>({revision:previousRevision,series_id:'synthetic-series',episode_id:'episode-01',ordinal:1,final_sha256:finalHash,current,job:jobId});
const refTemplate=()=>({canon:canon(),expected_head:null,ordinal:1,job:jobId,engine:'hyperframes',final_sha256:finalHash,warning:'Yalnız devam referansı; insan QA eksik.'});
const draftTemplate=()=>({video:video(),expected_draft:null,previous_revision:previousRevision,next_ordinal:2,warning:'Eski metni, sahne ve cue alanlarını birlikte değiştirin.'});
const accepted=()=>({revision:newRevision,record:{job:jobId,engine:'hyperframes'},status:'accepted_reference',publication_ready:false});
const drafted=()=>({child_job:childId,parent_job:jobId,previous_revision:previousRevision,draft_revision:draftRevision,status:'draft_pending',publication_ready:false});
function selected(account='sample-series',id=jobId,series=false){context.fixtureJob={id,status:'prepared',files:[],payload:{input:{title:'Sentetik bölüm',content:'Yerel metin.'},account:{id:account},format:{adapter:'account-pack',name:'Yerel konu'},...(series?{series_revision:{previous_revision:previousRevision}}:{})}};run("state.account=state.catalog.accounts.find(a=>a.id==='"+account+"');state.job=fixtureJob;state.jobEpoch++;seriesJobChanged(state.job);tab('qa')");}
function complete(){run(`seriesRenderState('${jobId}','hyperframes',{status:'complete',files:{'render-1080.mp4':'${finalHash}'}})`);}
function setInput(id,value){$(id).value=value;for(const listener of $(id).listeners.input||[])listener();}
function check(id,value=true){$(id).checked=value;for(const listener of $(id).listeners.change||[])listener();}
function refConsent(){setInput('series-accepted-by','Synthetic reviewer');check('series-reference-rights');check('series-reference-only');}
function draftConsent(){const proposal=video();proposal.script='Yeni ve ayrı sentetik senaryo.';proposal.scenes[0].information=proposal.script;proposal.cues[0].text=proposal.script;setInput('series-video',JSON.stringify(proposal));setInput('series-continuation-note','Önceki nesne kimliği korunuyor; elle incelenecek.');setInput('series-approved-by','Synthetic drafter');check('series-draft-rights');check('series-review-pending');}
function defaultApi(path){if(path==='/api/series/reference-template')return refTemplate();if(path==='/api/series/state')return {episodes:[episode()],drafts:[],human_acceptance:'incomplete',publication_ready:false};if(path==='/api/series/draft-template')return draftTemplate();if(path==='/api/series/accept')return accepted();if(path==='/api/series/draft')return drafted();throw Error('Unexpected '+path);}
function mockDefault(){context.mockApi=async(path,data)=>defaultApi(path);run('api=mockApi;refreshJobs=async()=>{}');}
async function loadRef(){selected();complete();mockDefault();await $('series-reference-load').listeners.click[0]();}
async function loadDraft(){selected();mockDefault();await $('series-state-read').listeners.click[0]();$('series-previous').value=previousRevision;$('series-previous').listeners.change[0]();await $('series-draft-load').listeners.click[0]();}
function acceptRef(){return $('series-reference-form').listeners.submit[0]({preventDefault(){}});}
function saveDraft(){return $('series-draft-form').listeners.submit[0]({preventDefault(){}});}
'''.replace('SERIES_SOURCE', json.dumps(SOURCE))

REAL_APP_SETUP = r'''
// Keep the production selection and queue functions, including their real hooks.
context.realSelectJob=run('selectJob');context.realRefreshJobs=run('refreshJobs');
const appCalls=[],appJobs=new Map();let appHead=null,appSaves=0,appDeferred=null;
function copy(value){return JSON.parse(JSON.stringify(value));}
function newVideo(text){const value=video();value.script=text;value.scenes[0].information=text;value.cues[0].text=text;return value;}
function editVideo(text){setInput('series-video',JSON.stringify(newVideo(text)));check('series-draft-rights');check('series-review-pending');}
function appCommitDraft(data){
 if(data.expected_draft!==appHead)throw Error('SERIES_DRAFT_HEAD_CHANGED: Başka taslak kaydedildi; önce yenileyin');
 appSaves++;appHead=String(appSaves).repeat(64);const id=String(appSaves).repeat(24),job=copy(appJobs.get(jobId));
 job.id=id;job.status='queued';job.payload.input.content=data.video.script;job.payload.series_revision={previous_revision:previousRevision,draft_revision:appHead};appJobs.set(id,job);
 return {...drafted(),child_job:id,draft_revision:appHead};
}
function enableRealApp(){
 appJobs.set(jobId,copy(run('state.job')));
 context.appApi=async(path,data)=>{
  appCalls.push({path,data:copy(data===undefined?null:data)});
  if(appDeferred?.path===path)return new Promise(resolve=>appDeferred.release=resolve);
  if(path==='/api/jobs')return {jobs:[...appJobs.values()].map(copy)};
  if(path==='/api/elevenlabs/state')return {requests:[]};
  if(path==='/api/series/draft')return appCommitDraft(data);
  const match=path.match(/^\/api\/jobs\/([a-f0-9]{24})(?:\/(.+))?$/);
  if(match&&!match[2]){assert.ok(appJobs.has(match[1]));return copy(appJobs.get(match[1]));}
  if(match?.[2]==='render-state')return {status:'not_started',files:{}};
  if(path.startsWith('/api/series/'))return defaultApi(path);
  throw Error('Unexpected actual app API '+path);
 };
 run('api=appApi;selectJob=realSelectJob;refreshJobs=realRefreshJobs');
}
async function realSavedDraft(){await loadDraft();draftConsent();enableRealApp();await saveDraft();assert.equal(appSaves,1);}
function releaseApp(value){const release=appDeferred.release;assert.equal(typeof release,'function');appDeferred=null;release(copy(value));}
'''


@unittest.skipUnless(shutil.which('node'), 'Node required for offline series UI')
class SeriesUI(PackFixtureCase):
    def dom(self, body):
        ui.WriterUi().dom(SETUP + body)

    def test_native_collapsed_panel_unique_ids_labels_and_mandatory_consents(self):
        ids = [n['attrs']['id'] for n in MARKUP.nodes if 'id' in n['attrs']]
        self.assertEqual(len(ids), len(set(ids)))
        panel = next(n for n in MARKUP.nodes if n['attrs'].get('id') == 'series-panel')
        self.assertEqual(panel['tag'], 'details')
        self.assertNotIn('open', panel['attrs'])
        children = [n for n in MARKUP.nodes if n['parent'] == MARKUP.nodes.index(panel)]
        self.assertEqual(children[0]['tag'], 'summary')
        labels = {n['attrs'].get('for') for n in MARKUP.nodes if n['tag'] == 'label'}
        for node in MARKUP.nodes:
            if node['tag'] in {'input', 'textarea', 'select'} and node['attrs'].get('id', '').startswith('series-'):
                self.assertIn(node['attrs']['id'], labels)
        for id_ in ['series-reference-rights', 'series-reference-only', 'series-draft-rights', 'series-review-pending']:
            attrs = next(n['attrs'] for n in MARKUP.nodes if n['attrs'].get('id') == id_)
            self.assertIn('required', attrs)
            self.assertNotIn('checked', attrs)
        self.assertEqual(next(n['attrs']['maxlength'] for n in MARKUP.nodes if n['attrs'].get('id') == 'series-canon'), '20000')
        self.assertEqual(next(n['attrs']['maxlength'] for n in MARKUP.nodes if n['attrs'].get('id') == 'series-video'), '70000')
        self.assertIn('Şema denetimi anlam doğruluğunu garanti etmez', HTML)

    def test_profile_gate_initial_state_and_inputs_never_dispatch_automatically(self):
        self.dom(r'''
        let calls=0;context.mockApi=async()=>{calls++;throw Error('No automatic request');};run('api=mockApi');
        selected('sample-reflection');assert.equal($('series-panel').hidden,true);selected();assert.equal($('series-panel').hidden,false);assert.equal($('series-panel').open,false);
        assert.equal($('series-reference-load').disabled,true);assert.equal($('series-draft-load').disabled,true);assert.equal($('series-reference-form').hidden,true);assert.equal($('series-draft-form').hidden,true);
        setInput('series-canon','{local draft');setInput('series-video','{local draft');check('series-reference-rights');assert.equal(calls,0);assert.equal($('series-accept').disabled,true);assert.equal($('series-draft-save').disabled,true);
        ''')

    def test_final_hash_gate_and_series_bound_bundle_never_reuse_stale_href(self):
        self.dom(r'''
        selected();complete();assert.equal($('series-reference-load').disabled,false);assert.equal($('series-bundle').hidden,true);
        selected('sample-series',jobId,true);complete();assert.equal($('series-bundle').hidden,false);assert.equal($('series-bundle').href,'/series-files/'+jobId+'/hyperframes/episode-package.zip');
        run(`seriesRenderState('${jobId}','hyperframes',null)`);assert.equal($('series-bundle').hidden,true);assert.ok(!('href' in $('series-bundle').attrs));assert.equal($('series-reference-load').disabled,true);
        for(const data of [{status:'running',files:{'render-1080.mp4':finalHash}},{status:'complete',files:{'render-1080.mp4':'bad'}}]){context.data=data;run(`seriesRenderState('${jobId}','hyperframes',data)`);assert.equal($('series-bundle').hidden,true);}
        ''')

    def test_exact_reference_accept_payload_actor_and_reference_only_result(self):
        self.dom(r'''
        await loadRef();refConsent();const calls=[],selectedJobs=[];let release;
        context.mockApi=async(path,data)=>{calls.push({path,data});return new Promise(resolve=>release=resolve);};context.open=async id=>selectedJobs.push(id);run('api=mockApi;selectJob=open');
        const pending=acceptRef();await settle();await acceptRef();assert.equal(calls.length,1);const body=calls[0].data;
        assert.equal(calls[0].path,'/api/series/accept');assert.deepEqual(Object.keys(body).sort(),['accepted_by','canon','engine','expected_head','job','ordinal','reference_only','rights_confirmed']);
        assert.equal(body.job,jobId);assert.equal(body.engine,'hyperframes');assert.equal(body.expected_head,null);assert.equal(body.ordinal,1);assert.equal(body.canon.accepted_by,'Synthetic reviewer');assert.equal(body.accepted_by,'Synthetic reviewer');assert.equal(body.reference_only,true);assert.equal(body.rights_confirmed,true);
        assert.equal(JSON.parse($('series-canon').value).accepted_by,'operator');release(accepted());await pending;assert.equal($('series-accept').disabled,true);assert.equal(run('seriesUI.reference.accepted'),true);assert.deepEqual(selectedJobs,[]);assert.match($('series-status').textContent,/Yalnız devam referansı.*insan QA ve yayın kabulü eksik/);
        ''')

    def test_reference_json_hash_actor_and_both_consents_are_required(self):
        self.dom(r'''
        await loadRef();refConsent();assert.equal($('series-accept').disabled,false);check('series-reference-only',false);assert.equal($('series-accept').disabled,true);check('series-reference-only');
        const invalid=canon();invalid.final_sha256='0'.repeat(64);setInput('series-canon',JSON.stringify(invalid));check('series-reference-rights');check('series-reference-only');assert.equal($('series-accept').disabled,true);
        setInput('series-canon','{invalid');assert.equal($('series-accept').disabled,true);setInput('series-accepted-by',' '.repeat(3));assert.equal($('series-accept').disabled,true);
        ''')

    def test_state_is_post_and_archived_previous_cannot_create_next(self):
        self.dom(r'''
        selected();const calls=[];context.mockApi=async(path,data)=>{calls.push({path,data});return {episodes:[episode(false)],drafts:[],human_acceptance:'incomplete'};};run('api=mockApi');
        await $('series-state-read').listeners.click[0]();assert.equal(calls[0].path,'/api/series/state');assert.deepEqual(JSON.parse(JSON.stringify(calls[0].data)),{account:'sample-series',limit:100});
        setInput('series-video','{preserved dirty video');$('series-previous').value=previousRevision;$('series-previous').listeners.change[0]();assert.equal($('series-video').value,'{preserved dirty video');assert.equal($('series-draft-load').disabled,true);assert.equal($('series-draft-save').disabled,true);assert.equal(calls.length,1);
        ''')

    def test_same_script_whitespace_case_or_missing_draft_consents_cannot_save(self):
        self.dom(r'''
        await loadDraft();setInput('series-continuation-note','Yerel devam notu.');setInput('series-approved-by','Reviewer');check('series-draft-rights');check('series-review-pending');assert.equal($('series-draft-save').disabled,true);
        const unchanged=video();unchanged.script='  '+video().script.toUpperCase().replace(/ /g,'  ')+' ';setInput('series-video',JSON.stringify(unchanged));check('series-draft-rights');check('series-review-pending');assert.equal($('series-draft-save').disabled,true);
        draftConsent();assert.equal($('series-draft-save').disabled,false);check('series-review-pending',false);assert.equal($('series-draft-save').disabled,true);
        ''')

    def test_exact_draft_payload_remains_pending_and_explicit_open_only(self):
        self.dom(r'''
        await loadDraft();draftConsent();const calls=[],selectedJobs=[];context.mockApi=async(path,data)=>{calls.push({path,data});return drafted();};context.open=async id=>selectedJobs.push(id);run('api=mockApi;selectJob=open;refreshJobs=async()=>{}');
        await saveDraft();assert.equal(calls.length,1);assert.equal(calls[0].path,'/api/series/draft');const body=calls[0].data;
        assert.deepEqual(Object.keys(body).sort(),['approved_by','continuation_note','expected_draft','previous_revision','review_pending','rights_confirmed','video']);assert.equal(body.previous_revision,previousRevision);assert.equal(body.expected_draft,null);assert.equal(body.review_pending,true);assert.equal(body.rights_confirmed,true);assert.equal(body.video.script,'Yeni ve ayrı sentetik senaryo.');
        assert.deepEqual(selectedJobs,[]);assert.equal(run('state.job.id'),jobId);assert.equal($('series-open').hidden,false);assert.match($('series-status').textContent,/otomatik kanon, render veya yayın kabulü yok/);
        await $('series-open').listeners.click[0]();assert.deepEqual(selectedJobs,[childId]);assert.ok(!calls.some(c=>/render|execute|connect|elevenlabs/.test(c.path)));
        ''')

    def test_late_reference_or_draft_template_cannot_overwrite_dirty_json(self):
        for kind in ['reference', 'draft']:
            with self.subTest(kind=kind):
                self.dom(r'''
                if(KIND==='reference'){selected();complete();}else await loadDraft();let release;context.mockApi=()=>new Promise(resolve=>release=resolve);run('api=mockApi');
                const pending=$(KIND==='reference'?'series-reference-load':'series-draft-load').listeners.click[0]();await settle();const field=KIND==='reference'?'series-canon':'series-video';setInput(field,'{new dirty local JSON');release(KIND==='reference'?refTemplate():draftTemplate());await pending;assert.equal($(field).value,'{new dirty local JSON');assert.equal($('series-open').hidden,true);
                '''.replace('KIND', json.dumps(kind)))

    def test_late_accept_on_job_switch_never_clobbers_b_draft_or_selection(self):
        self.dom(r'''
        await loadRef();refConsent();let release;context.mockApi=()=>new Promise(resolve=>release=resolve);run('api=mockApi');const pending=acceptRef();await settle();selected('sample-series','e'.repeat(24));setInput('series-canon','{B local canon');release(accepted());await pending;
        assert.equal(run('state.job.id'),'e'.repeat(24));assert.equal($('series-canon').value,'{B local canon');assert.equal(run('seriesUI.reference'),null);assert.equal($('series-accept').disabled,true);
        ''')

    def test_accept_checkbox_revoke_recheck_drops_old_response(self):
        self.dom(r'''
        await loadRef();refConsent();let release;context.mockApi=()=>new Promise(resolve=>release=resolve);run('api=mockApi');const pending=acceptRef();await settle();check('series-reference-only',false);check('series-reference-only');release(accepted());await pending;
        assert.equal(run('seriesUI.reference.accepted'),false);assert.match($('series-status').textContent,/önceki yanıt.*değiştirmedi/);
        ''')

    def test_late_draft_save_and_queue_refresh_keep_new_draft_and_hide_old_child(self):
        for phase in ['save', 'refresh']:
            with self.subTest(phase=phase):
                self.dom(r'''
                await loadDraft();draftConsent();let release;const calls=[];context.mockApi=async(path)=>{calls.push(path);return PHASE==='save'?new Promise(resolve=>release=resolve):drafted();};context.refresh=()=>PHASE==='refresh'?new Promise(resolve=>release=resolve):Promise.resolve();run('api=mockApi;refreshJobs=refresh');
                const pending=saveDraft();await settle();setInput('series-video','{changed after submission');release(PHASE==='save'?drafted():undefined);await pending;
                assert.equal($('series-video').value,'{changed after submission');assert.equal($('series-open').hidden,true);assert.deepEqual(calls,['/api/series/draft']);assert.equal(run('state.job.id'),jobId);
                '''.replace('PHASE', json.dumps(phase)))

    def test_silent_form_and_context_mutations_invalidate_pending_draft_result(self):
        for mutation in ["$('series-approved-by').value='Other'", "$('series-video').value='{}'", "$('series-review-pending').checked=false", "run('state.jobEpoch++')", "run('state.epoch++')", "$('render-engine').value='remotion'", "run('state.account=state.catalog.accounts.find(a=>a.id===\"sample-reflection\")')"]:
            with self.subTest(mutation=mutation):
                self.dom(r'''
                await loadDraft();draftConsent();let release;context.mockApi=()=>new Promise(resolve=>release=resolve);run('api=mockApi;refreshJobs=async()=>{}');const pending=saveDraft();await settle();MUTATION;release(drafted());await pending;assert.equal($('series-open').hidden,true);assert.equal(run('seriesUI.child'),null);
                '''.replace('MUTATION', mutation))

    def test_same_job_refresh_preserves_dirty_json_but_disables_stale_metadata(self):
        self.dom(r'''
        await loadRef();setInput('series-canon','{dirty canon');setInput('series-video','{dirty video');run('state.jobEpoch++;seriesJobChanged(state.job)');
        assert.equal($('series-canon').value,'{dirty canon');assert.equal($('series-video').value,'{dirty video');assert.equal(run('seriesUI.reference'),null);assert.equal(run('seriesUI.draft'),null);assert.equal($('series-accept').disabled,true);assert.equal($('series-draft-save').disabled,true);
        ''')

    def test_final_hash_change_blocks_reference_and_late_state_preserves_edits(self):
        self.dom(r'''
        await loadRef();refConsent();const before=$('series-canon').value;run(`seriesRenderState('${jobId}','hyperframes',{status:'complete',files:{'render-1080.mp4':'0'.repeat(64)}})`);assert.equal($('series-canon').value,before);assert.equal($('series-accept').disabled,true);
        await loadDraft();draftConsent();let release;context.mockApi=()=>new Promise(resolve=>release=resolve);run('api=mockApi');const pending=$('series-state-read').listeners.click[0]();await settle();setInput('series-video','{new edit during state read');release({episodes:[episode()],drafts:[],human_acceptance:'incomplete'});await pending;
        assert.equal($('series-video').value,'{new edit during state read');assert.equal(run('seriesUI.stateFresh'),false);assert.equal($('series-draft-save').disabled,true);
        ''')

    def test_backend_errors_are_visible_without_fallback_or_automatic_retry(self):
        for message in ['SERIES_REFERENCE_MISSING: Önce referans seçin', 'SERIES_CANON_CONFLICT: Nesne veya kıyafet çelişiyor', 'SERIES_SCRIPT_REUSED: Eski senaryo yeni bölüm değildir']:
            with self.subTest(message=message):
                self.dom(r'''
                await loadDraft();draftConsent();let calls=0;context.mockApi=async()=>{calls++;throw Error(MESSAGE);};run('api=mockApi');await saveDraft();await settle();assert.equal(calls,1);assert.equal($('series-open').hidden,true);assert.ok($('series-status').textContent.includes(MESSAGE));
                '''.replace('MESSAGE', json.dumps(message)))

    def test_disclosure_preserves_values_and_hidden_panel_moves_focus(self):
        self.dom(r'''
        await loadRef();setInput('series-canon','{unfinished reference');$('series-panel').open=true;$('series-panel').open=false;$('series-panel').open=true;assert.equal($('series-canon').value,'{unfinished reference');
        $('series-canon').focus();assert.equal(document.activeElement,$('series-canon'));selected('sample-reflection');assert.equal($('series-panel').hidden,true);assert.equal(document.activeElement,$('render-title'));assert.equal(visible(document.activeElement),true);
        ''')

    def test_successful_save_then_edit_saves_again_from_committed_revision(self):
        self.dom(REAL_APP_SETUP + r'''
        await realSavedDraft();assert.equal(run('seriesUI.draft.expected_draft'),appHead);assert.equal(run('seriesCurrent(seriesUI.child.snapshot)'),true);assert.equal(run('seriesUI.videoDirty'),false);
        const first=appHead;editVideo('İkinci ayrı devam taslağı.');await saveDraft();
        const saves=appCalls.filter(call=>call.path==='/api/series/draft');assert.equal(appSaves,2);assert.equal(saves[0].data.expected_draft,null);assert.equal(saves[1].data.expected_draft,first);assert.equal(run('seriesUI.draft.expected_draft'),appHead);
        assert.equal(run('state.job.id'),jobId);assert.equal(run('seriesUI.child.id'),'2'.repeat(24));assert.equal(run('seriesCurrent(seriesUI.child.snapshot)'),true);assert.equal($('series-open').hidden,false);
        assert.equal(appCalls.filter(call=>call.path==='/api/series/draft-template').length,0);
        ''')

    def test_committed_base_survives_edits_while_queue_refresh_is_pending(self):
        self.dom(REAL_APP_SETUP + r'''
        await loadDraft();draftConsent();enableRealApp();appDeferred={path:'/api/jobs'};const pending=saveDraft();await settle();
        assert.equal(appSaves,1);assert.equal(run('seriesUI.draft.expected_draft'),appHead);const first=appHead;
        editVideo('Kuyruk beklerken yazılan yeni taslak.');const raw=$('series-video').value;releaseApp({jobs:[...appJobs.values()]});await pending;
        assert.equal($('series-video').value,raw);assert.equal(run('seriesUI.child'),null);assert.equal(run('seriesUI.draft.expected_draft'),first);assert.equal(run('state.job.id'),jobId);
        await saveDraft();assert.equal(appSaves,2);assert.equal(appCalls.filter(call=>call.path==='/api/series/draft')[1].data.expected_draft,first);
        ''')

    def test_two_fast_save_clicks_dispatch_once_then_explicit_edit_uses_new_base(self):
        self.dom(REAL_APP_SETUP + r'''
        await loadDraft();draftConsent();enableRealApp();appDeferred={path:'/api/series/draft'};const pending=saveDraft();await settle();await saveDraft();
        assert.equal(appCalls.filter(call=>call.path==='/api/series/draft').length,1);appHead=draftRevision;releaseApp(drafted());await pending;
        assert.equal(run('seriesUI.draft.expected_draft'),draftRevision);editVideo('Çift tıklama sonrası açık yeni düzenleme.');await saveDraft();assert.equal(appSaves,1);assert.equal(appCalls.filter(call=>call.path==='/api/series/draft')[1].data.expected_draft,draftRevision);
        ''')

    def test_stale_lineage_or_invalid_save_response_cannot_advance_local_base(self):
        for phase in ['stale-lineage', 'invalid']:
            with self.subTest(phase=phase):
                self.dom(REAL_APP_SETUP + r'''
                await loadDraft();draftConsent();enableRealApp();appDeferred={path:'/api/series/draft'};const pending=saveDraft();await settle();
                const result=drafted();if(PHASE==='stale-lineage'){editVideo('Kaydet beklerken değişen yeni senaryo.');run('state.jobEpoch++');}else result.parent_job='9'.repeat(24);
                const raw=$('series-video').value;releaseApp(result);await pending;
                assert.equal(run('seriesUI.draft.expected_draft'),null);assert.equal($('series-video').value,raw);assert.equal(run('seriesUI.child'),null);assert.equal(appCalls.filter(call=>call.path==='/api/jobs').length,0);
                '''.replace('PHASE', json.dumps(phase)))

    def test_pending_post_edit_then_second_save_uses_verified_first_head(self):
        self.dom(REAL_APP_SETUP + r'''
        await loadDraft();draftConsent();enableRealApp();appDeferred={path:'/api/series/draft'};const pending=saveDraft();await settle();const firstBody=copy(appCalls[0].data);
        editVideo('POST beklerken yazılan ikinci senaryo.');setInput('series-continuation-note','Yeni devam notu korunmalı.');setInput('series-approved-by','New reviewer');check('series-draft-rights');check('series-review-pending');
        const editor=$('series-video').value,note=$('series-continuation-note').value,actor=$('series-approved-by').value,result=appCommitDraft(firstBody),firstHead=result.draft_revision;releaseApp(result);await pending;
        assert.equal(run('seriesUI.draft.expected_draft'),firstHead);assert.equal($('series-video').value,editor);assert.equal($('series-continuation-note').value,note);assert.equal($('series-approved-by').value,actor);assert.equal(run('seriesUI.videoDirty'),true);assert.equal($('series-draft-rights').checked,true);assert.equal($('series-review-pending').checked,true);assert.equal(run('seriesUI.child'),null);assert.equal($('series-open').hidden,true);
        await saveDraft();const posts=appCalls.filter(call=>call.path==='/api/series/draft');assert.equal(posts.length,2);assert.equal(posts[1].data.expected_draft,firstHead);assert.equal(posts[1].data.video.script,'POST beklerken yazılan ikinci senaryo.');assert.equal(posts[1].data.approved_by,actor);assert.equal(appSaves,2);assert.equal(run('state.job.id'),jobId);
        ''')

    def test_pending_post_silent_edits_advance_only_commit_metadata(self):
        for field in ['video', 'note', 'actor']:
            with self.subTest(field=field):
                self.dom(REAL_APP_SETUP + r'''
                await loadDraft();draftConsent();enableRealApp();appDeferred={path:'/api/series/draft'};const pending=saveDraft();await settle();const body=copy(appCalls[0].data);
                if(FIELD==='video')$('series-video').value=JSON.stringify(newVideo('Sessiz yeni DOM senaryosu.'));if(FIELD==='note')$('series-continuation-note').value='Sessiz yeni devam notu.';if(FIELD==='actor')$('series-approved-by').value='Silent reviewer';
                const rawFields={video:$('series-video').value,note:$('series-continuation-note').value,actor:$('series-approved-by').value,dirty:run('seriesUI.videoDirty'),rights:$('series-draft-rights').checked,review:$('series-review-pending').checked},result=appCommitDraft(body);releaseApp(result);await pending;
                assert.equal(run('seriesUI.draft.expected_draft'),result.draft_revision);assert.deepEqual({video:$('series-video').value,note:$('series-continuation-note').value,actor:$('series-approved-by').value,dirty:run('seriesUI.videoDirty'),rights:$('series-draft-rights').checked,review:$('series-review-pending').checked},rawFields);assert.equal(run('seriesUI.child'),null);
                await saveDraft();assert.equal(appSaves,2);assert.equal(appCalls.filter(call=>call.path==='/api/series/draft')[1].data.expected_draft,result.draft_revision);
                '''.replace('FIELD', json.dumps(field)))

    def test_pending_post_consent_or_canon_edits_do_not_lose_known_commit(self):
        for change in ['consent', 'consent-restore', 'canon', 'canon-actor']:
            with self.subTest(change=change):
                self.dom(REAL_APP_SETUP + r'''
                await loadDraft();draftConsent();enableRealApp();appDeferred={path:'/api/series/draft'};const pending=saveDraft();await settle();const body=copy(appCalls[0].data);
                if(CHANGE==='consent')check('series-review-pending',false);if(CHANGE==='consent-restore'){check('series-review-pending',false);check('series-review-pending');}if(CHANGE==='canon')setInput('series-canon','{new unfinished canon');if(CHANGE==='canon-actor')setInput('series-accepted-by','New canon reviewer');
                const fields={canon:$('series-canon').value,actor:$('series-accepted-by').value,video:$('series-video').value,videoDirty:run('seriesUI.videoDirty'),canonDirty:run('seriesUI.canonDirty'),rights:$('series-draft-rights').checked,review:$('series-review-pending').checked},result=appCommitDraft(body);releaseApp(result);await pending;
                assert.equal(run('seriesUI.draft.expected_draft'),result.draft_revision);assert.deepEqual({canon:$('series-canon').value,actor:$('series-accepted-by').value,video:$('series-video').value,videoDirty:run('seriesUI.videoDirty'),canonDirty:run('seriesUI.canonDirty'),rights:$('series-draft-rights').checked,review:$('series-review-pending').checked},fields);assert.equal(run('seriesUI.child'),null);if(CHANGE==='consent')assert.equal($('series-draft-save').disabled,true);
                '''.replace('CHANGE', json.dumps(change)))

    def test_two_quick_submits_during_edited_post_do_not_double_dispatch(self):
        self.dom(REAL_APP_SETUP + r'''
        await loadDraft();draftConsent();enableRealApp();appDeferred={path:'/api/series/draft'};const pending=saveDraft();await settle();editVideo('Bekleyen ilk kayıt sırasında yeni taslak.');await saveDraft();await saveDraft();assert.equal(appCalls.length,1);
        const result=appCommitDraft(appCalls[0].data);releaseApp(result);await pending;assert.equal(run('seriesUI.draft.expected_draft'),result.draft_revision);assert.equal(run('seriesUI.child'),null);await saveDraft();assert.equal(appSaves,2);assert.equal(appCalls.filter(call=>call.path==='/api/series/draft').length,2);
        ''')

    def test_pending_post_never_transfers_commit_to_switched_job_or_returned_a(self):
        for returned in [False, True]:
            with self.subTest(returned=returned):
                self.dom(REAL_APP_SETUP + r'''
                await loadDraft();draftConsent();enableRealApp();const other='9'.repeat(24),b=copy(appJobs.get(jobId));b.id=other;b.payload.input.content='Başka değişmez seri işi.';appJobs.set(other,b);appDeferred={path:'/api/series/draft'};const pending=saveDraft();await settle();const body=copy(appCalls[0].data);
                await run(`selectJob('${other}')`);await settle();if(RETURNED){await run(`selectJob('${jobId}')`);await settle();}setInput('series-video','{new local selection draft');const raw=$('series-video').value,result=appCommitDraft(body);releaseApp(result);await pending;
                assert.equal(run('state.job.id'),RETURNED?jobId:other);assert.equal(run('seriesUI.draft'),null);assert.equal($('series-video').value,raw);assert.equal(run('seriesUI.child'),null);
                '''.replace('RETURNED', json.dumps(returned)))

    def test_pending_post_never_transfers_commit_to_changed_previous_or_base(self):
        for mutation in ["$('series-previous').value='9'.repeat(64);$('series-previous').listeners.change[0]()", "const previous=$('series-previous').value;$('series-previous').value='9'.repeat(64);$('series-previous').listeners.change[0]();$('series-previous').value=previous;$('series-previous').listeners.change[0]()", "run('seriesUI.draft.expected_draft=\"8\".repeat(64)')", "run('seriesUI.draft={...seriesUI.draft}')", "run('seriesUI.listing.episodes[0].final_sha256=\"7\".repeat(64)')"]:
            with self.subTest(mutation=mutation):
                self.dom(REAL_APP_SETUP + r'''
                await loadDraft();draftConsent();enableRealApp();appDeferred={path:'/api/series/draft'};const pending=saveDraft();await settle();const body=copy(appCalls[0].data);MUTATION;const localBase=run('JSON.stringify(seriesUI.draft)'),raw=$('series-video').value,result=appCommitDraft(body);releaseApp(result);await pending;
                assert.equal(run('JSON.stringify(seriesUI.draft)'),localBase);assert.equal($('series-video').value,raw);assert.equal(run('seriesUI.child'),null);
                '''.replace('MUTATION', mutation))

    def test_malformed_success_cannot_advance_head_even_when_editor_changed(self):
        for mutation in ["r.parent_job='9'.repeat(24)", "r.previous_revision='9'.repeat(64)", "r.child_job=jobId", "r.child_job='invalid'", "r.draft_revision='invalid'", "r.status='accepted_reference'", "r.publication_ready=true"]:
            with self.subTest(mutation=mutation):
                self.dom(REAL_APP_SETUP + r'''
                await loadDraft();draftConsent();enableRealApp();appDeferred={path:'/api/series/draft'};const pending=saveDraft();await settle();editVideo('Yeni yerel taslak yanlış cevabı kabul etmez.');const r=drafted();MUTATION;const raw=$('series-video').value;releaseApp(r);await pending;assert.equal(run('seriesUI.draft.expected_draft'),null);assert.equal($('series-video').value,raw);assert.equal(run('seriesUI.child'),null);
                '''.replace('MUTATION', mutation))

    def test_real_concurrent_third_head_is_not_silently_rebased(self):
        self.dom(REAL_APP_SETUP + r'''
        await loadDraft();draftConsent();enableRealApp();appDeferred={path:'/api/series/draft'};const pending=saveDraft();await settle();const body=copy(appCalls[0].data);editVideo('Başka oturumla yarışan yeni yerel taslak.');const raw=$('series-video').value,r=appCommitDraft(body),known=r.draft_revision;appHead='7'.repeat(64);releaseApp(r);await pending;
        assert.equal(run('seriesUI.draft.expected_draft'),known);await saveDraft();const posts=appCalls.filter(call=>call.path==='/api/series/draft');assert.equal(posts.length,2);assert.equal(posts[1].data.expected_draft,known);assert.notEqual(posts[1].data.expected_draft,appHead);assert.equal(appSaves,1);assert.equal($('series-video').value,raw);assert.match($('series-status').textContent,/SERIES_DRAFT_HEAD_CHANGED/);assert.equal(run('seriesUI.child'),null);
        ''')

    def test_queue_refresh_failure_preserves_verified_base_for_next_explicit_save(self):
        self.dom(REAL_APP_SETUP + r'''
        await loadDraft();draftConsent();enableRealApp();context.queueError=async()=>{throw Error('Synthetic queue unavailable');};run('refreshJobs=queueError');await saveDraft();
        assert.equal(appSaves,1);assert.equal(run('seriesUI.draft.expected_draft'),appHead);assert.equal(run('seriesUI.child'),null);assert.match($('series-status').textContent,/Taslak kaydı alındı.*iş listesi yenilenemedi.*Otomatik tekrar yapılmadı/);
        const first=appHead;editVideo('Liste hatasından sonra açık yeni taslak.');run('refreshJobs=realRefreshJobs');await saveDraft();assert.equal(appSaves,2);assert.equal(appCalls.filter(call=>call.path==='/api/series/draft')[1].data.expected_draft,first);assert.equal($('series-open').hidden,false);
        ''')

    def test_actual_select_job_get_drops_late_open_after_same_job_draft_edit(self):
        self.dom(REAL_APP_SETUP + r'''
        await realSavedDraft();const saved=run('seriesUI.child.id');appDeferred={path:'/api/jobs/'+saved};const pending=$('series-open').listeners.click[0]();await settle();
        assert.equal(typeof appDeferred.release,'function');editVideo('Aç beklerken A üzerinde yeni yerel taslak.');const raw=$('series-video').value;
        releaseApp(appJobs.get(saved));await pending;await settle();assert.equal(run('state.job.id'),jobId);assert.equal($('series-video').value,raw);assert.equal(run('seriesUI.videoDirty'),true);assert.equal($('series-open').hidden,true);
        ''')

    def test_actual_select_job_get_cannot_roll_back_b_selection_or_b_draft(self):
        self.dom(REAL_APP_SETUP + r'''
        await realSavedDraft();const saved=run('seriesUI.child.id'),other='9'.repeat(24),b=copy(appJobs.get(jobId));b.id=other;b.payload.input.content='Başka değişmez iş.';appJobs.set(other,b);
        appDeferred={path:'/api/jobs/'+saved};const pending=$('series-open').listeners.click[0]();await settle();
        await run(`selectJob('${other}')`);await settle();setInput('series-video','{B new dirty continuation');const raw=$('series-video').value;
        releaseApp(appJobs.get(saved));await pending;await settle();assert.equal(run('state.job.id'),other);assert.equal($('series-video').value,raw);assert.equal(run('seriesUI.videoDirty'),true);
        ''')

    def test_actual_open_guard_checks_silent_form_mutations_and_consent_generation(self):
        for mutation in ["$('series-video').value='{silent newer JSON'", "$('series-approved-by').value='Changed actor'", "check('series-review-pending',false);check('series-review-pending')"]:
            with self.subTest(mutation=mutation):
                self.dom(REAL_APP_SETUP + r'''
                await realSavedDraft();const saved=run('seriesUI.child.id');appDeferred={path:'/api/jobs/'+saved};const pending=$('series-open').listeners.click[0]();await settle();MUTATION;const raw=run('seriesRaw()');
                releaseApp(appJobs.get(saved));await pending;await settle();assert.equal(run('state.job.id'),jobId);assert.equal(run('seriesRaw()'),raw);
                '''.replace('MUTATION', mutation))

    def test_unchanged_explicit_open_uses_real_app_hooks_and_selects_child_once(self):
        self.dom(REAL_APP_SETUP + r'''
        await realSavedDraft();const saved=run('seriesUI.child.id');appDeferred={path:'/api/jobs/'+saved};const pending=$('series-open').listeners.click[0]();await settle();await $('series-open').listeners.click[0]();
        assert.equal(appCalls.filter(call=>call.path==='/api/jobs/'+saved).length,1);releaseApp(appJobs.get(saved));await pending;await settle();
        assert.equal(run('state.job.id'),saved);assert.equal(run('seriesUI.job'),saved);assert.equal($('series-video').value,'');assert.equal(run('seriesUI.child'),null);
        assert.ok(!appCalls.some(call=>/\/render$|\/execute$|\/connect$/.test(call.path)));
        ''')

    def test_no_storage_external_request_or_credential_surface(self):
        for forbidden in ['localStorage', 'sessionStorage', 'innerHTML', 'eval(', 'new Function', 'console.', 'fetch(', 'https://', 'http://']:
            self.assertNotIn(forbidden, SOURCE)
        self.assertNotIn('series-key', HTML)


if __name__ == '__main__':
    unittest.main()
