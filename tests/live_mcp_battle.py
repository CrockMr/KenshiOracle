"""Run the battle harness through public MCP tools, with local server logs."""
import json
import sys
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from probe import ProbeError


class Adapter:
    transport = 'mcp-stdio'

    def __init__(self, session):
        self.session = session

    async def call(self, command, **params):
        result = await self.session.call_tool(command, params)
        if result.isError:
            raise ProbeError(' '.join(block.text for block in result.content if block.type == 'text'))
        if result.structuredContent is not None:
            return result.structuredContent
        texts = [block.text for block in result.content if block.type == 'text']
        if len(texts) != 1:
            raise ProbeError('MCP response did not contain one JSON result')
        return json.loads(texts[0])


async def run(scenario, *args, **kwargs):
    params = StdioServerParameters(command=sys.executable, args=[str(Path('mcp-server/server.py').resolve())])
    with Path('runtime/mcp-battle.stderr.log').open('w', encoding='utf-8') as log:
        async with stdio_client(params, errlog=log) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                if 'prepare_battle_scene' not in {tool.name for tool in tools.tools}:
                    raise ProbeError('Battle tool absent from MCP registry')
                await scenario(*args, client=Adapter(session), **kwargs)
