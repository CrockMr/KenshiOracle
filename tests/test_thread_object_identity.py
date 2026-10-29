import struct
import pytest
from thread_minidump import metadata_ranges
from thread_object_identity import parse_base_header


def test_metadata_range_single_input_remains_compatible():
    assert metadata_ranges((0x1000,24))==[(0x1000,24)]
    assert metadata_ranges(extra_memory_ranges=[(0x1000,24),(0x2000,60976)])==[(0x1000,24),(0x2000,60976)]
    assert metadata_ranges()==[]


@pytest.mark.parametrize('ranges',[
    '',0,[(0x1000,24)]*2,[(0x1000,24),(0x1010,8)],[(0x1000,0)],
    [(True,24)],[(0x1000,True)],[(2**47-8,24)],[(0,24)],
    [(0x1000,1024*1024+1)],[(0x1000,700000),(0x200000,700000)],
    [(0x1000*i,1) for i in range(1,10)],[(0x1000,)],
])
def test_metadata_range_rejects_ambiguous_or_excessive_reads(ranges):
    with pytest.raises(ValueError):metadata_ranges(extra_memory_ranges=ranges)


def test_metadata_ranges_do_not_mix_legacy_and_multi_input():
    with pytest.raises(ValueError):metadata_ranges((0x1000,24),[(0x2000,24)])


def test_sdk_base_header_requires_matching_tid_and_canonical_vptr():
    raw=struct.pack('<QQIB3x',0x7ff600001000,0x124,42,1)
    assert parse_base_header(raw,42)==dict(vptr='0x7ff600001000',target_handle_value='0x124',thread_id=42,running=True)
    with pytest.raises(ValueError):parse_base_header(raw,43)
    with pytest.raises(ValueError):parse_base_header(raw[:-1],42)
    for vptr,handle,running in [(0,0x124,0),(2**48,0x124,0),(0x1001,0x124,0),(0x1000,0,0),(0x1000,0x124,2)]:
        with pytest.raises(ValueError):parse_base_header(struct.pack('<QQIB3x',vptr,handle,42,running),42)
