"""Bounded, one-request-per-connection client. No game API in this process."""
import asyncio
import json
import uuid
from pathlib import Path

MAX_LINE = 65536


class ProbeError(RuntimeError):
    pass


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
                'reference_controls', 'meitou_config', 'game_install'):
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
        async def exchange():
            reader, writer = await asyncio.open_connection('127.0.0.1', self.port, limit=MAX_LINE)
            try:
                request_id = uuid.uuid4().hex
                writer.write((json.dumps(dict(id=request_id, command=command, params=params), allow_nan=False) + '\n').encode())
                await writer.drain()
                raw = await reader.readline()
                if not raw.endswith(b'\n') or len(raw) > MAX_LINE:
                    raise ProbeError('Réponse tronquée ou trop longue')
                reply = json.loads(raw)
                if not isinstance(reply, dict) or reply.get('id') != request_id:
                    raise ProbeError('Identifiant de réponse incorrect')
                if 'error' in reply:
                    raise ProbeError(str(reply['error']))
                if 'result' not in reply:
                    raise ProbeError('Réponse sans résultat')
                return reply['result']
            finally:
                writer.close()
                await writer.wait_closed()
        try:
            return await asyncio.wait_for(exchange(), self.timeout)
        except (TimeoutError, OSError) as exc:
            raise ProbeError('Jeu figé ou non lancé : délai expiré ou connexion impossible') from exc
        except (ValueError, UnicodeError) as exc:
            raise ProbeError('Réponse du plugin invalide') from exc
