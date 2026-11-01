from pack_fixture_case import PackFixtureCase
from storymotion.account_packs import account_catalog
"""Offline writer UI contracts. No browser, live key or vendor request is used."""
import json
import shutil
import subprocess
import unittest
from test_compact_ui import BOOT, MARKUP, JS, ROOT
from storymotion.provider_catalog import build_registry, public_capabilities

PUBLIC_CAPABILITIES = public_capabilities(build_registry())

WRITER_SETUP = r'''
const connection='a'.repeat(32), request='b'.repeat(32), jobId='c'.repeat(24);
const metadata=provider=>({provider,models:[{id:'synthetic-'+provider,name:'Synthetic contract model',max_output_tokens:8000}],truncated:false});
function ready(mode='demo'){
 run("state.account=state.catalog.accounts.find(a=>a.id==='sample-reflection');$('title').value='Yerel başlık';$('brief').value='Yalnız yerel taslak bağlamı.';$('caption').value='Normal cümle yazımı.';$('writer-tokens').value='2000';");
 run(`writerConfig({mode:'${mode}'});writer.connection='${connection}';writer.provider='openai';writer.expiresAt=Date.now()+900000;writerMetadata(${JSON.stringify(metadata('openai'))});writerControls();`);
}
function preview(status='preview'){
 return {request,context:JSON.parse(run('JSON.stringify(writerContext())')),provider:'openai',model:'synthetic-openai',maximum_output_tokens:2000,status,dispatch_count:0,artifact:null};
}
function shownPreview(){const item=preview();context.item=item;run('writer.preview=item;writer.result=item;writer.request=item.request;writer.previewUntil=Date.now()+120000;writerPreviewSummary(item);writerControls();');return item;}
function consent(){ $('writer-cost-ack').checked=true;$('writer-rights-ack').checked=true;run('writerControls()'); }
const settle=()=>new Promise(resolve=>setImmediate(resolve));
context.capabilityFixture=CAPABILITY_FIXTURE;
run('capabilityCatalog(capabilityFixture);writerConfig({mode:"off",providers:["openai","anthropic","gemini","openrouter"]})');
run('tab("writer")');
'''


