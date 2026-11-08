"""Assemble reviewed publication data into a deterministic, standalone public tree."""

import argparse
import copy
import hashlib
from importlib.metadata import version as package_version
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import tempfile

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.input_policy import publication_path_problem
from tools.references.contracts import validate_proposal, validate_public_source
from tools.validate_publication import (
    ROOT, ContractError, digest, key_for, require, validate_bundle,
)

VERSION = '0.1.0'
ASSET_ROOTS = {'sources', 'evidence', 'compiled', 'suites', 'reports', 'artifacts'}
HASH = re.compile(r'^[a-f0-9]{64}$')
SLUG = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
MAX_BYTES = 256 * 1024 * 1024
TOOL_FILES = (
    'tools/assemble_publication.py', 'tools/validate_publication.py',
    'tools/input_policy.py', 'tools/references/contracts.py', 'tools/requirements-ci.txt',
    'schema/publication/0.1.0/bundle.schema.json', 'schema/reference/0.1.0/records.schema.json',
)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def parse(data):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'Duplicate JSON key in assembly input')
            result[key] = value
        return result
    def invalid(_):
        raise ContractError('Non-finite JSON number in assembly input')
    return json.loads(data, object_pairs_hook=pairs, parse_constant=invalid)


def directory(path):
    path = Path(path).absolute()
    require(path == path.resolve(), 'Assembly paths must not traverse symlinks or parent segments')
    return path


def safe_name(name):
    require(isinstance(name, str) and publication_path_problem(name) is None, 'Disallowed assembly path')
    return name


def read_file(root, name):
    """Read a named regular file only; no directory discovery or symlink traversal."""
    safe_name(name)
    parts = PurePosixPath(name).parts
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        with os.fdopen(os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd), 'rb') as stream:
            require(stat.S_ISREG(os.fstat(stream.fileno()).st_mode), 'Assembly input must be a regular file')
            data = stream.read(MAX_BYTES + 1)
            require(len(data) <= MAX_BYTES, 'Assembly input exceeds 256 MiB')
            return data
    finally:
        os.close(fd)


def file_inventory(files):
    return [{'path': name, 'sha256': sha(data), 'size': len(data)} for name, data in sorted(files.items())]


def tool_identity():
    return {'name': 'rulebooks-publication-assembler', 'version': VERSION,
            'python': '.'.join(map(str, sys.version_info[:3])),
            'dependencies': {name: package_version(name) for name in ('jsonschema', 'referencing', 'attrs', 'jsonschema-specifications', 'rpds-py')},
            'files': file_inventory({name: (ROOT / name).read_bytes() for name in TOOL_FILES})}


def asset_pins(bundle):
    pins = {}
    for record in bundle['records']:
        kind = record.get('kind')
        entries = record.get('files', []) if kind == 'DefinitionPackage' else []
        if kind == 'VerificationRecord':
            entries = [record['suite']] + ([record['report']] if 'report' in record else [])
        if kind == 'BuildArtifact':
            entries = [record['output']]
        for entry in entries:
            name = safe_name(entry['path'])
            require(PurePosixPath(name).parts[0] in ASSET_ROOTS, 'Publication asset needs an allowed source/evidence/compiled directory')
            require(name not in pins or pins[name] == entry['sha256'], 'Conflicting digests for one asset path')
            pins[name] = entry['sha256']
    return pins


