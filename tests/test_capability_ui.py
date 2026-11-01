from pack_fixture_case import PackFixtureCase
from storymotion.account_packs import account_catalog
"""Capability catalog navigation contracts. Catalog actions never dispatch a provider."""
import json
import shutil
import subprocess
import unittest
from test_compact_ui import BOOT, MARKUP, JS, CSS, ROOT
from storymotion.provider_catalog import build_registry, public_capabilities

PUBLIC = public_capabilities(build_registry())
EMPTY = public_capabilities(build_registry({}, local_renderers=()))
SETUP = r'''
const fixture=PUBLIC_FIXTURE, emptyFixture=EMPTY_FIXTURE;
context.fixture=fixture;context.emptyFixture=emptyFixture;
run('capabilityCatalog(fixture);writerConfig({mode:"off",providers:["openai","anthropic","gemini","openrouter"]});voiceConfig({mode:"off"});tab("capabilities")');
const row=(provider,capability)=>fixture.find(r=>r.provider===provider&&r.capability===capability);
const card=(provider,capability)=>$('capability-list').children.find(n=>n.dataset.provider===provider&&n.dataset.capability===capability);
const actionButton=node=>node.children.find(n=>n.tagName==='button');
const settle=()=>new Promise(resolve=>setImmediate(resolve));
'''


