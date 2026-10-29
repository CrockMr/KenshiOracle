// SPDX-License-Identifier: GPL-3.0-only
#pragma once
// Project-owned synthetic data only. No Kenshi/SDK includes or runtime access.
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <deque>
#include <algorithm>
#include <limits>
#include "../plugin/StatisticsDetail.h"
#include "../plugin/NavTelemetry.h"
#include "../plugin/CallTelemetry.h"
#include "../plugin/CharsTelemetry.h"
#include "../plugin/FunctionProbeTarget.h"
using json::Value;
struct Sample {double ms,mainAI,navMs,navMax;unsigned long index,navCalls;NavBuckets navThreads;CallBuckets functionCalls;unsigned long functionNested;};
static std::deque<Sample> samples;
static CharsHistory charsHistory;
static bool profiling=false,navProfiling=false,functionProfiling=false,functionThreadCpu=false;
static FunctionProbeTarget functionTarget=FunctionProbePeriodic;
static const int slowNavCapacity=32;
static const double slowNavThreshold=10.0;
static SlowNavCall slowNav[slowNavCapacity];
static int slowNavNext=0,slowNavCount=0;
static const char* navKinds[3]={"game_thread","other_threads","unclassified"};
static const char* rootFrameSymbol="?renderOneFrame@Root@Ogre@@QEAA_NXZ";
struct SyntheticBinding {std::string modulePath,addressHex;};
static SyntheticBinding rootFrameBinding;
static CRITICAL_SECTION snapshotLock;
struct SnapshotLock {SnapshotLock(){InitializeCriticalSection(&snapshotLock);}~SnapshotLock(){DeleteCriticalSection(&snapshotLock);}};
struct Guard {Guard(){EnterCriticalSection(&snapshotLock);}~Guard(){LeaveCriticalSection(&snapshotLock);}};
#include "../plugin/FrameStatistics.h"
#include "StatisticsLegacyOracle.h"

// layout 0: all retained calls in the window; 1: mixed before/inside/after;
// 2: all outside; 3: ring wrapped and aggregate count exceeds capacity;
// 4: aggregate slow count == retained count, so retention is not truncated.
static void makeStatisticsSnapshot(int available,int retained,int layout,int flags,FunctionProbeTarget target){
    samples.clear();profiling=(flags&1)!=0;navProfiling=(flags&2)!=0;
    functionProfiling=(flags&4)!=0;functionThreadCpu=(flags&8)!=0;functionTarget=target;
    rootFrameBinding.modulePath="OWN fixture\\OgreMain_x64.dll";rootFrameBinding.addressHex="0x123456789abc";
    for(int i=0;i<available;++i){
        Sample s;s.ms=3.125+(i%11)*.25;s.mainAI=.5+(i%3)*.125;s.navMs=(i%5)*.25;s.navMax=s.navMs;
        s.index=10000+i;s.navCalls=i%5;s.functionNested=i%3;
        for(int k=0;k<3;++k){s.navThreads.calls[k]=(i+k)%3;s.navThreads.ms[k]=s.navThreads.calls[k]*.125;s.navThreads.maximum[k]=s.navThreads.calls[k]?.125:0;}
        for(int k=0;k<2;++k){s.navThreads.returnedCalls[k]=(i+k)%2;s.navThreads.returnedMs[k]=s.navThreads.returnedCalls[k]*.25;s.navThreads.returnedMax[k]=s.navThreads.returnedMs[k];s.navThreads.returnedHierarchical[k]=k?s.navThreads.returnedCalls[k]:0;}
        // Keep retention tests independent of ring membership: old ring records
        // may be out of this requested tail even when aggregate totals are high.
        s.navThreads.slowCalls=layout==4?(i==available-1?(unsigned long)retained:0):2;
        CharsBuckets chars;
        for(int k=0;k<10;++k){
            unsigned long tid=100+(k%9);unsigned __int64 created=k==0?0:134376935315380313ui64+k;
            s.functionCalls.record(tid,.5+(k%3)*.125,functionThreadCpu&&k%3!=0,15.625,3.125,created);
            chars.record(tid,created,100.0,100.25+k*.125,100.375+k*.125);
        }
        charsHistory.store(s.index,chars);samples.push_back(s);
    }
    slowNavCount=retained;slowNavNext=layout==3?7:retained%slowNavCapacity;
    for(int k=0;k<retained;++k){
        SlowNavCall c={0};unsigned long inside=10000+(available?((k*13)%available):0);
        c.completionFrame=layout==2?9999:(layout==1?(k%3==0?9999:(k%3==1?inside:10000+available)):inside);
        c.startFrame=c.completionFrame-2;c.thread=100+k%9;c.gameThread=101;c.kind=k%3;
        c.started=9999.125+k*16.0;c.elapsed=10.25+k;c.startKey=0xffffffffu-k;c.goalKey=k;
        c.radius=k%3?1.25f:std::numeric_limits<float>::quiet_NaN();c.water=k%2?0.0f:std::numeric_limits<float>::infinity();
        c.hierarchical=k%2!=0;c.result=k%3!=0;c.cpuAvailable=k%2!=0;c.cpuUserMs=31.25;c.cpuKernelMs=15.625;
        c.outputSizeBefore=k;c.outputSizeAfter=c.result?k+4:k;
        for(int q=0;q<4;++q){c.startVector[q]=(float)(k*8+q);c.goalVector[q]=(float)(k*8-q);}
        if(k%3==0)c.startVector[3]=std::numeric_limits<float>::infinity();
        if(k%5==0)c.goalVector[2]=std::numeric_limits<float>::quiet_NaN();
        slowNav[(slowNavNext-slowNavCount+slowNavCapacity+k)%slowNavCapacity]=c;
    }
}
