import json
from types import SimpleNamespace

from openpyxl import Workbook, load_workbook

from job_search_assistant.searching.providers import SearchProviders
from job_search_assistant.searching.normalization import Posting
from job_search_assistant.searching.discovery import balanced_plan
from job_search_assistant.searching.reporting import export, coverage_summary
from job_search_assistant.searching.benchmark import evaluate_discovery


def test_search_layout_change_is_failure_not_zero_results():
    import pytest
    from job_search_assistant.searching.discovery import web_search
    client=SimpleNamespace(get=lambda url:SimpleNamespace(html='<html>Unexpected page</html>',url=url))
    with pytest.raises(ValueError,match='format unrecognized'):
        list(web_search('query',client))


def test_provider_failover_and_denied_host_not_retried(monkeypatch):
    monkeypatch.delenv('BRAVE_SEARCH_API_KEY', raising=False)
    calls=[]
    def denied(q,c):
        calls.append('denied')
        raise ValueError('HTTP 403')
    def good(q,c):
        calls.append(q)
        return [Posting('https://example.com/role')]
    providers=SearchProviders(None,denied)
    providers.providers.append(('independent',good))
    found,attempts,complete=providers.search('first')
    assert complete and len(found)==1
    assert [a['status'] for a in attempts]==['failed','success']
    providers.search('second')
    assert calls==['denied','first','second']


def test_transient_failure_retries_once_and_exhaustion_does_not_hammer(monkeypatch):
    monkeypatch.delenv('BRAVE_SEARCH_API_KEY', raising=False)
    calls=[]
    def unavailable(q,c):
        calls.append(q)
        raise OSError('timeout')
    providers=SearchProviders(None,unavailable)
    assert providers.search('first')[2] is False
    assert providers.search('second')[1]==[]
    assert calls==['first','first']


def test_small_budget_covers_groups_and_rotates_within_groups():
    queries=[('titles','a'),('titles','b'),('employers','c'),('employers','d')]
    first=balanced_plan(queries)
    second=balanced_plan(queries,1)
    assert len({m for m,q in first[:4]})==4
    assert first!=second
    assert set(first)==set(second)


def test_report_prominently_labels_incomplete_run_and_shows_unreviewed_lead(tmp_path):
    coverage=[dict(source='query',method='title',kind='web query',status='failed',attempts=[{}],error='HTTP 202')]
    results=[(Posting('https://example.com/role','Example','Engineering Manager'),'verification','Location evidence needed',{})]
    xlsx,md=export(tmp_path,'incomplete',results,coverage)
    assert '**Search incomplete**' in md.read_text()
    assert 'Location evidence needed' in md.read_text()
    wb=load_workbook(xlsx)
    assert wb['Run Summary']['B2'].value=='Search incomplete'
    assert wb['Needs Verification']['H2'].value=='Needs assessment'
    wb.close()
    assert coverage_summary([],[])['status']=='Search incomplete'


def test_benchmark_matches_ats_alias_even_if_job_is_filtered():
    results=[(Posting('https://job-boards.greenhouse.io/demo/jobs/123'),'duplicate','Already tracked',{})]
    report=evaluate_discovery([{'url':'https://example.com/job?gh_jid=123','source':'employer'},
                               {'url':'https://example.com/missed','source':'board'}],results)
    assert report['recall']==0.5
    assert report['postings'][0]['state']=='duplicate'
    assert report['sources']['board']=={'found':0,'total':1}


def test_documented_ashby_api_does_not_request_authenticated_root_robots():
    from job_search_assistant.searching.retrieval import PublicClient
    from job_search_assistant.ingestion import Page, FetchError
    import pytest
    calls=[]
    def fetch(url,**kwargs):
        calls.append(url)
        assert '/posting-api/job-board/' in url
        return Page(url,'{"jobs":[]}')
    client=PublicClient(delay=0,fetcher=fetch)
    assert client.get('https://api.ashbyhq.com/posting-api/job-board/demo',True)=={'jobs':[]}
    assert len(calls)==1
    def denied(url,**kwargs): raise FetchError('HTTP 401')
    client=PublicClient(delay=0,fetcher=denied)
    with pytest.raises(FetchError,match='401'):
        client.get('https://api.ashbyhq.com/posting-api/job-board/demo',True)


def test_failed_queries_persist_and_independent_inventory_still_runs(tmp_path,monkeypatch):
    from job_search_assistant.searching import engine, discovery
    tracker=tmp_path/'tracker.xlsx'
    wb=Workbook(); wb.active.append(['Company','Job title','Job posting (URL)']);wb.save(tracker);wb.close()
    monkeypatch.setattr(engine,'load_service',lambda *a,**kw:SimpleNamespace(resume='Synthetic resume'))
    monkeypatch.setattr(engine,'SearchReviewer',lambda *a:None)
    monkeypatch.setattr(engine,'plan',lambda:[('title','query')])
    monkeypatch.setattr(discovery,'load_sources',lambda path:[{'platform':'greenhouse','board':'demo'}])
    def failed(*a): raise ValueError('HTTP 202')
    monkeypatch.setattr(engine,'web_search',failed)
    boards=[]
    def feed(platform,board,client):
        boards.append((platform,board))
        return [Posting('https://example.com/role','Example','Engineering Manager',location='Canada')]
    monkeypatch.setattr(engine,'ats_board',feed)
    monkeypatch.setattr(engine,'enrich',lambda p,c:p)
    monkeypatch.delenv('BRAVE_SEARCH_API_KEY',raising=False)
    outputs=engine._run_search(tmp_path,workbook=tracker,max_queries=1,progress=lambda x:None)
    private=tmp_path/'.job-search-assistant-private/search'
    assert ['title','query'] in json.loads((private/'pending-queries.json').read_text())
    assert boards==[('greenhouse','demo')]
    assert 'Search incomplete' in outputs[1].read_text()
    assert json.loads((private/'learned-boards.json').read_text())==[['greenhouse','demo']]
