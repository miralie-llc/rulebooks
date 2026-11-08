# Building publication data

The [publication assembler](../../tools/assemble_publication.py) implements [issue #4](https://github.com/miralie-llc/rulebooks/issues/4). It turns already-reviewed publication records into a deterministic directory of public JSON and declared source/evidence files. This is the data input for the planned Astro site; it does not render pages, deploy to Cloudflare, infer rules or run game packages.

**Any producer can supply these inputs.** A person can author the records directly, an external editorial pipeline can export them, or the optional knowledge workflow can produce a reviewed RulebookEdition. Existing review metadata is validated and preserved. No private reference store, draft reconstruction or repeated game-editorial pass is required.

## Two equivalent input paths

### Reviewed bundle

Supply an existing [publication contract 0.1.0](../architecture/publication-contract.md) bundle: `schemaVersion`, `purpose`, `records` and `publication`. This is the direct path for a producer already emitting that exchange format.

```sh
python3 tools/assemble_publication.py data/publication.json \
  --output dist/publication
```

`dist/publication` must not exist. A build never clears or overwrites an old directory. Select a fresh output location for the next build.

### Explicit record-file selection

For small independently authored records, replace the bundle's `records` array with `recordFiles`, a nonempty list of unique relative JSON paths. The other three fields are unchanged. This selection format is closed: no globs, discovery directories, optional private inputs or implicit latest-version resolution.

For example, the `recordFiles` value may be:

```json
[
  "records/nim-game-1.json",
  "records/nim-rulebook-1.json",
  "sources/selected-source/1.json"
]
```

Paths resolve beneath the selection file's directory. Each file contains one publication record, or a reviewed public Source envelope in the format produced by source promotion. Editorially original rules do not need a fabricated Source. The Source envelope is checked, and its enclosed Source is included in the bundle; private intake receipts are never exported.

The selection's `publication` is the existing complete Publication object, including exact Game defaults, record manifest hashes, source commit, release timestamp/owner and accepted release review. It is not a new approval format. The manifest must identify exactly the selected records. The assembler neither invents reviewers nor recalculates review digests to approve changed content. Release selection review is distinct from the already-completed review of game rules.

The resulting bundle sorts records by identity for stable serialization. It preserves the publication object, ordered rules/sections and review data exactly. A source file's formatting changes its input byte hash, while the record digest continues to use the contract's canonical JSON encoding.

## Explicit public assets only

Only the following file references are copied:

- `DefinitionPackage.files`;
- `VerificationRecord.suite` and optional `report`;
- `BuildArtifact.output`.

Their paths must begin with `sources/`, `evidence/`, `compiled/`, `suites/`, `reports/` or `artifacts/`. Each file must match its declared SHA-256, be a regular file and remain inside the input directory without symlinks. Files are bounded to 256 MiB each. Different records cannot assign different hashes to one asset path: use versioned or content-addressed paths for changed package sources.

Unlisted files are never read or copied, even when next to the selection. Repository tooling, raw-reference directories, private context and credentials are disallowed input paths. Publication validation checks the full reference graph, coverage and verification associations before output is written. Source metadata uses the existing public-locator restrictions.

Named files are explicitly public publication assets, not implicit permission to redistribute third-party references. Rights, confidentiality and release authorization still require the existing publication review. The assembler does not perform secret scanning or determine whether a source proves a rule. Reference capture permissions are not consulted because the private store is not a build input.

## Output for the site and downloads

| Path | Contents |
|---|---|
| `catalog.json` | Current discovery selection: Game title/pin, exact edition link and reading status, optional family/publisher metadata and recommended formalization pin |
| `records/<Kind>/<id>/<revision>.json` | Immutable record envelope with publication schema version and purpose |
| `records/BGSMRelease/<version>.json` | Exact model-release record envelope |
| `releases/<release-id>/bundle.json` | Complete validated exchange bundle with canonical compact JSON |
| `releases/<release-id>/manifest.json` | Existing reviewed Publication object with its exact record pins and hashes, wrapped with schema version/purpose |
| `releases/<release-id>/catalog.json` | Immutable copy of that release's discovery selection |
| `releases/<release-id>/<declared-asset-path>` | Exact source, compiled or verification bytes; bundle-relative links continue to resolve |
| `assembly.json` | Current assembly receipt: input byte inventory/digest, tool/runtime identity and output byte inventory |
| `releases/<release-id>/assembly.json` | Immutable copy of that assembly receipt |

Paths in catalog rows are relative to the public output root. The Astro renderer can load `catalog.json`, follow the selected record paths and render rule sections without parsing source PDFs or loading an interpreter. Stable rule IDs remain in RulebookEdition for page anchors in issue #5. Reading status and optional recommended formalization are distinct; a recommendation is not proof of executable verification.

The root catalog is the only mutable discovery alias. Package/model dependencies and downloads use exact pins. Record URLs are independent of the current release, and a change to a discovery default does not alter an older edition's bytes.

## Determinism and integrity

All JSON outputs use compact sorted-key UTF-8 encoding without a trailing newline. Arrays that have editorial meaning retain their order. No wall-clock build timestamp, absolute input location, environment credential or filesystem modification time enters output. The release timestamp comes from the supplied reviewed Publication.

Assembly format `0.1.0` is independent of publication schema `0.1.0`. The receipt contains:

- SHA-256 and size for each selected input file, plus a canonical digest of that input inventory;
- assembler version and hashes of its code, validation policy, schemas and dependency lock input;
- actual Python and validation dependency versions;
- SHA-256 and size for every output other than the current receipt and its identical archive copy.

Those two receipt files are excluded from their own inventory to avoid a self-hash cycle. The command returns their byte digest as `assemblyDigest`; retain it independently with the artifact. Older receipt copies are ordinary hashed outputs of subsequent releases. Identical inputs, prior artifact and tool/runtime versions produce identical bytes. Different runtimes are explicitly identified rather than silently treated as identical builds. File ownership, permissions and mtimes are not part of byte reproducibility.

## Preserve earlier releases

For every build after the first, supply the **actual previously published output directory** and its independently retained receipt digest:

```sh
python3 tools/assemble_publication.py data/publication.json \
  --previous "$PREVIOUS_PUBLICATION_DIRECTORY" \
  --previous-digest "$PREVIOUS_ASSEMBLY_DIGEST" \
  --output "$NEW_PUBLICATION_DIRECTORY"
```

The incoming Publication must pin the previous Publication ID/digest and retain historical records under the existing immutability rules. The assembler verifies the previous output's complete file inventory, archived publication chain, record URLs and assets before carrying them forward. It rejects unlisted files, changed old revisions and reused release IDs anywhere in that chain. Only the current catalog and root receipt are replaced in the new tree; the previous directory is untouched.

The builder stages the output and moves it into a new destination after successful validation/writes. Use one writer per destination and preserve the prior artifact until deployment succeeds. Build output is an artifact, not a deployment transaction.

**Current limit:** withdrawal packaging is rejected explicitly. Blindly retaining older bundles could republish a withdrawn payload. The later editorial/evolution work in issue #11 must define removal notices, historical download treatment and rights-sensitive removal before enabling that path. Ordinary additive revisions and default changes work now. This limitation does not prevent publishing the initial catalog.

## Try it now without inventing catalog data

The repository still contains developer fixtures rather than collected, published games. Use the explicit fixture opt-in for a local demonstration:

```sh
python3 tools/assemble_publication.py \
  tests/fixtures/publication/first-games.json \
  --output .cache/assembly/first-games-demo \
  --allow-fixtures
```

This produces separate chess, Nim and RPS records with fixture labels and preserves their distinct reading/formalization states. It does not publish them. Without the flag, fixture bundles are rejected. Do not deploy fixture output as collected catalog content.

Tests exercise both input paths, byte-identical repeat builds, source-envelope input, reference/coverage failures, corruption and path boundaries, old release retention, changed defaults and operation with no private reference configuration. CI runs them through the existing unit-test discovery; no hosting credentials or Sites integration are involved. The next browsing issue consumes this output in the existing Astro/Cloudflare plan.
