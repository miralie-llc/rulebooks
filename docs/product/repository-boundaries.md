# Repository and data policy

RuleBooks is intended for open development. The repository maintains the product's code, contracts, original content, work queues and contributor documentation. Private inputs and temporary authoring context are separate from that maintained project.

## Maintained material

| Material | Location and policy |
|---|---|
| Current architecture, decisions and active implementation plan | `docs/`; keep authoritative guidance current and retire completed planning |
| BGSM, original game definitions, schemas and executable examples | Product source/data paths; examples demonstrate supported behavior |
| Content wishlist and semantic gaps | `work/content/` and `work/semantic/`; versioned public-intended product data |
| Software tasks | Engineering plan or software issue tracker; separate from the product queues |
| Superseded proposals, exploratory prototypes and agent handoffs | Optional personal context outside the checkout; never a product dependency |
| Raw sources, purchased documents and extraction output | Restricted reference storage outside Git |
| Credentials and operational secrets | Credential manager; never authored into repository files |
| Caches and regenerable output | Ignored local/CI storage; approved releases retained separately by digest |

Public records cannot hide sensitive information behind an `internal` flag. Private workflow notes, if needed, belong in separate restricted storage keyed by a public record ID.

## Optional personal context

A developer may create a Git-ignored `LOCAL_CONTEXT.md` pointing to an external personal index. Agents can read that index for orientation and consult individual historical notes when relevant. The maintained project takes precedence. The pointer and its target may be absent or deleted at any time.

Builds, tests, public documentation links, queue evidence and release tooling must not depend on personal context. Do not put personal filesystem paths in committed files. Retain useful conclusions as self-contained current decisions or design principles, rather than links to private working history.

## Public contribution and release boundary

Treat a public push, pull request, CI log or preview as publication. Private drafts must be reviewed before reaching those surfaces.

- Give authors and agents only the inputs needed for their task, without production credentials or unattended publication authority.
- Review candidate files, commit messages and the full outgoing history. A clean final tree does not remove private content from earlier commits. Transfer private work as reviewed changes without bringing private draft history into public branches.
- Run credential checks before pushing; inspect sensitive filenames, personal information, internal URLs, embedded metadata and source permissions as well. Scanners do not establish that every sentence is suitable for publication.
- Build the site from explicit approved publication inputs in a clean output directory. Do not copy the checkout, work-queue drafts, private captures or build logs wholesale.
- Keep reports free of secret values. If a credential is exposed, revoke or rotate it and handle any history cleanup separately. See [GitHub's sensitive-data removal guidance](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository).

These are required workflow properties; the [implementation plan](implementation-plan.md) tracks the tooling needed to enforce them. `.gitignore` prevents accidental additions but does not restrict access, remove tracked files or prevent copying sensitive content into another file.

## Reference-storage contract

Raw reference material needs durable restricted storage, distinct from disposable personal context. Configure local access through a setting such as `RULEBOOKS_REFERENCE_ROOT`; keep credentials in the storage provider's credential mechanism. Public site builds should not require access to raw captures.

The ingestion pipeline must:

1. Assign a stable source ID and record the game/publisher edition, title, locator, acquisition method and use/redistribution status. Keep private procurement details separate.
2. Store original bytes immutably by digest with content type and acquisition time. Preserve distinct source editions.
3. Store extracted text/OCR with the original digest, extractor version, options and page/section anchors. Process untrusted documents without publication credentials.
4. Review source identity, extraction quality and permitted public use. Unknown redistribution status does not authorize copying source content into the public catalog.
5. Promote only reviewed Source metadata and citations into Git. Opaque capture IDs/digests may support authorized retrieval; public records must not contain signed URLs, credentials, private storage paths or purchaser identities.
6. Back up originals and private manifests and test retrieval. A digest is neither a backup nor redistribution permission.

Migrate any existing local captures by inventorying them, copying to durable storage, verifying checksums/counts and testing retrieval from another workspace before removing the local copy. The ignored `reference/` path is transitional local staging, not a durable or access-controlled store. Source citations must remain usable without a personal research directory.
