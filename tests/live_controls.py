"""Manual control check. Initial state must be observed before use."""
import argparse
import asyncio
import json
from probe import Client


async def main(action):
    client = Client()
    commands = {
        'pause': [('pause', {'paused': True})],
        'speed5': [('pause', {'paused': False}), ('set_game_speed', {'speed': 5})],
        'restore1': [('pause', {'paused': False}), ('set_game_speed', {'speed': 1})],
    }
    for command, params in commands[action]:
        print(json.dumps(dict(command=command, result=await client.call(command, **params))), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['pause', 'speed5', 'restore1'])
    asyncio.run(main(parser.parse_args().action))
