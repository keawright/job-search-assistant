import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("repository_guard", Path(__file__).resolve().parents[1] / "tools/check_repository.py")
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


@pytest.mark.parametrize("path", ["TASK.md", "resume.pdf", "resume.docx", "jobs.XLSX", "archive/old.xlsx", ".env", ".env.production", "data/private/profile.json", "credentials.json", ".ssh/id_ed25519", "new_urls.txt"])
def test_private_files_blocked_even_if_force_added(path):
    assert guard.check_blob(path, b"private data")


@pytest.mark.parametrize("content", [
    "gh" + "p_" + "A" * 36,
    "AK" + "IA" + "A" * 16,
    "-----BEGIN " + "PRIVATE KEY-----",
    "api_key = '" + "a" * 32 + "'",
    "https://user:" + "sensitive" + "@production.invalid",
])
def test_credentials_detected_without_echoing_values(content):
    assert guard.check_blob("src/config.py", content.encode())


def test_synthetic_sources_allowed():
    assert not guard.check_blob("examples/preferences.json", b'{"country":"Canada"}')
    assert not guard.check_blob("tests/test_example.py", b'url = "https://user:password@example.com"')


def test_binary_and_symlink_rejected():
    assert guard.check_blob("attachment.bin", b"\xff\x00")
    assert guard.check_blob("link", b"../private", "120000")
