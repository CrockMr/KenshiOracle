// SPDX-License-Identifier: GPL-3.0-only
#pragma once
#include <string>

// Two rules of the probe's service that need no game header, so that they can
// be tested alone (tests/test_probe_service.cpp).
namespace oracle {
// A probe load is proved by the world itself: after the request the world must
// be seen unavailable (absent, uninitialized, resetting or loading), then ready.
// SaveManager::getCurrentGame() cannot prove it. In Kenshi 1.0.65 that name is
// read from the "continue" entry of settings.cfg at startup and written again
// only after a save; no load changes it (docs/scene-setup.md, Load lifecycle).
// A load refused by the engine leaves the old world untouched: it is never seen
// unavailable, so the load never completes.
struct LoadWitness {
    bool pending,unloaded;
    LoadWitness():pending(false),unloaded(false){}
    void request(){pending=true;unloaded=false;}
    // available: the world exists, is initialized, and neither resets nor loads.
    // ready: available, no load is pending, and the epoch accepts the requested
    // save. Returns true once, on the observation that completes the load.
    bool observe(bool available,bool ready){
        if(!pending)return false;
        if(!available){unloaded=true;return false;}
        if(!unloaded||!ready)return false;
        pending=false;return true;
    }
};
// The Renderer hook serves commands where the game loop does not run. It
// leaves a command that needs the loop in the queue for the loop's own hook.
// Without a ready world and with no loop frame for this many Renderer frames in
// a row (the main menu, or the blocking part of a load), no loop will take the
// command: it is answered world_not_ready at once instead of timing out.
static const unsigned long menuLoopIdleFrames=8;
enum MenuServiceAction {MenuServe,MenuWait,MenuRefuse};
inline bool menuServedCommand(const std::string& command,bool worldReady){
    return command=="ping"||command=="load_save"||command=="get_rekenshi_settings"||(command.compare(0,6,"setup_")==0&&!worldReady);
}
inline MenuServiceAction menuServiceAction(const std::string& command,bool worldReady,unsigned long framesWithoutLoop){
    if(menuServedCommand(command,worldReady))return MenuServe;
    return !worldReady&&framesWithoutLoop>=menuLoopIdleFrames?MenuRefuse:MenuWait;
}
// Renderer frames since the loop hook last advanced its frame counter.
struct LoopIdle {
    unsigned long loopFrame,frames;
    LoopIdle():loopFrame(0),frames(0){}
    void observe(unsigned long currentLoopFrame){
        if(currentLoopFrame!=loopFrame){loopFrame=currentLoopFrame;frames=0;}
        else if(frames<0xfffffffful)++frames;
    }
};
}
