// SPDX-License-Identifier: GPL-3.0-only
#pragma once
#include "OracleHandleIds.h"
#include <set>

namespace oracle {
static const size_t maximumSavedOrigins=100000;
class SavedOrigins {
    std::string pendingSave,pendingFingerprint;
    std::vector<SavedHandleId> pendingIds;
    std::set<std::string> pendingUnique,committedUnique;
    void requireToken(const std::string& candidate) const {
        if(token.empty()||candidate!=token)throw Error("origin_context_token_invalid","saved origin registration token is absent or stale");
    }
public:
    bool prepared;
    std::string saveName,sourceFingerprint,token;
    size_t expected;
    std::vector<SavedHandleId> ids;
    std::map<std::string,std::string> currentToSaved,savedToCurrent;
    SavedOrigins():prepared(false),expected(0){}
    void swap(SavedOrigins& other){
        std::swap(prepared,other.prepared);std::swap(expected,other.expected);saveName.swap(other.saveName);sourceFingerprint.swap(other.sourceFingerprint);token.swap(other.token);ids.swap(other.ids);currentToSaved.swap(other.currentToSaved);savedToCurrent.swap(other.savedToCurrent);pendingSave.swap(other.pendingSave);pendingFingerprint.swap(other.pendingFingerprint);pendingIds.swap(other.pendingIds);pendingUnique.swap(other.pendingUnique);committedUnique.swap(other.committedUnique);
    }
    void clear(){
        prepared=false;saveName.clear();sourceFingerprint.clear();token.clear();expected=0;ids.clear();pendingSave.clear();pendingFingerprint.clear();pendingIds.clear();pendingUnique.clear();committedUnique.clear();currentToSaved.clear();savedToCurrent.clear();
    }
    void begin(const std::string& save,const std::string& fingerprint,size_t count,const std::string& newToken){
        if(save.empty()||save.size()>128||save=="."||save==".."||save.find_first_of("<>:\"/\\|?*")!=std::string::npos||save[save.size()-1]=='.'||save[save.size()-1]==' ')
            throw Error("invalid_request","invalid saved origin save_name");
        for(size_t i=0;i<save.size();++i)if((unsigned char)save[i]<32||(unsigned char)save[i]==127)throw Error("invalid_request","invalid saved origin save_name");
        if(fingerprint.size()!=71||fingerprint.compare(0,7,"sha256:")!=0||fingerprint.find_first_not_of("0123456789abcdef",7)!=std::string::npos)
            throw Error("invalid_request","source_fingerprint must be sha256: followed by 64 lowercase hexadecimal digits");
        if(count>maximumSavedOrigins)throw Error("invalid_request","saved origin count exceeds 100000");
        if(newToken.empty()||newToken.size()>200||newToken.find('\0')!=std::string::npos)throw Error("invalid_request","invalid saved origin registration token");
        pendingSave=save;pendingFingerprint=fingerprint;expected=count;token=newToken;pendingIds.clear();pendingUnique.clear();
    }
    void add(const std::string& candidate,const std::vector<SavedHandleId>& chunk){
        requireToken(candidate);
        if(chunk.empty()||chunk.size()>maximumSavedHandleIds||pendingIds.size()+chunk.size()>expected)throw Error("invalid_request","saved origin chunk exceeds registration count or 1..128 limit");
        std::set<std::string> unique;
        // Validate even directly constructed structs; callers cannot smuggle a
        // component value that disagrees with the complete saved ID.
        for(size_t i=0;i<chunk.size();++i){const SavedHandleId parsed=parseSavedHandleId(chunk[i].savedId);
            if(parsed.type!=chunk[i].type||parsed.container!=chunk[i].container||parsed.containerSerial!=chunk[i].containerSerial||parsed.index!=chunk[i].index||parsed.serial!=chunk[i].serial)
                throw Error("invalid_request","saved origin components disagree with the complete ID");
            if(pendingUnique.count(parsed.savedId)||!unique.insert(parsed.savedId).second)throw Error("origin_identity_ambiguous","duplicate complete saved origin ID");
        }
        // No chunk entries become visible until every entry has passed.
        std::vector<SavedHandleId> nextIds=pendingIds;nextIds.insert(nextIds.end(),chunk.begin(),chunk.end());
        std::set<std::string> nextUnique=pendingUnique;nextUnique.insert(unique.begin(),unique.end());pendingIds.swap(nextIds);pendingUnique.swap(nextUnique);
    }
    void commit(const std::string& candidate){
        requireToken(candidate);if(pendingIds.size()!=expected)throw Error("origin_context_incomplete","saved origin registration count is incomplete");
        saveName.swap(pendingSave);sourceFingerprint.swap(pendingFingerprint);ids.swap(pendingIds);committedUnique.swap(pendingUnique);
        currentToSaved.clear();savedToCurrent.clear();prepared=true;token.clear();expected=0;pendingSave.clear();pendingFingerprint.clear();pendingIds.clear();pendingUnique.clear();
    }
    size_t pendingCount() const {return pendingIds.size();}
    void requirePrepared() const {if(!prepared)throw Error("origin_context_required","prepare saved origins for the current loaded save before dump_state");}
    void bind(const std::string& current,const std::string& saved){
        requirePrepared();SavedHandleId currentId=parseSavedHandleId(current),savedId=parseSavedHandleId(saved);
        if(!committedUnique.count(saved)||currentId.type!=savedId.type)throw Error("origin_identity_ambiguous","origin binding has an unregistered ID or mismatched type");
        std::map<std::string,std::string>::const_iterator c=currentToSaved.find(current),s=savedToCurrent.find(saved);
        if((c!=currentToSaved.end()&&c->second!=saved)||(s!=savedToCurrent.end()&&s->second!=current))throw Error("origin_identity_ambiguous","saved origin resolution is not bijective");
        currentToSaved[current]=saved;savedToCurrent[saved]=current;
    }
    std::string canonicalId(const std::string& raw) const {std::map<std::string,std::string>::const_iterator found=currentToSaved.find(raw);return found==currentToSaved.end()?raw:found->second;}
    // A registered saved ID alone is insufficient: the complete current HAND
    // must have a proved binding, including an identity binding raw == saved.
    bool hasSavedOrigin(const std::string& raw) const {return prepared&&currentToSaved.count(raw)!=0;}
    std::string currentId(const std::string& saved) const {std::map<std::string,std::string>::const_iterator found=savedToCurrent.find(saved);return found==savedToCurrent.end()?std::string():found->second;}
    void retainLoaded(const std::set<std::string>& loaded){
        // An old alias is reusable only while that exact complete raw ID is in
        // the current loaded census. No object pointer is retained in the cache.
        std::map<std::string,std::string> nextCurrent,nextSaved;
        for(std::map<std::string,std::string>::const_iterator i=currentToSaved.begin();i!=currentToSaved.end();++i)if(loaded.count(i->first)){nextCurrent.insert(*i);nextSaved[i->second]=i->first;}
        currentToSaved.swap(nextCurrent);savedToCurrent.swap(nextSaved);
    }
};
template<class Proof> inline void commitSavedOriginsWithProof(SavedOrigins& active,const std::string& token,const Proof& prove){
    SavedOrigins candidate=active;candidate.commit(token);prove(candidate);active.swap(candidate);
}
inline std::string canonicalCameraFollowId(const SavedOrigins& origins,const std::string& raw){return origins.prepared?origins.canonicalId(raw):raw;}
class SavedOriginEpoch {
    const void* world;
    std::string requestedSave;
    bool awaitingProbeLoad;
    unsigned long generation;
public:
    SavedOriginEpoch():world(0),awaitingProbeLoad(false),generation(0){}
    unsigned long serial() const {return generation;}
    void invalidate(SavedOrigins& origins){++generation;origins.clear();world=0;requestedSave.clear();awaitingProbeLoad=false;}
    void expectLoad(const std::string& save,SavedOrigins& origins){invalidate(origins);requestedSave=save;awaitingProbeLoad=true;}
    bool acceptsSaveName(const std::string& save) const {return world&&!awaitingProbeLoad&&!requestedSave.empty()&&save==requestedSave;}
    void synchronize(const void* candidate,bool ready,SavedOrigins& origins){
        if(!ready||candidate!=world){
            ++generation;origins.clear();world=ready?candidate:0;
            // Only an explicit probe load carries its requested directory name
            // through the unavailable interval. A later UI transition revokes
            // that source claim, even when the GameWorld address is reused.
            if(!awaitingProbeLoad)requestedSave.clear();
        }
        if(ready)awaitingProbeLoad=false;
    }
};
inline void canonicalizeHandleReference(json::Value& value,const SavedOrigins& origins){if(value.type==json::Value::STRING)value.str=origins.canonicalId(value.str);}
struct OriginRowIdLess {bool operator()(const json::Value& a,const json::Value& b) const {return a.at("id").str<b.at("id").str;}};
struct OriginStringLess {bool operator()(const json::Value& a,const json::Value& b) const {return a.str<b.str;}};
inline void sortOriginRows(json::Value& rows){
    std::sort(rows.array.begin(),rows.array.end(),OriginRowIdLess());
    for(size_t i=1;i<rows.array.size();++i)if(rows.array[i-1].at("id").str==rows.array[i].at("id").str)throw Error("origin_identity_ambiguous","canonical snapshot contains duplicate entity IDs");
}
inline void canonicalizeSnapshotOrigins(json::Value& state,const SavedOrigins& origins){
    origins.requirePrepared();json::Value& characters=state.object["characters"];json::Value& squads=state.object["squads"];
    for(size_t i=0;i<characters.array.size();++i){json::Value& row=characters.array[i];canonicalizeHandleReference(row.object["id"],origins);canonicalizeHandleReference(row.object["squad_id"],origins);
        if(row.object["order"].type==json::Value::OBJECT)canonicalizeHandleReference(row.object["order"].object["target_id"],origins);
    }
    for(size_t i=0;i<squads.array.size();++i){json::Value& row=squads.array[i];canonicalizeHandleReference(row.object["id"],origins);canonicalizeHandleReference(row.object["leader_id"],origins);json::Value& members=row.object["members"];
        for(size_t j=0;j<members.array.size();++j)canonicalizeHandleReference(members.array[j],origins);
        std::sort(members.array.begin(),members.array.end(),OriginStringLess());
        for(size_t j=1;j<members.array.size();++j)if(members.array[j-1].str==members.array[j].str)throw Error("origin_identity_ambiguous","canonical squad contains duplicate member IDs");
    }
    sortOriginRows(characters);sortOriginRows(squads);
}
}
