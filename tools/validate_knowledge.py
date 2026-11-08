"""Validate private knowledge drafts and project explicitly reviewed rulebooks offline."""

import argparse
import copy
import json
import os
from pathlib import Path, PurePosixPath
import sys

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.validate_publication import ContractError, digest, load_json, require, reviewed_digest
from tools.references.contracts import validate as reference_shape, validate_public_source, validate_proposal
from tools.references.store import external_path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = load_json(ROOT / 'schema/knowledge/0.1.0/knowledge.schema.json')
PUBLIC = load_json(ROOT / 'schema/publication/0.1.0/bundle.schema.json')
REFERENCE = load_json(ROOT / 'schema/reference/0.1.0/records.schema.json')
REGISTRY = Registry().with_resources([(s['$id'], Resource.from_contents(s)) for s in [SCHEMA, PUBLIC, REFERENCE]])
TOPICS = {'players', 'components', 'setup', 'turns', 'actions', 'constraints', 'information', 'scoring', 'ending'}


def shape(kind, value, schema=SCHEMA):
    validator = Draft202012Validator({'$ref': schema['$id']+'#/$defs/'+kind}, registry=REGISTRY, format_checker=FormatChecker())
    require(not list(validator.iter_errors(value)), f'Invalid {kind} structure; inspect the private input locally')


def index(records, key='id'):
    result = {r[key]: r for r in records}
    require(len(result) == len(records), f'Duplicate {key}')
    return result


def refs(values, available, message):
    require(set(values) <= set(available), message)


def pin(value):
    return {'id': value['id'], 'revision': value['revision'], 'digest': digest(value)}


def fixture(value, allow):
    require(allow or 'testOnly' not in value, 'Fixture requires explicit --allow-fixtures')


def validate_draft(draft, *, previous=None, allow_fixtures=False):
    shape('draft', draft)
    fixture(draft, allow_fixtures)
    sources = index(draft['sources'])
    runs = index(draft['runs'])
    evidence = index(draft['evidence'])
    rules = index(draft['rules'])
    entities = index(draft.get('entities', []))
    index(draft['questions'])
    coverage = index(draft['coverage'], 'topic')
    require(set(coverage) == TOPICS, 'Coverage must account for all nine topics')
    for source in sources.values():
        index(source.get('artifacts', []))
        for artifact in source.get('artifacts', []):
            name = artifact['path']
            path = PurePosixPath(name)
            require(path.parts and not path.is_absolute() and '..' not in path.parts and '\\' not in name and str(path) == name,
                    'Artifact requires a normalized relative path')
    for run in runs.values():
        refs(run['sourceIds'], sources, 'Run references unknown source')
        version = run['tool']['version']
        require(version.lower() not in {'latest', 'current', 'unknown'} and not any(c in version for c in '*^~<>'), 'Record an exact tool version')
    for item in evidence.values():
        require(item['sourceId'] in sources and item['runId'] in runs, 'Evidence references unknown source/run')
        require(item['sourceId'] in runs[item['runId']]['sourceIds'], 'Evidence source absent from generating run inputs')
        source = sources[item['sourceId']]
        if source['kind'] == 'editorial':
            require('artifactId' not in item, 'Editorial evidence has no artifact')
        else:
            require(item.get('artifactId') in {a['id'] for a in source['artifacts']}, 'Evidence references unknown artifact')
        location = item['locator']
        if location['kind'] == 'time':
            require(location['endMs'] > location['startMs'] and sources[item['sourceId']]['kind'] == 'playthrough', 'Invalid playthrough time span')
        if location['kind'] == 'bytes':
            require(location['endByte'] > location['startByte'], 'Invalid byte span')
    for rule in rules.values():
        require(rule['runId'] in runs, 'Rule references unknown run')
        refs(rule.get('entityIds', []), entities, 'Rule references unknown entity')
        refs(rule.get('premises', []), rules, 'Rule references unknown premise')
        require(rule['basis'] == 'inferred' or not rule.get('premises'), 'Only inferred rules have premises')
        links = index(rule['evidence'], 'evidenceId')
        refs(links, evidence, 'Rule references unknown evidence')
        supporting = [evidence[x['evidenceId']] for x in rule['evidence'] if x['relation'] == 'supports']
        refs([evidence[x['evidenceId']]['sourceId'] for x in rule['evidence']], runs[rule['runId']]['sourceIds'], 'Rule evidence absent from generating run inputs')
        require(supporting or rule.get('premises'), 'Every proposed rule needs supporting evidence or premises')
        if rule['basis'] == 'explicit':
            require(supporting and all(sources[e['sourceId']]['kind'] == 'document' for e in supporting), 'Explicit rules require document assertions, not play observations')
        if rule['basis'] == 'editorial':
            require(supporting and all(sources[e['sourceId']]['kind'] == 'editorial' for e in supporting), 'Editorial rules require original-definition attribution')
        for link in rule['evidence']:
            if link['relation'] == 'contradicts':
                require(any(q['kind'] == 'conflict' and rule['id'] in q['ruleIds'] and link['evidenceId'] in q['evidenceIds'] for q in draft['questions']),
                        'Contradicting evidence needs an explicit conflict question')
    visiting, visited = set(), set()
    def visit(identifier):
        require(identifier not in visiting, 'Circular inference premises')
        if identifier in visited:
            return
        visiting.add(identifier)
        for parent in rules[identifier].get('premises', []):
            visit(parent)
        visiting.remove(identifier)
        visited.add(identifier)
    for identifier in rules:
        visit(identifier)
    for entity in entities.values():
        refs(entity['ruleIds'], rules, 'Entity references unknown rules')
        if 'action' in entity:
            action = entity['action']
            refs(action['actorIds'], entities, 'Action references unknown actors')
            require(all(entities[a]['kind'] == 'player' for a in action['actorIds']), 'Action actors must be player entities')
            refs(action['conditionRuleIds'] + action['effectRuleIds'], entity['ruleIds'], 'Action conditions/effects need supporting rule links')
    for question in draft['questions']:
        refs(question['ruleIds'], rules, 'Question references unknown rules')
        refs(question['evidenceIds'], evidence, 'Question references unknown evidence')
        require(question['runId'] in runs, 'Question references unknown run')
    for row in coverage.values():
        refs(row['ruleIds'], rules, 'Coverage references unknown rule')
        require(all(rules[r]['topic'] == row['topic'] for r in row['ruleIds']), 'Coverage topic differs from referenced rule')
        require((row['status'] in {'described', 'partial'}) == bool(row['ruleIds']), 'Coverage status/rule inventory mismatch')
    require(set(rules) == {r for c in coverage.values() for r in c['ruleIds']}, 'Coverage omits a proposed rule')
    if previous is not None:
        validate_draft(previous, allow_fixtures=allow_fixtures)
        require(draft.get('previous') == pin(previous) and draft['id'] == previous['id'] and draft['revision'] == previous['revision'] + 1,
                'Draft predecessor mismatch')
        require(draft['game'] == previous['game'] and draft.get('testOnly') == previous.get('testOnly'), 'Draft lineage cannot change game identity or fixture status')
    return {'rules': len(rules), 'evidence': len(evidence), 'questions': len(draft['questions']), 'historyChecked': previous is not None}


