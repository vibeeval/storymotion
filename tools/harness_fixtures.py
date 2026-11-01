"""Internal offline fixture registry; never changes bundled or customer packs."""
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch
from storymotion import account_packs

FIXTURE_ROOT=Path(__file__).resolve().parents[1]/'tests/fixtures/pack-registry'

@contextmanager
def fixture_scope():
    # Mirrors PackFixtureCase for standalone source-only test entrypoints.
    # It does not write work/accountpacks or alter product catalog authority.
    with patch.object(account_packs,'ROOT',FIXTURE_ROOT):
        packs,errors=account_packs.catalog()
        if errors or not packs:raise RuntimeError('HARNESS_FIXTURE_REGISTRY_INVALID')
        yield

def pack_path(account):
    path=FIXTURE_ROOT/'accountpacks/neutral'/(account+'.json')
    if not path.is_file():raise RuntimeError('HARNESS_FIXTURE_PACK_MISSING')
    return path


def template_fixture_brief(account,spec,*args,**kwargs):
    """Explicit synthetic caller context for source-only geometry tests.

    This is not shipped and never supplies claims for customer requests.
    """
    from storymotion.claims import numeric_tokens
    from storymotion.template_intake import audience_values
    from storymotion.template_families import make_brief
    from storymotion.writing_context import sources,snapshot
    from storymotion.security import digest
    data=sources({'synthetic-template':{'url':'https://example.org/synthetic-template-fixture',
        'title':'Explicit synthetic template input','locator':'Local original geometry fixture',
        'excerpt':'Original deterministic test input; values are synthetic, without independent factual verification.',
        'rights_note':'Original synthetic caller declaration for tests only; not an external study or commercial clearance.'}})
    binding={'schema_version':1,'account':account,'sources':snapshot('sources',account,data,None),'canon':None}
    binding['binding_sha256']=digest(binding)
    tokens=numeric_tokens(' '.join(audience_values(spec)))
    claims=[{'text':'Synthetic displayed values: '+' '.join(sorted(tokens)),
             'source':'synthetic-template','scope':'Only supplied synthetic template inputs; no empirical claim, independent truth, or publication approval.'}]
    kwargs.setdefault('claims',claims);kwargs.setdefault('production_context',binding)
    return make_brief(account,spec,*args,**kwargs)
