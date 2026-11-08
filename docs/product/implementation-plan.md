# Implementation plan and release gates

Part of [proposal 0.3.0](README.md). Work proceeds by completed slices. No site deployment, code transfer or new runtime implementation is performed by this proposal.

## Starting position

The repository has [vocabulary](../reference/vocabulary.md), a selected product/data plan, [versioned product work queues](../../work/README.md), and [publication contract 0.1.0](../architecture/publication-contract.md) with schema, relationship/integrity validation and self-contained test fixtures. The first fixtures cover chess, Nim and RPS without populating the content or semantic queues. The [publication assembler](../development/publication-assembly.md) now builds public JSON and separate declared assets with deterministic receipts and preserved revision URLs. The [Astro browsing site](../development/site.md) now presents actual editorial drafts for Nim, rock-paper-scissors and chess, with sources and exact revision links. The BGSM explorer renders versioned model records and reverse rule links when supplied by a publication; the current site exposes the editorial vocabulary and an explicit no-release state. The [experimental public reference engine](../architecture/reference-semantics.md) now supplies a bounded declarative execution boundary. Accepted content/model releases, executable chance evidence and the reviewed Nim conformance slice remain separate gates.

Existing external implementations may inform or accelerate the public toolchain after code, license and conformance review. Any adopted code must be maintained here or pinned as an explicit reproducible dependency. Personal research folders and neighboring checkouts are never required to build or validate this repository.

## Ordered milestones

| Milestone | Deliverable | Exit criterion |
|---|---|---|
| M0 — Establish the contract | Selected schema for editions with optional formalizations, BGSM releases/concepts/gaps, coverage and publication manifests; self-contained test fixtures | Clearly labeled test fixtures exercise absent, partial and complete formal coverage without being published as collected game data or work items |
| M1 — Make both halves browsable | Static game catalog/edition pages and BGSM concept/version pages; source links, cross-links, coverage and search; JSON/source downloads | A reviewer can move game → rule → concept → other uses, and see a game with no formalization. No runtime service required to read it |
| M2 — Own the public reference tooling | Implement or adopt a semantic charter, narrow compiler/interpreter, necessary libraries and conformance fixtures under RuleBooks ownership with provenance/license review; pin a reproducible build | A clean CI environment compiles and evaluates a versioned coin-toss package, checks weighted alternatives, exports an inspectable representation and publishes evidence |
| M3 — Close the first real game loop | Extend only needed semantics to express a small normal-play Nim game through public source and the reference interpreter | Setup, actors, legal actions, rejection without mutation, state reduction and outcomes work; compare all reachable states for a stated bounded configuration using independently specified expected behavior |
| M4 — Exercise editorial and model change | Reviewed chess/Nim/RPS editions, submission templates, previews, review records, gap queue and a second experimental BGSM release | Add a readable-only game; resolve one real gap; publish its new formalization; show old/new versions side by side while old pins still resolve |
| M5 — Launch and operate | Production static hosting, checks, protected release job, monitoring, backups, rollback and owner runbook | Owner completes preview → promote → smoke check → rollback → restore rehearsal; all launch gates below pass |
| M6 — Expand from evidence | First independent target-language adapter, additional games, later editor UI | Named target runtime executes one supported subset with explicit behavior mappings; contributor volume grows only with review capacity |

M0 precedes the public data surfaces. M1 can proceed alongside M2 after the contract stabilizes. M3 depends on M2; M4 exercises M0–M3 together. Hosting can be prepared early, but launch follows the operational rehearsal. A catalog alpha after M1 is useful and must clearly identify its incomplete formal tooling.

For M2, establish a single maintained implementation here. If adopting external code, preserve attribution/history, select the smallest appropriate boundary, and run its tests. Any imported definitions need an explicit tested importer or reviewed re-authoring; similar notation does not establish equivalent meaning.

