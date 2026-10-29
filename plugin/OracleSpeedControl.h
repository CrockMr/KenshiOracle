// SPDX-License-Identifier: GPL-3.0-only
#pragma once
#include <float.h>

namespace oracle {
// Knowledge about explicit control operations, not a guessed hidden engine
// field. A paused effective speed of zero never becomes a selected speed.
struct SpeedSelection {
    const void* world;
    double speed;
    bool known;
    const char* source;
    SpeedSelection():world(0),speed(0),known(false),source("unknown"){}
    void clear(){world=0;speed=0;known=false;source="unknown";}
    void synchronize(const void* current,bool ready){
        if(!current||!ready){clear();return;}
        if(world!=current){clear();world=current;}
    }
    void remember(double value,const char* provenance){
        if(world&&_finite(value)&&value>0&&value<=5){speed=value;known=true;source=provenance;}
    }
};
}
