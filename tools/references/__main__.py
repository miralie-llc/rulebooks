"""Operate the private reference store without exposing it to site builds."""

import argparse
import json
import os
from pathlib import Path

from .contracts import ReferenceError
from .store import LocalStore, bytes_from, external_path, parse
from .handoff import import_handoff


def private_json(path):
    return parse(bytes_from(external_path(path)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    init = sub.add_parser('init')
    init.add_argument('--access', choices=['owner','group','server-acl'], default='owner')
    init.add_argument('--accept-server-access-controls', action='store_true')
    handoff = sub.add_parser('import-handoff')
    handoff.add_argument('--manifest', type=Path, required=True)
    capture = sub.add_parser('capture')
    capture.add_argument('--file', type=Path, required=True)
    capture.add_argument('--metadata', type=Path, required=True)
    capture.add_argument('--media-type', required=True)
    extract = sub.add_parser('extract')
    extract.add_argument('--capture', required=True)
    extract.add_argument('--file', type=Path, required=True)
    extract.add_argument('--metadata', type=Path, required=True)
    extract.add_argument('--media-type', default='text/plain; charset=utf-8')
    review = sub.add_parser('review')
    review.add_argument('--capture', required=True)
    review.add_argument('--proposal', type=Path, required=True)
    review.add_argument('--reviewer', required=True, help='Public reviewer handle; not an email or private account identifier')
    review.add_argument('--extract-id')
    review.add_argument('--revision', type=int)
    review.add_argument('--accept-public-metadata', action='store_true', required=True,
                        help='Assert that source identity, citations, public fields and any selected extract were reviewed')
    promote = sub.add_parser('promote')
    promote.add_argument('--review', required=True)
    promote.add_argument('--output', type=Path, required=True)
    retrieve = sub.add_parser('retrieve')
    retrieve.add_argument('--capture', required=True)
    retrieve.add_argument('--extract-id')
    retrieve.add_argument('--revision', type=int)
    retrieve.add_argument('--output', type=Path, required=True)
    sub.add_parser('verify')
    backup = sub.add_parser('backup')
    backup.add_argument('--output', type=Path, required=True)
    backup.add_argument('--accept-server-access-controls', action='store_true')
    restore = sub.add_parser('restore')
    restore.add_argument('--backup', type=Path, required=True)
    restore.add_argument('--output', type=Path, required=True)
    restore.add_argument('--expected-digest', required=True)
    restore.add_argument('--accept-server-access-controls', action='store_true')
    args = parser.parse_args()
    try:
        if args.command == 'restore':
            restored = LocalStore.restore(args.backup, args.output, args.expected_digest, server_acl_confirmed=args.accept_server_access_controls)
            result = {'restored':True, **restored.verify()}
        else:
            root = os.environ.get('RULEBOOKS_REFERENCE_ROOT')
            if not root:
                raise ReferenceError('Set RULEBOOKS_REFERENCE_ROOT outside repository configuration')
            store = LocalStore.create(root, args.access, server_acl_confirmed=args.accept_server_access_controls) if args.command == 'init' else LocalStore(root)
            if args.command == 'init':
                result = {'initialized':True,'access':store.config['access'],'storeId':store.config['id']}
            elif args.command == 'import-handoff':
                record = import_handoff(store, args.manifest)
                result = {'handoffId':record['handoff']['handoffId'],'manifestDigest':record['manifestDigest'],
                          'captureId':record['captureId'],'extracts':record['extracts']}
            elif args.command == 'capture':
                record = store.capture(args.file, private_json(args.metadata), args.media_type)
                result = {'captureId':record['id'],'sha256':record['object']['sha256']}
            elif args.command == 'extract':
                record = store.add_extract(args.capture, args.file, private_json(args.metadata), args.media_type)
                result = {'extractId':record['metadata']['id'],'revision':record['metadata']['revision'],'sha256':record['object']['sha256']}
            elif args.command == 'review':
                record = store.review(args.capture, private_json(args.proposal), args.reviewer, extract_id=args.extract_id, revision=args.revision)
                result = {'reviewId':record['id'],'proposalDigest':record['proposalDigest']}
            elif args.command == 'promote':
                record = store.promote(args.review, args.output)
                result = {'source':record['source'],'sha256':record['outputDigest'],'promotionId':record['id']}
            elif args.command == 'retrieve':
                result = {'sha256':store.retrieve(args.capture, args.output, extract_id=args.extract_id, revision=args.revision)}
            elif args.command == 'verify':
                result = store.verify()
            elif args.command == 'backup':
                result = {'backupDigest':store.backup(args.output, server_acl_confirmed=args.accept_server_access_controls)}
        print(json.dumps(result, sort_keys=True))
    except ReferenceError as error:
        parser.exit(1, f'Reference operation rejected: {error}\n')
    except (OSError, ValueError, KeyError, TypeError):
        parser.exit(1, 'Reference operation failed. Inspect private inputs, permissions and storage locally; details were not logged.\n')


if __name__ == '__main__':
    main()