@unittest.skipUnless(shutil.which('node'), 'Node required for catalog DOM contracts')
class CapabilityUi(PackFixtureCase):
    def dom(self, body):
        script = BOOT.replace('STRUCTURE', json.dumps(MARKUP.nodes)).replace('SOURCE', json.dumps(JS))
        script = script.replace('CATALOG', json.dumps(account_catalog(json.loads((ROOT / 'catalog/accounts.json').read_text()))))
        script = script.replace('PROVIDERS', json.dumps(json.loads((ROOT / 'catalog/providers.json').read_text())['providers']))
        setup = SETUP.replace('PUBLIC_FIXTURE', json.dumps(PUBLIC)).replace('EMPTY_FIXTURE', json.dumps(EMPTY))
        script = script.replace('async function scenario(){ BODY }', setup + '\nasync function scenario(){ BODY }')
        result = subprocess.run(['node'], input=script.replace('BODY', body), text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_registry_counts_and_modality_filters_are_honest(self):
        self.dom(r'''
        assert.equal($('capability-list').children.length,fixture.length);
        const expected=fixture.filter(r=>r.adapter_registered&&r.selectable).length;
        assert.match($('capability-summary').textContent,new RegExp(expected+' kayıtlı adaptör'));
        for(const category of ['text','image','video','audio','render']){
          $('capability-category').value=category;$('capability-category').listeners.change[0]();
          for(const article of $('capability-list').children){const entry=row(article.dataset.provider,article.dataset.capability);context.entry=entry;assert.equal(run('capabilityFamily(entry)'),category);}
        }
        $('capability-category').value='all';$('capability-status-filter').value='registered';run('capabilityList()');assert.equal($('capability-list').children.length,expected);
        $('capability-status-filter').value='unavailable';run('capabilityList()');assert.equal($('capability-list').children.length,fixture.length-expected);
        assert.equal($('writer-model').children.length,0);
        ''')

    def test_planned_same_provider_capability_has_no_connection_action(self):
        self.dom(r'''
        const image=card('openai','image_generation'),text=card('openai','text');
        assert.match(image.textContent,/Planlandı · bağlantı yok/);assert.equal(actionButton(image).disabled,true);
        assert.equal(actionButton(image).attrs['aria-disabled'],'true');assert.equal(actionButton(image).listeners.click,undefined);
        assert.equal(actionButton(text).disabled,false);assert.match(actionButton(text).textContent,/Yazarı aç/);
        $('writer-key').value='FAKE_NOT_SHARED';context.entry=row('openai','image_generation');run('capabilityOpen(entry)');
        assert.equal(visible($('tab-capabilities')),true);assert.equal($('el-key').value,'');assert.equal($('writer-key').value,'FAKE_NOT_SHARED');
        assert.equal(run('writer.connection'),null);assert.equal(run('voice.connection'),null);
        ''')

    def test_writer_navigation_off_is_not_connect_or_generation(self):
        self.dom(r'''
        $('writer-key').value='FAKE_OLD_FIELD';const button=actionButton(card('gemini','text'));button.listeners.click[0]();
        assert.equal(visible($('tab-writer')),true);assert.equal($('writer-provider').value,'gemini');assert.equal($('writer-key').value,'');
        assert.equal($('writer-connect').disabled,true);assert.equal(run('writer.connection'),null);assert.equal(run('writer.preview'),null);
        assert.equal(document.activeElement,$('writer-how').querySelector('summary'));assert.match($('writer-mode').textContent,/Bağlantılar kapalı/);
        assert.match($('writer-status').textContent,/bağlantı veya üretim başlatılmadı/);
        ''')

    def test_existing_connection_is_never_rebound_by_catalog_click(self):
        self.dom(r'''
        run("writerConfig({mode:'demo'});writer.connection='a'.repeat(32);writer.provider='openai';writer.expiresAt=Date.now()+900000;writerMetadata({provider:'openai',models:[{id:'synthetic-openai',name:'Synthetic contract'}]});");
        const selected=$('writer-provider').value;actionButton(card('gemini','text')).listeners.click[0]();
        assert.equal(run('writer.provider'),'openai');assert.equal(run('writer.connection'),'a'.repeat(32));assert.equal($('writer-provider').value,selected);
        assert.match($('writer-status').textContent,/önce bu bağlantıyı kesin/);assert.equal(document.activeElement,$('writer-disconnect'));
        assert.equal(run('voice.connection'),null);
        ''')

    def test_voice_and_local_render_navigation_do_not_share_keys_or_dispatch(self):
        self.dom(r'''
        $('writer-key').value='FAKE_TEXT_ONLY';actionButton(card('elevenlabs','voice')).listeners.click[0]();
        assert.equal($('el-key').value,'');assert.equal($('writer-key').value,'FAKE_TEXT_ONLY');assert.equal(document.activeElement,$('el-how').querySelector('summary'));
        const engine=$('render-engine').value;actionButton(card('remotion','animation_render')).listeners.click[0]();
        assert.equal(visible($('tab-qa')),true);assert.equal($('render-engine').value,engine);assert.equal(document.activeElement,$('render-title'));
        assert.match($('notice').textContent,/render başlatılmadı/);
        assert.equal(run('writer.connection'),null);assert.equal(run('voice.connection'),null);
        assert.match(card('hyperframes','animation_render').textContent,/doctor/);
        ''')

    def test_descriptive_json_without_registered_adapter_cannot_unlock_writer(self):
        self.dom(r'''
        run("capabilityCatalog(emptyFixture);writerConfig({mode:'demo',providers:['openai','runway']})");
        assert.equal($('writer-provider').children.length,0);assert.equal($('writer-connect').disabled,true);
        for(const article of $('capability-list').children)assert.equal(actionButton(article).disabled,true);
        assert.match(card('openai','text').textContent,/Kayıtlı adaptör yok/);
        $('writer-provider').value='openai';$('writer-key').value='FAKE_NOT_ALLOWED';$('writer-connect-form').listeners.submit[0]({preventDefault(){}});await settle();
        assert.equal(run('writer.connection'),null);assert.equal($('writer-key').value,'');assert.equal($('writer-model').children.length,0);
        ''')

    def test_new_host_registered_text_adapter_is_not_rejected_by_global_four_list(self):
        self.dom(r'''
        const extension={...row('openai','text'),provider:'future_text',name:'Yeni kayıtlı metin adaptörü',documentation:[]};context.extended=[...fixture,extension];
        run("capabilityCatalog(extended);writerConfig({mode:'demo',providers:['future_text']})");
        assert.equal($('writer-provider').children.length,1);assert.equal($('writer-provider').value,'');assert.equal($('writer-model').children.length,0);$('writer-provider').value='future_text';
        let calls=0;context.mockApi=async(path,payload)=>{calls++;assert.equal(path,'/api/llm/connect');assert.equal(payload.provider,'future_text');return {connection:'a'.repeat(32),ttl_seconds:900,metadata:{provider:'future_text',models:[{id:'server-listed-model',name:'Only server metadata'}]}};};run('api=mockApi');
        $('writer-key').value='FAKE_FUTURE_CONTRACT';$('writer-connect-form').listeners.submit[0]({preventDefault(){}});await settle();
        assert.equal(calls,1);assert.equal(run('writer.provider'),'future_text');assert.equal($('writer-model').value,'server-listed-model');
        assert.equal($('writer-generate').disabled,true);
        ''')

    def test_unknown_api_is_disabled_and_document_links_are_safe(self):
        self.dom(r'''
        const unknown={...row('openai','image_generation'),provider:'unknown_vendor',name:'Unknown API',status:'unknown_not_verified',adapter_registered:false,selectable:false,documentation:[{title:'Bad',url:'javascript:alert(1)'},{title:'Bad userinfo',url:'https://user@example.com/docs'},{title:'Reference',url:'https://example.com/docs'}]};context.unknown=[...fixture,unknown];run('capabilityCatalog(unknown)');
        const article=card('unknown_vendor','image_generation');assert.match(article.textContent,/API durumu belirsiz/);assert.equal(actionButton(article).disabled,true);
        const links=article.children.find(n=>n.tagName==='details').children.filter(n=>n.tagName==='a');assert.equal(links.length,1);assert.equal(links[0].href,'https://example.com/docs');assert.equal(links[0].rel,'noopener noreferrer');
        assert.equal(article.children.find(n=>n.tagName==='details').children[0].tagName,'summary');
        assert.ok(!all.some(n=>n.id.includes('endpoint')));
        ''')
        for forbidden in ['localStorage', 'sessionStorage', 'innerHTML', 'console.log', 'console.error']:
            self.assertNotIn(forbidden, JS)
        self.assertIn('.capability-filters', CSS)
        self.assertIn('@media(max-width:700px)', CSS)


if __name__ == '__main__':
    unittest.main()
