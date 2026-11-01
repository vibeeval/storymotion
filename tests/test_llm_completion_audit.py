from pack_fixture_case import PackFixtureCase
"""Synthetic audit fault injection; no provider network or paid calls."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from storymotion.llm_service import LLMService,DemoScriptTransport
from storymotion.llm_api import SYNTHETIC_MODEL_IDS
from storymotion.providers import ProviderError
from test_llm_service import HeldTransport,ChangedTransport

KEY='FAKE_OPAQUE_AUDIT_ONLY_123456789'
EVENT='validated_proposal_received_human_review_pending'


class CompletionAuditTests(PackFixtureCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='completion-audit-');self.root=Path(self.temp.name);self.services=[]
    def tearDown(self):
        for s in self.services:s.close()
        self.temp.cleanup()
    def service(self,name='main',transport=None):
        s=LLMService(self.root/name,mode='demo',transport=transport or DemoScriptTransport());self.services.append(s);return s
    def ready(self,s,account='sample-mechanism'):
        ref=s.connect('openai',KEY)['connection'];context={'account':account,'title':'Sentetik olay kaydı','brief':'Aynı nesnenin hareket sırasını açıkla.','caption':''}
        request=s.preview(ref,context,2000,model=SYNTHETIC_MODEL_IDS['openai'])['request'];s.approve(ref,request,2000,True,True);return ref,request
    def fault(self,s):
        original=s.event
        def event(request,name):
            if name==EVENT:
                self.assertIn(s.row(request)['status'],('completed','received_after_cancel_review'))
                raise OSError(KEY) # error text must never persist
            return original(request,name)
        return patch.object(s,'event',side_effect=event)
    def test_committed_artifact_survives_event_failure_accepts_and_does_not_hold_distinct_job(self):
        s=self.service();ref,request=self.ready(s)
        with self.fault(s):result=s.execute(ref,request,False)
        self.assertEqual(result['status'],'completed');self.assertIsNotNone(result['artifact']);self.assertEqual(result['dispatch_count'],1)
        self.assertEqual(result['completion_audit_error'],'COMPLETION_AUDIT_WRITE_FAILED');self.assertIsNone(result['error_code'])
        proposal=s.download(request,'proposal.json');receipt=s.download(request,'receipt.json')
        accepted=s.accept(request,lambda *_:'a'*24);self.assertEqual(accepted['status'],'accepted_review')
        other,second=self.ready(s,'sample-reflection');self.assertEqual(s.execute(other,second,False)['status'],'completed')
        self.assertEqual(len(s.transport.calls),2) # one per separately approved intent
        self.assertEqual(s.download(request,'proposal.json'),proposal);self.assertEqual(s.download(request,'receipt.json'),receipt)
        for p in self.root.rglob('*'):
            if p.is_file():self.assertNotIn(KEY.encode(),p.read_bytes())
    def test_persistent_completion_fault_survives_restart_and_cached_execute_never_resends(self):
        s=self.service();ref,request=self.ready(s)
        with self.fault(s):result=s.execute(ref,request,False)
        self.assertEqual(result['status'],'completed');self.assertEqual(result['completion_audit_error'],'COMPLETION_AUDIT_WRITE_FAILED')
        self.assertEqual(len(s.transport.calls),1);s.disconnect(ref)
        second=self.service();cached=second.execute('missing-session',request,False)
        self.assertEqual(cached['status'],'completed');self.assertEqual(cached['artifact'],result['artifact']);self.assertEqual(cached['completion_audit_error'],result['completion_audit_error'])
        self.assertFalse(second.transport.calls)
    def test_cancelled_inflight_artifact_with_audit_fault_stays_review_hold(self):
        held=HeldTransport();s=self.service(transport=held);ref,request=self.ready(s);s.execute(ref,request)
        self.assertTrue(held.started.wait(1));self.assertEqual(s.cancel(request)['status'],'uncertain')
        with self.fault(s):
            held.release.set()
            with s.lock:worker=s.threads.get(request)
            if worker:worker.join(2)
        self.assertNotIn(request,s.threads);result=s.get(request)
        self.assertEqual(result['status'],'received_after_cancel_review');self.assertEqual(result['completion_audit_error'],'COMPLETION_AUDIT_WRITE_FAILED')
        self.assertEqual(len(held.calls),1)
        with self.assertRaisesRegex(ProviderError,'VALIDATED_COMPLETED'):s.accept(request,lambda *_:'b'*24)
        other,second=self.ready(s,'sample-reflection')
        with self.assertRaisesRegex(ProviderError,'HOLD'):s.execute(other,second,False)
    def test_genuine_transport_uncertainty_has_no_artifact_and_keeps_retry_hold(self):
        s=self.service(transport=ChangedTransport(error='TRANSPORT_OUTCOME_UNCERTAIN'));ref,request=self.ready(s);result=s.execute(ref,request,False)
        self.assertEqual(result['status'],'uncertain');self.assertIsNone(result['artifact']);self.assertIsNone(result['completion_audit_error'])
        self.assertEqual(len(s.transport.calls),1)
        with self.assertRaises(ProviderError):s.execute(ref,request,False)
    def test_interrupted_postcommit_audit_is_durably_pending_without_resend(self):
        s=self.service();ref,request=self.ready(s);original=s.event
        def event(request,name):
            if name==EVENT:raise SystemExit('simulated process interruption after result commit')
            return original(request,name)
        with patch.object(s,'event',side_effect=event),self.assertRaises(SystemExit):s.execute(ref,request,False)
        result=s.get(request);self.assertEqual(result['status'],'completed');self.assertEqual(result['completion_audit_error'],'COMPLETION_AUDIT_PENDING')
        s.disconnect(ref);second=self.service();cached=second.execute('missing-session',request,False)
        self.assertEqual(cached['artifact'],result['artifact']);self.assertEqual(cached['completion_audit_error'],'COMPLETION_AUDIT_PENDING')
        self.assertFalse(second.transport.calls);self.assertEqual(len(s.transport.calls),1)
    def test_old_database_migrates_and_successful_completion_has_no_audit_warning(self):
        from storymotion.local_state import private_directory,private_database
        root=self.root.resolve()/'legacy';private_directory(root);db=private_database(root,'llm-jobs.sqlite3')
        try:
            db.execute('CREATE TABLE llm_requests(id TEXT PRIMARY KEY,job TEXT NOT NULL,payload TEXT NOT NULL,status TEXT NOT NULL,approved_until REAL,deadline REAL,owner TEXT,dispatch_count INTEGER NOT NULL DEFAULT 0,binding_scope TEXT,approval TEXT,artifact TEXT,error_code TEXT,accepted_job TEXT,updated REAL NOT NULL)')
            db.commit()
        finally:db.close()
        self.assertEqual(root.stat().st_mode&0o777,0o700);self.assertEqual((root/'llm-jobs.sqlite3').stat().st_mode&0o777,0o600)
        s=self.service('legacy');ref,request=self.ready(s);result=s.execute(ref,request,False)
        self.assertEqual(result['status'],'completed');self.assertIsNone(result['completion_audit_error'])
        with s.db() as db:
            events=[r[0] for r in db.execute('SELECT event FROM llm_events WHERE request=?',(request,))]
            self.assertEqual(events.count(EVENT),1)


if __name__=='__main__':unittest.main()
