"""One list of protocol error codes for the native probe, the MeitouClient adapter, the test fake and the client."""
import asyncio
from pathlib import Path
import re

import pytest

from fake_probe import FakeProbe
import fake_probe
from oracle_runner import ScenarioError
from probe import CLIENT_CODES, ERROR_CODES, UNCERTAIN_CODES, Client, ProbeError

ROOT = Path(__file__).resolve().parents[1]
CODE = r'"([a-z][a-z0-9]*(?:_[a-z0-9]+)*)"'


def native_codes():
    """Codes the native sources can send: oracle::Error(code, ...) and error(id, message, code)."""
    found = set()
    for path in sorted((ROOT / 'plugin').glob('*.h')) + [ROOT / 'plugin' / 'Probe.cpp']:
        text = path.read_text(encoding='utf-8')
        found.update(re.findall(r'\bError\(' + CODE, text))
        # Error(condition ? "code_a" : "code_b", ...)
        for first, second in re.findall(r'\bError\([^";]*\?\s*' + CODE + r'\s*:\s*' + CODE, text):
            found.update((first, second))
        found.update(re.findall(r'\berror\([^;]*?,"[^"]*",' + CODE + r'\)', text))
    # The default code of error(id, message): every std::exception that is not an oracle::Error.
    found.add('invalid_request')
    return found


def meitou_codes():
    """Codes in the lines the patch series adds to MeitouClient (adapter sources, not its tests)."""
    found = set()
    for path in sorted((ROOT / 'integrations' / 'meitou').glob('*.patch')):
        for line in path.read_text(encoding='utf-8').splitlines():
            if not line.startswith('+') or 'Assert.' in line or 'InlineData' in line:
                continue
            found.update(re.findall(r'OracleHostError\(' + CODE, line))
            found.update(re.findall(r'\.(?:Cancel|Fail)\((?:[^"()]*\?\s*)?' + CODE, line))
            found.update(re.findall(r'\.Cancel\([^"()]*\?\s*"[a-z_]+"\s*:\s*' + CODE, line))
            found.update(re.findall(r'\bError\((?:[A-Za-z.]+,\s*)?' + CODE + r',', line))
            found.update(re.findall(r'\(string Code, string Message\)\??\s+\w+\s*=\s*\(' + CODE, line))
    return found


def fake_codes():
    text = (ROOT / 'tests' / 'fake_probe.py').read_text(encoding='utf-8')
    found = set(re.findall(r"ProbeError\('([a-z][a-z0-9_]*)(?:: |')", text))
    found.update(value[0] for name, value in vars(fake_probe).items()
                 if re.fullmatch(r'[GM][0-9]', name) and isinstance(value, tuple))
    return found


def test_every_producer_only_sends_listed_codes():
    native, meitou, fake = native_codes(), meitou_codes(), fake_codes()
    # The scan found the codes this contract is about; an empty scan would prove nothing.
    assert {'world_not_ready', 'timeout', 'busy', 'internal_error', 'not_implemented', 'response_too_large',
            'already_exists', 'state_unavailable'} <= native
    assert {'world_not_ready', 'timeout', 'cancelled', 'busy', 'internal_error', 'not_implemented',
            'response_too_large', 'already_exists', 'load_failed'} <= meitou
    assert {'world_not_ready', 'invalid_request', 'not_found', 'busy'} <= fake
    assert native - ERROR_CODES == set()
    assert meitou - ERROR_CODES == set()
    assert fake - ERROR_CODES == set()
    assert ERROR_CODES - native - meitou == set()  # no listed code that nobody sends
    assert not ERROR_CODES & CLIENT_CODES and UNCERTAIN_CODES <= ERROR_CODES | CLIENT_CODES


def test_the_same_conditions_have_the_same_code_on_both_engines():
    shared = {'world_not_ready', 'timeout', 'busy', 'internal_error', 'not_implemented', 'response_too_large'}
    assert shared <= native_codes() & meitou_codes()
    native = (ROOT / 'plugin' / 'Probe.cpp').read_text(encoding='utf-8')
    assert 'std::runtime_error("world not ready")' not in native
    assert 'oracle::Error("timeout","main thread timeout; execution may already have started")' in native


