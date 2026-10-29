// SPDX-License-Identifier: GPL-3.0-only
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <iostream>
#include "../plugin/CharsTelemetry.h"
#include "../plugin/ThreadIdentity.h"
static LARGE_INTEGER frequency;static CRITICAL_SECTION lock;static volatile unsigned long calls=0;
static ThreadIdentityState identity={0,0};static CharsBuckets bucket;static double legacy=0;
static double clockMs(){LARGE_INTEGER t;QueryPerformanceCounter(&t);return 1000.0*t.QuadPart/frequency.QuadPart;}
static bool creation(unsigned __int64& result){FILETIME c,e,k,u;if(!GetThreadTimes(GetCurrentThread(),&c,&e,&k,&u))return false;ULARGE_INTEGER t;t.LowPart=c.dwLowDateTime;t.HighPart=c.dwHighDateTime;result=t.QuadPart;return true;}
static void original(){++calls;}
int main(){try{
    QueryPerformanceFrequency(&frequency);InitializeCriticalSection(&lock);cachedThreadCreation(identity,creation);
    json::Value out=json::Value::obj(),rows=json::Value::arr();const int iterations=100000,repeats=7;
    for(int rep=0;rep<repeats;++rep)for(int order=0;order<2;++order){int mode=(rep+order)%2;bucket=CharsBuckets();legacy=0;double start=clockMs();
        for(int i=0;i<iterations;++i){
            if(!mode){double t=clockMs();original();EnterCriticalSection(&lock);legacy+=clockMs()-t;LeaveCriticalSection(&lock);}
            else{DWORD thread=GetCurrentThreadId();unsigned __int64 stamp=cachedThreadCreation(identity,creation);double t=clockMs();original();double end=clockMs();EnterCriticalSection(&lock);double acquired=clockMs();legacy+=acquired-t;bucket.record(thread,stamp,t,end,acquired);LeaveCriticalSection(&lock);}
        }
        double elapsed=clockMs()-start;json::Value row=json::Value::obj();row.object["repetition"]=json::Value((double)rep);row.object["mode"]=json::Value(std::string(mode?"split":"legacy"));
        row.object["elapsed_ms"]=json::Value(elapsed);row.object["per_call_us"]=json::Value(elapsed*1000/iterations);row.object["legacy_ms"]=json::Value(legacy);row.object["bucket_calls"]=json::Value((double)bucket.total.calls);rows.array.push_back(row);
    }
    DeleteCriticalSection(&lock);out.object["rows"]=rows;out.object["calls"]=json::Value((double)calls);out.object["iterations"]=json::Value((double)iterations);out.object["repeats"]=json::Value((double)repeats);
    out.object["compiler"]=json::Value((double)_MSC_VER);out.object["pointer_bytes"]=json::Value((double)sizeof(void*));out.object["bucket_bytes"]=json::Value((double)sizeof(CharsBuckets));out.object["synthetic_only"]=json::Value::flag(true);
    std::cout<<json::dump(out)<<"\n";return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
