// SPDX-License-Identifier: GPL-3.0-only
#pragma once
// Scene setup commands (probe 0.11.0). docs/scene-setup.md freezes their names,
// parameter keys, gate rows and refusal texts; change them only with a new
// contract version, never by renaming here.
//
// KenshiLib headers only bind declarations to game addresses. The three engine
// calls below (RootObjectFactory::createRandomSquad, FactionRelations::setRelation,
// Character::healCompletely) are declared only, so every mutating reply carries
// a before/after read-back. Nothing here saves.
//
// Validation order of every command: unknown keys, gate, parameter values,
// lookups and semantic refusals, engine call. Included after OracleState.h;
// all functions run on the game thread (drainCommands or loopHook).
#include <kenshi/RootObjectFactory.h>
#include <kenshi/GameData.h>
#include <kenshi/GameDataManager.h>
#include <kenshi/FactionRelations.h>
#include <kenshi/Platoon.h>
#include <set>

namespace oracle {
static const unsigned int setupMaximumPlayers=64,setupMaximumMembers=64,setupMaximumSpawnRows=32,setupMaximumRelationRows=100;
// Load lifecycle (Q1). requested*: the last accepted load_save. It completes on
// the first ready frame where the epoch accepts it and SaveManager::getCurrentGame()
// equals it (Observed equal in local runs; see docs/scene-setup.md); loaded* then holds that
// load and the epoch serial it completed in. A failed load never completes, and
// a UI load changes the serial, which closes the gate without clearing worldMutated.
struct SetupLoad {
    bool pending,requestedAllow,loadedAllow;std::string requestedSave,loadedSave;unsigned long loadedEpoch;
    SetupLoad():pending(false),requestedAllow(false),loadedAllow(false),loadedEpoch(0){}
};
static SetupLoad setupLoad;
// Set immediately before a mutating engine call, even if the call then fails;
// cleared only when a probe load completes.
static bool worldMutated=false;
inline void acceptSetupLoad(const std::string& save,bool allow){setupLoad.pending=true;setupLoad.requestedSave=save;setupLoad.requestedAllow=allow;setupLoad.loadedSave.clear();setupLoad.loadedAllow=false;setupLoad.loadedEpoch=0;}
inline void observeSetupLoad(GameWorld* world){
    // Never throws. synchronizeWorld first, so the recorded serial is the one of
    // this ready frame and not of an earlier unavailable read.
    if(!setupLoad.pending)return;
    try{
        synchronizeWorld(world);if(!worldReady(world)||lastRequestedSave!=setupLoad.requestedSave||!savedOriginEpoch.acceptsSaveName(setupLoad.requestedSave))return;
        SaveManager* saves=SaveManager::getSingleton();if(!saves||saves->getCurrentGame()!=setupLoad.requestedSave)return;
    }catch(...){return;}
    setupLoad.pending=false;setupLoad.loadedSave=setupLoad.requestedSave;setupLoad.loadedAllow=setupLoad.requestedAllow;setupLoad.loadedEpoch=savedOriginEpoch.serial();worldMutated=false;
}
inline bool setupProbeLoadCurrent(){return !setupLoad.pending&&!setupLoad.loadedSave.empty()&&setupLoad.loadedEpoch==savedOriginEpoch.serial()&&lastRequestedSave==setupLoad.loadedSave&&savedOriginEpoch.acceptsSaveName(setupLoad.loadedSave);}
struct SetupRefusal {
    const char* code;const char* message;
    SetupRefusal():code(0),message(0){}
    SetupRefusal(const char* c,const char* m):code(c),message(m){}
};
// Gate rows in contract order: G1, G2, G3, M1, M2 (mutations), G4, G5 (saved
// origins: census, spawn, heal). More than 64 player characters is an
// engine-internal safety failure, not a gate row: requireSetupGate raises it
// after the gate passes, so gate.refusal never carries it.
inline SetupRefusal setupRefusal(GameWorld* world,bool mutation,bool origins){
    if(!worldReady(world))return SetupRefusal("world_not_ready","world is unavailable or a save is loading");
    if(!setupProbeLoadCurrent())return SetupRefusal("not_allowed","scene setup requires a world loaded by the probe's load_save");
    if(!setupLoad.loadedAllow)return SetupRefusal("not_allowed","scene setup was not enabled: load the save with allow_setup:true");
    if(mutation&&(active()||!world->isPaused()))return SetupRefusal("invalid_request","scene setup mutations require a paused world and no run_until");
    // Q4: OptionsHolder::autosave, absent options refused. Whether that flag is the effective autosave state is Unknown.
    if(mutation&&(!::options||::options->autosave))return SetupRefusal("not_allowed","scene setup mutations are refused while autosave is enabled");
    if(!world->player||!world->player->getAllPlayerCharacters().size())return SetupRefusal("state_unavailable","player unavailable");
    if(origins&&!savedOrigins.prepared)return SetupRefusal("origin_context_required","scene setup requires prepared saved origins");
    return SetupRefusal();
}
inline const lektor<Character*>& setupPlayers(GameWorld* world){if(!world->player)throw Error("state_unavailable","player unavailable");const lektor<Character*>& list=world->player->getAllPlayerCharacters();if(!list.size())throw Error("state_unavailable","player unavailable");if(list.size()>setupMaximumPlayers)throw Error("state_unavailable","more than 64 player characters");return list;}
inline void requireSetupGate(GameWorld* world,bool mutation,bool origins){synchronizeWorld(world);SetupRefusal r=setupRefusal(world,mutation,origins);if(r.code)throw Error(r.code,r.message);setupPlayers(world);}
inline Value setupRefusalValue(const SetupRefusal& r){if(!r.code)return Value();Value v=Value::obj();v.object["code"]=Value(std::string(r.code));v.object["message"]=Value(std::string(r.message));return v;}
inline Value setupGate(GameWorld* world){
    bool current=setupProbeLoadCurrent();Value v=Value::obj();
    v.object["open"]=Value::flag(worldReady(world)&&current&&setupLoad.loadedAllow);v.object["probe_loaded_save"]=current?Value(setupLoad.loadedSave):Value();v.object["allow_setup"]=Value::flag(current&&setupLoad.loadedAllow);
    v.object["epoch"]=Value((double)savedOriginEpoch.serial());v.object["refusal"]=setupRefusalValue(setupRefusal(world,false,true));v.object["mutation_refusal"]=setupRefusalValue(setupRefusal(world,true,true));return v;
}
inline Value setupWorld(GameWorld* world){Value v=Value::obj();v.object["elapsed_seconds"]=Value(gameSeconds(world));v.object["paused"]=Value::flag(world->isPaused());return v;}
inline void setupCommon(GameWorld* world,Value& out){out.object["saved"]=Value::flag(false);out.object["world_mutated"]=Value::flag(true);out.object["world_after"]=setupWorld(world);out.object["gate"]=setupGate(world);}
inline std::string buildCommit(){std::string c(KENSHI_PROBE_BUILD_COMMIT_TEXT);return c.size()==40&&c.find_first_not_of("0123456789abcdef")==std::string::npos?c:std::string("unknown");}
// World-readiness indicators for ping, reads only, each made only where the
// probe already makes it: isLoadingFromASaveGame on an initialized world that is
// not resetting; isPaused and ZoneManager::isLoading only when worldReady holds.
// Otherwise null, and the reason names the first failing term. The meaning of
// the raw zone_manager_is_loading value is Unknown.
inline Value worldReadiness(GameWorld* world){
    Value v=Value::obj();bool present=world!=0,pending,pausePending;{Guard g;pending=loadPending;pausePending=loadPausePending;}v.object["world_present"]=Value::flag(present);
    v.object["initialized"]=present?Value::flag(world->initialized):Value();v.object["game_resetting"]=present?Value::flag(world->gameResetting):Value();
    const char* base=!present?"world_unavailable":!world->initialized?"world_not_initialized":world->gameResetting?"game_resetting":0;bool fromSave=!base&&world->isLoadingFromASaveGame();
    v.object["loading_from_save"]=base?Value():Value::flag(fromSave);v.object["loading_from_save_unavailable_reason"]=base?Value(std::string(base)):Value();
    v.object["load_pending"]=Value::flag(pending);v.object["load_pause_pending"]=Value::flag(pausePending);bool ready=worldReady(world);v.object["world_ready"]=Value::flag(ready);
    const char* why=base?base:fromSave?"loading_from_save":ready?0:pending?"load_pending":pausePending?"load_pause_pending":"world_not_ready";const char* zoneWhy=why?why:!world->zoneMgr?"zone_manager_unavailable":0;
    v.object["paused"]=why?Value():Value::flag(world->isPaused());v.object["paused_unavailable_reason"]=why?Value(std::string(why)):Value();
    v.object["zone_manager_is_loading"]=zoneWhy?Value():Value((double)world->zoneMgr->isLoading());v.object["zone_manager_unavailable_reason"]=zoneWhy?Value(std::string(zoneWhy)):Value();
    v.object["frame"]=Value((double)frame);return v;
}
inline double setupDistanceXZ(const Ogre::Vector3& a,const Ogre::Vector3& b){double dx=(double)a.x-b.x,dz=(double)a.z-b.z;return sqrt(dx*dx+dz*dz);}
inline std::string setupCanonicalId(const std::string& raw){return raw.empty()?raw:savedOrigins.canonicalId(raw);}
inline Value setupCharacterRow(Character* c){
    Value row=Value::obj();row.object["id"]=optionalId(setupCanonicalId(objectId(c)));row.object["template_id"]=optionalId(dataId(c->getGameData()));row.object["faction_id"]=optionalId(factionId(c->getFaction()));
    row.object["squad_id"]=optionalId(setupCanonicalId(squadId(c)));row.object["position"]=position(c->getPosition());row.object["dead"]=Value::flag(c->isDead());row.object["unconscious"]=Value::flag(c->isUnconcious());return row;
}
// setup_heal shape: parts in body order (part index), id <record id>:<side>.
// strict (setup_heal) refuses what the reply cannot state; a spawn row degrades
// to null instead (including an invalid part count, since the squad already
// exists), and a negative or non-finite maximum to max:null.
inline Value setupMedical(Character* c,bool strict){
    MedicalSystem* m=c->getMedical();if(!m){if(strict)throw Error("state_unavailable","medical system unavailable");return Value();}
    int count=m->getPartCount();if(count<0||count>256){if(strict)throw Error("state_unavailable","invalid health part count");return Value();}Value parts=Value::arr();
    for(int i=0;i<count;++i){MedicalSystem::HealthPartStatus* part=m->getPart((unsigned __int64)i);const char* side=part?sideName(part->side):0;std::string id=part?dataId(part->data):std::string();
        if(!side||id.empty()){if(strict)throw Error("state_unavailable","medical system unavailable");return Value();}
        bool maximum=_finite(part->_maxHealth)&&part->_maxHealth>=0;if(!maximum&&strict)throw Error("state_unavailable","medical system unavailable");
        Value row=Value::obj();row.object["id"]=Value(id+":"+side);row.object["flesh"]=finiteOrNull(part->flesh);row.object["stun"]=finiteOrNull(part->fleshStun);row.object["max"]=maximum?finiteOrNull(part->_maxHealth):Value();parts.array.push_back(row);}
    Value out=Value::obj();out.object["parts"]=parts;out.object["blood"]=finiteOrNull(m->blood);out.object["dead"]=Value::flag(c->isDead());out.object["unconscious"]=Value::flag(c->isUnconcious());return out;
}
// Exact GameData string id; a duplicated id is an engine-internal failure.
inline Faction* setupFaction(GameWorld* world,const std::string& id){
    const lektor<Faction*>* all=world->factionMgr?world->factionMgr->getAllFactions():0;if(!all||all->size()>512)throw Error("state_unavailable","faction list unavailable");Faction* found=0;
    for(unsigned int i=0;i<all->size();++i){Faction* f=(*all)[i];if(f&&factionId(f)==id){if(found&&found!=f)throw Error("state_unavailable","faction id is ambiguous");found=f;}}
    if(!found)throw Error("not_found","faction not found");return found;
}

// --- setup_info (gate G1 only) ---------------------------------------------
inline Value setupInfo(GameWorld* world,const Value& p){
    keys(p,0,0);requireWorld(world);bool current=setupProbeLoadCurrent();SaveManager* saves=SaveManager::getSingleton();Value out=Value::obj();
    out.object["gate"]=setupGate(world);out.object["current_save"]=saves?Value(saves->getCurrentGame()):Value();out.object["probe_loaded_save"]=current?Value(setupLoad.loadedSave):Value();out.object["world_mutated"]=Value::flag(worldMutated);
    // autosave_configured is the same options flag natively; the probe cannot block UI save keys.
    out.object["autosave_enabled"]=::options?Value::flag(::options->autosave):Value();out.object["autosave_configured"]=::options?Value::flag(::options->autosave):Value();
    out.object["player_save_requests_blocked"]=Value::flag(false);out.object["squad_size"]=Value();return out;
}

// --- setup_area_census (read-only; paused or running) ----------------------
// The dump_state character set (update list, death list, active-platoon
// members) within a horizontal radius, inclusive, sorted by distance then id.
struct SetupCensusRow {double distance;std::string id;Character* character;};
struct SetupCensusLess {bool operator()(const SetupCensusRow& a,const SetupCensusRow& b) const {return a.distance!=b.distance?a.distance<b.distance:a.id<b.id;}};
inline Value setupAreaCensus(GameWorld* world,const Value& p){
    const char* allowed[]={"center","radius","limit"};keys(p,allowed,3);requireSetupGate(world,false,true);
    Ogre::Vector3 center=readPosition(p,"center");double radius=number(p,"radius",0.1,20000),limit=number(p,"limit",1,100);if(floor(limit)!=limit)throw Error("invalid_request","limit must be an integer");
    Loaded loaded=loadedObjects(world);refreshSavedOriginBindings(loaded);std::vector<SetupCensusRow> found;std::set<std::string> ids;
    // A non-finite position cannot be placed inside or outside the radius: an internal failure, never a skipped row.
    for(Characters::const_iterator i=loaded.characters.begin();i!=loaded.characters.end();++i){Ogre::Vector3 at=i->second->getPosition();position(at);double d=setupDistanceXZ(at,center);if(d<=radius){SetupCensusRow row={d,setupCanonicalId(i->first),i->second};if(!ids.insert(row.id).second)throw Error("origin_identity_ambiguous","census contains duplicate character IDs");found.push_back(row);}}
    std::sort(found.begin(),found.end(),SetupCensusLess());
    Value rows=Value::arr();int alive=0,dead=0,unconscious=0,player=0;
    for(size_t i=0;i<found.size();++i){Character* c=found[i].character;bool d=c->isDead(),u=c->isUnconcious(),own=c->isPlayerCharacter();dead+=d;unconscious+=(!d&&u);alive+=(!d&&!u);player+=own;
        if(rows.array.size()<(size_t)limit){Value row=setupCharacterRow(c);row.object["id"]=Value(found[i].id);row.object["is_player"]=Value::flag(own);row.object["distance_xz"]=Value(found[i].distance);rows.array.push_back(row);}}
    Value out=Value::obj();out.object["center"]=vectorJSON(center);out.object["radius"]=Value(radius);out.object["characters"]=rows;out.object["count"]=Value((double)found.size());out.object["truncated"]=Value::flag(found.size()>rows.array.size());
    out.object["alive_count"]=Value((double)alive);out.object["dead_count"]=Value((double)dead);out.object["unconscious_count"]=Value((double)unconscious);out.object["player_count"]=Value((double)player);
    out.object["gate"]=setupGate(world);out.object["world"]=setupWorld(world);return out;
}

// --- setup_spawn_squad -----------------------------------------------------
// GameDataContainer::getData(sid) is declared only; its record type is checked.
// createRandomSquad is declared only: count, randomness and immediate versus
// queued creation are Unknown, as are its null home/town/area/container/platoon
// arguments. The probe passes size multiplier 1.0 and squad type roaming;
// whether the engine also applies settings.cfg inside the call is Unknown.
inline void setupRequireNearPlayer(GameWorld* world,const Ogre::Vector3& pos){
    const lektor<Character*>& list=setupPlayers(world);
    for(unsigned int i=0;i<list.size();++i){Character* c=list[i];if(!c||c->isDead())continue;Ogre::Vector3 at=c->getPosition();position(at);if(setupDistanceXZ(at,pos)<=2000)return;}
    throw Error("invalid_request","spawn position must be within 2000 units (horizontal) of a player character");
}
inline Value setupSpawnSquad(GameWorld* world,const Value& p){
    const char* allowed[]={"template_id","faction_id","position","max_count","permanent"};keys(p,allowed,5);requireSetupGate(world,true,true);
    std::string sid=text(p,"template_id",128),fid=text(p,"faction_id",128);Ogre::Vector3 pos=readPosition(p,"position");
    double count=number(p,"max_count",1,16);if(floor(count)!=count)throw Error("invalid_request","max_count must be an integer");bool permanent=p.object.count("permanent")?flag(p,"permanent"):false;
    GameData* squad=world->gamedata.getData(sid);if(!squad)throw Error("not_found","template not found");if(squad->type!=SQUAD_TEMPLATE)throw Error("invalid_request","template is not a SQUAD_TEMPLATE record");
    Faction* faction=setupFaction(world,fid);if(faction==world->player->getFaction())throw Error("invalid_request","spawning into the player faction is refused");
    setupRequireNearPlayer(world,pos);if(!world->theFactory)throw Error("state_unavailable","factory unavailable");
    std::set<Character*> before;{Loaded loaded=loadedObjects(world);for(Characters::const_iterator i=loaded.characters.begin();i!=loaded.characters.end();++i)before.insert(i->second);}
    Value out=Value::obj();out.object["world_before"]=setupWorld(world);hand none;
    worldMutated=true;double started=now();
    Platoon* created=world->theFactory->createRandomSquad(faction,pos,0,(int)count,0,squad,0,0,0,permanent,none,0,1.0f,SQ_ROAMING,false);
    double elapsed=now()-started;Loaded loaded=loadedObjects(world);refreshSavedOriginBindings(loaded);size_t fresh=0;
    for(Characters::const_iterator i=loaded.characters.begin();i!=loaded.characters.end();++i)if(!before.count(i->second)){++fresh;if(i->second->isPlayerCharacter())throw Error("state_unavailable","unexpected player enlistment; reload the save");}
    ActivePlatoon* platoon=created?created->getActivePlatoon():0;Value members=Value::arr();lektor<RootObject*>* things=platoon?platoon->getThings():0;
    if(things){if(things->size()>setupMaximumMembers)throw Error("state_unavailable","squad has more than 64 members");
        for(unsigned int i=0;i<things->size();++i){RootObject* o=(*things)[i];if(!o||o->getHandle().type!=CHARACTER)continue;Character* c=static_cast<Character*>(o);
            if(c->isPlayerCharacter())throw Error("state_unavailable","unexpected player enlistment; reload the save");Value row=setupCharacterRow(c);row.object["medical"]=setupMedical(c,false);members.array.push_back(row);}}
    out.object["template_id"]=Value(sid);out.object["faction_id"]=Value(fid);out.object["position"]=vectorJSON(pos);out.object["max_count"]=Value(count);out.object["permanent"]=Value::flag(permanent);
    out.object["size_multiplier"]=Value(1.0);out.object["squad_type"]=Value(std::string("roaming"));out.object["returned_squad_id"]=optionalId(created?setupCanonicalId(objectId(created)):std::string());out.object["returned_members"]=members;
    out.object["new_loaded_count"]=Value((double)fresh);out.object["new_loaded_truncated"]=Value::flag(fresh>setupMaximumSpawnRows);out.object["rng_key"]=Value();
    Value detail=Value::obj();detail.object["call"]=Value(std::string("RootObjectFactory::createRandomSquad"));detail.object["call_ms"]=finiteOrNull(elapsed);out.object["engine_detail"]=detail;setupCommon(world,out);return out;
}

// --- setup_set_relation ----------------------------------------------------
// FactionRelations::setRelation(Faction* who, float) is called on
// source->relations with who=target, and no war-flag setter is called. It is
// declared only; one set changed both directions (Observed: 2 cells, then 0).
// Whether it changes a war state internally is Unknown, and no war-flag reader
// is verified, so at_war is null. Reads use getFactionRelation and isEnemy, as
// dump_state and BattleScene.h do; the whole matrix is diffed.
struct SetupMatrix {std::vector<Faction*> factions;std::vector<float> values;std::vector<char> enemies;};
inline SetupMatrix setupReadMatrix(GameWorld* world){
    SetupMatrix m;const lektor<Faction*>* all=world->factionMgr?world->factionMgr->getAllFactions():0;if(!all||all->size()>512)throw Error("state_unavailable","faction list unavailable");
    for(unsigned int i=0;i<all->size();++i)if((*all)[i])m.factions.push_back((*all)[i]);size_t n=m.factions.size();m.values.assign(n*n,0.0f);m.enemies.assign(n*n,2);
    for(size_t i=0;i<n;++i){FactionRelations* r=m.factions[i]->relations;if(!r)continue;for(size_t j=0;j<n;++j){if(i==j)continue;m.values[i*n+j]=r->getFactionRelation(m.factions[j]);m.enemies[i*n+j]=r->isEnemy(m.factions[j])?1:0;}}
    return m;
}
inline Value setupRelationCell(Faction* a,Faction* b){Value v=Value::obj();FactionRelations* r=a->relations;v.object["relation"]=r?finiteOrNull(r->getFactionRelation(b)):Value();v.object["is_enemy"]=r?Value::flag(r->isEnemy(b)):Value();v.object["at_war"]=Value();return v;}
inline Value setupEnemy(char e){return e==2?Value():Value::flag(e==1);}
inline Value setupMatrixChanges(const SetupMatrix& before,const SetupMatrix& after,size_t& total){
    Value rows=Value::arr();total=0;if(before.factions!=after.factions)throw Error("state_unavailable","faction list changed during the command");size_t n=before.factions.size();
    for(size_t i=0;i<n;++i)for(size_t j=0;j<n;++j){size_t k=i*n+j;bool same=before.enemies[k]==after.enemies[k]&&(before.values[k]==after.values[k]||(!_finite(before.values[k])&&!_finite(after.values[k])));if(same)continue;++total;if(rows.array.size()>=setupMaximumRelationRows)continue;
        Value row=Value::obj();row.object["source_id"]=optionalId(factionId(before.factions[i]));row.object["target_id"]=optionalId(factionId(before.factions[j]));row.object["relation_before"]=finiteOrNull(before.values[k]);row.object["relation_after"]=finiteOrNull(after.values[k]);
        row.object["is_enemy_before"]=setupEnemy(before.enemies[k]);row.object["is_enemy_after"]=setupEnemy(after.enemies[k]);row.object["at_war_before"]=Value();row.object["at_war_after"]=Value();rows.array.push_back(row);}
    return rows;
}
inline Value setupSetRelation(GameWorld* world,const Value& p){
    const char* allowed[]={"source_id","target_id","value"};keys(p,allowed,3);requireSetupGate(world,true,false);
    std::string sourceId=text(p,"source_id",128),targetId=text(p,"target_id",128);float value=(float)number(p,"value",-100,100);
    Faction* source=setupFaction(world,sourceId);Faction* target=setupFaction(world,targetId);if(source==target)throw Error("invalid_request","source and target must differ");
    if(!source->relations||!target->relations)throw Error("state_unavailable","faction relations unavailable");
    Value out=Value::obj();out.object["world_before"]=setupWorld(world);SetupMatrix before=setupReadMatrix(world);Value forward=Value::obj(),backward=Value::obj();forward.object["before"]=setupRelationCell(source,target);backward.object["before"]=setupRelationCell(target,source);
    worldMutated=true;source->relations->setRelation(target,value);
    forward.object["after"]=setupRelationCell(source,target);backward.object["after"]=setupRelationCell(target,source);SetupMatrix after=setupReadMatrix(world);size_t total=0;
    out.object["source_id"]=Value(sourceId);out.object["target_id"]=Value(targetId);out.object["value"]=Value((double)value);out.object["source_to_target"]=forward;out.object["target_to_source"]=backward;
    out.object["changes"]=setupMatrixChanges(before,after,total);out.object["changed_cells"]=Value((double)total);out.object["changes_truncated"]=Value::flag(total>setupMaximumRelationRows);out.object["faction_count"]=Value((double)before.factions.size());
    Value detail=Value::obj();detail.object["call"]=Value(std::string("source.relations->setRelation(target, value)"));detail.object["at_war_unavailable_reason"]=Value(std::string("no war-flag reader is verified on the original"));out.object["engine_detail"]=detail;setupCommon(world,out);return out;
}

// --- setup_heal ------------------------------------------------------------
// Character::healCompletely is declared only (its RVA lies in the MedicalSystem
// range). Whether it clears the unconscious flag at once is Unknown.
inline Character* setupLoadedCharacter(const Loaded& loaded,const std::string& id){
    // Malformed, unknown, non-character and unloaded ids share one refusal;
    // saved-origin ambiguity stays an engine failure.
    SavedHandleId parsed;try{parsed=parseSavedHandleId(id);}catch(const Error&){throw Error("not_found","character is not loaded");}
    if(parsed.type!=(unsigned int)CHARACTER)throw Error("not_found","character is not loaded");
    Characters::const_iterator found=loaded.characters.find(loadedInputId(loaded,id,(unsigned int)CHARACTER));if(found==loaded.characters.end())throw Error("not_found","character is not loaded");return found->second;
}
inline Value setupHeal(GameWorld* world,const Value& p){
    const char* allowed[]={"character_id"};keys(p,allowed,1);requireSetupGate(world,true,true);std::string requested=text(p,"character_id",200);
    Loaded loaded=loadedObjects(world);refreshSavedOriginBindings(loaded);Character* c=setupLoadedCharacter(loaded,requested);
    if(c->isDead())throw Error("invalid_request","character is dead");Value before=setupMedical(c,true);
    Value out=Value::obj();out.object["world_before"]=setupWorld(world);
    worldMutated=true;c->healCompletely();
    out.object["character_id"]=Value(requested);out.object["before"]=before;out.object["after"]=setupMedical(c,true);setupCommon(world,out);return out;
}

// setup_teleport_character is reserved and answered like any unknown command.
inline Value setupCommand(GameWorld* world,const std::string& command,const Value& p){
    if(command=="setup_info")return setupInfo(world,p);
    if(command=="setup_area_census")return setupAreaCensus(world,p);
    if(command=="setup_spawn_squad")return setupSpawnSquad(world,p);
    if(command=="setup_set_relation")return setupSetRelation(world,p);
    if(command=="setup_heal")return setupHeal(world,p);
    throw std::runtime_error("unknown command");
}
}
