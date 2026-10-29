"""Load every distributed scenario through the production contract validator.

This test only reads JSON examples. It never looks for a save or contacts Kenshi.
"""
from pathlib import Path

import pytest

from oracle_schema import load_scenario


EXAMPLES = Path(__file__).resolve().parents[1] / 'scenarios'


def test_calm_city_template_is_available():
    assert (EXAMPLES / 'ville-calme.json').is_file()


@pytest.mark.parametrize('path', sorted(EXAMPLES.glob('*.json')), ids=lambda path: path.name)
def test_distributed_scenario_validates_with_production_loader(path):
    scenario = load_scenario(path)
    assert scenario['name'] == path.stem


def test_distributed_scenario_names_do_not_collide_on_windows():
    paths = sorted(EXAMPLES.glob('*.json'))
    assert paths
    names = [load_scenario(path)['name'].casefold() for path in paths]
    assert len(names) == len(set(names))
