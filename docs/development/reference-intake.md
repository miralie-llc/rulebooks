# Private reference intake and public source promotion

The first intake implementation uses a restricted local/shared filesystem outside Git. The selected machine-specific location and shell configuration belong in private operational context. Set `RULEBOOKS_REFERENCE_ROOT` there; never commit its value. Cloud object storage is deferred.

The CLI is `python3 -m tools.references`. It never downloads documents, runs extractors, opens a browser or publishes a website. Supply already-acquired bytes and already-produced extracts. This keeps untrusted document parsing separate from storage and promotion. Test captures are synthetic and created in temporary directories; no test content enters the actual store or public data.

A companion collection workflow can supply a [versioned handoff manifest](reference-handoff.md) naming an original and ready derivatives in its own workspace. RuleBooks copies only the named, verified artifacts into its separate managed root; it does not reorganize the collector's folders or consume unlisted intermediates.

## Storage and access

Initialize a new or empty directory outside every Git checkout:

```sh
python3 -m tools.references init --access owner
python3 -m tools.references verify
```

Owner mode uses owner-only directories and read-only private objects. `--access group` uses the directory's existing group, setgid directories and group-readable objects for authorized operators sharing a filesystem. It requires membership in that group. Files are published into the store atomically; existing keys cannot be overwritten with different bytes by the CLI. No delete command is provided.

Owner/group modes require POSIX permissions to remove access for other users. Shared mounts must honor those permissions and map identities/groups consistently across machines. A CIFS/NFS mount name or VPC location does not itself prove access restriction. If initialization cannot establish restrictions, it stops before accepting records.

For a share already protected by server access controls, an operator may explicitly choose delegated access:

```sh
python3 -m tools.references init --access server-acl --accept-server-access-controls
```

This mode records reliance on existing server ACLs and client mount access rather than attempting to verify or change them. It does not claim POSIX isolation of local users or derive security from a VPC address. Use it only after the share owner confirms those controls. Path, object-type, no-overwrite and digest checks still apply. Backup and restore into another destination require the same confirmation flag for that destination; it is not inherited as an authorization to copy anywhere. Filesystem administrators and authorized writers remain trusted: hashes detect corruption but are not signatures, encryption or an immutable-storage service.

The directory contains:

| Location | Purpose |
|---|---|
| `.store.json` | Private store identity and access policy |
| `objects/sha256/<digest>` | Original and extracted bytes, deduplicated by SHA-256 |
| `captures/<capture-id>.json` | Source identity, edition, acquisition, rights status and original object pin |
| `extracts/<capture-id>/<extract-id>/<revision>.json` | Versioned extraction, exact original/predecessor digests, extractor/options and anchors |
| `reviews/<review-id>.json` | Accepted public proposal and exact capture/optional extract digests |
| `promotions/<promotion-id>.json` | Exact review, Source pin and exported-byte digest |
| `handoffs/<handoff-id>.json` | Sealed collector manifest, its digest and resulting capture/extract pins |

Records have their own integrity envelope. Capture/review/promotion IDs are opaque random IDs, not filenames or source URLs. Reacquiring identical bytes creates a distinct acquisition record while storing the bytes once. Different source editions remain distinct capture records even if they happen to have identical bytes. Intake objects are bounded to 256 MiB each in this first implementation.

## Capture metadata

Prepare metadata JSON in private storage, then ingest the original:

```sh
python3 -m tools.references capture --file "$ORIGINAL_FILE" --metadata "$PRIVATE_METADATA" --media-type application/pdf
```

The [reference schema](../../schema/reference/0.1.0/records.schema.json) defines `captureMetadata`:

- `sourceId`: stable public Source identity; `gameId`: the game/candidate being researched.
- `publisherEdition`, when applicable, names the game's publisher edition. `sourceEdition` separately records this document's edition label or explicit unknown. FIDE's source edition does not invent a publisher edition for chess.
- `title`, acquisition `method`/`acquiredAt`, and optional `privateLocator`/`privateNote`.
- `redistribution.status`: `unknown`, `restricted` or `permitted`; permitted requires a recorded basis.

Acquisition details, receipts, signed retrieval URLs and purchaser information stay private. Unknown rights do not prevent retaining a source identity or preparing metadata-only citations; they never authorize copying original/extracted content into the public repository. Source use still needs human review under the [repository policy](../product/repository-boundaries.md).

The command prints only the capture ID and digest. It does not echo the original path or private metadata. Retain private intake requests and receipts according to the operator's retention policy; public builds never need them.

## Versioned extraction and citation anchors

Run the chosen parser/OCR tool separately without publication credentials. Review its output and record its exact version/options. Submit the output as data:

```sh
python3 -m tools.references extract --capture "$CAPTURE_ID" --file "$EXTRACT_FILE" --metadata "$PRIVATE_EXTRACT_METADATA"
```

`extractMetadata` requires an ID, positive integer revision, extractor name/version/options and anchors. Each anchor has a readable `locator`, inclusive `startByte`, exclusive `endByte`, and optional page number. Bounds are offsets into the stored extract bytes, not the PDF's bytes or Unicode character positions. They must be nonempty and within the extract. The locator should also identify the source provision/page for human review.

Revision 2 requires revision 1, and so on; prior outputs remain intact. The original capture digest and previous extract-record digest are fixed. Updating an extractor creates a new extract revision, not a new source edition or an overwrite. This establishes reproducibility inputs; it does not prove OCR accuracy or execute an extractor during validation.

