"""Prepare Astro's local data: explicit editorial previews or verified publications."""
import argparse
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile

from jsonschema import Draft202012Validator, FormatChecker

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.assemble_publication import canonical, directory, read_file, record_path, verify_assembly
from tools.references.contracts import validate_proposal
from tools.site_vocabulary import vocabulary
from tools.site_indexes import indexes
from tools.site_gaps import selected_gaps
from tools.runtime.specimens import build_specimens
from tools.validate_publication import ROOT, digest, key_for, load_json, require

SCHEMA = load_json(ROOT / 'schema/publication/0.1.0/bundle.schema.json')
PREVIEW_KINDS = {'Game', 'GameFamily', 'PublisherEdition', 'RulebookEdition', 'Source'}


def preview_catalog(path):
    path = Path(path)
    root = directory(path.absolute().parent)
    config = load_json(path)
    require(set(config) == {'schemaVersion','mode','authorship','recordFiles','games'}, 'Invalid preview catalog fields')
    require(config['schemaVersion'] == '0.1.0' and config['mode'] == 'editorial-preview', 'Preview must be explicitly labeled')
    author = config['authorship']
    require(isinstance(author, dict) and set(author) == {'name','kind'} and author['kind'] in {'human','agent'} and isinstance(author['name'], str) and author['name'].strip(), 'Preview needs actual authorship')
    require(isinstance(config['recordFiles'], list) and config['recordFiles'] and len(set(config['recordFiles'])) == len(config['recordFiles']), 'Select unique record files')
    records = []
    # The existing publication shapes are reused without pretending editorial
    # acceptance. This adaptation is ONLY for previews; publication is unchanged.
    definitions = copy.deepcopy(SCHEMA['$defs'])
    for kind in PREVIEW_KINDS:
        definitions[kind]['properties'].pop('testOnly', None)
    definitions['RulebookEdition']['required'].remove('review')
    definitions['RulebookEdition']['properties'].pop('review')
    for name in config['recordFiles']:
        require(name.startswith('records/') and name.endswith('.json'), 'Preview inputs must be explicit record JSON files')
        value = json.loads(read_file(root, name), object_pairs_hook=unique_pairs)
        require(isinstance(value, dict) and value.get('kind') in PREVIEW_KINDS, 'Unsupported preview record kind')
        shape = {'$schema':SCHEMA['$schema'], '$ref':'#/$defs/'+value['kind'], '$defs':definitions}
        require(not list(Draft202012Validator(shape, format_checker=FormatChecker()).iter_errors(value)), 'Invalid preview record shape')
        require(name == f"records/{value['kind']}-{value['id']}-{value['revision']}.json", 'Preview filename must match its record pin')
        records.append(value)
    by_key = {key_for(r):r for r in records}
    require(len(by_key) == len(records), 'Duplicate preview record pin')
    def resolve(kind, pin):
        value = by_key.get((kind,pin['id'],pin['revision']))
        require(value is not None, 'Unresolved preview record pin')
        return value
    def origin(value):
        require(value is not None, 'Every readable rule needs attribution')
        for citation in value.get('citations', []):
            resolve('Source', citation['source'])
    game_ids = {r['id'] for r in records if r['kind']=='Game'}
    edition_owners, publisher_owners = {}, {}
    for record in records:
        kind = record['kind']
        if kind == 'Source':
            validate_proposal({'source':record,'citations':[{'source':{'id':record['id'],'revision':record['revision']},'locator':'Source identity'}]})
        if kind == 'Game':
            require(resolve('RulebookEdition',record['defaultEdition'])['gameId'] == record['id'], 'Default edition belongs to another game')
            if 'family' in record:
                resolve('GameFamily',record['family'])
            if 'publisherEdition' in record:
                require(resolve('PublisherEdition',record['publisherEdition'])['gameId'] == record['id'], 'Publisher edition belongs to another game')
        if kind == 'PublisherEdition':
            require(record['gameId'] in game_ids, 'Publisher edition has no game')
            require(publisher_owners.setdefault(record['gameId'],record['id']) == record['id'], 'Game has multiple publisher identities')
            resolve('Source',record['source']['source'])
            if 'predecessor' in record:
                predecessor = resolve('PublisherEdition',record['predecessor'])
                require(predecessor['id'] != record['id'] and predecessor['gameId'] != record['gameId'], 'Publisher successor must identify a different game')
        if kind == 'RulebookEdition':
            require(record['gameId'] in game_ids, 'Rulebook has no game')
            require(edition_owners.setdefault(record['id'],record['gameId']) == record['gameId'], 'Rulebook lineage changed games')
            if 'previous' in record:
                previous = resolve('RulebookEdition',record['previous'])
                require(previous['id'] == record['id'] and previous['revision'] < record['revision'] and previous['gameId']==record['gameId'], 'Invalid earlier rulebook revision')
            sections, rules = set(), set()
            for section in record['sections']:
                require(section['id'] not in sections, 'Duplicate section anchor')
                sections.add(section['id'])
                for rule in section['rules']:
                    require(rule['id'] not in rules, 'Duplicate rule anchor')
                    rules.add(rule['id'])
                    origin(rule.get('origin',record.get('origin')))
    seen = set()
    require(isinstance(config['games'],list) and config['games'], 'Select at least one game')
    for pin in config['games']:
        require(set(pin)=={'id','revision'}, 'Discovery needs an exact Game pin')
        resolve('Game',pin)
        require(pin['id'] not in seen, 'Duplicate discovery game')
        seen.add(pin['id'])
    for record in records:
        if record['kind']=='Game' and record['id'] in publisher_owners:
            require(record.get('publisherEdition',{}).get('id') == publisher_owners[record['id']], 'Publisher identity needs reciprocal Game link')
    return {'mode':'editorial-preview','schemaVersion':'0.1.0','authorship':author,'games':config['games'],'records':records}


