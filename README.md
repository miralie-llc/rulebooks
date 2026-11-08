# RuleBooks.games

RuleBooks.games is a public library of board and tabletop game rules and the home of the Board Game Semantic Model (BGSM). Readable game editions can exist before they have formal representations. Versioned formalizations connect those rules to shared semantics, with explicit coverage, sources and verification evidence. New games expose gaps; reviewed changes evolve BGSM without rewriting existing publications.

RuleBooks owns the semantic specification and the planned basic public compiler/interpreter tooling. Gameplay products consume its published definitions.

The repository contains the selected product plan, vocabulary and versioned product work queues. The public site and publication workflows are planned, not yet deployed.

- [Product and operating proposal: selected direction](docs/product/README.md)
- [Implementation plan and launch gates](docs/product/implementation-plan.md)
- [Data addition and BGSM evolution](docs/product/contribution-workflow.md)
- [Deployment, monitoring and ownership](docs/product/operations.md)
- [Public repository, private research and publication boundaries](docs/product/repository-boundaries.md)
- [Content and semantic work queues](work/README.md)
- [RuleBooks vocabulary](docs/reference/vocabulary.md)
- [Research and source register](docs/reference/sources.md)
- [Design principles](docs/architecture/principles.md)

Validate product work records with Python 3.10+ and jsonschema 4.x:

```sh
python3 -m pip install 'jsonschema>=4,<5'
python3 tools/validate_work.py
```
