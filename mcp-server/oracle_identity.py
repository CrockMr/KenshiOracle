"""Validation of saved handles sent to the public SDK resolver.

Names and index/serial pairs are deliberately not identity keys. A resolver
response is evidence only for the complete saved handle in its game instance.
"""
import re


_HAND = re.compile(r'hand:(0|[1-9][0-9]*):(0|[1-9][0-9]*):(0|[1-9][0-9]*):(0|[1-9][0-9]*):(0|[1-9][0-9]*)', re.ASCII)
_FINGERPRINT = re.compile(r'sha256:[0-9a-f]{64}', re.ASCII)


def validate_saved_handles(ids):
    if type(ids) is not list or not 1 <= len(ids) <= 128:
        raise ValueError('ids must contain 1..128 complete saved character or squad handles')
    for identity in ids:
        if type(identity) is not str or len(identity) > 59:
            raise ValueError('Each saved identity must be a complete canonical handle')
        match = _HAND.fullmatch(identity)
        if not match:
            raise ValueError('Each saved identity must be hand:TYPE:C:CS:I:S using canonical decimal integers')
        components = [int(part) for part in match.groups()]
        if components[0] not in (1, 34) or any(part > 0xffffffff for part in components):
            raise ValueError('Saved handles require type 1 or 34 and five unsigned 32-bit components')
    return ids


def validate_origin_fingerprint(value):
    if type(value) is not str or not _FINGERPRINT.fullmatch(value):
        raise ValueError('source_fingerprint must be sha256: followed by 64 lowercase hexadecimal characters')
    return value


def validate_origin_token(value):
    if type(value) is not str or not 1 <= len(value) <= 200 or not value.isascii() or any(ord(c) < 33 or ord(c) > 126 for c in value):
        raise ValueError('token must be the bounded opaque token returned by its preparation command')
    return value
