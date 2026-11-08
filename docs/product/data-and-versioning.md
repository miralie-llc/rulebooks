# Data, authority and versioning

Part of [proposal 0.3.0](README.md). This is the selected logical model. [Publication contract 0.1.0](../architecture/publication-contract.md) now implements its first exchange schema, relationship validator and game-shaped test fixtures. The publication assembler, actual collected game entries and semantic runtime remain implementation work. Work-item validation remains separate.

## Small records with explicit relationships

`Required` means required for a published record of that type. Drafts may be incomplete. Optional objects are absent when unused; consumers do not receive hundreds of empty fields.

| Record | Required information | Relationships and optional detail |
|---|---|---|
| GameFamily | Stable ID, display title | Optional discovery grouping of related games/publisher editions; not an executable rules identity |
| Game | Stable ID, title, default published RulebookEdition | Distinct identity for each publisher edition of a game; optional family ID, publisher-edition attribution, aliases and discovery tags |
| PublisherEdition | Stable ID, game ID, publisher/issuing authority, external edition label, identifying source | Optional external identifier, release date and predecessor; the publisher's version, never a RuleBooks revision counter. Absent for games without an applicable publisher edition |
| RulebookEdition | ID/revision, game ID, label, declared scope, ordered readable rule sections, sources/editorial origin, review record | Our selected rules/profile for that exact game; has zero or more formalizations; optional parent, variant description and annotations |
| Rule | Stable ID within edition lineage, readable statement, section, source links or original-definition attribution | Edition revision pins its text; optional cross-game vocabulary links and examples |
| Source | ID, title, publisher/author if known, edition/date or explicit unknown, locator and access date | Article/page/section anchors; optional permitted capture and digest. One source can support many rules |
| Formalization | ID/revision, exact edition pin, exact BGSM release, language/dialect version, package/entry and dependency pins, rule coverage, review record | Zero or more compiled artifacts, verification records and target-language exports |
| DefinitionPackage | ID/revision, source files with digests, language, semantic-library pins, exported definitions | Optional exact dependencies; source maps link definitions to rule IDs. Shared modules use the same packaging discipline |
| BGSMRelease | Version, status, concept/law index, exact library pins, changelog, supported capability profile, conformance-suite pin | Predecessor and migration guidance; may be experimental or recommended |
| Concept | Stable ID, versioned meaning, category, laws/constraints, examples, status | Related concepts and game/rule usages; executable implementation references where available |
| SemanticGap | ID, kind, exact rule/edition or formalization pin, expected meaning, minimal example, current limitation, status | Affected BGSM versions, related games and optional proposal/resolution links |
| WorkItem | ID, queue, kind, title, status, target, acceptance criteria | Versioned product work: wishlist, content task or semantic gap; optional dependencies/evidence/resolution. A semantic-gap item owns its gap detail rather than duplicating a separate tracker record |
| VerificationRecord | Subject digest, implementation/build identity, suite digest, method, scope/bounds, result, run provenance | Counterexamples or report artifact; failure and unknown are valid evidence |
| BuildArtifact | Input/package digest, BGSM/language pins, compiler build, output digest, source map | Export adds target dialect/runtime, mappings and supported subset |
| Publication | Release ID, repository commit, exact record/artifact manifest, checksums, release notes, publisher/review provenance | Selects default editions/formalizations; previous publication and withdrawal notices |

Rule and Concept may be entries in a small file rather than separate files or database tables. Review records capture author, reviewer, time, decision and reviewed commit/digest. Authorship can name an agent and the responsible human; publication has a human accountable owner.

## Publisher editions are game identities, not our revisions

Use **RulebookEdition** for our editorial record. Its `revision` is explicitly a RuleBooks content revision. A **PublisherEdition** records the external publisher's edition label and provenance. Never put that label in `revision`, infer it from BGSM versions, or change it when correcting our prose.

Each Game has at most one PublisherEdition identity in this initial model; a new publisher edition gets a new Game. Multiple RulebookEdition profiles and their revisions can describe that Game. Source-document editions and corrected printings remain source metadata unless they identify a distinct game edition.

The following Dominion identifiers illustrate the identity model; they are not collected catalog entries:

```text
GameFamily: dominion
├── Game: dominion-first-edition
│   ├── PublisherEdition: first-edition (publisher's label/source)
│   └── RulebookEdition: dominion-first-standard @ revision 4
└── Game: dominion-second-edition
    ├── PublisherEdition: second-edition (publisher's label/source)
    └── RulebookEdition: dominion-second-standard @ revision 1
        └── Formalization: ... @ revision 2, targeting BGSM <exact version>
```

Dominion's second edition is a separate game identity in this model. Fixing a typo in our second-edition rulebook advances its RuleBooks revision from 1 to 2; it does not create Dominion third edition. Each publisher edition can independently have several RuleBooks profiles and revisions, including several formalizations under different BGSM versions. Family pages can recommend an edition, but pinned definitions always identify the specific game.

Publisher numbering is an external label, not necessarily a semantic version. Localizations, corrected printings, expansions and publisher editions should be classified from their actual identity and rules differences; do not assume every new box or translated title is a new game. Capture printing/source revisions separately when they do not establish a distinct game edition. Classical games may have no publisher edition; an authority's rulebook version still needs attribution, without inventing a publisher for the game.

Optional interpretation notes, authorities, reusable procedural layers and historical examples attach by reference. They are loaded when requested. A minimal source attribution is part of ordinary authoring, while a multi-authority evidence graph is an extension. An original formal game can cite its editorial definition rather than invent an external authority.

## What is canonical

The published edition is RuleBooks' editorial statement of the selected game's rules, with its scope and sources. This is not a claim that RuleBooks outranks an external authority.

