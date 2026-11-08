# Producing draft game knowledge for RuleBooks

**Contract 0.1.0.** Your tool should deliver a **`GameKnowledgeDraft`**, describing what it believes the rules are, why it believes them, and what remains uncertain. PDFs and extracted files are its evidence, not its primary knowledge output. The normative [JSON Schema](../../schema/knowledge/0.1.0/knowledge.schema.json) and [validator/projector](../../tools/validate_knowledge.py) implement this interface. The [architecture guide](../architecture/draft-game-knowledge.md) describes editorial review and preservation.

## What to give RuleBooks

For each game/profile, provide:

1. **`draft.json`**: one complete, versioned knowledge snapshot conforming to `GameKnowledgeDraft`.
2. **Evidence handoff manifests and their named files**, following the [artifact handoff contract](reference-handoff.md). Draft evidence references those exact artifacts. Original definitions use editorial attribution instead of invented downloads.
3. **The previous draft snapshot**, when updating an existing draft, so its predecessor digest and identity can be checked. Keep older evidence and drafts available.

This draft interface is optional. If your process already produces reviewed records, submit those directly through the [publication contract](../architecture/publication-contract.md), preserving the actual authorship, review and provenance. Your existing process can fulfill the editor role; RuleBooks does not require a duplicate editorial pass. When submitting an unreviewed draft, do not fabricate acceptance to satisfy a publication schema. You do not need to implement BGSM, produce GDL, operate the RuleBooks store, or finish all research before submitting a useful draft.

Keep actual drafts, review decisions, acquisition material and promotion traces in a restricted private workspace outside Git and outside the managed reference store. Source-control contains this contract and clearly marked synthetic fixtures only. No absolute physical storage location is part of the interface.

One possible collector layout is:

```text
collector-workspace/
  game/profile/
    acquisitions/
      document-001/
        originals/rules.pdf
        extracts/ocr.txt
        images/page-01.png
        handoff.json
    knowledge/
      research-id/1/draft.json
      research-id/2/draft.json
```

The hierarchy is your choice. An artifact's `path` is relative to its referenced handoff manifest, not relative to `draft.json`. The separate RuleBooks managed store remains excluded from collector scans.

## Required draft fields

| Field | Producer responsibility |
|---|---|
| `schemaVersion`, `kind` | Exactly `0.1.0` and `GameKnowledgeDraft` |
| `id`, `revision` | Stable research/profile ID and positive snapshot revision; start at 1 |
| `previous` | Required at revision 2+: prior draft ID, revision and canonical JSON digest |
| `game` | Candidate game ID and title; optional externally identified `publisherEdition` label |
| `profile` | Human label and scope with summary, explicit inclusions and exclusions |
| `sources` | Document, playthrough or original editorial definition identities; identified document edition or `{ "unknown": true }` |
| `runs` | Tool/process identity, exact version, timestamp and source inputs |
| `evidence` | Located observations from those sources, linked to the generating run |
| `rules` | Proposed readable rules, gameplay topic, dimension, derivation basis and supporting evidence/premises |
| `coverage` | Account for the nine gameplay topics below, including explicit unknowns |
| `questions` | Unresolved ambiguities, conflicts and missing knowledge; `[]` if none known |
| `entities` | Optional named gameplay structure linked to proposed rules |

Arrays contain distinct stable IDs. IDs are lowercase hyphenated slugs, unique within their collection. A rule's identity is its draft lineage plus rule ID; it is not a global cross-game concept. Retain IDs across corrections. The editor explicitly maps accepted proposals to public rule IDs.

A publisher edition identifies which game you researched. A document edition identifies which source you consulted. A draft revision identifies your changed research output. None is a BGSM or RuleBooks publication revision. If the game/publisher identity changes, create a new draft lineage; document why the old identity was uncertain rather than rewriting its historical snapshots.

## Evidence and inference

Each non-editorial Source has one or more `artifacts`. Each artifact has a local `id`, `handoffId`, `manifestDigest`, relative `path` and file `sha256`. The manifest digest pins the complete canonical handoff metadata, including extraction provenance; the file digest pins artifact bytes. This supports the PDF, OCR and several page/diagram images under the same source identity. Each evidence entry selects one with `sourceId` and `artifactId`, then supplies:

