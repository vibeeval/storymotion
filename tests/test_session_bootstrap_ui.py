import shutil
import unittest

from pack_fixture_case import PackFixtureCase
import test_compact_ui as ui


@unittest.skipUnless(shutil.which('node'),'Node required for offline bootstrap DOM contracts')
class SessionBootstrapUI(PackFixtureCase):
    def test_one_time_fragment_is_removed_before_fetch_and_not_stored_in_app_state(self):
        ui.CompactUi().dom(r'''
        const token='FAKE_'+'B'.repeat(38),events=[];
        window.location={hash:'#bootstrap='+token,pathname:'/',search:''};
        window.history={replaceState(state,title,url){events.push('history');assert.equal(url,'/');window.location.hash='';}};
        context.fetch=async(path,options)=>{events.push('fetch');assert.equal(path,'/api/bootstrap');assert.equal(options.credentials,'same-origin');assert.equal(options.method,'POST');assert.equal(options.headers['X-Storymotion-Token'],token);assert.equal(options.headers['X-Storymotion-Local'],'1');assert.equal(options.body,'{}');return{ok:true};};
        await run('bootstrapSession()');assert.deepEqual(events,['history','fetch']);
        assert.equal(window.location.hash,'');assert.ok(!run('JSON.stringify(state)').includes(token));
        await run('bootstrapSession()');assert.equal(events.length,2);
        ''')

    def test_invalid_or_rejected_bootstrap_does_not_echo_token_or_retry(self):
        ui.CompactUi().dom(r'''
        let calls=0;window.location={hash:'#bootstrap=INVALID_PRIVATE_VALUE',pathname:'/',search:''};
        window.history={replaceState(){window.location.hash='';}};context.fetch=async()=>{calls++;return{ok:false};};
        await assert.rejects(run('bootstrapSession()'),error=>!error.message.includes('INVALID_PRIVATE_VALUE'));
        assert.equal(calls,0);assert.equal(window.location.hash,'');
        window.location.hash='#bootstrap='+'FAKE_'+'B'.repeat(38);
        await assert.rejects(run('bootstrapSession()'),error=>!error.message.includes('FAKE_'));
        assert.equal(calls,1);assert.equal(window.location.hash,'');
        ''')
