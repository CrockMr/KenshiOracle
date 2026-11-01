"""Resolve isolated local endpoints without changing the original configuration."""
import os
from pathlib import Path

from probe import config


def target_config(original, target='original'):
    if target == 'original':
        return original
    if target != 'meitou':
        raise ValueError('target must be original or meitou')
    if not original.get('meitou_config'):
        raise ValueError('Set meitou_config to the separate MeitouClient configuration file')
    result = config(original['meitou_config'])
    if result.get('target') != 'meitou':
        raise ValueError('The MeitouClient configuration must explicitly declare target=meitou')
    port = result.get('port', 47801)
    if type(port) is not int or not 1 <= port <= 65535 or port == original.get('port', 47800):
        raise ValueError('MeitouClient requires a distinct valid loopback port')
    if not result.get('runtime'):
        raise ValueError('MeitouClient requires its own runtime directory')
    if original.get('runtime') and (os.path.normcase(str(Path(result['runtime']).resolve()))
                                  == os.path.normcase(str(Path(original['runtime']).resolve()))):
        raise ValueError('MeitouClient requires its own runtime directory')
    result['port'] = port
    result.setdefault('state_schema', '0.2')
    # One local profile may hold both targets' entries; lookups are keyed by target.
    if not result.get('engine_profile') and original.get('engine_profile'):
        result['engine_profile'] = original['engine_profile']
    return result
