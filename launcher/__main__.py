"""Run the existing oracle orchestration directly, without an MCP client."""
import argparse
import asyncio
import json
from pathlib import Path
import sys


def repeat_count(value):
    count = int(value)
    if not 1 <= count <= 100:
        raise argparse.ArgumentTypeError('repeat must be between 1 and 100')
    return count


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest='command', required=True)
    for name in ('run-scenario', 'prepare-scenario', 'restore-scenario',
                 'run-reference-scenario', 'restore-reference'):
        command = commands.add_parser(name)
        command.add_argument('--config', default='config.json')
        if name in ('run-scenario', 'prepare-scenario', 'restore-scenario'):
            command.add_argument('--target', choices=('original', 'meitou'), default='original')
        if name not in ('restore-scenario', 'restore-reference'):
            command.add_argument('scenario', help='Path to a schema 0.1 scenario JSON')
        if name in ('run-scenario', 'run-reference-scenario'):
            command.add_argument('--repeat', type=repeat_count)
        if name == 'run-scenario':
            command.add_argument('--prepare', action='store_true',
                help='Reload the scenario save and select x1 in pause before capturing controls; '
                     'restoration returns to this prepared save, not an earlier unsaved game')
        if name == 'restore-scenario':
            command.add_argument('--save', help='Explicit recovery save override, only when known')
    comparison = commands.add_parser('compare', help='Compare two completed, certified campaigns locally')
    comparison.add_argument('original_report')
    comparison.add_argument('meitou_report')
    comparison.add_argument('output')
    comparison.add_argument('--minimum-repetitions', type=repeat_count, default=5)
    comparison.add_argument('--position-tolerance', type=float, default=0.000001)
    comparison.add_argument('--number-tolerance', type=float, default=0.0)
    comparison.add_argument('--arrival-radius', type=float, default=5.0)
    comparison.add_argument('--known-deviations', help='JSON mapping exact metric IDs to documented evidence rules')
    return result


async def execute(args):
    # These modules are also used by the MCP server, but do not import that server
    # or its SDK. Resolve from this checkout rather than relying on PYTHONPATH.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'mcp-server'))
    from oracle_runner import (OracleSession, execute_scenario,
                               restore_interrupted_scenario, scenario_lock)
    from oracle_schema import load_scenario
    from probe import config

    if args.command == 'compare':
        from oracle_comparison import compare_campaigns, read_json
        rules = read_json(args.known_deviations, 1024 * 1024) if args.known_deviations else None
        return await asyncio.to_thread(compare_campaigns, args.original_report, args.meitou_report, args.output,
            minimum_repetitions=args.minimum_repetitions,
            tolerances=dict(position=args.position_tolerance, number=args.number_tolerance),
            arrival_radius=args.arrival_radius, known_deviations=rules)

    cfg = config(args.config)
    cfg.setdefault('target', 'original')
    if getattr(args, 'target', 'original') != 'original':
        from oracle_targets import target_config
        cfg = target_config(cfg, args.target)
    if args.command == 'restore-reference':
        from original_reference import restore_original_reference
        return restore_original_reference(cfg)
    if args.command == 'restore-scenario':
        return await restore_interrupted_scenario(cfg, save=args.save)
    scenario = load_scenario(args.scenario)
    if args.command == 'run-reference-scenario':
        from original_reference import run_original_reference
        return await run_original_reference(scenario, cfg, repeat=args.repeat)
    if args.command == 'prepare-scenario' or args.prepare:
        # Preparation must not bypass a previous run's recovery record or race
        # another scenario. Release the lock before the runner acquires it.
        with scenario_lock(cfg['runtime']):
            guard = Path(cfg['runtime']) / 'oracle-restoration.json'
            if guard.exists() and json.loads(guard.read_text(encoding='utf-8')).get('restore_required'):
                raise ValueError('An interrupted scenario requires restore-scenario before preparation')
            session = OracleSession(cfg)
            loaded = await session.load(scenario['save'], lock_edge=False)
            speed = await session.call('set_game_speed', speed=1, preserve_pause=True)
        if args.command == 'prepare-scenario':
            return dict(prepared=True, save=scenario['save'], load=loaded, speed=speed)
    return await execute_scenario(scenario, cfg, repeat=args.repeat)


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        result = asyncio.run(execute(args))
    except KeyboardInterrupt:
        print('Interrupted; inspect the recovery record and use restore-scenario if required.', file=sys.stderr)
        return 130
    except Exception as exc:
        print(type(exc).__name__ + ': ' + str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
