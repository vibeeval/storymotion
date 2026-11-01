from pack_fixture_case import PackFixtureCase
from storymotion.account_packs import account_catalog
"""Offline completed-audio binding UI contracts; no live key or provider dispatch."""
import json
import shutil
import subprocess
import unittest

from test_compact_ui import BOOT, CSS, HTML, JS, MARKUP, ROOT


AUDIO_SETUP = r'''
const parent='a'.repeat(24),child='d'.repeat(24),request='b'.repeat(32),connection='c'.repeat(32);
const parentFixture={id:parent,status:'prepared',files:[],payload:{input:{title:'Yerel ses denemesi',content:'Sentetik metin.'},account:{id:'sample-reflection'},format:{name:'Yerel konu',adapter:'account-pack'}}};
const childFixture={...parentFixture,id:child,status:'queued'};
const result=()=>({job:childFixture,parent_job:parent,child_job:child,publication_ready:false});
const completed=(status='completed',artifact={files:{'audio.mp3':'f'.repeat(64),'alignment.json':'e'.repeat(64)}})=>({request,status,artifact});
function ready(status='completed',artifact){
 context.parentFixture=parentFixture;context.item=completed(status,artifact);
 run(`state.job=parentFixture;state.jobEpoch=1;voiceConfig({mode:'demo'});voice.connection='${connection}';voice.request=item.request;audioBindSource(parentFixture.id,item);voiceControls();`);
}
function consent(){
 $('audio-bind-approved-by').value='Synthetic local reviewer';$('audio-bind-rights-note').value='Synthetic audio fixture; no personal voice.';
 for(const id of ['audio-bind-approved-by','audio-bind-rights-note'])for(const fn of $(id).listeners.input)fn();
 $('audio-bind-rights').checked=true;for(const fn of $('audio-bind-rights').listeners.change)fn();
}
const settle=()=>new Promise(resolve=>setImmediate(resolve));
function submit(){return $('audio-bind-form').listeners.submit[0]({preventDefault(){}});}
'''


