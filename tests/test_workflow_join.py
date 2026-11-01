from pack_fixture_case import PackFixtureCase
"""Joined provider->profile->Engine receipt->QA contracts, not video E2E."""
import json
import tempfile
import unittest
from unittest.mock import patch
from storymotion.security import WorkflowError,write_json,file_hash
from storymotion.engine import Engine
from workflow_join_fixture import JoinedCase,ACCOUNTS,PROVIDERS


class WorkflowJoinTests(PackFixtureCase):
    def test_all_four_providers_and_profiles_bind_both_engine_receipts_to_incomplete_qa(self):
        with tempfile.TemporaryDirectory() as temp,patch('storymotion.engine.checked_process',side_effect=AssertionError('External tools forbidden')),patch('storymotion.qa_review.checked_process',side_effect=AssertionError('Capture/decode forbidden')):
            from pathlib import Path
            for provider in PROVIDERS:
                for account in ACCOUNTS:
                    with self.subTest(provider=provider,account=account):
                        case=JoinedCase(Path(temp)/(provider+'-'+account),provider,account)
                        try:
                            case.accept();reviews=[]
                            for engine in ('hyperframes','remotion'):
                                ident,out=case.seed_receipt(engine);review=case.review(engine);reviews.append(review['review_id'])
                                bound,_,_=case.d.reviews.verified_render(case.job,engine)
                                self.assertEqual(bound['engine_job'],ident);self.assertEqual(review['render_sha256'],bound['render_sha256'])
                            self.assertNotEqual(*reviews);self.assertEqual(case.capture_count,2)
                            self.assertEqual(len(case.d.llm.transport.calls),1);case.assert_no_secret()
                        finally:case.close()
    def test_account_pack_wrong_engine_and_changed_receipt_are_rejected_before_capture(self):
        with tempfile.TemporaryDirectory() as temp:
            case=JoinedCase(temp,'gemini','sample-reflection')
            try:
                case.accept();hf,_=case.seed_receipt('hyperframes');rem,out=case.seed_receipt('remotion');case.review('remotion')
                with case.d.connection() as db:db.execute('UPDATE dashboard_renders SET engine_job=? WHERE job=? AND engine=?',(hf,case.job,'remotion'))
                with patch.object(case.d.reviews.runtime(),'_build') as build:
                    with self.assertRaises(WorkflowError):case.d.reviews.action(case.job,'review-create',{'engine':'remotion'})
                    build.assert_not_called()
                with case.d.connection() as db:db.execute('UPDATE dashboard_renders SET engine_job=? WHERE job=? AND engine=?',(rem,case.job,'remotion'))
                (out/'render-engine.json').write_text('{}')
                result=case.d.reviews.state(case.job,'remotion');self.assertEqual(result['state'],'invalidated');self.assertEqual(result['files'],{})
                with self.assertRaises(WorkflowError):case.d.reviews.download(case.job,'remotion','plan.json')
            finally:case.close()
    def test_accepted_account_pack_cannot_overwrite_current_receipt_with_another_jobs_input(self):
        with tempfile.TemporaryDirectory() as temp:
            case=JoinedCase(temp,'openrouter','sample-series')
            try:
                case.accept();case.seed_receipt('hyperframes')
                source=case.d.output(case.job)/'render-input-hyperframes.json';value=json.loads(source.read_text());value['title']='Unexpected external edit';write_json(source,value)
                with patch.object(case.d.reviews.runtime(),'_build') as build:
                    with self.assertRaises(WorkflowError):case.d.reviews.action(case.job,'review-create',{'engine':'hyperframes'})
                    build.assert_not_called()
                with case.d.connection() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM dashboard_reviews').fetchone()[0],0)
            finally:case.close()


if __name__=='__main__':unittest.main()
