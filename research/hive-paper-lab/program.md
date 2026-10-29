# Autoresearch: a falsifiable paper hypothesis using Hive

## Objective

Find a defensible new research question, preferably using Hive, including LLM
evaluation where useful. Produce executable probes, preserved raw evidence,
rejected hypotheses and a concrete next experimental protocol. Publication and
novelty are not established by this screening cycle.

## Fixed baseline

- Author implementation: `17e45e6b27db7591f64f11f2af83c3b59c3c126b`.
- Verify archive SHA256 and all 647 Git blobs before collecting data.
- Mac arm64, existing compiled author C library; no source edits or training.
- Seeds: 20261022, 20261023, 20261024. Fixed trajectory budget per seed.
- Existing full training remains stopped. No native library optimization.
- TP3-specific `program_autoresearch.md`, Make targets and sanitizer workflow are
  absent here. Use source verification, legal trajectory replay, independent
  geometric invariants and codec round trips as applicable correctness gates.
  A crash, inconsistent native oracle, or failed invariant blocks conclusions
  from the affected experiment.

## Screening loop

1. Generate legal native-game trajectories and collect logical state snapshots.
2. Probe state information loss and missing turn information. Counterfactual clock
   changes must be labelled synthetic unless independently replayable.
3. Compare full-state representations with lossless round-trip checks. Measure
   bytes and actual LLM token counts separately; file compression is not model
   reasoning improvement.
4. Build paired LLM questions with engine-checkable answers. Vary one factor at a
   time: rotation, piece-list order, irrelevant identifiers, or serialization.
5. Run a bounded local open-model inference pilot if the runtime is available.
   Freeze the model, prompts and decoding; retain every response. Keep paired
   tasks grouped by source state. The pilot is development data, not a held-out
   confirmation set or evidence about all LLMs.
6. Rank hypotheses against primary related work. Keep only experimentally
   validated artifacts; record inconclusive and rejected ideas explicitly.

## Candidate questions and falsification

- H1: Representation transformations change LLM accuracy/consistency despite
  preserving task-relevant information. Reject if paired effects are negligible
  on adequately powered held-out tests; consistency alone is not correctness.
- H2: Lossless compact state serialization improves accuracy per input token.
  Reject if it only reduces bytes or shifts syntax without improved held-out
  token/accuracy tradeoffs. Do not put oracle answers into the representation.
- H3: Apparent benefits of history partly compensate for missing state metadata.
  Require history/no-history × complete/incomplete-state controls before claims.
- H4: A time-aware search key avoids distinct-clock cache collisions. A diagnostic
  can support correctness only; Elo/learning benefit needs new experiments.
- H5: A new GNN/Transformer for Hive is novel on its own. Reject this novelty
  claim: related Hive GNN implementations and board-game Transformers exist.

## Publication gate

Primary-source novelty review; engine/oracle validation; independent held-out
seeds, grouped confidence intervals, multiple model families and sizes; controls
for option order, token budget and trivial baselines; full costs and limitations.
No stopping or choosing hypotheses based on a desired publication outcome.
