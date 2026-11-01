"""Conservative numeric/price traceability guard, not a truth detector."""
import re
import unicodedata
from urllib.parse import urlsplit
from .security import WorkflowError


def numeric_tokens(text):
    return set(re.findall(r'\d+(?:[.,]\d+)*(?:\s*%)?',unicodedata.normalize('NFKC',text)))


def audit_claims(brief,source_registry=None,*,fictional=False):
    claims=brief.get('claims',[])
    if not isinstance(claims,list):raise WorkflowError('Claims must be a list')
    registry=source_registry or {};links=[]
    for claim in claims:
        if not isinstance(claim,dict) or set(claim)!={'text','source','scope'} or not all(isinstance(v,str) and v.strip() for v in claim.values()):
            raise WorkflowError('Claim requires exact text, caller source ID and scope')
        source=registry.get(claim['source'])
        if not isinstance(source,dict):raise WorkflowError('Claim source must exist in the caller-owned registry')
        url=source.get('url','');parsed=urlsplit(url)
        if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
            raise WorkflowError('Claim source requires a bounded HTTPS source link')
        if len(url)>2000:raise WorkflowError('Claim source link too long')
        links.append({'text':claim['text'],'source_id':claim['source'],'source_url':url,'scope':claim['scope'],
                      'source_truth':'pending_human_review'})
        if 'excerpt' in source:
            from .security import digest
            links[-1].update(source_snapshot_sha256=digest(source),locator=source['locator'],excerpt=source['excerpt'])
    text=' '.join(str(brief.get(k,'')) for k in ['title','script','caption'])+' '+' '.join(s.get('heading','')+' '+s.get('information','') for s in brief.get('scenes',[]))
    covered=' '.join(c['text'] for c in claims)
    if not fictional:
        uncovered=numeric_tokens(text)-numeric_tokens(covered)
        price=bool(re.search(r'[$€₺]|\b(?:USD|EUR|TRY|TL|fiyat[ıi]?|ücretsiz|bedava|dolar|avro)\b',text,re.I))
        if uncovered or price and not claims:raise WorkflowError('Unsourced number or price; add a caller-registered scoped claim before production')
    return {'status':'incomplete','source_links':links,'source_truth':'pending_human_review',
            'numeric_price_guard':'fictional_explicit_exemption' if fictional else 'pass',
            'limitation':'Conservative surface check; nonnumeric claims and source truth still require human review'}