def unique_pairs(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, 'Duplicate preview JSON key')
        value[key] = item
    return value


def prepare(catalog_path, *, publication=None, expected_digest=None):
    outputs = {}
    if publication:
        require(expected_digest, 'Reviewed publication needs its trusted assembly digest')
        receipt, files, bundle = verify_assembly(publication, expected_digest)
        content = {'mode':'publication','schemaVersion':bundle['schemaVersion'],'games':bundle['publication']['games'],
                   'records':[json.loads(raw)['record'] for name,raw in sorted(files.items()) if name.startswith('records/')],
                   'publication':bundle['publication']}
        outputs.update({'public/data/'+name:raw for name,raw in files.items()})
        outputs['public/data/assembly.json'] = canonical(receipt)
    else:
        require(expected_digest is None, 'Assembly digest requires a publication directory')
        content = preview_catalog(catalog_path)
        for record in content['records']:
            outputs['public/data/'+record_path(record)] = canonical({'schemaVersion':'0.1.0','purpose':'editorial-preview','record':record})
    content['vocabulary'] = vocabulary(ROOT / 'docs/reference/vocabulary.md')
    outputs['public/data/vocabulary/'+content['vocabulary']['version']+'.json'] = canonical(content['vocabulary'])
    content['gaps'] = selected_gaps(ROOT,content)
    outputs['public/data/gaps.json'] = canonical(content['gaps'])
    content['digest'] = digest(content)
    outputs['content.json'] = canonical(content)
    if not publication:
        outputs['public/data/catalog.json'] = canonical(content)
    specimen_files,specimens = build_specimens()
    outputs.update(specimen_files)
    outputs['specimens.json'] = canonical(specimens)
    generated,search,downloads,budget = indexes(content,outputs)
    outputs.update(generated)
    outputs['search.json'] = canonical(search)
    outputs['downloads.json'] = canonical(downloads)
    outputs['budget.json'] = canonical(budget)
    outputs['site-cache.json'] = canonical({'kind':'RuleBooksSiteCache'})
    target = ROOT / '.cache/site-generated'
    require(target == target.resolve(), 'Site cache must not be a symlink')
    if target.exists():
        marker = target / 'site-cache.json'
        require(marker.is_file() and load_json(marker) == {'kind':'RuleBooksSiteCache'}, 'Refusing to replace an unrelated cache directory')
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='rulebooks-site-',dir=target.parent) as temporary:
        stage = Path(temporary)/'prepared';stage.mkdir()
        for name, raw in outputs.items():
            path=stage/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
        if target.exists():
            shutil.rmtree(target)
        stage.rename(target)
    return {'mode':content['mode'],'games':len(content['games']),'records':len(content['records']),'digest':content['digest']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog',default=ROOT/'data/catalog/catalog.json',type=Path)
    parser.add_argument('--publication',type=Path)
    parser.add_argument('--digest')
    args=parser.parse_args()
    try:
        print(json.dumps(prepare(args.catalog,publication=args.publication,expected_digest=args.digest),sort_keys=True))
    except (ValueError,OSError,KeyError,TypeError):
        parser.exit(1,'Site data validation failed; inspect the selected catalog locally.\n')


if __name__=='__main__':
    main()
