"""Shared synthetic Python/native/C# canonical conformance vectors."""
import base64
import hashlib
import json
from pathlib import Path

import pytest

from oracle_schema import _check_json_values, _encode, canonical_bytes


SOURCE = Path(__file__).resolve().parents[1] / 'schema' / 'canonical-vectors.json'
DOCUMENT = json.loads(SOURCE.read_text(encoding='utf-8'))


@pytest.mark.parametrize('case', DOCUMENT['cases'], ids=lambda case: case['name'])
def test_shared_canonical_vector(case):
    _check_json_values(case['input'])
    actual = (canonical_bytes(case['input']) if case['kind'] == 'state'
              else (_encode(case['input']) + '\n').encode('utf-8'))
    assert actual == base64.b64decode(case['expected_base64'], validate=True)
    assert hashlib.sha256(actual).hexdigest() == case['expected_sha256']


def test_historical_59_vectors_remain_the_native_phase1_bytes():
    assert DOCUMENT['historical_case_count'] == 59
    expected = b''.join(base64.b64decode(case['expected_base64'], validate=True)
                        for case in DOCUMENT['cases'][:59])
    pinned = '413a593b4b2378ecffdba277942ed6ef0797302667a1f02e39260ff5c7b8fab7'
    assert hashlib.sha256(expected).hexdigest() == DOCUMENT['historical_expected_sha256'] == pinned
