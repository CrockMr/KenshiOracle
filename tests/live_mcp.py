"""Manual read-only MCP check against the real plugin; not a pytest test."""
import asyncio
import json
import sys
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from probe import Client


async def main():
    params = StdioServerParameters(command=sys.executable,
                                   args=[str(Path('mcp-server/server.py').resolve())])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            for name, args in [('ping', {}), ('get_frame_stats', {'n': 30})]:
                result = await session.call_tool(name, args)
                if result.isError:
                    raise RuntimeError(str(result.content))
                print(json.dumps(dict(tool=name, success=True)), flush=True)

    for line in [b'{invalid}\n', b'{"id":"a","id":"b"}\n',
                 b'{"id":"check","command":"unknown","params":{}}\n',
                 b'{"id":"type","command":"list_characters","params":{"limit":"oops"}}\n']:
        reader, writer = await asyncio.open_connection('127.0.0.1', 47800)
        try:
            writer.write(line)
            await writer.drain()
            response = json.loads(await asyncio.wait_for(reader.readline(), 10))
            if 'error' not in response:
                raise RuntimeError('Malformed command was not rejected')
            print(json.dumps(dict(rejected=line.decode().strip(), error=response['error'])), flush=True)
        finally:
            writer.close()
            await writer.wait_closed()
    print(json.dumps(dict(final_ping=await Client().call('ping'))), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
