"""Run unmodified author Coach and the published JSON parameters on the local CPU."""
import argparse
import hashlib
import importlib
import json
import logging
import os
import platform
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from verify_source import ROOT, verify


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="tile_relative/regular/spatial_planes_4/1")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20261022)
    parser.add_argument("--check-only", action="store_true", help="Original full-size inference; no training")
    cli = parser.parse_args()
    output = cli.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if (output / "run.json").exists():
        raise RuntimeError("Output already contains a run; use a new directory")
    lock = verify()
    author = ROOT / "work/author"
    for entry in lock["files"]:
        path = Path(entry["path"])
        if path.suffix in {".py", ".c", ".h", ".json"}:
            data = (author / path).read_bytes()
            digest = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
            if digest != entry["git_blob_sha1"]:
                raise RuntimeError(f"Original source/config differs: {path}")
    config = (author / "results" / cli.config).resolve()
    if not config.is_relative_to((author / "results").resolve()):
        raise RuntimeError("Config must select a published result directory")
    training = json.loads((config / "training-parameters.json").read_text())
    network = json.loads((config / "nn-parameters.json").read_text())
    os.chdir(author / "hive-engine")
    sys.path.insert(0, str(author / "hive-engine"))
    import coloredlogs
    import numpy as np
    import torch
    # NumPy <1.24 exposed np.str as the builtin str. Restore that exact alias for the old source.
    np.str = str
    coloredlogs.install(level="INFO")
    random.seed(cli.seed)
    np.random.seed(cli.seed)
    torch.manual_seed(cli.seed)
    # Match the original relative-library path and set configuration before MCTS imports its globals.
    hive = importlib.import_module("hive.HiveGame")
    absolute = cli.config.startswith("absolute_coord/")
    hive.ACTION_ENCODING = hive.ABSOLUTE_COORDINATE if absolute else hive.TILE_RELATIVE
    hive.ACTION_SPACE_SHAPE = (11, 26, 26) if absolute else (22, 7, 11)
    hive.ACTION_SPACE_SIZE = np.prod(hive.ACTION_SPACE_SHAPE)
    hive.USE_SYMMETRIES = "symmetries" in config.parts
    nnet_module = importlib.import_module("hive.pytorch.NNet")
    effective_training = dict(training, results=str(output), checkpoint=str(output / "checkpoints"))
    effective_network = dict(network, cuda=False, results=str(output))
    nnet_module.args.update(effective_network)
    from utils import dotdict
    game = hive.HiveGame()
    nnet = nnet_module.NNetWrapper(game)
    metadata = {"status": "initializing", "pid": os.getpid(), "started_utc": datetime.now(timezone.utc).isoformat(),
                "author_commit": lock["commit"], "published_config": cli.config, "seed": cli.seed,
                "original_seeds": "not published; this seed is a new local repetition", "platform": platform.platform(),
                "python": sys.version, "torch": torch.__version__, "numpy": np.__version__, "device": "cpu",
                "torch_threads": torch.get_num_threads(), "action_size": int(game.getActionSize()),
                "parameters": sum(p.numel() for p in nnet.nnet.parameters()),
                "use_symmetries": hive.USE_SYMMETRIES, "published_training": training, "published_network": network,
                "effective_training": effective_training, "effective_network": effective_network,
                "environment_differences": ["macOS arm64 CPU instead of Linux/NVIDIA CUDA", "modern Python/PyTorch/NumPy"],
                "compatibility_shims": {"numpy.str": "builtin str, as in the author's old NumPy"},
                "algorithm_source_edits": []}

    def save_status(status, **extra):
        metadata.update(status=status, **extra)
        (output / "run.json").write_text(json.dumps(metadata, indent=2) + "\n")

    if cli.check_only:
        save_status("inference_check")
        start = time.monotonic()
        board = game.getInitBoard()
        policy, value = nnet.predict(board[1])
        if len(policy) != game.getActionSize() or not np.all(np.isfinite(policy)) or not np.all(np.isfinite(value)):
            raise RuntimeError("Original network produced invalid outputs")
        print(json.dumps({"parameters": metadata["parameters"], "device": "cpu", "policy_sum": float(policy.sum()),
                          "value": float(value[0]), "inference_seconds": time.monotonic() - start}), flush=True)
        save_status("inference_check_passed")
        return
    from Coach import Coach
    coach = Coach(game, nnet, dotdict(effective_training))
    nnet.save_checkpoint(folder=str(output), filename="initial.pth.tar")
    (output / "training-parameters.json").write_text(json.dumps(effective_training, indent=2) + "\n")
    (output / "nn-parameters.json").write_text(json.dumps(effective_network, indent=2) + "\n")
    save_status("running_original_coach")
    logging.info("Original Coach: full published configuration %s, %d parameters", cli.config, metadata["parameters"])
    try:
        coach.learn()
    except BaseException as error:
        save_status("failed", error=repr(error))
        raise
    nnet.save_checkpoint(folder=str(output), filename="final.pth.tar")
    save_status("completed", completed_utc=datetime.now(timezone.utc).isoformat())


if __name__ == "__main__":
    main()
