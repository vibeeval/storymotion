"""Nonempty source identities for testing customer-identity isolation."""
from contextlib import contextmanager
from unittest.mock import patch

from storymotion.account_packs import ACCOUNTS, render_profile


def source_identity(account):
    return {'name': 'Neutral source fixture ' + account,
            'handle': '@source_fixture_' + account.replace('-', '_')}


def source_profile(account):
    profile = render_profile(account)
    profile.update(source_identity(account))
    return profile


def source_identity_values():
    return tuple(value for account in ACCOUNTS for value in source_identity(account).values())


@contextmanager
def source_identity_profiles():
    # Exercise the real customer-identity normalization after loading a profile.
    with patch('storymotion.engine.render_profile', side_effect=source_profile) as loader:
        yield loader


def assert_no_source_identity(testcase, text):
    for expected in source_identity_values():
        testcase.assertTrue(expected, 'Source-identity exclusion must be nonempty')
        testcase.assertNotIn(expected, text)
