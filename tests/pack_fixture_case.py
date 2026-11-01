"""Explicit class-scoped registry fixtures; the shipped product has one pack."""
import unittest
from pathlib import Path
from unittest.mock import patch

from storymotion import account_packs

FIXTURE_ROOT = Path(__file__).resolve().parent / 'fixtures/pack-registry'


class PackFixtureCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        fixture_scope = patch.object(account_packs, 'ROOT', FIXTURE_ROOT)
        fixture_scope.start()
        cls.addClassCleanup(fixture_scope.stop)