- `locator`: a one-based PDF/image `page`, named `section`, playthrough `time` interval in integer milliseconds, or `bytes` interval;
- `observation`: a concise account of what was actually stated or observed;
- `runId`: the extraction/analysis run that produced the observation.

Time and byte intervals are start-inclusive/end-exclusive. PDF page means the physical file page; a printed page label can go in `label`. A section locator supplies its readable `label`. Crop, rotation and OCR provenance remain in the artifact handoff's derivative metadata. A timestamp refers to the underlying playthrough timeline; if the artifact is a transcript, preserve that timeline mapping. The validator can check byte bounds, but cannot prove page/timestamp accuracy or interpretation.

An editorial Source instead supplies `attribution`, has no artifacts, and identifies an original definition that the author intentionally chose. Its evidence locates the relevant authored clause. Do not label a sourced or inferred game rule editorial just to avoid citations.

Acquisition game/publisher-edition metadata is research context, not exclusive ownership of a source. If it differs from the current draft, include a source `applicability` explanation for the reviewer. Reusing a source across games does not require downloading it again, and an applicability explanation does not establish that its rules govern the new game/profile. The actual source ID and document edition must still match the handoff exactly.

For a proposed rule, `basis` distinguishes:

| Basis | Meaning and requirements |
|---|---|
| `explicit` | A document states the rule. Supporting evidence must come from documents. A classification is still subject to review. |
| `inferred` | You deduced the rule. Supply `rationale`, supporting evidence and/or `premises` naming other proposed rules. Cycles are rejected. |
| `editorial` | An author intentionally defines this configuration. Supply rationale and evidence from editorial sources. |

Every evidence link has a `relation`: `supports`, `contradicts` or `context`. Contradicting evidence requires an explicit conflict question. Every rule needs support or inference premises. Evidence that a move happened is not evidence that every similar move is legal; absence of a move is not a prohibition. Confidence scores are deliberately absent in 0.1.0: provide concrete uncertainty and support instead of an uncalibrated percentage.

A run records `tool.name`, exact `tool.version`, `createdAt` and `sourceIds`. Optional `configuration` is a reproducibility summary. AI-assisted runs can additionally record `agent.provider`, `agent.model` and `agent.promptDigest`; retain the corresponding prompt/configuration privately if needed. A model identifier alone does not make inference reproducible. Record concise derivation rationale, not hidden reasoning transcripts, credentials or unrelated conversations.

## Proposed rules and gameplay structure

A rule includes `id`, `statement`, `topic`, `dimension`, `basis`, `runId` and `evidence`. An inferred rule also requires `rationale`; optional `premises` identify supporting proposed rules. Optional `entityIds` connect it to named objects. Statements must include their relevant conditions and exceptions; do not leave meaning solely in an entity description that will not appear in the readable rulebook.

Use these nine topics for the coverage checklist: **players, components, setup, turns, actions, constraints, information, scoring, ending**. Exactly one coverage row per topic declares `described`, `partial`, `unknown` or `outside-scope`, plus rule IDs and a note. `described` is the producer's claim that this topic is described within the selected scope, not editorial approval or formal completeness. Only described/partial rows list rules. Unknown and outside-scope rows list none; explain the distinction. Every proposed rule must appear under its topic.

`dimension` separately classifies a rule as `game`, `player`, `event`, `tournament` or `composition`. This allows reusable clock, player-conduct or tournament procedures without creating actual event records. Default to `game` for ordinary gameplay mechanics. Keep materially different editions, variants or profiles in separate drafts; do not silently merge their rules.

Optional `entities` name **players, components, spaces, resources, phases, actions and outcomes**. Each has a description and supporting `ruleIds`. An action may additionally name player `actorIds`, `conditionRuleIds` and `effectRuleIds`. For example, the [Nim draft](../../tests/fixtures/knowledge/nim-normal-play/draft.json) identifies the current player, heap and remove action, with the bounds rule as a condition and removal rule as the effect.

