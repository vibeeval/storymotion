"""Construct synthetic key shapes at runtime, never embed usable credentials."""
import unittest

from storymotion.security import scan_bytes


class SecretFormatTests(unittest.TestCase):
    def test_google_key_detected_in_assignments_urls_and_unlabelled_content(self):
        value='AI'+'za'+'A1_-'*8+'B2c'
        self.assertEqual(len(value),39)
        for text in (value,'"api_key":"'+value+'"','https://example.invalid/?key='+value,'prefix'+value+'suffix'):
            with self.subTest(text_kind=text[:8]):self.assertIn('google-api-key',[r['kind'] for r in scan_bytes(text.encode())])

    def test_short_examples_public_hashes_and_fake_assignments_do_not_match(self):
        for text in ('AIza','AI'+'za'+'A'*34,'AI'+'za'+'!'*35,'abc123'*12,'https://example.invalid/public','api_key=FAKE_TEST_VALUE_123456'):
            with self.subTest(text_kind=text[:8]):self.assertEqual(scan_bytes(text.encode()),[])

    def test_existing_common_key_private_key_and_bearer_patterns_remain_active(self):
        cases=[('sk-'+'a'*30,'provider-key'),('ghp_'+'b'*36,'provider-key'),('AKIA'+'A'*16,'provider-key'),
               ('-----BEGIN '+'PRIVATE KEY-----','private-key'),('Bearer '+'C'*30,'bearer')]
        for text,kind in cases:
            with self.subTest(kind=kind):self.assertIn(kind,[r['kind'] for r in scan_bytes(text.encode())])
