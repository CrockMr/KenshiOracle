// SPDX-License-Identifier: GPL-3.0-only
#include <windows.h>
#include <cstring>
#include <iostream>
#include "../plugin/json.h"
typedef json::Value Value;
static void require(bool ok){if(!ok)throw std::runtime_error("JSON ownership assertion");}
static bool equal(const Value& a,const Value& b){
    if(a.type!=b.type||a.boolean!=b.boolean||std::memcmp(&a.number,&b.number,sizeof(double))||a.str!=b.str||a.object.size()!=b.object.size()||a.array.size()!=b.array.size())return false;
    std::map<std::string,Value>::const_iterator i=a.object.begin(),j=b.object.begin();
    for(;i!=a.object.end();++i,++j)if(i->first!=j->first||!equal(i->second,j->second))return false;
    for(size_t k=0;k<a.array.size();++k)if(!equal(a.array[k],b.array[k]))return false;return true;
}
static Value value(int type,int tag){
    Value v;v.type=(Value::Type)type;v.boolean=tag%2!=0;v.number=tag?123.5:-0.0;
    v.str=std::string("inactive\0payload",16);v.str+=(char)tag;
    v.object["inactive\nkey"]=Value((double)tag);v.array.push_back(Value(std::string("\xc3\xa9\xf0\x9f\x98\x80")));return v;
}
struct Work{Value response;HANDLE done,gate;Work():done(CreateEvent(0,TRUE,FALSE,0)),gate(CreateEvent(0,TRUE,FALSE,0)){require(done!=0&&gate!=0);}~Work(){CloseHandle(done);CloseHandle(gate);}};
static DWORD WINAPI service(void* context){Work* w=(Work*)context;if(WaitForSingleObject(w->gate,5000)!=WAIT_OBJECT_0)return 1;Value result=value(Value::OBJECT,3);w->response.swap(result);SetEvent(w->done);return 0;}
int main(){try{
    for(int a=0;a<6;++a)for(int b=0;b<6;++b){Value x=value(a,a),y=value(b,b+1),oldX=x,oldY=y;
        x.swap(y);require(equal(x,oldY)&&equal(y,oldX));x.swap(x);require(equal(x,oldY));
        x.swap(y);require(equal(x,oldX)&&equal(y,oldY));}
    // A result moved into an envelope leaves only a default, harmless local.
    Value payload=value(Value::OBJECT,1),original=payload,envelope=Value::obj();
    envelope.object["id"]=Value(std::string("id-\xc3\xa9-\"-\\"));envelope.object["result"].swap(payload);
    require(equal(envelope.at("result"),original)&&equal(payload,Value()));
    Value hidden=value(Value::NIL,0),other=value(Value::BOOL,2);unsigned __int64 nanBits=0x7ff8000000000123ui64;
    std::memcpy(&hidden.number,&nanBits,sizeof(double));Value oldHidden=hidden,oldOther=other;
    hidden.swap(other);require(equal(hidden,oldOther)&&equal(other,oldHidden));
    for(int i=0;i<200;++i){Work w;HANDLE thread=CreateThread(0,0,service,&w,0,0);require(thread!=0);SetEvent(w.gate);
        require(WaitForSingleObject(w.done,5000)==WAIT_OBJECT_0);Value reply;reply.swap(w.response);
        require(equal(reply,value(Value::OBJECT,3))&&equal(w.response,Value()));
        require(WaitForSingleObject(thread,5000)==WAIT_OBJECT_0);CloseHandle(thread);}
    {Work w;HANDLE thread=CreateThread(0,0,service,&w,0,0);require(thread!=0);Value consumer;
        require(WaitForSingleObject(w.done,0)==WAIT_TIMEOUT);SetEvent(w.gate);
        require(WaitForSingleObject(thread,5000)==WAIT_OBJECT_0);CloseHandle(thread);
        require(equal(consumer,Value())&&equal(w.response,value(Value::OBJECT,3)));}
    std::cout<<"JSON ownership, hidden payload, self-swap and signaled handoff checks passed (v100 x64)\n";return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
