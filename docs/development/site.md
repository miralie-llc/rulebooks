# Astro catalog and rulebook browsing

The site is a static Astro application in this repository. It reads validated public records at build time. Browsing never reads the private reference store, parses PDFs, invokes a compiler or requires a database.

## Run locally

Use Node 22.23.4 and Python 3.11 with the pinned validation dependencies:

```sh
python3 -m pip install -r tools/requirements-ci.txt
npm ci --ignore-scripts --no-audit --no-fund
npm run dev
```

Open `http://127.0.0.1:4321`. Set `RULEBOOKS_PYTHON` to a virtual environment's Python executable if needed. The wrapper prepares the catalog before starting Astro. Restart after editing catalog JSON; Astro watches layout/style changes normally.

```sh
npm run build
npm run test:site
npm run preview
```

`dist/` is the static deployable output. `.cache/site-generated/` contains disposable prepared inputs; both are ignored. No hosting credentials are needed. CI builds and checks the site; Cloudflare upload, protected promotion and monitoring remain [issue #12](https://github.com/miralie-llc/rulebooks/issues/12).

## Two explicit input modes

The default [catalog](../../data/catalog/catalog.json) selects small, newly authored game records. These are **editorial previews**, not contract fixtures or accepted publications. The preview validator reuses publication 0.1.0 record shapes, omits acceptance review, rejects `review` and `testOnly` fields, checks attribution and exact relationships, and supports only readable catalog entities. It does not change the publication contract or accept formalization records.

Every preview page labels its status and carries `noindex, nofollow`; downloaded records carry `purpose: editorial-preview`. The catalog records actual authorship. Approval is never inferred from a successful build. Preview URLs and revisions are provisional until accepted in a publication.

| Game | Current readable data | Remaining content work |
|---|---|---|
| Nim | Complete within two exact configurations: heaps 3/4/5 and 1/2, normal-play ending | Editorial/source acceptance |
| Rock-paper-scissors | Complete one-round casual profile, including ties and invalid reveals | Editorial/source acceptance; this deliberately differs from WRPSA match procedures |
| Chess | Partial FIDE 2023 introduction with exact article citations | Full baseline, including movement and special moves, then acceptance |

No entry currently claims BGSM mapping or executable verification. Source documents and original editorial choices are distinguished per rule. Nothing under `tests/fixtures/` populates the default site.

For a reviewed release, use [the assembler](publication-assembly.md), then pass its output and the independently retained receipt digest:

```sh
npm run build -- --publication .cache/publication --digest "$ASSEMBLY_SHA256"
```

This verifies the entire assembly and rejects fixtures. Pages use the selected Game pins, while historical rulebook/source records remain available at exact revision URLs. Original public JSON and assets are copied unchanged under `/data/`, including archived releases; no private captures or work queues are copied. Upstream teams may supply already-reviewed records directly; the optional reference-intake and draft-knowledge workflows are not prerequisites.

## Routes and changes

- `/`: searchable library with readable-coverage filters.
- `/games/{id}/`: selected default rulebook for a game.
- `/editions/{id}/{revision}/#rule-{ruleId}`: pinned rulebook and stable rule links.
- `/families/{id}/`: related games, including distinct publisher editions when supplied.
- `/sources/{id}/{revision}/`: source identity, edition and citation usage.
- `/data/records/{kind}/{id}/{revision}.json`: exact structured record.

Publisher editions are displayed only when recorded; a RuleBooks revision is always labeled separately. A new profile gets its own rulebook identity; a corrected accepted rulebook gets a new revision and preserves earlier URLs. Discovery follows the publication manifest, not whichever revision happens to be numerically highest.

To add preview content, author records under `data/catalog/records/`, list them in `catalog.json`, and select each Game's exact revision in `games`. Every rule needs a resolvable source citation or original editorial attribution. Source URLs must pass the same public-source policy used by intake. Do not copy review metadata or confidential research into this catalog. Update the relevant [content task](../../work/README.md); acceptance and formalization remain separate milestones.

## Verification

Python checks validate catalog boundaries, source/default pins, provenance, preview labeling, and retention of verified historical downloads. Site tests inspect the built routes, rule anchors, local links/assets, scope labels and JSON downloads. CI also runs repository checks and credential scans. Manual browser checks cover search, reset, native profile selection, keyboard navigation and narrow-screen reading. Content completeness and source interpretation still require editorial judgment.

## BGSM and vocabulary explorer

`/bgsm/` lists accepted model releases supplied by the verified publication, including historical records. `/bgsm/{version}/` renders release changes, status at publication, capabilities, libraries and conformance-package pins. `/bgsm/{version}/concepts/{id}/` renders the exact concept revision selected by that release, its laws/examples and reverse links to exact rule usages. Rule pages link back through their formalization coverage. Release membership and coverage do not establish runtime implementation or successful verification.

The default catalog has no accepted BGSM release or invented concept mappings. `/vocabulary/0.2/` instead projects the maintained editorial vocabulary's tables, explicitly labeled as a mutable editorial draft rather than executable semantics. Only that maintained file supplies these definitions; personal research and context are never read. A future accepted model is populated by the existing publication contract, without changing these routes or guessing meaning from terminology.

## Search, coverage and downloads

`/search/` searches game titles/aliases/scopes, exact BGSM concepts and editorial vocabulary with distinct type/status labels. `/editions/{id}/{revision}/coverage/` separates reading completeness, individual rule mappings, and verification method/result/scope/bounds. It does not turn a represented rule or passing structural check into a claim of executable completeness.

`/data/discovery/games/{id}.json` contains only discovery metadata and coverage counts. The build rejects an individual discovery record exceeding 20 KiB and records measured sizes in `/data/discovery/budget.json`. Expanded records and evidence stay separate. `/downloads/` links the actual emitted files, with byte counts and SHA-256 values; `/data/downloads.json` is the machine-readable inventory (excluding itself). In reviewed mode, the original assembler manifests, receipts, source packages and artifacts remain unchanged. A hash from the same site identifies bytes; the independently retained assembly digest remains the trust anchor.

`/gaps/` publishes only explicit selections from [data/site/gaps.json](../../data/site/gaps.json). Each selection pins a semantic work item's exact byte hash. The work must be in review or done, target an actual rulebook revision and include that exact record as evidence. The public projection keeps its status and selected evidence fields. An empty list is intentional until modeling produces an evidenced limitation. Missing formalizations never create gaps automatically. Changing selected work requires reviewing and updating its digest.
