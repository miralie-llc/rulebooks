# Experimental reference semantics and toolchain

This is the RuleBooks-owned, bounded reference contract for issue #8. Its source is maintained here, originally authored for this project under the existing [repository license](../../LICENSE); no sibling engine, archived proposal or third-party implementation has been copied. It is an experimental engineering specimen, not an accepted BGSM publication or a claim of complete board-game support.

## Independent pins

| Layer | Exact identity |
|---|---|
| JSON storage/grammar | `schema/runtime/0.1.0/program.schema.json` |
| Authoring language | `rulebooks-json` `0.1.0` |
| Semantic charter | BGSM draft `0.1.0-draft.1` |
| Core operation library | `core` `0.1.0` |
| Reference implementation | `rulebooks-reference` `0.1.0`, plus actual build digest |

These identifiers are independent even where initial numbers match. Compilation rejects ranges, unknown versions and unsupported capabilities. A future accepted BGSMRelease must carry its actual concepts, conformance package and acceptance metadata through the publication contract; this document does not fabricate that record. Changes to meaning require a new semantic pin, syntax changes a language pin, and implementation changes a new implementation build. Existing published records are never rewritten by an interpreter update.

## One turn, five boundaries

1. **Legal intent:** a named player proposes an action ID and exact parameter values from finite declared domains. The action predicate must evaluate to a boolean. Unknown actors/actions/parameters, out-of-domain values and intents in terminal states are rejected. There are at most 4,096 enumerated candidate intents across the program.
2. **Resolution:** a legal intent produces an event, or a finite distribution over events. Positive integer weights are normalized with exact rational arithmetic. Identical events are combined by canonical JSON value. No random sample is drawn, and no hidden choice is made on the caller's behalf.
3. **Deterministic reduction:** the caller selects one permitted resolved event. Effects read the same pre-state and event, then update declared state slots simultaneously in a fresh value. A forged event is rejected. Neither legal checks, failed attempts nor successful transitions mutate the input state.
4. **Observation:** this version exposes a deep copy of the full state to every declared player. Hidden information, private commitments, simultaneous independent submissions and information-set reasoning are unsupported. An RPS commitment cannot be modeled faithfully merely by putting secret choices in this public state.
5. **Outcome:** an expression returns exactly `terminal` and `winners`. Winners must be distinct declared players; a nonterminal state has no winners. A terminal state with no winners is a draw. Terminal states have no legal intents.

Rejection is separate from a gameplay penalty: no automatic penalty, turn loss or hidden mutation is inferred. Rules must explicitly model any such consequence as a legal action in a future supported scope.

## Expressions and laws

Values are JSON nulls, booleans, bounded integers, strings, lists and objects. Floating-point numbers are rejected. Strings are at most 1,024 characters; integer magnitude is at most one billion; list length at most 128; value/expression nesting at most 24. Programs are at most 64 KiB. These limits bound this implementation; they are not universal laws of board games.

- Literals are scalar/list values or `{"literal": value}` for objects. Objects with executable meaning use a closed expression shape.
- Variables use `{"var":"state.slot"}`, `actor`, `params.name`, or `event.name`, depending on phase. Legal predicates and resolution can access state/actor/params; reduction sees state/event; outcomes see state. No ambient environment, filesystem, network, clock or host language is visible.
- Operations use `{"op":"name","args":[...]}`. `eq` compares typed canonical JSON values; boolean `true` is distinct from integer `1`. `lt`, `le`, `add`, `sub` require integers. `and`, `or`, `not` require booleans. `and`, `or`, and `if` evaluate only the necessary branch.
- `get` and `set` operate on lists with zero-based nonnegative in-range indices; `set` returns a new list. `length` returns length; `sum` requires integers. `array` evaluates its elements. `object` takes unique `[key, expression]` pairs.
- Resolution alone can use `{"chance":[{"weight":1,"value":expression}, ...]}`. Chance is forbidden in predicates, effects and outcomes. Events with weight zero are rejected rather than silently discarded.
- For identical program, state, actor and intent, legal results and resolution distributions are identical. For identical pre-state and selected event, reduction is identical. Observations are value copies, not mutable handles into runtime state.

Compilation checks shape, pins, operation names/arity, phase bindings, source-pointer existence and declared state slots. It is not a complete static type proof or proof of termination across an unbounded sequence of turns. Value types, arithmetic bounds and outcome invariants are also checked when evaluated. The runtime does not accept arbitrary Python callbacks, plugin names or MDX from game records.

## Run and inspect

```sh
python3 -m tools.runtime tests/fixtures/runtime/counter.json --output .cache/runtime/counter.json
python3 -m unittest discover -s tests -p 'test_runtime.py' -v
```

The emitted inspection document retains the declarative program, exact pins, canonical source digest, rule-to-JSON-pointer source map and implementation build identity (source/schema/dependency-lock hashes, actual Python and jsonschema versions). It is an inspectable validated tree, not a separate opaque bytecode VM. A source map connects a named rule to a real source node; it does not prove that the expression faithfully implements the rule.

The counter fixture is a developer-owned behavioral specimen, not collected Nim or a published game. Tests independently specify expected legal intents, state transitions and outcomes; reject illegal intents, forged events, unsafe bindings and unsupported versions; and verify exact weighted alternatives and nonmutation. All tests run in the existing clean CI environment. Adding host operations changes reviewed code and its build digest; adding a game only supplies constrained language data.

The next slices exercise coin/weighted alternatives with emitted evidence (#9), then the reviewed, exact Nim scope with independent exhaustive comparison (#10). No general GDL/Ludii translation or public browser execution is claimed.
