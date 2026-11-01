from pack_fixture_case import PackFixtureCase
"""A rejected certainty claim must not move from narration into public copy."""
import json
import unittest
from storymotion.creative import ACCOUNTS,validate_proposal
from storymotion.engine import ROOT
from storymotion.security import WorkflowError


def fixture(account='sample-reflection'):
    return json.loads((ROOT/'tests/fixtures/examples/golden'/f'{account}.json').read_text())


class PsychologyAudienceTests(PackFixtureCase):
    def test_prohibited_script_claim_cannot_escape_into_other_audience_surfaces(self):
        for path in ('title','caption','scenes.0.heading','scenes.0.information'):
            value=fixture();target=value;parts=path.split('.')
            for part in parts[:-1]:target=target[int(part)] if isinstance(target,list) else target[part]
            target[parts[-1]]='Bu davranışın kesin nedeni budur.'
            with self.subTest(path=path),self.assertRaisesRegex(WorkflowError,'certainty/diagnosis'):
                validate_proposal('sample-reflection',value)
    def test_whitespace_case_and_script_still_share_the_same_boundary(self):
        value=fixture();value['caption']='BU DAVRANIŞIN KESİN\n   NEDENİ BUDUR.'
        with self.assertRaisesRegex(WorkflowError,'certainty/diagnosis'):validate_proposal('sample-reflection',value)
        value=fixture();value['script']='Bu davranışın kesin nedeni budur.';value['cues']=[{'start':0,'end':16,'text':value['script']}]
        with self.assertRaisesRegex(WorkflowError,'certainty/diagnosis'):validate_proposal('sample-reflection',value)
    def test_valid_goldens_and_instruction_data_are_preserved(self):
        for account in ACCOUNTS:
            value=fixture(account);result=validate_proposal(account,value)
            self.assertEqual(result['script'],value['script']);self.assertFalse(result['creative']['audit']['publication_ready'])
        value=fixture();value['brief']='Kesin nedeni gibi kesinlik iddialarını kullanma; iki olasılık açık kalsın.'
        self.assertEqual(validate_proposal('sample-reflection',value)['brief'],value['brief'])
    def test_account_specific_guard_does_not_become_a_global_keyword_policy(self):
        value=fixture('sample-flow');value['caption']='Her zaman aynı istek kimliğiyle denetlenen teknik örnek.'
        self.assertEqual(validate_proposal('sample-flow',value)['caption'],value['caption'])


if __name__=='__main__':unittest.main()
