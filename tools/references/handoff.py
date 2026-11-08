"""Import only explicitly named, checksum-verified companion workflow artifacts."""

import hashlib
import os
from pathlib import Path, PurePosixPath
import stat

from .contracts import digest, require, validate
from .store import MAX_BYTES, bytes_from, external_path, now, parse


def read_artifact(root, entry):
    name = entry['path']
    path = PurePosixPath(name)
    require(name and path.parts and not path.is_absolute() and '..' not in path.parts and '\\' not in name and str(path) == name,
            'Handoff artifacts require normalized relative paths inside the handoff directory')
    # Resolve each directory through no-follow descriptors. A collector changing a
    # path to a symlink must not make us read elsewhere on this machine.
    directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in path.parts[:-1]:
            next_directory = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            os.close(directory);directory = next_directory
        with os.fdopen(os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory), 'rb') as stream:
            require(stat.S_ISREG(os.fstat(stream.fileno()).st_mode), 'Handoff artifact is not a regular file')
            data = stream.read(MAX_BYTES + 1)
    finally:
        os.close(directory)
    require(0 < len(data) <= MAX_BYTES and len(data) == entry['size'] and hashlib.sha256(data).hexdigest() == entry['sha256'],
            'Handoff artifact size/digest mismatch')
    return data


def verify_receipt(store, handoff_id):
    record = store._record('handoffs/'+handoff_id+'.json','handoffReceipt')
    manifest = record['handoff']
    require(manifest['handoffId'] == handoff_id and record['manifestDigest'] == digest(manifest), 'Handoff receipt identity/digest mismatch')
    capture = store.get_capture(record['captureId'])
    original = manifest['original']
    require(capture['metadata'] == manifest['capture'] and capture['object'] == {k:original[k] for k in ['sha256','size','mediaType']}, 'Handoff capture receipt mismatch')
    expected = {(d['metadata']['id'],d['metadata']['revision']):d for d in manifest.get('derived',[])}
    require(len(expected) == len(manifest.get('derived',[])) and len(record['extracts']) == len(expected), 'Handoff extract receipt inventory mismatch')
    seen=set()
    for pin in record['extracts']:
        key=(pin['id'],pin['revision'])
        require(key in expected and key not in seen, 'Handoff extract pin mismatch')
        seen.add(key)
        extract=store.get_extract(capture['id'],pin['id'],pin['revision'])
        artifact=expected[key]
        require(digest(extract)==pin['recordDigest'] and extract['metadata']==artifact['metadata']
                and extract['object']=={k:artifact['file'][k] for k in ['sha256','size','mediaType']}, 'Handoff extract receipt mismatch')
    return record


def import_handoff(store, manifest_path):
    path=external_path(manifest_path)
    manifest=validate('handoff',parse(bytes_from(path)))
    receipt_key='handoffs/'+manifest['handoffId']+'.json'
    if (store.root/receipt_key).exists():
        receipt=verify_receipt(store,manifest['handoffId'])
        require(receipt['manifestDigest']==digest(manifest),'Handoff ID already identifies different metadata; sealed handoffs are immutable')
        return receipt
    require(not path.is_relative_to(store.root),'Collection handoffs must be outside the managed store')
    derived=sorted(manifest.get('derived',[]),key=lambda d:(d['metadata']['id'],d['metadata']['revision']))
    versions={}
    paths=set()
    for entry in [manifest['original'],*[d['file'] for d in derived]]:
        require(entry['path'] not in paths,'Handoff repeats an artifact path')
        paths.add(entry['path'])
        read_artifact(path.parent,entry)
    for artifact in derived:
        metadata=artifact['metadata'];identifier=metadata['id']
        version=metadata['extractor']['version']
        require(version.lower() not in {'latest','current','unknown'} and not any(c in version for c in '*^~<>'), 'Handoff extractor needs an exact recorded version')
        require(metadata['revision']==versions.get(identifier,0)+1,'Initial handoff must include contiguous extract revisions starting at 1')
        versions[identifier]=metadata['revision']
        require(all(0<=a['startByte']<a['endByte']<=artifact['file']['size'] for a in metadata['anchors']), 'Handoff extract anchors exceed artifact bytes')
    # Verify every named artifact before any writes. Read/hash again at ingestion
    # so a changed artifact cannot be recorded as the previously verified bytes.
    capture=store.capture_bytes(read_artifact(path.parent,manifest['original']),manifest['capture'],manifest['original']['mediaType'])
    pins=[]
    for artifact in derived:
        extract=store.extract_bytes(capture['id'],read_artifact(path.parent,artifact['file']),artifact['metadata'],artifact['file']['mediaType'])
        pins.append({'id':extract['metadata']['id'],'revision':extract['metadata']['revision'],'recordDigest':digest(extract)})
    receipt={'schemaVersion':'0.1.0','kind':'handoff-receipt','createdAt':now(),'handoff':manifest,'manifestDigest':digest(manifest),'captureId':capture['id'],'extracts':pins}
    store._put_record(receipt_key,'handoffReceipt',receipt)
    return receipt
