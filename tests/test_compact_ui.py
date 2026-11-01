from pack_fixture_case import PackFixtureCase
from storymotion.account_packs import account_catalog
"""Offline markup and DOM-contract checks; actual browser acceptance is separate."""
import json
from html.parser import HTMLParser
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / 'dashboard/index.html').read_text()
JS = (ROOT / 'dashboard/app.js').read_text()
CSS = (ROOT / 'dashboard/style.css').read_text()


class Markup(HTMLParser):
    def __init__(self):
        super().__init__()
        self.nodes = []
        self.stack = []
        self.feed(HTML)

    def handle_starttag(self, tag, attrs):
        node = {'tag': tag, 'attrs': dict(attrs), 'parent': self.stack[-1] if self.stack else None}
        self.nodes.append(node)
        index = len(self.nodes) - 1
        if tag not in {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}:
            self.stack.append(index)

    def handle_endtag(self, tag):
        for position in range(len(self.stack) - 1, -1, -1):
            if self.nodes[self.stack[position]]['tag'] == tag:
                del self.stack[position:]
                return

    def ancestors(self, node):
        while node['parent'] is not None:
            node = self.nodes[node['parent']]
            yield node


MARKUP = Markup()
BOOT = r'''
const assert=require('node:assert/strict'), vm=require('node:vm');
const structure=STRUCTURE;
const all=[], byId={};
class Element {
  constructor(tag,attrs={}){this.tagName=tag;this.attrs={...attrs};this.children=[];this.parentElement=null;this.listeners={};this.hidden='hidden' in attrs;this.disabled='disabled' in attrs;this.required='required' in attrs;this.checked='checked' in attrs;this.open='open' in attrs;this._value=attrs.value||'';this._text='';this.dataset={};for(const k in attrs)if(k.startsWith('data-'))this.dataset[k.slice(5)]=attrs[k];this.className=attrs.class||'';this.classList={toggle(){}};}
  get id(){return this.attrs.id||'';}
  set value(value){this._value=String(value);}
  get value(){return this._value;}
  get selectedOptions(){return this.children.filter(n=>n.value===this.value).slice(0,1);}
  get textContent(){return this._text+this.children.map(n=>n.textContent).join('');}
  set textContent(value){this._text=String(value);this.children=[];}
  append(...nodes){for(const node of nodes){node.parentElement=this;this.children.push(node);if(this.tagName==='select'&&this.children.length===1)this._value=node.value;}}
  replaceChildren(...nodes){this.children=[];this._text='';if(this.tagName==='select')this._value='';this.append(...nodes);}
  addEventListener(name,fn){(this.listeners[name]??=[]).push(fn);}
  setAttribute(k,v){this.attrs[k]=String(v);}
  removeAttribute(k){delete this.attrs[k];}
  contains(node){return node===this||this.children.some(n=>n.contains(node));}
  querySelector(tag){return this.children.find(n=>n.tagName===tag)||this.children.map(n=>n.querySelector(tag)).find(Boolean);}
  focus(){if(!this.disabled&&visible(this))document.activeElement=this;}
}
function visible(node){for(let n=node;n;n=n.parentElement){if(n.hidden)return false;if(n.parentElement?.tagName==='details'&&!n.parentElement.open&&n.tagName!=='summary')return false;}return true;}
for(const item of structure){const node=new Element(item.tag,item.attrs);all.push(node);if(node.id)byId[node.id]=node;if(item.parent!==null)all[item.parent].append(node);}
const document={activeElement:null,getElementById:id=>{assert.ok(byId[id],`Unknown element: ${id}`);return byId[id];},createElement:tag=>new Element(tag),querySelectorAll:selector=>selector==='[data-tab]'?all.filter(n=>'tab' in n.dataset):selector==='.tab-panel'?all.filter(n=>n.className.split(' ').includes('tab-panel')):[]};
const window={listeners:{},addEventListener(name,fn){(this.listeners[name]??=[]).push(fn);}};
let network=0;
const context=vm.createContext({document,window,setTimeout:()=>1,clearTimeout:()=>{},fetch:()=>{network++;throw Error('Network forbidden in offline UI tests');}});
vm.runInContext(SOURCE.replace(/\nstart\(\);\s*$/,''),context);
const run=code=>vm.runInContext(code,context);
const $=id=>document.getElementById(id);
const catalog=CATALOG, providers=PROVIDERS;
run('state.catalog='+JSON.stringify(catalog)+';state.providers='+JSON.stringify(providers)+';');
async function scenario(){ BODY }
scenario().then(()=>assert.equal(network,0)).catch(error=>{console.error(error);process.exitCode=1;});
'''


