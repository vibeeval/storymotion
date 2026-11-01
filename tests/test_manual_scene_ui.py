from pack_fixture_case import PackFixtureCase
"""Manual scene editor DOM contracts; mocks only, no native/media/vendor work."""
import json
import shutil
import unittest

import test_llm_ui as ui
from test_compact_ui import MARKUP, ROOT

SOURCE = (ROOT / 'dashboard/scene-plan.js').read_text()
SETUP = r'''
ready();run(MANUAL_SOURCE);
const manualHash='1'.repeat(64),sourceHash='2'.repeat(64),canonHash='3'.repeat(64),childId='d'.repeat(24);
function manualTemplate(account='sample-reflection'){
 const kind=account==='sample-reflection'?'possibility-branches':account==='sample-flow'?'process-route':'clue-inspect';
 const content=kind==='possibility-branches'?{left:'Bir olasılık olabilir.',right:'Başka bir olasılık olabilir.',question:'Hangi ayrıntıyı gözleyebilirim?'}:kind==='process-route'?{nodes:['Girdi','İşlem','Sonuç'],from_node:0,to_node:2}:{clue_id:'pinned-clue',note:'Mevcut nesne izini inceliyorum.'};
 return {plan:{schema_version:1,recipe:'manual-account-scenes-1',account,canon_revision:account==='sample-series'?canonHash:null,scenes:[0,1].map(i=>({scene_id:'beat-'+(i+1),kind,content:{...content},claim_indexes:[],cue_indexes:[i],object_id:'same-object',camera:'locked'}))},expected_video_sha256:manualHash,supported_kinds:account==='sample-reflection'?['observation','possibility-branches']:account==='sample-flow'?['object-transform','process-route']:['canon-board','clue-inspect'],claims:[{text:'Özgün sentetik çizim.',source:'owned',scope:'Yalnız fixture'}],source_binding_sha256:sourceHash,semantic_mapping:'manual_required_not_inferred',review_status:'incomplete',publication_ready:false};
}
function manualJob(account='sample-reflection',id=jobId){return {id,payload:{account:{id:account},format:{adapter:'account-pack'},template:{template:{video:{scenes:[{id:'beat-1',heading:'Yerel bir'},{id:'beat-2',heading:'Yerel iki'}],production_context:{canon:account==='sample-series'?{revision:canonHash,data:{open_clues:[{id:'pinned-clue',object_id:'same-object',description:'Kabul edilmiş aynı nesne izi.'}]}}:null}}}}}};}
function choose(account='sample-reflection',id=jobId){context.manualJobFixture=manualJob(account,id);run('state.job=manualJobFixture;state.jobEpoch++;manualSceneJobChanged(state.job)');}
async function load(account='sample-reflection'){
 choose(account);context.template=manualTemplate(account);context.mockApi=async(path,data)=>{assert.equal(path,'/api/jobs/'+jobId+'/scene-plan-template');assert.deepEqual(JSON.parse(JSON.stringify(data)),{});return context.template;};run('api=mockApi');await $('manual-load').listeners.click[0]();
}
function scene(index){$('manual-scene').value=String(index);$('manual-scene').listeners.change[0]();}
function input(id,value){$(id).value=value;for(const listener of $(id).listeners.input||[])listener();}
function approve(){for(let i=0;i<2;i++){scene(i);input('manual-claims','0');}input('manual-approved-by','Synthetic local reviewer');$('manual-ack').checked=true;$('manual-ack').listeners.change[0]();}
function submit(){return $('manual-form').listeners.submit[0]({preventDefault(){}});}
const saved=()=>({parent_job:jobId,child_job:childId,publication_ready:false,provider_calls:0,render_started:false});
'''.replace('MANUAL_SOURCE', json.dumps(SOURCE))