def validate_handoffs(draft, handoffs):
    """Check declared artifact identities; the reference importer verifies file bytes."""
    manifests = index(handoffs, 'handoffId')
    for manifest in handoffs:
        reference_shape('handoff', manifest)
    sizes = {}
    for source in draft['sources']:
        for artifact in source.get('artifacts', []):
            manifest = manifests.get(artifact['handoffId'])
            require(manifest is not None, 'Missing evidence handoff manifest')
            require(digest(manifest) == artifact['manifestDigest'], 'Evidence handoff manifest digest mismatch')
            metadata = manifest['capture']
            require(metadata['sourceId'] == source['id'] and metadata['sourceEdition'] == source['edition'],
                    'Evidence handoff identity/edition mismatch')
            if metadata['gameId'] != draft['game']['id'] or metadata.get('publisherEdition') != draft['game'].get('publisherEdition'):
                require(source.get('applicability'), 'Different acquisition game/publisher edition context requires applicability rationale')
            files = index([manifest['original'], *[d['file'] for d in manifest.get('derived', [])]], 'path')
            entry = files.get(artifact['path'])
            require(entry is not None and entry['sha256'] == artifact['sha256'], 'Evidence artifact path/digest mismatch')
            sizes[(source['id'], artifact['id'])] = entry['size']
    for evidence in draft['evidence']:
        if evidence['locator']['kind'] == 'bytes':
            key = (evidence['sourceId'], evidence.get('artifactId'))
            require(key in sizes and evidence['locator']['endByte'] <= sizes[key], 'Byte evidence exceeds its artifact')
    return len(sizes)


