"""Stable posting identities; tracking URLs never create a new vacancy."""
from dataclasses import dataclass, field, asdict
import hashlib
import re
from urllib.parse import urlsplit, parse_qs, urlencode, urlunsplit

from ..ingestion import normalize_url


def words(value):
    return ' '.join(re.findall(r'\w+', str(value or '').casefold()))


def canonical(url):
    url = normalize_url(url)
    p = urlsplit(url)
    query = {k: v for k, v in parse_qs(p.query).items()
             if k.casefold() not in {'gh_src', 'source', 'ref', 'refid', 'referral', 'embed', 'lever-source', 'lever-via', 'trk', 'trackingid'}}
    host = (p.hostname or '').lower()
    if host.endswith('linkedin.com'):
        host = 'www.linkedin.com'
        query = {}
    return urlunsplit((p.scheme, host, p.path.rstrip('/'), urlencode(query, doseq=True), ''))


def identities(url):
    p = urlsplit(canonical(url)); host = p.hostname or ''; path = p.path
    keys = {'url:' + canonical(url)}
    query = parse_qs(p.query)
    if query.get('gh_jid'):
        keys.add('greenhouse:' + query['gh_jid'][0])
    if 'greenhouse.io' in host:
        match = re.search(r'/jobs/(\d+)', path)
        if match: keys.add('greenhouse:' + match[1])
    if host.endswith('linkedin.com'):
        match = re.search(r'/view/(?:.*-)?(\d+)', path)
        if match: keys.add('linkedin:' + match[1])
    for domain, prefix in [('ashbyhq.com', 'ashby'), ('lever.co', 'lever')]:
        if host.endswith(domain):
            match = re.search(r'([0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})', path, re.I)
            if match: keys.add(prefix + ':' + match[1].lower())
    if 'myworkdayjobs.com' in host:
        match = re.search(r'_((?:R[-_]?\d+|JR[-_]?\d+|REQ[-_]?\d+|reqid\d+|\d{2}WD\d+))(?:-\d+)?$', path, re.I)
        if match: keys.add('workday:' + host.split('.')[0] + ':' + match[1].casefold())
    if host.endswith('smartrecruiters.com'):
        match = re.search(r'/(\d+)', path)
        if match: keys.add('smartrecruiters:' + match[1])
    if 'zohorecruit.' in host:
        job_id = query.get('jobid', [''])[0]
        match = re.search(r'/jobs/Careers/(\d+)', path)
        if job_id or match: keys.add('zoho:' + host + ':' + (job_id or match[1]))
    if host.endswith('bamboohr.com'):
        match = re.search(r'/(?:careers|jobs)/(\d+)', path)
        if match: keys.add('bamboohr:' + host + ':' + match[1])
    if host.endswith('icims.com'):
        match = re.search(r'/jobs/(\d+)', path)
        if match: keys.add('icims:' + host + ':' + match[1])
    if host.endswith('jobvite.com'):
        match = re.search(r'/([^/]+)/job/([^/]+)', path)
        if match: keys.add('jobvite:' + match[1] + ':' + match[2])
    return keys


def title_key(title):
    title = re.sub(r'\b(sr\.?)(?=\s)', 'senior', str(title), flags=re.I)
    title = re.sub(r'(?:\s*[-|,]\s*)?(?:canada|can|remote|halifax|toronto|united states|usa)\s*$', '', title, flags=re.I)
    return words(title)


def company_key(company):
    return re.sub(r'\s+(inc|ltd|limited|corporation|corp|technologies)$', '', words(company))


@dataclass
class Posting:
    url: str
    company: str = ''
    title: str = ''
    description: str = ''
    location: str = ''
    arrangement: str = 'unknown'
    salary: str = ''
    posted: str = ''
    discovered: str = ''
    source: str = ''
    full_text: bool = False
    application_evidence: str = ''
    aliases: list[str] = field(default_factory=list)
    application_status: str = 'unverified'
    application_checked_on: str = ''
    application_verification_url: str = ''
    application_verification_method: str = ''
    application_verification_evidence: str = ''
    application_verification_fresh: bool = False

    @property
    def key(self):
        return hashlib.sha256(canonical(self.url).encode()).hexdigest()

    @property
    def content_hash(self):
        data = '|'.join(str(v) for k, v in asdict(self).items() if k not in {'discovered', 'source', 'aliases', 'application_status', 'application_checked_on'} and not k.startswith('application_verification_'))
        return hashlib.sha256(data.encode()).hexdigest()
