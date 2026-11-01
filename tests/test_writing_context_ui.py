from pack_fixture_case import PackFixtureCase
"""Offline DOM: explicit context saves and stale approval invalidation."""
import json,shutil,unittest
from pathlib import Path
import test_llm_ui as writer_ui
from test_compact_ui import ROOT,MARKUP
from storymotion.writing_context import snapshot
from test_writing_context import SOURCE
PANEL=(ROOT/'dashboard/writing-context.js').read_text()
EMPTY={'account':'sample-mechanism','sources':None,'canon':None}
SAVED={**EMPTY,'sources':snapshot('sources','sample-mechanism',SOURCE,None)}
SETUP='context.panel='+json.dumps(PANEL)+';context.empty='+json.dumps(EMPTY)+';context.saved='+json.dumps(SAVED)+''';
run('state.account=null');vm.runInContext(panel,context);
function selectAccountLocal(id='sample-mechanism'){run(`state.account=state.catalog.accounts.find(x=>x.id==='${id}')`);}
'''
# Node's outer sandbox variable is explicitly injected; no API is run at load.
SETUP=SETUP.replace('vm.runInContext(panel,context)','vm.runInContext(context.panel,context)')


@unittest.skipUnless(shutil.which('node'),'Node required for context DOM contracts')
class WritingContextUi(PackFixtureCase):
    def dom(self,body):writer_ui.WriterUi().dom(SETUP+body)
    def test_real_bootstrap_without_selected_account_does_not_treat_null_as_loaded(self):
        self.dom(r'''
        run('writerControls()');assert.equal(run('writerContext().account'),'');
        assert.equal(run('writingContextReady(undefined)'),false);assert.equal(run('JSON.stringify(writingContextRefs(undefined))'),'{}');
        assert.equal($('writer-preview').disabled,true);assert.equal($('writer-generate').disabled,true);
        ''')
    def test_loading_failed_and_unsaved_context_cannot_generate_or_auto_save(self):
        self.dom(r'''
        selectAccountLocal();ready();selectAccountLocal();let reads=0;context.fetch=async()=>{reads++;return{ok:true,json:async()=>context.empty};};
        await run('writingContextChanged("sample-mechanism")');assert.equal(reads,1);assert.equal(run('writingContextReady("sample-mechanism")'),true);
        $('writing-sources-json').value='not saved';$('writing-sources-json').listeners.input[0]();
        assert.equal(reads,1);assert.equal(run('writingContextReady("sample-mechanism")'),false);assert.equal($('writer-preview').disabled,true);assert.equal($('writer-generate').disabled,true);
        context.fetch=async()=>({ok:false});await run('writingContextChanged("sample-mechanism")');
        assert.equal(run('writingContextReady("sample-mechanism")'),false);assert.match($('writing-context-status').textContent,/doğrulanamadı/);
        ''')
    def test_explicit_save_pins_revision_clears_approval_and_preserves_other_inputs(self):
        self.dom(r'''
        selectAccountLocal();context.fetch=async()=>({ok:true,json:async()=>context.empty});await run('writingContextChanged("sample-mechanism")');ready();selectAccountLocal();shownPreview();consent();
        $('title').value='Korunan başlık';$('writer-key').value='FAKE_INPUT_ONLY';$('writing-sources-json').value=JSON.stringify(context.saved.sources.data);$('writing-source-rights').checked=true;
        const calls=[];context.mockApi=async(path,data)=>{calls.push({path,data});assert.equal(path,'/api/writing-context/save-sources');assert.equal(data.expected_revision,null);assert.equal(data.rights_confirmed,true);return context.saved;};run('api=mockApi');
        $('writing-save-sources').listeners.click[0]();await settle();
        assert.equal(calls.length,1);assert.equal(run('writerContext().source_revision'),context.saved.sources.revision);assert.equal(run('writer.preview'),null);assert.equal($('writer-cost-ack').checked,false);assert.equal($('writing-source-rights').checked,false);
        assert.equal($('title').value,'Korunan başlık');assert.equal($('writer-key').value,'FAKE_INPUT_ONLY');
        ''')
    def test_slow_previous_account_read_cannot_replace_latest_account_canon(self):
        self.dom(r'''
        const queue=[];context.fetch=()=>new Promise(resolve=>queue.push(resolve));selectAccountLocal();const first=run('writingContextChanged("sample-mechanism")');
        selectAccountLocal('sample-series');const second=run('writingContextChanged("sample-series")');
        queue[1]({ok:true,json:async()=>({...context.empty,account:'sample-series'})});await second;queue[0]({ok:true,json:async()=>context.saved});await first;
        assert.equal(run('writingContextReady("sample-series")'),true);assert.equal(run('writingContextReady("sample-mechanism")'),false);assert.equal($('writing-canon-area').hidden,false);assert.equal(run('writingContextRefs("sample-series").source_revision'),undefined);
        ''')
    def test_context_revision_is_part_of_awaiting_approval_snapshot(self):
        self.dom(r'''
        selectAccountLocal();context.fetch=async()=>({ok:true,json:async()=>context.empty});await run('writingContextChanged("sample-mechanism")');ready();selectAccountLocal();const p=shownPreview();consent();const before=run('writerApprovalContext(writer.preview)');
        context.fetch=async()=>({ok:true,json:async()=>context.saved});await run('writingContextChanged("sample-mechanism")');context.p=p;
        assert.notEqual(run('writerApprovalContext(p)'),before);assert.equal($('writer-generate').disabled,true);assert.equal($('writer-cost-ack').checked,false);
        ''')
    def test_stale_completed_result_can_be_replaced_by_new_preview_without_dispatch(self):
        self.dom(r'''
        selectAccountLocal();context.fetch=async()=>({ok:true,json:async()=>context.empty});await run('writingContextChanged("sample-mechanism")');ready();selectAccountLocal();shownPreview();
        run('writer.result={...writer.result,status:"completed",artifact:{files:{}},context_current:true}');
        context.fetch=async()=>({ok:true,json:async()=>context.saved});await run('writingContextChanged("sample-mechanism")');
        assert.equal(run('writer.result.context_current'),false);assert.equal($('writer-preview').disabled,false);assert.equal($('writer-generate').disabled,true);
        $('writer-review-ack').checked=true;const calls=[];context.mockApi=async(path,data)=>{calls.push(path);assert.equal(path,'/api/llm/preview');assert.equal(data.context.source_revision,context.saved.sources.revision);return {...preview(),context:data.context,request:'d'.repeat(32)};};run('api=mockApi');
        // Direct event delivery also cannot accept or execute the stale result.
        $('writer-accept').listeners.click[0]();await settle();$('writer-generate').listeners.click[0]();await settle();assert.equal(calls.length,0);
        $('writer-preview').listeners.click[0]();await settle();assert.deepEqual(calls,['/api/llm/preview']);
        assert.equal(run('writer.result.request'),'d'.repeat(32));assert.equal(run('writer.preview.context.source_revision'),context.saved.sources.revision);assert.equal($('writer-generate').disabled,true);
        consent();assert.equal($('writer-generate').disabled,false);
        ''')
    def test_stale_uncertain_dispatch_and_cancel_review_still_block_new_preview(self):
        self.dom(r'''
        selectAccountLocal();context.fetch=async()=>({ok:true,json:async()=>context.empty});await run('writingContextChanged("sample-mechanism")');ready();selectAccountLocal();shownPreview();
        const calls=[];context.mockApi=async(path)=>{calls.push(path);throw Error('No request expected');};run('api=mockApi');
        for(const status of ['dispatching','uncertain','received_after_cancel_review']){
          context.status=status;run('writer.result={...writer.result,status,context_current:false};writerControls()');
          assert.equal($('writer-preview').disabled,true);$('writer-preview').listeners.click[0]();await settle();assert.equal(calls.length,0);
        }
        ''')
    def test_each_editor_preserves_edits_made_while_its_save_is_pending(self):
        self.dom(r'''
        selectAccountLocal('sample-series');const initial={account:'sample-series',sources:null,canon:null};context.fetch=async()=>({ok:true,json:async()=>initial});await run('writingContextChanged("sample-series")');
        for(const kind of ['sources','canon']){
          const node=$('writing-'+kind+'-json');node.value=JSON.stringify({draft:'submitted'});node.listeners.input[0]();
          let release;const calls=[];context.mockApi=(path,body)=>{calls.push({path,body});return new Promise(resolve=>{release=resolve;});};run('api=mockApi');
          const pending=$(kind==='sources'?'writing-save-sources':'writing-accept-reference').listeners.click[0]();await settle();
          node.value=JSON.stringify({draft:'new edit during await'});node.listeners.input[0]();
          const result={...initial,[kind]:{revision:'e'.repeat(64),data:{draft:'submitted'}}};if(kind==='canon')result.canon.data.source_revision=null;
          release(result);await pending;assert.equal(calls.length,1);assert.equal(JSON.parse(node.value).draft,'new edit during await');
          assert.equal(run('writingContextReady("sample-series")'),false);assert.match($('writing-context-status').textContent,/düzenlemeler korundu/);
          assert.equal(run('writingContextRefs("sample-series").'+(kind==='sources'?'source_revision':'canon_revision')),'e'.repeat(64));
        }
        ''')
    def test_saving_one_editor_never_discards_other_unsaved_editor(self):
        self.dom(r'''
        for(const saved of ['sources','canon']){
          selectAccountLocal('sample-series');const initial={account:'sample-series',sources:null,canon:null};context.fetch=async()=>({ok:true,json:async()=>initial});await run('writingContextChanged("sample-series")');
          const other=saved==='sources'?'canon':'sources',otherNode=$('writing-'+other+'-json');otherNode.value=JSON.stringify({unsaved:other});otherNode.listeners.input[0]();
          $('writing-'+saved+'-json').value=JSON.stringify({submitted:saved});$('writing-'+saved+'-json').listeners.input[0]();
          const result={...initial,[saved]:{revision:'f'.repeat(64),data:{submitted:saved}}};if(saved==='canon')result.canon.data.source_revision=null;
          const calls=[];context.mockApi=async(path,body)=>{calls.push({path,body});return result;};run('api=mockApi');
          await $(saved==='sources'?'writing-save-sources':'writing-accept-reference').listeners.click[0]();
          assert.equal(calls.length,1);assert.equal(JSON.parse(otherNode.value).unsaved,other);assert.equal(JSON.parse($('writing-'+saved+'-json').value).submitted,saved);
          assert.equal(run('writingContextReady("sample-series")'),false);assert.match($('writing-context-status').textContent,/düzenlemeler korundu/);
          // Leave and reselect to isolate the second direction.
          selectAccountLocal();context.fetch=async()=>({ok:true,json:async()=>context.empty});await run('writingContextChanged("sample-mechanism")');
        }
        ''')
    def test_slow_read_keeps_same_account_edits_and_never_enables_generation(self):
        self.dom(r'''
        selectAccountLocal();let release;context.fetch=()=>new Promise(resolve=>{release=resolve;});const pending=run('writingContextChanged("sample-mechanism")');
        $('writing-sources-json').value='{"new":"local"}';$('writing-sources-json').listeners.input[0]();release({ok:true,json:async()=>context.saved});await pending;
        assert.equal($('writing-sources-json').value,'{"new":"local"}');assert.equal(run('writingContextReady("sample-mechanism")'),false);assert.equal($('writer-preview').disabled,true);
        ''')
    def test_explicit_reload_discards_only_draft_versions_present_at_click(self):
        self.dom(r'''
        selectAccountLocal();context.fetch=async()=>({ok:true,json:async()=>context.empty});await run('writingContextChanged("sample-mechanism")');
        $('writing-sources-json').value='invalid local draft';$('writing-sources-json').listeners.input[0]();
        context.fetch=async()=>({ok:true,json:async()=>context.saved});await $('writing-context-reload').listeners.click[0]();
        assert.equal(JSON.parse($('writing-sources-json').value)['test-study'].title,context.saved.sources.data['test-study'].title);assert.equal(run('writingContextReady("sample-mechanism")'),true);
        ''')
    def test_native_disclosure_labels_and_no_storage_markup_or_secret_calls(self):
        attrs=next(n['attrs'] for n in MARKUP.nodes if n['attrs'].get('id')=='writing-context-panel');self.assertNotIn('open',attrs)
        for forbidden in ('innerHTML','localStorage','sessionStorage','console.log','/api/llm/connect','/api/llm/execute'):self.assertNotIn(forbidden,PANEL)
        for id in ('writing-source-rights','writing-canon-confirm','writing-canon-rights'):
            self.assertTrue(any(n['tag']=='label' and n['attrs'].get('for')==id for n in MARKUP.nodes))


if __name__=='__main__':unittest.main()
