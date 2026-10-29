// SPDX-License-Identifier: GPL-3.0-only
#pragma once

// Caller supplies thread-local depth. Unwinding must restore it even when the
// original game function throws; only outermost completed calls are timed.
struct CallDepthGuard {
    unsigned int& depth;
    bool outermost;
    explicit CallDepthGuard(unsigned int& value):depth(value),outermost(value++==0){}
    ~CallDepthGuard(){--depth;}
private:
    CallDepthGuard(const CallDepthGuard&);
    CallDepthGuard& operator=(const CallDepthGuard&);
};

struct CallTotals {
    double ms, maximum, userMs, kernelMs;
    unsigned long calls, cpuAvailable;
    CallTotals():ms(0),maximum(0),userMs(0),kernelMs(0),calls(0),cpuAvailable(0){}
    void record(double elapsed,bool cpu,double user,double kernel){
        ms+=elapsed;maximum=std::max(maximum,elapsed);++calls;
        if(cpu){++cpuAvailable;userMs+=user;kernelMs+=kernel;}
    }
    void merge(const CallTotals& other){
        ms+=other.ms;maximum=std::max(maximum,other.maximum);calls+=other.calls;
        userMs+=other.userMs;kernelMs+=other.kernelMs;cpuAvailable+=other.cpuAvailable;
    }
};
struct CallThread {unsigned long id;unsigned __int64 creation;CallTotals totals;CallThread():id(0),creation(0){}};
struct CallBuckets {
    enum {capacity=8};
    CallTotals total,overflow;
    CallThread threads[capacity];
    int size;
    CallBuckets():size(0){}
    void addThread(unsigned long id,unsigned __int64 creation,const CallTotals& totals){
        for(int i=0;i<size;++i)if(threads[i].id==id&&threads[i].creation==creation){threads[i].totals.merge(totals);return;}
        if(size<capacity){threads[size].id=id;threads[size].creation=creation;threads[size].totals=totals;++size;}
        else overflow.merge(totals);
    }
    void record(unsigned long id,double elapsed,bool cpu,double user,double kernel,unsigned __int64 creation=0){
        CallTotals one;one.record(elapsed,cpu,user,kernel);total.merge(one);addThread(id,creation,one);
    }
    void merge(const CallBuckets& other){
        total.merge(other.total);overflow.merge(other.overflow);
        for(int i=0;i<other.size;++i)addThread(other.threads[i].id,other.threads[i].creation,other.threads[i].totals);
    }
};
