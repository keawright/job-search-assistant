"""Independent title, board, employer and specialization discovery strategies."""
import json
import re
from pathlib import Path
from urllib.parse import quote, urljoin, parse_qs, urlsplit
from bs4 import BeautifulSoup
from .normalization import Posting

PRIMARY = ['Engineering Manager','Senior Engineering Manager','Software Engineering Manager',
           'Software Development Manager','Platform Engineering Manager','Infrastructure Engineering Manager',
           'Backend Engineering Manager','Data Engineering Manager','Technical Program Manager',
           'Senior Technical Program Manager','Engineering Program Manager','Technical Delivery Manager']
SECONDARY = ['Technical Project Manager','IT Program Manager','Director of Engineering',
             'Director of Software Engineering','Director of Technical Program Management','Director of Technology',
             'Engineering Delivery Manager','Development Manager','Agile Delivery Manager',
             'Organizational Change Manager','Technical Operations Manager']
BOARDS = ['linkedin.com/jobs','ca.indeed.com','wellfound.com','welcometothejungle.com','builtin.com',
          'remote.co','weworkremotely.com','remoteok.com','workintech.ca','careerbeacon.com','digitalnovascotia.com',
          'jobs.novascotia.ca','jobs.smartrecruiters.com','myworkdayjobs.com','bamboohr.com','jobvite.com','icims.com']
# Discovery seeds, not claims that an employer currently has a suitable vacancy.
EMPLOYERS = {
    'saas': 'Clio Jobber JaneApp Thinkific D2L AbsorbSoftware FreshBooks Hootsuite Unbounce Vidyard 1Password Ada Loopio Docebo Float TouchBistro Lightspeed Coveo Rewind Plooto',
    'infrastructure': 'GrafanaLabs Elastic MongoDB Confluent Redis CockroachLabs ClickHouse Temporal HashiCorp Cloudflare Fastly Tailscale Docker GitLab GitHub Canonical Sentry Honeycomb Datadog Render',
    'fintech': 'Wealthsimple KOHO NeoFinancial Borrowell Wave Stripe Affirm Mercury Brex Ramp FloatFinancial Shakepay Coinbase Kraken AnchorageDigital Chainalysis TRMLabs DapperLabs Alchemy',
    'atlantic': 'DashSocial Introhive Verafin CoLab Spellbook SonraiSecurity BeyondTrust REDspace DashQ Proposify SimplyCast Mariner Eastlink BellAtlantic Rogers CGI NTTData IBM Deloitte Accenture MOBIA Bulletproof IMP Lixar Kainos Wattpad Salesforce GeneralDynamics LockheedMartin Ultra',
    'health-commerce': 'Fullscript League Maple Felix Dialogue PointClickCare Jane WELL Shopify Faire Instacart ApplyDigital TELUSHealth LifeRaft SpryPoint CarbonCure OpusFundServices Citco',
}


def plan():
    queries = [('title', f'"{title}" (Canada remote OR Halifax) jobs -filetype:pdf') for title in PRIMARY + SECONDARY]
    queries += [('related title', f'\"{title}\" Canada remote careers') for title in ['DevOps Manager','Site Reliability Engineering Manager','Developer Experience Manager','Head of Engineering','Cloud Engineering Manager','Manager, Infrastructure','Engineering Enablement Lead']]
    queries += [('board', f'site:{board} ("engineering manager" OR "technical program manager" OR "delivery manager") (Canada OR Halifax)') for board in BOARDS]
    queries += [('specialization', f'("engineering manager" OR "program manager") {term} Canada remote careers')
                for term in ['platform','infrastructure','backend','distributed systems','data platform','SaaS','IAM identity','fintech','organizational transformation']]
    for category, names in EMPLOYERS.items():
        queries += [('employer:' + category, f'"{name}" careers ("engineering manager" OR "program manager" OR "delivery manager") Canada') for name in names.split()]
    return queries


def web_search(query, client):
    page = client.get('https://html.duckduckgo.com/html/?q=' + quote(query))
    soup = BeautifulSoup(page.html,'html.parser')
    if not soup.select('a.result__a') and re.search('captcha|anomaly|challenge',page.html,re.I):
        raise ValueError('Search blocked by anti-bot challenge; no bypass attempted')
    for a in soup.select('a.result__a')[:15]:
        href = urljoin(page.url,a.get('href',''))
        href = parse_qs(urlsplit(href).query).get('uddg',[href])[0]
        if href.startswith('https://'):
            yield Posting(href,title=a.get_text(' ',strip=True),source='Search: ' + query)


