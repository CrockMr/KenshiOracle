import pytest
from thread_metadata import locate_module


def modules():
    return [dict(name='a.dll',path='a.dll',base='0x1000',size=0x100),
            dict(name='b.dll',path='b.dll',base='0x2000',size=0x100)]


def test_module_half_open_ranges_and_relative_offset():
    assert locate_module(0x1000,modules())['offset']=='0x0'
    assert locate_module(0x10ff,modules())['name']=='a.dll'
    assert locate_module(0x1100,modules()) is None
    assert locate_module(0x2010,modules())['offset']=='0x10'


def test_null_or_unmapped_address_does_not_invent_module():
    assert locate_module(None,modules()) is None
    assert locate_module(0x3000,modules()) is None


def test_overlapping_module_evidence_is_rejected():
    rows=modules()+[dict(name='overlap.dll',path='other',base='0x1080',size=0x100)]
    with pytest.raises(ValueError,match='Overlapping'): locate_module(0x1090,rows)
