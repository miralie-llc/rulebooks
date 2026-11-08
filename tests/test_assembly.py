"""Public assembly tests; fixtures remain developer data, never collected games."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools.assemble_publication import assemble, canonical, sha, verify_assembly
from tools.validate_publication import ContractError, digest, load_json, manifest_entry, reviewed_digest, validate_bundle
from tools.references.contracts import validate_public_source

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests/fixtures/publication'


def seal(bundle):
    for record in bundle['records']:
        if 'review' in record:
            record['review']['reviewedDigest'] = reviewed_digest(record)
    bundle['publication']['manifest'] = [manifest_entry(r) for r in bundle['records']]
    bundle['publication']['review']['reviewedDigest'] = reviewed_digest(bundle['publication'])
    return bundle


def tree(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*') if p.is_file()}


class AssemblyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='rulebooks-assembly-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.inputs = self.root / 'inputs'
        self.inputs.mkdir()
        self.bundle = load_json(FIXTURES / 'first-games.json')
        shutil.copytree(FIXTURES / 'sources', self.inputs / 'sources')
        self.write()

    def write(self):
        self.entry = self.inputs / 'publication.json'
        self.entry.write_text(json.dumps(self.bundle, indent=2)+'\n')

    def build(self, name='output', **kw):
        return assemble(self.entry, self.root / name, allow_fixtures=True, **kw)

    def next_release(self):
        previous = copy.deepcopy(self.bundle)
        self.bundle['publication'].update(id='second-release', previous={'id':previous['publication']['id'], 'sha256':digest(previous['publication'])})
        seal(self.bundle)
        self.write()
        return previous

    def test_same_inputs_produce_identical_bytes_in_different_output_locations(self):
        first = self.build('one')
        for file in self.inputs.rglob('*'):
            os.utime(file, (1000000000, 1000000000))
        second = self.build('two')
        self.assertEqual(first, second)
        self.assertEqual(tree(self.root / 'one'), tree(self.root / 'two'))
        receipt, files, bundle = verify_assembly(self.root / 'one', first['assemblyDigest'], allow_fixtures=True)
        self.assertEqual(receipt['inputDigest'], digest(receipt['inputs']))
        self.assertEqual(bundle['publication'], self.bundle['publication'])
        self.assertIn('python', receipt['tool'])
        self.assertTrue(receipt['tool']['files'])

    def test_output_is_compact_schema_tagged_and_fixture_labeled(self):
        result = self.build()
        output = self.root / 'output'
        self.assertEqual(result['purpose'], 'contract-fixture')
        catalog = load_json(output / 'catalog.json')
        self.assertEqual(len(catalog['games']), 3)
        chess = next(g for g in catalog['games'] if g['game']['id'] == 'chess')
        self.assertNotIn('recommendedFormalization', chess)
        self.assertEqual(chess['edition']['readingStatus'], 'partial')
        for path in output.rglob('*.json'):
            raw = path.read_bytes()
            self.assertEqual(raw, canonical(json.loads(raw)))
        record = load_json(output / chess['edition']['record'])
        self.assertEqual(record['schemaVersion'], '0.1.0')
        self.assertTrue(record['record']['testOnly'])
        self.assertLess(len((output / chess['record']).read_bytes()), 20 * 1024)

    def test_publisher_editions_remain_distinct_from_editorial_revisions(self):
        self.bundle = load_json(FIXTURES / 'publisher-editions.json')
        self.write()
        self.build()
        catalog = load_json(self.root / 'output/catalog.json')
        self.assertEqual(len(catalog['games']), 2)
        self.assertEqual(len({g['game']['id'] for g in catalog['games']}), 2)
        self.assertEqual(len({g['publisherEdition']['id'] for g in catalog['games']}), 2)
        self.assertEqual(len({g['family']['id'] for g in catalog['games']}), 1)
        editions = list((self.root / 'output/records/RulebookEdition').rglob('*.json'))
        self.assertEqual(len(editions), 3)

    def test_explicit_record_files_and_direct_bundle_have_same_public_content(self):
        self.build('direct')
        selection = {k:v for k,v in self.bundle.items() if k != 'records'}
        selection['recordFiles'] = []
        (self.inputs / 'records').mkdir()
        for i, record in enumerate(reversed(self.bundle['records'])):
            name = f'records/r{i}.json'
            (self.inputs / name).write_text(json.dumps(record))
            selection['recordFiles'].append(name)
        self.entry.write_text(json.dumps(selection))
        self.build('selected')
        for name in tree(self.root / 'direct'):
            if not name.endswith('assembly.json'):
                self.assertEqual((self.root / 'direct' / name).read_bytes(), (self.root / 'selected' / name).read_bytes())

    def test_existing_review_and_publication_digests_are_preserved(self):
        self.build()
        bundle = load_json(self.root / 'output/releases/first-games/bundle.json')
        self.assertEqual(bundle['publication']['review'], self.bundle['publication']['review'])
        old = {tuple(manifest_entry(r).items()) for r in self.bundle['records']}
        self.assertEqual({tuple(manifest_entry(r).items()) for r in bundle['records']}, old)
        validate_bundle(bundle, self.root / 'output/releases/first-games', allow_fixtures=True)

    def test_changed_reviewed_bytes_are_not_automatically_reapproved(self):
        edition = next(r for r in self.bundle['records'] if r['kind'] == 'RulebookEdition')
        edition['label'] = 'Changed after review'
        self.write()
        with self.assertRaisesRegex(ContractError, 'Review digest'):
            self.build()
        self.assertFalse((self.root / 'output').exists())

    def test_unlisted_private_files_and_directories_are_never_read_or_copied(self):
        (self.inputs / 'private-notes.txt').write_text('Do not publish this.')
        (self.inputs / '.private').mkdir()
        (self.inputs / '.private/raw.pdf').write_bytes(b'private')
        with patch.dict(os.environ, {'RULEBOOKS_REFERENCE_ROOT':'/unavailable-private-store'}):
            self.build()
        self.assertFalse(any(b'Do not publish' in data for data in tree(self.root / 'output').values()))
        receipt = load_json(self.root / 'output/assembly.json')
        self.assertNotIn('private-notes.txt', {i['path'] for i in receipt['inputs']})
        self.assertNotIn(str(self.root), json.dumps(receipt))

    def test_dangling_references_and_bad_coverage_stop_build(self):
        self.bundle['records'] = [r for r in self.bundle['records'] if r['kind'] != 'Source']
        seal(self.bundle);self.write()
        with self.assertRaisesRegex(ContractError, 'Dangling Source'):
            self.build()
        self.bundle = load_json(FIXTURES / 'first-games.json')
        formal = next(r for r in self.bundle['records'] if r['kind'] == 'Formalization')
        formal['coverage'].pop()
        seal(self.bundle);self.write()
        with self.assertRaisesRegex(ContractError, 'every edition rule'):
            self.build()

    def test_asset_corruption_path_escape_and_symlink_rejected(self):
        package = next(r for r in self.bundle['records'] if r['kind'] == 'DefinitionPackage')
        asset = self.inputs / package['files'][0]['path']
        original = asset.read_bytes()
        asset.write_bytes(b'Changed')
        with self.assertRaisesRegex(ContractError, 'asset digest'):
            self.build()
        asset.unlink();(self.root / 'outside.txt').write_bytes(original)
        asset.symlink_to(self.root / 'outside.txt')
        with self.assertRaises(OSError):
            self.build()
        asset.unlink();asset.write_bytes(original)
        package['files'][0]['path'] = '../outside.txt'
        seal(self.bundle);self.write()
        with self.assertRaisesRegex(ContractError, 'Disallowed'):
            self.build()

    def test_record_selection_rejects_private_paths_and_unknown_fields(self):
        selection = {k:v for k,v in self.bundle.items() if k != 'records'}
        selection['recordFiles'] = ['.private/review.json']
        self.entry.write_text(json.dumps(selection))
        with self.assertRaisesRegex(ContractError, 'Disallowed'):
            self.build()
        selection['unexpected'] = True
        self.entry.write_text(json.dumps(selection))
        with self.assertRaisesRegex(ContractError, 'selection fields'):
            self.build()

    def test_revision_urls_and_previous_release_bytes_survive_new_default(self):
        first = self.build('one')
        old_files = tree(self.root / 'one')
        old = self.next_release()
        game = copy.deepcopy(next(r for r in self.bundle['records'] if r['kind']=='Game' and r['id']=='chess'))
        edition = copy.deepcopy(next(r for r in self.bundle['records'] if r['kind']=='RulebookEdition' and r['gameId']=='chess'))
        edition.update(revision=2, previous={'id':edition['id'],'revision':1}, change={'kind':'editorial','summary':'Clarify excerpt label.'}, label='Clarified excerpt')
        game.update(revision=2, defaultEdition={'id':edition['id'],'revision':2})
        self.bundle['records'].extend([game, edition])
        self.bundle['publication']['games'] = [({'id':game['id'],'revision':2} if p['id']=='chess' else p) for p in self.bundle['publication']['games']]
        seal(self.bundle);self.write()
        second = self.build('two', previous=self.root / 'one', previous_digest=first['assemblyDigest'])
        for name, data in old_files.items():
            if name not in {'catalog.json', 'assembly.json'}:
                self.assertEqual((self.root / 'two' / name).read_bytes(), data)
        catalog = load_json(self.root / 'two/catalog.json')
        self.assertEqual(next(g for g in catalog['games'] if g['game']['id']=='chess')['edition']['revision'], 2)
        verify_assembly(self.root / 'two', second['assemblyDigest'], allow_fixtures=True)
        self.assertEqual(load_json(self.root / 'two/releases/first-games/bundle.json')['publication'], old['publication'])

    def test_previous_requires_trusted_digest_and_rejects_tampering(self):
        first = self.build('one');self.next_release()
        with self.assertRaisesRegex(ContractError, 'supplied together'):
            self.build('two', previous=self.root / 'one')
        with self.assertRaisesRegex(ContractError, 'receipt digest'):
            self.build('two', previous=self.root / 'one', previous_digest='0'*64)
        (self.root / 'one/catalog.json').write_text('{}')
        with self.assertRaisesRegex(ContractError, 'output digest'):
            self.build('two', previous=self.root / 'one', previous_digest=first['assemblyDigest'])

    def test_contaminated_previous_directory_is_rejected(self):
        first = self.build('one');self.next_release()
        (self.root / 'one/private-notes.txt').write_text('Unlisted')
        with self.assertRaisesRegex(ContractError, 'unlisted files'):
            self.build('two', previous=self.root / 'one', previous_digest=first['assemblyDigest'])

    def test_reused_release_id_and_changed_immutable_record_rejected(self):
        first = self.build('one');self.next_release()
        self.bundle['records'][0]['title'] = 'Changed immutable identity'
        seal(self.bundle);self.write()
        with self.assertRaisesRegex(ContractError, 'Immutable record'):
            self.build('two', previous=self.root / 'one', previous_digest=first['assemblyDigest'])
        self.bundle = load_json(FIXTURES / 'first-games.json')
        self.bundle['publication']['previous'] = {'id':'first-games','sha256':digest(load_json(FIXTURES / 'first-games.json')['publication'])}
        seal(self.bundle);self.write()
        with self.assertRaisesRegex(ContractError, 'new release ID'):
            self.build('two', previous=self.root / 'one', previous_digest=first['assemblyDigest'])

    def test_cannot_overwrite_an_existing_build_or_write_into_input_tree(self):
        self.build()
        with self.assertRaisesRegex(ContractError, 'new directory'):
            self.build()
        with self.assertRaisesRegex(ContractError, 'separate'):
            assemble(self.entry, self.inputs / 'build', allow_fixtures=True)

    def test_fixture_output_requires_explicit_opt_in(self):
        with self.assertRaisesRegex(ContractError, 'explicit --allow-fixtures'):
            assemble(self.entry, self.root / 'output')

    def test_public_source_envelope_is_a_direct_input_without_private_intake(self):
        # Structural test of a publication-shaped input; not an authenticated approval.
        self.bundle['purpose'] = 'publication'
        self.bundle['publication']['commit'] = '1'*40
        for record in self.bundle['records']:
            record.pop('testOnly', None)
        seal(self.bundle)
        selection = {k:v for k,v in self.bundle.items() if k!='records'}
        selection['recordFiles'] = []
        (self.inputs / 'records').mkdir()
        for i, record in enumerate(self.bundle['records']):
            name = f'records/r{i}.json'
            value = record
            if record['kind'] == 'Source':
                proposal = {'source':record,'citations':[{'source':{'id':record['id'],'revision':record['revision']},'locator':'Source edition'}]}
                value = {'schemaVersion':'0.1.0',**proposal,'review':{'reviewer':'fixture-reviewer','reviewedAt':'2026-11-07T12:00:00Z','proposalDigest':digest(proposal)}}
                validate_public_source(value)
            (self.inputs / name).write_text(json.dumps(value))
            selection['recordFiles'].append(name)
        self.entry.write_text(json.dumps(selection))
        result = assemble(self.entry, self.root / 'output')
        self.assertEqual(result['purpose'], 'publication')

    def test_verification_artifacts_are_separate_and_integrity_checked(self):
        formal = next(r for r in self.bundle['records'] if r['kind']=='Formalization')
        package = next(r for r in self.bundle['records'] if r['kind']=='DefinitionPackage')
        verification = {'kind':'VerificationRecord','testOnly':True,'id':'fixture-verification','revision':1,
            'formalization':{'id':formal['id'],'revision':formal['revision']},'subjectDigest':digest(formal),
            'implementation':{'id':'fixture-checker','version':'0.1.0','buildDigest':'1'*64},
            'suite':copy.deepcopy(package['files'][0]),'method':'structural','scope':'Fixture structure only','result':'pass',
            'run':{'at':'2026-11-07T00:00:00Z','url':'https://example.org/fixture-run'}}
        self.bundle['records'].append(verification)
        seal(self.bundle);self.write()
        self.build()
        output = self.root / 'output/releases/first-games'
        self.assertEqual((output / verification['suite']['path']).read_bytes(), (self.inputs / verification['suite']['path']).read_bytes())
        verification['subjectDigest'] = '0'*64;seal(self.bundle);self.write()
        with self.assertRaisesRegex(ContractError, 'formalization digest'):
            self.build('bad')

    def test_withdrawal_cannot_silently_republish_archived_payload(self):
        first = self.build('one')
        previous = self.next_release()
        removed = next(r for r in self.bundle['records'] if r['kind']=='Formalization')
        self.bundle['records'].remove(removed)
        self.bundle['publication']['recommendedFormalizations'] = [p for p in self.bundle['publication'].get('recommendedFormalizations',[]) if p['id'] != removed['id']]
        self.bundle['publication']['withdrawals'] = [{'record':manifest_entry(removed),'reason':'Remove this fixture mapping.'}]
        seal(self.bundle);self.write()
        with self.assertRaisesRegex(ContractError, 'explicit removal policy'):
            self.build('two', previous=self.root/'one', previous_digest=first['assemblyDigest'])
        self.assertFalse((self.root/'two').exists())

    def test_asset_path_conflict_between_revisions_is_rejected(self):
        original = next(r for r in self.bundle['records'] if r['kind']=='DefinitionPackage')
        revised = copy.deepcopy(original)
        revised['revision'] = 2
        revised['files'][0]['sha256'] = '0'*64
        self.bundle['records'].append(revised)
        seal(self.bundle);self.write()
        with self.assertRaisesRegex(ContractError, 'Conflicting digests'):
            self.build()

    def test_cli_operates_without_reference_configuration(self):
        env = dict(os.environ);env.pop('RULEBOOKS_REFERENCE_ROOT',None)
        result = subprocess.run([sys.executable, str(ROOT/'tools/assemble_publication.py'), str(self.entry), '--output', str(self.root/'cli'), '--allow-fixtures'], env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['releaseId'], 'first-games')


if __name__ == '__main__':
    unittest.main()
