"""Read-only, bounded public retrieval with robots checks and host pacing."""
import json
import time
from urllib.parse import urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser
from ..ingestion import fetch_page, FetchError, extract_posting, closure_evidence


class PublicClient:
    def __init__(self, budget=250, delay=1.0, fetcher=fetch_page):
        self.budget, self.delay, self.fetcher = budget, delay, fetcher
        self.calls = 0
        self.robots, self.last, self.failures = {}, {}, {}

    def _reserve(self, url):
        if self.calls >= self.budget: raise FetchError('Search request budget reached')
        host = urlsplit(url).netloc
        wait = self.delay - (time.monotonic() - self.last.get(host, 0))
        if wait > 0: time.sleep(wait)
        self.calls += 1; self.last[host] = time.monotonic()

    def _read(self,url,types,check_redirects=False):
        self._reserve(url)
        return self.fetcher(url,timeout=10,max_bytes=8_000_000,content_types=types,
                            redirect_check=self._redirect if check_redirects else None)

    def _redirect(self,url):
        self._allowed(url)
        self._reserve(url)

    def _allowed(self, url):
        p = urlsplit(url); root = urlunsplit((p.scheme,p.netloc,'','',''))
        if root in self.failures: raise FetchError(self.failures[root])
        if root not in self.robots:
            try:
                page = self._read(root + '/robots.txt', ('text/plain','text/html'))
                robot = RobotFileParser(); robot.parse(page.html.splitlines())
                self.robots[root] = robot
            except FetchError as exc:
                if str(exc).startswith('HTTP 404'):
                    robot = RobotFileParser(); robot.parse([]); self.robots[root] = robot
                else:
                    self.failures[root] = 'Robots/access check unavailable: ' + str(exc)
                    raise FetchError(self.failures[root])
        robot = self.robots[root]
        if not robot.can_fetch('JobSearchAssistant', url): raise FetchError('robots.txt disallows this URL')
        crawl_delay = robot.crawl_delay('JobSearchAssistant') or robot.crawl_delay('*') or 0
        if crawl_delay > 30: raise FetchError('robots crawl delay exceeds this run pacing budget')
        self.delay = max(self.delay, crawl_delay)
    def get(self,url,json_response=False):
        self._allowed(url)
        types = ('application/json','text/json') if json_response else ('text/html','application/xhtml+xml')
        page = self._read(url, types, check_redirects=True)
        return json.loads(page.html) if json_response else page


def enrich(posting, client):
    posting.application_status='unverified'
    posting.application_verification_fresh=False
    posting.application_verification_evidence='Current application check incomplete'
    try:
        page = client.get(posting.url)
    except (ValueError, OSError) as exc:
        from .verification import mark_removed
        if mark_removed(posting, posting.url, exc):
            return posting
        raise
    data = extract_posting(page.html)
    feed_evidence = (posting.full_text and posting.source.startswith(('Greenhouse board:', 'Lever board:', 'Ashby board:'))
                     and len(posting.description.strip()) >= 100)
    complete_page = bool(data.company and data.title and data.description)
    posting.aliases = list(set(posting.aliases + [posting.url]))
    posting.url = page.url
    if complete_page or not feed_evidence:
        posting.company = data.company or posting.company
        posting.title = data.title or posting.title
        posting.description = data.description or ''
        posting.full_text = complete_page
    posting.location = data.location.evidence or posting.location
    posting.arrangement = data.location.arrangement
    posting.posted = data.posting_date.isoformat() if data.posting_date else posting.posted
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(page.html, 'html.parser')
    application = next((a.get_text(' ',strip=True) for a in soup.find_all(['a','button'])
                        if 'apply' in a.get_text(' ',strip=True).casefold()), '')
    from .verification import verify_live
    verify_live(posting,client,page=page)
    posting.application_evidence = ('Closed: ' + closure_evidence(page.html)) if closure_evidence(page.html) else application
    return posting
