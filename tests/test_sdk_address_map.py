"""Synthetic AMD64 PE metadata only; no game bytes or process access."""
import hashlib
import struct
import pytest
from sdk_address_map import build, annotate


def pe(sections, directories, dll=False):
    """Own small fixture images with normal PE32+ section/file alignment."""
    data = bytearray(max(raw+len(body) for _, _, raw, body, _ in sections))
    data[:2] = b'MZ';struct.pack_into('<I', data, 0x3c, 0x80)
    data[0x80:0x84] = b'PE\0\0'
    struct.pack_into('<HHIIIHH', data, 0x84, 0x8664, len(sections), 1234, 0, 0, 240, 0x2022 if dll else 0x22)
    opt = 0x98;struct.pack_into('<H', data, opt, 0x20b)
    struct.pack_into('<Q', data, opt+24, 0x180000000 if dll else 0x140000000)
    struct.pack_into('<II', data, opt+32, 0x1000, 0x200)
    struct.pack_into('<II', data, opt+56, 0x4000, 0x200)
    struct.pack_into('<I', data, opt+108, 16)
    for index, (rva, size) in directories.items():struct.pack_into('<II', data, opt+112+index*8, rva, size)
    for i, (name, va, raw, body, flags) in enumerate(sections):
        off=opt+240+40*i;data[off:off+8]=name.encode().ljust(8,b'\0')
        struct.pack_into('<IIII', data, off+8, len(body), va, len(body), raw)
        struct.pack_into('<I', data, off+36, flags);data[raw:raw+len(body)]=body
    return data


def images(tmp_path, targets=(0x1010,0x1100,0x1200,0x3080), regions=((0x1010,0x1050,0x3000),(0x1100,0x1150,0x3004))):
    text=bytearray(0x200)
    for slot in range(3):
        text[slot*6:slot*6+6]=b'\xff\x25'+struct.pack('<i',0x3000+slot*8-(0x1000+slot*6+6))
    text[18]=0xcc
    exports=[('FUNC_BEGIN',0x1000),('?first@World@@QEAAXXZ',0x1000),('?_NV_first@World@@QEAAXXZ',0x1000),
             ('?second@World@@QEAAXXZ',0x1006),('?leaf@World@@QEAAXXZ',0x100c),('FUNC_END',0x1012),
             ('?GetRealAddress@KenshiLib@@YA_JPEAX@Z',0x1080)]
    edata=bytearray(0x400);count=len(exports)
    # Arrays and strings fit within this single export-directory region.
    functions, names, ordinals, cursor=0x2040,0x2080,0x20c0,0x2100
    struct.pack_into('<IIHHIIIIIII',edata,0,0,0,0,0,0x20f0,1,count,count,functions,names,ordinals)
    edata[0xf0:0xf8]=b'Own.dll\0'
    for i,(name,rva) in enumerate(exports):
        struct.pack_into('<I',edata,functions-0x2000+i*4,rva)
        struct.pack_into('<I',edata,names-0x2000+i*4,cursor)
        struct.pack_into('<H',edata,ordinals-0x2000+i*2,i)
        value=name.encode()+b'\0';edata[cursor-0x2000:cursor-0x2000+len(value)]=value;cursor+=len(value)
    lib=pe([('.text',0x1000,0x200,text,0x60000020),('.edata',0x2000,0x400,edata,0x40000040),
            ('.data',0x3000,0x800,bytearray(0x200),0xc0000040)],{0:(0x2000,0x400)},True)
    pdata=bytearray(0x200)
    for i,row in enumerate(regions):struct.pack_into('<III',pdata,i*12,*row)
    xdata=bytearray(0x200);xdata[:8]=b'\x01\0\0\0\x01\0\0\0'
    exe=pe([('.text',0x1000,0x200,bytearray(0x800),0x60000020),('.pdata',0x2000,0xa00,pdata,0x40000040),
            ('.rdata',0x3000,0xc00,xdata,0x40000040)],{3:(0x2000,len(regions)*12)})
    paths=(tmp_path/'Own.dll',tmp_path/'Steam.br',tmp_path/'Own.exe')
    for path,value in zip(paths,(lib,struct.pack('<%dI'%len(targets),*targets),exe)):path.write_bytes(value)
    return paths


def mutate(path,offset,fmt,*values):
    data=bytearray(path.read_bytes());struct.pack_into(fmt,data,offset,*values);path.write_bytes(data)


