"""Manual functional oracle validation through real MCP; never collected by pytest.

Loads only the save named in the validated scenario. The runner reloads it before
each repetition and restores its starting save and captured controls afterwards.
Optional local historical manifests add protection checks for this installation.
"""
import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from oracle_schema import canonical_bytes, load_scenario, load_state
from probe import config


def manifest(path):
    return {str(file.relative_to(path)).replace('\\', '/'): hashlib.sha256(file.read_bytes()).hexdigest()
            for file in sorted(path.rglob('*')) if file.is_file()}


def value(response):
    if response.isError:
        raise RuntimeError('\n'.join(getattr(item, 'text', '') for item in response.content))
    return response.structuredContent or json.loads(response.content[0].text)


async def main(args):
    root = Path(__file__).resolve().parents[1]
    cfg = config(args.config)
    scenario = load_scenario(args.scenario)
    preflight_path = (Path(args.protection_manifest) if args.protection_manifest else
                      root/'runtime/oracle-phase1/preflight-0820.json')
    preflight = json.loads(preflight_path.read_text(encoding='utf-8')) if preflight_path.exists() else None
    if preflight:
        for name, files in preflight['save_manifests'].items():
            assert manifest(Path(preflight['save_root'])/name) == files, name
    settings = Path(cfg['working_directory'])/'settings.cfg' if 'working_directory' in cfg else None
    original_settings = settings.read_bytes() if settings and settings.exists() else None
    output = Path(args.output) if args.output else root/'runtime/oracle-phase1'/(
        'live-'+scenario['name']+'-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    report = dict(scenario=str(Path(args.scenario).resolve()), transport='MCP stdio', completed=False)
    env = dict(os.environ, KENSHI_PROBE_CONFIG=str(Path(args.config).resolve()))
    params = StdioServerParameters(command=sys.executable, args=[str(root/'mcp-server/server.py')], env=env)
    try:
        async with stdio_client(params) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()
                report['tool_names'] = sorted(tool.name for tool in (await session.list_tools()).tools)
                report['ping_before'] = value(await session.call_tool('ping', {}))
                assert report['ping_before']['schema_version'] == '0.1'
                assert report['ping_before']['paused']
                # Capture controls in the same saved world that the runner
                # restores. A camera from a different save may be constrained
                # by unloaded terrain or the engine's own camera transitions.
                report['preparation_load'] = value(await session.call_tool('load_save',
                    dict(name=scenario['save'])))
                # The hidden pre-pause selection is not exposed by KenshiLib.
                # Establish an explicit x1 reference, while remaining in pause.
                report['speed_preparation'] = value(await session.call_tool('set_game_speed',
                    dict(speed=1, preserve_pause=True)))
                report['scene_before'] = value(await session.call_tool('get_scene_state', {}))
                request = dict(path=str(Path(args.scenario).resolve()))
                if args.repeat is not None:
                    request['repeat'] = args.repeat
                report['run'] = value(await session.call_tool('run_scenario', request))
                details = json.loads(Path(report['run']['report']).read_text(encoding='utf-8'))
                report['verified_snapshots'] = []
                for execution in details['executions']:
                    for capture in execution['checkpoints']:
                        state = load_state(capture['path'])
                        payload = Path(capture['path']).read_bytes()
                        assert payload == canonical_bytes(state) == Path(capture['source_path']).read_bytes()
                        assert hashlib.sha256(payload).hexdigest() == capture['sha256']
                        if report['ping_before'].get('saved_origins_required'):
                            assert capture['identity_source']['source_fingerprint'] == details['source_fingerprint']
                            assert capture['identity_source']['save_name'] == scenario['save']
                        report['verified_snapshots'].append(dict(execution=execution['execution'], name=capture['name'],
                            path=capture['path'], sha256=capture['sha256'], counts=capture['counts'],
                            identity_source=capture.get('identity_source')))
                report['ping_after'] = value(await session.call_tool('ping', {}))
                report['scene_after'] = value(await session.call_tool('get_scene_state', {}))
                assert report['ping_before']['instance_id'] == report['ping_after']['instance_id']
                assert report['run']['restored'] and details['restoration']['verified']
                report['completed'] = True
    except BaseException as exc:
        report['error'] = type(exc).__name__+': '+str(exc)
        raise
    finally:
        if original_settings is not None:
            if settings.read_bytes() != original_settings:
                settings.write_bytes(original_settings)
            report['settings_restored_exactly'] = settings.read_bytes() == original_settings
        if preflight:
            report['protected_saves_unchanged'] = {
                name: manifest(Path(preflight['save_root'])/name) == files
                for name, files in preflight['save_manifests'].items()}
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        print(json.dumps(dict(output=str(output.resolve()), completed=report['completed'], run=report.get('run'),
            error=report.get('error'), protected_saves_unchanged=report.get('protected_saves_unchanged'),
            settings_restored_exactly=report.get('settings_restored_exactly')), ensure_ascii=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('scenario')
    parser.add_argument('--config', default='config.json')
    parser.add_argument('--repeat', type=int)
    parser.add_argument('--output')
    parser.add_argument('--protection-manifest', help='Local baseline containing save_root and save_manifests')
    asyncio.run(main(parser.parse_args()))
