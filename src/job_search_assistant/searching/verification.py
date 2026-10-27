"""Independent, dated application-status proof; an AI verdict cannot supply it."""
from datetime import date
import re
from urllib.parse import urlsplit
from bs4 import BeautifulSoup

from .normalization import canonical, identities
from ..ingestion import closure_evidence

METHODS={'live_employer_application_form','connected_current_employer_application_form'}
ATS=('greenhouse.io','lever.co','ashbyhq.com','myworkdayjobs.com','smartrecruiters.com',
     'bamboohr.com','jobvite.com','icims.com','dayforcehcm.com','successfactors.com','zohorecruit.com','zohorecruit.in')
AGGREGATORS=('linkedin.com','indeed.com','wellfound.com','builtin.com','himalayas.app',
             'jobs.ca','jobgether.com','remoteok.com','welcometothejungle.com')


def is_employer_url(url,company=""):
    host=urlsplit(url).hostname or ''
    if not host or any(host==d or host.endswith('.'+d) for d in AGGREGATORS): return False
    if any(host==d or host.endswith('.'+d) for d in ATS): return True
    compact=re.sub(r'[^a-z0-9]','',company.casefold())
    domain=re.sub(r'[^a-z0-9]','',host.casefold())
    return len(compact)>=4 and compact in domain


def current_application_verified(posting,as_of=None):
    today=(as_of or date.today()).isoformat()
    if (posting.application_status!='accepting' or posting.application_checked_on!=today
            or posting.application_verification_fresh is not True
            or posting.application_verification_method not in METHODS
            or not posting.application_verification_evidence.strip()
            or not is_employer_url(posting.application_verification_url,posting.company)):
        return False
    # Bind proof to this vacancy, not an unrelated application or careers page.
    proof=identities(posting.application_verification_url)
    return any(proof & identities(url) for url in [posting.url]+posting.aliases)


def choose_verification(checks):
    """Conflicting current employer pages cannot establish acceptance."""
    from dataclasses import replace
    accepting=[p for p in checks if current_application_verified(p)]
    closed=[p for p in checks if p.application_status=='closed' and p.application_verification_fresh]
    if accepting and closed:
        return replace(closed[-1],application_status='unverified',
                       application_verification_evidence='Conflicting current employer application pages; acceptance remains unverified')
    return max(checks,key=lambda p:(current_application_verified(p),p.application_status=='closed',p.application_verification_fresh))


def form_surface(text):
    """Require applicant fields and a role-application heading, not just Apply."""
    start=re.search(r'apply for (?:this|the) (?:job|position)|submit your application|application form',text,re.I)
    if not start: return False
    body=text[start.start():start.start()+14000].casefold()
    return bool(re.search(r'resume|curriculum vitae|\bcv\b',body) and 'email' in body
                and re.search(r'full name|first name|your name',body))


def inspect_connected(posting,raw,checked_on=None):
    """Cached/indexed pages are not promoted to verified current status.

    The connected tool supplies crawl-age metadata. Only a same-day snapshot of
    the employer/ATS application surface can establish current acceptance here.
    """
    checked_on=checked_on or date.today().isoformat()
    lines=re.findall(r'^L\d+: ?(.*)$',raw,re.M)
    text='\n'.join(lines)
    if not text: text=raw
    fresh=bool(re.search(r'Crawled: today\b',raw,re.I))
    source=re.search(r'^.*?\((https?://[^\s]+)\)\n',raw)
    resolved=source[1] if source else posting.url
    redirect=re.search(r'Redirected to URL: (https?://[^;\s]+)',raw)
    if redirect: resolved=redirect[1]
    blocked=any(term in raw for term in ['Failed to fetch','not accessible via this tool','enable JavaScript','Blocked by robots.txt','Total lines: 0'])
    closed=re.search(r'(?:this|the) (?:job|position|role|vacancy|job posting|job opening) (?:has expired|is closed|is no longer available|has been filled|has been closed)|no longer accepting applications|the job you are trying to apply for is no longer available',text,re.I)
    status='unverified'; reason='No job-specific employer application form verified'
    if blocked: reason='Page unavailable, blocked or JavaScript-only; current status unverified'
    elif not fresh: reason='Retrieved snapshot is not dated today; current application status unverified'
    elif not is_employer_url(resolved,posting.company): reason='Third-party/unconfirmed source; employer application status still needs verification'
    elif closed: status='closed';reason=closed[0]
    elif form_surface(text) and re.search(r'\[Input\]|\[Select\]|\[Button: Attach',text): status='accepting';reason='Same-day employer/ATS page displays application heading, resume/CV, email and applicant-name fields'
    elif redirect: reason='Redirected away from the specific vacancy; acceptance not verified'
    posting.application_status=status
    posting.application_checked_on=checked_on
    posting.application_verification_url=resolved
    posting.application_verification_method='connected_current_employer_application_form' if fresh and status=='accepting' else 'connected_current_page' if fresh else 'connected_cached_page'
    posting.application_verification_evidence=reason
    posting.application_verification_fresh=fresh
    return status,reason


def inspect_live(posting,page):
    """A fresh HTTP read must expose an actual application form."""
    soup=BeautifulSoup(page.html,'html.parser')
    for item in soup(['script','style','nav','footer','header']): item.decompose()
    text=soup.get_text(' ',strip=True)
    closed=closure_evidence(page.html)
    applicant_form=False
    for form in soup.find_all('form'):
        fields=form.get_text(' ',strip=True)+' '+ ' '.join(str(x.get('name','')) for x in form.find_all(['input','textarea']))
        applicant_form |= bool(re.search(r'resume|\bcv\b',fields,re.I) and re.search('email',fields,re.I) and re.search('name',fields,re.I))
    status='closed' if closed and is_employer_url(page.url,posting.company) else 'accepting' if applicant_form and form_surface(text) and is_employer_url(page.url,posting.company) else 'unverified'
    posting.application_status=status
    posting.application_checked_on=date.today().isoformat()
    posting.application_verification_url=page.url
    posting.application_verification_method='live_employer_application_form' if status=='accepting' else 'live_employer_page'
    posting.application_verification_evidence=closed or ('Applicant form fields visible on current HTTP response' if status=='accepting' else 'Current page did not expose a verifiable application form')
    posting.application_verification_fresh=True
    return status


def verify_live(posting,client,page=None):
    """Follow one explicit same-vacancy Apply link, without submitting anything."""
    from urllib.parse import urljoin
    posting.application_status='unverified'
    posting.application_verification_fresh=False
    posting.application_checked_on=date.today().isoformat()
    page=page or client.get(posting.url)
    inspect_live(posting,page)
    if posting.application_status!='unverified': return
    soup=BeautifulSoup(page.html,'html.parser')
    for anchor in soup.find_all('a',href=True):
        if 'apply' not in anchor.get_text(' ',strip=True).casefold(): continue
        target=urljoin(page.url,anchor['href'])
        try:
            if canonical(target)==canonical(posting.url) or not identities(target)&identities(posting.url):continue
            inspect_live(posting,client.get(target))
        except (ValueError,OSError):
            posting.application_verification_evidence='Application-link retrieval failed; acceptance remains unverified'
        break
