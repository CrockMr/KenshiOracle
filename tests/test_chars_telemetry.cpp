// SPDX-License-Identifier: GPL-3.0-only
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <iostream>
#include "../plugin/CharsTelemetry.h"
#include "../plugin/NavTelemetry.h"
#include "../plugin/CallTelemetry.h"
static void require(bool ok){if(!ok)throw std::runtime_error("chars telemetry assertion");}
static void reconcile(const CharsBuckets& b){CharsTotals sum=b.overflow;for(int i=0;i<b.size;++i)sum.merge(b.threads[i].totals);
    require(sum.calls==b.total.calls&&sum.callMs==b.total.callMs&&sum.postMs==b.total.postMs&&sum.legacyMs==b.total.legacyMs);}
static CRITICAL_SECTION telemetryLock;static HANDLE held,measure;static volatile LONG originalCalls=0;
static double clockMs(){LARGE_INTEGER f,t;QueryPerformanceFrequency(&f);QueryPerformanceCounter(&t);return 1000.0*t.QuadPart/f.QuadPart;}
static DWORD WINAPI holder(void*){EnterCriticalSection(&telemetryLock);SetEvent(held);WaitForSingleObject(measure,5000);Sleep(20);LeaveCriticalSection(&telemetryLock);return 0;}
struct OldSample{double ms,mainAI,navMs,navMax;unsigned long index,navCalls;NavBuckets navThreads;CallBuckets functionCalls;unsigned long functionNested;};
struct NewSample{double ms,mainAI,navMs,navMax;unsigned long index,navCalls;NavBuckets navThreads;CallBuckets functionCalls;unsigned long functionNested;CharsBuckets charsCalls;};
int main(){try{
    CharsBuckets a;a.record(7,100,10,12,15);a.record(7,100,20,24,25);a.record(7,200,30,31,32);reconcile(a);
    require(a.size==2&&a.total.calls==3&&a.total.callMs==7&&a.total.postMs==5&&a.total.legacyMs==12);
    require(a.total.maxCall==4&&a.total.maxPost==3&&a.total.maxLegacy==5);
    CharsBuckets b;for(int i=0;i<12;++i)b.record(100+i,1000+i,0,1,3);require(b.size==8&&b.overflow.calls==4);reconcile(b);
    a.merge(b);reconcile(a);require(a.total.calls==15&&a.size==8&&a.overflow.calls==6);
    CharsBuckets frozen=a;a=CharsBuckets();require(!a.total.calls&&frozen.total.calls==15);reconcile(frozen);
    CharsHistory* history=new CharsHistory;bool missing=false;try{history->at(1);}catch(const std::runtime_error&){missing=true;}require(missing);
    CharsBuckets historyInput=frozen;history->store(1,historyInput);historyInput.clear();require(!historyInput.total.calls&&history->at(1).total.calls==15);
    history->store(3601,historyInput);missing=false;try{history->at(1);}catch(const std::runtime_error&){missing=true;}require(missing&&history->at(3601).total.calls==0);delete history;
    json::Value data=charsJSON(frozen,5);require(data.at("calls_total").number==15&&data.at("threads_truncated").boolean);
    CharsBuckets unknown;unknown.record(9,0,0,1,1);require(charsJSON(unknown,1).at("threads").array[0].at("created_filetime").type==json::Value::NIL);
    InitializeCriticalSection(&telemetryLock);held=CreateEvent(0,TRUE,FALSE,0);measure=CreateEvent(0,TRUE,FALSE,0);require(held&&measure);
    HANDLE thread=CreateThread(0,0,holder,0,0,0);require(thread&&WaitForSingleObject(held,5000)==WAIT_OBJECT_0);
    double started=clockMs();InterlockedIncrement(&originalCalls);double finished=clockMs();SetEvent(measure);EnterCriticalSection(&telemetryLock);double acquired=clockMs();
    CharsBuckets contention;contention.record(GetCurrentThreadId(),1,started,finished,acquired);LeaveCriticalSection(&telemetryLock);
    require(WaitForSingleObject(thread,5000)==WAIT_OBJECT_0);CloseHandle(thread);CloseHandle(held);CloseHandle(measure);DeleteCriticalSection(&telemetryLock);
    require(originalCalls==1&&contention.total.postMs>=10&&contention.total.legacyMs>=contention.total.postMs);
    require(contention.total.callMs+contention.total.postMs==contention.total.legacyMs);
    json::Value out=json::Value::obj();out.object["contention"]=charsJSON(contention,1);out.object["bucket_bytes"]=json::Value((double)sizeof(CharsBuckets));
    out.object["sample_bytes"]=json::Value((double)sizeof(OldSample));out.object["rejected_embedded_sample_bytes"]=json::Value((double)sizeof(NewSample));
    out.object["history_bytes"]=json::Value((double)sizeof(CharsHistory));
    std::cout<<json::dump(out)<<"\n";return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
