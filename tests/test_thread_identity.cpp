// SPDX-License-Identifier: GPL-3.0-only
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#define _WIN32_WINNT 0x0601
#include <windows.h>
#include <algorithm>
#include <iostream>
#include <stdexcept>
#include "../plugin/ThreadIdentity.h"
#include "../plugin/CallTelemetry.h"

static void require(bool ok){if(!ok)throw std::runtime_error("thread identity assertion");}
static unsigned int fakeReads=0;
static bool success(unsigned __int64& v){++fakeReads;v=123;return true;}
static bool failure(unsigned __int64& v){++fakeReads;v=999;return false;}
static bool zero(unsigned __int64& v){++fakeReads;v=0;return true;}
__declspec(thread) static ThreadIdentityState identity={0,0};
__declspec(thread) static unsigned int realReads=0;
static bool realCreation(unsigned __int64& value){
    ++realReads;FILETIME c,e,k,u;
    if(!GetThreadTimes(GetCurrentThread(),&c,&e,&k,&u))return false;
    ULARGE_INTEGER n;n.LowPart=c.dwLowDateTime;n.HighPart=c.dwHighDateTime;value=n.QuadPart;return true;
}
static DWORD WINAPI worker(void*){
    if(identity.attempted||identity.creation||realReads)return 1;
    unsigned __int64 first=cachedThreadCreation(identity,realCreation);
    if(!first)return 2;
    for(int i=0;i<10000;++i)if(cachedThreadCreation(identity,realCreation)!=first)return 3;
    if(realReads!=1)return 4;
    FILETIME c,e,k,u;if(!GetThreadTimes(GetCurrentThread(),&c,&e,&k,&u))return 5;
    ULARGE_INTEGER n;n.LowPart=c.dwLowDateTime;n.HighPart=c.dwHighDateTime;
    if(n.QuadPart!=first)return 6;
    // Disabled CPU preserves identity, with every call unavailable rather than zero measured.
    CallBuckets b;b.record(GetCurrentThreadId(),1,false,0,0,first);
    if(b.size!=1||b.threads[0].creation!=first||b.total.cpuAvailable||b.total.calls!=1)return 7;
    return 0;
}
int main(){try{
    ThreadIdentityState known={0,0};
    for(int i=0;i<10000;++i)require(cachedThreadCreation(known,success)==123);
    require(fakeReads==1&&known.attempted==1);
    ThreadIdentityState unknown={0,0};require(cachedThreadCreation(unknown,failure)==0);
    require(cachedThreadCreation(unknown,success)==0&&fakeReads==2);
    ThreadIdentityState invalid={0,0};require(cachedThreadCreation(invalid,zero)==0);
    require(cachedThreadCreation(invalid,success)==0&&fakeReads==3);
    require(cachedThreadCreation(identity,realCreation)>0&&realReads==1);
    // Two generations; new threads must not inherit their predecessor's TLS state.
    for(int generation=0;generation<2;++generation){
        HANDLE handles[4];for(int i=0;i<4;++i){handles[i]=CreateThread(0,0,worker,0,0,0);require(handles[i]!=0);}
        require(WaitForMultipleObjects(4,handles,TRUE,10000)==WAIT_OBJECT_0);
        for(int i=0;i<4;++i){DWORD result=99;require(GetExitCodeThread(handles[i],&result)&&result==0);CloseHandle(handles[i]);}
    }
    require(realReads==1&&cachedThreadCreation(identity,realCreation)>0&&realReads==1);
    std::cout<<"TLS creation: one read/lifetime, failures unknown, new threads isolated, CPU-off identity retained (v100 x64)\n";
    return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
