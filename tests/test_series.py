from test_catalog_integration import authenticated_handler
from pack_fixture_case import PackFixtureCase
"""Neutral serial state/prepare tests; mock receipts are NOT native media QA."""
import copy
import hashlib
import io
import json
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from storymotion.dashboard import Dashboard
from storymotion.engine import Engine, ROOT
from storymotion.security import WorkflowError, canonical, digest, file_hash, write_json
from storymotion.local_state import private_directory, write_private
from storymotion.dashboard import Handler
from test_catalog_integration import MemoryConnection


class SerialLifecycleTests(PackFixtureCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.d=Dashboard(self.tmp.name);self.receipts={}
        t=self.d.template('sample-series','account-video');v=t['template']['video']
        self.job=self.d.enqueue({'account':'sample-series','format':'account-video','title':v['title'],'brief':v['brief'],
            'content':v['script'],'caption':v['caption'],'provider':'local','model':'manual','task':'text','template_revision':0})['id']
        self.add_receipt(self.job)
        self.patch=patch.object(self.d.reviews,'verified_render',side_effect=self.verify);self.patch.start()
    def tearDown(self):
        self.patch.stop();self.d.renders.close();self.d.clear_keys();self.tmp.cleanup()
    def add_receipt(self, job):
        for engine in ('hyperframes','remotion'):
            p=self.d.workspace/'renders'/digest([job,engine])[:24]/'render-1080.mp4';private_directory(p.parent);write_private(p,b'NOT_MEDIA: owned synthetic serial receipt '+job.encode()+engine.encode())
            self.receipts[(job,engine)]=({'dashboard_job':job,'engine':engine,'engine_job':digest([job,engine])[:24],
                'render_sha256':file_hash(p),'receipt_sha256':digest(['sentinel-receipt',job,engine]),
                'manifest_sha256':digest(['sentinel-manifest',job,engine]),'payload_sha256':digest(self.d.job(job)['payload'])},p)
    def verify(self, job, engine):
        self.d.renders.validate(job,engine)
        if (job,engine) not in self.receipts:raise WorkflowError('No mock complete render receipt')
        b,p=self.receipts[(job,engine)]
        if file_hash(p)!=b['render_sha256'] or digest(self.d.job(job)['payload'])!=b['payload_sha256']:raise WorkflowError('Mock receipt changed')
        return copy.deepcopy(b),{},p
    def accept_body(self, job=None,engine='hyperframes'):
        r=self.d.series.reference_template(job or self.job,engine)
        return {k:r[k] for k in ('job','engine','expected_head','ordinal','canon')}|{'accepted_by':'operator','rights_confirmed':True,'reference_only':True}
    def accepted(self):return self.d.series.accept(self.accept_body())['revision']
    def draft_body(self, previous):
        t=self.d.series.draft_template(previous);v=t['video']
        sentences=['Zarfın köşesindeki çizgiye yeniden baktım.','Işığı çevirdim ve aynı izi karşılaştırdım.','Bu kez çizginin yanında küçük bir nokta gördüm.']
        v.update(title='Nötr ikinci bölüm',script=' '.join(sentences),caption='Aynı nesne için elle yazılmış ikinci teknik taslak.')
        v['creative']['topic_id']='neutral-episode-two'
        for i,s in enumerate(sentences):v['cues'][i]['text']=s;v['scenes'][i]['information']=s
        v['scenes'][-1]['object_after']='Zarfın aynı köşesinde küçük nokta; anlamı açık.';v['continuity']['next']=v['scenes'][-1]['object_after']
        return {'previous_revision':previous,'expected_draft':t['expected_draft'],'video':v,'approved_by':'operator',
                'continuation_note':'Aynı zarf ve köşe izini koruyarak yeni gözlem; olayın anlamı insan incelemesinde.',
                'rights_confirmed':True,'review_pending':True}
    def counts(self):
        with self.d.connection() as db:return [db.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in ('dashboard_jobs','series_episodes','series_drafts','series_heads','series_draft_heads')]
    def test_two_episode_manual_lifecycle_and_explicit_acceptance(self):
        previous=self.accepted();body=self.draft_body(previous);r=self.d.series.draft(body);child=r['child_job']
        self.assertEqual(self.d.series.state()['episodes'][0]['revision'],previous)
        self.assertEqual(len(self.d.series.state()['episodes']),1);self.assertEqual(r['status'],'draft_pending')
        self.assertTrue(self.d.series.draft(body)['reused']);self.assertEqual(self.counts(),[2,1,1,1,1])
        v=self.d.renders.video_input(self.d.job(child));ctx=v['production_context']
        self.assertEqual(ctx['canon']['data']['final_sha256'],self.receipts[(self.job,'hyperframes')][0]['render_sha256'])
        self.assertEqual(v['continuity']['previous'],ctx['canon']['data']['objects'][0]['state'])
        self.assertIsNone(v['audio']);self.assertEqual(v['alignment'],'provisional_silent');self.assertNotIn('audio_timing',v)
        self.add_receipt(child);accepted=self.d.series.accept(self.accept_body(child));self.assertFalse(accepted['publication_ready'])
        state=self.d.series.state();self.assertEqual(len(state['episodes']),2);self.assertEqual([e['current'] for e in state['episodes']],[False,True])
        self.assertEqual(accepted['record']['previous_revision'],previous);self.assertEqual(accepted['record']['ordinal'],2)
        self.assertEqual(accepted['record']['human_qa'],'incomplete');self.d.assert_provenance(self.d.job(child))
        with self.assertRaisesRegex(WorkflowError,'STALE_PREVIOUS'):self.d.series.draft_template(previous)
        self.assertTrue(self.d.series.accept(self.accept_body())['reused'])
    def test_no_render_or_forged_final_can_be_attested(self):
        body=self.accept_body();before=self.counts();body['canon']['final_sha256']='a'*64
        with self.assertRaises(WorkflowError):self.d.series.accept(body)
        self.assertEqual(self.counts(),before)
        self.receipts.clear()
        with self.assertRaises(WorkflowError):self.d.series.reference_template(self.job,'remotion')
    def test_accept_requires_rights_actor_and_reference_only(self):
        for field,value in [('rights_confirmed',False),('reference_only',False),('accepted_by','someone else'),('ordinal',2),('expected_head','a'*64)]:
            body=self.accept_body();body[field]=value;before=self.counts()
            with self.subTest(field=field),self.assertRaises(WorkflowError):self.d.series.accept(body)
            self.assertEqual(self.counts(),before)
    def test_cast_object_final_conflicts_have_zero_writes(self):
        for path,value in [('cast','wrong-person'),('state','not the final'),('series','BAD SERIES')]:
            b=self.accept_body();before=self.counts()
            if path=='cast':b['canon']['cast'][0]['id']=value
            elif path=='state':b['canon']['objects'][0]['state']=value
            else:b['canon']['series_id']=value
            with self.subTest(path=path),self.assertRaises(WorkflowError):self.d.series.accept(b)
            self.assertEqual(self.counts(),before)
    def test_missing_reference_old_script_or_contradiction_zero_child(self):
        previous=self.accepted()
        for change in ('missing','unchanged','cast','object','first_state','audio','consent','new_bible'):
            b=self.draft_body(previous);before=self.counts()
            if change=='missing':b['previous_revision']='b'*64
            elif change=='unchanged':b['video']=self.d.series.draft_template(previous)['video']
            elif change=='cast':b['video']['creative']['characters'][0]['wardrobe']='different-shirt'
            elif change=='object':b['video']['continuity']['object_id']='unknown-envelope'
            elif change=='first_state':b['video']['continuity']['previous']='invented earlier event'
            elif change=='audio':b['video']['audio']={'file':'old.mp3'}
            elif change=='consent':b['review_pending']=False
            else:b['video']['production_context']={}
            with self.subTest(change=change),self.assertRaises(WorkflowError):self.d.series.draft(b)
            self.assertEqual(self.counts(),before)
    def test_final_hash_tamper_blocks_next_and_accept(self):
        previous=self.accepted();body=self.draft_body(previous);self.receipts[(self.job,'hyperframes')][1].write_bytes(b'changed');before=self.counts()
        for op in [lambda:self.d.series.draft_template(previous),lambda:self.d.series.draft(body)]:
            with self.assertRaises(WorkflowError):op()
        self.assertEqual(self.counts(),before)
    def test_superseding_draft_invalidates_old_prepare_render_and_export(self):
        previous=self.accepted();b=self.draft_body(previous);old=self.d.series.draft(b);self.add_receipt(old['child_job'])
        b['expected_draft']=old['draft_revision'];b['video']['title']='İkinci bölüm revizyonu';new=self.d.series.draft(b)
        self.assertNotEqual(old['child_job'],new['child_job'])
        for op in [lambda:self.d.prepare(old['child_job']),lambda:self.d.renders.validate(old['child_job'],'hyperframes'),lambda:self.d.series.download(old['child_job'],'remotion')]:
            with self.assertRaisesRegex(WorkflowError,'SUPERSEDED'):op()
        with self.assertRaises(WorkflowError):self.d.series.draft({**b,'expected_draft':None,'video':self.draft_body(previous)['video']})
        self.d.assert_provenance(self.d.job(new['child_job']));self.assertEqual(len(self.d.series.state()['episodes']),1)
    def test_draft_race_expected_head_rejects_second_stale_request(self):
        previous=self.accepted();a=self.draft_body(previous);b=copy.deepcopy(a);b['video']['title']='Çakışan taslak'
        self.d.series.draft(a);before=self.counts()
        with self.assertRaisesRegex(WorkflowError,'DRAFT_HEAD_CHANGED'):self.d.series.draft(b)
        self.assertEqual(self.counts(),before)
    def test_real_prepare_two_engines_carries_pinned_final_and_canon(self):
        previous=self.accepted();r=self.d.series.draft(self.draft_body(previous));child=r['child_job'];self.d.prepare(child)
        v=self.d.renders.video_input(self.d.job(child));out=self.d.output(child);p=out/'series-unit-input.json';write_json(p,v)
        for engine in ('hyperframes','remotion'):
            e=Engine(self.d.workspace/('prepare-'+engine))
            try:
                key=e.create(p,render_engine=engine)['job'];e.run(key,'prepare');generated=e.directory(key)
                context=json.loads((generated/'writing-context.json').read_text())
                self.assertEqual(context['binding']['canon']['data']['final_sha256'],self.receipts[(self.job,'hyperframes')][0]['render_sha256'])
                self.assertEqual(e.payload(key)['brief']['script'],v['script'])
                self.assertTrue((generated/'index.html').exists())
            finally:e.store.db.close()
    def test_export_wrap_contains_exact_previous_and_current_hashes(self):
        previous=self.accepted();child=self.d.series.draft(self.draft_body(previous))['child_job'];self.add_receipt(child)
        inner=io.BytesIO()
        with zipfile.ZipFile(inner,'w') as z:z.writestr('SYNTHETIC_NOT_RENDER.txt','Unit contract only')
        with patch.object(self.d.renders,'download',return_value=inner.getvalue()):
            for engine in ('hyperframes','remotion'):
                raw=self.d.series.download(child,engine)
                with zipfile.ZipFile(io.BytesIO(raw)) as z:
                    m=json.loads(z.read('series-reference.json'));self.assertEqual(z.read('episode-delivery.zip'),inner.getvalue())
                    self.assertEqual(m['delivery_sha256'],hashlib.sha256(inner.getvalue()).hexdigest())
                    self.assertEqual(m['series_revision']['previous_revision'],previous);self.assertFalse(m['publication_ready'])
    def test_accept_hash_changes_during_validation_zero_reference(self):
        b=self.accept_body();original=self.verify;count=[0]
        def changed(job,engine):
            count[0]+=1
            if count[0]>1:self.receipts[(job,engine)][1].write_bytes(b'changed during acceptance')
            return original(job,engine)
        before=self.counts()
        with patch.object(self.d.reviews,'verified_render',side_effect=changed),self.assertRaises(WorkflowError):self.d.series.accept(b)
        self.assertEqual(self.counts(),before)

    def test_actual_handler_requires_same_origin_and_returns_structured_series_state(self):
        server=SimpleNamespace(server_address=('127.0.0.1',4453),dashboard=self.d)
        def call(action,body,origin='http://127.0.0.1:4453'):
            raw=canonical(body).encode();request=('POST /api/series/'+action+' HTTP/1.1\r\nHost: 127.0.0.1:4453\r\nOrigin: '+origin+'\r\nX-Storymotion-Local: 1\r\nContent-Type: application/json\r\nContent-Length: '+str(len(raw))+'\r\n\r\n').encode()+raw
            connection=MemoryConnection(request);authenticated_handler(connection,('127.0.0.1',1),server)
            head,result=bytes(connection.output).split(b'\r\n\r\n',1)
            return int(head.split()[1]),json.loads(result)
        before=self.counts();self.assertEqual(call('accept',self.accept_body(),'https://attacker.invalid')[0],403);self.assertEqual(self.counts(),before)
        status,result=call('accept',self.accept_body());self.assertEqual(status,200)
        status,t=call('draft-template',{'previous_revision':result['revision']});self.assertEqual(status,200);self.assertEqual(t['next_ordinal'],2)
        status,listing=call('state',{});self.assertEqual(status,200);self.assertEqual(len(listing['episodes']),1)
        self.assertEqual(call('state',{'unknown':True})[0],400)

    def test_export_superseded_during_read_releases_zero_bytes(self):
        previous=self.accepted();body=self.draft_body(previous);old=self.d.series.draft(body);self.add_receipt(old['child_job'])
        def change(*args):
            body['expected_draft']=old['draft_revision'];body['video']['title']='Yeni revizyon'
            self.d.series.draft(body);return b'NOT_A_REAL_ZIP: intercepted packaging sentinel'
        with patch.object(self.d.renders,'download',side_effect=change),self.assertRaisesRegex(WorkflowError,'SUPERSEDED'):
            self.d.series.download(old['child_job'],'hyperframes')

    def test_separate_instance_race_never_overwrites_accepted_head(self):
        other=Dashboard(self.d.workspace);errors=[];results=[];barrier=threading.Barrier(2)
        try:
            body=self.accept_body();second=copy.deepcopy(body);second['accepted_by']='second operator';second['canon']['accepted_by']='second operator'
            def run(service,data):
                try:barrier.wait(5);results.append(service.series.accept(data))
                except Exception as e:errors.append(e)
            with patch.object(other.reviews,'verified_render',side_effect=self.verify):
                threads=[threading.Thread(target=run,args=(self.d,body)),threading.Thread(target=run,args=(other,second))]
                for t in threads:t.start()
                for t in threads:t.join(10)
                self.assertTrue(all(not t.is_alive() for t in threads))
            self.assertEqual(len(results),1);self.assertEqual(len(errors),1);self.assertIsInstance(errors[0],WorkflowError)
            self.assertEqual(self.counts(),[1,1,0,1,0])
        finally:other.renders.close();other.clear_keys()


if __name__=='__main__':unittest.main()
