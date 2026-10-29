"""Private PDF description fallback; never establishes current vacancy status."""

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

from .ingestion import normalize_url


def extract_pdf(path):
    """Prefer selectable text; image exports use local Windows OCR when available."""
    text = ""
    try:
        from pypdf import PdfReader
    except ImportError:
        pass
    else:
        reader = PdfReader(path)
        if len(reader.pages) > 40:
            raise ValueError("PDF exceeds the 40-page limit")
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    if len(text.strip()) >= 100:
        return text, "PDF text"
    executable = shutil.which("pdftotext")
    if not executable and os.name == "nt":
        candidate = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Git/mingw64/bin/pdftotext.exe"
        if candidate.is_file():
            executable = str(candidate)
    if executable:
        result = subprocess.run([executable, "-layout", str(path), "-"], capture_output=True, timeout=60, check=True)
        text = result.stdout.decode("utf-8", "replace")
        if len(text.strip()) >= 100:
            return text, "PDF text"
    if os.name != "nt":
        raise ValueError("No readable PDF text; install pypdf or supply a searchable PDF (image OCR requires Windows)")
    script = Path(__file__).with_name("pdf_ocr.ps1").read_text(encoding="utf-8")
    result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                            env={**os.environ, "JSA_PDF_PATH": str(path.resolve())},
                            capture_output=True, timeout=180, check=True)
    text = result.stdout.decode("utf-8-sig", "replace")
    if len(text.strip()) < 100:
        raise ValueError("PDF contains insufficient readable text after OCR")
    return text, "Windows OCR"


def _words(value):
    return re.findall(r"[a-z0-9]+", str(value).casefold())


@dataclass(frozen=True)
class Document:
    path: Path
    sha256: str
    text: str
    method: str


class LocalDescriptions:
    def __init__(self, root, jobs, *, reader=extract_pdf, progress=None):
        self.root = Path(root)
        self.jobs = jobs
        self.reader = reader
        self.progress = progress
        self._documents = None
        self.errors = []

    def documents(self):
        if self._documents is not None:
            return self._documents
        self._documents = []
        cache = self.root / ".job-search-assistant-private" / "jd-text"
        for path in sorted((self.root / "JDs").glob("*")):
            if path.suffix.casefold() != ".pdf" or not path.is_file():
                continue
            try:
                if path.stat().st_size > 30_000_000:
                    raise ValueError("PDF exceeds the 30 MB limit")
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                target = cache / f"{digest}.json"
                if target.exists():
                    saved = json.loads(target.read_text(encoding="utf-8"))
                    text, method = saved["text"], saved["method"]
                else:
                    if self.progress:
                        self.progress(f"Reading local job description: {path.name}")
                    text, method = self.reader(path)
                    cache.mkdir(parents=True, exist_ok=True)
                    target.write_text(json.dumps({"text": text, "method": method}, ensure_ascii=False), encoding="utf-8")
                if len(text.strip()) < 100:
                    raise ValueError("PDF contains insufficient role text")
                self._documents.append(Document(path, digest, text, method))
            except (OSError, ValueError, KeyError, subprocess.SubprocessError):
                self.errors.append(f"Could not read local PDF {path.name}; check PDF text/OCR availability.")
        return self._documents

    @staticmethod
    def matches(document, job):
        # URL identity beats filename guesses. Do not match company names alone.
        urls = re.findall(r"https?://[^\s<>]+", document.text)
        for url in urls:
            try:
                if normalize_url(url.rstrip('.,)')) == normalize_url(job.url):
                    return True
            except ValueError:
                pass
        heading = " ".join(_words(document.text[:3000]))
        company = " ".join(_words(job.company))
        title = " ".join(_words(job.title))
        # Exact normalized company and title in the opening section, not similar jobs.
        return (len(company) >= 3 and company not in ("unknown company", "unknown", "company")
                and len(title) >= 8 and title != "needs posting review"
                and f" {company} " in f" {heading} " and f" {title} " in f" {heading} ")

    def find(self, job):
        documents = self.documents()
        mapping_path = self.root / "JDs" / "matches.json"
        try:
            mappings = json.loads(mapping_path.read_text(encoding="utf-8-sig")) if mapping_path.exists() else {}
            if not isinstance(mappings, dict):
                raise ValueError("Invalid mapping")
            explicit = []
            for doc in documents:
                entry = mappings.get(doc.path.name)
                if entry is not None and normalize_url(entry["url"]) == normalize_url(job.url):
                    if entry["sha256"] != doc.sha256:
                        return None, [f"Mapped PDF {doc.path.name} changed; review its job identity and update matches.json."]
                    explicit.append(doc)
        except (OSError, ValueError, TypeError, KeyError):
            return None, ["Invalid JDs/matches.json; fix the explicit PDF-to-posting mappings before assessment."]
        matches = explicit or [doc for doc in documents if doc.path.name not in mappings and self.matches(doc, job)]
        # Multiple identical exports are harmless; different descriptions are ambiguous.
        matches = list({doc.sha256: doc for doc in matches}.values())
        if not matches:
            return None, list(self.errors) + (["No matching local PDF description verified in JDs; check employer/title or add a reviewed matches.json entry."] if documents else [])
        if len(matches) != 1:
            return None, ["Multiple local PDFs match this job; remove superseded exports or clarify the posting identity."]
        doc = matches[0]
        peers = {other.id for other in self.jobs if self.matches(doc, other)} if not explicit else {job.id}
        if len(peers) > 1:
            return None, [f"Local PDF {doc.path.name} matches multiple tracked jobs; posting identity needs review."]
        return doc, []
