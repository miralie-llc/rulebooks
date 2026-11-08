import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from tools.prepare_site import preview_catalog
from tools.site_indexes import indexes
from tools.site_gaps import selected_gaps
from tools.site_vocabulary import vocabulary
from tools.assemble_publication import sha
from tools.validate_publication import ContractError

ROOT=Path(__file__).resolve().parents[1]


class SiteIndexTests(unittest.TestCase):
    def setUp(self):
        self.content=preview_catalog(ROOT/'data/catalog/catalog.json')
        self.content['vocabulary']=vocabulary(ROOT/'docs/reference/vocabulary.md')

    def test_budget_rejects_large_game_metadata(self):
        next(r for r in self.content['records'] if r['kind']=='Game')['title']='x'*21000
        with self.assertRaises(ContractError):indexes(self.content,{})

    def test_no_implicit_gap_publication(self):
        self.assertEqual(selected_gaps(ROOT,self.content)['items'],[])

    def test_gap_selection_requires_exact_bytes_and_actual_target_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for name in ('data','docs','work','schema'):shutil.copytree(ROOT/name,root/name)
            edition=next(r for r in self.content['records'] if r['kind']=='RulebookEdition')
            item={'schemaVersion':'0.1.0','id':'semantic-fixture','queue':'semantic','kind':'semantic-gap',
                  'title':'Temporary selection test only','status':'review',
                  'target':{'kind':'rulebook','id':edition['id'],'revision':str(edition['revision'])},
                  'acceptance':['Test the explicit gap projection'],
                  'gap':{'classification':'needs-triage','problem':'Fictional projection test','expected':'Exact evidence','example':'A test record'},
                  'evidence':[{'path':f"data/catalog/records/RulebookEdition-{edition['id']}-{edition['revision']}.json",'note':'Test evidence'}]}
            file=root/'work/semantic/semantic-fixture.json';file.parent.mkdir(exist_ok=True);file.write_text(json.dumps(item))
            selection=root/'data/site/gaps.json'
            def pin():selection.write_text(json.dumps({'schemaVersion':'0.1.0','items':[{'id':item['id'],'sha256':sha(file.read_bytes())}]}))
            pin();self.assertEqual(selected_gaps(root,self.content)['items'][0]['target'],item['target'])
            file.write_text(file.read_text()+'\n')
            with self.assertRaises(ContractError):selected_gaps(root,self.content)
            item['target']['revision']='999';file.write_text(json.dumps(item));pin()
            with self.assertRaises(ContractError):selected_gaps(root,self.content)
            item['target']['revision']=str(edition['revision']);item['evidence']=[];file.write_text(json.dumps(item));pin()
            with self.assertRaises(ContractError):selected_gaps(root,self.content)
