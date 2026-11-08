"""Site input boundaries and history preservation; no fictional approvals in the catalog."""
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from tools import prepare_site
from tools.assemble_publication import assemble, verify_assembly
from tools.validate_publication import ContractError

ROOT = Path(__file__).resolve().parents[1]


class SiteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='rulebooks-site-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.catalog = self.root / 'catalog'
        shutil.copytree(ROOT / 'data/catalog', self.catalog)
        self.entry = self.catalog / 'catalog.json'
        shutil.copytree(ROOT/'data/site',self.root/'data/site')
        shutil.copytree(ROOT/'work',self.root/'work')
        shutil.copytree(ROOT/'schema',self.root/'schema')
        shutil.copytree(ROOT/'docs',self.root/'docs')
        shutil.copytree(ROOT/'data/catalog',self.root/'data/catalog')

    def change(self, name, modify):
        file = self.catalog / name
        value = json.loads(file.read_text())
        modify(value)
        file.write_text(json.dumps(value))

    def test_actual_games_are_not_fixtures_or_accepted_releases(self):
        content = prepare_site.preview_catalog(self.entry)
        self.assertEqual(len(content['games']), 3)
        self.assertEqual(content['authorship']['kind'], 'agent')
        for record in content['records']:
            self.assertNotIn('testOnly',record)
            self.assertNotIn('review',record)
        self.assertEqual({r['readingStatus'] for r in content['records'] if r['kind']=='RulebookEdition'}, {'partial','complete'})

    def test_preview_rejects_review_and_fixture_flags(self):
        file='records/RulebookEdition-nim-one-two-1.json'
        original=(self.catalog/file).read_text()
        for field,value in [('review',{}),('testOnly',True)]:
            with self.subTest(field=field):
                (self.catalog/file).write_text(original)
                self.change(file,lambda r:r.update({field:value}))
                with self.assertRaises(ContractError): prepare_site.preview_catalog(self.entry)

    def test_missing_citation_and_duplicate_rule_anchor_fail(self):
        file='records/RulebookEdition-nim-one-two-1.json'
        original=(self.catalog/file).read_text()
        for mutate in [lambda r:r['sections'][0]['rules'][0].pop('origin',None),
                       lambda r:r['sections'][0]['rules'].append(copy.deepcopy(r['sections'][0]['rules'][0]))]:
            (self.catalog/file).write_text(original)
            self.change(file,mutate)
            with self.assertRaises(ContractError): prepare_site.preview_catalog(self.entry)

    def test_wrong_game_and_missing_source_pins_fail(self):
        file='records/Game-nim-normal-play-1.json'
        self.change(file,lambda r:r.update(defaultEdition={'id':'rps-one-round','revision':1}))
        with self.assertRaises(ContractError): prepare_site.preview_catalog(self.entry)
        shutil.copyfile(ROOT/'data/catalog'/file,self.catalog/file)
        self.change('catalog.json',lambda c:c['recordFiles'].remove('records/Source-cornell-nim-2004-1.json'))
        with self.assertRaises(ContractError): prepare_site.preview_catalog(self.entry)

    def test_private_paths_and_symlink_inputs_fail(self):
        self.change('catalog.json',lambda c:c['recordFiles'].append('../secret.json'))
        with self.assertRaises(ContractError): prepare_site.preview_catalog(self.entry)
        shutil.copyfile(ROOT/'data/catalog/catalog.json',self.entry)
        file=self.catalog/'records/Game-chess-1.json'
        outside=self.root/'outside.json';file.rename(outside);file.symlink_to(outside)
        with self.assertRaises((ContractError,OSError)): prepare_site.preview_catalog(self.entry)

    def test_generated_preview_downloads_retain_status_and_rebuild_deterministically(self):
        with patch.object(prepare_site,'ROOT',self.root):
            first=prepare_site.prepare(self.entry)
            second=prepare_site.prepare(self.entry)
        self.assertEqual(first,second)
        public=self.root/'.cache/site-generated/public/data'
        record=json.loads((public/'records/RulebookEdition/nim-one-two/1.json').read_text())
        self.assertEqual(record['purpose'],'editorial-preview')
        self.assertNotIn('review',record['record'])
        self.assertFalse((public/'work').exists())

    def test_unrelated_cache_is_never_deleted(self):
        cache=self.root/'.cache/site-generated';cache.mkdir(parents=True)
        (cache/'keep.txt').write_text('keep')
        with patch.object(prepare_site,'ROOT',self.root), self.assertRaises(ContractError):
            prepare_site.prepare(self.entry)
        self.assertEqual((cache/'keep.txt').read_text(),'keep')

    def test_publication_requires_trusted_digest_and_rejects_fixtures(self):
        fixture=ROOT/'tests/fixtures/publication/publisher-editions.json'
        output=self.root/'publication'
        result=assemble(fixture,output,allow_fixtures=True)
        with patch.object(prepare_site,'ROOT',self.root):
            with self.assertRaises(ContractError): prepare_site.prepare(self.entry,publication=output)
            with self.assertRaises(ContractError):
                prepare_site.prepare(self.entry,publication=output,expected_digest=result['assemblyDigest'])

    def test_verified_record_history_and_original_download_bytes_are_retained(self):
        # Mock ONLY the verified input boundary; production never enables fixtures.
        fixture=ROOT/'tests/fixtures/publication/publisher-editions.json'
        output=self.root/'publication'
        result=assemble(fixture,output,allow_fixtures=True)
        receipt,files,bundle=verify_assembly(output,result['assemblyDigest'],allow_fixtures=True)
        # A later release may no longer select an old revision in its current bundle.
        bundle=copy.deepcopy(bundle)
        historical=next(r for r in bundle['records'] if r['kind']=='RulebookEdition')
        bundle['records'].remove(historical)
        with patch.object(prepare_site,'ROOT',self.root), patch.object(prepare_site,'verify_assembly',return_value=(receipt,files,bundle)) as verify:
            prepare_site.prepare(self.entry,publication=output,expected_digest=result['assemblyDigest'])
        verify.assert_called_once_with(output,result['assemblyDigest'])
        generated=self.root/'.cache/site-generated'
        content=json.loads((generated/'content.json').read_text())
        self.assertIn(historical,content['records'])
        self.assertEqual(content['mode'],'publication')
        for name,raw in files.items():
            self.assertEqual((generated/'public/data'/name).read_bytes(),raw)