def test_exact_region_aliases_leaf_and_no_nearest_symbol(tmp_path):
    paths=images(tmp_path);m=build(*paths)
    assert m['resolver']['function_slot_count']==3 and m['resolver']['table_entry_count']==4
    assert m['resolver']['pointer_table_rva']==0x3000 and not m['runtime_binding_verified']
    assert m['sources']['library']['sha256']==hashlib.sha256(paths[0].read_bytes()).hexdigest()
    r=annotate(0x1020,m)
    assert r['status']=='unwind_region' and r['unwind_region']['begin_rva']==0x1010
    assert {x['name'] for x in r['aliases']}=={'?first@World@@QEAAXXZ','?_NV_first@World@@QEAAXXZ'}
    assert all(x['name']!='FUNC_BEGIN' for x in m['slots'][0]['aliases'])
    assert annotate(0x1050,m)['status']=='unknown_no_unwind_region' # half-open end
    assert annotate(0x1090,m)['aliases']==[] # no preceding-symbol estimate
    leaf=annotate(0x1200,m)
    assert leaf['status']=='exact_entry_only' and leaf['unwind_region'] is None
    assert annotate(0x1201,m)['status']=='unknown_no_unwind_region'
    assert m['trailing_slots'][0]['classification']=='not_a_verified_function_stub'


def test_different_stub_slots_with_same_target_keep_every_alias(tmp_path):
    m=build(*images(tmp_path,targets=(0x1010,0x1010,0x1200,0x3080)))
    r=annotate(0x1020,m)
    assert {x['slot'] for x in r['aliases']}=={0,1}
    assert len(r['aliases'])==3


def add_import(lib):
    data=bytearray(lib.read_bytes())
    struct.pack_into('<II',data,0x98+112+8,0x2300,40)
    struct.pack_into('<IIIII',data,0x700,0x2340,0,0,0x2330,0x2360)
    data[0x730:0x738]=b'Own2.dll';data[0x738]=0
    struct.pack_into('<QQ',data,0x740,0x2380,0)
    struct.pack_into('<QQ',data,0x760,0x2380,0)
    struct.pack_into('<H',data,0x780,0);data[0x782:0x786]=b'Fn\0\0'
    lib.write_bytes(data)


def test_imports_are_metadata_only_and_have_bounded_thunks(tmp_path):
    paths=images(tmp_path);add_import(paths[0]);m=build(*paths)
    row=m['imports']['library']['descriptors'][0]
    assert row['dll']=='Own2.dll' and row['thunk_count']==1 and row['names_validated']


@pytest.mark.parametrize('change',['descriptor_end','name_bounds','thunk_bounds','ordinal_bits','iat_terminator'])
def test_bad_import_ranges_do_not_pass(tmp_path,change):
    paths=images(tmp_path);lib=paths[0];add_import(lib)
    if change=='descriptor_end':mutate(lib,0x98+112+8+4,'I',20)
    elif change=='name_bounds':mutate(lib,0x700+12,'I',0x4000)
    elif change=='thunk_bounds':mutate(lib,0x740,'Q',0x3fff)
    elif change=='ordinal_bits':mutate(lib,0x740,'Q',0x8000000000010001)
    else:mutate(lib,0x768,'Q',0x1234)
    with pytest.raises(ValueError):build(*paths)


def test_overlapping_unwind_regions_stay_unknown(tmp_path):
    m=build(*images(tmp_path,regions=((0x1010,0x1130,0x3000),(0x1100,0x1150,0x3004))))
    r=annotate(0x1110,m)
    assert m['pdata_metadata']['overlap_count']==1
    assert r['status']=='unknown_ambiguous_unwind_region' and r['aliases']==[]
    assert r['unwind_region'] is None and len(r['candidate_unwind_regions'])==2


@pytest.mark.parametrize('change',['dos','signature','machine','optional','directory_count','header_bounds','raw_section','virtual_overlap','raw_overlap'])
def test_malformed_pe_is_not_accepted(tmp_path,change):
    lib,table,exe=images(tmp_path)
    if change=='dos':mutate(lib,0,'H',0)
    elif change=='signature':mutate(lib,0x80,'I',0)
    elif change=='machine':mutate(lib,0x84,'H',0x14c)
    elif change=='optional':mutate(lib,0x98,'H',0x10b)
    elif change=='directory_count':mutate(lib,0x98+108,'I',65)
    elif change=='header_bounds':mutate(lib,0x98+60,'I',0x180)
    elif change=='raw_section':mutate(lib,0x188+20,'I',0xffff)
    elif change=='virtual_overlap':mutate(lib,0x188+40+12,'I',0x1100)
    else:mutate(lib,0x188+40+20,'I',0x200)
    with pytest.raises(ValueError):build(lib,table,exe)


