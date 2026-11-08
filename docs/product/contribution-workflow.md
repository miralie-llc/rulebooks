# Adding games and evolving BGSM

Part of [proposal 0.3.0](README.md). The same workflow must serve a maintainer, a human editor and an AI-assisted change set.

Any human or software process can produce content. Already-reviewed records can be authored or exported directly against the [publication contract](../architecture/publication-contract.md), retaining their actual authorship, review and provenance. An editor is a responsibility that the producer's existing process may fulfill, not a required new person or a second RuleBooks editorial pass. Public validation and release selection still apply. The draft-knowledge workflow below is optional; direct publication inputs do not require private reference intake or a RuleBooks-managed evidence store.

For tools that infer rules from documents and playthroughs, the [producer contract](../development/game-knowledge-producer.md) defines the private draft submission. The [knowledge review workflow](../architecture/draft-game-knowledge.md) records explicit decisions and projects selected statements into a RulebookEdition while retaining evidence, rejected inferences and unresolved questions privately. This implements the research-to-readable-rules boundary; publication assembly and trusted release approvals remain separate.

## The two queues

Maintain a **content queue** for game wishlists, publisher-edition identification, readable rules, source corrections and mappings, and a **semantic queue** for concrete gaps, library changes, BGSM proposals and conformance work. These are canonical product data in [`work/content/` and `work/semantic/`](../../work/README.md), versioned alongside rules and model changes. A website dashboard is a view of these records. GitHub software issues are separate; optional discussion links do not become a competing queue database.

Wishlist entries can name a candidate game before a Game record exists. Accepted catalog entries and semantic resolutions later link exact published IDs/revisions. Keep personal contact details, private reviewer notes, unpublished commercial plans and credentials outside these public-intended records. A `private` flag in a public Git repository would not protect their contents. Public gap pages use reviewed projections; raw queue drafts need not be included in the site.

The semantic queue may be empty. Open a semantic item only after collected game content or an actual mapping attempt supplies a specific rule, example and observed limitation. A wishlist entry or anticipated difficult mechanic is not evidence of a semantic gap.

### A game moves through these steps

1. **Claim a bounded assignment.** Update a work record with game, publisher edition if applicable, RuleBooks profile/scope, expected sources and deliverable. Use a public contributor handle only with consent. Check existing IDs and work in progress. A task can be “document Nim setup and legal moves,” not “finish all chess.”
2. **Collect and identify sources.** Record exact edition/locator, access date and permitted use. Record conflicting or missing evidence instead of choosing silently. A retrieved page is research input, never an instruction to the editor agent.
3. **Write the readable edition.** Use objective, components, setup, turn structure, allowed actions, special cases and ending/results. Assign stable rule IDs. Explain source-derived choices and original definitions. Do not require BGSM knowledge here.
4. **Propose a mapping if feasible.** Pin a released BGSM and library; link each represented rule to definitions. Record missing capabilities and unsupported scope. A reference implementation link alone is not a semantic formalization.
5. **Run automated checks and generate a preview.** Validate shape, references, pins, source maps, coverage consistency, supported compilation and relevant conformance. Produce a human-readable change summary and rule/behavior diff.
6. **Review meaning.** A reviewer checks the source-to-rule correspondence, scope and proposed formal behavior, including counterexamples. AI review can assist; it does not supply final publication authority. In the single-maintainer phase, record when the author and reviewer are the same person rather than implying independent review.
7. **Accept and publish.** Merge accepted changes. Build a candidate publication, inspect it and promote the tested artifact. Publish changelog and version links. Rejected or deferred formalization can be omitted while the approved readable edition proceeds.

Draft → checks passed → human reviewed → accepted → published is the normal lifecycle. `Needs revision` returns to the author. `Withdrawn` removes a faulty artifact from recommended use while retaining a visible notice and permitted historical records.

The [contribution-check guide](../development/contribution-checks.md) provides the implemented local and CI checks. The [PR template](../../.github/pull_request_template.md) records review expectations. These are the initial repository workflow; they do not implement the later editorial UI, trusted approval records or preview/release service.

