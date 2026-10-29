// SPDX-License-Identifier: GPL-3.0-only
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#define _WIN32_WINNT 0x0601
#include <windows.h>
#include <iostream>
#include <iomanip>
#include <locale>
#include <map>
#include <stdexcept>
typedef unsigned __int64 U64;
struct Cpu {U64 created,user,kernel;};
static U64 ticks(FILETIME f){ULARGE_INTEGER n;n.LowPart=f.dwLowDateTime;n.HighPart=f.dwHighDateTime;return n.QuadPart;}
static Cpu readCpu(){
    FILETIME c,e,k,u;if(!GetThreadTimes(GetCurrentThread(),&c,&e,&k,&u))throw std::runtime_error("GetThreadTimes failed");
    Cpu n={ticks(c),ticks(u),ticks(k)};return n;
}
static U64 gcd(U64 a,U64 b){while(b){U64 r=a%b;a=b;b=r;}return a;}
static double clockMs(){LARGE_INTEGER t,f;QueryPerformanceCounter(&t);QueryPerformanceFrequency(&f);return t.QuadPart*1000.0/f.QuadPart;}
static volatile U64 sink=0;
int main(){try{
    if(_MSC_VER!=1600||sizeof(void*)!=8)throw std::runtime_error("Requires v100 x64");
    std::cout.imbue(std::locale::classic());std::cout<<std::setprecision(17);
    const int iterations=20000,repeats=7;double elapsed[repeats];Cpu first=readCpu();
    for(int r=0;r<repeats;++r){double started=clockMs();
        for(int i=0;i<iterations;++i){Cpu a=readCpu(),b=readCpu();
            if(a.created!=first.created||b.created!=first.created||b.user<a.user||b.kernel<a.kernel)throw std::runtime_error("Counter or lifetime regressed");
            sink+=(b.user-a.user)+(b.kernel-a.kernel);
        }elapsed[r]=clockMs()-started;
    }
    std::map<U64,U64> histogram;U64 samples=0,zeros=0,positive=0,deltaGcd=0,overflow=0;
    Cpu a=readCpu(),last=a;double started=clockMs();
    while(clockMs()-started<500){
        for(int i=0;i<64;++i)sink=sink*1664525+1013904223;
        Cpu b=readCpu();if(b.created!=first.created||b.user<last.user||b.kernel<last.kernel)throw std::runtime_error("Scan counter or lifetime regressed");
        U64 d=(b.user-last.user)+(b.kernel-last.kernel);++samples;
        if(!d)++zeros;else{++positive;deltaGcd=gcd(deltaGcd,d);if(histogram.count(d)||histogram.size()<32)++histogram[d];else ++overflow;}
        last=b;
    }
    double scanWall=clockMs()-started;LARGE_INTEGER frequency;QueryPerformanceFrequency(&frequency);
    std::cout<<"{\"compiler\":"<<_MSC_VER<<",\"pointer_bytes\":"<<sizeof(void*)<<",\"pid\":"<<GetCurrentProcessId()<<",\"tid\":"<<GetCurrentThreadId()
        <<",\"created_filetime\":\""<<first.created<<"\",\"qpc_frequency\":"<<frequency.QuadPart<<",\"iterations\":"<<iterations<<",\"repeats\":"<<repeats<<",\"read_cost\":[";
    for(int r=0;r<repeats;++r){if(r)std::cout<<",";std::cout<<"{\"repeat\":"<<r<<",\"elapsed_ms\":"<<elapsed[r]<<",\"paired_read_mean_us\":"<<elapsed[r]*1000/iterations<<"}";}
    std::cout<<"],\"scan\":{\"wall_ms\":"<<scanWall<<",\"cpu_delta_100ns\":"<<(last.user-a.user)+(last.kernel-a.kernel)<<",\"samples\":"<<samples
        <<",\"zero_deltas\":"<<zeros<<",\"positive_deltas\":"<<positive<<",\"positive_gcd_100ns\":"<<deltaGcd<<",\"histogram_overflow\":"<<overflow<<",\"histogram\":[";
    bool comma=false;for(std::map<U64,U64>::const_iterator i=histogram.begin();i!=histogram.end();++i){if(comma)std::cout<<",";comma=true;std::cout<<"{\"delta_100ns\":"<<i->first<<",\"count\":"<<i->second<<"}";}
    std::cout<<"]},\"sink\":"<<sink<<"}\n";return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
