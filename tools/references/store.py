"""Append-only local reference storage, guarded by POSIX owner/group permissions."""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import uuid

from .contracts import ROOT, ReferenceError, canonical, digest, require, validate, validate_proposal, validate_public_source

MAX_BYTES = 256 * 1024 * 1024
ID = r'[a-f0-9]{32}'
SLUG = r'[a-z0-9]+(?:-[a-z0-9]+)*'
KEY = re.compile(rf'(?:objects/sha256/[a-f0-9]{{64}}|captures/{ID}\.json|extracts/{ID}/{SLUG}/[1-9][0-9]*\.json|reviews/{ID}\.json|promotions/{ID}\.json|handoffs/{SLUG}\.json|\.store\.json|\.backup\.json)')


def now():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def parse(data):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'Duplicate key in private record')
            result[key] = value
        return result
    def invalid(value):
        raise ReferenceError('Non-finite number in private record')
    return json.loads(data, object_pairs_hook=pairs, parse_constant=invalid)


def external_path(path):
    path = Path(path).expanduser()
    require(path.is_absolute(), 'Private paths must be absolute')
    require(path == path.resolve(), 'Private paths must not contain symlinks or traversal')
    require(not path.is_relative_to(ROOT), 'Private storage/output must be outside the repository')
    require(not any((p / '.git').exists() for p in [path, *path.parents]), 'Private storage/output must be outside any Git checkout')
    return path


def bytes_from(path):
    flags = os.O_RDONLY | os.O_NOFOLLOW
    with os.fdopen(os.open(path, flags), 'rb') as stream:
        require(stat.S_ISREG(os.fstat(stream.fileno()).st_mode), 'Input must be a regular file')
        data = stream.read(MAX_BYTES + 1)
    require(0 < len(data) <= MAX_BYTES, 'Input must be nonempty and at most 256 MiB')
    return data


