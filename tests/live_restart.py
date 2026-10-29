"""Manual destructive test on an explicitly disposable, supervised game process."""
import asyncio
import json
import sys
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from probe import config


async def main():
    cfg = config()
    state_path = Path(cfg['runtime'])/'state.json'
    before = json.loads(state_path.read_text())
    params = StdioServerParameters(command=sys.executable,
                                   args=[str(Path('mcp-server/server.py').resolve())])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool('restart_game', {})
            if result.isError:
                raise RuntimeError(str(result.content))
    after = json.loads(state_path.read_text())
    if before['pid'] == after['pid'] or not after.get('restart_ack'):
        raise RuntimeError('Restart not confirmed by PID change and acknowledgement')
    archives = sorted(Path(cfg['crashes']).iterdir())
    archive = archives[-1]
    if (archive/'reason.txt').read_text() != 'requested':
        raise RuntimeError('Requested restart archive missing')
    if not (archive/Path(cfg['log']).name).is_file():
        raise RuntimeError('Log not archived')
    print(json.dumps(dict(before_pid=before['pid'], after_pid=after['pid'], ack=after['restart_ack'], archive=str(archive))), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
