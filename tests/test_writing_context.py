from pack_fixture_case import PackFixtureCase
"""Synthetic source/canon lifecycle with real validators, no network/render."""
import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from storymotion.dashboard import Dashboard
from storymotion.engine import Engine
from storymotion.llm_service import LLMService,DemoScriptTransport,golden_fixture,plan_prompt
from storymotion.llm_api import SYNTHETIC_MODEL_IDS
from storymotion.providers import ProviderError,Response
from storymotion.security import WorkflowError,canonical,digest,write_json
from storymotion.writing_context import bound_brief,validate_binding
from test_llm_service import HeldTransport,ChangedTransport

KEY='FAKE_WRITING_CONTEXT_ONLY_123456'
SOURCE={'test-study':{'url':'https://example.org/synthetic-study','title':'Özgün sentetik not','locator':'Sentetik madde A','excerpt':'Bu özgün çizim yalnız sentetik bir örnektir.','rights_note':'Original synthetic test text; not an external paper'}}


def accepted_reference(source=None):
    v=golden_fixture('sample-series')
    return {'series_id':'synthetic-series','episode_id':'synthetic-final-01','bible_version':'synthetic-bible-1','origin':'synthetic_reference_test',
      'final_sha256':digest('Original synthetic final reference, not media'),'accepted_by':'Synthetic human fixture','narrator':'first_person',
      'cast':[{k:c[k] for k in ('id','wardrobe')} for c in v['creative']['characters']],'objects':[{'id':v['continuity']['object_id'],'state':v['continuity']['previous'],'identity_note':'Same synthetic nick'}],
      'open_clues':[{'id':'nick-01','object_id':v['continuity']['object_id'],'description':'Same synthetic nick remains open'}],'source_revision':source}


class SourceTransport(DemoScriptTransport):
    def __init__(self,change=None):super().__init__();self.change=change
    def exchange(self,plan,key,permit,job):
        response=super().exchange(plan,key,permit,job);body=json.loads(response.body)
        slot=body['output'][0]['content'][0] if plan.provider=='openai' else body['content'][0] if plan.provider=='anthropic' else body['candidates'][0]['content']['parts'][0] if plan.provider=='gemini' else body['choices'][0]['message']
        name='content' if plan.provider=='openrouter' else 'text';v=json.loads(slot[name]);v['claims']=[{'text':v['script'],'source':'test-study','scope':'Original synthetic fixture only; no empirical claim'}]
        if self.change:self.change(v)
        slot[name]=canonical(v);return Response(200,'application/json',canonical(body).encode())


