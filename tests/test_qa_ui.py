from pack_fixture_case import PackFixtureCase
from storymotion.account_packs import account_catalog
"""Host-mapped QA UI contracts, entirely offline with bounded synthetic data."""
import json
import shutil
import subprocess
import unittest
from test_compact_ui import BOOT, MARKUP, JS, ROOT

QA_JS = (ROOT / 'dashboard/qa-panel.js').read_text()
QA_SETUP = r'''
vm.runInContext(QA_SOURCE,context);
run('tab("qa")');
const job='c'.repeat(24), hash='d'.repeat(64);
function ready(){run(`qaReview.job='${job}';qaReview.engine='hyperframes';qaReview.renderComplete=true;qaReview.renderHash='${hash}';reviewControls();`);}
function data(overrides={}){return {review_id:'review-001',state:'ready',status:'incomplete',render_sha256:hash,coverage:{planned:4,captured:4,pages:1},issues:[],files:{'contact-board.png':'hash','transition-strip.png':'hash','smoke.json':'hash'},...overrides};}
const settle=()=>new Promise(resolve=>setImmediate(resolve));
'''


@unittest.skipUnless(shutil.which('node'), 'Node required for QA DOM contracts')
class QaUi(PackFixtureCase):
    def dom(self, body):
        script = BOOT.replace('STRUCTURE', json.dumps(MARKUP.nodes)).replace('SOURCE', json.dumps(JS))
        script = script.replace('CATALOG', json.dumps(account_catalog(json.loads((ROOT / 'catalog/accounts.json').read_text()))))
        script = script.replace('PROVIDERS', json.dumps(json.loads((ROOT / 'catalog/providers.json').read_text())['providers']))
        script = script.replace('async function scenario(){ BODY }', QA_SETUP.replace('QA_SOURCE', json.dumps(QA_JS)) + '\nasync function scenario(){ BODY }')
        result = subprocess.run(['node'], input=script.replace('BODY', body), text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_create_requires_complete_hash_bound_render(self):
        self.dom(r'''
        let calls=0;context.mockApi=async(path)=>{calls++;assert.match(path,/\/review-create$/);return data();};run('api=mockApi');
        run(`qaReview.job='${job}';qaReview.engine='hyperframes';reviewControls();`);
        $('qa-review-create').listeners.click[0]();await settle();assert.equal(calls,0);assert.equal($('qa-review-create').disabled,true);
        run(`reviewRenderState('${job}','hyperframes',{status:'complete',files:{}})`);assert.equal($('qa-review-create').disabled,true);
        run(`reviewRenderState('${job}','hyperframes',{status:'complete',files:{'render-1080.mp4':'${hash}'}})`);assert.equal($('qa-review-create').disabled,false);
        $('qa-review-create').listeners.click[0]();await settle();assert.equal(calls,1);assert.equal($('qa-issue-save').disabled,false);
        assert.match($('qa-review-summary').textContent,/INCOMPLETE.*İnsan QA/);
        ''')

    def test_only_registered_safe_basenames_become_links_and_images(self):
        self.dom(r'''
        ready();context.evidence=data({files:{'contact-board.png':'hash','transition-strip.webp':'hash','smoke.json':'hash','proof.svg':'hash','../escape.png':'hash','https://evil.test/p.png':'hash','encoded%2fpath.png':'hash','.hidden.png':'hash'}});run('reviewDisplay(evidence)');
        const links=$('qa-review-files').children;assert.equal(links.length,4);
        for(const link of links)assert.match(link.href,/^\/review-files\/[a-f0-9]{24}\/hyperframes\/[A-Za-z0-9._-]+$/);
        const images=$('qa-review-images').children.map(n=>n.children[0]);assert.equal(images.length,2);
        for(const image of images){assert.match(image.src,/\.(png|webp)$/);assert.ok(!image.src.includes('evil'));assert.ok(image.alt);}
        assert.equal(run("reviewFileURL('not-listed.png')"),null);assert.equal(run("reviewFileURL('../escape.png')"),null);
        ''')

    def test_status_wrapping_and_stale_hash_fail_closed(self):
        self.dom(r'''
        ready();context.evidence={review:data({status:'pass'})};run('reviewDisplay(evidence)');assert.match($('qa-review-summary').textContent,/PASS.*İnsan QA/);
        assert.equal($('qa-review-recheck').disabled,false);$('qa-issue-description').focus();
        run("qaReview.renderHash='e'.repeat(64);reviewSummary();reviewControls()");
        assert.equal($('qa-issue-save').disabled,true);assert.equal($('qa-review-recheck').disabled,true);assert.equal(visible($('qa-issue-form')),false);
        assert.equal(document.activeElement,$('qa-review-title'));assert.equal(visible(document.activeElement),true);
        assert.equal($('qa-review-summary').dataset.status,'incomplete');assert.match($('qa-review-summary').textContent,/^(INCOMPLETE|INVALIDATED)/);assert.doesNotMatch($('qa-review-summary').textContent,/\bPASS\b/);
        context.evidence=data({state:'invalidated',status:'fail'});run('reviewDisplay(evidence)');assert.equal($('qa-issue-save').disabled,true);
        ''')

    def test_render_state_change_cannot_keep_stale_pass_visible(self):
        self.dom(r'''
        ready();context.evidence=data({status:'pass'});run('reviewDisplay(evidence)');assert.match($('qa-review-summary').textContent,/^PASS/);
        run(`reviewRenderState('${job}','hyperframes',{status:'complete',files:{'render-1080.mp4':'e'.repeat(64)}})`);
        assert.match($('qa-review-summary').textContent,/^(INCOMPLETE|INVALIDATED)/);assert.doesNotMatch($('qa-review-summary').textContent,/\bPASS\b/);
        assert.equal($('qa-review-summary').dataset.status,'incomplete');assert.equal($('qa-review-recheck').disabled,true);assert.equal($('qa-issue-save').disabled,true);
        run(`reviewRenderState('${job}','hyperframes',{status:'running',files:{'render-1080.mp4':'${hash}'}})`);
        assert.match($('qa-review-summary').textContent,/^INCOMPLETE/);assert.doesNotMatch($('qa-review-summary').textContent,/\bPASS\b/);
        ''')

    def test_state_error_blocks_previous_pass_until_verified_refresh(self):
        self.dom(r'''
        ready();context.evidence=data({status:'pass'});run('reviewDisplay(evidence)');
        context.mockApi=async()=>{throw Error('Synthetic state read failed');};run('api=mockApi');
        try{await run('reviewLoad()');}catch{}
        assert.match($('qa-review-summary').textContent,/^INCOMPLETE/);assert.doesNotMatch($('qa-review-summary').textContent,/\bPASS\b/);
        assert.equal($('qa-review-summary').dataset.status,'incomplete');assert.equal($('qa-review-recheck').disabled,true);assert.equal(run('reviewIsCurrent()'),false);
        context.mockApi=async()=>data({status:'pass'});run('api=mockApi');await run('reviewLoad()');
        assert.match($('qa-review-summary').textContent,/^PASS/);assert.equal($('qa-review-summary').dataset.status,'pass');assert.equal($('qa-review-recheck').disabled,false);
        ''')

    def test_action_error_does_not_leave_pass_status_or_enabled_actions(self):
        self.dom(r'''
        ready();context.evidence=data({status:'pass'});run('reviewDisplay(evidence)');
        context.mockApi=async()=>{throw Error('Synthetic recheck failed');};run('api=mockApi');await run("reviewAction('review-recheck',{})");
        assert.match($('qa-review-summary').textContent,/^INCOMPLETE/);assert.doesNotMatch($('qa-review-summary').textContent,/\bPASS\b/);
        assert.equal($('qa-review-summary').dataset.status,'incomplete');assert.equal($('qa-review-recheck').disabled,true);assert.equal($('qa-issue-save').disabled,true);
        ''')

    def test_plan_error_cannot_leave_prior_pass_visible(self):
        self.dom(r'''
        ready();context.mockApi=async()=>{throw Error('Synthetic plan verification failed');};run('api=mockApi');
        context.evidence=data({status:'pass',files:{'plan.json':'hash'}});run('reviewDisplay(evidence)');await settle();
        assert.match($('qa-review-summary').textContent,/^INCOMPLETE/);assert.doesNotMatch($('qa-review-summary').textContent,/\bPASS\b/);
        assert.equal($('qa-review-summary').dataset.status,'incomplete');assert.equal($('qa-review-recheck').disabled,true);
        ''')

    def test_late_error_from_previous_engine_does_not_invalidate_current_review(self):
        self.dom(r'''
        ready();context.evidence=data({status:'pass'});run('reviewDisplay(evidence)');let reject;
        context.mockApi=async()=>new Promise((resolve,fail)=>{reject=fail;});run('api=mockApi');const pending=run('reviewLoad()');
        run("qaReview.epoch++;qaReview.engine='remotion';reviewDisplay(evidence)");reject(Error('Old engine failed'));
        try{await pending;}catch{}
        assert.match($('qa-review-summary').textContent,/^PASS/);assert.equal($('qa-review-summary').dataset.status,'pass');assert.equal(run('reviewIsCurrent()'),true);
        ''')

    def test_integer_crop_scene_membership_and_issue_payload(self):
        self.dom(r'''
        ready();context.evidence=data();run('reviewDisplay(evidence)');
        run("qaReview.plan={frame_count:120,fps:30,viewport:{width:1080,height:1920},scene_ranges:[{id:'s1',start_frame:0,end_frame_exclusive:60},{id:'s2',start_frame:60,end_frame_exclusive:120}]}");
        const fill={'qa-issue-frame':'30','qa-issue-scene':'s1','qa-issue-severity':'major','qa-issue-description':'Synthetic text overlap','qa-issue-fix':'Adjust local text placement','qa-affected-scenes':'s1','qa-affected-checks':'text_safe_area','qa-bound-x':'20','qa-bound-y':'40','qa-bound-width':'200','qa-bound-height':'100'};
        for(const [id,value] of Object.entries(fill))$(id).value=value;
        let sent;context.mockApi=async(path,payload)=>{sent=payload;assert.match(path,/\/review-issue$/);return data();};run('api=mockApi');
        $('qa-issue-form').listeners.submit[0]({preventDefault(){}});await settle();
        assert.equal(sent.engine,'hyperframes');assert.equal(sent.issue.frame,30);assert.equal(sent.issue.bounds.width,200);assert.equal(sent.issue.scene_id,'s1');
        assert.equal(sent.issue.affected_scene_ids[0],'s1');assert.equal(sent.issue.local_fix,'Adjust local text placement');
        $('qa-bound-x').value='1.5';assert.throws(()=>run('reviewIssue()'));$('qa-bound-x').value='1000';assert.throws(()=>run('reviewIssue()'));
        $('qa-bound-x').value='20';$('qa-issue-frame').value='61';assert.throws(()=>run('reviewIssue()'));
        $('qa-issue-frame').value='30';$('qa-affected-scenes').value='s2';assert.throws(()=>run('reviewIssue()'));
        ''')

    def test_resolve_and_recheck_are_explicit_never_human_acceptance(self):
        self.dom(r'''
        ready();const issue={id:'issue-1',frame:30,scene_id:'s1',severity:'major',status:'open',description:'Synthetic defect',local_fix:'Local note',crop_evidence_id:'crop-issue-1'};
        context.evidence=data({issues:[issue],files:{'crop-issue-1.png':'hash'}});run('reviewDisplay(evidence)');
        assert.equal($('qa-review-issues').children.length,1);assert.equal($('qa-resolve-issue').value,'issue-1');
        const calls=[];context.mockApi=async(path,payload)=>{calls.push({path,payload});return data({issues:[{...issue,status:'fixed',local_fix:payload.local_fix||'Local note'}]});};run('api=mockApi');
        assert.equal(calls.length,0);$('qa-resolve-fix').value='Changed only the local placement';$('qa-resolve-form').listeners.submit[0]({preventDefault(){}});await settle();
        assert.equal(calls.length,1);assert.match(calls[0].path,/\/review-resolve$/);assert.equal(calls[0].payload.issue_id,'issue-1');assert.equal(calls[0].payload.local_fix,'Changed only the local placement');
        assert.match($('qa-review-summary').textContent,/INCOMPLETE.*İnsan QA/);
        $('qa-review-recheck').listeners.click[0]();await settle();assert.equal(calls.length,2);assert.match(calls[1].path,/\/review-recheck$/);
        assert.ok(!calls.some(x=>/accept|publish|provider|execute/.test(x.path)));
        ''')

    def test_late_job_engine_response_is_ignored(self):
        self.dom(r'''
        ready();let release;context.mockApi=async()=>new Promise(resolve=>{release=resolve;});run('api=mockApi');
        const pending=run('reviewLoad()');run("qaReview.epoch++;qaReview.engine='remotion';qaReview.data=null");release(data());await pending;
        assert.equal(run('qaReview.data'),null);assert.equal($('qa-review-images').children.length,0);
        ''')

    def test_plan_metadata_supplies_scene_ids_and_raw_display_is_bounded(self):
        self.dom(r'''
        ready();const plan={render_sha256:hash,frame_count:120,fps:30,viewport:{width:1080,height:1920},scene_ranges:[{id:'actual-scene',start_frame:0,end_frame_exclusive:120}]};
        context.mockApi=async(path)=>{assert.match(path,/\/plan\.json$/);return plan;};run('api=mockApi');
        context.evidence=data({files:{'plan.json':'hash'},extra:'x'.repeat(25000)});run('reviewDisplay(evidence)');await settle();
        assert.equal($('qa-issue-scene').value,'');assert.equal($('qa-scene-options').children[0].value,'actual-scene');assert.equal($('qa-issue-frame').max,119);
        assert.match($('qa-bounds-note').textContent,/1080.*1920/);assert.ok($('qa-review-raw').textContent.length<20100);
        ''')
        for forbidden in ['localStorage', 'sessionStorage', 'innerHTML', 'console.log', 'console.error']:
            self.assertNotIn(forbidden, QA_JS)


if __name__ == '__main__':
    unittest.main()
