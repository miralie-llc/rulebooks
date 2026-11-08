# Publication contract fixtures

These are **contract tests, not public game data**. No fixture completes a content task, creates a semantic gap, releases BGSM or supplies executable verification. They belong in tests and must be excluded from public catalog inputs.

- [first-games.json](first-games.json): chess with no formalization, complete-within-scope Nim coverage, and partial RPS coverage. These are the games from the actual content work list. Chess is explicitly an incomplete excerpt; Nim uses heaps `[1, 2]`; RPS is one round with ties ending the round.
- [publisher-editions.json](publisher-editions.json): fictional Orchard first and second editions are distinct Games in one family. The first edition has two RuleBooks revisions with unchanged rule text. No publisher-edition relationship is invented for chess, Nim or RPS.
- [sources/](sources/): plain-text placeholders that identify themselves as non-executable. Their bytes test package hashes and exported-name references, not compilation or game behavior.

The `0.0.0-fixture.1` model/language and all review actors, review decisions and commit placeholders are fictional. Each record has `testOnly: true`; the bundle has `purpose: contract-fixture`. The validator requires `--allow-fixtures`. There are no persisted VerificationRecords or BuildArtifacts in these examples; tests construct synthetic records for those contracts in memory.

The chess citations point to the [FIDE Laws effective 1 January 2023](https://handbook.fide.com/chapter/E012023). The short prose is an original paraphrase for contract illustration, not a complete transcription or reviewed rules guide. Source metadata grants no redistribution rights to source captures. Nim and RPS name their original editorial fixture origin explicitly and inherit it at rule level to avoid repetition.

Keep hand-edited fixtures readable. If intentionally changing their payloads, update review hashes and then manifest hashes using the documented encoding in [the contract guide](../../../docs/architecture/publication-contract.md). Hash updates are not real editorial approval. The `seal()` helper in the test module is only for mutation tests; it is not a production publishing tool.
