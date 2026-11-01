"""Explicit maintenance of root snapshots in the five neutral authoring fixtures.

Runtime validation never calls this helper. It does not accept stale hashes or
repair customer work; it authors reproducible test data using the host contract.
"""
import argparse
import copy
import json
import sys
from pathlib import Path

if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from storymotion.security import WorkflowError, digest
from storymotion.writing_context import canon, snapshot, sources, validate_binding

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = tuple('tests/fixtures/examples/edit-plans/' + account + '.json' for account in
                 ('sample-flow', 'sample-mechanism', 'sample-reflection', 'sample-series')) + ('tests/fixtures/examples/raster/neutral-brief.json',)


def rebind_fixture(value):
    value = copy.deepcopy(value)
    context = value['production_context']
    account = value['brand']
    if context['account'] != account:
        raise WorkflowError('Fixture account mismatch; do not repair a foreign binding')
    for kind in ('sources', 'canon'):
        current = context[kind]
        if current is None:
            continue
        if current['account'] != account or current['kind'] != kind or current['parent'] is not None:
            raise WorkflowError('Fixture authoring supports matching root snapshots only')
        data = current['data']
        if kind == 'sources':
            data = sources(data)
        else:
            data['source_revision'] = context['sources']['revision'] if context['sources'] else None
            data = canon(data)
        context[kind] = snapshot(kind, account, data, None)
    context['binding_sha256'] = digest({k: v for k, v in context.items() if k != 'binding_sha256'})
    validate_binding(context, account)
    return value


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--write', action='store_true', help='Write only the fixed neutral fixture paths')
    args = parser.parse_args()
    from unittest.mock import patch
    from storymotion import account_packs
    from pack_fixture_case import FIXTURE_ROOT
    with patch.object(account_packs, 'ROOT', FIXTURE_ROOT):
        for name in FIXTURES:
            path = ROOT / name
            current = json.loads(path.read_text())
            rebuilt = rebind_fixture(current)
            if args.write:
                path.write_text(json.dumps(rebuilt, ensure_ascii=False, indent=2) + '\n')
            elif rebuilt != current:
                raise SystemExit('Stale neutral fixture binding: ' + name)
    print('Neutral fixture bindings match the deterministic host contract')
