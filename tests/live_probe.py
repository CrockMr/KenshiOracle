"""Read-only manual smoke check; not collected by pytest. Requires a loaded game."""
import asyncio
import json
from probe import Client


async def main():
    client = Client()
    for command, params in [('ping', {}), ('get_frame_stats', {'n': 300}),
                            ('list_characters', {'limit': 5}), ('ping', {})]:
        try:
            result = await client.call(command, **params)
            if command == 'get_frame_stats':
                result.pop('per_frame', None)
            print(json.dumps(dict(command=command, result=result), ensure_ascii=False), flush=True)
        except Exception as exc:
            print(json.dumps(dict(command=command, error=str(exc)), ensure_ascii=False), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
