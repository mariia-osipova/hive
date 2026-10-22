"""The pilot decision uses the fixed held-out pairs, including negative results."""
import importlib.util
from pathlib import Path

import pytest
import torch

path = Path(__file__).resolve().parents[2] / "scripts/report_pilot.py"
spec = importlib.util.spec_from_file_location("report_pilot", path)
reporting = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reporting)


def pair(first, second, wins):
    return {"first": first, "second": second, "result": {"matches": [
        {"match": i, "first_color": "white" if i % 2 == 0 else "black", "result": outcome}
        for i, outcome in enumerate(wins)]}}


def test_identical_models_do_not_satisfy_pilot_success_criterion():
    random_results = [1, -1] * 50
    report = {"games_per_pair": 100, "pairs": [
        pair("trained", "initial", [1, -1] * 50),
        pair("trained", "random", random_results),
        pair("initial", "random", random_results)]}
    summary = reporting.summarize_holdout(report)
    assert summary["random_win_rate_difference"] == {"estimate": 0.0, "ci95": [0.0, 0.0]}
    assert summary["trained_vs_initial"]["estimate"] == 0.5
    assert not summary["positive_signal_criterion_met"]


def test_strong_improvement_requires_both_fixed_comparisons():
    report = {"games_per_pair": 100, "pairs": [
        pair("trained", "initial", [1] * 80 + [-1] * 20),
        pair("trained", "random", [1] * 90 + [-1] * 10),
        pair("initial", "random", [1] * 40 + [-1] * 60)]}
    assert reporting.summarize_holdout(report)["positive_signal_criterion_met"]
    report["pairs"][0] = pair("trained", "initial", [-1] * 100)
    assert not reporting.summarize_holdout(report)["positive_signal_criterion_met"]


def test_incomplete_or_unbalanced_evaluation_is_rejected():
    report = {"games_per_pair": 100, "pairs": [
        pair("trained", "initial", [1] * 100),
        pair("trained", "random", [1] * 99),
        pair("initial", "random", [1] * 100)]}
    with pytest.raises(ValueError, match="complete and color balanced"):
        reporting.summarize_holdout(report)


def test_resource_units_and_model_state_fingerprints(tmp_path):
    path = tmp_path / "time.log"
    path.write_text("12.50 real 10.00 user 0.25 sys\n 104857600 maximum resident set size\n")
    resources = reporting.resource_measurements(path)
    assert resources["wall_seconds"] == 12.5
    assert resources["peak_process_rss_bytes"] == 104857600
    first = {"weight": torch.tensor([1.0]), "bn.num_batches_tracked": torch.tensor(2)}
    assert reporting.state_digest(first) == reporting.state_digest(dict(reversed(list(first.items()))))
    second = {**first, "bn.num_batches_tracked": torch.tensor(3)}
    assert reporting.state_digest(first) != reporting.state_digest(second)