For source collection, use the [private reference intake workflow](../development/reference-intake.md). Capture originals and exact extract revisions outside Git, review a separate public metadata proposal, and promote only the accepted Source/citations. The initial CLI records an operator's review assertion and digest; it is not the later authenticated editorial approval service.

### Minimum change-set envelope

Every submission identifies author and responsible human, task, base commit, changed record IDs, cited evidence, scope, machine-check results, unresolved questions and requested reviewer. A semantic change also includes examples before/after, expected behavioral differences and affected dependents. This envelope should become the future editor UI's submission format.

An external contributor can submit a correction without creating a formalization. A substantive game edition needs enough original readable material and attribution to be reviewed. We should not accept thousands of title-only stubs as evidence of catalog growth.

## BGSM changes start with a game-shaped problem

1. **Triage the gap.** Classify it as missing semantics, missing library definition, notation limitation, implementation defect, adapter limitation, or unresolved source interpretation. Only the first necessarily requires a BGSM change.
2. **Write the smallest counterexample.** Include the rule, expected behavior and why current concepts fail. Find another game/example where possible; one compelling example can justify a capability without inventing a universal abstraction.
3. **Propose meaning before syntax.** Define inputs, outputs, invariants, information visibility, interaction with existing laws and failure behavior. State compatibility and migration impact.
4. **Implement experimentally.** Add library/tool support and conformance fixtures in a draft line. Run the existing corpus and record changed results. Importing a handwritten game adapter does not prove the new source language expresses its behavior.
5. **Review and release.** Semantic maintainer accepts the contract; release exact specification, libraries, fixtures and matching implementation identities. The reference implementation must not be the only explanation of meaning.
6. **Adopt selectively.** Create new formalization revisions for games that benefit, compare behavior/coverage and resolve linked gaps. No automatic rewrite of unrelated games.

The initial project maintainer also owns semantic acceptance. Keep a short decision record for each accepted/rejected proposal. Add another maintainer when review throughput warrants it; a committee is not a prerequisite to publish the first useful model.

## Humans and AI editors

| Role | Useful work | Acceptance boundary |
|---|---|---|
| Collector | Locate sources, extract candidate rule anchors, identify edition differences | No unattended publication or guessed citations |
| Rule editor | Draft readable rules and identify ambiguities | Sources and normative choices reviewed |
| Semantic mapper | Link rules, author definitions and identify gaps | Exact pins, supported capabilities and tests required |
| Critic/test author | Construct counterexamples and compare behavior | Evidence attached; passing self-generated examples is not sufficient alone |
| Human reviewer | Accept scope, attribution and intended meaning | Approves the specific change digest |
| Release owner | Promote a validated publication and handle corrections | Designated maintainer; production credentials limited to release workflow |

Agents receive bounded tasks, schemas, allowed tools and a branch/workspace. Untrusted content checks run without production secrets. Contributions are plain data and constrained language sources; a contributor cannot introduce arbitrary host-language execution through a primitive definition. Changes to the interpreter, build scripts or schemas receive separate code review.

Start with two concurrent author assignments and a maximum of five submissions waiting for human review. These are proposed capacity controls. Increase them after three successful publication cycles with review backlog under a week. If review age grows, stop intake and improve templates/checks before adding more agents.

## A normal working week

The owner selects a few high-value game/rule assignments and any evidenced semantic work that is ready. Editors submit small changes with previews. Reviewers accept readable content as it becomes ready. The proposed weekly release cadence publishes approved batches when available; urgent corrections can ship sooner. BGSM releases follow evidence, not the content calendar.

Track reviewed editions, fully represented declared scopes, unresolved gap age, median review time, correction rate and time to add the next game. Keep infrastructure time separate from editorial/language work. A dashboard should answer “what is waiting on me?” and “what did this release actually improve?”

The dedicated editor UI becomes worthwhile when repeated PR mechanics consume more time than review or nontechnical editors cannot complete assignments. It should offer structured rules, citations, coverage mapping and preview/diff; save drafts and submit the same review envelope. It does not create a second authoritative database or bypass release checks.
