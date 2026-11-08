# Design principles

These principles support the [current product plan](../product/README.md) and guide implementation choices.

- **Small authored definitions, derived machine artifacts.** Keep exact semantic-library pins and source maps. Avoid duplicating expanded ASTs in every game and variant.
- **Honest incompleteness.** Unresolved predicates and missing capabilities must be inspectable. Parsing is not execution; execution is not proof of faithful rules.
- **Provenance by stable rule reference.** Minimal source attribution belongs in the core authoring workflow. Rich source captures, competing interpretations and historical adjudications attach separately.
- **Independent game dimensions.** Mechanics, play procedure, player conduct, event policy and tournament format can be described independently. Composing them requires semantic prerequisites, not arbitrary checkbox combinations.
- **Variants as reviewed changes to exact bases.** Inherit unchanged meaning and laws. Revalidate the assembled definition; avoid copying whole games.
- **Translation has a behavioral contract.** State, intent, information and result mappings need executable evidence against named target runtimes. Unsupported capabilities must remain visible.
- **Examples drive semantics.** Small chance, agency and hidden-information specimens reveal different gaps. Broad handwritten game support does not establish equivalent source-language support.

BGSM and the basic public toolchain belong to RuleBooks. Readable editions do not require executable definitions, and ordinary game documents do not require a rich evidence graph.
