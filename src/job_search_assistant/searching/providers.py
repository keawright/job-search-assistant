"""Bounded provider failover. Credentials never enter reports or URLs."""
import json
import os
from urllib.parse import urlencode
from urllib.request import Request

from .normalization import Posting


def brave_search(query, client):
    client._reserve('https://api.search.brave.com')
    request = Request('https://api.search.brave.com/res/v1/web/search?' +
                      urlencode({'q': query, 'country': 'CA', 'count': 20}),
                      headers={'X-Subscription-Token': os.environ['BRAVE_SEARCH_API_KEY'],
                               'Accept': 'application/json'})
    # Fixed official API endpoint; no credential-bearing redirects.
    from urllib.request import build_opener, HTTPRedirectHandler
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    try:
        with build_opener(NoRedirect).open(request, timeout=10) as response:
            raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ValueError('Response too large')
        data = json.loads(raw)
        if not isinstance(data.get('web', {}).get('results', []), list):
            raise ValueError('Invalid results')
    except (OSError, ValueError):
        raise ValueError('Brave Search API unavailable; check credentials, quota or network') from None
    for item in data.get('web', {}).get('results', []):
        if item.get('url', '').startswith('https://'):
            yield Posting(item['url'], title=item.get('title', ''), source='Brave search: ' + query)


class SearchProviders:
    def __init__(self, client, public_search):
        self.client = client
        self.providers = [('Brave API', brave_search)] if os.environ.get('BRAVE_SEARCH_API_KEY') else []
        self.providers.append(('DuckDuckGo HTML', public_search))
        self.failed = set()

    def search(self, query):
        attempts = []
        for name, search in self.providers:
            if name in self.failed:
                continue
            for retry in range(2):
                try:
                    found = list(search(query, self.client))
                    attempts.append({'provider': name, 'status': 'success', 'retry': retry})
                    return found, attempts, True
                except (ValueError, OSError) as exc:
                    attempts.append({'provider': name, 'status': 'failed', 'error': str(exc), 'retry': retry})
                    # Do not hammer denied hosts, challenges or exhausted budgets.
                    if any(s in str(exc).lower() for s in ('robots', '401', '403', '429', '202', 'challenge', 'budget')):
                        break
            self.failed.add(name)
        return [], attempts, False