def ats_board(platform, board, client):
    if platform == 'greenhouse':
        data = client.get(f'https://boards-api.greenhouse.io/v1/boards/{quote(board)}/jobs?content=true', True)
        for j in data['jobs']:
            yield Posting(j['absolute_url'],board,j['title'],BeautifulSoup(j.get('content',''),'html.parser').get_text(' ',strip=True),
                          j.get('location',{}).get('name',''),source=f'Greenhouse board:{board}',full_text=bool(j.get('content')),
                          application_evidence='Listed in public employer ATS feed')
    elif platform == 'lever':
        data = client.get(f'https://api.lever.co/v0/postings/{quote(board)}?mode=json', True)
        for j in data:
            text = j.get('descriptionPlain','') + ' ' + ' '.join(x.get('text','') + ' ' + BeautifulSoup(x.get('content',''),'html.parser').get_text(' ',strip=True) for x in j.get('lists',[]))
            yield Posting(j['hostedUrl'],board,j['text'],text,j.get('categories',{}).get('location',''),
                          j.get('workplaceType','unknown'),posted='',source=f'Lever board:{board}',full_text=len(text.strip())>=100,
                          application_evidence='Listed in public employer ATS feed')
    elif platform == 'ashby':
        data = client.get(f'https://api.ashbyhq.com/posting-api/job-board/{quote(board)}', True)
        for j in data['jobs']:
            if j.get('isListed') is False: continue
            yield Posting(j['jobUrl'],board,j['title'],j.get('descriptionPlain',''),j.get('location',''),
                          'remote' if j.get('isRemote') else 'unknown',source=f'Ashby board:{board}',full_text=bool(j.get('descriptionPlain')),
                          application_evidence='Listed in public employer ATS feed')


def capture_postings(folder):
    """Import connected-search evidence when local sockets are unavailable.

    Search excerpts remain unverified; a separate full-text retrieval or grounded
    review is required before promotion. Each raw response retains its query log.
    """
    if not folder: return
    for path in sorted(Path(folder).glob('*.txt')):
        raw = path.read_text(encoding='utf-8')
        pattern = r'^([^\n]+) \((https?://[^\s]+)\)\n'
        matches = list(re.finditer(pattern,raw,re.M))
        for i,m in enumerate(matches):
            text = raw[m.end():matches[i+1].start() if i+1<len(matches) else len(raw)]
            title,company=m[1],''
            if ' @ ' in title:
                title,company=title.split(' @ ',1); company=company.split(' | ')[0]
            elif ' at ' in title:
                title,company=title.rsplit(' at ',1); company=company.split(' | ')[0].split(' ? ')[0]
            title=re.sub(r'^Job Application for ', '', title)
            board=board_from_url(m[2])
            if not company and board: company=board[1]
            yield Posting(m[2],company=company,title=title,description=text,source=f'Connected search capture:{path.name}')


def board_from_url(url):
    p=urlsplit(url); bits=p.path.strip('/').split('/')
    if not bits or not bits[0]: return None
    if p.hostname in {'job-boards.greenhouse.io','boards.greenhouse.io','job-boards.eu.greenhouse.io'}: return 'greenhouse',bits[0]
    if p.hostname=='jobs.lever.co': return 'lever',bits[0]
    if p.hostname=='jobs.ashbyhq.com': return 'ashby',bits[0]
    return None


def employer_page(url,client):
    """Follow visible role/ATS links on a public employer career page only."""
    from .eligibility import title_gate
    page=client.get(url)
    soup=BeautifulSoup(page.html,'html.parser')
    roles=[];boards=set()
    for anchor in soup.find_all('a',href=True):
        href=urljoin(page.url,anchor['href'])
        if not href.startswith(('https://','http://')): continue
        board=board_from_url(href)
        if board: boards.add(board)
        title=anchor.get_text(' ',strip=True)
        if title_gate(title):
            roles.append(Posting(href,title=title,source='Employer career page: '+page.url))
    return roles,boards