def project(draft, review, sources, *, handoffs=(), allow_fixtures=False):
    """Pure projection; no file I/O, authentication, publication or semantic execution."""
    validate_draft(draft, allow_fixtures=allow_fixtures)
    validate_handoffs(draft, handoffs)
    shape('review', review)
    fixture(review, allow_fixtures)
    require(draft.get('testOnly') == review.get('testOnly'), 'Fixture marker mismatch')
    require(review['draft'] == pin(draft), 'Review does not pin this exact draft')
    require(review['review']['reviewedDigest'] == reviewed_digest(review), 'Editorial decision digest mismatch')
    decisions = index(review['decisions'], 'ruleId')
    questions = index(review['questions'], 'questionId')
    rules = index(draft['rules'])
    evidence = index(draft['evidence'])
    source_inputs = index(draft['sources'])
    require(set(decisions) == set(rules), 'Review must account for every proposed rule exactly once')
    require(set(questions) == {q['id'] for q in draft['questions']}, 'Review must account for every question exactly once')
    sections = index(review['sections'])
    mappings = index(review['sourceMappings'], 'draftSourceId')
    refs(mappings, source_inputs, 'Source mapping references unknown draft source')
    public_sources = {}
    for source in sources:
        shape('Source', source, PUBLIC)
        fixture(source, allow_fixtures)
        require(source.get('testOnly') == draft.get('testOnly'), 'Public Source fixture marker mismatch')
        key = (source['id'], source['revision'])
        require(key not in public_sources, 'Duplicate public Source pin')
        public_sources[key] = source
        public_value = {k: v for k, v in source.items() if k != 'testOnly'}
        validate_proposal({'source': public_value, 'citations': [{'source': {'id': key[0], 'revision': key[1]}, 'locator': 'Source identity review'}]})
    for mapping in mappings.values():
        p = mapping['source']
        public = public_sources.get((p['id'], p['revision']))
        require(public is not None, 'Source mapping lacks a supplied public Source revision')
        original = source_inputs[mapping['draftSourceId']]
        require(original['kind'] != 'editorial' and original['edition'] == public['edition'], 'Source mapping changes document edition or editorial origin')
    accepted = {r for r, d in decisions.items() if d['decision'] == 'accept'}
    require(accepted, 'Projection requires at least one accepted rule')
    output_ids = set()
    def supporting_sources(identifier):
        rule = rules[identifier]
        found = {evidence[l['evidenceId']]['sourceId'] for l in rule['evidence'] if l['relation'] == 'supports'}
        for premise in rule.get('premises', []):
            found |= supporting_sources(premise)
        return found
    output_sections = {k: {**v, 'rules': []} for k, v in sections.items()}
    for identifier, decision in decisions.items():
        if decision['decision'] != 'accept':
            continue
        require(set(rules[identifier].get('premises', [])) <= accepted, 'Accepted inference depends on an unaccepted premise')
        require(decision['sectionId'] in sections, 'Accepted rule references unknown section')
        output = decision['output']
        require(output['id'] not in output_ids, 'Duplicate published rule ID')
        output_ids.add(output['id'])
        require('origin' in output, 'Accepted rule requires explicit public origin')
        external = {s for s in supporting_sources(identifier) if source_inputs[s]['kind'] != 'editorial'}
        if external:
            require(external <= set(mappings), 'Accepted rule loses a supporting source mapping')
            origin = output['origin']
            require(origin['kind'] == 'source', 'Accepted rule loses external attribution')
            expected = {(mappings[s]['source']['id'], mappings[s]['source']['revision']) for s in external}
            actual = {(c['source']['id'], c['source']['revision']) for c in origin['citations']}
            require(actual == expected, 'Public citations must preserve supporting source pins')
        else:
            require(output['origin']['kind'] == 'editorial', 'Original definition needs editorial attribution')
        output_sections[decision['sectionId']]['rules'].append(copy.deepcopy(output))
    require(all(s['rules'] for s in output_sections.values()), 'Review includes an empty output section')
    for question in draft['questions']:
        decision = questions[question['id']]
        if decision['decision'] == 'resolved':
            refs(decision['evidenceIds'], evidence, 'Resolution references unknown evidence')
        else:
            affected = not question['ruleIds'] or bool(set(question['ruleIds']) & accepted)
            require(not (question['blocks'] == 'publication' and affected), 'Unresolved publication blocker affects accepted rules')
            require(not (question['blocks'] == 'completeness' and review['target']['readingStatus'] == 'complete'), 'Unresolved completeness question forbids complete reading status')
            require(decision['publicNote'] in review['target']['scope']['excludes'], 'Deferred question needs a visible scope limitation')
    if review['target']['readingStatus'] == 'complete':
        for row in draft['coverage']:
            require(row['status'] in {'described', 'outside-scope'} and set(row['ruleIds']) <= accepted, 'Incomplete draft coverage cannot become a complete rulebook')
    edition = {'kind': 'RulebookEdition', **copy.deepcopy(review['target']), 'gameId': draft['game']['id'],
               'dimensions': sorted({rules[r]['dimension'] for r in accepted}), 'sections': list(output_sections.values()),
               'review': copy.deepcopy(review['review'])}
    if draft.get('testOnly'):
        edition['testOnly'] = True
    edition['review']['reviewedDigest'] = reviewed_digest(edition)
    shape('RulebookEdition', edition, PUBLIC)
    trace = {'schemaVersion': '0.1.0', 'kind': 'KnowledgePromotionTrace', 'draft': copy.deepcopy(draft),
             'editorialReview': copy.deepcopy(review), 'sourceRecords': copy.deepcopy(sources), 'handoffs': copy.deepcopy(list(handoffs)), 'editionDigest': digest(edition)}
    shape('trace', trace)
    return edition, trace


