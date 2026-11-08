"""Test the collector/RuleBooks boundary with synthetic private handoffs."""

import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tools.references.contracts import ReferenceError
from tools.references.handoff import import_handoff
from tools.references.store import LocalStore


class ReferenceHandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='rulebooks-handoff-test-');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.collection=self.root/'collection';self.collection.mkdir()
        self.store=LocalStore.create(self.root/'managed')
        self.original=b'Synthetic original document bytes, not a real PDF.\n'
        self.text=b'Article 1: take one token.\n'
        self.image=b'Fixture image bytes, never decoded by intake.\n'
        def artifact(name,data,media):
            (self.collection/name).write_bytes(data)
            return {'path':name,'sha256':hashlib.sha256(data).hexdigest(),'size':len(data),'mediaType':media}
        def metadata(id,data):
            return {'id':id,'revision':1,'extractor':{'name':'fixture-processor','version':'1.0.0','options':{}},
                    'anchors':[{'locator':'Article 1','page':1,'startByte':0,'endByte':len(data)}]}
        self.manifest={'schemaVersion':'0.1.0','kind':'reference-handoff','handoffId':'fixture-handoff',
                       'capture':{'sourceId':'fixture-source','gameId':'fixture-game','title':'Fixture rules',
                                  'sourceEdition':{'unknown':True},'acquisition':{'method':'provided','acquiredAt':'2026-11-07T00:00:00Z'},
                                  'redistribution':{'status':'unknown'}},
                       'original':artifact('original.pdf',self.original,'application/pdf'),
                       'derived':[{'file':artifact('text.txt',self.text,'text/plain'),'metadata':metadata('text',self.text)},
                                  {'file':artifact('page.png',self.image,'image/png'),'metadata':metadata('page-image',self.image)}]}
        self.path=self.collection/'handoff.json'

    def write_manifest(self):
        self.path.write_text(json.dumps(self.manifest))

    def test_import_copies_only_named_artifacts_and_keeps_collection_unchanged(self):
        (self.collection/'debug.log').write_text('Not selected for intake')
        self.write_manifest();before={p.name:p.read_bytes() for p in self.collection.iterdir()}
        result=import_handoff(self.store,self.path)
        self.assertEqual(self.store.verify(),{'captures':1,'extracts':2,'reviews':0,'promotions':0,'objects':3,'handoffs':1})
        self.assertEqual({p.name:p.read_bytes() for p in self.collection.iterdir()},before)
        self.assertEqual(self.store.get_capture(result['captureId'])['metadata']['sourceId'],'fixture-source')
        self.assertFalse(any('debug' in key for key in self.store.keys()))

    def test_successful_handoff_retry_is_idempotent(self):
        self.write_manifest();first=import_handoff(self.store,self.path)
        second=import_handoff(self.store,self.path)
        self.assertEqual(first,second)
        self.assertEqual(self.store.verify()['captures'],1)
        self.manifest['capture']['title']='Changed sealed manifest';self.write_manifest()
        with self.assertRaisesRegex(ReferenceError,'already identifies different'):
            import_handoff(self.store,self.path)

    def test_bad_checksum_fails_before_any_capture_is_written(self):
        self.manifest['derived'][1]['file']['sha256']='0'*64;self.write_manifest()
        with self.assertRaisesRegex(ReferenceError,'size/digest'):import_handoff(self.store,self.path)
        self.assertEqual(self.store.verify()['captures'],0)
        self.assertEqual(self.store.verify()['objects'],0)

    def test_unready_or_unattributed_manifest_is_rejected(self):
        del self.manifest['capture']['acquisition'];self.write_manifest()
        with self.assertRaises(ReferenceError):import_handoff(self.store,self.path)

    def test_traversal_and_symlink_cannot_read_outside_handoff(self):
        self.manifest['original']['path']='../elsewhere.pdf';self.write_manifest()
        with self.assertRaises(ReferenceError):import_handoff(self.store,self.path)
        outside=self.root/'elsewhere.pdf';outside.write_bytes(self.original)
        (self.collection/'original.pdf').unlink();(self.collection/'original.pdf').symlink_to(outside)
        self.manifest['original']['path']='original.pdf';self.write_manifest()
        with self.assertRaises(OSError):import_handoff(self.store,self.path)
        self.assertEqual(self.store.verify()['captures'],0)

    def test_duplicate_artifacts_and_missing_extract_revision_fail(self):
        self.manifest['derived'][1]['file']=copy.deepcopy(self.manifest['derived'][0]['file']);self.write_manifest()
        with self.assertRaisesRegex(ReferenceError,'repeats an artifact'):import_handoff(self.store,self.path)
        self.manifest['derived'].pop();self.manifest['derived'][0]['metadata']['revision']=2;self.write_manifest()
        with self.assertRaisesRegex(ReferenceError,'contiguous extract revisions'):import_handoff(self.store,self.path)

    def test_original_only_handoff_is_valid(self):
        del self.manifest['derived'];self.write_manifest()
        result=import_handoff(self.store,self.path)
        self.assertEqual(result['extracts'],[])
        self.assertEqual(self.store.verify()['extracts'],0)

    def test_handoff_receipt_survives_backup_restore(self):
        self.write_manifest();result=import_handoff(self.store,self.path)
        backup=self.root/'backup';checksum=self.store.backup(backup)
        restored=LocalStore.restore(backup,self.root/'restored',checksum)
        self.assertEqual(import_handoff(restored,self.path),result)
        self.assertEqual(restored.verify(),self.store.verify())


if __name__=='__main__':unittest.main()
