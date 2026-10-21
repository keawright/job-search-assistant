"""Check the Git index before committing; never print secret values.

This is a conservative extra guard, not a comprehensive secret detector. It
reads staged blobs, so unstaged edits cannot hide something queued for commit.
"""

from pathlib import PurePosixPath
import re
import subprocess
import sys
from urllib.parse import urlsplit

PRIVATE_SUFFIXES = {".pdf", ".doc", ".docx", ".xlsx", ".xls", ".xlsm", ".xlsb", ".ods", ".csv", ".tsv", ".db", ".sqlite", ".sqlite3", ".pem", ".key", ".p12", ".pfx"}
PRIVATE_PARTS = {"archive", ".job-search-assistant-private", ".venv", "__pycache__", ".pytest_cache", ".ssh", ".aws", ".codex", ".agents", ".tools"}
PRIVATE_NAMES = {"task.md", "new_urls.txt", ".git-credentials", ".netrc", ".npmrc", ".pypirc", "credentials.json"}
PATTERNS = {
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----"),
    "GitHub token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
    "AWS access key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "API token": re.compile(r"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}\b"),
    "literal credential assignment": re.compile(r'''(?i)["']?\b(?:api[_-]?key|client[_-]?secret|password|access[_-]?token|refresh[_-]?token)["']?\s*[:=]\s*["'][^\s"']{8,}["']'''),
}


def check_blob(path: str, content: bytes, mode: str = "100644") -> list[str]:
    name = PurePosixPath(path.lower())
    problems = []
    if (name.suffix in PRIVATE_SUFFIXES or any(part in PRIVATE_PARTS or part.endswith(".egg-info") for part in name.parts)
            or name.name in PRIVATE_NAMES or name.name.startswith((".env", "id_rsa", "id_ed25519", "credentials.", "service-account"))
            or "data/private" in name.as_posix() or name.name.endswith("secrets.json")):
        problems.append("private data, spreadsheet, or credential file")
    if mode not in ("100644", "100755"):
        problems.append("symlinks and submodules require explicit publication review")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return problems + ["binary/non-UTF-8 file requires explicit publication review"]
    if "\x00" in text:
        problems.append("binary content requires explicit publication review")
    for label, pattern in PATTERNS.items():
        if pattern.search(text):
            problems.append(label)
    for url in re.findall(r"https?://[^\s<>\"']+", text):
        try:
            parts = urlsplit(url)
            # example.com is used solely for synthetic credential rejection tests.
            if (parts.username or parts.password) and parts.hostname != "example.com":
                problems.append("credential embedded in URL")
        except ValueError:
            continue
    return problems


def main():
    staged = subprocess.check_output(["git", "ls-files", "--stage", "-z"])
    count = 0
    failed = False
    for entry in staged.split(b"\0"):
        if not entry:
            continue
        metadata, path = entry.split(b"\t", 1)
        mode, object_id, stage = metadata.decode("ascii").split()
        filename = path.decode("utf-8")
        blob = subprocess.check_output(["git", "cat-file", "blob", object_id])
        issues = check_blob(filename, blob, mode)
        if stage != "0":
            issues.append("unresolved merge conflict")
        for issue in issues:
            print(f"BLOCKED: {filename}: {issue}")
        failed |= bool(issues)
        count += 1
    if not count:
        print("No tracked/staged files to check.")
        return 1
    if failed:
        return 1
    print(f"Checked {count} staged/tracked files: no prohibited files or recognized secret patterns found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