class LocalStore:
    def __init__(self, root, *, allow_backup=False):
        self.root = external_path(root)
        require(self.root.is_dir(), 'Reference store is not initialized')
        self.allow_backup = allow_backup
        marker = self.root / '.store.json'
        require(marker.is_file() and not marker.is_symlink(), 'Reference store is not initialized')
        self.config = parse(bytes_from(marker))
        require(set(self.config) == {'schemaVersion','id','access','gid'} and self.config['schemaVersion'] == '0.1.0'
                and re.fullmatch(ID, self.config['id']) and self.config['access'] in {'owner','group','server-acl'}, 'Invalid store configuration')
        self._permissions(self.root, directory=True)
        self._permissions(marker)

    @classmethod
    def _blank(cls, root, access, *, allow_backup=False, server_acl_confirmed=False):
        root = external_path(root)
        require(not root.exists() or root.is_dir() and not any(root.iterdir()), 'Initialization requires a new or empty directory')
        root.mkdir(mode=0o700, parents=False, exist_ok=True)
        require(access in {'owner','group','server-acl'}, 'Unknown storage access policy')
        require(access != 'server-acl' or server_acl_confirmed, 'Server ACL mode requires explicit operator confirmation')
        require(access == 'server-acl' or root.stat().st_uid == os.getuid(), 'Only the directory owner may initialize storage')
        instance = cls.__new__(cls)
        instance.root, instance.allow_backup = root, allow_backup
        instance.config = {'schemaVersion':'0.1.0','id':uuid.uuid4().hex,'access':access,'gid':root.stat().st_gid}
        require(access != 'group' or root.stat().st_gid in {os.getgid(), *os.getgroups()}, 'Store group is not available to this operator')
        if access != 'server-acl':
            root.chmod(instance.directory_mode)
        return instance

    @classmethod
    def create(cls, root, access='owner', *, server_acl_confirmed=False):
        instance = cls._blank(root, access, server_acl_confirmed=server_acl_confirmed)
        instance._put('.store.json', canonical(instance.config))
        return cls(root)

    @property
    def directory_mode(self):
        return 0o2770 if self.config['access'] == 'group' else 0o700

    @property
    def file_mode(self):
        return 0o440 if self.config['access'] == 'group' else 0o400

    def _permissions(self, path, *, directory=False):
        require(not path.is_symlink(), 'Symlinks are forbidden in reference storage')
        info = path.stat()
        require(stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode), 'Unexpected reference storage entry type')
        if self.config['access'] == 'server-acl':
            return  # Access is delegated explicitly to server ACLs/client mount policy.
        require(info.st_mode & 0o007 == 0, 'Reference storage grants access to other users')
        if self.config['access'] == 'owner':
            require(info.st_uid == os.getuid() and info.st_mode & 0o077 == 0, 'Reference storage is restricted to its owner')
        else:
            require(info.st_gid == self.config['gid'] and self.config['gid'] in {os.getgid(), *os.getgroups()}, 'Operator is not in the reference storage group')

    def _path(self, key, create=False):
        require(KEY.fullmatch(key), 'Invalid reference object key')
        path = self.root / key
        current = self.root
        self._permissions(current, directory=True)
        for part in Path(key).parts[:-1]:
            current = current / part
            if create and not current.exists():
                try:
                    current.mkdir(mode=self.directory_mode)
                    if self.config['access'] != 'server-acl':
                        current.chmod(self.directory_mode)
                except FileExistsError:
                    pass
            require(current.is_dir(), 'Reference record does not exist')
            self._permissions(current, directory=True)
        if path.exists() or path.is_symlink():
            self._permissions(path)
        return path

    def _get(self, key):
        path = self._path(key)
        require(path.is_file(), 'Reference record does not exist')
        return bytes_from(path)

    def _put(self, key, data):
        require(0 < len(data) <= MAX_BYTES, 'Reference object exceeds the supported size')
        path = self._path(key, create=True)
        temporary = self.root / ('.pending-' + uuid.uuid4().hex)
        try:
            with os.fdopen(os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            if self.config['access'] == 'group':
                os.chown(temporary, -1, self.config['gid'])
            if self.config['access'] != 'server-acl':
                temporary.chmod(self.file_mode)
            try:
                os.link(temporary, path, follow_symlinks=False)
            except FileExistsError:
                require(self._get(key) == data, 'Immutable reference record already exists with different bytes')
        finally:
            temporary.unlink(missing_ok=True)

    def _record(self, key, kind):
        wrapper = parse(self._get(key))
        require(set(wrapper) == {'record','sha256'} and wrapper['sha256'] == digest(wrapper['record']), 'Private record digest mismatch')
        validate(kind, wrapper['record'])
        return wrapper['record']

    def _put_record(self, key, kind, record):
        validate(kind, record)
        self._put(key, canonical({'record':record,'sha256':digest(record)}))

    def _blob(self, data, media_type):
        sha = hashlib.sha256(data).hexdigest()
        self._put('objects/sha256/' + sha, data)
        return {'sha256':sha,'size':len(data),'mediaType':media_type}

    def _blob_bytes(self, entry):
        data = self._get('objects/sha256/' + entry['sha256'])
        require(len(data) == entry['size'] and hashlib.sha256(data).hexdigest() == entry['sha256'], 'Reference bytes fail size/digest verification')
        return data

    def capture(self, source_file, metadata, media_type):
        return self.capture_bytes(bytes_from(source_file), metadata, media_type)

    def capture_bytes(self, data, metadata, media_type):
        validate('captureMetadata', metadata)
        require(0 < len(data) <= MAX_BYTES, 'Input must be nonempty and at most 256 MiB')
        record = {'schemaVersion':'0.1.0','kind':'capture','id':uuid.uuid4().hex,'createdAt':now(),
                  'metadata':metadata,'object':{'sha256':hashlib.sha256(data).hexdigest(),'size':len(data),'mediaType':media_type}}
        validate('capture', record)
        self._blob(data, media_type)
        self._put_record('captures/'+record['id']+'.json', 'capture', record)
        return record

    def get_capture(self, capture_id):
        record = self._record('captures/'+capture_id+'.json', 'capture')
        require(record['id'] == capture_id, 'Capture identity mismatch')
        self._blob_bytes(record['object'])
        return record

    def add_extract(self, capture_id, source_file, metadata, media_type='text/plain; charset=utf-8'):
        return self.extract_bytes(capture_id, bytes_from(source_file), metadata, media_type)

    def extract_bytes(self, capture_id, data, metadata, media_type='text/plain; charset=utf-8'):
        capture = self.get_capture(capture_id)
        validate('extractMetadata', metadata)
        require(metadata['extractor']['version'].lower() not in {'latest','current','unknown'} and not any(c in metadata['extractor']['version'] for c in '*^~<>'), 'Extractor needs an exact recorded version')
        require(0 < len(data) <= MAX_BYTES, 'Input must be nonempty and at most 256 MiB')
        require(all(0 <= a['startByte'] < a['endByte'] <= len(data) for a in metadata['anchors']), 'Extract anchors exceed the byte boundaries')
        record = {'schemaVersion':'0.1.0','kind':'extract','createdAt':now(),'captureId':capture_id,
                  'captureDigest':digest(capture),'originalDigest':capture['object']['sha256'],'metadata':metadata,
                  'object':{'sha256':hashlib.sha256(data).hexdigest(),'size':len(data),'mediaType':media_type}}
        if metadata['revision'] > 1:
            record['previousDigest'] = digest(self.get_extract(capture_id, metadata['id'], metadata['revision']-1))
        validate('extract', record)
        self._blob(data, media_type)
        self._put_record(f"extracts/{capture_id}/{metadata['id']}/{metadata['revision']}.json", 'extract', record)
        return record

    def get_extract(self, capture_id, extract_id, revision):
        record = self._record(f'extracts/{capture_id}/{extract_id}/{revision}.json', 'extract')
        capture = self.get_capture(capture_id)
        require(record['captureId'] == capture_id and record['metadata']['id'] == extract_id and record['metadata']['revision'] == revision, 'Extract identity mismatch')
        require(record['captureDigest'] == digest(capture) and record['originalDigest'] == capture['object']['sha256'], 'Extract belongs to different original bytes')
        data = self._blob_bytes(record['object'])
        require(all(0 <= a['startByte'] < a['endByte'] <= len(data) for a in record['metadata']['anchors']), 'Extract anchors exceed the byte boundaries')
        if revision > 1:
            previous = self._record(f'extracts/{capture_id}/{extract_id}/{revision-1}.json','extract')
            require(record['previousDigest'] == digest(previous), 'Extract predecessor digest mismatch')
        return record

    def review(self, capture_id, proposal, reviewer, *, extract_id=None, revision=None):
        capture = self.get_capture(capture_id)
        validate_proposal(proposal)
        require(proposal['source']['id'] == capture['metadata']['sourceId'], 'Source proposal does not identify this capture source')
        require(proposal['source']['edition'] == capture['metadata']['sourceEdition'], 'Public source edition differs from the captured source edition')
        require(proposal['source']['reuse'] != 'permission-recorded' or capture['metadata']['redistribution']['status'] == 'permitted', 'Capture has no recorded redistribution permission')
        require(str(self.root) not in canonical(proposal).decode(), 'Public proposal contains a private storage location')
        record = {'schemaVersion':'0.1.0','kind':'review','id':uuid.uuid4().hex,'createdAt':now(),
                  'captureId':capture_id,'captureDigest':digest(capture),'proposal':proposal,'proposalDigest':digest(proposal),
                  'reviewer':reviewer,'decision':'accepted','extractionQuality':'not-used'}
        require((extract_id is None) == (revision is None), 'Extract ID and revision must be supplied together')
        if extract_id is not None:
            extract = self.get_extract(capture_id, extract_id, revision)
            locators = {anchor['locator'] for anchor in extract['metadata']['anchors']}
            require(all(citation['locator'] in locators for citation in proposal['citations']), 'Citation locator is absent from the selected extract anchors')
            record['extract'] = {'id':extract_id,'revision':revision,'recordDigest':digest(extract)}
            record['extractionQuality'] = 'accepted'
        self._put_record('reviews/'+record['id']+'.json', 'review', record)
        return record

    def get_review(self, review_id):
        record = self._record('reviews/'+review_id+'.json', 'review')
        require(record['id'] == review_id, 'Review identity mismatch')
        capture = self.get_capture(record['captureId'])
        require(record['captureDigest'] == digest(capture) and record['proposalDigest'] == digest(record['proposal']), 'Review subject digest mismatch')
        validate_proposal(record['proposal'])
        require(record['proposal']['source']['id'] == capture['metadata']['sourceId'] and record['proposal']['source']['edition'] == capture['metadata']['sourceEdition'], 'Reviewed source identity mismatch')
        require(record['proposal']['source']['reuse'] != 'permission-recorded' or capture['metadata']['redistribution']['status'] == 'permitted', 'Review has no recorded redistribution permission')
        if 'extract' in record:
            pin = record['extract']
            extract = self.get_extract(record['captureId'], pin['id'], pin['revision'])
            require(pin['recordDigest'] == digest(extract), 'Review extract digest mismatch')
            locators = {anchor['locator'] for anchor in extract['metadata']['anchors']}
            require(all(citation['locator'] in locators for citation in record['proposal']['citations']), 'Reviewed citation is absent from extract anchors')
        return record

    def public_source(self, review_id):
        review = self.get_review(review_id)
        result = {'schemaVersion':'0.1.0', **review['proposal'], 'review':{
            'reviewer':review['reviewer'],'reviewedAt':review['createdAt'],'proposalDigest':review['proposalDigest']}}
        return validate_public_source(result)

    def promote(self, review_id, output):
        result = self.public_source(review_id)
        path = Path(output).absolute()
        require(path == path.resolve() and not path.is_relative_to(self.root), 'Public output cannot be a private store path or symlink')
        source = result['source']
        if path.is_relative_to(ROOT):
            require(path == ROOT / 'data/sources' / source['id'] / (str(source['revision'])+'.json'), 'Public source output must use its canonical repository location')
        require(path.suffix == '.json', 'Public source output must be JSON')
        data = canonical(result) + b'\n'
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            require(bytes_from(path) == data, 'Public source revision already exists with different bytes')
        else:
            temporary = path.parent / ('.source-' + uuid.uuid4().hex)
            try:
                with os.fdopen(os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644), 'wb') as stream:
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
                try:
                    os.link(temporary, path, follow_symlinks=False)
                except FileExistsError:
                    require(bytes_from(path) == data, 'Public source revision already exists with different bytes')
            finally:
                temporary.unlink(missing_ok=True)
        review = self.get_review(review_id)
        event = {'schemaVersion':'0.1.0','kind':'promotion','id':uuid.uuid4().hex,'createdAt':now(),
                 'reviewId':review_id,'reviewDigest':digest(review),'source':{'id':source['id'],'revision':source['revision']},
                 'outputDigest':hashlib.sha256(data).hexdigest()}
        self._put_record('promotions/'+event['id']+'.json','promotion',event)
        return event

    def retrieve(self, capture_id, output, *, extract_id=None, revision=None):
        path = external_path(output)
        require(not path.is_relative_to(self.root), 'Retrieval output must be outside the store')
        require((extract_id is None) == (revision is None), 'Extract ID and revision must be supplied together')
        record = self.get_capture(capture_id) if extract_id is None else self.get_extract(capture_id, extract_id, revision)
        data = self._blob_bytes(record['object'])
        # Do not create world-readable copies in a permissive output directory.
        require(path.parent.is_dir() and path.parent.stat().st_mode & 0o007 == 0, 'Retrieval directory must be restricted')
        with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as stream:
            stream.write(data)
        return record['object']['sha256']

    def keys(self):
        keys = []
        for parent, dirs, files in os.walk(self.root, followlinks=False):
            self._permissions(Path(parent), directory=True)
            for directory in dirs:
                self._permissions(Path(parent)/directory, directory=True)
            for name in files:
                path = Path(parent)/name
                key = path.relative_to(self.root).as_posix()
                require(KEY.fullmatch(key) and (self.allow_backup or key != '.backup.json'), 'Unexpected store entry; pause writes and inspect locally')
                self._permissions(path)
                keys.append(key)
        return sorted(keys)

    def verify(self):
        keys = self.keys()
        counts = {'captures':0,'extracts':0,'reviews':0,'promotions':0,'objects':0,'handoffs':0}
        for key in keys:
            if key.startswith('objects/'):
                require(hashlib.sha256(self._get(key)).hexdigest() == key.rsplit('/',1)[1], 'Stored object digest mismatch')
                counts['objects'] += 1
            elif key.startswith('captures/'):
                self.get_capture(Path(key).stem);counts['captures'] += 1
            elif key.startswith('extracts/'):
                parts = key.split('/')
                self.get_extract(parts[1], parts[2], int(Path(parts[3]).stem));counts['extracts'] += 1
            elif key.startswith('reviews/'):
                self.get_review(Path(key).stem);counts['reviews'] += 1
            elif key.startswith('handoffs/'):
                from .handoff import verify_receipt
                verify_receipt(self, Path(key).stem)
                counts['handoffs'] += 1
            elif key.startswith('promotions/'):
                record = self._record(key,'promotion')
                review = self.get_review(record['reviewId'])
                output = self.public_source(record['reviewId'])
                pin = {'id':output['source']['id'],'revision':output['source']['revision']}
                require(record['id'] == Path(key).stem and record['source'] == pin and record['reviewDigest'] == digest(review) and record['outputDigest'] == hashlib.sha256(canonical(output)+b'\n').hexdigest(), 'Promotion receipt mismatch')
                counts['promotions'] += 1
        return counts

    def backup(self, output, *, server_acl_confirmed=False):
        self.verify()
        require(self.config['access'] != 'server-acl' or server_acl_confirmed, 'Confirm backup destination access controls for server ACL storage')
        destination = external_path(output)
        require(not destination.exists() and not destination.is_relative_to(self.root), 'Backup needs a new directory outside the store')
        temporary = destination.parent / ('.reference-copy-' + uuid.uuid4().hex)
        try:
            target = LocalStore._blank(temporary, self.config['access'], allow_backup=True, server_acl_confirmed=server_acl_confirmed)
            target.config = dict(self.config)
            if target.config['access'] == 'group':
                os.chown(target.root, -1, target.config['gid'])
            rows = []
            for key in self.keys():
                require(key != '.backup.json', 'Back up a live store, not a backup snapshot')
                data = self._get(key)
                target._put(key,data)
                rows.append({'path':key,'sha256':hashlib.sha256(data).hexdigest(),'size':len(data)})
            manifest = {'schemaVersion':'0.1.0','kind':'reference-backup','createdAt':now(),'files':rows}
            target._put('.backup.json',canonical(manifest))
            target.verify()
            temporary.rename(destination)
            return digest(manifest)
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)

    @classmethod
    def restore(cls, backup, output, expected_digest, *, server_acl_confirmed=False):
        source = cls(backup, allow_backup=True)
        require(source.config['access'] != 'server-acl' or server_acl_confirmed, 'Confirm restore destination access controls for server ACL storage')
        manifest = parse(source._get('.backup.json'))
        require(digest(manifest) == expected_digest and set(manifest) == {'schemaVersion','kind','createdAt','files'}
                and manifest['schemaVersion'] == '0.1.0' and manifest['kind'] == 'reference-backup', 'Backup manifest digest/format mismatch')
        entries = manifest['files']
        require(isinstance(entries,list) and all(isinstance(e,dict) and set(e)=={'path','sha256','size'} for e in entries), 'Invalid backup entries')
        names = [e['path'] for e in entries]
        require(len(names)==len(set(names)) and set(names) == set(source.keys())-{'.backup.json'}, 'Backup file inventory mismatch')
        source.verify()
        destination = external_path(output)
        require(not destination.exists() and not destination.is_relative_to(source.root), 'Restore needs a new directory outside the backup')
        temporary = destination.parent / ('.reference-copy-' + uuid.uuid4().hex)
        try:
            target = cls._blank(temporary, source.config['access'], server_acl_confirmed=server_acl_confirmed)
            target.config = dict(source.config)
            if target.config['access'] == 'group':
                os.chown(target.root, -1, target.config['gid'])
            for entry in entries:
                data = source._get(entry['path'])
                require(len(data) == entry['size'] and hashlib.sha256(data).hexdigest() == entry['sha256'], 'Backup file digest mismatch')
                target._put(entry['path'],data)
            target.verify()
            temporary.rename(destination)
            return cls(destination)
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)
