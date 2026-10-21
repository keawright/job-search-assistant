"""Bounded public search for alternatives to incomplete LinkedIn postings."""

from dataclasses import dataclass
import re
from urllib.parse import parse_qs, quote, urljoin, urlsplit

from bs4 import BeautifulSoup

from .ingestion import FetchError, extract_posting, normalize_url


@dataclass(frozen=True)
class Identity:
    company: str
    title: str
    location: str | None = None


def linkedin_identity(title: str) -> Identity | None:
    title = " ".join(title.split())
    match = re.fullmatch(r"(.+?) hiring (.+?) in (.+?) \| LinkedIn(?: Jobs)?", title)
    if match:
        return Identity(match[1], match[2], match[3])
    match = re.fullmatch(r"(.+?) at (.+?) [—–] (.+?) \| LinkedIn(?: Jobs)?", title)
    return Identity(match[2], match[1], match[3]) if match else None


def is_linkedin(url: str) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    return host == "linkedin.com" or host.endswith(".linkedin.com")


def search_postings(identity: Identity, fetcher) -> list[str]:
    """No API key; a blocked search yields a review issue in the caller."""
    query = f'"{identity.company}" "{identity.title}" {identity.location or ""} jobs -site:linkedin.com'
    page = fetcher("https://html.duckduckgo.com/html/?q=" + quote(query))
    soup = BeautifulSoup(page.html, "html.parser")
    urls = []
    for anchor in soup.select("a.result__a"):
        href = urljoin(page.url, anchor.get("href", ""))
        href = parse_qs(urlsplit(href).query).get("uddg", [href])[0]
        try:
            normalized = normalize_url(href)
        except ValueError:
            continue
        host = urlsplit(normalized).hostname or ""
        if is_linkedin(normalized) or host == "duckduckgo.com" or host.endswith(".duckduckgo.com"):
            continue
        if normalized not in urls:
            urls.append(normalized)
        if len(urls) == 3:
            break
    return urls


def _normalized(value: str) -> str:
    return " ".join(re.findall(r"\w+", value.casefold()))


def find_alternative(identity: Identity, fetcher, searcher=search_postings):
    """Require structured company/title agreement and visible location evidence.

    Search snippets alone never establish a match or closure. Multiple matching
    URLs are ambiguous, so leave them for human review.
    """
    matches = {}
    for url in searcher(identity, fetcher)[:3]:
        try:
            normalize_url(url)
            if is_linkedin(url):
                continue
            page = fetcher(url)
            if is_linkedin(page.url):
                continue
            posting = extract_posting(page.html)
            if (_normalized(posting.company or "") != _normalized(identity.company)
                    or _normalized(posting.title or "") != _normalized(identity.title)):
                continue
            if identity.location:
                soup = BeautifulSoup(page.html, "html.parser")
                for element in soup(["script", "style", "nav", "footer", "header"]):
                    element.decompose()
                # Every location component must occur; do not substitute a role
                # in another city simply because the company/title agree.
                text = " " + _normalized(soup.get_text(" ", strip=True)) + " "
                parts = [_normalized(part) for part in identity.location.split(",")]
                if any(" " + part + " " not in text for part in parts if part):
                    continue
            matches[normalize_url(page.url)] = page
        except (FetchError, ValueError):
            continue
    return next(iter(matches.values())) if len(matches) == 1 else None