class WritingContextTests(PackFixtureCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory(prefix='writing-context-');self.root=Path(self.tmp.name);self.services=[]
    def tearDown(self):
        for s in self.services:s.close()
        self.tmp.cleanup()
    def service(self,name='main',transport=None):
        s=LLMService(self.root/name,mode='demo',transport=transport or SourceTransport());self.services.append(s);return s
    def source(self,s,account='sample-mechanism',expected=None,value=None):return s.contexts.save('sources',account,copy.deepcopy(SOURCE if value is None else value),expected,True)
    def context(self,s,account='sample-mechanism'):
        c={'account':account,'title':'Sentetik kaynak provası','brief':'Aynı nesnenin hareket sırasını açıkla.','caption':''};v=s.contexts.state(account)
        for kind,key in [('sources','source_revision'),('canon','canon_revision')]:
            if v[kind]:c[key]=v[kind]['revision']
        return c
    def ready(self,s,account='sample-mechanism',provider='openai'):
        ref=s.connect(provider,KEY)['connection'];r=s.preview(ref,self.context(s,account),2000,model=SYNTHETIC_MODEL_IDS[provider])['request'];s.approve(ref,r,2000,True,True);return ref,r
    def test_sources_are_immutable_cas_idempotent_and_short_reference_only(self):
        s=self.service();a=self.source(s);revision=a['sources']['revision'];self.assertEqual(self.source(s,expected=revision),a)
        modified=copy.deepcopy(SOURCE);modified['test-study']['excerpt']='Farklı özgün sentetik not.'
        b=self.source(s,expected=revision,value=modified);self.assertNotEqual(b['sources']['revision'],revision)
        with self.assertRaises(WorkflowError):self.source(s,expected=revision)
        with s.db() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM writing_context_revisions').fetchone()[0],2)
        self.assertEqual(a['sources']['data'],SOURCE)
    def test_invalid_source_url_long_quote_rights_and_active_key_leave_zero_revisions(self):
        s=self.service();s.connect('openai',KEY)
        for variant in ('query','userinfo','long','raw','secret','rights'):
            v=copy.deepcopy(SOURCE)
            if variant=='query':v['test-study']['url']='https://example.org/?token=nope'
            if variant=='userinfo':v['test-study']['url']='https://user:pass@example.org/a'
            if variant=='long':v['test-study']['excerpt']='word '*26
            if variant=='raw':v['test-study']['raw_pdf']='not allowed'
            if variant=='secret':v['test-study']['rights_note']=KEY
            with self.subTest(variant=variant),self.assertRaises((WorkflowError,ProviderError)):s.contexts.save('sources','sample-mechanism',v,None,variant!='rights')
        with s.db() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM writing_context_revisions').fetchone()[0],0)
    def test_four_native_protocols_bind_source_quote_through_prompt_receipt_accept_and_prepare(self):
        for provider in ('openai','anthropic','gemini','openrouter'):
            s=self.service(provider);self.source(s);ref,r=self.ready(s,provider=provider);result=s.execute(ref,r,False)
            self.assertEqual(result['status'],'completed');value=json.loads(s.download(r,'proposal.json'));binding=value['production_context']
            self.assertEqual(binding['sources']['data'],SOURCE);self.assertEqual(result['artifact']['writing_context_sha256'],binding['binding_sha256'])
            link=value['creative']['audit']['claim_traceability']['source_links'][0];self.assertEqual(link['excerpt'],SOURCE['test-study']['excerpt']);self.assertEqual(link['locator'],SOURCE['test-study']['locator']);self.assertEqual(link['source_snapshot_sha256'],digest(SOURCE['test-study']))
            seen=[];s.accept(r,lambda v,a:seen.append(v) or 'a'*24);self.assertEqual(seen[0],value)
            path=self.root/(provider+'.json');write_json(path,value);e=Engine(self.root/(provider+'-engine'));job=e.create(path)['job'];e.run(job,'prepare')
            try:self.assertEqual(json.loads((e.directory(job)/'source-brief.json').read_text())['production_context'],binding)
            finally:e.store.db.close()
            prompt=json.loads(plan_prompt(type('P',(),{'provider':provider,'body':json.loads(s.row(r)['payload'])['plan']['body']})()))
            self.assertEqual(prompt['writing_context'],binding);self.assertEqual(len(s.transport.calls),1)
    def test_four_profiles_keep_their_distinct_contracts_with_sources(self):
        for account in ('sample-flow','sample-mechanism','sample-reflection','sample-series'):
            s=self.service(account);self.source(s,account);ref,r=self.ready(s,account);result=s.execute(ref,r,False)
            self.assertEqual(result['status'],'completed');v=json.loads(s.download(r,'proposal.json'));self.assertEqual(v['brand'],account)
            self.assertEqual(v['creative']['canon_status'],'noncanonical_fixture' if account=='sample-series' else 'standalone')
            self.assertEqual(s.contexts.state(account)['canon'],None)
    def test_changed_source_after_approval_prevents_dispatch_and_old_proposal_accept(self):
        s=self.service();a=self.source(s);ref,r=self.ready(s);new=copy.deepcopy(SOURCE);new['test-study']['excerpt']='Değişen sentetik kayıt.'
        self.source(s,expected=a['sources']['revision'],value=new)
        with self.assertRaises(WorkflowError):s.execute(ref,r,False)
        self.assertFalse(s.transport.calls)
        ref,r=self.ready(s);self.assertEqual(s.execute(ref,r,False)['status'],'completed');head=s.contexts.state('sample-mechanism')['sources']['revision'];self.source(s,expected=head)
        called=[]
        with self.assertRaises(WorkflowError):s.accept(r,lambda *_:called.append(True) or 'a'*24)
        self.assertFalse(called)
    def test_model_cannot_invent_registry_source_or_author_host_context(self):
        for kind in ('invented','self-context'):
            def change(v):
                if kind=='invented':v['claims'][0]['source']='invented-study'
                else:v['production_context']={'sources':SOURCE}
            s=self.service(kind,SourceTransport(change));self.source(s);ref,r=self.ready(s);result=s.execute(ref,r,False)
            self.assertEqual(result['status'],'received_invalid_review');self.assertIsNone(result['artifact']);self.assertFalse((s.root/r/'proposal.json').exists())
    def test_tampered_quote_binding_and_cross_account_context_fail_before_engine_job(self):
        s=self.service();self.source(s);ref,r=self.ready(s);s.execute(ref,r,False);original=json.loads(s.download(r,'proposal.json'))
        for kind in ('quote','hash','account'):
            v=copy.deepcopy(original)
            if kind=='quote':v['production_context']['sources']['data']['test-study']['excerpt']='Tampered quote.'
            elif kind=='hash':v['production_context']['binding_sha256']='0'*64
            else:v['production_context']['account']='sample-reflection'
            with self.subTest(kind=kind),self.assertRaises(WorkflowError):bound_brief('sample-mechanism',v)
    def test_inflight_and_uncertain_requests_prevent_context_rebind(self):
        held=HeldTransport();s=self.service(transport=held);a=self.source(s);ref,r=self.ready(s);s.execute(ref,r)
        try:
            self.assertTrue(held.started.wait(1))
            with self.assertRaises(WorkflowError):self.source(s,expected=a['sources']['revision'])
            s.cancel(r)
            with self.assertRaises(WorkflowError):self.source(s,expected=a['sources']['revision'])
        finally:
            held.release.set()
            with s.lock:worker=s.threads.get(r)
            if worker:worker.join(2)
    def test_canon_requires_explicit_accepted_reference_and_never_imports_drafts(self):
        s=self.service();v=accepted_reference()
        for kind in ('draft','extra-status','unconfirmed','wrong-account'):
            x=copy.deepcopy(v)
            if kind=='draft':x['origin']='proposal'
            if kind=='extra-status':x['status']='accepted'
            with self.subTest(kind=kind),self.assertRaises(WorkflowError):s.contexts.save('canon','sample-reflection' if kind=='wrong-account' else 'sample-series',x,None,kind!='unconfirmed')
        self.assertIsNone(s.contexts.state('sample-series')['canon'])
    def test_canon_bound_noncanonical_proposal_does_not_mutate_accepted_reference(self):
        s=self.service();source=self.source(s,'sample-series');reference=accepted_reference(source['sources']['revision']);a=s.contexts.save('canon','sample-series',reference,None,True)
        ref,r=self.ready(s,'sample-series');result=s.execute(ref,r,False);self.assertEqual(result['status'],'completed');seen=[];s.accept(r,lambda v,a:seen.append(v) or 'a'*24)
        self.assertEqual(s.contexts.state('sample-series')['canon'],a['canon']);self.assertEqual(seen[0]['creative']['canon_status'],'noncanonical_fixture');self.assertEqual(seen[0]['production_context']['canon']['data']['origin'],'synthetic_reference_test')
    def test_canon_change_stale_source_or_wrong_state_and_wardrobe_are_not_accepted(self):
        for kind in ('object','wardrobe','source'):
            s=self.service(kind);a=self.source(s,'sample-series');reference=accepted_reference(a['sources']['revision'])
            if kind=='object':reference['objects'][0]['state']='Different accepted object state.'
            if kind=='wardrobe':reference['cast'][0]['wardrobe']='cream-tshirt'
            if kind=='source':reference['source_revision']='0'*64
            if kind=='source':
                with self.assertRaises(WorkflowError):s.contexts.save('canon','sample-series',reference,None,True)
                continue
            s.contexts.save('canon','sample-series',reference,None,True);ref,r=self.ready(s,'sample-series');result=s.execute(ref,r,False)
            self.assertEqual(result['status'],'received_invalid_review');self.assertIsNone(result['artifact'])
    def test_canon_cas_changes_invalidate_pending_approval_without_a_dispatch(self):
        s=self.service();source=self.source(s,'sample-series');reference=accepted_reference(source['sources']['revision']);a=s.contexts.save('canon','sample-series',reference,None,True);ref,r=self.ready(s,'sample-series')
        reference['episode_id']='synthetic-final-02';b=s.contexts.save('canon','sample-series',reference,a['canon']['revision'],True)
        with self.assertRaises(WorkflowError):s.contexts.save('canon','sample-series',reference,a['canon']['revision'],True)
        with self.assertRaises(WorkflowError):s.execute(ref,r,False)
        self.assertFalse(s.transport.calls);self.assertNotEqual(a['canon']['revision'],b['canon']['revision'])
    def test_source_binding_survives_measured_retime_and_qa_stays_pending(self):
        from audio_fixture import alignment
        from storymotion.audio_retime import retime,validate_timed_brief
        from storymotion.writing_context import audit_bound_claims
        s=self.service();self.source(s);ref,r=self.ready(s);s.execute(ref,r,False);v=json.loads(s.download(r,'proposal.json'))
        timed=retime(v,alignment(v['script']),20,'a'*64);timed.update(audio={'sha256':'a'*64},alignment='imported_timing')
        validated=validate_timed_brief(timed);self.assertEqual(validated['production_context'],v['production_context'])
        audit=audit_bound_claims(timed);self.assertEqual(audit['status'],'incomplete');self.assertEqual(audit['source_truth'],'pending_human_review');self.assertEqual(audit['source_links'][0]['excerpt'],SOURCE['test-study']['excerpt'])
        timed['production_context']['sources']['data']['test-study']['excerpt']='Tampered.'
        with self.assertRaises(WorkflowError):audit_bound_claims(timed)
    def test_source_only_scene_number_is_not_silently_unsourced(self):
        from storymotion.claims import audit_claims
        with self.assertRaises(WorkflowError):audit_claims({'script':'Özgün çizim.','claims':[],'scenes':[{'heading':'Çizim','information':'Ölçüm12oldu.'}]})
    def test_stale_context_is_visible_without_reclassifying_completed_provider_result(self):
        s=self.service();a=self.source(s);ref,r=self.ready(s);s.execute(ref,r,False);v=copy.deepcopy(SOURCE);v['test-study']['excerpt']='Yeni kısa kaynak notu.'
        self.source(s,expected=a['sources']['revision'],value=v);state=s.get(r)
        self.assertEqual(state['status'],'completed');self.assertFalse(state['context_current']);self.assertIsNotNone(state['artifact'])


if __name__=='__main__':unittest.main()
