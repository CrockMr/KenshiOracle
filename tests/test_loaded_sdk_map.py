import struct
import pytest
from loaded_sdk_map import compare_pointer_table


def test_loaded_slots_require_every_full_pointer_match():
    slots=[dict(game_rva=0x1000),dict(game_rva=0x2000)]
    data=struct.pack('<QQ',0x7ff000001000,0x7ff000002000)
    r=compare_pointer_table(data,0x7ff000000000,slots)
    assert r['verified'] and r['actual_sha256']==r['expected_sha256'] and r['slots_checked']==2
    r=compare_pointer_table(struct.pack('<QQ',0x7ff000001000,0x7ff000002008),0x7ff000000000,slots)
    assert not r['verified'] and r['mismatched_slots']==[1]


def test_missing_pointer_bytes_and_overflow_are_not_partial_successes():
    with pytest.raises(ValueError):compare_pointer_table(b'123',1,[dict(game_rva=1)])
    with pytest.raises(ValueError):compare_pointer_table(b'12345678',2**64-1,[dict(game_rva=1)])
