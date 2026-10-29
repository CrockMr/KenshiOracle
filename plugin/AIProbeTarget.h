// SPDX-License-Identifier: GPL-3.0-only
#pragma once
#include <string>
enum AIProbeTarget { AIProbeInvalid, AIProbePeriodic, AIProbeFourFrame };
static AIProbeTarget parseAIProbeTarget(const std::string& name){
    if(name.empty()||name=="periodicUpdate")return AIProbePeriodic;
    if(name=="update4Frame")return AIProbeFourFrame;
    return AIProbeInvalid;
}
static const char* aiProbeFunctionName(AIProbeTarget target){
    return target==AIProbePeriodic?"AI::periodicUpdate":target==AIProbeFourFrame?"AI::update4Frame":"";
}