def test_the_protocol_document_lists_exactly_the_codes():
    text = (ROOT / 'docs' / 'protocol.md').read_text(encoding='utf-8')
    section = text.split('## Error codes', 1)[1].split('\n## ', 1)[0]
    documented = {code for line in section.splitlines() if line.startswith('| `')
                  for code in re.findall(r'`([a-z_]+)`', line.split('|')[1])}
    assert documented == ERROR_CODES | CLIENT_CODES


@pytest.mark.parametrize('text,code,message', [
    ('world_not_ready: world is unavailable or a save is loading', 'world_not_ready',
     'world is unavailable or a save is loading'),
    ('world_not_ready', 'world_not_ready', ''),
    ('busy', 'busy', ''),
    ('timeout: Host response timed out', 'timeout', 'Host response timed out'),
    ('get_clock failed: {"original": "x"}', None, 'get_clock failed: {"original": "x"}'),
    ('Probe did not accept allow_setup; update the probe', None, 'Probe did not accept allow_setup; update the probe'),
    ('Restoration mismatch: paused', None, 'Restoration mismatch: paused'),
    ('unsaved: text', None, 'unsaved: text'),
])
def test_a_code_is_read_from_code_colon_message_text_only(text, code, message):
    error = ProbeError(text)
    assert (error.code, error.message, str(error)) == (code, message, text)


def test_an_explicit_code_and_a_scenario_error_keep_it():
    error = ProbeError('no_reply: no reply within 10 s', 'no_reply')
    assert (error.code, error.message, error.uncertain) == ('no_reply', 'no reply within 10 s', True)
    wrapped = ScenarioError(str(error) + '; report: somewhere', error.code)
    assert wrapped.code == 'no_reply' and str(wrapped).startswith('no_reply: no reply')
    assert ScenarioError('world not ready during camera restoration', 'world_not_ready').code == 'world_not_ready'
    assert ProbeError('busy: wait').uncertain is False and ProbeError('timeout: late').uncertain is True


@pytest.mark.parametrize('message,code', [
    ('world not ready', 'world_not_ready'),
    ('main thread timeout; execution may already have started', 'timeout'),
    ('queue full', 'busy'),
    ('unknown command', 'not_implemented'),
    ('internal error', 'internal_error'),
    ('internal network error', 'internal_error'),
    ('response too large; reduce n or limit', 'response_too_large'),
    ('paused must be bool', 'invalid_request'),
])
def test_replies_of_probes_up_to_0_12_0_get_the_code_they_have_since(message, code):
    error = ProbeError.from_reply(dict(code='invalid_request', message=message))
    assert error.code == code and error.message == message
    assert str(error) == 'invalid_request: ' + message  # what the probe sent stays readable


def test_a_reply_error_keeps_its_code_and_odd_shapes_have_none():
    error = ProbeError.from_reply(dict(code='state_unavailable', message='player unavailable'))
    assert (error.code, error.message, str(error)) == ('state_unavailable', 'player unavailable',
                                                       'state_unavailable: player unavailable')
    assert ProbeError.from_reply('plain text from an unknown producer').code is None
    assert ProbeError.from_reply(dict(message='no code')).code is None


def test_the_code_crosses_the_wire_and_an_absent_probe_is_unreachable(tmp_path):
    async def run():
        async with FakeProbe(tmp_path / 'snapshots') as fake:
            fake.failures['get_clock'] = 'world_not_ready: world is unavailable or a save is loading'
            with pytest.raises(ProbeError) as refused:
                await Client(fake.port, 1).call('get_clock')
            port = fake.port
        with pytest.raises(ProbeError) as absent:
            await Client(port, 1).call('ping')
        return refused.value, absent.value
    refused, absent = asyncio.run(run())
    assert (refused.code, refused.message) == ('world_not_ready', 'world is unavailable or a save is loading')
    assert absent.code == 'unreachable' and absent.uncertain is False
