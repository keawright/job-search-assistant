"""Bounded public-URL fetching and conservative JobPosting extraction."""

from dataclasses import dataclass
from datetime import date
import http.client
import ipaddress
import json
import socket
import ssl
import time
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from .models import Location


class FetchError(ValueError):
    """A URL could not safely yield a readable job posting."""


def normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    if parts.scheme.lower() not in ("http", "https") or not parts.hostname or parts.username or parts.password:
        raise ValueError("Posting URL must be HTTP(S) with a hostname and no credentials")
    if parts.port not in (None, 80, 443):
        raise ValueError("Only standard HTTP/HTTPS ports are supported")
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k.lower() not in ("fbclid", "gclid")]
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), urlencode(sorted(query)), ""))


@dataclass(frozen=True)
class Page:
    url: str
    html: str


def _public_addresses(host: str, port: int) -> list[str]:
    addresses = list(dict.fromkeys(result[4][0] for result in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)))
    if not addresses or any(not ipaddress.ip_address(address).is_global or ipaddress.ip_address(address).is_multicast for address in addresses):
        raise FetchError("URL resolves to a non-public address")
    return addresses


class _PinnedHTTP(http.client.HTTPConnection):
    def connect(self):
        self.sock = socket.create_connection((self._public_ip, self.port), self.timeout)


class _PinnedHTTPS(http.client.HTTPSConnection):
    def connect(self):
        sock = socket.create_connection((self._public_ip, self.port), self.timeout)
        try:
            self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
        except Exception:
            sock.close()
            raise


def fetch_page(url: str, *, timeout: float = 20, max_bytes: int = 2_000_000) -> Page:
    """Validate every redirect and pin the connection to a checked public IP.

    HTTPS retains hostname certificate validation. No cookies, authentication,
    proxy environment variables, browser automation, or decompression are used.
    """
    started = time.monotonic()
    current = url.strip()
    try:
        for _ in range(6):
            normalize_url(current)
            parts = urlsplit(current)
            port = parts.port or (443 if parts.scheme.lower() == "https" else 80)
            addresses = _public_addresses(parts.hostname, port)
            remaining = timeout - (time.monotonic() - started)
            if remaining <= 0:
                raise FetchError("Fetch time budget exceeded")
            if parts.scheme.lower() == "https":
                conn = _PinnedHTTPS(parts.hostname, port, timeout=remaining, context=ssl.create_default_context())
            else:
                conn = _PinnedHTTP(parts.hostname, port, timeout=remaining)
            conn._public_ip = addresses[0]
            try:
                target = urlunsplit(("", "", parts.path or "/", parts.query, ""))
                conn.request("GET", target, headers={"User-Agent": "JobSearchAssistant/0.2", "Accept": "text/html,application/xhtml+xml", "Accept-Encoding": "identity"})
                response = conn.getresponse()
                if response.status in (301, 302, 303, 307, 308):
                    location = response.getheader("Location")
                    if not location:
                        raise FetchError("Redirect has no destination")
                    destination = urljoin(current, location)
                    if parts.scheme.lower() == "https" and urlsplit(destination).scheme.lower() != "https":
                        raise FetchError("Refused HTTPS downgrade redirect")
                    current = destination
                    continue
                if response.status != 200:
                    raise FetchError(f"HTTP {response.status}; availability remains unverified")
                content_type = response.getheader("Content-Type", "").split(";", 1)[0].strip().lower()
                if content_type not in ("text/html", "application/xhtml+xml"):
                    raise FetchError("Expected an HTML page")
                if response.getheader("Content-Encoding", "identity").lower() != "identity":
                    raise FetchError("Compressed responses are not supported")
                length = response.getheader("Content-Length")
                if length and int(length) > max_bytes:
                    raise FetchError("Page exceeds the response-size limit")
                body = bytearray()
                while True:
                    remaining = timeout - (time.monotonic() - started)
                    if remaining <= 0:
                        raise FetchError("Fetch time budget exceeded")
                    if conn.sock:
                        conn.sock.settimeout(remaining)
                    chunk = response.read1(min(65536, max_bytes + 1 - len(body)))
                    if not chunk:
                        break
                    body.extend(chunk)
                    if len(body) > max_bytes:
                        raise FetchError("Page exceeds the response-size limit")
                # Let the HTML parser detect charset declarations where possible.
                encoding = response.headers.get_content_charset() or "utf-8"
                return Page(current, bytes(body).decode(encoding, errors="replace"))
            finally:
                conn.close()
        raise FetchError("Too many redirects")
    except (OSError, http.client.HTTPException, UnicodeError, LookupError, ValueError) as exc:
        if isinstance(exc, FetchError):
            raise
        raise FetchError(str(exc)) from exc


