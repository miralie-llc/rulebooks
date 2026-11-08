"""Check maintained paths, Markdown links and queue evidence in an exact candidate."""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import posixpath
import re
import subprocess
import sys
import tempfile
import unicodedata
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit

from markdown_it import MarkdownIt
from jsonschema import ValidationError

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.prepare_site import preview_catalog
from tools.references.contracts import validate_public_source
from tools.validate_knowledge import validate_fixture as validate_knowledge_fixture

if __package__:
    from .input_policy import repository_path_problem
    from .validate_work import validate_records
    from .validate_publication import load_json, validate_bundle
else:
    from input_policy import repository_path_problem
    from validate_work import validate_records
    from validate_publication import load_json, validate_bundle

ROOT = Path(__file__).resolve().parents[1]


class CheckError(ValueError):
    pass


def git(root, *args):
    process = subprocess.run(["git", "-c", "core.quotePath=false", *args], cwd=root, capture_output=True)
    if process.returncode:
        raise CheckError("Git query failed; check the repository, revision and full local history")
    return process.stdout


def commit_id(root, revision):
    value = git(root, "rev-parse", "--verify", "--end-of-options", revision + "^{commit}").decode().strip()
    if not re.fullmatch(r"[a-f0-9]{40}", value):
        raise CheckError("Expected a full commit ID")
    return value


def snapshot(root, candidate="working", revision="HEAD"):
    root = Path(root).resolve()
    entries = []
    if candidate == "head":
        commit = commit_id(root, revision)
        for line in git(root, "ls-tree", "-rz", commit).split(b"\0"):
            if line:
                info, raw_name = line.split(b"\t", 1)
                mode, kind, blob = info.decode().split()
                entries.append((raw_name.decode(), mode, blob))
    elif candidate == "index":
        for line in git(root, "ls-files", "--stage", "-z").split(b"\0"):
            if line:
                info, raw_name = line.split(b"\t", 1)
                mode, blob, stage = info.decode().split()
                if stage != "0":
                    raise CheckError("Resolve index conflicts before review")
                entries.append((raw_name.decode(), mode, blob))
    elif candidate == "working":
        names = git(root, "ls-files", "--cached", "--others", "--exclude-standard", "-z").decode().split("\0")
        for name in sorted(set(filter(None, names))):
            path = root / name
            if not path.exists() and not path.is_symlink():
                continue  # A working-tree deletion is not in the candidate.
            entries.append((name, "100644" if path.is_file() and not path.is_symlink() else "unsupported", None))
    else:
        raise CheckError("Unknown candidate mode")
    result = {}
    for name, mode, blob in entries:
        problem = repository_path_problem(name)
        if problem:
            raise CheckError(f"Rejected repository path ({problem}): {name}")
        path = root / name
        if mode not in {"100644", "100755"}:
            raise CheckError(f"Symlinks/submodules/non-files are not review inputs: {name}")
        if blob is None:
            if not path.resolve().is_relative_to(root) or any(p.is_symlink() for p in path.parents if p != root and root in p.parents):
                raise CheckError(f"Symlink/path escape: {name}")
            data = path.read_bytes()
        else:
            data = git(root, "cat-file", "blob", blob)
        result[name] = data
    return result


