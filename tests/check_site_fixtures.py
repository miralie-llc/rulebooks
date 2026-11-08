"""Render fictional model fixtures in an isolated build, never into the real site."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from html.parser import HTMLParser
from urllib.parse import urlsplit, unquote

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.assemble_publication import canonical, record_path
from tools.site_vocabulary import vocabulary
from tools.site_indexes import indexes
from tools.runtime.specimens import build_specimens
from tools.runtime.nim import build_nim


class Links(HTMLParser):
    def __init__(self):
        super().__init__();self.links=[];self.ids=[]
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if 'id' in attrs:self.ids.append(attrs['id'])
        for key in ('href','src'):
            if key in attrs:self.links.append(attrs[key])


def check():
    fixture=json.loads((ROOT/'tests/fixtures/publication/first-games.json').read_text())
    publisher=json.loads((ROOT/'tests/fixtures/publication/publisher-editions.json').read_text())
    records=fixture['records']+publisher['records']
    release=next(r for r in records if r['kind']=='BGSMRelease')
    archived=copy.deepcopy(release);archived.update(version='0.0.0-fixture.0',status='archived')
    release.update(previous=archived['version'],breaking=True,migration='Fictional migration example for rendering tests.')
    records.append(archived)
    fixture_content={'mode':'contract-fixture','schemaVersion':'0.1.0','records':records,
                     'games':fixture['publication']['games']+publisher['publication']['games'],
                     'vocabulary':vocabulary(ROOT/'docs/reference/vocabulary.md'), 'gaps':{'items':[]}}
    parent=ROOT/'.cache';parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='site-fixture-',dir=parent) as directory:
        root=Path(directory)
        for name in ('astro.config.mjs','package.json','tsconfig.json'):shutil.copyfile(ROOT/name,root/name)
        shutil.copytree(ROOT/'src',root/'src')
        (root/'node_modules').symlink_to(ROOT/'node_modules',target_is_directory=True)
        cache=root/'.cache/site-generated';cache.mkdir(parents=True)
        (cache/'content.json').write_bytes(canonical(fixture_content))
        for record in records:
            target=cache/'public/data'/record_path(record);target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(canonical({'purpose':'contract-fixture','record':record}))
        target=cache/'public/data/vocabulary/0.2.json';target.parent.mkdir(parents=True)
        target.write_bytes(canonical(fixture_content['vocabulary']))
        (cache/'public/data/gaps.json').write_bytes(canonical(fixture_content['gaps']))
        outputs={p.relative_to(cache).as_posix():p.read_bytes() for p in (cache/'public').rglob('*') if p.is_file()}
        specimen_files,specimens=build_specimens()
        outputs.update(specimen_files)
        for name,raw in specimen_files.items():
            target=cache/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
        (cache/'specimens.json').write_bytes(canonical(specimens))
        nim_files,nim=build_nim()
        outputs.update(nim_files)
        for name,raw in nim_files.items():
            target=cache/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
        (cache/'nim.json').write_bytes(canonical(nim))
        generated,search,downloads,budget=indexes(fixture_content,outputs)
        for name,raw in generated.items():
            target=cache/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
        for name,value in [('search',search),('downloads',downloads),('budget',budget)]:
            (cache/(name+'.json')).write_bytes(canonical(value))
        result=subprocess.run([os.environ.get('RULEBOOKS_NODE','node'),str(ROOT/'node_modules/astro/bin/astro.mjs'),'build'],cwd=root,
                              env={**os.environ,'ASTRO_TELEMETRY_DISABLED':'1'},capture_output=True,text=True)
        if result.returncode:raise AssertionError(result.stdout+result.stderr)
        pages={}
        for file in (root/'dist').rglob('*.html'):
            parser=Links();parser.feed(file.read_text());pages[file]=parser
            assert len(parser.ids)==len(set(parser.ids)),file
            assert 'Contract fixture' in file.read_text(),file
        for file,parser in pages.items():
            for href in parser.links:
                url=urlsplit(href)
                if url.scheme or url.netloc:continue
                target=root/'dist'/url.path.lstrip('/') if url.path else file
                if target.is_dir():target=target/'index.html'
                assert target.is_file(),(file,href)
                if url.fragment and target in pages:assert unquote(url.fragment) in pages[target].ids,(file,href)
        concept=root/'dist/bgsm/0.0.0-fixture.1/concepts/state/index.html'
        assert 'Rules using this concept' in concept.read_text()
        assert '/editions/' in concept.read_text()
        assert (root/'dist/bgsm/0.0.0-fixture.0/index.html').exists()
        assert 'Breaking change' in (root/'dist/bgsm/0.0.0-fixture.1/index.html').read_text()
        assert 'Publisher edition:' in (root/'dist/games/fixture-orchard-1/index.html').read_text()
        print(f'Isolated model/publisher fixture build: {len(pages)} pages and all local links passed.')


if __name__=='__main__':check()
