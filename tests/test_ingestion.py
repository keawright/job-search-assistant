from datetime import date
from email.message import Message
import json

import pytest

from job_search_assistant import ingestion
from job_search_assistant.ingestion import FetchError, extract_posting, fetch_page, normalize_url


def page(data):
    return '<html><script type="application/ld+json">' + json.dumps(data) + '</script></html>'


def test_schema_graph_extracts_only_explicit_facts():
    result = extract_posting(page({"@graph": [{"@type": "Organization"}, {"@type": "JobPosting", "title": "Engineering Manager",
         "hiringOrganization": {"name": "Example"}, "description": "<p>Lead <b>teams</b>.</p>", "datePosted": "2026-10-01",
         "validThrough": "2026-10-25T23:59:00-03:00", "jobLocationType": "TELECOMMUTE",
         "applicantLocationRequirements": {"@type": "Country", "name": "CA"}}]}))
    assert result.company == "Example"
    assert result.title == "Engineering Manager"
    assert result.description == "Lead teams ."
    assert result.posting_date == date(2026, 10, 1)
    assert result.deadline == date(2026, 10, 25)
    assert result.location.allowed_remote_countries == ("Canada",)


def test_remote_without_country_remains_unknown():
    result = extract_posting(page({"@type": "JobPosting", "jobLocationType": "TELECOMMUTE"}))
    assert result.location.allowed_remote_countries is None
    assert result.posting_date is None


def test_office_address_not_assumed_mandatory_attendance():
    result = extract_posting(page({"@type": "JobPosting", "jobLocation": {"address": {"addressLocality": "Toronto"}}}))
    assert result.location.arrangement == "unknown"


def test_multiple_jobs_not_silently_selected():
    result = extract_posting(page([{"@type": "JobPosting", "title": "One"}, {"@type": "JobPosting", "title": "Two"}]))
    assert result.title is None
    assert "Multiple" in result.flags[0]


def test_fallback_excludes_scripts_and_flags_review():
    result = extract_posting('<title>Role</title><nav>Menu</nav><main>Lead a team<script>secret()</script></main>')
    assert result.description == "Lead a team"
    assert result.company is None
    assert "fallback" in result.flags[0]


def test_bad_metadata_dates_and_types_do_not_become_facts():
    result = extract_posting(page({"@type": "JobPosting", "datePosted": "last week", "validThrough": "soon"}))
    assert result.posting_date is None and result.deadline is None
    assert len([f for f in result.flags if "Unrecognized" in f]) == 2
    assert extract_posting(page({"@type": 42})).company is None


def test_normalization_preserves_job_ids_removes_tracking():
    assert normalize_url("https://EXAMPLE.com/job/?id=123&utm_source=mail#top") == "https://example.com/job?id=123"
    assert normalize_url("https://example.com/job?id=123") != normalize_url("https://example.com/job?id=456")


@pytest.mark.parametrize("url", ["file:///secret", "https://user:password@example.com", "ftp://example.com/job", "http://example.com:8080/job"])
def test_unsafe_url_syntax_rejected(url):
    with pytest.raises(ValueError):
        normalize_url(url)


@pytest.mark.parametrize("address", ["127.0.0.1", "10.0.0.1", "169.254.169.254", "::1", "224.0.0.1"])
def test_private_and_multicast_destinations_blocked(monkeypatch, address):
    monkeypatch.setattr(ingestion.socket, "getaddrinfo", lambda *a, **k: [(None, None, None, None, (address, 80))])
    with pytest.raises(FetchError, match="non-public"):
        fetch_page("http://example.com/job")


class Response:
    def __init__(self, status=200, body=b"<main>Job</main>", **headers):
        self.status, self.body = status, body
        self.headers = Message()
        self.headers["Content-Type"] = "text/html; charset=utf-8"
        for key, value in headers.items():
            self.headers[key.replace("_", "-")] = value

    def getheader(self, key, default=None):
        return self.headers.get(key, default)

    def read1(self, size):
        chunk, self.body = self.body[:size], self.body[size:]
        return chunk


def connection_mock(monkeypatch, responses):
    connections = []
    class Connection:
        sock = None
        def __init__(self, *args, **kwargs):
            self.response = responses[len(connections)]
            self.closed = False
            connections.append(self)
        def request(self, *args, **kwargs):
            self.request_args = (args, kwargs)
        def getresponse(self):
            return self.response
        def close(self):
            self.closed = True
    monkeypatch.setattr(ingestion, "_PinnedHTTP", Connection)
    monkeypatch.setattr(ingestion, "_PinnedHTTPS", Connection)
    monkeypatch.setattr(ingestion.socket, "getaddrinfo", lambda host, *a, **k: [(None, None, None, None, ("127.0.0.1" if host == "localhost" else "93.184.216.34", 80))])
    return connections


def test_redirect_revalidates_destination_before_connect(monkeypatch):
    connections = connection_mock(monkeypatch, [Response(302, Location="http://localhost/secret")])
    with pytest.raises(FetchError, match="non-public"):
        fetch_page("http://example.com/job")
    assert len(connections) == 1 and connections[0].closed
    assert connections[0]._public_ip == "93.184.216.34"


def test_https_downgrade_redirect_rejected(monkeypatch):
    connection_mock(monkeypatch, [Response(302, Location="http://example.com/job")])
    with pytest.raises(FetchError, match="downgrade"):
        fetch_page("https://example.com/job")


@pytest.mark.parametrize("response,limit,message", [(Response(403), 100, "HTTP 403"), (Response(body=b"x"*101), 100, "size limit"),
    (Response(Content_Length="1000"), 100, "size limit"), (Response(Content_Encoding="gzip"), 100, "Compressed")])
def test_fetch_failures_bounded_and_explicit(monkeypatch, response, limit, message):
    connection_mock(monkeypatch, [response])
    with pytest.raises(FetchError, match=message):
        fetch_page("https://example.com/job", max_bytes=limit)


def test_success_records_resolved_url(monkeypatch):
    connection_mock(monkeypatch, [Response(302, Location="/resolved"), Response()])
    assert fetch_page("https://example.com/job").url == "https://example.com/resolved"
