"""Keep a single current workbook; preserve older files byte for byte."""

import hashlib
from pathlib import Path
import shutil


def workbooks(directory: Path) -> list[Path]:
    return sorted(p for p in directory.iterdir() if p.is_file() and p.suffix.lower() == ".xlsx" and not p.name.startswith("~$"))


def current_workbook(directory: Path) -> Path:
    files = workbooks(directory)
    if len(files) != 1:
        raise ValueError("Expected one current .xlsx workbook in this folder; select the latest explicitly with --workbook")
    return files[0]


def fingerprint(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def archive_older_workbooks(latest: Path) -> list[Path]:
    """Archive only sibling workbooks, never directories or the current output.

    Exclusive destination creation avoids replacing an older archive. A verified
    byte-for-byte copy is made before the original file is removed. On failure,
    the current workbook remains available and no old data is overwritten.
    """
    latest = latest.resolve(strict=True)
    root = latest.parent.resolve(strict=True)
    archive = root / "archive"
    if archive.is_symlink() or archive.resolve().parent != root:
        raise ValueError("Archive directory must remain inside the project workbook folder")
    archive.mkdir(exist_ok=True)
    moved = []
    for source in workbooks(root):
        if source.resolve() == latest:
            continue
        if source.is_symlink() or source.resolve().parent != root:
            raise ValueError("Archive source must be a regular workbook in the current folder")
        before = fingerprint(source)
        destination = archive / source.name
        index = 1
        while True:
            try:
                handle = destination.open("xb")
                break
            except FileExistsError:
                destination = archive / f"{source.stem}-{index}{source.suffix}"
                index += 1
        try:
            with handle, source.open("rb") as stream:
                shutil.copyfileobj(stream, handle)
            if fingerprint(destination) != before or fingerprint(source) != before:
                raise OSError(f"Workbook changed during archiving: {source.name}; source retained")
            shutil.copystat(source, destination)
            source.unlink()
        except Exception:
            # Both copies remain on disk for recovery if a lock/change prevented
            # completing the move. Never remove the original on an error.
            raise
        moved.append(destination)
    return moved
