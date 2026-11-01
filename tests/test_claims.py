from pack_fixture_case import PackFixtureCase
import unittest
from storymotion.claims import audit_claims
from storymotion.security import WorkflowError


class SourceClaimGuard(PackFixtureCase):
    def test_unsourced_number_and_price_fail_closed(self):
        for text in ['Başarı yüzde 80 arttı.','Fiyatı 19,99 USD.','Bu servis ücretsiz.','Oran ８０ oldu.']:
            with self.subTest(text=text),self.assertRaises(WorkflowError):audit_claims({'script':text,'claims':[]})
    def test_registered_source_link_is_traceability_not_truth_approval(self):
        brief={'script':'Sentetik ölçüm 12 oldu.','claims':[{'text':'Sentetik ölçüm 12 oldu.','source':'local-study','scope':'Yalnız örnek veri'}]}
        result=audit_claims(brief,{'local-study':{'url':'https://example.org/study'}})
        self.assertEqual(result['numeric_price_guard'],'pass');self.assertEqual(result['status'],'incomplete')
        self.assertEqual(result['source_links'][0]['source_truth'],'pending_human_review')
        brief['script']='Sentetik ölçüm 13 oldu.'
        with self.assertRaises(WorkflowError):audit_claims(brief,{'local-study':{'url':'https://example.org/study'}})
    def test_fabricated_source_and_credential_url_refused(self):
        b={'script':'12','claims':[{'text':'12','source':'made-up','scope':'test'}]}
        for registry in [{},{'made-up':{'url':'file:///private'}},{'made-up':{'url':'https://EXAMPLE_USER:EXAMPLE_PASS@example.org'}}]:
            with self.assertRaises(WorkflowError):audit_claims(b,registry)
    def test_explicit_fiction_does_not_certify_real_world_numbers(self):
        r=audit_claims({'script':'E-17, saat 04.17.','claims':[]},fictional=True)
        self.assertEqual(r['status'],'incomplete');self.assertEqual(r['numeric_price_guard'],'fictional_explicit_exemption')
