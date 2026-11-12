"""The native probe uses the two service rules of plugin/ProbeService.h where they belong.

The rules themselves are tested natively (tests/test_probe_service.cpp, v100 x64). These checks read the sources:
they hold the wiring, which no native test can reach without the game.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PROBE = (ROOT / 'plugin' / 'Probe.cpp').read_text(encoding='utf-8')
SETUP = (ROOT / 'plugin' / 'OracleSetup.h').read_text(encoding='utf-8')
SERVICE = (ROOT / 'plugin' / 'ProbeService.h').read_text(encoding='utf-8')


def function_body(source, signature):
    """The text of one top-level function, from its signature to the next line starting a declaration."""
    start = source.index(signature)
    end = re.search(r'\n(?:static|inline|struct|namespace|template|#include)\b', source[start + len(signature):])
    return source[start:start + len(signature) + (end.start() if end else len(source))]


def test_a_probe_load_is_proved_by_the_world_and_not_by_the_current_save_name():
    observe = function_body(SETUP, 'inline void observeSetupLoad(GameWorld* world){')
    # getCurrentGame() names the last save written or the settings' "continue" entry; no load changes it.
    assert 'getCurrentGame' not in observe
    assert 'setupLoad.witness.observe(available,ready)' in observe
    assert 'world->initialized&&!world->gameResetting&&!world->isLoadingFromASaveGame()' in observe
    assert 'saves->name==setupLoad.requestedSave' in observe
    assert 'setupLoad.witness.request()' in function_body(SETUP, 'inline void acceptSetupLoad(')
    assert '!setupLoad.witness.pending' in function_body(SETUP, 'inline bool setupProbeLoadCurrent(){')


def test_the_renderer_hook_watches_the_load_and_the_loop_before_it_serves_commands():
    renderer = function_body(PROBE, 'static void rendererHook(Renderer* renderer){')
    served = renderer.index('drainCommands(ou,true)')
    # The loop hook does not run at the main menu: the Renderer hook must see the world unavailable there.
    assert -1 < renderer.index('oracle::observeSetupLoad(ou)') < served
    assert -1 < renderer.index('loopIdle.observe(frame)') < served
    assert 'oracle::observeSetupLoad(world)' in function_body(PROBE, 'static void loopHook(GameWorld* world,float dt){')


def test_a_command_no_loop_will_take_is_answered_world_not_ready():
    drain = function_body(PROBE, 'static void drainCommands(GameWorld* world,bool menuService){')
    assert 'oracle::menuServiceAction(w->request.at("command").str,oracle::worldReady(world),loopIdle.frames)' in drain
    assert 'if(action==oracle::MenuWait){queue.push_front(w);break;}' in drain
    # Same code and message as a command that finds no ready world by itself.
    refusal = 'throw oracle::Error("world_not_ready","world is unavailable or a save is loading")'
    assert 'if(refuse)' + refusal in drain
    assert refusal.replace('throw oracle::', 'throw ') in function_body(
        (ROOT / 'plugin' / 'OracleState.h').read_text(encoding='utf-8'), 'inline void requireWorld(GameWorld* world){')
    # The commands the Renderer hook serves itself are listed once.
    assert PROBE.count('"get_rekenshi_settings"') == 1
    assert 'command=="ping"||command=="load_save"||command=="get_rekenshi_settings"' in SERVICE


def test_the_native_rules_have_their_v100_test():
    script = (ROOT / 'tests' / 'test-probe-service-v100.cmd').read_text(encoding='utf-8')
    assert 'test_probe_service.cpp' in script
    assert '#include "../plugin/ProbeService.h"' in (ROOT / 'tests' / 'test_probe_service.cpp').read_text(encoding='utf-8')
