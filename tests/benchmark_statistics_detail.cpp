// SPDX-License-Identifier: GPL-3.0-only
// Native production stats() against frozen 0.8.19 stats()+projection, same
// immutable OWN snapshots. No game/SDK, hooks, transport, locks under contention,
// JSON parsing or measured FPS. JSON validation is outside the timed sections.
#include <iostream>
#include "StatisticsSnapshotFixture.h"
static volatile unsigned __int64 sink=0;
static double clockMs(){LARGE_INTEGER t,f;QueryPerformanceCounter(&t);QueryPerformanceFrequency(&f);return 1000.0*t.QuadPart/f.QuadPart;}
static unsigned long fnv1a(const std::string& text){unsigned long result=2166136261ul;for(size_t i=0;i<text.size();++i)result=(result^(unsigned char)text[i])*16777619ul;return result;}
static Value operation(int op,int requested){
    if(op==0)return legacyStatistics(requested);
    if(op==1)return stats(requested,StatisticsFull);
    if(op==2){Value v=legacyStatistics(requested);applyStatisticsDetail(v,StatisticsAggregates);return v;}
    return stats(requested,StatisticsAggregates);
}
struct Fixture {const char* name;int count,slow,layout;bool sparse;};
static void setup(const Fixture& f){
    makeStatisticsSnapshot(f.count,f.slow,f.layout,15,FunctionProbeOgreRootFrame);
    if(f.sparse)for(size_t i=0;i<samples.size();++i){
        Sample& s=samples[i];s.mainAI=0;s.navMs=s.navMax=0;s.navCalls=0;s.navThreads=NavBuckets();s.functionNested=0;
        s.functionCalls=CallBuckets();s.functionCalls.record(18784,7.25,true,0,0,134376935315380313ui64);
        CharsBuckets empty;charsHistory.store(s.index,empty);
    }
}
int main(){try{
    if(_MSC_VER!=1600||sizeof(void*)!=8)throw std::runtime_error("v100 x64 required");
    SnapshotLock lockLifetime;
    const Fixture fixtures[]={
        {"empty",0,0,0,true},{"sparse_root_60",60,0,0,true},{"sparse_root_100",100,0,0,true},
        {"sparse_root_600",600,0,0,true},{"sparse_root_3600",3600,0,0,true},
        {"dense_root_600_retained32",600,32,0,false},
        {"dense_root_600_mixed_retention",600,32,1,false},
        {"dense_root_3600_wrapped_ring",3600,32,3,false}
    };
    const char* names[]={"legacy_full","direct_full","legacy_projected","direct_aggregates"};
    const int iterations=40,repeats=7;
    Value report=Value::obj(),rows=Value::arr(),inventory=Value::arr();
    report.object["schema"]=Value(1.0);report.object["synthetic_only"]=Value::flag(true);
    report.object["compiler"]=Value((double)_MSC_VER);report.object["pointer_bytes"]=Value((double)sizeof(void*));
    report.object["iterations"]=Value((double)iterations);report.object["repeats"]=Value((double)repeats);
    report.object["clock"]=Value(std::string("QueryPerformanceCounter"));
    report.object["ordering"]=Value(std::string("All eight operations rotated by repetition; immutable snapshot per fixture; one warm-up per operation."));
    report.object["scope"]=Value(std::string("Complete native stats construction including destruction; optional JSON serialization. No IPC, game contention, concurrent mutation or FPS inference."));
    for(int kind=0;kind<(int)(sizeof(fixtures)/sizeof(fixtures[0]));++kind){
        const Fixture& f=fixtures[kind];setup(f);const int requested=f.count?f.count:1;
        std::string full=json::dump(operation(0,requested)),compact=json::dump(operation(2,requested));
        if(full!=json::dump(operation(1,requested))||compact!=json::dump(operation(3,requested)))throw std::runtime_error("native statistics oracle disagreement");
        Value inv=Value::obj();inv.object["name"]=Value(std::string(f.name));inv.object["available_frames"]=Value((double)f.count);
        inv.object["requested_frames"]=Value((double)requested);inv.object["slow_ring_records"]=Value((double)f.slow);
        inv.object["full_bytes"]=Value((double)full.size());inv.object["compact_bytes"]=Value((double)compact.size());
        inv.object["full_fnv1a32"]=Value((double)fnv1a(full));inv.object["compact_fnv1a32"]=Value((double)fnv1a(compact));
        inv.object["oracle_equal"]=Value::flag(true);inventory.array.push_back(inv);
        for(int mode=0;mode<8;++mode){Value warm=operation(mode%4,requested);if(mode>=4)sink+=json::dump(warm).size();else sink+=warm.object.size();}
        for(int rep=0;rep<repeats;++rep)for(int order=0;order<8;++order){
            const int mode=(order+rep)%8,op=mode%4;const bool serialize=mode>=4;double start=clockMs();
            for(int i=0;i<iterations;++i){Value result=operation(op,requested);sink+=result.object.size()+(unsigned __int64)result.at("count").number;if(serialize)sink+=json::dump(result).size();}
            const double elapsed=clockMs()-start;
            Value row=Value::obj();row.object["fixture"]=Value(std::string(f.name));row.object["repetition"]=Value((double)rep);row.object["order"]=Value((double)order);
            row.object["operation"]=Value(std::string(names[op]));row.object["serialize"]=Value::flag(serialize);
            row.object["elapsed_ms"]=Value(elapsed);row.object["per_operation_ms"]=Value(elapsed/iterations);rows.array.push_back(row);
        }
        if(full!=json::dump(operation(0,requested))||compact!=json::dump(operation(3,requested)))throw std::runtime_error("snapshot changed during benchmark");
    }
    report.object["fixtures"]=inventory;report.object["rows"]=rows;report.object["checksum"]=Value((double)sink);
    std::cout<<json::dump(report)<<"\n";return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
