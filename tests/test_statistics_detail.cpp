// SPDX-License-Identifier: GPL-3.0-only
#include <iostream>
#include <limits>
static size_t rowBuildCounts[2]={0,0};
#define KPROBE_STATISTICS_ROW_BUILT(kind) (++rowBuildCounts[kind])
#include "StatisticsSnapshotFixture.h"
using json::Value;
static int checks=0;
static void require(bool ok){++checks;if(!ok)throw std::runtime_error("statistics detail assertion failed");}
static Value params(const Value& detail){Value p=Value::obj();p.object["detail"]=detail;return p;}
static Value fixture(int count,int rows,int slow){
    Value v=Value::obj();v.object["count"]=Value((double)count);v.object["mean_ms"]=count?Value(7.25):Value();
    if(!count)return v;
    v.object["first_frame"]=Value(5000.0);v.object["last_frame"]=Value(4999.0+count);
    v.object["median_ms"]=Value(6.0);v.object["p95_ms"]=Value(8.0);v.object["p99_ms"]=Value(10.0);v.object["max_ms"]=Value(31.0);
    v.object["series_truncated"]=Value::flag(count>100);
    v.object["navmesh_slow_calls_total"]=Value((double)(slow+3));
    v.object["navmesh_slow_calls_capacity"]=Value(32.0);v.object["navmesh_slow_calls_threshold_ms"]=Value(10.0);
    v.object["navmesh_slow_calls_retention_truncated"]=Value::flag(true);
    Value systems=Value::obj(),identity=Value::obj(),threads=Value::arr();
    identity.object["created_filetime"]=Value(std::string("134376915914545795"));identity.object["thread_id"]=Value(18372.0);
    identity.object["cpu_user_total_ms"]=Value(31.25);identity.object["cpu_kernel_total_ms"]=Value(15.625);identity.object["unavailable"]=Value();threads.array.push_back(identity);
    systems.object["threads"]=threads;systems.object["null_alias"]=Value();systems.object["calls_total"]=Value(1651.0);
    systems.object["negative_zero"]=Value(-0.0);systems.object["future_field"]=Value(std::string("preserved"));
    v.object["systems"]=systems;v.object["future_root_field"]=identity;
    v.object["per_frame"]=Value::arr();v.object["navmesh_slow_calls"]=Value::arr();
    for(int i=0;i<rows;++i){Value row=Value::obj();row.object["frame"]=Value((double)(5000+i));row.object["frame_ms"]=Value(7.25);v.object["per_frame"].array.push_back(row);}
    for(int i=0;i<slow;++i){Value row=identity;row.object["result"]=Value::flag(false);v.object["navmesh_slow_calls"].array.push_back(row);}
    return v;
}
static void projection(int count,int rows,int slow){
    Value original=fixture(count,rows,slow),compact=original;std::string bytes=json::dump(original);
    require(parseStatisticsDetail(Value::obj())==StatisticsAggregates);
    applyStatisticsDetail(compact,StatisticsFull);require(json::dump(compact)==bytes);
    applyStatisticsDetail(compact,parseStatisticsDetail(params(Value(std::string("full")))));require(json::dump(compact)==bytes);
    applyStatisticsDetail(compact,parseStatisticsDetail(params(Value(std::string("aggregates")))));
    require(json::dump(original)==bytes);require(compact.at("per_frame").type==Value::NIL&&compact.at("navmesh_slow_calls").type==Value::NIL);
    const Value& m=compact.at("statistics_detail");require(m.type==Value::OBJECT&&m.object.size()==3&&m.at("mode").str=="aggregates");
    require(m.at("per_frame_rows_omitted").number==rows&&m.at("navmesh_slow_rows_omitted").number==slow);
    compact.object.erase("statistics_detail");compact.object.erase("per_frame");compact.object.erase("navmesh_slow_calls");
    original.object.erase("per_frame");original.object.erase("navmesh_slow_calls");require(json::dump(compact)==json::dump(original));
}
static void badParam(const Value& detail){bool rejected=false;try{parseStatisticsDetail(params(detail));}catch(const std::runtime_error&){rejected=true;}require(rejected);}
static void badResponse(Value v){std::string before=json::dump(v);bool rejected=false;try{applyStatisticsDetail(v,StatisticsAggregates);}catch(const std::runtime_error&){rejected=true;}require(rejected);require(json::dump(v)==before);}
static int snapshotCases=0;
static void snapshotOracle(int available,int requested,int retained,int layout,int flags,FunctionProbeTarget target){
    makeStatisticsSnapshot(available,retained,layout,flags,target);
    Value legacy=legacyStatistics(requested);const std::string fullBytes=json::dump(legacy);
    const int count=std::min(available,requested),frames=std::min(count,100);
    size_t expectedSlow=0;
    if(count)for(int i=0;i<slowNavCount;++i){const SlowNavCall& call=slowNav[(slowNavNext-slowNavCount+slowNavCapacity+i)%slowNavCapacity];if(call.completionFrame>=samples[available-count].index&&call.completionFrame<=samples.back().index)++expectedSlow;}
    rowBuildCounts[0]=rowBuildCounts[1]=0;
    require(json::dump(stats(requested))==fullBytes);
    require(rowBuildCounts[0]==frames&&rowBuildCounts[1]==expectedSlow);
    rowBuildCounts[0]=rowBuildCounts[1]=0;
    require(json::dump(stats(requested,StatisticsFull))==fullBytes);
    require(rowBuildCounts[0]==frames&&rowBuildCounts[1]==expectedSlow);
    applyStatisticsDetail(legacy,StatisticsAggregates);
    rowBuildCounts[0]=rowBuildCounts[1]=0;
    Value direct=stats(requested,StatisticsAggregates);
    require(json::dump(direct)==json::dump(legacy));
    require(rowBuildCounts[0]==0&&rowBuildCounts[1]==0);
    require(direct.at("statistics_detail").at("per_frame_rows_omitted").number==frames);
    require(direct.at("statistics_detail").at("navmesh_slow_rows_omitted").number==expectedSlow);
    if(count){require(direct.at("navmesh_slow_calls_retention_truncated").boolean==(direct.at("navmesh_slow_calls_total").number>expectedSlow));require(direct.at("series_truncated").boolean==(count>100));}
    require(json::dump(legacyStatistics(requested))==fullBytes); // Snapshot remains unchanged.
    ++snapshotCases;
}
static void badDirect(Value value,size_t frames,size_t slow){
    const std::string before=json::dump(value);bool rejected=false;
    try{setAggregateStatisticsDetail(value,frames,slow);}catch(const std::runtime_error&){rejected=true;}
    require(rejected&&json::dump(value)==before);
}
int main(){try{
    SnapshotLock snapshotLockLifetime;
    require(_MSC_VER==1600&&sizeof(void*)==8);
    projection(0,0,0);projection(1,1,0);projection(100,100,32);projection(3600,100,32);
    projection(3600,100,0);projection(7,7,32);
    badParam(Value());badParam(Value::flag(true));badParam(Value::flag(false));badParam(Value(0.0));badParam(Value::obj());badParam(Value::arr());
    badParam(Value(std::string("")));badParam(Value(std::string("Full")));badParam(Value(std::string("compact")));badParam(Value(std::string("full\0",5)));
    bool rejected=false;try{parseStatisticsDetail(Value());}catch(const std::runtime_error&){rejected=true;}require(rejected);
    Value v=fixture(1,1,0);v.object["count"]=Value::flag(true);badResponse(v);
    const double invalidCounts[]={-1,3601,.5,std::numeric_limits<double>::infinity(),std::numeric_limits<double>::quiet_NaN()};
    for(int i=0;i<5;++i){v=fixture(1,1,0);v.object["count"]=Value(invalidCounts[i]);badResponse(v);}
    v=fixture(1,1,0);v.object.erase("per_frame");badResponse(v);
    v=fixture(1,1,0);v.object["per_frame"]=Value();badResponse(v);
    v=fixture(1,1,0);v.object["navmesh_slow_calls"]=Value::obj();badResponse(v);
    v=fixture(1,1,0);v.object.erase("navmesh_slow_calls");badResponse(v);
    badResponse(fixture(1,2,0));badResponse(fixture(3600,101,0));badResponse(fixture(3600,100,33));
    v=fixture(0,0,0);v.object["per_frame"]=Value::arr();v.object["per_frame"].array.push_back(Value());badResponse(v);
    v=fixture(1,1,0);v.object["statistics_detail"]=Value();badResponse(v);
    v=fixture(1,1,0);applyStatisticsDetail(v,StatisticsAggregates);badResponse(v);
    v=fixture(0,0,0);v.object["per_frame"]=Value::arr();v.object["navmesh_slow_calls"]=Value::arr();applyStatisticsDetail(v,StatisticsAggregates);
    require(v.at("mean_ms").type==Value::NIL&&v.at("count").number==0&&v.at("statistics_detail").at("per_frame_rows_omitted").number==0);
    v=fixture(1,1,0);std::string before=json::dump(v);rejected=false;try{applyStatisticsDetail(v,(StatisticsDetail)9);}catch(const std::runtime_error&){rejected=true;}require(rejected&&json::dump(v)==before);
    const int counts[]={0,1,7,99,100,101,3600};
    for(int i=0;i<7;++i)for(int layout=0;layout<5;++layout)snapshotOracle(counts[i],3600,32,layout,15,FunctionProbeOgreRootFrame);
    for(int target=FunctionProbeInvalid;target<=FunctionProbeOgreRootFrame;++target)
        for(int flags=0;flags<16;++flags)snapshotOracle(121,100,flags%3==0?0:32,flags%5,flags,(FunctionProbeTarget)target);
    snapshotOracle(3600,1,32,1,15,FunctionProbePeriodic);
    snapshotOracle(3600,7,32,3,15,FunctionProbeCharsUT);
    snapshotOracle(101,101,0,0,0,FunctionProbeInvalid);
    // Explicit bounds: completion_frame at both ends is included; older/newer
    // ring entries are excluded, and start_frame is not the admission criterion.
    makeStatisticsSnapshot(1,3,0,15,FunctionProbeOgreRootFrame);
    slowNav[0].completionFrame=9999;slowNav[1].completionFrame=10000;slowNav[2].completionFrame=10001;
    Value boundary=stats(1,StatisticsAggregates);require(boundary.at("statistics_detail").at("navmesh_slow_rows_omitted").number==1);
    v=fixture(0,0,0);badDirect(v,1,0);badDirect(v,0,1);
    v=fixture(1,1,0);badDirect(v,1,0);v.object.erase("per_frame");v.object.erase("navmesh_slow_calls");
    badDirect(v,0,0);badDirect(v,2,0);badDirect(v,1,33);
    v.object["count"]=Value::flag(true);badDirect(v,1,0);
    v=fixture(0,0,0);v.object["statistics_detail"]=Value();badDirect(v,0,0);
    rowBuildCounts[0]=rowBuildCounts[1]=0;rejected=false;try{stats(1,(StatisticsDetail)9);}catch(const std::runtime_error&){rejected=true;}require(rejected&&rowBuildCounts[0]==0&&rowBuildCounts[1]==0);
    std::cout<<"{\"passed\":true,\"checks\":"<<checks<<",\"snapshot_cases\":"<<snapshotCases<<",\"toolset\":\"v100 x64\",\"same_aggregate_projection\":true,\"default_request_aggregates\":true,\"explicit_full_unchanged\":true,\"aggregate_detail_rows_built\":0}\n";return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
