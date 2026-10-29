"""Read-only native MCP registry and scene-command check; run outside measurements."""
import asyncio
import json
import sys
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    params = StdioServerParameters(command=sys.executable, args=[str(Path('mcp-server/server.py').resolve())])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            names = sorted(tool.name for tool in (await session.list_tools()).tools)
            assert len(names) == 17 and 'save_scene_snapshot' in names
            results = {}
            for name, args in [('ping', {}), ('game_status', {}), ('get_scene_state', {}), ('list_towns', dict(limit=1, name_filter='Heng'))]:
                result = await session.call_tool(name, args)
                if result.isError:
                    raise RuntimeError(str(result.content))
                results[name] = [block.text for block in result.content if block.type=='text']
            data = dict(tools=names, results=results)
            Path('runtime/mcp-inventory.json').write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
            print(json.dumps(data, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
