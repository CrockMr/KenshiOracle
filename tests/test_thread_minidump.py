import struct
import pytest
from thread_minidump import read_thread_lifetimes,read_memory_range


def dump(tmp_path):
    raw=bytearray(512)
    struct.pack_into('<4sIIIIIQ',raw,0,b'MDMP',42899,2,32,0,0,0x1400)
    struct.pack_into('<III',raw,32,3,52,56)
    struct.pack_into('<III',raw,44,17,76,108)
    struct.pack_into('<I',raw,56,1)
    struct.pack_into('<I',raw,60,7)
    struct.pack_into('<II',raw,100,256,200)
    struct.pack_into('<III',raw,108,12,64,1)
    struct.pack_into('<IIIIQ',raw,120,7,0,0,0,123)
    path=tmp_path/'test.dmp';path.write_bytes(raw);return path,raw


def test_recorded_thread_identity_is_read_without_live_process(tmp_path):
    p,_=dump(tmp_path)
    assert read_thread_lifetimes(p)==[dict(tid=7,created_filetime='123',dump_flags=0,dump_error='0x0',exit_status=0)]


def test_native_unused_directory_padding_is_allowed_but_not_nonempty_padding(tmp_path):
    p,raw=dump(tmp_path)
    struct.pack_into('<II',raw,8,4,456)
    struct.pack_into('<III',raw,456,3,52,56)
    struct.pack_into('<III',raw,468,17,76,108)
    struct.pack_into('<III',raw,480,0,0,0);struct.pack_into('<III',raw,492,0,0,0)
    p.write_bytes(raw);assert read_thread_lifetimes(p)[0]['created_filetime']=='123'
    struct.pack_into('<I',raw,484,1);p.write_bytes(raw)
    with pytest.raises(ValueError,match='unused'):read_thread_lifetimes(p)


def test_memory_metadata_is_read_only_from_one_recorded_range(tmp_path):
    raw=bytearray(128);raw[:4]=b'MDMP';struct.pack_into('<II',raw,8,1,32)
    struct.pack_into('<III',raw,32,5,20,44);struct.pack_into('<I',raw,44,1)
    struct.pack_into('<QII',raw,48,0x1000,4,80);raw[80:84]=b'abcd'
    path=tmp_path/'memory.dmp';path.write_bytes(raw)
    assert read_memory_range(path,0x1001,2)==b'bc'
    with pytest.raises(ValueError):read_memory_range(path,0x1003,2)
    struct.pack_into('<I',raw,60,126);path.write_bytes(raw)
    with pytest.raises(ValueError):read_memory_range(path,0x1001,2)


@pytest.mark.parametrize('change',['magic','directory','duplicate','context','missing','flags','error','thread_bound','info_bound'])
def test_invalid_or_incomplete_dump_is_not_used_as_identity_evidence(tmp_path,change):
    p,raw=dump(tmp_path)
    if change=='magic':raw[:4]=b'PEXX'
    elif change=='directory':struct.pack_into('<I',raw,12,500)
    elif change=='duplicate':struct.pack_into('<I',raw,44,3)
    elif change=='context':struct.pack_into('<I',raw,100,100)
    elif change=='missing':struct.pack_into('<I',raw,120,8)
    elif change=='flags':struct.pack_into('<I',raw,124,0x10)
    elif change=='error':struct.pack_into('<I',raw,128,0x80004005)
    elif change=='thread_bound':struct.pack_into('<I',raw,56,9)
    else:struct.pack_into('<I',raw,116,100)
    p.write_bytes(raw)
    with pytest.raises(ValueError):read_thread_lifetimes(p)