@unittest.skipUnless(shutil.which('node'), 'Node is required for offline DOM contracts')
class CompactUi(PackFixtureCase):
    def dom(self, body):
        script = BOOT.replace('STRUCTURE', json.dumps(MARKUP.nodes)).replace('SOURCE', json.dumps(JS))
        script = script.replace('CATALOG', json.dumps(account_catalog(json.loads((ROOT / 'catalog/accounts.json').read_text()))))
        script = script.replace('PROVIDERS', json.dumps(json.loads((ROOT / 'catalog/providers.json').read_text())['providers']))
        script = script.replace('BODY', body)
        result = subprocess.run(['node'], input=script, text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_unique_ids_and_control_labels(self):
        ids = [n['attrs']['id'] for n in MARKUP.nodes if 'id' in n['attrs']]
        self.assertEqual(len(ids), len(set(ids)))
        labels = {n['attrs'].get('for') for n in MARKUP.nodes if n['tag'] == 'label'}
        controls = {n['attrs']['id'] for n in MARKUP.nodes if n['tag'] in {'input', 'select', 'textarea'}}
        self.assertTrue(controls <= labels, controls - labels)
        self.assertTrue(labels <= set(ids))

    def test_native_disclosure_and_final_consent_structure(self):
        for node in (n for n in MARKUP.nodes if n['tag'] == 'details'):
            children = [n for n in MARKUP.nodes if n['parent'] == MARKUP.nodes.index(node)]
            self.assertEqual(children[0]['tag'], 'summary')
            self.assertNotIn('role', children[0]['attrs'])
            self.assertNotIn('open', node['attrs'])
        for id_ in ['el-cost-ack', 'el-rights-ack', 'el-generate', 'el-exact-text', 'el-price-status', 'el-live-budget']:
            node = next(n for n in MARKUP.nodes if n['attrs'].get('id') == id_)
            ancestors = list(MARKUP.ancestors(node))
            self.assertNotIn('details', [n['tag'] for n in ancestors], id_)
            self.assertIn('el-step-approve', [n['attrs'].get('id') for n in ancestors])
        for id_ in ['el-cost-ack', 'el-rights-ack']:
            attrs = next(n['attrs'] for n in MARKUP.nodes if n['attrs'].get('id') == id_)
            self.assertIn('required', attrs)
            self.assertNotIn('checked', attrs)

    def test_off_and_disconnected_modes_hide_unavailable_fields(self):
        self.dom(r'''
        run("voiceConfig({mode:'off'})");
        assert.equal(visible($('el-flow')),false);assert.equal(visible($('el-key')),false);
        assert.equal($('el-connect').disabled,true);assert.equal(visible($('el-how')),true);
        for(const mode of ['demo','live']){
          run(`voiceConfig({mode:'${mode}'})`);
          assert.equal(visible($('el-key')),true);assert.equal($('el-connect').disabled,false);
          for(const id of ['el-step-select','el-step-text','el-step-approve'])assert.equal(visible($(id)),false);
          assert.equal(visible($('el-how')),false);assert.equal($('el-generate').disabled,true);
        }
        ''')

    def test_connected_preview_and_explicit_consents(self):
        self.dom(r'''
        run("voiceConfig({mode:'demo'});voice.connection='synthetic-connection';state.job={id:'j1',payload:{input:{title:'Deneme'},account:{id:'sample-series'},format:{name:'Hikaye'}}};voiceMetadata({voices:[{voice_id:'demo-v',name:'Demo ses'}],models:[{model_id:'demo-m',name:'Demo model',maximum_text_length_per_request:10000}]});");
        assert.equal(visible($('el-step-select')),true);assert.equal(visible($('el-step-text')),true);
        assert.equal(visible($('el-key')),false);assert.equal(visible($('el-step-approve')),false);
        $('el-tts').value='Sadece yerel deneme.';
        run("voice.preview={request:'p1',characters:20};voicePreviewSummary(voice.preview);voiceControls();");
        for(const id of ['el-exact-text','el-exact-selection','el-exact-limit','el-price-status','el-cost-ack','el-rights-ack','el-generate'])assert.equal(visible($(id)),true,id);
        assert.equal($('el-exact-text').textContent,'Sadece yerel deneme.');
        assert.match($('el-exact-selection').textContent,/Demo ses.*Demo model/);
        assert.match($('el-exact-limit').textContent,/20 karakter.*1 gönderim/);
        assert.equal($('el-generate').disabled,true);
        $('el-cost-ack').checked=true;run('voiceControls()');assert.equal($('el-generate').disabled,true);
        $('el-rights-ack').checked=true;run('voiceControls()');assert.equal($('el-generate').disabled,false);
        run('voiceResetPreview()');assert.equal(visible($('el-step-approve')),false);
        assert.equal($('el-cost-ack').checked,false);assert.equal($('el-rights-ack').checked,false);
        ''')

    def test_live_cost_gate_and_focus_after_disconnect(self):
        self.dom(r'''
        run("voiceConfig({mode:'live'});voice.connection='synthetic-connection';voice.preview={characters:12};voiceControls();");
        $('el-cost-ack').checked=true;$('el-rights-ack').checked=true;
        run('voiceControls()');assert.equal($('el-generate').disabled,true);
        for(const id of ['el-max-usd','el-estimate-usd','el-quote-source'])assert.equal($(id).required,true);
        $('el-max-usd').value='1';$('el-estimate-usd').value='0.5';$('el-quote-source').value='Synthetic quote, no charge';
        run('voiceControls()');assert.equal($('el-generate').disabled,false);
        $('el-estimate-usd').value='2';run('voiceControls()');assert.equal($('el-generate').disabled,true);
        $('el-estimate-usd').value='0.5';run('voiceControls()');$('el-generate').focus();
        run('voice.connection=null;voiceResetPreview();');
        assert.equal(document.activeElement,$('el-key'));assert.equal(visible(document.activeElement),true);
        assert.equal(visible($('el-step-select')),false);assert.equal(visible($('el-step-approve')),false);
        assert.equal($('el-generate').disabled,true);
        ''')

    def test_disclosure_preserves_values_and_connection_clears_password(self):
        self.dom(r'''
        $('llm-demo').hidden=false;$('llm-demo').open=true;
        const same=$('demo-key');same.value='FAKE_TRANSIENT_DEMO';$('budget').value='5';
        $('llm-demo').open=false;$('llm-plan').open=false;$('llm-demo').open=true;$('llm-plan').open=true;
        assert.equal($('demo-key'),same);assert.equal(same.value,'FAKE_TRANSIENT_DEMO');assert.equal($('budget').value,'5');
        run("voiceConfig({mode:'demo'});api=async(path,data)=>{if(path.endsWith('/connect'))return {connection:'only-mock',metadata:{voices:[{voice_id:'v',name:'Demo'}],models:[{model_id:'m',name:'Demo',maximum_text_length_per_request:10000}]}};throw Error('Unexpected API path');};");
        $('el-key').value='FAKE_EPHEMERAL_TEST';$('el-connect').focus();
        $('el-connect-form').listeners.submit[0]({preventDefault(){}});
        await new Promise(resolve=>setImmediate(resolve));
        assert.equal($('el-key').value,'');assert.equal(visible($('el-connected')),true);
        assert.equal(document.activeElement,$('el-voice'));assert.equal(visible(document.activeElement),true);
        run("voice.connection=null;voiceControls();api=async()=>{throw Error('Synthetic connection failure');};");
        $('el-key').value='FAKE_FAILURE_TEST';$('el-connect-form').listeners.submit[0]({preventDefault(){}});
        await new Promise(resolve=>setImmediate(resolve));
        assert.equal($('el-key').value,'');assert.equal(visible($('el-step-select')),false);
        ''')

    def test_topics_keep_profile_ids_and_brand_is_customer_owned(self):
        self.dom(r'''
        $('category').value='all';run('accountList()');
        const expected=['Sample Reflection','Sample Flow','Sample Mechanism','Sample Series'];
        const titles=$('account-list').children.map(n=>n.textContent);assert.equal(titles.length,4);
        for(const name of expected)assert.ok(titles.includes(name));
        assert.equal($('brand-name').value,'');assert.equal($('brand-handle').value,'');
        const sourceName='Neutral source fixture series',sourceHandle='@source_fixture_series';
        context.sourceName=sourceName;context.sourceHandle=sourceHandle;
        run("state.catalog.accounts.find(a=>a.id==='sample-series').name=sourceName;state.catalog.accounts.find(a=>a.id==='sample-series').handle=sourceHandle;");
        run("api=async()=>({revision:1,template:{video:{title:sourceName+' örneği',brief:'Yerel brief',script:'Değişmeyen metin.',caption:sourceHandle+' için demo'}}});");
        await run("selectAccount('sample-series')");
        assert.equal(run('state.account.id'),'sample-series');assert.equal($('account-name').textContent,'Sample Series');
        assert.equal($('content').value,'Değişmeyen metin.');assert.match($('caption').value,/Sample Series/);
        assert.ok(!$('title').value.includes(sourceName));assert.ok(!$('caption').value.includes(sourceHandle));
        assert.match($('title').value,/Sample Series/);
        $('brand-name').value='Müşteri Stüdyosu';$('brand-handle').value='@musteri';run('updateBrandHeading()');
        assert.equal($('account-name').textContent,'Müşteri Stüdyosu');assert.match($('account-handle').textContent,/@musteri/);
        let captured;context.capture=value=>{captured=value;};
        run("api=async(path,data)=>{if(path==='/api/jobs'){capture(data);return {id:'mock-job'};}throw Error('Unexpected path');};refreshJobs=async()=>{};");
        $('brief-form').listeners.submit[0]({preventDefault(){}});await new Promise(resolve=>setImmediate(resolve));
        assert.equal(captured.account,'sample-series');assert.equal(captured.brand_identity.name,'Müşteri Stüdyosu');assert.equal(captured.brand_identity.handle,'@musteri');
        $('brand-name').value='';$('brand-handle').value='';
        $('brief-form').listeners.submit[0]({preventDefault(){}});await new Promise(resolve=>setImmediate(resolve));
        assert.equal(captured.brand_identity.name,'');assert.equal(captured.brand_identity.handle,'');
        ''')

    def test_no_client_secret_persistence_and_mobile_focus_contract(self):
        for forbidden in ['localStorage', 'sessionStorage', 'innerHTML', 'console.log', 'console.error']:
            self.assertNotIn(forbidden, JS)
        self.assertIn('input.value=\'\'', JS)
        self.assertIn('[hidden]{display:none!important}', CSS)
        self.assertIn('summary:focus-visible', CSS)
        self.assertIn('@media(max-width:700px)', CSS)
        self.assertIn('minmax(0,1fr)', CSS)
        self.assertIn('overflow-wrap:anywhere', CSS)
        self.assertIn('@media(prefers-reduced-motion:reduce)', CSS)
        catalog = account_catalog(json.loads((ROOT / 'catalog/accounts.json').read_text()))
        for account in catalog['accounts']:
            self.assertTrue(account['display_name'])
            self.assertNotIn(account['display_name'], HTML)


if __name__ == '__main__':
    unittest.main()