def verify_trace(trace, edition, *, allow_fixtures=False):
    shape('trace', trace)
    expected, regenerated = project(trace['draft'], trace['editorialReview'], trace['sourceRecords'], handoffs=trace['handoffs'], allow_fixtures=allow_fixtures)
    require(edition == expected and trace == regenerated, 'Promotion trace/output mismatch')
    return True


def validate_fixture(directory):
    """Exercise the entire synthetic handoff-to-edition chain in repository checks."""
    directory = Path(directory)
    draft = load_json(directory / 'draft.json')
    review = load_json(directory / 'review.json')
    require(draft.get('testOnly') and review.get('testOnly'), 'Knowledge fixtures must be explicitly test-only')
    sources = [load_json(p) for p in sorted(directory.glob('*.source.json'))]
    handoffs = [load_json(p) for p in sorted(directory.glob('*.handoff.json'))]
    for manifest in handoffs:
        reference_shape('handoff', manifest)
        for entry in [manifest['original'], *[d['file'] for d in manifest.get('derived', [])]]:
            path = (directory / entry['path']).resolve()
            require(path.is_relative_to(directory.resolve()), 'Fixture artifact escapes its directory')
            raw = path.read_bytes()
            import hashlib
            require(len(raw) == entry['size'] and hashlib.sha256(raw).hexdigest() == entry['sha256'], 'Fixture artifact size/digest mismatch')
    edition, trace = project(draft, review, sources, handoffs=handoffs, allow_fixtures=True)
    require(edition == load_json(directory / 'expected-edition.json'), 'Expected edition differs from reviewed projection')
    verify_trace(trace, edition, allow_fixtures=True)
    return len(draft['rules'])


def write_projection(directory, edition, trace, server_acl=False):
    root = external_path(directory)
    require(not any((p / '.store.json').exists() for p in [root, *root.parents]), 'Knowledge workspace must be outside the managed reference store')
    root.mkdir(mode=0o700, parents=False, exist_ok=False)
    require(server_acl or root.stat().st_mode & 0o077 == 0, 'Output directory needs private permissions or explicit server ACL confirmation')
    for name, value in [('edition.json', edition), ('trace.json', trace)]:
        with os.fdopen(os.open(root / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['validate', 'project'])
    parser.add_argument('--draft', required=True)
    parser.add_argument('--previous')
    parser.add_argument('--review')
    parser.add_argument('--source', action='append', default=[], help='Reviewed public-source envelope; repeat for each Source')
    parser.add_argument('--handoff', action='append', default=[], help='Evidence artifact manifest; repeat for each acquisition')
    parser.add_argument('--output-dir', help='New private directory outside Git and the managed reference store')
    parser.add_argument('--allow-fixtures', action='store_true')
    parser.add_argument('--accept-server-access-controls', action='store_true')
    args = parser.parse_args()
    try:
        draft = load_json(args.draft)
        previous = load_json(args.previous) if args.previous else None
        result = validate_draft(draft, previous=previous, allow_fixtures=args.allow_fixtures)
        handoffs = [load_json(p) for p in args.handoff]
        result['artifactBindingsChecked'] = bool(handoffs)
        if handoffs:
            validate_handoffs(draft, handoffs)
        if args.command == 'project':
            require(args.review and args.output_dir, 'Projection requires review and output directory')
            sources = []
            for path in args.source:
                value = load_json(path)
                if args.allow_fixtures and value.get('kind') == 'Source' and value.get('testOnly'):
                    sources.append(value)
                else:
                    sources.append(validate_public_source(value)['source'])
            edition, trace = project(draft, load_json(args.review), sources, handoffs=handoffs, allow_fixtures=args.allow_fixtures)
            write_projection(args.output_dir, edition, trace, args.accept_server_access_controls)
            result = {'editionDigest': digest(edition), 'traceDigest': digest(trace), 'published': False}
        print(json.dumps(result, sort_keys=True))
    except (ValueError, OSError, KeyError):
        parser.exit(1, 'Knowledge validation/projection failed; inspect private inputs locally. No publication occurred.\n')


if __name__ == '__main__':
    main()