@unittest.skipUnless(shutil.which('node'), 'Node required for offline manual scene UI')
class ManualSceneUI(PackFixtureCase):
    def dom(self, body):
        ui.WriterUi().dom(SETUP + body)

    def test_closed_native_disclosure_labels_and_readonly_references(self):
        ids = [n['attrs']['id'] for n in MARKUP.nodes if 'id' in n['attrs']]
        self.assertEqual(len(ids), len(set(ids)))
        labels = {n['attrs'].get('for') for n in MARKUP.nodes if n['tag'] == 'label'}
        for id_ in ['manual-scene', 'manual-kind', 'manual-content', 'manual-claims', 'manual-camera', 'manual-approved-by', 'manual-ack']:
            self.assertIn(id_, labels)
        step = next(n for n in MARKUP.nodes if n['attrs'].get('id') == 'manual-step')
        self.assertEqual(step['tag'], 'details')
        self.assertNotIn('open', step['attrs'])
        children = [n for n in MARKUP.nodes if n['parent'] == MARKUP.nodes.index(step)]
        self.assertEqual(children[0]['tag'], 'summary')
        self.assertEqual(next(n for n in MARKUP.nodes if n['attrs'].get('id') == 'manual-refs')['tag'], 'pre')
        editor_limit = int(next(n for n in MARKUP.nodes if n['attrs'].get('id') == 'manual-content')['attrs']['maxlength'])
        self.assertGreater(editor_limit, 0)
        self.assertLessEqual(editor_limit, 6000)
        self.assertIn('required', next(n for n in MARKUP.nodes if n['attrs'].get('id') == 'manual-ack')['attrs'])

    def test_only_original_and_audio_three_profile_jobs_are_supported_without_calls(self):
        self.dom(r'''
        let calls=0;context.mockApi=async()=>{calls++;throw Error('Unexpected API');};run('api=mockApi');
        for(const account of ['sample-reflection','sample-flow','sample-series']){choose(account);assert.equal($('manual-step').hidden,false);assert.equal($('manual-form').hidden,true);assert.equal($('manual-open').hidden,true);}
        for(const revision of ['edit_revision','raster_revision','scene_plan_revision']){choose();context.changed={...manualJob(),payload:{...manualJob().payload,[revision]:{parent_job:'x'}}};run('state.job=changed;manualSceneJobChanged(changed)');assert.equal($('manual-step').hidden,true,revision);await $('manual-load').listeners.click[0]();}
        choose('sample-mechanism');assert.equal($('manual-step').hidden,true);choose();run("state.job.payload.format.adapter='hyperframes-fixture';manualSceneJobChanged(state.job)");assert.equal($('manual-step').hidden,true);
        choose();run('state.job.payload.audio_revision={};manualSceneJobChanged(state.job)');assert.equal($('manual-step').hidden,false);assert.equal(calls,0);
        ''')

    def test_three_template_contracts_and_pinned_refs_do_not_claim_semantic_acceptance(self):
        self.dom(r'''
        for(const account of ['sample-reflection','sample-flow','sample-series']){
         await load(account);assert.equal($('manual-form').hidden,false);assert.equal($('manual-kind').children.length,2);assert.equal($('manual-submit').disabled,true);
         assert.equal($('manual-claims').required,account!=='sample-series');assert.equal($('manual-claims').value,'');
         const refs=JSON.parse($('manual-refs').textContent);assert.equal(refs.scene_id,'beat-1');assert.equal(refs.object_id,'same-object');assert.deepEqual(refs.cue_indexes,[0]);assert.equal(refs.claims[0].index,0);
         assert.equal(refs.source_binding_sha256,sourceHash);assert.equal(refs.review_status,'incomplete');assert.match($('manual-status').textContent,/elle eşleştirin.*yapılmadı/);
         if(account==='sample-series')assert.equal(refs.canon_revision,canonHash);
        }
        ''')

    def test_scene_and_kind_switches_preserve_raw_drafts_including_invalid_json(self):
        self.dom(r'''
        await load();input('manual-content','{invalid unfinished');input('manual-claims','0');$('manual-camera').value='push-in';$('manual-camera').listeners.change[0]();scene(1);input('manual-content',JSON.stringify({left:'Başka sahne.',right:'İkinci olasılık.',question:'Hangi ayrıntı?'}));scene(0);
        assert.equal($('manual-content').value,'{invalid unfinished');assert.equal($('manual-claims').value,'0');assert.equal($('manual-camera').value,'push-in');assert.equal($('manual-submit').disabled,true);
        $('manual-kind').value='observation';$('manual-kind').listeners.change[0]();assert.equal(JSON.parse($('manual-content').value).object,'clock');
        input('manual-content',JSON.stringify({object:'chair',prompt:'Hangi ayrıntı?',observation:'Yalnız görünen ayrıntı.'}));$('manual-kind').value='possibility-branches';$('manual-kind').listeners.change[0]();assert.equal($('manual-content').value,'{invalid unfinished');
        $('manual-kind').value='observation';$('manual-kind').listeners.change[0]();assert.equal(JSON.parse($('manual-content').value).object,'chair');
        ''')

    def test_kind_defaults_are_profile_scoped_and_serial_clues_are_existing(self):
        self.dom(r'''
        for(const account of ['sample-reflection','sample-flow','sample-series']){
          await load(account);for(const option of $('manual-kind').children){$('manual-kind').value=option.value;$('manual-kind').listeners.change[0]();const content=JSON.parse($('manual-content').value);if(option.value==='process-route')assert.deepEqual(content.nodes,['Girdi','İşlem','Sonuç']);if(option.value==='object-transform')assert.equal(content.object,'document');if(option.value==='observation')assert.equal(content.object,'clock');if(option.value==='canon-board')assert.deepEqual(content.clue_ids,['pinned-clue']);if(option.value==='clue-inspect')assert.equal(content.clue_id,'pinned-clue');}
        }
        input('manual-content',JSON.stringify({clue_id:'invented-clue',note:'Bir not.'}));approve();assert.equal($('manual-submit').disabled,true);
        ''')

    def test_claim_indexes_are_explicit_unique_bounded_and_required_for_every_scene(self):
        for account in ['sample-reflection', 'sample-flow']:
            with self.subTest(account=account):
                self.dom(r'''
                await load(ACCOUNT);const calls=[];context.mockApi=async path=>{calls.push(path);};run('api=mockApi');
                input('manual-approved-by','Reviewer');$('manual-ack').checked=true;$('manual-ack').listeners.change[0]();assert.equal($('manual-submit').disabled,true);
                for(const invalid of ['', '-1', '0.5', '0, 0', '1', '0,']){approve();input('manual-claims',invalid);$('manual-ack').checked=true;$('manual-ack').listeners.change[0]();await submit();assert.equal($('manual-submit').disabled,true,invalid);}
                approve();scene(0);input('manual-claims','');scene(1);$('manual-ack').checked=true;$('manual-ack').listeners.change[0]();assert.equal($('manual-submit').disabled,true);assert.deepEqual(calls,[]);
                '''.replace('ACCOUNT', json.dumps(account)))

    def test_exact_save_payload_retains_pinned_refs_and_never_auto_opens_child(self):
        self.dom(r'''
        await load();approve();$('manual-refs').textContent='Changed display only';$('manual-camera').value='follow-object';$('manual-camera').listeners.change[0]();$('manual-ack').checked=true;$('manual-ack').listeners.change[0]();
        const calls=[],selected=[];context.mockApi=async(path,data)=>{calls.push({path,data});return saved();};context.sel=async id=>selected.push(id);run('api=mockApi;selectJob=sel;refreshJobs=async()=>{}');
        await submit();assert.equal(calls.length,1);assert.equal(calls[0].path,'/api/jobs/'+jobId+'/scene-plan');const body=calls[0].data;
        assert.deepEqual(Object.keys(body).sort(),['approved_by','expected_video_sha256','plan','review_pending']);assert.equal(body.expected_video_sha256,manualHash);assert.equal(body.approved_by,'Synthetic local reviewer');assert.equal(body.review_pending,true);
        for(const [i,item] of body.plan.scenes.entries()){assert.equal(item.scene_id,'beat-'+(i+1));assert.equal(item.object_id,'same-object');assert.deepEqual(Array.from(item.cue_indexes),[i]);assert.deepEqual(Array.from(item.claim_indexes),[0]);}
        assert.equal(body.plan.scenes[1].camera,'follow-object');assert.equal(run('state.job.id'),jobId);assert.deepEqual(selected,[]);assert.equal($('manual-open').hidden,false);
        await $('manual-open').listeners.click[0]();assert.deepEqual(selected,[childId]);assert.ok(!calls.some(x=>/render|execute|connect|elevenlabs/.test(x.path)));
        ''')

    def test_double_load_and_save_clicks_post_once(self):
        self.dom(r'''
        choose();context.template=manualTemplate();let release;const calls=[];context.mockApi=async(path,data)=>{calls.push(path);return new Promise(resolve=>release=resolve);};run('api=mockApi;refreshJobs=async()=>{}');
        const loading=$('manual-load').listeners.click[0]();await settle();await $('manual-load').listeners.click[0]();assert.equal(calls.length,1);release(context.template);await loading;approve();
        const saving=submit();await settle();await submit();assert.equal(calls.length,2);release(saved());await saving;assert.equal(calls.length,2);assert.equal($('manual-open').hidden,false);
        ''')

    def test_late_reload_cannot_overwrite_new_dirty_raw_fields(self):
        self.dom(r'''
        await load();input('manual-content','{first dirty draft');let release;context.mockApi=()=>new Promise(resolve=>release=resolve);run('api=mockApi');
        const pending=$('manual-load').listeners.click[0]();await settle();input('manual-content','{new dirty draft');release(manualTemplate());await pending;
        assert.equal($('manual-content').value,'{new dirty draft');assert.equal(run('manualSceneUI.dirty'),true);assert.equal($('manual-open').hidden,true);
        ''')

    def test_late_load_for_changed_job_or_account_does_not_reveal_old_form(self):
        for mutation in ["choose('sample-flow','e'.repeat(24))", "run('state.epoch++;state.account=state.catalog.accounts.find(a=>a.id===\"sample-series\");manualSceneJobChanged(null)')"]:
            with self.subTest(mutation=mutation):
                self.dom(r'''
                choose();let release;context.mockApi=()=>new Promise(resolve=>release=resolve);run('api=mockApi');const pending=$('manual-load').listeners.click[0]();await settle();MUTATION;
                $('manual-content').value='Next local draft';release(manualTemplate());await pending;assert.equal($('manual-content').value,'Next local draft');assert.equal($('manual-form').hidden,true);assert.equal($('manual-open').hidden,true);
                '''.replace('MUTATION', mutation))

    def test_pending_save_snapshot_rejects_event_and_silent_context_changes(self):
        mutations = [
            "input('manual-content','{new raw draft')",
            "$('manual-content').value='{}'",
            "$('manual-kind').value='observation'",
            "$('manual-claims').value=''",
            "$('manual-camera').value='push-in'",
            "$('manual-approved-by').value='New reviewer'",
            "$('manual-ack').checked=false",
            "run('state.jobEpoch++')",
            "run('state.epoch++')",
            "run('state.account=state.catalog.accounts.find(a=>a.id===\"sample-series\")')",
            "run('manualSceneUI.drafts[0].content=\"{}\"')",
            "run('manualSceneUI.base.expected_video_sha256=\"9\".repeat(64)')",
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.dom(r'''
                await load();approve();let release;const calls=[];context.mockApi=path=>{calls.push(path);return new Promise(resolve=>release=resolve);};context.refresh=async()=>calls.push('refreshJobs');run('api=mockApi;refreshJobs=refresh');
                const pending=submit();await settle();MUTATION;release(saved());await pending;assert.deepEqual(calls,['/api/jobs/'+jobId+'/scene-plan']);assert.equal($('manual-open').hidden,true);assert.equal(run('state.job.id'),jobId);
                '''.replace('MUTATION', mutation))

    def test_save_then_queue_refresh_cannot_reveal_child_after_new_edit(self):
        self.dom(r'''
        await load();approve();let release;context.mockApi=async()=>saved();context.refresh=()=>new Promise(resolve=>release=resolve);run('api=mockApi;refreshJobs=refresh');
        const pending=submit();await settle();input('manual-content','{new draft during queue read');release();await pending;
        assert.equal($('manual-open').hidden,true);assert.equal($('manual-content').value,'{new draft during queue read');
        ''')

    def test_rechecking_consent_cannot_restore_inflight_old_snapshot(self):
        self.dom(r'''
        await load();approve();let release;context.mockApi=()=>new Promise(resolve=>release=resolve);run('api=mockApi;refreshJobs=async()=>{}');
        const pending=submit();await settle();$('manual-ack').checked=false;$('manual-ack').listeners.change[0]();$('manual-ack').checked=true;$('manual-ack').listeners.change[0]();release(saved());await pending;assert.equal($('manual-open').hidden,true);
        ''')

    def test_same_job_render_hook_keeps_drafts_and_new_job_clears_them(self):
        self.dom(r'''
        await load();input('manual-content','{preserved raw draft');run('manualSceneJobChanged(state.job)');assert.equal($('manual-content').value,'{preserved raw draft');assert.equal($('manual-form').hidden,false);
        choose('sample-reflection','e'.repeat(24));assert.equal($('manual-content').value,'');assert.equal($('manual-form').hidden,true);assert.equal($('manual-open').hidden,true);
        ''')

    def test_template_failure_preserves_dirty_editor_and_does_not_retry(self):
        self.dom(r'''
        await load();input('manual-content','{kept draft');let calls=0;context.mockApi=async()=>{calls++;throw Error('Synthetic template failure');};run('api=mockApi');await $('manual-load').listeners.click[0]();
        assert.equal(calls,1);assert.equal($('manual-content').value,'{kept draft');assert.match($('manual-status').textContent,/Synthetic template failure/);assert.equal($('manual-open').hidden,true);
        ''')

    def test_malformed_template_or_cross_profile_kinds_fail_closed(self):
        for mutation in ["data.expected_video_sha256='invalid'", "data.supported_kinds=['clue-inspect']", "data.plan.account='sample-series'", "data.semantic_mapping='verified'", "data.review_status='pass'", "data.plan.scenes[0].object_id='../file'", "data.plan.scenes[0].cue_indexes=[0,0]"]:
            with self.subTest(mutation=mutation):
                self.dom(r'''
                choose();const data=manualTemplate();MUTATION;context.data=data;context.mockApi=async()=>data;run('api=mockApi');await $('manual-load').listeners.click[0]();assert.equal($('manual-form').hidden,true);assert.equal($('manual-submit').disabled,true);assert.match($('manual-status').textContent,/doğrulanamadı/);
                '''.replace('MUTATION', mutation))

    def test_bad_child_binding_or_error_never_creates_open_link(self):
        for mutation in ["data.parent_job='e'.repeat(24)", "data.child_job='invalid'", 'data.publication_ready=true', 'data.child_job=jobId', "throw Error('Synthetic save failure')"]:
            with self.subTest(mutation=mutation):
                self.dom(r'''
                await load();approve();let calls=0;context.mockApi=async()=>{calls++;const data=saved();MUTATION;return data;};run('api=mockApi;refreshJobs=async()=>{throw Error("No refresh expected")};');await submit();assert.equal(calls,1);assert.equal($('manual-open').hidden,true);assert.match($('manual-status').textContent,/doğrulanamadı|Synthetic save failure/);
                '''.replace('MUTATION', mutation))

    def test_no_storage_code_evaluation_or_external_network_surface(self):
        for forbidden in ['localStorage', 'sessionStorage', 'innerHTML', 'eval(', 'new Function', 'console.', 'fetch(', 'http://', 'https://']:
            self.assertNotIn(forbidden, SOURCE)


if __name__ == '__main__':
    unittest.main()
