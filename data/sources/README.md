# Reviewed public source records

Promoted source metadata belongs at `<source-id>/<revision>.json` under this directory. Each file contains a Source record, citations that pin that exact revision, and the public reviewer handle/time plus a digest of the reviewed proposal. The [reference contract](../../schema/reference/0.1.0/records.schema.json) defines the envelope; the Source itself uses publication contract 0.1.0.

This directory currently contains no collected source records. Contract examples remain in `tests/`; public metadata appears here only through explicit review and promotion. Do not place originals, extracts, acquisition records, private reviews, storage locations or backup manifests here.

Follow the [private intake and promotion procedure](../../docs/development/reference-intake.md). Repository checks validate public source records without opening a private store. Promotion stages repository data; it does not publish a website or complete a game's content task. The future assembler will select exact Source pins from these records.
