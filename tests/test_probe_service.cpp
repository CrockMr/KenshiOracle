// SPDX-License-Identifier: GPL-3.0-only
#include "../plugin/ProbeService.h"
#include <iostream>
#include <stdexcept>
static unsigned checks=0;
static void require(bool v){++checks;if(!v)throw std::runtime_error("probe service assertion failed");}
int main(){try{
    require(_MSC_VER==1600&&sizeof(void*)==8);
    using namespace oracle;
    // A load completes once: unavailable after the request, then ready.
    {LoadWitness w;require(!w.pending&&!w.observe(true,true)&&!w.observe(false,false));
        w.request();require(w.pending&&!w.unloaded);
        require(!w.observe(true,false));require(!w.unloaded);
        require(!w.observe(false,false));require(w.unloaded&&w.pending);
        require(!w.observe(true,false));require(w.pending);
        require(w.observe(true,true));require(!w.pending);
        require(!w.observe(true,true));}
    // A load the engine refused leaves the old world in place: it reads ready
    // again without ever having been unavailable, and never completes.
    {LoadWitness w;w.request();for(int i=0;i<1000;++i)require(!w.observe(true,true));require(w.pending&&!w.unloaded);}
    // From the main menu the world is unavailable at the request already; a load
    // that fails there never reads ready.
    {LoadWitness w;w.request();for(int i=0;i<1000;++i)require(!w.observe(false,false));require(w.pending&&w.unloaded);require(w.observe(true,true));}
    // A second request forgets what the first one saw.
    {LoadWitness w;w.request();require(!w.observe(false,false));w.request();require(!w.unloaded&&!w.observe(true,true));
        require(!w.observe(false,false));require(w.observe(true,true));}
    // An unavailable world is never ready, whatever the caller claims.
    {LoadWitness w;w.request();require(!w.observe(false,true));require(w.pending);}

    // Commands the Renderer hook serves itself.
    require(menuServiceAction("ping",false,0)==MenuServe&&menuServiceAction("ping",true,100000)==MenuServe);
    require(menuServiceAction("load_save",false,100000)==MenuServe&&menuServiceAction("get_rekenshi_settings",true,0)==MenuServe);
    require(menuServiceAction("setup_info",false,0)==MenuServe&&menuServiceAction("setup_spawn_squad",false,100000)==MenuServe);
    // With a ready world a setup command belongs to the loop, like any other.
    require(menuServiceAction("setup_info",true,0)==MenuWait&&menuServiceAction("setup_info",true,100000)==MenuWait);
    // A loop command waits while a loop runs or a world is ready.
    require(menuServiceAction("get_clock",true,0)==MenuWait&&menuServiceAction("get_clock",true,100000)==MenuWait);
    require(menuServiceAction("get_clock",false,0)==MenuWait&&menuServiceAction("get_clock",false,menuLoopIdleFrames-1)==MenuWait);
    // No ready world and no loop frame: it is refused instead of left to time out.
    require(menuServiceAction("get_clock",false,menuLoopIdleFrames)==MenuRefuse&&menuServiceAction("dump_state",false,100000)==MenuRefuse);
    require(menuServiceAction("no_such_command",false,menuLoopIdleFrames)==MenuRefuse&&menuServiceAction("",false,menuLoopIdleFrames)==MenuRefuse);
    require(menuServiceAction("setup",false,menuLoopIdleFrames)==MenuRefuse&&menuServiceAction("pings",false,menuLoopIdleFrames)==MenuRefuse);

    // Renderer frames without a loop frame are counted; a loop frame resets them.
    {LoopIdle idle;require(idle.frames==0);idle.observe(0);idle.observe(0);idle.observe(0);require(idle.frames==3);
        idle.observe(1);require(idle.frames==0&&idle.loopFrame==1);idle.observe(1);require(idle.frames==1);
        idle.observe(7);require(idle.frames==0);for(unsigned long i=0;i<menuLoopIdleFrames;++i)idle.observe(7);
        require(idle.frames==menuLoopIdleFrames&&menuServiceAction("get_clock",false,idle.frames)==MenuRefuse);
        idle.observe(8);require(menuServiceAction("get_clock",false,idle.frames)==MenuWait);}
    {LoopIdle idle;idle.frames=0xfffffffful;idle.observe(0);require(idle.frames==0xfffffffful);}
    std::cout<<"Probe service checks passed: "<<checks<<" assertions\n";return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
