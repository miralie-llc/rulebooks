# Candidate Nim conformance slice

The [authored definition](../../data/definitions/nim-one-two/1.json) implements the exact [two-heap rulebook draft](../../data/catalog/records/RulebookEdition-nim-one-two-1.json): heaps `[1, 2]`, Player A first, visible counters, remove one or more from one heap, final removal wins. It uses the [experimental reference semantics](../architecture/reference-semantics.md). **Editorial and semantic acceptance remain pending.** No accepted Formalization, BGSMRelease or game VerificationRecord is claimed.

```sh
python3 -m tools.runtime.nim
python3 -m unittest discover -s tests -p 'test_nim.py' -v
npm run build
```

The static review page at `/tools/nim/` exposes the source, rule links, inspection artifact and actual verification report. All seven readable rule IDs have candidate source mappings. Setup, actor legality, heap/amount selection, list update, turn change and outcome are visible declarative operations; the reference engine contains no whole-game Nim primitive.

The independent oracle directly enumerates ordinary Nim moves and outcomes, without using the expression evaluator to derive expectations. Starting from `[1, 2]`, it checks all **8 reachable states**, **10 legal transitions**, **2 terminal states**, and **374 rejected actor/parameter combinations**. It compares exact legal-intent sets, deterministic resolutions, resulting states, public observations, terminal winners and nonmutation. Mutating setup, turn changes, winner assignment or rule coverage causes tests to fail.

These bounds do not cover the 3/4/5 profile, arbitrary heap counts, misère play, hidden information or competition procedures. State counts include distinct player-to-move and winner values; they are not counts of heap arrangements alone.

Candidate artifacts live under a digest-addressed `/data/candidates/nim/` directory and are identified as `draft-game-definition`. The report pins the exact rulebook digest, source digest, implementation build and independent suite identity. Draft candidate URLs are for review; retained published-release history begins with acceptance and the publication assembler.

Issue #10 stays open until accountable acceptance and publication through the existing contracts. Keeping this candidate pending review does not block readable rules, developer specimens, or independent contribution-workflow implementation. Approval must not be inferred from compilation or test success.