For a particular formalization, the authored package plus exact semantic dependencies determines executable meaning. The compiled artifact is derived, and must agree with its inputs. A target-language export is also derived. Each formalization declares which edition rules it covers; multiple formalizations can target different BGSM versions without changing the edition.

If prose and formal behavior disagree, neither discrepancy is silently accepted. Record the problem, remove the affected formalization's recommendation, and correct the responsible record in a new revision. A complete-coverage badge requires review of this correspondence; successful parsing is insufficient. An edition can remain published while its formalization is under correction.

## Coverage and evidence are different axes

Display reading completeness, formal coverage and verification independently. A readable-only entry can report:

```text
Reading edition: reviewed within its declared scope
Formal coverage: not yet formalized
Verification: no executable verification available
```

For each rule, coverage is `represented`, `partial`, `unrepresented`, or `outside-declared-scope`, with definition links or a reason/gap. Outside scope is visible in the scope declaration; it cannot be used to advertise a partial game as complete. Coverage summaries are derived from those rows. Do not present a percentage unless the denominator and granularity are meaningful.

Verification methods include structural checks, type/binding checks, scenario tests, bounded exhaustive exploration and proofs where available. A complete mapping with only scenario tests is different from a partial mapping exhaustively tested over its small subset. The UI must preserve that difference.

## Versions that must not be conflated

| Version | Changes when | Compatibility rule |
|---|---|---|
| Publication schema | Storage/exchange shape changes | Every shape change gets an exact new version; closed-schema readers must be updated even for optional additions. Required-field/meaning changes need explicit migration. |
| Publisher edition | Publisher releases a distinct edition of the game | Separate Game identity, linked through GameFamily; preserve external label and source; never incremented by RuleBooks |
| RuleBooks rulebook revision | Our published rules, explanations, citations or scope change | New immutable RulebookEdition revision, classifying editorial vs rule change; publisher edition stays fixed |
| BGSM release | Semantic definitions, laws or capabilities change | Never change meaning at an existing version; breaking changes explicitly marked, including during 0.x |
| Language/dialect | Syntax, binding or authoring rules change | Different from BGSM meaning; pin independently |
| Semantic library/module | Reusable definitions change | Exact pins; no floating `latest` or dependency ranges in releases |
| Formalization revision | Mapping, package, coverage or target BGSM changes | New revision may describe the same edition under another BGSM version |
| Compiler/interpreter build | Implementation changes | Compatibility is demonstrated by tests, not inferred from a matching version string |
| Site/publication release | UI or published selection changes | Does not by itself change game or BGSM meaning |

Use stable IDs plus immutable revisions/digests for content. Use semantic versioning for contracts where compatibility has a defined meaning. Early BGSM releases remain experimental until the intended stability boundary is established; “0.1” is not an excuse for overwriting published semantics. A law correction that changes observable meaning requires a new explicitly breaking semantic release.

## How typical changes behave

| Change | New records | Existing consumers |
|---|---|---|
| Publisher releases second edition | Separate Game and PublisherEdition, plus its own RulebookEdition lineage | First-edition game pins keep meaning first edition; no automatic substitution |
| Fix a typo | New edition revision; lineage identifies editorial-only change | Old edition stays available; retain old formalization link until its edition association is explicitly carried forward and reviewed |
| Correct a game rule | New edition and affected formalization revisions; regression example | Prior revision gets correction notice; default changes only after review |
| Add a game BGSM cannot express | New edition and gaps | No BGSM or other-game migration required |
| Add a semantic concept | New BGSM/library release with laws and fixtures | Existing pins continue to resolve unchanged |
| Formalize the game in the new model | New formalization for the same edition | Readers can compare old and new coverage/results |
| Fix an interpreter bug | New implementation and verification evidence | Prior artifacts/evidence retained; affected results marked suspect or withdrawn |
| Change an external source URL | New source/edition metadata revision as appropriate | Archived citation identity retained; public reading does not depend on live fetches |

For example, a readable RPS edition can exist with no formalization. A gap demonstrates why publishing both players' commitments early changes the game. A later BGSM release introduces the required information boundary with laws and tests. A new RPS formalization pins it. Chess and Nim need no edits merely because that release exists.

Migrations are explicit change sets: old pin, new pin, transformation, coverage delta, behavioral comparison and reviewer. Do not bulk-recompile and replace historical artifacts. Old content must be readable/downloadable without an old runtime. Initially, actively test one recommended BGSM line and one experimental line; list older execution support as archived or unsupported. Preserve build recipes and permitted artifacts without promising indefinite maintenance of every runtime.

## Publication and retrieval

Proposed routes include `/games/chess`, `/editions/<id>/<revision>`, `/bgsm/<version>/concepts/<id>`, `/formalizations/<id>/<revision>`, `/gaps/<id>`, and `/releases/<release-id>/manifest.json`. These are not deployed endpoints.

Mutable discovery pages link to exact pins. Downloads resolve through one publication manifest, so a consumer cannot accidentally combine a new index with an old definition. Serve compact manifests and separate source/compiled/evidence downloads. Set a provisional 20 KiB budget for an individual game discovery JSON record; require justification for increases. This is a product budget, not an assertion about full chess definition size.

Keep private research captures outside the public build input. Publish authorized original text and source metadata; separately track whether captures or excerpts may be redistributed. The repository already contains a [GPL-3.0 license](../../LICENSE); this proposal does not change it. The [license-scope policy](repository-boundaries.md#license-scope) explains its application to project-authored code, specification and original data; contributor terms remain a maintainer decision before external contributions are accepted. Do not infer reuse permission for third-party material from a source URL or the repository license.
