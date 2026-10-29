"""Two-phase camera restoration against a configurable synthetic tracking rig."""
import asyncio
from copy import deepcopy

import pytest

from fake_probe import FakeProbe
from oracle_runner import OracleSession, control_params


def config(tmp_path):
    return dict(runtime=str(tmp_path/'runtime'), runs=str(tmp_path/'runs'),
                oracle_output=str(tmp_path/'native'), timeout=2,
                load_timeout=2, run_until_timeout=2, scenario_timeout=10)


@pytest.mark.parametrize('baseline_height', [0, 9.8, 17.125])
def test_controller_observes_tracking_baseline_after_reload_instead_of_guessing_actor_height(
        tmp_path, baseline_height):
    async def run():
        cfg = config(tmp_path)
        fake = FakeProbe(cfg['oracle_output'], camera_tracking_base_offset=[2, baseline_height, -4],
                         camera_move_duration=.12)
        actor = fake.state['characters'][0]
        actor['position'] = [5, 23, -13]
        fake.camera_follow_id = actor['id']
        fake._camera_tracking_active = True
        fake.camera_follow_offset = [7, -3, 11]
        original = await fake.call('get_scene_state')
        assert original['camera_center'] == pytest.approx([14, 20+baseline_height, -6])
        # Loading changes the actor's foot location; the requested camera still
        # belongs to the captured pose, and its baseline is an independent rig.
        fake.initial_state['characters'][0]['position'] = [14, 58, -31]
        session = OracleSession(cfg, fake)
        await session.load('Synthetic save')
        after_load = deepcopy(fake.state['characters'])
        baseline_observations, observations = [], []
        restored = await session.restore_controls(original,
            baseline_observations=baseline_observations, observations=observations)
        expected_baseline = [16, 58+baseline_height, -35]
        assert restored['baseline']['camera_center'] == pytest.approx(expected_baseline)
        assert restored['scene']['camera_center'] == pytest.approx(original['camera_center'])
        assert fake.camera_follow_offset == pytest.approx([
            wanted-observed for wanted, observed in zip(original['camera_center'], expected_baseline)])
        assert restored['pose_verified_in_pause'] and not restored['unpaused_after_verification']
        assert fake.state['characters'] == after_load
        assert restored['scene']['camera_restore_token'] is None
        assert not restored['scene']['scene_camera_control_owned']
        assert restored['scene']['edge_scrolling'] == original['edge_scrolling']
        assert any(row.get('accepted') for row in baseline_observations)
        assert any(not row.get('accepted') for row in baseline_observations)
        assert baseline_observations[-1]['stable_seconds'] >= .5
        assert observations[-1]['stable_seconds'] >= .5
        mutations = [row['command'] for row in fake.requests if row['command'] in (
            'prepare_scene_control', 'commit_scene_control', 'restore_scene_control')]
        assert mutations == ['prepare_scene_control', 'commit_scene_control']
    asyncio.run(run())


@pytest.mark.parametrize('follow,free,paused', [
    (True, False, True), (True, True, False), (False, False, False), (False, True, True),
])
def test_direct_controller_restores_follow_unfollow_modes_and_verifies_before_resume(tmp_path, follow, free, paused):
    async def run():
        cfg = config(tmp_path)
        fake = FakeProbe(cfg['oracle_output'], camera_tracking_base_offset=[1, 12.25, -2])
        fake.camera_center = [-21, 6, 44]
        fake.free_camera = free
        fake.camera_zoom = 55 if free else -55
        fake.state['clock']['paused'] = paused
        original = await fake.call('get_scene_state')
        params = control_params(original)
        params['camera_follow_id'] = fake.state['characters'][0]['id'] if follow else None
        actors = deepcopy(fake.state['characters'])
        observations = []
        result = await OracleSession(cfg, fake).restore_controls(params=params, observations=observations)
        assert result['pose_verified_in_pause']
        assert result['unpaused_after_verification'] is (not paused)
        assert result['scene']['paused'] is paused
        assert result['scene']['free_camera'] is free
        assert result['scene']['camera_zoom'] == params['camera_zoom']
        assert result['scene']['camera_follow_id'] == params['camera_follow_id']
        assert result['scene']['camera_center'] == pytest.approx(params['camera_center'])
        assert fake.state['characters'] == actors
        assert observations[-1]['scene']['paused'] is True
        prepares = [index for index, row in enumerate(fake.requests) if row['command'] == 'prepare_scene_control']
        commits = [index for index, row in enumerate(fake.requests) if row['command'] == 'commit_scene_control']
        resumes = [index for index, row in enumerate(fake.requests)
                   if row['command'] == 'pause' and row['params']['paused'] is False]
        assert len(prepares) == len(commits) == 1 and prepares[0] < commits[0]
        assert fake.requests[prepares[0]]['params']['paused'] is True
        if paused:
            assert resumes == []
        else:
            assert len(resumes) == 1 and resumes[0] > commits[0]
            assert result['verified_paused_scene']['paused'] is True
            assert result['verified_paused_scene']['camera_center'] == pytest.approx(params['camera_center'])
    asyncio.run(run())
