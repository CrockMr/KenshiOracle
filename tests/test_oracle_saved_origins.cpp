// SPDX-License-Identifier: GPL-3.0-only
#include "../plugin/OracleSavedOrigins.h"
#include <iostream>

static unsigned int checks=0;
static void require(bool okay){++checks;if(!okay)throw std::runtime_error("saved origins assertion failed");}
static const std::string fingerprint="sha256:"+std::string(64,'a');
static std::vector<oracle::SavedHandleId> ids(const char* first,const char* second=0){
    std::vector<oracle::SavedHandleId> out;if(first)out.push_back(oracle::parseSavedHandleId(first));if(second)out.push_back(oracle::parseSavedHandleId(second));return out;
}
static void badBegin(oracle::SavedOrigins& registry,const std::string& save,const std::string& source,size_t count){
    bool failed=false;try{registry.begin(save,source,count,"bad-begin");}catch(const oracle::Error&){failed=true;}require(failed);
}
static void badAdd(oracle::SavedOrigins& registry,const std::string& token,const std::vector<oracle::SavedHandleId>& chunk){
    bool failed=false;try{registry.add(token,chunk);}catch(const oracle::Error&){failed=true;}require(failed);
}
static void badCommit(oracle::SavedOrigins& registry,const std::string& token){
    bool failed=false;try{registry.commit(token);}catch(const oracle::Error&){failed=true;}require(failed);
}
static void badBind(oracle::SavedOrigins& registry,const std::string& current,const std::string& saved){
    std::map<std::string,std::string> forward=registry.currentToSaved,reverse=registry.savedToCurrent;
    bool failed=false;try{registry.bind(current,saved);}catch(const oracle::Error& e){failed=e.code=="origin_identity_ambiguous";}require(failed);
    require(registry.currentToSaved==forward&&registry.savedToCurrent==reverse);
}
struct FixtureCommitProof {
    bool ambiguous;
    int* calls;
    void operator()(oracle::SavedOrigins& candidate) const {
        ++*calls;require(candidate.prepared&&candidate.ids.size()==2&&candidate.token.empty());
        candidate.bind("hand:1:12:101:4:3090576128",candidate.ids[0].savedId);
        candidate.bind(ambiguous?"hand:1:12:101:4:3090576128":"hand:1:6:102:5:1865356416",candidate.ids[1].savedId);
    }
};
static void commitFollowChecks(){
    const char* savedA="hand:1:372:2911010816:4:3090576128";const char* savedB="hand:1:373:2914428672:5:1865356416";
    const std::string oldRaw="hand:1:9:99:4:3090576128",newRaw="hand:1:12:101:4:3090576128",newRawB="hand:1:6:102:5:1865356416",unmatched="hand:1:999:999:1:999";
    oracle::SavedOrigins active;require(oracle::canonicalCameraFollowId(active,oldRaw)==oldRaw);
    active.begin("old",fingerprint,1,"old-token");active.add("old-token",ids(savedA));active.commit("old-token");active.bind(oldRaw,savedA);
    active.begin("replacement",fingerprint,2,"replacement-token");active.add("replacement-token",ids(savedA,savedB));
    require(oracle::canonicalCameraFollowId(active,oldRaw)==savedA&&oracle::canonicalCameraFollowId(active,newRaw)==newRaw);
    int calls=0;FixtureCommitProof rejected={true,&calls};bool failed=false;
    try{oracle::commitSavedOriginsWithProof(active,"replacement-token",rejected);}catch(const oracle::Error& e){failed=e.code=="origin_identity_ambiguous";}require(failed&&calls==1);
    // Neither the previous active cache nor the full pending registration may
    // change when two saved origins resolve to one current loaded object.
    require(active.prepared&&active.saveName=="old"&&active.ids.size()==1&&active.currentId(savedA)==oldRaw);
    require(active.token=="replacement-token"&&active.pendingCount()==2&&active.expected==2);
    require(active.currentId(savedB).empty()&&oracle::canonicalCameraFollowId(active,newRaw)==newRaw);
    FixtureCommitProof accepted={false,&calls};failed=false;
    try{oracle::commitSavedOriginsWithProof(active,"stale-token",accepted);}catch(const oracle::Error& e){failed=e.code=="origin_context_token_invalid";}require(failed&&calls==1&&active.token=="replacement-token");
    oracle::commitSavedOriginsWithProof(active,"replacement-token",accepted);
    require(calls==2&&active.prepared&&active.saveName=="replacement"&&active.ids.size()==2&&active.token.empty());
    // No snapshot has run: commit itself must make canonical follows usable
    // immediately, so the scenario guard never captures an obsolete raw CS.
    require(oracle::canonicalCameraFollowId(active,newRaw)==savedA&&oracle::canonicalCameraFollowId(active,newRawB)==savedB);
    require(oracle::canonicalCameraFollowId(active,oldRaw)==oldRaw&&oracle::canonicalCameraFollowId(active,unmatched)==unmatched);
    require(oracle::canonicalCameraFollowId(active,std::string()).empty());
    active.clear();require(oracle::canonicalCameraFollowId(active,newRaw)==newRaw);
}
static json::Value fixtureCharacter(const std::string& id,const std::string& squad,const std::string& target){
    json::Value row=json::Value::obj();row.object["id"]=json::Value(id);row.object["squad_id"]=json::Value(squad);
    row.object["race_id"]=json::Value(std::string("hand:1:9:101:4:3090576128"));row.object["faction_id"]=row.object["race_id"];
    row.object["health"]=json::Parser("[{\"id\":\"hand:1:9:101:4:3090576128\",\"current\":12}]").parse();
    row.object["order"]=json::Value::obj();row.object["order"].object["type"]=json::Value(std::string("attack"));row.object["order"].object["target_id"]=target.empty()?json::Value():json::Value(target);return row;
}
static json::Value fixtureSquad(const std::string& id,const std::string& leader,const std::vector<std::string>& members){
    json::Value row=json::Value::obj();row.object["id"]=json::Value(id);row.object["leader_id"]=leader.empty()?json::Value():json::Value(leader);row.object["faction_id"]=json::Value(std::string("hand:1:9:101:4:3090576128"));
    row.object["members"]=json::Value::arr();for(size_t i=0;i<members.size();++i)row.object["members"].array.push_back(json::Value(members[i]));return row;
}
static void badSnapshot(json::Value snapshot,const oracle::SavedOrigins& registry){
    bool failed=false;try{oracle::canonicalizeSnapshotOrigins(snapshot,registry);}catch(const oracle::Error& e){failed=e.code=="origin_identity_ambiguous";}require(failed);
}
static void snapshotChecks(){
    const std::string savedA="hand:1:372:2911010816:4:3090576128",savedB="hand:1:373:2914428672:5:1865356416";
    const std::string rawA="hand:1:9:101:4:3090576128",rawB="hand:1:1:102:5:1865356416",runtimeOnly="hand:1:999:999:9:999";
    const std::string squadA="hand:34:372:2911010816:0:0",squadB="hand:34:373:2914428672:0:0",rawSquadA="hand:34:9:101:0:0",rawSquadB="hand:34:1:102:0:0";
    oracle::SavedOrigins registry;registry.begin("fixture",fingerprint,4,"fixture-token");registry.add("fixture-token",ids(savedA.c_str(),savedB.c_str()));registry.add("fixture-token",ids(squadA.c_str(),squadB.c_str()));registry.commit("fixture-token");
    registry.bind(rawA,savedA);registry.bind(rawB,savedB);registry.bind(rawSquadA,squadA);registry.bind(rawSquadB,squadB);
    json::Value snapshot=json::Value::obj();snapshot.object["characters"]=json::Value::arr();snapshot.object["squads"]=json::Value::arr();
    snapshot.object["characters"].array.push_back(fixtureCharacter(rawB,rawSquadB,std::string()));snapshot.object["characters"].array.push_back(fixtureCharacter(rawA,rawSquadA,rawB));snapshot.object["characters"].array.push_back(fixtureCharacter(runtimeOnly,rawSquadA,runtimeOnly));
    std::vector<std::string> members;members.push_back(rawB);members.push_back(rawA);
    snapshot.object["squads"].array.push_back(fixtureSquad(rawSquadB,std::string(),std::vector<std::string>()));snapshot.object["squads"].array.push_back(fixtureSquad(rawSquadA,rawA,members));
    snapshot.object["factions"]=json::Parser("[{\"id\":\"hand:1:9:101:4:3090576128\",\"name\":\"unchanged\"}]").parse();
    snapshot.object["relations"]=json::Parser("[{\"source_id\":\"hand:1:9:101:4:3090576128\",\"target_id\":\"hand:34:9:101:0:0\",\"value\":-20}]").parse();
    std::string unchangedFactions=oracle::canonical(snapshot.at("factions")),unchangedRelations=oracle::canonical(snapshot.at("relations"));
    std::string unchangedHealth=oracle::canonical(snapshot.at("characters").array[1].at("health"));
    json::Value permutation=snapshot;std::reverse(permutation.object["characters"].array.begin(),permutation.object["characters"].array.end());std::reverse(permutation.object["squads"].array.begin(),permutation.object["squads"].array.end());std::reverse(permutation.object["squads"].array[0].object["members"].array.begin(),permutation.object["squads"].array[0].object["members"].array.end());
    oracle::canonicalizeSnapshotOrigins(snapshot,registry);oracle::canonicalizeSnapshotOrigins(permutation,registry);
    require(oracle::canonical(snapshot)==oracle::canonical(permutation));
    const std::vector<json::Value>& characters=snapshot.at("characters").array;const std::vector<json::Value>& squads=snapshot.at("squads").array;
    require(characters[0].at("id").str==savedA&&characters[1].at("id").str==savedB&&characters[2].at("id").str==runtimeOnly);
    require(characters[0].at("squad_id").str==squadA&&characters[1].at("squad_id").str==squadB);
    require(characters[0].at("order").at("target_id").str==savedB&&characters[1].at("order").at("target_id").type==json::Value::NIL&&characters[2].at("order").at("target_id").str==runtimeOnly);
    require(squads[0].at("id").str==squadA&&squads[1].at("id").str==squadB&&squads[0].at("leader_id").str==savedA&&squads[1].at("leader_id").type==json::Value::NIL);
    require(squads[0].at("members").array[0].str==savedA&&squads[0].at("members").array[1].str==savedB);
    require(characters[0].at("race_id").str==rawA&&characters[0].at("faction_id").str==rawA&&squads[0].at("faction_id").str==rawA);
    require(oracle::canonical(characters[0].at("health"))==unchangedHealth&&oracle::canonical(snapshot.at("factions"))==unchangedFactions&&oracle::canonical(snapshot.at("relations"))==unchangedRelations);
    std::string once=oracle::canonical(snapshot);oracle::canonicalizeSnapshotOrigins(snapshot,registry);require(oracle::canonical(snapshot)==once);
    json::Value duplicate=snapshot;duplicate.object["characters"].array.push_back(fixtureCharacter(rawA,rawSquadA,rawB));badSnapshot(duplicate,registry);
    duplicate=snapshot;duplicate.object["squads"].array.push_back(fixtureSquad(rawSquadA,rawA,members));badSnapshot(duplicate,registry);
    duplicate=snapshot;duplicate.object["squads"].array[0].object["members"].array.push_back(json::Value(rawA));badSnapshot(duplicate,registry);
    std::set<std::string> loaded;loaded.insert(rawA);loaded.insert(rawSquadA);registry.retainLoaded(loaded);
    require(registry.currentId(savedA)==rawA&&registry.canonicalId(rawA)==savedA&&registry.currentId(squadA)==rawSquadA);
    require(registry.currentId(savedB).empty()&&registry.canonicalId(rawB)==rawB&&registry.currentId(squadB).empty());
    loaded.clear();registry.retainLoaded(loaded);require(registry.currentToSaved.empty()&&registry.savedToCurrent.empty());
    // Reused index/serial and a different full raw handle cannot inherit the
    // pruned alias. A later explicit resolver proof may bind a new full handle.
    require(registry.canonicalId("hand:1:10:101:4:3090576128")=="hand:1:10:101:4:3090576128");registry.bind("hand:1:10:101:4:3090576128",savedA);require(registry.currentId(savedA)=="hand:1:10:101:4:3090576128");
    badBind(registry,rawA,"hand:34:372:2911010816:0:0");badBind(registry,rawB,"hand:1:1000:1000:1:1");
}
static void identityOriginChecks(){
    const char* saved="hand:1:7:100:1:200";
    const char* replacement="hand:1:7:100:2:201";
    const char* current="hand:1:18:300:2:201";
    oracle::SavedOrigins origins;
    require(!origins.hasSavedOrigin(saved));
    origins.begin("identity-origin",fingerprint,1,"first");origins.add("first",ids(saved));
    require(!origins.hasSavedOrigin(saved)); // A pending manifest is not proof.
    origins.commit("first");
    require(!origins.hasSavedOrigin(saved)); // Registered but unresolved remains unknown.
    origins.bind(saved,saved);
    require(origins.hasSavedOrigin(saved)); // Equal raw/saved HAND still has proof.
    require(!origins.hasSavedOrigin(replacement));
    origins.begin("replacement-origin",fingerprint,1,"second");origins.add("second",ids(replacement));
    require(origins.hasSavedOrigin(saved)); // Atomic replacement keeps the old active proof.
    require(!origins.hasSavedOrigin(replacement));
    origins.commit("second");
    require(!origins.hasSavedOrigin(saved)&&!origins.hasSavedOrigin(replacement));
    origins.bind(current,replacement);
    require(origins.hasSavedOrigin(current));
    require(!origins.hasSavedOrigin(replacement)); // Do not confuse the saved key with its current alias.
    std::set<std::string> loaded;loaded.insert(saved);origins.retainLoaded(loaded);
    require(!origins.hasSavedOrigin(current)); // A departed exact HAND loses its proof.
    origins.bind(current,replacement);origins.clear();
    require(!origins.hasSavedOrigin(current)&&!origins.hasSavedOrigin(replacement));
}
int main(){try{
    require(_MSC_VER==1600&&sizeof(void*)==8);
    const char* savedA="hand:1:372:2911010816:4:3090576128";
    const char* savedB="hand:1:373:2914428672:5:1865356416";
    const char* savedC="hand:1:374:3821533184:6:2201171968";
    const char* savedSquad="hand:34:372:2911010816:0:0";
    const char* currentA="hand:1:12:1234567890:4:3090576128";
    const char* currentB="hand:1:6:2234567890:5:1865356416";
    oracle::SavedOrigins registry;
    require(!registry.prepared&&registry.ids.empty()&&registry.currentToSaved.empty()&&registry.savedToCurrent.empty());
    require(registry.canonicalId(currentA)==currentA&&registry.currentId(savedA).empty());
    badAdd(registry,"absent",ids(savedA));badCommit(registry,"absent");
    badBegin(registry,"",fingerprint,1);badBegin(registry,"../save",fingerprint,1);badBegin(registry,"a/b",fingerprint,1);badBegin(registry,"a\\b",fingerprint,1);badBegin(registry,"a:save",fingerprint,1);badBegin(registry,".",fingerprint,1);badBegin(registry,"..",fingerprint,1);badBegin(registry,std::string(129,'s'),fingerprint,1);
    badBegin(registry,"save","",1);badBegin(registry,"save",std::string(64,'a'),1);badBegin(registry,"save","sha256:"+std::string(64,'A'),1);badBegin(registry,"save","sha256:"+std::string(64,'g'),1);badBegin(registry,"save","sha256:"+std::string(63,'a'),1);badBegin(registry,"save",fingerprint,100001);
    require(!registry.prepared&&registry.ids.empty());
    registry.begin("KenshiProbe_test",fingerprint,3,"first");
    require(!registry.prepared&&registry.ids.empty());
    badAdd(registry,"other-token",ids(savedA));badCommit(registry,"other-token");badCommit(registry,"first");
    registry.add("first",ids(savedA,savedB));
    badCommit(registry,"first");
    // The new ID in this chunk must not survive rejection of its duplicate.
    badAdd(registry,"first",ids(savedC,savedA));
    registry.add("first",ids(savedSquad));registry.commit("first");
    require(registry.prepared&&registry.saveName=="KenshiProbe_test"&&registry.sourceFingerprint==fingerprint&&registry.ids.size()==3);
    std::map<std::string,bool> committed;for(size_t i=0;i<registry.ids.size();++i)committed[registry.ids[i].savedId]=true;
    require(committed.count(savedA)==1&&committed.count(savedB)==1&&committed.count(savedSquad)==1&&committed.count(savedC)==0);
    badAdd(registry,"first",ids(savedC));badCommit(registry,"first");
    registry.bind(currentA,savedA);registry.bind(currentB,savedB);registry.bind(savedSquad,savedSquad);
    require(registry.canonicalId(currentA)==savedA&&registry.canonicalId(currentB)==savedB&&registry.canonicalId(savedSquad)==savedSquad);
    require(registry.currentId(savedA)==currentA&&registry.currentId(savedB)==currentB);
    require(registry.canonicalId(savedC)==savedC&&registry.currentId(savedC).empty());
    // Repeating an already proved pair is harmless. Neither direction can be
    // rebound while aliases from this world epoch remain in the cache.
    registry.bind(currentA,savedA);require(registry.currentToSaved.size()==3&&registry.savedToCurrent.size()==3);
    badBind(registry,currentA,savedB);badBind(registry,currentB,savedA);
    badBind(registry,"hand:1:99:99:4:3090576128",savedA);
    registry.begin("next-save","sha256:"+std::string(64,'b'),2,"replacement");
    require(registry.prepared&&registry.saveName=="KenshiProbe_test"&&registry.ids.size()==3&&registry.canonicalId(currentA)==savedA);
    registry.add("replacement",ids(savedC));badCommit(registry,"replacement");
    require(registry.prepared&&registry.saveName=="KenshiProbe_test"&&registry.ids.size()==3&&registry.currentId(savedA)==currentA);
    registry.add("replacement",ids(savedSquad));registry.commit("replacement");
    require(registry.prepared&&registry.saveName=="next-save"&&registry.sourceFingerprint=="sha256:"+std::string(64,'b')&&registry.ids.size()==2);
    require(registry.currentToSaved.empty()&&registry.savedToCurrent.empty()&&registry.canonicalId(currentA)==currentA&&registry.currentId(savedA).empty());
    // Duplicate IDs inside a chunk reject the entire chunk too. Empty chunks
    // are unnecessary; an empty manifest itself is a valid committed context.
    registry.begin("duplicate",fingerprint,2,"duplicate-token");badAdd(registry,"duplicate-token",ids(savedA,savedA));registry.add("duplicate-token",ids(savedA,savedB));registry.commit("duplicate-token");
    require(registry.ids.size()==2);
    registry.begin("empty",fingerprint,0,"empty-token");registry.commit("empty-token");require(registry.prepared&&registry.saveName=="empty"&&registry.ids.empty());
    registry.begin("chunk-limit",fingerprint,129,"chunk-token");
    std::vector<oracle::SavedHandleId> excessive;for(unsigned int i=0;i<129;++i){std::ostringstream value;value<<"hand:1:1:2:"<<i<<":3";excessive.push_back(oracle::parseSavedHandleId(value.str()));}
    badAdd(registry,"chunk-token",excessive);excessive.pop_back();registry.add("chunk-token",excessive);registry.add("chunk-token",ids("hand:1:1:2:128:3"));registry.commit("chunk-token");require(registry.ids.size()==129);
    registry.begin("count-budget",fingerprint,1,"budget-token");badAdd(registry,"budget-token",ids(savedA,savedB));registry.add("budget-token",ids(savedA));registry.commit("budget-token");require(registry.ids.size()==1&&registry.ids[0].savedId==savedA);
    registry.bind(currentA,savedA);registry.begin("in-flight",fingerprint,1,"pending-on-reset");registry.add("pending-on-reset",ids(savedB));registry.clear();
    require(!registry.prepared&&registry.ids.empty()&&registry.currentToSaved.empty()&&registry.savedToCurrent.empty());
    require(registry.saveName.empty()&&registry.sourceFingerprint.empty()&&registry.canonicalId(currentA)==currentA&&registry.currentId(savedA).empty());
    badCommit(registry,"pending-on-reset");badAdd(registry,"pending-on-reset",ids(savedB));
    registry.clear();require(!registry.prepared&&registry.ids.empty());
    registry.begin("maximum-count",fingerprint,100000,"maximum-token");registry.clear();require(!registry.prepared);
    int firstWorld=0,secondWorld=0;oracle::SavedOriginEpoch epoch;
    epoch.synchronize(&firstWorld,true,registry);registry.begin("epoch-save",fingerprint,1,"epoch-active");registry.add("epoch-active",ids(savedA));registry.commit("epoch-active");registry.bind(currentA,savedA);
    registry.begin("epoch-save",fingerprint,1,"epoch-pending");registry.add("epoch-pending",ids(savedB));
    epoch.synchronize(&firstWorld,true,registry);require(registry.prepared&&registry.currentId(savedA)==currentA&&registry.pendingCount()==1);
    epoch.synchronize(&firstWorld,false,registry);require(!registry.prepared&&registry.ids.empty()&&registry.pendingCount()==0&&registry.currentToSaved.empty());badCommit(registry,"epoch-pending");
    epoch.synchronize(&firstWorld,true,registry);registry.begin("first-world",fingerprint,1,"first-world-token");registry.add("first-world-token",ids(savedA));registry.commit("first-world-token");registry.bind(currentA,savedA);
    epoch.synchronize(&secondWorld,true,registry);require(!registry.prepared&&registry.ids.empty()&&registry.currentToSaved.empty());
    registry.begin("second-world",fingerprint,1,"second-world-token");registry.add("second-world-token",ids(savedB));registry.commit("second-world-token");
    epoch.invalidate(registry);require(!registry.prepared&&registry.saveName.empty()&&registry.ids.empty());
    epoch.synchronize(&secondWorld,true,registry);registry.begin("explicit-reset",fingerprint,0,"explicit-reset-token");registry.commit("explicit-reset-token");epoch.invalidate(registry);epoch.synchronize(&secondWorld,true,registry);require(!registry.prepared);
    // Source directory names come exclusively from an explicit probe load.
    // The serialized game's internal name (often autosave1) is irrelevant.
    epoch.expectLoad("KenshiProbe_test",registry);require(!epoch.acceptsSaveName("KenshiProbe_test"));
    epoch.synchronize(&firstWorld,false,registry);epoch.synchronize(0,false,registry);require(!epoch.acceptsSaveName("KenshiProbe_test"));
    epoch.synchronize(&firstWorld,true,registry);require(epoch.acceptsSaveName("KenshiProbe_test")&&!epoch.acceptsSaveName("autosave1"));
    registry.begin("KenshiProbe_test",fingerprint,0,"directory-source");registry.commit("directory-source");epoch.synchronize(&firstWorld,true,registry);require(registry.prepared&&epoch.acceptsSaveName("KenshiProbe_test"));
    // An unrequested UI reload invalidates the old source claim permanently;
    // returning to the same GameWorld address cannot make it eligible again.
    epoch.synchronize(&firstWorld,false,registry);epoch.synchronize(&firstWorld,true,registry);require(!registry.prepared&&!epoch.acceptsSaveName("KenshiProbe_test"));
    epoch.expectLoad("ville-calme",registry);epoch.synchronize(&secondWorld,true,registry);require(epoch.acceptsSaveName("ville-calme")&&!epoch.acceptsSaveName("KenshiProbe_test"));
    epoch.synchronize(&firstWorld,true,registry);require(!epoch.acceptsSaveName("ville-calme"));
    epoch.expectLoad("KenshiProbe_test",registry);epoch.invalidate(registry);epoch.synchronize(&firstWorld,true,registry);require(!epoch.acceptsSaveName("KenshiProbe_test"));
    snapshotChecks();
    commitFollowChecks();
    identityOriginChecks();
    std::cout<<"{\"passed\":true,\"checks\":"<<checks<<",\"toolset\":\"v100 x64\"}\n";return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
