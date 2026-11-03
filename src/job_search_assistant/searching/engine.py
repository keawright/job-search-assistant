"""Repeatable discovery orchestration and auditable recommendation promotion."""
from dataclasses import asdict
from datetime import date, datetime
import json
import re
from pathlib import Path

from ..archive import current_workbook, fingerprint
from ..assessment import load_service, AssessmentError
from ..ingestion import FetchError
from .normalization import Posting, canonical, company_key
from .storage import Store
from .discovery import plan, web_search, ats_board, board_from_url, capture_postings, employer_page, EMPLOYERS
from .retrieval import PublicClient, enrich
from .eligibility import title_gate, location_gate, exclusion_reason
from .evaluation import SearchReviewer, decide, review_hash
from .reporting import export, coverage_summary
from .verification import current_closure_verified


def _run_search(folder, *, workbook=None,captures=None,reviews=None,offline=False,max_queries=200,
               max_requests=250,max_assessments=100,resume_path=None,model=None,benchmark_file=None,progress=print):
    folder=Path(folder).resolve(); source=Path(workbook or current_workbook(folder)).resolve()
    private=folder/'.job-search-assistant-private'/'search'; private.mkdir(parents=True,exist_ok=True)
    run=datetime.now().strftime('%Y%m%d-%H%M%S-%f'); checked=date.today().isoformat()
    before=fingerprint(source)
    store=Store(private/'discovery.sqlite3'); coverage=[]; results=[]; candidates={}
    try:
        imported=store.import_workbook(source)
        for old in sorted((folder/'archive').glob('*.xlsx')):
            imported+=store.import_workbook(old)
        # Reports are also reviewed history, including exports from versions
        # that did not mark Needs Verification findings as reported.
        for old in sorted((private/'reports').glob('job-search-*.xlsx')):
            imported+=store.import_workbook(old)
        pending_urls=folder/'new_urls.txt'
        if pending_urls.exists():
            from .normalization import identities
            for url in pending_urls.read_text(encoding='utf-8-sig').splitlines():
                if url.strip() and not url.lstrip().startswith('#'):
                    try:
                        for identity in identities(url.strip()):
                            store.db.execute('INSERT OR IGNORE INTO exclusions VALUES(?,?)',(identity,'Pending URL input list'))
                    except ValueError: pass
            store.db.commit()
        progress(f'Imported {imported} workbook rows across current/archive files and every worksheet.')
        service=load_service(folder,offline=True,resume_path=resume_path)
        if service is None: raise ValueError('Configure a private resume before search; no fabricated assessments')
        resume=service.resume
        additions=private/'candidate-additions.md'
        if additions.exists(): resume+='\n\n'+additions.read_text(encoding='utf-8')
        reviewer=None if offline else SearchReviewer(private,resume,model,max_assessments)
        reviewed={}
        if reviews:
            for item in json.loads(Path(reviews).read_text(encoding='utf-8')):
                p=Posting(**item['posting']); reviewed[canonical(p.url)]=item
        def add(p):
            try: key=canonical(p.url)
            except ValueError: return
            old=store.db.execute('SELECT first_seen FROM findings WHERE key=?',(p.key,)).fetchone()
            p.discovered=old[0] if old else p.discovered or checked
            if key not in candidates or (p.full_text and not candidates[key].full_text): candidates[key]=p
        # Only retry leads that have never appeared in a completed report.
        for payload, in store.db.execute("SELECT payload FROM findings WHERE state='verification' AND reported_on IS NULL"):
            add(Posting(**json.loads(payload)))
        for p in capture_postings(captures): add(p)
        if captures:
            for meta in sorted(Path(captures).glob('*.meta.json')):
                c=json.loads(meta.read_text(encoding='utf-8'))
                raw=meta.with_name(meta.name.replace('.meta.json','.txt'))
                count=len(list(capture_postings_single(raw)))
                limitation='Search-index evidence; full posting/application verification separate. '+c.get('limitation','')
                if raw.exists() and 'Blocked by robots.txt' in raw.read_text(encoding='utf-8'):
                    limitation+=' Some requested domains blocked by robots.txt; no bypass attempted.'
                coverage.append(dict(source=meta.stem,method='Connected search: '+' | '.join(c['queries']),checked=c['checked_on'],
                                     discovered=count,assessed=0,error=limitation))
        for item in reviewed.values(): add(Posting(**item['posting']))
        for page_file in sorted((private/'pages').glob('*.json')):
            page=json.loads(page_file.read_text(encoding='utf-8'))
            text=page.get('text','')
            unavailable=any(t in text for t in ['not accessible via this tool','enable JavaScript','Total lines: 0','Failed to fetch'])
            coverage.append(dict(source=page.get('url',page_file.name),method='Connected public page retrieval',
                                 checked=page.get('checked_on',checked),discovered=0,assessed=0,
                                 error='Unavailable/JavaScript-only; not verified' if unavailable else 'Public page read; application and eligibility evaluated separately'))

        client=PublicClient(max_requests)
        if not offline:
            queries=plan()
            seed_names={name.casefold() for names in EMPLOYERS.values() for name in names.split()}
            for name, in store.db.execute("SELECT name FROM employers WHERE category='discovered' ORDER BY name"):
                if name.casefold() not in seed_names and len(name)<60 and re.fullmatch(r'[\w &.+-]+',name):
                    queries.append(('learned employer',f'"{name}" careers ("engineering manager" OR "program manager") Canada'))
            from .providers import SearchProviders
            from .discovery import balanced_plan, load_sources
            pending_file=private/'pending-queries.json'
            pending=json.loads(pending_file.read_text(encoding='utf-8')) if pending_file.exists() else []
            rotation_file=private/'query-rotation.json'
            rotation=json.loads(rotation_file.read_text()) if rotation_file.exists() else 0
            queries=balanced_plan(queries,rotation)
            # Alternate unfinished work with fresh groups so neither can starve.
            from itertools import zip_longest
            combined=[]
            for pair in zip_longest(pending,queries):
                for item in pair:
                    if item and tuple(item) not in combined: combined.append(tuple(item))
            selected=combined[:max_queries]; remaining=combined[max_queries:]
            providers=SearchProviders(client,web_search)
            for query_index,(method,query) in enumerate(selected):
                # Preserve request capacity for employer feeds and role verification.
                if client.calls >= max_requests * 0.4:
                    remaining.extend(selected[query_index:])
                    break
                found,attempts,complete=providers.search(query)
                for p in found: add(p)
                if not complete: remaining.append((method,query))
                coverage.append(dict(source=query,method=method,checked=checked,discovered=len(found),assessed=0,
                                     status='success' if complete else 'failed',kind='web query',attempts=attempts,
                                     error='' if complete else ('All configured search providers unavailable' if attempts else 'Not executed: all search providers unavailable')))
            pending_file.write_text(json.dumps(remaining,indent=2),encoding='utf-8')
            rotation_file.write_text(json.dumps(rotation+1))
            coverage.append(dict(source='Query scheduling',method='Query budget',checked=checked,
                                 discovered=0,assessed=0,kind='schedule',deferred=len(remaining),planned=len(combined),selected=len(selected),
                                 error=f'{len(remaining)} unfinished queries saved for later runs' if remaining else ''))
            boards=set()
            for entry in load_sources(private/'employer-sources.json'):
                if entry.get('platform'):
                    boards.add((entry['platform'],entry['board']))
                if entry.get('url'): add(Posting(entry['url'],source='Employer source inventory'))
            careers_file=private/'learned-careers.json'
            known_careers=json.loads(careers_file.read_text()) if careers_file.exists() else []
            for url in known_careers: add(Posting(url,source='Saved employer careers page'))
            explored=set()
            aggregators=('linkedin.com','indeed.com','reddit.com','wellfound.com','jobs.ca','builtin.com','himalayas.app')
            from urllib.parse import urlsplit
            for p in list(candidates.values()):
                host=urlsplit(p.url).hostname or ''
                if (len(explored)>=40 or host in explored or any(host.endswith(a) for a in aggregators)
                        or title_gate(p.title) or not re.search(r'/careers(?:/|$)|/jobs/?(?:\?|$)',p.url)):
                    continue
                explored.add(host)
                if p.url not in known_careers: known_careers.append(p.url)
                try:
                    found,new_boards=employer_page(p.url,client)
                    boards.update(new_boards)
                    for candidate in found: add(candidate)
                    error=''
                except (ValueError,OSError) as exc:
                    found=[]; error=str(exc)
                coverage.append(dict(source=p.url,method='Direct employer career-page links',checked=checked,discovered=len(found),assessed=0,error=error))
            careers_file.write_text(json.dumps(known_careers,indent=2))
            for p in candidates.values():
                board=board_from_url(p.url)
                if board: boards.add(board)
            # Learn employer ATS boards from existing exclusions as well.
            for identity, in store.db.execute("SELECT identity FROM exclusions WHERE identity LIKE 'url:%'"):
                board=board_from_url(identity[4:])
                if board: boards.add(board)
            for payload, in store.db.execute('SELECT payload FROM findings'):
                board=board_from_url(json.loads(payload)['url'])
                if board: boards.add(board)
            # Persist discovered boards independently of future search results.
            inventory=private/'learned-boards.json'
            if inventory.exists(): boards.update(tuple(x) for x in json.loads(inventory.read_text()))
            inventory.write_text(json.dumps(sorted(boards),indent=2))
            for platform,board in sorted(boards):
                try:
                    found=list(ats_board(platform,board,client))
                    for p in found: add(p)
                    error=''
                except (ValueError,OSError,KeyError) as exc:
                    found=[];error=str(exc)
                coverage.append(dict(source=f'{platform}:{board}',method='Public employer ATS feed',checked=checked,discovered=len(found),assessed=0,error=error))
        for category,names in EMPLOYERS.items():
            for name in names.split(): store.db.execute('INSERT OR IGNORE INTO employers VALUES(?,?,?,?)',(name,'',category,checked))
        progress(f'{len(candidates)} unique candidate URLs discovered; applying exclusions before role assessment.')
        for index,p in enumerate(candidates.values(),1):
            progress(f'[{index}/{len(candidates)}] {p.company} {p.title}')
            state,reason=store.duplicate(p); review={}
            hard_exclusion=exclusion_reason(p)
            if state=='duplicate': pass
            elif hard_exclusion: state,reason='rejected',hard_exclusion
            elif state=='uncertain': state='verification'
            elif re.search(r'/careers/?(?:[?#].*)?$|/jobs/?(?:[?#].*)?$|/company/[^/]+/jobs|/role/l/|indeed\.com/[a-z]-.*jobs\.html',p.url,re.I): state,reason='rejected','Career/search index rather than a specific vacancy; visible links are explored separately where accessible'
            elif re.search(r'\.pdf(?:[?#]|$)',p.url,re.I): state,reason='rejected','Document search result; no verified current application posting'
            elif not title_gate(p.title) and p.title not in {'page_title','Jobs',''} and canonical(p.url) not in reviewed: state,reason='rejected','Title outside target software/technical leadership and delivery roles'
            else:
                item=reviewed.get(canonical(p.url))
                if item:
                    if item.get('input_hash')!=review_hash(p,resume):
                        state,reason='verification','Review does not match current role/candidate evidence'
                    else:
                        review=item['review']
                        try: state,reason=decide(p,review,resume)
                        except (ValueError,TypeError,KeyError): state,reason='verification','Review failed evidence validation'
                else:
                    if not offline:
                        try: p=enrich(p,client)
                        except (ValueError,OSError) as exc: reason='Role retrieval unavailable: '+str(exc)
                    matched,duplicate_reason=store.duplicate(p)
                    loc,loc_reason=location_gate(p.description,p.location)
                    hard_exclusion=exclusion_reason(p)
                    if hard_exclusion: state,reason='rejected',hard_exclusion
                    elif matched=='duplicate': state,reason='duplicate',duplicate_reason
                    elif matched=='uncertain': state,reason='verification',duplicate_reason
                    elif current_closure_verified(p): state,reason='rejected','Employer vacancy closed or removed: '+p.application_verification_evidence
                    elif loc=='ineligible': state,reason='rejected',loc_reason
                    elif not p.full_text: state,reason='verification',reason or 'Full employer role description/application status not verified'
                    elif reviewer is None: state,reason='verification','Grounded fit review required'
                    else:
                        try:
                            review=reviewer.review(p); state,reason=decide(p,review,resume)
                        except (ValueError,OSError) as exc: state,reason='verification','Assessment unavailable: '+str(exc)
            if state not in {'duplicate'} and current_closure_verified(p):
                state,reason='rejected','Employer vacancy closed or removed: '+p.application_verification_evidence
            # Preserve a grounded review for audit even when duplicate/location
            # gates prevent recommending it. This does not override those gates.
            if not review and canonical(p.url) in reviewed:
                item=reviewed[canonical(p.url)]
                if item.get('input_hash')==review_hash(p,resume):
                    from .evaluation import validate_review, context_for
                    try:
                        validate_review(item['review'],resume,context_for(p))
                        review=item['review']
                    except (ValueError,TypeError,KeyError): pass
            results.append((p,state,reason,review))
            store.record(p,state,reason,review,run)
            if p.company:
                store.db.execute('INSERT OR IGNORE INTO employers VALUES(?,?,?,?)',(p.company,p.url,'discovered',checked))
        results.sort(key=lambda r:(0 if r[2]=='Strong Fit' else 1, -date.fromisoformat(r[0].posted[:10]).toordinal() if re.fullmatch(r'\d{4}-\d{2}-\d{2}',r[0].posted[:10]) else 0,r[0].company,r[0].title))
        companies=set(); final=[]
        for p,state,reason,review in results:
            if state=='recommended':
                if company_key(p.company) in companies:
                    state,reason='superseded','Only strongest new fit per company recommended by default'
                    store.record(p,state,reason,review,run)
                else: companies.add(company_key(p.company))
            final.append((p,state,reason,review))
        coverage.append(dict(source='Grounded candidate review',method='Exact-quotation validated review',checked=checked,
                             discovered=len(candidates),assessed=sum(bool(r[3]) for r in final),error='No hiring probabilities; uncertainty holds recommendations.'))
        for c in coverage: store.coverage(run,c)
        if fingerprint(source)!=before: raise ValueError('Input workbook changed during search; rerun with latest edits')
        if benchmark_file:
            from .benchmark import evaluate_discovery
            benchmark=evaluate_discovery(json.loads(Path(benchmark_file).read_text(encoding='utf-8')),final)
            (private/f'benchmark-{run}.json').write_text(json.dumps(benchmark,indent=2),encoding='utf-8')
            coverage.append(dict(source='Discovery benchmark',method='Reference posting recall',checked=checked,
                                 discovered=benchmark['found'],assessed=0,error=f"Found {benchmark['found']} of {benchmark['total']} reference postings; misses recorded in benchmark JSON"))
        # Keep duplicate decisions in the private audit history, without showing
        # previously reviewed links again in any result tab or CSV.
        outputs=export(private/'reports',run,[r for r in final if r[1]!='duplicate'],coverage)
        for p,state,reason,review in final:
            if state in {'recommended','verification'}: store.db.execute('UPDATE findings SET reported_on=? WHERE key=?',(run,p.key))
        manifest={'run':run,'workbook':str(source),'workbook_sha256':before,'imported_rows':imported,
                  'discovered':len(candidates),'recommended':sum(r[1]=='recommended' for r in final),
                  'verification':sum(r[1]=='verification' for r in final),'requests':client.calls,
                  'assessed':sum(bool(r[3]) for r in final),'summary':coverage_summary(final,coverage),'outputs':[str(p) for p in outputs]}
        (private/f'run-{run}.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        progress(json.dumps(manifest,indent=2)); return outputs
    finally: store.close()


def capture_postings_single(path):
    if not path.exists(): return []
    return re.findall(r'^([^\n]+) \((https?://[^\s]+)\)\n',path.read_text(encoding='utf-8'),re.M)


def run_search(folder, **kwargs):
    from .locking import run_lock
    private=Path(folder).resolve()/'.job-search-assistant-private'/'search'
    with run_lock(private/'.run.lock'):
        return _run_search(folder,**kwargs)
