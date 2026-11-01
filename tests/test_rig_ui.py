from pack_fixture_case import PackFixtureCase
"""Offline neutral rig import contracts; synthetic annotations and mocked HTTP only."""
import json
import shutil
import unittest

import test_llm_ui as ui
from test_compact_ui import CSS, HTML, JS, MARKUP, ROOT

SOURCE = (ROOT / 'dashboard/rig-panel.js').read_text()
SETUP = r'''
ready();context.TextEncoder=TextEncoder;run(RIG_SOURCE);
const sourceId='c'.repeat(24),rigChild='d'.repeat(24),otherId='e'.repeat(24),videoHash='f'.repeat(64),descriptorHash='a'.repeat(64);
const descriptor=()=>({schema_version:1,rig_id:'neutral-presenter-1',sha256:descriptorHash,file:'renderers/neutral-rig.json',license:'original_project_vectors'});
function clone(value){return JSON.parse(JSON.stringify(value));}
function sourceJob(account='sample-flow',id=sourceId){return {id,status:'prepared',files:[],payload:{account:{id:account},format:{adapter:'account-pack',name:'Yerel konu'},input:{title:'Sentetik rig örneği',content:'Yalnız sentetik metin.'},template:{template:{video:{brand:account,script:'Yalnız sentetik metin.',audio:{sha256:'b'.repeat(64),file:'synthetic.wav'},audio_timing:{schema_version:1,audio_duration_seconds:2,timeline_duration_seconds:3}}}}}};}
function templateSpec(account='sample-flow'){return {schema_version:1,account,rig_id:'neutral-presenter-1',rig_sha256:descriptorHash,source_audio_sha256:'b'.repeat(64),source_script_sha256:'c'.repeat(64),source_timing_sha256:'d'.repeat(64),audio_duration_seconds:2,timeline_duration_seconds:3,fps:30,provenance:{method:'manual_annotation',tool:'manual',note:'Synthetic local test; not acoustic evidence.',approved_by:'operator',rights_confirmed:false,human_phonetic:'pending',human_visual:'pending'},mouthCues:[],visual_tracks:{blinks:[],head:[{time:0,rotate:0,x:0,y:0},{time:3,rotate:0,x:0,y:0}]}};}
function rigTemplate(){return {job:run('rigSourceJob()'),expected_video_sha256:videoHash,rig_descriptor:descriptor(),spec:templateSpec(run('state.job.payload.account.id')),warning:'Boş mouthCues kasıtlıdır; otomatik fonem üretilmez.'};}
function filledSpec(method='manual_annotation'){const s=templateSpec(run('state.job.payload.account.id'));s.provenance={...s.provenance,method,approved_by:'Synthetic reviewer',rights_confirmed:true};s.mouthCues=[{start:0,end:1,value:'A'},{start:1,end:2,value:'X'}];return s;}
function selected(account='sample-flow',id=sourceId,job=null){context.sourceFixture=job||sourceJob(account,id);run("state.account=state.catalog.accounts.find(a=>a.id==='"+account+"');state.job=sourceFixture;state.jobEpoch++;rigJobChanged(state.job);tab('qa')");}
function input(id,value){$(id).value=value;for(const fn of $(id).listeners.input||[])fn();}
function change(id,value){$(id).value=value;for(const fn of $(id).listeners.change||[])fn();}
function rights(value=true){$('rig-rights').checked=value;for(const fn of $('rig-rights').listeners.change||[])fn();}
function fill(method='manual_annotation'){input('rig-json',JSON.stringify(filledSpec(method)));input('rig-approved-by','Synthetic reviewer');change('rig-method',method);rights();}
function imported(){const parent=run('rigSourceJob()'),job=sourceJob(run('state.job.payload.account.id'),rigChild);job.status='queued';job.payload.rig_revision={parent_job:parent};return {parent_job:parent,child_job:rigChild,job,reused:false,provider_calls:0,render_started:false,publication_ready:false,human_phonetic:'pending',human_visual:'pending'};}
function mockDefault(){context.rigApi=async(path,data)=>{if(path.endsWith('/rig-template'))return rigTemplate();if(path.endsWith('/rig-import'))return imported();throw Error('Unexpected rig API '+path);};run('api=rigApi;refreshJobs=async()=>{}');}
async function loaded(account='sample-flow',id=sourceId,job=null){selected(account,id,job);mockDefault();await $('rig-load').listeners.click[0]();}
function submit(){return $('rig-form').listeners.submit[0]({preventDefault(){}});}
function fileChanged(file){$('rig-file').files=file?[file]:[];for(const fn of $('rig-file').listeners.change||[])return fn();}
const realSelect=run('selectJob'),realRefresh=run('refreshJobs');
const appCalls=[],appJobs=new Map();let appDeferred=null;
function actualApp(){appJobs.set(run('state.job.id'),clone(run('state.job')));context.actualApi=async(path,data)=>{
 appCalls.push({path,data});if(appDeferred?.path===path)return new Promise(resolve=>appDeferred.release=resolve);
 if(path==='/api/jobs')return {jobs:[...appJobs.values()].map(clone)};
 if(path==='/api/elevenlabs/state')return {requests:[]};
 const match=path.match(/^\/api\/jobs\/([a-f0-9]{24})(?:\/(.+))?$/);
 if(match&&!match[2]){assert.ok(appJobs.has(match[1]));return clone(appJobs.get(match[1]));}
  if(match?.[2]==='render-state')return {status:'not_started',files:{}};
  if(['check','prepare'].includes(match?.[2]))return {status:'prepared'};
 if(match?.[2]==='rig-import'){const result=imported();appJobs.set(result.child_job,result.job);return result;}
 if(match?.[2]==='rig-template')return rigTemplate();
 throw Error('Unexpected actual app request '+path);
};context.realSelect=realSelect;context.realRefresh=realRefresh;run('api=actualApi;selectJob=realSelect;refreshJobs=realRefresh');}
async function actualSaved(){await loaded();fill();actualApp();await submit();assert.equal($('rig-open').hidden,false);}
function releaseApp(value){const release=appDeferred.release;assert.equal(typeof release,'function');appDeferred=null;release(clone(value));}
'''.replace('RIG_SOURCE', json.dumps(SOURCE))


