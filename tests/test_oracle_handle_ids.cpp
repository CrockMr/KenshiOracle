// SPDX-License-Identifier: GPL-3.0-only
#include "../plugin/OracleHandleIds.h"
#include <iostream>
static unsigned int checks=0;
static void require(bool okay){++checks;if(!okay)throw std::runtime_error("saved handle assertion failed");}
static void badId(const std::string& id){bool failed=false;try{oracle::parseSavedHandleId(id);}catch(const oracle::Error& e){failed=e.code=="invalid_request";}require(failed);}
static void badParams(const json::Value& value){bool failed=false;try{oracle::readSavedHandleIds(value);}catch(const oracle::Error& e){failed=e.code=="invalid_request";}require(failed);}
struct OpaqueLoadedObject {};
int main(){try{
    require(_MSC_VER==1600&&sizeof(void*)==8);
    oracle::SavedHandleId character=oracle::parseSavedHandleId("hand:1:372:2911010816:4:3090576128");
    require(character.type==1&&character.container==372&&character.containerSerial==2911010816U&&character.index==4&&character.serial==3090576128U);
    oracle::SavedHandleId platoon=oracle::parseSavedHandleId("hand:34:4294967295:4294967295:4294967295:4294967295");
    require(platoon.type==34&&platoon.container==UINT_MAX&&platoon.containerSerial==UINT_MAX&&platoon.index==UINT_MAX&&platoon.serial==UINT_MAX);
    require(platoon.savedId.size()==oracle::maximumSavedHandleIdBytes);
    require(oracle::parseSavedHandleId("hand:1:0:0:0:0").serial==0);
    const char* invalid[]={"","hand:","HAND:1:2:3:4:5","hand:1:2:3:4","hand:1:2:3:4:5:6","hand:1:2:3:4:5:","hand:1:2:3:4:","hand:1:2:3::5","hand:1:2:3:4:5x","hand:1:2:3:4:5\n"," hand:1:2:3:4:5","hand:1: 2:3:4:5","hand:1:+2:3:4:5","hand:1:-2:3:4:5","hand:1:2.0:3:4:5","hand:1:2e1:3:4:5","hand:01:2:3:4:5","hand:1:02:3:4:5","hand:0:2:3:4:5","hand:2:2:3:4:5","hand:35:2:3:4:5","hand:4294967295:2:3:4:5","hand:4294967296:2:3:4:5","hand:1:4294967296:3:4:5","hand:1:2:4294967296:4:5","hand:1:2:3:4294967296:5","hand:1:2:3:4:4294967296","hand:1:9999999999999999999999999999999999999999999999:3:4:5"};
    for(size_t i=0;i<sizeof(invalid)/sizeof(invalid[0]);++i)badId(invalid[i]);
    badId(std::string("hand:1:2:3:4:5\0",15));badId("hand:1:2:3:4:\xff");
    badParams(json::Value());badParams(json::Value::obj());
    json::Value params=json::Value::obj();params.object["ids"]=json::Value::arr();badParams(params);
    params.object["ids"].array.push_back(json::Value(1.0));badParams(params);
    params.object["ids"].array[0]=json::Value(character.savedId);params.object["extra"]=json::Value();badParams(params);params.object.erase("extra");
    require(oracle::readSavedHandleIds(params).size()==1);
    for(size_t i=1;i<oracle::maximumSavedHandleIds;++i)params.object["ids"].array.push_back(json::Value(platoon.savedId));
    require(oracle::readSavedHandleIds(params).size()==128);
    // A malformed final entry makes the whole parse fail; the caller receives
    // no partial list on which it could begin invoking engine resolvers.
    params.object["ids"].array[127]=json::Value(std::string("hand:1:2:3:4:4294967296"));badParams(params);
    params.object["ids"].array[127]=json::Value(platoon.savedId);params.object["ids"].array.push_back(json::Value(platoon.savedId));badParams(params);
    std::map<std::string,OpaqueLoadedObject*> loaded;OpaqueLoadedObject current,other;loaded["hand:1:12:123:4:3090576128"]=&current;
    require(oracle::loadedPointerId(loaded,&current)=="hand:1:12:123:4:3090576128");
    require(oracle::loadedPointerId(loaded,&other).empty());
    require(oracle::loadedPointerId(loaded,(OpaqueLoadedObject*)0).empty());
    // This address is deliberately not a live object. Membership checks must
    // never dereference a non-null SDK result outside the loaded census.
    require(oracle::loadedPointerId(loaded,reinterpret_cast<OpaqueLoadedObject*>(1)).empty());
    json::Value row=oracle::savedHandleResolution(character,true,oracle::loadedPointerId(loaded,&current));
    require(row.at("saved_id").str==character.savedId&&row.at("current_id").str==loaded.begin()->first&&row.at("loaded").boolean&&row.at("resolved").boolean);
    row=oracle::savedHandleResolution(character,true,std::string());require(row.at("current_id").type==json::Value::NIL&&!row.at("loaded").boolean&&row.at("resolved").boolean);
    row=oracle::savedHandleResolution(character,false,std::string());require(row.at("current_id").type==json::Value::NIL&&!row.at("loaded").boolean&&!row.at("resolved").boolean);
    json::Value response=json::Value::obj();response.object["id"]=json::Value(std::string(64,'x'));response.object["result"]=json::Value::obj();response.object["result"].object["resolutions"]=json::Value::arr();
    for(size_t i=0;i<128;++i)response.object["result"].object["resolutions"].array.push_back(oracle::savedHandleResolution(platoon,true,platoon.savedId));
    require(json::dump(response).size()<32768);
    std::cout<<"{\"passed\":true,\"checks\":"<<checks<<",\"maximum_response_bytes\":"<<json::dump(response).size()<<",\"toolset\":\"v100 x64\"}\n";return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
