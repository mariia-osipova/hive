"""Extract verified original sources and build the author's C library on this Mac."""
import hashlib
import json
import platform
import shutil
import subprocess
import tarfile
from pathlib import Path

from verify_source import ROOT, REBUILT_FILES, verify, verify_worktree


def main():
    lock = verify()
    author = ROOT / "work/author"
    author.mkdir(parents=True, exist_ok=True)
    with tarfile.open(ROOT / "upstream" / lock["archive"]) as archive:
        for member in archive.getmembers():
            if not member.isfile():
                continue
            relative = Path(member.name.partition("/")[2])
            if relative.is_absolute() or ".." in relative.parts:
                raise RuntimeError("Unsafe archive path")
            target = author / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            data = archive.extractfile(member).read()
            if not target.exists():
                target.write_bytes(data)
                target.chmod(member.mode & 0o777)
            elif str(relative) not in REBUILT_FILES and target.read_bytes() != data:
                raise RuntimeError(f"Original extracted file was modified: {relative}")
    verify_worktree(lock)
    candidates = sorted(Path("/opt/homebrew/bin").glob("gcc-[0-9]*"), reverse=True)
    compiler = next((p for p in candidates if p.name.removeprefix("gcc-").isdigit()), None)
    if compiler is None:
        raise RuntimeError("GNU GCC with OpenMP is required: brew install gcc")
    cdir = author / "beekeeper/c"
    sources = ["engine/board.c", "engine/list.c", "engine/moves.c", "engine/node.c", "engine/tt.c",
               "engine/utils.c", "mm/mm.c", "mm/evaluation.c", "mcts/mcts.c"]
    library = cdir / "build/libhive.so"
    library.parent.mkdir(exist_ok=True)
    command = [str(compiler), "-shared", "-fPIC", "-std=gnu99", "-O3", "-march=native", "-fopenmp",
               "-fcommon", "-fsigned-char", "-DCENTERED=1", "-I", "engine", *sources, "-lm", "-o", str(library)]
    subprocess.run(command, cwd=cdir, check=True)
    manifest = {"author_commit": lock["commit"], "platform": platform.platform(), "machine": platform.machine(),
                "compiler": subprocess.check_output([str(compiler), "--version"], text=True).splitlines()[0],
                "command": command, "library_sha256": hashlib.sha256(library.read_bytes()).hexdigest(),
                "compatibility_flags": {"-fcommon": "Old GCC global-definition behavior",
                                        "-fsigned-char": "Match Linux x86 default char signedness"}}
    (ROOT / "work/build.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