def load_input(path):
    path = Path(path).absolute()
    root = directory(path.parent)
    raw = read_file(root, path.name)
    selection = parse(raw)
    require(isinstance(selection, dict), 'Publication input must be an object')
    inputs = {path.name: raw}
    if 'recordFiles' in selection:
        require(set(selection) == {'schemaVersion', 'purpose', 'recordFiles', 'publication'}, 'Invalid record-file selection fields')
        names = selection['recordFiles']
        require(isinstance(names, list) and names and all(isinstance(n, str) and n.endswith('.json') for n in names), 'Select explicit JSON record files')
        require(len(names) == len(set(names)) and path.name not in names, 'Duplicate or recursive record-file selection')
        records = []
        for name in names:
            data = read_file(root, name)
            inputs[name] = data
            value = parse(data)
            if isinstance(value, dict) and set(value) == {'schemaVersion', 'source', 'citations', 'review'}:
                value = validate_public_source(value)['source']
            records.append(value)
        bundle = {k: copy.deepcopy(v) for k, v in selection.items() if k != 'recordFiles'}
        bundle['records'] = records
    else:
        require(set(selection) == {'schemaVersion', 'purpose', 'records', 'publication'}, 'Invalid publication bundle fields')
        bundle = selection
    require(isinstance(bundle['records'], list) and all(isinstance(r, dict) and 'kind' in r for r in bundle['records']), 'Invalid publication records')
    assets = {}
    for name, expected in asset_pins(bundle).items():
        data = read_file(root, name)
        require(sha(data) == expected, 'Publication asset digest mismatch')
        assets[name] = data
        inputs[name] = data
    return root, bundle, assets, file_inventory(inputs)


def validate_snapshot(bundle, assets, *, previous=None, allow_fixtures=False):
    # Validate exactly the bytes we read, not a second mutable view of the inputs.
    with tempfile.TemporaryDirectory(prefix='rulebooks-assembly-validation-') as temporary:
        root = Path(temporary)
        for name, data in assets.items():
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        result = validate_bundle(bundle, root, previous=previous, allow_fixtures=allow_fixtures)
    # Deliberately fictional URLs are allowed only in explicitly opted-in fixtures.
    # Production inputs retain the same public-source policy as direct promotion.
    for source in (r for r in bundle['records'] if r['kind'] == 'Source' and bundle['purpose'] == 'publication'):
        public = {k: v for k, v in source.items() if k != 'testOnly'}
        validate_proposal({'source': public, 'citations': [{'source': {'id': source['id'], 'revision': source['revision']}, 'locator': 'Public source metadata'}]})
    return result


def record_path(record):
    parts = key_for(record)
    return 'records/' + '/'.join(map(str, parts)) + '.json'


def catalog(bundle):
    records = {key_for(r): r for r in bundle['records']}
    games = []
    recommendations = {}
    for pin in bundle['publication'].get('recommendedFormalizations', []):
        formal = records[('Formalization', pin['id'], pin['revision'])]
        recommendations[(formal['edition']['id'], formal['edition']['revision'])] = formal
    for pin in bundle['publication']['games']:
        game = records[('Game', pin['id'], pin['revision'])]
        edition = records[('RulebookEdition', game['defaultEdition']['id'], game['defaultEdition']['revision'])]
        row = {'game': pin, 'title': game['title'], 'record': record_path(game),
               'edition': {**game['defaultEdition'], 'record': record_path(edition), 'label': edition['label'], 'readingStatus': edition['readingStatus']}}
        for name in ('family', 'publisherEdition', 'aliases', 'tags'):
            if name in game:
                row[name] = copy.deepcopy(game[name])
        formal = recommendations.get((edition['id'], edition['revision']))
        if formal:
            row['recommendedFormalization'] = {'id': formal['id'], 'revision': formal['revision'], 'record': record_path(formal)}
        games.append(row)
    return {'schemaVersion': bundle['schemaVersion'], 'assemblyVersion': VERSION, 'purpose': bundle['purpose'],
            'release': {'id': bundle['publication']['id'], 'manifest': 'releases/'+bundle['publication']['id']+'/manifest.json'},
            'games': sorted(games, key=lambda row: row['game']['id'])}


def output_name(name):
    safe_name(name)
    require(name == 'catalog.json' or PurePosixPath(name).parts[0] in {'records', 'releases'}, 'Unexpected public output path')