def inventory(files):
    entries = [{"path":name, "sha256":hashlib.sha256(data).hexdigest()} for name, data in sorted(files.items())]
    digest = hashlib.sha256(json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {"sha256":digest, "files":entries}


def export_files(files, root):
    for name, data in files.items():
        path = Path(root) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


class HTMLLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.anchors = [], set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        for key in ["href", "src"]:
            if key in attrs:
                self.links.append(attrs[key])
        for key in ["id", "name"]:
            if attrs.get(key):
                self.anchors.add(attrs[key])


def markdown_references(data):
    parser = MarkdownIt("commonmark").enable(["table", "strikethrough"])
    tokens = parser.parse(data.decode("utf-8"))
    links, anchors, counts = [], set(), {}
    html = HTMLLinks()
    for index, token in enumerate(tokens):
        if token.type == "heading_open":
            heading = tokens[index + 1]
            text = "".join(t.content for t in (heading.children or []) if t.type in {"text", "code_inline", "image"})
            slug = "".join(c for c in text.lower() if c in "-_ " or unicodedata.category(c)[0] in "LNM")
            slug = slug.replace(" ", "-")
            number = counts.get(slug, 0)
            candidate = f"{slug}-{number}" if number else slug
            while candidate in anchors:
                number += 1
                candidate = f"{slug}-{number}"
            counts[slug] = number + 1
            anchors.add(candidate)
        if token.type == "html_block":
            html.feed(token.content)
        for child in token.children or []:
            if child.type == "link_open":
                links.append(child.attrGet("href"))
            elif child.type == "image":
                links.append(child.attrGet("src"))
            elif child.type == "html_inline":
                html.feed(child.content)
    return links + html.links, anchors | html.anchors


def check_links(files):
    documents = {name:markdown_references(data) for name, data in files.items() if name.endswith(".md")}
    directories = {str(parent) for name in files for parent in PurePosixPath(name).parents}
    checked = 0
    for name, (links, _) in documents.items():
        for href in links:
            parts = urlsplit(href)
            if parts.scheme in {"http", "https", "mailto"} or parts.netloc:
                continue  # External availability is a separate task; never fetch from CI.
            if parts.scheme or parts.path.startswith("/") or "\\" in unquote(parts.path):
                raise CheckError(f"Unsupported local link in {name}")
            target = posixpath.normpath(posixpath.join(posixpath.dirname(name), unquote(parts.path))) if parts.path else name
            if target.startswith("../") or target not in files and target not in directories:
                raise CheckError(f"Broken/unpublished local link in {name}: {target}")
            fragment = unquote(parts.fragment)
            if fragment:
                doc = target
                if doc in directories:
                    doc = posixpath.join(doc, "README.md")
                if doc in documents:
                    if fragment not in documents[doc][1]:
                        raise CheckError(f"Missing Markdown anchor in {name}: {target}#{fragment}")
                elif not re.fullmatch(r"L[1-9][0-9]*(?:-L[1-9][0-9]*)?", fragment):
                    raise CheckError(f"Unsupported file fragment in {name}: {target}")
            checked += 1
    return checked


def validate_candidate(files):
    links = check_links(files)
    with tempfile.TemporaryDirectory(prefix="rulebooks-check-") as directory:
        root = Path(directory)
        export_files(files, root)
        records = [(root / name, json.loads(data)) for name, data in sorted(files.items()) if name.startswith("work/") and name.endswith(".json")]
        if not records:
            raise CheckError("No product work records in candidate")
        try:
            count = validate_records(records, root=root)
        except ValidationError as error:
            raise CheckError(f"Work record violates {error.validator}; inspect it locally") from None
        fixtures = 0
        for path in sorted((root / "tests/fixtures/publication").glob("*.json")):
            bundle = load_json(path)
            if bundle.get("purpose") != "contract-fixture":
                raise CheckError("Persisted publication fixtures must be explicitly marked as test data")
            validate_bundle(bundle, path.parent, allow_fixtures=True)
            fixtures += 1
        catalog = root / "data/catalog/catalog.json"
        if catalog.exists():
            preview_catalog(catalog)
        sources = 0
        knowledge_fixtures = 0
        for path in sorted((root / 'tests/fixtures/knowledge').glob('*/draft.json')):
            validate_knowledge_fixture(path.parent)
            knowledge_fixtures += 1
        for name, data in files.items():
            if name.endswith('.json'):
                value = json.loads(data)
                if isinstance(value, dict) and value.get('kind') in {'GameKnowledgeDraft', 'GameKnowledgeReview', 'KnowledgePromotionTrace'}:
                    if not name.startswith('tests/fixtures/knowledge/') or not value.get('testOnly'):
                        raise CheckError('Private knowledge drafts/reviews/traces are not repository content')
        for path in sorted((root / "data/sources").rglob('*.json')):
            value = validate_public_source(load_json(path))
            source = value['source']
            expected = root / 'data/sources' / source['id'] / (str(source['revision']) + '.json')
            if path != expected:
                raise CheckError('Public source filename must match its exact Source ID/revision')
            sources += 1
    return {"files":len(files), "localLinks":links, "workRecords":count, "publicationFixtures":fixtures, "publicSources":sources, "knowledgeFixtures":knowledge_fixtures}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", choices=["working", "index", "head"], default="working")
    args = parser.parse_args()
    try:
        result = validate_candidate(snapshot(ROOT, args.candidate))
    except (ValueError, OSError) as error:
        parser.exit(1, f"Repository checks failed: {error}\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
