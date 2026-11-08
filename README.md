# RuleBooks.games

RuleBooks.games is a public library of board and tabletop game rules and the home of the Board Game Semantic Model (BGSM). Readable game editions can exist before they have formal representations. Versioned formalizations connect those rules to shared semantics, with explicit coverage, sources and verification evidence. New games expose gaps; reviewed changes evolve BGSM without rewriting existing publications.

RuleBooks owns the semantic specification and the planned basic public compiler/interpreter tooling. Gameplay products consume its published definitions.

The repository contains the selected product plan, vocabulary, versioned product work queues, and publication and draft game-knowledge contracts 0.1.0 with validation and test fixtures. Local tools support optional private reference intake, reviewed rule projection and reproducible public-data assembly. The Astro site and Cloudflare release workflow are planned, not yet deployed.

- [Product and operating proposal: selected direction](docs/product/README.md)
- [Implementation plan and launch gates](docs/product/implementation-plan.md)
- [Implementation project and engineering issues](https://github.com/orgs/miralie-llc/projects/4)
- [Data addition and BGSM evolution](docs/product/contribution-workflow.md)
- [Publication contract: entities, relationships and first-game examples](docs/architecture/publication-contract.md)
- [Build publication data from reviewed bundles or individual records](docs/development/publication-assembly.md)
- [Deployment, monitoring and ownership](docs/product/operations.md)
- [Public repository, private research and publication boundaries](docs/product/repository-boundaries.md)
- [Contributor checks and local pre-publication review](docs/development/contribution-checks.md)
- [Private reference intake and public source promotion](docs/development/reference-intake.md)
- [Companion collection workflow handoff contract](docs/development/reference-handoff.md)
- [Producing draft game knowledge: rules, structure, evidence and questions](docs/development/game-knowledge-producer.md)
- [Draft knowledge review and provenance-preserving publication](docs/architecture/draft-game-knowledge.md)
- [Content and semantic work queues](work/README.md)
- [RuleBooks vocabulary](docs/reference/vocabulary.md)
- [Research and source register](docs/reference/sources.md)
- [Design principles](docs/architecture/principles.md)

Run repository checks with Python 3.11 and the same dependencies as CI:

```sh
python3 -m pip install -r tools/requirements-ci.txt
python3 tools/install_gitleaks.py
python3 tools/check_repository.py
python3 -m unittest discover -s tests -v
```

Before a public push, follow the [local review procedure](docs/development/contribution-checks.md), including credential scans of candidate files and outgoing history. The commands above do not publish anything.

[Repository validation](.github/workflows/validate.yml) runs on pull requests and pushes to `main`. It checks maintained paths/links, work records, credentials, publication contracts and contribution boundaries; site builds and deployment will follow the [operations plan](docs/product/operations.md). Game examples under `tests/fixtures/` are contract tests, not collected or published catalog entries.
