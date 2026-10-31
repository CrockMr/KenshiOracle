"""Launch the opt-in Meitou adapter under the existing process supervisor."""
import argparse
import asyncio
from copy import deepcopy
import os
from pathlib import Path
import subprocess
import sys


def launch_config(cfg):
    result = deepcopy(cfg)
    if result.get('target') != 'meitou':
        raise ValueError('This launcher requires target=meitou')
    if result.get('launcher_click', False) is not False:
        raise ValueError('launcher_click applies only to the original kenshi_x64.exe launcher')
    port = result.get('port', 47801)
    if type(port) is not int or not 1 <= port <= 65535 or port == 47800:
        raise ValueError('Meitou requires a valid port distinct from the original default')
    arguments = result.get('arguments', [])
    if not isinstance(arguments, list) or any(not isinstance(value, str) for value in arguments):
        raise ValueError('arguments must be a list of strings')
    if any(value.startswith('--oracle') for value in arguments):
        raise ValueError('Configure oracle port/output as fields; the launcher supplies its own --oracle options')
    result['arguments'] = [*arguments, '--oracle', '--oracle-port', str(port),
                           '--oracle-output', str(Path(result['oracle_output']).resolve())]
    result['port'] = port
    return result


def isolated_work_config(cfg):
    """Give UserConfig.Load a private first-choice copy of the player's settings."""
    from original_reference import read_bounded, settings_path
    result = deepcopy(cfg)
    work = settings_path(Path(cfg['runtime']) / 'game-work' / 'meitou.user.json').parent
    work.mkdir(parents=True, exist_ok=True)
    sources = [Path(cfg.get('working_directory', Path(cfg['executable']).parent)) / 'meitou.user.json',
               Path(cfg['executable']).parent / 'meitou.user.json']
    destination = settings_path(work / 'meitou.user.json')
    source = next((settings_path(path) for path in sources if path.is_file()), None)
    raw = read_bounded(source, 1024 * 1024) if source is not None else b'{}\n'
    destination.write_bytes(raw)
    result['working_directory'] = str(work)
    return result


async def run(cfg):
    from launcher.watchdog import Watchdog
    from oracle_runner import scenario_lock
    import psutil
    cfg = launch_config(cfg)
    if any((p.info['name'] or '').lower() == 'meitouclient.exe'
           for p in psutil.process_iter(['name'])):
        raise RuntimeError('Close the existing MeitouClient before starting its supervised oracle process')

    def spawn(command, **kwargs):
        if cfg.get('game_install'):
            kwargs['env'] = dict(kwargs.get('env', os.environ), KENSHI_PATH=cfg['game_install'])
        return subprocess.Popen(command, **kwargs)

    with scenario_lock(Path(cfg['runtime']) / 'watchdog-owner'):
        await Watchdog(isolated_work_config(cfg), spawn=spawn).run()


def main(argv=None):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'mcp-server'))
    from probe import config
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default='config.meitou.json')
    args = parser.parse_args(argv)
    asyncio.run(run(config(args.config)))


if __name__ == '__main__':
    main()
