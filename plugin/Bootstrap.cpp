// SPDX-License-Identifier: GPL-3.0-only
// Optional preload helper. API declarations: kenshi/GameLauncher.h.
#include <kenshi/GameLauncher.h>
#include <core/Functions.h>
#include <Debug.h>
#include <windows.h>
#include <fstream>
#include <time.h>
#include "BootstrapActivation.h"
static void (*originalPaint)(GameLauncher*)=0;
static LONG submitted=0;
static BootstrapActivation activation;
static void paintHook(GameLauncher* launcher){
    originalPaint(launcher);
    if(!activation.active(_time64(0)))return;
    if(InterlockedCompareExchange(&submitted,1,0)==0){
        DebugLog("[KenshiOracle] optional bootstrap accepting configured launcher");
        launcher->OnBnClickedLauncherOk();
    }
}
__declspec(dllexport) void startPlugin(){
    // Opt in only for the isolated test campaign; regular launches keep the launcher.
    std::ifstream flag("mods/KenshiProbe/auto_launch.enabled",std::ios::in|std::ios::binary);activation=readBootstrapActivation(flag);
    if(!activation.active(_time64(0)))return;
    if(KenshiLib::AddHook(KenshiLib::GetRealAddress(&GameLauncher::OnPaint),(void*)&paintHook,&originalPaint)!=KenshiLib::SUCCESS)
        DebugLog("[KenshiOracle] optional bootstrap hook failed");
    else DebugLog("[KenshiOracle] optional launcher bootstrap installed");
}
