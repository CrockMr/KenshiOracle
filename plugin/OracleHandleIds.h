// SPDX-License-Identifier: GPL-3.0-only
#pragma once
#include "OracleFormat.h"
#include <limits.h>

// Engine-independent validation. The wire order is TYPE:C:CS:I:S; the public
// hand constructor takes I:S:TYPE:C:CS instead. Keep those orders explicit.
namespace oracle {
static const size_t maximumSavedHandleIds=128;
static const size_t maximumSavedHandleIdBytes=51;
struct SavedHandleId {
    std::string savedId;
    unsigned int type,container,containerSerial,index,serial;
};
inline SavedHandleId parseSavedHandleId(const std::string& id){
    typedef char UnsignedIntMustBe32Bits[sizeof(unsigned int)==4?1:-1];
    if(id.size()>maximumSavedHandleIdBytes||id.compare(0,5,"hand:")!=0)
        throw Error("invalid_request","saved handle must be hand:TYPE:C:CS:I:S with five uint32 components");
    unsigned int components[5];size_t offset=5;
    for(size_t part=0;part<5;++part){
        size_t first=offset;unsigned int value=0;
        while(offset<id.size()&&id[offset]>='0'&&id[offset]<='9'){
            unsigned int digit=(unsigned int)(id[offset]-'0');
            if(value>(UINT_MAX-digit)/10)throw Error("invalid_request","saved handle component exceeds uint32");
            value=value*10+digit;++offset;
        }
        if(offset==first||(offset-first>1&&id[first]=='0'))throw Error("invalid_request","saved handle components must be canonical unsigned decimal integers");
        components[part]=value;
        if(part<4){if(offset>=id.size()||id[offset]!=':')throw Error("invalid_request","saved handle must contain exactly five uint32 components");++offset;}
        else if(offset!=id.size())throw Error("invalid_request","saved handle must contain exactly five uint32 components");
    }
    // Enums.h itemType: CHARACTER=1 and PLATOON=34. The engine integration also
    // checks these values at compile time against the installed public headers.
    if(components[0]!=1&&components[0]!=34)throw Error("invalid_request","saved handle type must be CHARACTER (1) or PLATOON (34)");
    SavedHandleId out;out.savedId=id;out.type=components[0];out.container=components[1];out.containerSerial=components[2];out.index=components[3];out.serial=components[4];return out;
}
inline std::vector<SavedHandleId> readSavedHandleIds(const json::Value& params){
    const char* allowed[]={"ids"};keys(params,allowed,1);const json::Value& ids=field(params,"ids");
    if(ids.type!=json::Value::ARRAY||ids.array.empty()||ids.array.size()>maximumSavedHandleIds)
        throw Error("invalid_request","ids must contain 1..128 saved handle strings");
    std::vector<SavedHandleId> out;out.reserve(ids.array.size());
    for(size_t i=0;i<ids.array.size();++i){
        if(ids.array[i].type!=json::Value::STRING)throw Error("invalid_request","each saved handle must be a string");
        out.push_back(parseSavedHandleId(ids.array[i].str));
    }
    return out;
}
template<class T> inline std::string loadedPointerId(const std::map<std::string,T*>& loaded,T* candidate){
    // A resolver can return a non-null pointer outside the loaded census. Only
    // compare it for equality; never dereference it or read its handle.
    if(candidate)for(typename std::map<std::string,T*>::const_iterator i=loaded.begin();i!=loaded.end();++i)if(i->second==candidate)return i->first;
    return std::string();
}
inline json::Value savedHandleResolution(const SavedHandleId& saved,bool resolved,const std::string& currentId){
    json::Value row=json::Value::obj();row.object["saved_id"]=json::Value(saved.savedId);row.object["current_id"]=currentId.empty()?json::Value():json::Value(currentId);row.object["loaded"]=json::Value::flag(!currentId.empty());row.object["resolved"]=json::Value::flag(resolved);return row;
}
}