@unittest.skipUnless(shutil.which('node'), 'Node required for writer DOM contracts')
class WriterUi(PackFixtureCase):
    def dom(self, body):
        boot = BOOT.replace('let network=0;', 'let network=0;let timerSeq=0;const timers=new Map();')
        boot = boot.replace('setTimeout:()=>1,clearTimeout:()=>{}', 'setTimeout:(fn,ms)=>{const id=++timerSeq;timers.set(id,{fn,ms});return id;},clearTimeout:id=>timers.delete(id)')
        boot = boot.replace('STRUCTURE', json.dumps(MARKUP.nodes)).replace('SOURCE', json.dumps(JS))
        boot = boot.replace('CATALOG', json.dumps(account_catalog(json.loads((ROOT / 'catalog/accounts.json').read_text()))))
        boot = boot.replace('PROVIDERS', json.dumps(json.loads((ROOT / 'catalog/providers.json').read_text())['providers']))
        boot = boot.replace('async function scenario(){ BODY }', WRITER_SETUP.replace('CAPABILITY_FIXTURE', json.dumps(PUBLIC_CAPABILITIES)) + '\nasync function scenario(){ BODY }')
        result = subprocess.run(['node'], input=boot.replace('BODY', body), text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_off_mode_and_final_gates_are_accessible(self):
        self.dom(r'''
        run('writerConfig()');assert.equal(visible($('writer-flow')),false);assert.equal(visible($('writer-key')),false);
        assert.equal($('writer-connect').disabled,true);assert.equal(visible($('writer-how')),true);
        assert.ok($('writer-how').querySelector('summary'));
        $('writer-key').value='FAKE_ONLY';context.mockApi=()=>{throw Error('API must not run while off');};run('api=mockApi');
        $('writer-connect-form').listeners.submit[0]({preventDefault(){}});await settle();assert.equal($('writer-key').value,'');
        ''')
        for id_ in ['writer-cost-ack', 'writer-rights-ack', 'writer-exact-model', 'writer-exact-context', 'writer-live-budget', 'writer-generate']:
            node = next(n for n in MARKUP.nodes if n['attrs'].get('id') == id_)
            self.assertNotIn('details', [n['tag'] for n in MARKUP.ancestors(node)])
        for id_ in ['writer-cost-ack', 'writer-rights-ack', 'writer-review-ack']:
            attrs = next(n['attrs'] for n in MARKUP.nodes if n['attrs'].get('id') == id_)
            self.assertIn('required', attrs)
            self.assertNotIn('checked', attrs)

    def test_four_provider_connections_clear_key_before_metadata(self):
        self.dom(r'''
        const calls=[];context.mockApi=async(path,data)=>{calls.push(path);assert.equal($('writer-key').value,'');if(path.endsWith('/disconnect'))return {};if(path.endsWith('/connect'))return {connection,expires_in_seconds:900,metadata:metadata(data.provider),mode:'demo'};throw Error('Unexpected path');};run('api=mockApi');
        for(const provider of ['openai','anthropic','gemini','openrouter']){
          run("writerConfig({mode:'demo'})");$('writer-provider').value=provider;$('writer-key').value='FAKE_OPAQUE_SAMPLE_12345';
          $('writer-connect-form').listeners.submit[0]({preventDefault(){}});await settle();
          assert.equal($('writer-key').value,'');assert.equal(run('writer.provider'),provider);
          assert.equal(visible($('writer-selection')),true);assert.equal(visible($('writer-approval')),false);
          assert.ok(!run('JSON.stringify(writer)').includes('FAKE_OPAQUE_SAMPLE_12345'));
          await run("writerDropConnection('Disconnected')");
        }
        assert.equal(calls.filter(x=>x.endsWith('/connect')).length,4);
        assert.ok(!calls.some(x=>x.endsWith('/execute')));
        ''')

    def test_live_free_format_key_is_sent_exactly_and_never_auto_dispatches(self):
        self.dom(r'''
        const opaque=String.raw`  ASCII "quoted" \ opaque +/= : value  `;
        const calls=[];context.mockApi=async(path,data)=>{calls.push(path);assert.equal($('writer-key').value,'');if(path.endsWith('/disconnect'))return {};assert.equal(path,'/api/llm/connect');assert.equal(data.value,opaque);return {connection,expires_in_seconds:900,metadata:metadata(data.provider)};};run('api=mockApi');
        for(const provider of ['openai','anthropic','gemini','openrouter']){
          run("writerConfig({mode:'live'})");$('writer-provider').value=provider;$('writer-key').value=opaque;
          assert.equal(calls.filter(x=>x.endsWith('/connect')).length,['openai','anthropic','gemini','openrouter'].indexOf(provider));
          $('writer-connect-form').listeners.submit[0]({preventDefault(){}});await settle();
          assert.equal(run('writer.provider'),provider);assert.equal($('writer-key').value,'');assert.equal($('writer-generate').disabled,true);
          assert.ok(!run('JSON.stringify(writer)').includes(opaque));await run("writerDropConnection('Disconnected')");
        }
        assert.equal(calls.filter(x=>x.endsWith('/connect')).length,4);assert.ok(!calls.some(x=>/preview|approve|execute/.test(x)));
        assert.equal($('writer-key').attrs.maxlength,'512');assert.equal($('writer-key').attrs.minlength,'1');assert.ok('required' in $('writer-key').attrs);
        ''')

    def test_legacy_fake_panel_is_demo_only_and_modes_are_explicit(self):
        self.dom(r'''
        $('provider-task').value='text';$('provider').value='openai';
        for(const mode of ['off','live','demo']){
          run(`writerConfig({mode:'${mode}'});modelList();`);
          assert.equal($('llm-demo').hidden,mode!=='demo');assert.equal($('llm-plan').hidden,mode!=='demo');
          assert.equal($('save-key').disabled,mode!=='demo');
        }
        run("writerConfig({mode:'off'})");assert.match($('writer-mode').textContent,/kapalı.*live.*yalnız demo/);
        run("writerConfig({mode:'live'})");assert.match($('writer-mode').textContent,/OpenAI.*Anthropic.*Gemini.*OpenRouter/);
        assert.match($('writer-key-note').textContent,/Erişim sağlayıcıda doğrulanır/);
        const providers=$('writer-provider').children.map(n=>n.value);assert.deepEqual(providers,['openai','anthropic','gemini','openrouter']);
        assert.equal($('writer-model').children.length,0);
        ''')

    def test_provider_change_clears_connection_and_wrong_metadata_never_falls_back(self):
        self.dom(r'''
        ready();shownPreview();consent();const calls=[];
        context.mockApi=async(path,data)=>{calls.push(path);if(path.endsWith('/disconnect'))return {};if(path.endsWith('/connect'))return {connection,ttl_seconds:900,metadata:metadata('openai')};throw Error('Unexpected path');};run('api=mockApi');
        $('writer-provider').value='gemini';$('writer-provider').listeners.change[0]();await settle();
        assert.equal(run('writer.connection'),null);assert.equal(run('writer.metadata'),null);assert.equal(run('writer.preview'),null);assert.equal($('writer-model').children.length,0);
        assert.equal($('writer-cost-ack').checked,false);assert.equal($('writer-rights-ack').checked,false);
        $('writer-key').value='FAKE_GEMINI_CONTRACT';$('writer-connect-form').listeners.submit[0]({preventDefault(){}});await settle();
        assert.equal(run('writer.connection'),null);assert.equal(run('writer.metadata'),null);assert.equal($('writer-model').children.length,0);assert.equal($('writer-generate').disabled,true);
        assert.ok(calls.filter(x=>x.endsWith('/disconnect')).length>=2);
        ''')

    def test_connect_failure_and_invalid_metadata_fail_closed(self):
        self.dom(r'''
        run("writerConfig({mode:'demo'})");
        context.mockApi=async()=>{assert.equal($('writer-key').value,'');throw Error('HTTP_401');};run('api=mockApi');
        $('writer-key').value='FAKE_REJECTED_SAMPLE';$('writer-connect-form').listeners.submit[0]({preventDefault(){}});await settle();
        assert.equal(run('writer.connection'),null);assert.equal($('writer-key').value,'');assert.equal($('writer-generate').disabled,true);
        const calls=[];context.mockApi=async(path)=>{calls.push(path);return path.endsWith('/connect')?{connection,ttl_seconds:900,metadata:{provider:'anthropic',models:[]}}:{};};run('api=mockApi');
        $('writer-key').value='FAKE_INVALID_METADATA';$('writer-connect-form').listeners.submit[0]({preventDefault(){}});await settle();
        assert.equal(run('writer.connection'),null);assert.equal($('writer-key').value,'');assert.ok(calls.includes('/api/llm/disconnect'));
        ''')

    def test_preview_uses_brief_without_job_and_preserves_exact_context(self):
        self.dom(r'''
        ready();assert.equal(run('state.job'),null);$('brand-name').value='My Studio';$('brand-handle').value='@mine';
        $('brief').value='Metin içinde Seri örneği geçiyorsa exact gösterilir.';
        let sent;context.mockApi=async(path,data)=>{assert.equal(path,'/api/llm/preview');sent=data;const c=data.context;return {...preview(),context:{caption:c.caption,brief:c.brief,title:c.title,account:c.account}};};run('api=mockApi');
        $('writer-preview').listeners.click[0]();await settle();
        assert.equal(sent.context.account,'sample-reflection');assert.equal(sent.max_output_tokens,2000);
        assert.equal(sent.model,'synthetic-openai');assert.equal(Object.keys(sent.context).length,4);
        assert.equal(visible($('writer-approval')),true);assert.equal($('writer-generate').disabled,true);
        assert.match($('writer-exact-context').textContent,/Seri örneği/);assert.match($('writer-exact-context').textContent,/My Studio/);
        assert.match($('writer-exact-model').textContent,/OpenAI.*synthetic-openai.*2000/);
        ''')

    def test_live_quote_and_two_consents_are_independent(self):
        self.dom(r'''
        ready('live');shownPreview();consent();assert.equal($('writer-generate').disabled,true);
        $('writer-max-usd').value='0';$('writer-estimate-usd').value='0';$('writer-quote-source').value='Own current quote';run('writerControls()');assert.equal($('writer-generate').disabled,true);
        $('writer-max-usd').value='2';$('writer-estimate-usd').value='1';run('writerControls()');assert.equal($('writer-generate').disabled,false);
        $('writer-rights-ack').checked=false;run('writerControls()');assert.equal($('writer-generate').disabled,true);
        consent();$('writer-estimate-usd').value='3';run('writerControls()');assert.equal($('writer-generate').disabled,true);
        $('writer-estimate-usd').value='1';$('writer-estimate-usd').listeners.input[0]();assert.equal($('writer-cost-ack').checked,false);assert.equal($('writer-rights-ack').checked,false);
        assert.equal(visible($('writer-live-budget')),true);
        ''')

    def test_context_model_and_token_changes_reset_preview(self):
        self.dom(r'''
        ready();for(const id of ['title','brief','caption','brand-name','brand-handle','writer-model','writer-tokens']){
          shownPreview();consent();for(const listener of $(id).listeners.input)listener();assert.equal(run('writer.preview'),null,id);
          assert.equal($('writer-cost-ack').checked,false);assert.equal($('writer-rights-ack').checked,false);assert.equal($('writer-generate').disabled,true);
        }
        for(const tokens of ['15','8001','17.5','']){$('writer-tokens').value=tokens;run('writerControls()');assert.equal($('writer-preview').disabled,true,tokens);}
        $('writer-tokens').value='8000';run('writerControls()');assert.equal($('writer-preview').disabled,false);
        ''')

    def test_metadata_preview_and_connection_expiry_fail_closed(self):
        self.dom(r'''
        ready();shownPreview();consent();const metadataTimer=run('writer.metadataTimer');timers.get(metadataTimer).fn();
        assert.equal(run('writer.preview'),null);assert.equal($('writer-generate').disabled,true);assert.equal($('writer-preview').disabled,true);
        ready();context.mockApi=async()=>preview();run('api=mockApi');$('writer-preview').listeners.click[0]();await settle();consent();
        const timer=run('writer.previewTimer');timers.get(timer).fn();assert.equal(run('writer.preview'),null);assert.equal($('writer-generate').disabled,true);
        await run("writerDropConnection('Disconnected')");run("writerConfig({mode:'demo'})");
        context.mockApi=async(path,data)=>path.endsWith('/connect')?{connection,ttl_seconds:900,metadata:metadata(data.provider)}:{};run('api=mockApi');
        $('writer-provider').value='openai';$('writer-key').value='FAKE_SESSION_TTL';$('writer-connect-form').listeners.submit[0]({preventDefault(){}});await settle();
        const expiry=run('writer.connectionTimer');timers.get(expiry).fn();await settle();
        assert.equal(run('writer.connection'),null);assert.equal($('writer-generate').disabled,true);assert.equal(visible($('writer-key')),true);
        ''')

    def test_late_preview_and_metadata_cannot_restore_disconnect(self):
        self.dom(r'''
        ready();let release;context.mockApi=async(path)=>path.endsWith('/preview')?new Promise(resolve=>{release=resolve;}):{};run('api=mockApi');
        const expected=preview();$('writer-preview').listeners.click[0]();await settle();await run("writerDropConnection('Disconnected')");release(expected);await settle();
        assert.equal(run('writer.preview'),null);assert.equal(run('writer.connection'),null);
        ready();context.mockApi=async(path)=>path.endsWith('/metadata')?new Promise(resolve=>{release=resolve;}):{};run('api=mockApi');
        $('writer-refresh').listeners.click[0]();await settle();await run("writerDropConnection('Disconnected')");release(metadata('openai'));await settle();
        assert.equal(run('writer.metadata'),null);assert.equal(visible($('writer-approval')),false);
        ''')

    def test_edit_during_approval_prevents_dispatch(self):
        self.dom(r'''
        ready();shownPreview();consent();let release;const calls=[];
        context.mockApi=async(path)=>{calls.push(path);if(path.endsWith('/approve'))return new Promise(resolve=>{release=resolve;});throw Error('Dispatch must not occur');};run('api=mockApi');
        $('writer-generate').listeners.click[0]();await settle();$('brief').value='Changed';$('brief').listeners.input[0]();release({});await settle();
        assert.deepEqual(calls,['/api/llm/approve']);assert.equal($('writer-generate').disabled,true);assert.equal(run('writer.preview'),null);
        ''')

    def test_pending_writer_budget_changes_require_new_preview_and_consent(self):
        for mode in ['demo', 'live']:
            for field in ['writer-max-usd', 'writer-estimate-usd', 'writer-quote-source']:
                with self.subTest(mode=mode, field=field):
                    self.dom(r'''
                    ready(MODE);shownPreview();$('writer-max-usd').value='2';$('writer-estimate-usd').value='0.25';$('writer-quote-source').value='Synthetic current quote';consent();
                    let release;const calls=[];context.mockApi=async(path)=>{calls.push(path);if(path.endsWith('/approve'))return new Promise(resolve=>{release=resolve;});throw Error('Dispatch must not occur');};run('api=mockApi');
                    $('writer-generate').listeners.click[0]();await settle();
                    $(FIELD).value=FIELD==='writer-quote-source'?'Changed synthetic quote':'0.50';for(const listener of $(FIELD).listeners.input)listener();
                    assert.deepEqual(calls,['/api/llm/approve']);release({});await settle();
                    assert.deepEqual(calls,['/api/llm/approve']);assert.equal(run('writer.preview'),null);assert.equal($('writer-generate').disabled,true);
                    consent();$('writer-generate').listeners.click[0]();await settle();assert.deepEqual(calls,['/api/llm/approve']);
                    '''.replace('MODE', json.dumps(mode)).replace('FIELD', json.dumps(field)))

    def test_pending_writer_consent_revocation_cannot_be_rechecked_into_old_approval(self):
        for mode in ['demo', 'live']:
            for field in ['writer-cost-ack', 'writer-rights-ack']:
                with self.subTest(mode=mode, field=field):
                    self.dom(r'''
                    ready(MODE);shownPreview();$('writer-max-usd').value='2';$('writer-estimate-usd').value='1';$('writer-quote-source').value='Synthetic quote';consent();
                    let release;const calls=[];context.mockApi=async(path)=>{calls.push(path);if(path.endsWith('/approve'))return new Promise(resolve=>{release=resolve;});throw Error('Dispatch must not occur');};run('api=mockApi');
                    $('writer-generate').listeners.click[0]();await settle();$(FIELD).checked=false;for(const listener of $(FIELD).listeners.change)listener();
                    consent();release({});await settle();assert.deepEqual(calls,['/api/llm/approve']);assert.equal(run('writer.preview'),null);assert.equal($('writer-generate').disabled,true);
                    '''.replace('MODE', json.dumps(mode)).replace('FIELD', json.dumps(field)))

    def test_writer_approval_snapshot_catches_silent_dom_changes(self):
        for field in ['writer-max-usd', 'writer-estimate-usd', 'writer-quote-source', 'writer-cost-ack', 'writer-rights-ack', 'writer-model', 'writer-tokens', 'brief']:
            with self.subTest(field=field):
                self.dom(r'''
                ready('live');shownPreview();$('writer-max-usd').value='2';$('writer-estimate-usd').value='1';$('writer-quote-source').value='Synthetic quote';consent();
                let release;const calls=[];context.mockApi=async(path)=>{calls.push(path);if(path.endsWith('/approve'))return new Promise(resolve=>{release=resolve;});throw Error('Dispatch must not occur');};run('api=mockApi');
                $('writer-generate').listeners.click[0]();await settle();
                if(FIELD.endsWith('-ack'))$(FIELD).checked=false;else $(FIELD).value=FIELD==='writer-model'?'changed-model':FIELD==='brief'?'Changed brief':'0.50';
                release({});await settle();assert.deepEqual(calls,['/api/llm/approve']);assert.equal(run('writer.preview'),null);assert.equal($('writer-generate').disabled,true);
                '''.replace('FIELD', json.dumps(field)))

    def test_pending_voice_budget_and_consent_changes_prevent_dispatch(self):
        for mode in ['demo', 'live']:
            for field in ['el-max-usd', 'el-estimate-usd', 'el-quote-source', 'el-cost-ack', 'el-rights-ack']:
                with self.subTest(mode=mode, field=field):
                    self.dom(r'''
                    run(`voiceConfig({mode:MODE});voice.connection='${connection}';state.job={id:'${jobId}',payload:{input:{title:'Sentetik'},account:{id:'sample-reflection'},format:{name:'Yerel'}}};voiceMetadata({voices:[{voice_id:'synthetic-voice',name:'Synthetic voice'}],models:[{model_id:'synthetic-model',name:'Synthetic model'}]});`);
                    $('el-tts').value='Yalnız sentetik yerel metin.';context.voicePreview={request,characters:27};run('voice.preview=voicePreview;voice.request=voicePreview.request;voicePreviewSummary(voicePreview)');
                    $('el-max-usd').value='2';$('el-estimate-usd').value='0.25';$('el-quote-source').value='Synthetic quote';$('el-cost-ack').checked=true;$('el-rights-ack').checked=true;run('voiceControls()');
                    let release;const calls=[];context.mockApi=async(path)=>{calls.push(path);if(path.endsWith('/approve'))return new Promise(resolve=>{release=resolve;});if(path.endsWith('/state'))return {requests:[]};throw Error('Dispatch must not occur');};run('api=mockApi');
                    $('el-generate').listeners.click[0]();await settle();
                    if(FIELD.endsWith('-ack')){$(FIELD).checked=false;for(const listener of $(FIELD).listeners.change)listener();$('el-cost-ack').checked=true;$('el-rights-ack').checked=true;}
                    else {$(FIELD).value=FIELD==='el-quote-source'?'Changed quote':'0.50';for(const listener of $(FIELD).listeners.input)listener();}
                    assert.deepEqual(calls,['/api/elevenlabs/approve']);release({});await settle();assert.deepEqual(calls,['/api/elevenlabs/approve']);
                    assert.equal(run('voice.preview'),null);assert.equal($('el-generate').disabled,true);
                    $('el-cost-ack').checked=true;$('el-rights-ack').checked=true;$('el-generate').listeners.click[0]();await settle();assert.deepEqual(calls,['/api/elevenlabs/approve']);
                    '''.replace('MODE', json.dumps(mode)).replace('FIELD', json.dumps(field)))

    def test_voice_approval_snapshot_catches_silent_selection_and_consent_changes(self):
        for field in ['el-max-usd', 'el-estimate-usd', 'el-quote-source', 'el-cost-ack', 'el-rights-ack', 'el-voice', 'el-model', 'el-tts']:
            with self.subTest(field=field):
                self.dom(r'''
                run(`voiceConfig({mode:'live'});voice.connection='${connection}';state.job={id:'${jobId}',payload:{input:{title:'Sentetik'},account:{id:'sample-reflection'},format:{name:'Yerel'}}};voiceMetadata({voices:[{voice_id:'synthetic-voice',name:'Synthetic voice'}],models:[{model_id:'synthetic-model',name:'Synthetic model'}]});`);
                $('el-tts').value='Yalnız sentetik yerel metin.';context.voicePreview={request,characters:27};run('voice.preview=voicePreview;voice.request=voicePreview.request');
                $('el-max-usd').value='2';$('el-estimate-usd').value='1';$('el-quote-source').value='Synthetic quote';$('el-cost-ack').checked=true;$('el-rights-ack').checked=true;run('voiceControls()');
                let release;const calls=[];context.mockApi=async(path)=>{calls.push(path);if(path.endsWith('/approve'))return new Promise(resolve=>{release=resolve;});if(path.endsWith('/state'))return {requests:[]};throw Error('Dispatch must not occur');};run('api=mockApi');
                $('el-generate').listeners.click[0]();await settle();if(FIELD.endsWith('-ack'))$(FIELD).checked=false;else $(FIELD).value='Changed';
                release({});await settle();assert.deepEqual(calls,['/api/elevenlabs/approve']);assert.equal(run('voice.preview'),null);assert.equal($('el-generate').disabled,true);
                '''.replace('FIELD', json.dumps(field)))

    def test_voice_backend_invalidation_removes_old_preview_and_generation(self):
        self.dom(r'''
        run(`voiceConfig({mode:'demo'});voice.connection='${connection}';state.job={id:'${jobId}',payload:{input:{title:'Sentetik'},account:{id:'sample-reflection'},format:{name:'Yerel'}}};voice.preview={request:'${request}',characters:20};voice.request='${request}';`);
        $('el-cost-ack').checked=true;$('el-rights-ack').checked=true;
        context.mockApi=async()=>({requests:[{request,status:'invalidated',dispatch_count:0,error_code:'VOICE_APPROVAL_EXPIRED_BEFORE_WIRE'}]});run('api=mockApi');
        await run(`voiceLoad('${jobId}','${request}')`);
        assert.equal(run('voice.preview'),null);assert.equal($('el-generate').disabled,true);
        assert.match($('el-status').textContent,/invalidated/);assert.match($('el-status').textContent,/VOICE_APPROVAL_EXPIRED_BEFORE_WIRE/);
        ''')

    def test_voice_unchanged_approval_dispatches_once_with_exact_budget(self):
        self.dom(r'''
        run(`voiceConfig({mode:'live'});voice.connection='${connection}';state.job={id:'${jobId}',payload:{input:{title:'Sentetik'},account:{id:'sample-reflection'},format:{name:'Yerel'}}};voiceMetadata({voices:[{voice_id:'synthetic-voice',name:'Synthetic voice'}],models:[{model_id:'synthetic-model',name:'Synthetic model'}]});`);
        $('el-tts').value='Yalnız sentetik metin.';context.voicePreview={request,characters:21};run('voice.preview=voicePreview;voice.request=voicePreview.request');
        $('el-max-usd').value='2';$('el-estimate-usd').value='1';$('el-quote-source').value='Synthetic quote';$('el-cost-ack').checked=true;$('el-rights-ack').checked=true;run('voiceControls()');
        let release,approval;const calls=[];context.mockApi=async(path,data)=>{calls.push(path);if(path.endsWith('/approve')){approval=data;return new Promise(resolve=>{release=resolve;});}if(path.endsWith('/execute'))return {};if(path.endsWith('/state'))return {requests:[{request,status:'completed'}]};throw Error('Unexpected path');};run('api=mockApi');
        $('el-generate').listeners.click[0]();$('el-generate').listeners.click[0]();await settle();assert.equal(calls.filter(x=>x.endsWith('/approve')).length,1);release({});await settle();
        assert.equal(approval.budget.max_usd,'2');assert.equal(approval.budget.estimate_usd,'1');assert.equal(approval.budget.quote_source,'Synthetic quote');assert.equal(approval.maximum_characters,21);
        assert.equal(calls.filter(x=>x.endsWith('/execute')).length,1);assert.equal(run('voice.preview'),null);assert.equal($('el-generate').disabled,true);
        assert.equal($('el-cost-ack').checked,false);assert.equal($('el-rights-ack').checked,false);
        ''')

    def test_double_click_and_uncertain_result_never_retry(self):
        self.dom(r'''
        ready();shownPreview();consent();let release;const calls=[];
        context.mockApi=async(path,data)=>{calls.push(path);if(path.endsWith('/approve'))return new Promise(resolve=>{release=resolve;});if(path.endsWith('/execute'))throw Error('Synthetic timeout');throw Error('Unexpected');};run('api=mockApi');
        $('writer-generate').listeners.click[0]();$('writer-generate').listeners.click[0]();await settle();release({});await settle();
        assert.equal(calls.filter(x=>x.endsWith('/approve')).length,1);assert.equal(calls.filter(x=>x.endsWith('/execute')).length,1);
        assert.equal(run('writer.result.status'),'uncertain');assert.equal($('writer-preview').disabled,true);assert.equal($('writer-generate').disabled,true);
        assert.match($('writer-status').textContent,/belirsiz/);$('writer-generate').listeners.click[0]();await settle();assert.equal(calls.length,2);
        ''')

    def test_live_dispatch_payload_is_exact_and_single_attempt(self):
        self.dom(r'''
        ready('live');const item=shownPreview();$('writer-max-usd').value='2';$('writer-estimate-usd').value='1';$('writer-quote-source').value='Synthetic current quote';consent();
        const calls=[];let approval;context.mockApi=async(path,data)=>{calls.push(path);if(path.endsWith('/approve')){approval=data;return {...item,status:'approved'};}if(path.endsWith('/execute'))return {...item,status:'dispatching',dispatch_count:1};throw Error('Unexpected path');};run('api=mockApi');
        $('writer-generate').listeners.click[0]();await settle();
        assert.equal(approval.connection,connection);assert.equal(approval.request,request);assert.equal(approval.maximum_output_tokens,2000);
        assert.equal(approval.ack_unknown_cost,true);assert.equal(approval.rights_confirmed,true);assert.equal(approval.budget.verified_by_user,true);assert.equal(approval.budget.max_usd,'2');
        assert.equal(calls.filter(x=>x.endsWith('/execute')).length,1);assert.equal(run('writer.attempts.has(writer.request)'),true);
        assert.equal($('writer-generate').disabled,true);assert.equal(visible($('writer-cancel')),true);
        ''')

    def test_completed_proposal_accept_is_explicit_and_never_renders(self):
        self.dom(r'''
        ready();const completed={...preview('completed'),dispatch_count:1,artifact:{synthetic:true,publication_ready:false,files:{'proposal.json':'hash','receipt.json':'hash'}}};
        const calls=[];let accepted;context.mockApi=async(path,data)=>{calls.push(path);if(path.startsWith('/llm-files/'))return {script:'Sentetik senaryo.',scenes:[]};if(path.endsWith('/accept')){accepted=data;return {accepted_job:jobId};}throw Error('Unexpected path');};run('api=mockApi;refreshJobs=async()=>{}');context.completed=completed;
        run('writer.request=completed.request');await run('writerDisplayResult(completed)');
        assert.equal(visible($('writer-result')),true);assert.equal($('writer-accept').disabled,true);assert.match($('writer-review-status').textContent,/Yayına hazır değildir/);
        assert.equal($('writer-script').textContent,'Sentetik senaryo.');assert.equal($('writer-downloads').children.length,2);
        for(const link of $('writer-downloads').children)assert.match(link.href,/^\/llm-files\/[a-f0-9]{32}\/(proposal|receipt)\.json$/);
        $('brand-name').value='New Studio';$('brand-handle').value='@new';$('writer-review-ack').checked=true;run('writerControls()');assert.equal($('writer-accept').disabled,false);
        $('writer-accept').listeners.click[0]();await settle();assert.equal(accepted.brand_identity.name,'New Studio');assert.equal(accepted.brand_identity.handle,'@new');
        assert.equal(run('writer.result.accepted_job'),jobId);assert.equal(visible($('writer-open-job')),true);
        assert.equal(calls.filter(x=>x.endsWith('/accept')).length,1);assert.ok(!calls.some(x=>/render|elevenlabs|prepare|execute/.test(x)));
        ''')

    def test_completed_artifact_audit_warning_is_visible_without_retry_or_automatic_accept(self):
        self.dom(r'''
        ready();const completed={...preview('completed'),completion_audit_error:'COMPLETION_AUDIT_WRITE_FAILED',dispatch_count:1,artifact:{synthetic:true,publication_ready:false,files:{'proposal.json':'hash','receipt.json':'hash'}}};
        const calls=[];context.mockApi=async(path)=>{calls.push(path);if(path.startsWith('/llm-files/'))return {script:'Korunan öneri.',scenes:[]};throw Error('No production or accept action allowed');};run('api=mockApi');context.completed=completed;
        run('writer.request=completed.request');await run('writerDisplayResult(completed)');
        assert.equal(run('writer.result.status'),'completed');assert.match($('writer-status').textContent,/Olay kaydı eksik/);
        assert.match($('writer-review-status').textContent,/Olay kaydı eksik/);assert.match($('writer-review-status').textContent,/Yayına hazır değildir/);
        assert.equal($('writer-accept').disabled,true);assert.equal($('writer-script').textContent,'Korunan öneri.');
        assert.equal(calls.filter(x=>/execute|accept|elevenlabs|render/.test(x)).length,0);
        $('writer-review-ack').checked=true;run('writerControls()');assert.equal($('writer-accept').disabled,false);
        ''')

    def test_no_client_storage_and_four_account_render_support(self):
        for forbidden in ['localStorage', 'sessionStorage', 'innerHTML', 'console.log', 'console.error']:
            self.assertNotIn(forbidden, JS)
        self.dom(r'''
        ready();run('renderLoad=async()=>{}');
        for(const adapter of ['account-pack','hyperframes-fixture']){run(`renderJobChanged({id:'${jobId}',payload:{format:{adapter:'${adapter}'}}})`);assert.equal($('render-start').disabled,false);}
        run("renderJobChanged({id:'local',payload:{format:{adapter:'plan-only'}}})");assert.equal($('render-start').disabled,true);
        ''')


if __name__ == '__main__':
    unittest.main()
