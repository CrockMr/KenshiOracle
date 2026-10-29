// SPDX-License-Identifier: GPL-3.0-only
#pragma once
#include "OracleFormat.h"
#include "OracleSpeedControl.h"
#include <kenshi/RaceData.h>
#include <kenshi/Platoon.h>
#include <kenshi/CharBody.h>
#include <kenshi/Tasker.h>
#include <ogre/OgreSceneNode.h>
#include <set>
#include "OracleTaskNames.h"
#include "OracleHandleIds.h"
#include "OracleSavedOrigins.h"
#include "OracleCameraFollow.h"

// All functions that accept engine objects run exclusively in drainCommands or
// loopHook. publishFile below receives only an owned JSON tree, never pointers.
namespace oracle {
static const char* schemaVersion="0.2";
inline Value supportedSchemaVersions(){Value out=Value::arr();out.array.push_back(Value(std::string("0.1")));out.array.push_back(Value(std::string("0.2")));return out;}
inline std::string requestedSchemaVersion(const Value& params){
    std::string version=params.object.count("schema_version")?text(params,"schema_version",8):std::string(schemaVersion);
    if(version!="0.1"&&version!="0.2")throw Error("invalid_request","schema_version must be 0.1 or 0.2");return version;
}
static std::string instanceId;
static unsigned long operationSequence=0;
static SpeedSelection selection;
static SavedOrigins savedOrigins;
static SavedOriginEpoch savedOriginEpoch;
static unsigned long savedOriginSequence=0;
static CameraRestorePending cameraRestore;
static unsigned long cameraRestoreSequence=0;
inline void invalidateSelectedSpeed(){selection.clear();}
inline void invalidateSavedOrigins(){savedOriginEpoch.invalidate(savedOrigins);cameraRestore.clear();}
inline void expectSavedOriginsLoad(const std::string& save){savedOriginEpoch.expectLoad(save,savedOrigins);cameraRestore.clear();}
inline void synchronizeWorld(GameWorld* world){
    bool ready=world&&world->initialized&&!world->gameResetting&&!world->isLoadingFromASaveGame()&&!loadPending&&!loadPausePending;
    selection.synchronize(world,ready);savedOriginEpoch.synchronize(world,ready,savedOrigins);cameraRestore.synchronize(savedOriginEpoch.serial());
}
inline void rememberSelectedSpeed(GameWorld* world,double speed,const char* source="probe_command"){
    synchronizeWorld(world);selection.remember(speed,source);
}
inline Value selectedSpeedValue(GameWorld* world){synchronizeWorld(world);return selection.known?Value(selection.speed):Value();}
struct Run {
    std::string id,status;
    double target,deadline;
    GameWorld* world;
    Run():status("cancelled"),target(0),deadline(0),world(0){}
};
static Run running;
inline bool active(){return running.status=="running";}
inline bool worldReady(GameWorld* world){return world&&world->initialized&&!world->gameResetting&&!world->isLoadingFromASaveGame()&&!loadPausePending&&!loadPending;}
inline void requireWorld(GameWorld* world){synchronizeWorld(world);if(!worldReady(world))throw Error("world_not_ready","world is unavailable or a save is loading");}
inline double gameSeconds(GameWorld* world){TimeOfDay t=world->getTimeStamp_inGameHours();double n=t.getTotalHours()*3600.0;if(!_finite(n)||n<0||n>1e9)throw Error("state_unavailable","invalid game clock");return n;}
inline Value clock(GameWorld* world){
    requireWorld(world);double seconds=gameSeconds(world),hours=seconds/3600.0;
    double day=floor(hours/24.0),hour=floor(fmod(hours,24.0)*1000000.0+0.5)/1000000.0;
    if(hour>=24){++day;hour=0;}
    Value out=Value::obj();out.object["day"]=Value(day);out.object["hour"]=Value(hour);out.object["elapsed_seconds"]=Value(seconds);
    // Both the SDK field and getter were observed to be zero while paused.
    // The neutral state records EFFECTIVE speed. Selected-speed knowledge is
    // separate control metadata, never inferred from this zero value.
    out.object["speed"]=finiteOrNull(world->getFrameSpeedMultiplier());out.object["paused"]=Value::flag(world->isPaused());return out;
}
inline std::string handleId(const hand& h){
    // Raw identity remains available for the resolver diagnostic. Snapshot
    // serialization canonicalizes only explicitly proved saved-origin aliases.
    if(h.isNull())return std::string();std::ostringstream s;s.imbue(std::locale::classic());s<<"hand:"<<(unsigned int)h.type<<':'<<h.container<<':'<<h.containerSerial<<':'<<h.index<<':'<<h.serial;return s.str();
}
inline Value optionalId(const std::string& s){return s.empty()?Value():Value(s);}
inline std::string objectId(RootObjectBase* o){return o?handleId(o->getHandle()):std::string();}
inline std::string dataId(GameData* data){return data?data->stringID:std::string();}
inline std::string factionId(Faction* faction){return faction?dataId(faction->getData()):std::string();}
inline std::string squadId(Character* c){ActivePlatoon* p=c->getPlatoon();return p&&p->me?objectId(p->me):std::string();}
inline Value position(const Ogre::Vector3& p){
    if(!_finite(p.x)||!_finite(p.y)||!_finite(p.z))throw Error("state_unavailable","invalid character position");return vectorJSON(p);
}
inline Ogre::Vector3 readPosition(const Value& p,const char* key){
    const Value& v=field(p,key);if(v.type!=Value::ARRAY||v.array.size()!=3)throw Error("invalid_request",std::string(key)+" must have three numbers");
    float a[3];for(int i=0;i<3;++i){if(v.array[i].type!=Value::NUMBER||!_finite(v.array[i].number)||fabs(v.array[i].number)>1e7)throw Error("invalid_request","invalid position coordinate");a[i]=(float)v.array[i].number;}return Ogre::Vector3(a[0],a[1],a[2]);
}
typedef std::map<std::string,Character*> Characters;
typedef std::map<std::string,Platoon*> Squads;
typedef std::map<std::string,Faction*> Factions;
struct Loaded {Characters characters;Squads squads;Factions factions;};
inline void addCharacter(Loaded& loaded,Character* c){
    if(!c)return;std::string id=objectId(c);if(id.empty())throw Error("state_unavailable","loaded character has no handle");
    Characters::iterator old=loaded.characters.find(id);if(old!=loaded.characters.end()&&old->second!=c)throw Error("state_unavailable","duplicate character identity");loaded.characters[id]=c;
    ActivePlatoon* activePlatoon=c->getPlatoon();if(activePlatoon&&activePlatoon->me){std::string sid=objectId(activePlatoon->me);if(sid.empty())throw Error("state_unavailable","loaded squad has no handle");loaded.squads[sid]=activePlatoon->me;}
    Faction* f=c->getFaction();std::string fid=factionId(f);if(!fid.empty())loaded.factions[fid]=f;
    if(loaded.characters.size()>20000)throw Error("state_unavailable","loaded character safety limit exceeded; no partial snapshot was produced");
}
inline Loaded loadedObjects(GameWorld* world){
    requireWorld(world);Loaded loaded;
    const ogre_unordered_set<Character*>::type& chars=world->getCharacterUpdateList();
    for(ogre_unordered_set<Character*>::type::const_iterator i=chars.begin();i!=chars.end();++i)addCharacter(loaded,*i);
    // Include retained dead characters and active-platoon members that need not
    // currently participate in the AI update list. These are public SDK fields.
    for(ogre_unordered_map<hand,Character*>::type::const_iterator i=world->deathParade.begin();i!=world->deathParade.end();++i)addCharacter(loaded,i->second);
    if(world->factionMgr){const lektor<Faction*>* factions=world->factionMgr->getAllFactions();
        if(factions){if(factions->size()>512)throw Error("state_unavailable","faction safety limit exceeded");
            for(unsigned int i=0;i<factions->size();++i){Faction* f=(*factions)[i];if(!f)continue;std::string fid=factionId(f);if(!fid.empty())loaded.factions[fid]=f;
                const lektor<Platoon*>* squads=f->getActivePlatoons();if(!squads)continue;if(squads->size()>10000)throw Error("state_unavailable","squad safety limit exceeded");
                for(unsigned int j=0;j<squads->size();++j){Platoon* p=(*squads)[j];if(!p)continue;ActivePlatoon* a=p->getActivePlatoon();if(!a)continue;std::string id=objectId(p);if(id.empty())throw Error("state_unavailable","active squad has no handle");loaded.squads[id]=p;
                    lektor<RootObject*>* members=a->getThings();if(!members)continue;if(members->size()>20000)throw Error("state_unavailable","squad member safety limit exceeded");
                    for(unsigned int k=0;k<members->size();++k){RootObject* object=(*members)[k];if(object&&object->getHandle().type==CHARACTER)addCharacter(loaded,static_cast<Character*>(object));}
                }
            }
        }
    }
    return loaded;
}
inline Value resolveSavedHandles(GameWorld* world,const Value& params){
    // Validate the entire request before constructing any engine handles or
    // invoking the public resolver. This command only runs in drainCommands.
    const std::vector<SavedHandleId> ids=readSavedHandleIds(params);
    requireWorld(world);if(active())throw Error("busy","wait for run_until to complete before resolving saved handles");
    if(!world->isPaused())throw Error("invalid_request","pause the game before resolve_saved_handles");
    typedef char CharacterTypeMustMatch[CHARACTER==1?1:-1];
    typedef char PlatoonTypeMustMatch[PLATOON==34?1:-1];
    Loaded loaded=loadedObjects(world);Value rows=Value::arr();
    for(size_t i=0;i<ids.size();++i){
        const SavedHandleId& id=ids[i];
        // Public util/hand.h:29,49-50; no global HandleManager is accessed.
        const hand saved(id.index,id.serial,(itemType)id.type,id.container,id.containerSerial);
        bool resolved=false;std::string currentId;
        if(id.type==(unsigned int)CHARACTER){Character* candidate=saved.getCharacter();resolved=candidate!=0;currentId=loadedPointerId(loaded.characters,candidate);}
        else{Platoon* candidate=saved.getPlatoon();resolved=candidate!=0;currentId=loadedPointerId(loaded.squads,candidate);}
        // The current ID comes from the loaded census. No method, including
        // getHandle(), is ever invoked on the resolver's candidate pointer.
        rows.array.push_back(savedHandleResolution(id,resolved,currentId));
    }
    Value out=Value::obj();out.object["resolutions"].swap(rows);return out;
}
inline void requireOriginRegistration(GameWorld* world){
    requireWorld(world);if(active())throw Error("busy","wait for run_until before registering saved origins");
    if(!world->isPaused())throw Error("invalid_request","pause the game before registering saved origins");
}
inline Value savedOriginRegistrationState(){
    Value out=Value::obj();out.object["prepared"]=Value::flag(savedOrigins.prepared);out.object["save_name"]=savedOrigins.prepared?Value(savedOrigins.saveName):Value();out.object["source_fingerprint"]=savedOrigins.prepared?Value(savedOrigins.sourceFingerprint):Value();out.object["count"]=Value((double)savedOrigins.ids.size());out.object["pending_count"]=Value((double)savedOrigins.pendingCount());out.object["expected_count"]=Value((double)savedOrigins.expected);if(!savedOrigins.token.empty())out.object["token"]=Value(savedOrigins.token);return out;
}
inline Value beginSavedOrigins(GameWorld* world,const Value& params){
    const char* allowed[]={"save_name","source_fingerprint","count"};keys(params,allowed,3);
    std::string save=text(params,"save_name",128),fingerprint=text(params,"source_fingerprint",71);double count=number(params,"count",0,(double)maximumSavedOrigins);
    if(floor(count)!=count)throw Error("invalid_request","saved origin count must be an integer");requireOriginRegistration(world);
    // getCurrentGame() is an internal saved name (for example autosave1), not
    // the directory passed to load(). Only that explicit request names source.
    if(lastRequestedSave.empty()||save!=lastRequestedSave||!savedOriginEpoch.acceptsSaveName(save))throw Error("origin_context_save_mismatch","saved origins must name the save loaded through the probe in the current world epoch");
    std::ostringstream token;token.imbue(std::locale::classic());token<<instanceId<<":origins:"<<++savedOriginSequence;
    savedOrigins.begin(save,fingerprint,(size_t)count,token.str());return savedOriginRegistrationState();
}
inline Value addSavedOrigins(GameWorld* world,const Value& params){
    const char* allowed[]={"token","ids"};keys(params,allowed,2);std::string token=text(params,"token",200);Value onlyIds=Value::obj();onlyIds.object["ids"]=field(params,"ids");const std::vector<SavedHandleId> ids=readSavedHandleIds(onlyIds);
    requireOriginRegistration(world);savedOrigins.add(token,ids);return savedOriginRegistrationState();
}
inline std::string resolvedLoadedId(const Loaded& loaded,const SavedHandleId& id){
    const hand saved(id.index,id.serial,(itemType)id.type,id.container,id.containerSerial);
    return id.type==(unsigned int)CHARACTER?loadedPointerId(loaded.characters,saved.getCharacter()):loadedPointerId(loaded.squads,saved.getPlatoon());
}
inline bool containsLoadedId(const Loaded& loaded,const std::string& id){return loaded.characters.count(id)||loaded.squads.count(id);}
inline void refreshSavedOriginBindings(SavedOrigins& next,const Loaded& loaded){
    next.requirePrepared();std::set<std::string> live;
    for(Characters::const_iterator i=loaded.characters.begin();i!=loaded.characters.end();++i)live.insert(i->first);
    for(Squads::const_iterator i=loaded.squads.begin();i!=loaded.squads.end();++i)live.insert(i->first);
    next.retainLoaded(live);
    for(size_t i=0;i<next.ids.size();++i){const SavedHandleId& saved=next.ids[i];std::string current=resolvedLoadedId(loaded,saved);
        // Full raw equality is sufficient for a retained dead object even if
        // the public resolver no longer returns it. No partial-key fallback.
        if(current.empty()&&live.count(saved.savedId))current=saved.savedId;
        if(!current.empty())next.bind(current,saved.savedId);
    }
    // A collision must fail the whole operation before publishing a new cache.
    for(std::map<std::string,std::string>::const_iterator i=next.currentToSaved.begin();i!=next.currentToSaved.end();++i)
        if(i->first!=i->second&&live.count(i->second))throw Error("origin_identity_ambiguous","a canonical saved ID collides with another loaded raw ID");
}
inline void refreshSavedOriginBindings(const Loaded& loaded){
    SavedOrigins next=savedOrigins;refreshSavedOriginBindings(next,loaded);savedOrigins.swap(next);
}
struct SavedOriginCommitProof {
    GameWorld* world;
    void operator()(SavedOrigins& candidate) const {Loaded loaded=loadedObjects(world);refreshSavedOriginBindings(candidate,loaded);}
};
inline Value commitSavedOrigins(GameWorld* world,const Value& params){
    const char* allowed[]={"token"};keys(params,allowed,1);std::string token=text(params,"token",200);requireOriginRegistration(world);
    SavedOriginCommitProof proof={world};commitSavedOriginsWithProof(savedOrigins,token,proof);return savedOriginRegistrationState();
}
inline Value savedOriginIdentitySource(){
    Value out=Value::obj();out.object["save_name"]=Value(savedOrigins.saveName);out.object["source_fingerprint"]=Value(savedOrigins.sourceFingerprint);out.object["count"]=Value((double)savedOrigins.ids.size());out.object["matched_count"]=Value((double)savedOrigins.currentToSaved.size());size_t characters=0,squads=0;
    for(std::map<std::string,std::string>::const_iterator i=savedOrigins.currentToSaved.begin();i!=savedOrigins.currentToSaved.end();++i)if(i->first!=i->second){if(parseSavedHandleId(i->first).type==(unsigned int)CHARACTER)++characters;else ++squads;}
    out.object["remapped_characters"]=Value((double)characters);out.object["remapped_squads"]=Value((double)squads);return out;
}
inline std::string loadedInputId(const Loaded& loaded,const std::string& id,unsigned int expectedType){
    SavedHandleId parsed=parseSavedHandleId(id);if(parsed.type!=expectedType)throw Error("invalid_request","handle type does not match the requested entity");
    if(containsLoadedId(loaded,id))return id;
    std::string cached=savedOrigins.prepared?savedOrigins.currentId(id):std::string();
    std::string resolved=resolvedLoadedId(loaded,parsed);
    if(!cached.empty()&&containsLoadedId(loaded,cached)){
        if(!resolved.empty()&&resolved!=cached)throw Error("origin_identity_ambiguous","saved ID resolves to a different currently loaded object");return cached;
    }
    return resolved;
}
inline const char* sideName(LeftRight side){switch(side){case SIDE_NEITHER:return "neither";case SIDE_LEFT:return "left";case SIDE_RIGHT:return "right";case SIDE_BOTH:return "both";default:return 0;}}
inline Value health(Character* c){
    MedicalSystem* med=c->getMedical();if(!med)return Value();int count=med->getPartCount();if(count<0||count>256)throw Error("state_unavailable","invalid health part count");
    std::map<std::string,Value> parts;for(int i=0;i<count;++i){MedicalSystem::HealthPartStatus* part=med->getPart((unsigned __int64)i);if(!part||!part->data)return Value();
        const char* side=sideName(part->side);std::string id=dataId(part->data);if(!side||id.empty())return Value();id+=":";id+=side;
        if(parts.count(id))throw Error("state_unavailable","duplicate health-part identity");Value row=Value::obj();row.object["id"]=Value(id);row.object["current"]=finiteOrNull(part->flesh);row.object["stun"]=finiteOrNull(part->fleshStun);row.object["maximum"]=part->_maxHealth>=0?finiteOrNull(part->_maxHealth):Value();parts[id]=row;
    }
    Value out=Value::arr();for(std::map<std::string,Value>::const_iterator i=parts.begin();i!=parts.end();++i)out.array.push_back(i->second);return out;
}
inline Value order(Character* c){
    CharBody* body=c->getBody();Tasker* task=body?body->getCurrentAction():0;if(!task)return Value();TaskType key=task->key();if(key==NULL_TASK)return Value();const char* name=taskName(key);
    // TODO(ORACLE-ORDER-ENUM): add a new public symbolic name if a later SDK
    // introduces a task outside the audited enum; never export an invented ID.
    if(!name)return Value();Value out=Value::obj();out.object["type"]=Value(std::string(name));out.object["target_id"]=optionalId(handleId(task->subject));out.object["position"]=Value();
    // Location storage is not meaningful for every Tasker. Only the explicitly
    // named movement actions expose it; unrelated dormant values stay null.
    if(key==MOVE_CUS_ORDERED||key==MOVE_ON_FREE_WILL||key==MOVE_ON_FREE_WILL_FAST){Ogre::Vector3 location=task->getLocation();if(_finite(location.x)&&_finite(location.y)&&_finite(location.z)&&fabs(location.x)<=1e9&&fabs(location.y)<=1e9&&fabs(location.z)<=1e9)out.object["position"]=vectorJSON(location);}return out;
}
inline Value snapshot(GameWorld* world,const std::string& version="0.1"){
    if(version!="0.1"&&version!="0.2")throw Error("invalid_request","schema_version must be 0.1 or 0.2");
    requireWorld(world);if(active())throw Error("busy","wait for run_until to complete before taking a checkpoint");
    if(!world->isPaused())throw Error("invalid_request","pause the game before dump_state");savedOrigins.requirePrepared();Loaded loaded=loadedObjects(world);refreshSavedOriginBindings(loaded);Value out=Value::obj();out.object["schema_version"]=Value(version);out.object["clock"]=clock(world);
    Value characters=Value::arr(),squads=Value::arr(),factions=Value::arr(),relations=Value::arr();std::map<std::string,std::vector<std::string> > memberIds;
    for(Characters::const_iterator i=loaded.characters.begin();i!=loaded.characters.end();++i){Character* c=i->second;Value row=Value::obj();row.object["id"]=Value(i->first);row.object["name"]=Value(c->getName());RaceData* race=c->getRace();row.object["race_id"]=optionalId(race?dataId(race->data):std::string());row.object["faction_id"]=optionalId(factionId(c->getFaction()));std::string sid=squadId(c);row.object["squad_id"]=optionalId(sid);if(!sid.empty())memberIds[sid].push_back(i->first);row.object["position"]=position(c->getPosition());row.object["state"]=Value(std::string(c->isDead()?"dead":c->isUnconcious()?"unconscious":"alive"));row.object["health"]=health(c);row.object["order"]=order(c);
        if(version=="0.2"){
            row.object["identity_origin"]=savedOrigins.hasSavedOrigin(i->first)?Value(std::string("saved")):Value();
            // An unresolved saved origin never proves generation. The town's
            // data ID/active HAND does not prove its level placement identity.
            // TODO(ORACLE-TOWN-PLACEMENT): verify Town::instanceID.uid against
            // the saved placement collection before assigning cross-engine IDs.
            row.object["current_town_id"]=Value();row.object["town_assignment"]=Value();
            row.object["in_combat"]=Value::flag(c->isInCombatMode(true,true));
        }characters.array.push_back(row);
    }
    for(Squads::const_iterator i=loaded.squads.begin();i!=loaded.squads.end();++i){Value row=Value::obj(),members=Value::arr();row.object["id"]=Value(i->first);row.object["faction_id"]=optionalId(factionId(i->second->getFaction()));const std::vector<std::string>& ids=memberIds[i->first];for(size_t j=0;j<ids.size();++j)members.array.push_back(Value(ids[j]));row.object["members"]=members;row.object["leader_id"]=optionalId(handleId(i->second->getSquadLeader_theRealOne()));
        if(version=="0.2"){
            row.object["identity_origin"]=savedOrigins.hasSavedOrigin(i->first)?Value(std::string("saved")):Value();
            row.object["template_id"]=optionalId(dataId(i->second->squadTemplate));
            row.object["origin_town_id"]=Value();
        }squads.array.push_back(row);
    }
    for(Factions::const_iterator i=loaded.factions.begin();i!=loaded.factions.end();++i){Value row=Value::obj();row.object["id"]=Value(i->first);row.object["name"]=Value(i->second->getName());factions.array.push_back(row);
        for(Factions::const_iterator j=loaded.factions.begin();j!=loaded.factions.end();++j){if(i==j)continue;Value relation=Value::obj();relation.object["source_id"]=Value(i->first);relation.object["target_id"]=Value(j->first);relation.object["value"]=i->second->relations?finiteOrNull(i->second->relations->getFactionRelation(j->second)):Value();relations.array.push_back(relation);}
    }
    out.object["characters"]=characters;out.object["squads"]=squads;out.object["factions"]=factions;out.object["relations"]=relations;canonicalizeSnapshotOrigins(out,savedOrigins);return out;
}
inline Value runResult(GameWorld* world){Value out=Value::obj();out.object["operation_id"]=Value(running.id);out.object["status"]=Value(running.status);out.object["target_seconds"]=Value(running.target);out.object["clock"]=worldReady(world)?clock(world):Value();return out;}
inline void stopRun(GameWorld* world,const char* status){if(active()){if(world&&world->initialized&&!world->gameResetting&&!world->isLoadingFromASaveGame())world->userPause(true);running.status=status;}}
inline void tick(GameWorld* world){
    synchronizeWorld(world);
    if(!active())return;
    if(world!=running.world||!worldReady(world)){stopRun(world,"cancelled");return;}
    if(now()>=running.deadline){stopRun(world,"timed_out");return;}
    if(gameSeconds(world)>=running.target){stopRun(world,"completed");return;}
    if(world->isPaused())stopRun(world,"cancelled");
}
inline Value startRun(GameWorld* world,const Value& p){
    const char* allowed[]={"target_seconds","timeout_seconds"};keys(p,allowed,2);requireWorld(world);if(active())throw Error("busy","run_until is already running");
    double target=number(p,"target_seconds",0,1e9),timeout=p.object.count("timeout_seconds")?number(p,"timeout_seconds",0.1,3600):120;
    if(!world->isPaused())throw Error("invalid_request","run_until must start paused");synchronizeWorld(world);double current=gameSeconds(world);
    if(current<target&&(!selection.known||selection.speed<=0))throw Error("invalid_request","selected speed is unknown; call set_game_speed with a positive speed and preserve_pause=true");
    Run next;std::ostringstream id;id.imbue(std::locale::classic());id<<instanceId<<':'<<++operationSequence;next.id=id.str();next.status=current>=target?"completed":"running";next.target=target;next.deadline=now()+timeout*1000.0;next.world=world;running=next;if(active()){world->setGameSpeed((float)selection.speed,false);world->userPause(false);}return runResult(world);
}
inline Value queryRun(GameWorld* world,const Value& p,bool cancel){const char* allowed[]={"operation_id"};keys(p,allowed,1);std::string id=text(p,"operation_id",200);if(id!=running.id||id.empty())throw Error("not_found","unknown run_until operation");if(cancel)stopRun(world,"cancelled");else tick(world);return runResult(world);}
inline Value issueOrder(GameWorld* world,const Value& p){
    const char* allowed[]={"type","character_id","squad_id","position","target_id"};keys(p,allowed,5);requireWorld(world);if(active()||!world->isPaused())throw Error("invalid_request","issue_order requires a paused checkpoint");
    std::string type=text(p,"type",16);if(type!="move"&&type!="attack")throw Error("not_implemented","only move and attack orders are implemented");
    bool one=p.object.count("character_id")!=0,squad=p.object.count("squad_id")!=0;if(one==squad)throw Error("invalid_request","provide exactly one of character_id and squad_id");
    if(type=="move"&&(!p.object.count("position")||p.object.count("target_id")))throw Error("invalid_request","move needs position and no target_id");
    if(type=="attack"&&(!p.object.count("target_id")||p.object.count("position")))throw Error("invalid_request","attack needs target_id and no position");
    std::string actor=text(p,one?"character_id":"squad_id");Ogre::Vector3 destination(0,0,0);if(type=="move")destination=readPosition(p,"position");Loaded loaded=loadedObjects(world);if(savedOrigins.prepared)refreshSavedOriginBindings(loaded);actor=loadedInputId(loaded,actor,(unsigned int)(one?CHARACTER:PLATOON));std::vector<Character*> actors;Character* target=0;
    if(type=="attack"){std::string id=loadedInputId(loaded,text(p,"target_id"),(unsigned int)CHARACTER);Characters::const_iterator found=loaded.characters.find(id);if(found==loaded.characters.end()||found->second->isDead())throw Error("not_found","attack target is not loaded and alive");target=found->second;destination=target->getPosition();}
    if(one){Characters::const_iterator found=loaded.characters.find(actor);if(found==loaded.characters.end())throw Error("not_found","character is not loaded");actors.push_back(found->second);}
    else{if(!loaded.squads.count(actor))throw Error("not_found","squad is not loaded");for(Characters::const_iterator i=loaded.characters.begin();i!=loaded.characters.end();++i)if(squadId(i->second)==actor)actors.push_back(i->second);}
    if(actors.empty())throw Error("not_found","no loaded members in requested squad");
    for(size_t i=0;i<actors.size();++i)if(actors[i]->isDead()||actors[i]==target||!actors[i]->getAI())throw Error("invalid_request","an order actor is dead, unavailable, or its own target");
    // Character.h:427 and Enums.h: MOVE_CUS_ORDERED / UNPROVOKED_FOCUSED_MELEE_ATTACK.
    for(size_t i=0;i<actors.size();++i)actors[i]->addOrder(0,type=="move"?MOVE_CUS_ORDERED:UNPROVOKED_FOCUSED_MELEE_ATTACK,target,false,true,destination);
    Value out=Value::obj();out.object["accepted"]=Value::flag(true);out.object["type"]=Value(type);out.object["affected_characters"]=Value((double)actors.size());return out;
}
inline void addCameraControl(GameWorld* world,Value& out){
    CameraClass* camera=sceneCamera(world);Ogre::SceneNode* center=camera->getCenterNode();Ogre::SceneNode* node=camera->getCameraNode();if(!center||!node)throw Error("state_unavailable","camera nodes unavailable");
    Ogre::Quaternion q=center->getOrientation();Value orientation=Value::arr();orientation.array.push_back(Value(q.w));orientation.array.push_back(Value(q.x));orientation.array.push_back(Value(q.y));orientation.array.push_back(Value(q.z));
    // The public saved-camera format uses the camera node's signed local Z,
    // not the nonnegative world-space camera/pivot distance. CameraClass.h:30,35;
    // MeitouClient docs/formats/camera.md, "Saved camera" (6b14126a).
    out.object["camera_orientation"]=orientation;out.object["camera_zoom"]=Value(node->getPosition().z);out.object["camera_node_position"]=vectorJSON(node->getPosition());out.object["selected_game_speed"]=selectedSpeedValue(world);out.object["selected_game_speed_source"]=Value(std::string(selection.source));out.object["camera_follow_id"]=optionalId(canonicalCameraFollowId(savedOrigins,handleId(camera->getFollowObject())));out.object["camera_restore_token"]=cameraRestore.active()?Value(cameraRestore.token):Value();
    out.object["camera_follow_offset"]=Value();out.object["camera_follow_position"]=Value();out.object["camera_follow_center_delta"]=Value();
    const hand& following=camera->getFollowObject();if(!following.isNull()){
        const Ogre::Vector3& offset=camera->objectCurrentlyFollowingOffset;
        if(_finite(offset.x)&&_finite(offset.y)&&_finite(offset.z)&&fabs(offset.x)<=1e7&&fabs(offset.y)<=1e7&&fabs(offset.z)<=1e7)out.object["camera_follow_offset"]=vectorJSON(offset);
        if(following.type==CHARACTER){Character* candidate=following.getCharacter();Character* loaded=0;
            // Diagnostic only: no census or pointer is cached. A public resolver
            // result is never dereferenced until membership is established.
            const ogre_unordered_set<Character*>::type& update=world->getCharacterUpdateList();
            if(candidate&&update.find(candidate)!=update.end())loaded=candidate;
            if(candidate&&!loaded)for(ogre_unordered_map<hand,Character*>::type::const_iterator i=world->deathParade.begin();i!=world->deathParade.end();++i)if(i->second==candidate){loaded=i->second;break;}
            if(loaded){Ogre::Vector3 at=loaded->getPosition();if(_finite(at.x)&&_finite(at.y)&&_finite(at.z)&&fabs(at.x)<=1e7&&fabs(at.y)<=1e7&&fabs(at.z)<=1e7){out.object["camera_follow_position"]=vectorJSON(at);Ogre::Vector3 delta=camera->getCenter()-at;if(_finite(delta.x)&&_finite(delta.y)&&_finite(delta.z)&&fabs(delta.x)<=1e7&&fabs(delta.y)<=1e7&&fabs(delta.z)<=1e7)out.object["camera_follow_center_delta"]=vectorJSON(delta);}}
        }
    }
}
inline CameraClass* requireRestoreCamera(GameWorld* world){CameraClass* camera=sceneCamera(world);if(!::options||!camera->getCenterNode()||!camera->getCameraNode())throw Error("state_unavailable","camera nodes or options unavailable");return camera;}
inline Character* cameraRestoreTarget(GameWorld* world,const CameraRestoreSpec& spec){
    if(spec.followId.empty())return 0;if(!world->isPaused())throw Error("invalid_request","pause before resolving a camera follow ID");
    Loaded loaded=loadedObjects(world);if(savedOrigins.prepared)refreshSavedOriginBindings(loaded);std::string id=loadedInputId(loaded,spec.followId,(unsigned int)CHARACTER);Characters::const_iterator found=loaded.characters.find(id);
    if(found==loaded.characters.end())throw Error("not_found","camera follow target is not a loaded character");return found->second;
    // TODO(ORACLE-CAMERA-NONCHARACTER): other follow types need an audited
    // loaded-object enumeration; never dereference a user-supplied pointer.
}
inline void applyCameraRestorePose(CameraClass* camera,const CameraRestoreSpec& spec,Character* follow){
    camera->stopFollowing();if(camera->isFreeCameraMode()!=spec.freeCamera)camera->setFreeCameraMode(spec.freeCamera);
    camera->manuallySetOrientationAndZoom(Ogre::Quaternion(spec.orientation[0],spec.orientation[1],spec.orientation[2],spec.orientation[3]),spec.zoom);
    camera->teleport(Ogre::Vector3(spec.center[0],spec.center[1],spec.center[2]));if(follow)camera->followObject(follow->getHandle());
}
inline Value cameraRestoreResult(GameWorld* world,CameraClass* camera,bool prepared,bool restored){
    Value out=Value::obj();out.object["prepared"]=Value::flag(prepared);out.object["restored"]=Value::flag(restored);out.object["camera_center"]=vectorJSON(camera->getCenter());out.object["camera_position"]=vectorJSON(camera->getCameraPos());out.object["free_camera"]=Value::flag(camera->isFreeCameraMode());out.object["edge_scrolling"]=Value::flag(::options->edgeScrolling);out.object["scene_camera_control_owned"]=Value::flag(sceneEdgeOwned);out.object["paused"]=Value::flag(world->isPaused());addCameraControl(world,out);if(prepared)out.object["token"]=Value(cameraRestore.token);return out;
}
inline Value restoreControl(GameWorld* world,const Value& params){
    // Low-level .9.3 behavior: acceptance is not a converged-restoration proof.
    CameraRestoreSpec spec=readCameraRestoreSpec(params);requireWorld(world);CameraClass* camera=requireRestoreCamera(world);Character* follow=cameraRestoreTarget(world,spec);
    stopRun(world,"cancelled");world->userPause(true);applyCameraRestorePose(camera,spec,follow);restoreSceneCamera();::options->edgeScrolling=spec.edgeScrolling;world->setGameSpeed((float)spec.speed,false);world->userPause(spec.paused);rememberSelectedSpeed(world,spec.speed);return cameraRestoreResult(world,camera,false,true);
}
inline Value prepareSceneControl(GameWorld* world,const Value& params){
    CameraRestoreSpec spec=readCameraRestoreSpec(params);requireWorld(world);if(cameraRestore.active())throw Error("camera_restore_busy","a scene-control calibration is already prepared");
    if(active()||!world->isPaused())throw Error("invalid_request","prepare_scene_control requires a paused checkpoint");CameraClass* camera=requireRestoreCamera(world);Character* follow=cameraRestoreTarget(world,spec);
    std::ostringstream id;id.imbue(std::locale::classic());id<<instanceId<<":camera:"<<++cameraRestoreSequence;CameraRestorePending next;
    next.begin(params,id.str(),savedOriginEpoch.serial(),follow?handleId(follow->getHandle()):std::string());
    // All parameters, target membership and owned JSON allocations precede any
    // game mutation. Keep the scene held while the client observes its baseline.
    controlSceneCamera();world->setGameSpeed((float)spec.speed,false);world->userPause(true);rememberSelectedSpeed(world,spec.speed);applyCameraRestorePose(camera,spec,follow);camera->objectCurrentlyFollowingOffset=Ogre::Vector3(0,0,0);cameraRestore.swap(next);return cameraRestoreResult(world,camera,true,false);
}
inline Value commitSceneControl(GameWorld* world,const Value& params){
    const char* allowed[]={"token"};keys(params,allowed,1);std::string token=text(params,"token",200);requireWorld(world);cameraRestore.require(token,savedOriginEpoch.serial());CameraRestoreSpec spec=readCameraRestoreSpec(cameraRestore.params);CameraClass* camera=requireRestoreCamera(world);
    if(active()||!world->isPaused()||!sceneEdgeOwned||::options->edgeScrolling||camera->isFreeCameraMode()!=spec.freeCamera||handleId(camera->getFollowObject())!=cameraRestore.followRaw||!selection.known||fabs(selection.speed-spec.speed)>1e-6)
        throw Error("camera_restore_state_changed","prepared camera mode, follow, pause, speed, or edge ownership changed");
    Ogre::Quaternion q=camera->getCenterNode()->getOrientation();const double observedQ[4]={q.w,q.x,q.y,q.z};double same=0,opposite=0;
    for(int i=0;i<4;++i){if(!_finite(observedQ[i]))throw Error("camera_restore_state_changed","prepared camera orientation is invalid");double a=observedQ[i]-spec.orientation[i],b=observedQ[i]+spec.orientation[i];same+=a*a;opposite+=b*b;}
    double zoom=camera->getCameraNode()->getPosition().z;if(!_finite(zoom)||fabs(zoom-spec.zoom)>1e-4||(std::min)(same,opposite)>1e-8)throw Error("camera_restore_state_changed","prepared camera orientation or zoom changed");
    Character* follow=cameraRestoreTarget(world,spec);if((follow?handleId(follow->getHandle()):std::string())!=cameraRestore.followRaw)throw Error("camera_restore_state_changed","prepared camera follow resolves to a different loaded object");
    Ogre::Vector3 calibrated(0,0,0);if(follow){Ogre::Vector3 offset=camera->objectCurrentlyFollowingOffset,observed=camera->getCenter();const double current[3]={offset.x,offset.y,offset.z},wanted[3]={spec.center[0],spec.center[1],spec.center[2]},baseline[3]={observed.x,observed.y,observed.z};float finalOffset[3];calibratedCameraFollowOffset(current,wanted,baseline,finalOffset);calibrated=Ogre::Vector3(finalOffset[0],finalOffset[1],finalOffset[2]);}
    // The native base pivot has been observed by the client across frames.
    // Apply only the measured correction, last after pose/follow setters.
    applyCameraRestorePose(camera,spec,follow);if(follow)camera->objectCurrentlyFollowingOffset=calibrated;
    restoreSceneCamera();::options->edgeScrolling=spec.edgeScrolling;world->setGameSpeed((float)spec.speed,false);world->userPause(spec.paused);rememberSelectedSpeed(world,spec.speed);cameraRestore.clear();return cameraRestoreResult(world,camera,false,true);
}
inline std::wstring widen(const std::string& text){int size=MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,text.data(),(int)text.size(),0,0);if(!size)throw Error("invalid_request","invalid UTF-8 path");std::wstring out(size,L'\0');MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,text.data(),(int)text.size(),&out[0],size);return out;}
inline std::string narrow(const std::wstring& text){int size=WideCharToMultiByte(CP_UTF8,0,text.data(),(int)text.size(),0,0,0,0);if(!size)throw Error("io_error","cannot encode path");std::string out(size,'\0');WideCharToMultiByte(CP_UTF8,0,text.data(),(int)text.size(),&out[0],size,0,0);return out;}
inline void makeDirectory(const std::wstring& path){
    DWORD attr=GetFileAttributesW(path.c_str());if(attr!=INVALID_FILE_ATTRIBUTES){if(!(attr&FILE_ATTRIBUTE_DIRECTORY)||(attr&FILE_ATTRIBUTE_REPARSE_POINT))throw Error("io_error","output directory is not a normal directory");return;}
    size_t split=path.find_last_of(L"\\/");if(split!=std::wstring::npos&&split>2)makeDirectory(path.substr(0,split));
    if(!CreateDirectoryW(path.c_str(),0)&&GetLastError()!=ERROR_ALREADY_EXISTS)throw Error("io_error","cannot create output directory");
}
inline Value publishFile(const Value& state,const std::string& filename){
    validateFilename(filename);wchar_t env[32768];DWORD size=GetEnvironmentVariableW(L"KENSHI_ORACLE_OUTPUT",env,32768);if(size>=32768)throw Error("io_error","output directory is too long");std::wstring root=size?std::wstring(env,size):std::wstring(L"oracle-dumps");
    wchar_t absolute[32768];DWORD n=GetFullPathNameW(root.c_str(),32768,absolute,0);if(!n||n>=32768)throw Error("io_error","cannot resolve output directory");root.assign(absolute,n);makeDirectory(root);std::wstring path=root+L"\\"+widen(filename);
    std::string bytes=canonical(state);if(bytes.size()>64*1024*1024)throw Error("state_unavailable","snapshot file exceeds 64 MiB safety limit");
    if(!MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,bytes.data(),(int)bytes.size(),0,0))throw Error("state_unavailable","snapshot contains invalid UTF-8");
    HANDLE file=CreateFileW(path.c_str(),GENERIC_WRITE,0,0,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,0);if(file==INVALID_HANDLE_VALUE)throw Error(GetLastError()==ERROR_FILE_EXISTS?"already_exists":"io_error","cannot create snapshot; existing files are never overwritten");
    DWORD written=0;bool okay=WriteFile(file,bytes.data(),(DWORD)bytes.size(),&written,0)&&written==bytes.size();if(okay)okay=FlushFileBuffers(file)!=FALSE;CloseHandle(file);if(!okay){DeleteFileW(path.c_str());throw Error("io_error","snapshot write failed");}
    Value out=Value::obj();out.object["path"]=Value(narrow(path));out.object["schema_version"]=state.at("schema_version");out.object["bytes"]=Value((double)bytes.size());return out;
}
}