@unittest.skipUnless(shutil.which('node'), 'Node required for audio UI contracts')
class AudioUi(PackFixtureCase):
    def dom(self, body):
        script = BOOT.replace('STRUCTURE', json.dumps(MARKUP.nodes)).replace('SOURCE', json.dumps(JS))
        script = script.replace('CATALOG', json.dumps(account_catalog(json.loads((ROOT / 'catalog/accounts.json').read_text()))))
        script = script.replace('PROVIDERS', json.dumps(json.loads((ROOT / 'catalog/providers.json').read_text())['providers']))
        script = script.replace('async function scenario(){ BODY }', AUDIO_SETUP + '\nasync function scenario(){ BODY }')
        result = subprocess.run(['node'], input=script.replace('BODY', body), text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_native_closed_disclosure_and_labeled_required_controls(self):
        ids = [n['attrs']['id'] for n in MARKUP.nodes if 'id' in n['attrs']]
        self.assertEqual(len(ids), len(set(ids)))
        step = next(n for n in MARKUP.nodes if n['attrs'].get('id') == 'audio-bind-step')
        self.assertEqual(step['tag'], 'details')
        self.assertIn('hidden', step['attrs'])
        self.assertNotIn('open', step['attrs'])
        children = [n for n in MARKUP.nodes if n['parent'] == MARKUP.nodes.index(step)]
        self.assertEqual(children[0]['tag'], 'summary')
        labels = {n['attrs'].get('for') for n in MARKUP.nodes if n['tag'] == 'label'}
        for id_, maximum in [('audio-bind-approved-by', '200'), ('audio-bind-rights-note', '1000')]:
            attrs = next(n['attrs'] for n in MARKUP.nodes if n['attrs'].get('id') == id_)
            self.assertIn(id_, labels)
            self.assertEqual(attrs['minlength'], '1')
            self.assertEqual(attrs['maxlength'], maximum)
            self.assertIn('required', attrs)
        checkbox = next(n['attrs'] for n in MARKUP.nodes if n['attrs'].get('id') == 'audio-bind-rights')
        self.assertIn('audio-bind-rights', labels)
        self.assertIn('required', checkbox)
        self.assertNotIn('checked', checkbox)
        self.assertIn('summary:focus-visible', CSS)
        self.assertIn('.audio-bind form,.audio-bind input{min-width:0;max-width:100%}', CSS)
        self.assertIn('Render veya sağlayıcı API çağrısı başlatmaz', HTML)
        self.assertIn('konuşan ağız ve taze viseme yoktur', HTML)
        self.assertIn('Zamanlama ve insan QA kabulü ayrıca bekler', HTML)

    def test_only_completed_artifact_reveals_binding_and_never_auto_dispatches(self):
        self.dom(r'''
        assert.equal($('audio-bind-step').hidden,true);assert.equal($('audio-bind-step').open,false);
        const calls=[];context.mockApi=async(path)=>{calls.push(path);return {requests:[completed()]};};run('api=mockApi');
        for(const status of ['preview','approved','dispatching','uncertain','failed_known_no_retry','received_after_cancel_review','invalidated','cancelled']){ready(status);assert.equal($('audio-bind-step').hidden,true,status);}
        ready('completed',null);assert.equal($('audio-bind-step').hidden,true);
        ready();assert.equal($('audio-bind-step').hidden,false);assert.equal($('audio-bind-step').open,false);assert.equal($('audio-bind-submit').disabled,true);
        await run(`voiceLoad('${parent}','${request}')`);$('audio-bind-step').open=true;consent();
        assert.equal($('audio-bind-submit').disabled,false);assert.deepEqual(calls,['/api/elevenlabs/state']);
        assert.ok(!calls.some(path=>/audio-bind|execute|render|connect/.test(path)));
        ''')

    def test_exact_payload_single_submit_selects_child_without_provider_or_render_calls(self):
        self.dom(r'''
        ready();consent();let release,sent;const calls=[],selected=[];
        context.mockApi=async(path,data)=>{calls.push(path);sent=data;return new Promise(resolve=>{release=resolve;});};
        context.refresh=async()=>calls.push('refreshJobs');context.select=async id=>selected.push(id);run('api=mockApi;refreshJobs=refresh;selectJob=select');
        const first=submit();await settle();await submit();assert.equal($('audio-bind-submit').disabled,true);assert.equal($('audio-bind-step').attrs['aria-busy'],'true');
        assert.deepEqual(calls,['/api/jobs/'+parent+'/audio-bind']);
        assert.deepEqual(JSON.parse(JSON.stringify(sent)),{request,approved_by:'Synthetic local reviewer',rights_note:'Synthetic audio fixture; no personal voice.',rights_confirmed:true,scene_word_spans:null,viseme_required:false});
        assert.ok(!JSON.stringify(sent).includes(connection));release(result());await first;
        assert.deepEqual(calls,['/api/jobs/'+parent+'/audio-bind','refreshJobs']);assert.deepEqual(selected,[child]);
        assert.equal($('audio-bind-step').attrs['aria-busy'],'false');assert.ok(!calls.some(path=>/execute|render|elevenlabs/.test(path)));
        ''')

    def test_blank_overlong_or_unconfirmed_form_cannot_post(self):
        self.dom(r'''
        ready();context.mockApi=async()=>{throw Error('No request allowed');};run('api=mockApi');
        for(const invalid of ['approved-blank','approved-long','rights-blank','rights-long','unconfirmed']){
          consent();if(invalid==='approved-blank')$('audio-bind-approved-by').value='  ';
          if(invalid==='approved-long')$('audio-bind-approved-by').value='x'.repeat(201);
          if(invalid==='rights-blank')$('audio-bind-rights-note').value='  ';
          if(invalid==='rights-long')$('audio-bind-rights-note').value='x'.repeat(1001);
          if(invalid==='unconfirmed')$('audio-bind-rights').checked=false;
          run('audioBindControls()');assert.equal($('audio-bind-submit').disabled,true,invalid);await submit();
          assert.match($('audio-bind-status').textContent,/açık kullanım hakkı onayı/);
        }
        ''')

    def test_stale_job_request_connection_epochs_or_form_never_select_child(self):
        edits = {
            'job': "run(\"state.job={...state.job,id:'e'.repeat(24)}\")",
            'job-epoch': "run('state.jobEpoch++')",
            'voice-epoch': "run('voice.epoch++')",
            'request': "run(\"voice.request='e'.repeat(32)\")",
            'connection': "run(\"voice.connection='e'.repeat(32)\")",
            'silent-approved-by': "$('audio-bind-approved-by').value='Changed reviewer'",
            'silent-rights-note': "$('audio-bind-rights-note').value='Changed rights'",
            'silent-rights': "$('audio-bind-rights').checked=false",
            'input-change-and-restore': "const previous=$('audio-bind-rights-note').value;$('audio-bind-rights-note').value='Changed';for(const fn of $('audio-bind-rights-note').listeners.input)fn();$('audio-bind-rights-note').value=previous;$('audio-bind-rights').checked=true;for(const fn of $('audio-bind-rights').listeners.change)fn()",
            'consent-revoked-and-rechecked': "$('audio-bind-rights').checked=false;for(const fn of $('audio-bind-rights').listeners.change)fn();$('audio-bind-rights').checked=true;for(const fn of $('audio-bind-rights').listeners.change)fn()",
            'invalidated': "context.invalid={...completed(),status:'invalidated'};run('audioBindSource(state.job.id,invalid)')",
        }
        for kind, edit in edits.items():
            with self.subTest(kind=kind):
                self.dom(r'''
                ready();consent();let release;const calls=[],selected=[];
                context.mockApi=async path=>{calls.push(path);return new Promise(resolve=>{release=resolve;});};
                context.refresh=async()=>calls.push('refreshJobs');context.select=async id=>selected.push(id);run('api=mockApi;refreshJobs=refresh;selectJob=select');
                const pending=submit();await settle();EDIT;release(result());await pending;
                assert.deepEqual(calls,['/api/jobs/'+parent+'/audio-bind']);assert.deepEqual(selected,[]);assert.equal(run('audioBind.pending'),null);
                '''.replace('EDIT', edit))

    def test_selection_change_while_refreshing_queue_cannot_open_child(self):
        self.dom(r'''
        ready();consent();let release;const selected=[],calls=[];context.mockApi=async path=>{calls.push(path);return result();};
        context.refresh=()=>new Promise(resolve=>{release=resolve;});context.select=async id=>selected.push(id);run('api=mockApi;refreshJobs=refresh;selectJob=select');
        const pending=submit();await settle();run('state.jobEpoch++');release();await pending;
        assert.deepEqual(selected,[]);assert.deepEqual(calls,['/api/jobs/'+parent+'/audio-bind']);
        ''')

    def test_existing_job_epoch_guard_prevents_late_child_get_overwriting_manual_selection(self):
        self.dom(r'''
        ready();consent();let release;const other={...parentFixture,id:'e'.repeat(24)};context.other=other;
        context.mockApi=async path=>{if(path.endsWith('/audio-bind'))return result();if(path==='/api/jobs/'+child)return new Promise(resolve=>{release=resolve;});if(path==='/api/jobs/'+other.id)return other;throw Error('Unexpected '+path);};
        run('api=mockApi;refreshJobs=async()=>{};voiceJobChanged=()=>{};renderJobChanged=()=>{}');
        const pending=submit();await settle();await run('selectJob(other.id)');release(childFixture);await pending;
        assert.equal(run('state.job.id'),other.id);assert.equal($('selected-job').textContent,'Yerel ses denemesi');
        ''')

    def test_invalid_response_and_local_error_do_not_select_or_retry(self):
        for mutation in ["data.parent_job='e'.repeat(24)", "data.child_job='invalid'", 'data.publication_ready=true', 'data.job={...data.job,id:parent}', 'data.child_job=parent;data.job={...data.job,id:parent}', "throw Error('Synthetic bind failure')"]:
            with self.subTest(mutation=mutation):
                self.dom(r'''
                ready();consent();const calls=[],selected=[];context.mockApi=async path=>{calls.push(path);const data=result();MUTATION;return data;};
                context.refresh=async()=>calls.push('refreshJobs');context.select=async id=>selected.push(id);run('api=mockApi;refreshJobs=refresh;selectJob=select');
                await submit();await settle();assert.deepEqual(selected,[]);assert.deepEqual(calls,['/api/jobs/'+parent+'/audio-bind']);
                assert.match($('audio-bind-status').textContent,/doğrulanamadı|Synthetic bind failure/);assert.equal(run('audioBind.pending'),null);
                '''.replace('MUTATION', mutation))

    def test_disclosure_preserves_values_and_hidden_step_moves_focus(self):
        self.dom(r'''
        ready();consent();$('audio-bind-step').open=true;const input=$('audio-bind-approved-by'),before=input.value;
        $('audio-bind-step').open=false;$('audio-bind-step').open=true;assert.equal($('audio-bind-approved-by'),input);assert.equal(input.value,before);assert.equal($('audio-bind-rights').checked,true);
        $('audio-bind-submit').focus();assert.equal(document.activeElement,$('audio-bind-submit'));run('voiceResetPreview()');
        assert.equal($('audio-bind-step').hidden,true);assert.equal(document.activeElement,$('el-title'));assert.equal(visible(document.activeElement),true);
        ''')

    def test_missing_failed_or_changed_audio_source_clears_old_rights_and_visibility(self):
        self.dom(r'''
        ready();consent();context.mockApi=async()=>({requests:[]});run('api=mockApi');await run(`voiceLoad('${parent}')`);assert.equal($('audio-bind-step').hidden,true);
        ready();consent();context.mockApi=async()=>{throw Error('Synthetic state error');};run('api=mockApi');await run(`voiceLoad('${parent}')`).catch(()=>{});assert.equal($('audio-bind-step').hidden,true);
        ready();consent();context.changed=completed('completed',{files:{'audio.mp3':'1'.repeat(64)}});run('audioBindSource(state.job.id,changed)');
        assert.equal($('audio-bind-step').hidden,false);assert.equal($('audio-bind-rights').checked,false);assert.equal($('audio-bind-submit').disabled,true);assert.equal($('audio-bind-approved-by').value,'');
        ''')

    def test_completed_saved_audio_binding_is_local_when_provider_mode_is_off(self):
        self.dom(r'''
        ready();run("voice.connection=null;voiceConfig({mode:'off'})");consent();assert.equal($('audio-bind-step').hidden,false);
        const calls=[];context.mockApi=async path=>{calls.push(path);return result();};context.refresh=async()=>{};context.select=async()=>{};run('api=mockApi;refreshJobs=refresh;selectJob=select');
        await submit();assert.deepEqual(calls,['/api/jobs/'+parent+'/audio-bind']);
        ''')

    def test_no_key_or_client_storage_is_added_to_audio_binding(self):
        for forbidden in ['localStorage', 'sessionStorage', 'innerHTML', 'console.log', 'console.error']:
            self.assertNotIn(forbidden, JS)
        self.assertNotIn('audio-bind-key', HTML)
        self.assertNotIn('viseme_required:true', JS)


if __name__ == '__main__':
    unittest.main()
