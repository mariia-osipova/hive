"""Check the pinned archive and every original Git blob, including experiment data."""
import hashlib
import json
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# The archive also ships a Linux binary; bootstrap replaces this one file on Mac.
REBUILT_FILES = {"beekeeper/c/build/libhive.so"}


def verify():
    lock = json.loads((ROOT / "upstream/author.lock.json").read_text())
    archive = ROOT / "upstream" / lock["archive"]
    if hashlib.sha256(archive.read_bytes()).hexdigest() != lock["sha256"]:
        raise RuntimeError("Archive hash mismatch")
    with tarfile.open(archive) as source:
        blobs = {}
        for member in source.getmembers():
            if member.isfile():
                name = member.name.partition("/")[2]
                data = source.extractfile(member).read()
                blobs[name] = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        expected = {entry["path"]: entry["git_blob_sha1"] for entry in lock["files"]}
        if blobs != expected:
            raise RuntimeError("Original Git tree differs from archive")
    return lock


def verify_worktree(lock=None):
    """Verify every extracted file except the explicitly rebuilt native binary."""
    lock = verify() if lock is None else lock
    author = ROOT / "work/author"
    for entry in lock["files"]:
        if entry["path"] in REBUILT_FILES:
            continue
        path = author / entry["path"]
        data = path.read_bytes()
        actual = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        if actual != entry["git_blob_sha1"]:
            raise RuntimeError(f"Original extracted file differs: {entry['path']}")
    return lock


def verify_build(lock=None):
    """Reject a stale/replaced native library before importing it with ctypes."""
    lock = verify_worktree() if lock is None else lock
    manifest = json.loads((ROOT / "work/build.json").read_text())
    library = ROOT / "work/author/beekeeper/c/build/libhive.so"
    if manifest["author_commit"] != lock["commit"]:
        raise RuntimeError("Native build targets a different author commit")
    if hashlib.sha256(library.read_bytes()).hexdigest() != manifest["library_sha256"]:
        raise RuntimeError("Native library hash differs from build manifest; bootstrap again")
    return manifest


if __name__ == "__main__":
    lock = verify()
    print(f"Verified {len(lock['files'])} original files at {lock['commit']}")
