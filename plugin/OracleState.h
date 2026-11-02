// SPDX-License-Identifier: GPL-3.0-only
#pragma once
#include "OracleFormat.h"
#include "OracleSpeedControl.h"
#include <kenshi/RaceData.h>
#include <kenshi/Platoon.h>
#include <kenshi/CharBody.h>
#include <kenshi/Tasker.h>
#include <kenshi/Enums.h>
#include <kenshi/StateBroadcastData.h>
#include <kenshi/CharStats.h>
#include <ogre/OgreSceneNode.h>
#include <set>
#include "OracleTaskNames.h"
#include "OracleHandleIds.h"
#include "OracleSavedOrigins.h"
#include "OracleCameraFollow.h"

// All functions that accept engine objects run exclusively in drainCommands or
// loopHook. publishFile below receives only an owned JSON tree, never pointers.
namespace oracle {
static const char* schemaVersion="0.4";
static const char* const stateSchemaVersions[]={"0.1","0.2","0.3","0.4"};
static const size_t stateSchemaVersionCount=sizeof(stateSchemaVersions)/sizeof(stateSchemaVersions[0]);
inline Value supportedSchemaVersions(){Value out=Value::arr();for(size_t i=0;i<stateSchemaVersionCount;++i)out.array.push_back(Value(std::string(stateSchemaVersions[i])));return out;}
inline void requireStateSchemaVersion(const std::string& version){
    for(size_t i=0;i<stateSchemaVersionCount;++i)if(version==stateSchemaVersions[i])return;
    throw Error("invalid_request","schema_version must be 0.1, 0.2, 0.3 or 0.4");
}
inline std::string requestedSchemaVersion(const Value& params){
    std::string version=params.object.count("schema_version")?text(params,"schema_version",8):std::string(schemaVersion);
    requireStateSchemaVersion(version);return version;
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
// seenFactions keeps every faction pointer met in the census, even when two share an id.
struct Loaded {Characters characters;Squads squads;Factions factions;std::set<Faction*> seenFactions;};
inline void addCharacter(Loaded& loaded,Character* c){
    if(!c)return;std::string id=objectId(c);if(id.empty())throw Error("state_unavailable","loaded character has no handle");
    Characters::iterator old=loaded.characters.find(id);if(old!=loaded.characters.end()&&old->second!=c)throw Error("state_unavailable","duplicate character identity");loaded.characters[id]=c;
    ActivePlatoon* activePlatoon=c->getPlatoon();if(activePlatoon&&activePlatoon->me){std::string sid=objectId(activePlatoon->me);if(sid.empty())throw Error("state_unavailable","loaded squad has no handle");loaded.squads[sid]=activePlatoon->me;}
    Faction* f=c->getFaction();std::string fid=factionId(f);if(!fid.empty()){loaded.factions[fid]=f;loaded.seenFactions.insert(f);}
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
            for(unsigned int i=0;i<factions->size();++i){Faction* f=(*factions)[i];if(!f)continue;std::string fid=factionId(f);if(!fid.empty()){loaded.factions[fid]=f;loaded.seenFactions.insert(f);}
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
// State 0.4 health parts add bandage, splint and wear (MedicalSystem.h
// HealthPartStatus bandaging 0x48, juryRigging 0x4C, wearDamage 0x50), member
// reads on the part the existing 0.1 path already resolved. The SDK headers must
// keep the documented layout; this does not prove it against the game binary.
typedef char PartBandagingAt48[offsetof(MedicalSystem::HealthPartStatus,bandaging)==0x48&&sizeof(((MedicalSystem::HealthPartStatus*)0)->bandaging)==4?1:-1];
typedef char PartJuryRiggingAt4C[offsetof(MedicalSystem::HealthPartStatus,juryRigging)==0x4C&&sizeof(((MedicalSystem::HealthPartStatus*)0)->juryRigging)==4?1:-1];
typedef char PartWearDamageAt50[offsetof(MedicalSystem::HealthPartStatus,wearDamage)==0x50&&sizeof(((MedicalSystem::HealthPartStatus*)0)->wearDamage)==4?1:-1];
inline Value health(Character* c,bool partCare=false){
    MedicalSystem* med=c->getMedical();if(!med)return Value();int count=med->getPartCount();if(count<0||count>256)throw Error("state_unavailable","invalid health part count");
    std::map<std::string,Value> parts;for(int i=0;i<count;++i){MedicalSystem::HealthPartStatus* part=med->getPart((unsigned __int64)i);if(!part||!part->data)return Value();
        const char* side=sideName(part->side);std::string id=dataId(part->data);if(!side||id.empty())return Value();id+=":";id+=side;
        if(parts.count(id))throw Error("state_unavailable","duplicate health-part identity");Value row=Value::obj();row.object["id"]=Value(id);row.object["current"]=finiteOrNull(part->flesh);row.object["stun"]=finiteOrNull(part->fleshStun);row.object["maximum"]=part->_maxHealth>=0?finiteOrNull(part->_maxHealth):Value();
        if(partCare){row.object["bandage"]=finiteOrNull(part->bandaging);row.object["splint"]=finiteOrNull(part->juryRigging);row.object["wear"]=finiteOrNull(part->wearDamage);}parts[id]=row;
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
// State 0.3: member reads only, no engine call on the character or its
// StateBroadcastData (Character.h stateBroadcast 0x1A0; StateBroadcastData.h
// _slaveState 0x0, isSlaveOf 0xE0). The owner pointer is dereferenced only
// after it is found, by pointer comparison, among every faction pointer the
// census met (two pointers sharing an id are both kept); the id then comes from factionId exactly as factions[].id does.
inline void addSlaveFields(Value& row,Character* c,const std::set<Faction*>& registered){
    // The SDK headers must keep the documented layout; this does not prove it against the game binary.
    typedef char BroadcastAt1A0[offsetof(Character,stateBroadcast)==0x1A0?1:-1];
    typedef char SlaveStateAt0[offsetof(StateBroadcastData,_slaveState)==0&&sizeof(SlaveStateEnum)==4?1:-1];
    typedef char SlaveOwnerAtE0[offsetof(StateBroadcastData,isSlaveOf)==0xE0?1:-1];
    row.object["slave_state"]=Value();row.object["slave_owner_faction_id"]=Value();
    StateBroadcastData* broadcast=c->stateBroadcast;if(!broadcast)return;
    row.object["slave_state"]=slaveStateName((int)broadcast->_slaveState);
    Faction* owner=broadcast->isSlaveOf;
    if(owner&&registered.count(owner))row.object["slave_owner_faction_id"]=optionalId(factionId(owner));
}
// State 0.4: member reads only, no engine call on the character, its
// MedicalSystem, its CharStats or the squad's Ownerships. Offsets are the SDK
// headers' (Character.h, MedicalSystem.h, CharStats.h, Platoon.h); the checks
// below do not prove them against the game binary and no value has been read in
// game (Unknown).
#define ORACLE_MEMBER_AT(check,type,member,offset,size) typedef char check[offsetof(type,member)==(offset)&&sizeof(((type*)0)->member)==(size)?1:-1]
ORACLE_MEMBER_AT(StatsAt450,Character,stats,0x450,8);
ORACLE_MEMBER_AT(MedicalAt458,Character,medical,0x458,sizeof(MedicalSystem));
ORACLE_MEMBER_AT(InSomethingAt2F8,Character,inSomething,0x2F8,4);
ORACLE_MEMBER_AT(IsCarryingAt348,Character,isCarryingSomething,0x348,1);
ORACLE_MEMBER_AT(CarryingObjectAt380,Character,carryingObject,0x380,sizeof(hand));
ORACLE_MEMBER_AT(BeingCarriedAt3D4,Character,_isBeingCarried,0x3D4,1);
ORACLE_MEMBER_AT(HungerAt60,MedicalSystem,hunger,0x60,4);
ORACLE_MEMBER_AT(FedAt64,MedicalSystem,fed,0x64,4);
ORACLE_MEMBER_AT(BloodAt70,MedicalSystem,blood,0x70,4);
ORACLE_MEMBER_AT(BleedRateAt78,MedicalSystem,currentBleedRate,0x78,4);
ORACLE_MEMBER_AT(Sub50KOAt162,MedicalSystem,sub50KO,0x162,1);
ORACLE_MEMBER_AT(BloodlossTraumaAt163,MedicalSystem,bloodlossTrauma,0x163,1);
ORACLE_MEMBER_AT(OwnershipsAt148,Platoon,ownerships,0x148,sizeof(Ownerships));
ORACLE_MEMBER_AT(MoneyAt88,Ownerships,money,0x88,4);
// One entry per statKeys entry (OracleFormat.h), same order; each member's
// offset is checked below against the contract table.
struct StatMember {float CharStats::* member;};
static const StatMember statMembers[]={
    {&CharStats::_strength},{&CharStats::__meleeAttack},{&CharStats::labouring},{&CharStats::science},{&CharStats::engineer},{&CharStats::robotics},
    {&CharStats::weaponSmith},{&CharStats::armourSmith},{&CharStats::medic},{&CharStats::thieving},{&CharStats::turrets},{&CharStats::farming},
    {&CharStats::cooking},{&CharStats::stealth},{&CharStats::_athletics},{&CharStats::_dexterity},{&CharStats::_meleeDefence},{&CharStats::_toughness},
    {&CharStats::assassin},{&CharStats::swimming},{&CharStats::perception},{&CharStats::katanas},{&CharStats::sabres},{&CharStats::hackers},
    {&CharStats::heavyWeapons},{&CharStats::blunt},{&CharStats::unarmed},{&CharStats::massCombat},{&CharStats::dodging},{&CharStats::polearms},
    {&CharStats::bows},{&CharStats::friendlyFire},{&CharStats::lockpicking},{&CharStats::bowSmith}};
typedef char StatMembersMatchKeys[sizeof(statMembers)/sizeof(statMembers[0])==statKeyCount?1:-1];
ORACLE_MEMBER_AT(StrengthAt80,CharStats,_strength,0x80,4);
ORACLE_MEMBER_AT(MeleeAttackAt120,CharStats,__meleeAttack,0x120,4);
ORACLE_MEMBER_AT(LabouringAtE4,CharStats,labouring,0xE4,4);
ORACLE_MEMBER_AT(ScienceAtE0,CharStats,science,0xE0,4);
ORACLE_MEMBER_AT(EngineerAtCC,CharStats,engineer,0xCC,4);
ORACLE_MEMBER_AT(RoboticsAtDC,CharStats,robotics,0xDC,4);
ORACLE_MEMBER_AT(WeaponSmithAtD0,CharStats,weaponSmith,0xD0,4);
ORACLE_MEMBER_AT(ArmourSmithAtD4,CharStats,armourSmith,0xD4,4);
ORACLE_MEMBER_AT(MedicAt98,CharStats,medic,0x98,4);
ORACLE_MEMBER_AT(ThievingAtAC,CharStats,thieving,0xAC,4);
ORACLE_MEMBER_AT(TurretsAt114,CharStats,turrets,0x114,4);
ORACLE_MEMBER_AT(FarmingAtE8,CharStats,farming,0xE8,4);
ORACLE_MEMBER_AT(CookingAtEC,CharStats,cooking,0xEC,4);
ORACLE_MEMBER_AT(StealthAtA4,CharStats,stealth,0xA4,4);
ORACLE_MEMBER_AT(AthleticsAt94,CharStats,_athletics,0x94,4);
ORACLE_MEMBER_AT(DexterityAt88,CharStats,_dexterity,0x88,4);
ORACLE_MEMBER_AT(MeleeDefenceAt124,CharStats,_meleeDefence,0x124,4);
ORACLE_MEMBER_AT(ToughnessAt90,CharStats,_toughness,0x90,4);
ORACLE_MEMBER_AT(AssassinAtB8,CharStats,assassin,0xB8,4);
ORACLE_MEMBER_AT(SwimmingAtA8,CharStats,swimming,0xA8,4);
ORACLE_MEMBER_AT(PerceptionAt8C,CharStats,perception,0x8C,4);
ORACLE_MEMBER_AT(KatanasAtF8,CharStats,katanas,0xF8,4);
ORACLE_MEMBER_AT(SabresAtFC,CharStats,sabres,0xFC,4);
ORACLE_MEMBER_AT(HackersAt100,CharStats,hackers,0x100,4);
ORACLE_MEMBER_AT(HeavyWeaponsAt108,CharStats,heavyWeapons,0x108,4);
ORACLE_MEMBER_AT(BluntAt104,CharStats,blunt,0x104,4);
ORACLE_MEMBER_AT(UnarmedAt10C,CharStats,unarmed,0x10C,4);
ORACLE_MEMBER_AT(MassCombatAt9C,CharStats,massCombat,0x9C,4);
ORACLE_MEMBER_AT(DodgingAtF0,CharStats,dodging,0xF0,4);
ORACLE_MEMBER_AT(PolearmsAt118,CharStats,polearms,0x118,4);
ORACLE_MEMBER_AT(BowsAt110,CharStats,bows,0x110,4);
ORACLE_MEMBER_AT(FriendlyFireAtF4,CharStats,friendlyFire,0xF4,4);
ORACLE_MEMBER_AT(LockpickingAtB0,CharStats,lockpicking,0xB0,4);
ORACLE_MEMBER_AT(BowSmithAtD8,CharStats,bowSmith,0xD8,4);
#undef ORACLE_MEMBER_AT
inline Value statsObject(const CharStats* stats){
    if(!stats)return Value();Value out=Value::obj();
    for(size_t i=0;i<statKeyCount;++i)out.object[statKeys[i]]=finiteOrNull(stats->*statMembers[i].member);return out;
}
inline Value medicalObject(const MedicalSystem& medical){
    Value out=Value::obj();out.object["blood"]=finiteOrNull(medical.blood);out.object["bleed_rate"]=finiteOrNull(medical.currentBleedRate);
    out.object["hunger"]=finiteOrNull(medical.hunger);out.object["fed"]=finiteOrNull(medical.fed);
    out.object["coma"]=Value::flag(medical.sub50KO);out.object["blood_loss_trauma"]=Value::flag(medical.bloodlossTrauma);return out;
}
inline void addState04Fields(Value& row,Character* c){
    // Character::medical is embedded, so it is present whenever the character is.
    row.object["medical"]=medicalObject(c->medical);
    row.object["stats"]=statsObject(c->stats);
    row.object["in_something"]=inSomethingName((int)c->inSomething);
    // carrying_id is encoded by handleId exactly as order.target_id is, and
    // canonicalizeSnapshotOrigins applies the same saved-origin rule to both.
    const hand& carried=c->carryingObject;const std::string carriedId=handleId(carried);
    row.object["carrying"]=carryingName(c->isCarryingSomething,carriedId.empty(),carried.type==CHARACTER);
    const Value& kind=row.object["carrying"];
    row.object["carrying_id"]=kind.type==Value::STRING&&kind.str=="character"?Value(carriedId):Value();
    row.object["being_carried"]=Value::flag(c->_isBeingCarried);
}
inline Value squadMoney(Platoon* squad){
    const int money=squad->ownerships.money;return money>=-1000000000&&money<=1000000000?Value((double)money):Value();
}
inline Value snapshot(GameWorld* world,const std::string& version="0.1"){
    requireStateSchemaVersion(version);
    requireWorld(world);if(active())throw Error("busy","wait for run_until to complete before taking a checkpoint");
    if(!world->isPaused())throw Error("invalid_request","pause the game before dump_state");savedOrigins.requirePrepared();Loaded loaded=loadedObjects(world);refreshSavedOriginBindings(loaded);Value out=Value::obj();out.object["schema_version"]=Value(version);out.object["clock"]=clock(world);
    Value characters=Value::arr(),squads=Value::arr(),factions=Value::arr(),relations=Value::arr();std::map<std::string,std::vector<std::string> > memberIds;
    const bool additive=version!="0.1",v04=version=="0.4",slaves=version=="0.3"||v04;const std::set<Faction*>& registered=loaded.seenFactions;
    for(Characters::const_iterator i=loaded.characters.begin();i!=loaded.characters.end();++i){Character* c=i->second;Value row=Value::obj();row.object["id"]=Value(i->first);row.object["name"]=Value(c->getName());RaceData* race=c->getRace();row.object["race_id"]=optionalId(race?dataId(race->data):std::string());row.object["faction_id"]=optionalId(factionId(c->getFaction()));std::string sid=squadId(c);row.object["squad_id"]=optionalId(sid);if(!sid.empty())memberIds[sid].push_back(i->first);row.object["position"]=position(c->getPosition());row.object["state"]=Value(std::string(c->isDead()?"dead":c->isUnconcious()?"unconscious":"alive"));row.object["health"]=health(c,v04);row.object["order"]=order(c);
        if(additive){
            row.object["identity_origin"]=savedOrigins.hasSavedOrigin(i->first)?Value(std::string("saved")):Value();
            // An unresolved saved origin never proves generation. The town's
            // data ID/active HAND does not prove its level placement identity.
            // TODO(ORACLE-TOWN-PLACEMENT): verify Town::instanceID.uid against
            // the saved placement collection before assigning cross-engine IDs.
            row.object["current_town_id"]=Value();row.object["town_assignment"]=Value();
            row.object["in_combat"]=Value::flag(c->isInCombatMode(true,true));
        }
        if(slaves)addSlaveFields(row,c,registered);
        if(v04)addState04Fields(row,c);
        characters.array.push_back(row);
    }
    for(Squads::const_iterator i=loaded.squads.begin();i!=loaded.squads.end();++i){Value row=Value::obj(),members=Value::arr();row.object["id"]=Value(i->first);row.object["faction_id"]=optionalId(factionId(i->second->getFaction()));const std::vector<std::string>& ids=memberIds[i->first];for(size_t j=0;j<ids.size();++j)members.array.push_back(Value(ids[j]));row.object["members"]=members;row.object["leader_id"]=optionalId(handleId(i->second->getSquadLeader_theRealOne()));
        if(additive){
            row.object["identity_origin"]=savedOrigins.hasSavedOrigin(i->first)?Value(std::string("saved")):Value();
            row.object["template_id"]=optionalId(dataId(i->second->squadTemplate));
            row.object["origin_town_id"]=Value();
        }
        if(v04)row.object["money"]=squadMoney(i->second);
        squads.array.push_back(row);
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
