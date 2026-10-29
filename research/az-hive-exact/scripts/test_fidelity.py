"""Meaningful failure checks for evidence verification and published aggregates."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import verify_source


class FidelityChecks(unittest.TestCase):
    def test_changed_csv_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "work/author/results/sample.csv"
            source.parent.mkdir(parents=True)
            data = b"1,20,30\n"
            lock = {"files": [{"path": "results/sample.csv", "git_blob_sha1":
                hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()}]}
            with patch.object(verify_source, "ROOT", root):
                source.write_bytes(data)
                verify_source.verify_worktree(lock)
                source.write_bytes(b"1,50,0\n")
                with self.assertRaisesRegex(RuntimeError, "Original extracted file differs"):
                    verify_source.verify_worktree(lock)

    def test_replaced_native_library_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            library = root / "work/author/beekeeper/c/build/libhive.so"
            library.parent.mkdir(parents=True)
            library.write_bytes(b"local binary")
            manifest = {"author_commit": "original", "library_sha256":
                        hashlib.sha256(library.read_bytes()).hexdigest()}
            (root / "work/build.json").write_text(json.dumps(manifest))
            with patch.object(verify_source, "ROOT", root):
                verify_source.verify_build({"commit": "original"})
                library.write_bytes(b"replaced")
                with self.assertRaisesRegex(RuntimeError, "Native library hash"):
                    verify_source.verify_build({"commit": "original"})

    def test_all_pinned_files_match_independent_github_tree(self):
        lock = verify_source.verify()
        tree = json.loads((verify_source.ROOT / "results/upstream-tree-2026-10-29.json").read_text())
        self.assertFalse(tree["truncated"])
        upstream = {e["path"]: e["sha"] for e in tree["tree"] if e["type"] == "blob"}
        pinned = {e["path"]: e["git_blob_sha1"] for e in lock["files"]}
        self.assertEqual(pinned, upstream)

    def test_published_aggregation_matches_author_plot_logic(self):
        import numpy as np
        import reanalyse_published_data
        with patch("builtins.print"):
            reanalyse_published_data.main()
        root = verify_source.ROOT
        report = json.loads((root / "results/published-data-audit.json").read_text())
        # Use the author's function bodies, without their unused matplotlib dependency.
        import ast
        source = ast.parse((root / "work/author/results/plots.py").read_text())
        functions = [node for node in source.body if isinstance(node, ast.FunctionDef)
                     and node.name in {"read_csv", "csv_to_winrates", "csvs_to_winrates"}]
        import csv
        namespace = dict(np=np, csv=csv, NUM_FILES=5, print=lambda *a: None)
        exec(compile(ast.Module(body=functions, type_ignores=[]), "author_plots", "exec"), namespace)
        for config, points in report["figures_4_5"].items():
            _, expected = namespace["csvs_to_winrates"](str(root / "work/author/results" / config))
            self.assertEqual([p["mean_win_rate"] for p in points], expected.tolist())

    def test_full_run_export_rejects_shortened_budget_and_false_completion(self):
        from export_run import inspect_run
        import export_run
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "work/author/results/config/1"
            config.mkdir(parents=True)
            training = dict(numIters=20, numEps=100, checkpoint="temp", results="results")
            network = dict(epochs=10, batch_size=64, results="results", cuda=True)
            (config / "training-parameters.json").write_text(json.dumps(training))
            (config / "nn-parameters.json").write_text(json.dumps(network))
            run = root / "run"
            run.mkdir()
            metadata = dict(published_config="config/1", status="running_original_coach",
                author_commit="original", algorithm_source_edits=[], published_training=training,
                published_network=network, effective_training=training.copy(), effective_network=network.copy())
            def save():
                (run / "run.json").write_text(json.dumps(metadata))
            save()
            with patch.object(export_run, "ROOT", root), patch.object(export_run, "verify_worktree", return_value={"commit": "original"}):
                self.assertEqual(inspect_run(run)["status"], "incomplete")
                metadata["effective_training"]["numEps"] = 1
                save()
                with self.assertRaisesRegex(RuntimeError, "budget/hyperparameters"):
                    inspect_run(run)
                metadata["effective_training"] = training.copy()
                metadata["status"] = "completed"
                save()
                with self.assertRaisesRegex(RuntimeError, "claims completion"):
                    inspect_run(run)


if __name__ == "__main__":
    unittest.main()
