from pack_fixture_case import PackFixtureCase
from storymotion.account_packs import account_catalog
import json
import shutil
import subprocess
import unittest
from test_compact_ui import BOOT,MARKUP,JS,ROOT
from storymotion.workflow_state import workflow_status

PANEL=(ROOT/'dashboard/workflow-panel.js').read_text()


@unittest.skipUnless(shutil.which('node'),'Node required for offline DOM contracts')
class WorkflowPanelTests(PackFixtureCase):
    def dom(self,body):
        script=BOOT.replace('STRUCTURE',json.dumps(MARKUP.nodes)).replace('SOURCE',json.dumps(JS)).replace('CATALOG',json.dumps(account_catalog(json.loads((ROOT/'catalog/accounts.json').read_text())))).replace('PROVIDERS',json.dumps(json.loads((ROOT/'catalog/providers.json').read_text())['providers']))
        setup='context.fixture='+json.dumps(workflow_status())+';vm.runInContext('+json.dumps(PANEL)+',context);'
        script=script.replace('async function scenario(){ BODY }',setup+'\nasync function scenario(){ BODY }').replace('BODY',body)
        result=subprocess.run(['node'],input=script,text=True,capture_output=True,timeout=15);self.assertEqual(result.returncode,0,result.stderr)
    def test_disclosure_shows_bounds_without_mutating_forms_or_connecting(self):
        self.dom(r'''
        let calls=0;context.fetch=async(path,options)=>{calls++;assert.equal(path,'/api/workflows');assert.equal(options.method,undefined);assert.equal(options.body,undefined);return{ok:true,json:async()=>context.fixture};};
        $('title').value='Korunan başlık';$('writer-key').value='FAKE_UI_FIELD_ONLY';$('workflow-details').open=true;
        await run('workflowAccountChanged("sample-flow")');
        assert.equal(calls,1);assert.equal($('workflow-stages').children.length,12);assert.match($('workflow-summary').textContent,/eksik/);
        assert.match($('workflow-evidence').textContent,/Bu kaynak sürümünün native kabulü bekliyor/);assert.match($('workflow-context').textContent,/Sample Flow/);
        assert.equal($('title').value,'Korunan başlık');assert.equal($('writer-key').value,'FAKE_UI_FIELD_ONLY');assert.equal($('workflow-details').open,true);
        assert.equal(run('writer.connection'),null);assert.equal(run('voice.connection'),null);
        ''')
    def test_slow_old_account_response_cannot_replace_latest_topic(self):
        self.dom(r'''
        const requests=[];context.fetch=()=>new Promise(resolve=>requests.push(resolve));
        const first=run('workflowAccountChanged("sample-reflection")');const second=run('workflowAccountChanged("sample-series")');
        requests[1]({ok:true,json:async()=>context.fixture});await second;
        requests[0]({ok:true,json:async()=>context.fixture});await first;
        assert.match($('workflow-context').textContent,/Sample Series/);assert.equal($('workflow-stages').children.length,12);
        ''')
    def test_bad_or_failed_inventory_clears_old_status_instead_of_leaving_ready_text(self):
        self.dom(r'''
        context.fetch=async()=>({ok:true,json:async()=>context.fixture});await run('workflowAccountChanged("sample-reflection")');
        context.fetch=async()=>({ok:false});await run('workflowAccountChanged("sample-series")');
        assert.match($('workflow-summary').textContent,/doğrulanamadı/);assert.equal($('workflow-stages').children.length,0);
        const bad=JSON.parse(JSON.stringify(context.fixture));bad.publication_ready=true;
        context.fetch=async()=>({ok:true,json:async()=>bad});await run('workflowAccountChanged("sample-reflection")');
        assert.match($('workflow-summary').textContent,/doğrulanamadı/);assert.equal($('workflow-stages').children.length,0);
        ''')
    def test_native_details_semantics_and_text_only_rendering(self):
        detail=next(x for x in MARKUP.nodes if x['attrs'].get('id')=='workflow-details')
        self.assertNotIn('open',detail['attrs']);self.assertIn('aria-live="polite"',(ROOT/'dashboard/index.html').read_text())
        for forbidden in ('innerHTML','localStorage','sessionStorage','POST','console.log'):self.assertNotIn(forbidden,PANEL)


if __name__=='__main__':unittest.main()
