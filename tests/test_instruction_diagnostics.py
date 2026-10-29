from copy import deepcopy
import pytest
from instruction_diagnostics import validate, summarize

IDENTITIES = [(42, '123')]


def sample():
    return dict(completed=True, pid=7, executable='game.exe', process_created_filetime='100',
        capture_flags=0x180, context_flags=0x100003, capture_returncode=0,
        capture_seconds=.01, elapsed_seconds=.02, cleanup_verified=True,
        cleanup=dict(marker_free_returncode=0, snapshot_free_returncode=0, process_handle_closed=True),
        missing_requested_lifetimes=[], modules=[dict(name='game.exe', path='game.exe', base='0x1000', size=256)],
        threads=[dict(tid=42, created_filetime='123', capture_filetime='500', context_bytes=1232,
            context_flags=0x100003, rip='0x1010', module=dict(name='game.exe', path='game.exe', offset='0x10'))])


def check(s):
    return validate(s, 7, 'game.exe', '100', IDENTITIES)


def test_validated_counts_do_not_claim_cpu_fractions():
    a = sample(); b = deepcopy(a); b['threads'][0]['capture_filetime'] = '501'
    result = summarize([a, b], 7, 'game.exe', '100', IDENTITIES)
    assert result['threads'][0]['addresses'][0]['observations'] == 2
    assert result['helper_seconds_sum'] == .04
    assert 'not stacks' in result['scope']


@pytest.mark.parametrize('field,value', [('completed', False), ('pid', 8), ('process_created_filetime', '101'),
    ('executable', 'other.exe'), ('capture_flags', 0x181), ('context_flags', 0), ('capture_returncode', 5),
    ('cleanup_verified', False), ('cleanup', {}), ('missing_requested_lifetimes', [42]),
    ('capture_seconds', float('nan')), ('elapsed_seconds', -1), ('capture_seconds', .03), ('error', {'message': 'failed'})])
def test_capture_contradictions_rejected(field, value):
    s = sample(); s[field] = value
    with pytest.raises(ValueError): check(s)


@pytest.mark.parametrize('field,value', [('tid', 43), ('created_filetime', '124'), ('capture_filetime', '0'),
    ('context_flags', 0), ('context_bytes', 255), ('rip', '0x1020'), ('module', None), ('error', 'unavailable')])
def test_context_contradictions_rejected(field, value):
    s = sample(); s['threads'][0][field] = value
    with pytest.raises(ValueError): check(s)


def test_duplicate_missing_and_reused_contexts_rejected():
    s = sample(); s['threads'] *= 2
    with pytest.raises(ValueError): check(s)
    s['threads'] = []
    with pytest.raises(ValueError): check(s)
    with pytest.raises(ValueError, match='increasing'): summarize([sample(), sample()], 7, 'game.exe', '100', IDENTITIES)


def test_unmapped_pc_preserved_without_nearest_symbol_guess():
    s = sample(); s['threads'][0].update(rip='0x2000', module=None)
    assert check(s)['threads'][0]['module'] is None


def test_changed_module_inventory_rejected():
    a = sample(); b = deepcopy(a); b['threads'][0]['capture_filetime'] = '501'; b['modules'][0]['size'] = 512
    with pytest.raises(ValueError, match='inventory'): summarize([a, b], 7, 'game.exe', '100', IDENTITIES)