@dataclass(frozen=True)
class ExtractedPosting:
    company: str | None
    title: str | None
    description: str | None
    posting_date: date | None
    deadline: date | None
    location: Location
    flags: tuple[str, ...]


def _date(value):
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _text(value):
    return BeautifulSoup(value, "html.parser").get_text(" ", strip=True) if isinstance(value, str) else None


def _postings(value):
    if isinstance(value, list):
        for item in value:
            yield from _postings(item)
    elif isinstance(value, dict):
        types = value.get("@type", [])
        types = [types] if isinstance(types, str) else types
        types = types if isinstance(types, list) else []
        if "JobPosting" in types:
            yield value
        else:
            for child in value.values():
                if isinstance(child, (dict, list)):
                    yield from _postings(child)


def extract_posting(html: str) -> ExtractedPosting:
    soup = BeautifulSoup(html, "html.parser")
    postings, flags = [], []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            postings.extend(_postings(json.loads(script.get_text())))
        except (ValueError, TypeError):
            flags.append("Invalid structured metadata ignored.")
    # Some sites repeat identical schema blocks in the head and body.
    postings = list({json.dumps(p, sort_keys=True): p for p in postings}.values())
    if len(postings) > 1:
        return ExtractedPosting(None, None, None, None, None, Location(), ("Multiple JobPosting records: choose a single posting URL.",))
    if not postings:
        for element in soup(["script", "style", "nav", "header", "footer", "noscript"]):
            element.decompose()
        main = soup.find("main") or soup.find("article")
        text = main.get_text(" ", strip=True) if main else None
        title = soup.title.get_text(" ", strip=True) if soup.title else None
        return ExtractedPosting(None, title, text, None, None, Location(), tuple(flags) + ("No JobPosting metadata; fallback page text requires review and may be a login or careers page.",))
    data = postings[0]
    organization = data.get("hiringOrganization", {})
    company = _text(organization.get("name")) if isinstance(organization, dict) else None
    location = Location()
    if str(data.get("jobLocationType", "")).upper() == "TELECOMMUTE":
        requirements = data.get("applicantLocationRequirements")
        countries = []
        if requirements:
            for item in requirements if isinstance(requirements, list) else [requirements]:
                if isinstance(item, dict) and item.get("@type") == "Country" and isinstance(item.get("name"), str):
                    country = item["name"].strip()
                    countries.append({"ca": "Canada", "canada": "Canada", "us": "United States", "usa": "United States"}.get(country.casefold(), country))
        location = Location(arrangement="remote", allowed_remote_countries=tuple(countries) if countries else None,
                            evidence=json.dumps({k: data[k] for k in ("jobLocationType", "applicantLocationRequirements") if k in data}, ensure_ascii=False))
    elif data.get("jobLocation"):
        flags.append("Structured job location is present but required office attendance needs review.")
    for key in ("datePosted", "validThrough"):
        if data.get(key) and _date(data[key]) is None:
            flags.append(f"Unrecognized {key}; kept unknown.")
    if not _text(data.get("description")):
        flags.append("Structured description is missing; add posting text for assessment.")
    flags.append("Source authority and current vacancy availability need verification; readable HTML does not confirm an open role.")
    return ExtractedPosting(company, _text(data.get("title")), _text(data.get("description")), _date(data.get("datePosted")), _date(data.get("validThrough")), location, tuple(flags))
