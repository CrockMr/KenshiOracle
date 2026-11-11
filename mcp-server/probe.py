"""Bounded, one-request-per-connection client. No game API in this process."""
import asyncio
import json
import re
import uuid
from pathlib import Path

MAX_LINE = 65536

# Every error code a probe (native plugin or MeitouClient adapter) may send, and
# the three this client reports itself. docs/protocol.md lists their meaning;
# tests/test_error_codes.py checks both producers against this list.
ERROR_CODES = frozenset({
    'already_exists', 'busy', 'camera_restore_busy', 'camera_restore_state_changed',
    'camera_restore_token_invalid', 'cancelled',
    'internal_error', 'invalid_request', 'io_error', 'load_failed', 'not_allowed', 'not_found', 'not_implemented',
    'origin_context_incomplete', 'origin_context_required', 'origin_context_save_mismatch',
    'origin_context_token_invalid', 'origin_identity_ambiguous', 'rekenshi_settings_unavailable',
    'rekenshi_settings_unverified', 'response_too_large', 'state_unavailable', 'timeout', 'world_not_ready'})
CLIENT_CODES = frozenset({'unreachable', 'no_reply', 'invalid_reply'})
# The command may have started although no result came back: never resend a mutation.
UNCERTAIN_CODES = frozenset({'timeout', 'no_reply'})
# Probes up to 0.12.0 send these conditions as invalid_request with a fixed message.
_LEGACY_CODES = {
    'world not ready': 'world_not_ready',
    'main thread timeout; execution may already have started': 'timeout',
    'queue full': 'busy',
    'unknown command': 'not_implemented',
    'internal error': 'internal_error',
    'internal network error': 'internal_error',
    'response too large; reduce n or limit': 'response_too_large',
}
_CODE = re.compile(r'[a-z][a-z0-9]*(?:_[a-z0-9]+)*', re.ASCII)


class ProbeError(RuntimeError):
    """A refusal from a probe, or a failure to get its reply.

    ``code`` is the protocol error code (ERROR_CODES), one of CLIENT_CODES for
    a failure on this side, or None when the error carries no code. ``message``
    is the text without the code and ``str()`` is ``code: message``. A text
    already spelled ``code: message`` (or a bare ``code``) yields its code. The
    fixed messages that probes up to 0.12.0 send as ``invalid_request`` get the
    code they have since; ``str()`` keeps what the probe sent.
    """

    def __init__(self, message='', code=None):
        text = str(message)
        super().__init__(text)
        if code is None:
            head, separator, tail = text.partition(': ')
            if _CODE.fullmatch(head) and (head in ERROR_CODES or head in CLIENT_CODES or '_' in head):
                code, text = head, tail
        elif text.startswith(code + ': '):
            text = text[len(code) + 2:]
        if code == 'invalid_request':
            code = _LEGACY_CODES.get(text, code)
        self.code, self.message = code, text

    @property
    def uncertain(self):
        """True when the command may have run although no result was received."""
        return self.code in UNCERTAIN_CODES

    @classmethod
    def from_reply(cls, error):
        """The error object of a reply line: ``{"code": ..., "message": ...}``."""
        if not isinstance(error, dict) or not isinstance(error.get('code'), str):
            return cls(str(error))
        code, message = error['code'], str(error.get('message', ''))
        return cls(f'{code}: {message}' if message else code, code)


async def read_runtime_state(path):
    """Read an atomically replaced Windows status file with bounded retries.

    Sharing violations can briefly reject opening the destination during replace.
    Persistent failures still propagate; no cached state is reported as current.
    """
    for attempt in range(4):
        try:
            return json.loads(Path(path).read_text(encoding='utf-8'))
        except (PermissionError, FileNotFoundError):
            if attempt == 3:
                raise
            await asyncio.sleep(.025)


def config(path='config.json'):
    p = Path(path).resolve()
    data = json.loads(p.read_text(encoding='utf-8'))
    for key in ('runtime', 'crashes', 'log', 'dump_directory', 'executable', 'working_directory',
                'oracle_output', 'runs', 'save_root', 'rekenshi_config', 'rekenshi_module',
                'reference_controls', 'meitou_config', 'game_install', 'engine_profile'):
        if key in data and data[key] is not None:
            data[key] = str((p.parent / data[key]).resolve())
    data.setdefault('runs', str(p.parent / 'runs'))
    data.setdefault('oracle_output', str(Path(data.get('working_directory',
                        Path(data.get('executable', p)).parent)) / 'oracle-dumps'))
    return data


class Client:
    def __init__(self, port=47800, timeout=10):
        self.port, self.timeout = port, timeout

    async def call(self, command, **params):
        sent = False

        async def exchange():
            nonlocal sent
            reader, writer = await asyncio.open_connection('127.0.0.1', self.port, limit=MAX_LINE)
            try:
                request_id = uuid.uuid4().hex
                writer.write((json.dumps(dict(id=request_id, command=command, params=params), allow_nan=False) + '\n').encode())
                sent = True
                await writer.drain()
                raw = await reader.readline()
                if not raw.endswith(b'\n') or len(raw) > MAX_LINE:
                    raise ProbeError('invalid_reply: truncated or oversized reply line', 'invalid_reply')
                reply = json.loads(raw)
                if not isinstance(reply, dict) or reply.get('id') != request_id:
                    raise ProbeError('invalid_reply: the reply id does not match the request', 'invalid_reply')
                if 'error' in reply:
                    raise ProbeError.from_reply(reply['error'])
                if 'result' not in reply:
                    raise ProbeError('invalid_reply: the reply has neither a result nor an error', 'invalid_reply')
                return reply['result']
            finally:
                writer.close()
                await writer.wait_closed()
        try:
            return await asyncio.wait_for(exchange(), self.timeout)
        except TimeoutError as exc:
            if not sent:  # Still connecting: the request never left this process.
                raise ProbeError('unreachable: no connection to 127.0.0.1:%d within %s s (game not started)'
                                 % (self.port, self.timeout), 'unreachable') from exc
            # The request may have been read: a mutation sent this way is uncertain.
            raise ProbeError(f'no_reply: no reply within {self.timeout} s (game frozen or loading); '
                             'the command may already have started', 'no_reply') from exc
        except OSError as exc:
            raise ProbeError('unreachable: no probe is listening on 127.0.0.1:%d (game not started)' % self.port,
                             'unreachable') from exc
        except (ValueError, UnicodeError) as exc:
            raise ProbeError('invalid_reply: the reply is not valid JSON', 'invalid_reply') from exc