## Review and public promotion

Prepare a separate private proposal containing only `source` and `citations`. The Source must match publication contract 0.1.0 and the capture's Source ID/document edition. Citations pin that exact Source revision and provide a locator. No acquisition fields are copied automatically.

Review source identity, the public title/author/URL, citations, reuse claims and the selected extraction. Use a consenting public reviewer handle, not a private account identifier or email. Record the acceptance explicitly:

```sh
python3 -m tools.references review --capture "$CAPTURE_ID" --proposal "$PRIVATE_SOURCE_PROPOSAL" --reviewer "$PUBLIC_REVIEWER" --extract-id "$EXTRACT_ID" --revision 1 --accept-public-metadata
```

Omit both extract arguments if review is based directly on the original. With a selected extract, each citation locator must exist in its anchors. The stored acceptance binds the exact capture, proposal and extract digests. A newer extract does not silently replace the reviewed version. The CLI records the operator's assertion of human review; it does not authenticate a human identity or supply the later editorial approval service.

Promotion requires an accepted review ID:

```sh
python3 -m tools.references promote --review "$REVIEW_ID" --output "data/sources/$SOURCE_ID/$SOURCE_REVISION.json"
```

The output contains only `schemaVersion`, `source`, `citations`, and public reviewer/time/proposal digest. It is checked again at promotion. Private acquisition details, raw bytes, extract text, private paths and capture/review IDs are omitted. A private receipt links the output digest back to its review. Existing public revisions cannot be overwritten with different bytes; corrections require a new Source revision and new review.

The first promotion policy accepts canonical HTTPS URLs without user credentials, query parameters, private/local hosts or filesystem/storage locators. Use a stable query-free public landing URL with citation locators when a download URL is signed. If an authoritative source genuinely requires a query URL, extend the reviewed policy deliberately rather than silently stripping parameters and changing its identity. Public fields remain subject to human confidentiality review and the pre-push credential scan; pattern checks cannot recognize every private fact.

Run [contribution checks](contribution-checks.md) before committing/pushing. CI validates promoted files and their exact filename/ID/revision using only public schemas and data. Private storage and credentials are not CI inputs. An assembler can consume the enclosed Source while preserving its pin; it must not copy this whole checkout or private storage into release output.

## Authorized retrieval and recovery

Retrieve originals or exact extract revisions only to a restricted directory outside Git and outside the store. Existing output files are never overwritten:

```sh
python3 -m tools.references retrieve --capture "$CAPTURE_ID" --output "$PRIVATE_ORIGINAL_COPY"
python3 -m tools.references retrieve --capture "$CAPTURE_ID" --extract-id "$EXTRACT_ID" --revision 1 --output "$PRIVATE_EXTRACT_COPY"
python3 -m tools.references verify
```

Access is controlled by filesystem identities/groups; the CLI also rejects permissive modes, symlinks, traversal, hash mismatches and unexpected entry types. No application token or cloud credential is used. Confirm access from each authorized host before relying on shared operation; a same-process test does not establish cross-host access control.

Pause writers while making a backup snapshot:

```sh
python3 -m tools.references backup --output "$NEW_PRIVATE_BACKUP_DIRECTORY"
python3 -m tools.references restore --backup "$PRIVATE_BACKUP_DIRECTORY" --output "$NEW_PRIVATE_RESTORE_DIRECTORY" --expected-digest "$RECORDED_BACKUP_DIGEST"
```

Backup verifies records and objects, copies them to a new restricted directory and records a complete file/digest inventory. Record the returned backup digest independently. Restore requires that expected digest, verifies all bytes and references, and writes to a new directory. Symlinks, unexpected inventory entries, corrupt bytes and nonempty destinations fail. Retained reviews and extraction revisions restore with their original identities. Partial staging directories are cleaned up on failure; existing stores are not replaced.

Automated tests rehearse retrieval and backup/restore with synthetic originals, two extract revisions, reviews and promotions. They also test unauthorized identities, corruption and path boundaries. Tests use system temporary storage outside Git; select an external `TMPDIR` if the default temporary directory is itself a checkout.

This supplies recovery tooling, not scheduled/off-device backups. A directory called backups, a mounted share, or a second folder on the same volume is not evidence of an independent recoverable copy. The operator must select a separate backup destination, schedule copies, preserve its access controls and rehearse retrieval from another authorized system before removing source staging.

## Migrate existing captures without losing evidence

1. Inventory the existing staging files privately: relative path, byte size, SHA-256, and classification as original, extract, script or temporary output. Do not commit that inventory.
2. Identify each original's Source ID/document edition, game/publisher edition where applicable, acquisition and rights status. Unknown values stay explicitly unknown; don't invent metadata to finish a batch.
3. Capture original bytes and compare the returned hash with the inventory. Register extracted outputs with actual extractor/version/options and anchors; keep unverified historical extracts private until their provenance is understood.
4. Run store verification, make an independent backup and restore it to a fresh restricted location. Compare object hashes/counts and retrieve selected originals and exact extract revisions from another authorized host/workspace.
5. Review and promote only public metadata/citations. Confirm a clean checkout validates without the store or personal context.
6. Only after these checks and an explicit cleanup decision remove obsolete staging copies. The intake tool does not delete the original inputs or migrate speculative content into the work queues.
