// SPDX-License-Identifier: GPL-3.0-only
#pragma once
#include "json.h"
#include <iomanip>
#include <cctype>

// Engine-independent canonical JSON. The state contract uses the same binary64
// quantisation in Python: floor(abs(x) * 1e6 + .5), ties away from zero.
namespace oracle {
struct Error : std::runtime_error {
    std::string code;
    Error(const char* c,const std::string& message):std::runtime_error(message),code(c){}
};
inline const json::Value& field(const json::Value& p,const char* name){
    if(p.type!=json::Value::OBJECT||!p.object.count(name))throw Error("invalid_request",std::string("missing field: ")+name);
    return p.at(name);
}
inline double number(const json::Value& p,const char* name,double low,double high){
    const json::Value& v=field(p,name);
    if(v.type!=json::Value::NUMBER||!_finite(v.number)||v.number<low||v.number>high)throw Error("invalid_request",std::string("invalid number: ")+name);
    return v.number;
}
inline std::string text(const json::Value& p,const char* name,size_t maximum=512){
    const json::Value& v=field(p,name);
    if(v.type!=json::Value::STRING||v.str.empty()||v.str.size()>maximum||v.str.find('\0')!=std::string::npos)throw Error("invalid_request",std::string("invalid string: ")+name);
    return v.str;
}
inline bool flag(const json::Value& p,const char* name){
    const json::Value& v=field(p,name);if(v.type!=json::Value::BOOL)throw Error("invalid_request",std::string("invalid boolean: ")+name);return v.boolean;
}
inline void keys(const json::Value& p,const char* const* allowed,size_t n){
    if(p.type!=json::Value::OBJECT)throw Error("invalid_request","params must be object");
    for(std::map<std::string,json::Value>::const_iterator i=p.object.begin();i!=p.object.end();++i){
        bool found=false;for(size_t j=0;j<n;++j)if(i->first==allowed[j])found=true;
        if(!found)throw Error("invalid_request",std::string("unknown parameter: ")+i->first);
    }
}
inline void appendNumber(std::string& out,double value){
    if(!_finite(value)||fabs(value)>1e9)throw Error("state_unavailable","state number is non-finite or outside canonical range");
    double magnitude=floor(fabs(value)*1000000.0+0.5);
    unsigned __int64 q=(unsigned __int64)magnitude;
    if(value<0&&q)out+='-';
    std::ostringstream whole;whole.imbue(std::locale::classic());whole<<(q/1000000);out+=whole.str();
    unsigned int fraction=(unsigned int)(q%1000000);
    if(fraction){std::ostringstream digits;digits.imbue(std::locale::classic());digits<<std::setw(6)<<std::setfill('0')<<fraction;std::string s=digits.str();while(!s.empty()&&s[s.size()-1]=='0')s.erase(s.size()-1);out+='.';out+=s;}
}
inline void appendCanonicalQuoted(std::string& out,const std::string& value){
    // Match Python json.dumps(..., ensure_ascii=False), including its five
    // short control escapes. The legacy wire serializer remains unchanged.
    out+='"';const char* hex="0123456789abcdef";
    for(size_t i=0;i<value.size();++i){unsigned char c=value[i];
        if(c=='"'||c=='\\'){out+='\\';out+=(char)c;}
        else if(c=='\b')out+="\\b";else if(c=='\t')out+="\\t";else if(c=='\n')out+="\\n";else if(c=='\f')out+="\\f";else if(c=='\r')out+="\\r";
        else if(c<32){out+="\\u00";out+=hex[c>>4];out+=hex[c&15];}
        else out+=(char)c;
    }out+='"';
}
inline void appendCanonical(std::string& out,const json::Value& v){
    if(v.type==json::Value::NUMBER){appendNumber(out,v.number);return;}
    if(v.type==json::Value::NIL){out+="null";return;}
    if(v.type==json::Value::BOOL){out+=v.boolean?"true":"false";return;}
    if(v.type==json::Value::STRING){appendCanonicalQuoted(out,v.str);return;}
    if(v.type==json::Value::OBJECT){out+='{';bool first=true;for(std::map<std::string,json::Value>::const_iterator i=v.object.begin();i!=v.object.end();++i){if(!first)out+=',';first=false;appendCanonicalQuoted(out,i->first);out+=':';appendCanonical(out,i->second);}out+='}';return;}
    out+='[';for(size_t i=0;i<v.array.size();++i){if(i)out+=',';appendCanonical(out,v.array[i]);}out+=']';
}
inline std::string canonical(const json::Value& v){std::string out;out.reserve(16384);appendCanonical(out,v);out+='\n';return out;}
inline json::Value finiteOrNull(double value){return _finite(value)&&fabs(value)<=1e9?json::Value(value):json::Value();}
// State 0.3 slave_state. KenshiLib Enums.h SlaveStateEnum: 0 NOT_SLAVE,
// 1 IS_SLAVE, 2 ESCAPING_SLAVE, 3 EX_SLAVE. Any other raw value is unknown and
// gives null, never not_slave.
inline json::Value slaveStateName(int raw){
    switch(raw){case 0:return json::Value(std::string("not_slave"));case 1:return json::Value(std::string("slave"));case 2:return json::Value(std::string("escaping_slave"));case 3:return json::Value(std::string("ex_slave"));default:return json::Value();}
}
// State 0.4 in_something. KenshiLib Character.h UseStuffState: 0 IN_NOTHING,
// 1 IN_BED, 2 IN_PRISON. Any other raw value is unknown and gives null.
inline json::Value inSomethingName(int raw){
    switch(raw){case 0:return json::Value(std::string("nothing"));case 1:return json::Value(std::string("bed"));case 2:return json::Value(std::string("prison"));default:return json::Value();}
}
// State 0.4 carrying. Not carrying gives nothing whatever the hand holds. A
// carrying flag with a null hand is unknown (null); a character hand gives
// character and any other non-null hand gives other.
inline json::Value carryingName(bool carrying,bool handNull,bool characterHand){
    if(!carrying)return json::Value(std::string("nothing"));if(handNull)return json::Value();
    return json::Value(std::string(characterHand?"character":"other"));
}
// State 0.4 stats keys: KenshiLib Enums.h StatsEnumerated order, name without
// STAT_ in lowercase, without STAT_HIVEMEDIC and STAT_VET (they share medic)
// and STAT_WEAPONS and STAT_SURVIVAL (no stored stat behind the number).
static const size_t statKeyCount=34;
static const char* const statKeys[statKeyCount]={
    "strength","melee_attack","labouring","science","engineering","robotics","smithing_weapon","smithing_armour",
    "medic","thieving","turrets","farming","cooking","stealth","athletics","dexterity","melee_defence","toughness",
    "assassination","swimming","perception","katanas","sabres","hackers","heavyweapons","blunt","martialarts",
    "masscombat","dodge","polearms","crossbows","friendly_fire","lockpicking","smithing_bow"};
// State 0.5 goal priority. KenshiLib AI/AITaskSystem.h taskPriority: 0
// TP_JUST_ACTION, 1 TP_FLUFF, 2 TP_NON_URGENT, 3 TP_URGENT, 4 TP_OBEDIENCE. Any
// other raw value (TP_MAX_SIZE included) is unknown and gives null.
inline json::Value goalPriorityName(int raw){
    switch(raw){case 0:return json::Value(std::string("just_action"));case 1:return json::Value(std::string("fluff"));case 2:return json::Value(std::string("non_urgent"));case 3:return json::Value(std::string("urgent"));case 4:return json::Value(std::string("obedience"));default:return json::Value();}
}
// State 0.5 goal rows: KenshiLib Enums.h TaskType, NULL_TASK 0 to
// BASH_GATE_PLAYER_ORDER 290 (OracleState.h checks both against the enum).
static const int goalNullTaskRow=0;
static const int goalLastTaskRow=290;
// State 0.5 goal of one AI task system, by member reads only: currentGoal
// (TaskMatch: taskData, subject) and currentGoalPriority. No engine function is
// called. A null task system or taskData, a row outside 0 to 290, NULL_TASK or a
// row without a name gives null; Task_Blank rows are goals and keep their name.
// A priority outside 0 to 4 gives priority null and keeps the other keys. The
// target is encoded by handId and is null for an empty id, as order.target_id.
// Templates so that the native tests can use fake objects of the same shape.
template<class Tasks,class Hand>
inline json::Value goalFromTaskSystem(const Tasks* tasks,const char* (*rowName)(int),std::string (*handId)(const Hand&)){
    if(!tasks||!tasks->currentGoal.taskData)return json::Value();
    const int row=(int)tasks->currentGoal.taskData->key;
    if(row<goalNullTaskRow||row>goalLastTaskRow||row==goalNullTaskRow)return json::Value();
    const char* name=rowName(row);if(!name||!*name)return json::Value();
    json::Value out=json::Value::obj();out.object["type"]=json::Value(std::string(name));
    out.object["priority"]=goalPriorityName((int)tasks->currentGoalPriority);
    const std::string target=handId(tasks->currentGoal.subject);
    out.object["target_id"]=target.empty()?json::Value():json::Value(target);return out;
}
template<class Mind,class Hand>
inline json::Value goalFromAI(const Mind* ai,const char* (*rowName)(int),std::string (*handId)(const Hand&)){
    return ai?goalFromTaskSystem(ai->taskSystemAI,rowName,handId):json::Value();
}
inline void validateFilename(const std::string& name){
    if(name.size()<6||name.size()>105||name.substr(name.size()-5)!=".json"||name.substr(0,name.size()-5).find_first_not_of("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")!=std::string::npos)
        throw Error("invalid_request","filename must be a simple name ending in .json");
    std::string stem=name.substr(0,name.size()-5);for(size_t i=0;i<stem.size();++i)stem[i]=(char)toupper((unsigned char)stem[i]);
    if(stem=="CON"||stem=="PRN"||stem=="AUX"||stem=="NUL"||(stem.size()==4&&(stem.substr(0,3)=="COM"||stem.substr(0,3)=="LPT")&&stem[3]>='0'&&stem[3]<='9'))throw Error("invalid_request","reserved filename");
}
}