@pytest.mark.parametrize('change',['export_bounds','ordinal','name','stub_name_alignment','opcode','slot_stride','table_writable','table_short','table_bytes','target_data','target_outside'])
def test_export_stub_and_table_guards(tmp_path,change):
    lib,table,exe=images(tmp_path)
    if change=='export_bounds':mutate(lib,0x98+112,'I',0x3ff0)
    elif change=='ordinal':mutate(lib,0x400+0xc0,'H',999)
    elif change=='name':mutate(lib,0x400+0x80,'I',0x23ff);mutate(lib,0x7ff,'B',65)
    elif change=='stub_name_alignment':mutate(lib,0x400+0x40+3*4,'I',0x1007)
    elif change=='opcode':mutate(lib,0x200,'H',0x24ff)
    elif change=='slot_stride':mutate(lib,0x200+6+2,'i',0x3008-(0x1006+6)+8)
    elif change=='table_writable':mutate(lib,0x188+80+36,'I',0x40000040)
    elif change=='table_short':table.write_bytes(struct.pack('<II',0x1010,0x1100))
    elif change=='table_bytes':table.write_bytes(table.read_bytes()+b'!')
    elif change=='target_data':mutate(table,0,'I',0x3000)
    else:mutate(table,0,'I',0x5000)
    with pytest.raises(ValueError):build(lib,table,exe)


@pytest.mark.parametrize('change',['size','reverse','code_bounds','unwind_bounds'])
def test_unwind_metadata_bounds_are_validated(tmp_path,change):
    lib,table,exe=images(tmp_path)
    if change=='size':mutate(exe,0x98+112+3*8+4,'I',23)
    elif change=='reverse':mutate(exe,0xa00,'II',0x1050,0x1010)
    elif change=='code_bounds':mutate(exe,0xa00+4,'I',0x1900)
    elif change=='unwind_bounds':mutate(exe,0xa00+8,'I',0x4000)
    with pytest.raises(ValueError):build(lib,table,exe)


def test_unsorted_source_is_exposed_not_silently_repaired(tmp_path):
    paths=images(tmp_path,regions=((0x1100,0x1150,0x3004),(0x1010,0x1050,0x3000)))
    m=build(*paths);r=annotate(0x1120,m)
    assert not m['pdata_metadata']['source_order_sorted']
    assert m['pdata_metadata']['source_order_regressions'][0]['table_index']==1
    assert m['pdata'][0]['begin_rva']==0x1100 and m['pdata_lookup_indices']==[1,0]
    assert r['status']=='static_unwind_region_unsorted_source'
    assert not r['source_table_order_sorted'] and r['unwind_region']['source_table_index']==0
    assert r['unwind_region']['begin_rva']==0x1100 and r['aliases'][0]['name']=='?second@World@@QEAAXXZ'


def test_chained_fragment_is_retained_as_a_region_not_extended_to_primary(tmp_path):
    paths=images(tmp_path,regions=((0x1010,0x1050,0x3000),(0x1100,0x1150,0x3040)))
    mutate(paths[2],0xc00,'BBBB',0x21,0,0,0)
    mutate(paths[2],0xc04,'III',0x1100,0x1150,0x3040)
    mutate(paths[2],0xc40,'BBBB',1,0,0,0)
    r=annotate(0x1020,build(*paths))
    assert r['unwind_region']['end_rva']==0x1050
    assert r['unwind_region']['chained_region']['begin_rva']==0x1100
    assert {a['name'] for a in r['aliases']}=={'?first@World@@QEAAXXZ','?_NV_first@World@@QEAAXXZ'}


def test_unknown_optional_unwind_format_is_explicit(tmp_path):
    paths=images(tmp_path);mutate(paths[2],0xc00,'B',7)
    r=annotate(0x1020,build(*paths))
    assert r['unwind_region']['unwind_version']==7
    assert not r['unwind_region']['optional_unwind_fields_decoded']


@pytest.mark.parametrize('value',[True,-1,2**32,'0x1010'])
def test_invalid_input_rva_is_not_coerced(tmp_path,value):
    with pytest.raises(ValueError):annotate(value,build(*images(tmp_path)))
