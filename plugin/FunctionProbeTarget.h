// SPDX-License-Identifier: GPL-3.0-only
#pragma once
#include <string>

enum FunctionProbeTarget {FunctionProbeInvalid,FunctionProbePeriodic,FunctionProbeFourFrame,FunctionProbeCharsUT,FunctionProbeZoneRendertime,FunctionProbeMedicalPeriodic,FunctionProbeHavokUpdate,FunctionProbeMainLoopGPU,FunctionProbeRendererUpdate,FunctionProbeOgreRootFrame};
static FunctionProbeTarget parseFunctionProbeTarget(const std::string& name){
    if(name.empty()||name=="periodicUpdate")return FunctionProbePeriodic;
    if(name=="update4Frame")return FunctionProbeFourFrame;
    if(name=="charsUpdateUT")return FunctionProbeCharsUT;
    if(name=="zoneRendertimeThread")return FunctionProbeZoneRendertime;
    if(name=="medicalPeriodicUpdate")return FunctionProbeMedicalPeriodic;
    if(name=="havokCharacterUpdate")return FunctionProbeHavokUpdate;
    if(name=="mainLoopGPUSensitive")return FunctionProbeMainLoopGPU;
    if(name=="rendererUpdate")return FunctionProbeRendererUpdate;
    if(name=="ogreRenderOneFrame")return FunctionProbeOgreRootFrame;
    return FunctionProbeInvalid;
}
static bool isAIProbe(FunctionProbeTarget target){return target==FunctionProbePeriodic||target==FunctionProbeFourFrame;}
static bool reusesMainServiceHook(FunctionProbeTarget target){return target==FunctionProbeMainLoopGPU;}
static bool reusesRendererServiceHook(FunctionProbeTarget target){return target==FunctionProbeRendererUpdate;}
static bool reusesServiceHook(FunctionProbeTarget target){return reusesMainServiceHook(target)||reusesRendererServiceHook(target);}
static const char* functionProbeName(FunctionProbeTarget target){
    return target==FunctionProbePeriodic?"AI::periodicUpdate":target==FunctionProbeFourFrame?"AI::update4Frame":
        target==FunctionProbeCharsUT?"GameWorld::charsUpdateUT":
        target==FunctionProbeZoneRendertime?"ZoneManager::updateRendertimeThread":
        target==FunctionProbeMedicalPeriodic?"MedicalSystem::periodicUpdate":
        target==FunctionProbeHavokUpdate?"HavokCharacter::update":
        target==FunctionProbeMainLoopGPU?"GameWorld::mainLoop_GPUSensitiveStuff":
        target==FunctionProbeRendererUpdate?"Renderer::update":
        target==FunctionProbeOgreRootFrame?"Ogre::Root::renderOneFrame":"";
}
