"""Measure discovery recall independently of fit and recommendation decisions."""
from .normalization import identities


def evaluate_discovery(references, results):
    observed = []
    for posting, state, reason, review in results:
        keys = set()
        for url in [posting.url] + posting.aliases:
            keys.update(identities(url))
        observed.append((keys, state, reason))
    rows = []
    for reference in references:
        keys = identities(reference['url'])
        match = next((r for r in observed if r[0] & keys), None)
        rows.append(dict(url=reference['url'], source=reference.get('source', 'unspecified'),
                         found=bool(match), state=match[1] if match else 'not discovered',
                         reason=match[2] if match else 'No matching URL or recognized ATS identity retrieved; inspect source coverage'))
    found = sum(r['found'] for r in rows)
    sources = {}
    for row in rows:
        counts = sources.setdefault(row['source'], {'found': 0, 'total': 0})
        counts['total'] += 1
        counts['found'] += row['found']
    return dict(found=found, total=len(rows), recall=found/len(rows) if rows else None,
                sources=sources, postings=rows)