These are a structured inventory of game knowledge. Conditions and effects point to readable claims; they are not executable predicates or state updates. Cross-game semantic identity, formal state types, operators and conformance belong to later BGSM work. You can submit all rules without inventing semantic primitives or filling an entity hierarchy.

## Questions stay first-class data

Each question has an ID, kind, question text, generating run, affected `ruleIds`, related `evidenceIds` and `blocks`:

- `publication`: the affected rules must not be accepted while this remains unresolved;
- `completeness`: a rulebook cannot claim complete reading coverage while this remains unresolved;
- `none`: nonblocking research or an extension outside the selected profile.

An empty affected-rule list means the whole profile. Use a `conflict` question when sources or observations disagree; retain both accounts as evidence or distinct proposed rules. Use `identity` when the publisher edition/profile itself is uncertain. Do not bury these conditions in logs or turn every unknown into a BGSM defect. No content or semantic work item is automatically created by this workflow.

## Concrete examples to copy structurally

All examples are **synthetic contract fixtures**, with fictional runs/reviews and original test artifacts. They do not constitute collected game entries or game implementations. Do not copy their identities, citations, reviews or `testOnly` markers into real work.

| Example | Producer output | Editorial result |
|---|---|---|
| [Chess](../../tests/fixtures/knowledge/chess/draft.json) | Explicit turn/king-safety statements; an invalid inference from a short invented playthrough; conflicting documentary evidence; unknown special-move conditions | Reject the inference, retain its evidence, publish only the mechanics excerpt and disclose missing special moves |
| [Nim](../../tests/fixtures/knowledge/nim-normal-play/draft.json) | Eight original rules defining visible heaps `[1, 2]`, A starting, removal from one heap and last-counter victory; named action/conditions | Complete readable definition of precisely that fixture configuration, with editorial attribution and no fabricated external sources |
| [Rock-paper-scissors](../../tests/fixtures/knowledge/rock-paper-scissors/draft.json) | Original one-round commitment/reveal rules; a playthrough-based replay inference conflicting with the selected tie policy | Reject the replay inference, preserve the observation for another profile, disclose unresolved physical conventions; current draft projects as partial |

Each folder also contains `review.json` and `expected-edition.json`. The [fixture guide](../../tests/fixtures/knowledge/README.md) traces the mappings and explains the RPS completeness limitation.

## Validate and hand off

Install the repository's pinned Python dependencies, then run:

```sh
python3 tools/validate_knowledge.py validate \
  --draft "$PRIVATE_DRAFT" \
  --handoff "$PRIVATE_DOCUMENT_HANDOFF" \
  --handoff "$PRIVATE_PLAYTHROUGH_HANDOFF"
```

Repeat `--handoff` for each referenced acquisition; omit it for an original editorial definition without artifacts. Add `--previous "$PRIVATE_PREVIOUS_DRAFT"` for a trusted predecessor check. Without manifests, draft validation checks shape and internal relationships only. With manifests it also checks declared source/game/edition and artifact path/hash bindings. It never fetches URLs, executes files or verifies the actual bytes; the reference importer performs file integrity checks separately.

Seal each draft snapshot after validation. Digests use the existing publication contract's compact sorted-key UTF-8 JSON encoding, not the pretty-printed file's byte hash. The `digest()` helper is the reference implementation. JSON input rejects duplicate keys and non-finite numbers. Do not reuse an existing ID/revision for changed bytes. New evidence, corrected claims or changed uncertainty produce a new revision and a new editorial review.

Deliver the draft and required handoffs together through the private workspace. The handoff importer supplies capture receipts; retain those alongside research snapshots so artifact handoff IDs remain resolvable into managed captures. Improved observations can continue to cite stable originals. This version binds derivatives already named in a sealed handoff; it does not yet reference later managed extract revisions directly. Keep unlisted processing intermediates in the collector workspace.

Your deliverable is useful even if most coverage is unknown. Identify gaps honestly; RuleBooks owns review, public source promotion, release assembly and eventual semantic mapping.
