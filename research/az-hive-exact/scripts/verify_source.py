"""Check the pinned archive and every original Git blob, including experiment data."""
import hashlib
import json
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def verify():
    lock = json.loads((ROOT / "upstream/author.lock.json").read_text())
    archive = ROOT / "upstream" / lock["archive"]
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == lock["sha256"], "Archive hash mismatch"
    with tarfile.open(archive) as source:
        blobs = {}
        for member in source.getmembers():
            if member.isfile():
                name = member.name.partition("/")[2]
                data = source.extractfile(member).read()
                blobs[name] = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        expected = {entry["path"]: entry["git_blob_sha1"] for entry in lock["files"]}
        assert blobs == expected, "Original Git tree differs from archive"
    return lock


if __name__ == "__main__":
    lock = verify()
    print(f"Verified {len(lock['files'])} original files at {lock['commit']}")