def verify_assembly(path, expected_digest, *, allow_fixtures=False):
    """Verify an independently pinned prior build, including its publication chain."""
    root = directory(path)
    require(isinstance(expected_digest, str) and HASH.fullmatch(expected_digest), 'Previous assembly requires an expected SHA-256')
    raw = read_file(root, 'assembly.json')
    require(sha(raw) == expected_digest, 'Previous assembly receipt digest mismatch')
    receipt = parse(raw)
    require(set(receipt) == {'assemblyVersion', 'schemaVersion', 'purpose', 'releaseId', 'inputs', 'inputDigest', 'tool', 'files'}, 'Invalid assembly receipt fields')
    require(receipt['assemblyVersion'] == VERSION and receipt['schemaVersion'] == '0.1.0', 'Unsupported prior assembly version')
    identifier = receipt['releaseId']
    require(isinstance(identifier, str) and SLUG.fullmatch(identifier), 'Invalid prior release ID')
    require(isinstance(receipt['inputs'], list) and digest(receipt['inputs']) == receipt['inputDigest'], 'Prior input inventory digest mismatch')
    archive_name = 'releases/'+identifier+'/assembly.json'
    require(read_file(root, archive_name) == raw, 'Prior archived assembly receipt mismatch')
    files = {}
    require(isinstance(receipt['files'], list), 'Invalid assembly output inventory')
    for entry in receipt['files']:
        require(isinstance(entry, dict) and set(entry) == {'path', 'sha256', 'size'}, 'Invalid assembly output entry')
        name = entry['path']
        output_name(name)
        require(name not in files and name != archive_name, 'Duplicate/self-referencing assembly inventory')
        data = read_file(root, name)
        require(sha(data) == entry['sha256'] and len(data) == entry['size'], 'Prior output digest/size mismatch')
        files[name] = data
    # Reject a contaminated previous output rather than carrying unlisted files forward.
    actual = set()
    for item in root.rglob('*'):
        require(not item.is_symlink(), 'Symlink in prior assembly')
        if item.is_file():
            actual.add(item.relative_to(root).as_posix())
        else:
            require(item.is_dir(), 'Non-regular entry in prior assembly')
    require(actual == set(files) | {'assembly.json', archive_name}, 'Prior assembly has missing or unlisted files')
    files[archive_name] = raw
    visited = set()
    def validate_release(release_id):
        require(release_id not in visited, 'Cyclic publication history')
        visited.add(release_id)
        prefix = 'releases/'+release_id+'/'
        require(prefix+'bundle.json' in files, 'Missing historical publication')
        bundle = parse(files[prefix+'bundle.json'])
        previous = validate_release(bundle['publication']['previous']['id']) if 'previous' in bundle['publication'] else None
        assets = {name: files[prefix+name] for name in asset_pins(bundle)}
        validate_snapshot(bundle, assets, previous=previous, allow_fixtures=allow_fixtures)
        require(bundle['publication']['id'] == release_id and bundle['purpose'] == receipt['purpose'], 'Prior release identity/purpose mismatch')
        require(not bundle['publication'].get('withdrawals'), 'Withdrawal packaging requires an explicit removal policy')
        for record in bundle['records']:
            expected = canonical({'schemaVersion': bundle['schemaVersion'], 'purpose': bundle['purpose'], 'record': record})
            require(files.get(record_path(record)) == expected, 'Historical record URL/content mismatch')
        expected_manifest = canonical({'schemaVersion': bundle['schemaVersion'], 'purpose': bundle['purpose'], 'publication': bundle['publication']})
        require(files.get(prefix+'manifest.json') == expected_manifest and files.get(prefix+'catalog.json') == canonical(catalog(bundle)), 'Prior manifest/catalog mismatch')
        return bundle
    current = validate_release(identifier)
    require(files.get('catalog.json') == files['releases/'+identifier+'/catalog.json'], 'Discovery catalog does not select the current release')
    require({PurePosixPath(name).parts[1] for name in files if name.startswith('releases/')} == visited, 'Unlinked release in prior assembly')
    return receipt, files, current


