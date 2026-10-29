// SPDX-License-Identifier: GPL-3.0-only
#pragma once

struct NavBuckets {
    double ms[3], maximum[3];
    unsigned long calls[3], slowCalls;
    double returnedMs[2], returnedMax[2];
    unsigned long returnedCalls[2], returnedHierarchical[2];
    NavBuckets():slowCalls(0){for(int i=0;i<3;++i){ms[i]=maximum[i]=0;calls[i]=0;}for(int i=0;i<2;++i){returnedMs[i]=returnedMax[i]=0;returnedCalls[i]=returnedHierarchical[i]=0;}}
};

struct SlowNavCall {
    double started, elapsed;
    unsigned long startFrame, completionFrame, thread, gameThread;
    unsigned int startKey, goalKey;
    float radius, water;
    float startVector[4], goalVector[4];
    double cpuUserMs, cpuKernelMs;
    int outputSizeBefore, outputSizeAfter;
    int kind;
    bool hierarchical, result, cpuAvailable;
};
