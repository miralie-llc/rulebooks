"""Reference contracts and public-field checks; never access the private store."""

import ipaddress
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from tools.validate_publication import digest, load_json

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = load_json(ROOT / 'schema/reference/0.1.0/records.schema.json')
PUBLIC = load_json(ROOT / 'schema/publication/0.1.0/bundle.schema.json')
REGISTRY = Registry().with_resources([(s['$id'], Resource.from_contents(s)) for s in [SCHEMA, PUBLIC]])


class ReferenceError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ReferenceError(message)


def validate(kind, value):
    schema = {'$ref':SCHEMA['$id']+'#/$defs/'+kind}
    error = next(Draft202012Validator(schema, registry=REGISTRY, format_checker=FormatChecker()).iter_errors(value), None)
    require(error is None, f'Invalid {kind} structure; inspect the private input locally')
    return value


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')


def validate_proposal(proposal):
    validate('proposal', proposal)
    source = proposal['source']
    require('testOnly' not in source, 'Test-only source records cannot be promoted')
    pin = {'id':source['id'], 'revision':source['revision']}
    require(all(c['source'] == pin for c in proposal['citations']), 'Citations must pin the proposed Source revision')
    # Do not fetch or follow a locator. Restrict the first promotion contract to
    # canonical public URLs without credentials or arbitrary query parameters.
    url = source['url']
    parts = urlsplit(url)
    require(parts.scheme == 'https' and parts.hostname and not parts.username and not parts.password and not parts.query,
            'Promotion requires a canonical HTTPS URL without credentials or query parameters')
    require(not parts.port or parts.port == 443, 'Nonstandard source URL ports require manual resolution')
    host = parts.hostname.lower().rstrip('.')
    require('.' in host and not host.endswith(('.localhost','.local','.internal','.invalid','.test','.home.arpa')) and host != 'localhost',
            'Private/local source URLs cannot be promoted')
    try:
        require(ipaddress.ip_address(host).is_global, 'Private/local source addresses cannot be promoted')
    except ValueError as error:
        if isinstance(error, ReferenceError):
            raise
    serialized = unquote(unquote(json.dumps(proposal, ensure_ascii=False)))
    require(not re.search(r'(?:file|s3)://|/(?:home|Users|mnt|media|private|tmp|var)/|[A-Za-z]:\\|\\\\|x-amz-|[?&](?:token|signature|sig|key|auth|expires)=', serialized, re.I),
            'Public proposal contains a private locator or credential-bearing URL pattern')
    return proposal


def validate_public_source(value):
    validate('publicSource', value)
    proposal = {'source':value['source'], 'citations':value['citations']}
    validate_proposal(proposal)
    require(value['review']['proposalDigest'] == digest(proposal), 'Public source review digest mismatch')
    return value
