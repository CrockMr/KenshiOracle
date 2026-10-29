// SPDX-License-Identifier: GPL-3.0-only
// Same OWN synthetic fixtures as benchmark_json.cpp; no game/SDK input.
#include <windows.h>
#include <iostream>
#include "../../plugin/json.h"
typedef json::Value Value;
static volatile unsigned __int64 sink=0;
static Value fixture(int kind){
    Value out=Value::obj();out.object["synthetic"]=Value::flag(true);out.object["frame"]=Value(1234.0);
    if(kind==0){out.object["name"]=Value(std::string("synthetic-empty\n\"\\"));out.object["paused"]=Value::flag(true);return out;}
    Value rows=Value::arr();int count=kind==1?40:100;
    for(int i=0;i<count;++i){Value row=Value::obj();std::ostringstream label;label<<"synthetic-"<<i;row.object["name"]=Value(label.str());
        row.object["index"]=Value((double)i);row.object["available"]=Value::flag(i%2==0);
        Value parts=Value::arr();for(int j=0;j<(kind==1?7:3);++j){Value p=Value::obj();p.object["value"]=Value(99.125-j-i*.01);p.object["maximum"]=Value(100.0);p.object["status"]=Value(std::string("synthetic\tpart"));parts.array.push_back(p);}
        row.object["parts"]=parts;rows.array.push_back(row);}
    out.object[kind==1?"actors":"series"]=rows;return out;
}
static Value envelope(const Value& source,bool transfer){
    Value payload=source,response=Value::obj();response.object["id"]=Value(std::string("synthetic-request"));
    if(transfer)response.object["result"].swap(payload);else response.object["result"]=payload;return response;
}
static Value pipeline(const Value& source,bool transfer){
    Value work,reply;
    if(transfer){Value response=envelope(source,true);work.swap(response);reply.swap(work);}
    else{work=envelope(source,false);reply=work;}
    return reply;
}
static double clockMs(){LARGE_INTEGER f,t;QueryPerformanceFrequency(&f);QueryPerformanceCounter(&t);return 1000.0*t.QuadPart/f.QuadPart;}
static unsigned long hash(const std::string& s){unsigned long h=2166136261ul;for(size_t i=0;i<s.size();++i)h=(h^(unsigned char)s[i])*16777619ul;return h;}
int main(){try{
    Value report=Value::obj(),rows=Value::arr();report.object["schema"]=Value(1.0);report.object["synthetic_only"]=Value::flag(true);
    report.object["compiler"]=Value((double)_MSC_VER);report.object["pointer_bytes"]=Value((double)sizeof(void*));
    const int iterations=60,repeats=7;report.object["iterations"]=Value((double)iterations);report.object["repeats"]=Value((double)repeats);
    const char* names[]={"envelope_copy","envelope_transfer","pipeline_copy","pipeline_transfer"};
    for(int kind=0;kind<3;++kind){Value source=fixture(kind);std::string expected=json::dump(source);
        if(json::dump(envelope(source,false))!=json::dump(envelope(source,true))||json::dump(pipeline(source,false))!=json::dump(pipeline(source,true)))throw std::runtime_error("Ownership wire disagreement");
        for(int rep=0;rep<repeats;++rep)for(int order=0;order<4;++order){int op=(order+rep)%4;double started=clockMs();
            for(int i=0;i<iterations;++i){Value result=op<2?envelope(source,op==1):pipeline(source,op==3);
                sink+=result.object.size()+result.at("result").object.size()+result.at("id").str.size();}
            double elapsed=clockMs()-started;Value row=Value::obj();row.object["fixture"]=Value((double)kind);row.object["repetition"]=Value((double)rep);row.object["operation"]=Value(std::string(names[op]));
            row.object["elapsed_ms"]=Value(elapsed);row.object["per_operation_ms"]=Value(elapsed/iterations);row.object["bytes"]=Value((double)expected.size());row.object["fnv1a32"]=Value((double)hash(expected));rows.array.push_back(row);}
    }
    report.object["rows"]=rows;report.object["checksum"]=Value((double)sink);std::cout<<json::dump(report)<<"\n";return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
