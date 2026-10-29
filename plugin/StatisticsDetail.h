// SPDX-License-Identifier: GPL-3.0-only
#pragma once
#include "json.h"

enum StatisticsDetail { StatisticsFull, StatisticsAggregates };

inline StatisticsDetail parseStatisticsDetail(const json::Value& params){
    if(params.type!=json::Value::OBJECT)throw std::runtime_error("statistics params must be object");
    std::map<std::string,json::Value>::const_iterator i=params.object.find("detail");
    if(i==params.object.end())return StatisticsAggregates;
    if(i->second.type!=json::Value::STRING)throw std::runtime_error("detail must be full or aggregates");
    if(i->second.str=="full")return StatisticsFull;
    if(i->second.str=="aggregates")return StatisticsAggregates;
    throw std::runtime_error("detail must be full or aggregates");
}

inline size_t statisticsDetailRows(const json::Value& statistics,const char* key,size_t maximum,bool empty){
    std::map<std::string,json::Value>::const_iterator i=statistics.object.find(key);
    if(i==statistics.object.end()){
        if(empty)return 0;
        throw std::runtime_error("statistics detail rows missing");
    }
    if(i->second.type!=json::Value::ARRAY||i->second.array.size()>maximum||
        (empty&&!i->second.array.empty()))throw std::runtime_error("invalid statistics detail rows");
    return i->second.array.size();
}

// Direct aggregate response: the caller counted the same filtered slow ring,
// but deliberately did not construct either detail array. Validate before any
// mutation; no omitted count is inferred from aggregate totals or capacity.
inline void setAggregateStatisticsDetail(json::Value& statistics,size_t frames,size_t slow){
    if(statistics.type!=json::Value::OBJECT||statistics.object.count("statistics_detail"))
        throw std::runtime_error("invalid statistics detail response");
    const json::Value& count=statistics.at("count");
    if(count.type!=json::Value::NUMBER||!_finite(count.number)||count.number<0||count.number>3600||
        floor(count.number)!=count.number)throw std::runtime_error("invalid statistics detail count");
    if(frames!=std::min((size_t)count.number,(size_t)100)||slow>32||(count.number==0&&slow))
        throw std::runtime_error("invalid omitted statistics detail counts");
    const char* keys[]={"per_frame","navmesh_slow_calls"};
    for(int k=0;k<2;++k){
        std::map<std::string,json::Value>::const_iterator i=statistics.object.find(keys[k]);
        if(i!=statistics.object.end()&&i->second.type!=json::Value::NIL)
            throw std::runtime_error("direct statistics detail rows already built");
    }
    json::Value metadata=json::Value::obj();
    metadata.object["mode"]=json::Value(std::string("aggregates"));
    metadata.object["per_frame_rows_omitted"]=json::Value((double)frames);
    metadata.object["navmesh_slow_rows_omitted"]=json::Value((double)slow);
    statistics.object["per_frame"]=json::Value();
    statistics.object["navmesh_slow_calls"]=json::Value();
    statistics.object["statistics_detail"]=metadata;
}

// Reference projection after the existing full response has been built.
// Retained as an independent native oracle for the direct construction path.
// All aggregate values, identities, bounds and retention flags remain untouched.
inline void applyStatisticsDetail(json::Value& statistics,StatisticsDetail detail){
    if(detail==StatisticsFull)return;
    if(detail!=StatisticsAggregates)throw std::runtime_error("invalid statistics detail mode");
    if(statistics.type!=json::Value::OBJECT||statistics.object.count("statistics_detail"))
        throw std::runtime_error("invalid statistics detail response");
    const json::Value& count=statistics.at("count");
    if(count.type!=json::Value::NUMBER||!_finite(count.number)||count.number<0||count.number>3600||
        floor(count.number)!=count.number)throw std::runtime_error("invalid statistics detail count");
    const size_t frames=statisticsDetailRows(statistics,"per_frame",std::min((size_t)count.number,(size_t)100),count.number==0);
    const size_t slow=statisticsDetailRows(statistics,"navmesh_slow_calls",32,count.number==0);
    json::Value metadata=json::Value::obj();
    metadata.object["mode"]=json::Value(std::string("aggregates"));
    metadata.object["per_frame_rows_omitted"]=json::Value((double)frames);
    metadata.object["navmesh_slow_rows_omitted"]=json::Value((double)slow);
    statistics.object["per_frame"]=json::Value();
    statistics.object["navmesh_slow_calls"]=json::Value();
    statistics.object["statistics_detail"]=metadata;
}
