"""Validate publication shape, references and integrity; never execute game sources."""

import argparse
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import best_match

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schema/publication/0.1.0/bundle.schema.json"


class ContractError(ValueError):
    """A structurally or relationally invalid publication."""


def require(condition, message):
    if not condition:
        raise ContractError(message)


def digest(value):
    """Contract 0.1.0 JSON digest: sorted keys, compact UTF-8, no trailing newline."""
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def reviewed_digest(value):
    return digest({key: item for key, item in value.items() if key != "review"})


def load_json(path):
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    def invalid_number(value):
        raise ContractError(f"Non-JSON number: {value}")

    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=unique_object, parse_constant=invalid_number)


def key_for(record):
    if record["kind"] == "BGSMRelease":
        return ("BGSMRelease", record["version"])
    return (record["kind"], record["id"], record["revision"])


def manifest_entry(record):
    keys = ("kind", "version") if record["kind"] == "BGSMRelease" else ("kind", "id", "revision")
    return {key: record[key] for key in keys} | {"sha256": digest(record)}


def validate_bundle(bundle, root, *, allow_fixtures=False, previous=None):
    root = Path(root).resolve()
    schema = load_json(SCHEMA)
    Draft202012Validator.check_schema(schema)
    error = best_match(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(bundle))
    if error:
        location = "/".join(str(part) for part in error.absolute_path)
        raise ContractError(f"Schema error at {location or '/'}: violates {error.validator}")

    fixture = bundle["purpose"] == "contract-fixture"
    require(not fixture or allow_fixtures, "Contract fixtures require explicit --allow-fixtures; they are not publications")
    records = {}
    for record in bundle["records"]:
        key = key_for(record)
        require(key not in records, f"Duplicate record pin: {key}")
        require(bool(record.get("testOnly")) == fixture, f"Fixture marker mismatch: {key}")
        records[key] = record

    def resolve(kind, pin):
        key = (kind, pin) if kind == "BGSMRelease" else (kind, pin["id"], pin["revision"])
        require(key in records, f"Dangling {kind} pin: {key}")
        return records[key]

    def check_file(file):
        path = (root / file["path"]).resolve()
        require(path.is_relative_to(root) and path.is_file(), f"File must exist inside bundle root: {file['path']}")
        require(hashlib.sha256(path.read_bytes()).hexdigest() == file["sha256"], f"File digest mismatch: {file['path']}")

    def review(record):
        require(record["review"]["reviewedDigest"] == reviewed_digest(record), "Review digest mismatch")

    def citation(item):
        resolve("Source", item["source"])

    games = {r["id"] for r in records.values() if r["kind"] == "Game"}
    publisher_owners, game_identities, edition_owners = {}, {}, {}
    for record in records.values():
        kind = record["kind"]
        if "review" in record:
            review(record)
        if kind == "Game":
            require(len(json.dumps(record, ensure_ascii=False).encode()) <= 20 * 1024, "Game discovery record exceeds 20 KiB")
            edition = resolve("RulebookEdition", record["defaultEdition"])
            require(edition["gameId"] == record["id"], "Default edition belongs to another game")
            if "family" in record:
                resolve("GameFamily", record["family"])
            identity = record.get("publisherEdition", {}).get("id")
            if record["id"] in game_identities:
                require(game_identities[record["id"]] == identity, "Game revisions cannot switch publisher edition identity")
            game_identities[record["id"]] = identity
            if identity:
                publisher = resolve("PublisherEdition", record["publisherEdition"])
                require(publisher["gameId"] == record["id"], "Publisher edition belongs to another game")
        elif kind == "PublisherEdition":
            require(record["gameId"] in games, "Publisher edition has no game")
            prior = publisher_owners.setdefault(record["id"], record["gameId"])
            require(prior == record["gameId"], "Publisher edition identity cannot change games")
            citation(record["source"])
            if "predecessor" in record:
                older = resolve(kind, record["predecessor"])
                require(older["id"] != record["id"] and older["gameId"] != record["gameId"], "Publisher successor requires a distinct publisher edition and Game")
        elif kind == "RulebookEdition":
            require(record["gameId"] in games, "Rulebook edition has no game")
            prior = edition_owners.setdefault(record["id"], record["gameId"])
            require(prior == record["gameId"], "Rulebook lineage cannot change games")
            if "previous" in record:
                older = resolve(kind, record["previous"])
                require(older["id"] == record["id"] and older["revision"] < record["revision"], "Invalid rulebook predecessor")
            for item in record.get("origin", {}).get("citations", []):
                citation(item)
            rules, sections = set(), set()
            for section in record["sections"]:
                require(section["id"] not in sections, "Duplicate section ID")
                sections.add(section["id"])
                for rule in section["rules"]:
                    require(rule["id"] not in rules, "Duplicate rule ID within edition")
                    rules.add(rule["id"])
                    origin = rule.get("origin", record.get("origin"))
                    require(origin is not None, "Every rule needs an origin, directly or inherited from its edition")
                    for item in origin.get("citations", []):
                        citation(item)
        elif kind == "BGSMRelease":
            for concept in record["concepts"]:
                resolve("Concept", concept)
            for package in record["libraries"] + [record["conformance"]]:
                require(resolve("DefinitionPackage", package)["bgsm"] == record["version"], "BGSM package targets another release")
            if "previous" in record:
                require(record["previous"] != record["version"], "BGSM release cannot precede itself")
                resolve(kind, record["previous"])
        elif kind == "DefinitionPackage":
            resolve("BGSMRelease", record["bgsm"])
            files = [file["path"] for file in record["files"]]
            require(len(files) == len(set(files)), "Duplicate package file path")
            for file in record["files"]:
                check_file(file)
            exports = [entry["id"] for entry in record["exports"]]
            require(len(exports) == len(set(exports)), "Duplicate exported definition")
            for entry in record["exports"]:
                require(entry["file"] in files, "Export must name a declared source file")
            for dependency in record["dependencies"]:
                target = resolve(kind, dependency)
                require(target["bgsm"] == record["bgsm"], "Package dependency targets another BGSM release")
                require(target["language"] == record["language"], "Package dependency uses another language version")

    # Every publisher identity is reciprocated by its game; no second identity for that game.
    by_game = {}
    for identity, game in publisher_owners.items():
        require(game_identities.get(game) == identity, "Game and publisher edition identity links disagree")
        require(game not in by_game or by_game[game] == identity, "Game has multiple publisher identities")
        by_game[game] = identity

    def check_cycles(kind, edges):
        visited, active = set(), set()

        def visit(key):
            require(key not in active, f"Cyclic {kind} references")
            if key in visited:
                return
            active.add(key)
            for target in edges(records[key]):
                visit(key_for(target))
            active.remove(key)
            visited.add(key)

        for key in records:
            if key[0] == kind:
                visit(key)

    check_cycles("DefinitionPackage", lambda r: [resolve("DefinitionPackage", p) for p in r["dependencies"]])
    check_cycles("PublisherEdition", lambda r: [resolve("PublisherEdition", r["predecessor"])] if "predecessor" in r else [])
    check_cycles("BGSMRelease", lambda r: [resolve("BGSMRelease", r["previous"])] if "previous" in r else [])

    def package_closure(package):
        found = set()

        def visit(item):
            key = key_for(item)
            if key in found:
                return
            found.add(key)
            for pin in item["dependencies"]:
                visit(resolve("DefinitionPackage", pin))
        visit(package)
        return found

    def definition(link, allowed):
        package = resolve("DefinitionPackage", link["package"])
        require(key_for(package) in allowed, "Definition is outside package dependency closure")
        require(link["definition"] in {e["id"] for e in package["exports"]}, "Dangling exported definition")

    coverage_summary = {}
    for key, record in records.items():
        if record["kind"] != "Formalization":
            continue
        edition = resolve("RulebookEdition", record["edition"])
        model = resolve("BGSMRelease", record["bgsm"])
        package = resolve("DefinitionPackage", record["package"])
        require(package["bgsm"] == record["bgsm"] and package["language"] == record["language"], "Formalization/package BGSM or language mismatch")
        allowed = package_closure(package)
        definition({"package":record["package"], "definition":record["entry"]}, allowed)
        model_concepts = {(p["id"], p["revision"]) for p in model["concepts"]}
        rules = {rule["id"]: rule for section in edition["sections"] for rule in section["rules"]}
        rows = record["coverage"]
        require(len({row["rule"] for row in rows}) == len(rows), "Duplicate coverage row")
        require({row["rule"] for row in rows} == set(rules), "Coverage must account for every edition rule exactly once")
        for row in rows:
            for pin in row.get("concepts", []):
                resolve("Concept", pin)
                require((pin["id"], pin["revision"]) in model_concepts, "Coverage concept is absent from formalization BGSM release")
            for link in row.get("definitions", []):
                definition(link, allowed)
            if row["status"] == "outside-declared-scope":
                require(row["reason"] in record["scope"]["excludes"], "Outside-scope reason must be declared in formalization exclusions")
        statuses = {row["status"] for row in rows}
        # Outside-scope rows still prevent a complete-edition claim; no adjustable denominator.
        coverage_summary[key] = "complete" if statuses == {"represented"} else "partial" if statuses & {"represented", "partial"} else "unrepresented"

    for record in records.values():
        kind = record["kind"]
        if kind not in {"VerificationRecord", "BuildArtifact"}:
            continue
        formalization = resolve("Formalization", record["formalization"])
        field = "subjectDigest" if kind == "VerificationRecord" else "inputDigest"
        require(record[field] == digest(formalization), f"{kind} does not match its formalization digest")
        if kind == "VerificationRecord":
            check_file(record["suite"])
            if "report" in record:
                check_file(record["report"])
        else:
            check_file(record["output"])
            rules = {row["rule"] for row in formalization["coverage"]}
            allowed = package_closure(resolve("DefinitionPackage", formalization["package"]))
            for item in record["sourceMap"]:
                require(item["rule"] in rules, "Artifact source map names a missing rule")
                definition(item["definition"], allowed)

    publication = bundle["publication"]
    review(publication)
    require(publication["owner"] == publication["review"]["responsibleHuman"], "Publication owner must be its responsible human")
    require(fixture or publication["commit"] != "0" * 40, "Publication must identify a real commit")
    manifest = {}
    for entry in publication["manifest"]:
        key = key_for(entry)
        require(key not in manifest, "Duplicate manifest pin")
        manifest[key] = entry["sha256"]
    require(set(manifest) == set(records), "Manifest must list exactly the supplied records")
    for key, record in records.items():
        require(manifest[key] == digest(record), f"Manifest digest mismatch: {key}")
    selected = set()
    for pin in publication["games"]:
        game = resolve("Game", pin)
        require(game["id"] not in selected, "Publication selects multiple revisions of one game")
        selected.add(game["id"])
    recommended = set()
    for pin in publication.get("recommendedFormalizations", []):
        formalization = resolve("Formalization", pin)
        edition = resolve("RulebookEdition", formalization["edition"])
        require(edition["gameId"] in selected, "Recommended formalization belongs to an unselected game")
        edition_key = key_for(edition)
        require(edition_key not in recommended, "Multiple recommended formalizations for an edition")
        recommended.add(edition_key)
        # A recommendation is not executable verification; failed evidence prevents recommendation.
        for evidence in records.values():
            if evidence["kind"] == "VerificationRecord" and evidence["formalization"] == pin:
                require(evidence["result"] != "fail", "Cannot recommend a formalization with failed verification")

    if "previous" in publication:
        require(previous is not None, "Previous publication is required to validate history")
        require(publication["previous"] == {"id":previous["publication"]["id"], "sha256":digest(previous["publication"])}, "Previous publication pin mismatch")
    else:
        require(previous is None, "New publication must pin the supplied previous publication")
    withdrawals = {}
    for notice in publication.get("withdrawals", []):
        key = key_for(notice["record"])
        require(key not in withdrawals and key not in records, "Withdrawn record must be unique and omitted from current records")
        withdrawals[key] = notice["record"]["sha256"]
    require(not withdrawals or previous is not None, "Withdrawals need the previous publication")
    if previous is not None:
        require(bundle["purpose"] == previous["purpose"], "Cannot promote a fixture through publication history")
        require(publication["id"] != previous["publication"]["id"], "New publication needs a new release ID")
        old_records = {key_for(r):r for r in previous["records"]}
        old_withdrawals = {key_for(n["record"]):n["record"]["sha256"] for n in previous["publication"].get("withdrawals", [])}
        for key, sha in old_withdrawals.items():
            require(withdrawals.get(key) == sha, "Historical withdrawal notices must be retained")
        for key, old in old_records.items():
            if key in records:
                require(digest(old) == digest(records[key]), f"Immutable record changed: {key}")
            else:
                require(withdrawals.get(key) == digest(old), f"Historical record missing without withdrawal: {key}")
        for key, sha in withdrawals.items():
            require((key in old_records and digest(old_records[key]) == sha) or old_withdrawals.get(key) == sha, "Withdrawal does not identify a historical record")
    return {"records":len(records), "games":len(selected), "formalCoverage":{"/".join(map(str, key)):status for key, status in coverage_summary.items()}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--allow-fixtures", action="store_true")
    parser.add_argument("--previous", type=Path, help="Trusted previously validated publication, for immutability checks")
    args = parser.parse_args()
    try:
        result = validate_bundle(load_json(args.bundle), args.bundle.parent, allow_fixtures=args.allow_fixtures, previous=load_json(args.previous) if args.previous else None)
    except (ValueError, OSError) as error:
        parser.exit(1, f"Invalid publication: {error}\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