For M3, a host-language primitive named `nim` that hides the whole game does not meet the gate. The published definition must expose its setup, legal action constraints, transition and outcome through reusable, inspectable semantic operations. A handwritten reference may be an oracle, but cannot stand in for the definition.

M6 begins with a bounded deterministic Nim export and a pinned external interpreter. GDL and Ludii are separate targets; neither is promised at launch. Each adapter must declare its supported subset, exact input/output language versions, interpreter build, and mappings for state, intent, observation and outcome. Compare all reachable mapped states for a small configuration and publish the verification bounds. Reject unsupported capabilities; label approximations as different derived games. Translation of a second language should not hold up the public library.

## First implementation backlog

Before a public push, apply the [pre-publication review boundary](repository-boundaries.md). Implement private reference intake before scaling AI collection. Full editorial and ingestion automation is not a prerequisite for publishing reviewed project documentation.

1. Add publication schemas and fixtures for readable-only, partial and complete-within-scope records; distinguish publisher-edition game identity from RuleBooks record revision; reject dangling/version-floating references.
2. Add a deterministic publication assembler with exact manifest and input/output hashes; keep product queue validation as a separate check.
3. Build game/edition/rule pages and a consistent visible edition/scope selector.
4. Build BGSM version/concept pages with reverse rule links, examples and capability status.
5. Add coverage/gap views and compact downloads; check the initial payload budget.
6. Establish the RuleBooks-owned reference-tool boundary and CI execution of imported tests.
7. Publish coin-toss source, compiled inspection view, source maps and actual verification evidence.
8. Implement the Nim slice and independent bounded conformance comparison.
9. Add contributor forms/templates over the Git-backed product queues, automated diff reports and preview/release workflow. Implement pre-public-push checks and private-reference intake before scaling AI collection.
10. Configure hosting/monitoring/backup and perform the launch rehearsal.

Engineering issues, dependencies and implementation status are tracked in the [RuleBooks implementation project](https://github.com/orgs/miralie-llc/projects/4). This document defines the milestone sequence and release gates. Game collection and evidenced semantic work remain in the [repository product queues](../../work/README.md).

## Launch checklist

- Three reviewed readable editions with stable rule IDs, scope and attributable sources; no silently unfinished reading paths.
- BGSM explorer, game explorer and mutual links work without requiring readers to understand compiler internals.
- At least one genuinely inspectable, executable complete game within a declared scope; partial and unsupported cases are equally clear.
- Exact versions and digests in every executable download; latest/default aliases never used as semantic dependencies.
- One actual evolution cycle demonstrated: new capability, new formalization, old edition still readable and old artifact retained.
- Reproducible pinned build, scoped conformance evidence, expected failures and source-map checks; generated output checked for drift.
- Mobile/keyboard usability and readable text checked; search, source links, JSON downloads and version switching tested in a browser.
- Public data/spec/code licenses and contributor terms selected; public build excludes private research and unapproved source captures.
- Named production owner, protected credentials, external probes, off-provider backup, tested rollback and restore.

Do not add broad browser tests to every content edit. Schema/reference checks apply to all records; semantic tests apply to affected dependencies; UI checks apply to changed views; full regression runs gate BGSM/tool releases. Preserve a reproducible full-suite release run so dependency analysis is not the sole guard.

## Capacity and scope control

Planning assumption: one experienced builder, a maintainer supplying product/semantic decisions, and AI assistance on bounded tasks. Reserve separate time for source review and BGSM design; tooling does not eliminate either. Re-estimate effort after M1 and the M2 build test, since the source-to-full-game gap is the largest uncertainty. A calendar launch promise before that experiment would be unreliable.

If M3 expands, ship the catalog alpha and continue the bounded Nim work. Cut adapters, advanced variants and editor UI first. Do not meet a date by relabeling partial formalization as complete. After launch, use a small rolling backlog: reader improvements, content additions, one language capability at a time, and operational maintenance.
