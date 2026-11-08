# Product work queues

These records are the canonical **content** and **semantic** queues. They are product data, versioned in Git; a future website/editor can browse and update them. They are not software implementation tickets or published game records.

Use one small JSON file per item, with filename equal to `id`:

- `content/`: game wishlist, edition identification, readable rules and mapping tasks.
- `semantic/`: concrete modeling gaps, library/notation limitations and proposals. A gap is triaged before assuming it requires a new BGSM concept.

The initial content records cover chess, Nim and rock-paper-scissors. Actual editorial draft records now exist in the [catalog](../data/catalog/catalog.json). Nim and rock-paper-scissors await acceptance; chess is an incomplete introduction. These tasks do not claim reviewed publication or formalization. The semantic queue starts empty: add work only after content review or a concrete mapping attempt reveals an evidenced limitation. Candidate game targets need no catalog entry. Once catalog records exist, link exact rulebook/publisher-edition identities and revisions in the target/evidence instead of overloading our record revisions.

Required fields are `schemaVersion`, `id`, `queue`, `kind`, `title`, `status`, `target`, and `acceptance`. A semantic gap also requires `gap` with classification, problem, expected behavior and a minimal example. Optional fields include evidence, dependencies, blocked reason and resolution. Keep contact details, secrets and private storage paths out of every field; everything committed here is intended to be public.

Workflow: `proposed` → `ready` → `in-progress` → `review` → `done`. Use `blocked` with a reason or `deferred` when work is intentionally postponed. `done` requires a resolution describing what landed, with exact references when available. Git history supplies change history; do not append an unbounded conversation transcript. A formalization can reference the gap ID; the gap record remains the single source of its status.

The work record schema is versioned independently at 0.1.0. It is deliberately small and can evolve as the editorial workflow becomes concrete. It is not the production game/BGSM schema.

```sh
python3 tools/validate_work.py
```

This checks schema, identity, queue placement, dependency integrity/cycles and local evidence paths. It does not establish source truth, detect all confidential text or approve publication. Public site views must select reviewed fields/items explicitly rather than copying this directory wholesale.
