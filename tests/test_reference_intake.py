"""Exercise private intake with synthetic bytes outside all Git checkouts."""

import copy
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools.references.contracts import ROOT, ReferenceError, canonical, digest, validate, validate_public_source
from tools.references.store import LocalStore
from tools.check_repository import CheckError, snapshot, validate_candidate


class ReferenceIntakeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='rulebooks-intake-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = LocalStore.create(self.root/'store')
        self.raw = self.root/'original.txt'
        self.raw.write_bytes(b'Fixture original rules, not a real rulebook.\nArticle 1: take one token.\n')
        self.metadata = {
            'sourceId':'fixture-source','gameId':'fixture-game','title':'Fixture rulebook',
            'sourceEdition':{'label':'Fixture edition A'},
            'acquisition':{'method':'provided','acquiredAt':'2026-11-07T00:00:00Z','privateLocator':'https://private.example.org/download?token=private-only-fixture',
                           'privateNote':'Purchaser/private note fixture: do not publish'},
            'redistribution':{'status':'unknown'},
        }
        self.proposal = {'source':{'kind':'Source','id':'fixture-source','revision':1,'title':'Fixture rules',
                                  'edition':{'label':'Fixture edition A'},'url':'https://example.org/rules',
                                  'accessed':'2026-11-07','reuse':'metadata-only'},
                         'citations':[{'source':{'id':'fixture-source','revision':1},'locator':'Article 1'}]}

    def capture(self):
        return self.store.capture(self.raw, copy.deepcopy(self.metadata), 'text/plain')

    def extract(self, capture, revision=1, payload=b'Article 1: take one token.\n'):
        path = self.root/'extracted.txt';path.write_bytes(payload)
        metadata = {'id':'plain-text','revision':revision,'extractor':{'name':'fixture-extractor','version':'1.0.0','options':{'language':'en'}},
                    'anchors':[{'locator':'Article 1','startByte':0,'endByte':len(payload),'page':1}]}
        return self.store.add_extract(capture['id'], path, metadata)

    def test_original_bytes_deduplicate_but_capture_identity_does_not(self):
        a,b = self.capture(),self.capture()
        self.assertNotEqual(a['id'], b['id'])
        self.assertEqual(a['object']['sha256'], hashlib.sha256(self.raw.read_bytes()).hexdigest())
        self.assertEqual(self.store.verify()['objects'],1)
        self.assertEqual(self.store.verify()['captures'],2)

    def test_extract_versions_preserve_original_and_prior_output(self):
        capture=self.capture();one=self.extract(capture);two=self.extract(capture,2,b'Corrected extraction.\n')
        self.assertEqual(two['originalDigest'],capture['object']['sha256'])
        self.assertEqual(two['previousDigest'],digest(one))
        self.assertNotEqual(one['object']['sha256'],two['object']['sha256'])
        self.assertEqual(self.store.get_extract(capture['id'],'plain-text',1),one)
        self.assertEqual(self.store.verify()['extracts'],2)

    def test_extract_cannot_skip_or_overwrite_revisions(self):
        capture=self.capture()
        with self.assertRaises(ReferenceError):self.extract(capture,2)
        self.extract(capture)
        with self.assertRaisesRegex(ReferenceError,'Immutable'):
            self.extract(capture,1,b'Different bytes')

    def test_extract_anchors_and_version_are_checked(self):
        capture=self.capture()
        metadata={'id':'text','revision':1,'extractor':{'name':'fixture','version':'latest','options':{}},
                  'anchors':[{'locator':'Article 1','startByte':0,'endByte':10**6}]}
        with self.assertRaisesRegex(ReferenceError,'exact recorded version'):
            self.store.add_extract(capture['id'],self.raw,metadata)
        metadata['extractor']['version']='1.0.0'
        with self.assertRaisesRegex(ReferenceError,'byte boundaries'):
            self.store.add_extract(capture['id'],self.raw,metadata)

    def test_review_and_promotion_export_only_explicit_public_fields(self):
        capture=self.capture();extract=self.extract(capture)
        review=self.store.review(capture['id'],self.proposal,'fixture-reviewer',extract_id='plain-text',revision=1)
        self.assertEqual(review['extract']['recordDigest'],digest(extract))
        output=self.root/'public-source.json'
        receipt=self.store.promote(review['id'],output)
        result=json.loads(output.read_text())
        validate_public_source(result)
        self.assertEqual(set(result),{'schemaVersion','source','citations','review'})
        for private in ['private-only-fixture','Purchaser/private',str(self.store.root),capture['id'],'originalDigest']:
            self.assertNotIn(private,output.read_text())
        self.assertEqual(receipt['outputDigest'],hashlib.sha256(output.read_bytes()).hexdigest())
        self.assertEqual(self.store.verify()['promotions'],1)

    def test_unknown_rights_allow_metadata_but_not_permission_claims(self):
        capture=self.capture()
        self.store.review(capture['id'],self.proposal,'fixture-reviewer')
        claimed=copy.deepcopy(self.proposal)
        claimed['source'].update(reuse='permission-recorded',permissionNote='Fixture permission')
        with self.assertRaisesRegex(ReferenceError,'redistribution permission'):
            self.store.review(capture['id'],claimed,'fixture-reviewer')
        self.metadata['redistribution']={'status':'permitted','basis':'Fictional grant for test bytes'}
        permitted=self.capture()
        self.store.review(permitted['id'],claimed,'fixture-reviewer')

    def test_source_identity_and_edition_cannot_be_switched_in_promotion(self):
        capture=self.capture()
        for field,value in [('id','another-source'),('edition',{'label':'Other edition'})]:
            proposal=copy.deepcopy(self.proposal);proposal['source'][field]=value
            if field=='id':proposal['citations'][0]['source']['id']=value
            with self.subTest(field=field),self.assertRaises(ReferenceError):
                self.store.review(capture['id'],proposal,'fixture-reviewer')

    def test_private_locators_and_signed_urls_never_promote(self):
        capture=self.capture()
        urls=['https://example.org/rules?X-Amz-Signature=fixture','https://user:pass@example.org/rules',
              'https://127.0.0.1/rules','https://192.168.0.1/rules','https://store.internal/rules','http://example.org/rules']
        for url in urls:
            proposal=copy.deepcopy(self.proposal);proposal['source']['url']=url
            with self.subTest(url=url),self.assertRaises(ReferenceError):
                self.store.review(capture['id'],proposal,'fixture-reviewer')
        for value in ['/private/fixture/capture.pdf','file:///tmp/fixture','s3://private-store/object']:
            proposal=copy.deepcopy(self.proposal);proposal['source']['title']=value
            with self.subTest(value=value),self.assertRaises(ReferenceError):
                self.store.review(capture['id'],proposal,'fixture-reviewer')

    def test_extra_private_fields_and_test_only_sources_rejected(self):
        capture=self.capture()
        for field,value in [('privateNote','private fixture'),('testOnly',True)]:
            proposal=copy.deepcopy(self.proposal);proposal['source'][field]=value
            with self.subTest(field=field),self.assertRaises(ReferenceError):
                self.store.review(capture['id'],proposal,'fixture-reviewer')

    def test_public_output_needs_existing_accepted_review(self):
        with self.assertRaises(ReferenceError):self.store.promote('0'*32,self.root/'output.json')
        self.assertFalse((self.root/'output.json').exists())

    def test_review_binds_exact_extract_even_when_newer_revision_exists(self):
        capture=self.capture();extract=self.extract(capture)
        review=self.store.review(capture['id'],self.proposal,'fixture-reviewer',extract_id='plain-text',revision=1)
        self.extract(capture,2,b'New extract\n')
        self.assertEqual(self.store.get_review(review['id'])['extract']['recordDigest'],digest(extract))

    def test_citation_must_resolve_in_the_selected_extract(self):
        capture=self.capture();self.extract(capture)
        self.proposal['citations'][0]['locator']='Article 2'
        with self.assertRaisesRegex(ReferenceError,'extract anchors'):
            self.store.review(capture['id'],self.proposal,'fixture-reviewer',extract_id='plain-text',revision=1)

    def test_public_revision_cannot_be_overwritten(self):
        capture=self.capture();review=self.store.review(capture['id'],self.proposal,'fixture-reviewer')
        output=self.root/'output.json';self.store.promote(review['id'],output)
        self.store.promote(review['id'],output)
        changed=copy.deepcopy(self.proposal);changed['source']['title']='A correction needs a new revision'
        other=self.store.review(capture['id'],changed,'fixture-reviewer')
        with self.assertRaisesRegex(ReferenceError,'different bytes'):self.store.promote(other['id'],output)

    def test_public_review_digest_rejects_changed_fields(self):
        capture=self.capture();review=self.store.review(capture['id'],self.proposal,'fixture-reviewer')
        result=self.store.public_source(review['id']);result['source']['title']='Changed after review'
        with self.assertRaisesRegex(ReferenceError,'review digest'):validate_public_source(result)

    def test_retrieval_requires_restricted_destination_and_checks_bytes(self):
        capture=self.capture()
        destination=self.root/'retrieved.txt'
        self.assertEqual(self.store.retrieve(capture['id'],destination),capture['object']['sha256'])
        self.assertEqual(destination.read_bytes(),self.raw.read_bytes())
        self.assertEqual(stat.S_IMODE(destination.stat().st_mode),0o600)
        with self.assertRaises(FileExistsError):self.store.retrieve(capture['id'],destination)
        (self.root/'public').mkdir(mode=0o755)
        with self.assertRaisesRegex(ReferenceError,'restricted'):
            self.store.retrieve(capture['id'],self.root/'public'/'copy.txt')
        with self.assertRaises(ReferenceError):self.store.retrieve(capture['id'],ROOT/'reference'/'copy.txt')

    def test_owner_and_group_permission_boundaries(self):
        self.assertEqual(stat.S_IMODE(self.store.root.stat().st_mode),0o700)
        with patch('tools.references.store.os.getuid',return_value=os.getuid()+1):
            with self.assertRaisesRegex(ReferenceError,'owner'):LocalStore(self.store.root)
        shared=LocalStore.create(self.root/'shared',access='group')
        self.assertEqual(stat.S_IMODE(shared.root.stat().st_mode),0o2770)
        self.assertEqual(stat.S_IMODE((shared.root/'.store.json').stat().st_mode),0o440)
        with patch('tools.references.store.os.getgid',return_value=123456),patch('tools.references.store.os.getgroups',return_value=[]):
            with self.assertRaisesRegex(ReferenceError,'group'):LocalStore(shared.root)
        self.store.root.chmod(0o755)
        with self.assertRaisesRegex(ReferenceError,'other users'):LocalStore(self.store.root)

    def test_initialization_cannot_consume_existing_data_or_a_git_checkout(self):
        with self.assertRaises(ReferenceError):LocalStore.create(self.store.root)
        checkout=self.root/'checkout';checkout.mkdir();(checkout/'.git').mkdir()
        with self.assertRaisesRegex(ReferenceError,'Git checkout'):LocalStore.create(checkout/'store')
        with self.assertRaises(ReferenceError):LocalStore.create(ROOT/'reference-store')

    def test_server_acl_mode_requires_explicit_confirmation_for_each_destination(self):
        root=self.root/'server-share';root.mkdir(mode=0o755)
        with self.assertRaisesRegex(ReferenceError,'explicit operator confirmation'):
            LocalStore.create(root,access='server-acl')
        shared=LocalStore.create(root,access='server-acl',server_acl_confirmed=True)
        self.assertEqual(stat.S_IMODE(root.stat().st_mode),0o755)
        self.assertEqual(LocalStore(root).config['access'],'server-acl')
        capture=shared.capture(self.raw,self.metadata,'text/plain')
        self.assertEqual(shared.get_capture(capture['id'])['object']['sha256'],hashlib.sha256(self.raw.read_bytes()).hexdigest())
        with self.assertRaisesRegex(ReferenceError,'backup destination'):
            shared.backup(self.root/'server-backup')
        checksum=shared.backup(self.root/'server-backup',server_acl_confirmed=True)
        with self.assertRaisesRegex(ReferenceError,'restore destination'):
            LocalStore.restore(self.root/'server-backup',self.root/'server-restored',checksum)
        restored=LocalStore.restore(self.root/'server-backup',self.root/'server-restored',checksum,server_acl_confirmed=True)
        self.assertEqual(restored.verify()['captures'],1)

    def test_symlinks_and_traversal_are_rejected(self):
        capture=self.capture()
        (self.root/'link').symlink_to(self.store.root,target_is_directory=True)
        with self.assertRaises(ReferenceError):LocalStore(self.root/'link')
        with self.assertRaises(ReferenceError):self.store.get_capture('../../private')
        blob=self.store.root/'objects/sha256'/capture['object']['sha256']
        blob.unlink();blob.symlink_to(self.raw)
        with self.assertRaisesRegex(ReferenceError,'Symlinks'):self.store.get_capture(capture['id'])

    def test_corrupted_original_or_private_record_is_not_retrievable(self):
        capture=self.capture();blob=self.store.root/'objects/sha256'/capture['object']['sha256']
        blob.chmod(0o600);blob.write_bytes(b'Corrupt')
        with self.assertRaisesRegex(ReferenceError,'verification'):self.store.get_capture(capture['id'])
        self.raw.write_bytes(b'Other original');capture=self.capture()
        record=self.store.root/'captures'/(capture['id']+'.json')
        wrapper=json.loads(record.read_text());wrapper['record']['metadata']['title']='Changed'
        record.chmod(0o600);record.write_text(json.dumps(wrapper))
        with self.assertRaisesRegex(ReferenceError,'record digest'):self.store.get_capture(capture['id'])

    def test_backup_restore_preserves_records_originals_extracts_and_reviews(self):
        capture=self.capture();self.extract(capture)
        review=self.store.review(capture['id'],self.proposal,'fixture-reviewer',extract_id='plain-text',revision=1)
        self.store.promote(review['id'],self.root/'public-source.json')
        backup=self.root/'backup';checksum=self.store.backup(backup)
        restored=LocalStore.restore(backup,self.root/'restored',checksum)
        self.assertEqual(restored.verify(),self.store.verify())
        self.assertEqual(restored.keys(),self.store.keys())
        for key in restored.keys():self.assertEqual(restored._get(key),self.store._get(key))
        self.assertEqual(restored.public_source(review['id']),self.store.public_source(review['id']))
        restored.retrieve(capture['id'],self.root/'restored-original.txt')
        self.assertEqual((self.root/'restored-original.txt').read_bytes(),self.raw.read_bytes())
        self.assertEqual(restored.get_extract(capture['id'],'plain-text',1)['originalDigest'],capture['object']['sha256'])

    def test_backup_manifest_and_payload_corruption_prevent_restore(self):
        capture=self.capture();backup=self.root/'backup';checksum=self.store.backup(backup)
        with self.assertRaisesRegex(ReferenceError,'manifest digest'):
            LocalStore.restore(backup,self.root/'bad-restore','0'*64)
        blob=backup/'objects/sha256'/capture['object']['sha256'];blob.chmod(0o600);blob.write_bytes(b'Corrupt')
        with self.assertRaises(ReferenceError):LocalStore.restore(backup,self.root/'bad-restore',checksum)
        self.assertFalse((self.root/'bad-restore').exists())

    def test_shared_group_backup_restore_and_nonempty_destination(self):
        shared=LocalStore.create(self.root/'shared',access='group')
        shared.capture(self.raw,self.metadata,'text/plain')
        checksum=shared.backup(self.root/'group-backup')
        restored=LocalStore.restore(self.root/'group-backup',self.root/'group-restored',checksum)
        self.assertEqual(restored.config['access'],'group')
        self.assertEqual(restored.verify()['captures'],1)
        with self.assertRaises(ReferenceError):LocalStore.restore(self.root/'group-backup',restored.root,checksum)

    def test_public_validation_has_no_private_store_dependency(self):
        capture=self.capture();review=self.store.review(capture['id'],self.proposal,'fixture-reviewer')
        exported=self.store.public_source(review['id'])
        with patch.dict(os.environ,{'RULEBOOKS_REFERENCE_ROOT':'/private/unavailable-reference-store'}),patch.object(LocalStore,'__init__',side_effect=AssertionError('Private store accessed')):
            validate_public_source(exported)

    def test_clean_candidate_validates_promoted_metadata_without_private_access(self):
        capture=self.capture();review=self.store.review(capture['id'],self.proposal,'fixture-reviewer')
        exported=self.store.public_source(review['id'])
        files=snapshot(ROOT)
        files['data/sources/fixture-source/1.json']=canonical(exported)
        with patch.dict(os.environ,{'RULEBOOKS_REFERENCE_ROOT':'/private/unavailable-reference-store'}),patch.object(LocalStore,'__init__',side_effect=AssertionError('Private store accessed')):
            self.assertEqual(validate_candidate(files)['publicSources'],1)
        files['data/sources/fixture-source/2.json']=files.pop('data/sources/fixture-source/1.json')
        with self.assertRaisesRegex(CheckError,'filename'):
            validate_candidate(files)

    def test_promotion_receipt_source_pin_is_checked(self):
        capture=self.capture();review=self.store.review(capture['id'],self.proposal,'fixture-reviewer')
        receipt=self.store.promote(review['id'],self.root/'output.json')
        path=self.store.root/'promotions'/(receipt['id']+'.json')
        wrapper=json.loads(path.read_text());wrapper['record']['source']['id']='another-source'
        wrapper['sha256']=digest(wrapper['record'])
        path.chmod(0o600);path.write_text(json.dumps(wrapper))
        with self.assertRaisesRegex(ReferenceError,'receipt mismatch'):self.store.verify()

    def test_cli_reports_identifiers_not_private_paths_or_metadata(self):
        metadata=self.root/'metadata.json';metadata.write_text(json.dumps(self.metadata))
        result=subprocess.run([sys.executable,'-m','tools.references','capture','--file',str(self.raw),'--metadata',str(metadata),'--media-type','text/plain'],
                              cwd=ROOT,env={**os.environ,'RULEBOOKS_REFERENCE_ROOT':str(self.store.root)},capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertNotIn(str(self.root),result.stdout+result.stderr)
        self.assertNotIn('Purchaser/private',result.stdout+result.stderr)
        self.assertEqual(set(json.loads(result.stdout)),{'captureId','sha256'})


if __name__ == '__main__':
    unittest.main()
