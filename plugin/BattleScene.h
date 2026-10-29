// SPDX-License-Identifier: GPL-3.0-only
#pragma once
#include <kenshi/RootObjectFactory.h>
#include <kenshi/GameData.h>
#include <kenshi/combat/CombatClass.h>
#include <kenshi/FactionRelations.h>

namespace battle {
static std::string prefix;
static unsigned long generation=0;
static int requested=0,spawned=0;

static void clear(){prefix.clear();requested=spawned=0;}

static Value health(Character* c){
    Value out=Value::obj(),parts=Value::arr();int count=c->medical.getPartCount();
    int limit=std::max(0,std::min(count,8));bool finite=true;double flesh=0,stun=0,maximum=0;
    for(int i=0;i<limit;++i){MedicalSystem::HealthPartStatus* part=c->medical.getPart((unsigned __int64)i);Value values=Value::arr();
        if(!part){finite=false;parts.array.push_back(Value());continue;}
        float raw[3]={part->flesh,part->fleshStun,part->_maxHealth};
        for(int k=0;k<3;++k){bool valid=_finite(raw[k])!=0;finite=finite&&valid;values.array.push_back(valid?Value(raw[k]):Value());}
        if(_finite(raw[0]))flesh+=raw[0];if(_finite(raw[1]))stun+=raw[1];if(_finite(raw[2]))maximum+=raw[2];parts.array.push_back(values);
    }
    out.object["part_count"]=Value((double)count);out.object["sampled_count"]=Value((double)limit);out.object["complete"]=Value::flag(count>=0&&count<=8&&finite);out.object["parts_flesh_stun_max"]=parts;
    out.object["flesh_sum"]=finite?Value(flesh):Value();out.object["flesh_stun_sum"]=finite?Value(stun):Value();out.object["max_health_sum"]=finite?Value(maximum):Value();return out;
}

static Value combatTarget(Character* c){
    CombatClass* combat=c->getCombatClass();if(!combat)return Value();
    Value out=Value::obj(),id=Value::arr();hand target=combat->_getAttackTarget();bool null=target.isNull();
    // Null SDK handles may leave irrelevant numeric fields uninitialised.
    if(!null){id.array.push_back(Value((double)target.type));id.array.push_back(Value((double)target.container));id.array.push_back(Value((double)target.containerSerial));id.array.push_back(Value((double)target.index));id.array.push_back(Value((double)target.serial));}
    out.object["handle"]=null?Value():id;out.object["sword_state"]=Value((double)combat->getCombatState());Character* victim=null?0:target.getCharacter();out.object["resolved"]=Value::flag(victim!=0);
    if(victim){std::string name=victim->getName();out.object["name"]=Value(name);out.object["position"]=vectorJSON(victim->getPosition());out.object["in_cohort"]=Value::flag(!prefix.empty()&&name.compare(0,prefix.size(),prefix)==0);
        Faction* own=c->getFaction();Faction* other=victim->getFaction();out.object["faction"]=other?Value(other->getName()):Value();out.object["same_faction"]=Value::flag(own&&other&&own==other);
        if(own&&other&&own!=other&&own->relations){out.object["enemy"]=Value::flag(own->relations->isEnemy(other));float relation=own->relations->getFactionRelation(other);out.object["relation"]=_finite(relation)?Value(relation):Value();}
    }return out;
}

static Value state(GameWorld* world){
    Value out=Value::obj(),members=Value::arr();int engaged=0,underAttack=0,dead=0,unconscious=0;
    const ogre_unordered_set<Character*>::type& list=world->getCharacterUpdateList();
    if(!prefix.empty())for(ogre_unordered_set<Character*>::type::const_iterator i=list.begin();i!=list.end();++i){
        Character* c=*i;if(!c)continue;std::string name=c->getName();if(name.compare(0,prefix.size(),prefix)!=0)continue;
        Value row=Value::obj();row.object["name"]=Value(name);row.object["position"]=vectorJSON(c->getPosition());
        bool fighting=c->isInCombatMode(true,true),under=c->isLiterallyUnderMeleeAttackRightNowForSure(),d=c->isDead(),u=c->isUnconcious();
        engaged+=fighting;underAttack+=under;dead+=d;unconscious+=u;
        row.object["combat_mode"]=Value::flag(fighting);row.object["under_melee_attack"]=Value::flag(under);row.object["dead"]=Value::flag(d);row.object["unconscious"]=Value::flag(u);row.object["is_player"]=Value::flag(c->isPlayerCharacter());
        row.object["health"]=health(c);row.object["attack_target"]=combatTarget(c);
        float blood=c->medical.blood;row.object["blood"]=_finite(blood)?Value(blood):Value();members.array.push_back(row);
    }
    out.object["active"]=Value::flag(!prefix.empty());out.object["prefix"]=Value(prefix);out.object["requested_entities"]=Value((double)requested);out.object["spawned_entities"]=Value((double)spawned);out.object["matched_loaded"]=Value((double)members.array.size());out.object["combat_mode_count"]=Value((double)engaged);out.object["under_melee_attack_count"]=Value((double)underAttack);out.object["dead_count"]=Value((double)dead);out.object["unconscious_count"]=Value((double)unconscious);out.object["members"]=members;return out;
}

struct Model {GameData* data;Faction* faction;float age;Model():data(0),faction(0),age(0){}};

static Model resolveModel(GameWorld* world,const std::string& sid,const std::string& factionName){
    Model result;
    const ogre_unordered_set<Character*>::type& list=world->getCharacterUpdateList();
    for(ogre_unordered_set<Character*>::type::const_iterator i=list.begin();i!=list.end();++i){
        Character* c=*i;if(!c||c->isPlayerCharacter()||c->isDead())continue;GameData* gd=c->getGameData();Faction* faction=c->getFaction();
        if(!gd||gd->type!=CHARACTER||gd->stringID!=sid||!faction||faction==world->player->getFaction())continue;
        if(!factionName.empty()&&faction->getName()!=factionName)continue;
        if(result.faction&&result.faction!=faction)throw std::runtime_error("template faction is ambiguous; specify a unique faction_name");
        result.data=gd;result.faction=faction;result.age=c->getAge();
    }
    if(!result.data||!result.faction||!_finite(result.age)||result.age<0)throw std::runtime_error("a loaded non-player CHARACTER template and faction are required");return result;
}

static Value factionInventory(const std::vector<Faction*>& candidates){
    std::map<std::string,Faction*> unique;for(unsigned int i=0;i<candidates.size();++i)if(candidates[i])unique[candidates[i]->getName()]=candidates[i];
    Value out=Value::obj(),rows=Value::arr();std::vector<Faction*> selected;for(std::map<std::string,Faction*>::const_iterator i=unique.begin();i!=unique.end()&&selected.size()<16;++i)selected.push_back(i->second);
    for(unsigned int i=0;i<selected.size();++i){Value row=Value::obj(),enemies=Value::arr();Faction* faction=selected[i];row.object["name"]=Value(faction->getName());
        if(faction->relations)for(unsigned int j=0;j<selected.size();++j)if(i!=j&&faction->relations->isEnemy(selected[j]))enemies.array.push_back(Value(selected[j]->getName()));
        row.object["relations_available"]=Value::flag(faction->relations!=0);row.object["enemy_names"]=enemies;rows.array.push_back(row);
    }out.object["factions"]=rows;out.object["total_factions_in_returned_characters"]=Value((double)unique.size());out.object["truncated"]=Value::flag(unique.size()>selected.size());return out;
}

static Value prepare(GameWorld* world,const std::string& sid,int pairs,const std::string& factionName,const std::string& opponentSid,const std::string& opponentFaction){
    if(!prefix.empty())throw std::runtime_error("reload the disposable save before preparing another battle");
    if(!world->theFactory||!world->player)throw std::runtime_error("factory or player unavailable");
    Model models[2];models[0]=resolveModel(world,sid,factionName);models[1]=opponentSid.empty()?models[0]:resolveModel(world,opponentSid,opponentFaction);
    bool enemies=false;float relationAB=0,relationBA=0;
    if(!opponentSid.empty()){
        Faction* a=models[0].faction;Faction* b=models[1].faction;
        if(a==b||!a->relations||!b->relations||!a->relations->isEnemy(b)||!b->relations->isEnemy(a))throw std::runtime_error("opponent factions must already be mutual enemies; relations were not changed");
        enemies=true;relationAB=a->relations->getFactionRelation(b);relationBA=b->relations->getFactionRelation(a);
    }
    const lektor<Character*>& players=world->player->getAllPlayerCharacters();if(!players.size()||!players[0])throw std::runtime_error("player anchor unavailable");
    Ogre::Vector3 anchor=players[0]->getPosition();
    if(!_finite(anchor.x)||!_finite(anchor.y)||!_finite(anchor.z))throw std::runtime_error("invalid scene anchor");
    std::vector<Ogre::Vector3> positions;
    for(int i=0;i<pairs*2;++i){Ogre::Vector3 p=anchor;p.x+=20.0f+5.0f*(i/2);p.z+=(i%2)?2.0f:-2.0f;
        // createRandomCharacter accepts world coordinates and grounds the actor.
        // findValidSpawnPos has undocumented search semantics; do not substitute
        // its output for this bounded, leader-relative placement.
        if(!_finite(p.x)||!_finite(p.y)||!_finite(p.z))throw std::runtime_error("invalid battle position");positions.push_back(p);
    }
    std::ostringstream token;token<<"KenshiProbeFight_"<<++generation<<"_";prefix=token.str();requested=pairs*2;spawned=0;
    Value out=Value::obj(),rows=Value::arr();std::vector<Character*> actors;double started=now();
    for(int i=0;i<requested;++i){
        if(now()-started>3000)break;
        Model& model=models[i%2];RootObject* root=world->theFactory->createRandomCharacter(model.faction,positions[i],0,model.data,0,model.age);if(!root)break;
        Character* c=static_cast<Character*>(root);std::ostringstream name;name<<prefix<<i;c->setName(name.str());actors.push_back(c);++spawned;
        if(c->isPlayerCharacter())throw std::runtime_error("unexpected player enlistment; reload the disposable save");
        Ogre::Vector3 actual=c->getPosition();double dx=actual.x-anchor.x,dz=actual.z-anchor.z;
        if(!_finite(actual.x)||!_finite(actual.y)||!_finite(actual.z)||dx*dx+dz*dz>40000.0)throw std::runtime_error("spawned actor too far from anchor; reload the disposable save");
        c->separateIntoMyOwnSquad(true);c->clearAllAIGoals();Value row=Value::obj();row.object["name"]=Value(name.str());row.object["requested_position"]=vectorJSON(positions[i]);row.object["position"]=vectorJSON(actual);row.object["template_id"]=Value(model.data->stringID);row.object["faction"]=Value(model.faction->getName());row.object["age"]=Value(model.age);rows.array.push_back(row);
    }
    bool complete=spawned==requested;
    if(complete)for(int i=0;i<requested;i+=2){actors[i]->addGoal(UNPROVOKED_FOCUSED_MELEE_ATTACK,actors[i+1]);actors[i+1]->addGoal(UNPROVOKED_FOCUSED_MELEE_ATTACK,actors[i]);}
    out.object["prepared"]=Value::flag(complete);out.object["prefix"]=Value(prefix);out.object["template_id"]=Value(sid);out.object["faction"]=Value(models[0].faction->getName());out.object["mutual_enemies_verified"]=Value::flag(enemies);if(enemies){out.object["relation_ab"]=_finite(relationAB)?Value(relationAB):Value();out.object["relation_ba"]=_finite(relationBA)?Value(relationBA):Value();}out.object["requested_entities"]=Value((double)requested);out.object["spawned_entities"]=Value((double)spawned);out.object["setup_ms"]=Value(now()-started);out.object["members"]=rows;return out;
}
}
