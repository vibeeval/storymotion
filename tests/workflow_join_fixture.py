"""Receipt integration fixture. The media sentinel is NOT a rendered MP4.

Real provider/HTTP/renderer/FFmpeg calls are forbidden. Real profile validation,
source preparation, Engine identity, receipt verification and QA persistence run.
"""
import json
from pathlib import Path
from unittest.mock import patch
from storymotion.dashboard import Dashboard
from storymotion.engine import Engine
from storymotion.qa_contract import build_sampling_plan,report_template
from storymotion.security import file_hash,write_json
from neutral_identity_fixture import source_identity_profiles,source_identity_values

ACCOUNTS=('sample-reflection','sample-flow','sample-mechanism','sample-series')
PROVIDERS=('openai','anthropic','gemini','openrouter')
KEY='FAKE_JOIN_CONTRACT_ONLY_123456789'


class JoinedCase:
    def __init__(self,root,provider,account):
        self.root=Path(root);self.provider=provider;self.account=account
        self.d=Dashboard(self.root,llm_mode='demo');self.capture_count=0
    def accept(self):
        c=self.d.llm_action('connect',{'provider':self.provider,'value':KEY});ref=c['connection']
        p=self.d.llm_action('preview',{'connection':ref,'context':{'account':self.account,'title':'Sentetik birleşim','brief':'Yalnız kanonik fixture; gerçek model kalitesi değildir.','caption':''},
            'model':c['metadata']['models'][0]['id'],'max_output_tokens':2000})
        self.d.llm_action('approve',{'connection':ref,'request':p['request'],'maximum_output_tokens':2000,'ack_unknown_cost':True,'rights_confirmed':True,'budget':None})
        self.d.llm.execute(ref,p['request'],asynchronous=False)
        assert self.d.llm.get(p['request'])['status']=='completed'
        a={'request':p['request'],'brand_identity':{'name':'Müşteri provası','handle':'musteriprovasi'}}
        first=self.d.llm_action('accept',a);second=self.d.llm_action('accept',a);assert first['accepted_job']==second['accepted_job']
        self.job=first['accepted_job'];row=self.d.job(self.job)
        assert row['payload']['format']['adapter']=='account-pack' and row['payload']['generation']['synthetic']
        assert not row['payload']['generation']['publication_ready'] and row['payload']['paid_calls']==0
        for engine in ('hyperframes','remotion'):assert self.d.renders.state(self.job,engine)['status']=='not_started'
        self.d.llm_action('disconnect',{'connection':ref});assert not self.d.llm.connections
        with source_identity_profiles():self.d.prepare(self.job)
        text=(self.d.output(self.job)/'source/index.html').read_text();assert '@musteriprovasi' in text
        for identity in source_identity_values():assert identity and identity not in text
        self.request=p['request'];return self.job
    def seed_receipt(self,engine):
        row=self.d.renders.validate(self.job,engine)
        source=self.d.output(self.job)/('render-input-'+engine+'.json');write_json(source,self.d.renders.video_input(row))
        e=Engine(self.root/'renders')
        try:
            ident=e.create(source,render_engine=engine)['job'];e.run(ident,until='prepare');out=e.directory(ident)
            # This sentinel only tests receipt plumbing. No decode/PASS is claimed.
            (out/'render-1080.mp4').write_bytes(b'NOT_A_VIDEO: explicit synthetic receipt contract only')
            payload=e.payload(ident);sha=file_hash(out/'render-1080.mp4')
            write_json(out/'render-engine.json',{'engine':engine,'render_sha256':sha,'execution_fingerprint':payload['execution']['fingerprint'],'synthetic_test_sentinel':True})
            e.store.set_stage(ident,'render','complete',{n:file_hash(out/n) for n in ('render-1080.mp4','render-engine.json')})
            with self.d.connection() as db:db.execute('INSERT OR REPLACE INTO dashboard_renders VALUES(?,?,?,?,?,?)',(self.job,engine,ident,'complete',None,1))
        finally:e.store.db.close()
        return ident,out
    def fake_capture(self,ident,payload,media):
        self.capture_count+=1;service=self.d.reviews.runtime()
        service._directory(ident).mkdir(parents=True,exist_ok=True)
        plan=build_sampling_plan(payload['brief'],payload['render_sha256'],payload['asset_hashes'],
            source_fingerprint=payload['source_fingerprint'],scene_keyframes=payload['scene_keyframes'])
        report=report_template(plan)
        service._persist(ident,payload,plan,report,{})
    def review(self,engine):
        with patch.object(self.d.reviews.runtime(),'_build',side_effect=self.fake_capture):
            result=self.d.reviews.action(self.job,'review-create',{'engine':engine})
        assert result['state']=='ready' and result['status']=='incomplete' and result['approval_fingerprint'] is None
        assert result['coverage']['captured']==0 # Never present sentinel as capture/decode evidence.
        return result
    def assert_no_secret(self):
        for path in self.root.rglob('*'):
            if path.is_file():assert KEY.encode() not in path.read_bytes(),path.name
    def close(self):
        self.d.renders.close();self.d.clear_keys()
        if self.d.reviews.service:self.d.reviews.service.db.close()

