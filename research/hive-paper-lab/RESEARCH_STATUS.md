# Hypothesis overlap check — 2026-10-29

The broad representation/order-sensitivity idea is already studied and cannot
serve as a novelty claim by itself. This targeted overlap check does not prove
that every possible Hive experiment has appeared previously.

| Candidate | Primary source examined | Decision |
| --- | --- | --- |
| H1: Information-preserving input order changes reasoning | [Premise Order Matters in Reasoning with Large Language Models](https://arxiv.org/abs/2402.08939v3), ICML 2024, studies reordered premises preserving the underlying task | Broad claim overlaps prior work |
| H1: Invariance to input permutations | [Set-LLM](https://arxiv.org/abs/2505.15433v1), 2025, proposes an architecture with a permutation-invariance proof | Invariance itself is not new |
| H1/H2: Equivalent board representations change performance | [Representation-Aligned Auxiliary Supervision for Language Model Adaptation](https://arxiv.org/abs/2610.04098v2), updated October 24, 2026, compares FEN/ASCII chess inputs and environment-derived tasks | Close overlap; switching to Hive does not establish novelty |
| H2: Compact state improves accuracy per token | Local screen checks lossless serialization and byte counts only | Unsupported until token/held-out accuracy results exist |
| H3: History compensates for missing metadata | No complete/incomplete-state × history/no-history experiment completed | Undone |
| H4: Search keys omit the clock | Reproducible synthetic clock intervention changes terminal status while preserving author key | Diagnostic only; reachable equal-board/different-clock pair and learning benefit unestablished |

The October 29 screen repeats all 48 trajectories, 974 state snapshots, 147
tactical cases, 5,844 rotation checks, 974 reflections and 974 codec round trips.
It concerns the author's modified rules, not standard Hive.

No LLM response dataset was produced in the existing pilot. `evaluate.py` is
preserved as unfinished development code, not completed evaluation. Exact case
counts, safe resume identity checks, option-order controls, held-out episodes,
confidence intervals and multiple model families remain necessary. Byte savings
do not establish token savings or reasoning gains.

A new contribution needs a narrower mechanism, independent paired held-out
evidence and explicit comparison against these approaches. The repository does
not currently establish a publication-ready theory or verified novelty.