def assemble(input_path, output, *, previous=None, previous_digest=None, allow_fixtures=False):
    input_root, bundle, assets, inputs = load_input(input_path)
    require((previous is None) == (previous_digest is None), 'Previous output and expected digest must be supplied together')
    old_bundle, files = None, {}
    if previous is not None:
        _, files, old_bundle = verify_assembly(previous, previous_digest, allow_fixtures=allow_fixtures)
    validate_snapshot(bundle, assets, previous=old_bundle, allow_fixtures=allow_fixtures)
    require(not bundle['publication'].get('withdrawals'), 'Withdrawal packaging requires an explicit removal policy')
    bundle['records'] = sorted(bundle['records'], key=key_for)
    identifier = bundle['publication']['id']
    prefix = 'releases/'+identifier+'/'
    require(not any(name.startswith(prefix) for name in files), 'Release ID was already published')
    def put(name, data):
        output_name(name)
        require(name not in files or files[name] == data, 'Immutable publication output changed')
        files[name] = data
    put(prefix+'bundle.json', canonical(bundle))
    put(prefix+'manifest.json', canonical({'schemaVersion': bundle['schemaVersion'], 'purpose': bundle['purpose'], 'publication': bundle['publication']}))
    discovery = canonical(catalog(bundle))
    put(prefix+'catalog.json', discovery)
    files['catalog.json'] = discovery  # Only this discovery alias is mutable.
    for record in bundle['records']:
        put(record_path(record), canonical({'schemaVersion': bundle['schemaVersion'], 'purpose': bundle['purpose'], 'record': record}))
    for name, data in assets.items():
        put(prefix+name, data)
    receipt = {'assemblyVersion': VERSION, 'schemaVersion': bundle['schemaVersion'], 'purpose': bundle['purpose'], 'releaseId': identifier,
               'inputs': inputs, 'inputDigest': digest(inputs), 'tool': tool_identity(), 'files': file_inventory(files)}
    raw_receipt = canonical(receipt)
    files['assembly.json'] = raw_receipt
    files[prefix+'assembly.json'] = raw_receipt
    target = directory(output)
    require(not target.exists(), 'Output must be a new directory; existing builds are never replaced')
    require(not target.is_relative_to(input_root) and not input_root.is_relative_to(target), 'Input and output trees must be separate')
    if previous is not None:
        previous_root = directory(previous)
        require(not target.is_relative_to(previous_root) and not previous_root.is_relative_to(target), 'Previous and next output trees must be separate')
    target.parent.mkdir(parents=True, exist_ok=True)
    # Build privately in a sibling staging directory. Publish it only after all writes succeed.
    with tempfile.TemporaryDirectory(prefix='.rulebooks-build-', dir=target.parent) as temporary:
        staging = Path(temporary) / 'output'
        staging.mkdir()
        for name, data in sorted(files.items()):
            path = staging / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        require(not target.exists(), 'Output appeared during assembly; choose a new destination')
        staging.rename(target)
    return {'releaseId': identifier, 'purpose': bundle['purpose'], 'files': len(files), 'assemblyDigest': sha(raw_receipt)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path, help='Reviewed bundle or explicit recordFiles selection')
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--previous', type=Path, help='Previously published output directory')
    parser.add_argument('--previous-digest', help='Independently retained previous assembly.json byte digest')
    parser.add_argument('--allow-fixtures', action='store_true', help='Build explicitly labeled developer fixtures only')
    args = parser.parse_args()
    try:
        result = assemble(args.input, args.output, previous=args.previous, previous_digest=args.previous_digest, allow_fixtures=args.allow_fixtures)
        print(json.dumps(result, sort_keys=True))
    except (ValueError, OSError, KeyError, TypeError, RecursionError):
        parser.exit(1, 'Publication assembly failed; inspect the selected inputs and previous release locally. No deployment occurred.\n')


if __name__ == '__main__':
    main()
