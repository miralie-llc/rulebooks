# Synthetic game-knowledge examples

These are contract examples, not collected rules, source endorsements, real reviews or executable games. All drafts, reviews, public Source fixtures and projected editions carry `testOnly: true`. The teaching sheets and observation transcripts are original synthetic test artifacts. Their acquisition manifests are schema examples; the real intake importer intentionally refuses source files inside Git.

Each game folder contains `draft.json`, `review.json` and `expected-edition.json`. Source-file examples additionally have `*.handoff.json` and `artifacts/`; chess has a fictional `*.source.json` publication record. The [producer guide](../../../docs/development/game-knowledge-producer.md) explains the input; the [architecture guide](../../../docs/architecture/draft-game-knowledge.md) explains review and trace retention.

| Game | Draft → review → public rules | Preserved privately |
|---|---|---|
| Chess | `white-first` and `king-safety` accepted into identically named public rules; `rook-frozen` rejected | Invented playthrough observation, conflicting teaching-sheet evidence, rejected inference rationale, resolved conflict and deferred missing-special-moves question |
| Nim | Eight original rules accepted; current player/heap/remove-action inventory links conditions and effects to those rules | Original-definition attribution, producer run, exact statements and review decisions; no invented downloaded source |
| Rock-paper-scissors | Nine one-round definition rules accepted; `repeat-ties` rejected | Invented replay observation, conflicting original tie policy, explanation for rejection and deferred physical-conventions question |

Chess's two selected rules form an incomplete excerpt. Nim's complete reading status applies only to the explicit visible heaps `[1, 2]` configuration with A starting and last-counter victory. RPS remains partial because this draft still includes the rejected replay claim in its ending-topic inventory. A subsequent draft can remove the rejected candidate, pin this predecessor and obtain new review; the retained earlier trace preserves its provenance. No fixture claims complete formal coverage or execution.

The chess rule ID `rook-frozen` is intentionally **wrong**: it demonstrates why observing no rook moves after a king move cannot establish a permanent movement prohibition. It is never projected into the readable edition and is unrelated to implementing castling. The RPS replay observation is likewise insufficient to define the selected one-round tie policy. Do not use these rejected statements as training rules or game requirements.

The projector generates a private trace containing the complete draft, review, source records and handoff manifests. It is tested in memory instead of committing a redundant copy. Tests compare generated editions with the saved expected outputs, verify that traces regenerate them, and check source-file hashes against synthetic handoffs.

Validate the simplest draft:

```sh
python3 tools/validate_knowledge.py validate \
  --draft tests/fixtures/knowledge/nim-normal-play/draft.json \
  --allow-fixtures
```

Exercise a full projection with a new private directory outside any Git checkout:

```sh
python3 tools/validate_knowledge.py project \
  --draft tests/fixtures/knowledge/nim-normal-play/draft.json \
  --review tests/fixtures/knowledge/nim-normal-play/review.json \
  --output-dir "$NEW_PRIVATE_PROJECTION_DIRECTORY" \
  --allow-fixtures
```

The resulting edition retains `testOnly: true`. It cannot be used as real publication content. All three examples are checked by `tools/check_repository.py` and `tests/test_knowledge.py`; no network or private research store is required.