@unittest.skipUnless(shutil.which('node'), 'Node required for offline rig DOM contracts')
class RigUI(PackFixtureCase):
    def dom(self, body):
        ui.WriterUi().dom(SETUP + body)

    def test_native_compact_panel_unique_ids_labels_and_honest_copy(self):
        ids = [n['attrs']['id'] for n in MARKUP.nodes if 'id' in n['attrs']]
        self.assertEqual(len(ids), len(set(ids)))
        panel = next(n for n in MARKUP.nodes if n['attrs'].get('id') == 'rig-panel')
        self.assertEqual(panel['tag'], 'details')
        self.assertNotIn('open', panel['attrs'])
        children = [n for n in MARKUP.nodes if n['parent'] == MARKUP.nodes.index(panel)]
        self.assertEqual(children[0]['tag'], 'summary')
        labels = {n['attrs'].get('for') for n in MARKUP.nodes if n['tag'] == 'label'}
        for node in MARKUP.nodes:
            if node['tag'] in {'input', 'textarea', 'select'} and node['attrs'].get('id', '').startswith('rig-'):
                self.assertIn(node['attrs']['id'], labels)
        attrs = {n['attrs'].get('id'): n['attrs'] for n in MARKUP.nodes}
        self.assertEqual(attrs['rig-json']['maxlength'], '110000')
        self.assertEqual(attrs['rig-approved-by']['maxlength'], '200')
        self.assertIn('required', attrs['rig-rights'])
        self.assertNotIn('checked', attrs['rig-rights'])
        self.assertIn('summary:focus-visible', CSS)
        self.assertIn('.connection-details', CSS)
        self.assertIn('Otomatik fonem üretimi yoktur', HTML)
        self.assertIn('sağlayıcı çağrısı veya render başlatmaz', HTML)
        self.assertIn('human_phonetic ve human_visual pending', HTML)

    def test_support_status_and_input_changes_never_dispatch(self):
        self.dom(r'''
        let calls=0;context.noApi=async()=>{calls++;throw Error('No automatic call');};run('api=noApi');
        for(const account of ['sample-reflection','sample-mechanism']){selected(account);assert.equal($('rig-load').disabled,true);assert.match($('rig-support').textContent,/yalnız.*Teknoloji.*Gizemli/);}
        for(const account of ['sample-flow','sample-series']){selected(account);assert.equal($('rig-load').disabled,false);const noAudio=sourceJob(account);delete noAudio.payload.template.template.video.audio_timing;selected(account,sourceId,noAudio);assert.equal($('rig-load').disabled,true);assert.match($('rig-support').textContent,/Önce.*sesi/);}
        for(const key of ['edit_revision','raster_revision','scene_plan_revision']){const job=sourceJob();job.payload[key]={};selected('sample-flow',sourceId,job);assert.equal($('rig-load').disabled,true);assert.match($('rig-support').textContent,/Görsel revizyondan önceki/);}
        input('rig-json','{draft');input('rig-approved-by','Reviewer');rights();assert.equal(calls,0);assert.equal($('rig-submit').disabled,true);
        ''')

    def test_template_has_empty_cues_fixed_sources_and_no_automatic_rights(self):
        self.dom(r'''
        await loaded();assert.equal($('rig-form').hidden,false);assert.equal($('rig-panel').open,false);const spec=JSON.parse($('rig-json').value);
        assert.deepEqual(spec.mouthCues,[]);assert.equal(spec.provenance.rights_confirmed,false);assert.equal(spec.provenance.human_phonetic,'pending');assert.equal(spec.provenance.human_visual,'pending');assert.equal($('rig-rights').checked,false);assert.equal($('rig-approved-by').value,'');assert.equal($('rig-submit').disabled,true);
        assert.ok($('rig-source').textContent.includes(videoHash));assert.ok($('rig-source').textContent.includes(descriptorHash));assert.match($('rig-status').textContent,/Boş.*otomatik fonem/);
        ''')

    def test_existing_rig_job_resolves_source_without_changing_selected_job(self):
        self.dom(r'''
        const job=sourceJob('sample-series',otherId);job.payload.rig_revision={parent_job:sourceId};await loaded('sample-series',otherId,job);fill();
        assert.equal(run('rigUI.base.source_job'),sourceId);const calls=[];context.mockApi=async(path,data)=>{calls.push({path,data});return imported();};run('api=mockApi');await submit();assert.equal(calls[0].path,'/api/jobs/'+otherId+'/rig-import');assert.equal(run('state.job.id'),otherId);assert.equal($('rig-open').hidden,false);
        ''')

    def test_exact_import_payload_single_pending_post_and_no_auto_selection(self):
        self.dom(r'''
        await loaded();fill();const sent=JSON.parse($('rig-json').value),calls=[];let release;context.mockApi=(path,data)=>{calls.push({path,data});return new Promise(resolve=>release=resolve);};run('api=mockApi');const pending=submit();await settle();await submit();assert.equal(calls.length,1);assert.equal($('rig-submit').disabled,true);
        assert.equal(calls[0].path,'/api/jobs/'+sourceId+'/rig-import');assert.deepEqual(Object.keys(calls[0].data).sort(),['approved_by','expected_video_sha256','review_pending','spec']);assert.equal(calls[0].data.expected_video_sha256,videoHash);assert.equal(calls[0].data.approved_by,sent.provenance.approved_by);assert.equal(calls[0].data.review_pending,true);assert.deepEqual(clone(calls[0].data.spec),sent);
        release(imported());await pending;assert.equal(run('state.job.id'),sourceId);assert.equal($('rig-open').hidden,false);assert.match($('rig-status').textContent,/otomatik render.*insan QA kabulü yapılmadı/);assert.equal($('rig-json').value,JSON.stringify(sent));
        ''')

    def test_methods_require_matching_json_and_never_claim_acoustic_verification(self):
        self.dom(r'''
        await loaded();for(const method of ['manual_annotation','external_phoneme_export','synthetic_test']){fill(method);assert.equal($('rig-submit').disabled,false);assert.equal(JSON.parse($('rig-json').value).provenance.human_phonetic,'pending');}
        change('rig-method','manual_annotation');rights();assert.equal($('rig-submit').disabled,true);
        ''')

    def test_rights_actor_human_state_and_source_bindings_fail_closed(self):
        for mutation in ["s.provenance.rights_confirmed=false", "s.provenance.approved_by='Another actor'", "s.provenance.human_phonetic='pass'", "s.provenance.human_visual='accepted'", "s.provenance.method='automatic'", "s.source_audio_sha256='0'.repeat(64)", "s.source_script_sha256='0'.repeat(64)", "s.source_timing_sha256='0'.repeat(64)", "s.rig_sha256='0'.repeat(64)", "s.audio_duration_seconds=1", "s.fps=24", "s.mouthCues=[]", "s.url='https://invalid.example/data'", "s.provenance.tool=''", "s.provenance.note=''"]:
            with self.subTest(mutation=mutation):
                self.dom(r'''
                await loaded();fill();const s=filledSpec();MUTATION;input('rig-json',JSON.stringify(s));rights();assert.equal($('rig-submit').disabled,true);let calls=0;context.noApi=async()=>calls++;run('api=noApi');await submit();assert.equal(calls,0);
                '''.replace('MUTATION', mutation))

    def test_cue_intervals_must_be_explicit_contiguous_bounded_and_complete(self):
        for cues in [[], [{'start':0.1,'end':2,'value':'A'}], [{'start':0,'end':1,'value':'A'}], [{'start':0,'end':1,'value':'A'},{'start':1.1,'end':2,'value':'X'}], [{'start':0,'end':2,'value':'phoneme-aa'}], [{'start':0,'end':3,'value':'X'}]]:
            with self.subTest(cues=cues):
                self.dom(r'''
                await loaded();fill();const s=filledSpec();s.mouthCues=CUES;input('rig-json',JSON.stringify(s));rights();assert.equal($('rig-submit').disabled,true);
                '''.replace('CUES', json.dumps(cues)))

    def test_invalid_template_proof_never_clobbers_existing_editor(self):
        for mutation in ["t.job=otherId", "t.expected_video_sha256='invalid'", "t.spec.rig_sha256='0'.repeat(64)", "t.spec.provenance.human_visual='pass'", "t.spec.provenance.rights_confirmed=true", "t.spec.mouthCues=[{start:0,end:2,value:'X'}]"]:
            with self.subTest(mutation=mutation):
                self.dom(r'''
                await loaded();input('rig-json','{retained draft');const t=rigTemplate();MUTATION;context.mockApi=async()=>t;run('api=mockApi');await $('rig-load').listeners.click[0]();assert.equal($('rig-json').value,'{retained draft');assert.match($('rig-status').textContent,/şablonu.*eşleşmedi/);
                '''.replace('MUTATION', mutation))

    def test_json_file_is_local_text_only_and_keeps_explicit_rights_off(self):
        self.dom(r'''
        await loaded();let reads=0,calls=0;const text=JSON.stringify(filledSpec('external_phoneme_export'));context.noApi=async()=>{calls++;throw Error('No network');};run('api=noApi');
        await fileChanged({name:'my-rig.JSON',size:Buffer.byteLength(text),type:'application/json',lastModified:1,text:async()=>{reads++;return text;}});
        assert.equal(reads,1);assert.equal(calls,0);assert.equal($('rig-json').value,text);assert.equal($('rig-method').value,'external_phoneme_export');assert.equal($('rig-approved-by').value,'Synthetic reviewer');assert.equal($('rig-rights').checked,false);assert.equal($('rig-submit').disabled,true);rights();assert.equal($('rig-submit').disabled,false);
        ''')

    def test_file_limits_invalid_json_and_non_json_files_preserve_editor(self):
        for variant in ['oversize','svg','empty','invalid','array','actual-oversize','utf8-oversize']:
            with self.subTest(variant=variant):
                self.dom(r'''
                await loaded();input('rig-json','{retained editor');const before=$('rig-json').value;let reads=0;
                const f={name:'rig.json',size:20,text:async()=>{reads++;return '{}';}};
                if(VARIANT==='oversize')f.size=110001;if(VARIANT==='svg')f.name='rig.svg';if(VARIANT==='empty')f.size=0;if(VARIANT==='invalid')f.text=async()=>'{invalid';if(VARIANT==='array')f.text=async()=>'[]';if(VARIANT==='actual-oversize')f.text=async()=>JSON.stringify({s:'x'.repeat(110001)});if(VARIANT==='utf8-oversize')f.text=async()=>JSON.stringify({s:'ş'.repeat(60000)});
                await fileChanged(f);assert.equal($('rig-json').value,before);assert.equal($('rig-rights').checked,false);if(['oversize','svg','empty'].includes(VARIANT))assert.equal(reads,0);assert.equal($('rig-submit').disabled,true);
                '''.replace('VARIANT', json.dumps(variant)))

    def test_imported_script_url_or_svg_strings_are_inert_editor_data(self):
        self.dom(r'''
        await loaded();const s=filledSpec();s.provenance.note='<svg onload="throw 1"><script>throw 1</script></svg> https://invalid.example';const text=JSON.stringify(s);await fileChanged({name:'rig.json',size:Buffer.byteLength(text),text:async()=>text});assert.equal($('rig-json').value,text);assert.equal($('rig-json').children.length,0);assert.equal($('rig-rights').checked,false);assert.equal(run('rigUI.child'),null);
        ''')

    def test_late_template_and_file_reads_cannot_replace_dirty_editor_or_b_selection(self):
        for phase in ['template','file','file-switch']:
            with self.subTest(phase=phase):
                self.dom(r'''
                await loaded();let release;const t=rigTemplate();let pending;
                if(PHASE==='template'){context.mockApi=()=>new Promise(resolve=>release=resolve);run('api=mockApi');pending=$('rig-load').listeners.click[0]();}else pending=fileChanged({name:'rig.json',size:100,text:()=>new Promise(resolve=>release=resolve)});
                await settle();if(PHASE==='file-switch')selected('sample-series',otherId);input('rig-json','{newer dirty JSON');const raw=$('rig-json').value;release(PHASE==='template'?t:JSON.stringify(filledSpec()));await pending;
                assert.equal($('rig-json').value,raw);assert.equal(run('state.job.id'),PHASE==='file-switch'?otherId:sourceId);assert.equal($('rig-open').hidden,true);
                '''.replace('PHASE', json.dumps(phase)))

    def test_late_save_and_queue_refresh_preserve_new_editor_and_hide_old_child(self):
        for phase in ['save','refresh']:
            with self.subTest(phase=phase):
                self.dom(r'''
                await loaded();fill();let release;context.mockApi=()=>PHASE==='save'?new Promise(resolve=>release=resolve):Promise.resolve(imported());context.waitQueue=()=>PHASE==='refresh'?new Promise(resolve=>release=resolve):Promise.resolve();run('api=mockApi;refreshJobs=waitQueue');const pending=submit();await settle();input('rig-json','{new edit during '+PHASE);release(PHASE==='save'?imported():undefined);await pending;
                assert.equal($('rig-json').value,'{new edit during '+PHASE);assert.equal(run('state.job.id'),sourceId);assert.equal(run('rigUI.child'),null);assert.equal($('rig-open').hidden,true);
                '''.replace('PHASE', json.dumps(phase)))

    def test_context_and_consent_generations_drop_pending_import_response(self):
        for mutation in ["run('state.jobEpoch++')", "run('state.epoch++')", "run('state.job.payload.template.template.video.script=\"Changed source\"')", "run('state.account=state.catalog.accounts.find(a=>a.id===\"sample-series\")')", "$('rig-json').value='{}'", "$('rig-approved-by').value='Silent changed actor'", "rights(false);rights()", "const old=$('rig-json').value;input('rig-json','{}');input('rig-json',old);rights()"]:
            with self.subTest(mutation=mutation):
                self.dom(r'''
                await loaded();fill();let release;context.mockApi=()=>new Promise(resolve=>release=resolve);run('api=mockApi');const pending=submit();await settle();MUTATION;const raw=$('rig-json').value;release(imported());await pending;assert.equal($('rig-json').value,raw);assert.equal(run('rigUI.child'),null);assert.equal($('rig-open').hidden,true);
                '''.replace('MUTATION', mutation))

    def test_same_immutable_job_refresh_preserves_dirty_editor_but_invalidates_proof(self):
        self.dom(r'''
        await loaded();fill();const raw=$('rig-json').value;run('state.jobEpoch++;rigJobChanged(state.job)');assert.equal($('rig-json').value,raw);assert.equal(run('rigUI.dirty'),true);assert.equal(run('rigUI.base'),null);assert.equal($('rig-submit').disabled,true);assert.equal($('rig-rights').checked,false);assert.match($('rig-source').textContent,/yeniden doğrulanmalı/);
        ''')

    def test_invalid_result_or_backend_errors_never_trigger_retry_or_selection(self):
        for variant in ['wrong-parent','wrong-child','paid','render','human-pass','error']:
            with self.subTest(variant=variant):
                self.dom(r'''
                await loaded();fill();let calls=0;const raw=$('rig-json').value,result=imported();if(VARIANT==='wrong-parent')result.parent_job=otherId;if(VARIANT==='wrong-child')result.job.id=otherId;if(VARIANT==='paid')result.provider_calls=1;if(VARIANT==='render')result.render_started=true;if(VARIANT==='human-pass')result.human_visual='pass';context.mockApi=async()=>{calls++;if(VARIANT==='error')throw Error('RIG_SOURCE_CHANGED: Kaynağı yenileyin');return result;};run('api=mockApi');await submit();assert.equal(calls,1);assert.equal(run('rigUI.child'),null);assert.equal(run('state.job.id'),sourceId);assert.ok($('rig-status').textContent);assert.equal($('rig-json').value,raw);if(VARIANT==='error'){assert.equal(run('rigUI.base'),null);assert.equal($('rig-rights').checked,false);assert.equal($('rig-submit').disabled,true);}
                '''.replace('VARIANT', json.dumps(variant)))

    def test_real_app_background_check_and_prepare_preserve_new_rig_draft(self):
        for operation in ['check', 'prepare']:
            with self.subTest(operation=operation):
                self.dom(r'''
                await loaded();fill();actualApp();await run('refreshJobs()');appDeferred={path:'/api/jobs/'+sourceId+'/'+OPERATION};const pending=OPERATION==='check'?$('check-job').listeners.click[0]():$('jobs').children[0].children[3].children[0].listeners.click[0]();await settle();
                input('rig-json','{new local rig during '+OPERATION);const raw=$('rig-json').value,base=run('JSON.stringify(rigUI.base)');releaseApp({status:'prepared'});await pending;await settle();assert.equal(run('state.job.id'),sourceId);assert.equal($('rig-json').value,raw);assert.equal(run('JSON.stringify(rigUI.base)'),base);assert.equal(run('rigUI.dirty'),true);
                '''.replace('OPERATION', json.dumps(operation)))

    def test_real_app_deferred_open_preserves_same_job_new_rig_draft(self):
        self.dom(r'''
        await actualSaved();appDeferred={path:'/api/jobs/'+rigChild};const pending=$('rig-open').listeners.click[0]();await settle();input('rig-json','{new JSON during child GET');const raw=$('rig-json').value;releaseApp(appJobs.get(rigChild));await pending;await settle();assert.equal(run('state.job.id'),sourceId);assert.equal($('rig-json').value,raw);assert.equal(run('rigUI.dirty'),true);
        ''')

    def test_real_app_deferred_open_preserves_b_selection_and_b_draft(self):
        self.dom(r'''
        await actualSaved();appJobs.set(otherId,sourceJob('sample-flow',otherId));appDeferred={path:'/api/jobs/'+rigChild};const pending=$('rig-open').listeners.click[0]();await settle();await run(`selectJob('${otherId}')`);await settle();input('rig-json','{B dirty JSON');releaseApp(appJobs.get(rigChild));await pending;await settle();assert.equal(run('state.job.id'),otherId);assert.equal($('rig-json').value,'{B dirty JSON');
        ''')

    def test_real_app_open_checks_silent_mutation_and_unchanged_open_still_works(self):
        for changed in [True, False]:
            with self.subTest(changed=changed):
                self.dom(r'''
                await actualSaved();appDeferred={path:'/api/jobs/'+rigChild};const pending=$('rig-open').listeners.click[0]();await settle();await $('rig-open').listeners.click[0]();if(CHANGED)$('rig-json').value='{silent JSON';const raw=$('rig-json').value;
                assert.equal(appCalls.filter(call=>call.path==='/api/jobs/'+rigChild).length,1);releaseApp(appJobs.get(rigChild));await pending;await settle();assert.equal(run('state.job.id'),CHANGED?sourceId:rigChild);if(CHANGED)assert.equal($('rig-json').value,raw);else assert.equal(run('rigUI.job'),rigChild);assert.ok(!appCalls.some(call=>/\/render$|\/execute$|\/connect$/.test(call.path)));
                '''.replace('CHANGED', json.dumps(changed)))

    def test_native_disclosure_preserves_values_and_hidden_form_relocates_focus(self):
        self.dom(r'''
        await loaded();$('rig-panel').open=true;input('rig-json','{unfinished rig');const node=$('rig-json');$('rig-panel').open=false;$('rig-panel').open=true;assert.equal($('rig-json'),node);assert.equal(node.value,'{unfinished rig');node.focus();selected('sample-reflection');assert.equal($('rig-form').hidden,true);assert.equal(document.activeElement,$('render-title'));assert.equal(visible(document.activeElement),true);
        ''')

    def test_no_storage_external_execution_or_credential_surface(self):
        for forbidden in ['localStorage', 'sessionStorage', 'innerHTML', 'eval(', 'new Function', 'console.', 'fetch(', 'https://', 'http://', 'createObjectURL', 'import(']:
            self.assertNotIn(forbidden, SOURCE)
        self.assertNotIn('rig-key', HTML)
        self.assertIn('selectJob(child.id,view)', SOURCE)
        self.assertIn("rig:typeof rigSelectionRevision==='function'", JS)
        self.assertIn("typeof rigJobChanged==='function'", JS)


if __name__ == '__main__':
    unittest.main()
