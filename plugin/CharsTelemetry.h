// SPDX-License-Identifier: GPL-3.0-only
#pragma once
#include "json.h"
#include <algorithm>

struct CharsTotals {
    unsigned long calls;
    double callMs,postMs,legacyMs,maxCall,maxPost,maxLegacy;
    CharsTotals():calls(0),callMs(0),postMs(0),legacyMs(0),maxCall(0),maxPost(0),maxLegacy(0){}
    void record(double call,double post,double legacy){
        ++calls;callMs+=call;postMs+=post;legacyMs+=legacy;
        maxCall=std::max(maxCall,call);maxPost=std::max(maxPost,post);maxLegacy=std::max(maxLegacy,legacy);
    }
    void merge(const CharsTotals& other){
        calls+=other.calls;callMs+=other.callMs;postMs+=other.postMs;legacyMs+=other.legacyMs;
        maxCall=std::max(maxCall,other.maxCall);maxPost=std::max(maxPost,other.maxPost);maxLegacy=std::max(maxLegacy,other.maxLegacy);
    }
};
struct CharsThread {unsigned long id;unsigned __int64 creation;CharsTotals totals;CharsThread():id(0),creation(0){}};
struct CharsBuckets {
    enum {capacity=8};
    CharsTotals total,overflow;CharsThread threads[capacity];int size;
    CharsBuckets():size(0){}
    void clear(){total=CharsTotals();overflow=CharsTotals();size=0;}
    void addThread(unsigned long id,unsigned __int64 creation,const CharsTotals& totals){
        for(int i=0;i<size;++i)if(threads[i].id==id&&threads[i].creation==creation){threads[i].totals.merge(totals);return;}
        if(size<capacity){threads[size].id=id;threads[size].creation=creation;threads[size].totals=totals;++size;}
        else overflow.merge(totals);
    }
    void record(unsigned long id,unsigned __int64 creation,double started,double finished,double acquired){
        CharsTotals one;one.record(finished-started,acquired-finished,acquired-started);total.merge(one);addThread(id,creation,one);
    }
    void merge(const CharsBuckets& other){
        total.merge(other.total);overflow.merge(other.overflow);
        for(int i=0;i<other.size;++i)addThread(other.threads[i].id,other.threads[i].creation,other.threads[i].totals);
    }
};
// Main service thread owns this fixed history. It avoids enlarging Sample or
// allocating a second deque per frame. Missing tags are errors, never zero calls.
struct CharsHistory {
    enum {capacity=3600};
    CharsBuckets entries[capacity];unsigned long frames[capacity];bool valid[capacity];
    CharsHistory(){for(int i=0;i<capacity;++i){frames[i]=0;valid[i]=false;}}
    void store(unsigned long frame,const CharsBuckets& bucket){int slot=frame%capacity;entries[slot]=bucket;frames[slot]=frame;valid[slot]=true;}
    const CharsBuckets& at(unsigned long frame)const{int slot=frame%capacity;if(!valid[slot]||frames[slot]!=frame)throw std::runtime_error("chars telemetry sample unavailable");return entries[slot];}
};
static const char* charsScope="All completed calls, including nested calls if any; bucket admission at telemetry-lock acquisition. Original-call wall and post-call-to-lock wall are disjoint intervals, not CPU time; post-call includes timer overhead and scheduling, not pure lock contention.";
inline json::Value charsTotalsJSON(const CharsTotals& t,int frames){
    json::Value v=json::Value::obj();
    v.object["calls_total"]=json::Value((double)t.calls);
    v.object["call_wall_total_ms"]=json::Value(t.callMs);v.object["post_call_to_lock_total_ms"]=json::Value(t.postMs);v.object["legacy_total_ms"]=json::Value(t.legacyMs);
    v.object["call_wall_mean_ms"]=json::Value(t.callMs/frames);v.object["post_call_to_lock_mean_ms"]=json::Value(t.postMs/frames);v.object["legacy_mean_ms"]=json::Value(t.legacyMs/frames);
    v.object["max_call_wall_ms"]=json::Value(t.maxCall);v.object["max_post_call_to_lock_ms"]=json::Value(t.maxPost);v.object["max_legacy_ms"]=json::Value(t.maxLegacy);return v;
}
inline json::Value charsJSON(const CharsBuckets& buckets,int frames){
    json::Value v=charsTotalsJSON(buckets.total,frames),rows=json::Value::arr();
    v.object["function"]=json::Value(std::string("GameWorld::charsUpdate"));v.object["scope"]=json::Value(std::string(charsScope));
    v.object["cpu_enabled"]=json::Value::flag(false);v.object["cpu_user_total_ms"]=json::Value();v.object["cpu_kernel_total_ms"]=json::Value();
    v.object["thread_identity_mode"]=json::Value(std::string("tls_creation_once"));v.object["thread_capacity"]=json::Value((double)CharsBuckets::capacity);
    for(int i=0;i<buckets.size;++i){const CharsThread& t=buckets.threads[i];json::Value row=charsTotalsJSON(t.totals,frames);
        row.object["thread_id"]=json::Value((double)t.id);std::ostringstream stamp;stamp.imbue(std::locale::classic());stamp<<t.creation;
        row.object["created_filetime"]=t.creation?json::Value(stamp.str()):json::Value();row.object["identity_verified"]=json::Value::flag(t.creation!=0);rows.array.push_back(row);}
    v.object["threads"]=rows;v.object["unlisted"]=charsTotalsJSON(buckets.overflow,frames);v.object["threads_truncated"]=json::Value::flag(buckets.overflow.calls>0);return v;
}
